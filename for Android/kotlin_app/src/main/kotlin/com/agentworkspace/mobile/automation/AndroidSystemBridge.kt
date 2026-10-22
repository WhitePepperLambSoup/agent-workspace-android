package com.agentworkspace.mobile.automation

import android.accessibilityservice.AccessibilityServiceInfo
import android.app.ActivityManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Looper
import android.provider.Settings
import android.view.accessibility.AccessibilityManager
import org.json.JSONArray
import org.json.JSONObject

/** JSON boundary used by Chaquopy in the engine process. */
object AndroidSystemBridge {
    @Volatile private var applicationContext: Context? = null
    @Volatile internal var service: AgentAccessibilityService? = null

    @JvmStatic
    fun initialize(context: Context) {
        applicationContext = context.applicationContext
    }

    @JvmStatic
    fun status(): String {
        val context = applicationContext
        val state = context?.let { AndroidAutomationControl.readState(it) } ?: JSONObject()
        val enabled = context?.let { isEnabled(it) } ?: false
        val connected = enabled && (service != null || context?.let {
            AndroidAutomationControl.hasRecentConnection(it)
        } == true)
        val memory = ActivityManager.MemoryInfo()
        (context?.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager)?.getMemoryInfo(memory)
        val switchedOn = context?.let { switchedOn(it) } ?: false
        val reason = when {
            context == null -> "Android system bridge is not initialized; restart the engine"
            !enabled && switchedOn -> "Accessibility is on for Agent Workspace but Android is not running it (this happens " +
                "after an update or a crash): turn it off and on again in Accessibility settings"
            !enabled -> "Enable Agent Workspace in Android Accessibility settings"
            !connected -> "Android accessibility service is disconnected; enable it in Accessibility settings"
            else -> null
        }
        val status = JSONObject()
            .put("available", context != null)
            .put("enabled", enabled)
            // The switch in Accessibility settings, which Android may keep on without running the service.
            .put("switched_on", switchedOn)
            .put("can_repair", context?.let { canRepair(it) } ?: false)
            .put("connected", connected)
            .put("local_connection", service != null)
            .put("paused", state.optBoolean("paused"))
            .put("takeover_requested", state.optBoolean("takeover_requested"))
            .put("screenshot_supported", Build.VERSION.SDK_INT >= 30 || LiveScreen.active)
            // Only meaningful in the :engine process, where the live screen runs.
            .put("live_screen_active", LiveScreen.active)
            .put("api_level", Build.VERSION.SDK_INT)
            .put("device", "${Build.MANUFACTURER} ${Build.MODEL}")
            .put("app_version", context?.let {
                it.packageManager.getPackageInfo(it.packageName, 0).versionName
            } ?: JSONObject.NULL)
            .put("abis", JSONArray(Build.SUPPORTED_ABIS.toList()))
            .put("memory_total_bytes", memory.totalMem)
            .put("memory_available_bytes", memory.availMem)
            .put("memory_usable_bytes", try {
                com.agentworkspace.mobile.localmodels.LocalModelContext.usableRamBytes(memory.availMem, memory.totalMem,
                    java.io.File("/proc/meminfo").readText(Charsets.US_ASCII))
            } catch (_: Exception) { memory.availMem })
            .put("settings_action", Settings.ACTION_ACCESSIBILITY_SETTINGS)
            .put("service_component", "${context?.packageName ?: "com.agentworkspace.mobile"}/com.agentworkspace.mobile.automation.AgentAccessibilityService")
            .put("reason", reason ?: JSONObject.NULL)
        return status.toString()
    }

    private fun component(context: Context) =
        ComponentName(context.packageName, AgentAccessibilityService::class.java.name)

    private fun switchedOn(context: Context): Boolean = runCatching {
        val ours = component(context)
        Settings.Secure.getString(context.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES).orEmpty()
            .split(':').any { ComponentName.unflattenFromString(it) == ours }
    }.getOrDefault(false)

    /** Granted only by the user, once, with adb (pm grant … WRITE_SECURE_SETTINGS). */
    private fun canRepair(context: Context) =
        context.checkSelfPermission(android.Manifest.permission.WRITE_SECURE_SETTINGS) == PackageManager.PERMISSION_GRANTED

    /**
     * On the user's tap: turns the accessibility service off and on again (or on), which brings back
     * one Android stopped running after an update or a crash. Needs WRITE_SECURE_SETTINGS; without it
     * Accessibility settings open for the user to do the same.
     */
    @JvmStatic
    fun repairAccessibility(context: Context): String {
        val resolver = context.contentResolver
        val ours = component(context)
        if (canRepair(context)) try {
            val others = Settings.Secure.getString(resolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES).orEmpty()
                .split(':').filter { it.isNotBlank() && ComponentName.unflattenFromString(it) != ours }
            Settings.Secure.putString(resolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES, others.joinToString(":"))
            Thread.sleep(500)
            Settings.Secure.putString(resolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
                (others + ours.flattenToString()).joinToString(":"))
            Settings.Secure.putInt(resolver, Settings.Secure.ACCESSIBILITY_ENABLED, 1)
            return JSONObject().put("ok", true).toString()
        } catch (_: SecurityException) {
            // The grant was taken back: fall through to the settings page.
        }
        val opened = openAccessibilitySettings(context)
        return JSONObject().put("ok", false).put("opened_settings", opened).toString()
    }

    private fun isEnabled(context: Context): Boolean {
        val manager = context.getSystemService(Context.ACCESSIBILITY_SERVICE) as AccessibilityManager
        return manager.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK)
            .any { info ->
                val declared = info.resolveInfo.serviceInfo
                declared.packageName == context.packageName &&
                    declared.name == AgentAccessibilityService::class.java.name
            }
    }

    @JvmStatic
    fun setPaused(context: Context, paused: Boolean): String {
        initialize(context)
        AndroidAutomationControl.set(context.applicationContext, paused, false)
        service?.invalidate()
        return status()
    }

    @JvmStatic
    fun requestTakeover(context: Context): String {
        initialize(context)
        AndroidAutomationControl.set(context.applicationContext, true, true)
        service?.invalidate()
        return status()
    }

    @JvmStatic
    fun resume(context: Context): String = setPaused(context, false)

    @JvmStatic
    fun pause(context: Context): String = setPaused(context, true)

    @JvmStatic
    fun openAccessibilitySettings(context: Context): Boolean = runCatching {
        context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        true
    }.getOrDefault(false)

    /** Asks for the screen capture consent; the live screen then runs until turned off or idle. */
    @JvmStatic
    fun startLiveScreen(context: Context): Boolean = runCatching {
        context.startActivity(Intent(context, LiveScreenConsentActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        true
    }.getOrDefault(false)

    @JvmStatic
    fun stopLiveScreen(context: Context) = LiveScreenService.stop(context)

    /**
     * Before a scheduled phone task: the phone must be unlocked (no app may unlock it) and the
     * accessibility service connected; a dark screen is turned on for the task.
     */
    @JvmStatic
    fun prepareUnattended(): String {
        val context = applicationContext ?: return JSONObject().put("ok", false).put("reason", "not initialized").toString()
        val keyguard = context.getSystemService(android.app.KeyguardManager::class.java)
        if (keyguard?.isKeyguardLocked == true) return JSONObject().put("ok", false)
            .put("reason", com.agentworkspace.mobile.UiText.of(context, "手机锁着屏，到点时没法操作", "The phone was locked at the time")).toString()
        if (service == null) return JSONObject().put("ok", false)
            .put("reason", com.agentworkspace.mobile.UiText.of(context, "无障碍服务没开", "The accessibility service is off")).toString()
        val power = context.getSystemService(android.os.PowerManager::class.java)
        if (power?.isInteractive == false) {
            @Suppress("DEPRECATION")
            power.newWakeLock(android.os.PowerManager.SCREEN_BRIGHT_WAKE_LOCK or android.os.PowerManager.ACQUIRE_CAUSES_WAKEUP,
                "agentworkspace:scheduled-phone-task").acquire(10_000)
            Thread.sleep(800)
        }
        return JSONObject().put("ok", true).toString()
    }

    @JvmStatic
    fun execute(requestJson: String): String {
        var background = false
        val request = try {
            require(requestJson.length in 2..32768)
            JSONObject(requestJson).also {
                // Set by the engine for conversation tasks: work on the background screen if it is on.
                background = it.remove("background") == true
                validateRequest(it)
            }
        } catch (_: Exception) {
            return failure("invalid_arguments", "Invalid or oversized Android system request").toString()
        }
        if (Looper.myLooper() == Looper.getMainLooper()) {
            return failure("main_thread", "Android system requests must run on an engine worker thread").toString()
        }
        val connected = service ?: return failure("service_unavailable",
            "Enable Agent Workspace in Android Accessibility settings and retry in the engine process").toString()
        return connected.executeRequest(request, background = background).toString()
    }

    // ---- The background screen (Device & tools → Background operation), see BackgroundScreen ----

    @JvmStatic
    fun backgroundStatus(): String =
        applicationContext?.let { BackgroundScreen.status(it).toString() } ?: JSONObject().put("supported", false).toString()

    @JvmStatic
    fun setBackground(enabled: Boolean): String {
        val context = applicationContext ?: return backgroundStatus()
        BackgroundScreen.setEnabled(context, enabled)
        // Turning it on asks Shizuku for permission right away, when that is what is missing.
        if (enabled) BackgroundScreen.requestPermission()
        return backgroundStatus()
    }

    @JvmStatic
    fun requestBackgroundPermission(): String {
        BackgroundScreen.requestPermission()
        return backgroundStatus()
    }

    /** Opens the background screen without a task (Device & tools → Test): its status, or why not. */
    @JvmStatic
    fun openBackground(): String {
        val context = applicationContext ?: return backgroundStatus()
        val error = runCatching { BackgroundScreen.open(context) }.exceptionOrNull()
        return JSONObject(backgroundStatus()).put("error", error?.message ?: JSONObject.NULL).toString()
    }

    /** Moves the app on the background screen to the phone's screen, for the user to take over. */
    @JvmStatic
    fun bringBackgroundToFront(): String {
        val error = BackgroundScreen.bringToFront()
        return JSONObject().put("ok", error == null).put("error", error ?: JSONObject.NULL).toString()
    }

    /** The background screen's picture as JPEG bytes (the conversation's live view), or null. */
    @JvmStatic
    fun backgroundPicture(maxEdge: Int): ByteArray? {
        if (BackgroundScreen.currentDisplay() == -1) return null
        val bitmap = BackgroundScreen.picture(maxEdge.coerceIn(200, 1600)) ?: return null
        return java.io.ByteArrayOutputStream().use { out ->
            bitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG, 80, out)
            bitmap.recycle()
            out.toByteArray()
        }
    }

    /** Actions a batch may contain (one approval covers them all; no app launches or nested batches). */
    private val batchActions = setOf("tap", "swipe", "ref", "type_text", "long_press", "scroll", "enter", "back", "tap_text")
    /** Actions that read the screen as it is when they run: no earlier snapshot needed. */
    private val freshActions = setOf("observe", "screenshot", "verify", "tap_text", "scroll_to_text", "wait_for", "open_page", "ocr",
        "launch_app", "back", "home", "recents", "notifications")
    private val pages = setOf("settings", "wifi", "bluetooth", "mobile_network", "data_usage", "airplane", "battery",
        "display", "sound", "location", "storage", "date", "language", "accessibility", "security", "nfc", "vpn",
        "developer", "apps", "notifications", "app_details", "url", "map", "web_search", "dial")
    /** A repeat's steps: by coordinates, scroll direction or back; a changing feed has no lasting refs. */
    private val repeatActions = setOf("tap", "swipe", "long_press", "scroll", "back")

    internal fun validateRequest(request: JSONObject, inBatch: Boolean = false, inRepeat: Boolean = false) {
        val action = string(request, "action", 32)
        val step = if (inBatch || inRepeat) emptySet() else setOf("snapshot_version", "expect", "timeout_ms")
        if (inBatch) require(action in batchActions)
        if (inRepeat) require(action in repeatActions && !request.has("ref"))
        val fields = when (action) {
            "observe" -> setOf("max_nodes", "max_depth", "wait_ms")
            "screenshot" -> setOf("marks")
            "verify" -> setOf("expect", "timeout_ms", "snapshot_version")
            "tap" -> step + setOf("x", "y", "confirmed")
            "swipe" -> step + setOf("x", "y", "x2", "y2")
            "ref" -> step + setOf("ref", "confirmed")
            "type_text" -> step + setOf("ref", "text")
            "long_press" -> step + setOf("ref", "x", "y", "confirmed")
            "scroll" -> step + setOf("ref", "direction")
            "enter" -> step + setOf("ref")
            "launch_app" -> step + setOf("package_name", "app_name")
            "back", "home", "recents", "notifications" -> step
            "batch" -> setOf("snapshot_version", "steps", "expect", "timeout_ms")
            "repeat" -> setOf("snapshot_version", "steps", "every_ms", "times")
            "stop_repeat" -> setOf("snapshot_version")
            "tap_text" -> step + setOf("text", "nth", "confirmed")
            "scroll_to_text" -> setOf("snapshot_version", "text", "direction", "ref", "max_scrolls", "tap", "confirmed")
            "wait_for" -> setOf("snapshot_version", "text", "gone_text", "max_wait_ms")
            "open_page" -> setOf("snapshot_version", "page", "package_name", "app_name", "url", "query", "number")
            "ocr" -> setOf("snapshot_version")
            else -> error("Unsupported action")
        }
        require(request.keys().asSequence().all { it == "action" || it in fields })
        // The user said yes to pressing a control that deletes, clears or pays (see needs_confirmation).
        if (request.has("confirmed")) require(request.get("confirmed") is Boolean)
        if (!inBatch && !inRepeat && action !in freshActions) string(request, "snapshot_version", 128)
        if (action == "tap_text") {
            string(request, "text", 200)
            if (request.has("nth")) integer(request, "nth", 1, 50)
        }
        if (action == "scroll_to_text") {
            string(request, "text", 200)
            if (request.has("direction")) require(string(request, "direction", 8) in setOf("up", "down", "left", "right"))
            if (request.has("ref")) require(string(request, "ref", 160).matches(Regex("n[0-9]{1,4}")))
            if (request.has("max_scrolls")) integer(request, "max_scrolls", 1, 40)
            if (request.has("tap")) require(request.get("tap") is Boolean)
        }
        if (action == "wait_for") {
            require(request.has("text") || request.has("gone_text"))
            if (request.has("text")) string(request, "text", 200)
            if (request.has("gone_text")) string(request, "gone_text", 200)
            if (request.has("max_wait_ms")) integer(request, "max_wait_ms", 500, 120_000)
        }
        if (action == "open_page") {
            val page = string(request, "page", 32)
            require(page in pages)
            if (request.has("package_name")) require(string(request, "package_name", 255)
                .matches(Regex("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z0-9_]+)+")))
            if (request.has("app_name")) string(request, "app_name", 100)
            if (page == "url") require(string(request, "url", 2000).let { it.startsWith("https://") || it.startsWith("http://") })
            if (page == "map" || page == "web_search") string(request, "query", 300)
            if (page == "dial") require(string(request, "number", 40).matches(Regex("[0-9+*#() -]{1,40}")))
        }
        if (request.has("snapshot_version")) string(request, "snapshot_version", 128)
        if (request.has("max_nodes")) integer(request, "max_nodes", 1, 400)
        if (request.has("max_depth")) integer(request, "max_depth", 1, 24)
        if (request.has("wait_ms")) integer(request, "wait_ms", 0, 5000)
        if (request.has("marks")) require(request.get("marks") is Boolean)
        if (action == "tap" || action == "swipe" || (action == "long_press" && !request.has("ref"))) {
            integer(request, "x", 0, 10000)
            integer(request, "y", 0, 10000)
        }
        if (action == "swipe") {
            integer(request, "x2", 0, 10000)
            integer(request, "y2", 0, 10000)
        }
        if (action == "ref" || action == "type_text" || (action in setOf("long_press", "scroll", "enter") && request.has("ref"))) {
            require(string(request, "ref", 160).matches(Regex("n[0-9]{1,4}")))
        }
        if (action == "long_press") require(request.has("ref") != (request.has("x") || request.has("y")))
        if (action == "scroll") require(string(request, "direction", 8) in setOf("up", "down", "left", "right", "top", "bottom"))
        if (action == "batch") {
            val steps = request.getJSONArray("steps")
            require(steps.length() in 1..12)
            for (index in 0 until steps.length()) validateRequest(steps.getJSONObject(index), inBatch = true)
        }
        if (action == "repeat") {
            val steps = request.getJSONArray("steps")
            require(steps.length() in 1..4)
            for (index in 0 until steps.length()) validateRequest(steps.getJSONObject(index), inRepeat = true)
            integer(request, "every_ms", 300, 3_600_000)
            if (request.has("times")) integer(request, "times", 1, 10_000)
        }
        if (action == "type_text") string(request, "text", 4096)
        if (action == "launch_app") {
            require(request.has("package_name") || request.has("app_name"))
            if (request.has("package_name")) require(string(request, "package_name", 255)
                .matches(Regex("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z0-9_]+)+")))
            if (request.has("app_name")) string(request, "app_name", 100)
        }
        if (action == "verify") require(request.has("expect"))
        if (request.has("expect")) {
            val expectation = request.getJSONObject("expect")
            require(expectation.length() in 1..5)
            expectation.keys().asSequence().forEach { key ->
                require(key in setOf("package_name", "activity_name", "text_contains", "view_id_exists", "resource_id"))
                string(expectation, key, 300)
            }
        }
        if (request.has("timeout_ms")) integer(request, "timeout_ms", 100, 5000)
    }

    private fun string(value: JSONObject, key: String, maximum: Int): String {
        val data = value.get(key)
        // JSON Schema maxLength and Python len count Unicode code points.
        require(data is String && data.isNotEmpty() &&
            data.codePointCount(0, data.length) <= maximum && '\u0000' !in data)
        return data
    }

    private fun integer(value: JSONObject, key: String, minimum: Int, maximum: Int): Int {
        val data = value.get(key)
        require(data is Int || data is Long)
        val number = (data as Number).toLong()
        require(number in minimum.toLong()..maximum.toLong())
        return number.toInt()
    }

    internal fun failure(code: String, message: String, observation: JSONObject? = null): JSONObject =
        JSONObject().put("ok", false).put("executed", false).put("verified", JSONObject.NULL)
            .put("error", JSONObject().put("code", code).put("message", message))
            .put("observation", observation ?: JSONObject.NULL)

    // ---- Shortcuts: recorded phone tasks, run again without the model (mobile_shortcuts.py) -----

    private fun outcome(ok: Boolean, reason: String?) = JSONObject().put("ok", ok).put("reason", reason ?: JSONObject.NULL)

    @JvmStatic
    fun shortcuts(): String {
        val context = applicationContext ?: return "[]"
        return JSONArray(PhoneMemory.shortcuts(context).map { it.json() }).toString()
    }

    /** Adds a shortcut or replaces one's name and steps: {"id"?, "name", "app"?, "app_label"?, "steps"}. */
    @JvmStatic
    fun saveShortcut(json: String): String = try {
        val context = applicationContext ?: throw IllegalStateException("not initialized")
        require(json.length <= 262_144) { "the shortcut is too large" }
        val value = JSONObject(json)
        fun words(key: String, limit: Int) = value.optString(key).takeUnless { value.isNull(key) || it.isBlank() }?.take(limit)
        PhoneMemory.putShortcut(context, words("id", 64), value.optString("name"), words("app", 255), words("app_label", 80),
            value.getJSONArray("steps")).json().put("ok", true).toString()
    } catch (error: Exception) {
        outcome(false, error.message ?: "invalid shortcut").toString()
    }

    @JvmStatic
    fun deleteShortcut(id: String): String {
        val context = applicationContext ?: return outcome(false, "not initialized").toString()
        PhoneMemory.deleteShortcut(context, id)
        return outcome(true, null).toString()
    }

    /**
     * Runs a saved shortcut now, on a worker thread (it waits for each step). Steps that need the
     * user's yes (deleting, paying) stop it.
     */
    @JvmStatic
    fun runShortcut(id: String): String {
        if (Looper.myLooper() == Looper.getMainLooper()) return outcome(false, "main thread").toString()
        val context = applicationContext ?: return outcome(false, "not initialized").toString()
        val connected = service ?: return outcome(false,
            com.agentworkspace.mobile.UiText.of(context, "无障碍服务没开", "The accessibility service is off")).toString()
        val shortcut = PhoneMemory.shortcuts(context).firstOrNull { it.id == id }
            ?: return outcome(false, com.agentworkspace.mobile.UiText.of(context, "没有这个快捷操作", "No such shortcut")).toString()
        val steps = JSONArray()
        val first = shortcut.steps.optJSONObject(0)?.optString("kind")
        // Recorded inside an app: open it first; recorded over the home screen: start from there.
        if (first != "launch" && first != "page") steps.put(
            if (shortcut.app != null) JSONObject().put("kind", "launch").put("package", shortcut.app)
            else JSONObject().put("kind", "key").put("key", "home"))
        for (index in 0 until shortcut.steps.length()) steps.put(shortcut.steps.get(index))
        val stopped = connected.replay(steps)
        val answer = outcome(stopped == null, stopped).put("steps", steps.length())
        // Which of the shortcut's own steps it stopped at (the AI can take over from there).
        if (stopped != null) answer.put("failed_step",
            (connected.replayStoppedAt - (steps.length() - shortcut.steps.length())).coerceAtLeast(0))
        return answer.toString()
    }

    @JvmStatic
    fun stopShortcut() { service?.stopReplay() }

    /** A phone-control task from the chat starts: what it does is kept (read with recordedSteps). */
    @JvmStatic
    fun beginRecording(taskId: String) {
        service?.let { it.startRecording(); it.recordStartingPoint(); it.beginStepShots(taskId) }
    }

    /** The task ended: no more step pictures for it. */
    @JvmStatic
    fun endRecording() { service?.endStepShots() }

    @JvmStatic
    fun recordedSteps(): String = JSONArray(service?.peekRecording().orEmpty()).toString()
}
