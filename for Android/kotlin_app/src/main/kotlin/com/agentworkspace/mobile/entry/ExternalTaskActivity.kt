package com.agentworkspace.mobile.entry

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.os.Bundle
import android.widget.Toast
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.embedded.EngineHttp
import org.json.JSONObject
import java.util.UUID
import kotlin.concurrent.thread

/**
 * Tasks started by other apps (Tasker, Shortcuts, automation apps): an explicit intent with action
 * [ACTION] and the request as the "prompt" extra ("phone_control" true to operate the phone). Off
 * until the user allows it: until then each request is shown with where it came from and asked
 * about. A started task still asks for approval like any other.
 */
class ExternalTaskActivity : Activity() {
    companion object {
        const val ACTION = "com.agentworkspace.mobile.action.RUN_TASK"
        private const val PREFS = "external_entry"

        fun enabled(context: Context): Boolean =
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean("enabled", false)

        fun setEnabled(context: Context, enabled: Boolean) {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean("enabled", enabled).apply()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prompt = intent?.getStringExtra("prompt")?.trim()?.take(8000)
        if (intent?.action != ACTION || prompt.isNullOrEmpty()) {
            Toast.makeText(this, UiText.of(this, "缺少要执行的内容（prompt）", "Nothing to do: the prompt extra is missing"), Toast.LENGTH_LONG).show()
            finish()
            return
        }
        val phone = intent.getBooleanExtra("phone_control", false)
        if (enabled(this)) { submit(prompt, phone); return }
        val source = referrer?.host ?: callingPackage ?: UiText.of(this, "未知应用", "an unknown app")
        AlertDialog.Builder(this, android.R.style.Theme_DeviceDefault_Dialog_Alert)
            .setTitle(UiText.of(this, "其他应用想让 Agent 做事", "Another app wants the agent to do something"))
            .setMessage(UiText.of(this, "来自：$source\n\n$prompt", "From: $source\n\n$prompt"))
            .setPositiveButton(UiText.of(this, "允许这一次", "Allow once")) { _, _ -> submit(prompt, phone) }
            .setNeutralButton(UiText.of(this, "以后都允许", "Always allow")) { _, _ -> setEnabled(this, true); submit(prompt, phone) }
            .setNegativeButton(UiText.of(this, "拒绝", "Deny")) { _, _ -> finish() }
            .setOnCancelListener { finish() }
            .show()
    }

    private fun submit(prompt: String, phone: Boolean) {
        val context = applicationContext
        thread(name = "external-task") {
            val error = runCatching {
                check(EngineHttp.ensureEngine(context)) { UiText.of(context, "AI 引擎没有启动", "The engine did not start") }
                val title = UiText.of(context, "外部触发：", "From another app: ") + prompt.replace('\n', ' ').take(24)
                val session = EngineHttp.request(context, "POST", "/sessions", JSONObject().put("title", title))
                check(session.ok) { session.error }
                val task = EngineHttp.request(context, "POST", "/mobile/tasks", JSONObject()
                    .put("session_id", session.body.getString("id")).put("prompt", prompt)
                    .put("request_id", "external-${UUID.randomUUID()}")
                    .apply { if (phone) put("phone_control", true) }, 20000)
                check(task.ok) { task.error }
            }.exceptionOrNull()
            runOnUiThread {
                Toast.makeText(context, if (error == null) UiText.of(context, "已交给 Agent：", "Sent to the agent: ") + prompt.take(30)
                    else UiText.of(context, "没能交给 Agent：", "Could not start: ") + error.message, Toast.LENGTH_LONG).show()
                finish()
            }
        }
    }
}
