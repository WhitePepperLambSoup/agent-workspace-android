package com.agentworkspace.mobile.capabilities

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Geocoder
import android.location.Location
import android.location.LocationManager
import android.net.Uri
import android.os.Build
import android.provider.ContactsContract
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Contacts, the phone's location and text messages for the personal-info tools. Contacts and
 * location work once the user allows them (Settings → Device & tools), like the calendar. A text
 * message is never sent by the app: it opens in the phone's Messages app with the text filled
 * in, and the user taps send (no SMS permission is asked for).
 */
object AndroidPersonalInfo {
    @Volatile private var context: Context? = null

    @JvmStatic fun initialize(context: Context) { this.context = context.applicationContext }

    private fun granted(context: Context, permission: String) =
        context.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED

    @JvmStatic
    fun access(context: Context): JSONObject = JSONObject()
        .put("contacts", granted(context, Manifest.permission.READ_CONTACTS))
        .put("location", granted(context, Manifest.permission.ACCESS_COARSE_LOCATION) ||
            granted(context, Manifest.permission.ACCESS_FINE_LOCATION))

    @JvmStatic
    fun execute(raw: String): String {
        val app = context ?: return fail("unavailable", "The personal info bridge is not ready")
        return try {
            val request = JSONObject(raw)
            when (request.optString("action")) {
                "find_contacts" -> contacts(app, request)
                "location" -> location(app)
                "compose_sms" -> composeSms(app, request)
                else -> JSONObject(fail("invalid_arguments", "Unknown action"))
            }.toString()
        } catch (error: SecurityException) {
            fail("permission_required", error.message ?: "Android refused access")
        } catch (error: Exception) {
            fail("failed", error.message ?: error.javaClass.simpleName)
        }
    }

    private fun fail(code: String, message: String): String =
        JSONObject().put("ok", false).put("code", code).put("error", message).toString()

    private fun contacts(app: Context, request: JSONObject): JSONObject {
        if (!granted(app, Manifest.permission.READ_CONTACTS)) return JSONObject(fail("permission_required", "contacts"))
        val query = request.optString("query").trim()
        require(query.isNotEmpty() && query.length <= 60) { "query must be 1 to 60 characters" }
        val limit = request.optInt("limit", 10).coerceIn(1, 20)
        val uri = Uri.withAppendedPath(ContactsContract.CommonDataKinds.Phone.CONTENT_FILTER_URI, Uri.encode(query))
        val found = LinkedHashMap<String, MutableList<String>>()
        app.contentResolver.query(uri, arrayOf(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
            ContactsContract.CommonDataKinds.Phone.NUMBER), null, null, null)?.use { cursor ->
            while (cursor.moveToNext() && found.size <= limit) {
                val name = cursor.getString(0) ?: continue
                val number = cursor.getString(1) ?: continue
                found.getOrPut(name) { mutableListOf() }.let { if (number !in it && it.size < 4) it.add(number) }
            }
        }
        val list = JSONArray()
        found.entries.take(limit).forEach { (name, numbers) -> list.put(JSONObject().put("name", name).put("numbers", JSONArray(numbers))) }
        return JSONObject().put("ok", true).put("contacts", list)
    }

    private fun location(app: Context): JSONObject {
        val fine = granted(app, Manifest.permission.ACCESS_FINE_LOCATION)
        if (!fine && !granted(app, Manifest.permission.ACCESS_COARSE_LOCATION)) return JSONObject(fail("permission_required", "location"))
        val manager = app.getSystemService(LocationManager::class.java)
        val providers = manager.getProviders(true).filter { it != LocationManager.PASSIVE_PROVIDER }
        if (providers.isEmpty()) return JSONObject(fail("location_off", "Location is turned off on this phone"))
        var best: Location? = null
        if (Build.VERSION.SDK_INT >= 30) {
            val provider = if (fine && LocationManager.GPS_PROVIDER in providers && LocationManager.NETWORK_PROVIDER !in providers)
                LocationManager.GPS_PROVIDER else providers.firstOrNull { it == LocationManager.NETWORK_PROVIDER || it == "fused" } ?: providers.first()
            val latch = CountDownLatch(1)
            manager.getCurrentLocation(provider, null, app.mainExecutor) { best = it; latch.countDown() }
            latch.await(12, TimeUnit.SECONDS)
        }
        if (best == null) best = providers.mapNotNull { runCatching { manager.getLastKnownLocation(it) }.getOrNull() }.maxByOrNull { it.time }
        val here = best ?: return JSONObject(fail("no_fix", "No location yet; try again outdoors or with Wi-Fi on"))
        val result = JSONObject().put("ok", true).put("latitude", here.latitude).put("longitude", here.longitude)
            .put("accuracy_m", here.accuracy.toInt()).put("age_s", (System.currentTimeMillis() - here.time) / 1000)
        // A street address when the phone's geocoder has one (it may need the network).
        runCatching {
            @Suppress("DEPRECATION")
            Geocoder(app, Locale.getDefault()).getFromLocation(here.latitude, here.longitude, 1)?.firstOrNull()
                ?.getAddressLine(0)?.let { result.put("address", it) }
        }
        return result
    }

    private fun composeSms(app: Context, request: JSONObject): JSONObject {
        val to = request.optString("to").trim()
        require(Regex("[0-9+*#() ,;-]{3,200}").matches(to)) { "to must be phone numbers" }
        val body = request.optString("body")
        require(body.length <= 2000) { "the message is longer than 2000 characters" }
        app.startActivity(Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + Uri.encode(to)))
            .putExtra("sms_body", body).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        return JSONObject().put("ok", true).put("opened", "messages").put("to", to)
    }
}
