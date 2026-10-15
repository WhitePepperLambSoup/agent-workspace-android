package com.agentworkspace.mobile.automation

import android.graphics.Bitmap
import android.graphics.Rect
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import java.util.concurrent.TimeUnit

/**
 * Words read off a screenshot with the app's bundled offline recognizer (Chinese and Latin). Badges,
 * pictures, games and canvases show words no control reports; read this way the agent can find and
 * tap them without looking at the picture itself.
 */
internal object ScreenText {
    /** Lines of text with their bounds, scaled by [scaleX]/[scaleY] from picture to screen pixels. */
    fun recognize(context: android.content.Context, bitmap: Bitmap, scaleX: Float, scaleY: Float): List<Pair<String, Rect>> {
        // :engine has no ML Kit initializer provider of its own.
        com.google.mlkit.common.sdkinternal.MlKitContext.initializeIfNeeded(context.applicationContext)
        val source = if (bitmap.config == Bitmap.Config.ARGB_8888) bitmap else bitmap.copy(Bitmap.Config.ARGB_8888, false)
        val recognizer = TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build())
        try {
            val text = Tasks.await(recognizer.process(InputImage.fromBitmap(source, 0)), 15, TimeUnit.SECONDS)
            return text.textBlocks.flatMap { it.lines }.mapNotNull { line ->
                val box = line.boundingBox ?: return@mapNotNull null
                val words = line.text.trim()
                if (words.isEmpty()) null else words to Rect((box.left * scaleX).toInt(), (box.top * scaleY).toInt(),
                    (box.right * scaleX).toInt(), (box.bottom * scaleY).toInt())
            }.sortedWith(compareBy({ it.second.top / 24 }, { it.second.left }))
        } finally {
            recognizer.close()
            if (source !== bitmap) source.recycle()
        }
    }
}
