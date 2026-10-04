package com.agentworkspace.mobile.embedded

import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.ForegroundInfo
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.agentworkspace.mobile.WebUiActivity
import kotlinx.coroutines.CancellationException
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.time.Instant

/** Native metadata mirrors due times; prompts and dispatch checkpoints stay in Python. */
class MobileScheduleCoordinator @JvmOverloads constructor(private val context: Context,
    storageFile: File = File(context.filesDir, "mobile-native-schedules.json")) {
    private val storage = CrossProcessJsonFile(storageFile)
    private val alarms = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager

    fun syncFromJson(payload: String) {
        val incoming = JSONObject(payload).getJSONArray("schedules")
        require(incoming.length() <= 128) { "Too many schedules" }
        val ids = mutableSetOf<String>()
        val fresh = JSONArray()
        for (index in 0 until incoming.length()) {
            val item = incoming.getJSONObject(index)
            val id = item.getString("schedule_id")
            require(id.isNotBlank() && id.length <= 256 && ids.add(id)) { "Invalid schedule ID" }
            val due = item.getString("next_due_at")
            Instant.parse(due)
            val rawRepeat = item.opt("repeat_seconds")
            val repeat = if (rawRepeat == null || rawRepeat == JSONObject.NULL) null else {
                require(rawRepeat is Number) { "Invalid schedule repeat interval" }
                rawRepeat.toLong().also {
                    require(it in 900..31536000 && rawRepeat.toDouble() == it.toDouble()) { "Invalid schedule repeat interval" }
                }
            }
            val safe = JSONObject().put("schedule_id", id).put("session_id", item.optString("session_id"))
                .put("title", item.optString("title").take(160)).put("next_due_at", due)
                .put("enabled", item.getBoolean("enabled"))
                .put("repeat_seconds", repeat ?: JSONObject.NULL)
                .put("last_status", item.optString("last_status"))
            fresh.put(safe)
        }
        var deleted = emptyList<String>()
        val changedDue = mutableSetOf<String>()
        storage.update { current ->
            val old = records(current.optJSONArray("schedules") ?: JSONArray()).associateBy { it.getString("schedule_id") }
            deleted = old.keys.filter { it !in ids }
            records(fresh).forEach { safe ->
                val existing = old[safe.getString("schedule_id")]
                if (existing?.optString("next_due_at") == safe.optString("next_due_at")) {
                    safe.put("alerted_due_at", existing.opt("alerted_due_at") ?: JSONObject.NULL)
                        .put("wake_status", existing.optString("wake_status", "scheduled"))
                } else {
                    if (existing != null) changedDue.add(safe.getString("schedule_id"))
                    safe.put("wake_status", "scheduled")
                }
            }
            JSONObject().put("schedules", fresh)
        }
        (deleted + changedDue).distinct().forEach {
            cancelAlarm(it)
            TaskNotificationPublisher(context).cancelSchedule(it)
        }
        records(fresh).filter { !it.optBoolean("enabled") }.forEach {
            cancelAlarm(it.getString("schedule_id"))
            TaskNotificationPublisher(context).cancelSchedule(it.getString("schedule_id"))
        }
        restoreAlarms()
    }

    fun statusJson(): String = storage.read().let {
        it.put("schedules", it.optJSONArray("schedules") ?: JSONArray()).put("timing", "inexact")
            .put("background_start", "launch_required_when_engine_stopped").toString()
    }

    fun due(scheduleId: String, nowMillis: Long): JSONObject? {
        val item = records(storage.read().optJSONArray("schedules") ?: JSONArray())
            .firstOrNull { it.optString("schedule_id") == scheduleId } ?: return null
        if (!item.optBoolean("enabled")) return null
        val due = runCatching { Instant.parse(item.getString("next_due_at")).toEpochMilli() }.getOrNull() ?: return null
        val alerted = item.optString("alerted_due_at") == item.optString("next_due_at")
        if (alerted && item.optLong("repeat_seconds", 0) <= 0) return null
        return item.takeIf { due <= nowMillis }
    }

    fun markLaunchRequired(scheduleId: String) {
        markWake(scheduleId, "launch_required", alerted = true)
        restoreAlarms()
    }

    fun markWake(scheduleId: String, status: String, alerted: Boolean = false) {
        storage.update { state ->
            records(state.optJSONArray("schedules") ?: JSONArray()).forEach {
                if (it.optString("schedule_id") == scheduleId) {
                    it.put("wake_status", status)
                    if (alerted) it.put("alerted_due_at", it.optString("next_due_at"))
                }
            }
            state
        }
    }

    fun restoreAlarms() {
        val manual = EngineLifecycleState(context).isManuallyStopped()
        val now = System.currentTimeMillis()
        records(storage.read().optJSONArray("schedules") ?: JSONArray()).forEach { item ->
            val id = item.optString("schedule_id")
            cancelAlarm(id)
            if (manual || !item.optBoolean("enabled")) return@forEach
            var due = runCatching { Instant.parse(item.getString("next_due_at")).toEpochMilli() }.getOrNull() ?: return@forEach
            if (item.optString("alerted_due_at") == item.optString("next_due_at")) {
                val repeatMillis = item.optLong("repeat_seconds", 0) * 1000L
                if (repeatMillis <= 0) return@forEach
                if (due <= now) due += ((now - due) / repeatMillis + 1) * repeatMillis
            }
            // Inexact delivery avoids requesting special exact-alarm access.
            alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, maxOf(due, now + 1000), pending(id))
        }
    }

    fun showLaunchNotification(item: JSONObject) {
        val notificationSettings = TaskNotificationSettings(context)
        if (!notificationSettings.isEnabled() || !notificationSettings.permissionGranted(context)) {
            markWake(item.getString("schedule_id"), "notification_permission_required", alerted = true)
            return
        }
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(NotificationChannel(CHANNEL_ID, "Scheduled tasks", NotificationManager.IMPORTANCE_DEFAULT))
        val id = item.getString("schedule_id")
        val launch = Intent(context, WebUiActivity::class.java)
            .setAction("com.agentworkspace.mobile.OPEN_SCHEDULE")
            .setData(Uri.parse("agentworkspace://schedule/${Uri.encode(id)}"))
            .putExtra("session_id", item.optString("session_id"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        manager.notify("agent-schedule:$id", 3002, NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_popup_reminder).setContentTitle(item.optString("title", "Scheduled task"))
            .setContentText("Open Agent Workspace to run the due task")
            .setContentIntent(PendingIntent.getActivity(context, 0, launch, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
            .setAutoCancel(true).setVisibility(NotificationCompat.VISIBILITY_PRIVATE).build())
        markWake(id, "launch_required", alerted = true)
    }

    private fun pending(id: String): PendingIntent = PendingIntent.getBroadcast(context, 0,
        Intent(context, ScheduleWakeReceiver::class.java).setAction(ACTION_WAKE)
            .setData(Uri.parse("agentworkspace://schedule-wake/${Uri.encode(id)}"))
            .putExtra(EXTRA_SCHEDULE_ID, id), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    private fun cancelAlarm(id: String) { alarms.cancel(pending(id)) }

    private fun records(array: JSONArray): List<JSONObject> = (0 until array.length()).mapNotNull(array::optJSONObject)

    companion object {
        const val ACTION_WAKE = "com.agentworkspace.mobile.SCHEDULE_WAKE"
        const val EXTRA_SCHEDULE_ID = "schedule_id"
        const val CHANNEL_ID = "agent_scheduled_tasks"
        private var applicationContext: Context? = null

        @JvmStatic
        fun initialize(context: Context) { applicationContext = context.applicationContext }

        @JvmStatic
        fun syncGlobalFromJson(payload: String): Boolean = applicationContext?.let {
            MobileScheduleCoordinator(it).syncFromJson(payload)
            true
        } ?: false
    }
}

class ScheduleWakeReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action in setOf(Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_MY_PACKAGE_REPLACED)) {
            MobileScheduleCoordinator(context).restoreAlarms()
            if (!EngineLifecycleState(context).isManuallyStopped()) {
                EngineRecovery.ensurePeriodic(context)
                EngineRecovery.enqueue(context, 60)
            }
            return
        }
        if (intent.action != MobileScheduleCoordinator.ACTION_WAKE) return
        val id = intent.getStringExtra(MobileScheduleCoordinator.EXTRA_SCHEDULE_ID) ?: return
        if (EngineLifecycleState(context).isManuallyStopped()) return
        val request = OneTimeWorkRequestBuilder<ScheduleWakeWorker>()
            .setInputData(workDataOf(MobileScheduleCoordinator.EXTRA_SCHEDULE_ID to id))
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST).build()
        WorkManager.getInstance(context).enqueueUniqueWork("mobile-schedule:$id", ExistingWorkPolicy.KEEP, request)
    }
}

class ScheduleWakeWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun getForegroundInfo(): ForegroundInfo {
        val manager = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(NotificationChannel(MobileScheduleCoordinator.CHANNEL_ID,
            "Scheduled tasks", NotificationManager.IMPORTANCE_LOW))
        return ForegroundInfo(3003, NotificationCompat.Builder(applicationContext, MobileScheduleCoordinator.CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_popup_reminder).setContentTitle("Checking scheduled tasks")
            .setOngoing(true).build())
    }

    override suspend fun doWork(): Result {
        val id = inputData.getString(MobileScheduleCoordinator.EXTRA_SCHEDULE_ID) ?: return Result.failure()
        val coordinator = MobileScheduleCoordinator(applicationContext)
        if (EngineLifecycleState(applicationContext).isManuallyStopped()) {
            coordinator.markWake(id, "manually_stopped")
            return Result.success()
        }
        val item = coordinator.due(id, System.currentTimeMillis()) ?: return Result.success()
        return try {
            val client = LocalEngineClient(applicationContext)
            val snapshot = client.request("POST", "/mobile/schedules/run", JSONObject())
            coordinator.syncFromJson(snapshot.toString())
            coordinator.markWake(id, "delivered")
            Result.success()
        } catch (error: Exception) {
            if (error is CancellationException) throw error
            // Android 12+ may forbid starting a dataSync FGS from this background wake.
            coordinator.markLaunchRequired(id)
            coordinator.showLaunchNotification(item)
            Result.success()
        }
    }
}
