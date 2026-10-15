package com.agentworkspace.mobile

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.Shader
import android.provider.Settings
import android.view.View
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/**
 * The start-up screen while the engine comes up: lines of light flow in from the left and draw
 * together into a lens around three turning orbits with a breathing core. It runs for exactly as
 * long as loading takes; [finish] then sends the orbits outwards and spreads the lines while the
 * console opens from the centre. With animations turned off in Android, it shows one still frame.
 */
@SuppressLint("ViewConstructor")
class StartupAnimationView(context: Context, private val dark: Boolean) : View(context) {
    private val density = resources.displayMetrics.density
    private val still = Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f

    private val accent = if (dark) Color.rgb(0x5C, 0xC6, 0xB1) else Color.rgb(0x0F, 0x76, 0x6E)
    private val sky = if (dark) Color.rgb(0x38, 0xBD, 0xF8) else Color.rgb(0x02, 0x84, 0xC7)
    private val violet = if (dark) Color.rgb(0xA7, 0x8B, 0xFA) else Color.rgb(0x7C, 0x3A, 0xED)

    private val line = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND; strokeWidth = 1.3f * density }
    private val glow = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND; strokeWidth = 5f * density }
    private val orbit = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND }
    private val core = Paint(Paint.ANTI_ALIAS_FLAG)
    private val halo = Paint(Paint.ANTI_ALIAS_FLAG)
    private val backdrop = Paint(Paint.ANTI_ALIAS_FLAG)
    private val path = Path()

    private var startedAt = 0L
    private var exitAt = 0L
    private var onExited: (() -> Unit)? = null

    /** Starts (or restarts) the loading loop from the lines drawing in. */
    fun start() {
        startedAt = System.nanoTime()
        exitAt = 0L
        onExited = null
        alpha = 1f
        postInvalidateOnAnimation()
    }

    /** Plays the opening and calls [onEnd] when the screen is clear; at once with animations off. */
    fun finish(onEnd: () -> Unit) {
        if (still || !isShown) { onEnd(); return }
        if (exitAt != 0L) { onExited = onEnd; return }
        exitAt = System.nanoTime()
        onExited = onEnd
        postInvalidateOnAnimation()
    }

    override fun onSizeChanged(width: Int, height: Int, oldWidth: Int, oldHeight: Int) {
        val colors = intArrayOf(accent, sky, violet, sky, accent)
        line.shader = LinearGradient(0f, 0f, width.toFloat(), 0f, colors, null, Shader.TileMode.CLAMP)
        glow.shader = LinearGradient(0f, 0f, width.toFloat(), 0f, colors, null, Shader.TileMode.CLAMP)
        orbit.shader = LinearGradient(width / 2f - 60 * density, 0f, width / 2f + 60 * density, 0f,
            intArrayOf(accent, sky, violet), null, Shader.TileMode.CLAMP)
        backdrop.shader = RadialGradient(width / 2f, height * CENTER, max(width, 1) * 0.75f,
            intArrayOf(withAlpha(sky, if (dark) 40 else 22), withAlpha(violet, if (dark) 14 else 8), withAlpha(accent, 0)),
            floatArrayOf(0f, 0.55f, 1f), Shader.TileMode.CLAMP)
    }

    override fun onDraw(canvas: Canvas) {
        if (startedAt == 0L) startedAt = System.nanoTime()
        val now = System.nanoTime()
        val time = if (still) 2.4f else (now - startedAt) / 1e9f
        val exit = if (exitAt == 0L) 0f else ((now - exitAt) / 1e9f / EXIT_SECONDS).coerceIn(0f, 1f)
        val opening = easeInOut(exit)
        // A soft light behind the lens, gone as the console opens.
        backdrop.alpha = (255 * (1f - opening) * ((time / 0.8f).coerceIn(0f, 1f))).toInt()
        canvas.drawCircle(width / 2f, height * CENTER, max(width, 1) * 0.75f, backdrop)
        drawLines(canvas, time, opening)
        drawOrbits(canvas, time, opening)
        if (exit >= 1f) {
            val done = onExited
            onExited = null
            done?.invoke()
            return
        }
        if (!still && isShown) postInvalidateOnAnimation()
    }

    /** Lines of light across the screen, drawn in one after another, pulled together at the centre. */
    private fun drawLines(canvas: Canvas, time: Float, opening: Float) {
        val width = width.toFloat()
        val height = height.toFloat()
        val centerX = width / 2f
        val centerY = height * CENTER
        val spread = min(height * 0.82f, width * 2.1f)
        val step = 6f * density
        for (index in 0 until LINES) {
            val offset = index - (LINES - 1) / 2f
            val base = centerY + offset / LINES * spread
            val drawn = ((time - index * 0.045f) / 0.95f).coerceIn(0f, 1f)
            if (drawn <= 0f) continue
            val reach = width * easeOut(drawn)
            val amplitude = (5f + 3f * sin(index * 1.7f)) * density * (1f + 2.2f * opening)
            val speed = 1.1f + 0.35f * ((index * 37) % 7) / 7f
            val pull = 0.88f * (1f - opening)
            path.reset()
            var x = 0f
            while (x <= reach) {
                // A lens: near the centre every line bends towards the middle of the screen.
                val focus = pull * exp(-((x - centerX) / (width * 0.3f)).let { it * it })
                val wave = sin(x / width * 2f * PI.toFloat() * 1.3f + time * speed + index * 0.8f) * amplitude
                val y = base + (centerY - base) * focus + wave * (1f - 0.6f * focus)
                if (x == 0f) path.moveTo(x, y) else path.lineTo(x, y)
                x += step
            }
            val nearness = 1f - kotlin.math.abs(offset) / (LINES / 2f)
            val fade = (1f - opening) * (0.12f + 0.7f * nearness * nearness)
            glow.alpha = (fade * 38).toInt()
            line.alpha = (fade * 255).toInt().coerceIn(0, 255)
            canvas.drawPath(path, glow)
            canvas.drawPath(path, line)
        }
    }

    /** Three tilted orbits turning around a breathing core, each with a bright comet. */
    private fun drawOrbits(canvas: Canvas, time: Float, opening: Float) {
        val centerX = width / 2f
        val centerY = height * CENTER
        val arrive = easeOutBack(((time - 0.25f) / 0.7f).coerceIn(0f, 1f))
        val scale = (0.55f + 0.45f * arrive) * (1f + 8f * opening)
        val visibility = ((time - 0.2f) / 0.5f).coerceIn(0f, 1f) * (1f - opening)
        if (visibility <= 0f && opening <= 0f) return
        val radiusX = 52f * density * scale
        val radiusY = 19f * density * scale
        canvas.save()
        canvas.translate(centerX, centerY)
        for (index in 0 until 3) {
            val tilt = index * 60f + time * 14f
            canvas.save()
            canvas.rotate(tilt)
            // The whole orbit, faint.
            orbit.strokeWidth = 1f * density
            orbit.alpha = (visibility * 70).toInt()
            path.reset()
            path.addOval(-radiusX, -radiusY, radiusX, radiusY, Path.Direction.CW)
            canvas.drawPath(path, orbit)
            // The comet: a tail that brightens towards its head.
            val head = time * 2.3f + index * 2.094f
            val segments = 18
            for (segment in 0 until segments) {
                val from = head - 1.5f * (segment + 1) / segments
                val to = head - 1.5f * segment / segments
                orbit.strokeWidth = (2.6f - 1.6f * segment / segments) * density
                orbit.alpha = (visibility * 255 * (1f - segment / segments.toFloat())).toInt().coerceIn(0, 255)
                canvas.drawLine(radiusX * cos(from), radiusY * sin(from), radiusX * cos(to), radiusY * sin(to), orbit)
            }
            canvas.restore()
        }
        // The core breathes while loading and swells as the console opens.
        val pulse = 1f + 0.18f * sin(time * 3.1f)
        val coreRadius = 5.5f * density * pulse * (1f + 5f * opening) * max(arrive, 0.01f)
        halo.shader = RadialGradient(0f, 0f, coreRadius * 5f, intArrayOf(withAlpha(sky, 110), withAlpha(accent, 0)), null, Shader.TileMode.CLAMP)
        halo.alpha = (visibility * 255).toInt()
        canvas.drawCircle(0f, 0f, coreRadius * 5f, halo)
        core.color = if (dark) Color.WHITE else accent
        core.alpha = (visibility * 255).toInt()
        canvas.drawCircle(0f, 0f, coreRadius, core)
        canvas.restore()
    }

    private fun withAlpha(color: Int, alpha: Int) = Color.argb(alpha, Color.red(color), Color.green(color), Color.blue(color))

    private fun easeOut(value: Float) = 1f - (1f - value).let { it * it * it }

    private fun easeInOut(value: Float) = if (value < 0.5f) 4f * value * value * value else 1f - (-2f * value + 2f).let { it * it * it } / 2f

    private fun easeOutBack(value: Float): Float {
        val overshoot = 1.7f
        val shifted = value - 1f
        return 1f + (overshoot + 1f) * shifted * shifted * shifted + overshoot * shifted * shifted
    }

    companion object {
        const val EXIT_SECONDS = 0.62f
        /** Where the orbits sit: a little above the middle, leaving room for the name and the step. */
        const val CENTER = 0.42f
        private const val LINES = 18
    }
}
