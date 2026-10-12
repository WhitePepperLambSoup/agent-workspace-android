package com.agentworkspace.mobile.sharing

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.graphics.Matrix
import android.media.ExifInterface
import android.os.Build
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.channels.FileChannel
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.StandardCopyOption
import java.nio.file.StandardOpenOption
import java.security.MessageDigest
import java.util.Locale
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sqrt

/**
 * Pictures are made ready to send on the way in, the way chat apps prepare photos: anything over
 * the engine's 4 MiB image limit (mobile_images.MAX_MOBILE_ATTACHMENT_BYTES), in a format providers
 * refuse (such as HEIC), larger than [PIXEL_BUDGET] (providers scale those down anyway), or turned
 * by an EXIF tag (the local model's decoder ignores it) is re-encoded upright. A picture that does
 * not decode is left as it is, and the engine explains why it cannot be sent.
 */
internal object ShareInboxImages {
    /** Below the engine's 4 MiB cap, with room to spare. */
    const val SEND_LIMIT = 3_500_000
    /** Pixels kept when a picture has to be re-encoded: about 2560 × 1920. */
    const val PIXEL_BUDGET = 2560 * 1920
    /** The longest side every supported provider accepts. */
    const val MAX_EDGE = 8000
    private val sendableTypes = setOf("image/png", "image/jpeg", "image/gif", "image/webp")
    private val sendableExtensions = setOf("png", "jpg", "jpeg", "jfif", "gif", "webp")
    private val imageExtensions = sendableExtensions + setOf("heic", "heif", "hif", "avif", "bmp", "dib", "dng", "tif", "tiff")

    fun isImage(name: String, mediaType: String): Boolean =
        mediaType.startsWith("image/") || extension(name) in imageExtensions

    /**
     * Replaces [staged] with a re-encoded copy (written through [scratch] first) and returns it, or
     * returns null when the picture can be sent as it is or could not be decoded.
     */
    fun fit(staged: StagedShareFile, name: String, mediaType: String, scratch: File): StagedShareFile? {
        if (!isImage(name, mediaType)) return null
        val sendable = if (mediaType.startsWith("image/")) mediaType in sendableTypes else extension(name) in sendableExtensions
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        runCatching { BitmapFactory.decodeFile(staged.file.path, bounds) }
        if (sendable && staged.size <= SEND_LIMIT && max(bounds.outWidth, bounds.outHeight) in 1..MAX_EDGE &&
            bounds.outWidth.toLong() * bounds.outHeight <= PIXEL_BUDGET && !turned(staged.file, bounds.outMimeType)) return null
        val picture = runCatching { decode(staged.file) }.getOrNull() ?: return null
        val encoded = try { runCatching { encode(picture) }.getOrNull() } finally { picture.recycle() }
        val (bytes, png) = encoded ?: return null
        check(!Files.exists(scratch.toPath(), LinkOption.NOFOLLOW_LINKS) || scratch.delete()) { "分享文件无法安全保存" }
        try {
            FileChannel.open(scratch.toPath(), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE,
                LinkOption.NOFOLLOW_LINKS).use { channel ->
                val buffer = ByteBuffer.wrap(bytes)
                while (buffer.hasRemaining()) channel.write(buffer)
                channel.force(true)
            }
            Files.move(scratch.toPath(), staged.file.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE)
        } catch (failure: Exception) {
            scratch.delete()
            throw failure
        }
        check(staged.file.setReadOnly()) { "分享文件无法安全保存" }
        val stem = name.substringBeforeLast('.', name)
        return StagedShareFile(staged.file, bytes.size.toLong(), MessageDigest.getInstance("SHA-256").digest(bytes).hex(),
            ShareInboxFiles.safeName(stem + if (png) ".png" else ".jpg"), if (png) "image/png" else "image/jpeg")
    }

    /** The scale that keeps a picture within [PIXEL_BUDGET] and [MAX_EDGE]. */
    fun scale(width: Int, height: Int): Double {
        if (width <= 0 || height <= 0) return 1.0
        return min(1.0, min(sqrt(PIXEL_BUDGET / (width.toDouble() * height)), MAX_EDGE.toDouble() / max(width, height)))
    }

    private fun turned(file: File, mimeType: String?): Boolean = mimeType == "image/jpeg" && runCatching {
        ExifInterface(file.path).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL) !in
            setOf(ExifInterface.ORIENTATION_NORMAL, ExifInterface.ORIENTATION_UNDEFINED)
    }.getOrDefault(false)

    private fun decode(file: File): Bitmap? {
        if (Build.VERSION.SDK_INT >= 28) {
            // ImageDecoder reads HEIF too and applies the EXIF orientation itself.
            return ImageDecoder.decodeBitmap(ImageDecoder.createSource(file)) { decoder, info, _ ->
                val scale = scale(info.size.width, info.size.height)
                if (scale < 1.0) decoder.setTargetSize((info.size.width * scale).roundToInt().coerceAtLeast(1),
                    (info.size.height * scale).roundToInt().coerceAtLeast(1))
                decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
            }
        }
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.path, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
        val scale = scale(bounds.outWidth, bounds.outHeight)
        var sample = 1
        while (bounds.outWidth / (sample * 2) >= bounds.outWidth * scale && bounds.outHeight / (sample * 2) >= bounds.outHeight * scale) sample *= 2
        val decoded = BitmapFactory.decodeFile(file.path, BitmapFactory.Options().apply { inSampleSize = sample }) ?: return null
        val rotation = runCatching {
            when (ExifInterface(file.path).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
                ExifInterface.ORIENTATION_ROTATE_90 -> 90f
                ExifInterface.ORIENTATION_ROTATE_180 -> 180f
                ExifInterface.ORIENTATION_ROTATE_270 -> 270f
                else -> 0f
            }
        }.getOrDefault(0f)
        val width = (bounds.outWidth * scale).roundToInt().coerceAtLeast(1)
        val height = (bounds.outHeight * scale).roundToInt().coerceAtLeast(1)
        val matrix = Matrix().apply {
            postScale(width.toFloat() / decoded.width, height.toFloat() / decoded.height)
            if (rotation != 0f) postRotate(rotation)
        }
        val result = Bitmap.createBitmap(decoded, 0, 0, decoded.width, decoded.height, matrix, true)
        if (result !== decoded) decoded.recycle()
        return result
    }

    /** JPEG unless the picture really has transparent pixels; smaller until it fits [SEND_LIMIT]. */
    private fun encode(picture: Bitmap): Pair<ByteArray, Boolean>? {
        val png = picture.hasAlpha() && transparent(picture)
        var bitmap = picture
        var quality = 90
        try {
            repeat(10) {
                val bytes = ByteArrayOutputStream().also {
                    check(bitmap.compress(if (png) Bitmap.CompressFormat.PNG else Bitmap.CompressFormat.JPEG, quality, it))
                }.toByteArray()
                if (bytes.size <= SEND_LIMIT) return bytes to png
                if (!png && quality > 70) quality -= 10
                else {
                    val next = Bitmap.createScaledBitmap(bitmap, (bitmap.width * 0.8).roundToInt().coerceAtLeast(1),
                        (bitmap.height * 0.8).roundToInt().coerceAtLeast(1), true)
                    if (bitmap !== picture) bitmap.recycle()
                    bitmap = next
                }
            }
            return null
        } finally {
            if (bitmap !== picture) bitmap.recycle()
        }
    }

    private fun transparent(bitmap: Bitmap): Boolean {
        val row = IntArray(bitmap.width)
        for (y in 0 until bitmap.height) {
            bitmap.getPixels(row, 0, bitmap.width, 0, y, bitmap.width, 1)
            if (row.any { (it ushr 24) != 0xFF }) return true
        }
        return false
    }

    private fun extension(name: String) = name.substringAfterLast('.', "").lowercase(Locale.ROOT)

    private fun ByteArray.hex(): String = joinToString("") { "%02x".format(it) }
}
