package com.agentworkspace.mobile.embedded

import android.content.Context
import android.content.Intent
import org.json.JSONObject
import java.io.File

/** All UI settings writes use one reservation coordinator in the UI process. */
object ProviderSettingsChange {
    private val coordinator = ProviderChangeCoordinator()
    @Volatile private var restartingFromToken: String? = null

    fun previousEngineToken(): String? = restartingFromToken

    /**
     * Apply a model or cloud-provider change to the running engine and save it, without a restart.
     * Returns false when this change needs the restart path instead: the on-device model is involved
     * (its weights load at engine start) or the engine cannot be reached. Throws when the engine
     * refuses because tasks are running.
     */
    fun applyWithoutRestart(context: Context, protocol: String, baseUrl: String, model: String,
                            reasoningEffort: String, contextSummaryEnabled: Boolean? = null,
                            allowLanHttp: Boolean? = null): Boolean {
        val application = context.applicationContext
        val current = MobileProviderSettings.load(application)
        val local = MobileProviderSettings.EMBEDDED_QWEN_BASE_URL
        if (current.baseUrl.trimEnd('/') == local || baseUrl.trimEnd('/') == local) return false
        val token = runCatching { File(application.filesDir, "serve.token").readText().trim() }.getOrNull()
            ?.takeIf { it.isNotEmpty() } ?: return false
        val effort = reasoningEffort.takeIf { it in MobileProviderSettings.reasoningEfforts(protocol, baseUrl, model) } ?: "auto"
        val lanHttp = allowLanHttp ?: current.allowLanHttp
        fun payload(protocol: String, baseUrl: String, model: String, effort: String, summary: Boolean?, lan: Boolean) = JSONObject()
            .put("protocol", protocol).put("base_url", baseUrl).put("model", model).put("reasoning_effort", effort)
            .put("allow_lan_http", lan)
            .apply {
                MobileProviderSettings.apiKeyFor(application, protocol, baseUrl)?.let { put("api_key", it) }
                if (summary != null) put("context_summary_enabled", summary)
            }
        val (code, reply) = try {
            post(application, token, "/mobile/provider/apply", payload(protocol, baseUrl, model, effort, contextSummaryEnabled, lanHttp))
        } catch (_: java.io.IOException) {
            return false
        }
        when (code) {
            200 -> Unit
            409 -> return false
            400 -> throw IllegalStateException(
                if (reply.optString("error").contains("finish active"))
                    com.agentworkspace.mobile.UiText.of(application, "请先停止或等待正在运行和排队的任务结束，再切换模型",
                        "Stop or wait for running and queued tasks before switching models")
                else reply.optString("error").ifBlank { "无法切换模型" })
            else -> return false
        }
        try {
            MobileProviderSettings.save(application, protocol, baseUrl, model, null, false, effort,
                contextSummaryEnabled = contextSummaryEnabled, allowLanHttp = lanHttp)
        } catch (failure: Exception) {
            // Keep the engine and the saved settings in agreement: put the engine back.
            runCatching { post(application, token, "/mobile/provider/apply",
                payload(current.protocol, current.baseUrl, current.model, current.reasoningEffort, current.contextSummaryEnabled,
                    current.allowLanHttp)) }
            throw failure
        }
        return true
    }

    private fun post(context: Context, token: String, path: String, body: JSONObject): Pair<Int, JSONObject> {
        val base = EngineAddress.baseUrl(context)
        // The body carries the provider's API key: only the engine that proves it holds the token gets
        // it. Unverified counts as unreachable (an IOException), so the change takes the restart path.
        EngineIdentity.require(base, token, 5000)
        val bytes = body.toString().toByteArray(Charsets.UTF_8)
        val connection = java.net.URL("$base$path").openConnection() as java.net.HttpURLConnection
        try {
            connection.requestMethod = "POST"
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 1500
            connection.readTimeout = 15000
            connection.doOutput = true
            connection.setRequestProperty("Authorization", "Bearer $token")
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            connection.setFixedLengthStreamingMode(bytes.size)
            connection.outputStream.use { it.write(bytes) }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText().take(64 * 1024) }.orEmpty()
            return code to (runCatching { JSONObject(text) }.getOrNull() ?: JSONObject())
        } finally {
            connection.disconnect()
        }
    }

    /**
     * Save a change at once when no engine is serving, and return true: the caller then starts the
     * engine again with it. False when one is serving; [apply] reserves the change with it instead.
     * This is the start-up screen's way out when a setting (an on-device model too large for the
     * phone, say) keeps the engine from starting: [apply] needs the engine and refused there.
     */
    fun saveWithoutEngine(context: Context, save: () -> Unit): Boolean {
        val token = runCatching { File(context.applicationContext.filesDir, "serve.token").readText().trim() }
            .getOrNull()?.takeIf { it.isNotEmpty() }
        if (token != null) return false
        coordinator.changeWithoutEngine(save)
        restartingFromToken = null
        return true
    }

    fun apply(context: Context, requireLocalEngine: Boolean = false, save: () -> Unit) {
        val application = context.applicationContext
        val tokenFile = File(application.filesDir, "serve.token")
        val token = runCatching { tokenFile.readText().trim() }.getOrNull()
            ?.takeIf { it.isNotEmpty() }
            ?: throw IllegalStateException("请先启动并连接本地 Agent 引擎")
        val http = LocalEngineClient(application, fixedToken = token)
        val client = object : ProviderChangeCoordinator.Client {
            override fun prepare(requireLocalEngine: Boolean): String {
                val result = http.request("POST", "/mobile/provider-change/prepare",
                    JSONObject().put("require_local_engine", requireLocalEngine))
                check(result.optBoolean("ok")) { "The engine could not reserve a provider change" }
                return result.getString("lease_id")
            }
            private fun operation(name: String, lease: String): ProviderChangeCoordinator.Reply {
                val result = http.request("POST", "/mobile/provider-change/$name",
                    JSONObject().put("lease_id", lease))
                return ProviderChangeCoordinator.Reply(result.getString("state"),
                    result.optBoolean("restart_required"))
            }
            override fun commit(lease: String) = operation("commit", lease)
            override fun status(lease: String) = operation("status", lease)
            override fun isCurrent(): Boolean = runCatching { tokenFile.readText().trim() == token }
                .getOrDefault(false)
        }
        coordinator.change(client, requireLocalEngine, save) {
            val configuration = MobileProviderSettings.load(application).toJson()
            TermuxDaemonService.start(application, Intent(application, TermuxDaemonService::class.java).apply {
                action = TermuxDaemonService.ACTION_RESTART
                putExtra(TermuxDaemonService.EXTRA_REASON, "provider settings changed (model, key or local engine)")
                putExtra(TermuxDaemonService.EXTRA_PROVIDER_CONFIGURATION, configuration)
                putExtra(TermuxDaemonService.EXTRA_EXPECTED_ENGINE_TOKEN, token)
            })
            restartingFromToken = token
        }
    }
}
