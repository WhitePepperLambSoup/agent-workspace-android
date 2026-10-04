package com.agentworkspace.mobile.workspace

import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import androidx.core.content.FileProvider
import java.io.Closeable
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.nio.file.Files
import java.security.MessageDigest
import java.util.UUID

data class CachedWorkspaceFile(val file: File, val mimeType: String, val sha256: String, val size: Long)

class WorkspaceFileDownloadStore @JvmOverloads constructor(
    context: Context,
    private val tokenFile: File = File(context.filesDir, "serve.token"),
    private val baseUrl: String = "http://127.0.0.1:8080",
) {
    private val context = context.applicationContext
    private val root: File get() = WorkspaceFileCache.root(context)

    init {
        val gateway = runCatching { URI(baseUrl) }.getOrNull()
        require(gateway?.scheme == "http" && gateway.host == "127.0.0.1" && gateway.port in 1..65535 &&
            gateway.userInfo == null && gateway.rawQuery == null && gateway.rawFragment == null && gateway.path.isNullOrEmpty()) {
            "Only the local runtime gateway can download workspace files"
        }
    }

    @Synchronized
    fun download(request: WorkspaceFileRequest): CachedWorkspaceFile {
        val token = runCatching { tokenFile.readText(Charsets.UTF_8).trim() }.getOrNull()
        check(!token.isNullOrEmpty() && token.length <= 4096 && token.none { it.isISOControl() }) {
            "The local engine is not ready; try again when it is running"
        }
        val url = Uri.parse(baseUrl).buildUpon().appendPath("mobile").appendPath("workspace").appendPath("download")
            .appendQueryParameter("path", request.path).apply {
                request.sha256?.let { appendQueryParameter("sha256", it) }
                request.workspaceId?.let { appendQueryParameter("workspace_id", it) }
            }.build().toString()
        val connection = URL(url).openConnection() as HttpURLConnection
        var directory: File? = null
        try {
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 5000
            connection.readTimeout = 30000
            connection.requestMethod = "GET"
            connection.setRequestProperty("Authorization", "Bearer $token")
            connection.setRequestProperty("Accept-Encoding", "identity")
            when (connection.responseCode) {
                200 -> Unit
                404 -> throw IOException("This file no longer exists; refresh the task files")
                409 -> throw IOException("This file changed; refresh the task files before exporting it")
                401, 403 -> throw IOException("The local engine session expired; try again when it is ready")
                else -> throw IOException("The local engine could not download this file")
            }
            val expectedSize = connection.contentLengthLong
            check(expectedSize >= -1) { "The downloaded file length is invalid" }
            WorkspaceFileCache.prepare(root, expectedSize.coerceAtLeast(0))
            directory = File(root, UUID.randomUUID().toString()).apply {
                check(mkdir() && canonicalFile == absoluteFile && !Files.isSymbolicLink(toPath())) {
                    "The private export cache is unavailable"
                }
            }
            val pin = WorkspaceFileCache.pin(directory)
            try {
                val partial = File(directory, ".partial")
                val digest = MessageDigest.getInstance("SHA-256")
                var size = 0L
                connection.inputStream.buffered(65536).use { input ->
                    partial.outputStream().buffered(65536).use { output ->
                        val buffer = ByteArray(65536)
                        while (true) {
                            if (Thread.currentThread().isInterrupted) throw IOException("File export was interrupted")
                            val count = input.read(buffer)
                            if (count < 0) break
                            if (count == 0) continue
                            check(Long.MAX_VALUE - size >= count) { "The downloaded file length is invalid" }
                            size += count
                            check(expectedSize < 0 || size <= expectedSize) { "The downloaded file exceeded its declared length" }
                            WorkspaceFileCache.checkFreeSpace(root, count.toLong())
                            digest.update(buffer, 0, count)
                            output.write(buffer, 0, count)
                        }
                    }
                }
                check(expectedSize < 0 || size == expectedSize) { "The file download was incomplete; try again" }
                val sha = digest.digest().hex()
                check(request.sha256 == null || request.sha256 == sha) {
                    "This file changed; refresh the task files before exporting it"
                }
                WorkspaceFileCache.checkFreeSpace(root)
                val file = File(directory, safeFilename(request.filename))
                check(partial.renameTo(file) && file.setReadOnly()) { "The downloaded file could not be secured" }
                directory.setLastModified(System.currentTimeMillis())
                return CachedWorkspaceFile(file, request.mimeType, sha, size)
            } finally { pin.close() }
        } catch (failure: Exception) {
            directory?.let { WorkspaceFileCache.discard(it) }
            throw failure
        } finally { connection.disconnect() }
    }

    fun save(file: CachedWorkspaceFile, destination: Uri) {
        require(destination.scheme == "content") { "The system file picker returned an invalid location" }
        WorkspaceFileCache.pin(file.file.parentFile!!).use {
            verify(file)
            try {
                val digest = MessageDigest.getInstance("SHA-256")
                var size = 0L
                val output = context.contentResolver.openOutputStream(destination, "wt")
                    ?: throw IOException("The selected document could not be opened for writing")
                output.use { target ->
                    file.file.inputStream().buffered(65536).use { input ->
                        val buffer = ByteArray(65536)
                        while (true) {
                            if (Thread.currentThread().isInterrupted) throw IOException("File saving was interrupted")
                            val count = input.read(buffer)
                            if (count < 0) break
                            if (count == 0) continue
                            check(Long.MAX_VALUE - size >= count) { "The cached file length is invalid" }
                            size += count
                            check(size <= file.size) { "The cached file changed; try exporting it again" }
                            digest.update(buffer, 0, count)
                            target.write(buffer, 0, count)
                        }
                    }
                    target.flush()
                }
                check(size == file.size && digest.digest().hex() == file.sha256) {
                    "The cached file changed; try exporting it again"
                }
            } catch (failure: Exception) {
                runCatching { DocumentsContract.deleteDocument(context.contentResolver, destination) }
                throw failure
            }
        }
    }

    fun verify(file: CachedWorkspaceFile) {
        val resolved = WorkspaceFileCache.checkedFile(context, file.file)
        check(resolved.length() == file.size && resolved.isFile) { "The cached file is unavailable; export it again" }
        val digest = MessageDigest.getInstance("SHA-256")
        resolved.inputStream().buffered(65536).use { input ->
            val buffer = ByteArray(65536)
            while (true) {
                if (Thread.currentThread().isInterrupted) throw IOException("File verification was interrupted")
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        check(digest.digest().hex() == file.sha256) { "The cached file changed; try exporting it again" }
    }

    private fun safeFilename(name: String): String {
        if (name.toByteArray(Charsets.UTF_8).size <= 200 && name != ".partial") return name
        val extension = name.substringAfterLast('.', "").take(16)
        val stem = "artifact-" + MessageDigest.getInstance("SHA-256").digest(name.toByteArray(Charsets.UTF_8)).hex().take(16)
        return if (extension.isEmpty()) stem else "$stem.$extension"
    }
}

private fun ByteArray.hex(): String = joinToString("") { "%02x".format(it) }

internal object WorkspaceFileCache {
    private const val MAX_CACHE_BYTES = 1024L * 1024 * 1024
    private const val MIN_FREE_BYTES = 32L * 1024 * 1024
    private const val MAX_FILES = 32
    private const val EXPORT_GRACE_MS = 24L * 60 * 60 * 1000
    private val directoryPattern = Regex("[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")
    private val pins = mutableMapOf<String, Int>()

    fun root(context: Context): File {
        val cache = context.cacheDir.canonicalFile
        val root = File(cache, "generated-files")
        check(root.canonicalFile == root && !Files.isSymbolicLink(root.toPath()) && (root.isDirectory || root.mkdirs())) {
            "The private export cache is unavailable"
        }
        return root
    }

    fun checkedFile(context: Context, file: File): File {
        val root = root(context)
        val absolute = file.absoluteFile
        val directory = absolute.parentFile ?: throw IllegalArgumentException("Invalid export file")
        require(directory.parentFile == root && directoryPattern.matches(directory.name) &&
            directory.canonicalFile == directory && absolute.canonicalFile == absolute &&
            !Files.isSymbolicLink(directory.toPath()) && !Files.isSymbolicLink(absolute.toPath()) && absolute.name != ".partial") {
            "Invalid export file"
        }
        return absolute
    }

    fun uriFile(context: Context, uri: Uri): File {
        require(uri.scheme == "content" && uri.authority == context.packageName + ".workspace-files") { "Invalid export URI" }
        val segments = uri.pathSegments
        require(segments.size == 3 && segments[0] == "generated_files" &&
            directoryPattern.matches(segments[1]) && segments[2].isNotEmpty() &&
            segments[2].none { it == '/' || it == '\\' || it.isISOControl() }) { "Invalid export URI" }
        val file = checkedFile(context, File(File(root(context), segments[1]), segments[2]))
        require(FileProvider.getUriForFile(context, context.packageName + ".workspace-files", file) == uri) { "Invalid export URI" }
        return file
    }

    @Synchronized
    fun pin(directory: File): Closeable {
        val key = directory.canonicalPath
        pins[key] = pins.getOrDefault(key, 0) + 1
        var closed = false
        return Closeable {
            synchronized(this) {
                if (!closed) {
                    val count = pins.getOrDefault(key, 1) - 1
                    if (count <= 0) pins.remove(key) else pins[key] = count
                    closed = true
                }
            }
        }
    }

    @Synchronized
    fun retain(file: File) { file.parentFile?.setLastModified(System.currentTimeMillis()) }

    @Synchronized
    fun prepare(root: File, incomingSize: Long) {
        require(incomingSize >= 0) { "The downloaded file length is invalid" }
        val entries = root.listFiles().orEmpty().filter { directoryPattern.matches(it.name) &&
            it.isDirectory && it.canonicalFile == it && !Files.isSymbolicLink(it.toPath()) }.sortedBy { it.lastModified() }
        var bytes = entries.sumOf { directory -> directory.listFiles().orEmpty().filter { it.isFile }.sumOf { it.length() } }
        var count = entries.size
        val cutoff = System.currentTimeMillis() - EXPORT_GRACE_MS
        for (directory in entries) {
            val withinBudget = incomingSize <= MAX_CACHE_BYTES && bytes <= MAX_CACHE_BYTES - incomingSize
            val free = root.usableSpace
            val enoughSpace = free >= MIN_FREE_BYTES && incomingSize <= free - MIN_FREE_BYTES
            if (count < MAX_FILES && withinBudget && enoughSpace) break
            if (directory.lastModified() >= cutoff || pins.getOrDefault(directory.canonicalPath, 0) > 0) continue
            val size = directory.listFiles().orEmpty().filter { it.isFile }.sumOf { it.length() }
            if (directory.deleteRecursively()) { bytes -= size; count-- }
        }
        check(count < MAX_FILES) {
            "The export cache is full while recently shared files are retained; try again later"
        }
        // The cache budget controls eviction; a large file is limited by actual storage.
        checkFreeSpace(root, incomingSize)
    }

    fun checkFreeSpace(root: File, incomingSize: Long = 0) {
        require(incomingSize >= 0) { "The downloaded file length is invalid" }
        val free = root.usableSpace
        check(free >= MIN_FREE_BYTES && incomingSize <= free - MIN_FREE_BYTES) {
            "There is not enough device storage to finish exporting this file"
        }
    }

    @Synchronized
    fun discard(directory: File) {
        if (pins.getOrDefault(directory.canonicalPath, 0) == 0) directory.deleteRecursively()
    }
}
