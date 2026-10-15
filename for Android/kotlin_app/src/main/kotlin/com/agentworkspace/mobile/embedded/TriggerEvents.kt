package com.agentworkspace.mobile.embedded

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiManager
import android.os.SystemClock
import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * Phone events for automatic triggers (mobile_triggers.py): charging started, Wi-Fi joined, an app
 * opened. Charging and Wi-Fi are watched while the engine service runs; app openings come from the
 * accessibility service and are reported only for apps a trigger names. The engine decides what
 * runs and applies each trigger's cooldown.
 */
object TriggerEvents {
    private val worker = Executors.newSingleThreadExecutor { Thread(it, "trigger-events") }
    @Volatile private var appPackages: Set<String> = emptySet()
    @Volatile private var fetchedAt = 0L
    private var receiver: BroadcastReceiver? = null
    private var network: ConnectivityManager.NetworkCallback? = null

    fun fire(context: Context, kind: String, value: String = "") {
        val app = context.applicationContext
        worker.execute {
            runCatching {
                EngineHttp.request(app, "POST", "/mobile/triggers/fire", JSONObject().put("kind", kind).put("value", value), 30000)
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

    /** Charging and Wi-Fi, for as long as the engine service runs. */
    fun start(context: Context) {
        val app = context.applicationContext
        if (receiver == null) {
            receiver = object : BroadcastReceiver() {
                override fun onReceive(context: Context, intent: Intent) { if (intent.action == Intent.ACTION_POWER_CONNECTED) fire(app, "charging") }
            }.also { app.registerReceiver(it, IntentFilter(Intent.ACTION_POWER_CONNECTED)) }
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
        receiver = null
        network = null
    }
}
