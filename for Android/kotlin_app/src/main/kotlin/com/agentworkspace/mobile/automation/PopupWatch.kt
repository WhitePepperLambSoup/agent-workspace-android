package com.agentworkspace.mobile.automation

import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.PowerManager
import android.os.SystemClock
import android.provider.Settings
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * Which installed app pops up by itself, for the app check (AppAudit): an app that comes to the front
 * when nobody touched anything, and a floating window that covers most of the screen over another
 * app. The accessibility service reports what it sees; only the app's id, the kind, the app that was
 * in front and the time are kept, for 7 days, on the phone. Off until the user turns it on; turning
 * it off clears the record. The service and AppAudit both run in :engine, so one copy in memory.
 */
/**
 * Whether [packageName], now in front after [fronts] (the apps in front before it, latest last),
 * got there by itself: nobody touched anything for [sinceTouchMs], the agent did nothing for
 * [sinceAgentMs], and it is not Back returning to the app before. From the home screen Back leads
 * nowhere, so an app showing up again right after the user left it for home came back by itself.
 */
internal fun jumpedToFront(
    fronts: List<String>, packageName: String, homes: Set<String>, ownApp: String, sinceTouchMs: Long, sinceAgentMs: Long,
): Boolean {
    val before = fronts.lastOrNull() ?: return false
    val back = fronts.size >= 2 && fronts[fronts.size - 2] == packageName && before !in homes
    return !back && before != ownApp && sinceTouchMs >= 2500 && sinceAgentMs >= 5000
}

object PopupWatch {
    private const val FILE = "automation/popup-watch.json"
    private const val KEEP_MS = 7L * 24 * 3600 * 1000
    private const val LIMIT = 400
    /** An action of the agent this recent explains a window appearing. */
    private const val AGENT_MS = 5000L

    private var loaded: JSONObject? = null
    private val ownApp = HashMap<String, Boolean>()
    private var homes: Set<String>? = null
    /** The apps in front, latest last: coming back to the one before is pressing Back, not a jump. */
    private val fronts = ArrayDeque<String>()
    private val overlaysShown = HashSet<String>()

    private fun file(context: Context) = File(context.filesDir, FILE)

    @Synchronized private fun state(context: Context): JSONObject = loaded ?: runCatching {
        JSONObject(file(context).readText())
    }.getOrDefault(JSONObject().put("enabled", false).put("records", JSONArray())).also { loaded = it }

    @Synchronized private fun save(context: Context) {
        val target = file(context)
        target.parentFile?.mkdirs()
        val partial = File(target.path + ".partial")
        partial.writeText(state(context).toString())
        partial.renameTo(target)
    }

    @JvmStatic fun enabled(context: Context): Boolean = state(context).optBoolean("enabled")

    @JvmStatic @Synchronized fun setEnabled(context: Context, on: Boolean) {
        val current = state(context)
        current.put("enabled", on)
        if (!on) current.put("records", JSONArray())
        fronts.clear()
        overlaysShown.clear()
        save(context)
    }

    /** The last 7 days, oldest first. */
    @JvmStatic @Synchronized fun records(context: Context): JSONArray {
        val since = System.currentTimeMillis() - KEEP_MS
        val all = state(context).optJSONArray("records") ?: JSONArray()
        return JSONArray((0 until all.length()).mapNotNull(all::optJSONObject).filter { it.optLong("at") >= since })
    }

    @Synchronized private fun record(context: Context, packageName: String, kind: String, over: String?) {
        val now = System.currentTimeMillis()
        val kept = records(context)
        // A window that flickers is one pop-up.
        val last = (0 until kept.length()).map(kept::getJSONObject).lastOrNull { it.optString("package") == packageName && it.optString("kind") == kind }
        if (last != null && now - last.optLong("at") < 10_000) return
        kept.put(JSONObject().put("package", packageName).put("kind", kind).put("over", over ?: JSONObject.NULL).put("at", now))
        val trimmed = if (kept.length() > LIMIT) JSONArray((kept.length() - LIMIT until kept.length()).map(kept::get)) else kept
        state(context).put("records", trimmed)
        save(context)
    }

    private fun keyboard(context: Context): String? =
        Settings.Secure.getString(context.contentResolver, Settings.Secure.DEFAULT_INPUT_METHOD)?.substringBefore('/')

    @Synchronized private fun homes(context: Context): Set<String> = homes
        ?: context.packageManager.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME), 0)
            .map { it.activityInfo.packageName }.toSet().also { homes = it }

    /** An app the user installed: not the phone's own, not a home screen or keyboard, not this app. */
    @Synchronized private fun installedApp(context: Context, packageName: String): Boolean = ownApp.getOrPut(packageName) {
        if (packageName == context.packageName || packageName in homes(context) || packageName == keyboard(context)) return@getOrPut false
        runCatching { context.packageManager.getApplicationInfo(packageName, 0).flags and ApplicationInfo.FLAG_SYSTEM == 0 }
            .getOrDefault(false)
    }

    /** [packageName] came to the front; [touchedAt] and [agentAt] in uptime millis. */
    @JvmStatic @Synchronized
    fun frontChanged(context: Context, packageName: String, touchedAt: Long, agentAt: Long) {
        if (!enabled(context) || fronts.lastOrNull() == packageName) return
        // The keyboard opening is not an app coming to the front.
        if (packageName == keyboard(context)) return
        val earlier = fronts.toList()
        fronts.addLast(packageName)
        while (fronts.size > 4) fronts.removeFirst()
        val now = SystemClock.uptimeMillis()
        if (!jumpedToFront(earlier, packageName, homes(context), context.packageName, now - touchedAt, now - agentAt)) return
        // With the screen off it is a call or an alarm.
        if (context.getSystemService(PowerManager::class.java)?.isInteractive != true) return
        if (installedApp(context, packageName)) record(context, packageName, "jump", earlier.last())
    }

    /** The apps whose floating window now covers most of the screen, with the app in front. */
    @JvmStatic @Synchronized
    fun overlays(context: Context, packages: Set<String>, front: String?, agentAt: Long) {
        if (!enabled(context)) return
        val appeared = packages - overlaysShown
        overlaysShown.clear()
        overlaysShown.addAll(packages)
        if (SystemClock.uptimeMillis() - agentAt < AGENT_MS) return
        for (name in appeared) if (name != front && installedApp(context, name)) record(context, name, "overlay", front)
    }
}
