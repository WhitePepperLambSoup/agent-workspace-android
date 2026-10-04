package com.agentworkspace.mobile

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat

/**
 * 原生前台服务 (Foreground Service)。
 * 持有 PARTIAL_WAKE_LOCK，保障 Agent 在后台长任务、代码生成或大模型流式思考时不被 Android 系统杀掉。
 */
class AgentService : Service() {

    private var wakeLock: PowerManager.WakeLock? = null
    private val channelId = "agent_running_channel"
    private val notificationId = 1001

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()

        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "AgentWorkspace::BackgroundExecutionLock"
        ).apply {
            acquire(30 * 60 * 1000L) // 保护 30 分钟
        }

        val notification = buildNotification(com.agentworkspace.mobile.UiText.of(this@AgentService, "Agent 正在后台准备执行任务...", "Agent is preparing a task in the background..."))
        startForeground(notificationId, notification)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val taskTitle = intent?.getStringExtra("TASK_TITLE") ?: com.agentworkspace.mobile.UiText.of(this@AgentService, "处理中...", "Working...")
        updateNotification(com.agentworkspace.mobile.UiText.of(this@AgentService, "任务进行中: $taskTitle", "Task running: $taskTitle"))
        return START_STICKY
    }

    fun updateNotification(content: String) {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(notificationId, buildNotification(content))
    }

    private fun buildNotification(text: String): Notification {
        return NotificationCompat.Builder(this, channelId)
            .setContentTitle(com.agentworkspace.mobile.UiText.of(this@AgentService, "Agent Workspace 运行中", "Agent Workspace running"))
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            channelId,
            com.agentworkspace.mobile.UiText.of(this@AgentService, "Agent 执行服务", "Agent execution service"),
            NotificationManager.IMPORTANCE_LOW
        )
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(channel)
    }

    override fun onDestroy() {
        super.onDestroy()
        wakeLock?.let {
            if (it.isHeld) it.release()
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
