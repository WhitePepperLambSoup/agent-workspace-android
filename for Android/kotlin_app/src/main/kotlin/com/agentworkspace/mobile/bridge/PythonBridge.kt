package com.agentworkspace.mobile.bridge

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

/**
 * Kotlin 与嵌入式 Termux Python Agent 引擎的通信桥梁。
 *
 * The daemon exposes the same authenticated Serve API used by the WebView. The
 * native fallback therefore creates or reuses a real persisted session instead
 * of posting to the old mock `/run` route.
 */
object PythonBridge {

    private const val BASE_URL = "http://127.0.0.1:8080"

    /** Backward-compatible overload for callers that do not have an Activity context. */
    fun executePromptFlow(sessionId: String, prompt: String): Flow<AgentStreamChunk> =
        executePromptFlowInternal(context = null, sessionId = sessionId, prompt = prompt)

    /** Execute a prompt using the daemon token and a persisted session. */
    fun executePromptFlow(
        context: Context,
        sessionId: String? = null,
        prompt: String,
    ): Flow<AgentStreamChunk> = executePromptFlowInternal(
        context = context,
        sessionId = sessionId,
        prompt = prompt,
    )

    private fun executePromptFlowInternal(
        context: Context?,
        sessionId: String?,
        prompt: String,
    ): Flow<AgentStreamChunk> = flow {
        emit(AgentStreamChunk.Thinking("正在分析任务意图并调度本地 Termux 引擎..."))

        val response = withContext(Dispatchers.IO) {
            try {
                val token = context?.let(::readServeToken).orEmpty()
                if (token.isBlank()) {
                    throw IOException("本地服务凭据尚未就绪，请稍后重试")
                }
                val resolvedSessionId = ensureSession(token, sessionId)
                requestJson(
                    url = "$BASE_URL/sessions/${encodePathSegment(resolvedSessionId)}/run",
                    token = token,
                    payload = JSONObject().put("prompt", prompt),
                )
            } catch (e: Exception) {
                JSONObject().put("__error", e.message ?: "本地服务请求失败")
            }
        }

        val error = response.optString("__error")
        if (error.isNotEmpty()) {
            emit(AgentStreamChunk.Error(error))
            return@flow
        }

        val status = response.optString("status")
        if (status == "error") {
            emit(AgentStreamChunk.Error(response.optString("error", "执行失败")))
            return@flow
        }

        val responseObject = response.optJSONObject("response")
        val reasoning = responseObject?.optString("reasoning")
        val text = response.optString("text").ifEmpty {
            responseObject?.optString("text") ?: "执行完成"
        }
        if (!reasoning.isNullOrEmpty()) {
            emit(AgentStreamChunk.Thinking(reasoning))
        }
        emit(AgentStreamChunk.Answer(text))
    }.flowOn(Dispatchers.IO)

    private fun readServeToken(context: Context): String? {
        val tokenFile = File(context.filesDir, "serve.token")
        if (!tokenFile.isFile) return null
        return runCatching { tokenFile.readText(Charsets.UTF_8).trim() }
            .getOrNull()
            ?.takeIf { it.isNotEmpty() }
    }

    private fun ensureSession(token: String, preferredId: String?): String {
        if (!preferredId.isNullOrBlank()) {
            val sessions = requestJson("$BASE_URL/sessions", token, null)
                .optJSONArray("sessions")
            for (index in 0 until (sessions?.length() ?: 0)) {
                if (sessions?.optJSONObject(index)?.optString("id") == preferredId) {
                    return preferredId
                }
            }
        }
        val created = requestJson(
            url = "$BASE_URL/sessions",
            token = token,
            payload = JSONObject().put("title", "Android Native"),
        )
        return created.optString("id").takeIf { it.isNotEmpty() }
            ?: throw IOException("服务未返回有效会话 ID")
    }

    private fun requestJson(
        url: String,
        token: String,
        payload: JSONObject?,
    ): JSONObject {
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = if (payload == null) "GET" else "POST"
            setRequestProperty("Authorization", "Bearer $token")
            setRequestProperty("Accept", "application/json")
            connectTimeout = 5000
            readTimeout = 60000
            doInput = true
            doOutput = payload != null
            if (payload != null) setRequestProperty("Content-Type", "application/json")
        }
        try {
            if (payload != null) {
                OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                    writer.write(payload.toString())
                }
            }
            val stream = if (connection.responseCode in 200..299) {
                connection.inputStream
            } else {
                connection.errorStream ?: connection.inputStream
            }
            val body = InputStreamReader(stream, Charsets.UTF_8).use { it.readText() }
            if (connection.responseCode !in 200..299) {
                throw IOException("HTTP ${connection.responseCode}: ${body.take(500)}")
            }
            return JSONObject(body)
        } finally {
            connection.disconnect()
        }
    }

    private fun encodePathSegment(value: String): String =
        java.net.URLEncoder.encode(value, Charsets.UTF_8.name())
            .replace("+", "%20")
}

sealed class AgentStreamChunk {
    data class Thinking(val text: String) : AgentStreamChunk()
    data class ToolCall(val toolName: String, val args: String) : AgentStreamChunk()
    data class Answer(val text: String) : AgentStreamChunk()
    data class Error(val message: String) : AgentStreamChunk()
}
