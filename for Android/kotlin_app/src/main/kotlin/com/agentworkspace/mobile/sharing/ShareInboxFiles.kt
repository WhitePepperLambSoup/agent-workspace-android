package com.agentworkspace.mobile.sharing

import java.io.File
import java.io.IOException
import java.io.InputStream
import java.nio.channels.Channels
import java.nio.channels.FileChannel
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.StandardOpenOption
import java.security.MessageDigest
import java.util.Locale

data class StagedShareFile(val file: File, val size: Long, val sha256: String)

/** Bounded stream staging used before the user chooses a workspace and session. */
object ShareInboxFiles {
    private const val BUFFER_SIZE = 64 * 1024
    private val reservedNames = setOf("CON", "PRN", "AUX", "NUL") +
        (1..9).flatMap { listOf("COM$it", "LPT$it") }

    fun copy(root: File, id: String, input: InputStream, expectedLength: Long = -1L): StagedShareFile {
        require(id.matches(Regex("[A-Za-z0-9._-]{1,128}"))) { "Invalid staged file identity" }
        require(expectedLength >= -1L) { "Invalid staged file length" }
        check(root.canonicalFile == root.absoluteFile && (root.isDirectory || root.mkdirs()) && !Files.isSymbolicLink(root.toPath())) {
            "Share inbox is unavailable"
        }
        if (expectedLength > 0 && root.usableSpace < expectedLength) throw IOException("设备存储空间不足")
        val partial = File(root, "$id.partial")
        val output = File(root, "$id.file")
        val digest = MessageDigest.getInstance("SHA-256")
        var size = 0L
        var createdPartial = false
        var published = false
        try {
            input.use { source ->
                if (Files.exists(output.toPath(), LinkOption.NOFOLLOW_LINKS)) throw IOException("分享文件已存在")
                FileChannel.open(partial.toPath(), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE,
                    LinkOption.NOFOLLOW_LINKS).use { channel ->
                createdPartial = true
                val target = Channels.newOutputStream(channel)
                val buffer = ByteArray(BUFFER_SIZE)
                while (true) {
                    if (Thread.currentThread().isInterrupted) throw IOException("分享文件导入已取消")
                    val count = source.read(buffer)
                    if (count < 0) break
                    if (count == 0) continue
                    if (Long.MAX_VALUE - size < count) throw IOException("分享文件长度无效")
                    size += count
                    if (expectedLength >= 0 && size > expectedLength) throw IOException("分享文件读取长度不一致")
                    if (root.usableSpace < count.toLong()) throw IOException("设备存储空间不足")
                    digest.update(buffer, 0, count)
                    target.write(buffer, 0, count)
                }
                channel.force(true)
            } }
            if (expectedLength >= 0 && size != expectedLength) throw IOException("分享文件读取不完整")
            Files.move(partial.toPath(), output.toPath())
            published = true
            check(output.setReadOnly()) { "分享文件无法安全保存" }
            return StagedShareFile(output, size, digest.digest().hex())
        } catch (failure: Exception) {
            if (createdPartial) partial.delete()
            if (published) output.delete()
            if (failure is IOException) throw failure
            throw IOException("分享文件无法保存", failure)
        }
    }

    fun safeName(raw: String): String {
        val base = raw.substringAfterLast('/').substringAfterLast('\\').trim()
            .filter { !it.isISOControl() && it !in "<>:\"/\\|?*" }
            .trimEnd('.', ' ')
            .ifEmpty { "shared-file" }
        val stem = base.substringBeforeLast('.', base).ifEmpty { "shared-file" }
        val extension = base.substringAfterLast('.', "").let { if (it.length <= 32 && it.isNotEmpty()) ".${it}" else "" }
        val safeStem = if (stem.substringBefore('.').uppercase(Locale.ROOT) in reservedNames) "file-$stem" else stem
        val name = "$safeStem$extension"
        if (name.toByteArray(Charsets.UTF_8).size <= 255 && name.codePointCount(0, name.length) <= 180) return name
        val suffix = extension
        val digest = MessageDigest.getInstance("SHA-256").digest(raw.toByteArray(Charsets.UTF_8)).hex().take(16)
        val limit = (255 - suffix.toByteArray(Charsets.UTF_8).size - digest.length - 1).coerceAtLeast(8)
        val codePointLimit = 180 - suffix.codePointCount(0, suffix.length) - digest.length - 1
        val kept = StringBuilder()
        for (codePoint in safeStem.codePoints().toArray()) {
            val candidate = kept.toString() + String(Character.toChars(codePoint))
            if (candidate.toByteArray(Charsets.UTF_8).size > limit || candidate.codePointCount(0, candidate.length) > codePointLimit) break
            kept.appendCodePoint(codePoint)
        }
        return "${kept.ifEmpty { "shared" }}-$digest$suffix"
    }

    private fun ByteArray.hex(): String = joinToString("") { "%02x".format(it) }
}
