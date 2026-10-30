package com.agentworkspace.mobile.automation

import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.LinearGradient
import android.graphics.Outline
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.drawable.Drawable

/**
 * The phone control panel's glass: a tint over what lies under the panel (blurred by the system on
 * Android 12+ when it can), a sheen along the top, a hairline edge and a bright inner rim where
 * light would catch the glass. Without the blur the tint is nearly solid, so the panel's text stays
 * readable over any app.
 */
internal class GlassPanelDrawable(private val radius: Float, private val rimWidth: Float) : Drawable() {
    var dark = false
        set(value) { if (field != value) { field = value; shadedFor = null; invalidateSelf() } }

    /** The system blurs what lies behind: the tint can let more of it through. */
    var blurred = false
        set(value) { if (field != value) { field = value; invalidateSelf() } }

    private val fill = Paint(Paint.ANTI_ALIAS_FLAG)
    private val sheen = Paint(Paint.ANTI_ALIAS_FLAG)
    private val edge = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeWidth = rimWidth }
    private val rim = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeWidth = rimWidth }
    private val shape = RectF()
    private var shadedFor: Rect? = null
    private var opacity = 255

    private fun tint(): Int = when {
        dark && blurred -> 0xC41F2725.toInt()
        dark -> 0xF71F2725.toInt()
        blurred -> 0xB8FFFFFF.toInt()
        else -> 0xF7FFFFFF.toInt()
    }

    // The window may ask for the outline (the blur's corners) before its first layout: keep the radius.
    private fun corner(bounds: Rect) = if (bounds.isEmpty) radius else minOf(radius, bounds.height() / 2f)

    private fun shade(bounds: Rect) {
        val top = bounds.top.toFloat()
        val height = bounds.height().toFloat()
        sheen.shader = LinearGradient(0f, top, 0f, top + height * 0.45f,
            if (dark) 0x1CFFFFFF else 0x66FFFFFF, 0x00FFFFFF, Shader.TileMode.CLAMP)
        edge.shader = LinearGradient(0f, top, 0f, top + height,
            if (dark) 0x2EFFFFFF else 0x14000000, if (dark) 0x14FFFFFF else 0x24000000, Shader.TileMode.CLAMP)
        rim.shader = LinearGradient(0f, top, 0f, top + minOf(height, radius * 2.5f),
            if (dark) 0x40FFFFFF else 0xE6FFFFFF.toInt(), 0x00FFFFFF, Shader.TileMode.CLAMP)
        shadedFor = Rect(bounds)
    }

    override fun draw(canvas: Canvas) {
        val bounds = bounds
        if (bounds.isEmpty) return
        if (shadedFor != bounds) shade(bounds)
        val layer = if (opacity < 255) canvas.saveLayerAlpha(RectF(bounds), opacity) else -1
        val r = corner(bounds)
        shape.set(bounds)
        fill.color = tint()
        canvas.drawRoundRect(shape, r, r, fill)
        canvas.drawRoundRect(shape, r, r, sheen)
        val half = rimWidth / 2f
        shape.inset(half, half)
        canvas.drawRoundRect(shape, r - half, r - half, edge)
        shape.inset(rimWidth, rimWidth)
        canvas.drawRoundRect(shape, r - half - rimWidth, r - half - rimWidth, rim)
        if (layer >= 0) canvas.restoreToCount(layer)
    }

    // The outline shapes the shadow and, on a window's background, the blurred area's corners.
    override fun getOutline(outline: Outline) {
        outline.setRoundRect(bounds, corner(bounds))
        outline.alpha = if (blurred) 0.4f else 1f
    }

    override fun onBoundsChange(bounds: Rect) { shadedFor = null }

    override fun setAlpha(alpha: Int) { opacity = alpha; invalidateSelf() }

    override fun getAlpha() = opacity

    override fun setColorFilter(colorFilter: ColorFilter?) {
        fill.colorFilter = colorFilter
        invalidateSelf()
    }

    @Deprecated("Deprecated in Java")
    override fun getOpacity() = PixelFormat.TRANSLUCENT
}
