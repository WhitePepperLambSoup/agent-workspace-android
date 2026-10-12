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

/** How deep inside a wordless row or button its words are looked for. */
private const val INNER_DEPTH = 4

/** Runs in :engine so the accessibility connection and Chaquopy share a process. */
class AgentAccessibilityService : AccessibilityService(), DisplayManager.DisplayListener {
    private val handler = Handler(Looper.getMainLooper())
    private val reader = android.os.HandlerThread("agent-accessibility-reader").apply { start() }
    private val readerHandler = Handler(reader.looper)
    // A snapshot stays usable while the same windows are shown in the same places (windowSignature)
    // and [epoch] has not moved: it moves when the display turns, automation is paused, or the agent
    // acted. Content that keeps changing inside a window (a clock, a video, a loading animation) only
    // moves [contentEpoch]; actions then check their own target instead of refusing every snapshot
    // of a lively screen.
    private val epoch = AtomicLong()
    private val contentEpoch = AtomicLong()
    private val sequence = AtomicLong()
    private val session = UUID.randomUUID().toString()
    private val executionLock = Any()
    // The last few snapshots, so an action may cite the observation or the screenshot before it.
    private val recent = object : LinkedHashMap<String, Snapshot>() {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Snapshot>?) = size > 4
    }
    @Volatile private var lastPackage: String? = null
    @Volatile private var lastActivity: String? = null
    /** "Operate the phone" from the floating bubble; it steps aside for screenshots and gestures. */
    @Volatile private var panel: PhoneControlPanel? = null

    private data class Screen(val width: Int, val height: Int, val rotation: Int, val density: Float) {
        fun json(): JSONObject = JSONObject().put("width", width).put("height", height)
            .put("rotation", rotation).put("density", density)
    }

    private data class Target(
        val windowId: Int, val path: List<Int>, val bounds: Rect,
        val className: String?, val viewId: String?, val sensitive: Boolean,
        /** What the control says (an editable field: its hint), to tell it from a recycled neighbour. */
        val label: String? = null, val visible: Boolean = true,
    ) {
        // Counting numbers ("重新发送(59)", a timer) keep a control the same while it stays in place.
        fun sameControl(other: Target?): Boolean = other != null && className == other.className &&
            viewId == other.viewId && (label == other.label ||
                bounds == other.bounds && label?.replace(digits, "#") == other.label?.replace(digits, "#"))

        companion object { private val digits = Regex("[0-9]+") }
    }

    private data class Snapshot(
        val version: String, val epoch: Long, val elapsed: Long, val screen: Screen, val controlRevision: String,
        val targets: Map<String, Target>, val observation: JSONObject, val sensitive: Boolean,
        val windows: String = "",
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
        // No system accessibility button: Android would pin it to every screen, in the agent's
        // screenshots too. The panel opens from the bubble and stays up over screens that hide
        // other apps' overlays (Settings), so a task can still go there.
    }

    /** When a list last moved: a fling keeps it going after the finger lifts. */
    @Volatile private var lastScrollAt = 0L

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Window events arrive late or for windows that end up where they were, so they only count as
        // content; whether the windows changed is decided by comparing them (windowSignature).
        contentEpoch.incrementAndGet()
        if (event?.eventType == AccessibilityEvent.TYPE_VIEW_SCROLLED) lastScrollAt = SystemClock.uptimeMillis()
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
        panel?.close()
        panel = null
        reader.quitSafely()
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

    /** Opens the phone control panel over the app in front (main thread; from PhoneControlReceiver). */
    internal fun openControlPanel() {
        // Reading the app in front asks that app; it is done off the main thread like other reads.
        readerHandler.post {
            val (front, label) = frontApp()
            handler.post { (panel ?: PhoneControlPanel(this).also { panel = it }).open(front, label) }
        }
    }

    private fun frontApp(): Pair<String?, String?> {
        var title: String? = null
        val front = runCatching {
            val current = windows
            try {
                current.filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION }
                    .sortedByDescending { (if (it.isActive) 2 else 0) + (if (it.isFocused) 1 else 0) }
                    .firstNotNullOfOrNull { window ->
                        val root = window.root ?: return@firstNotNullOfOrNull null
                        try { root.packageName?.toString()?.also { title = bounded(window.title, 60) } } finally { recycle(root) }
                    }
            } finally { current.forEach { recycle(it) } }
        }.getOrNull() ?: lastPackage
        val label = front?.let { name ->
            runCatching { packageManager.getApplicationLabel(packageManager.getApplicationInfo(name, 0)).toString() }.getOrNull()
        } ?: title
        return front to label
    }

    /** In words, what an android_action request does (the panel's steps and approval prompts). */
    internal fun describeAction(arguments: JSONObject): String {
        fun say(zh: String, en: String) = com.agentworkspace.mobile.UiText.of(this, zh, en)
        val saved = arguments.optString("snapshot_version").takeIf { it.isNotEmpty() }?.let { synchronized(recent) { recent[it] } }
        fun named(target: Target?) = target?.label?.takeIf { it.isNotBlank() }?.take(24)
        val x = arguments.optInt("x")
        val y = arguments.optInt("y")
        return when (arguments.optString("action")) {
            "tap" -> named(saved?.let { hit(it.targets.values, x, y) })?.let { say("点按「$it」", "Tap “$it”") }
                ?: say("点按屏幕 ($x, $y)", "Tap the screen at ($x, $y)")
            "swipe" -> {
                val dx = arguments.optInt("x2") - x
                val dy = arguments.optInt("y2") - y
                if (kotlin.math.abs(dy) >= kotlin.math.abs(dx)) {
                    if (dy < 0) say("向上滑动", "Swipe up") else say("向下滑动", "Swipe down")
                } else if (dx < 0) say("向左滑动", "Swipe left") else say("向右滑动", "Swipe right")
            }
            "ref" -> named(saved?.targets?.get(arguments.optString("ref")))?.let { say("点按「$it」", "Tap “$it”") }
                ?: say("点按一个控件", "Tap a control")
            "type_text" -> named(saved?.targets?.get(arguments.optString("ref")))?.let { say("在「$it」里输入文字", "Type into “$it”") }
                ?: say("输入文字", "Type text")
            "launch_app" -> {
                val name = arguments.optString("package_name")
                val label = runCatching { packageManager.getApplicationLabel(packageManager.getApplicationInfo(name, 0)).toString() }
                    .getOrNull() ?: arguments.optString("app_name").ifEmpty { name }.take(24)
                say("打开「$label」", "Open $label")
            }
            "back" -> say("返回", "Go back")
            "home" -> say("回到桌面", "Go to the home screen")
            else -> say("操作手机", "Use the phone")
        }
    }

    internal fun executeRequest(request: JSONObject): JSONObject = synchronized(executionLock) {
        var actionStarted = false
        var actionExecuted = false
        try {
            val action = request.getString("action")
            val say = { zh: String, en: String -> com.agentworkspace.mobile.UiText.of(this, zh, en) }
            when (action) {
                "observe" -> {
                    panel?.step(say("查看屏幕", "Looking at the screen"))
                    // An app busy drawing can answer slowly once; a second read usually goes through.
                    val observed = try { capture(request.optInt("max_nodes", 400), request.optInt("max_depth", 24)) }
                        catch (_: TimeoutException) { capture(request.optInt("max_nodes", 400), request.optInt("max_depth", 24)) }
                    return@synchronized result(observed)
                }
                "screenshot" -> {
                    panel?.step(say("截图看屏幕", "Taking a screenshot"))
                    return@synchronized screenshot()
                }
                "verify" -> {
                    if (request.has("snapshot_version")) requireSnapshot(request.getString("snapshot_version"))
                    return@synchronized verify(request, false)
                }
            }
            ensureUnpaused()
            val source = requireSnapshot(request.getString("snapshot_version"))
            panel?.step(describeAction(request))
            actionStarted = true
            val executed = perform(request, source)
            actionExecuted = executed
            invalidate()
            if (!executed) {
                // Android dropped the gesture or click (the user touching the screen cancels one):
                // what happened is unclear, so a person looks before anything else is done.
                AndroidAutomationControl.set(this, true, false, automatic = true)
                return@synchronized AndroidSystemBridge.failure("action_failed",
                    "Android rejected the action; automation was paused for inspection", freshObservation())
            }
            if (action == "swipe") settleScrolling() else Thread.sleep(180)
            if (request.has("expect")) return@synchronized verify(request, true)
            result(capture(), executed = true).put("verification", JSONObject().put("status", "not_requested"))
        } catch (error: AutomationFailure) {
            // Refusals come before anything reaches the screen (an app that is not installed, a control
            // that moved), so there is nothing to inspect and automation keeps running.
            AndroidSystemBridge.failure(error.code, error.message ?: "Android system action failed", freshObservation())
                .put("executed", actionExecuted)
        } catch (_: TimeoutException) {
            if (actionStarted) {
                AndroidAutomationControl.set(this, true, true, automatic = true)
                invalidate()
                AndroidSystemBridge.failure("action_timeout",
                    "Android did not confirm completion; take over before retrying", freshObservation())
                    .put("executed", if (actionExecuted) true else JSONObject.NULL).put("action_state", "unknown")
            } else {
                AndroidSystemBridge.failure("observation_timeout", "Android screen observation timed out")
            }
        } catch (_: Exception) {
            if (actionStarted) AndroidAutomationControl.set(this, true, false, automatic = true)
            AndroidSystemBridge.failure("bridge_error", "Android system operation failed", freshObservation())
                .put("executed", actionExecuted)
        }
    }

    /**
     * A swipe flings the list on after the finger lifts. Read the screen once it has stopped (at most
     * 1.5 s): read while it moves, every row's position is already wrong, and a tap computed from
     * them lands on a neighbour (on a real phone, "Storage" instead of "Battery").
     */
    private fun settleScrolling() {
        val deadline = SystemClock.uptimeMillis() + 1500
        Thread.sleep(250)
        while (SystemClock.uptimeMillis() < deadline && SystemClock.uptimeMillis() - lastScrollAt < 250) Thread.sleep(50)
    }

    private fun ensureUnpaused() {
        val control = AndroidAutomationControl.readState(this)
        if (control.optBoolean("paused") || control.optBoolean("takeover_requested")) {
            // Said plainly so the agent stops instead of trying to reach the phone some other way.
            throw AutomationFailure("paused", (if (control.optBoolean("automatic"))
                "Automation paused itself after an action Android rejected or did not confirm. "
                else "The user paused automation. ") +
                "Stop and tell the user; do not try another way to operate the phone. They can check the screen " +
                "and resume it (Retry in the phone control window, or Resume in Agent Workspace).")
        }
    }

    private fun requireSnapshot(version: String): Snapshot {
        val saved = synchronized(recent) { recent[version] }
            ?: throw AutomationFailure("stale_snapshot", "Observe the screen before acting; use a recent snapshot_version")
        // Each check says why, so the agent knows what changed. Time alone matters little (waiting
        // for an approval takes a while): the windows and the target itself are checked.
        val why = when {
            !saved.observation.optBoolean("stable") -> "Windows were opening or closing while the screen was read"
            saved.epoch != epoch.get() -> "An action ran or the display changed since this snapshot"
            saved.screen != screen() -> "The display turned or changed size"
            saved.windows != windowSignature() -> "A different window or app is showing now"
            SystemClock.elapsedRealtime() - saved.elapsed > 10 * 60_000 -> "This snapshot is over ten minutes old"
            saved.controlRevision != AndroidAutomationControl.readState(this).optString("revision") ->
                "Automation was paused or resumed since this snapshot"
            else -> return saved
        }
        throw AutomationFailure("stale_snapshot", "$why; observe again before acting")
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

    /** Reads the windows; [store] = false only looks (a check before acting) without issuing a version. */
    // Reading the windows the first time, or of an app that redraws all the time, fetches each node
    // from the app and can take seconds.
    private fun capture(maxNodes: Int = 400, maxDepth: Int = 24, store: Boolean = true): Snapshot = onReader(10_000) {
        val generation = epoch.get()
        val content = contentEpoch.get()
        val display = screen()
        val version = "$session:$generation:${sequence.incrementAndGet()}"
        val targets = linkedMapOf<String, Target>()
        val ownLabels = hashMapOf<String, String?>()
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
            val label = if (protected) null else ownLabel(node)
            targets[ref] = Target(windowId, path, Rect(bounds), className, viewId, protected, label, node.isVisibleToUser)
            ownLabels[ref] = label
            val firstInside = targets.size
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
                // Android 13+ fetches a node's descendants in one round trip instead of one per node.
                val child = (if (Build.VERSION.SDK_INT >= 33) node.getChild(index, AccessibilityNodeInfo.FLAG_PREFETCH_DESCENDANTS_HYBRID)
                    else node.getChild(index)) ?: continue
                try { visit(child, windowId, path + index, ref, depth + 1, protected) }
                finally { recycle(child) }
            }
            // A row or button without words of its own is known by the words inside it (as
            // innerLabel reads them from a live node), so a recycled row is not taken for it.
            if (label == null && !protected && node.isClickable) {
                val inner = targets.entries.drop(firstInside)
                    .filter { (_, it) -> !it.sensitive && it.path.size - path.size <= INNER_DEPTH }
                    .mapNotNull { (key, _) -> ownLabels[key]?.takeIf { it.isNotBlank() } }
                    .take(2).joinToString(" / ").take(160).ifEmpty { null }
                if (inner != null) targets[ref] = targets.getValue(ref).copy(label = inner)
            }
        }

        val allWindows = windows
        val observedWindows = appWindows(allWindows)
        val windowsBefore = signature(observedWindows)
        try {
            observedWindows.take(8).forEach { window ->
                val root = if (Build.VERSION.SDK_INT >= 33) window.getRoot(AccessibilityNodeInfo.FLAG_PREFETCH_DESCENDANTS_HYBRID)
                    else window.root
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
            allWindows.forEach { recycle(it) }
        }
        val activity = if (activePackage == lastPackage) lastActivity else null
        val data = JSONObject().put("snapshot_version", version).put("timestamp_ms", System.currentTimeMillis())
            .put("package_name", activePackage ?: JSONObject.NULL).put("activity_name", activity ?: JSONObject.NULL)
            .put("activity_source", if (activity == null) JSONObject.NULL else "accessibility_window_event")
            .put("screen", display.json()).put("windows", windowsJson).put("nodes", nodes)
            .put("truncated", truncated).put("stable", generation == epoch.get() && windowsBefore == windowSignature())
            // Content moved while it was read: fine for acting, but prefer refs or a fresh look.
            .put("content_changing", content != contentEpoch.get())
            .put("sensitive_content_redacted", sensitive)
        Snapshot(version, generation, SystemClock.elapsedRealtime(), display,
            AndroidAutomationControl.readState(this).optString("revision"), targets, data, sensitive, windowsBefore)
            .also { if (store) synchronized(recent) { recent[version] = it } }
    }

    /** What a control says by itself (an editable field: its hint). */
    private fun ownLabel(node: AccessibilityNodeInfo): String? =
        if (node.isEditable) bounded(node.hintText ?: node.contentDescription, 160)
        else bounded(node.text ?: node.contentDescription, 160)

    /** The first words inside [node], read the way capture() reads them for a control without its own. */
    private fun innerLabel(node: AccessibilityNodeInfo): String? {
        val found = mutableListOf<String>()
        fun walk(current: AccessibilityNodeInfo, depth: Int) {
            for (index in 0 until minOf(current.childCount, 400)) {
                if (found.size >= 2) return
                val child = current.getChild(index) ?: continue
                try {
                    if (child.isPassword || (Build.VERSION.SDK_INT >= 34 && child.isAccessibilityDataSensitive)) continue
                    ownLabel(child)?.takeIf { it.isNotBlank() }?.let { found += it }
                    if (depth < INNER_DEPTH) walk(child, depth + 1)
                } finally { recycle(child) }
            }
        }
        walk(node, 1)
        return found.take(2).joinToString(" / ").take(160).ifEmpty { null }
    }

    private fun freshObservation(): JSONObject? = runCatching { capture().observation }.getOrNull()

    private fun result(saved: Snapshot, executed: Boolean = false, verified: Boolean? = null): JSONObject =
        JSONObject().put("ok", true).put("executed", executed).put("verified", verified ?: JSONObject.NULL)
            .put("observation", saved.observation)

    private fun perform(request: JSONObject, saved: Snapshot): Boolean {
        return when (request.getString("action")) {
            "tap" -> gesture(saved, request.getInt("x"), request.getInt("y"), duration = 70)
            "swipe" -> gesture(saved, request.getInt("x"), request.getInt("y"), request.getInt("x2"), request.getInt("y2"), 350)
            "back", "home" -> onReader {
                recheck(saved)
                performGlobalAction(if (request.getString("action") == "back") GLOBAL_ACTION_BACK else GLOBAL_ACTION_HOME)
            }
            "launch_app" -> {
                val intent = launchIntent(request)
                onReader {
                    recheck(saved)
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    startActivity(intent)
                    true
                }
            }
            "ref", "type_text" -> actOnRef(request, saved)
            else -> throw AutomationFailure("invalid_arguments", "Unsupported Android action")
        }
    }

    /** The apps on the home screen and in the app drawer, by the name under their icon. */
    private fun launcherApps(): List<Pair<String, android.content.ComponentName>> =
        packageManager.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER), 0)
            .map { it.loadLabel(packageManager).toString().trim() to
                android.content.ComponentName(it.activityInfo.packageName, it.activityInfo.name) }

    /**
     * What launch_app opens: the package's launcher entry, or the app called [app_name] (the name
     * under its icon, as people say it: an exact name first, then the one app whose name contains it
     * or is contained in it). Models rarely know a phone maker's package names.
     */
    private fun launchIntent(request: JSONObject): Intent {
        val packageName = request.optString("package_name")
        if (packageName.isNotEmpty()) {
            packageManager.getLaunchIntentForPackage(packageName)?.let { return it }
            if (!request.has("app_name")) throw AutomationFailure("app_unavailable",
                "No installed app with a launcher entry has this package; launch it by app_name, the name under its icon")
        }
        val wanted = request.getString("app_name").trim()
        val apps = launcherApps()
        fun Pair<String, android.content.ComponentName>.app() = second.packageName
        val matches = apps.filter { it.first.equals(wanted, ignoreCase = true) }.ifEmpty {
            apps.filter { it.first.isNotEmpty() && (it.first.contains(wanted, true) || wanted.contains(it.first, true)) }
        }
        val packages = matches.map { it.app() }.distinct()
        if (packages.size == 1) return Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
            .setComponent(matches.first().second)
        if (packages.isEmpty()) throw AutomationFailure("app_unavailable",
            "No installed app is called ${wanted.take(60)}; check the name under its icon on the home screen")
        throw AutomationFailure("app_ambiguous", "Several apps match ${wanted.take(60)}: " +
            matches.distinctBy { it.app() }.take(8).joinToString("; ") { "${it.first.take(40)} (${it.app()})" } +
            ". Launch one by its exact name or package_name")
    }

    /**
     * Clicks or types into a control from the snapshot. The control is acted on directly, so it may
     * have moved (a list scrolled a little), but it must still be the same control, not a recycled row
     * showing something else. A control just off screen in a list is first scrolled into view; a text
     * that is not clickable itself is clicked through its clickable container, as a finger would.
     */
    private fun actOnRef(request: JSONObject, saved: Snapshot): Boolean {
        val target = saved.targets[request.getString("ref")]
            ?: throw AutomationFailure("unknown_ref", "The reference is not part of this screen snapshot")
        if (target.sensitive) throw AutomationFailure("protected_node", "Password and sensitive controls cannot be read or edited")
        val typing = request.getString("action") == "type_text"
        var node: AccessibilityNodeInfo? = null
        var tapAt: Rect? = null
        try {
            fun checkSame(current: AccessibilityNodeInfo) {
                val label = ownLabel(current) ?: if (current.isClickable) innerLabel(current) else null
                val now = Target(target.windowId, target.path, Rect().also { current.getBoundsInScreen(it) },
                    bounded(current.className, 160), bounded(current.viewIdResourceName, 255), false, label)
                if (!target.sameControl(now) || !current.isEnabled || current.isPassword ||
                    (Build.VERSION.SDK_INT >= 34 && current.isAccessibilityDataSensitive)) {
                    throw AutomationFailure("target_changed", "The referenced control changed; observe again")
                }
            }
            val visible = onReader {
                recheck(saved)
                val found = resolve(target) ?: throw AutomationFailure("stale_snapshot", "The referenced control disappeared; observe again")
                node = found
                checkSame(found)
                found.isVisibleToUser
            }
            if (!visible) {
                onReader { node?.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_SHOW_ON_SCREEN.id) }
                Thread.sleep(450)
                onReader { node?.refresh() }
            }
            val done = onReader {
                recheck(saved)
                val current = node ?: throw AutomationFailure("stale_snapshot", "The referenced control disappeared; observe again")
                checkSame(current)
                if (!current.isVisibleToUser) throw AutomationFailure("not_visible",
                    "The control is off screen and could not be scrolled into view; swipe to it, then observe again")
                if (typing) {
                    if (!current.isEditable) throw AutomationFailure("not_editable", "The referenced control does not accept text")
                    return@onReader current.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, Bundle().apply {
                        putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, request.getString("text"))
                    })
                }
                if (clickThrough(current)) return@onReader true
                // Neither it nor a container takes a click action (custom drawn views): tap its middle.
                tapAt = Rect().also { current.getBoundsInScreen(it) }
                false
            }
            val area = tapAt
            if (done || area == null) return done
            val (x, y) = area.centerX() to area.centerY()
            if (x !in 0 until saved.screen.width || y !in 0 until saved.screen.height) return false
            val shield = panel
            return if (shield != null) shield.outOfTheWay { dispatch(saved, x, y, x, y, 70) } else dispatch(saved, x, y, x, y, 70)
        } finally { node?.let { recycle(it) } }
    }

    /** Clicks [node], or the nearest clickable container of it (a row around its text). */
    private fun clickThrough(node: AccessibilityNodeInfo): Boolean {
        if (node.isClickable && node.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true
        var current: AccessibilityNodeInfo? = node.parent
        var depth = 0
        while (current != null && depth < 6) {
            if (current.isClickable && current.isEnabled && current.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                recycle(current)
                return true
            }
            val parent = current.parent
            recycle(current)
            current = parent
            depth += 1
        }
        current?.let { recycle(it) }
        return !node.isClickable && node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
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
        // What is under the finger must still be what the snapshot showed there: content may change
        // around it (a clock, a video), but a feed that scrolled puts another row at the same place.
        val expected = hit(saved.targets.values, x, y)
        val current = capture(store = false)
        if (current.targets.values.any { it.sensitive && it.bounds.contains(x, y) }) {
            throw AutomationFailure("protected_node", "The target contains password or sensitive content")
        }
        val now = hit(current.targets.values, x, y)
        if (if (expected == null) now != null else !expected.sameControl(now)) {
            throw AutomationFailure("target_changed", "Something else is at these coordinates now; observe again")
        }
        // The phone control panel lets the finger through to the app while the gesture runs.
        val shield = panel
        return if (shield != null) shield.outOfTheWay { dispatch(saved, x, y, x2, y2, duration) }
            else dispatch(saved, x, y, x2, y2, duration)
    }

    private fun dispatch(saved: Snapshot, x: Int, y: Int, x2: Int, y2: Int, duration: Long): Boolean {
        val completion = CountDownLatch(1)
        var completed = false
        val accepted = onReader {
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

    /** Which windows are on screen, in which order and where: what an observation's coordinates rely on. */
    private fun signature(list: List<AccessibilityWindowInfo>): String = list.joinToString(";") { window ->
        val bounds = Rect().also { window.getBoundsInScreen(it) }
        "${window.id}:${window.type}:${bounds.flattenToString()}"
    }

    private fun windowSignature(): String = onReader {
        val current = windows
        try { signature(appWindows(current)) } finally { current.forEach { recycle(it) } }
    }

    /**
     * The windows the agent works with, top first. Accessibility overlays (the phone control panel,
     * a screen reader's highlight) are not part of the app on screen.
     */
    private fun appWindows(all: List<AccessibilityWindowInfo>): List<AccessibilityWindowInfo> =
        all.filter { it.type != AccessibilityWindowInfo.TYPE_ACCESSIBILITY_OVERLAY }.sortedByDescending { it.layer }

    /** The control the finger lands on: the smallest visible one, in the topmost window there. */
    private fun hit(targets: Collection<Target>, x: Int, y: Int): Target? {
        val under = targets.filter { it.visible && it.bounds.contains(x, y) }
        val window = under.firstOrNull()?.windowId ?: return null
        return under.filter { it.windowId == window }.minByOrNull { it.bounds.width().toLong() * it.bounds.height() }
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
        // A screen other than the expected one is news for the agent, which gets it right here.
        return result(observed, executed, matched).put("ok", matched)
            .put("verification", JSONObject().put("status", if (matched) "matched" else "not_matched")
                .put("checked", JSONArray(expectation.keys().asSequence().toList())))
    }

    private class Grab(val bitmap: Bitmap, val source: String)

    private fun screenshot(): JSONObject {
        var observed = capture()
        repeat(3) {
            if (observed.sensitive) return AndroidSystemBridge.failure("protected_content",
                "Screenshot capture is blocked while password or sensitive controls are visible", observed.observation)
            val grabbed = try {
                val shield = panel
                if (shield != null) shield.outOfTheWay { grab() } else grab()
            } catch (failure: AutomationFailure) {
                return AndroidSystemBridge.failure(failure.code, failure.message ?: "Android did not provide a screenshot",
                    freshObservation())
            }
            // Content may move while the picture is taken; only another window or a turned display
            // makes the picture belong to a different screen than the observation returned with it.
            if (observed.epoch == epoch.get() && observed.screen == screen() && observed.windows == windowSignature()) {
                return saveScreenshot(grabbed, observed)
            }
            grabbed.bitmap.recycle()
            observed = capture()
        }
        return AndroidSystemBridge.failure("screen_unsettled",
            "Windows kept opening or closing during the capture; try again in a moment", observed.observation)
    }

    /** The live screen's newest frame when it is on, otherwise Android's accessibility screenshot. */
    private fun grab(): Grab {
        LiveScreen.frame()?.let { return Grab(it.bitmap, "live") }
        if (Build.VERSION.SDK_INT < 30) throw AutomationFailure("unsupported_api",
            "Screenshots on Android 10 and older need the live screen; turn it on in Device & tools")
        repeat(2) { attempt ->
            val completed = CountDownLatch(1)
            var bitmap: Bitmap? = null
            var captureError: Int? = null
            onReader {
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
            if (!completed.await(4000, TimeUnit.MILLISECONDS)) throw AutomationFailure("screenshot_timeout",
                "Android did not provide a screenshot")
            val captured = bitmap
            if (captured != null && captureError == null) return Grab(captured, "accessibility")
            captured?.recycle()
            // Android hands out about one accessibility screenshot per second.
            if (captureError == ERROR_TAKE_SCREENSHOT_INTERVAL_TIME_SHORT && attempt == 0) {
                Thread.sleep(1100)
                return@repeat
            }
            throw AutomationFailure("screenshot_unavailable",
                "Android blocked screenshot capture; secure windows cannot be captured")
        }
        throw AutomationFailure("screenshot_unavailable", "Android did not provide a screenshot")
    }

    private fun saveScreenshot(grabbed: Grab, observed: Snapshot): JSONObject {
        val captured = grabbed.bitmap
        try {
            // Every later model call carries the picture again: a 1280-pixel JPEG keeps text readable
            // at about a tenth of the bytes of a full-size PNG.
            val factor = minOf(1.0, 1280.0 / maxOf(captured.width, captured.height))
            val image = if (factor < 1.0) Bitmap.createScaledBitmap(captured,
                maxOf(1, (captured.width * factor).toInt()), maxOf(1, (captured.height * factor).toInt()), true) else captured
            try {
                val directory = File(filesDir, "workspace/automation/screenshots").apply {
                    check(mkdirs() || isDirectory)
                }
                require(directory.canonicalPath.startsWith(File(filesDir, "workspace").canonicalPath + File.separator))
                val name = "screen-${UUID.randomUUID()}.jpg"
                val output = File(directory, name)
                FileOutputStream(output).use { stream -> check(image.compress(Bitmap.CompressFormat.JPEG, 85, stream)) }
                if (output.length() > 5 * 1024 * 1024) {
                    output.delete()
                    return AndroidSystemBridge.failure("screenshot_too_large", "Android screenshot exceeds the image size limit", observed.observation)
                }
                directory.listFiles()?.filter { it.name.startsWith("screen-") && it.extension in setOf("png", "jpg") }
                    ?.sortedByDescending { it.lastModified() }?.drop(20)?.forEach { it.delete() }
                return result(observed).put("screenshot", JSONObject()
                    .put("path", "automation/screenshots/$name").put("absolute_path", output.absolutePath)
                    .put("media_type", "image/jpeg").put("snapshot_version", observed.version).put("source", grabbed.source)
                    .put("width", image.width).put("height", image.height)
                    .put("screen_width", observed.screen.width).put("screen_height", observed.screen.height)
                    .put("pixel_to_screen_x", observed.screen.width.toDouble() / image.width)
                    .put("pixel_to_screen_y", observed.screen.height.toDouble() / image.height))
            } finally { if (image !== captured) image.recycle() }
        } finally { captured.recycle() }
    }

    /**
     * Runs window reads and actions one at a time on [reader], not on the main thread: an app slow to
     * answer would otherwise freeze this process's main thread, which also draws the phone control
     * panel (Android then reports the panel as not responding).
     */
    private fun <T> onReader(timeoutMs: Long = 3000, block: () -> T): T {
        if (Looper.myLooper() == reader.looper) return block()
        val task = FutureTask(Callable { block() })
        readerHandler.post(task)
        return try { task.get(timeoutMs, TimeUnit.MILLISECONDS) }
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
