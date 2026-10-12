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
    private val preferences = service.getSharedPreferences("phone-control", android.content.Context.MODE_PRIVATE)
    /** "Always allow": phone tasks from this panel run without asking (the user can turn it off here). */
    private var alwaysAllow: Boolean
        get() = preferences.getBoolean("always_allow", false)
        set(value) { preferences.edit().putBoolean("always_allow", value).apply() }

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
            service.sendBroadcast(Intent(ACTION_PANEL_OPENED).setPackage(service.packageName))
        } else if (stage == Stage.DONE) {
            targetPackage = packageName ?: targetPackage
            targetLabel = label ?: targetLabel
        }
        if (stage == Stage.DONE || (stage == Stage.COMPOSE && taskId == null)) setStage(Stage.COMPOSE)
        else render()
    }

    fun close() {
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
        announceClosed()
    }

    private fun announceClosed() {
        service.sendBroadcast(Intent(ACTION_PANEL_CLOSED).setPackage(service.packageName))
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
            if (root == null || taskId == null) return@post
            stepCount += 1
            status = description
            steps.addLast(description)
            while (steps.size > MAX_STEPS) steps.removeFirst()
            if (stage == Stage.WORKING) render()
        }
    }

    // ---- Stages ------------------------------------------------------------------------------

    private fun setStage(next: Stage) {
        stage = next
        val view = root ?: return
        params?.let {
            // Only the input takes the keyboard; while the agent works the app keeps its focus.
            it.flags = if (next == Stage.COMPOSE) it.flags and WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE.inv()
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
        box.addView(grip(), LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(16)))
        when (stage) {
            Stage.COMPOSE -> renderCompose(box)
            Stage.WORKING -> renderWorking(box)
            Stage.APPROVAL -> renderApproval(box)
            Stage.DONE -> renderDone(box)
        }
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
        inputRow.addView(send, LinearLayout.LayoutParams(dp(42), dp(42)).apply { marginStart = dp(8); bottomMargin = dp(1) })
        box.addView(inputRow, spaced(10))
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

    private fun renderWorking(box: LinearLayout) {
        val line = row()
        line.addView(pulse(), LinearLayout.LayoutParams(dp(22), dp(22)))
        val texts = LinearLayout(service).apply {
            orientation = LinearLayout.VERTICAL
            setOnClickListener { stepsOpen = !stepsOpen; render() }
        }
        texts.addView(label(if (stopping) text("正在停止…", "Stopping…") else status.ifBlank { text("正在准备…", "Getting ready…") },
            14.5f, primaryText(), bold = true, single = true))
        texts.addView(label(if (stepCount > 0) text("第 $stepCount 步 · 点这里看过程", "Step $stepCount · tap for details")
            else text("AI 正在思考", "The agent is thinking"), 12f, secondaryText(), single = true))
        line.addView(texts, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply { marginStart = dp(12) })
        // Stuck or misread the screen: have it look again and carry on.
        line.addView(iconButton(R.drawable.ic_panel_refresh, accent(), text("让 AI 重新看屏幕", "Have the agent look again")) { refresh() })
        line.addView(iconButton(R.drawable.ic_panel_stop, DANGER, text("停止", "Stop")) { stop() })
        box.addView(line)
        if (stepsOpen && steps.isNotEmpty()) {
            val list = LinearLayout(service).apply { orientation = LinearLayout.VERTICAL }
            steps.forEach { list.addView(label("• $it", 12.5f, secondaryText(), single = true)) }
            box.addView(list, spaced(8))
        }
    }

    private fun renderApproval(box: LinearLayout) {
        val request = approval ?: run { setStage(Stage.WORKING); return }
        box.addView(label(text("需要你确认", "Needs your approval"), 15f, primaryText(), bold = true))
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
        val header = row()
        header.addView(label(if (failed) text("没有完成", "Not finished") else text("完成了", "Done"), 15f,
            if (failed) DANGER else accent(), bold = true), LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        header.addView(iconButton(R.drawable.ic_bubble_close, secondaryText(), text("关闭", "Close")) { close() })
        box.addView(header)
        val scroll = ScrollView(service).apply { isVerticalScrollBarEnabled = true }
        scroll.addView(label(result?.ifBlank { null }?.let(::plainText) ?: text("（没有文字结果）", "(No written result)"), 14f, primaryText()))
        box.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
            topMargin = dp(6)
        })
        scroll.post { if (scroll.height > dp(200)) scroll.layoutParams = scroll.layoutParams.apply { height = dp(200) } }
        val buttons = row().apply { gravity = Gravity.END }
        buttons.addView(button(text("打开对话", "Open chat"), accent(), filled = false) { openConversation() })
        // Did not get there (or misread the screen): try again, looking at the screen afresh.
        lastRequest?.let { request ->
            buttons.addView(button(text("重试", "Retry"), accent(), filled = failed) { submit(request, retry = true) }, gap(8))
        }
        buttons.addView(button(text("继续说", "Follow up"), accent(), filled = !failed) { setStage(Stage.COMPOSE) }, gap(8))
        box.addView(buttons, spaced(12))
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
                if (pending != null && !resolving) {
                    if (approval?.optString("request_id") != pending.optString("request_id")) {
                        approval = pending
                        setStage(Stage.APPROVAL)
                        root?.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
                    }
                } else if (pending == null && stage == Stage.APPROVAL && !resolving) {
                    approval = null
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
        when (event.optString("event_type")) {
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

    private fun finish(message: String, failure: Boolean) {
        poller?.cancel()
        poller = null
        result = message
        failed = failure
        stopping = false
        approval = null
        taskId = null
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
