package com.agentworkspace.mobile.sharing

import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.URLEncoder
import java.nio.file.Files
import java.nio.file.LinkOption
import java.security.MessageDigest

internal class InboxTransferFailure(message: String, val uncertain: Boolean = false, cause: Throwable? = null) :
    IOException(message, cause)

internal class ShareInboxUpload(private val tokenFile: File, private val baseUrl: String = "http://127.0.0.1:8080",
    private val fixedToken: String? = null) {
    init {
        val uri = URI(baseUrl)
        require(uri.scheme == "http" && uri.host == "127.0.0.1" && uri.port in 1..65535 &&
            uri.userInfo == null && uri.rawQuery == null && uri.fragment == null && uri.path.isEmpty())
    }

    fun validateTarget(workspaceId: String, sessionId: String) {
        val response = get("/sessions?workspace_id=${encode(workspaceId)}")
        val sessions = response.getJSONArray("sessions")
        require((0 until sessions.length()).any { index ->
            val session = sessions.getJSONObject(index)
            session.optString("id") == sessionId && session.optString("workspace_id") == workspaceId
        }) { "所选会话不属于此工作区，请重新选择" }
    }

    fun upload(item: InboxItem, file: File): JSONObject {
        require(item.kind == "file" && item.workspaceId != null && item.sessionId != null && item.size >= 0 &&
            item.sha256.matches(Regex("[a-f0-9]{64}"))) { "文件尚未准备完成" }
        check(Files.isRegularFile(file.toPath(), LinkOption.NOFOLLOW_LINKS) && file.canonicalFile == file.absoluteFile &&
            file.length() == item.size) { "待导入文件已变化，请重新分享" }
        val path = "/mobile/attachments/upload?session_id=${encode(item.sessionId)}" +
            "&workspace_id=${encode(item.workspaceId)}&filename=${encode(item.name)}" +
            "&media_type=${encode(item.mediaType)}&request_id=${encode(item.uploadRequestId)}"
        val connection = connection(path)
        var mayHaveSubmitted = false
        var explicitRejection = false
        try {
            connection.requestMethod = "POST"
            connection.doOutput = true
            connection.readTimeout = 30000
            connection.setRequestProperty("Content-Type", item.mediaType)
            connection.setFixedLengthStreamingMode(item.size)
            connection.connect()
            mayHaveSubmitted = true
            val digest = MessageDigest.getInstance("SHA-256")
            var copied = 0L
            file.inputStream().use { input -> connection.outputStream.use { output ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    if (Thread.currentThread().isInterrupted) throw IOException("文件导入被中断")
                    val count = input.read(buffer)
                    if (count < 0) break
                    if (count == 0) continue
                    copied += count
                    if (copied > item.size) throw IOException("待导入文件已变化")
                    digest.update(buffer, 0, count)
                    output.write(buffer, 0, count)
                }
                check(copied == item.size && hex(digest.digest()) == item.sha256) { "待导入文件校验失败" }
            } }
            val status = connection.responseCode
            if (status != 201) {
                explicitRejection = status in 400..499 || status == 507
                throw InboxTransferFailure(when (status) {
                    401 -> "本地服务凭据失效，请等待服务恢复后重试"
                    404 -> "所选工作区或会话已不存在"
                    409 -> "导入请求与原文件不一致，请保留此项并重新分享文件"
                    507 -> "工作区存储空间不足"
                    else -> "本地服务未能确认文件导入，请重试"
                }, uncertain = !explicitRejection)
            }
            val receipt = connection.inputStream.use { JSONObject(String(it.readBytesLimited(64 * 1024), Charsets.UTF_8)) }
            validateReceipt(item, receipt)
            return JSONObject().put("name", receipt.getString("name")).put("path", receipt.getString("path"))
                .put("size", receipt.getLong("size")).put("sha256", receipt.getString("sha256"))
                .put("media_type", receipt.getString("media_type"))
        } catch (failure: InboxTransferFailure) {
            throw failure
        } catch (failure: Exception) {
            throw InboxTransferFailure(if (mayHaveSubmitted && !explicitRejection)
                "导入结果尚未确认，重试会核实同一次请求" else "无法连接本地服务，请稍后重试",
                uncertain = mayHaveSubmitted && !explicitRejection, cause = failure)
        } finally { connection.disconnect() }
    }

    private fun get(path: String): JSONObject {
        val connection = connection(path)
        try {
            connection.requestMethod = "GET"
            check(connection.responseCode == 200) { "无法核实所选工作区和会话" }
            return connection.inputStream.use { JSONObject(String(it.readBytesLimited(ShareInboxStore.MAX_METADATA_BYTES), Charsets.UTF_8)) }
        } finally { connection.disconnect() }
    }

    private fun connection(path: String): HttpURLConnection {
        val token = fixedToken ?: tokenFile.inputStream().use { String(it.readBytesLimited(4096), Charsets.UTF_8).trim() }
        require(token.isNotEmpty() && token.none { it == '\r' || it == '\n' }) { "本地服务尚未就绪" }
        return (URL(baseUrl + path).openConnection() as HttpURLConnection).apply {
            instanceFollowRedirects = false
            setRequestProperty("Authorization", "Bearer $token")
            connectTimeout = 3000
            readTimeout = 10000
        }
    }

    companion object {
        fun validateReceipt(item: InboxItem, receipt: JSONObject) {
            require(receipt.opt("name") is String && receipt.getString("name") == item.name &&
                receipt.opt("size") is Number && receipt.getLong("size") == item.size &&
                receipt.optString("sha256") == item.sha256 &&
                receipt.optString("request_id") == item.uploadRequestId) { "文件导入回执与原文件不一致" }
            val actualMime = receipt.opt("media_type") as? String ?: throw IllegalArgumentException("缺少文件类型")
            require(actualMime.length <= 128 && actualMime.matches(Regex("[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+"))) {
                "文件导入回执媒体类型无效"
            }
            val path = receipt.getString("path")
            require(path.length <= 2048 && path.startsWith("uploads/") && path.none { it.isISOControl() || it in "\\:" } &&
                path.split('/').all { it.isNotEmpty() && it != "." && it != ".." } && path.substringAfterLast('/') == item.name) {
                "文件导入回执路径无效"
            }
        }

        private fun encode(value: String): String = URLEncoder.encode(value, "UTF-8")
        fun hex(bytes: ByteArray): String = bytes.joinToString("") { "%02x".format(it) }
    }
}
