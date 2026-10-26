package com.agentworkspace.mobile.devices

import android.content.Context
import android.graphics.BitmapFactory
import android.net.Uri
import com.google.zxing.BarcodeFormat
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.LuminanceSource
import com.google.zxing.MultiFormatReader
import com.google.zxing.RGBLuminanceSource
import com.google.zxing.ReaderException
import com.google.zxing.common.GlobalHistogramBinarizer
import com.google.zxing.common.HybridBinarizer
import java.io.File
import java.io.InputStream

/**
 * A desktop's pairing QR code (Settings → Phone connection) read from a photo of its screen or
 * from a picture, offline and without Google Play services.
 */
object PairingQr {
    private val hints = mapOf(
        DecodeHintType.POSSIBLE_FORMATS to listOf(BarcodeFormat.QR_CODE),
        DecodeHintType.TRY_HARDER to true,
        DecodeHintType.CHARACTER_SET to "UTF-8",
    )

    // A picture cropped to the code and its quiet zone, which the finder search can miss.
    private val pureHints = hints + (DecodeHintType.PURE_BARCODE to true)

    /** The text of the QR code in [pixels] (ARGB, row by row), or null when there is none. */
    fun decode(width: Int, height: Int, pixels: IntArray): String? {
        val source: LuminanceSource = RGBLuminanceSource(width, height, pixels)
        // A dark-mode screen shows the code light on dark.
        for (candidate in listOf(source, source.invert())) {
            for (binarized in listOf(BinaryBitmap(HybridBinarizer(candidate)), BinaryBitmap(GlobalHistogramBinarizer(candidate)))) {
                read(binarized, hints)?.let { return it }
            }
            read(BinaryBitmap(HybridBinarizer(candidate)), pureHints)?.let { return it }
        }
        return null
    }

    private fun read(bitmap: BinaryBitmap, hints: Map<DecodeHintType, Any>): String? =
        try {
            MultiFormatReader().decode(bitmap, hints).text
        } catch (_: ReaderException) {
            null
        }

    /**
     * The QR code in an image, read at a few sizes: a photo of a screen is large and the code in
     * it can be small, while a screenshot reads best near its own size.
     */
    fun decodeImage(open: () -> InputStream?): String? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        // Reading only the bounds always returns null; the size is in [bounds].
        (open() ?: return null).use { BitmapFactory.decodeStream(it, null, bounds) }
        val longest = maxOf(bounds.outWidth, bounds.outHeight)
        if (longest <= 0) return null
        val samples = listOf(2400, 1600, 1000).map { edge ->
            var sample = 1
            while (longest / (sample * 2) >= edge) sample *= 2
            sample
        }.distinct()
        for (sample in samples) {
            val bitmap = open()?.use { BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample }) }
                ?: continue
            try {
                val pixels = IntArray(bitmap.width * bitmap.height)
                bitmap.getPixels(pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
                decode(bitmap.width, bitmap.height, pixels)?.let { return it }
            } finally {
                bitmap.recycle()
            }
        }
        return null
    }

    fun decodeFile(file: File): String? = decodeImage { runCatching { file.inputStream() }.getOrNull() }

    fun decodeUri(context: Context, uri: Uri): String? = decodeImage { runCatching { context.contentResolver.openInputStream(uri) }.getOrNull() }
}
