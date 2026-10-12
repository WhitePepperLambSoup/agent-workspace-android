package com.agentworkspace.mobile.automation

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.projection.MediaProjectionConfig
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.app.NotificationCompat
import com.agentworkspace.mobile.UiText

/**
 * Keeps [LiveScreen] running in the :engine process. Android hands a screen capture only to a
 * foreground service of the mediaProjection type, and shows its own recording indicator while it
 * runs; the notification turns it off, and so does half an hour without a screenshot.
 */
class LiveScreenService : Service() {
    companion object {
        private const val ACTION_START = "com.agentworkspace.mobile.action.LIVE_SCREEN_START"
        private const val ACTION_STOP = "com.agentworkspace.mobile.action.LIVE_SCREEN_STOP"
        private const val EXTRA_CODE = "capture_code"
        private const val EXTRA_DATA = "capture_data"
        private const val CHANNEL_ID = "agent_live_screen"
        private const val NOTIFICATION_ID = 3007
        private const val IDLE_LIMIT_MS = 30 * 60_000L

        fun start(context: Context, code: Int, data: Intent) {
            context.startForegroundService(Intent(context, LiveScreenService::class.java).setAction(ACTION_START)
                .putExtra(EXTRA_CODE, code).putExtra(EXTRA_DATA, data))
        }

        fun stop(context: Context) {
            runCatching { context.startService(Intent(context, LiveScreenService::class.java).setAction(ACTION_STOP)) }
        }
    }

    private val handler = Handler(Looper.getMainLooper())
    private val idleCheck = object : Runnable {
        override fun run() {
            if (!LiveScreen.active) { finish(); return }
            if (LiveScreen.idleMs() > IDLE_LIMIT_MS) LiveScreen.stop() else handler.postDelayed(this, 60_000)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action != ACTION_START) {
            LiveScreen.stop()
            finish()
            return START_NOT_STICKY
        }
        val data = if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra(EXTRA_DATA, Intent::class.java)
            else @Suppress("DEPRECATION") intent.getParcelableExtra(EXTRA_DATA)
        val code = intent.getIntExtra(EXTRA_CODE, 0)
        try {
            // Android 14 requires the service to be in the foreground before the capture starts.
            goForeground()
            val projection = getSystemService(MediaProjectionManager::class.java)
                .getMediaProjection(code, data ?: error("missing consent"))
                ?: error("Screen capture was not allowed")
            AndroidSystemBridge.initialize(this)
            LiveScreen.start(this, projection) { handler.post { finish() } }
            handler.removeCallbacks(idleCheck)
            handler.postDelayed(idleCheck, 60_000)
        } catch (_: Exception) {
            LiveScreen.stop()
            Toast.makeText(this, UiText.of(this, "无法开启实时画面", "Could not turn on the live screen"), Toast.LENGTH_SHORT).show()
            finish()
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        handler.removeCallbacks(idleCheck)
        LiveScreen.stop()
        super.onDestroy()
    }

    private fun finish() {
        handler.removeCallbacks(idleCheck)
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun goForeground() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL_ID,
            UiText.of(this, "实时画面", "Live screen"), NotificationManager.IMPORTANCE_LOW))
        val stop = PendingIntent.getService(this, 0, Intent(this, LiveScreenService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setContentTitle(UiText.of(this, "实时画面已开启", "Live screen is on"))
            .setContentText(UiText.of(this, "AI 操作手机时直接看当前画面；半小时不用会自动关闭",
                "The agent sees the current screen while it uses the phone; turns off after half an hour unused"))
            .setOngoing(true)
            .addAction(0, UiText.of(this, "关闭", "Turn off"), stop)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }
}

/** Asks Android for the screen capture consent (the whole screen), then hands it to [LiveScreenService]. */
class LiveScreenConsentActivity : ComponentActivity() {
    private val consent = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val data = result.data
        if (result.resultCode == RESULT_OK && data != null) LiveScreenService.start(this, result.resultCode, data)
        else Toast.makeText(this, UiText.of(this, "没有开启实时画面", "The live screen was not turned on"), Toast.LENGTH_SHORT).show()
        finish()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (savedInstanceState != null) return
        val manager = getSystemService(MediaProjectionManager::class.java)
        val request = if (Build.VERSION.SDK_INT >= 34) {
            manager.createScreenCaptureIntent(MediaProjectionConfig.createConfigForDefaultDisplay())
        } else manager.createScreenCaptureIntent()
        try { consent.launch(request) } catch (_: Exception) { finish() }
    }
}
