package com.agentworkspace.mobile.automation

import android.accessibilityservice.AccessibilityService
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.SystemClock
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo
import android.view.inputmethod.InputMethodManager
import android.widget.LinearLayout
import android.widget.TextView
import com.agentworkspace.mobile.UiText
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** What a demonstration keeps of the words on the screen, on plain values so it can be tested without a phone. */
internal object DemonstrationWords {
    private val separators = Regex("[\\s,，.．。·\\-–—_¥￥$€£]")
    private val longNumber = Regex("\\d{4,}")
    private val amount = Regex("[¥￥$€£]\\s*\\d")
    private val key = Regex("[0-9A-Za-z]")

    /** This many keys in a row on an app's own keypad are a number or a code, not buttons to find again. */
    private const val KEYS_IN_A_ROW = 4

    /** The words, unless they look like a code, a phone number or an amount, however they are written. */
    fun keep(text: String?): String? {
        val value = text?.replace(Regex("\\s+"), " ")?.trim()?.take(200)
        return value?.takeIf { it.isNotEmpty() && !amount.containsMatchIn(it) && !longNumber.containsMatchIn(it.replace(separators, "")) }
    }

    /** A text field by what it says when empty, never by what it holds. */
    fun fieldName(hint: String?, description: String?): String? = keep(hint) ?: keep(description)

    fun yours(words: String): JSONObject = JSONObject().put("kind", "tap").put("x", 0).put("y", 0).put("label", words)

    private fun isKey(step: JSONObject?): Boolean =
        step?.optString("kind") == "tap" && key.matches(step.optString("label").trim())

    /**
     * Adds a step to [steps]. A run of single keys collapses into [yours] (a PIN pad's digits, in
     * order, would be the PIN), and a key after that adds nothing; the same goes for [yours] itself.
     */
    fun add(steps: JSONArray, step: JSONObject, yours: JSONObject) {
        val last = steps.optJSONObject(steps.length() - 1)
        val afterYours = last != null && last.optString("label") == yours.optString("label")
        if (afterYours && (isKey(step) || step.optString("label") == yours.optString("label"))) return
        if (isKey(step)) {
            var run = 0
            while (isKey(steps.optJSONObject(steps.length() - 1 - run))) run++
            if (run + 1 >= KEYS_IN_A_ROW) {
                repeat(run) { steps.remove(steps.length() - 1) }
                steps.put(yours)
                return
            }
        }
        steps.put(step)
    }
}

/**
 * 「演示一遍」: the user's own taps in other apps, as shortcut steps (mobile_shortcuts.KINDS), so the
 * app can do it again later. Started from the Shortcuts page through the engine; a small bar over the
 * screen says that it records, how many steps, and ends it. What is kept: the app opened, the controls
 * tapped or long-pressed by their words (and where), the fields typed into (never what was typed: the
 * user fills that in before saving), the direction of scrolling, and the keyboard's own search key
 * (an "enter" step when the keyboard closed after typing without a tap). Nothing in this app, the home
 * screen, the keyboard or the notification shade; nothing from a password field or what a text field
 * holds; no words with a long number in them (codes, phone numbers, amounts). On a password or payment
 * screen, and for a run of keys on an app's own keypad, one step says it is the user's to do there.
 */
internal class DemonstrationRecorder(private val service: AccessibilityService, private val finished: () -> Unit) {
    companion object {
        const val MAX_STEPS = 60
        fun resultFile(context: Context): File = File(context.filesDir, "automation/demonstration.json")
    }

    private val steps = JSONArray()
    private val ignored: Set<String>
    private var front: String? = null
    private var firstApp: String? = null
    private var lastClickAt = 0L
    private var lastScroll: Pair<String, Long>? = null
    private var keyboardShown = false
    private var bar: View? = null
    private var count: TextView? = null
    private var atTop = true

    init {
        val manager = service.packageManager
        // Settings answers as a home screen too, while the phone starts (priority -1000); it is an app here.
        val homes = manager.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME), 0)
            .filter { it.priority >= 0 }
            .mapNotNull { it.activityInfo?.packageName }
        val keyboards = runCatching {
            (service.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).enabledInputMethodList.map { it.packageName }
        }.getOrDefault(emptyList())
        ignored = (homes + keyboards + listOf(service.packageName, "com.android.systemui", "android")).toSet()
    }

    fun start() {
        showBar()
        // From the home screen, so the first step is the app the user opens.
        service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)
    }

    fun onEvent(event: AccessibilityEvent) {
        // About the whole screen: it comes without a package.
        if (event.eventType == AccessibilityEvent.TYPE_WINDOWS_CHANGED) { keyboard(); return }
        val app = event.packageName?.toString() ?: return
        when (event.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> if (app !in ignored && app != front) {
                // Opened from the home screen (or the recents): an app step. Led there by a tap in the
                // app before, replaying that tap gets there again. A screen with no icon of its own (Settings'
                // search, from a bar that reports no click) cannot be opened that way.
                if ((front == null || SystemClock.uptimeMillis() - lastClickAt > 1500) && service.packageManager.getLaunchIntentForPackage(app) != null)
                    add(JSONObject().put("kind", "launch").put("package", app))
                front = app
                if (firstApp == null) firstApp = app
            }
            AccessibilityEvent.TYPE_VIEW_CLICKED, AccessibilityEvent.TYPE_VIEW_LONG_CLICKED -> if (app !in ignored && front != null) {
                lastClickAt = SystemClock.uptimeMillis()
                val node = event.source
                try {
                    if (node?.isPassword == true || event.isPassword || passwordInputType(node?.inputType ?: 0)) return
                    if (secretScreen()) { add(yours()); return }
                    val step = JSONObject().put("kind", if (event.eventType == AccessibilityEvent.TYPE_VIEW_CLICKED) "tap" else "long")
                    place(step, node)
                    // A text field by its hint, as AgentAccessibilityService.ownLabel knows it: its text is what was typed.
                    val field = node?.isEditable == true || event.className?.contains("EditText") == true
                    step.put("label", (if (field) DemonstrationWords.fieldName(node?.hintText?.toString(), node?.contentDescription?.toString())
                        else words(node) ?: words(event.text?.joinToString(" "))) ?: JSONObject.NULL)
                    node?.className?.toString()?.take(120)?.let { step.put("class", it) }
                    add(step)
                } finally { node?.recycle() }
            }
            // Words a tap put there (a calculator's display, a quantity's +) come back when the tap is
            // replayed; only what is typed on the keyboard needs a typing step. A click's own change
            // arrives before the click, so the keyboard tells them apart, not the time since a tap.
            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED -> if (app !in ignored && front != null && keyboardOpen() && SystemClock.uptimeMillis() - lastClickAt > 600) {
                val node = event.source
                try {
                    if (node == null || node.isPassword || passwordInputType(node.inputType)) return
                    // The field by its hint or name; what was typed stays out.
                    val label = words(node.hintText?.toString()) ?: words(node.contentDescription?.toString())
                        ?: node.viewIdResourceName?.substringAfterLast('/')?.take(120) ?: return
                    val last = steps.optJSONObject(steps.length() - 1)
                    if (last?.optString("kind") == "type" && last.optString("label") == label) return
                    val step = JSONObject().put("kind", "type").put("label", label).put("text", "")
                    place(step, node)
                    node.className?.toString()?.take(120)?.let { step.put("class", it) }
                    add(step)
                } finally { node?.recycle() }
            }
            AccessibilityEvent.TYPE_VIEW_SCROLLED -> if (app !in ignored && front != null) {
                // -1: not told how far (older Android, some lists); taken as down.
                val deltaX = if (Build.VERSION.SDK_INT >= 28) event.scrollDeltaX else -1
                val deltaY = if (Build.VERSION.SDK_INT >= 28) event.scrollDeltaY else -1
                // A list that just got its content reports a scroll that moved nothing.
                if (deltaX == 0 && deltaY == 0) return
                val direction = when {
                    deltaX == -1 && deltaY == -1 -> "down"
                    deltaY < 0 -> "up"
                    deltaX > 0 && deltaY == 0 -> "right"
                    deltaX < 0 && deltaY == 0 -> "left"
                    else -> "down"
                }
                val now = SystemClock.uptimeMillis()
                val previous = lastScroll
                lastScroll = direction to now
                // One step per swipe: a fling sends many.
                if (previous != null && previous.first == direction && now - previous.second < 700) return
                add(JSONObject().put("kind", "scroll").put("direction", direction))
            }
        }
    }

    /** The keyboard closed right after typing, with no tap: its own search or done key. */
    private fun keyboard() {
        val shown = keyboardOpen()
        if (keyboardShown && !shown && steps.optJSONObject(steps.length() - 1)?.optString("kind") == "type" &&
            SystemClock.uptimeMillis() - lastClickAt > 400) add(JSONObject().put("kind", "enter"))
        keyboardShown = shown
    }

    private fun keyboardOpen(): Boolean =
        runCatching { service.windows.any { it.type == AccessibilityWindowInfo.TYPE_INPUT_METHOD } }.getOrDefault(false)

    private fun place(step: JSONObject, node: AccessibilityNodeInfo?) {
        val bounds = Rect().also { node?.getBoundsInScreen(it) }
        step.put("x", bounds.centerX().coerceAtLeast(0)).put("y", bounds.centerY().coerceAtLeast(0))
    }

    /** A control's words: its own, else the first of its children's; none that look like a code or a number. */
    private fun words(node: AccessibilityNodeInfo?, depth: Int = 0): String? {
        node ?: return null
        // What a field inside a row holds is typed text, a password field's even more so.
        val hidden = node.isEditable || node.isPassword || (Build.VERSION.SDK_INT >= 34 && node.isAccessibilityDataSensitive)
        val own = if (hidden) null else words(node.text?.toString()) ?: words(node.contentDescription?.toString())
        if (own != null || depth >= 3) return own
        for (index in 0 until minOf(node.childCount, 8)) {
            val child = node.getChild(index) ?: continue
            try { words(child, depth + 1)?.let { return it } } finally { child.recycle() }
        }
        return null
    }

    private fun words(text: String?): String? = DemonstrationWords.keep(text)

    /** Whether the window in front asks for a password or shows a payment step. */
    private fun secretScreen(): Boolean {
        val root = runCatching { service.rootInActiveWindow }.getOrNull() ?: return false
        var seen = 0
        fun visit(node: AccessibilityNodeInfo, depth: Int): Boolean {
            if (++seen > 400 || depth > 24) return false
            if (node.isVisibleToUser && (node.isPassword || (Build.VERSION.SDK_INT >= 34 && node.isAccessibilityDataSensitive) ||
                    passwordInputType(node.inputType) ||
                    PaymentFirewall.marksPaymentScreen(node.text?.toString()) ||
                    PaymentFirewall.marksPaymentScreen(node.contentDescription?.toString()))) return true
            for (index in 0 until minOf(node.childCount, 200)) {
                val child = node.getChild(index) ?: continue
                try { if (visit(child, depth + 1)) return true } finally { child.recycle() }
            }
            return false
        }
        return try { visit(root, 0) } finally { root.recycle() }
    }

    /** The step that stands for what stays out: a replay stops there, as it finds no such control. */
    private fun yours(): JSONObject = DemonstrationWords.yours(UiText.of(service, "这里需要你自己完成", "Finish this step yourself"))

    private fun add(step: JSONObject) {
        if (steps.length() >= MAX_STEPS) return
        DemonstrationWords.add(steps, step, yours())
        count?.text = recordingText()
    }

    private fun recordingText(): String =
        UiText.of(service, "正在记录你的操作 · ${steps.length()} 步", "Recording what you do · ${steps.length()} steps")

    /** Ends the recording: kept for the Shortcuts page to review, unless cancelled. */
    fun stop(keep: Boolean) {
        bar?.let { runCatching { (service.getSystemService(Context.WINDOW_SERVICE) as WindowManager).removeView(it) } }
        bar = null
        val file = resultFile(service)
        if (keep) {
            file.parentFile?.mkdirs()
            val staging = File(file.parentFile, "${file.name}.tmp")
            staging.writeText(JSONObject().put("app", firstApp ?: JSONObject.NULL).put("steps", steps)
                .put("at", System.currentTimeMillis()).toString())
            staging.renameTo(file)
        }
        finished()
    }

    private fun dp(value: Int): Int = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), service.resources.displayMetrics).toInt()

    private fun showBar() {
        val windows = service.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val row = LinearLayout(service).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(14), dp(6), dp(6), dp(6))
            background = GradientDrawable().apply { cornerRadius = dp(22).toFloat(); setColor(0xEE1F2A28.toInt()) }
            elevation = dp(8).toFloat()
        }
        val dot = View(service).apply { background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(0xFFE5484D.toInt()) } }
        row.addView(dot, LinearLayout.LayoutParams(dp(8), dp(8)).apply { marginEnd = dp(8) })
        val label = TextView(service).apply {
            setTextColor(0xFFFFFFFF.toInt())
            textSize = 13f
            text = recordingText()
        }
        count = label
        row.addView(label)
        fun button(text: String, primary: Boolean, action: () -> Unit) = TextView(service).apply {
            this.text = text
            textSize = 13f
            setTextColor(if (primary) 0xFF0F2A24.toInt() else 0xFFFFFFFF.toInt())
            setPadding(dp(12), dp(6), dp(12), dp(6))
            background = GradientDrawable().apply { cornerRadius = dp(16).toFloat(); setColor(if (primary) 0xFF7FE0C4.toInt() else 0x33FFFFFF) }
            setOnClickListener { action() }
        }
        row.addView(button(UiText.of(service, "取消", "Cancel"), false) { stop(false) },
            LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { marginStart = dp(10) })
        row.addView(button(UiText.of(service, "完成", "Done"), true) { stop(true) },
            LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { marginStart = dp(6) })
        val statusBar = service.resources.getIdentifier("status_bar_height", "dimen", "android")
            .takeIf { it != 0 }?.let { service.resources.getDimensionPixelSize(it) } ?: dp(24)
        val layout = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT,
        ).apply { gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL; y = statusBar + dp(4) }
        // The bar may cover the app's own buttons: a tap on its words moves it to the other edge.
        label.setOnClickListener {
            atTop = !atTop
            layout.gravity = (if (atTop) Gravity.TOP else Gravity.BOTTOM) or Gravity.CENTER_HORIZONTAL
            layout.y = if (atTop) statusBar + dp(4) else dp(72)
            runCatching { windows.updateViewLayout(row, layout) }
        }
        runCatching { windows.addView(row, layout) }.onSuccess { bar = row }
    }
}
