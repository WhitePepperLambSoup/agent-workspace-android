package com.agentworkspace.mobile.embedded

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.util.AtomicFile
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.agentworkspace.mobile.WebUiActivity
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.RandomAccessFile
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.OffsetDateTime

class TaskNotificationSettings(context: Context, storageFile: File? = null) {
    private val storage = AtomicFile(storageFile ?: File(context.filesDir, "task-notification-settings.json"))

    fun isEnabled(): Boolean = read().optBoolean("enabled", true)

    fun setEnabled(enabled: Boolean) {
        // The engine runs in another process, so read the atomic file on every access.
        withStorageLock { writeAtomicJson(storage, JSONObject().put("enabled", enabled)) }
    }

    fun permissionGranted(context: Context): Boolean {
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(
                context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return false
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        return manager.areNotificationsEnabled() &&
            manager.getNotificationChannel(TaskNotificationPublisher.CHANNEL_ID)?.importance != NotificationManager.IMPORTANCE_NONE
    }

    fun toJson(context: Context): String = JSONObject()
        .put("enabled", isEnabled())
        .put("permission_granted", permissionGranted(context))
        .toString()

    private fun read(): JSONObject = withStorageLock { readAtomicJson(storage) }

    private fun <T> withStorageLock(action: () -> T): T = synchronized(storageLock) {
        RandomAccessFile(File(storage.baseFile.path + ".lock"), "rw").use { file ->
            file.channel.lock().use { action() }
        }
    }

    companion object {
        private val storageLock = Any()
        fun systemSettingsIntent(context: Context): Intent = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
            .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }
}

data class TaskNotificationSnapshot(
    val taskId: String,
    val sessionId: String,
    val state: String,
    val preview: String,
    val createdAtMillis: Long?,
    val approvalId: String?,
    val sequence: Long,
    val updatedAtMillis: Long? = null,
    /** An expert team at work: what its experts do, by app language ("zh", "en", "ja", "ko"). */
    val teamProgress: Map<String, String> = emptyMap(),
    /** Where the agent is in its studio while the task runs (mobile_studio_pose.POSES), for the studio widget. */
    val pose: String? = null,
    /** A running task to report when it goes quiet: not paused, not on the phone's own model. */
    val quietCheck: Boolean = false,
) {
    companion object {
        private val states = setOf("queued", "running", "waiting_approval", "succeeded", "failed", "cancelled", "interrupted")
        val poses = setOf("window", "desk", "shelf", "sandbox", "console", "board", "door", "idle")

        fun fromJson(value: JSONObject): TaskNotificationSnapshot? {
            val id = value.optString("task_id").trim()
            val session = value.optString("session_id").trim()
            val state = value.optString("state")
            if (id.isEmpty() || session.isEmpty() || state !in states) return null
            return TaskNotificationSnapshot(
                id, session, state,
                value.optString("prompt_preview").take(256),
                isoMillis(value.optString("created_at")),
                value.optString("approval_id").takeUnless { it.isBlank() || it == "null" },
                value.optLong("last_sequence"),
                isoMillis(value.optString("updated_at")),
                value.optJSONObject("team_progress")?.let { lines ->
                    lines.keys().asSequence().associateWith { lines.optString(it).take(200) }.filterValues { it.isNotBlank() }
                } ?: emptyMap(),
                value.optString("pose").takeIf { it in poses },
                value.optBoolean("quiet_check"),
            )
        }

        /** The engine writes "+00:00" offsets, which Instant.parse rejects before Java 12. */
        fun isoMillis(text: String): Long? = runCatching { Instant.parse(text).toEpochMilli() }.getOrNull()
            ?: runCatching { OffsetDateTime.parse(text).toInstant().toEpochMilli() }.getOrNull()
    }
}

data class TaskNotificationChange(val kind: Kind, val task: TaskNotificationSnapshot) {
    enum class Kind { NOTIFY, CANCEL }
}

/** Persists handled transitions before posting, so process restarts cannot replay results. */
class TaskNotificationTracker(storageFile: File, private val startupAtMillis: Long? = null) {
    private val storage = AtomicFile(storageFile)
    private var ledger = readAtomicJson(storage)

    @Synchronized
    fun accept(tasks: JSONArray, enabled: Boolean, nowMillis: Long = System.currentTimeMillis()): List<TaskNotificationChange> {
        val firstSnapshot = !ledger.has("baseline_at")
        val baseline = ledger.optLong("baseline_at", startupAtMillis ?: nowMillis)
        val records = ledger.optJSONObject("tasks") ?: JSONObject()
        val seen = mutableSetOf<String>()
        val changes = mutableListOf<TaskNotificationChange>()
        for (index in 0 until tasks.length()) {
            val task = tasks.optJSONObject(index)?.let(TaskNotificationSnapshot::fromJson) ?: continue
            seen.add(task.taskId)
            val previous = records.optJSONObject(task.taskId)
            val handled = previous?.optJSONArray("handled") ?: JSONArray()
            val handledKeys = (0 until handled.length()).map { handled.optString(it) }.toMutableSet()
            var waitingVisible = previous?.optBoolean("waiting_visible") == true
            if (waitingVisible && (task.state != "waiting_approval" || !enabled)) {
                changes.add(TaskNotificationChange(TaskNotificationChange.Kind.CANCEL, task))
                waitingVisible = false
            }
            // When its events last moved: a running task with nothing new for five minutes is told
            // once (the desktop app's quiet conversation), and the notice goes when it moves on.
            val lastSequence = previous?.optLong("sequence", -1L) ?: -1L
            val movedAt = if (previous == null || task.sequence != lastSequence) nowMillis
                else previous.optLong("moved_at", nowMillis)
            var quietVisible = previous?.optBoolean("quiet_visible") == true
            if (quietVisible && (task.state != "running" || task.sequence != lastSequence || !enabled)) {
                changes.add(TaskNotificationChange(TaskNotificationChange.Kind.CANCEL, task))
                quietVisible = false
            }

            val key = when (task.state) {
                "waiting_approval" -> if (task.approvalId != null) "approval:${task.approvalId}"
                    else if (previous?.optString("state") == "waiting_approval") previous.optString("approval_key")
                    else "approval-sequence:${task.sequence}"
                "succeeded", "failed" -> task.state
                else -> null
            }
            if (key != null && key !in handledKeys) {
                val currentCompletion = task.state == "waiting_approval" ||
                    (!firstSnapshot && previous != null) ||
                    (task.createdAtMillis != null && task.createdAtMillis >= baseline &&
                        (!firstSnapshot || startupAtMillis != null))
                if (enabled && currentCompletion) {
                    changes.add(TaskNotificationChange(TaskNotificationChange.Kind.NOTIFY, task))
                    waitingVisible = task.state == "waiting_approval"
                }
                handledKeys.add(key)
            }
            val quietKey = "quiet:${task.sequence}"
            if (enabled && task.state == "running" && task.quietCheck && nowMillis - movedAt >= QUIET_MILLIS &&
                quietKey !in handledKeys) {
                changes.add(TaskNotificationChange(TaskNotificationChange.Kind.NOTIFY, task.copy(state = QUIET_STATE)))
                handledKeys.add(quietKey)
                quietVisible = true
            }
            records.put(task.taskId, JSONObject()
                .put("session_id", task.sessionId)
                .put("state", task.state)
                .put("approval_key", if (task.state == "waiting_approval") key else JSONObject.NULL)
                .put("waiting_visible", waitingVisible)
                .put("sequence", task.sequence)
                .put("moved_at", movedAt)
                .put("quiet_visible", quietVisible)
                .put("handled", JSONArray(handledKeys.toList())))
        }
        for (id in records.keys().asSequence().toList()) {
            val record = records.optJSONObject(id) ?: continue
            if (id !in seen && (record.optBoolean("waiting_visible") || record.optBoolean("quiet_visible"))) {
                changes.add(TaskNotificationChange(TaskNotificationChange.Kind.CANCEL, TaskNotificationSnapshot(
                    id, record.optString("session_id"), record.optString("state"), "", null, null, 0,
                )))
                record.put("waiting_visible", false)
                record.put("quiet_visible", false)
            }
        }
        ledger = JSONObject().put("baseline_at", baseline).put("tasks", records)
        writeAtomicJson(storage, ledger)
        return changes
    }

    companion object {
        const val QUIET_MILLIS = 5 * 60_000L
        /** The notice's own state: a running task with nothing new for QUIET_MILLIS. */
        const val QUIET_STATE = "quiet"
    }
}

class TaskNotificationPublisher(private val context: Context) {
    private val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

    init {
        manager.createNotificationChannel(NotificationChannel(CHANNEL_ID, com.agentworkspace.mobile.UiText.of(context, "任务结果与批准", "Task results & approvals"), NotificationManager.IMPORTANCE_DEFAULT))
    }

    fun apply(change: TaskNotificationChange) {
        if (change.kind == TaskNotificationChange.Kind.CANCEL) manager.cancel(tag(change.task.taskId), NOTIFICATION_ID)
        else {
            com.agentworkspace.mobile.notifications.NotificationBudget.makeRoom(manager)
            manager.notify(tag(change.task.taskId), NOTIFICATION_ID, buildNotification(change.task))
        }
    }

    fun buildNotification(task: TaskNotificationSnapshot): Notification {
        val title = when (task.state) {
            "waiting_approval" -> com.agentworkspace.mobile.UiText.of(context, "任务等待批准", "Task awaiting approval")
            "failed" -> com.agentworkspace.mobile.UiText.of(context, "任务执行失败", "Task failed")
            TaskNotificationTracker.QUIET_STATE -> com.agentworkspace.mobile.UiText.of(context, "任务 5 分钟没有新进展", "No progress on a task for 5 minutes")
            else -> com.agentworkspace.mobile.UiText.of(context, "任务已完成", "Task completed")
        }
        val openTask = PendingIntent.getActivity(context, 0, navigationIntent(context, task),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val builder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setContentTitle(title)
            .setContentText(task.preview.ifBlank { "Agent Workspace" })
            .setContentIntent(openTask)
            .setAutoCancel(true)
            .setCategory(if (task.state == "waiting_approval") NotificationCompat.CATEGORY_REMINDER else NotificationCompat.CATEGORY_STATUS)
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
        if (task.state == "waiting_approval" && task.approvalId != null) {
            builder.addAction(android.R.drawable.ic_menu_view, com.agentworkspace.mobile.UiText.of(context, "查看批准", "Review"), openTask)
            builder.addAction(android.R.drawable.ic_menu_close_clear_cancel, com.agentworkspace.mobile.UiText.of(context, "拒绝此次", "Reject"),
                action(task, TaskActionReceiver.ACTION_DENY_ONCE))
            builder.addAction(android.R.drawable.ic_menu_close_clear_cancel, com.agentworkspace.mobile.UiText.of(context, "取消任务", "Cancel task"),
                action(task, TaskActionReceiver.ACTION_CANCEL_TASK))
        }
        return builder.build()
    }

    private fun action(task: TaskNotificationSnapshot, name: String): PendingIntent =
        PendingIntent.getBroadcast(context, 0, TaskActionReceiver.actionIntent(context, task, name),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

    fun cancelAllTasks() {
        manager.activeNotifications.filter { it.tag?.startsWith(TAG_PREFIX) == true }
            .forEach { manager.cancel(it.tag, it.id) }
    }

    fun cancelSchedule(scheduleId: String) = manager.cancel("agent-schedule:$scheduleId", 3002)

    companion object {
        const val CHANNEL_ID = "agent_task_results"
        const val EXTRA_SESSION_ID = "session_id"
        const val EXTRA_TASK_ID = "task_id"
        const val ACTION_OPEN_TASK = "com.agentworkspace.mobile.OPEN_TASK"
        const val NOTIFICATION_ID = 3001
        private const val TAG_PREFIX = "agent-task:"

        fun tag(taskId: String): String = "$TAG_PREFIX$taskId"

        fun navigationIntent(context: Context, task: TaskNotificationSnapshot): Intent = Intent(context, WebUiActivity::class.java)
            .setAction(ACTION_OPEN_TASK)
            .setData(Uri.parse("agentworkspace://task/${Uri.encode(task.taskId)}"))
            .putExtra(EXTRA_SESSION_ID, task.sessionId)
            .putExtra(EXTRA_TASK_ID, task.taskId)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
    }
}

class TaskNotificationMonitor(
    private val context: Context,
    storageFile: File = File(context.filesDir, "task-notification-state.json"),
    private val tokenFile: File = File(context.filesDir, "serve.token"),
    /** Null: the engine's address at each poll (EngineAddress). */
    private val fixedEndpoint: URL? = null,
    private val taskStateListener: (List<TaskNotificationSnapshot>?) -> Unit = {},
    /** Running long-lived services and whether they should keep the CPU awake. */
    private val servicesListener: (Int, Boolean) -> Unit = { _, _ -> },
) {
    private val settings = TaskNotificationSettings(context)
    private val tracker = TaskNotificationTracker(storageFile, System.currentTimeMillis())
    private val publisher = TaskNotificationPublisher(context)
    private var failures = 0

    suspend fun run() {
        while (currentCoroutineContext().isActive) delay(pollOnce())
    }

    /** A busy engine can miss one poll; only report it unreachable after several in a row. */
    private fun unreachable(retryMillis: Long): Long {
        failures += 1
        if (failures >= 3) {
            taskStateListener(null)
            return retryMillis
        }
        return 2000
    }

    fun pollOnce(): Long {
        val token = runCatching { tokenFile.readText().trim() }.getOrNull()
        if (token.isNullOrEmpty()) {
            failures = 0
            taskStateListener(null)
            return 2000
        }
        try {
            val endpoint = fixedEndpoint ?: URL("${EngineAddress.baseUrl(context)}/mobile/tasks")
            val connection = endpoint.openConnection() as HttpURLConnection
            val snapshot = try {
                connection.setRequestProperty("Authorization", "Bearer $token")
                connection.connectTimeout = 1500
                connection.readTimeout = 2000
                if (connection.responseCode !in 200..299) return unreachable(10000)
                connection.inputStream.bufferedReader(Charsets.UTF_8).use { JSONObject(it.readText()) }
            } finally { connection.disconnect() }
            val tasks = snapshot.optJSONArray("tasks") ?: return unreachable(10000)
            failures = 0
            snapshot.optJSONObject("services")?.let {
                servicesListener(it.optInt("running").coerceAtLeast(0), it.optBoolean("keep_awake"))
            }
            taskStateListener((0 until tasks.length()).mapNotNull {
                tasks.optJSONObject(it)?.let(TaskNotificationSnapshot::fromJson)
            })
            val enabled = settings.isEnabled() && settings.permissionGranted(context)
            if (!enabled) publisher.cancelAllTasks()
            tracker.accept(tasks, enabled).forEach(publisher::apply)
            val states = (0 until tasks.length()).mapNotNull { tasks.optJSONObject(it)?.optString("state") }
            return when {
                states.any { it == "running" || it == "queued" } -> 2000
                "waiting_approval" in states -> 5000
                else -> 10000
            }
        } catch (error: Exception) {
            android.util.Log.w("AgentNotifications", "Task status polling failed: ${error.javaClass.simpleName}")
            return unreachable(10000)
        }
    }
}

private fun readAtomicJson(storage: AtomicFile): JSONObject = runCatching {
    JSONObject(String(storage.readFully(), Charsets.UTF_8))
}.getOrElse { JSONObject() }

private fun writeAtomicJson(storage: AtomicFile, value: JSONObject) {
    val stream = storage.startWrite()
    try {
        stream.write(value.toString().toByteArray(Charsets.UTF_8))
        storage.finishWrite(stream)
    } catch (error: Exception) {
        storage.failWrite(stream)
        throw error
    }
}
