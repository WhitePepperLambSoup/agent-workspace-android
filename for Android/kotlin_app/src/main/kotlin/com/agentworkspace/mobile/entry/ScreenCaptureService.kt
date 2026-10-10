package com.agentworkspace.mobile.entry

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.ResultReceiver
import android.os.SystemClock
import android.util.DisplayMetrics
import android.view.Display
import androidx.core.app.NotificationCompat
import com.agentworkspace.mobile.UiText
import java.io.File
import kotlin.concurrent.thread

/**
 * Takes one screenshot through Android's screen capture permission, for asking about the screen
 * when the accessibility service is off. Android only hands out a capture to a foreground service of
 * the mediaProjection type, so this runs as one for the second or so the capture takes, then stops.
 * The result (the PNG's path, or a message) goes back through the caller's [ResultReceiver].
 */
class ScreenCaptureService : Service() {
    companion object {
        const val RESULT_OK = 1
        const val RESULT_FAILED = 2
        const val KEY_PATH = "path"
        const val KEY_MESSAGE = "message"
        private const val EXTRA_CODE = "capture_code"
        private const val EXTRA_DATA = "capture_data"
        private const val EXTRA_RECEIVER = "capture_receiver"
        private const val CHANNEL_ID = "agent_screen_capture"
        private const val NOTIFICATION_ID = 3006
        // Long enough for the permission dialog to fade out of the mirrored frames.
        private const val SETTLE_MS = 450L
        private const val TIMEOUT_MS = 4000L

        /** Starts a capture with the user's consent ([code] and [data] from the permission dialog). */
        fun start(context: Context, code: Int, data: Intent, receiver: ResultReceiver) {
            context.startForegroundService(Intent(context, ScreenCaptureService::class.java)
                .putExtra(EXTRA_CODE, code).putExtra(EXTRA_DATA, data).putExtra(EXTRA_RECEIVER, receiver))
        }

        /** Where screenshots wait while the user marks what to ask about; nothing else is kept here. */
        fun folder(context: Context): File = File(context.cacheDir, "screen-ask").apply { mkdirs() }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val receiver = intent?.parcelable<ResultReceiver>(EXTRA_RECEIVER)
        val data = intent?.parcelable<Intent>(EXTRA_DATA)
        val code = intent?.getIntExtra(EXTRA_CODE, 0) ?: 0
        if (receiver == null || data == null) { stopSelf(startId); return START_NOT_STICKY }
        try {
            // Android 14 requires the service to be in the foreground before the capture starts.
            goForeground()
        } catch (failure: Exception) {
            receiver.send(RESULT_FAILED, Bundle().apply { putString(KEY_MESSAGE, failure.message) })
            stopSelf(startId)
            return START_NOT_STICKY
        }
        thread(name = "agent-screen-capture") {
            val result = runCatching { capture(code, data) }
            stopForeground(STOP_FOREGROUND_REMOVE)
            result.onSuccess { receiver.send(RESULT_OK, Bundle().apply { putString(KEY_PATH, it.absolutePath) }) }
                .onFailure { receiver.send(RESULT_FAILED, Bundle().apply { putString(KEY_MESSAGE, it.message) }) }
            stopSelf(startId)
        }
        return START_NOT_STICKY
    }

    private fun goForeground() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL_ID,
            UiText.of(this, "截取屏幕", "Screen capture"), NotificationManager.IMPORTANCE_LOW))
        val notification: Notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setContentTitle(UiText.of(this, "正在截取屏幕", "Capturing the screen"))
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    /** Mirrors the screen into an image reader until the frames settle, keeps the last one, stops. */
    private fun capture(code: Int, data: Intent): File {
        val projection = getSystemService(MediaProjectionManager::class.java).getMediaProjection(code, data)
            ?: throw IllegalStateException(UiText.of(this, "没有获得截取屏幕的许可", "Screen capture was not allowed"))
        val handlerThread = HandlerThread("agent-screen-frames").apply { start() }
        val handler = Handler(handlerThread.looper)
        val lock = Object()
        var latest: Image? = null
        var stopped = false
        var reader: ImageReader? = null
        var display: VirtualDisplay? = null
        try {
            // Required before createVirtualDisplay on Android 14.
            projection.registerCallback(object : MediaProjection.Callback() {
                override fun onStop() { synchronized(lock) { stopped = true } }
            }, handler)
            val metrics = DisplayMetrics()
            @Suppress("DEPRECATION")
            getSystemService(DisplayManager::class.java).getDisplay(Display.DEFAULT_DISPLAY).getRealMetrics(metrics)
            val width = metrics.widthPixels
            val height = metrics.heightPixels
            reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 3).apply {
                setOnImageAvailableListener({ source ->
                    val image = runCatching { source.acquireLatestImage() }.getOrNull() ?: return@setOnImageAvailableListener
                    synchronized(lock) { latest?.close(); latest = image }
                }, handler)
            }
            display = projection.createVirtualDisplay("agent-screen-ask", width, height, metrics.densityDpi,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, reader.surface, null, handler)
            val started = SystemClock.uptimeMillis()
            while (true) {
                Thread.sleep(50)
                val elapsed = SystemClock.uptimeMillis() - started
                val bitmap = synchronized(lock) {
                    if (stopped) throw IllegalStateException(UiText.of(this, "截取屏幕被系统中止", "Android stopped the screen capture"))
                    val image = latest
                    if (image != null && elapsed >= SETTLE_MS) {
                        latest = null
                        try { image.toBitmap() } finally { image.close() }
                    } else null
                }
                if (bitmap != null) return save(bitmap)
                if (elapsed > TIMEOUT_MS) throw IllegalStateException(UiText.of(this, "没有收到屏幕画面", "No screen image arrived"))
            }
        } finally {
            display?.release()
            synchronized(lock) { latest?.close(); latest = null }
            reader?.close()
            projection.stop()
            handlerThread.quitSafely()
        }
    }

    private fun Image.toBitmap(): Bitmap {
        val plane = planes[0]
        val stride = plane.pixelStride
        // Rows can be wider than the image; copy the padded rows, then cut the padding off.
        val padded = Bitmap.createBitmap(plane.rowStride / stride, height, Bitmap.Config.ARGB_8888)
        padded.copyPixelsFromBuffer(plane.buffer)
        if (padded.width == width) return padded
        return Bitmap.createBitmap(padded, 0, 0, width, height).also { padded.recycle() }
    }

    private fun save(bitmap: Bitmap): File {
        val file = File(folder(this), "screen-${System.currentTimeMillis()}.png")
        try {
            file.outputStream().use { if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)) throw IllegalStateException("PNG") }
        } finally {
            bitmap.recycle()
        }
        return file
    }
}

@Suppress("DEPRECATION")
private inline fun <reified T : android.os.Parcelable> Intent.parcelable(name: String): T? =
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) getParcelableExtra(name, T::class.java) else getParcelableExtra(name)
