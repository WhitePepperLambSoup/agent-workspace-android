package com.agentworkspace.mobile.embedded

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

class LocalEngineClient @JvmOverloads constructor(context: Context,
    private val tokenFile: File = File(context.filesDir, "serve.token"),
    /** Null: the engine's address at each request (EngineAddress), beside the token file. */
    private val baseUrl: String? = null,
    private val fixedToken: String? = null) {
    class RequestOutcomeUnknown(message: String, cause: Throwable? = null) :
        IllegalStateException(message, cause)

    fun request(method: String, path: String, payload: JSONObject? = null): JSONObject {
        require(path.startsWith("/") && !path.startsWith("//")) { "Invalid local route" }
        val token = fixedToken ?: tokenFile.readText().trim()
        require(token.isNotEmpty()) { "The engine token is unavailable" }
        val body = payload?.toString()?.toByteArray(Charsets.UTF_8)
        val base = baseUrl ?: EngineAddress.baseUrl(tokenFile.absoluteFile.parentFile ?: File("."))
        // Before connecting, so a refusal cannot have applied anything: the token goes only to the
        // engine that proves it holds it, not to another app on the port (EngineIdentity).
        EngineIdentity.require(base, token, 5000)
        val connection = URL(base + path).openConnection() as HttpURLConnection
        var mayHaveSubmitted = false
        var rejected = false
        try {
            connection.requestMethod = method
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("Authorization", "Bearer $token")
            connection.connectTimeout = 1500
            connection.readTimeout = 5000
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                // Streaming prevents a buffered POST from being replayed when
                // the engine applied it but its response was lost.
                connection.setFixedLengthStreamingMode(body.size)
            }
            connection.connect()
            // A failure before connecting cannot have applied this request.
            // Once connected, a mutation may reach the engine even if its
            // write or reply subsequently fails.
            mayHaveSubmitted = method !in setOf("GET", "HEAD") || body != null
            if (body != null) {
                connection.outputStream.use { it.write(body) }
            }
            rejected = connection.responseCode !in 200..299
            check(!rejected) { "The local engine rejected the request" }
            return connection.inputStream.bufferedReader(Charsets.UTF_8).use { reader ->
                val buffer = CharArray(8192)
                val value = StringBuilder()
                while (true) {
                    val count = reader.read(buffer)
                    if (count < 0) break
                    check(value.length + count <= 1024 * 1024) { "Local response is too large" }
                    value.append(buffer, 0, count)
                }
                JSONObject(value.toString())
            }
        } catch (failure: Exception) {
            if (failure is java.net.ConnectException) EngineIdentity.forget(base, token)
            if (mayHaveSubmitted && !rejected)
                throw RequestOutcomeUnknown("The local request may have been applied, but its reply could not be confirmed", failure)
            throw failure
        } finally { connection.disconnect() }
    }
}
