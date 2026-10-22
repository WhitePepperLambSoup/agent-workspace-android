package com.agentworkspace.mobile.embedded

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.SystemClock
import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * Phone events for automatic triggers (mobile_triggers.py): charging started, Wi-Fi joined, the
 * battery level dropped, headphones or a Bluetooth audio device connected, the phone unlocked, an
 * app opened. All but app openings are watched while the engine service runs; app openings come
 * from the accessibility service and are reported only for apps a trigger names. The engine
 * decides what runs and applies each trigger's cooldown. Calendar triggers need no event here: the
 * engine reads upcoming events itself.
 */
object TriggerEvents {
    private val worker = Executors.newSingleThreadExecutor { Thread(it, "trigger-events") }
    @Volatile private var appPackages: Set<String> = emptySet()
    @Volatile private var fetchedAt = 0L
    private var receiver: BroadcastReceiver? = null
    private var network: ConnectivityManager.NetworkCallback? = null
    private var audio: AudioDeviceCallback? = null
    private var batteryLevel = -1
    private val headsetTypes = setOf(AudioDeviceInfo.TYPE_WIRED_HEADSET, AudioDeviceInfo.TYPE_WIRED_HEADPHONES,
        AudioDeviceInfo.TYPE_BLUETOOTH_A2DP, AudioDeviceInfo.TYPE_BLUETOOTH_SCO, AudioDeviceInfo.TYPE_USB_HEADSET,
        AudioDeviceInfo.TYPE_HEARING_AID, AudioDeviceInfo.TYPE_BLE_HEADSET, AudioDeviceInfo.TYPE_BLE_SPEAKER)

    fun fire(context: Context, kind: String, value: String = "", previous: String = "") {
        val app = context.applicationContext
        worker.execute {
            runCatching {
                EngineHttp.request(app, "POST", "/mobile/triggers/fire",
                    JSONObject().put("kind", kind).put("value", value).put("previous", previous), 30000)
            }
        }
    }

    private fun onBroadcast(app: Context, intent: Intent) {
        when (intent.action) {
            Intent.ACTION_POWER_CONNECTED -> fire(app, "charging")
            Intent.ACTION_USER_PRESENT -> fire(app, "unlock")
            Intent.ACTION_BATTERY_CHANGED -> {
                val scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, 100).takeIf { it > 0 } ?: return
                val level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) * 100 / scale
                val plugged = intent.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) != 0
                // Only drops on battery, and only below the highest mark a trigger may set (90 %).
                if (level in 0 until batteryLevel && !plugged && level <= 90) fire(app, "battery_low", "$level", "$batteryLevel")
                if (level >= 0) batteryLevel = level
            }
        }
    }

    /** The engine added, removed or paused a trigger: read them again at the next app opening. */
    @JvmStatic
    fun invalidate() { fetchedAt = 0L }

    /** From the accessibility service: an app came to the front. */
    fun appOpened(context: Context, packageName: String) {
        val app = context.applicationContext
        worker.execute {
            if (SystemClock.elapsedRealtime() - fetchedAt > 60_000) {
                fetchedAt = SystemClock.elapsedRealtime()
                appPackages = runCatching {
                    val triggers = EngineHttp.request(app, "GET", "/mobile/triggers", null, 5000).body.optJSONArray("triggers")
                    (0 until (triggers?.length() ?: 0)).map { triggers!!.getJSONObject(it) }
                        .filter { it.optString("kind") == "app_open" && it.optBoolean("enabled") }.map { it.optString("value") }.toSet()
                }.getOrDefault(appPackages)
            }
            if (packageName in appPackages) {
                runCatching { EngineHttp.request(app, "POST", "/mobile/triggers/fire", JSONObject().put("kind", "app_open").put("value", packageName), 30000) }
            }
        }
    }

    /** Charging, Wi-Fi, battery, unlocking and audio devices, for as long as the engine service runs. */
    fun start(context: Context) {
        val app = context.applicationContext
        if (receiver == null) {
            receiver = object : BroadcastReceiver() {
                override fun onReceive(context: Context, intent: Intent) = onBroadcast(app, intent)
            }.also {
                app.registerReceiver(it, IntentFilter().apply {
                    addAction(Intent.ACTION_POWER_CONNECTED)
                    addAction(Intent.ACTION_USER_PRESENT)
                    addAction(Intent.ACTION_BATTERY_CHANGED)
                })
            }
        }
        if (audio == null) {
            val registeredAt = SystemClock.elapsedRealtime()
            audio = object : AudioDeviceCallback() {
                override fun onAudioDevicesAdded(added: Array<out AudioDeviceInfo>) {
                    // Registering reports the devices already connected; those are not "connecting".
                    if (SystemClock.elapsedRealtime() - registeredAt < 5000) return
                    // One headset can show up as two devices (media and calls): one event for both.
                    val device = added.firstOrNull { it.isSink && it.type in headsetTypes } ?: return
                    fire(app, "headset", device.productName?.toString().orEmpty())
                }
            }.also { runCatching { app.getSystemService(AudioManager::class.java).registerAudioDeviceCallback(it, null) } }
        }
        if (network == null) {
            val registeredAt = SystemClock.elapsedRealtime()
            network = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    // The network already up when the engine starts is not "joining" one.
                    if (SystemClock.elapsedRealtime() - registeredAt < 5000) return
                    @Suppress("DEPRECATION")
                    val name = runCatching { app.getSystemService(WifiManager::class.java).connectionInfo?.ssid }.getOrNull()
                        ?.takeUnless { it.contains("unknown ssid", ignoreCase = true) }.orEmpty()
                    fire(app, "wifi", name)
                }
            }.also {
                runCatching {
                    app.getSystemService(ConnectivityManager::class.java).registerNetworkCallback(
                        NetworkRequest.Builder().addTransportType(NetworkCapabilities.TRANSPORT_WIFI).build(), it)
                }
            }
        }
    }

    fun stop(context: Context) {
        val app = context.applicationContext
        receiver?.let { runCatching { app.unregisterReceiver(it) } }
        network?.let { runCatching { app.getSystemService(ConnectivityManager::class.java).unregisterNetworkCallback(it) } }
        audio?.let { runCatching { app.getSystemService(AudioManager::class.java).unregisterAudioDeviceCallback(it) } }
        receiver = null
        network = null
        audio = null
        batteryLevel = -1
    }
}
