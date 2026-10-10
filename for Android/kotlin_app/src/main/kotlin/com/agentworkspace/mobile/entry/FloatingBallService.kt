package com.agentworkspace.mobile.entry

import android.animation.ValueAnimator
import android.annotation.SuppressLint
import android.app.Service
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.IBinder
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import com.agentworkspace.mobile.R
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.automation.AgentAccessibilityService
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
import kotlin.math.hypot

/**
 * A small bubble over other apps. Tap: new conversation. Long press: circle to ask about the screen,
 * ask by voice, or hide the bubble. Drag to move it; it settles against the nearest side.
 * Needs "display over other apps"; the user turns it on in Settings → Global entry.
 */
class FloatingBallService : Service() {
    companion object {
        private const val PREFERENCES = "agent-floating-ball"
        private const val ACCENT = 0xFF0F766E.toInt()
        private val SCREENSHOT_PATH = Regex("automation/screenshots/screen-[0-9a-fA-F-]{36}\\.png")
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

    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private lateinit var windowManager: WindowManager
    private var ball: FrameLayout? = null
    private var menu: View? = null
    private lateinit var params: WindowManager.LayoutParams
    private var busy = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(WindowManager::class.java)
        if (!canDraw(this)) { stopSelf(); return }
        runCatching { showBall() }.onFailure { stopSelf() }
        current = this
        applyVisibility()
    }

    private fun applyVisibility() {
        ball?.visibility = if (busy || hiddenBy > 0) View.INVISIBLE else View.VISIBLE
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!isEnabled(this) || !canDraw(this)) { stopSelf(); return START_NOT_STICKY }
        return START_STICKY
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        hideMenu()
        ball?.let { settle(animate = false) }
    }

    override fun onDestroy() {
        if (current === this) current = null
        scope.cancel()
        hideMenu()
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
            alpha = 0.82f
            contentDescription = UiText.of(this@FloatingBallService, "问 Agent", "Ask Agent")
            addView(ImageView(this@FloatingBallService).apply { setImageResource(R.drawable.ic_quick_ask) },
                FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER))
        }
        params = WindowManager.LayoutParams(size, size, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT).apply {
            gravity = Gravity.TOP or Gravity.START
            x = if (preferences.getBoolean("left", false)) 0 else screenWidth() - size
            y = (preferences.getFloat("y", 0.35f) * screenHeight()).toInt()
        }
        val slop = ViewConfiguration.get(this).scaledTouchSlop
        val longPress = ViewConfiguration.getLongPressTimeout().toLong()
        var downX = 0f
        var downY = 0f
        var startX = 0
        var startY = 0
        var dragging = false
        var pressed = false
        val showMenuLater = Runnable { if (pressed && !dragging) { pressed = false; showMenu() } }
        view.setOnTouchListener { _, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downX = event.rawX; downY = event.rawY; startX = params.x; startY = params.y
                    dragging = false; pressed = true
                    view.alpha = 1f
                    view.postDelayed(showMenuLater, longPress)
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = event.rawX - downX
                    val dy = event.rawY - downY
                    if (!dragging && hypot(dx, dy) > slop) { dragging = true; view.removeCallbacks(showMenuLater); hideMenu() }
                    if (dragging) {
                        params.x = (startX + dx).toInt()
                        params.y = (startY + dy).toInt()
                        runCatching { windowManager.updateViewLayout(view, params) }
                    }
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    view.removeCallbacks(showMenuLater)
                    view.alpha = 0.82f
                    if (dragging) settle(animate = true)
                    else if (pressed && event.actionMasked == MotionEvent.ACTION_UP) open("text")
                    pressed = false
                    dragging = false
                }
            }
            true
        }
        windowManager.addView(view, params)
        ball = view
    }

    /** Moves the bubble to the nearest side and keeps it on screen. */
    private fun settle(animate: Boolean) {
        val view = ball ?: return
        val size = params.width
        val left = params.x + size / 2 < screenWidth() / 2
        val targetX = if (left) 0 else screenWidth() - size
        params.y = params.y.coerceIn(dp(24), (screenHeight() - size - dp(24)).coerceAtLeast(dp(24)))
        getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
            .putBoolean("left", left).putFloat("y", params.y.toFloat() / screenHeight().coerceAtLeast(1)).apply()
        if (!animate || abs(params.x - targetX) < 2) {
            params.x = targetX
            runCatching { windowManager.updateViewLayout(view, params) }
            return
        }
        ValueAnimator.ofInt(params.x, targetX).apply {
            duration = 180
            addUpdateListener {
                params.x = it.animatedValue as Int
                if (ball != null) runCatching { windowManager.updateViewLayout(view, params) }
            }
            start()
        }
    }

    private fun open(mode: String) {
        hideMenu()
        runCatching { startActivity(QuickEntry.intent(this, mode)) }
    }

    private fun showMenu() {
        hideMenu()
        val dark = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply {
                cornerRadius = dp(14).toFloat()
                setColor(if (dark) 0xFF1F2725.toInt() else Color.WHITE)
                setStroke(1, if (dark) 0x33FFFFFF else 0x22000000)
            }
            elevation = dp(8).toFloat()
            setPadding(0, dp(6), 0, dp(6))
        }
        fun item(zh: String, en: String, action: () -> Unit) = panel.addView(TextView(this).apply {
            text = UiText.of(this@FloatingBallService, zh, en)
            textSize = 15f
            setTextColor(if (dark) Color.WHITE else 0xFF18201E.toInt())
            setPadding(dp(18), dp(12), dp(18), dp(12))
            setOnClickListener { hideMenu(); action() }
        })
        item("圈选提问", "Circle to ask") { askAboutScreen() }
        item("语音提问", "Ask by voice") { open("voice") }
        item("新对话", "New chat") { open("text") }
        item("隐藏悬浮球", "Hide the bubble") {
            setEnabled(this, false)
            Toast.makeText(this, UiText.of(this, "悬浮球已隐藏，可在设置 → 全局入口里重新打开",
                "Bubble hidden; turn it back on in Settings → Global entry"), Toast.LENGTH_LONG).show()
        }
        panel.setOnTouchListener { _, event ->
            if (event.actionMasked == MotionEvent.ACTION_OUTSIDE) hideMenu()
            false
        }
        panel.measure(View.MeasureSpec.UNSPECIFIED, View.MeasureSpec.UNSPECIFIED)
        val left = params.x + params.width / 2 < screenWidth() / 2
        val layout = WindowManager.LayoutParams(WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH,
            PixelFormat.TRANSLUCENT).apply {
            gravity = Gravity.TOP or Gravity.START
            x = if (left) params.width + dp(8) else (screenWidth() - params.width - dp(8) - panel.measuredWidth).coerceAtLeast(0)
            y = params.y.coerceAtMost((screenHeight() - panel.measuredHeight - dp(24)).coerceAtLeast(0))
        }
        runCatching { windowManager.addView(panel, layout); menu = panel }
    }

    private fun hideMenu() {
        menu?.let { runCatching { windowManager.removeView(it) } }
        menu = null
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
        hideMenu()
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
                EngineHttp.request(this, "POST", "/mobile/android-system", JSONObject().put("action", "screenshot"), 20000)
            } catch (_: Exception) {
                return Shot.Unavailable
            }
            val shot = reply.body.optJSONObject("screenshot")
            val path = shot?.optString("path").orEmpty()
            if (reply.ok && shot != null && SCREENSHOT_PATH.matches(path)) {
                val source = File(filesDir, "workspace/$path")
                val target = File(ScreenCaptureService.folder(this), "screen-${System.currentTimeMillis()}.png")
                source.copyTo(target, overwrite = true)
                return Shot.Taken(target)
            }
            when (reply.body.optJSONObject("error")?.optString("code").orEmpty()) {
                // A password field on screen: the screen capture permission would show it too.
                "protected_content" -> throw IllegalStateException(UiText.of(this,
                    "屏幕上有密码等敏感内容，不能截屏", "Sensitive content such as a password is on screen; it can't be captured"))
                // The automation check that the screen held still, tripped by the bubble's menu
                // closing or an animation: take it again.
                "stale_snapshot" -> if (attempt < 2) Thread.sleep(300) else return Shot.Unavailable
                // Accessibility can't capture here; the screen capture permission still may.
                else -> return Shot.Unavailable
            }
        }
        return Shot.Unavailable
    }
}
