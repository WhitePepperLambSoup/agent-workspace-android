package com.agentworkspace.mobile.automation

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Path
import android.graphics.Rect
import android.hardware.display.DisplayManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.DisplayMetrics
import android.view.Display
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.util.concurrent.Callable
import java.util.concurrent.CountDownLatch
import java.util.concurrent.ExecutionException
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException
import java.util.concurrent.atomic.AtomicLong

/** Runs in :engine so the accessibility connection and Chaquopy share a process. */
class AgentAccessibilityService : AccessibilityService(), DisplayManager.DisplayListener {
    private val handler = Handler(Looper.getMainLooper())
    private val epoch = AtomicLong()
    private val sequence = AtomicLong()
    private val session = UUID.randomUUID().toString()
    private val executionLock = Any()
    @Volatile private var snapshot: Snapshot? = null
    @Volatile private var lastPackage: String? = null
    @Volatile private var lastActivity: String? = null

    private data class Screen(val width: Int, val height: Int, val rotation: Int, val density: Float) {
        fun json(): JSONObject = JSONObject().put("width", width).put("height", height)
            .put("rotation", rotation).put("density", density)
    }

    private data class Target(
        val windowId: Int, val path: List<Int>, val bounds: Rect,
        val className: String?, val viewId: String?, val sensitive: Boolean,
    )

    private data class Snapshot(
        val version: String, val epoch: Long, val elapsed: Long, val screen: Screen, val controlRevision: String,
        val targets: Map<String, Target>, val observation: JSONObject, val sensitive: Boolean,
    )

    private class AutomationFailure(val code: String, message: String) : RuntimeException(message)

    private val heartbeat = object : Runnable {
        override fun run() {
            if (AndroidSystemBridge.service === this@AgentAccessibilityService) {
                AndroidAutomationControl.connected(this@AgentAccessibilityService, true)
                handler.postDelayed(this, 2000)
            }
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        AndroidSystemBridge.initialize(this)
        AndroidSystemBridge.service = this
        (getSystemService(Context.DISPLAY_SERVICE) as DisplayManager).registerDisplayListener(this, handler)
        invalidate()
        handler.post(heartbeat)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        invalidate()
        if (event?.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            val packageName = bounded(event.packageName, 255)
            val className = bounded(event.className, 255)
            if (packageName != null && className != null && className.contains('.') &&
                !className.startsWith("android.widget.") && !className.startsWith("android.view.")) {
                lastPackage = packageName
                lastActivity = className
            }
        }
    }

    override fun onInterrupt() {
        invalidate()
        AndroidAutomationControl.set(this, true, true)
    }

    override fun onDestroy() {
        handler.removeCallbacks(heartbeat)
        (getSystemService(Context.DISPLAY_SERVICE) as DisplayManager).unregisterDisplayListener(this)
        if (AndroidSystemBridge.service === this) AndroidSystemBridge.service = null
        AndroidAutomationControl.connected(this, false)
        invalidate()
        super.onDestroy()
    }

    override fun onDisplayAdded(displayId: Int) = invalidate()
    override fun onDisplayRemoved(displayId: Int) = invalidate()
    override fun onDisplayChanged(displayId: Int) = invalidate()

    internal fun invalidate() {
        epoch.incrementAndGet()
    }

    internal fun executeRequest(request: JSONObject): JSONObject = synchronized(executionLock) {
        var actionStarted = false
        var actionExecuted = false
        try {
            val action = request.getString("action")
            when (action) {
                "observe" -> return@synchronized result(capture(request.optInt("max_nodes", 400), request.optInt("max_depth", 24)))
                "screenshot" -> return@synchronized screenshot()
                "verify" -> {
                    if (request.has("snapshot_version")) requireSnapshot(request.getString("snapshot_version"))
                    return@synchronized verify(request, false)
                }
            }
            ensureUnpaused()
            val source = requireSnapshot(request.getString("snapshot_version"))
            actionStarted = true
            val executed = perform(request, source)
            actionExecuted = executed
            invalidate()
            if (!executed) {
                AndroidAutomationControl.set(this, true, false)
                return@synchronized AndroidSystemBridge.failure("action_failed",
                    "Android rejected the action; automation was paused for inspection", freshObservation())
            }
            Thread.sleep(180)
            if (request.has("expect")) return@synchronized verify(request, true)
            result(capture(), executed = true).put("verification", JSONObject().put("status", "not_requested"))
        } catch (error: AutomationFailure) {
            if (actionStarted && error.code !in setOf("stale_snapshot", "paused", "out_of_bounds")) {
                AndroidAutomationControl.set(this, true, false)
            }
            AndroidSystemBridge.failure(error.code, error.message ?: "Android system action failed", freshObservation())
                .put("executed", actionExecuted)
        } catch (_: TimeoutException) {
            if (actionStarted) {
                AndroidAutomationControl.set(this, true, true)
                invalidate()
                AndroidSystemBridge.failure("action_timeout",
                    "Android did not confirm completion; take over before retrying", freshObservation())
                    .put("executed", if (actionExecuted) true else JSONObject.NULL).put("action_state", "unknown")
            } else {
                AndroidSystemBridge.failure("observation_timeout", "Android screen observation timed out")
            }
        } catch (_: Exception) {
            if (actionStarted) AndroidAutomationControl.set(this, true, false)
            AndroidSystemBridge.failure("bridge_error", "Android system operation failed", freshObservation())
                .put("executed", actionExecuted)
        }
    }

    private fun ensureUnpaused() {
        val control = AndroidAutomationControl.readState(this)
        if (control.optBoolean("paused") || control.optBoolean("takeover_requested")) {
            throw AutomationFailure("paused", "Android automation is paused; resume it in Agent Workspace")
        }
    }

    private fun requireSnapshot(version: String): Snapshot {
        val saved = snapshot ?: throw AutomationFailure("stale_snapshot", "Observe the screen before acting")
        if (!saved.observation.optBoolean("stable") || saved.version != version || saved.epoch != epoch.get() ||
            SystemClock.elapsedRealtime() - saved.elapsed > 30000 || saved.screen != screen() ||
            saved.controlRevision != AndroidAutomationControl.readState(this).optString("revision")) {
            throw AutomationFailure("stale_snapshot", "The screen changed; observe again before acting")
        }
        return saved
    }

    private fun recheck(saved: Snapshot) {
        ensureUnpaused()
        requireSnapshot(saved.version)
    }

    @Suppress("DEPRECATION")
    private fun screen(): Screen {
        val display = (getSystemService(Context.DISPLAY_SERVICE) as DisplayManager)
            .getDisplay(Display.DEFAULT_DISPLAY)
        val metrics = DisplayMetrics()
        display?.getRealMetrics(metrics)
        if (metrics.widthPixels <= 0 || metrics.heightPixels <= 0) {
            metrics.setTo(resources.displayMetrics)
        }
        return Screen(metrics.widthPixels, metrics.heightPixels, display?.rotation ?: 0, metrics.density)
    }

    private fun capture(maxNodes: Int = 400, maxDepth: Int = 24): Snapshot = onMain {
        val generation = epoch.get()
        val display = screen()
        val version = "$session:$generation:${sequence.incrementAndGet()}"
        val targets = linkedMapOf<String, Target>()
        val nodes = JSONArray()
        val windowsJson = JSONArray()
        var truncated = false
        var sensitive = false
        var activePackage: String? = null

        fun visit(node: AccessibilityNodeInfo, windowId: Int, path: List<Int>, parent: String?, depth: Int, parentSensitive: Boolean) {
            if (targets.size >= maxNodes || depth > maxDepth) {
                truncated = true
                return
            }
            val protected = parentSensitive || node.isPassword ||
                (Build.VERSION.SDK_INT >= 34 && node.isAccessibilityDataSensitive)
            sensitive = sensitive || protected
            val ref = "n${targets.size + 1}"
            val bounds = Rect().also { node.getBoundsInScreen(it) }
            val className = bounded(node.className, 160)
            val viewId = bounded(node.viewIdResourceName, 255)
            targets[ref] = Target(windowId, path, Rect(bounds), className, viewId, protected)
            nodes.put(JSONObject()
                .put("ref", ref).put("parent_ref", parent ?: JSONObject.NULL).put("window_id", windowId)
                .put("class_name", className ?: JSONObject.NULL).put("view_id", viewId ?: JSONObject.NULL)
                .put("text", if (protected) JSONObject.NULL else bounded(node.text, 512) ?: JSONObject.NULL)
                .put("description", if (protected) JSONObject.NULL else bounded(node.contentDescription, 512) ?: JSONObject.NULL)
                .put("hint", if (protected) JSONObject.NULL else bounded(node.hintText, 512) ?: JSONObject.NULL)
                .put("bounds", boundsJson(bounds))
                .put("clickable", node.isClickable).put("editable", node.isEditable).put("enabled", node.isEnabled)
                .put("visible", node.isVisibleToUser).put("focused", node.isFocused)
                .put("password", node.isPassword).put("sensitive", protected).put("child_count", node.childCount))
            val children = minOf(node.childCount, 400)
            if (depth >= maxDepth) {
                if (children > 0) truncated = true
                return
            }
            if (children != node.childCount) truncated = true
            for (index in 0 until children) {
                if (targets.size >= maxNodes) { truncated = true; break }
                val child = node.getChild(index) ?: continue
                try { visit(child, windowId, path + index, ref, depth + 1, protected) }
                finally { recycle(child) }
            }
        }

        val observedWindows = windows.sortedByDescending { it.layer }
        try {
            observedWindows.take(8).forEach { window ->
                val root = window.root
                val bounds = Rect().also { window.getBoundsInScreen(it) }
                val packageName = bounded(root?.packageName, 255)
                if (window.type == AccessibilityWindowInfo.TYPE_APPLICATION &&
                    (window.isActive || window.isFocused || activePackage == null)) {
                    activePackage = packageName
                }
                windowsJson.put(JSONObject().put("id", window.id).put("type", window.type).put("layer", window.layer)
                    .put("active", window.isActive).put("focused", window.isFocused).put("bounds", boundsJson(bounds))
                    .put("package_name", packageName ?: JSONObject.NULL)
                    .put("title", bounded(window.title, 255) ?: JSONObject.NULL))
                if (root != null) {
                    try { visit(root, window.id, emptyList(), null, 0, false) }
                    finally { recycle(root) }
                }
            }
            if (observedWindows.size > 8) truncated = true
            if (targets.isEmpty()) {
                rootInActiveWindow?.let { root ->
                    try {
                        activePackage = bounded(root.packageName, 255)
                        val bounds = Rect().also { root.getBoundsInScreen(it) }
                        windowsJson.put(JSONObject().put("id", root.windowId).put("type", AccessibilityWindowInfo.TYPE_APPLICATION)
                            .put("active", true).put("focused", true).put("bounds", boundsJson(bounds))
                            .put("package_name", activePackage ?: JSONObject.NULL).put("title", JSONObject.NULL))
                        visit(root, -1, emptyList(), null, 0, false)
                    } finally { recycle(root) }
                }
            }
        } finally {
            observedWindows.forEach { recycle(it) }
        }
        val activity = if (activePackage == lastPackage) lastActivity else null
        val data = JSONObject().put("snapshot_version", version).put("timestamp_ms", System.currentTimeMillis())
            .put("package_name", activePackage ?: JSONObject.NULL).put("activity_name", activity ?: JSONObject.NULL)
            .put("activity_source", if (activity == null) JSONObject.NULL else "accessibility_window_event")
            .put("screen", display.json()).put("windows", windowsJson).put("nodes", nodes)
            .put("truncated", truncated).put("stable", generation == epoch.get())
            .put("sensitive_content_redacted", sensitive)
        Snapshot(version, generation, SystemClock.elapsedRealtime(), display,
            AndroidAutomationControl.readState(this).optString("revision"), targets, data, sensitive)
            .also { snapshot = it }
    }

    private fun freshObservation(): JSONObject? = runCatching { capture().observation }.getOrNull()

    private fun result(saved: Snapshot, executed: Boolean = false, verified: Boolean? = null): JSONObject =
        JSONObject().put("ok", true).put("executed", executed).put("verified", verified ?: JSONObject.NULL)
            .put("observation", saved.observation)

    private fun perform(request: JSONObject, saved: Snapshot): Boolean {
        return when (request.getString("action")) {
            "tap" -> gesture(saved, request.getInt("x"), request.getInt("y"), duration = 70)
            "swipe" -> gesture(saved, request.getInt("x"), request.getInt("y"), request.getInt("x2"), request.getInt("y2"), 350)
            "back", "home" -> onMain {
                recheck(saved)
                performGlobalAction(if (request.getString("action") == "back") GLOBAL_ACTION_BACK else GLOBAL_ACTION_HOME)
            }
            "launch_app" -> onMain {
                recheck(saved)
                val intent = packageManager.getLaunchIntentForPackage(request.getString("package_name"))
                    ?: throw AutomationFailure("app_unavailable", "The requested app has no visible launcher activity")
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                startActivity(intent)
                true
            }
            "ref", "type_text" -> onMain {
                recheck(saved)
                val target = saved.targets[request.getString("ref")]
                    ?: throw AutomationFailure("unknown_ref", "The reference is not part of this screen snapshot")
                if (target.sensitive) throw AutomationFailure("protected_node", "Password and sensitive controls cannot be read or edited")
                val node = resolve(target) ?: throw AutomationFailure("stale_snapshot", "The referenced control disappeared; observe again")
                try {
                    val bounds = Rect().also { node.getBoundsInScreen(it) }
                    if (bounds != target.bounds || bounded(node.className, 160) != target.className ||
                        bounded(node.viewIdResourceName, 255) != target.viewId || !node.isVisibleToUser || !node.isEnabled ||
                        node.isPassword || (Build.VERSION.SDK_INT >= 34 && node.isAccessibilityDataSensitive)) {
                        throw AutomationFailure("stale_snapshot", "The referenced control changed; observe again")
                    }
                    recheck(saved)
                    if (request.getString("action") == "type_text") {
                        if (!node.isEditable) throw AutomationFailure("not_editable", "The referenced control does not accept text")
                        node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, Bundle().apply {
                            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, request.getString("text"))
                        })
                    } else {
                        node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                    }
                } finally { recycle(node) }
            }
            else -> throw AutomationFailure("invalid_arguments", "Unsupported Android action")
        }
    }

    private fun resolve(target: Target): AccessibilityNodeInfo? {
        var node: AccessibilityNodeInfo? = if (target.windowId == -1) rootInActiveWindow else {
            val current = windows
            try { current.firstOrNull { it.id == target.windowId }?.root }
            finally { current.forEach { recycle(it) } }
        }
        for (index in target.path) {
            val parent = node ?: return null
            node = parent.getChild(index)
            recycle(parent)
        }
        return node
    }

    private fun gesture(saved: Snapshot, x: Int, y: Int, x2: Int = x, y2: Int = y, duration: Long): Boolean {
        if (x !in 0 until saved.screen.width || y !in 0 until saved.screen.height ||
            x2 !in 0 until saved.screen.width || y2 !in 0 until saved.screen.height) {
            throw AutomationFailure("out_of_bounds", "Coordinates must fit the current display; observe again")
        }
        if (saved.targets.values.any {
                it.sensitive &&
                    Rect(minOf(x, x2), minOf(y, y2), maxOf(x, x2) + 1, maxOf(y, y2) + 1)
                        .intersect(it.bounds)
            }) {
            throw AutomationFailure("protected_node", "The target contains password or sensitive content")
        }
        val completion = CountDownLatch(1)
        var completed = false
        val accepted = onMain {
            recheck(saved)
            val path = Path().apply { moveTo(x.toFloat(), y.toFloat()); lineTo(x2.toFloat(), y2.toFloat()) }
            val gesture = GestureDescription.Builder().addStroke(
                GestureDescription.StrokeDescription(path, 0, duration)).build()
            dispatchGesture(gesture, object : GestureResultCallback() {
                override fun onCompleted(gestureDescription: GestureDescription) {
                    completed = true
                    completion.countDown()
                }
                override fun onCancelled(gestureDescription: GestureDescription) { completion.countDown() }
            }, handler)
        }
        if (!accepted) return false
        if (!completion.await(2500, TimeUnit.MILLISECONDS)) throw TimeoutException()
        return completed
    }

    private fun verify(request: JSONObject, executed: Boolean): JSONObject {
        val expectation = request.getJSONObject("expect")
        val deadline = SystemClock.elapsedRealtime() + request.optInt("timeout_ms", 1500)
        var observed: Snapshot
        var matched: Boolean
        do {
            observed = capture()
            matched = matchesAndroidObservation(observed.observation, expectation)
            if (matched || SystemClock.elapsedRealtime() >= deadline) break
            Thread.sleep(150)
        } while (true)
        if (executed && !matched) AndroidAutomationControl.set(this, true, false)
        return result(observed, executed, matched).put("ok", matched)
            .put("verification", JSONObject().put("status", if (matched) "matched" else "not_matched")
                .put("checked", JSONArray(expectation.keys().asSequence().toList())))
    }

    private fun screenshot(): JSONObject {
        if (Build.VERSION.SDK_INT < 30) return AndroidSystemBridge.failure("unsupported_api",
            "Screenshots require Android 11 (API 30) or newer; use the accessibility tree", freshObservation())
        val observed = capture()
        if (observed.sensitive || observed.observation.optBoolean("truncated")) return AndroidSystemBridge.failure("protected_content",
            "Screenshot capture is blocked while password or sensitive controls are visible", observed.observation)
        val completed = CountDownLatch(1)
        var bitmap: Bitmap? = null
        var captureError: Int? = null
        onMain {
            takeScreenshot(Display.DEFAULT_DISPLAY, mainExecutor, object : TakeScreenshotCallback {
                override fun onSuccess(screenshot: ScreenshotResult) {
                    try {
                        val wrapped = Bitmap.wrapHardwareBuffer(screenshot.hardwareBuffer, screenshot.colorSpace)
                        bitmap = wrapped?.copy(Bitmap.Config.ARGB_8888, false)
                        wrapped?.recycle()
                    } catch (_: Exception) { captureError = -1 }
                    finally { screenshot.hardwareBuffer.close(); completed.countDown() }
                }
                override fun onFailure(errorCode: Int) { captureError = errorCode; completed.countDown() }
            })
        }
        if (!completed.await(4000, TimeUnit.MILLISECONDS)) return AndroidSystemBridge.failure("screenshot_timeout",
            "Android did not provide a screenshot", freshObservation())
        val captured = bitmap
        if (captured == null || captureError != null) return AndroidSystemBridge.failure("screenshot_unavailable",
            "Android blocked screenshot capture; secure windows cannot be captured", freshObservation())
        try {
            if (observed.epoch != epoch.get() || observed.screen != screen()) return AndroidSystemBridge.failure("stale_snapshot",
                "The screen changed during capture; observe again", freshObservation())
            val factor = minOf(1.0, 1600.0 / maxOf(captured.width, captured.height))
            val image = if (factor < 1.0) Bitmap.createScaledBitmap(captured,
                maxOf(1, (captured.width * factor).toInt()), maxOf(1, (captured.height * factor).toInt()), true) else captured
            try {
                val directory = File(filesDir, "workspace/automation/screenshots").apply {
                    check(mkdirs() || isDirectory)
                }
                require(directory.canonicalPath.startsWith(File(filesDir, "workspace").canonicalPath + File.separator))
                val name = "screen-${UUID.randomUUID()}.png"
                val output = File(directory, name)
                FileOutputStream(output).use { stream -> check(image.compress(Bitmap.CompressFormat.PNG, 100, stream)) }
                if (output.length() > 5 * 1024 * 1024) {
                    output.delete()
                    return AndroidSystemBridge.failure("screenshot_too_large", "Android screenshot exceeds the image size limit", observed.observation)
                }
                directory.listFiles()?.filter { it.name.startsWith("screen-") && it.extension == "png" }
                    ?.sortedByDescending { it.lastModified() }?.drop(20)?.forEach { it.delete() }
                return result(observed).put("screenshot", JSONObject()
                    .put("path", "automation/screenshots/$name").put("absolute_path", output.absolutePath)
                    .put("media_type", "image/png").put("snapshot_version", observed.version)
                    .put("width", image.width).put("height", image.height)
                    .put("screen_width", observed.screen.width).put("screen_height", observed.screen.height)
                    .put("pixel_to_screen_x", observed.screen.width.toDouble() / image.width)
                    .put("pixel_to_screen_y", observed.screen.height.toDouble() / image.height))
            } finally { if (image !== captured) image.recycle() }
        } finally { captured.recycle() }
    }

    private fun <T> onMain(block: () -> T): T {
        if (Looper.myLooper() == Looper.getMainLooper()) return block()
        val task = FutureTask(Callable { block() })
        handler.post(task)
        return try { task.get(3000, TimeUnit.MILLISECONDS) }
        catch (error: ExecutionException) { throw error.cause ?: error }
        catch (error: TimeoutException) { task.cancel(false); throw error }
    }

    private fun bounded(value: CharSequence?, maximum: Int): String? = value?.toString()?.take(maximum)

    private fun boundsJson(bounds: Rect): JSONObject = JSONObject().put("left", bounds.left)
        .put("top", bounds.top).put("right", bounds.right).put("bottom", bounds.bottom)

    @Suppress("DEPRECATION")
    private fun recycle(node: AccessibilityNodeInfo) { node.recycle() }

    @Suppress("DEPRECATION")
    private fun recycle(window: AccessibilityWindowInfo) { window.recycle() }
}

internal fun matchesAndroidObservation(observation: JSONObject, expectation: JSONObject): Boolean {
    if (!observation.optBoolean("stable")) return false
    val observedNodes = observation.optJSONArray("nodes") ?: JSONArray()
    val publicNodes = (0 until observedNodes.length()).mapNotNull(observedNodes::optJSONObject)
        .filter { it.optBoolean("visible") && !it.optBoolean("password") && !it.optBoolean("sensitive") }
    return expectation.keys().asSequence().all { key ->
        val wanted = expectation.getString(key)
        when (key) {
            "package_name", "activity_name" -> observation.optString(key) == wanted
            "text_contains" -> publicNodes.any { node ->
                (!node.isNull("text") && node.optString("text").contains(wanted)) ||
                    (!node.isNull("description") && node.optString("description").contains(wanted))
            }
            "view_id_exists", "resource_id" -> publicNodes.any { it.optString("view_id") == wanted }
            else -> false
        }
    }
}
