package com.agentworkspace.mobile.documents

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.BitmapShader
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import android.text.StaticLayout
import android.text.TextPaint
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * A tutorial picture made from a task's step pictures (mobile_step_tutorial.py): a title, then each
 * step numbered with what to do and, where there is one, the screen it is done on with the spot to
 * touch circled. A long one becomes several pictures of at most [PART] pixels, as JPEG.
 */
object StepTutorial {
    private const val WIDTH = 1080
    private const val MARGIN = 64
    private const val BADGE = 76
    private const val GUTTER = 28
    private const val PICTURE = 600
    private const val PART = 12_000
    private const val MAX_FRAMES = 80

    private val ink = Color.rgb(0x1F, 0x23, 0x28)
    private val muted = Color.rgb(0x65, 0x6D, 0x76)
    private val accent = Color.rgb(0x1A, 0x73, 0xE8)
    private val finished = Color.rgb(0x1F, 0x88, 0x3D)
    private val mark = Color.rgb(0xE5, 0x48, 0x4D)
    private val edge = Color.rgb(0xD0, 0xD7, 0xDE)

    private class Block(val height: Int, val draw: (Canvas, Int) -> Unit)

    /** [spec]: {title, subtitle, output_dir, frames: [{number, caption, picture, covers, ring: [x, y], done}]}. */
    @JvmStatic
    fun render(spec: String): String = try {
        JSONObject().put("outputs", draw(JSONObject(spec))).toString()
    } catch (error: Exception) {
        JSONObject().put("error", (error.message ?: error.javaClass.simpleName).take(300)).toString()
    }

    private fun paint(size: Float, color: Int, bold: Boolean = false) = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
        textSize = size
        this.color = color
        typeface = if (bold) Typeface.DEFAULT_BOLD else Typeface.DEFAULT
    }

    private fun layout(value: String, paint: TextPaint, width: Int): StaticLayout =
        StaticLayout.Builder.obtain(value, 0, value.length, paint, width).setLineSpacing(0f, 1.18f).build()

    private fun Canvas.drawAt(layout: StaticLayout, x: Int, y: Int) {
        save()
        translate(x.toFloat(), y.toFloat())
        layout.draw(this)
        restore()
    }

    private fun draw(spec: JSONObject): JSONArray {
        val folder = File(spec.getString("output_dir"))
        require(folder.isDirectory) { "output_dir must be a folder" }
        val frames = spec.getJSONArray("frames")
        require(frames.length() in 1..MAX_FRAMES) { "A tutorial has 1 to $MAX_FRAMES steps" }
        val inner = WIDTH - MARGIN * 2
        val title = layout(spec.optString("title").take(200).ifBlank { " " }, paint(58f, ink, bold = true), inner)
        val subtitle = spec.optString("subtitle").take(200).takeIf { it.isNotBlank() }?.let { layout(it, paint(34f, muted), inner) }
        val blocks = arrayListOf(Block(title.height + (subtitle?.let { 18 + it.height } ?: 0) + 56) { canvas, top ->
            canvas.drawAt(title, MARGIN, top)
            subtitle?.let { canvas.drawAt(it, MARGIN, top + title.height + 18) }
        })
        for (index in 0 until frames.length()) blocks.add(step(frames.getJSONObject(index)))
        // Whole steps per picture: one is never cut in two.
        val parts = ArrayList<List<Block>>()
        var current = ArrayList<Block>()
        var height = MARGIN
        for (block in blocks) {
            if (current.isNotEmpty() && height + block.height > PART) {
                parts.add(current)
                current = ArrayList()
                height = MARGIN
            }
            current.add(block)
            height += block.height
        }
        parts.add(current)
        val outputs = JSONArray()
        parts.forEachIndexed { number, part ->
            // Each block ends with its own space below, which is the bottom margin of the last one.
            val total = MARGIN + part.sumOf { it.height }
            val image = Bitmap.createBitmap(WIDTH, total, Bitmap.Config.RGB_565)
            try {
                image.eraseColor(Color.WHITE)
                val canvas = Canvas(image)
                var top = MARGIN
                part.forEach { it.draw(canvas, top); top += it.height }
                val file = File(folder, "tutorial-${number + 1}.jpg")
                file.outputStream().use {
                    if (!image.compress(Bitmap.CompressFormat.JPEG, 88, it)) error("The tutorial picture could not be encoded")
                }
                outputs.put(JSONObject().put("path", file.path).put("width", WIDTH).put("height", total))
            } finally { image.recycle() }
        }
        return outputs
    }

    private fun step(frame: JSONObject): Block {
        val left = MARGIN + BADGE + GUTTER
        val caption = layout(frame.optString("caption").take(300).ifBlank { " " }, paint(46f, ink), WIDTH - left - MARGIN)
        // The first line sits level with the number.
        val lift = ((BADGE - (caption.getLineBottom(0) - caption.getLineTop(0))) / 2).coerceAtLeast(0)
        val header = maxOf(BADGE, lift + caption.height)
        // Only the size now: the picture itself is read when it is drawn, one at a time.
        val source = frame.optString("picture").takeIf { it.isNotEmpty() }
        val bounds = source?.let { BitmapFactory.Options().apply { inJustDecodeBounds = true; BitmapFactory.decodeFile(it, this) } }
            ?.takeIf { it.outWidth > 0 && it.outHeight > 0 }
        val shown = bounds?.let { PICTURE * it.outHeight / it.outWidth } ?: 0
        val ring = frame.optJSONArray("ring")?.takeIf { it.length() == 2 }
            ?.let { it.getDouble(0).toFloat().coerceIn(0f, 1f) to it.getDouble(1).toFloat().coerceIn(0f, 1f) }
        val covers = frame.optJSONArray("covers")?.let { list ->
            (0 until minOf(list.length(), 6)).mapNotNull { index ->
                list.optJSONArray(index)?.takeIf { it.length() == 4 }
                    ?.let { box -> FloatArray(4) { box.getDouble(it).toFloat().coerceIn(0f, 1f) } }
            }
        }.orEmpty()
        val done = frame.optBoolean("done")
        val number = frame.optString("number").take(3)
        return Block(header + (if (bounds != null) GUTTER + shown else 0) + MARGIN) { canvas, top ->
            val cx = MARGIN + BADGE / 2f
            val cy = top + BADGE / 2f
            canvas.drawCircle(cx, cy, BADGE / 2f, Paint(Paint.ANTI_ALIAS_FLAG).apply { color = if (done) finished else accent })
            val white = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.WHITE }
            if (done) {
                val tick = Path().apply { moveTo(cx - 17, cy + 1); lineTo(cx - 5, cy + 13); lineTo(cx + 18, cy - 12) }
                canvas.drawPath(tick, white.apply {
                    style = Paint.Style.STROKE; strokeWidth = 8f; strokeCap = Paint.Cap.ROUND; strokeJoin = Paint.Join.ROUND
                })
            } else {
                white.apply { textSize = 40f; typeface = Typeface.DEFAULT_BOLD; textAlign = Paint.Align.CENTER }
                canvas.drawText(number, cx, cy - (white.ascent() + white.descent()) / 2, white)
            }
            canvas.drawAt(caption, left, top + lift)
            if (bounds == null) return@Block
            val picture = BitmapFactory.decodeFile(source, BitmapFactory.Options().apply { inMutable = true }) ?: return@Block
            try {
                paintOut(picture, covers, ring)
                val y = (top + header + GUTTER).toFloat()
                val box = RectF(left.toFloat(), y, (left + PICTURE).toFloat(), y + shown)
                val shader = BitmapShader(picture, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP).apply {
                    setLocalMatrix(Matrix().apply {
                        setRectToRect(RectF(0f, 0f, picture.width.toFloat(), picture.height.toFloat()), box, Matrix.ScaleToFit.FILL)
                    })
                }
                canvas.drawRoundRect(box, 28f, 28f, Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG or Paint.DITHER_FLAG)
                    .apply { this.shader = shader })
                canvas.drawRoundRect(box, 28f, 28f, Paint(Paint.ANTI_ALIAS_FLAG).apply {
                    style = Paint.Style.STROKE; strokeWidth = 3f; color = edge
                })
                ring?.let { (fx, fy) ->
                    val x = box.left + fx * box.width()
                    val ry = box.top + fy * box.height()
                    canvas.drawCircle(x, ry, 46f, Paint(Paint.ANTI_ALIAS_FLAG).apply { color = mark; alpha = 0x38 })
                    canvas.drawCircle(x, ry, 46f, Paint(Paint.ANTI_ALIAS_FLAG).apply {
                        color = mark; style = Paint.Style.STROKE; strokeWidth = 9f
                    })
                }
            } finally { picture.recycle() }
        }
    }

    /**
     * Small floating windows on a picture (the bubble, a floating assist button), filled with the
     * color found most around each: on the flat background of most screens, nothing shows where it
     * was. One holding the spot the step touches stays.
     */
    private fun paintOut(picture: Bitmap, covers: List<FloatArray>, ring: Pair<Float, Float>?) {
        if (covers.isEmpty() || !picture.isMutable) return
        val canvas = Canvas(picture)
        val fill = Paint()
        for (box in covers) {
            if (ring != null && ring.first in box[0]..box[2] && ring.second in box[1]..box[3]) continue
            // A little wider: the window's edge is drawn soft.
            val left = ((box[0] * picture.width).toInt() - 3).coerceIn(0, picture.width)
            val top = ((box[1] * picture.height).toInt() - 3).coerceIn(0, picture.height)
            val right = ((box[2] * picture.width).toInt() + 3).coerceIn(0, picture.width)
            val bottom = ((box[3] * picture.height).toInt() + 3).coerceIn(0, picture.height)
            if (right <= left || bottom <= top) continue
            fill.color = around(picture, left, top, right, bottom)
            canvas.drawRect(left.toFloat(), top.toFloat(), right.toFloat(), bottom.toFloat(), fill)
        }
    }

    /** The color most common just outside a box (colors close together count as one). */
    private fun around(picture: Bitmap, left: Int, top: Int, right: Int, bottom: Int): Int {
        val counts = HashMap<Int, IntArray>()
        fun take(x: Int, y: Int) {
            if (x !in 0 until picture.width || y !in 0 until picture.height) return
            val color = picture.getPixel(x, y)
            val red = Color.red(color)
            val green = Color.green(color)
            val blue = Color.blue(color)
            val sums = counts.getOrPut(((red shr 4) shl 8) or ((green shr 4) shl 4) or (blue shr 4)) { IntArray(4) }
            sums[0]++
            sums[1] += red
            sums[2] += green
            sums[3] += blue
        }
        for (x in left - 1..right) { take(x, top - 1); take(x, bottom) }
        for (y in top until bottom) { take(left - 1, y); take(right, y) }
        val most = counts.values.maxByOrNull { it[0] } ?: return Color.WHITE
        return Color.rgb(most[1] / most[0], most[2] / most[0], most[3] / most[0])
    }
}
