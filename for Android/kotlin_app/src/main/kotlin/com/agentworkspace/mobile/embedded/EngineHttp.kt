package com.agentworkspace.mobile.embedded

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** Calls to the local engine that need its status code and error message (LocalEngineClient drops both). */
object EngineHttp {
    data class Reply(val code: Int, val body: JSONObject) {
        val ok get() = code in 200..299
        val error get() = body.optString("error").ifBlank { "The local engine answered $code" }
    }

    fun token(context: Context): String = File(context.filesDir, "serve.token").readText().trim()
        .also { require(it.isNotEmpty()) { "The engine token is unavailable" } }

    fun request(context: Context, method: String, path: String, body: JSONObject? = null, readTimeoutMs: Int = 15000): Reply {
        require(path.startsWith("/") && !path.startsWith("//")) { "Invalid local route" }
        val connection = URL("http://127.0.0.1:8080$path").openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 1500
            connection.readTimeout = readTimeoutMs
            connection.setRequestProperty("Authorization", "Bearer ${token(context)}")
            if (body != null) {
                val bytes = body.toString().toByteArray(Charsets.UTF_8)
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.setFixedLengthStreamingMode(bytes.size)
                connection.outputStream.use { it.write(bytes) }
            }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { reader ->
                val buffer = CharArray(8192)
                val value = StringBuilder()
                while (true) {
                    val count = reader.read(buffer)
                    if (count < 0) break
                    check(value.length + count <= 8 * 1024 * 1024) { "Local response is too large" }
                    value.append(buffer, 0, count)
                }
                value.toString()
            }.orEmpty()
            return Reply(code, runCatching { JSONObject(text) }.getOrNull() ?: JSONObject())
        } finally {
            connection.disconnect()
        }
    }
}
