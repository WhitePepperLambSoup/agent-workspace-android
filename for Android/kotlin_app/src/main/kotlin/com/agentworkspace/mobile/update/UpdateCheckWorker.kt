package com.agentworkspace.mobile.update

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.WebUiActivity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit

/**
 * About every twelve hours, with a network, asks GitHub for a newer release while the app is not
 * open, and tells about a new version once with a notification; opening the app offers it (the
 * check at start, AppSupportController). Follows the "check for updates automatically" setting.
 */
class UpdateCheckWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val context = applicationContext
        if (!UpdateChecker.autoCheckEnabled(context)) return Result.success()
        // Checked at start or on return a moment ago: nothing new to learn.
        if (!UpdateChecker.dueForAutoCheck(context, slackMs = TimeUnit.HOURS.toMillis(1))) return Result.success()
        val release = withContext(Dispatchers.IO) { runCatching { UpdateChecker.fetchLatest() }.getOrNull() } ?: return Result.success()
        UpdateChecker.markChecked(context, release.version)
        if (UpdateChecker.isNewer(release.version, UpdateChecker.installedVersion(context)) &&
            UpdateChecker.shouldNotify(context, release.version) && notify(context, release.version)) {
            UpdateChecker.markNotified(context, release.version)
        }
        return Result.success()
    }

    companion object {
        private const val WORK = "agent-update-check"
        private const val CHANNEL = "agent_app_updates"

        /** Called from the main process (where WorkManager starts); keeps an existing schedule. */
        fun schedule(context: Context) {
            if (!UpdateChecker.autoCheckEnabled(context)) return
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(WORK, ExistingPeriodicWorkPolicy.KEEP,
                PeriodicWorkRequestBuilder<UpdateCheckWorker>(12, TimeUnit.HOURS)
                    .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                    .setInitialDelay(12, TimeUnit.HOURS)
                    .build())
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK)
        }

        private fun notify(context: Context, version: String): Boolean {
            if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return false
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(NotificationChannel(CHANNEL,
                UiText.of(context, "应用更新", "App updates"), NotificationManager.IMPORTANCE_DEFAULT))
            val open = Intent(context, WebUiActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            return runCatching {
                manager.notify("agent-app-update", 3010, NotificationCompat.Builder(context, CHANNEL)
                    .setSmallIcon(android.R.drawable.stat_sys_download_done)
                    .setContentTitle(UiText.of(context, "Agent Workspace 有新版本 v$version", "Agent Workspace $version is available"))
                    .setContentText(UiText.of(context, "打开应用即可下载安装", "Open the app to download and install it"))
                    .setAutoCancel(true)
                    .setContentIntent(PendingIntent.getActivity(context, 3010, open,
                        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
                    .build())
                true
            }.getOrDefault(false)
        }
    }
}
