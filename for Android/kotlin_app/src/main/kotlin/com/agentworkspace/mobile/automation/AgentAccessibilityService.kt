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

/** How deep inside a list row a control is still known by the row's words (Target.context). */
private const val ROW_DEPTH = 6

/** A finger held this long is a long press on every Android version. */
private const val LONG_PRESS_MS = 650L

private val GOES_ON_SWIPE = Regex("上滑或点击|上滑跳转|向上滑动|滑动查看详情|(?i)swipe up")

/** Actions that only move the screen or press a system key: failing one does not pause automation. */
private val HARMLESS_ACTIONS = setOf("scroll", "swipe", "back", "home", "recents", "notifications", "launch_app")

/** Actions a finger or a click lands with: checked against the screen as it is at that moment. */
private val TOUCHING_ACTIONS = setOf("tap", "ref", "long_press", "type_text", "enter", "swipe")

/** A repeat without a count runs at most this long. */
private const val MAX_REPEAT_MS = 4 * 60 * 60 * 1000L
private const val MAX_IDLE_ROUNDS = 5

/**
 * How long and how many rounds a repeat may run: at most four hours, and for an unattended task
 * within what is left of its hosted limits (the engine sends them): its time, and its steps, each
 * step of every round counting as one.
 */
internal object RepeatAllowance {
    data class Limits(val ms: Long, val rounds: Int?, val byTime: Boolean, val bySteps: Boolean)

    fun of(hostedMs: Long?, hostedSteps: Int?, stepsPerRound: Int, times: Int?): Limits {
        val ms = minOf(MAX_REPEAT_MS, hostedMs ?: MAX_REPEAT_MS)
        val stepRounds = hostedSteps?.let { it / maxOf(1, stepsPerRound) }
        val rounds = listOfNotNull(times, stepRounds).minOrNull()
        return Limits(ms, rounds, byTime = ms < MAX_REPEAT_MS, bySteps = stepRounds != null && stepRounds == rounds && stepRounds != times)
    }
}

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
    // A control keeps its ref while the same windows show (read only on the reader thread), so an
    // action's result can list just what changed; other windows start the numbering afresh.
    private val refMemory = HashMap<String, String>()
    private var refWindows: String? = null
    private var refNext = 1
    @Volatile private var refEpoch = 0L
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
        /** What a finger can do with it: the screenshot marks these, scroll looks for [scrollable]. */
        val clickable: Boolean = false, val editable: Boolean = false, val scrollable: Boolean = false,
        val longClickable: Boolean = false,
        /** In or on a view that rotates what it shows by itself (a search box's hot searches). */
        val rotating: Boolean = false,
        /**
         * The first words of the list row it is in (see rowWords), null outside a list: a recycled
         * row puts another item's "删除" at the same place, under other words.
         */
        val context: String? = null,
    ) {
        val actionable: Boolean get() = clickable || editable || scrollable || longClickable

        // Counting numbers ("重新发送(59)", a timer) and the words a switcher rotates through keep a
        // control the same while it stays in place. Its row must still say the same (numbers aside):
        // the same words on the button alone used to pass a recycled row for the one approved.
        fun sameControl(other: Target?): Boolean = other != null && className == other.className &&
            viewId == other.viewId && (label == other.label || bounds == other.bounds &&
                (rotating || label?.replace(digits, "#") == other.label?.replace(digits, "#"))) &&
            TouchGuard.sameRow(context, other.context)

        companion object {
            private val digits = Regex("[0-9]+")
            private val rotators = setOf("TextSwitcher", "ImageSwitcher", "ViewSwitcher", "ViewFlipper", "AdapterViewFlipper", "ViewAnimator")
            fun rotates(className: String?): Boolean = className?.substringAfterLast('.') in rotators
        }
    }

    private data class Snapshot(
        val version: String, val epoch: Long, val elapsed: Long, val screen: Screen, val controlRevision: String,
        val targets: Map<String, Target>, val observation: JSONObject, val sensitive: Boolean,
        val windows: String = "",
    )

    /** [confirmation]: with needs_confirmation, the token the engine keeps for the user's yes. */
    private class AutomationFailure(val code: String, message: String, val confirmation: String? = null) : RuntimeException(message)

    private val confirmations = ConfirmationBook({ SystemClock.elapsedRealtime() })

    override fun onServiceConnected() {
        super.onServiceConnected()
        AndroidSystemBridge.initialize(this)
        AndroidSystemBridge.service = this
        (getSystemService(Context.DISPLAY_SERVICE) as DisplayManager).registerDisplayListener(this, handler)
        invalidate()
        // For the app's own process, which asks whether the service runs (AndroidSystemBridge.status).
        AndroidAutomationControl.connected(this, true)
        // No system accessibility button: Android would pin it to every screen, in the agent's
        // screenshots too. The panel opens from the bubble and stays up over screens that hide
        // other apps' overlays (Settings), so a task can still go there.
    }

    /** When a list last moved: a fling keeps it going after the finger lifts. */
    @Volatile private var lastScrollAt = 0L

    /** The display the request being run works on: the phone's screen, or the background screen. */
    @Volatile private var screenId = Display.DEFAULT_DISPLAY
    private val onBackground: Boolean get() = screenId != Display.DEFAULT_DISPLAY

    /** Whether the user started the request's task on the phone in person (the engine says). */
    @Volatile private var taskInPerson = false

    /** The windows of [display] (the background screen's when the agent works there). */
    private fun screenWindows(display: Int = screenId): List<AccessibilityWindowInfo> =
        if (display == Display.DEFAULT_DISPLAY || Build.VERSION.SDK_INT < 30) windows
        else windowsOnAllDisplays.get(display) ?: emptyList()

    /** For PopupWatch: when the user last touched something, and when the agent last acted. */
    @Volatile private var touchedAt = 0L
    @Volatile private var agentActedAt = 0L
    @Volatile private var overlayCheckPending = false

    /** 「演示一遍」: the user's own taps being recorded as a shortcut (main thread). */
    private var demonstration: DemonstrationRecorder? = null
    val demonstrating: Boolean get() = demonstration != null

    /** Starts recording the user's taps (main thread); false while the agent works the phone. */
    fun startDemonstration(): Boolean {
        if (demonstration != null) return true
        // Not while the agent is working the phone: its taps are not the user's.
        if (SystemClock.uptimeMillis() - agentActedAt < 3000) return false
        DemonstrationRecorder.resultFile(this).delete()
        demonstration = DemonstrationRecorder(this) {
            demonstration = null
            // Back to the app, where the Shortcuts page shows the steps to check and save.
            packageManager.getLaunchIntentForPackage(packageName)?.let { intent ->
                runCatching { startActivity(intent.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK or android.content.Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED)) }
            }
        }.also { it.start() }
        return true
    }

    fun stopDemonstration(keep: Boolean) { demonstration?.stop(keep) }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Window events arrive late or for windows that end up where they were, so they only count as
        // content; whether the windows changed is decided by comparing them (windowSignature).
        contentEpoch.incrementAndGet()
        if (event != null && SystemClock.uptimeMillis() - agentActedAt > 1500) demonstration?.onEvent(event)
        when (event?.eventType) {
            AccessibilityEvent.TYPE_VIEW_SCROLLED -> lastScrollAt = SystemClock.uptimeMillis()
            AccessibilityEvent.TYPE_VIEW_CLICKED, AccessibilityEvent.TYPE_VIEW_LONG_CLICKED,
            AccessibilityEvent.TYPE_VIEW_CONTEXT_CLICKED, AccessibilityEvent.TYPE_TOUCH_INTERACTION_START,
            AccessibilityEvent.TYPE_GESTURE_DETECTION_START -> touchedAt = SystemClock.uptimeMillis()
            AccessibilityEvent.TYPE_WINDOWS_CHANGED -> if (!overlayCheckPending && PopupWatch.enabled(this)) {
                overlayCheckPending = true
                readerHandler.postDelayed({ overlayCheckPending = false; checkOverlays() }, 400)
            }
        }
        if (event?.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            val packageName = bounded(event.packageName, 255)
            val className = bounded(event.className, 255)
            if (packageName != null && className != null && className.contains('.') &&
                !className.startsWith("android.widget.") && !className.startsWith("android.view.")) {
                // Another app came to the front: automatic triggers may be waiting for it.
                if (packageName != lastPackage && packageName != this.packageName) {
                    com.agentworkspace.mobile.embedded.TriggerEvents.appOpened(this, packageName)
                }
                if (packageName != lastPackage) PopupWatch.frontChanged(this, packageName, touchedAt, agentActedAt)
                lastPackage = packageName
                lastActivity = className
            }
        }
    }

    /** Floating windows over most of the phone's screen, by app (reader thread). */
    private fun checkOverlays() {
        val size = screen(Display.DEFAULT_DISPLAY)
        if (size.width <= 0 || size.height <= 0) return
        val large = HashSet<String>()
        val all = runCatching { screenWindows(Display.DEFAULT_DISPLAY) }.getOrDefault(emptyList())
        try {
            for (window in all) {
                if (window.type != AccessibilityWindowInfo.TYPE_SYSTEM) continue
                val bounds = Rect().also { window.getBoundsInScreen(it) }
                if (!bounds.intersect(0, 0, size.width, size.height) ||
                    bounds.width().toLong() * bounds.height() < size.width.toLong() * size.height * 2 / 5) continue
                val root = window.root ?: continue
                try { bounded(root.packageName, 255)?.let(large::add) } finally { recycle(root) }
            }
        } finally { all.forEach { recycle(it) } }
        PopupWatch.overlays(this, large, lastPackage, agentActedAt)
    }

    override fun onInterrupt() {
        invalidate()
        // Any app may call AccessibilityManager.interrupt(); this service gives no spoken feedback to
        // stop. Automation still pauses (the user resumes it), but as a pause of its own with this
        // reason: it used to be recorded as the user taking over, and the agent told the user so.
        AndroidAutomationControl.set(this, true, false, automatic = true, reason = AndroidAutomationControl.INTERRUPTED)
    }

    override fun onDestroy() {
        demonstration?.stop(false)
        stopRepeat("the accessibility service stopped")
        // Forced: the repeat's stop is only posted, so the panel would still shrink to its pill
        // and keep its window, blur listener, coroutines and polling after the service is gone.
        panel?.close(force = true)
        panel = null
        reader.quitSafely()
        (getSystemService(Context.DISPLAY_SERVICE) as DisplayManager).unregisterDisplayListener(this)
        // A newer instance already connected has written its own state; this one must not undo it.
        if (AndroidSystemBridge.service === this) {
            AndroidSystemBridge.service = null
            AndroidAutomationControl.connected(this, false)
        }
        invalidate()
        super.onDestroy()
    }

    // Only the screen the agent works on changing makes its reads stale: turning the phone while
    // the agent works on the background screen leaves that screen as it was, and another display
    // coming (a cast) leaves the phone's screen as it was. A display going away may take a read.
    override fun onDisplayAdded(displayId: Int) { if (displayId == screenId) invalidate() }
    override fun onDisplayRemoved(displayId: Int) = invalidate()
    override fun onDisplayChanged(displayId: Int) { if (displayId == screenId) invalidate() }

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

    /**
     * In words, what an android_action request does (the panel's steps and approval prompts).
     * [forApproval]: for the person deciding, also the text to be typed and every step of a batch
     * (steps that send, delete or pay marked ⚠); the panel's step list keeps the short form, which is
     * also what it remembers for the app.
     */
    internal fun describeAction(arguments: JSONObject, forApproval: Boolean = false): String {
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
                // One that stays on a control presses it: the person approving is told so.
                val pressed = saved?.let { snapshot ->
                    if (TouchGuard.barelyMoves(x, y, x + dx, y + dy, snapshot.screen.density)) hit(snapshot.targets.values, x, y)?.label
                    else pressedBySwipe(arguments, snapshot).firstNotNullOfOrNull { it.label }
                }?.takeIf { it.isNotBlank() }?.take(24)
                if (pressed != null) say("点按「$pressed」", "Tap “$pressed”")
                else if (kotlin.math.abs(dy) >= kotlin.math.abs(dx)) {
                    if (dy < 0) say("向上滑动", "Swipe up") else say("向下滑动", "Swipe down")
                } else if (dx < 0) say("向左滑动", "Swipe left") else say("向右滑动", "Swipe right")
            }
            "ref" -> named(saved?.targets?.get(arguments.optString("ref")))?.let { say("点按「$it」", "Tap “$it”") }
                ?: say("点按一个控件", "Tap a control")
            "type_text" -> {
                val field = named(saved?.targets?.get(arguments.optString("ref")))
                val typed = arguments.optString("text")
                if (forApproval && typed.isNotEmpty()) {
                    // What is approved is what gets typed: the start of it, and how long it is.
                    // Each case is a whole sentence, so the Japanese and Korean catalogs translate it.
                    val (start, more) = TouchGuard.typedPreview(typed)
                    val count = typed.length
                    when {
                        field != null && more -> say("在「$field」里输入“$start”…（共 $count 字）", "Type “$start”… ($count characters) into “$field”")
                        field != null -> say("在「$field」里输入“$start”", "Type “$start” into “$field”")
                        more -> say("输入“$start”…（共 $count 字）", "Type “$start”… ($count characters)")
                        else -> say("输入“$start”", "Type “$start”")
                    }
                } else field?.let { say("在「$it」里输入文字", "Type into “$it”") } ?: say("输入文字", "Type text")
            }
            "launch_app" -> {
                val name = arguments.optString("package_name")
                val label = runCatching { packageManager.getApplicationLabel(packageManager.getApplicationInfo(name, 0)).toString() }
                    .getOrNull() ?: arguments.optString("app_name").ifEmpty { name }.take(24)
                say("打开「$label」", "Open $label")
            }
            "long_press" -> (if (arguments.has("ref")) named(saved?.targets?.get(arguments.optString("ref")))
                else named(saved?.let { hit(it.targets.values, x, y) }))?.let { say("长按「$it」", "Long-press “$it”") }
                ?: say("长按", "Long-press")
            "scroll" -> when (arguments.optString("direction")) {
                "up" -> say("往上翻", "Scroll up")
                "top" -> say("翻到最上面", "Scroll to the top")
                "bottom" -> say("翻到最下面", "Scroll to the bottom")
                "left" -> say("往左翻", "Scroll left")
                "right" -> say("往右翻", "Scroll right")
                else -> say("往下翻", "Scroll down")
            }
            "enter" -> say("按键盘上的确认键", "Press the keyboard's enter key")
            "recents" -> say("打开最近任务", "Open recent apps")
            "notifications" -> say("下拉通知栏", "Open the notifications")
            "batch" -> {
                val steps = arguments.optJSONArray("steps") ?: JSONArray()
                // Approved, every step is shown (a batch has at most 12): a "发送" at step 6 is in it.
                val shown = if (forApproval) steps.length() else minOf(steps.length(), 4)
                val parts = (0 until shown).map { index ->
                    describeAction(JSONObject(steps.getJSONObject(index).toString())
                        .put("snapshot_version", arguments.optString("snapshot_version")), forApproval)
                        .let { if (forApproval && TouchGuard.weighty(it)) "⚠ $it" else it }
                }
                say("连续 ${steps.length()} 步：", "${steps.length()} steps: ") + parts.joinToString(say("，", ", ")) +
                    (if (steps.length() > shown) say("……", "…") else "")
            }
            "repeat" -> {
                val seconds = arguments.optLong("every_ms") / 1000.0
                val every = if (seconds == Math.floor(seconds)) seconds.toLong().toString() else "%.1f".format(seconds)
                val what = describeAction(JSONObject().put("action", "batch").put("steps", arguments.optJSONArray("steps") ?: JSONArray())
                    .put("snapshot_version", arguments.optString("snapshot_version")), forApproval)
                    .substringAfter("：").substringAfter(": ")
                val times = if (arguments.has("times")) arguments.optInt("times") else null
                say("每 $every 秒：$what" + (times?.let { "，共 $it 次" } ?: "，直到停止（最长 4 小时）"),
                    "Every $every s: $what" + (times?.let { ", $it times" } ?: ", until stopped (4 hours at most)"))
            }
            "stop_repeat" -> say("停止定时重复", "Stop the repeat")
            "tap_text" -> arguments.optString("text").take(24).let { say("点按「$it」", "Tap “$it”") }
            "scroll_to_text" -> arguments.optString("text").take(24).let {
                if (arguments.optBoolean("tap")) say("翻找「$it」并点开", "Scroll to “$it” and tap it")
                else say("翻找「$it」", "Scroll to “$it”")
            }
            "wait_for" -> arguments.optString("text").ifEmpty { null }?.take(24)?.let { say("等待出现「$it」", "Wait for “$it”") }
                ?: arguments.optString("gone_text").take(24).let { say("等待「$it」消失", "Wait until “$it” is gone") }
            "open_page" -> say("打开「${pageName(arguments, true)}」", "Open ${pageName(arguments, false)}")
            "back" -> say("返回", "Go back")
            "home" -> say("回到桌面", "Go to the home screen")
            else -> say("操作手机", "Use the phone")
        }
    }

    /** An app in front that the agent keeps away from: one the user listed, or one 长辈模式 guards. */
    private class Blocked(val label: String, private val elder: Boolean) {
        override fun toString() = label

        /** For the model; [brought]: the action itself brought the app up. */
        fun refusal(brought: Boolean): String = when {
            elder -> "In elder mode the agent does not use $label: installing or removing apps and remote control " +
                "are how many scams work. Stop and tell them plainly; a family member can help if it is really needed."
            brought -> "That brought up $label, which the user does not let the agent read or use. Stop here and tell the user."
            else -> "The user does not let the agent read or use $label. Stop here and tell the user: they can do " +
                "this themselves, or take the app off the list under Device & tools."
        }
    }

    // The phone's own installers, also under a maker's name ElderGuard does not list (looked up once).
    private val systemInstallers: Set<String> by lazy { ElderGuard.installerPackages(packageManager) }

    private fun blockedFront(): Blocked? {
        val elder = ElderGuard.on(this)
        if (BlockedApps.packages(this).isEmpty() && !elder) return null
        // Not only the app in front: one in the other half of a split screen or in a small window is
        // on the screen as well, and its windows are read and can be tapped like the front one's.
        val shown = (listOfNotNull(frontPackage()) + appsOnScreen()).distinct()
        val front = shown.firstOrNull { (elder && ElderGuard.guarded(it, systemInstallers)) || BlockedApps.blocked(this, it) } ?: return null
        val guarded = elder && ElderGuard.guarded(front, systemInstallers)
        val label = runCatching { packageManager.getApplicationLabel(packageManager.getApplicationInfo(front, 0)).toString() }
            .getOrDefault(front)
        return Blocked(label, guarded)
    }

    /** The packages of every app window on the screen the agent works on. */
    private fun appsOnScreen(): List<String> = onReader {
        val all = screenWindows()
        try {
            all.filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION }
                .mapNotNull { window -> window.root?.let { root -> root.packageName?.toString().also { recycle(root) } } }
        } finally { all.forEach { recycle(it) } }
    }

    // ---- A task recorded as a shortcut, and a shortcut run again ------------------------------

    @Volatile private var recording: MutableList<JSONObject>? = null
    @Volatile private var replayStop = false

    /** From now on, each action done is kept (the panel saves them as a shortcut if asked). */
    internal fun startRecording() { recording = java.util.Collections.synchronizedList(ArrayList()) }

    internal fun takeRecording(): List<JSONObject> = recording?.toList().orEmpty().also { recording = null }

    /** The actions kept so far, still recording (a chat task's steps; the panel takes its own). */
    internal fun peekRecording(): List<JSONObject> = recording?.toList().orEmpty()

    // ---- Step replay: a small picture after each action of a task (StepShots) -------------------

    @Volatile private var shotTask: String? = null
    @Volatile private var shotIndex = 0
    private val shotWorker = java.util.concurrent.Executors.newSingleThreadExecutor { Thread(it, "agent-step-shots") }

    internal fun beginStepShots(taskId: String) {
        shotTask = taskId.takeIf { Regex("[A-Za-z0-9-]{1,64}").matches(it) }
        shotIndex = 0
        shotWorker.execute { runCatching { StepShots.prune(this) } }
    }

    internal fun endStepShots() { shotTask = null }

    /**
     * After the screen settles. A screen with protected content, or a screenshot Android refuses (one a
     * second at most), leaves the step without a picture. [point]: where the action touched.
     */
    private fun shootStep(label: String, point: Pair<Float, Float>? = null) {
        val task = shotTask ?: return
        val index = ++shotIndex
        if (index > 60) return
        val step = StepShots.Step(index, label, System.currentTimeMillis(), point)
        // The picture is taken later, after the request: of the screen the action was on.
        val on = screenId
        shotWorker.execute {
            Thread.sleep(700)
            if (shotTask != task) return@execute
            val shotAt = System.currentTimeMillis()
            // Not stored: the agent's current snapshot must stay the one it acts on.
            val grabbed = runCatching { if (capture(store = false, on = on).sensitive) null else grab(on) }.getOrNull()
            val covers = if (grabbed == null) emptyList() else runCatching { floatingWindows(on) }.getOrDefault(emptyList())
            try { runCatching { StepShots.save(this, task, step, grabbed?.bitmap, shotAt, covers) } } finally { grabbed?.bitmap?.recycle() }
        }
    }

    /**
     * Small windows floating over the app (this app's bubble and stop button, a phone's floating
     * assist button or side-bar handle), as fractions of the screen: a tutorial made from the pictures
     * paints them out, since whoever follows it has none of them.
     */
    private fun floatingWindows(on: Int): List<FloatArray> {
        val size = screen(on)
        if (size.width <= 0 || size.height <= 0) return emptyList()
        val found = ArrayList<FloatArray>()
        val all = screenWindows(on)
        try {
            for (window in all) {
                if (window.type != AccessibilityWindowInfo.TYPE_SYSTEM &&
                    window.type != AccessibilityWindowInfo.TYPE_ACCESSIBILITY_OVERLAY) continue
                val bounds = Rect().also { window.getBoundsInScreen(it) }
                // By shape, as phones draw such buttons from their system UI too: bars along the screen
                // (status, navigation) and large windows (a dialog, the task panel) are part of the picture.
                if (bounds.isEmpty || bounds.width() > size.width * 0.6 || bounds.height() > size.height * 0.6 ||
                    bounds.width().toLong() * bounds.height() > size.width.toLong() * size.height / 6) continue
                // Such a window may reach past the screen's edge: only the part on it is pictured.
                if (!bounds.intersect(0, 0, size.width, size.height)) continue
                found.add(floatArrayOf(bounds.left.toFloat() / size.width, bounds.top.toFloat() / size.height,
                    bounds.right.toFloat() / size.width, bounds.bottom.toFloat() / size.height))
            }
        } finally { all.forEach { recycle(it) } }
        return found
    }

    /** Where on the screen an action touched, as fractions of it; null for one that touched no spot. */
    private fun touchedPoint(request: JSONObject, source: Snapshot): Pair<Float, Float>? {
        if (source.screen.width <= 0 || source.screen.height <= 0) return null
        fun center(ref: String) = source.targets[ref]?.bounds?.let { it.exactCenterX() to it.exactCenterY() }
        val (x, y) = when (request.optString("action")) {
            "ref", "type_text" -> center(request.optString("ref"))
            "long_press" -> if (request.has("ref")) center(request.optString("ref"))
                else request.optInt("x").toFloat() to request.optInt("y").toFloat()
            "tap" -> request.optInt("x").toFloat() to request.optInt("y").toFloat()
            else -> null
        } ?: return null
        return (x / source.screen.width).coerceIn(0f, 1f) to (y / source.screen.height).coerceIn(0f, 1f)
    }

    /**
     * Where a recorded task starts, as its first step: the app in front (opened first when the
     * shortcut runs again) or the home screen. Nothing when this app is in front.
     */
    internal fun recordStartingPoint() {
        val front = runCatching { frontPackage() }.getOrNull() ?: return
        if (front == packageName || front == "com.android.systemui") return
        // Settings also answers the home intent (its FallbackHome, only used while booting).
        val homes = runCatching {
            packageManager.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME), 0)
                .map { it.activityInfo.packageName }.toSet() - "com.android.settings"
        }.getOrDefault(emptySet())
        record(if (front in homes || "launcher" in front) JSONObject().put("kind", "key").put("key", "home")
            else JSONObject().put("kind", "launch").put("package", front))
    }

    private fun record(step: JSONObject?) {
        val list = recording ?: return
        if (step != null && list.size < 60) list.add(step)
    }

    /** An action as a step that can be found again later: by the words of what it touched. */
    private fun recordAction(request: JSONObject, source: Snapshot) {
        if (recording == null) return
        fun spot(target: Target?, x: Int, y: Int) = JSONObject().put("x", x).put("y", y)
            .put("label", target?.label?.takeIf { it.isNotBlank() } ?: JSONObject.NULL)
            .put("class", target?.className ?: JSONObject.NULL)
        val x = request.optInt("x")
        val y = request.optInt("y")
        val byRef = source.targets[request.optString("ref")]
        val action = request.optString("action")
        fun optional(step: JSONObject) = step.apply {
            if (PhoneMemory.closesPopup(optString("label").takeUnless { isNull("label") }, optString("class").takeUnless { isNull("class") })) {
                put("optional", true)
            }
        }
        record(when (action) {
            "ref" -> byRef?.let { optional(spot(it, it.bounds.centerX(), it.bounds.centerY()).put("kind", "tap")) }
            "tap" -> optional(spot(hit(source.targets.values, x, y), x, y).put("kind", "tap"))
            "long_press" -> (byRef?.let { spot(it, it.bounds.centerX(), it.bounds.centerY()) }
                ?: spot(hit(source.targets.values, x, y), x, y)).put("kind", "long")
            "type_text" -> byRef?.let { spot(it, it.bounds.centerX(), it.bounds.centerY()).put("kind", "type")
                .put("text", request.optString("text")) }
            "enter" -> JSONObject().put("kind", "enter")
            "scroll" -> JSONObject().put("kind", "scroll").put("direction", request.optString("direction"))
            "swipe" -> JSONObject().put("kind", "swipe").put("x", x).put("y", y)
                .put("x2", request.optInt("x2")).put("y2", request.optInt("y2"))
            "launch_app" -> runCatching { launchIntent(request).let { it.component?.packageName ?: it.`package` } }
                .getOrNull()?.let { JSONObject().put("kind", "launch").put("package", it) }
            "back", "home", "recents", "notifications" -> JSONObject().put("kind", "key").put("key", action)
            else -> null
        })
    }

    internal fun stopReplay() { replayStop = true }

    /** The step the last replay stopped at (an index into the steps it was given), or -1. */
    @Volatile internal var replayStoppedAt = -1

    /**
     * Runs a saved shortcut on the screen as it is now: each step finds its control again by its
     * words (where it was is only a fallback for controls without words). Null when it got through,
     * else why it stopped. Not recorded itself; paused or kept-away apps stop it like any action.
     */
    internal fun replay(steps: JSONArray): String? {
        replayStop = false
        replayStoppedAt = -1
        val kept = recording
        recording = null
        try {
            for (index in 0 until steps.length()) {
                replayStoppedAt = index
                if (replayStop) return com.agentworkspace.mobile.UiText.of(this, "你停止了它", "you stopped it")
                val step = steps.optJSONObject(index) ?: continue
                var request: JSONObject? = null
                var problem: String? = null
                val label = step.optString("label").takeUnless { step.isNull("label") || it.isBlank() }
                // When its control is missing: close what is in the way (an ad, a splash screen, a
                // popup), give a splash time to end, then scroll the page to it; look again after each
                // that did something.
                val recoveries = listOf(null, { dismissPopup() },
                    { label != null && !step.optBoolean("optional") && waitForLabel(label) },
                    { label != null && !step.optBoolean("optional") && scrollToLabel(label) })
                for (recovery in recoveries) {
                    if (recovery != null && !recovery()) continue
                    try {
                        request = replayRequest(step)
                        break
                    } catch (failure: AutomationFailure) {
                        problem = failure.message ?: failure.code
                        if (failure.code != "not_found") break
                    }
                }
                if (request == null) {
                    // A tap that closed an ad when this was recorded: no ad this time.
                    if (step.optBoolean("optional")) continue
                    return problem
                }
                val response = executeRequest(request)
                if (!response.optBoolean("ok", true)) {
                    return response.optJSONObject("error")?.optString("message")
                        ?: com.agentworkspace.mobile.UiText.of(this, "第 ${index + 1} 步没有成功", "Step ${index + 1} did not work")
                }
            }
            replayStoppedAt = -1
            return null
        } finally { recording = kept }
    }

    /** Taps one visible ad or popup close control, if there is one; true when it did. */
    private fun dismissPopup(): Boolean {
        val observed = capture()
        val close = observed.targets.entries.firstOrNull { (_, target) ->
            target.visible && !target.sensitive && PhoneMemory.closesPopup(target.label, target.className)
        }
            ?: return false
        val response = executeRequest(JSONObject().put("action", "ref").put("ref", close.key).put("snapshot_version", observed.version))
        Thread.sleep(700)
        return response.optBoolean("ok", true)
    }

    /** A splash screen with no close control yet, or a page still loading: up to 6 s for these words to show. */
    private fun waitForLabel(label: String): Boolean {
        repeat(12) {
            if (replayStop) return false
            Thread.sleep(500)
            dismissPopup()
            if (textMatches(capture(), label).any { it.value.visible }) return true
        }
        return false
    }

    /** An ad that opens another app on a swipe says so ("上滑或点击 跳转详情或第三方应用"). */
    private fun goesOnSwipe(observed: Snapshot): Boolean =
        observed.targets.values.any { it.visible && it.label?.let(GOES_ON_SWIPE::containsMatchIn) == true }

    /** Scrolls the page until a control with these words is on screen; true when one is. */
    private fun scrollToLabel(label: String): Boolean {
        val before = capture()
        if (goesOnSwipe(before)) return false
        val app = observedPackage(before.observation)
        val answer = executeRequest(JSONObject().put("action", "scroll_to_text").put("text", label.take(200)).put("max_scrolls", 10))
        if (answer.optBoolean("ok", false)) return true
        val code = answer.optJSONObject("error")?.optString("code")
        android.util.Log.i("AgentReplay", "scroll_to_text for a shortcut step: $code")
        // Scrolled to the end of the list without it: swiping will not find it either.
        if (code == "not_found" || code == "blocked_app" || code == "paused") return false
        // A list the accessibility tree does not mark as scrollable: swipe up a screen at a time.
        repeat(8) {
            val observed = capture()
            // A swipe that left the app is no longer looking through its page (an unreadable
            // snapshot is not taken for another app).
            val now = observedPackage(observed.observation)
            if ((now != null && now != app) || goesOnSwipe(observed)) return false
            val width = observed.screen.width
            val height = observed.screen.height
            val swiped = executeRequest(JSONObject().put("action", "swipe").put("snapshot_version", observed.version)
                .put("x", width / 2).put("y", height * 3 / 4).put("x2", width / 2).put("y2", height / 3))
            if (!swiped.optBoolean("ok", true)) return false
            if (textMatches(capture(), label).any { it.value.visible }) return true
        }
        return false
    }

    private fun replayRequest(step: JSONObject): JSONObject {
        val observed = capture()
        val request = JSONObject().put("snapshot_version", observed.version)
        val label = step.optString("label").takeUnless { step.isNull("label") || it.isEmpty() }
        fun located(editable: Boolean = false): String? {
            if (label == null) return null
            val x = step.optInt("x")
            val y = step.optInt("y")
            return textMatches(observed, label).filter { it.value.visible && (!editable || it.value.editable) }
                .sortedWith(compareBy({ it.value.className != step.optString("class") },
                    { kotlin.math.abs(it.value.bounds.centerX() - x) + kotlin.math.abs(it.value.bounds.centerY() - y) }))
                .firstOrNull()?.key ?: throw AutomationFailure("not_found", com.agentworkspace.mobile.UiText.of(this,
                    "屏幕上找不到「${label.take(30)}」", "“${label.take(30)}” is not on the screen"))
        }
        return when (step.optString("kind")) {
            "tap" -> located()?.let { request.put("action", "ref").put("ref", it) }
                ?: request.put("action", "tap").put("x", step.optInt("x")).put("y", step.optInt("y"))
            "long" -> located()?.let { request.put("action", "long_press").put("ref", it) }
                ?: request.put("action", "long_press").put("x", step.optInt("x")).put("y", step.optInt("y"))
            "type" -> request.put("action", "type_text").put("ref", located(editable = true)
                ?: throw AutomationFailure("not_found", "no field")).put("text", step.optString("text"))
            "enter" -> request.put("action", "enter")
            "scroll" -> request.put("action", "scroll").put("direction", step.optString("direction", "down"))
            "swipe" -> request.put("action", "swipe").put("x", step.optInt("x")).put("y", step.optInt("y"))
                .put("x2", step.optInt("x2")).put("y2", step.optInt("y2"))
            "launch" -> request.put("action", "launch_app").put("package_name", step.getString("package"))
            "key" -> request.put("action", step.getString("key"))
            "page" -> JSONObject(step.getJSONObject("request").toString())
            "find" -> JSONObject().put("action", "scroll_to_text").put("text", step.getString("text")).put("tap", step.optBoolean("tap"))
            else -> throw AutomationFailure("invalid_arguments", "unknown step")
        }
    }

    /** What open_page opens, as the approval prompt names it. */
    private fun pageName(arguments: JSONObject, chinese: Boolean): String {
        val names = mapOf(
            "settings" to ("设置" to "Settings"), "wifi" to ("WLAN 设置" to "Wi-Fi settings"),
            "bluetooth" to ("蓝牙设置" to "Bluetooth settings"), "mobile_network" to ("移动网络设置" to "mobile network settings"),
            "data_usage" to ("流量使用" to "data usage"), "airplane" to ("飞行模式设置" to "airplane mode settings"),
            "battery" to ("电池" to "battery"), "display" to ("显示设置" to "display settings"),
            "sound" to ("声音设置" to "sound settings"), "location" to ("位置信息设置" to "location settings"),
            "storage" to ("存储" to "storage"), "date" to ("日期和时间" to "date and time"),
            "language" to ("语言设置" to "language settings"), "accessibility" to ("无障碍设置" to "accessibility settings"),
            "security" to ("安全设置" to "security settings"), "nfc" to ("NFC 设置" to "NFC settings"),
            "vpn" to ("VPN 设置" to "VPN settings"), "developer" to ("开发者选项" to "developer options"),
            "apps" to ("应用管理" to "apps"), "notifications" to ("通知设置" to "notification settings"),
            "app_details" to ("应用信息" to "app info"), "url" to ("网页" to "the web page"),
            "map" to ("地图搜索" to "a map search"), "web_search" to ("网页搜索" to "a web search"),
            "dial" to ("拨号界面" to "the dialer"),
        )
        val page = arguments.optString("page")
        val name = names[page]?.let { if (chinese) it.first else it.second } ?: page
        val detail = arguments.optString("app_name").ifEmpty { arguments.optString("package_name") }
            .ifEmpty { arguments.optString("url") }.ifEmpty { arguments.optString("query") }.ifEmpty { arguments.optString("number") }
        return if (detail.isEmpty()) name else "$name：${detail.take(60)}"
    }

    /**
     * [settle]: wait for a page to finish loading before reading it back (not between a batch's steps).
     * Whatever the action, the screen of an app the user keeps the agent away from is not returned.
     */
    internal fun executeRequest(request: JSONObject, settle: Boolean = true, background: Boolean = false, byUser: Boolean = false,
        inPerson: Boolean? = null): JSONObject =
        synchronized(executionLock) {
        // A batch runs its steps through here too: they stay on the screen the batch works on, for
        // the same task.
        val outer = screenId
        val outerInPerson = taskInPerson
        if (inPerson != null) taskInPerson = inPerson
        // A task from a conversation works on the background screen when the user turned it on
        // (BackgroundScreen); the phone control panel's tasks always use the phone's own screen.
        if (background && BackgroundScreen.enabled(this)) {
            screenId = try { BackgroundScreen.open(this) } catch (error: Exception) {
                return@synchronized AndroidSystemBridge.failure("background_unavailable",
                    "Background operation is on, but the background screen is unavailable: ${error.message}. Shizuku " +
                    "stops when the phone restarts. Stop and tell the user: start Shizuku again, or turn off background " +
                    "operation under Device & tools so the agent uses the phone's own screen.")
            }
        }
        try {
            val response = executeUnguarded(request, settle, byUser)
            if (response.isNull("observation") || response.optJSONObject("error")?.optString("code") == "blocked_app") {
                return@synchronized response
            }
            val blocked = runCatching { blockedFront() }.getOrNull() ?: return@synchronized response
            // The action opened (or went into) such an app: say so, without its screen.
            AndroidSystemBridge.failure("blocked_app", blocked.refusal(true)).put("executed", response.optBoolean("executed"))
        } finally {
            screenId = outer
            taskInPerson = outerInPerson
            agentActedAt = SystemClock.uptimeMillis()
        }
    }

    /**
     * The words on the screen, for a request sent with "send the words on the screen" on: visible
     * text of the apps under the panel, never password or sensitive fields, nothing of an app the
     * user keeps the agent away from (observe refuses those), at most [limit] characters.
     */
    internal fun screenWords(limit: Int): String {
        val result = executeRequest(JSONObject().put("action", "observe"))
        val observation = result.optJSONObject("observation") ?: return ""
        val windows = observation.optJSONArray("windows")
        val ours = (0 until (windows?.length() ?: 0)).map { windows!!.getJSONObject(it) }
            .filter { it.optString("package_name") == packageName }.map { it.optInt("id") }.toSet()
        val nodes = observation.optJSONArray("nodes") ?: return ""
        val words = LinkedHashSet<String>()
        for (index in 0 until nodes.length()) {
            val node = nodes.getJSONObject(index)
            if (node.optBoolean("sensitive") || node.optBoolean("password") || node.optInt("window_id") in ours) continue
            if (node.has("visible") && !node.optBoolean("visible")) continue
            val text = node.optString("text").ifBlank { node.optString("description") }.trim()
            if (text.isNotEmpty() && text.length <= 300) words.add(text)
        }
        return words.joinToString(" / ").take(limit)
    }

    /**
     * This app, which the agent neither reads nor operates. A debuggable build (never published)
     * leaves it open, so the evaluation scenarios that work its own screens can run there
     * (mobile_evaluation lists them only in such a build).
     */
    private val keptAway: String? by lazy {
        if (applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE != 0) null else packageName
    }

    private fun ownApp() = AutomationFailure("own_app", "This is Agent Workspace itself, whose approvals and settings are " +
        "the user's: the agent does not read or operate it, in any mode. Open the app the task is about with launch_app or " +
        "open_page; anything to do in Agent Workspace is for the user, so tell them.")

    private fun executeUnguarded(request: JSONObject, settle: Boolean, byUser: Boolean = false): JSONObject = synchronized(executionLock) {
        // An app the agent opens comes to the front while the action runs: not a pop-up (PopupWatch).
        agentActedAt = SystemClock.uptimeMillis()
        var actionStarted = false
        var actionExecuted = false
        // Moving the screen or pressing a system key changes nothing in an app: when Android drops one
        // (or the page changes under it), the agent looks again instead of everything stopping.
        val harmless = request.optString("action") in HARMLESS_ACTIONS
        try {
            val action = request.getString("action")
            val say = { zh: String, en: String -> com.agentworkspace.mobile.UiText.of(this, zh, en) }
            // An app the user keeps away from the agent: nothing of it is read, nothing is done in it.
            if (action != "stop_repeat") blockedFront()?.let { blocked ->
                return@synchronized AndroidSystemBridge.failure("blocked_app", blocked.refusal(false))
            }
            // With this app in front the agent can only leave it (nothing of it is read: see capture).
            if (TouchGuard.refusedInOwnApp(action, byUser) && keptAway != null && frontPackage() == keptAway) throw ownApp()
            // Reading the screen works with it dark or locked; anything that touches it does not. The
            // background screen is drawn whatever the phone's screen does: that one is left alone.
            if (!onBackground && action !in setOf("observe", "verify", "wait_for", "stop_repeat")) {
                screenGate(refuseLocked = action !in setOf("screenshot", "ocr"))
            }
            // With the phone locked, the background screen is read but not operated, unless the user
            // started this task on the phone in person: whoever has the phone in the drawer did not.
            if (onBackground && TouchGuard.refusedWhileLocked(action, keyguardLocked(), taskInPerson)) {
                throw AutomationFailure("phone_locked", "The phone is locked, and this task was not started by the " +
                    "user on the phone (a schedule, a notification rule, another device or another app started it), so " +
                    "nothing is tapped, typed or opened on the background screen until the phone is unlocked. Stop and " +
                    "tell the user; they can unlock the phone and run the task again")
            }
            if (onBackground && action in setOf("repeat", "home", "recents", "notifications")) {
                throw AutomationFailure("not_on_background", if (action == "home") "The background screen has no " +
                    "home screen: open the next app with launch_app" else "That belongs to the phone's own screen, which " +
                    "the user is using; the background screen cannot do it")
            }
            when (action) {
                "observe" -> {
                    panel?.step(say("查看屏幕", "Looking at the screen"))
                    // Asked to wait (a page still loading): read once the screen has been quiet a moment.
                    if (request.has("wait_ms")) waitUntilQuiet(request.getLong("wait_ms").coerceIn(0, 5000))
                    // An app busy drawing can answer slowly once; a second read usually goes through.
                    val observed = try { capture(request.optInt("max_nodes", 400), request.optInt("max_depth", 24)) }
                        catch (_: TimeoutException) { capture(request.optInt("max_nodes", 400), request.optInt("max_depth", 24)) }
                    return@synchronized result(observed)
                }
                "screenshot" -> {
                    panel?.step(say("截图看屏幕", "Taking a screenshot"))
                    return@synchronized screenshot(marks = request.optBoolean("marks", true))
                }
                "batch" -> return@synchronized batch(request)
                "repeat" -> return@synchronized startRepeat(request)
                "stop_repeat" -> {
                    val stopped = stopRepeat("stopped by the agent")
                    return@synchronized result(capture()).put("executed", stopped)
                        .put("repeat", repeatStatus()?.json() ?: JSONObject.NULL)
                }
                "verify" -> {
                    if (request.has("snapshot_version")) requireSnapshot(request.getString("snapshot_version"))
                    return@synchronized verify(request, false)
                }
                "ocr" -> {
                    panel?.step(say("读屏幕上的文字", "Reading the words on the screen"))
                    return@synchronized ocr()
                }
                "scroll_to_text" -> return@synchronized scrollToText(request)
                "wait_for" -> return@synchronized waitFor(request)
                "open_page" -> return@synchronized openPage(request)
            }
            ensureUnpaused()
            // By what it says, on the screen as it is now: becomes a ref action (or a tap on read words).
            val matched = if (action == "tap_text") resolveText(request) else null
            // Opening an app or a system key does not depend on what the screen showed: no snapshot needed.
            val source = if (!request.has("snapshot_version") && action in setOf("launch_app", "back", "home", "recents", "notifications"))
                capture() else requireSnapshot(request.getString("snapshot_version"))
            panel?.step(describeAction(request))
            actionStarted = true
            val executed = perform(request, source)
            actionExecuted = executed
            invalidate()
            if (executed) {
                recordAction(request, source)
                shootStep(describeAction(request), touchedPoint(request, source))
            }
            if (!executed && (harmless || onBackground)) {
                // Nobody touches the background screen, so a dropped gesture there is no sign of the
                // user taking over; with the phone's screen off, Android may drop such gestures.
                return@synchronized AndroidSystemBridge.failure("action_failed", if (onBackground)
                    "The background screen did not take the gesture (with the phone's screen off Android may drop " +
                        "them); act by the control's ref instead, or look again" else
                    "Android did not take the action; look at the screen and try another way", freshObservation())
            }
            if (!executed) {
                // Android dropped the gesture or click (the user touching the screen cancels one):
                // what happened is unclear, so a person looks before anything else is done.
                AndroidAutomationControl.set(this, true, false, automatic = true)
                return@synchronized AndroidSystemBridge.failure("action_failed",
                    "Android rejected the action; automation was paused for inspection", freshObservation())
            }
            when {
                action == "swipe" || action == "scroll" -> settleScrolling()
                action == "type_text" || !settle -> Thread.sleep(180)
                // A tap that opens a page: return what the page shows once it has loaded, so the
                // agent need not look again just to wait (that cost a model call each time).
                action == "launch_app" -> {
                    val opened = runCatching { launchIntent(request).let { it.component?.packageName ?: it.`package` } }.getOrNull()
                    if (opened != null && opened == observedPackage(source.observation)) waitUntilQuiet(1500, 350)
                    else waitForNewScreen(source.windows, observedPackage(source.observation))
                }
                else -> { Thread.sleep(180); waitUntilQuiet(1500, 350) }
            }
            val response = if (request.has("expect")) verify(request, true)
                else result(if (action == "launch_app") readableCapture() else capture(), executed = true)
                    .put("verification", JSONObject().put("status", "not_requested"))
            matched?.let { response.put("matched", it) }
            response
        } catch (error: AutomationFailure) {
            // Refusals come before anything reaches the screen (an app that is not installed, a control
            // that moved), so there is nothing to inspect and automation keeps running.
            AndroidSystemBridge.failure(error.code, error.message ?: "Android system action failed", freshObservation())
                .put("executed", actionExecuted)
                .also { failure -> error.confirmation?.let { failure.getJSONObject("error").put("confirmation_token", it) } }
        } catch (_: TimeoutException) {
            if (actionStarted && harmless) {
                invalidate()
                AndroidSystemBridge.failure("action_timeout",
                    "Android did not confirm the action; look at the screen before going on", freshObservation())
                    .put("executed", if (actionExecuted) true else JSONObject.NULL)
            } else if (actionStarted) {
                AndroidAutomationControl.set(this, true, true, automatic = true)
                invalidate()
                AndroidSystemBridge.failure("action_timeout",
                    "Android did not confirm completion; take over before retrying", freshObservation())
                    .put("executed", if (actionExecuted) true else JSONObject.NULL).put("action_state", "unknown")
            } else {
                AndroidSystemBridge.failure("observation_timeout", "Android screen observation timed out")
            }
        } catch (error: Exception) {
            android.util.Log.w("AgentAccessibility", "${request.optString("action")} failed", error)
            if (actionStarted && !harmless) AndroidAutomationControl.set(this, true, false, automatic = true)
            AndroidSystemBridge.failure("bridge_error",
                if (harmless) "Android could not do that here (the screen may have changed); look again and try another way"
                else "Android system operation failed", freshObservation())
                .put("executed", actionExecuted)
        }
    }

    /**
     * Several actions in one call (digits on a calculator, a form, type then send): each step is
     * checked against the screen as it is by then. A step names controls of the observation the batch
     * was planned on; such a control must still be the same one, in the same window, or the batch
     * stops there with what was done so far. One approval covers the whole batch.
     */
    private fun batch(request: JSONObject): JSONObject {
        ensureUnpaused()
        val planned = requireSnapshot(request.getString("snapshot_version"))
        val steps = request.getJSONArray("steps")
        val done = JSONArray()
        var current = planned
        var last: JSONObject? = null
        for (index in 0 until steps.length()) {
            val step = JSONObject(steps.getJSONObject(index).toString())
            fun stop(code: String, message: String): JSONObject =
                AndroidSystemBridge.failure(code, "Step ${index + 1}: $message", freshObservation())
                    .put("executed", index > 0).put("steps", done).put("completed", index)
            if (index > 0) {
                // The planned control, found again in the screen as it is now.
                if (step.has("ref")) {
                    val wanted = planned.targets[step.getString("ref")]
                        ?: return stop("unknown_ref", "the reference is not part of the planned observation")
                    step.put("ref", current.targets.entries.firstOrNull { (_, target) ->
                        target.windowId == wanted.windowId && target.path == wanted.path && wanted.sameControl(target)
                    }?.key ?: return stop("target_changed", "the screen changed after step $index; observe again"))
                } else if (step.optString("action") in setOf("tap", "long_press") && step.has("x")) {
                    val x = step.getInt("x")
                    val y = step.getInt("y")
                    val wanted = hit(planned.targets.values, x, y)
                    val now = hit(current.targets.values, x, y)
                    if (if (wanted == null) now != null else !wanted.sameControl(now)) {
                        return stop("target_changed", "something else is at these coordinates after step $index; observe again")
                    }
                }
            }
            val result = executeRequest(step.put("snapshot_version", current.version), settle = index == steps.length() - 1)
            done.put(JSONObject().put("action", step.optString("action")).put("executed", result.optBoolean("executed"))
                .apply { result.optJSONObject("error")?.let { put("error", it.optString("code")) } })
            if (!result.optBoolean("ok", true) || !result.optBoolean("executed")) {
                return result.put("steps", done).put("completed", index).put("executed", index > 0 || result.optBoolean("executed"))
            }
            last = result
            val next = result.optJSONObject("observation")?.optString("snapshot_version")
            current = next?.let { synchronized(recent) { recent[it] } } ?: return stop("stale_snapshot", "the screen could not be read")
        }
        if (request.has("expect")) {
            return verify(request, true).put("steps", done).put("completed", steps.length())
        }
        return (last ?: result(capture())).put("steps", done).put("completed", steps.length())
    }

    /** A run of steps repeated at fixed times by the phone itself ("swipe up every 8 seconds"). */
    internal data class RepeatStatus(
        val id: String, val description: String, val everyMs: Long, val times: Int?, val done: Int,
        val running: Boolean, val reason: String?,
    ) {
        fun json(): JSONObject = JSONObject().put("id", id).put("every_ms", everyMs)
            .put("times", times ?: JSONObject.NULL).put("done", done).put("running", running)
            .put("stopped_because", reason ?: JSONObject.NULL).apply {
                // Leaving the app or tapping stop is the user's decision, not a fault to work around:
                // an agent once reopened the app and started over.
                if (reason != null && (reason.startsWith("the user left") || reason == PhoneControlPanel.STOPPED_BY_USER)) {
                    put("user_choice", true)
                    put("note", "The user stopped this on purpose. Do not reopen the app or start it again unless they ask.")
                }
            }
    }

    @Volatile private var repeat: RepeatStatus? = null
    @Volatile private var repeatThread: Thread? = null
    @Volatile private var repeatEndedAt = 0L

    internal fun repeatStatus(): RepeatStatus? = repeat

    private fun publishRepeat(status: RepeatStatus) {
        if (!status.running && repeat?.running != false) repeatEndedAt = SystemClock.elapsedRealtime()
        repeat = status
        // A repeat started from a chat has no panel yet: one comes up as a small pill, so the user
        // can see it running and stop it.
        handler.post {
            if (AndroidSystemBridge.service !== this) return@post
            (panel ?: PhoneControlPanel(this).also { panel = it }).repeatChanged(status)
        }
    }

    /** Stops the running repeat, if any; true when one was running. */
    internal fun stopRepeat(reason: String): Boolean {
        val thread = repeatThread ?: return false
        repeatThread = null
        thread.interrupt()
        repeat?.let { if (it.running) publishRepeat(it.copy(running = false, reason = reason)) }
        return true
    }

    /**
     * Starts [request]'s steps every every_ms milliseconds, times times (or until stopped, at most
     * four hours), and returns at once: the phone keeps the time, so the agent's thinking does not
     * stretch it. Each round reads the screen first. It stops by itself when the user leaves the app
     * it started in, the screen goes off, automation is paused, or the panel's stop is tapped. Steps
     * use coordinates, scroll directions or back: a feed shows something else every round, so refs
     * would not stay valid.
     */
    private fun startRepeat(request: JSONObject): JSONObject {
        ensureUnpaused()
        val planned = requireSnapshot(request.getString("snapshot_version"))
        val steps = request.getJSONArray("steps")
        val everyMs = request.getLong("every_ms")
        val times = if (request.has("times")) request.getInt("times") else null
        // An unattended task's repeat goes on after the task: it keeps within the task's hosted limits.
        val allowance = RepeatAllowance.of(
            if (request.has("hosted_ms")) request.getLong("hosted_ms") else null,
            if (request.has("hosted_steps")) request.getInt("hosted_steps") else null,
            steps.length(), times,
        )
        if (allowance.ms <= 0 || allowance.rounds == 0) throw AutomationFailure("hosted_limit", "What is left of this " +
            "unattended task's hosted limits (time or steps) leaves no room for a repeat. Stop and tell the user; they can " +
            "raise the limits under Device & tools → Hosted limits, or start the repeat themselves")
        val app = observedPackage(planned.observation)
        stopRepeat("replaced by a new repeat")
        val description = describeAction(JSONObject().put("action", "batch").put("steps", steps)
            .put("snapshot_version", planned.version)).substringAfter("：").substringAfter(": ")
        val id = UUID.randomUUID().toString()
        val status = RepeatStatus(id, description, everyMs, times, 0, true, null)
        publishRepeat(status)
        val power = getSystemService(android.os.PowerManager::class.java)
        val thread = Thread({
            val started = SystemClock.elapsedRealtime()
            val limit = started + allowance.ms
            val rounds = allowance.rounds
            var done = 0
            var idle = 0
            var slot = 0L
            var reason: String? = null
            try {
                while (rounds == null || done < rounds) {
                    // Rounds keep to the clock: round n starts at start + n × interval.
                    val wait = started + slot * everyMs - SystemClock.elapsedRealtime()
                    if (wait > 0) Thread.sleep(wait)
                    if (SystemClock.elapsedRealtime() > limit) {
                        reason = if (allowance.byTime) "reached the task's hosted time limit" else "reached the four-hour limit"
                        break
                    }
                    if (!power.isInteractive) { reason = "the screen went off"; break }
                    reason = synchronized(executionLock) { repeatRound(steps, app) }
                    if (reason != null) break
                    // Only rounds that did something count; a screen that refuses every round ends it.
                    if (roundActed) { done += 1; idle = 0 } else if (++idle >= MAX_IDLE_ROUNDS) {
                        reason = "none of the steps could be done $MAX_IDLE_ROUNDS rounds in a row"; break
                    }
                    if (repeatThread === Thread.currentThread()) publishRepeat(status.copy(done = done))
                    // A round that ran past its slot skips the missed ones instead of bunching up.
                    slot = maxOf(slot + 1, (SystemClock.elapsedRealtime() - started) / everyMs + 1)
                }
            } catch (_: InterruptedException) {
                return@Thread
            } catch (error: Exception) {
                reason = error.message ?: "a step failed"
            }
            if (repeatThread === Thread.currentThread()) {
                repeatThread = null
                val ended = reason ?: if (allowance.bySteps) "reached the task's hosted step limit" else "finished"
                publishRepeat(status.copy(done = done, running = false, reason = ended))
            }
        }, "agent-repeat")
        repeatThread = thread
        thread.start()
        return result(planned, executed = true).put("repeat", status.json()
            .put("note", "Started. The phone runs it by itself: tell the user now and end your turn; do not watch it. " +
                "It stops when they leave the app, the screen goes off or they tap stop." +
                if (allowance.byTime || allowance.bySteps) " As this task runs unattended, it also stops at what is " +
                    "left of the task's hosted limits: about " +
                    (if (allowance.ms < 60_000) "${allowance.ms / 1000} seconds" else "${allowance.ms / 60_000} minutes") +
                    (allowance.rounds?.let { ", $it rounds" } ?: "") + "." else ""))
    }

    /** Whether the last round did at least one step (read only by the repeat thread). */
    private var roundActed = false

    /** One round of a repeat; the reason to stop, or null to carry on. */
    private fun repeatRound(steps: JSONArray, app: String?): String? {
        roundActed = false
        val control = AndroidAutomationControl.readState(this)
        if (control.optBoolean("paused") || control.optBoolean("takeover_requested")) return "automation was paused"
        blockedFront()?.let { return "the user keeps the agent away from $it" }
        for (index in 0 until steps.length()) {
            // Stopped while waiting for the lock: not one more tap.
            if (Thread.interrupted()) throw InterruptedException()
            val snapshot = capture()
            val now = observedPackage(snapshot.observation)
            if (app != null && now != null && now != app) return "the user left $app"
            // Which app is in front could not be read this time: no step into the unknown; the
            // round goes on (and rounds that do nothing end the repeat after a few).
            if (app != null && now == null) continue
            val step = JSONObject(steps.getJSONObject(index).toString()).put("snapshot_version", snapshot.version)
            panel?.step(describeAction(step))
            agentActedAt = SystemClock.uptimeMillis()
            val done = try { perform(step, snapshot) } catch (failure: AutomationFailure) {
                when (failure.code) {
                    // A refused tap (something else under the finger) skips this round's step, as a person would.
                    "target_changed", "not_scrollable", "control_disabled" -> false
                    // The window changed right then: another app means the user left, anything else waits a round.
                    "stale_snapshot" -> {
                        val after = observedPackage(capture().observation)
                        if (app != null && after != null && after != app) return "the user left $app"
                        false
                    }
                    else -> return failure.message ?: failure.code
                }
            }
            invalidate()
            if (done) roundActed = true
            if (step.optString("action") in setOf("swipe", "scroll")) settleScrolling() else Thread.sleep(180)
            if (!done && step.optString("action") == "back") return "Android did not go back"
        }
        return null
    }

    /** Waits until no accessibility events arrived for [quietMs] (a page done loading), at most [maxMs]. */
    private fun waitUntilQuiet(maxMs: Long, quietMs: Long = 600) {
        val deadline = SystemClock.uptimeMillis() + maxMs
        var seen = contentEpoch.get()
        var quietSince = SystemClock.uptimeMillis()
        while (SystemClock.uptimeMillis() < deadline) {
            Thread.sleep(100)
            val now = contentEpoch.get()
            if (now != seen) { seen = now; quietSince = SystemClock.uptimeMillis() }
            else if (SystemClock.uptimeMillis() - quietSince >= quietMs) return
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
            throw AutomationFailure("paused", AndroidAutomationControl.pausedMessage(control))
        }
    }

    /**
     * Before an action: a locked phone is refused (no app may unlock it), without lighting the
     * screen; a dark one that is not locked yet is woken, since a tap on it would do nothing.
     */
    private fun keyguardLocked(): Boolean =
        getSystemService(android.app.KeyguardManager::class.java)?.isKeyguardLocked == true

    private fun screenGate(refuseLocked: Boolean) {
        val locked = keyguardLocked()
        if (locked && refuseLocked) throw AutomationFailure("phone_locked", "The phone is locked and no app may " +
            "unlock it. Stop and ask the user to unlock the phone; go on once they have")
        val power = getSystemService(android.os.PowerManager::class.java) ?: return
        if (locked || power.isInteractive) return
        @Suppress("DEPRECATION")
        power.newWakeLock(android.os.PowerManager.SCREEN_BRIGHT_WAKE_LOCK or android.os.PowerManager.ACQUIRE_CAUSES_WAKEUP or
            android.os.PowerManager.ON_AFTER_RELEASE, "agentworkspace:phone-action").acquire(3000)
        val until = SystemClock.uptimeMillis() + 1500
        while (!power.isInteractive && SystemClock.uptimeMillis() < until) Thread.sleep(100)
        Thread.sleep(300)
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

    /**
     * The size and turn of the screen [on] (by default the one the agent works on). The background
     * screen keeps its own portrait size while the phone's screen turns: taking the phone's for it put
     * taps out of bounds and the screenshot's scale wrong.
     */
    @Suppress("DEPRECATION")
    private fun screen(on: Int = screenId): Screen {
        val manager = getSystemService(Context.DISPLAY_SERVICE) as DisplayManager
        val display = manager.getDisplay(on) ?: manager.getDisplay(Display.DEFAULT_DISPLAY)
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
    private fun capture(maxNodes: Int = 400, maxDepth: Int = 24, store: Boolean = true, on: Int = screenId): Snapshot = onReader(10_000) {
        val generation = epoch.get()
        val content = contentEpoch.get()
        val display = screen(on)
        val version = "$session:$generation:${sequence.incrementAndGet()}"
        val targets = linkedMapOf<String, Target>()
        val ownLabels = hashMapOf<String, String?>()
        val nodes = JSONArray()
        val windowsJson = JSONArray()
        var truncated = false
        var sensitive = false
        var activePackage: String? = null

        // [before]: in a list, the words of the item before this child (TouchGuard.wordsBefore).
        fun visit(node: AccessibilityNodeInfo, windowId: Int, path: List<Int>, parent: String?, depth: Int, parentSensitive: Boolean,
                  parentRotating: Boolean = false, inList: Boolean = false, before: String? = null) {
            if (targets.size >= maxNodes || depth > maxDepth) {
                truncated = true
                return
            }
            val protected = parentSensitive || secret(node)
            sensitive = sensitive || protected
            val ref = refMemory.getOrPut("$windowId/${path.joinToString(".")}") { "n${refNext++}" }
            val bounds = Rect().also { node.getBoundsInScreen(it) }
            val className = bounded(node.className, 160)
            val viewId = bounded(node.viewIdResourceName, 255)
            val label = if (protected) null else ownLabel(node)
            val rotating = parentRotating || Target.rotates(className)
            targets[ref] = Target(windowId, path, Rect(bounds), className, viewId, protected, label, node.isVisibleToUser,
                node.isClickable, node.isEditable, node.isScrollable, node.isLongClickable, rotating)
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
                .put("scrollable", node.isScrollable).put("long_clickable", node.isLongClickable)
                .put("checked", if (node.isCheckable) node.isChecked else JSONObject.NULL).put("selected", node.isSelected)
                .put("password", node.isPassword).put("sensitive", protected).put("child_count", node.childCount))
            val children = minOf(node.childCount, 400)
            if (depth >= maxDepth) {
                if (children > 0) truncated = true
                return
            }
            if (children != node.childCount) truncated = true
            val list = listOfRows(node)
            // The children of a list read so far: their words, and whether each is a control.
            val earlier = ArrayList<Pair<String?, Boolean>>()
            for (index in 0 until children) {
                if (targets.size >= maxNodes) { truncated = true; break }
                // Android 13+ fetches a node's descendants in one round trip instead of one per node.
                val child = (if (Build.VERSION.SDK_INT >= 33) node.getChild(index, AccessibilityNodeInfo.FLAG_PREFETCH_DESCENDANTS_HYBRID)
                    else node.getChild(index)) ?: continue
                try {
                    visit(child, windowId, path + index, ref, depth + 1, protected, rotating, list,
                        if (list) TouchGuard.wordsBefore(earlier) else null)
                    if (list) earlier += refMemory["$windowId/${(path + index).joinToString(".")}"]?.let { ownLabels[it] } to actionable(child)
                } finally { recycle(child) }
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
            // A list row: its first words (as rowWords reads them from a live node) go with every
            // control in it, so the same button in a recycled row showing another item is told apart.
            if (inList && !protected) {
                val inside = targets.entries.drop(firstInside).map { it.key to it.value }
                val insideWords = inside
                    .filter { (_, it) -> !it.sensitive && it.path.size - path.size <= INNER_DEPTH }
                    .mapNotNull { (key, _) -> ownLabels[key]?.takeIf { it.isNotBlank() } }
                // A list left flat (a web page's): a control with nothing inside goes by the item's words before it.
                val lead = if (insideWords.isEmpty() && actionable(node)) listOfNotNull(before) else emptyList()
                val words = (lead + listOfNotNull(label?.takeIf { it.isNotBlank() }) + insideWords)
                    .take(2).joinToString(" / ").take(160).ifEmpty { null }
                if (words != null) {
                    // A row of a list inside this row already named its own controls.
                    for ((key, target) in listOf(ref to targets.getValue(ref)) + inside) {
                        if (target.context == null && target.path.size - path.size <= ROW_DEPTH) {
                            targets[key] = target.copy(context = words)
                        }
                    }
                }
            }
        }

        // This app's own windows (the app, its bubble) are listed but not read: their approvals and
        // settings are the user's, and a finger landing on one is refused (ownWindowAt).
        val own = keptAway
        val isOwn = { name: String? -> own != null && name == own }
        val allWindows = screenWindows(on)
        val observedWindows = appWindows(allWindows)
        val windowsBefore = signature(observedWindows)
        if (windowsBefore != refWindows || refNext > 9000) {
            refMemory.clear()
            refNext = 1
            refWindows = windowsBefore
            refEpoch += 1
        }
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
                    try { if (!isOwn(packageName)) visit(root, window.id, emptyList(), null, 0, false) }
                    finally { recycle(root) }
                }
            }
            if (observedWindows.size > 8) truncated = true
            // The active window's root belongs to the phone's screen: no use on the background screen.
            if (targets.isEmpty() && on == Display.DEFAULT_DISPLAY && !isOwn(activePackage)) {
                rootInActiveWindow?.let { root ->
                    try {
                        activePackage = bounded(root.packageName, 255)
                        val bounds = Rect().also { root.getBoundsInScreen(it) }
                        windowsJson.put(JSONObject().put("id", root.windowId).put("type", AccessibilityWindowInfo.TYPE_APPLICATION)
                            .put("active", true).put("focused", true).put("bounds", boundsJson(bounds))
                            .put("package_name", activePackage ?: JSONObject.NULL).put("title", JSONObject.NULL))
                        if (!isOwn(activePackage)) visit(root, -1, emptyList(), null, 0, false)
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
            // The same ref_epoch: refs name the same controls as in the previous observation.
            .put("ref_epoch", refEpoch)
            .put("truncated", truncated).put("stable", generation == epoch.get() && windowsBefore == windowSignature(on))
            // Content moved while it was read: fine for acting, but prefer refs or a fresh look.
            .put("content_changing", content != contentEpoch.get())
            .put("sensitive_content_redacted", sensitive)
            .put("locked", on == Display.DEFAULT_DISPLAY &&
                getSystemService(android.app.KeyguardManager::class.java)?.isKeyguardLocked == true)
            .put("background_screen", on != Display.DEFAULT_DISPLAY)
            .put("own_app", isOwn(activePackage))
        Snapshot(version, generation, SystemClock.elapsedRealtime(), display,
            AndroidAutomationControl.readState(this).optString("revision"), targets, data, sensitive, windowsBefore)
            .also { if (store) synchronized(recent) { recent[version] = it } }
    }

    /** A password or other sensitive control, a shown password included (passwordInputType). */
    private fun secret(node: AccessibilityNodeInfo): Boolean = node.isPassword ||
        (Build.VERSION.SDK_INT >= 34 && node.isAccessibilityDataSensitive) || passwordInputType(node.inputType)

    /** What a control says by itself (an editable field: its hint). */
    private fun ownLabel(node: AccessibilityNodeInfo): String? =
        if (node.isEditable) bounded(node.hintText ?: node.contentDescription, 160)
        else bounded(node.text ?: node.contentDescription, 160)

    /** The first words inside [node], read the way capture() reads them for a control without its own. */
    private fun innerLabel(node: AccessibilityNodeInfo): String? = innerWords(node).take(2).joinToString(" / ").take(160).ifEmpty { null }

    private fun innerWords(node: AccessibilityNodeInfo): List<String> {
        val found = mutableListOf<String>()
        fun walk(current: AccessibilityNodeInfo, depth: Int) {
            for (index in 0 until minOf(current.childCount, 400)) {
                if (found.size >= 2) return
                val child = current.getChild(index) ?: continue
                try {
                    if (secret(child)) continue
                    ownLabel(child)?.takeIf { it.isNotBlank() }?.let { found += it }
                    if (depth < INNER_DEPTH) walk(child, depth + 1)
                } finally { recycle(child) }
            }
        }
        walk(node, 1)
        return found
    }

    /** Whether [node] lays out list rows: it scrolls and holds more than one child (not a page in a ScrollView). */
    private fun listOfRows(node: AccessibilityNodeInfo): Boolean = node.isScrollable && node.childCount > 1

    /** Whether a finger does something to [node]: a list item that is one is no text of an item. */
    private fun actionable(node: AccessibilityNodeInfo): Boolean =
        node.isClickable || node.isLongClickable || node.isEditable || node.isCheckable

    /**
     * The first words of the list row [node] is in, read the way capture() reads them (Target.context):
     * the row's own words, then the first ones inside it; a control with nothing inside, in a list left
     * flat, also goes by the item's words before it ([path]: [node]'s child indexes, to find them).
     * Null outside a list or deeper than ROW_DEPTH.
     */
    private fun rowWords(node: AccessibilityNodeInfo, path: List<Int>): String? {
        var current = node
        val climbed = mutableListOf<AccessibilityNodeInfo>()
        try {
            for (level in 0..ROW_DEPTH) {
                val parent = current.parent ?: return null
                climbed += parent
                if (listOfRows(parent)) {
                    if (secret(current)) return null
                    val inner = innerWords(current)
                    val index = path.getOrNull(path.size - 1 - level)
                    val lead = if (inner.isEmpty() && actionable(current) && index != null) listOfNotNull(wordsBefore(parent, index))
                        else emptyList()
                    return (lead + listOfNotNull(ownLabel(current)?.takeIf { it.isNotBlank() }) + inner)
                        .take(2).joinToString(" / ").take(160).ifEmpty { null }
                }
                current = parent
            }
            return null
        } finally { climbed.forEach { recycle(it) } }
    }

    /** The words of the item before child [index] of [list], as capture() finds them. */
    private fun wordsBefore(list: AccessibilityNodeInfo, index: Int): String? =
        TouchGuard.wordsBefore((maxOf(0, index - TouchGuard.ROW_LOOKBACK) until index).map { at ->
            val child = list.getChild(at) ?: return@map null to false
            try { (if (secret(child)) null else ownLabel(child)) to actionable(child) } finally { recycle(child) }
        })

    private fun freshObservation(): JSONObject? = runCatching { capture().observation }.getOrNull()

    private fun result(saved: Snapshot, executed: Boolean = false, verified: Boolean? = null): JSONObject =
        JSONObject().put("ok", true).put("executed", executed).put("verified", verified ?: JSONObject.NULL)
            .put("observation", saved.observation)
            .also { response -> recentRepeat()?.let { response.put("repeat", it.json()) } }

    /** The repeat while it runs and for two minutes after it ended, so the agent knows how it went. */
    private fun recentRepeat(): RepeatStatus? = repeat?.takeIf {
        it.running || SystemClock.elapsedRealtime() - repeatEndedAt < 120_000
    }

    /** A point on the status or navigation bar: a tap there reaches no app control. */
    private fun onSystemBar(saved: Snapshot, x: Int, y: Int): Boolean {
        val windows = saved.observation.optJSONArray("windows") ?: return false
        return (0 until windows.length()).map { windows.getJSONObject(it) }.any { window ->
            val bounds = window.optJSONObject("bounds") ?: return@any false
            window.optInt("type") == AccessibilityWindowInfo.TYPE_SYSTEM &&
                window.optString("package_name") == "com.android.systemui" &&
                bounds.optInt("bottom") - bounds.optInt("top") < saved.screen.height * 0.15 &&
                x in bounds.optInt("left") until bounds.optInt("right") && y in bounds.optInt("top") until bounds.optInt("bottom")
        }
    }

    private fun controls(snapshot: Snapshot): List<TouchGuard.Control> = snapshot.targets.values.map { target ->
        TouchGuard.Control(target.bounds.left, target.bounds.top, target.bounds.right, target.bounds.bottom, target.label,
            target.visible, target.clickable, target.longClickable, target.scrollable, target.windowId, target.path, target.className)
    }

    /** The controls a swipe presses, going by what [snapshot] shows. */
    private fun pressedBySwipe(request: JSONObject, snapshot: Snapshot): List<TouchGuard.Control> =
        TouchGuard.pressedBySwipe(controls(snapshot), request.optInt("x"), request.optInt("y"), request.optInt("x2"),
            request.optInt("y2"), snapshot.screen.width, snapshot.screen.height)

    /** The words on what this action presses, in the snapshot it cites and on the screen as it is now. */
    private fun pressedWords(request: JSONObject, saved: Snapshot, live: Snapshot): List<String?> {
        val read = request.optString("read_label").ifEmpty { null }
        if (request.has("ref")) return listOf(saved.targets[request.getString("ref")]?.label, read)
        val pressed = when (request.getString("action")) {
            "enter" -> emptyList()
            "swipe" -> pressedBySwipe(request, saved) + pressedBySwipe(request, live)
            else -> TouchGuard.pressed(controls(saved), request.optInt("x"), request.optInt("y")) +
                TouchGuard.pressed(controls(live), request.optInt("x"), request.optInt("y"))
        }
        return pressed.map { it.label } + read
    }

    /**
     * The screen as it is now, read whole: the snapshot an action cites may be seconds old, or cut short
     * by limits the request asked for. A slow read refuses the action: nothing has been done yet.
     */
    private fun liveScreen(): Snapshot = try { capture(store = false) } catch (_: TimeoutException) {
        throw AutomationFailure("observation_timeout", "The screen could not be read to check this action; look again")
    }

    /** The picture of a window was last found free of payment words: a run of taps there reads it once. */
    private var pictureCheckedWindows: String? = null
    private var pictureCheckedAt = 0L

    /**
     * A wordless control in a window that says next to nothing (a game, a canvas, an app without
     * accessibility): the controls cannot tell whether this is a payment step, so the picture has to.
     * A window whose picture cannot be had is refused.
     */
    private fun checkPicture(request: JSONObject, saved: Snapshot, live: Snapshot) {
        val target = if (request.has("ref")) saved.targets[request.getString("ref")] else null
        val x = target?.bounds?.centerX() ?: request.optInt("x")
        val y = target?.bounds?.centerY() ?: request.optInt("y")
        val controls = controls(live)
        if (!TouchGuard.saysAlmostNothing(controls, hit(live.targets.values, x, y)?.windowId) &&
            !TouchGuard.pictureUnder(controls, x, y, live.screen.width, live.screen.height)) return
        if (pictureCheckedWindows == live.windows && SystemClock.elapsedRealtime() - pictureCheckedAt < 2000) return
        val read = try {
            recognizeText(live).map { (text, box) -> TouchGuard.Line(text, box.left, box.top, box.right, box.bottom) }
        } catch (error: InterruptedException) {
            throw error
        } catch (_: Exception) {
            throw AutomationFailure("unreadable_screen", "This window shows almost no readable controls and Android does " +
                "not give the agent its picture, so the payment firewall cannot tell what this press does. Stop and tell " +
                "the user this step is theirs to do on the phone (on Android 10 and older, the live screen in Device & " +
                "tools lets the agent read such windows).")
        }
        TouchGuard.pictureReason(read, x, y)?.let { throw paymentBlocked(it) }
        pictureCheckedWindows = live.windows
        pictureCheckedAt = SystemClock.elapsedRealtime()
    }

    private fun paymentBlocked(why: String) = AutomationFailure("payment_blocked", "Payment firewall: $why. The agent never " +
        "pays, transfers or enters payment passwords, in any mode. Stop operating the phone now and tell the user in your " +
        "reply that this step is theirs to finish on the phone; do not look for another way to do it.")

    /**
     * What every touch goes through, by what the finger lands on rather than what the action is called.
     * A swipe with real movement presses nothing: in a list it is never refused for the words on the
     * screen, outside one (a slider) a payment step still stops it.
     */
    private fun checkTouch(request: JSONObject, saved: Snapshot, live: Snapshot) {
        val action = request.getString("action")
        val swipe = action == "swipe"
        val pressing = action in setOf("tap", "ref", "long_press") ||
            (swipe && (pressedBySwipe(request, saved).isNotEmpty() || pressedBySwipe(request, live).isNotEmpty()))
        if ((action == "tap" || (action == "long_press" && !request.has("ref")) || (swipe && pressing)) &&
            (onSystemBar(saved, request.optInt("x"), request.optInt("y")))) {
            throw AutomationFailure("system_bar", "That point is on the status or navigation bar, not the app. A control " +
                "hidden up there (a header that slid away) comes back by scrolling the page up; or use tap_text")
        }
        val words = pressedWords(request, saved, live)
        val screen = (saved.targets.values + live.targets.values).filter { it.visible }.map { it.label } +
            request.optString("read_label").ifEmpty { null }
        // The payment firewall: no mode, approval or confirmed=true lets the agent pay; the user does.
        if (!swipe || pressing || !TouchGuard.startsInList(controls(live), request.optInt("x"), request.optInt("y"))) {
            TouchGuard.paymentReason(screen, words)?.let { throw paymentBlocked(it) }
        }
        // A task-wide go-ahead does not cover these: the user says yes to each one in the conversation.
        if (pressing) {
            if (ElderGuard.on(this)) {
                val app = observedPackage(saved.observation)
                (ElderGuard.permissionRow(app, words) ?: ElderGuard.permissionPage(app, screen))?.let { row ->
                    throw AutomationFailure("blocked_app", Blocked("“${row.trim().take(30)}”", true).refusal(false))
                }
            }
            TouchGuard.consequential(words)?.let { label ->
                val target = if (request.has("ref")) saved.targets[request.getString("ref")]
                    else hit(saved.targets.values.filter { it.clickable || it.longClickable }, request.optInt("x"), request.optInt("y"))
                val control = ConfirmationBook.Control(observedPackage(saved.observation), label,
                    target?.className, target?.viewId)
                // The engine hands back the token of this refusal once the user has answered: that very
                // control, once. A swipe cannot carry one: it is pressed by tap or ref.
                if (swipe || !confirmations.redeem(request.optString("confirmed").ifEmpty { null }, control)) {
                    throw AutomationFailure("needs_confirmation", "“$label” deletes, clears, uninstalls, stops an app or pays. " +
                        "Do not press it yet: ask the user in your reply whether to, and end your turn. Only after they say yes " +
                        "in a new message, repeat the same action with confirmed=true (by tap or ref if this was a swipe); " +
                        "before that it does not count.", confirmations.issue(control))
                }
            }
            if (words.all { it.isNullOrBlank() }) checkPicture(request, saved, live)
        }
    }

    private fun perform(request: JSONObject, saved: Snapshot): Boolean {
        val action = request.getString("action")
        if (action == "swipe" && TouchGuard.barelyMoves(request.optInt("x"), request.optInt("y"), request.optInt("x2"),
                request.optInt("y2"), saved.screen.density)) {
            throw AutomationFailure("not_a_swipe", "That swipe barely moves, and Android takes it as a tap. Use tap or ref " +
                "for a control; a swipe has to travel")
        }
        val live = if (action in TOUCHING_ACTIONS) liveScreen().also { checkTouch(request, saved, it) } else null
        // A global action would go to the phone's own screen: the background screen gets the key.
        if (action == "back" && onBackground) {
            onReader { recheck(saved) }
            BackgroundScreen.key(android.view.KeyEvent.KEYCODE_BACK)?.let { throw AutomationFailure("action_failed", it) }
            return true
        }
        return when (action) {
            "tap" -> gesture(saved, live!!, request.getInt("x"), request.getInt("y"), duration = 70)
            "swipe" -> gesture(saved, live!!, request.getInt("x"), request.getInt("y"), request.getInt("x2"), request.getInt("y2"), 350)
            "long_press" -> if (request.has("ref")) actOnRef(request, saved)
                else gesture(saved, live!!, request.getInt("x"), request.getInt("y"), duration = LONG_PRESS_MS)
            "scroll" -> actOnRef(request.apply { if (!has("ref")) put("ref", defaultScrollable(saved, getString("direction"))) }, saved)
            "enter" -> if (request.has("ref")) actOnRef(request, saved) else onReader {
                recheck(saved)
                val focused = findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
                    ?: throw AutomationFailure("not_editable", "No text field has the keyboard focus; type into one first or pass its ref")
                try { imeEnter(focused) } finally { recycle(focused) }
            }
            "back", "home", "recents", "notifications" -> onReader {
                recheck(saved)
                performGlobalAction(when (request.getString("action")) {
                    "back" -> GLOBAL_ACTION_BACK
                    "home" -> GLOBAL_ACTION_HOME
                    "recents" -> GLOBAL_ACTION_RECENTS
                    else -> GLOBAL_ACTION_NOTIFICATIONS
                })
            }
            "launch_app" -> {
                val intent = launchIntent(request)
                if (keptAway != null && (intent.component?.packageName ?: intent.`package`) == keptAway) throw ownApp()
                if (onBackground) {
                    onReader { recheck(saved) }
                    BackgroundScreen.start(intent)?.let { throw AutomationFailure("launch_failed", it) }
                    return true
                }
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

    /**
     * The list to scroll when none is named: the main list of the app in front. That is the largest
     * scrollable going that way, or the list inside it when it fills most of it: an app's whole-screen
     * layout often reports itself scrollable (collapsing a header) while the feed is the list within.
     */
    private fun defaultScrollable(saved: Snapshot, direction: String): String {
        val front = saved.observation.optJSONArray("windows")?.let { windows ->
            (0 until windows.length()).map { windows.getJSONObject(it) }
                .firstOrNull { it.optInt("type") == AccessibilityWindowInfo.TYPE_APPLICATION && it.optBoolean("active") }
                ?.optInt("id")
        }
        val vertical = direction != "left" && direction != "right"
        fun sideways(target: Target) = target.className.orEmpty().let { name ->
            listOf("ViewPager", "HorizontalScrollView", "TabLayout", "Gallery").any { name.contains(it) }
        }
        fun area(target: Target) = target.bounds.width().toLong() * target.bounds.height()
        val candidates = saved.targets.entries.filter { (_, target) ->
            target.scrollable && target.visible && !target.sensitive && (front == null || target.windowId == front)
        }
        val going = candidates.filter { (_, target) -> sideways(target) != vertical }.ifEmpty { candidates }
        var chosen = going.maxByOrNull { area(it.value) }
            ?: throw AutomationFailure("not_scrollable", "Nothing on this screen scrolls; swipe instead, or pass the ref of the list")
        while (true) {
            val inner = going.filter { (key, target) ->
                key != chosen.key && target.path.size > chosen.value.path.size &&
                    target.path.subList(0, chosen.value.path.size) == chosen.value.path &&
                    area(target) * 10 >= area(chosen.value) * 6
            }.maxByOrNull { area(it.value) } ?: break
            chosen = inner
        }
        return chosen.key
    }

    private fun plain(text: String): String = text.filterNot { it.isWhitespace() }.lowercase()

    private fun frontWindow(saved: Snapshot): Int? = saved.observation.optJSONArray("windows")?.let { windows ->
        (0 until windows.length()).map { windows.getJSONObject(it) }
            .firstOrNull { it.optInt("type") == AccessibilityWindowInfo.TYPE_APPLICATION && it.optBoolean("active") }
            ?.optInt("id")
    }

    /**
     * The controls showing [wanted] (exactly, else containing it), one per thing a finger would tap:
     * a text inside a clickable row counts as that row. On screen and in the app in front first.
     */
    private fun textMatches(saved: Snapshot, wanted: String): List<Map.Entry<String, Target>> {
        val key = plain(wanted)
        if (key.isEmpty()) return emptyList()
        val labelled = saved.targets.entries.filter { (_, target) -> !target.sensitive && !target.label.isNullOrBlank() }
        val exact = labelled.filter { (_, target) -> plain(target.label!!) == key }
        val found = exact.ifEmpty { labelled.filter { (_, target) -> plain(target.label!!).contains(key) } }
        val front = frontWindow(saved)
        // The clickable control a text belongs to (itself, or the nearest clickable container).
        fun owner(entry: Map.Entry<String, Target>): Map.Entry<String, Target> = saved.targets.entries
            .filter { (_, target) -> target.windowId == entry.value.windowId && target.clickable &&
                target.path.size <= entry.value.path.size && entry.value.path.subList(0, target.path.size) == target.path }
            .maxByOrNull { it.value.path.size } ?: entry
        val owners = found.map(::owner).distinctBy { it.key }
        // A clickable text inside a clickable box is one thing to tap, not two: keep the box.
        fun inside(inner: Target, outer: Target) = inner.windowId == outer.windowId && inner.path.size > outer.path.size &&
            inner.path.subList(0, outer.path.size) == outer.path
        return owners.filter { candidate -> owners.none { other -> other !== candidate && inside(candidate.value, other.value) } }
            .sortedWith(compareBy({ !it.value.visible }, { front != null && it.value.windowId != front },
                { it.value.bounds.top }, { it.value.bounds.left }))
    }

    private fun candidates(matches: List<Map.Entry<String, Target>>): String = matches.take(6).joinToString("; ") { (ref, target) ->
        "$ref “${target.label?.take(40)}” [${target.bounds.left},${target.bounds.top},${target.bounds.right},${target.bounds.bottom}]"
    }

    /**
     * tap_text: the control showing the text, as a ref action on the screen as it is now (or, when no
     * control says it, the words read off the screenshot, as a tap there). [request] becomes that action.
     */
    private fun resolveText(request: JSONObject): JSONObject {
        val wanted = request.getString("text")
        val nth = request.optInt("nth", 0)
        val observed = capture()
        val matches = textMatches(observed, wanted)
        request.remove("text")
        request.remove("nth")
        request.put("snapshot_version", observed.version)
        if (matches.isNotEmpty()) {
            val chosen = when {
                nth > 0 -> matches.getOrNull(nth - 1) ?: throw AutomationFailure("not_found",
                    "Only ${matches.size} control(s) show “${wanted.take(60)}”: ${candidates(matches)}")
                matches.size == 1 -> matches[0]
                else -> throw AutomationFailure("ambiguous", "${matches.size} controls show “${wanted.take(60)}”: " +
                    "${candidates(matches)}. Pass nth (1 is the first listed) or act on one by ref")
            }
            request.put("action", "ref").put("ref", chosen.key)
            return JSONObject().put("ref", chosen.key).put("label", chosen.value.label ?: JSONObject.NULL).put("via", "screen")
        }
        // Words drawn in a picture (a badge, a game, a canvas) are not controls: read the screenshot.
        val read = runCatching { recognizeText(observed) }.getOrNull().orEmpty()
        // "确认付款" anywhere in the same picture makes this a payment step, whichever words are tapped.
        TouchGuard.pictureReason(read.map { (text, box) -> TouchGuard.Line(text, box.left, box.top, box.right, box.bottom) })
            ?.let { throw paymentBlocked(it) }
        val key = plain(wanted)
        val line = read.filter { plain(it.first) == key }.ifEmpty { read.filter { plain(it.first).contains(key) } }
            .minByOrNull { it.first.length }
            ?: throw AutomationFailure("not_found", "Nothing on this screen shows “${wanted.take(60)}”" +
                (if (read.isEmpty()) "" else " (also not in the words read off the screenshot)") +
                "; scroll_to_text finds it further down a list")
        // The words read there go with the tap: the control under them often has none of its own, and
        // the payment firewall and the delete check must still see "立即支付" or "删除".
        request.put("action", "tap").put("x", line.second.centerX()).put("y", line.second.centerY())
            .put("read_label", line.first)
        return JSONObject().put("label", line.first).put("via", "screenshot_text")
    }

    /** Words on the screen read from a screenshot (offline Chinese and Latin recognition), in screen coordinates. */
    private fun recognizeText(observed: Snapshot): List<Pair<String, Rect>> {
        if (observed.sensitive) throw AutomationFailure("protected_content",
            "Reading the screen's picture is blocked while password or sensitive controls are visible")
        val grabbed = panel?.let { shield -> shield.outOfTheWay { grab() } } ?: grab()
        try {
            return ScreenText.recognize(this, grabbed.bitmap, observed.screen.width.toFloat() / grabbed.bitmap.width,
                observed.screen.height.toFloat() / grabbed.bitmap.height)
        } finally { grabbed.bitmap.recycle() }
    }

    /** ocr: the words in the screen's picture, for what the controls do not say (badges, pictures, canvases). */
    private fun ocr(): JSONObject {
        val observed = capture()
        val read = recognizeText(observed)
        return result(observed).put("screen_text", JSONArray().apply {
            read.take(200).forEach { (text, box) -> put(JSONObject().put("text", text).put("bounds", boundsJson(box))) }
        })
    }

    /**
     * scroll_to_text: scrolls the list until a control showing the text is on screen (or the list ends),
     * and taps it when asked. One call instead of a scroll and a look for every screenful.
     */
    private fun scrollToText(request: JSONObject): JSONObject {
        ensureUnpaused()
        val wanted = request.getString("text")
        val direction = request.optString("direction", "down")
        val limit = request.optInt("max_scrolls", 15).coerceIn(1, 40)
        panel?.step(describeAction(request))
        var observed = capture()
        var scrolls = 0
        while (true) {
            val found = textMatches(observed, wanted).firstOrNull { it.value.visible }
            if (found != null) {
                record(JSONObject().put("kind", "find").put("text", wanted).put("tap", request.optBoolean("tap")))
                // Pictured after it settles, so a tap below shows where it led.
                shootStep(describeAction(request))
                if (request.optBoolean("tap")) {
                    val tap = JSONObject().put("action", "ref").put("ref", found.key).put("snapshot_version", observed.version)
                        .put("confirmed", request.optString("confirmed"))
                    panel?.step(describeAction(tap))
                    if (!perform(tap, observed)) throw AutomationFailure("action_failed", "Android rejected the tap")
                    invalidate()
                    Thread.sleep(180)
                    waitUntilQuiet(1500, 350)
                    return result(capture(), executed = true).put("found", JSONObject().put("label", found.value.label)
                        .put("tapped", true)).put("scrolls", scrolls)
                }
                return result(observed, executed = scrolls > 0).put("found", JSONObject().put("ref", found.key)
                    .put("label", found.value.label)).put("scrolls", scrolls)
            }
            if (scrolls >= limit) throw AutomationFailure("not_found",
                "“${wanted.take(60)}” did not appear after $scrolls scrolls")
            val before = observed.targets.values.filter { it.visible }.mapNotNull { it.label }.joinToString("|")
            val step = JSONObject().put("action", "scroll").put("direction", direction).put("snapshot_version", observed.version)
            if (request.has("ref")) step.put("ref", request.getString("ref"))
            if (!perform(step, observed)) throw AutomationFailure("action_failed", "Android rejected the scroll")
            invalidate()
            settleScrolling()
            scrolls += 1
            observed = capture()
            // The list ended: nothing new came into view.
            if (observed.targets.values.filter { it.visible }.mapNotNull { it.label }.joinToString("|") == before) {
                throw AutomationFailure("not_found", "Reached the end of the list after $scrolls scroll(s); " +
                    "“${wanted.take(60)}” is not in it (try the other direction or another list by ref)")
            }
        }
    }

    /** wait_for: watches the screen until a text appears (or disappears), at most timeout_ms. */
    private fun waitFor(request: JSONObject): JSONObject {
        val appears = request.optString("text").ifEmpty { null }
        val disappears = request.optString("gone_text").ifEmpty { null }
        val deadline = SystemClock.elapsedRealtime() + request.optLong("max_wait_ms", 15_000).coerceIn(500, 120_000)
        panel?.step(describeAction(request))
        while (true) {
            val observed = capture()
            val showing = { wanted: String -> observed.targets.values.any { target ->
                target.visible && !target.sensitive && target.label?.let { plain(it).contains(plain(wanted)) } == true } }
            val met = (appears == null || showing(appears)) && (disappears == null || !showing(disappears))
            if (met || SystemClock.elapsedRealtime() >= deadline) return result(observed).put("met", met)
            Thread.sleep(500)
        }
    }

    /**
     * open_page: a system page or another app's page by its own entry (Wi-Fi settings, an app's details,
     * a web address, a map search, the dialer with a number filled in) instead of tapping through menus.
     * Nothing is changed or called: only the page opens.
     */
    private fun openPage(request: JSONObject): JSONObject {
        ensureUnpaused()
        val page = request.getString("page")
        fun settings(action: String) = Intent(action)
        val packageName = request.optString("package_name").ifEmpty {
            request.optString("app_name").ifEmpty { null }?.let { name ->
                launcherApps().firstOrNull { it.first.equals(name.trim(), ignoreCase = true) }?.second?.packageName
                    ?: throw AutomationFailure("app_unavailable", "No installed app is called ${name.take(60)}")
            }
        }
        val intent = when (page) {
            "settings" -> settings(android.provider.Settings.ACTION_SETTINGS)
            "wifi" -> settings(android.provider.Settings.ACTION_WIFI_SETTINGS)
            "bluetooth" -> settings(android.provider.Settings.ACTION_BLUETOOTH_SETTINGS)
            "mobile_network" -> settings(android.provider.Settings.ACTION_WIRELESS_SETTINGS)
            "data_usage" -> settings(android.provider.Settings.ACTION_DATA_USAGE_SETTINGS)
            "airplane" -> settings(android.provider.Settings.ACTION_AIRPLANE_MODE_SETTINGS)
            "battery" -> settings(Intent.ACTION_POWER_USAGE_SUMMARY)
            "display" -> settings(android.provider.Settings.ACTION_DISPLAY_SETTINGS)
            "sound" -> settings(android.provider.Settings.ACTION_SOUND_SETTINGS)
            "location" -> settings(android.provider.Settings.ACTION_LOCATION_SOURCE_SETTINGS)
            "storage" -> settings(android.provider.Settings.ACTION_INTERNAL_STORAGE_SETTINGS)
            "date" -> settings(android.provider.Settings.ACTION_DATE_SETTINGS)
            "language" -> settings(android.provider.Settings.ACTION_LOCALE_SETTINGS)
            "accessibility" -> settings(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS)
            "security" -> settings(android.provider.Settings.ACTION_SECURITY_SETTINGS)
            "nfc" -> settings(android.provider.Settings.ACTION_NFC_SETTINGS)
            "vpn" -> settings(android.provider.Settings.ACTION_VPN_SETTINGS)
            "developer" -> settings(android.provider.Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS)
            "apps" -> settings(android.provider.Settings.ACTION_MANAGE_APPLICATIONS_SETTINGS)
            "notifications" -> if (packageName != null) Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                .putExtra(android.provider.Settings.EXTRA_APP_PACKAGE, packageName)
                else settings("android.settings.NOTIFICATION_SETTINGS")
            "app_details" -> Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                android.net.Uri.fromParts("package", packageName
                    ?: throw AutomationFailure("invalid_arguments", "app_details needs package_name or app_name"), null))
            "url" -> {
                val address = request.optString("url")
                if (!address.startsWith("https://") && !address.startsWith("http://")) {
                    throw AutomationFailure("invalid_arguments", "url must be an http(s) address")
                }
                Intent(Intent.ACTION_VIEW, android.net.Uri.parse(address))
            }
            "map" -> Intent(Intent.ACTION_VIEW, android.net.Uri.parse("geo:0,0?q=" + android.net.Uri.encode(request.optString("query"))))
            "web_search" -> Intent(Intent.ACTION_WEB_SEARCH).putExtra(android.app.SearchManager.QUERY, request.optString("query"))
            // The dialer with the number filled in: the user presses call.
            "dial" -> Intent(Intent.ACTION_DIAL, android.net.Uri.parse("tel:" + android.net.Uri.encode(request.optString("number"))))
            else -> throw AutomationFailure("invalid_arguments", "Unknown page")
        }.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val opens = intent.resolveActivity(packageManager) ?: throw AutomationFailure("page_unavailable",
            "This phone has no page for $page; open Settings and look for it there")
        // This app's pages, and the system's pages about it (stop it, its permissions, its notifications).
        if (keptAway != null && (opens.packageName == keptAway || packageName == keptAway)) throw ownApp()
        panel?.step(describeAction(request))
        val windowsBefore = windowSignature()
        val packageBefore = frontPackage()
        if (onBackground) {
            BackgroundScreen.start(intent)?.let { throw AutomationFailure("page_unavailable", it) }
        } else onReader { startActivity(intent) }
        invalidate()
        record(JSONObject().put("kind", "page").put("request", JSONObject(request.toString()).apply { remove("snapshot_version") }))
        shootStep(describeAction(request))
        waitForNewScreen(windowsBefore, packageBefore)
        return result(readableCapture(), executed = true)
    }

    /** The screen once an app window reports itself (right after a switch it may not yet). */
    private fun readableCapture(): Snapshot {
        var observed = capture()
        repeat(3) {
            if (!observed.observation.isNull("package_name")) return observed
            Thread.sleep(300)
            observed = capture()
        }
        return observed
    }

    /**
     * After opening an app or a page: until another screen shows (it takes a moment to start, and
     * the old screen stays quiet meanwhile), then until it has drawn. At most about 5 s.
     */
    private fun waitForNewScreen(windowsBefore: String, packageBefore: String? = null) {
        val deadline = SystemClock.uptimeMillis() + 3000
        while (SystemClock.uptimeMillis() < deadline) {
            val front = frontPackage()
            // Another app in front, readable (during the switch no window reports its app yet).
            if (windowSignature() != windowsBefore && front != null && (packageBefore == null || front != packageBefore)) break
            Thread.sleep(100)
        }
        waitUntilQuiet(2000, 400)
    }

    /** The package of the app window in front, or null while none can be read. */
    private fun frontPackage(): String? = onReader {
        val all = screenWindows()
        try {
            val apps = all.filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION }
            // On the background screen nothing is active or focused for the user: its top app counts.
            (apps.firstOrNull { it.isActive || it.isFocused } ?: if (onBackground) apps.maxByOrNull { it.layer } else null)
                ?.let { window -> window.root?.let { root -> root.packageName?.toString().also { recycle(root) } } }
                ?: if (onBackground) null else rootInActiveWindow?.let { root -> root.packageName?.toString().also { recycle(root) } }
        } finally { all.forEach { recycle(it) } }
    }

    /** The keyboard's action key (search, go, send, next) on a text field; Android 11 and later. */
    private fun imeEnter(node: AccessibilityNodeInfo): Boolean {
        if (Build.VERSION.SDK_INT < 30) throw AutomationFailure("unsupported_api",
            "Pressing the keyboard's enter key needs Android 11; tap the search or send button instead")
        if (!node.isEditable) throw AutomationFailure("not_editable", "The control is not a text field")
        // The key only works in the field that has the keyboard, as for a finger: focus it first and
        // wait until the focus has arrived (it does so a moment later).
        if (!node.isFocused) {
            node.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
            var waited = 0
            while (waited < 600 && node.refresh() && !node.isFocused) {
                if (waited == 200) node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                Thread.sleep(50)
                waited += 50
            }
        }
        return node.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.id)
    }

    /**
     * Scrolls [node] or the nearest scrollable container around it, by the list's own scroll action
     * (no guessing of swipe coordinates): "down" shows what is further down.
     */
    private fun scrollThrough(node: AccessibilityNodeInfo, direction: String): Boolean {
        val specific = if (Build.VERSION.SDK_INT >= 23) when (direction) {
            "up" -> AccessibilityNodeInfo.AccessibilityAction.ACTION_SCROLL_UP.id
            "down" -> AccessibilityNodeInfo.AccessibilityAction.ACTION_SCROLL_DOWN.id
            "left" -> AccessibilityNodeInfo.AccessibilityAction.ACTION_SCROLL_LEFT.id
            else -> AccessibilityNodeInfo.AccessibilityAction.ACTION_SCROLL_RIGHT.id
        } else null
        val generic = if (direction == "down" || direction == "right") AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
            else AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
        val vertical = direction == "up" || direction == "down"
        fun tryScroll(current: AccessibilityNodeInfo): Boolean {
            if (!current.isScrollable) return false
            // A pager's "forward" turns to the next tab: never the way to scroll a list up or down.
            val name = current.className?.toString().orEmpty()
            if (vertical && listOf("ViewPager", "HorizontalScrollView", "TabLayout").any { name.contains(it) }) return false
            val before = rowsMark(current)
            val acted = (specific != null && current.actionList.any { it.id == specific } && current.performAction(specific)) ||
                current.performAction(generic)
            if (!acted) return false
            // Some layouts accept the action and move nothing (a whole-screen layout with a header to
            // collapse, a list already at its end): only rows that moved count.
            Thread.sleep(300)
            return current.childCount == 0 || rowsMark(current) != before
        }
        if (tryScroll(node)) return true
        var current: AccessibilityNodeInfo? = node.parent
        var depth = 0
        while (current != null && depth < 8) {
            if (tryScroll(current)) { recycle(current); return true }
            val parent = current.parent
            recycle(current)
            current = parent
            depth += 1
        }
        current?.let { recycle(it) }
        return false
    }

    /**
     * What a list shows and where: the first visible rows that say something, a few levels down (a
     * ScrollView's one child stays clipped to the same box however far it scrolls). The same after a
     * scroll means it did not move.
     */
    private fun rowsMark(list: AccessibilityNodeInfo): String {
        list.refresh()
        val mark = StringBuilder()
        var found = 0
        fun visit(node: AccessibilityNodeInfo, depth: Int) {
            for (index in 0 until node.childCount) {
                if (found >= 6) return
                val child = node.getChild(index) ?: continue
                try {
                    if (!child.isVisibleToUser) continue
                    val label = (child.text ?: child.contentDescription)?.toString()?.take(40)
                    if (label != null || depth == 0) {
                        val box = Rect().also { child.getBoundsInScreen(it) }
                        mark.append(box.left).append(',').append(box.top).append(':').append(label ?: "").append(';')
                        if (label != null) found++
                    }
                    if (depth < 3) visit(child, depth + 1)
                } finally { recycle(child) }
            }
        }
        visit(list, 0)
        return mark.toString()
    }

    /** Scrolls the containers around [node] back toward their start; true when one moved. */
    private fun scrollContainersBack(node: AccessibilityNodeInfo): Boolean {
        var current: AccessibilityNodeInfo? = node.parent
        var depth = 0
        var moved = false
        while (current != null && depth < 12) {
            val name = current.className?.toString().orEmpty()
            if (current.isScrollable && !name.contains("ViewPager") && !name.contains("HorizontalScrollView")) {
                val before = rowsMark(current)
                val acted = current.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_SCROLL_UP.id) ||
                    current.performAction(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD)
                if (acted) {
                    Thread.sleep(250)
                    if (rowsMark(current) != before) moved = true
                }
            }
            val parent = current.parent
            recycle(current)
            current = parent
            depth += 1
        }
        current?.let { recycle(it) }
        return moved
    }

    /** Long-presses [node] or the nearest container that takes a long press. */
    private fun longClickThrough(node: AccessibilityNodeInfo): Boolean {
        if (node.isLongClickable && node.performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK)) return true
        var current: AccessibilityNodeInfo? = node.parent
        var depth = 0
        while (current != null && depth < 6) {
            if (current.isLongClickable && current.isEnabled && current.performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK)) {
                recycle(current)
                return true
            }
            val parent = current.parent
            recycle(current)
            current = parent
            depth += 1
        }
        current?.let { recycle(it) }
        return false
    }

    /** Whether a field shows [wanted], ignoring spaces and the separators fields add while formatting. */
    private fun shows(node: AccessibilityNodeInfo, wanted: String): Boolean? {
        val text = node.text?.toString() ?: return null
        fun plain(value: String) = value.filterNot { it.isWhitespace() || it in "-()" }
        return plain(text).contains(plain(wanted))
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
        val operation = request.getString("action")
        val typing = operation == "type_text"
        var node: AccessibilityNodeInfo? = null
        var tapAt: Rect? = null
        try {
            fun checkSame(current: AccessibilityNodeInfo) {
                val label = ownLabel(current) ?: if (current.isClickable) innerLabel(current) else null
                val now = Target(target.windowId, target.path, Rect().also { current.getBoundsInScreen(it) },
                    bounded(current.className, 160), bounded(current.viewIdResourceName, 255), false, label,
                    context = rowWords(current, target.path))
                if (!target.sameControl(now) || secret(current)) {
                    throw AutomationFailure("target_changed", "The referenced control changed; observe again")
                }
                // Said apart from a changed control: observing again shows the same greyed-out button.
                if (!current.isEnabled) throw AutomationFailure("control_disabled", "That control is disabled (greyed " +
                    "out) and takes no taps. Do what enables it first (fill in the form, pick a value), or use another " +
                    "control; a control marked offscreen may belong to another tab or page")
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
                var shown = onReader { node?.refresh(); node?.isVisibleToUser == true }
                // A header that slid away while a list scrolled (a search box in a collapsing toolbar)
                // comes back when its containers scroll back toward the top.
                val above = target.bounds.centerY() < saved.screen.height / 8
                var tries = 0
                while (!shown && above && tries < 6 && onReader(8000) { node?.let { scrollContainersBack(it) } == true }) {
                    Thread.sleep(350)
                    shown = onReader { node?.refresh(); node?.isVisibleToUser == true }
                    tries += 1
                }
            }
            // Scrolling to the very top or bottom takes several scrolls of the list.
            val done = onReader(if (operation == "scroll") 15_000 else 3000) {
                recheck(saved)
                val current = node ?: throw AutomationFailure("stale_snapshot", "The referenced control disappeared; observe again")
                checkSame(current)
                if (!current.isVisibleToUser) throw AutomationFailure("not_visible",
                    "The control is off screen and could not be scrolled into view; swipe to it, then observe again")
                when (operation) {
                    "type_text" -> {
                        if (!current.isEditable) throw AutomationFailure("not_editable", "The referenced control does not " +
                            "accept text. If it looks like a search box, tap it first: that often opens the real field")
                        return@onReader current.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, Bundle().apply {
                            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, request.getString("text"))
                        })
                    }
                    "enter" -> return@onReader imeEnter(current)
                    "scroll" -> when (val direction = request.getString("direction")) {
                        // All the way: the list's own scroll again and again until it stops moving.
                        "top", "bottom" -> {
                            var moved = 0
                            while (moved < 30 && scrollThrough(current, if (direction == "top") "up" else "down")) moved++
                            if (moved > 0) return@onReader true
                        }
                        else -> if (scrollThrough(current, direction)) return@onReader true
                    }
                    "long_press" -> if (longClickThrough(current)) return@onReader true
                    else -> if (clickThrough(current)) return@onReader true
                }
                // A finger dragged inside a button presses it: only what is a list is dragged.
                if (operation == "scroll" && !target.scrollable) throw AutomationFailure("not_scrollable",
                    "That control does not scroll and no list around it moved (it may be at its end). Pass the ref of " +
                        "the list, or swipe")
                // Neither it nor a container takes the action (custom drawn views): do it with a finger.
                tapAt = Rect().also { current.getBoundsInScreen(it) }
                false
            }
            if (typing) return typedOrPasted(node!!, request.getString("text"), done)
            val area = tapAt
            if (done || area == null) return done
            val (x, y) = area.centerX() to area.centerY()
            if (x !in 0 until saved.screen.width || y !in 0 until saved.screen.height) return false
            if (keptAway != null && TouchGuard.ownWindowAt(saved.observation.optJSONArray("windows"), x, y, packageName)) throw ownApp()
            val shield = panel
            // A list that offers no scroll action is dragged inside its own bounds, checked like any swipe.
            val drag = if (operation != "scroll") emptyList() else when (request.getString("direction")) {
                "down", "bottom" -> listOf(x, area.top + area.height() * 3 / 4, x, area.top + area.height() / 4)
                "up", "top" -> listOf(x, area.top + area.height() / 4, x, area.top + area.height() * 3 / 4)
                "right" -> listOf(area.left + area.width() * 3 / 4, y, area.left + area.width() / 4, y)
                else -> listOf(area.left + area.width() / 4, y, area.left + area.width() * 3 / 4, y)
            }
            if (drag.isNotEmpty()) checkTouch(JSONObject().put("action", "swipe").put("x", drag[0]).put("y", drag[1])
                .put("x2", drag[2]).put("y2", drag[3]), saved, liveScreen())
            fun finger(): Boolean = when (operation) {
                "scroll" -> dispatch(saved, drag[0], drag[1], drag[2], drag[3], 350)
                "long_press" -> dispatch(saved, x, y, x, y, LONG_PRESS_MS)
                else -> dispatch(saved, x, y, x, y, 70)
            }
            return if (shield != null) shield.outOfTheWay { finger() } else finger()
        } finally { node?.let { recycle(it) } }
    }

    /**
     * Checks that a field shows the typed text. Some apps' fields ignore setting the text directly;
     * the text is then pasted, as a person would (the clipboard keeps it afterwards).
     */
    private fun typedOrPasted(node: AccessibilityNodeInfo, text: String, set: Boolean): Boolean {
        if (set) {
            Thread.sleep(150)
            val shown = onReader { node.refresh(); shows(node, text) }
            // A field that does not report its text cannot be checked; setting it said it worked.
            if (shown != false) return true
        }
        // The user is using the phone meanwhile: their clipboard is not taken for the background screen.
        if (onBackground) throw AutomationFailure("text_not_accepted", "The field did not take the text; on the " +
            "background screen it is not pasted (that would replace the user's clipboard). Tap the field to focus it " +
            "and try again, or tell the user this field needs the phone's own screen")
        val pasted = onReader {
            getSystemService(android.content.ClipboardManager::class.java)
                .setPrimaryClip(android.content.ClipData.newPlainText("Agent Workspace", text))
            node.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
            val length = node.text?.length ?: 0
            node.performAction(AccessibilityNodeInfo.ACTION_SET_SELECTION, Bundle().apply {
                putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_START_INT, 0)
                putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_END_INT, length)
            })
            node.performAction(AccessibilityNodeInfo.ACTION_PASTE)
        }
        Thread.sleep(150)
        if (pasted && onReader { node.refresh(); shows(node, text) } != false) return true
        throw AutomationFailure("text_not_accepted",
            "The field did not take the text (neither set nor pasted); tap it to focus it, then try again")
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
            val current = screenWindows()
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

    private fun gesture(saved: Snapshot, current: Snapshot, x: Int, y: Int, x2: Int = x, y2: Int = y, duration: Long): Boolean {
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
        if (current.targets.values.any { it.sensitive && it.bounds.contains(x, y) }) {
            throw AutomationFailure("protected_node", "The target contains password or sensitive content")
        }
        if (keptAway != null && TouchGuard.ownWindowAt(current.observation.optJSONArray("windows"), x, y, packageName)) throw ownApp()
        val now = hit(current.targets.values, x, y)
        if (if (expected == null) now != null else !expected.sameControl(now)) {
            throw AutomationFailure("target_changed", "Something else is at these coordinates now; observe again")
        }
        // The phone control panel lets the finger through to the app while the gesture runs.
        val shield = panel?.takeIf { !onBackground }
        return if (shield != null) shield.outOfTheWay { dispatch(saved, x, y, x2, y2, duration) }
            else dispatch(saved, x, y, x2, y2, duration)
    }

    private fun dispatch(saved: Snapshot, x: Int, y: Int, x2: Int, y2: Int, duration: Long): Boolean {
        val completion = CountDownLatch(1)
        var completed = false
        val accepted = onReader {
            recheck(saved)
            val path = Path().apply { moveTo(x.toFloat(), y.toFloat()); lineTo(x2.toFloat(), y2.toFloat()) }
            val builder = GestureDescription.Builder().addStroke(GestureDescription.StrokeDescription(path, 0, duration))
            if (onBackground && Build.VERSION.SDK_INT >= 30) builder.setDisplayId(screenId)
            val gesture = builder.build()
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

    /**
     * Which windows are on screen, in which order and where: what an observation's coordinates rely
     * on. The app's own floating bubble is left out: it moves and comes back on its own (snapping to
     * the side, reappearing after the app closes), which made every snapshot stale. It stays in the
     * observation's windows, so a tap that would land on it is still refused (ownWindowAt).
     */
    private fun signature(list: List<AccessibilityWindowInfo>): String = list.filterNot { ownOverlay(it) }
        .joinToString(";") { window ->
        val bounds = Rect().also { window.getBoundsInScreen(it) }
        "${window.id}:${window.type}:${bounds.flattenToString()}"
    }

    // Window ids of this app's own floating windows (the bubble and its menu); asked once per window.
    private val ownOverlays = java.util.concurrent.ConcurrentHashMap<Int, Boolean>()

    private fun ownOverlay(window: AccessibilityWindowInfo): Boolean {
        if (window.type != AccessibilityWindowInfo.TYPE_SYSTEM) return false
        ownOverlays[window.id]?.let { return it }
        val root = window.root ?: return false
        val own = try { root.packageName?.toString() == packageName } finally { recycle(root) }
        if (ownOverlays.size > 256) ownOverlays.clear()
        ownOverlays[window.id] = own
        return own
    }

    private fun windowSignature(display: Int = screenId): String = onReader {
        val current = screenWindows(display)
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

    private fun screenshot(marks: Boolean = true): JSONObject {
        var observed = capture()
        repeat(3) {
            if (observed.sensitive) return AndroidSystemBridge.failure("protected_content",
                "Screenshot capture is blocked while password or sensitive controls are visible", observed.observation)
            val grabbed = try {
                val shield = panel?.takeIf { !onBackground }
                if (shield != null) shield.outOfTheWay { grab() } else grab()
            } catch (failure: AutomationFailure) {
                return AndroidSystemBridge.failure(failure.code, failure.message ?: "Android did not provide a screenshot",
                    freshObservation())
            }
            // Content may move while the picture is taken; only another window or a turned display
            // makes the picture belong to a different screen than the observation returned with it.
            if (observed.epoch == epoch.get() && observed.screen == screen() && observed.windows == windowSignature()) {
                return saveScreenshot(grabbed, observed, marks)
            }
            grabbed.bitmap.recycle()
            observed = capture()
        }
        return AndroidSystemBridge.failure("screen_unsettled",
            "Windows kept opening or closing during the capture; try again in a moment", observed.observation)
    }

    /**
     * The background screen's picture when the agent works there; else the live screen's newest
     * frame when it is on, otherwise Android's accessibility screenshot.
     */
    private fun grab(on: Int = screenId): Grab {
        if (on != Display.DEFAULT_DISPLAY) {
            val picture = BackgroundScreen.picture() ?: throw AutomationFailure("screenshot_unavailable",
                "The background screen has not drawn anything yet; look again in a moment")
            return Grab(picture.copy(Bitmap.Config.ARGB_8888, true).also { picture.recycle() }, "background")
        }
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

    /**
     * Numbers the controls a finger can use on the picture (Set-of-Mark): "12" is ref n12, so a
     * model that reads the picture acts on the control by its ref instead of estimating coordinates.
     * Small controls are numbered first; whole-screen containers and overlapping labels are skipped.
     */
    private fun drawMarks(image: Bitmap, observed: Snapshot): Int {
        val canvas = android.graphics.Canvas(image)
        val scaleX = image.width.toFloat() / observed.screen.width
        val scaleY = image.height.toFloat() / observed.screen.height
        val size = 12f * (image.width / 576f).coerceIn(1f, 2f)
        val text = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.WHITE; textSize = size; typeface = android.graphics.Typeface.DEFAULT_BOLD
        }
        val box = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply {
            style = android.graphics.Paint.Style.STROKE; strokeWidth = 1.6f
        }
        val fill = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG)
        val palette = intArrayOf(0xFFD32F2F.toInt(), 0xFF1976D2.toInt(), 0xFF388E3C.toInt(), 0xFF7B1FA2.toInt(),
            0xFFE65100.toInt(), 0xFF00838F.toInt())
        val labels = mutableListOf<android.graphics.RectF>()
        var count = 0
        observed.targets.entries.asSequence()
            .filter { (_, target) -> target.visible && target.actionable && !target.sensitive }
            .map { (ref, target) -> ref to android.graphics.RectF(target.bounds.left * scaleX, target.bounds.top * scaleY,
                target.bounds.right * scaleX, target.bounds.bottom * scaleY) }
            .filter { (_, area) -> area.width() >= 8 && area.height() >= 8 &&
                area.width() * area.height() < image.width * image.height * 0.45f }
            .sortedBy { (_, area) -> area.width() * area.height() }
            .take(80)
            .forEach { (ref, area) ->
                val number = ref.removePrefix("n")
                val color = palette[(number.toIntOrNull() ?: 0) % palette.size]
                val width = text.measureText(number) + 6f
                val height = size + 4f
                val label = listOf(
                    android.graphics.RectF(area.left, area.top, area.left + width, area.top + height),
                    android.graphics.RectF(area.right - width, area.bottom - height, area.right, area.bottom),
                ).firstOrNull { candidate -> labels.none { android.graphics.RectF.intersects(it, candidate) } } ?: return@forEach
                box.color = color
                canvas.drawRect(area, box)
                fill.color = color
                canvas.drawRect(label, fill)
                canvas.drawText(number, label.left + 3f, label.bottom - 3f - text.descent() / 2, text)
                labels += label
                count += 1
            }
        return count
    }

    private fun saveScreenshot(grabbed: Grab, observed: Snapshot, marks: Boolean = true): JSONObject {
        val captured = grabbed.bitmap
        try {
            // Every later model call carries the picture again: a 1280-pixel JPEG keeps text readable
            // at about a tenth of the bytes of a full-size PNG.
            val factor = minOf(1.0, 1280.0 / maxOf(captured.width, captured.height))
            val scaled = if (factor < 1.0) Bitmap.createScaledBitmap(captured,
                maxOf(1, (captured.width * factor).toInt()), maxOf(1, (captured.height * factor).toInt()), true) else captured
            // The marks are drawn on a copy that may be changed (a screenshot buffer may not be).
            val image = if (!marks || scaled.isMutable) scaled else scaled.copy(Bitmap.Config.ARGB_8888, true)
                .also { if (scaled !== captured) scaled.recycle() }
            val marked = if (marks) runCatching { drawMarks(image, observed) }.getOrDefault(0) else 0
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
                    .put("pixel_to_screen_y", observed.screen.height.toDouble() / image.height)
                    .put("marks", marked))
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

/** The app a snapshot shows, or null when it could not be read (a busy app, a window changing).
 * Android's optString gives the text "null" for a JSON null, which read as another app. */
internal fun observedPackage(observation: JSONObject): String? =
    if (observation.isNull("package_name")) null else observation.optString("package_name").ifEmpty { null }

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
