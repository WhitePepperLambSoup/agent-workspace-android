package com.agentworkspace.mobile.embedded

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import kotlinx.coroutines.CancellationException
import org.json.JSONObject

class TaskActionExecutor(private val client: LocalEngineClient) {
    fun execute(intent: Intent): Boolean {
        val action = intent.action
        if (action !in setOf(TaskActionReceiver.ACTION_DENY_ONCE, TaskActionReceiver.ACTION_CANCEL_TASK)) return false
        val id = intent.getStringExtra(TaskNotificationPublisher.EXTRA_TASK_ID)?.takeIf { it.isNotBlank() } ?: return false
        val session = intent.getStringExtra(TaskNotificationPublisher.EXTRA_SESSION_ID) ?: return false
        val snapshot = client.request("GET", "/mobile/tasks/${Uri.encode(id)}")
        val task = snapshot.optJSONObject("task") ?: return false
        if (task.optString("task_id") != id || task.optString("session_id") != session) return false
        val state = task.optString("state")
        if (state !in setOf("queued", "running", "waiting_approval", "interrupted")) return false
        if (action == TaskActionReceiver.ACTION_CANCEL_TASK) {
            client.request("POST", "/mobile/tasks/${Uri.encode(id)}/cancel", JSONObject())
            return true
        }
        val requestId = intent.getStringExtra(TaskActionReceiver.EXTRA_APPROVAL_ID)?.takeIf { it.isNotBlank() } ?: return false
        if (state != "waiting_approval" || task.optString("approval_id") != requestId) return false
        val approvals = snapshot.optJSONArray("approvals") ?: return false
        val relevant = (0 until approvals.length()).any {
            val approval = approvals.optJSONObject(it)
            approval != null && approval.optString("task_id") == id && approval.optString("request_id") == requestId
        }
        if (!relevant) return false
        client.request("POST", "/mobile/approvals/${Uri.encode(requestId)}/resolve",
            JSONObject().put("allowed", false).put("scope", "once"))
        return true
    }
}

class TaskActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action ?: return
        if (action !in setOf(ACTION_DENY_ONCE, ACTION_CANCEL_TASK)) return
        val taskId = intent.getStringExtra(TaskNotificationPublisher.EXTRA_TASK_ID) ?: return
        val sessionId = intent.getStringExtra(TaskNotificationPublisher.EXTRA_SESSION_ID) ?: return
        val approvalId = intent.getStringExtra(EXTRA_APPROVAL_ID)
        val request = OneTimeWorkRequestBuilder<TaskActionWorker>().setInputData(workDataOf(
            "action" to action, TaskNotificationPublisher.EXTRA_TASK_ID to taskId,
            TaskNotificationPublisher.EXTRA_SESSION_ID to sessionId, EXTRA_APPROVAL_ID to approvalId,
        )).build()
        WorkManager.getInstance(context).enqueueUniqueWork("mobile-task-action:$taskId:$approvalId:$action",
            ExistingWorkPolicy.KEEP, request)
    }

    companion object {
        const val ACTION_DENY_ONCE = "com.agentworkspace.mobile.DENY_APPROVAL_ONCE"
        const val ACTION_CANCEL_TASK = "com.agentworkspace.mobile.CANCEL_TASK"
        const val EXTRA_APPROVAL_ID = "approval_id"

        fun actionIntent(context: Context, task: TaskNotificationSnapshot, action: String): Intent =
            Intent(context, TaskActionReceiver::class.java).setAction(action)
                .setData(Uri.parse("agentworkspace://task-action/${Uri.encode(task.taskId)}/${Uri.encode(task.approvalId ?: "")}/${Uri.encode(action)}"))
                .putExtra(TaskNotificationPublisher.EXTRA_SESSION_ID, task.sessionId)
                .putExtra(TaskNotificationPublisher.EXTRA_TASK_ID, task.taskId)
                .putExtra(EXTRA_APPROVAL_ID, task.approvalId)
    }
}

class TaskActionWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val action = inputData.getString("action") ?: return Result.failure()
        val intent = Intent(action)
            .putExtra(TaskNotificationPublisher.EXTRA_TASK_ID, inputData.getString(TaskNotificationPublisher.EXTRA_TASK_ID))
            .putExtra(TaskNotificationPublisher.EXTRA_SESSION_ID, inputData.getString(TaskNotificationPublisher.EXTRA_SESSION_ID))
            .putExtra(TaskActionReceiver.EXTRA_APPROVAL_ID, inputData.getString(TaskActionReceiver.EXTRA_APPROVAL_ID))
        return try {
            if (TaskActionExecutor(LocalEngineClient(applicationContext)).execute(intent)) {
                val id = intent.getStringExtra(TaskNotificationPublisher.EXTRA_TASK_ID)!!
                val manager = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
                manager.cancel(TaskNotificationPublisher.tag(id), TaskNotificationPublisher.NOTIFICATION_ID)
            }
            Result.success()
        } catch (error: Exception) {
            if (error is CancellationException) throw error
            android.util.Log.w("AgentTaskActions", "Task action needs an available engine")
            Result.failure()
        }
    }
}
