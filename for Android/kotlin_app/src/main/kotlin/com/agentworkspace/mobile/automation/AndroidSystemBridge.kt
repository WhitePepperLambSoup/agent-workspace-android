package com.agentworkspace.mobile.automation

import android.accessibilityservice.AccessibilityServiceInfo
import android.app.ActivityManager
import android.content.Context
import android.content.Intent
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
        val reason = when {
            context == null -> "Android system bridge is not initialized; restart the engine"
            !enabled -> "Enable Agent Workspace in Android Accessibility settings"
            !connected -> "Android accessibility service is disconnected; enable it in Accessibility settings"
            else -> null
        }
        val status = JSONObject()
            .put("available", context != null)
            .put("enabled", enabled)
            .put("connected", connected)
            .put("local_connection", service != null)
            .put("paused", state.optBoolean("paused"))
            .put("takeover_requested", state.optBoolean("takeover_requested"))
            .put("screenshot_supported", Build.VERSION.SDK_INT >= 30)
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

    @JvmStatic
    fun execute(requestJson: String): String {
        val request = try {
            require(requestJson.length in 2..32768)
            JSONObject(requestJson).also { validateRequest(it) }
        } catch (_: Exception) {
            return failure("invalid_arguments", "Invalid or oversized Android system request").toString()
        }
        if (Looper.myLooper() == Looper.getMainLooper()) {
            return failure("main_thread", "Android system requests must run on an engine worker thread").toString()
        }
        val connected = service ?: return failure("service_unavailable",
            "Enable Agent Workspace in Android Accessibility settings and retry in the engine process").toString()
        return connected.executeRequest(request).toString()
    }

    internal fun validateRequest(request: JSONObject) {
        val action = string(request, "action", 32)
        val fields = when (action) {
            "observe" -> setOf("max_nodes", "max_depth")
            "screenshot" -> emptySet()
            "verify" -> setOf("expect", "timeout_ms", "snapshot_version")
            "tap" -> setOf("snapshot_version", "x", "y", "expect", "timeout_ms")
            "swipe" -> setOf("snapshot_version", "x", "y", "x2", "y2", "expect", "timeout_ms")
            "ref" -> setOf("snapshot_version", "ref", "expect", "timeout_ms")
            "type_text" -> setOf("snapshot_version", "ref", "text", "expect", "timeout_ms")
            "launch_app" -> setOf("snapshot_version", "package_name", "expect", "timeout_ms")
            "back", "home" -> setOf("snapshot_version", "expect", "timeout_ms")
            else -> error("Unsupported action")
        }
        require(request.keys().asSequence().all { it == "action" || it in fields })
        if (action !in setOf("observe", "screenshot", "verify")) string(request, "snapshot_version", 128)
        if (request.has("snapshot_version")) string(request, "snapshot_version", 128)
        if (request.has("max_nodes")) integer(request, "max_nodes", 1, 400)
        if (request.has("max_depth")) integer(request, "max_depth", 1, 24)
        if (action == "tap" || action == "swipe") {
            integer(request, "x", 0, 10000)
            integer(request, "y", 0, 10000)
        }
        if (action == "swipe") {
            integer(request, "x2", 0, 10000)
            integer(request, "y2", 0, 10000)
        }
        if (action == "ref" || action == "type_text") {
            require(string(request, "ref", 160).matches(Regex("n[0-9]{1,3}")))
        }
        if (action == "type_text") string(request, "text", 4096)
        if (action == "launch_app") require(string(request, "package_name", 255)
            .matches(Regex("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z0-9_]+)+")))
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
}
