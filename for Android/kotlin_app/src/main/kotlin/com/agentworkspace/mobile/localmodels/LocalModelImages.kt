package com.agentworkspace.mobile.localmodels

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject

/** Decode bounded imported image files to the RGB input accepted by mtmd. */
object LocalModelImages {
    const val MAX_IMAGES = 4
    const val MAX_IMAGE_BYTES = 5 * 1024 * 1024
    const val MAX_TOTAL_BYTES = 20 * 1024 * 1024
    const val MAX_EDGE = 512
    private val mediaTypes = setOf("image/png", "image/jpeg", "image/webp", "image/gif")

    fun count(request: JSONObject): Int {
        if (!request.has("encoded_images")) return 0
        val images = request.opt("encoded_images") as? JSONArray
            ?: throw IllegalArgumentException("Invalid local image array")
        require(images.length() in 1..MAX_IMAGES) { "Attach one to four images" }
        return images.length()
    }

    fun prepare(request: JSONObject): Array<ByteArray> {
        val count = count(request)
        if (count == 0) return emptyArray()
        val encoded = request.getJSONArray("encoded_images")
        val metadata = JSONArray()
        var totalBytes = 0
        val rgbImages = Array(count) { index ->
            val image = encoded.optJSONObject(index)
                ?: throw IllegalArgumentException("Invalid local image entry")
            val mediaType = image.opt("media_type") as? String
            require(mediaType in mediaTypes) { "Unsupported local image format" }
            val text = image.opt("base64") as? String
                ?: throw IllegalArgumentException("Invalid local image encoding")
            require(text.isNotEmpty() && text.length <= ((MAX_IMAGE_BYTES + 2) / 3) * 4 &&
                text.length % 4 == 0 && text.matches(Regex("[A-Za-z0-9+/]+={0,2}")))
                { "Local image exceeds its encoded file limit" }
            val bytes = Base64.decode(text, Base64.NO_WRAP)
            totalBytes += bytes.size
            require(bytes.size in 1..MAX_IMAGE_BYTES && totalBytes <= MAX_TOTAL_BYTES)
                { "Local images exceed their bounded file limits" }
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
            require(bounds.outWidth in 1..20000 && bounds.outHeight in 1..20000 &&
                bounds.outWidth.toLong() * bounds.outHeight <= 64L * 1024 * 1024 &&
                bounds.outMimeType == mediaType) { "Local image header or dimensions are invalid" }
            var sample = 1
            while (bounds.outWidth / sample > MAX_EDGE || bounds.outHeight / sample > MAX_EDGE)
                sample *= 2
            val options = BitmapFactory.Options().apply {
                inSampleSize = sample
                inPreferredConfig = Bitmap.Config.ARGB_8888
            }
            val decoded = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
                ?: throw IllegalArgumentException("Local image could not be decoded")
            val bitmap = if (decoded.width <= MAX_EDGE && decoded.height <= MAX_EDGE) decoded
                else {
                    val ratio = MAX_EDGE.toDouble() / maxOf(decoded.width, decoded.height)
                    Bitmap.createScaledBitmap(decoded, maxOf(1, (decoded.width * ratio).toInt()),
                        maxOf(1, (decoded.height * ratio).toInt()), true).also { decoded.recycle() }
                }
            try {
                val pixels = IntArray(bitmap.width * bitmap.height)
                bitmap.getPixels(pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
                val rgb = ByteArray(pixels.size * 3)
                for (pixel in pixels.indices) {
                    val color = pixels[pixel]
                    val alpha = color ushr 24
                    for (channel in 0..2) {
                        val value = (color ushr (16 - channel * 8)) and 255
                        rgb[pixel * 3 + channel] =
                            ((value * alpha + 255 * (255 - alpha) + 127) / 255).toByte()
                    }
                }
                metadata.put(JSONObject().put("width", bitmap.width).put("height", bitmap.height))
                rgb
            } finally { bitmap.recycle() }
        }
        request.remove("encoded_images")
        request.put("images", metadata)
        return rgbImages
    }
}
