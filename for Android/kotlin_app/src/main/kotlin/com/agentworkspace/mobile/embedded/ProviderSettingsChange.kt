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
            application.startForegroundService(Intent(application, TermuxDaemonService::class.java).apply {
                action = TermuxDaemonService.ACTION_RESTART
                putExtra(TermuxDaemonService.EXTRA_PROVIDER_CONFIGURATION, configuration)
                putExtra(TermuxDaemonService.EXTRA_EXPECTED_ENGINE_TOKEN, token)
            })
            restartingFromToken = token
        }
    }
}
