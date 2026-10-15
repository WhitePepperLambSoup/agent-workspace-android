package com.agentworkspace.mobile.entry

import android.animation.TimeInterpolator
import android.animation.ValueAnimator
import android.annotation.SuppressLint
import android.app.Service
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.res.ColorStateList
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager
import android.view.animation.AccelerateInterpolator
import android.view.animation.DecelerateInterpolator
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import com.agentworkspace.mobile.R
import com.agentworkspace.mobile.UiText
import androidx.core.content.ContextCompat
import com.agentworkspace.mobile.automation.AgentAccessibilityService
import com.agentworkspace.mobile.automation.AndroidSystemBridge
import com.agentworkspace.mobile.automation.PhoneControlPanel
import com.agentworkspace.mobile.automation.PhoneControlReceiver
import com.agentworkspace.mobile.embedded.EngineHttp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.hypot
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * A small bubble over other apps. Tap: five actions spring out around it (operate phone, new chat,
 * ask by voice, circle to ask, voice note); tap again or outside to fold them back. Drag to move it; it settles
 * against the nearest side. Dragging shows a target at the bottom: drop the bubble there to hide it.
 * Needs "display over other apps"; the user turns it on in Settings → Global entry.
 */
class FloatingBallService : Service() {
    companion object {
        private const val PREFERENCES = "agent-floating-ball"
        private const val ACCENT = 0xFF0F766E.toInt()
        private const val ACCENT_DARK = 0xFF5CC6B1.toInt()
        private const val IDLE_ALPHA = 0.82f
        // The engine writes JPEG since 1.6.0 (PNG before); a .png-only check sent every circle to ask
        // through the screen capture permission prompt.
        private val SCREENSHOT_PATH = Regex("automation/screenshots/screen-[0-9a-fA-F-]{36}\\.(png|jpg)")
        // Main thread only. Cleared in onDestroy, so it never outlives the service.
        @SuppressLint("StaticFieldLeak")
        private var current: FloatingBallService? = null
        private var hiddenBy = 0

        /**
         * Keeps the bubble out of sight while a screen is being asked about: it would otherwise float
         * over the circle-to-ask screen. Counted, so overlapping callers each undo only their own.
         */
        fun setBallHidden(hidden: Boolean) {
            hiddenBy = (hiddenBy + if (hidden) 1 else -1).coerceAtLeast(0)
            current?.applyVisibility()
        }

        fun isEnabled(context: Context): Boolean =
            context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).getBoolean("enabled", false)

        fun canDraw(context: Context): Boolean = Settings.canDrawOverlays(context)

        /**
         * Turning it on without the overlay permission only records the request; it takes effect when
         * the user comes back having granted it (see [sync]), so a declined permission leaves it off.
         * Returns whether the permission still has to be granted.
         */
        fun setEnabled(context: Context, enabled: Boolean): Boolean {
            val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            val waiting = enabled && !canDraw(context)
            preferences.edit().putBoolean("enabled", enabled && !waiting).putBoolean("pending", waiting).apply()
            sync(context)
            return waiting
        }

        /** Back in the app: a request the user did not grant the permission for is dropped. */
        fun onAppResumed(context: Context) {
            val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            if (preferences.getBoolean("pending", false) && !canDraw(context)) {
                preferences.edit().putBoolean("pending", false).apply()
            }
            sync(context)
        }

        /** Shows or removes the bubble to match the setting and the overlay permission. */
        fun sync(context: Context) {
            val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            if (preferences.getBoolean("pending", false) && canDraw(context)) {
                preferences.edit().putBoolean("enabled", true).putBoolean("pending", false).apply()
            }
            val intent = Intent(context, FloatingBallService::class.java)
            if (isEnabled(context) && canDraw(context)) runCatching { context.startService(intent) }
            else context.stopService(intent)
        }
    }

    /**
     * A damped spring as an interpolator, settled by the end of the animation: [damping] below 1
     * overshoots a little (0.6: about 9 %, 0.85: under 1 %), like the springs of the web UI.
     */
    private class SpringInterpolator(private val damping: Float) : TimeInterpolator {
        private val omega = 6.2f / damping
        private val damped = omega * sqrt(1f - damping * damping)
        override fun getInterpolation(input: Float): Float {
            if (input >= 1f) return 1f
            val decay = exp(-damping * omega * input)
            return 1f - decay * (cos(damped * input) + damping * omega / damped * sin(damped * input))
        }
    }

    private class BubbleAction(val zh: String, val en: String, val icon: Int, val capturesScreen: Boolean = false, val run: () -> Unit)

    /** One action in the open menu: where it sits ([x], [y]) and the offset back to the bubble it flew out of. */
    private class RadialItem(val view: View, val label: View, val action: BubbleAction, val x: Float, val y: Float, val homeX: Float, val homeY: Float)

    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private lateinit var windowManager: WindowManager
    private var ball: FrameLayout? = null
    private lateinit var params: WindowManager.LayoutParams
    private var busy = false
    private val bouncy = SpringInterpolator(0.62f)
    private val gentle = SpringInterpolator(0.85f)
    // The open menu: a full-screen window with a scrim, its own copy of the bubble and the actions.
    private var radial: FrameLayout? = null
    private var radialItems: List<RadialItem> = emptyList()
    private var radialCenter: FrameLayout? = null
    private var radialScrim: View? = null
    private var radialClosing = false
    // While dragging: the target at the bottom that hides the bubble.
    private var target: FrameLayout? = null
    private var targetCircle: View? = null
    private var targetIcon: View? = null
    private var overTarget = false
    private var settleAnimator: ValueAnimator? = null
    // The phone control panel (in :engine) is open; it says when it closes.
    private var hiddenForPanel = false
    private val panelReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            if (intent.action == PhoneControlPanel.ACTION_PANEL_OPENED) {
                // Opened some other way than the bubble's own action: step aside all the same.
                if (!hiddenForPanel) { hiddenForPanel = true; setBallHidden(true) }
            } else panelClosed()
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(WindowManager::class.java)
        if (!canDraw(this)) { stopSelf(); return }
        runCatching { showBall() }.onFailure { stopSelf() }
        current = this
        applyVisibility()
        ContextCompat.registerReceiver(this, panelReceiver, IntentFilter(PhoneControlPanel.ACTION_PANEL_CLOSED).apply {
            addAction(PhoneControlPanel.ACTION_PANEL_OPENED)
        }, ContextCompat.RECEIVER_NOT_EXPORTED)
    }

    private fun applyVisibility() {
        // While the menu is open its own copy of the bubble stands in for this one.
        ball?.visibility = if (busy || hiddenBy > 0 || (radial != null && !radialClosing)) View.INVISIBLE else View.VISIBLE
        if (hiddenBy > 0) closeRadial(instant = true)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!isEnabled(this) || !canDraw(this)) { stopSelf(); return START_NOT_STICKY }
        return START_STICKY
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        closeRadial(instant = true)
        hideTarget(instant = true)
        ball?.let { settle(animate = false) }
    }

    override fun onDestroy() {
        runCatching { unregisterReceiver(panelReceiver) }
        panelClosed()
        if (current === this) current = null
        scope.cancel()
        settleAnimator?.cancel()
        closeRadial(instant = true)
        hideTarget(instant = true)
        ball?.let { runCatching { windowManager.removeView(it) } }
        ball = null
        super.onDestroy()
    }

    private fun dp(value: Int): Int =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), resources.displayMetrics).toInt()

    private fun screenWidth() = resources.displayMetrics.widthPixels
    private fun screenHeight() = resources.displayMetrics.heightPixels

    @SuppressLint("ClickableViewAccessibility")
    private fun showBall() {
        val size = dp(48)
        val preferences = getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
        val view = FrameLayout(this).apply {
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(ACCENT); setStroke(dp(2), 0x33FFFFFF) }
            elevation = dp(6).toFloat()
            alpha = IDLE_ALPHA
            contentDescription = UiText.of(this@FloatingBallService, "问 Agent", "Ask Agent")
            addView(ImageView(this@FloatingBallService).apply { setImageResource(R.drawable.ic_quick_ask) },
                FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER))
            // It sits against the screen edge, where a swipe is the system's back gesture: a drag that
            // starts on the bubble moves the bubble.
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                addOnLayoutChangeListener { v, _, _, _, _, _, _, _, _ -> v.systemGestureExclusionRects = listOf(Rect(0, 0, v.width, v.height)) }
            }
        }
        params = WindowManager.LayoutParams(size, size, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT).apply {
            gravity = Gravity.TOP or Gravity.START
            x = if (preferences.getBoolean("left", false)) 0 else screenWidth() - size
            y = (preferences.getFloat("y", 0.35f) * screenHeight()).toInt()
        }
        val slop = ViewConfiguration.get(this).scaledTouchSlop
        var downX = 0f
        var downY = 0f
        var startX = 0
        var startY = 0
        var dragging = false
        view.setOnTouchListener { _, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downX = event.rawX; downY = event.rawY; startX = params.x; startY = params.y
                    dragging = false
                    settleAnimator?.cancel()
                    view.animate().scaleX(0.88f).scaleY(0.88f).alpha(1f).setInterpolator(DecelerateInterpolator()).setDuration(110).start()
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = event.rawX - downX
                    val dy = event.rawY - downY
                    if (!dragging && hypot(dx, dy) > slop) { dragging = true; showTarget() }
                    if (dragging) follow(startX + dx.toInt(), startY + dy.toInt())
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    val released = event.actionMasked == MotionEvent.ACTION_UP
                    if (dragging && overTarget && released) dropIntoTarget()
                    else {
                        view.animate().scaleX(1f).scaleY(1f).alpha(IDLE_ALPHA).setInterpolator(bouncy).setDuration(420).start()
                        if (dragging) { hideTarget(); settle(animate = true) }
                        else if (released) openRadial()
                    }
                    dragging = false
                }
            }
            true
        }
        windowManager.addView(view, params)
        ball = view
    }

    /** Moves the bubble to the nearest side and keeps it on screen; it springs there with a little give. */
    private fun settle(animate: Boolean) {
        val view = ball ?: return
        settleAnimator?.cancel()
        val size = params.width
        val left = params.x + size / 2 < screenWidth() / 2
        val targetX = if (left) 0 else screenWidth() - size
        val targetY = params.y.coerceIn(dp(24), (screenHeight() - size - dp(24)).coerceAtLeast(dp(24)))
        getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
            .putBoolean("left", left).putFloat("y", targetY.toFloat() / screenHeight().coerceAtLeast(1)).apply()
        if (!animate || (abs(params.x - targetX) < 2 && abs(params.y - targetY) < 2)) {
            params.x = targetX
            params.y = targetY
            runCatching { windowManager.updateViewLayout(view, params) }
            return
        }
        settleAnimator = moveBall(targetX, targetY, 460, gentle)
    }

    private fun moveBall(toX: Int, toY: Int, duration: Long, interpolator: TimeInterpolator): ValueAnimator {
        val view = ball
        val fromX = params.x
        val fromY = params.y
        return ValueAnimator.ofFloat(0f, 1f).apply {
            this.duration = duration
            this.interpolator = interpolator
            addUpdateListener {
                val progress = it.animatedValue as Float
                params.x = fromX + ((toX - fromX) * progress).toInt()
                params.y = fromY + ((toY - fromY) * progress).toInt()
                if (ball != null && view != null) runCatching { windowManager.updateViewLayout(view, params) }
            }
            start()
        }
    }

    private fun open(mode: String) {
        runCatching { startActivity(QuickEntry.intent(this, mode)) }
    }

    /**
     * Operate the phone: the accessibility service opens its panel over the app in front. The bubble
     * stays out of sight (and out of the agent's screenshots and taps) until the panel closes.
     */
    private fun openPhoneControl() {
        android.util.Log.i("PhoneControlPanel", "Bubble: operate the phone (accessibility on: ${accessibilityServiceOn()})")
        if (!accessibilityServiceOn()) {
            Toast.makeText(this, UiText.of(this, "AI 操作手机需要无障碍权限：请在列表里开启 Agent Workspace",
                "Operating the phone needs accessibility: turn on Agent Workspace in the list"), Toast.LENGTH_LONG).show()
            AndroidSystemBridge.openAccessibilitySettings(this)
            return
        }
        if (!hiddenForPanel) { hiddenForPanel = true; setBallHidden(true) }
        runCatching {
            sendBroadcast(Intent(this, PhoneControlReceiver::class.java).setAction(PhoneControlReceiver.ACTION_OPEN))
        }.onFailure {
            android.util.Log.w("PhoneControlPanel", "Could not reach the accessibility service", it)
            panelClosed()
        }
    }

    private fun panelClosed() {
        android.util.Log.i("PhoneControlPanel", "Panel closed; bubble hidden for it: $hiddenForPanel")
        if (hiddenForPanel) { hiddenForPanel = false; setBallHidden(false) }
    }

    private fun dark() = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES

    // ---- The menu: four actions spring out on an arc toward the middle of the screen ------------

    private fun openRadial() {
        if (radial != null || busy || hiddenBy > 0) return
        val ballView = ball ?: return
        val dark = dark()
        val size = params.width
        val root = FrameLayout(this).apply { clipChildren = false; clipToPadding = false }
        val scrim = View(this).apply {
            setBackgroundColor(if (dark) 0x8C000000.toInt() else 0x66000000)
            alpha = 0f
            setOnClickListener { closeRadial() }
        }
        root.addView(scrim, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        val actions = listOf(
            BubbleAction("操作手机", "Operate phone", R.drawable.ic_bubble_control) { openPhoneControl() },
            BubbleAction("新对话", "New chat", R.drawable.ic_bubble_new) { open("text") },
            BubbleAction("语音提问", "Ask by voice", R.drawable.ic_bubble_mic) { open("voice") },
            BubbleAction("圈选提问", "Circle to ask", R.drawable.ic_bubble_scan, capturesScreen = true) { askAboutScreen() },
            BubbleAction("录音速记", "Voice note", R.drawable.ic_bubble_note) { runCatching { startActivity(QuickEntry.voiceNoteActivity(this)) } },
        )
        val circle = dp(52)
        val views = actions.map { action ->
            val label = TextView(this).apply {
                text = UiText.of(this@FloatingBallService, action.zh, action.en)
                textSize = 13.5f
                setTextColor(if (dark) Color.WHITE else 0xFF18201E.toInt())
                background = GradientDrawable().apply { cornerRadius = dp(14).toFloat(); setColor(if (dark) 0xF0222A28.toInt() else 0xF5FFFFFF.toInt()) }
                elevation = dp(4).toFloat()
                setPadding(dp(12), dp(6), dp(12), dp(6))
                importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            }
            val button = FrameLayout(this).apply {
                background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(if (dark) 0xFF26302E.toInt() else Color.WHITE) }
                elevation = dp(8).toFloat()
                addView(ImageView(this@FloatingBallService).apply {
                    setImageResource(action.icon)
                    imageTintList = ColorStateList.valueOf(if (dark) ACCENT_DARK else ACCENT)
                }, FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER))
            }
            val item = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                clipChildren = false
                contentDescription = label.text
                isClickable = true
                isFocusable = true
                setOnClickListener { chooseRadial(this) }
            }
            Triple(item, label, button)
        }
        val center = FrameLayout(this).apply {
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(ACCENT); setStroke(dp(2), 0x33FFFFFF) }
            elevation = dp(10).toFloat()
            contentDescription = UiText.of(this@FloatingBallService, "关闭", "Close")
            setOnClickListener { closeRadial() }
            addView(ImageView(this@FloatingBallService).apply { setImageResource(R.drawable.ic_quick_ask); tag = "sparkle" },
                FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER))
            addView(ImageView(this@FloatingBallService).apply {
                setImageResource(R.drawable.ic_bubble_close); tag = "close"; alpha = 0f; rotation = -90f; scaleX = 0.5f; scaleY = 0.5f
            }, FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER))
        }
        for ((item, _, _) in views) root.addView(item, FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT))
        root.addView(center, FrameLayout.LayoutParams(size, size))
        center.alpha = 0f
        val layout = WindowManager.LayoutParams(WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT).apply {
            gravity = Gravity.TOP or Gravity.START
            // The scrim covers the status and navigation bars too, not just the area between them.
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) fitInsetsTypes = 0
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
            }
        }
        if (runCatching { windowManager.addView(root, layout) }.isFailure) return
        radial = root
        radialScrim = scrim
        radialCenter = center
        radialClosing = false
        // Positions are known once the window is laid out: the bubble's place on screen, the window's.
        root.addOnLayoutChangeListener(object : View.OnLayoutChangeListener {
            override fun onLayoutChange(v: View, left: Int, top: Int, right: Int, bottom: Int,
                                        oldLeft: Int, oldTop: Int, oldRight: Int, oldBottom: Int) {
                root.removeOnLayoutChangeListener(this)
                if (radial !== root) return
                val ballAt = IntArray(2).also { ballView.getLocationOnScreen(it) }
                val rootAt = IntArray(2).also { root.getLocationOnScreen(it) }
                val cx = ballAt[0] - rootAt[0] + size / 2f
                val cy = ballAt[1] - rootAt[1] + size / 2f
                // Children sit at the window's top left; translations place them.
                center.translationX = cx - size / 2f
                center.translationY = cy - size / 2f
                center.alpha = 1f
                applyVisibility()
                val onLeft = cx < root.width / 2f
                // Fan toward the middle of the screen; near the top or bottom edge, turn it away from the edge.
                // Five actions need a wider arc than four to keep their circles apart.
                val radius = dp(if (views.size > 4) 136 else 112).toFloat()
                val step = if (views.size > 4) 32.0 else 40.0
                val first = step * (views.size - 1) / 2
                val room = radius + dp(44)
                var middle = if (onLeft) 0.0 else 180.0
                if (cy < room) middle += if (onLeft) 52.0 else -52.0
                else if (root.height - cy < room) middle += if (onLeft) -52.0 else 52.0
                radialItems = views.mapIndexed { index, (item, label, button) ->
                    item.removeAllViews()
                    if (onLeft) { item.addView(button, LinearLayout.LayoutParams(circle, circle)); item.addView(label, gap(onLeft)) }
                    else { item.addView(label, gap(onLeft)); item.addView(button, LinearLayout.LayoutParams(circle, circle)) }
                    item.measure(View.MeasureSpec.UNSPECIFIED, View.MeasureSpec.UNSPECIFIED)
                    // Top to bottom in list order, [step] degrees apart.
                    val angle = Math.toRadians(if (onLeft) middle - first + step * index else middle + first - step * index)
                    val px = cx + (radius * cos(angle)).toFloat()
                    val py = cy + (radius * sin(angle)).toFloat()
                    val circleX = if (onLeft) circle / 2f else item.measuredWidth - circle / 2f
                    item.pivotX = circleX
                    item.pivotY = item.measuredHeight / 2f
                    RadialItem(item, label, actions[index], px - circleX, py - item.measuredHeight / 2f, cx - px, cy - py)
                }
                animateRadialOpen(onLeft)
            }
        })
        ballView.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
    }

    private fun gap(left: Boolean) = LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
        if (left) marginStart = dp(10) else marginEnd = dp(10)
    }

    private fun animateRadialOpen(left: Boolean) {
        radialScrim?.animate()?.alpha(1f)?.setDuration(240)?.setInterpolator(DecelerateInterpolator())?.start()
        radialCenter?.let { center ->
            center.scaleX = 0.86f; center.scaleY = 0.86f
            center.animate().scaleX(1f).scaleY(1f).setInterpolator(bouncy).setDuration(460).start()
            center.findViewWithTag<View>("sparkle")?.animate()?.rotation(90f)?.alpha(0f)?.scaleX(0.5f)?.scaleY(0.5f)?.setDuration(200)?.start()
            center.findViewWithTag<View>("close")?.animate()?.rotation(0f)?.alpha(1f)?.scaleX(1f)?.scaleY(1f)
                ?.setInterpolator(bouncy)?.setDuration(460)?.start()
        }
        radialItems.forEachIndexed { index, item ->
            item.view.apply {
                alpha = 0f; scaleX = 0.3f; scaleY = 0.3f; translationX = item.x + item.homeX; translationY = item.y + item.homeY
                animate().translationX(item.x).translationY(item.y).scaleX(1f).scaleY(1f).alpha(1f)
                    .setStartDelay(index * 32L).setDuration(480).setInterpolator(bouncy).start()
            }
            item.label.apply {
                alpha = 0f; translationX = dp(if (left) -10 else 10).toFloat()
                animate().alpha(1f).translationX(0f).setStartDelay(120 + index * 32L).setDuration(260)
                    .setInterpolator(DecelerateInterpolator()).start()
            }
        }
    }

    /** The chosen action swells and fades while the others fold back; then the menu goes and the action runs. */
    private fun chooseRadial(chosen: View) {
        if (radialClosing) return
        val action = radialItems.firstOrNull { it.view === chosen }?.action ?: return
        chosen.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
        // Circle to ask captures the screen, so it waits until the menu is gone; the rest open at once.
        closeRadial(chosen = chosen, after = if (action.capturesScreen) action.run else null)
        if (!action.capturesScreen) action.run()
    }

    private fun closeRadial(instant: Boolean = false, chosen: View? = null, after: (() -> Unit)? = null) {
        val root = radial ?: return
        if (instant) {
            root.animate().cancel()
            runCatching { windowManager.removeView(root) }
            radial = null; radialItems = emptyList(); radialCenter = null; radialScrim = null; radialClosing = false
            applyVisibility()
            return
        }
        if (radialClosing) return
        radialClosing = true
        val count = radialItems.size
        radialItems.forEachIndexed { index, item ->
            item.view.animate().cancel()
            item.label.animate().cancel()
            if (item.view === chosen) {
                item.view.animate().scaleX(1.18f).scaleY(1.18f).alpha(0f).setStartDelay(0).setDuration(200)
                    .setInterpolator(DecelerateInterpolator()).start()
            } else {
                item.view.animate().translationX(item.x + item.homeX).translationY(item.y + item.homeY).scaleX(0.3f).scaleY(0.3f).alpha(0f)
                    .setStartDelay((count - 1 - index) * 18L).setDuration(190).setInterpolator(AccelerateInterpolator(1.3f)).start()
            }
        }
        radialCenter?.let { center ->
            center.findViewWithTag<View>("close")?.animate()?.rotation(-90f)?.alpha(0f)?.scaleX(0.5f)?.scaleY(0.5f)
                ?.setInterpolator(AccelerateInterpolator())?.setDuration(160)?.start()
            center.findViewWithTag<View>("sparkle")?.animate()?.rotation(0f)?.alpha(1f)?.scaleX(1f)?.scaleY(1f)
                ?.setInterpolator(DecelerateInterpolator())?.setDuration(220)?.start()
        }
        val scrim = radialScrim
        val finish = Runnable {
            if (radial !== root) return@Runnable
            runCatching { windowManager.removeView(root) }
            radial = null; radialItems = emptyList(); radialCenter = null; radialScrim = null; radialClosing = false
            applyVisibility()
            after?.invoke()
        }
        if (scrim != null) scrim.animate().alpha(0f).setStartDelay(40).setDuration(200).withEndAction(finish).start()
        else finish.run()
    }

    // ---- Drag to hide: a target rises from the bottom while the bubble is dragged ---------------

    // Same frame as the bubble's own window position, clear of the gesture bar.
    private fun targetCenter(): Pair<Int, Int> = screenWidth() / 2 to screenHeight() - dp(150)

    private fun showTarget() {
        if (target != null) return
        val box = dp(120)
        val circle = View(this).apply {
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(0xCC1F2725.toInt()); setStroke(dp(1), 0x40FFFFFF) }
            elevation = dp(6).toFloat()
        }
        val icon = ImageView(this).apply { setImageResource(R.drawable.ic_bubble_close); elevation = dp(7).toFloat() }
        val frame = FrameLayout(this).apply {
            clipChildren = false
            addView(circle, FrameLayout.LayoutParams(dp(60), dp(60), Gravity.CENTER))
            addView(icon, FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER))
            contentDescription = UiText.of(this@FloatingBallService, "拖到这里隐藏悬浮球", "Drop here to hide the bubble")
        }
        val (centerX, centerY) = targetCenter()
        val layout = WindowManager.LayoutParams(box, box, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT).apply {
            gravity = Gravity.TOP or Gravity.START
            x = centerX - box / 2
            y = centerY - box / 2
        }
        if (runCatching { windowManager.addView(frame, layout) }.isFailure) return
        target = frame
        targetCircle = circle
        targetIcon = icon
        overTarget = false
        frame.alpha = 0f
        frame.translationY = dp(60).toFloat()
        frame.animate().alpha(1f).translationY(0f).setInterpolator(bouncy).setDuration(420).start()
    }

    private fun hideTarget(instant: Boolean = false) {
        val frame = target ?: return
        target = null
        targetCircle = null
        targetIcon = null
        overTarget = false
        if (instant) { runCatching { windowManager.removeView(frame) }; return }
        frame.animate().alpha(0f).translationY(dp(60).toFloat()).setInterpolator(AccelerateInterpolator()).setDuration(180)
            .withEndAction { runCatching { windowManager.removeView(frame) } }.start()
    }

    /**
     * Follows the finger; near the target the bubble snaps into it, and the target grows into a red ring
     * (its window lies above the bubble's, so it must stay see-through) while the bubble shrinks a little.
     */
    private fun follow(x: Int, y: Int) {
        val view = ball ?: return
        val size = params.width
        val (centerX, centerY) = targetCenter()
        val near = target != null && hypot((x + size / 2 - centerX).toFloat(), (y + size / 2 - centerY).toFloat()) <
            dp(if (overTarget) 96 else 72)
        if (near != overTarget) {
            overTarget = near
            targetCircle?.let { circle ->
                (circle.background as? GradientDrawable)?.apply {
                    setColor(if (near) 0x47DC2626 else 0xCC1F2725.toInt())
                    setStroke(dp(if (near) 3 else 1), if (near) 0xFFEF4444.toInt() else 0x40FFFFFF)
                }
                circle.animate().scaleX(if (near) 1.35f else 1f).scaleY(if (near) 1.35f else 1f).setInterpolator(bouncy).setDuration(360).start()
            }
            targetIcon?.animate()?.alpha(if (near) 0f else 1f)?.setDuration(140)?.start()
            view.animate().scaleX(if (near) 0.8f else 0.88f).scaleY(if (near) 0.8f else 0.88f).setInterpolator(bouncy).setDuration(360).start()
            view.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK)
            settleAnimator?.cancel()
            if (near) { settleAnimator = moveBall(centerX - size / 2, centerY - size / 2, 220, gentle); return }
        }
        if (near) return
        params.x = x
        params.y = y
        runCatching { windowManager.updateViewLayout(view, params) }
    }

    /** Dropped on the target: the bubble shrinks into it, then the setting turns off. */
    private fun dropIntoTarget() {
        val view = ball ?: return
        targetCircle?.animate()?.scaleX(1.5f)?.scaleY(1.5f)?.alpha(0f)?.setDuration(240)?.start()
        view.animate().scaleX(0f).scaleY(0f).alpha(0f).setInterpolator(AccelerateInterpolator()).setDuration(220).withEndAction {
            hideTarget(instant = true)
            setEnabled(this, false)
            Toast.makeText(this, UiText.of(this, "悬浮球已隐藏，可在设置 → 全局入口里重新打开",
                "Bubble hidden; turn it back on in Settings → Global entry"), Toast.LENGTH_LONG).show()
        }.start()
    }

    /**
     * Circle to ask. With the accessibility service on, it takes the screenshot without asking;
     * otherwise the circle-to-ask screen asks Android for screen capture permission each time.
     */
    private fun askAboutScreen() {
        if (busy) return
        if (!accessibilityServiceOn()) { openScreenAsk(null); return }
        busy = true
        applyVisibility()
        scope.launch {
            var opened = false
            try {
                delay(350) // let the bubble and its menu leave the frame
                when (val shot = withContext(Dispatchers.IO) { captureScreen() }) {
                    is Shot.Taken -> { openScreenAsk(shot.file); opened = true }
                    // Accessibility is on but can't capture here (Android 10, or the service not
                    // connected yet): the screen capture permission still can.
                    Shot.Unavailable -> { openScreenAsk(null); opened = true }
                }
            } catch (failure: Exception) {
                Toast.makeText(this@FloatingBallService, failure.message ?: UiText.of(this@FloatingBallService,
                    "无法截屏", "Could not take a screenshot"), Toast.LENGTH_LONG).show()
            } finally {
                // The circle-to-ask screen hides the bubble itself once it is up.
                if (opened) delay(1500)
                busy = false
                applyVisibility()
            }
        }
    }

    private fun openScreenAsk(screenshot: File?) {
        closeRadial(instant = true)
        runCatching { startActivity(ScreenAskActivity.intent(this, screenshot)) }
            .onFailure { screenshot?.delete() }
    }

    private fun accessibilityServiceOn(): Boolean {
        val enabled = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES) ?: return false
        val service = ComponentName(this, AgentAccessibilityService::class.java)
        return enabled.split(':').any { ComponentName.unflattenFromString(it) == service }
    }

    private sealed interface Shot {
        data class Taken(val file: File) : Shot
        data object Unavailable : Shot
    }

    private fun captureScreen(): Shot {
        repeat(3) { attempt ->
            val reply = try {
                // A clean picture: the numbered control marks are for the model, not for circling.
                EngineHttp.request(this, "POST", "/mobile/android-system", JSONObject().put("action", "screenshot").put("marks", false), 20000)
            } catch (_: Exception) {
                return Shot.Unavailable
            }
            val shot = reply.body.optJSONObject("screenshot")
            val path = shot?.optString("path").orEmpty()
            if (reply.ok && shot != null && SCREENSHOT_PATH.matches(path)) {
                val source = File(filesDir, "workspace/$path")
                val target = File(ScreenCaptureService.folder(this), "screen-${System.currentTimeMillis()}.${path.substringAfterLast('.')}")
                source.copyTo(target, overwrite = true)
                return Shot.Taken(target)
            }
            when (reply.body.optJSONObject("error")?.optString("code").orEmpty()) {
                // A password field on screen: the screen capture permission would show it too.
                "protected_content" -> throw IllegalStateException(UiText.of(this,
                    "屏幕上有密码等敏感内容，不能截屏", "Sensitive content such as a password is on screen; it can't be captured"))
                // Windows still opening or closing (the bubble's menu going away): take it again.
                "stale_snapshot", "screen_unsettled" -> if (attempt < 2) Thread.sleep(300) else return Shot.Unavailable
                // Accessibility can't capture here; the screen capture permission still may.
                else -> return Shot.Unavailable
            }
        }
        return Shot.Unavailable
    }
}
