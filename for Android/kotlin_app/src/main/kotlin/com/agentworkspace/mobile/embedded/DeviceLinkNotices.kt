package com.agentworkspace.mobile.embedded

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.WebUiActivity
import org.json.JSONObject

/**
 * What a paired computer sent or finished (mobile_management._handoff_finished, mobile_link): quiet
 * notifications. Silent on purpose: the phone may be in a pocket or by a bed, and none of it is
 * urgent enough to ring. Those that wait for the user (an approval, a request to do something on
 * this phone) have their own channel, so the user can let that one make a sound in system settings.
 */
object DeviceLinkNotices {
    const val ACTION_OPEN = "com.agentworkspace.mobile.OPEN_DEVICE_TASKS"
    const val ACTION_OPEN_COMPUTER = "com.agentworkspace.mobile.OPEN_COMPUTER"
    const val ACTION_COPY = "com.agentworkspace.mobile.DEVICE_LINK_COPY"
    const val EXTRA_HOST = "com.agentworkspace.mobile.extra.HOST_ID"
    const val EXTRA_SECTION = "com.agentworkspace.mobile.extra.COMPUTER_SECTION"
    private const val EXTRA_TEXT = "com.agentworkspace.mobile.extra.LINK_TEXT"
    private const val EXTRA_TAG = "com.agentworkspace.mobile.extra.LINK_TAG"
    private const val CHANNEL = "agent_device_link"
    private const val CHANNEL_WAITING = "agent_device_link_waiting"
    private const val NOTIFICATION_ID = 3040

    @Volatile private var context: Context? = null

    @JvmStatic fun initialize(context: Context) { this.context = context.applicationContext }

    @JvmStatic
    fun execute(raw: String): String {
        val app = context ?: return fail("unavailable", "Notifications are not ready")
        return try {
            val request = JSONObject(raw)
            when (request.optString("action")) {
                "cancel" -> cancel(app, request.optString("tag"))
                "notify", "approval", "turn", "run", "file", "text", "conversation", "job", "online", "moved" ->
                    notify(app, request)
                else -> JSONObject().put("ok", false).put("code", "invalid_arguments").put("error", "Unknown action")
            }.toString()
        } catch (error: Exception) {
            fail("failed", error.message ?: error.javaClass.simpleName)
        }
    }

    private fun fail(code: String, message: String): String =
        JSONObject().put("ok", false).put("code", code).put("error", message).toString()

    private fun cancel(app: Context, tag: String): JSONObject {
        if (tag.isNotBlank()) NotificationManagerCompat.from(app).cancel("agent-device-link:$tag", NOTIFICATION_ID)
        return JSONObject().put("ok", true)
    }

    private fun channels(app: Context, manager: NotificationManager) {
        manager.createNotificationChannel(NotificationChannel(CHANNEL,
            UiText.of(app, "电脑上的任务", "Tasks on your computer"), NotificationManager.IMPORTANCE_LOW))
        manager.createNotificationChannel(NotificationChannel(CHANNEL_WAITING,
            UiText.of(app, "电脑等你确认", "Your computer is waiting for you"), NotificationManager.IMPORTANCE_LOW))
    }

    private fun openComputer(app: Context, hostId: String, section: String): Intent =
        Intent(app, WebUiActivity::class.java).setAction(ACTION_OPEN_COMPUTER)
            .putExtra(EXTRA_HOST, hostId.take(128)).putExtra(EXTRA_SECTION, section)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)

    private fun notify(app: Context, request: JSONObject): JSONObject {
        val action = request.optString("action")
        val named = request.optString("host").trim().take(60)
        val host = named.ifEmpty { UiText.of(app, "电脑", "your computer") }
        // "E2E-Desk 上的…" with a space after a name, "电脑上的…" without.
        val where = if (named.isEmpty()) host else "$host "
        val hostId = request.optString("host_id")
        val id = request.optString("id").take(128)
        val title = request.optString("title").trim().take(120)
        val text = request.optString("text").take(2000)
        val finished = request.optBoolean("finished")
        val link = request.optBoolean("link")
        // Finished turns and scheduled results from one computer replace each other (its page lists
        // them all); the rest are one notification each.
        val tag = when (action) {
            "notify" -> id.ifBlank { text.take(40) }
            "turn", "run", "online", "moved" -> "$action:$hostId"
            else -> "$action:${id.ifBlank { hostId }}"
        }
        val heading = when (action) {
            "approval" -> UiText.of(app, "${where}上的任务等你审批", "A task on $host needs your approval")
            "turn" -> if (finished) UiText.of(app, "${where}上的任务完成了", "Task finished on $host")
                else UiText.of(app, "${where}上的任务没有完成", "Task did not finish on $host")
            "run" -> if (finished) UiText.of(app, "定时任务「$title」有结果了", "Scheduled task “$title” has a result")
                else UiText.of(app, "定时任务「$title」没有完成", "Scheduled task “$title” did not finish")
            "file" -> UiText.of(app, "收到 ${host} 发来的 ${request.optString("name").take(80)}",
                "Received ${request.optString("name").take(80)} from $host")
            "text" -> if (link) UiText.of(app, "${host} 发来的链接", "Link from $host")
                else UiText.of(app, "${host} 发来的文字", "Text from $host")
            "conversation" -> UiText.of(app, "${host} 发来了对话「$title」", "Conversation “$title” from $host")
            "job" -> UiText.of(app, "${host} 想在这台手机上做事", "$host asks to do something on this phone")
            "online" -> UiText.of(app, "${host} 已上线", "$host is back online")
            "moved" -> UiText.of(app, "在 ${request.optString("url").take(80)} 找到了 $host",
                "Found $host at ${request.optString("url").take(80)}")
            else -> if (finished) UiText.of(app, "${where}上的任务完成了", "Task finished on $host")
                else UiText.of(app, "${where}上的任务没有完成", "Task did not finish on $host")
        }
        val body = when (action) {
            "turn" -> if (title.isNotEmpty() && text.isNotEmpty()) "$title：$text" else title.ifEmpty { text }
            "file" -> request.optString("folder").take(60).ifEmpty { "来自电脑" }.let { folder ->
                UiText.of(app, "存在工作区的「$folder」文件夹", "Saved in your workspace, folder $folder")
            }
            "conversation" -> UiText.of(app, "点开在手机上继续", "Tap to continue it on the phone")
            "moved" -> UiText.of(app, "点开选择是否换到这个地址", "Tap to choose whether to use this address")
            "online" -> UiText.of(app, "现在可以把任务交给它了", "You can hand tasks to it now")
            else -> text
        }
        if (!NotificationManagerCompat.from(app).areNotificationsEnabled()) {
            return JSONObject().put("ok", true).put("posted", false)
        }
        val manager = app.getSystemService(NotificationManager::class.java)
        channels(app, manager)
        val code = tag.hashCode()
        val open = when (action) {
            "notify" -> Intent(app, WebUiActivity::class.java).setAction(ACTION_OPEN)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            "conversation" -> Intent(app, WebUiActivity::class.java).setAction(TaskNotificationPublisher.ACTION_OPEN_TASK)
                .putExtra(TaskNotificationPublisher.EXTRA_SESSION_ID, request.optString("session_id").take(256))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            else -> openComputer(app, hostId, when (action) {
                "approval" -> "approvals"
                "job" -> "jobs"
                "file", "text", "run", "turn" -> "inbox"
                else -> ""
            })
        }
        val waiting = action == "approval" || action == "job"
        val builder = NotificationCompat.Builder(app, if (waiting) CHANNEL_WAITING else CHANNEL)
            .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
            .setContentTitle(heading)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(PendingIntent.getActivity(app, code, open,
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
        if (action == "text" && text.isNotBlank()) {
            val copy = Intent(app, DeviceLinkActionReceiver::class.java).setAction(ACTION_COPY)
                .putExtra(EXTRA_TEXT, text.take(65536)).putExtra(EXTRA_TAG, tag)
            builder.addAction(0, UiText.of(app, "复制", "Copy"),
                PendingIntent.getBroadcast(app, code, copy, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
            val uri = runCatching { Uri.parse(text.trim()) }.getOrNull()
            if (link && uri != null && uri.scheme in setOf("http", "https") && !uri.host.isNullOrBlank()) {
                val view = Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                builder.addAction(0, UiText.of(app, "打开", "Open"),
                    PendingIntent.getActivity(app, code + 1, view, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
            }
        }
        com.agentworkspace.mobile.notifications.NotificationBudget.makeRoom(manager)
        manager.notify("agent-device-link:$tag", NOTIFICATION_ID, builder.build())
        return JSONObject().put("ok", true).put("posted", true)
    }

    /** Copy is the user's own tap on the notification: the text goes to the clipboard. */
    fun copy(app: Context, intent: Intent) {
        val text = intent.getStringExtra(EXTRA_TEXT)?.take(65536) ?: return
        app.getSystemService(ClipboardManager::class.java)?.setPrimaryClip(ClipData.newPlainText("Agent Workspace", text))
        Toast.makeText(app, UiText.of(app, "已复制", "Copied"), Toast.LENGTH_SHORT).show()
        intent.getStringExtra(EXTRA_TAG)?.let { cancel(app, it) }
    }
}

/** The notification's "Copy" button (DeviceLinkNotices). Not exported: only this app's own notifications reach it. */
class DeviceLinkActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == DeviceLinkNotices.ACTION_COPY) DeviceLinkNotices.copy(context.applicationContext, intent)
    }
}
