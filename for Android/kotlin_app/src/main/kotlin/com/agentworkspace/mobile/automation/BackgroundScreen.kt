package com.agentworkspace.mobile.automation

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.hardware.display.DisplayManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.util.DisplayMetrics
import android.view.Display
import androidx.core.app.NotificationCompat
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.WebUiActivity
import org.json.JSONObject
import rikka.shizuku.Shizuku
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * The background screen: an off-screen display the agent works on while the user keeps using the
 * phone's own screen (Device & tools → Background operation). It needs Shizuku, which lends shell
 * rights to [BackgroundScreenService]; the agent then reads and acts on the display through the
 * accessibility service as on the phone screen, by node actions, which leave the screen's focus
 * alone. Apps opened there run as usual but are not seen; the user can move one to the phone's
 * screen. Without Shizuku, or with it off, phone tasks use the phone's own screen as before.
 *
 * Runs in the engine process (Shizuku's provider is declared there). Calls block: never on the main
 * thread.
 */
object BackgroundScreen {
    private const val SERVICE_VERSION = 1
    private const val PERMISSION_REQUEST = 7301
    /** A display left unused this long is closed (an app open on it keeps running until then). */
    private const val IDLE_MS = 10 * 60_000L

    private val lock = Any()
    @Volatile private var remote: IBackgroundScreen? = null
    @Volatile private var displayId = -1
    @Volatile private var lastUse = 0L
    private val main = Handler(Looper.getMainLooper())
    private var connection: ServiceConnection? = null

    class Unavailable(message: String) : RuntimeException(message)

    private fun flag(context: Context) = File(context.filesDir, "background_screen")

    /** The user's choice (Device & tools); the screen is used only when it is on and Shizuku is ready. */
    fun enabled(context: Context): Boolean = flag(context).exists()

    fun setEnabled(context: Context, on: Boolean) {
        if (on) flag(context).writeText("1") else {
            flag(context).delete()
            close()
        }
    }

    private fun shizukuRunning(): Boolean = runCatching { Shizuku.pingBinder() }.getOrDefault(false)

    private fun permitted(): Boolean = shizukuRunning() && runCatching {
        !Shizuku.isPreV11() && Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED
    }.getOrDefault(false)

    /** For Device & tools: whether it can be used, and why not. */
    fun status(context: Context): JSONObject {
        val installed = runCatching { context.packageManager.getPackageInfo("moe.shizuku.privileged.api", 0); true }
            .getOrDefault(false)
        val running = shizukuRunning()
        val permitted = permitted()
        val reason = when {
            Build.VERSION.SDK_INT < 30 -> "needs_android_11"
            !installed && !running -> "shizuku_missing"
            !running -> "shizuku_stopped"
            !permitted -> "shizuku_permission"
            else -> null
        }
        return JSONObject().put("enabled", enabled(context)).put("supported", Build.VERSION.SDK_INT >= 30)
            .put("shizuku_installed", installed).put("shizuku_running", running).put("permitted", permitted)
            .put("active", displayId != -1 && remote?.asBinder()?.isBinderAlive == true)
            .put("display_id", displayId).put("reason", reason ?: JSONObject.NULL)
            // For the setup steps: Shizuku starts through wireless debugging, which needs both.
            .put("developer_options", globalFlag(context, Settings.Global.DEVELOPMENT_SETTINGS_ENABLED) ?: JSONObject.NULL)
            .put("wifi", wifiConnected(context))
    }

    private fun globalFlag(context: Context, name: String): Boolean? =
        runCatching { Settings.Global.getInt(context.contentResolver, name) == 1 }.getOrNull()

    private fun wifiConnected(context: Context): Boolean = runCatching {
        val connectivity = context.getSystemService(ConnectivityManager::class.java)
        connectivity.allNetworks.any { connectivity.getNetworkCapabilities(it)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true }
    }.getOrDefault(false)

    /**
     * After a restart Shizuku is stopped until the user starts it again through wireless debugging.
     * When the background screen is on, say so once per boot (a quiet notification that opens the
     * setup steps), so the first phone task does not just fall back to the phone's own screen.
     */
    fun remindAfterBoot(context: Context) {
        val app = context.applicationContext
        main.postDelayed({
            Thread {
                runCatching {
                    if (Build.VERSION.SDK_INT < 30 || !enabled(app) || shizukuRunning()) return@Thread
                    val boot = File("/proc/sys/kernel/random/boot_id").readText().trim()
                    val marker = File(app.filesDir, "background_screen_reminded")
                    if (marker.isFile && marker.readText() == boot) return@Thread
                    marker.writeText(boot)
                    val manager = app.getSystemService(NotificationManager::class.java)
                    manager.createNotificationChannel(NotificationChannel(CHANNEL,
                        UiText.of(app, "后台操作", "Background operation"), NotificationManager.IMPORTANCE_LOW))
                    val open = Intent(app, WebUiActivity::class.java).setAction(ACTION_SETUP)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                    manager.notify(NOTIFICATION_ID, NotificationCompat.Builder(app, CHANNEL)
                        .setSmallIcon(android.R.drawable.ic_dialog_info)
                        .setContentTitle(UiText.of(app, "后台操作需要重新启动 Shizuku", "Background operation needs Shizuku started again"))
                        .setContentText(UiText.of(app, "手机重启后 Shizuku 会停止。点这里按步骤启动；不启动时，手机任务在前台进行。",
                            "Shizuku stops when the phone restarts. Tap to start it again; until then phone tasks use the screen."))
                        .setContentIntent(PendingIntent.getActivity(app, NOTIFICATION_ID, open, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
                        .setAutoCancel(true).build())
                }
            }.start()
        }, 90_000)
    }

    const val ACTION_SETUP = "com.agentworkspace.mobile.OPEN_BACKGROUND_SETUP"
    private const val CHANNEL = "agent_background_screen"
    private const val NOTIFICATION_ID = 3030

    /** Shizuku asks the user (its own dialog); the answer shows in [status]. */
    fun requestPermission(): Boolean = runCatching {
        if (!shizukuRunning() || Shizuku.isPreV11()) return false
        if (Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED) return true
        Shizuku.requestPermission(PERMISSION_REQUEST)
        false
    }.getOrDefault(false)

    /** Whether a request should run on the background screen: on, and Shizuku ready. */
    fun usable(context: Context): Boolean = Build.VERSION.SDK_INT >= 30 && enabled(context) && permitted()

    /** The display to work on, created on first use; throws [Unavailable] with the reason. */
    fun open(context: Context): Int {
        check(Looper.myLooper() != Looper.getMainLooper()) { "not on the main thread" }
        synchronized(lock) {
            val service = remote?.takeIf { it.asBinder().isBinderAlive } ?: bind(context)
            if (displayId == -1) {
                val metrics = DisplayMetrics()
                @Suppress("DEPRECATION")
                (context.getSystemService(DisplayManager::class.java).getDisplay(Display.DEFAULT_DISPLAY))
                    .getRealMetrics(metrics)
                // Upright, as the phone is usually held.
                val width = minOf(metrics.widthPixels, metrics.heightPixels)
                val height = maxOf(metrics.widthPixels, metrics.heightPixels)
                displayId = service.open(width, height, metrics.densityDpi)
                if (displayId < 0) throw Unavailable("Android did not create the background screen")
                scheduleIdleClose()
            }
            lastUse = SystemClock.elapsedRealtime()
            return displayId
        }
    }

    private fun bind(context: Context): IBackgroundScreen {
        if (Build.VERSION.SDK_INT < 30) throw Unavailable("The background screen needs Android 11 or newer")
        if (!shizukuRunning()) throw Unavailable("Shizuku is not running")
        if (!permitted()) throw Unavailable("Agent Workspace may not use Shizuku yet")
        val latch = CountDownLatch(1)
        var bound: IBackgroundScreen? = null
        val connection = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
                bound = binder?.takeIf { it.pingBinder() }?.let { IBackgroundScreen.Stub.asInterface(it) }
                latch.countDown()
            }
            override fun onServiceDisconnected(name: ComponentName?) {
                remote = null
                displayId = -1
            }
        }
        val args = Shizuku.UserServiceArgs(ComponentName(context.packageName, BackgroundScreenService::class.java.name))
            .daemon(false).processNameSuffix("screen").debuggable(false).version(SERVICE_VERSION)
        main.post { runCatching { Shizuku.bindUserService(args, connection) }.onFailure { latch.countDown() } }
        latch.await(20, TimeUnit.SECONDS)
        val service = bound ?: throw Unavailable("The background screen service did not start")
        this.connection = connection
        remote = service
        displayId = -1
        return service
    }

    private fun scheduleIdleClose() {
        main.postDelayed(object : Runnable {
            override fun run() {
                if (displayId == -1) return
                if (SystemClock.elapsedRealtime() - lastUse >= IDLE_MS) {
                    Thread { close() }.start()
                } else main.postDelayed(this, 60_000)
            }
        }, 60_000)
    }

    /** The open display's id, or -1 (nothing is created). */
    fun currentDisplay(): Int = if (remote?.asBinder()?.isBinderAlive == true) displayId else -1

    fun picture(maxEdge: Int = 1600): Bitmap? = remote?.let { service ->
        lastUse = SystemClock.elapsedRealtime()
        runCatching { service.picture(maxEdge, 85) }.getOrNull()?.let { BitmapFactory.decodeByteArray(it, 0, it.size) }
    }

    /** Starts [intent] on the background screen; the error am printed, or null. */
    fun start(intent: android.content.Intent): String? {
        val service = remote ?: return "no background screen"
        lastUse = SystemClock.elapsedRealtime()
        val uri = android.content.Intent(intent).apply { flags = 0 }.toUri(android.content.Intent.URI_INTENT_SCHEME)
        return runCatching { service.start(uri) }.getOrElse { it.toString() }.takeIf { it.isNotEmpty() }
    }

    fun key(keyCode: Int): String? {
        val service = remote ?: return "no background screen"
        lastUse = SystemClock.elapsedRealtime()
        return runCatching { service.key(keyCode) }.getOrElse { it.toString() }.takeIf { it.isNotEmpty() }
    }

    /** Moves the app on the background screen to the phone's screen; an error, or null. */
    fun bringToFront(): String? {
        val service = remote ?: return "no background screen"
        return runCatching { service.bringToFront() }.getOrElse { it.toString() }.takeIf { it.isNotEmpty() }
    }

    fun close() {
        synchronized(lock) {
            runCatching { remote?.close() }
            displayId = -1
        }
    }
}
