package com.agentworkspace.mobile.automation

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

/**
 * What the phone control panel remembers, on the phone only (files in the engine process):
 * how requests in an app were done (passed to the agent next time it works in that app), and
 * shortcuts, recorded tasks the user saved to run again without the model.
 */
internal object PhoneMemory {
    private const val TIPS = "automation/app-tips.json"
    private const val SHORTCUTS = "automation/shortcuts.json"
    private const val TIPS_PER_APP = 3
    private const val MAX_SHORTCUTS = 50

    data class Shortcut(val id: String, val name: String, val app: String?, val appLabel: String?,
        val steps: JSONArray, val created: Long) {
        fun json(): JSONObject = JSONObject().put("id", id).put("name", name).put("app", app ?: JSONObject.NULL)
            .put("app_label", appLabel ?: JSONObject.NULL).put("steps", steps).put("created", created)

        companion object {
            fun from(value: JSONObject) = Shortcut(value.getString("id"), value.getString("name"),
                value.optString("app").ifEmpty { null }.takeUnless { value.isNull("app") },
                value.optString("app_label").ifEmpty { null }.takeUnless { value.isNull("app_label") },
                value.optJSONArray("steps") ?: JSONArray(), value.optLong("created"))
        }
    }

    private fun read(context: Context, name: String): String? = runCatching {
        File(context.filesDir, name).takeIf { it.isFile && it.length() < 2_000_000 }?.readText()
    }.getOrNull()

    private fun write(context: Context, name: String, text: String) {
        val target = File(context.filesDir, name)
        target.parentFile?.mkdirs()
        val partial = File(target.path + ".partial")
        partial.writeText(text)
        check(partial.renameTo(target)) { "Could not save $name" }
    }

    // ---- How requests in an app were done -------------------------------------------------------

    /** The last few requests done in [packageName] and their steps, as one line for the agent. */
    @Synchronized
    fun tips(context: Context, packageName: String?): String? {
        if (packageName == null) return null
        val entries = runCatching { JSONObject(read(context, TIPS) ?: "{}").optJSONArray(packageName) }.getOrNull() ?: return null
        val lines = (0 until entries.length()).mapNotNull { entries.optJSONObject(it) }.map { entry ->
            val steps = entry.optJSONArray("steps") ?: JSONArray()
            "“${entry.optString("request").take(80)}”: " + (0 until steps.length()).joinToString(" → ") { steps.optString(it) }
        }
        return lines.joinToString("; ").take(1800).ifEmpty { null }
    }

    @Synchronized
    fun rememberTip(context: Context, packageName: String?, request: String?, steps: List<String>) {
        if (packageName == null || request.isNullOrBlank() || steps.isEmpty()) return
        val all = runCatching { JSONObject(read(context, TIPS) ?: "{}") }.getOrDefault(JSONObject())
        val previous = all.optJSONArray(packageName) ?: JSONArray()
        val kept = JSONArray().put(JSONObject().put("request", request.take(200))
            .put("steps", JSONArray(steps.take(20).map { it.take(60) })).put("at", System.currentTimeMillis()))
        for (index in 0 until previous.length()) {
            val entry = previous.optJSONObject(index) ?: continue
            if (kept.length() >= TIPS_PER_APP) break
            if (entry.optString("request") != request.take(200)) kept.put(entry)
        }
        all.put(packageName, kept)
        // At most a hundred apps are remembered: the oldest go.
        if (all.length() > 100) all.keys().asSequence().toList()
            .sortedBy { all.optJSONArray(it)?.optJSONObject(0)?.optLong("at") ?: 0L }
            .take(all.length() - 100).forEach { all.remove(it) }
        write(context, TIPS, all.toString())
    }

    // ---- Shortcuts --------------------------------------------------------------------------------

    @Synchronized
    fun shortcuts(context: Context): List<Shortcut> = runCatching {
        val list = JSONArray(read(context, SHORTCUTS) ?: "[]")
        (0 until list.length()).mapNotNull { index -> runCatching { Shortcut.from(list.getJSONObject(index)) }.getOrNull() }
    }.getOrDefault(emptyList())

    @Synchronized
    fun saveShortcut(context: Context, name: String, app: String?, appLabel: String?, steps: List<JSONObject>): Shortcut {
        val shortcut = Shortcut(UUID.randomUUID().toString(), name.take(40), app, appLabel, JSONArray(steps), System.currentTimeMillis())
        val list = (listOf(shortcut) + shortcuts(context)).take(MAX_SHORTCUTS)
        write(context, SHORTCUTS, JSONArray(list.map { it.json() }).toString())
        return shortcut
    }

    @Synchronized
    fun deleteShortcut(context: Context, id: String) {
        write(context, SHORTCUTS, JSONArray(shortcuts(context).filter { it.id != id }.map { it.json() }).toString())
    }

    /**
     * Adds a shortcut, or replaces the name and steps of the one with [id] (edited in the app's
     * workflow page). The steps are checked like recorded ones: known kinds and fields only.
     */
    @Synchronized
    fun putShortcut(context: Context, id: String?, name: String, app: String?, appLabel: String?, steps: JSONArray): Shortcut {
        val clean = cleanSteps(steps)
        require(clean.isNotEmpty()) { "a shortcut needs at least one step" }
        val all = shortcuts(context)
        val previous = id?.let { wanted -> all.firstOrNull { it.id == wanted } ?: throw NoSuchElementException("no such shortcut") }
        val shortcut = Shortcut(previous?.id ?: UUID.randomUUID().toString(),
            name.trim().take(40).ifEmpty { previous?.name ?: "Shortcut" },
            previous?.app ?: app, previous?.appLabel ?: appLabel, JSONArray(clean), previous?.created ?: System.currentTimeMillis())
        val list = if (previous != null) all.map { if (it.id == shortcut.id) shortcut else it }
            else (listOf(shortcut) + all).take(MAX_SHORTCUTS)
        write(context, SHORTCUTS, JSONArray(list.map { it.json() }).toString())
        return shortcut
    }

    /** Words that only ever dismiss something ("跳过 3", "以后再说", "Skip"), with or without a countdown. */
    private val POPUP_DISMISS = Regex("^(\\d+\\s*[s秒]?\\s*)?(跳过|跳过广告|关闭广告|以后再说|下次再说|暂不|暂不需要|我知道了|知道了|" +
        "skip|skip ad|close ad|not now|×|✕|╳)(\\s*\\d+\\s*[s秒]?)?$", RegexOption.IGNORE_CASE)
    /** "关闭" is also a switch's state ("蓝牙 · 关闭"): it closes something only on an icon or a button. */
    private val POPUP_CLOSE = Regex("^(关闭|close|x)$", RegexOption.IGNORE_CASE)
    private val TOGGLES = listOf("Switch", "CheckBox", "ToggleButton", "RadioButton", "CompoundButton")

    /**
     * A control that closes an ad or a popup: a recorded tap on one is optional when replayed, and
     * one in the way of a step is tapped first. Never a switch or a check box, whatever it says.
     */
    fun closesPopup(label: String?, className: String? = null): Boolean {
        val words = label?.trim() ?: return false
        val kind = className.orEmpty().substringAfterLast('.')
        if (TOGGLES.any { kind.contains(it) }) return false
        if (POPUP_DISMISS.matches(words)) return true
        return POPUP_CLOSE.matches(words) && (kind.contains("Image") || kind == "Button")
    }

    private val PACKAGE = Regex("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z0-9_]+)+")
    private val KEYS = setOf("back", "home", "recents", "notifications")
    private val DIRECTIONS = setOf("up", "down", "left", "right")

    /** Steps as AgentAccessibilityService records them (at most 60), with nothing else kept. */
    fun cleanSteps(steps: JSONArray): List<JSONObject> = (0 until minOf(steps.length(), 60)).map { index ->
        val step = steps.getJSONObject(index)
        fun words(key: String, limit: Int) = step.optString(key).takeUnless { step.isNull(key) || it.isBlank() }?.take(limit)
        fun point(value: JSONObject, x: String, y: String) =
            value.put(x, step.optInt(x).coerceIn(0, 20_000)).put(y, step.optInt(y).coerceIn(0, 20_000))
        fun spot(kind: String) = point(JSONObject().put("kind", kind), "x", "y")
            .put("label", words("label", 200) ?: JSONObject.NULL).put("class", words("class", 120) ?: JSONObject.NULL)
        when (val kind = step.getString("kind")) {
            // optional: it closed an ad when recorded; a run without that ad goes on without it.
            "tap" -> spot(kind).apply { if (step.optBoolean("optional")) put("optional", true) }
            "long" -> spot(kind)
            "type" -> spot(kind).put("text", step.getString("text").take(4096))
            "enter" -> JSONObject().put("kind", kind)
            "scroll" -> JSONObject().put("kind", kind)
                .put("direction", step.optString("direction", "down").also { require(it in DIRECTIONS) { "unknown direction" } })
            "swipe" -> point(point(JSONObject().put("kind", kind), "x", "y"), "x2", "y2")
            "launch" -> JSONObject().put("kind", kind)
                .put("package", step.getString("package").also { require(PACKAGE.matches(it)) { "invalid app package" } })
            "key" -> JSONObject().put("kind", kind).put("key", step.getString("key").also { require(it in KEYS) { "unknown key" } })
            "page" -> JSONObject().put("kind", kind).put("request", JSONObject(step.getJSONObject("request").toString()).also {
                require(it.optString("action") == "open_page") { "a page step opens a page" }
                AndroidSystemBridge.validateRequest(it)
            })
            "find" -> JSONObject().put("kind", kind)
                .put("text", (words("text", 200) ?: throw IllegalArgumentException("a find step needs words"))).put("tap", step.optBoolean("tap"))
            else -> throw IllegalArgumentException("unknown step kind")
        }
    }
}
