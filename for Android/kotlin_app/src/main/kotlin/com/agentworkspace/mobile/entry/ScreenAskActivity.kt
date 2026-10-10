package com.agentworkspace.mobile.entry

import android.annotation.SuppressLint
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.drawable.GradientDrawable
import android.media.projection.MediaProjectionConfig
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.ResultReceiver
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.FileProvider
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.sharing.ShareInboxController
import java.io.File
import java.util.UUID
import kotlin.concurrent.thread

/**
 * Circle to ask: the screen, frozen as a screenshot, under a layer where the user circles what they
 * want to ask about. The circled part (or the whole screen) goes to the attachment inbox and a new
 * conversation opens with it attached. The screenshot comes from the accessibility service when
 * the floating bubble could take one ([EXTRA_SCREENSHOT]); otherwise this asks Android for screen
 * capture permission and takes it through [ScreenCaptureService].
 */
class ScreenAskActivity : Activity() {
    companion object {
        const val EXTRA_SCREENSHOT = "screenshot_path"
        private const val REQUEST_CAPTURE = 41

        /** Opens over the current app in its own task, so the app's own window stays out of the way. */
        fun intent(context: Context, screenshot: File? = null): Intent =
            Intent(context, ScreenAskActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK or Intent.FLAG_ACTIVITY_NO_ANIMATION)
                .apply { if (screenshot != null) putExtra(EXTRA_SCREENSHOT, screenshot.absolutePath) }
    }

    private var screenshot: File? = null
    private var image: Bitmap? = null
    private var selection: SelectionView? = null
    private var askButton: TextView? = null
    private var sending = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        FloatingBallService.setBallHidden(true)
        // Earlier screenshots left behind by a crash or a killed process.
        ScreenCaptureService.folder(this).listFiles()?.forEach { if (System.currentTimeMillis() - it.lastModified() > 600_000) it.delete() }
        val given = intent.getStringExtra(EXTRA_SCREENSHOT)?.let(::File)
        when {
            given != null && given.parentFile?.canonicalPath == ScreenCaptureService.folder(this).canonicalPath -> show(given)
            savedInstanceState == null -> requestCapture()
            else -> finish()
        }
    }

    override fun onDestroy() {
        if (!sending) screenshot?.delete()
        image?.recycle()
        FloatingBallService.setBallHidden(false)
        super.onDestroy()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() = finish()

    private fun dp(value: Int): Int =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), resources.displayMetrics).toInt()

    private fun requestCapture() {
        val manager = getSystemService(MediaProjectionManager::class.java)
        // The whole screen: Android 14+ would otherwise also offer recording a single app.
        val request = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            manager.createScreenCaptureIntent(MediaProjectionConfig.createConfigForDefaultDisplay())
        } else {
            manager.createScreenCaptureIntent()
        }
        try {
            @Suppress("DEPRECATION")
            startActivityForResult(request, REQUEST_CAPTURE)
        } catch (_: ActivityNotFoundException) {
            fail(UiText.of(this, "这台手机不支持截取屏幕", "This phone does not support screen capture"))
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_CAPTURE) return
        if (resultCode != RESULT_OK || data == null) { finish(); return }
        val receiver = object : ResultReceiver(Handler(Looper.getMainLooper())) {
            override fun onReceiveResult(code: Int, result: Bundle?) {
                if (isFinishing || isDestroyed) {
                    result?.getString(ScreenCaptureService.KEY_PATH)?.let { File(it).delete() }
                    return
                }
                val path = result?.getString(ScreenCaptureService.KEY_PATH)
                if (code == ScreenCaptureService.RESULT_OK && path != null) show(File(path))
                else fail(UiText.of(this@ScreenAskActivity, "无法截取屏幕：", "Could not capture the screen: ") +
                    (result?.getString(ScreenCaptureService.KEY_MESSAGE) ?: ""))
            }
        }
        try {
            ScreenCaptureService.start(this, resultCode, data, receiver)
        } catch (failure: Exception) {
            fail(UiText.of(this, "无法截取屏幕：", "Could not capture the screen: ") + (failure.message ?: ""))
        }
    }

    private fun fail(message: String) {
        Toast.makeText(this, message.trim(), Toast.LENGTH_LONG).show()
        finish()
    }

    /** Shows the screenshot edge to edge, the way the screen looked, with the selection layer. */
    private fun show(file: File) {
        val bitmap = BitmapFactory.decodeFile(file.absolutePath)
        if (bitmap == null) { file.delete(); fail(UiText.of(this, "截图无法读取", "The screenshot could not be read")); return }
        screenshot = file
        image = bitmap
        val root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        val view = SelectionView(this, bitmap) { selected -> askButton?.isEnabled = selected; askButton?.alpha = if (selected) 1f else 0.45f }
        selection = view
        root.addView(view, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        root.addView(pill(UiText.of(this, "圈出想问的部分", "Circle what you want to ask about"), primary = false).apply { isClickable = false },
            FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.TOP or Gravity.CENTER_HORIZONTAL).apply { topMargin = dp(40) })
        val bar = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
        fun add(button: TextView) = bar.addView(button, LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT,
            LinearLayout.LayoutParams.WRAP_CONTENT).apply { marginStart = dp(6); marginEnd = dp(6) })
        add(pill(UiText.of(this, "取消", "Cancel"), primary = false).apply { setOnClickListener { finish() } })
        add(pill(UiText.of(this, "整屏提问", "Ask about the whole screen"), primary = false).apply { setOnClickListener { send(null) } })
        askButton = pill(UiText.of(this, "提问", "Ask"), primary = true).apply {
            isEnabled = false; alpha = 0.45f
            setOnClickListener { selection?.region?.let { send(it) } }
        }
        add(askButton!!)
        root.addView(bar, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT,
            Gravity.BOTTOM).apply { bottomMargin = dp(36) })
        setContentView(root)
        // After setContentView: before it the window has no decor view to hide the bars of.
        fullScreen()
    }

    private fun fullScreen() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            window.attributes = window.attributes.apply {
                layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
            }
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.setDecorFitsSystemWindows(false)
            window.insetsController?.let {
                it.hide(WindowInsets.Type.systemBars())
                it.systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        } else {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        }
    }

    private fun pill(text: String, primary: Boolean) = TextView(this).apply {
        this.text = text
        textSize = 15f
        setTextColor(Color.WHITE)
        gravity = Gravity.CENTER
        setPadding(dp(18), dp(11), dp(18), dp(11))
        background = GradientDrawable().apply {
            cornerRadius = dp(22).toFloat()
            setColor(if (primary) 0xFF0F766E.toInt() else 0xCC1F2725.toInt())
            setStroke(1, 0x33FFFFFF)
        }
        elevation = dp(4).toFloat()
    }

    /** The circled part, or the whole screen for null, into the inbox; then a new conversation. */
    private fun send(region: ScreenRegion?) {
        val source = screenshot ?: return
        val bitmap = image ?: return
        if (sending) return
        sending = true
        thread(name = "agent-screen-ask") {
            val result = runCatching {
                val folder = File(cacheDir, "camera").apply { mkdirs() }
                val target = File(folder, "screen-${System.currentTimeMillis()}.png")
                if (region == null) {
                    source.copyTo(target, overwrite = true)
                } else {
                    val part = Bitmap.createBitmap(bitmap, region.left, region.top, region.width, region.height)
                    try { target.outputStream().use { part.compress(Bitmap.CompressFormat.PNG, 100, it) } } finally { if (part !== bitmap) part.recycle() }
                }
                target
            }
            runOnUiThread {
                source.delete()
                result.onSuccess { target ->
                    val batch = UUID.randomUUID().toString()
                    ShareInboxController.get(this).captureFiles(listOf(FileProvider.getUriForFile(this, "$packageName.camera", target)), batch)
                    startActivity(QuickEntry.intent(this, "screen", batch))
                    finish()
                }.onFailure {
                    sending = false
                    fail(UiText.of(this, "无法保存截图：", "Could not save the screenshot: ") + (it.message ?: ""))
                }
            }
        }
    }

    /** The screenshot, fitted to the screen, with the stroke being drawn and the part it selected. */
    @SuppressLint("ViewConstructor")
    private class SelectionView(context: Context, private val bitmap: Bitmap, private val onSelected: (Boolean) -> Unit) : View(context) {
        var region: ScreenRegion? = null
            private set
        private val density = resources.displayMetrics.density
        private val xs = ArrayList<Float>()
        private val ys = ArrayList<Float>()
        private val stroke = Path()
        private var drawing = false
        private val imagePaint = Paint(Paint.FILTER_BITMAP_FLAG)
        private val shade = Paint().apply { color = 0x99000000.toInt() }
        private val glow = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND; strokeJoin = Paint.Join.ROUND
            strokeWidth = 10 * density; color = 0x5514B8A6
        }
        private val line = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND; strokeJoin = Paint.Join.ROUND
            strokeWidth = 3.5f * density; color = Color.WHITE
        }
        private val frame = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE; strokeWidth = 2.5f * density; color = 0xFF2DD4BF.toInt()
        }
        private val box = RectF()

        private fun fit() = ScreenSelection.fit(bitmap.width, bitmap.height, width, height)

        @SuppressLint("ClickableViewAccessibility")
        override fun onTouchEvent(event: MotionEvent): Boolean {
            val fit = fit()
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    xs.clear(); ys.clear(); stroke.reset(); region = null; drawing = true
                    stroke.moveTo(event.x, event.y)
                    onSelected(false)
                }
                MotionEvent.ACTION_MOVE -> {
                    for (index in 0 until event.historySize) stroke.lineTo(event.getHistoricalX(index), event.getHistoricalY(index))
                    stroke.lineTo(event.x, event.y)
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> drawing = false
            }
            for (index in 0 until event.historySize) { xs.add(fit.toImageX(event.getHistoricalX(index))); ys.add(fit.toImageY(event.getHistoricalY(index))) }
            xs.add(fit.toImageX(event.x)); ys.add(fit.toImageY(event.y))
            if (!drawing) {
                val pixels = 1f / fit.scale
                region = ScreenSelection.region(xs.toFloatArray(), ys.toFloatArray(), bitmap.width, bitmap.height,
                    padding = (16 * density * pixels).toInt(), minimum = (96 * density * pixels).toInt(), tapSlop = (12 * density * pixels).toInt())
                if (region == null) stroke.reset()
                onSelected(region != null)
            }
            invalidate()
            return true
        }

        override fun onDraw(canvas: Canvas) {
            val fit = fit()
            canvas.save()
            canvas.translate(fit.dx, fit.dy)
            canvas.scale(fit.scale, fit.scale)
            canvas.drawBitmap(bitmap, 0f, 0f, imagePaint)
            canvas.restore()
            val selected = region
            if (selected != null && !drawing) {
                box.set(fit.toViewX(selected.left.toFloat()), fit.toViewY(selected.top.toFloat()),
                    fit.toViewX(selected.right.toFloat()), fit.toViewY(selected.bottom.toFloat()))
                // Dim everything but the selected part.
                canvas.drawRect(0f, 0f, width.toFloat(), box.top, shade)
                canvas.drawRect(0f, box.bottom, width.toFloat(), height.toFloat(), shade)
                canvas.drawRect(0f, box.top, box.left, box.bottom, shade)
                canvas.drawRect(box.right, box.top, width.toFloat(), box.bottom, shade)
                canvas.drawRoundRect(box, 6 * density, 6 * density, frame)
            }
            if (drawing || selected != null) {
                canvas.drawPath(stroke, glow)
                canvas.drawPath(stroke, line)
            }
        }
    }
}
