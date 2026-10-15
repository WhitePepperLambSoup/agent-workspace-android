package com.agentworkspace.mobile.automation

import android.content.Intent
import android.content.res.ColorStateList
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.text.InputType
import android.text.TextUtils
import android.util.TypedValue
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.agentworkspace.mobile.R
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.WebUiActivity
import com.agentworkspace.mobile.embedded.EngineHttp
import com.agentworkspace.mobile.embedded.MobileProviderSettings
import com.agentworkspace.mobile.embedded.ProviderModelCatalog
import com.agentworkspace.mobile.embedded.TaskNotificationPublisher
import com.agentworkspace.mobile.embedded.TermuxDaemonService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * "Operate the phone" from the floating bubble: a small window over the app in use where the user
 * types what the agent should do there; the agent then works through this accessibility service
 * while the window shows its steps, asks for approvals and shows the result.
 *
 * It is an accessibility overlay of [AgentAccessibilityService] (same process), so the service can
 * move it out of the way of its own work: [outOfTheWay] hides it and lets touches through for each
 * screenshot and gesture, and observations leave accessibility overlays out.
 * Main thread only, except [outOfTheWay] and [step].
 */
internal class PhoneControlPanel(private val service: AgentAccessibilityService) {
    companion object {
        /** Tells the floating bubble (main process) that the panel closed and it may show again. */
        const val ACTION_PANEL_CLOSED = "com.agentworkspace.mobile.action.PHONE_PANEL_CLOSED"
        /** Tells the bubble to step aside: it would be in the agent's screenshots and under its taps. */
        const val ACTION_PANEL_OPENED = "com.agentworkspace.mobile.action.PHONE_PANEL_OPENED"
        private const val ACCENT = 0xFF0F766E.toInt()
        private const val ACCENT_DARK = 0xFF5CC6B1.toInt()
        private const val DANGER = 0xFFB42318.toInt()
        private const val POLL_MS = 600L
        private const val MAX_STEPS = 6
        internal const val STOPPED_BY_USER = "stopped by the user"
    }

    private enum class Stage { COMPOSE, WORKING, APPROVAL, DONE }

    private val windowManager = service.getSystemService(WindowManager::class.java)
    private val main = Handler(Looper.getMainLooper())
    private var scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var root: FrameLayout? = null
    private var card: LinearLayout? = null
    private var params: WindowManager.LayoutParams? = null
    private var stage = Stage.COMPOSE
    private var targetPackage: String? = null
    private var targetLabel: String? = null
    private var sessionId: String? = null
    private var taskId: String? = null
    private var sequence = 0L
    private var poller: Job? = null
    private var status = ""
    private var stepCount = 0
    private val steps = ArrayDeque<String>()
    private var stepsOpen = false
    private var approval: JSONObject? = null
    private var resolving = false
    private var answer = StringBuilder()
    private var result: String? = null
    private var failed = false
    private var stopping = false
    private var draft = ""
    private var lastRequest: String? = null
    private var hiddenDepth = 0
    @Volatile private var shown = false
    // Shrunk to a pill in a corner so the screen stays in view (a video, a feed); an approval brings
    // the panel back, a tap on the pill too.
    private var collapsed = false
    // Opened only to show a repeat started from a chat; it goes away once the repeat ends.
    private var openedForRepeat = false
    private var repeatState: AgentAccessibilityService.RepeatStatus? = null
    private var chooserOpen = false
    // The provider in use, from the engine: what the model and effort choices offer.
    private var provider: JSONObject? = null
    private val preferences = service.getSharedPreferences("phone-control", android.content.Context.MODE_PRIVATE)
    /** "Always allow": phone tasks from this panel run without asking (the user can turn it off here). */
    private var alwaysAllow: Boolean
        get() = preferences.getBoolean("always_allow", false)
        set(value) { preferences.edit().putBoolean("always_allow", value).apply() }
    /** Send the words on the screen (and the app's name) with each request, so the agent starts knowing what is shown. */
    private var sendScreen: Boolean
        get() = preferences.getBoolean("send_screen", false)
        set(value) { preferences.edit().putBoolean("send_screen", value).apply() }
    /** Shrink to the pill as soon as a task starts. */
    private var autoCollapse: Boolean
        get() = preferences.getBoolean("auto_collapse", false)
        set(value) { preferences.edit().putBoolean("auto_collapse", value).apply() }
    /** The model and reasoning effort this panel's tasks use; empty: the app's own setting. */
    private var panelModel: String
        get() = preferences.getString("model", "").orEmpty()
        set(value) { preferences.edit().putString("model", value).apply() }
    private var panelEffort: String
        get() = preferences.getString("effort", "").orEmpty()
        set(value) { preferences.edit().putString("effort", value).apply() }
    private var shrinkAfterApproval = false
    private var bubbleHidden = false
    // Paused: the task finishes its current step and waits; the user may add to the request meanwhile.
    private var paused = false
    private var pausing = false
    private var addition = ""
    // The task's conversation and steps, shown in the panel without opening the app.
    private var contextOpen = false
    private val contextItems = ArrayList<Pair<String, String>>()
    private var listening: com.agentworkspace.mobile.voice.OfflineVoiceSession? = null
    // This task's steps in words (remembered for the app when it succeeds) and as actions (a shortcut).
    private val taskSteps = ArrayList<String>()
    private var recorded: List<JSONObject> = emptyList()
    private var savedShortcut = false
    private var replaying: PhoneMemory.Shortcut? = null
    private var confirmDelete: String? = null
    private var modelsFetching = false
    /** The provider last asked for its models, so a failing one is not asked on every redraw. */
    private var modelsTried = ""

    val isOpen: Boolean get() = root != null
    /** Waiting for the user's request, with no task running. */
    val composing: Boolean get() = stage == Stage.COMPOSE && taskId == null

    private fun text(zh: String, en: String) = UiText.of(service, zh, en)
    private fun dp(value: Int): Int =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), service.resources.displayMetrics).toInt()
    private fun dark() = (service.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
    private fun accent() = if (dark()) ACCENT_DARK else ACCENT
    private fun primaryText() = if (dark()) Color.WHITE else 0xFF18201E.toInt()
    private fun secondaryText() = if (dark()) 0xFFA2AFAB.toInt() else 0xFF56625F.toInt()
    private fun surface() = if (dark()) 0xFF1F2725.toInt() else Color.WHITE
    private fun field() = if (dark()) 0xFF2A3431.toInt() else 0xFFF1F5F4.toInt()

    // ---- Opening and closing -----------------------------------------------------------------

    /** Opens on the app in front ([packageName], [label]); an open panel just comes back to the input. */
    fun open(packageName: String?, label: String?) {
        if (root == null) {
            targetPackage = packageName
            targetLabel = label
            if (!addWindow()) { announceClosed(); return }
            bubbleAside(true)
        } else if (stage == Stage.DONE) {
            targetPackage = packageName ?: targetPackage
            targetLabel = label ?: targetLabel
        }
        collapsed = false
        openedForRepeat = false
        loadProvider()
        if (stage == Stage.DONE || (stage == Stage.COMPOSE && taskId == null)) setStage(Stage.COMPOSE)
        else render()
    }

    /** The provider in use, as the engine runs it (settings saved in the app process may be newer here). */
    private fun loadProvider() {
        scope.launch {
            val reply = withContext(Dispatchers.IO) {
                runCatching { EngineHttp.request(service, "GET", "/mobile/settings", null, 3000) }.getOrNull()
            }
            provider = reply?.takeIf { it.ok }?.body ?: withContext(Dispatchers.IO) {
                runCatching { JSONObject(MobileProviderSettings.load(service).toPublicJson()) }.getOrNull()
            }
            if (stage == Stage.COMPOSE) render()
        }
    }

    fun close() {
        // A repeat keeps going after its task: the panel shrinks to its pill instead, so it can be stopped.
        if (repeatState?.running == true && root != null) {
            if (stage == Stage.COMPOSE || stage == Stage.APPROVAL) stage = Stage.DONE
            hideKeyboard()
            collapsed = true
            render()
            return
        }
        val view = root ?: return
        poller?.cancel()
        poller = null
        hideKeyboard()
        root = null
        card = null
        shown = false
        hiddenDepth = 0
        runCatching { windowManager.removeView(view) }
        scope.cancel()
        scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
        sessionId = null; taskId = null; sequence = 0; result = null; failed = false; stopping = false
        approval = null; steps.clear(); stepCount = 0; draft = ""; answer = StringBuilder()
        stage = Stage.COMPOSE
        collapsed = false; openedForRepeat = false; chooserOpen = false; shrinkAfterApproval = false
        paused = false; addition = ""; contextOpen = false; contextItems.clear()
        listening?.cancel(); listening = null
        announceClosed()
    }

    /** A repeat started or moved on (from the service, main thread): shown in the panel, or as a pill. */
    fun repeatChanged(status: AgentAccessibilityService.RepeatStatus) {
        repeatState = status
        if (root == null) {
            if (!status.running) return
            targetPackage = null; targetLabel = null
            if (!addWindow()) return
            openedForRepeat = true
            collapsed = true
            stage = Stage.DONE
            result = null
        }
        render()
        // Opened only for it: the pill shows how it ended for a moment, then goes.
        if (!status.running && openedForRepeat && taskId == null) {
            main.postDelayed({ if (openedForRepeat && repeatState?.running != true) close() }, 5000)
        }
    }

    private fun announceClosed() {
        bubbleHidden = false
        service.sendBroadcast(Intent(ACTION_PANEL_CLOSED).setPackage(service.packageName))
    }

    /** Hides the floating bubble while the panel stands in for it, or brings it back. */
    private fun bubbleAside(hide: Boolean) {
        if (hide == bubbleHidden) return
        bubbleHidden = hide
        service.sendBroadcast(Intent(if (hide) ACTION_PANEL_OPENED else ACTION_PANEL_CLOSED).setPackage(service.packageName))
    }

    private fun addWindow(): Boolean {
        val frame = object : FrameLayout(service) {
            // While typing the panel has the focus, so Back comes here: it closes the panel, as it
            // would close a dialog, instead of being lost.
            override fun dispatchKeyEvent(event: android.view.KeyEvent): Boolean {
                if (event.keyCode == android.view.KeyEvent.KEYCODE_BACK && stage == Stage.COMPOSE) {
                    if (event.action == android.view.KeyEvent.ACTION_UP) close()
                    return true
                }
                return super.dispatchKeyEvent(event)
            }

            // Android 16 (predictive back) no longer sends the Back key to windows: the same, as a callback.
            private val backCallback: Any? = if (android.os.Build.VERSION.SDK_INT >= 33)
                android.window.OnBackInvokedCallback { if (stage == Stage.COMPOSE) close() } else null

            override fun onAttachedToWindow() {
                super.onAttachedToWindow()
                if (android.os.Build.VERSION.SDK_INT >= 33) findOnBackInvokedDispatcher()?.registerOnBackInvokedCallback(
                    android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, backCallback as android.window.OnBackInvokedCallback)
            }

            override fun onDetachedFromWindow() {
                if (android.os.Build.VERSION.SDK_INT >= 33) findOnBackInvokedDispatcher()
                    ?.unregisterOnBackInvokedCallback(backCallback as android.window.OnBackInvokedCallback)
                super.onDetachedFromWindow()
            }
        }.apply { setPadding(dp(8), dp(4), dp(8), dp(10)); clipToPadding = false }
        val box = LinearLayout(service).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply {
                cornerRadius = dp(22).toFloat(); setColor(surface())
                setStroke(dp(1), if (dark()) 0x26FFFFFF else 0x14000000)
            }
            elevation = dp(10).toFloat()
            setPadding(dp(14), dp(2), dp(14), dp(12))
        }
        frame.addView(box, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        val statusBar = service.resources.getIdentifier("status_bar_height", "dimen", "android")
            .takeIf { it != 0 }?.let { service.resources.getDimensionPixelSize(it) } ?: dp(24)
        val layout = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
            y = statusBar + dp(2)
            softInputMode = WindowManager.LayoutParams.SOFT_INPUT_ADJUST_NOTHING
        }
        runCatching { windowManager.addView(frame, layout) }.onFailure { failure ->
            android.util.Log.w("PhoneControlPanel", "Could not show the panel", failure)
            return false
        }
        root = frame
        card = box
        params = layout
        shown = true
        frame.alpha = 0f
        frame.translationY = -dp(24).toFloat()
        frame.animate().alpha(1f).translationY(0f).setDuration(260).start()
        return true
    }

    // ---- Getting out of the agent's way --------------------------------------------------------

    /**
     * Runs [block] (a screenshot or a gesture, on an engine worker thread) with the panel hidden and
     * letting touches through, so the agent neither sees it nor taps it.
     */
    fun <T> outOfTheWay(block: () -> T): T {
        if (!shown || Looper.myLooper() == Looper.getMainLooper()) return block()
        val hidden = CountDownLatch(1)
        main.post { hide(); hidden.countDown() }
        hidden.await(500, TimeUnit.MILLISECONDS)
        // A couple of frames for the screen to show what lies under the panel.
        SystemClock.sleep(90)
        try { return block() } finally { main.post { unhide() } }
    }

    private fun hide() {
        val view = root ?: return
        if (hiddenDepth++ > 0) return
        view.animate().cancel()
        view.alpha = 0f
        params?.let {
            it.flags = it.flags or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
            runCatching { windowManager.updateViewLayout(view, it) }
        }
    }

    private fun unhide() {
        val view = root ?: return
        if (hiddenDepth == 0 || --hiddenDepth > 0) return
        params?.let {
            it.flags = it.flags and WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE.inv()
            runCatching { windowManager.updateViewLayout(view, it) }
        }
        view.animate().alpha(1f).setDuration(120).start()
    }

    /** What the agent is doing right now, from the accessibility service (any thread). */
    fun step(description: String) {
        if (!shown) return
        main.post {
            if (root == null || (taskId == null && replaying == null)) return@post
            stepCount += 1
            status = description
            steps.addLast(description)
            while (steps.size > MAX_STEPS) steps.removeFirst()
            if (taskSteps.size < 30) taskSteps.add(description)
            if (stage == Stage.WORKING) render()
        }
    }

    // ---- Stages ------------------------------------------------------------------------------

    private fun setStage(next: Stage) {
        stage = next
        val view = root ?: return
        params?.let {
            // Only the input takes the keyboard; while the agent works the app keeps its focus
            // (paused, the agent does nothing: the user may type what to add).
            val typing = next == Stage.COMPOSE || (next == Stage.WORKING && paused)
            it.flags = if (typing) it.flags and WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE.inv()
                else it.flags or WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
            it.softInputMode = if (next == Stage.COMPOSE) WindowManager.LayoutParams.SOFT_INPUT_STATE_VISIBLE or
                WindowManager.LayoutParams.SOFT_INPUT_ADJUST_NOTHING else WindowManager.LayoutParams.SOFT_INPUT_ADJUST_NOTHING
            runCatching { windowManager.updateViewLayout(view, it) }
        }
        if (next != Stage.COMPOSE) hideKeyboard()
        render()
        card?.let { box -> box.alpha = 0.55f; box.animate().alpha(1f).setDuration(160).start() }
    }

    private fun render() {
        val box = card ?: return
        box.removeAllViews()
        // Whenever the agent has a task, the user can shrink the panel to the pill and open it again.
        val pill = collapsed && stage != Stage.COMPOSE
        // A finished task's pill leaves the bubble free for the next request; while the agent works,
        // the bubble stays out of its way.
        bubbleAside(!(pill && stage == Stage.DONE && taskId == null))
        shape(pill)
        if (pill) { renderPill(box); return }
        box.addView(grip(), LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(16)))
        when (stage) {
            Stage.COMPOSE -> renderCompose(box)
            Stage.WORKING -> renderWorking(box)
            Stage.APPROVAL -> renderApproval(box)
            Stage.DONE -> renderDone(box)
        }
        if (stage == Stage.WORKING || stage == Stage.DONE) renderRepeat(box)
    }

    /** The whole panel across the top, or the pill in the top corner. */
    private fun shape(pill: Boolean) {
        val layout = params ?: return
        val view = root ?: return
        val width = if (pill) WindowManager.LayoutParams.WRAP_CONTENT else WindowManager.LayoutParams.MATCH_PARENT
        val gravity = Gravity.TOP or (if (pill) Gravity.END else Gravity.CENTER_HORIZONTAL)
        card?.let { box ->
            if (pill) box.setPadding(dp(10), dp(4), dp(6), dp(4)) else box.setPadding(dp(14), dp(2), dp(14), dp(12))
            (box.layoutParams as? FrameLayout.LayoutParams)?.let { it.width = width; box.layoutParams = it }
        }
        if (layout.width == width && layout.gravity == gravity) return
        layout.width = width
        layout.gravity = gravity
        layout.x = 0
        runCatching { windowManager.updateViewLayout(view, layout) }
    }

    /** Collapsed: what is going on in a few words; tap to open the panel again. */
    private fun renderPill(box: LinearLayout) {
        val repeat = repeatState
        val running = taskId != null || repeat?.running == true
        val line = row().apply {
            setOnClickListener { collapsed = false; render() }
            contentDescription = text("展开操控小窗", "Open the phone control panel")
        }
        if (running) line.addView(pulse(), LinearLayout.LayoutParams(dp(18), dp(18)))
        val waiting = stage == Stage.APPROVAL
        val words = when {
            // Shrunk while a decision waits: the pill says so, and the task waits until it is opened.
            waiting -> text("待你确认 · 点开", "Needs you · tap")
            stage == Stage.WORKING && paused -> text("已暂停 · 点开", "Paused · tap")
            stage == Stage.WORKING -> if (stepCount > 0) text("第 $stepCount 步", "Step $stepCount") else text("思考中", "Thinking")
            repeat?.running == true -> "⟳ ${repeat.done}" + (repeat.times?.let { "/$it" } ?: "")
            repeat != null && openedForRepeat -> text("定时重复已结束", "Repeat ended")
            failed -> text("没有完成", "Not finished")
            else -> text("完成了", "Done")
        }
        line.addView(label(words, 13f, when {
            waiting -> accent()
            failed && !running -> DANGER
            else -> primaryText()
        }, bold = true, single = true), gap(if (running) 8 else 2))
        if (repeat?.running == true) {
            line.addView(iconButton(R.drawable.ic_panel_stop, DANGER, text("停止定时重复", "Stop the repeat")) {
                service.stopRepeat(STOPPED_BY_USER)
            }, gap(2))
        }
        box.addView(line)
    }

    /** A repeat the phone runs on its own: what it does, how far it got, and a way to stop it. */
    private fun renderRepeat(box: LinearLayout) {
        val repeat = repeatState ?: return
        val count = "${repeat.done}" + (repeat.times?.let { "/$it" } ?: "")
        val line = row()
        line.addView(label(if (repeat.running) text("定时重复：${repeat.description} · 已执行 $count 次", "Repeating: ${repeat.description} · $count done")
            else text("定时重复已结束（$count 次）：${repeatReason(repeat.reason)}", "Repeat ended ($count): ${repeatReason(repeat.reason)}"),
            12.5f, if (repeat.running) accent() else secondaryText()),
            LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        if (repeat.running) line.addView(button(text("停止", "Stop"), DANGER, filled = false) { service.stopRepeat(STOPPED_BY_USER) }, gap(8))
        box.addView(line, spaced(10))
    }

    private fun repeatReason(reason: String?): String = when {
        reason == null || reason == "finished" -> text("全部完成", "all done")
        reason == STOPPED_BY_USER -> text("你停止了它", "you stopped it")
        reason == "stopped by the agent" -> text("AI 停止了它", "the agent stopped it")
        reason == "the screen went off" -> text("屏幕熄灭了", "the screen went off")
        reason == "automation was paused" -> text("自动化已暂停", "automation was paused")
        reason.startsWith("the user left") -> text("离开了原来的应用", "you left the app")
        reason == "reached the four-hour limit" -> text("已到 4 小时上限", "it reached the four-hour limit")
        reason == "replaced by a new repeat" -> text("换成了新的定时重复", "a new repeat replaced it")
        reason.startsWith("none of the steps could be done") ->
            text("连续几轮都点不到目标", "its steps could not be done several rounds in a row")
        else -> reason
    }

    private fun renderCompose(box: LinearLayout) {
        val header = row()
        header.addView(icon(R.drawable.ic_bubble_control, accent(), 20))
        val titles = LinearLayout(service).apply { orientation = LinearLayout.VERTICAL }
        titles.addView(label(text("让 AI 操作手机", "Let the agent use your phone"), 15f, primaryText(), bold = true))
        targetLabel?.let { titles.addView(label(text("在「$it」里", "In $it"), 12.5f, secondaryText())) }
        header.addView(titles, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply { marginStart = dp(10) })
        header.addView(iconButton(R.drawable.ic_bubble_close, secondaryText(), text("关闭", "Close")) { close() })
        box.addView(header)

        val input = EditText(service).apply {
            setText(draft)
            setSelection(draft.length)
            hint = text("想让 AI 在这里帮你做什么？", "What should the agent do here?")
            setHintTextColor(secondaryText())
            setTextColor(primaryText())
            textSize = 15.5f
            minLines = 1
            maxLines = 4
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            imeOptions = EditorInfo.IME_ACTION_SEND
            background = GradientDrawable().apply { cornerRadius = dp(16).toFloat(); setColor(field()) }
            setPadding(dp(12), dp(10), dp(12), dp(10))
            addTextChangedListener(object : android.text.TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
                override fun afterTextChanged(s: android.text.Editable?) { draft = s?.toString().orEmpty() }
            })
        }
        val send = FrameLayout(service).apply {
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(accent()) }
            contentDescription = text("发送", "Send")
            addView(ImageView(service).apply { setImageResource(R.drawable.ic_panel_send); imageTintList = ColorStateList.valueOf(if (dark()) 0xFF0B1F1C.toInt() else Color.WHITE) },
                FrameLayout.LayoutParams(dp(20), dp(20), Gravity.CENTER))
            setOnClickListener { it.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY); submit(input.text.toString()) }
        }
        input.setOnEditorActionListener { _, action, _ ->
            if (action == EditorInfo.IME_ACTION_SEND) { submit(input.text.toString()); true } else false
        }
        val inputRow = row().apply { gravity = Gravity.BOTTOM }
        inputRow.addView(input, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        // Speak the request instead of typing it (offline, once the speech model is installed).
        micButton { spoken -> draft = spoken; input.setText(spoken); input.setSelection(spoken.length) }
            ?.let { inputRow.addView(it, LinearLayout.LayoutParams(dp(40), dp(42)).apply { marginStart = dp(4) }) }
        inputRow.addView(send, LinearLayout.LayoutParams(dp(42), dp(42)).apply { marginStart = dp(8); bottomMargin = dp(1) })
        box.addView(inputRow, spaced(10))
        renderShortcuts(box)
        // The model and reasoning effort for tasks from here; the app's own setting until one is picked.
        box.addView(modelRow(), spaced(8))
        if (chooserOpen) box.addView(chooser(), spaced(6))
        // Shrink while it works, so a video or a feed stays in view; approvals still come up.
        val shrink = row()
        shrink.addView(label(text("运行时收起成小圆点（不挡屏幕）", "Shrink while it works (keeps the screen clear)"), 12.5f,
            secondaryText()), LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        shrink.addView(android.widget.Switch(service).apply {
            isChecked = autoCollapse
            contentDescription = text("运行时收起", "Shrink while it works")
            setOnCheckedChangeListener { _, checked -> autoCollapse = checked }
        })
        box.addView(shrink, spaced(4))
        // Auto context: off unless the user turns it on; when on, it says what is sent.
        val context = row()
        context.addView(label(if (sendScreen) text("提问时附带「${targetLabel ?: text("当前应用", "this app")}」的名字和屏幕上的文字",
                "Questions carry the app's name and the words on the screen") else text("提问时附带屏幕上的文字", "Send the words on the screen with questions"),
            12.5f, if (sendScreen) accent() else secondaryText(), bold = sendScreen), LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        context.addView(android.widget.Switch(service).apply {
            isChecked = sendScreen
            contentDescription = text("附带屏幕文字", "Send screen text")
            setOnCheckedChangeListener { _, checked -> sendScreen = checked; render() }
        })
        box.addView(context, spaced(4))
        // Hosted mode: the agent operates without asking; shown here so it is easy to turn off.
        val hosted = row()
        hosted.addView(label(if (alwaysAllow) text("托管中：点按、滑动和输入不再询问", "Hosted: taps, swipes and typing are not asked")
            else text("托管（不再逐步确认）", "Hosted (no step-by-step approval)"), 12.5f,
            if (alwaysAllow) accent() else secondaryText(), bold = alwaysAllow),
            LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        hosted.addView(android.widget.Switch(service).apply {
            isChecked = alwaysAllow
            thumbTintList = ColorStateList.valueOf(if (alwaysAllow) accent() else Color.WHITE)
            trackTintList = ColorStateList.valueOf(if (alwaysAllow) (accent() and 0x00FFFFFF or 0x66000000) else 0x40808080)
            contentDescription = text("托管模式", "Hosted mode")
            setOnCheckedChangeListener { _, checked -> alwaysAllow = checked; render() }
        })
        box.addView(hosted, spaced(8))
        box.addView(label(if (alwaysAllow) text("密码框始终不会碰；删除文件仍会询问。也可以随时点停止。",
                "Password fields are never touched; deleting files still asks. You can stop at any time.")
            else text("AI 会看屏幕，再点按、输入和滑动；需要你确认的操作会在这里询问。",
                "The agent looks at the screen, then taps, types and swipes; anything that needs your approval is asked here."),
            12f, secondaryText()), spaced(4))
        input.requestFocus()
        main.postDelayed({ if (stage == Stage.COMPOSE) showKeyboard(input) }, 180)
    }

    private fun effortLabel(value: String): String = when (value) {
        "auto" -> text("自动", "Auto")
        "none" -> text("关闭", "Off")
        "low" -> text("低", "Low")
        "medium" -> text("中", "Medium")
        "high" -> text("高", "High")
        "xhigh" -> text("很高", "Very high")
        "max" -> text("最高", "Max")
        else -> value
    }

    /** The panel's own model choice applies only while the provider it was made for is in use. */
    private fun chosenModel(): String {
        val base = provider?.optString("base_url") ?: return panelModel
        return panelModel.takeIf { preferences.getString("model_base", "") == base }.orEmpty()
    }

    /** The panel's effort, while the model in use offers it. */
    private fun chosenEffort(): String {
        if (panelEffort.isEmpty() || (chosenModel().isEmpty() && panelModel.isNotEmpty())) return ""
        val info = provider ?: return panelEffort
        val model = chosenModel().ifEmpty { info.optString("model") }
        return panelEffort.takeIf {
            it in MobileProviderSettings.reasoningEfforts(info.optString("protocol"), info.optString("base_url"), model)
        }.orEmpty()
    }

    /** The provider's model list, read once a day when the chooser opens (the app's settings read it too). */
    private fun refreshModels(protocol: String, base: String) {
        val listing = runCatching { ProviderModelCatalog.cached(service, protocol, base) }.getOrNull()
        if (modelsFetching || modelsTried == "$protocol $base" ||
            (listing != null && System.currentTimeMillis() - listing.fetchedAt < 24 * 3600_000L)) return
        if (base == MobileProviderSettings.EMBEDDED_QWEN_BASE_URL) return
        modelsFetching = true
        modelsTried = "$protocol $base"
        scope.launch {
            withContext(Dispatchers.IO) { runCatching { ProviderModelCatalog.fetch(service, protocol, base, null) } }
            modelsFetching = false
            if (stage == Stage.COMPOSE && chooserOpen) render()
        }
    }

    private fun modelRow(): View {
        val appModel = provider?.optString("model").orEmpty()
        val model = chosenModel().ifEmpty { appModel }.ifEmpty { text("读取中…", "Loading…") }
        val effort = chosenEffort().ifEmpty { provider?.optString("reasoning_effort").orEmpty().ifEmpty { "auto" } }
        val line = row().apply {
            background = GradientDrawable().apply { cornerRadius = dp(12).toFloat(); setColor(field()) }
            setPadding(dp(12), dp(8), dp(10), dp(8))
            setOnClickListener { chooserOpen = !chooserOpen; render() }
            contentDescription = text("选择模型和思考程度", "Choose the model and reasoning effort")
        }
        line.addView(label(model, 13f, primaryText(), bold = true, single = true),
            LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        line.addView(label(text("思考：", "Thinking: ") + effortLabel(effort) + if (chooserOpen) "  ▴" else "  ▾", 12.5f, secondaryText(), single = true), gap(8))
        return line
    }

    /** The provider's models (its own list when it was read, otherwise the known names) and efforts. */
    private fun chooser(): View {
        val column = LinearLayout(service).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply { cornerRadius = dp(12).toFloat(); setColor(field()) }
            setPadding(dp(4), dp(4), dp(4), dp(8))
        }
        val info = provider ?: return column.apply { addView(label(text("正在读取模型…", "Reading the models…"), 12.5f, secondaryText())) }
        val protocol = info.optString("protocol")
        val base = info.optString("base_url")
        val appModel = info.optString("model")
        refreshModels(protocol, base)
        // Without the provider's own list, only a known provider's names: a custom address has none.
        val listed = runCatching { ProviderModelCatalog.cached(service, protocol, base)?.models?.map { it.id } }.getOrNull()
            ?: MobileProviderSettings.providerPresets.firstOrNull {
                it.protocol == protocol && it.baseUrl?.trimEnd('/').equals(base.trimEnd('/'), ignoreCase = true)
            }?.models.orEmpty()
        val models = listOf("") + (listOf(appModel) + listed).filter { it.isNotBlank() }.distinct().take(200)
        if (modelsFetching) column.addView(label(text("正在获取模型列表…", "Getting the model list…"), 12f,
            secondaryText()).apply { setPadding(dp(10), dp(6), 0, dp(2)) })
        val list = LinearLayout(service).apply { orientation = LinearLayout.VERTICAL }
        val chosen = chosenModel()
        models.forEach { id ->
            val selected = id == chosen
            list.addView(label(if (id.isEmpty()) text("跟随应用设置（$appModel）", "App setting ($appModel)") else id, 13.5f,
                if (selected) accent() else primaryText(), bold = selected, single = true).apply {
                setPadding(dp(10), dp(8), dp(10), dp(8))
                setOnClickListener {
                    panelModel = id
                    preferences.edit().putString("model_base", base).apply()
                    val efforts = MobileProviderSettings.reasoningEfforts(protocol, base, id.ifEmpty { appModel })
                    if (panelEffort !in efforts) panelEffort = ""
                    render()
                }
            })
        }
        val scroll = ScrollView(service).apply { addView(list) }
        column.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        scroll.post { if (scroll.height > dp(176)) scroll.layoutParams = scroll.layoutParams.apply { height = dp(176) } }
        val efforts = MobileProviderSettings.reasoningEfforts(protocol, base, chosen.ifEmpty { appModel })
        val chips = row()
        (listOf("") + efforts).distinct().forEach { value ->
            val selected = value == chosenEffort()
            chips.addView(label(if (value.isEmpty()) text("应用设置", "App setting") else effortLabel(value), 12.5f,
                if (selected) accent() else primaryText(), bold = selected, single = true).apply {
                setPadding(dp(10), dp(6), dp(10), dp(6))
                background = GradientDrawable().apply {
                    cornerRadius = dp(14).toFloat(); setStroke(dp(1), if (selected) accent() else (if (dark()) 0x33FFFFFF else 0x22000000))
                }
                setOnClickListener {
                    panelEffort = value
                    if (chosenModel().isEmpty() && panelModel.isNotEmpty()) panelModel = ""
                    render()
                }
            }, gap(6))
        }
        column.addView(label(text("思考程度", "Reasoning effort"), 12f, secondaryText()).apply { setPadding(dp(10), dp(8), 0, dp(4)) })
        column.addView(android.widget.HorizontalScrollView(service).apply {
            isHorizontalScrollBarEnabled = false
            addView(chips)
        })
        if (efforts.size <= 1) column.addView(label(text("这个模型自己决定思考程度", "This model decides its own effort"), 11.5f,
            secondaryText()).apply { setPadding(dp(10), dp(4), 0, 0) })
        return column
    }

    private fun renderWorking(box: LinearLayout) {
        val line = row()
        if (paused) line.addView(icon(R.drawable.ic_panel_pause, accent(), 22), LinearLayout.LayoutParams(dp(22), dp(22)))
        else line.addView(pulse(), LinearLayout.LayoutParams(dp(22), dp(22)))
        val texts = LinearLayout(service).apply {
            orientation = LinearLayout.VERTICAL
            setOnClickListener { contextOpen = !contextOpen; render() }
        }
        texts.addView(label(when {
            stopping -> text("正在停止…", "Stopping…")
            paused -> text("已暂停", "Paused")
            else -> status.ifBlank { text("正在准备…", "Getting ready…") }
        }, 14.5f, primaryText(), bold = true, single = true))
        texts.addView(label(when {
            paused -> text("做完这一步就停住；可以补充要求，再点继续", "Holds after this step; add to the request, then go on")
            stepCount > 0 -> text("第 $stepCount 步 · 点这里看过程", "Step $stepCount · tap for details")
            else -> text("AI 正在思考 · 点这里看过程", "The agent is thinking · tap for details")
        }, 12f, secondaryText(), single = true))
        line.addView(texts, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply { marginStart = dp(12) })
        // Out of the way while it works (a video, a feed): a small pill keeps the progress.
        line.addView(iconButton(R.drawable.ic_panel_collapse, secondaryText(), text("收起", "Shrink")) { collapsed = true; render() })
        if (replaying != null) {
            // A shortcut runs without the agent: it can only be stopped.
            line.addView(iconButton(R.drawable.ic_panel_stop, DANGER, text("停止", "Stop")) { stop() })
            box.addView(line)
            return
        }
        // Stuck or misread the screen: have it look again and carry on.
        if (!paused) line.addView(iconButton(R.drawable.ic_panel_refresh, accent(), text("让 AI 重新看屏幕", "Have the agent look again")) { refresh() })
        // Pause, not stop: the task keeps its place and goes on when the user says so.
        line.addView(iconButton(if (paused) R.drawable.ic_panel_play else R.drawable.ic_panel_pause, accent(),
            if (paused) text("继续", "Go on") else text("暂停", "Pause")) { setPaused(!paused) })
        line.addView(iconButton(R.drawable.ic_panel_stop, DANGER, text("停止", "Stop")) { stop() })
        box.addView(line)
        if (paused) renderAddition(box)
        if (contextOpen) renderContext(box)
    }

    /** While paused: what the user adds to the request (typed or spoken), and the way on. */
    private fun renderAddition(box: LinearLayout) {
        val input = EditText(service).apply {
            setText(addition)
            setSelection(addition.length)
            hint = text("补充要求，比如「改成第二个」", "Add to the request, such as “the second one instead”")
            setHintTextColor(secondaryText())
            setTextColor(primaryText())
            textSize = 14.5f
            maxLines = 3
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            background = GradientDrawable().apply { cornerRadius = dp(14).toFloat(); setColor(field()) }
            setPadding(dp(12), dp(8), dp(12), dp(8))
            addTextChangedListener(object : android.text.TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
                override fun afterTextChanged(s: android.text.Editable?) { addition = s?.toString().orEmpty() }
            })
        }
        val inputRow = row().apply { gravity = Gravity.CENTER_VERTICAL }
        inputRow.addView(input, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        micButton { spoken -> addition = spoken; input.setText(spoken); input.setSelection(spoken.length) }
            ?.let { inputRow.addView(it, gap(4)) }
        box.addView(inputRow, spaced(10))
        val buttons = row().apply { gravity = Gravity.END }
        buttons.addView(button(text("补充", "Add"), accent(), filled = false) { addToRequest(input.text.toString(), goOn = false) })
        buttons.addView(button(text("补充并继续", "Add and go on"), accent(), filled = true) {
            val words = input.text.toString()
            if (words.isBlank()) setPaused(false) else addToRequest(words, goOn = true)
        }, gap(8))
        box.addView(buttons, spaced(8))
    }

    /** The task so far: the request, the agent's words, each tool it used and how it went. */
    private fun renderContext(box: LinearLayout) {
        val list = LinearLayout(service).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(10), dp(6), dp(10), dp(8)) }
        if (contextItems.isEmpty()) list.addView(label(text("还没有内容", "Nothing yet"), 12.5f, secondaryText()))
        contextItems.forEach { (kind, words) ->
            val (prefix, color) = when (kind) {
                "user" -> text("你：", "You: ") to accent()
                "ai" -> "AI：" to primaryText()
                "tool" -> "› " to secondaryText()
                "error" -> "✗ " to DANGER
                "approval" -> text("待确认：", "Approval: ") to accent()
                else -> "  " to secondaryText()
            }
            list.addView(label(prefix + words, if (kind == "ai" || kind == "user") 13f else 12f, color).apply {
                setPadding(0, dp(3), 0, dp(3))
                setTextIsSelectable(false)
            })
        }
        val scroll = ScrollView(service).apply {
            isVerticalScrollBarEnabled = true
            background = GradientDrawable().apply { cornerRadius = dp(12).toFloat(); setColor(field()) }
            addView(list)
        }
        box.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(8) })
        val limit = (service.resources.displayMetrics.heightPixels * 0.42f).toInt()
        scroll.post {
            if (scroll.height > limit) scroll.layoutParams = scroll.layoutParams.apply { height = limit }
            scroll.fullScroll(View.FOCUS_DOWN)
        }
    }

    private fun setPaused(value: Boolean) {
        val id = taskId?.takeIf { it != "pending" } ?: return
        if (pausing) return
        pausing = true
        scope.launch {
            val reply = withContext(Dispatchers.IO) {
                runCatching { EngineHttp.request(service, "POST", "/mobile/tasks/${Uri.encode(id)}/${if (value) "pause" else "unpause"}",
                    JSONObject(), 15000) }.getOrNull()
            }
            pausing = false
            if (reply?.ok == true) {
                paused = reply.body.optBoolean("paused", value)
                contextItems.add("note" to if (paused) text("已暂停", "Paused") else text("继续", "Going on"))
            } else status = if (value) text("暂停没有送达，可以直接停止", "The pause did not arrive; you can stop instead")
                else text("继续没有送达，请再点一次", "Going on did not arrive; tap again")
            // The window takes the keyboard while paused and gives it back when the task goes on.
            if (stage == Stage.WORKING) setStage(Stage.WORKING) else render()
        }
    }

    /** Adds the user's words to the running task (read before its next step), then maybe goes on. */
    private fun addToRequest(words: String, goOn: Boolean) {
        val id = taskId?.takeIf { it != "pending" } ?: return
        val request = words.trim()
        if (request.isEmpty()) return
        scope.launch {
            val reply = withContext(Dispatchers.IO) {
                runCatching { EngineHttp.request(service, "POST", "/mobile/tasks/${Uri.encode(id)}/steer",
                    JSONObject().put("prompt", request).put("input_id", "addition-${UUID.randomUUID()}"), 15000) }.getOrNull()
            }
            if (reply?.ok == true) {
                addition = ""
                contextItems.add("user" to request)
                if (goOn) setPaused(false) else render()
            } else {
                status = text("补充没有送达，请再试一次", "That did not arrive; try again")
                render()
            }
        }
    }

    /** A microphone for offline speech, when its model is installed and the app may use the microphone. */
    private fun micButton(onText: (String) -> Unit): View? {
        val ready = com.agentworkspace.mobile.voice.OfflineSpeech.status(service).optBoolean("available") &&
            service.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) == android.content.pm.PackageManager.PERMISSION_GRANTED
        if (!ready) return null
        val active = listening != null
        return iconButton(R.drawable.ic_bubble_mic, if (active) DANGER else accent(),
            if (active) text("说完了", "Done speaking") else text("说话输入", "Speak")) {
            listening?.let { it.finish(); return@iconButton }
            val session = com.agentworkspace.mobile.voice.OfflineVoiceSession(service, object : com.agentworkspace.mobile.voice.OfflineVoiceSession.Listener {
                override fun onLevel(level: Float) {}
                override fun onText(text: String) { onText(text) }
                override fun onRecognizing() {}
                override fun onFinished(text: String, heardSpeech: Boolean) {
                    listening = null
                    if (text.isNotBlank()) onText(text)
                    render()
                }
                override fun onError(message: String) {
                    listening = null
                    status = message
                    render()
                }
            })
            listening = session
            session.start()
            render()
        }
    }

    private fun renderApproval(box: LinearLayout) {
        val request = approval ?: run { setStage(Stage.WORKING); return }
        val header = row()
        header.addView(label(text("需要你确认", "Needs your approval"), 15f, primaryText(), bold = true),
            LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        // Look at the screen first, then decide: the pill keeps the question waiting.
        header.addView(iconButton(R.drawable.ic_panel_collapse, secondaryText(), text("收起", "Shrink")) {
            shrinkAfterApproval = false
            collapsed = true
            render()
        })
        box.addView(header)
        box.addView(label(describeApproval(request), 14f, primaryText()), spaced(6))
        val buttons = row().apply { gravity = Gravity.END }
        buttons.addView(button(text("拒绝", "Deny"), DANGER, filled = false) { resolve(false, "once") })
        buttons.addView(button(text("允许", "Allow"), accent(), filled = true) { resolve(true, "once") }, gap(8))
        box.addView(buttons, spaced(12))
        val wider = row().apply { gravity = Gravity.END }
        wider.addView(button(text("本次都允许", "Allow for this task"), accent(), filled = false) { resolve(true, "task") })
        wider.addView(button(text("一直允许（托管）", "Always allow"), accent(), filled = false) {
            alwaysAllow = true
            resolve(true, "task")
        }, gap(8))
        box.addView(wider, spaced(8))
        box.addView(label(text("「本次都允许」：这次任务不再逐一询问。「一直允许」：以后在这里交给 AI 的操作都直接执行，可在输入框下方关闭。密码框始终不会碰。",
            "“Allow for this task”: no more questions this time. “Always allow”: tasks given here run without asking from now on; turn it off under the input. Password fields are never touched."),
            11.5f, secondaryText()), spaced(8))
    }

    private fun renderDone(box: LinearLayout) {
        if (openedForRepeat && result == null) {
            // Shown only for a repeat started from a chat: the repeat row below says it all.
            val header = row()
            header.addView(label(text("定时重复", "Repeat"), 15f, accent(), bold = true),
                LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            header.addView(iconButton(R.drawable.ic_panel_collapse, secondaryText(), text("收起", "Shrink")) { collapsed = true; render() })
            header.addView(iconButton(R.drawable.ic_bubble_close, secondaryText(), text("关闭", "Close")) { close() })
            box.addView(header)
            return
        }
        val header = row()
        header.addView(label(if (failed) text("没有完成", "Not finished") else text("完成了", "Done"), 15f,
            if (failed) DANGER else accent(), bold = true), LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        header.addView(iconButton(R.drawable.ic_panel_context, if (contextOpen) accent() else secondaryText(),
            text("看过程", "Show the steps")) { contextOpen = !contextOpen; render() })
        header.addView(iconButton(R.drawable.ic_panel_collapse, secondaryText(), text("收起", "Shrink")) { collapsed = true; render() })
        header.addView(iconButton(R.drawable.ic_bubble_close, secondaryText(), text("关闭", "Close")) { close() })
        box.addView(header)
        if (contextOpen) renderContext(box)
        val scroll = ScrollView(service).apply { isVerticalScrollBarEnabled = true }
        scroll.addView(label(result?.ifBlank { null }?.let(::plainText) ?: text("（没有文字结果）", "(No written result)"), 14f, primaryText()))
        box.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
            topMargin = dp(6)
        })
        scroll.post { if (scroll.height > dp(200)) scroll.layoutParams = scroll.layoutParams.apply { height = dp(200) } }
        val buttons = row().apply { gravity = Gravity.END }
        if (sessionId != null) buttons.addView(button(text("打开对话", "Open chat"), accent(), filled = false) { openConversation() })
        // Did not get there (or misread the screen): try again, looking at the screen afresh.
        lastRequest?.let { request ->
            buttons.addView(button(text("重试", "Retry"), accent(), filled = failed) { submit(request, retry = true) }, gap(8))
        }
        buttons.addView(button(text("继续说", "Follow up"), accent(), filled = !failed) { setStage(Stage.COMPOSE) }, gap(8))
        box.addView(buttons, spaced(12))
        // Done this way once: the same steps again later with one tap, without the model.
        if (savedShortcut) {
            box.addView(label(text("已存为快捷操作：下次打开这个面板，点它就能直接做", "Saved as a shortcut: next time, tap it in this panel"),
                12f, accent()), spaced(8))
        } else if (recorded.isNotEmpty() && !failed) {
            val save = row().apply { gravity = Gravity.END }
            save.addView(button(text("存为快捷操作（不用 AI 再做一遍）", "Save as a shortcut (no AI next time)"), accent(), filled = false) {
                val name = (lastRequest ?: text("快捷操作", "Shortcut")).take(24)
                val steps = recorded
                scope.launch {
                    withContext(Dispatchers.IO) { runCatching { PhoneMemory.saveShortcut(service, name, targetPackage, targetLabel, steps) } }
                    savedShortcut = true
                    render()
                }
            })
            box.addView(save, spaced(8))
        }
        // Done well: let the AI write it up as a skill (general steps it can follow on a changed
        // screen), unlike a shortcut, which replays the exact taps.
        if (!failed && sessionId != null) {
            val skill = row().apply { gravity = Gravity.END }
            skill.addView(button(text("存为技能（AI 以后照着做）", "Save as a skill (the AI follows it later)"), accent(), filled = false) {
                setStage(Stage.COMPOSE)
                submit(text("把刚才这次操作整理成一个技能保存下来（用 save_skill），写成以后在类似请求里能照着做的通用步骤，然后告诉我技能名。",
                    "Save what you just did as a skill (save_skill): general steps to follow for similar requests later, then tell me its name."))
            })
            box.addView(skill, spaced(8))
        }
    }

    // ---- Shortcuts -----------------------------------------------------------------------------

    /** Saved shortcuts for the app in front (and those that open their own app first), as chips. */
    private fun renderShortcuts(box: LinearLayout) {
        val all = runCatching { PhoneMemory.shortcuts(service) }.getOrDefault(emptyList())
        val fitting = all.filter { shortcut ->
            val first = shortcut.steps.optJSONObject(0)?.optString("kind")
            shortcut.app == null || shortcut.app == targetPackage || first == "launch" || first == "page"
        }.take(8)
        if (fitting.isEmpty()) return
        box.addView(label(text("快捷操作（点一下直接做，长按删除）", "Shortcuts (tap to run, hold to delete)"), 12f, secondaryText()), spaced(10))
        val chips = LinearLayout(service).apply { orientation = LinearLayout.HORIZONTAL }
        fitting.forEach { shortcut ->
            chips.addView(label(shortcut.name, 13f, accent(), bold = true, single = true).apply {
                setPadding(dp(12), dp(7), dp(12), dp(7))
                background = GradientDrawable().apply { cornerRadius = dp(16).toFloat(); setStroke(dp(1), accent()) }
                setOnClickListener { runShortcut(shortcut) }
                setOnLongClickListener { confirmDelete = shortcut.id; render(); true }
            }, gap(6))
        }
        box.addView(android.widget.HorizontalScrollView(service).apply { isHorizontalScrollBarEnabled = false; addView(chips) }, spaced(6))
        fitting.firstOrNull { it.id == confirmDelete }?.let { shortcut ->
            val confirm = row().apply { gravity = Gravity.CENTER_VERTICAL }
            confirm.addView(label(text("删除「${shortcut.name}」？", "Delete “${shortcut.name}”?"), 12.5f, primaryText()),
                LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            confirm.addView(button(text("取消", "Cancel"), accent(), filled = false) { confirmDelete = null; render() })
            confirm.addView(button(text("删除", "Delete"), DANGER, filled = false) {
                confirmDelete = null
                scope.launch {
                    withContext(Dispatchers.IO) { runCatching { PhoneMemory.deleteShortcut(service, shortcut.id) } }
                    render()
                }
            }, gap(6))
            box.addView(confirm, spaced(6))
        }
    }

    /** Runs a saved shortcut: each step finds its control on the screen again; no model involved. */
    private fun runShortcut(shortcut: PhoneMemory.Shortcut) {
        if (stage != Stage.COMPOSE || taskId != null || replaying != null) return
        replaying = shortcut
        result = null; failed = false; stopping = false
        status = text("快捷操作：${shortcut.name}", "Shortcut: ${shortcut.name}")
        stepCount = 0; steps.clear(); taskSteps.clear()
        collapsed = autoCollapse
        hideKeyboard()
        setStage(Stage.WORKING)
        scope.launch {
            val outcome = withContext(Dispatchers.IO) {
                runCatching { service.replay(shortcut.steps) }.getOrElse { it.message ?: text("出错了", "Something went wrong") }
            }
            replaying = null
            lastRequest = null
            recorded = emptyList()
            savedShortcut = false
            result = if (outcome == null) text("快捷操作「${shortcut.name}」做完了（${shortcut.steps.length()} 步）",
                "Shortcut “${shortcut.name}” done (${shortcut.steps.length()} steps)")
                else text("快捷操作「${shortcut.name}」停在这里：$outcome", "Shortcut “${shortcut.name}” stopped: $outcome")
            failed = outcome != null
            collapsed = false
            if (root != null) setStage(Stage.DONE)
        }
    }

    // ---- The task ----------------------------------------------------------------------------

    private fun submit(raw: String, retry: Boolean = false) {
        val request = raw.trim()
        if (request.isEmpty() || stage != (if (retry) Stage.DONE else Stage.COMPOSE)) return
        if (!retry) draft = ""
        lastRequest = request
        result = null; failed = false; stopping = false; approval = null; resolving = false
        status = ""; stepCount = 0; steps.clear(); answer = StringBuilder()
        taskId = "pending"
        chooserOpen = false
        openedForRepeat = false
        if (repeatState?.running != true) repeatState = null
        collapsed = autoCollapse
        shrinkAfterApproval = false
        paused = false
        addition = ""
        // A follow-up continues the same conversation: its context goes on from what is shown.
        if (!retry && sessionId == null) contextItems.clear()
        taskSteps.clear()
        recorded = emptyList()
        savedShortcut = false
        confirmDelete = null
        service.startRecording()
        setStage(Stage.WORKING)
        scope.launch {
            try {
                status = text("正在连接 AI 引擎…", "Connecting to the engine…"); render()
                if (!withContext(Dispatchers.IO) { ensureEngine() }) {
                    throw IllegalStateException(text("AI 引擎没有启动，请打开 Agent Workspace 后重试", "The engine did not start; open Agent Workspace and try again"))
                }
                // A request typed here, after looking at the screen, is the go-ahead to act again
                // when automation was paused (by the user, or after an action Android rejected).
                withContext(Dispatchers.IO) {
                    val control = AndroidAutomationControl.readState(service)
                    if (control.optBoolean("paused") || control.optBoolean("takeover_requested")) {
                        AndroidAutomationControl.set(service, false, false)
                        service.invalidate()
                    }
                }
                val session = sessionId ?: withContext(Dispatchers.IO) { createSession(request) }
                sessionId = session
                val created = withContext(Dispatchers.IO) {
                    EngineHttp.request(service, "POST", "/mobile/tasks", task(session, request, retry), 20000)
                }
                if (!created.ok) throw IllegalStateException(created.error)
                val id = created.body.optJSONObject("task")?.optString("task_id")?.ifBlank { null }
                    ?: throw IllegalStateException(text("引擎没有返回任务", "The engine returned no task"))
                if (taskId != "pending") {
                    // Stopped while it was being submitted.
                    withContext(Dispatchers.IO) {
                        runCatching { EngineHttp.request(service, "POST", "/mobile/tasks/${Uri.encode(id)}/cancel", JSONObject(), 15000) }
                    }
                    return@launch
                }
                taskId = id
                sequence = 0
                status = text("AI 正在看屏幕…", "The agent is looking at the screen…")
                render()
                poller = scope.launch { follow() }
            } catch (failure: Exception) {
                if (taskId == "pending") finish(failure.message ?: text("无法开始", "Could not start"), true)
            }
        }
    }

    /**
     * The task as the engine takes it: the user's own words as the message (what the conversation, the
     * widget and notifications show); the engine adds its phone instructions, the app the panel was
     * opened over and whether this is a retry.
     */
    private fun task(session: String, request: String, retry: Boolean): JSONObject = JSONObject()
        .put("session_id", session).put("prompt", request).put("phone_control", true)
        .apply {
            targetLabel?.let { name -> put("phone_app", (targetPackage?.let { "$name ($it)" } ?: name).take(200)) }
            if (retry) put("phone_retry", true)
            if (alwaysAllow) put("auto_approve", true)
            // How earlier requests in this app were done: fewer steps spent finding the way.
            runCatching { PhoneMemory.tips(service, targetPackage) }.getOrNull()?.let { put("phone_tips", it) }
            if (sendScreen) runCatching { service.screenWords(2000) }.getOrNull()?.takeIf { it.isNotBlank() }?.let { put("phone_screen", it) }
            // The panel's own choice, for this task only; the app's setting stays as it is.
            chosenModel().takeIf { it.isNotEmpty() }?.let { put("model", it) }
            chosenEffort().takeIf { it.isNotEmpty() }?.let { put("reasoning_effort", it) }
        }
        .put("request_id", "phone-${UUID.randomUUID()}")

    private fun createSession(request: String): String {
        val title = text("操作手机：", "Phone: ") + request.replace('\n', ' ').take(24)
        val reply = EngineHttp.request(service, "POST", "/sessions", JSONObject().put("title", title), 15000)
        if (!reply.ok) throw IllegalStateException(reply.error)
        return reply.body.optString("id").ifBlank { throw IllegalStateException(text("无法创建对话", "Could not create a conversation")) }
    }

    private fun healthy(): Boolean = runCatching { EngineHttp.request(service, "GET", "/health", null, 2000).ok }.getOrDefault(false)

    /** Starts the engine the way the app does when it is not running yet (it shares this process). */
    private fun ensureEngine(): Boolean {
        if (healthy()) return true
        runCatching {
            TermuxDaemonService.start(service, Intent(service, TermuxDaemonService::class.java)
                .putExtra(TermuxDaemonService.EXTRA_PROVIDER_CONFIGURATION, MobileProviderSettings.load(service).toJson()))
        }
        repeat(80) {
            SystemClock.sleep(500)
            if (healthy()) return true
        }
        return false
    }

    /** Follows the task until it ends: model steps, approvals and the reply. */
    private suspend fun follow() {
        val id = taskId ?: return
        var misses = 0
        while (scope.isActive && root != null && taskId == id) {
            try {
                val updates = withContext(Dispatchers.IO) {
                    EngineHttp.request(service, "GET", "/mobile/tasks/${Uri.encode(id)}/events?after=$sequence", null, 10000)
                }
                if (updates.ok) updates.body.optJSONArray("events")?.let { events ->
                    for (index in 0 until events.length()) events.optJSONObject(index)?.let(::consume)
                }
                val snapshot = withContext(Dispatchers.IO) {
                    EngineHttp.request(service, "GET", "/mobile/tasks/${Uri.encode(id)}", null, 10000)
                }
                if (!snapshot.ok) throw IllegalStateException(snapshot.error)
                misses = 0
                val pending = snapshot.body.optJSONArray("approvals")?.optJSONObject(0)
                snapshot.body.optJSONObject("task")?.let { task ->
                    if (!pausing && task.has("paused") && task.optBoolean("paused") != paused) {
                        paused = task.optBoolean("paused")
                        if (stage == Stage.WORKING) setStage(Stage.WORKING) else render()
                    }
                }
                if (pending != null && !resolving) {
                    if (approval?.optString("request_id") != pending.optString("request_id")) {
                        contextItems.add("approval" to describeApproval(pending))
                        approval = pending
                        // An approval needs the user: a shrunk panel opens again for it, and shrinks back after.
                        shrinkAfterApproval = shrinkAfterApproval || collapsed
                        collapsed = false
                        setStage(Stage.APPROVAL)
                        root?.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
                    }
                } else if (pending == null && stage == Stage.APPROVAL && !resolving) {
                    approval = null
                    shrinkBack()
                    setStage(Stage.WORKING)
                }
                val task = snapshot.body.optJSONObject("task")
                val state = task?.optString("state")
                if (state in setOf("succeeded", "failed", "cancelled", "interrupted")) {
                    // The reply can be recorded after the events read above: read them once more.
                    withContext(Dispatchers.IO) {
                        runCatching { EngineHttp.request(service, "GET", "/mobile/tasks/${Uri.encode(id)}/events?after=$sequence", null, 10000) }.getOrNull()
                    }?.takeIf { it.ok }?.body?.optJSONArray("events")?.let { events ->
                        for (index in 0 until events.length()) events.optJSONObject(index)?.let(::consume)
                    }
                }
                when (state) {
                    "succeeded" -> { finish(result?.takeIf { it.isNotBlank() } ?: answer.toString().trim(), false); return }
                    "failed" -> { finish(task.optString("reason").ifBlank { text("任务失败", "The task failed") }, true); return }
                    "cancelled" -> { finish(text("已停止", "Stopped"), true); return }
                    "interrupted" -> { finish(text("任务被中断，可在应用里继续", "The task was interrupted; resume it in the app"), true); return }
                }
            } catch (failure: Exception) {
                if (++misses >= 8) { finish(text("和 AI 引擎的连接中断了", "Lost the connection to the engine"), true); return }
            }
            delay(POLL_MS)
        }
    }

    private fun consume(event: JSONObject) {
        val number = event.optLong("sequence")
        if (number <= sequence) return
        sequence = number
        val envelope = event.optJSONObject("payload") ?: JSONObject()
        val payload = envelope.optJSONObject("data") ?: envelope
        val type = event.optString("event_type")
        noteContext(type, payload)
        when (type) {
            "assistant.delta" -> if (payload.optString("kind") != "reasoning") answer.append(payload.optString("text"))
            "runtime.message.created" -> if (payload.optString("role") == "assistant") {
                // Each model turn starts its text afresh; the last one is the reply.
                val content = payload.optString("content")
                answer = StringBuilder(content)
                if (content.isNotBlank()) { status = plainText(content).lineSequence().first { it.isNotBlank() }.take(80); render() }
            }
            "runtime.model.requested" -> if (stage == Stage.WORKING && status.isBlank()) {
                status = text("AI 正在思考…", "The agent is thinking…"); render()
            }
            "runtime.tool.started" -> {
                val name = payload.optString("name").ifBlank { payload.optString("tool_name") }
                if (!name.startsWith("android_")) { status = text("使用工具：$name", "Using $name"); render() }
            }
            "task.completed" -> payload.optString("text").takeIf { it.isNotBlank() }?.let { result = it; answer = StringBuilder(it) }
        }
    }

    /** One line of the context view for an event of the task, if it says something to the user. */
    private fun noteContext(type: String, payload: JSONObject) {
        val entry: Pair<String, String>? = when {
            type == "runtime.message.created" -> {
                val content = plainText(payload.optString("content")).trim()
                when {
                    content.isEmpty() || content.startsWith("[Phone control]") -> null
                    payload.optString("role") == "user" -> "user" to content.substringBefore("\n\n[Phone control]").take(600)
                    payload.optString("role") == "assistant" -> "ai" to content.take(1200)
                    else -> null
                }
            }
            type == "runtime.tool.proposed" -> {
                val name = payload.optString("name").ifBlank { payload.optString("tool_name") }
                val arguments = payload.optJSONObject("arguments")
                "tool" to if (name == "android_action" && arguments != null) {
                    // In words, as the approval prompt says it.
                    runCatching { service.describeAction(arguments) }.getOrDefault(name)
                } else toolWords(name, arguments)
            }
            type == "runtime.tool.settled" -> {
                val outcome = payload.opt("result")?.toString().orEmpty()
                val error = runCatching { JSONObject(outcome).optJSONObject("error") }.getOrNull()
                if (error != null) "error" to "${error.optString("code")}：${error.optString("message").take(160)}" else null
            }
            type == "runtime.image.attached" -> "note" to text("截了一张图", "Took a screenshot")
            type.endsWith("input.received") -> null  // shown when sent from here
            else -> null
        }
        entry?.let {
            // What the user added from here comes back as the task's own message: once is enough.
            if (it.first == "user" && contextItems.any { item -> item == it }) return
            contextItems.add(it)
            while (contextItems.size > 200) contextItems.removeAt(0)
            if (contextOpen && stage != Stage.COMPOSE) render()
        }
    }

    private fun toolWords(name: String, arguments: JSONObject?): String = when (name) {
        "android_observe" -> if (arguments?.has("until_text") == true || arguments?.has("until_gone") == true)
            text("等待屏幕变化", "Waiting for the screen") else text("查看屏幕", "Looked at the screen")
        "android_screenshot" -> text("截图看屏幕", "Took a screenshot")
        else -> name + (arguments?.optString("path")?.takeIf { it.isNotEmpty() }?.let { " $it" } ?: "")
    }

    private fun resolve(allowed: Boolean, scope: String) {
        val request = approval ?: return
        if (resolving) return
        resolving = true
        this.scope.launch {
            val reply = withContext(Dispatchers.IO) {
                runCatching {
                    EngineHttp.request(service, "POST", "/mobile/approvals/${Uri.encode(request.optString("request_id"))}/resolve",
                        JSONObject().put("allowed", allowed).put("scope", scope), 15000)
                }.getOrNull()
            }
            resolving = false
            if (reply?.ok == true) {
                approval = null
                status = if (allowed) text("已允许，继续操作…", "Allowed; carrying on…") else text("已拒绝", "Denied")
                shrinkBack()
                setStage(Stage.WORKING)
            } else {
                status = text("确认没有送达，请再试一次", "The answer did not arrive; try again")
                render()
            }
        }
    }

    /** The user saw it stuck or misreading: the running task looks at the screen again and carries on. */
    private fun refresh() {
        val id = taskId?.takeIf { it != "pending" } ?: return
        status = text("已请 AI 重新看屏幕…", "Asked the agent to look again…")
        render()
        scope.launch {
            val reply = withContext(Dispatchers.IO) {
                runCatching {
                    EngineHttp.request(service, "POST", "/mobile/tasks/${Uri.encode(id)}/steer", JSONObject()
                        .put("prompt", text("（刷新）屏幕可能变了，或者刚才没读清楚：请先用 android_screenshot 重新看当前屏幕，再继续。",
                            "(Refresh) The screen may have changed or was misread: look at the current screen again with android_screenshot, then carry on."))
                        .put("input_id", "refresh-${UUID.randomUUID()}"), 15000)
                }.getOrNull()
            }
            if (reply?.ok != true && taskId == id) {
                status = text("刷新没有送达，可以停止后重试", "The refresh did not arrive; stop and retry")
                render()
            }
        }
    }

    private fun stop() {
        if (replaying != null) {
            service.stopReplay()
            stopping = true
            render()
            return
        }
        val id = taskId ?: return
        if (stopping) return
        // Not submitted yet: the submission cancels what it creates once it sees this.
        if (id == "pending") { finish(text("已停止", "Stopped"), true); return }
        stopping = true
        render()
        scope.launch {
            withContext(Dispatchers.IO) {
                runCatching { EngineHttp.request(service, "POST", "/mobile/tasks/${Uri.encode(id)}/cancel", JSONObject(), 15000) }
            }
        }
    }

    /** A panel shrunk before an approval opened it shrinks again once it is answered. */
    private fun shrinkBack() {
        if (shrinkAfterApproval) collapsed = true
        shrinkAfterApproval = false
    }

    private fun finish(message: String, failure: Boolean) {
        poller?.cancel()
        poller = null
        result = message
        failed = failure
        stopping = false
        approval = null
        taskId = null
        // What worked, kept for this app (the agent reads it next time) and as a possible shortcut.
        val actions = service.takeRecording()
        recorded = if (failure) emptyList() else actions
        if (!failure && taskSteps.isNotEmpty()) {
            val app = targetPackage
            val request = lastRequest
            val words = taskSteps.toList()
            scope.launch(Dispatchers.IO) { runCatching { PhoneMemory.rememberTip(service, app, request, words) } }
        }
        // The reply shows in full, unless a repeat it started is still running over the screen.
        shrinkAfterApproval = false
        paused = false
        listening?.cancel()
        listening = null
        collapsed = collapsed && repeatState?.running == true
        if (root == null) return
        setStage(Stage.DONE)
        root?.performHapticFeedback(if (failure) HapticFeedbackConstants.REJECT else HapticFeedbackConstants.CONFIRM)
    }

    private fun openConversation() {
        val session = sessionId ?: return
        runCatching {
            service.startActivity(Intent(service, WebUiActivity::class.java)
                .setAction(TaskNotificationPublisher.ACTION_OPEN_TASK)
                .setData(Uri.parse("agentworkspace://session/${Uri.encode(session)}"))
                .putExtra(TaskNotificationPublisher.EXTRA_SESSION_ID, session)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP))
        }
        close()
    }

    private fun describeApproval(request: JSONObject): String {
        val details = request.optJSONObject("details") ?: JSONObject()
        if (request.optString("kind") == "egress") {
            val host = runCatching { Uri.parse(details.optString("endpoint")).host }.getOrNull() ?: details.optString("endpoint")
            return text("把对话和屏幕内容发送到 $host", "Send the conversation and screen content to $host")
        }
        val tool = details.optString("tool")
        val arguments = details.optJSONObject("arguments") ?: JSONObject()
        if (tool == "android_action") return service.describeAction(arguments)
        return text("使用工具 $tool", "Use the tool $tool")
    }

    // ---- Small view helpers ------------------------------------------------------------------

    /** A breathing dot while the agent works: a solid core and a ring that swells and fades. */
    private fun pulse(): View = FrameLayout(service).apply {
        val ring = View(service).apply { background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(accent()) } }
        val core = View(service).apply { background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(accent()) } }
        addView(ring, FrameLayout.LayoutParams(dp(10), dp(10), Gravity.CENTER))
        addView(core, FrameLayout.LayoutParams(dp(10), dp(10), Gravity.CENTER))
        android.animation.ObjectAnimator.ofPropertyValuesHolder(ring,
            android.animation.PropertyValuesHolder.ofFloat(View.SCALE_X, 1f, 2.2f),
            android.animation.PropertyValuesHolder.ofFloat(View.SCALE_Y, 1f, 2.2f),
            android.animation.PropertyValuesHolder.ofFloat(View.ALPHA, 0.55f, 0f)).apply {
            duration = 1100
            repeatCount = android.animation.ValueAnimator.INFINITE
            // Runs only while the dot is on screen; each render replaces it.
            ring.addOnAttachStateChangeListener(object : View.OnAttachStateChangeListener {
                override fun onViewAttachedToWindow(v: View) { start() }
                override fun onViewDetachedFromWindow(v: View) { cancel() }
            })
        }
    }

    /** A grip along the top: drag it to move the panel up or down, out of the way of the app. */
    private fun grip(): View {
        val handle = FrameLayout(service).apply {
            addView(View(service).apply {
                background = GradientDrawable().apply { cornerRadius = dp(2).toFloat(); setColor(if (dark()) 0x40FFFFFF else 0x26000000) }
            }, FrameLayout.LayoutParams(dp(36), dp(4), Gravity.CENTER))
            contentDescription = text("拖动移开", "Drag to move")
        }
        var startY = 0
        var downY = 0f
        handle.setOnTouchListener { _, event ->
            val layout = params ?: return@setOnTouchListener false
            when (event.actionMasked) {
                android.view.MotionEvent.ACTION_DOWN -> { startY = layout.y; downY = event.rawY }
                android.view.MotionEvent.ACTION_MOVE -> {
                    val height = root?.height ?: 0
                    val limit = (service.resources.displayMetrics.heightPixels - height - dp(48)).coerceAtLeast(0)
                    layout.y = (startY + (event.rawY - downY).toInt()).coerceIn(0, limit)
                    root?.let { view -> runCatching { windowManager.updateViewLayout(view, layout) } }
                }
            }
            true
        }
        return handle
    }

    private fun row() = LinearLayout(service).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }

    private fun spaced(top: Int) = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        .apply { topMargin = dp(top) }

    private fun gap(start: Int) = LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        .apply { marginStart = dp(start) }

    private fun label(value: String, size: Float, color: Int, bold: Boolean = false, single: Boolean = false) = TextView(service).apply {
        text = value
        textSize = size
        setTextColor(color)
        if (bold) typeface = Typeface.DEFAULT_BOLD
        if (single) { maxLines = 1; ellipsize = TextUtils.TruncateAt.END }
        setLineSpacing(0f, 1.15f)
    }

    private fun icon(resource: Int, tint: Int, size: Int) = ImageView(service).apply {
        setImageResource(resource)
        imageTintList = ColorStateList.valueOf(tint)
        layoutParams = LinearLayout.LayoutParams(dp(size), dp(size))
    }

    private fun iconButton(resource: Int, tint: Int, description: String, action: () -> Unit) = FrameLayout(service).apply {
        contentDescription = description
        background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(field()) }
        addView(ImageView(service).apply { setImageResource(resource); imageTintList = ColorStateList.valueOf(tint) },
            FrameLayout.LayoutParams(dp(18), dp(18), Gravity.CENTER))
        layoutParams = LinearLayout.LayoutParams(dp(36), dp(36)).apply { marginStart = dp(8) }
        setOnClickListener { it.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY); action() }
    }

    private fun button(value: String, color: Int, filled: Boolean, action: () -> Unit) = TextView(service).apply {
        text = value
        textSize = 14f
        typeface = Typeface.DEFAULT_BOLD
        gravity = Gravity.CENTER
        setTextColor(if (filled) (if (dark()) 0xFF0B1F1C.toInt() else Color.WHITE) else color)
        background = GradientDrawable().apply {
            cornerRadius = dp(18).toFloat()
            if (filled) setColor(color) else { setColor(Color.TRANSPARENT); setStroke(dp(1), color) }
        }
        setPadding(dp(14), dp(8), dp(14), dp(8))
        setOnClickListener { it.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY); action() }
    }

    private fun showKeyboard(view: View) {
        view.requestFocus()
        service.getSystemService(InputMethodManager::class.java)?.showSoftInput(view, InputMethodManager.SHOW_IMPLICIT)
    }

    private fun hideKeyboard() {
        val view = root ?: return
        service.getSystemService(InputMethodManager::class.java)?.hideSoftInputFromWindow(view.windowToken, 0)
    }
}

/**
 * A reply written in Markdown as plain text for the panel's small text view: "**56,088**" and
 * "`99×99`" read as 56,088 and 99×99, headings lose their #, list items get a bullet.
 */
internal fun plainText(markdown: String): String = markdown.lineSequence()
    .filterNot { it.trimStart().startsWith("```") }
    .map { line ->
        line.replace(Regex("^\\s{0,3}#{1,6}\\s+"), "")
            .replace(Regex("^(\\s*)[-*+]\\s+"), "$1• ")
            .replace(Regex("\\[([^\\]]+)]\\([^)]*\\)"), "$1")
            .replace(Regex("(\\*\\*|__)(.+?)\\1"), "$2")
            .replace(Regex("(?<![\\w*])\\*(?!\\s)(.+?)(?<!\\s)\\*(?![\\w*])"), "$1")
            .replace(Regex("`([^`]*)`"), "$1")
    }
    .joinToString("\n").trim()
