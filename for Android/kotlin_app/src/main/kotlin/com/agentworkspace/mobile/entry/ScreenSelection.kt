package com.agentworkspace.mobile.entry

import kotlin.math.max
import kotlin.math.min

/** A part of a screenshot, in its pixels; right and bottom are exclusive. */
data class ScreenRegion(val left: Int, val top: Int, val right: Int, val bottom: Int) {
    val width: Int get() = right - left
    val height: Int get() = bottom - top
}

/** How a screenshot is drawn into a view: scaled by [scale], then offset by [dx], [dy]. */
data class ScreenFit(val scale: Float, val dx: Float, val dy: Float) {
    fun toImageX(viewX: Float) = (viewX - dx) / scale
    fun toImageY(viewY: Float) = (viewY - dy) / scale
    fun toViewX(imageX: Float) = imageX * scale + dx
    fun toViewY(imageY: Float) = imageY * scale + dy
}

/** Turns the stroke the user draws around something on a screenshot into the part to ask about. */
object ScreenSelection {
    /** The whole screenshot centred in the view, as large as fits. */
    fun fit(imageWidth: Int, imageHeight: Int, viewWidth: Int, viewHeight: Int): ScreenFit {
        if (imageWidth <= 0 || imageHeight <= 0 || viewWidth <= 0 || viewHeight <= 0) return ScreenFit(1f, 0f, 0f)
        val scale = min(viewWidth.toFloat() / imageWidth, viewHeight.toFloat() / imageHeight)
        return ScreenFit(scale, (viewWidth - imageWidth * scale) / 2f, (viewHeight - imageHeight * scale) / 2f)
    }

    /**
     * The part of a [width] × [height] screenshot marked by a stroke through ([xs], [ys]), in its
     * pixels. The stroke's bounding box is widened by [padding] so a loose circle keeps what it went
     * around, then grown to at least [minimum] per side so an underline still gives the model some
     * context. A stroke no larger than [tapSlop] either way is a tap, not a selection: null.
     */
    fun region(xs: FloatArray, ys: FloatArray, width: Int, height: Int, padding: Int, minimum: Int, tapSlop: Int): ScreenRegion? {
        if (width <= 0 || height <= 0) return null
        var left = Float.POSITIVE_INFINITY
        var top = Float.POSITIVE_INFINITY
        var right = Float.NEGATIVE_INFINITY
        var bottom = Float.NEGATIVE_INFINITY
        for (index in 0 until min(xs.size, ys.size)) {
            val x = xs[index]
            val y = ys[index]
            if (x.isNaN() || y.isNaN()) continue
            left = min(left, x); right = max(right, x)
            top = min(top, y); bottom = max(bottom, y)
        }
        if (left > right || top > bottom) return null
        if (right - left <= tapSlop && bottom - top <= tapSlop) return null
        val (x0, x1) = span(left - padding, right + padding, minimum, width)
        val (y0, y1) = span(top - padding, bottom + padding, minimum, height)
        return if (x1 > x0 && y1 > y0) ScreenRegion(x0, y0, x1, y1) else null
    }

    /** [start, end) within [0, limit), at least [minimum] long where the limit allows. */
    private fun span(start: Float, end: Float, minimum: Int, limit: Int): Pair<Int, Int> {
        var from = start.toInt().coerceIn(0, limit)
        var to = kotlin.math.ceil(end).toInt().coerceIn(0, limit)
        val wanted = min(minimum, limit)
        if (to - from < wanted) {
            val middle = (from + to) / 2
            from = (middle - wanted / 2).coerceIn(0, limit - wanted)
            to = from + wanted
        }
        return from to to
    }
}
