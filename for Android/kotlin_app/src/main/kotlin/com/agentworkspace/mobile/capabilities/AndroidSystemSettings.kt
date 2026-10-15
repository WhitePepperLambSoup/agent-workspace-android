package com.agentworkspace.mobile.capabilities

import android.app.NotificationManager
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.os.SystemClock
import android.provider.Settings
import android.view.KeyEvent
import org.json.JSONObject
import kotlin.math.roundToInt

/**
 * The phone's quick switches for the system_status / system_settings tools: volume, brightness,
 * Do Not Disturb, media playback, and the Wi-Fi, Bluetooth and other panels. What Android lets
 * an app change directly is changed (volume, media keys; brightness and Do Not Disturb once the
 * user has granted those two settings); Wi-Fi and Bluetooth can only be switched by the user, so
 * their panel opens for them (or phone control taps the switch).
 */
object AndroidSystemSettings {
    @Volatile private var context: Context? = null

    @JvmStatic fun initialize(context: Context) { this.context = context.applicationContext }

    private val streams = mapOf(
        "media" to AudioManager.STREAM_MUSIC, "ring" to AudioManager.STREAM_RING,
        "alarm" to AudioManager.STREAM_ALARM, "notification" to AudioManager.STREAM_NOTIFICATION,
    )

    @JvmStatic
    fun execute(raw: String): String {
        val app = context ?: return fail("unavailable", "The phone settings bridge is not ready")
        return try {
            val request = JSONObject(raw)
            when (request.optString("action")) {
                "status" -> status(app)
                "volume" -> volume(app, request)
                "brightness" -> brightness(app, request)
                "dnd" -> dnd(app, request)
                "media" -> media(app, request)
                "open" -> open(app, request)
                else -> fail("invalid_arguments", "Unknown action")
            }.toString()
        } catch (error: SecurityException) {
            fail("permission_required", error.message ?: "Android refused the change")
        } catch (error: Exception) {
            fail("failed", error.message ?: error.javaClass.simpleName)
        }
    }

    private fun fail(code: String, message: String): String =
        JSONObject().put("ok", false).put("code", code).put("error", message).toString()

    private fun ok() = JSONObject().put("ok", true)

    private fun status(app: Context): JSONObject {
        val audio = app.getSystemService(AudioManager::class.java)
        val notifications = app.getSystemService(NotificationManager::class.java)
        val volumes = JSONObject()
        for ((name, stream) in streams) {
            val max = audio.getStreamMaxVolume(stream)
            volumes.put(name, JSONObject().put("level", audio.getStreamVolume(stream)).put("max", max)
                .put("percent", if (max > 0) (audio.getStreamVolume(stream) * 100.0 / max).roundToInt() else 0))
        }
        val resolver = app.contentResolver
        return ok()
            .put("wifi_enabled", runCatching { app.getSystemService(WifiManager::class.java).isWifiEnabled }.getOrNull() ?: JSONObject.NULL)
            .put("bluetooth_enabled", runCatching { app.getSystemService(BluetoothManager::class.java).adapter?.isEnabled }.getOrNull() ?: JSONObject.NULL)
            .put("do_not_disturb", notifications.currentInterruptionFilter > NotificationManager.INTERRUPTION_FILTER_ALL)
            .put("do_not_disturb_access", notifications.isNotificationPolicyAccessGranted)
            .put("brightness_percent", runCatching { (Settings.System.getInt(resolver, Settings.System.SCREEN_BRIGHTNESS) * 100.0 / 255).roundToInt() }.getOrNull() ?: JSONObject.NULL)
            .put("brightness_auto", runCatching { Settings.System.getInt(resolver, Settings.System.SCREEN_BRIGHTNESS_MODE) == 1 }.getOrNull() ?: JSONObject.NULL)
            .put("brightness_access", Settings.System.canWrite(app))
            .put("volumes", volumes)
            .put("music_playing", audio.isMusicActive)
    }

    private fun volume(app: Context, request: JSONObject): JSONObject {
        val stream = streams[request.optString("stream", "media")] ?: throw IllegalArgumentException("stream must be media, ring, alarm or notification")
        val percent = request.getInt("percent").coerceIn(0, 100)
        val audio = app.getSystemService(AudioManager::class.java)
        val max = audio.getStreamMaxVolume(stream)
        audio.setStreamVolume(stream, (percent * max / 100.0).roundToInt(), 0)
        return ok().put("stream", request.optString("stream", "media")).put("level", audio.getStreamVolume(stream)).put("max", max)
    }

    private fun brightness(app: Context, request: JSONObject): JSONObject {
        if (!Settings.System.canWrite(app)) return JSONObject(fail("permission_required",
            "Changing brightness needs the 'modify system settings' permission for Agent Workspace. Open it with " +
                "action open, panel write_settings, and ask the user to allow it."))
        val resolver = app.contentResolver
        if (request.optBoolean("auto")) {
            Settings.System.putInt(resolver, Settings.System.SCREEN_BRIGHTNESS_MODE, 1)
            return ok().put("brightness_auto", true)
        }
        val percent = request.getInt("percent").coerceIn(1, 100)
        Settings.System.putInt(resolver, Settings.System.SCREEN_BRIGHTNESS_MODE, 0)
        Settings.System.putInt(resolver, Settings.System.SCREEN_BRIGHTNESS, (percent * 255 / 100.0).roundToInt().coerceIn(1, 255))
        return ok().put("brightness_percent", percent)
    }

    private fun dnd(app: Context, request: JSONObject): JSONObject {
        val notifications = app.getSystemService(NotificationManager::class.java)
        if (!notifications.isNotificationPolicyAccessGranted) return JSONObject(fail("permission_required",
            "Switching Do Not Disturb needs Do Not Disturb access for Agent Workspace. Open it with action open, " +
                "panel dnd_access, and ask the user to allow it."))
        val on = request.getBoolean("on")
        notifications.setInterruptionFilter(if (on) NotificationManager.INTERRUPTION_FILTER_PRIORITY else NotificationManager.INTERRUPTION_FILTER_ALL)
        return ok().put("do_not_disturb", on)
    }

    private fun media(app: Context, request: JSONObject): JSONObject {
        val key = when (request.optString("key")) {
            "play" -> KeyEvent.KEYCODE_MEDIA_PLAY
            "pause" -> KeyEvent.KEYCODE_MEDIA_PAUSE
            "play_pause" -> KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE
            "next" -> KeyEvent.KEYCODE_MEDIA_NEXT
            "previous" -> KeyEvent.KEYCODE_MEDIA_PREVIOUS
            else -> throw IllegalArgumentException("key must be play, pause, play_pause, next or previous")
        }
        val audio = app.getSystemService(AudioManager::class.java)
        val now = SystemClock.uptimeMillis()
        audio.dispatchMediaKeyEvent(KeyEvent(now, now, KeyEvent.ACTION_DOWN, key, 0))
        audio.dispatchMediaKeyEvent(KeyEvent(now, now, KeyEvent.ACTION_UP, key, 0))
        return ok().put("key", request.optString("key")).put("music_playing", audio.isMusicActive)
    }

    private fun open(app: Context, request: JSONObject): JSONObject {
        val panel = request.optString("panel")
        val intent = when (panel) {
            "wifi" -> Intent(if (Build.VERSION.SDK_INT >= 29) Settings.Panel.ACTION_WIFI else Settings.ACTION_WIFI_SETTINGS)
            "internet" -> Intent(if (Build.VERSION.SDK_INT >= 29) Settings.Panel.ACTION_INTERNET_CONNECTIVITY else Settings.ACTION_WIRELESS_SETTINGS)
            "bluetooth" -> Intent(Settings.ACTION_BLUETOOTH_SETTINGS)
            "nfc" -> Intent(if (Build.VERSION.SDK_INT >= 29) Settings.Panel.ACTION_NFC else Settings.ACTION_NFC_SETTINGS)
            "volume" -> Intent(if (Build.VERSION.SDK_INT >= 29) Settings.Panel.ACTION_VOLUME else Settings.ACTION_SOUND_SETTINGS)
            "write_settings" -> Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS, Uri.parse("package:${app.packageName}"))
            "dnd_access" -> Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)
            else -> throw IllegalArgumentException("panel must be wifi, internet, bluetooth, nfc, volume, write_settings or dnd_access")
        }
        app.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        return ok().put("opened", panel)
    }
}
