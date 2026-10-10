package com.agentworkspace.mobile.voice

import android.app.Activity
import android.app.Dialog
import android.content.Context
import android.content.res.Configuration
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.GradientDrawable
import android.text.method.ScrollingMovementMethod
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.TextView
import com.agentworkspace.mobile.UiText

/**
 * The bottom panel shown while offline voice input listens: a live level meter, the text recognized
 * so far, and Cancel / Done. The finished text goes to [onText], which puts it in the composer.
 */
class VoiceInputDialog(private val activity: Activity, private val onText: (String) -> Unit) {
    private val dialog = Dialog(activity)
    private val dark = (activity.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
        Configuration.UI_MODE_NIGHT_YES
    private val textColor = if (dark) Color.WHITE else 0xFF18201E.toInt()
    private val muted = if (dark) 0xB3FFFFFF.toInt() else 0x99000000.toInt()
    private val accent = 0xFF0F766E.toInt()
    private val title = TextView(activity)
    private val transcript = TextView(activity)
    private val meter = LevelMeter(activity, accent)
    private val primary = TextView(activity)
    private val secondary = TextView(activity)
    private var session: OfflineVoiceSession? = null
    private var delivered = false

    val isShowing: Boolean get() = dialog.isShowing

    private fun dp(value: Int): Int =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), activity.resources.displayMetrics).toInt()

    fun show() {
        val panel = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(22), dp(20), dp(22), dp(16))
            background = GradientDrawable().apply {
                cornerRadius = dp(22).toFloat()
                setColor(if (dark) 0xFF1F2725.toInt() else Color.WHITE)
            }
        }
        val header = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        title.apply { textSize = 18f; setTextColor(textColor) }
        header.addView(title, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        header.addView(meter, LinearLayout.LayoutParams(dp(56), dp(28)))
        panel.addView(header)
        transcript.apply {
            textSize = 16f
            setTextColor(textColor)
            setHintTextColor(muted)
            hint = UiText.of(activity, "请说话，说完停顿一下会自动结束", "Speak; pausing at the end finishes")
            maxLines = 6
            movementMethod = ScrollingMovementMethod()
            setPadding(0, dp(14), 0, dp(10))
        }
        panel.addView(transcript, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        panel.addView(TextView(activity).apply {
            text = UiText.of(activity, "离线识别 · 录音只在手机上处理", "Offline · audio stays on this phone")
            textSize = 12f
            setTextColor(muted)
            setPadding(0, 0, 0, dp(10))
        })
        val footer = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.END or Gravity.CENTER_VERTICAL }
        footer.addView(button(secondary, filled = false))
        footer.addView(button(primary, filled = true), LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT).apply { marginStart = dp(8) })
        panel.addView(footer)

        dialog.setContentView(panel)
        dialog.setCanceledOnTouchOutside(true)
        dialog.setOnCancelListener { session?.cancel() }
        dialog.window?.apply {
            setBackgroundDrawable(ColorDrawable(Color.TRANSPARENT))
            setGravity(Gravity.BOTTOM)
            setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            attributes = attributes.apply { y = dp(12) }
            decorView.setPadding(dp(12), 0, dp(12), 0)
            addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
        dialog.show()
        listen()
    }

    /** Stops listening and closes without delivering anything (the activity is going away). */
    fun cancel() {
        session?.cancel()
        if (dialog.isShowing) dialog.dismiss()
    }

    private fun button(view: TextView, filled: Boolean): TextView = view.apply {
        textSize = 15f
        gravity = Gravity.CENTER
        minWidth = dp(72)
        setPadding(dp(16), dp(9), dp(16), dp(9))
        setTextColor(if (filled) Color.WHITE else accent)
        background = GradientDrawable().apply {
            cornerRadius = dp(20).toFloat()
            if (filled) setColor(accent) else setStroke(dp(1), accent)
        }
    }

    private fun listen() {
        delivered = false
        title.text = UiText.of(activity, "正在听…", "Listening…")
        transcript.text = ""
        meter.visibility = View.VISIBLE
        meter.reset()
        secondary.text = UiText.of(activity, "取消", "Cancel")
        secondary.setOnClickListener { dialog.cancel() }
        primary.text = UiText.of(activity, "完成", "Done")
        primary.isEnabled = true
        primary.alpha = 1f
        primary.setOnClickListener { session?.finish() }
        session = OfflineVoiceSession(activity, object : OfflineVoiceSession.Listener {
            override fun onLevel(level: Float) = meter.push(level)
            override fun onText(text: String) { transcript.text = text }
            override fun onRecognizing() {
                title.text = UiText.of(activity, "正在识别…", "Recognizing…")
                meter.visibility = View.INVISIBLE
                primary.isEnabled = false
                primary.alpha = 0.5f
            }
            override fun onFinished(text: String, heardSpeech: Boolean) {
                if (text.isNotBlank()) {
                    deliver(text)
                    return
                }
                retryable(if (heardSpeech) UiText.of(activity, "没有识别出内容", "Nothing was recognized")
                    else UiText.of(activity, "没有听到说话", "No speech was heard"))
            }
            override fun onError(message: String) = retryable(message)
        }).also { it.start() }
    }

    private fun deliver(text: String) {
        if (delivered) return
        delivered = true
        onText(text)
        if (dialog.isShowing) dialog.dismiss()
    }

    private fun retryable(message: String) {
        title.text = message
        meter.visibility = View.INVISIBLE
        primary.text = UiText.of(activity, "再说一次", "Try again")
        primary.isEnabled = true
        primary.alpha = 1f
        primary.setOnClickListener { listen() }
        secondary.text = UiText.of(activity, "关闭", "Close")
    }

    /** Five bars following the recent input level. */
    private class LevelMeter(context: Context, color: Int) : View(context) {
        private val levels = FloatArray(5)
        private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { this.color = color }
        private val bar = RectF()

        fun reset() {
            levels.fill(0f)
            invalidate()
        }

        fun push(level: Float) {
            System.arraycopy(levels, 1, levels, 0, levels.size - 1)
            // Speech sits around 0.02-0.2 RMS; a square root spreads that over the bar height.
            levels[levels.size - 1] = kotlin.math.sqrt((level * 4f).coerceIn(0f, 1f))
            invalidate()
        }

        override fun onDraw(canvas: Canvas) {
            val gap = width / (levels.size * 3f)
            val barWidth = gap * 2
            val radius = barWidth / 2
            for (index in levels.indices) {
                val height = (height * (0.18f + 0.82f * levels[index])).coerceAtLeast(barWidth)
                val left = gap / 2 + index * (barWidth + gap)
                bar.set(left, (this.height - height) / 2, left + barWidth, (this.height + height) / 2)
                canvas.drawRoundRect(bar, radius, radius, paint)
            }
        }
    }
}
