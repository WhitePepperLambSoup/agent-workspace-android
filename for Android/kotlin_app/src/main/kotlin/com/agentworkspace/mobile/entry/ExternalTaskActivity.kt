package com.agentworkspace.mobile.entry

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.Signature
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.embedded.EngineHttp
import org.json.JSONArray
import org.json.JSONObject
import java.security.MessageDigest
import java.util.UUID
import kotlin.concurrent.thread

/** Who may start a task without being asked, on plain values so it can be tested without a phone. */
internal object ExternalEntry {
    /** An app as Android knows it: its package and the certificate it is signed with. */
    data class App(val packageName: String, val certificate: String)

    enum class Decision { RUN, ASK_ONCE, ASK_OFFERING_ALWAYS }

    /**
     * An app the user allowed runs without a dialog. A caller Android does not name cannot be allowed
     * by name, and operating the phone is asked about every time, so neither offers "always".
     */
    fun decide(caller: App?, allowed: Collection<App>, phone: Boolean): Decision = when {
        caller == null || phone -> Decision.ASK_ONCE
        caller in allowed -> Decision.RUN
        else -> Decision.ASK_OFFERING_ALWAYS
    }

    fun encode(apps: Collection<App>): String = JSONArray(apps.map {
        JSONObject().put("package", it.packageName).put("certificate", it.certificate)
    }).toString()

    /** A stored list that cannot be read allows nobody. */
    fun decode(stored: String?): List<App> = runCatching {
        val list = JSONArray(stored ?: "[]")
        (0 until list.length()).map { list.getJSONObject(it).let { app -> App(app.getString("package"), app.getString("certificate")) } }
    }.getOrDefault(emptyList())
}

/**
 * Tasks started by other apps (Tasker, Shortcuts, automation apps): an explicit intent with action
 * [ACTION] and the request as the "prompt" extra ("phone_control" true to operate the phone). Each
 * request is shown with where it came from and asked about, until the user allows that app (package
 * and signing certificate) from now on. A request to operate the phone is asked about every time. A
 * started task still asks for approval like any other.
 */
class ExternalTaskActivity : Activity() {
    companion object {
        const val ACTION = "com.agentworkspace.mobile.action.RUN_TASK"
        private const val PREFS = "external_entry"
        private const val ALLOWED = "allowed"
        // Earlier versions kept one switch for every app on the phone. Whoever had it on is asked once again, per app.
        private const val OLD_SWITCH = "enabled"

        private fun allowed(context: Context): List<ExternalEntry.App> {
            val preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            if (preferences.contains(OLD_SWITCH)) preferences.edit().remove(OLD_SWITCH).apply()
            return ExternalEntry.decode(preferences.getString(ALLOWED, null))
        }

        private fun store(context: Context, apps: List<ExternalEntry.App>) {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(ALLOWED, ExternalEntry.encode(apps)).apply()
        }

        /** The allowed apps for the settings page: [{"package", "label"}]. */
        fun allowedApps(context: Context): String = JSONArray(allowed(context).map { app ->
            JSONObject().put("package", app.packageName).put("label", label(context, app.packageName))
        }).toString()

        fun forget(context: Context, packageName: String) {
            store(context, allowed(context).filterNot { it.packageName == packageName })
        }

        private fun label(context: Context, packageName: String): String = runCatching {
            val manager = context.packageManager
            manager.getApplicationLabel(manager.getApplicationInfo(packageName, 0)).toString()
        }.getOrDefault(packageName)

        /** The SHA-256 of what the app is signed with now; null when Android does not say. */
        private fun certificate(context: Context, packageName: String): String? = runCatching {
            val manager = context.packageManager
            val signatures: Array<Signature>? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                manager.getPackageInfo(packageName, PackageManager.GET_SIGNING_CERTIFICATES).signingInfo?.apkContentsSigners
            } else {
                @Suppress("DEPRECATION")
                manager.getPackageInfo(packageName, PackageManager.GET_SIGNATURES).signatures
            }
            signatures?.takeIf { it.isNotEmpty() }?.map { signature ->
                MessageDigest.getInstance("SHA-256").digest(signature.toByteArray()).joinToString("") { "%02x".format(it) }
            }?.sorted()?.joinToString(",")
        }.getOrNull()
    }

    /**
     * The app that sent this, as Android recorded it. getReferrer prefers what the sender wrote into the
     * intent itself, so that goes first; a package Android cannot name stays unknown.
     */
    private fun caller(): ExternalEntry.App? {
        intent.removeExtra(Intent.EXTRA_REFERRER)
        intent.removeExtra(Intent.EXTRA_REFERRER_NAME)
        val name = (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) launchedFromPackage else null)
            ?: callingPackage ?: referrer?.takeIf { it.scheme == "android-app" }?.host
        return name?.let { packageName -> certificate(this, packageName)?.let { ExternalEntry.App(packageName, it) } }
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
        val caller = caller()
        val decision = ExternalEntry.decide(caller, allowed(this), phone)
        if (decision == ExternalEntry.Decision.RUN) { submit(prompt, phone); return }
        val source = caller?.let { "${label(this, it.packageName)} (${it.packageName})" } ?: UiText.of(this, "未知应用", "an unknown app")
        val warning = if (phone) UiText.of(this, "这个任务会通过无障碍操作你的手机：点按、滑动和输入。", "This task will operate your phone through accessibility: tapping, swiping and typing.") + "\n\n" else ""
        val dialog = AlertDialog.Builder(this, android.R.style.Theme_DeviceDefault_Dialog_Alert)
            .setTitle(UiText.of(this, "其他应用想让 Agent 做事", "Another app wants the agent to do something"))
            .setMessage(warning + UiText.of(this, "来自：$source\n\n$prompt", "From: $source\n\n$prompt"))
            .setPositiveButton(UiText.of(this, "允许这一次", "Allow once")) { _, _ -> submit(prompt, phone) }
            .setNegativeButton(UiText.of(this, "拒绝", "Deny")) { _, _ -> finish() }
            .setOnCancelListener { finish() }
        if (decision == ExternalEntry.Decision.ASK_OFFERING_ALWAYS && caller != null) {
            dialog.setNeutralButton(UiText.of(this, "以后都允许这个应用", "Always allow this app")) { _, _ ->
                store(this, allowed(this).filterNot { it.packageName == caller.packageName } + caller)
                submit(prompt, phone)
            }
        }
        dialog.show()
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
