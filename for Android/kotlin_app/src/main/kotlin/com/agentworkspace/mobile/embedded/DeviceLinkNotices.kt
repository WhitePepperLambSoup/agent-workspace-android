package com.agentworkspace.mobile.embedded

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.WebUiActivity
import org.json.JSONObject

/**
 * A task handed to a paired computer finished there (mobile_management._handoff_finished): one
 * quiet notification that opens Outgoing and hand-offs. Silent on purpose: the phone may be in a
 * pocket or by a bed, and the result can wait to be read.
 */
object DeviceLinkNotices {
    const val ACTION_OPEN = "com.agentworkspace.mobile.OPEN_DEVICE_TASKS"
    private const val CHANNEL = "agent_device_link"

    @Volatile private var context: Context? = null

    @JvmStatic fun initialize(context: Context) { this.context = context.applicationContext }

    @JvmStatic
    fun execute(raw: String): String {
        val app = context ?: return fail("unavailable", "Notifications are not ready")
        return try {
            val request = JSONObject(raw)
            when (request.optString("action")) {
                "notify" -> notify(app, request)
                else -> JSONObject().put("ok", false).put("code", "invalid_arguments").put("error", "Unknown action")
            }.toString()
        } catch (error: Exception) {
            fail("failed", error.message ?: error.javaClass.simpleName)
        }
    }

    private fun fail(code: String, message: String): String =
        JSONObject().put("ok", false).put("code", code).put("error", message).toString()

    private fun notify(app: Context, request: JSONObject): JSONObject {
        val named = request.optString("host").trim().take(60)
        val host = named.ifEmpty { UiText.of(app, "电脑", "your computer") }
        // "E2E-Desk 上的…" with a space after a name, "电脑上的…" without.
        val where = if (named.isEmpty()) host else "$host "
        val title = if (request.optBoolean("finished")) UiText.of(app, "${where}上的任务完成了", "Task finished on $host")
            else UiText.of(app, "${where}上的任务没有完成", "Task did not finish on $host")
        val text = request.optString("text").take(300)
        if (!NotificationManagerCompat.from(app).areNotificationsEnabled()) {
            return JSONObject().put("ok", true).put("posted", false)
        }
        val manager = app.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL,
            UiText.of(app, "电脑上的任务", "Tasks on your computer"), NotificationManager.IMPORTANCE_LOW))
        val id = request.optString("id").ifBlank { title }
        val open = Intent(app, WebUiActivity::class.java).setAction(ACTION_OPEN)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        manager.notify("agent-device-link:$id", 3040, NotificationCompat.Builder(app, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setAutoCancel(true)
            .setContentIntent(PendingIntent.getActivity(app, 3040, open,
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
            .build())
        return JSONObject().put("ok", true).put("posted", true)
    }
}
