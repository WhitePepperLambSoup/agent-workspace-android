package com.agentworkspace.mobile.notifications

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Settings
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.WebUiActivity
import com.agentworkspace.mobile.embedded.EngineHttp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import org.json.JSONObject

/**
 * Notification-triggered tasks. Android hands every notification to this listener once the user
 * grants notification access; only those from apps that have an enabled rule are read and sent to
 * the local engine, everything else is dropped untouched. The engine decides whether a rule
 * matches, asks first (a notification with Run / Ignore) or starts the task.
 */
class AgentNotificationListener : NotificationListenerService() {
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onNotificationPosted(notification: StatusBarNotification) {
        if (notification.packageName == packageName) return
        val flags = notification.notification.flags
        if (flags and Notification.FLAG_ONGOING_EVENT != 0 || flags and Notification.FLAG_GROUP_SUMMARY != 0) return
        scope.launch { runCatching { forward(notification) } }
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    private fun forward(posted: StatusBarNotification) {
        val index = RuleIndex.get(this) ?: return
        if (!index.enabled || posted.packageName !in index.packages) return
        val extras = posted.notification.extras
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val lines = extras.getCharSequenceArray(Notification.EXTRA_TEXT_LINES)?.joinToString("\n")
        val text = (extras.getCharSequence(Notification.EXTRA_BIG_TEXT) ?: extras.getCharSequence(Notification.EXTRA_TEXT))
            ?.toString().orEmpty().ifBlank { lines.orEmpty() }
        if (title.isBlank() && text.isBlank()) return
        val label = runCatching {
            packageManager.getApplicationLabel(packageManager.getApplicationInfo(posted.packageName, 0)).toString()
        }.getOrDefault(posted.packageName)
        val reply = EngineHttp.request(this, "POST", "/mobile/notification-rules/trigger", JSONObject()
            .put("package", posted.packageName)
            .put("app_label", label.take(80))
            .put("title", title.take(200))
            .put("text", text.take(2000)))
        if (!reply.ok) return
        val results = reply.body.optJSONArray("results") ?: return
        for (index2 in 0 until results.length()) {
            val result = results.optJSONObject(index2) ?: continue
            if (result.optString("status") == "confirm") RuleConfirmation.show(this, result)
        }
    }

    /** Which apps have rules; refreshed every 30 s so new rules apply without restarting anything. */
    private data class RuleIndex(val enabled: Boolean, val packages: Set<String>, val fetchedAt: Long) {
        companion object {
            @Volatile private var cached: RuleIndex? = null

            fun get(context: Context): RuleIndex? {
                val now = System.currentTimeMillis()
                cached?.takeIf { now - it.fetchedAt < 30_000 }?.let { return it }
                val reply = runCatching { EngineHttp.request(context, "GET", "/mobile/notification-rules", readTimeoutMs = 5000) }
                    .getOrNull()?.takeIf { it.ok } ?: return null
                val packages = reply.body.optJSONArray("packages")?.let { list ->
                    (0 until list.length()).map { list.optString(it) }.filter { it.isNotBlank() }.toSet()
                } ?: emptySet()
                return RuleIndex(reply.body.optBoolean("enabled"), packages, now).also { cached = it }
            }
        }
    }

    companion object {
        fun accessGranted(context: Context): Boolean =
            NotificationManagerCompat.getEnabledListenerPackages(context).contains(context.packageName)

        fun accessSettingsIntent(context: Context): Intent {
            val component = ComponentName(context, AgentNotificationListener::class.java)
            return if (Build.VERSION.SDK_INT >= 30) {
                Intent(Settings.ACTION_NOTIFICATION_LISTENER_DETAIL_SETTINGS)
                    .putExtra(Settings.EXTRA_NOTIFICATION_LISTENER_COMPONENT_NAME, component.flattenToString())
            } else {
                Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS")
            }.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
    }
}

/** "Let Agent handle this notification?" with Run / Ignore, for rules that ask first. */
object RuleConfirmation {
    const val CHANNEL_ID = "agent_notification_rules"
    const val ACTION_RUN = "com.agentworkspace.mobile.NOTIFICATION_RULE_RUN"
    const val ACTION_IGNORE = "com.agentworkspace.mobile.NOTIFICATION_RULE_IGNORE"
    const val EXTRA_TRIGGER = "trigger_id"

    private fun id(trigger: String) = 0x4E000000 or (trigger.hashCode() and 0x00FFFFFF)

    fun show(context: Context, result: JSONObject) {
        val trigger = result.optString("trigger_id").takeIf { it.length in 8..64 } ?: return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL_ID,
            UiText.of(context, "通知触发确认", "Notification rule confirmations"), NotificationManager.IMPORTANCE_DEFAULT))
        fun action(name: String) = PendingIntent.getBroadcast(context, id(trigger) + name.length,
            Intent(context, NotificationRuleReceiver::class.java).setAction(name).putExtra(EXTRA_TRIGGER, trigger),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val open = PendingIntent.getActivity(context, id(trigger), Intent(context, WebUiActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val source = result.optString("app_label")
        val title = result.optString("title")
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setContentTitle(UiText.of(context, "让 Agent 处理这条通知？", "Let Agent handle this notification?"))
            .setContentText(UiText.of(context, "「${result.optString("rule_name")}」· 来自 $source：$title",
                "\"${result.optString("rule_name")}\" · from $source: $title"))
            .setContentIntent(open)
            .setAutoCancel(true)
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
            .setTimeoutAfter(3_600_000L)
            .addAction(android.R.drawable.ic_media_play, UiText.of(context, "运行", "Run"), action(ACTION_RUN))
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, UiText.of(context, "忽略", "Ignore"), action(ACTION_IGNORE))
            .build()
        runCatching { manager.notify(id(trigger), notification) }
    }

    fun cancel(context: Context, trigger: String) =
        context.getSystemService(NotificationManager::class.java).cancel(id(trigger))
}

class NotificationRuleReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val trigger = intent.getStringExtra(RuleConfirmation.EXTRA_TRIGGER)?.takeIf { it.length in 8..64 } ?: return
        val path = when (intent.action) {
            RuleConfirmation.ACTION_RUN -> "/mobile/notification-rules/run"
            RuleConfirmation.ACTION_IGNORE -> "/mobile/notification-rules/dismiss"
            else -> return
        }
        RuleConfirmation.cancel(context, trigger)
        val pending = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val reply = runCatching { EngineHttp.request(context, "POST", path, JSONObject().put("trigger_id", trigger)) }.getOrNull()
                if (intent.action == RuleConfirmation.ACTION_RUN && reply?.ok != true) {
                    android.os.Handler(android.os.Looper.getMainLooper()).post {
                        android.widget.Toast.makeText(context, UiText.of(context,
                            "没能启动任务：${reply?.error ?: "本地引擎未运行"}",
                            "Could not start the task: ${reply?.error ?: "the local engine is not running"}"),
                            android.widget.Toast.LENGTH_LONG).show()
                    }
                }
            } finally { pending.finish() }
        }
    }
}
