package com.agentworkspace.mobile.workspace

import org.json.JSONObject
import java.util.Locale

data class WorkspaceFileRequest(
    val requestId: String,
    val action: String,
    val path: String,
    val sha256: String?,
    val mimeType: String,
    val workspaceId: String? = null,
) {
    val filename: String get() = path.substringAfterLast('/')

    fun result(ok: Boolean, error: String? = null, cancelled: Boolean = false): JSONObject =
        JSONObject().put("request_id", requestId).put("ok", ok).put("action", action).put("path", path).apply {
            if (workspaceId != null) put("workspace_id", workspaceId)
            if (error != null) put("error", error)
            if (cancelled) put("cancelled", true)
        }

    companion object {
        private val fields = setOf("request_id", "action", "path", "sha256", "mime_type", "workspace_id")
        private val requestIdPattern = Regex("[A-Za-z0-9._:-]{1,128}")
        private val shaPattern = Regex("[a-fA-F0-9]{64}")
        private val privateSegments = setOf(".agent", ".agent-workspace", ".git", "uploads")

        fun parse(json: String): WorkspaceFileRequest {
            require(json.length <= 8192) { "The file action request is too large" }
            val payload = try { JSONObject(json) }
            catch (_: Exception) { throw IllegalArgumentException("The file action request must be JSON") }
            require(payload.keys().asSequence().all { it in fields }) { "Unsupported file action fields" }
            fun string(key: String): String {
                val value = payload.opt(key)
                require(value is String) { "Missing or invalid $key" }
                return value
            }
            val requestId = string("request_id")
            require(requestIdPattern.matches(requestId)) { "Invalid file action request_id" }
            val action = string("action")
            require(action in setOf("open", "share", "save")) { "Unsupported file action" }
            val workspaceId = if (!payload.has("workspace_id") || payload.isNull("workspace_id")) null else string("workspace_id").also {
                require(requestIdPattern.matches(it)) { "Invalid workspace_id" }
            }
            val path = string("path")
            validatePath(path)
            val sha = if (!payload.has("sha256") || payload.isNull("sha256")) null else string("sha256").also {
                require(shaPattern.matches(it)) { "Invalid file SHA-256 digest" }
            }.lowercase(Locale.ROOT)
            val suppliedMime = if (!payload.has("mime_type") || payload.isNull("mime_type")) null else string("mime_type")
            val mime = WorkspaceFileMime.vetted(path, suppliedMime)
            return WorkspaceFileRequest(requestId, action, path, sha, mime, workspaceId)
        }

        private fun validatePath(path: String) {
            require(path.isNotBlank() && path.length <= 2048 && !path.startsWith('/')) {
                "A relative workspace file path is required"
            }
            require(path.none { it.isISOControl() || it in "\\:" }) { "Invalid workspace file path" }
            val segments = path.split('/')
            require(segments.all { it.isNotEmpty() && it != "." && it != ".." && it.lowercase(Locale.ROOT) !in privateSegments }) {
                "The file path cannot access private or parent directories"
            }
        }
    }
}

internal object WorkspaceFileMime {
    private val types = mapOf(
        "pdf" to "application/pdf",
        "docx" to "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx" to "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx" to "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "doc" to "application/msword", "xls" to "application/vnd.ms-excel", "ppt" to "application/vnd.ms-powerpoint",
        "odt" to "application/vnd.oasis.opendocument.text", "ods" to "application/vnd.oasis.opendocument.spreadsheet",
        "odp" to "application/vnd.oasis.opendocument.presentation", "rtf" to "application/rtf", "epub" to "application/epub+zip",
        "txt" to "text/plain", "log" to "text/plain", "md" to "text/markdown", "markdown" to "text/markdown",
        "csv" to "text/csv", "tsv" to "text/tab-separated-values", "json" to "application/json", "xml" to "application/xml",
        "html" to "text/html", "htm" to "text/html", "css" to "text/css", "js" to "text/javascript", "mjs" to "text/javascript",
        "py" to "text/x-python", "yaml" to "application/yaml", "yml" to "application/yaml",
        "png" to "image/png", "jpg" to "image/jpeg", "jpeg" to "image/jpeg", "gif" to "image/gif",
        "webp" to "image/webp", "bmp" to "image/bmp", "svg" to "image/svg+xml", "avif" to "image/avif",
        "ico" to "image/vnd.microsoft.icon", "tif" to "image/tiff", "tiff" to "image/tiff",
        "mp3" to "audio/mpeg", "wav" to "audio/wav", "ogg" to "audio/ogg", "flac" to "audio/flac", "m4a" to "audio/mp4",
        "mp4" to "video/mp4", "webm" to "video/webm", "mov" to "video/quicktime", "mkv" to "video/x-matroska",
        "zip" to "application/zip", "tar" to "application/x-tar", "gz" to "application/gzip", "7z" to "application/x-7z-compressed",
        "rar" to "application/vnd.rar", "bin" to "application/octet-stream",
    )
    private val aliases = mapOf(
        "text/markdown" to setOf("text/plain", "text/x-markdown"),
        "text/javascript" to setOf("application/javascript", "application/x-javascript"),
        "application/xml" to setOf("text/xml"), "application/yaml" to setOf("text/yaml", "text/x-yaml"),
        "application/rtf" to setOf("text/rtf"), "audio/wav" to setOf("audio/x-wav", "audio/vnd.wave"),
        "audio/flac" to setOf("audio/x-flac"),
        "image/bmp" to setOf("image/x-ms-bmp"), "image/vnd.microsoft.icon" to setOf("image/x-icon"),
        "application/gzip" to setOf("application/x-gzip"), "application/vnd.rar" to setOf("application/x-rar-compressed"),
    )

    fun vetted(path: String, supplied: String?): String {
        val expected = types[path.substringAfterLast('.', "").lowercase(Locale.ROOT)]
        if (supplied == null || supplied == "application/octet-stream") return expected ?: "application/octet-stream"
        val mime = supplied.lowercase(Locale.ROOT)
        require(mime.length <= 128 && Regex("[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+").matches(mime) &&
            mime != "application/vnd.android.package-archive") { "Unsupported file type" }
        if (expected == null) return "application/octet-stream"
        require(mime == expected || mime in aliases[expected].orEmpty()) {
            "The file type does not match its filename"
        }
        return expected
    }
}
