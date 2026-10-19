package com.agentworkspace.mobile.notifications

import android.app.ActivityOptions
import android.app.Notification
import android.app.PendingIntent
import android.app.RemoteInput
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.service.notification.StatusBarNotification
import com.agentworkspace.mobile.automation.BlockedApps
import org.json.JSONArray
import org.json.JSONObject

/**
 * The agent's notification tools (android_adapter/notification_tools.py), through the connected
 * notification listener in this process: list what is in the shade, answer a message from its
 * notification (the app's own quick reply) and open the page a notification leads to.
 *
 * Never: the app's own notifications, ongoing ones (music, downloads), apps the user keeps the agent
 * away from, or anything but a notification's reply field and its main tap. Verification codes are
 * hidden by the engine before the model reads the text.
 */
object NotificationActions {
    private const val MAX_LISTED = 40

    @JvmStatic
    fun execute(requestJson: String): String = runCatching {
        val request = JSONObject(requestJson)
        val listener = AgentNotificationListener.connected
            ?: return failure("access_off", "Notification access is off or not connected")
        when (request.optString("action")) {
            "list" -> list(listener)
            "reply" -> reply(listener, request.optString("key"), request.optString("text"))
            "open" -> open(listener, request.optString("key"))
            else -> failure("invalid_arguments", "Unknown notification action")
        }
    }.getOrElse { failure("failed", it.message ?: it.javaClass.simpleName) }

    private fun failure(code: String, message: String): String =
        JSONObject().put("ok", false).put("code", code).put("error", message).toString()

    private fun usable(listener: AgentNotificationListener, posted: StatusBarNotification): Boolean {
        if (posted.packageName == listener.packageName) return false
        val flags = posted.notification.flags
        if (flags and Notification.FLAG_ONGOING_EVENT != 0 || flags and Notification.FLAG_GROUP_SUMMARY != 0) return false
        return !BlockedApps.blocked(listener, posted.packageName)
    }

    private fun active(listener: AgentNotificationListener): List<StatusBarNotification> =
        (listener.activeNotifications ?: emptyArray()).filter { usable(listener, it) }.sortedByDescending { it.postTime }

    /** The action that takes a typed reply (the app's quick reply), if the notification has one. */
    private fun replyAction(posted: StatusBarNotification): Notification.Action? =
        posted.notification.actions?.firstOrNull { action ->
            action.actionIntent != null && action.remoteInputs?.any { it.allowFreeFormInput } == true
        }

    private fun list(listener: AgentNotificationListener): String {
        val items = JSONArray()
        for (posted in active(listener).take(MAX_LISTED)) {
            val extras = posted.notification.extras
            val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
            val lines = extras.getCharSequenceArray(Notification.EXTRA_TEXT_LINES)?.joinToString("\n")
            val text = (extras.getCharSequence(Notification.EXTRA_BIG_TEXT) ?: extras.getCharSequence(Notification.EXTRA_TEXT))
                ?.toString().orEmpty().ifBlank { lines.orEmpty() }
            val label = runCatching {
                listener.packageManager.getApplicationLabel(listener.packageManager.getApplicationInfo(posted.packageName, 0)).toString()
            }.getOrDefault(posted.packageName)
            items.put(JSONObject()
                .put("key", posted.key)
                .put("package", posted.packageName)
                .put("app", label.take(80))
                .put("title", title.take(200))
                .put("text", text.take(600))
                .put("posted_ms", posted.postTime)
                .put("can_reply", replyAction(posted) != null)
                .put("can_open", posted.notification.contentIntent != null))
        }
        return JSONObject().put("ok", true).put("notifications", items).toString()
    }

    private fun find(listener: AgentNotificationListener, key: String): StatusBarNotification? =
        active(listener).firstOrNull { it.key == key }

    private fun reply(listener: AgentNotificationListener, key: String, text: String): String {
        if (text.isBlank() || text.length > 2000) return failure("invalid_arguments", "The reply must be 1 to 2000 characters")
        val posted = find(listener, key) ?: return failure("not_found", "That notification is no longer shown")
        val action = replyAction(posted) ?: return failure("no_reply", "This notification has no reply field")
        val intent = Intent()
        val results = Bundle()
        val inputs = action.remoteInputs.orEmpty()
        inputs.filter { it.allowFreeFormInput }.forEach { results.putCharSequence(it.resultKey, text) }
        RemoteInput.addResultsToIntent(inputs, intent, results)
        if (Build.VERSION.SDK_INT >= 28) RemoteInput.setResultsSource(intent, RemoteInput.SOURCE_FREE_FORM_INPUT)
        action.actionIntent.send(listener, 0, intent)
        return JSONObject().put("ok", true).put("sent", true).put("app", posted.packageName).toString()
    }

    private fun open(listener: AgentNotificationListener, key: String): String {
        val posted = find(listener, key) ?: return failure("not_found", "That notification is no longer shown")
        val target = posted.notification.contentIntent ?: return failure("no_page", "This notification opens nothing")
        if (Build.VERSION.SDK_INT >= 34) {
            @Suppress("DEPRECATION")
            val mode = if (Build.VERSION.SDK_INT >= 36) ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOW_ALWAYS
                else ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED
            val options = ActivityOptions.makeBasic().setPendingIntentBackgroundActivityStartMode(mode)
            target.send(listener, 0, null, null, null, null, options.toBundle())
        } else {
            target.send()
        }
        return JSONObject().put("ok", true).put("opened", true).put("app", posted.packageName).toString()
    }
}
