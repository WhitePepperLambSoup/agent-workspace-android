package com.agentworkspace.mobile.localmodels

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.net.Uri
import android.os.Binder
import android.os.Bundle
import android.os.Process
import org.json.JSONObject

/** Private IPC into :engine; this provider has no externally accessible storage. */
class LocalModelControlProvider : ContentProvider() {
    override fun onCreate() = true
    override fun call(method: String, arg: String?, extras: Bundle?): Bundle {
        check(Binder.getCallingUid() == Process.myUid()) { "Local model control is private to this application" }
        val application = requireNotNull(context).applicationContext
        val result = try {
            val raw = extras?.getString("settings") ?: "{}"
            require(raw.length <= 4096)
            val options = JSONObject(raw)
            when (method) {
                "start" -> LocalModelBenchmark.start(application, options)
                "cancel" -> LocalModelBenchmark.cancel(application)
                "status" -> {
                    val model = options.optString("model_id")
                    val configured = LocalModelPerformance.integer(options, "context_tokens", 262144)
                    val mode = options.optString("memory_mode", "balanced")
                    val plan = JSONObject(LocalModelBridge.contextPlan(model, configured, mode))
                    val recommended = plan.optInt("recommended_context_tokens", 0)
                    JSONObject().put("ok", true).put("context_plan", plan)
                        .put("recommendation", JSONObject().put("context_tokens", recommended)
                            .put("threads", LocalModelPerformance.threads(0, Runtime.getRuntime().availableProcessors()))
                            .put("timeout_seconds", LocalModelPerformance.timeoutSeconds(0, recommended,
                                JSONObject(LocalModelBridge.status()).optJSONObject("last_generation"))))
                        .put("benchmark", LocalModelBenchmark.status(application))
                }
                else -> throw IllegalArgumentException("Unknown local model control operation")
            }
        } catch (failure: Exception) {
            JSONObject().put("ok", false).put("error", failure.message ?: "本机设备设置不可用")
        }
        return Bundle().apply { putString("result", result.toString()) }
    }
    override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor? = null
    override fun getType(uri: Uri): String? = null
    override fun insert(uri: Uri, values: ContentValues?): Uri? = throw UnsupportedOperationException()
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = throw UnsupportedOperationException()
    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?): Int = throw UnsupportedOperationException()
}
