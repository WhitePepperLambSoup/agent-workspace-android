package com.agentworkspace.mobile.embedded

import android.app.ActivityManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.BroadcastReceiver
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.agentworkspace.mobile.WebUiActivity
import kotlinx.coroutines.CancellationException
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/** A best-effort Android wake, never an unknown task/action replay. */
object EngineRecovery {
    const val ACTION_RECOVER = "com.agentworkspace.mobile.RECOVER_ENGINE"
    const val ACTION_SCHEDULING = "com.agentworkspace.mobile.ENGINE_RECOVERY_SCHEDULING"
    private const val PERIODIC_WORK = "agent-engine-recovery-periodic"
    private const val IMMEDIATE_WORK = "agent-engine-recovery-once"
    private const val CHANNEL = "agent_engine_recovery"

    @JvmStatic fun ensurePeriodic(context: Context) {
        if (EngineLifecycleState(context).isManuallyStopped()) return
        dispatchScheduling(context, "periodic")
    }

    @JvmStatic fun enqueue(context: Context, delaySeconds: Long = 10) {
        if (EngineLifecycleState(context).isManuallyStopped()) return
        dispatchScheduling(context, "once", delaySeconds)
    }

    @JvmStatic fun cancel(context: Context) {
        dispatchScheduling(context, "cancel")
    }

    private fun dispatchScheduling(context: Context, operation: String, delaySeconds: Long = 10) {
        // The service lives in :engine. WorkManager is initialized by Startup in
        // the main process, so enqueue there through a private explicit receiver.
        context.sendBroadcast(Intent(context, EngineRecoveryReceiver::class.java)
            .setAction(ACTION_SCHEDULING).putExtra("operation", operation)
            .putExtra("delay_seconds", delaySeconds.coerceIn(1, 900)))
    }

    internal fun scheduleInMainProcess(context: Context, operation: String, delaySeconds: Long) {
        val work = WorkManager.getInstance(context)
        if (operation == "cancel") {
            work.cancelUniqueWork(PERIODIC_WORK)
            work.cancelUniqueWork(IMMEDIATE_WORK)
            return
        }
        if (EngineLifecycleState(context).isManuallyStopped()) return
        when (operation) {
            // The first periodic run waits a full period: enqueued while the engine is starting, an
            // immediate run found no token yet and restarted the engine in the middle of start-up.
            "periodic" -> work.enqueueUniquePeriodicWork(PERIODIC_WORK, ExistingPeriodicWorkPolicy.KEEP,
                PeriodicWorkRequestBuilder<EngineRecoveryWorker>(15, TimeUnit.MINUTES)
                    .setInitialDelay(15, TimeUnit.MINUTES).build())
            "once" -> work.enqueueUniqueWork(IMMEDIATE_WORK, ExistingWorkPolicy.KEEP,
                OneTimeWorkRequestBuilder<EngineRecoveryWorker>()
                    .setInitialDelay(delaySeconds.coerceIn(1, 900), TimeUnit.SECONDS).build())
        }
    }

    @JvmStatic fun batterySettingsIntent(context: Context): Intent =
        Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    @JvmStatic fun appSettingsIntent(context: Context): Intent =
        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    @JvmStatic fun status(context: Context): String {
        val power = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        val activities = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val notifications = TaskNotificationSettings(context)
        return JSONObject().put("engine", JSONObject(EngineLifecycleState(context).statusJson()))
            .put("battery_optimization_exempt", power.isIgnoringBatteryOptimizations(context.packageName))
            .put("power_save", power.isPowerSaveMode).put("device_idle", power.isDeviceIdleMode)
            .put("background_restricted", Build.VERSION.SDK_INT >= 28 && activities.isBackgroundRestricted)
            .put("notifications_enabled", notifications.isEnabled() && notifications.permissionGranted(context))
            .put("recovery_policy", "bounded_best_effort_no_action_replay")
            .put("oem_limit", "Android/OEM may freeze or stop the engine even with a foreground notification; opening the app is the recovery entry")
            .put("schedules", JSONObject(MobileScheduleCoordinator(context).statusJson())).toString()
    }

    @JvmStatic fun showLaunchRequired(context: Context, reason: String) {
        val settings = TaskNotificationSettings(context)
        if (!settings.isEnabled() || !settings.permissionGranted(context)) return
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(NotificationChannel(CHANNEL, com.agentworkspace.mobile.UiText.of(context, "引擎恢复", "Engine recovery"), NotificationManager.IMPORTANCE_DEFAULT))
        val launch = Intent(context, WebUiActivity::class.java).setAction("com.agentworkspace.mobile.OPEN_ENGINE_RECOVERY")
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        manager.notify("agent-engine-recovery", 3004, NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_popup_reminder).setContentTitle(com.agentworkspace.mobile.UiText.of(context, "Agent 需要恢复后台运行", "Agent needs to resume in the background"))
            .setContentText(reason.take(160)).setAutoCancel(true).setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
            .setContentIntent(PendingIntent.getActivity(context, 3004, launch,
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)).build())
    }

    @JvmStatic fun clearLaunchNotification(context: Context) {
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .cancel("agent-engine-recovery", 3004)
    }

    fun reconcileSchedules(context: Context) {
        if (EngineLifecycleState(context).isManuallyStopped()) return
        val snapshot = LocalEngineClient(context).request("POST", "/mobile/schedules/run", JSONObject())
        MobileScheduleCoordinator(context).syncFromJson(snapshot.toString())
    }
}

class EngineRecoveryReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != EngineRecovery.ACTION_SCHEDULING) return
        val operation = intent.getStringExtra("operation") ?: return
        if (operation !in setOf("periodic", "once", "cancel")) return
        EngineRecovery.scheduleInMainProcess(context, operation, intent.getLongExtra("delay_seconds", 10))
    }
}

private const val STARTUP_GRACE_MS = 90_000L

class EngineRecoveryWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val state = EngineLifecycleState(applicationContext)
        if (state.isManuallyStopped()) return Result.success()
        val current = JSONObject(state.statusJson())
        if (current.optBoolean("requires_user_launch")) {
            EngineRecovery.showLaunchRequired(applicationContext, com.agentworkspace.mobile.UiText.of(applicationContext, "Android 已限制后台执行，请打开应用恢复", "Android restricted background work; open the app to resume"))
            return Result.success()
        }
        val token = runCatching { File(applicationContext.filesDir, "serve.token").readText().trim() }
            .getOrNull()?.takeIf { it.isNotEmpty() }
        // An engine that is still starting has not published its token or answered /health yet.
        // That is not a failure; restarting it now interrupts a start-up that cannot stop cleanly.
        if (current.optString("state") == "starting" &&
            System.currentTimeMillis() - current.optLong("updated_at_ms") < STARTUP_GRACE_MS) {
            return if (runAttemptCount < 3) Result.retry() else Result.success()
        }
        val client = LocalEngineClient(applicationContext, fixedToken = token)
        val healthy = try { client.request("GET", "/health").optBoolean("ok") }
        catch (error: Exception) { if (error is CancellationException) throw error; false }
        if (healthy) {
            // HTTP can remain healthy while the task admission fence awaits restart.
            val runtime = try { client.request("GET", "/mobile/runtime") }
            catch (error: Exception) {
                if (error is CancellationException) throw error
                return if (runAttemptCount < 3) Result.retry() else Result.success()
            }
            if (!runtime.optBoolean("restart_required")) {
                if (runtime.optBoolean("maintenance"))
                    return if (runAttemptCount < 3) Result.retry() else Result.success()
                EngineRecovery.clearLaunchNotification(applicationContext)
                // The scheduler's durable dispatch keys reconcile missed occurrences.
                // Existing task/action records are never replayed by this worker.
                runCatching { EngineRecovery.reconcileSchedules(applicationContext) }
                    .onFailure { if (it is CancellationException) throw it }
                return Result.success()
            }
        }
        if (!state.reserveAutomaticRecovery(System.currentTimeMillis())) {
            if (JSONObject(state.statusJson()).optBoolean("requires_user_launch")) {
                EngineRecovery.showLaunchRequired(applicationContext, com.agentworkspace.mobile.UiText.of(applicationContext, "自动恢复已达到上限，请打开应用继续", "Automatic recovery reached its limit; open the app to continue"))
            }
            return Result.success()
        }
        try {
            val configuration = MobileProviderSettings.load(applicationContext).toJson()
            applicationContext.startForegroundService(Intent(applicationContext, TermuxDaemonService::class.java)
                .setAction(EngineRecovery.ACTION_RECOVER).apply {
                    putExtra(TermuxDaemonService.EXTRA_PROVIDER_CONFIGURATION, configuration)
                    if (token != null) putExtra(TermuxDaemonService.EXTRA_EXPECTED_ENGINE_TOKEN, token)
                })
        } catch (_: Exception) {
            state.markLaunchRequired("Android refused a background service start; open the app to recover")
            EngineRecovery.showLaunchRequired(applicationContext, com.agentworkspace.mobile.UiText.of(applicationContext, "系统限制了后台启动，请打开应用恢复", "The system blocked a background start; open the app to resume"))
        }
        return Result.success()
    }
}
