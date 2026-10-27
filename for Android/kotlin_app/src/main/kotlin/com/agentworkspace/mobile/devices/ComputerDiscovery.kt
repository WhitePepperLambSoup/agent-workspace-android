package com.agentworkspace.mobile.devices

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Handler
import android.os.Looper
import java.net.Inet4Address
import java.net.Inet6Address
import java.net.InetAddress
import java.util.ArrayDeque
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject

/**
 * Computers on this network with the phone connection turned on: Agent Workspace announces
 * `_agentworkspace._tcp` (docs/DEVICE_LINK_V2.md 2.6) with its desktop id, whether it uses HTTPS,
 * its certificate fingerprint and whether it is showing a pairing code.
 *
 * What an announcement says proves nothing (anyone on the network can announce), so a found
 * computer only fills in the address; the user still compares the fingerprint or scans the code.
 */
object ComputerDiscovery {
    private const val SERVICE_TYPE = "_agentworkspace._tcp."
    private val HEX = Regex("[0-9a-f]{64}")
    private val ID = Regex("[A-Za-z0-9._:-]{1,128}")

    @Volatile private var context: Context? = null

    @JvmStatic fun initialize(context: Context) { this.context = context.applicationContext }

    data class Found(
        val name: String,
        val url: String,
        val tls: Boolean,
        val fingerprint: String?,
        val id: String?,
        val pairing: Boolean,
    ) {
        fun json(): JSONObject = JSONObject().put("name", name).put("url", url).put("tls", tls)
            .put("fingerprint", fingerprint ?: JSONObject.NULL).put("id", id ?: JSONObject.NULL)
            .put("pairing", pairing)
    }

    /** For the engine (mobile_link): blocks for up to [timeoutMs] and returns a JSON array. */
    @JvmStatic
    fun discoverJson(timeoutMs: Int): String {
        val app = context ?: return "[]"
        val latch = CountDownLatch(1)
        var result: List<Found> = emptyList()
        discover(app, timeoutMs.coerceIn(1000, 15000).toLong()) { found ->
            result = found
            latch.countDown()
        }
        latch.await(timeoutMs.coerceIn(1000, 15000).toLong() + 3000, TimeUnit.MILLISECONDS)
        return JSONArray(result.map { it.json() }).toString()
    }

    /**
     * Looks for [timeoutMs], resolving each announcement one at a time (older Android versions
     * resolve one service at a time), then hands back what was found, computers waiting to pair first.
     */
    fun discover(context: Context, timeoutMs: Long, done: (List<Found>) -> Unit) {
        val manager = context.getSystemService(NsdManager::class.java)
        if (manager == null) { done(emptyList()); return }
        val main = Handler(Looper.getMainLooper())
        val pending = ArrayDeque<NsdServiceInfo>()
        val found = LinkedHashMap<String, Found>()
        var resolving = false
        var finished = false

        fun resolveNext() {
            if (finished || resolving) return
            val next = pending.pollFirst() ?: return
            resolving = true
            @Suppress("DEPRECATION")
            manager.resolveService(next, object : NsdManager.ResolveListener {
                override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                    main.post { resolving = false; resolveNext() }
                }

                override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
                    main.post {
                        resolving = false
                        parse(serviceInfo)?.let { found[it.id ?: it.url] = it }
                        resolveNext()
                    }
                }
            })
        }

        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) {}
            override fun onDiscoveryStopped(serviceType: String) {}
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                main.post { if (!finished) { finished = true; done(emptyList()) } }
            }
            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {}
            override fun onServiceLost(serviceInfo: NsdServiceInfo) {}
            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                main.post {
                    if (pending.size < 32) pending.addLast(serviceInfo)
                    resolveNext()
                }
            }
        }
        try {
            manager.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener)
        } catch (_: Exception) {
            done(emptyList())
            return
        }
        main.postDelayed({
            if (finished) return@postDelayed
            finished = true
            runCatching { manager.stopServiceDiscovery(listener) }
            done(found.values.sortedWith(compareByDescending<Found> { it.pairing }.thenBy { it.name }))
        }, timeoutMs)
    }

    private fun parse(info: NsdServiceInfo): Found? {
        val attributes = runCatching { info.attributes }.getOrNull() ?: emptyMap()
        fun text(key: String): String? = attributes[key]?.let { String(it, Charsets.UTF_8) }?.trim()?.takeIf { it.isNotEmpty() }
        if (text("v") != "1") return null
        @Suppress("DEPRECATION")
        val address: InetAddress = info.host ?: return null
        if (address.isLoopbackAddress || address.isMulticastAddress) return null
        val port = info.port.takeIf { it in 1..65535 } ?: return null
        val tls = text("tls") == "1"
        val host = when (address) {
            is Inet6Address -> "[${address.hostAddress?.substringBefore('%')}]"
            is Inet4Address -> address.hostAddress ?: return null
            else -> return null
        }
        val fingerprint = text("fp")?.lowercase()?.takeIf { tls && HEX.matches(it) }
        if (tls && fingerprint == null) return null
        return Found(
            name = info.serviceName.take(100),
            url = "${if (tls) "https" else "http"}://$host:$port",
            tls = tls,
            fingerprint = fingerprint,
            id = text("id")?.takeIf { ID.matches(it) },
            pairing = text("pair") == "1",
        )
    }
}
