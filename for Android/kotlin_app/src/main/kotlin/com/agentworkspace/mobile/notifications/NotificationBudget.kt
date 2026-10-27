package com.agentworkspace.mobile.notifications

import android.app.Notification
import android.app.NotificationManager
import android.service.notification.StatusBarNotification

/**
 * Android keeps about 50 notifications per app and silently drops new ones past that, so a phone
 * that finished many tasks would stop showing even "waiting for your approval". Before one of this
 * app's own notifications is posted, the oldest news (finished tasks, things a computer sent) go
 * first, keeping at most [NEWS] of them; notifications that wait for a decision are trimmed only if
 * the app would otherwise reach [LIMIT]. Ongoing ones (the engine's own) are never touched.
 */
object NotificationBudget {
    const val NEWS = 20
    const val LIMIT = 40
    private val MANAGED = listOf("agent-task:", "agent-device-link:", "agent-schedule:")

    /** One of the app's notifications as the budget sees it. */
    data class Entry(val key: Any, val removable: Boolean, val waiting: Boolean, val postTime: Long)

    /** Which notifications go so that one more fits: [entries] are all of the app's notifications. */
    fun toRemove(entries: List<Entry>): List<Entry> {
        val removable = entries.filter { it.removable }
        val news = removable.filterNot { it.waiting }.sortedBy { it.postTime }
        val gone = news.take((news.size - (NEWS - 1)).coerceAtLeast(0)).toMutableList()
        val left = entries.size - gone.size
        if (left >= LIMIT) {
            // Still too many: the oldest of the rest, news first, then old decisions.
            val rest = (news - gone.toSet()) + removable.filter { it.waiting }.sortedBy { it.postTime }
            gone += rest.take(left - LIMIT + 1)
        }
        return gone
    }

    /** Makes room for one more notification of this app. */
    fun makeRoom(manager: NotificationManager) {
        val active = runCatching { manager.activeNotifications.toList() }.getOrNull() ?: return
        val entries = active.map { notification ->
            Entry(
                key = notification,
                removable = notification.notification.flags and Notification.FLAG_ONGOING_EVENT == 0 &&
                    notification.notification.flags and Notification.FLAG_FOREGROUND_SERVICE == 0 &&
                    notification.tag?.let { tag -> MANAGED.any(tag::startsWith) } == true,
                waiting = waitsForUser(notification),
                postTime = notification.postTime,
            )
        }
        toRemove(entries).forEach { entry ->
            val notification = entry.key as StatusBarNotification
            runCatching { manager.cancel(notification.tag, notification.id) }
        }
    }

    /** Tasks waiting for approval are posted as reminders, and a computer's requests on their own channel. */
    private fun waitsForUser(notification: StatusBarNotification): Boolean =
        notification.notification.category == Notification.CATEGORY_REMINDER ||
            notification.notification.channelId == "agent_device_link_waiting"
}
