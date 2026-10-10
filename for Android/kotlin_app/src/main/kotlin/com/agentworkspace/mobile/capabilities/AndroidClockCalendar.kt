package com.agentworkspace.mobile.capabilities

import android.Manifest
import android.app.ActivityManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.ContentUris
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.provider.AlarmClock
import android.provider.CalendarContract
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.agentworkspace.mobile.UiText
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/**
 * Alarms and timers in the phone's own Clock app, and the user's calendar, for the agent's
 * set_alarm, set_timer, list_calendar_events and add_calendar_event tools.
 *
 * The Clock app is opened with its public intents. Android only lets an app open another app's
 * screen while it is itself on screen, so when Agent Workspace is in the background the alarm
 * is offered as a notification the user taps instead. Calendar access needs the calendar
 * permission, which the user grants on Settings → Device & tools.
 */
object AndroidClockCalendar {
    private const val CHANNEL_ID = "agent_clock"
    @Volatile private var applicationContext: Context? = null

    @JvmStatic
    fun initialize(context: Context) { applicationContext = context.applicationContext }

    private fun context(): Context = applicationContext ?: error("Clock and calendar are not initialized")

    private fun failure(code: String, message: String) =
        JSONObject().put("ok", false).put("code", code).put("error", message).toString()

    // ---- Clock app ---------------------------------------------------------------------------

    /** The phone's local date, time and time zone (Python's clock may not know the zone). */
    @JvmStatic
    fun now(): String {
        val now = java.time.ZonedDateTime.now()
        return JSONObject()
            .put("date", now.toLocalDate().toString())
            .put("time", now.format(DateTimeFormatter.ofPattern("HH:mm")))
            .put("weekday", now.dayOfWeek.value)
            .put("zone", now.zone.id)
            .toString()
    }

    @JvmStatic
    fun setAlarm(requestJson: String): String = guarded {
        val request = JSONObject(requestJson)
        var hour = request.optInt("hour", -1)
        var minute = request.optInt("minute", -1)
        if (request.has("in_minutes")) {
            val minutes = request.getInt("in_minutes")
            require(minutes in 1..1440) { "An alarm can be at most 24 hours from now" }
            val at = LocalDateTime.now().plusMinutes(minutes.toLong())
            hour = at.hour
            minute = at.minute
        }
        require(hour in 0..23 && minute in 0..59) { "Alarm time is out of range" }
        val intent = Intent(AlarmClock.ACTION_SET_ALARM)
            .putExtra(AlarmClock.EXTRA_HOUR, hour)
            .putExtra(AlarmClock.EXTRA_MINUTES, minute)
            .putExtra(AlarmClock.EXTRA_SKIP_UI, true)
        val label = request.optString("label").take(60)
        if (label.isNotBlank()) intent.putExtra(AlarmClock.EXTRA_MESSAGE, label)
        val days = request.optJSONArray("days")
        if (days != null && days.length() > 0) {
            intent.putExtra(AlarmClock.EXTRA_DAYS, ArrayList((0 until days.length()).map { days.getInt(it) }
                .onEach { require(it in 1..7) { "Alarm day is out of range" } }))
        }
        val title = UiText.of(context(), "点按设置 %02d:%02d 的闹钟", "Tap to set an alarm for %02d:%02d").format(hour, minute)
        JSONObject(deliver(intent, title, label)).put("time", "%02d:%02d".format(hour, minute)).toString()
    }

    @JvmStatic
    fun setTimer(requestJson: String): String = guarded {
        val request = JSONObject(requestJson)
        val seconds = request.getInt("seconds")
        require(seconds in 1..86400) { "Timer length is out of range" }
        val intent = Intent(AlarmClock.ACTION_SET_TIMER)
            .putExtra(AlarmClock.EXTRA_LENGTH, seconds)
            .putExtra(AlarmClock.EXTRA_SKIP_UI, true)
        val label = request.optString("label").take(60)
        if (label.isNotBlank()) intent.putExtra(AlarmClock.EXTRA_MESSAGE, label)
        val minutes = (seconds + 59) / 60
        val title = UiText.of(context(), "点按开始 %d 分钟计时", "Tap to start a %d-minute timer").format(minutes)
        deliver(intent, title, label)
    }

    private fun deliver(intent: Intent, notificationTitle: String, label: String): String {
        val context = context()
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (intent.resolveActivity(context.packageManager) == null)
            return failure("no_clock_app", "No clock app on this phone accepts alarms or timers")
        if (appOnScreen(context)) {
            context.startActivity(intent)
            return JSONObject().put("ok", true).put("delivered", "clock_app").toString()
        }
        // Opening another app from the background is blocked; a notification is not.
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled())
            return failure("app_in_background", "Open Agent Workspace and ask again: the clock app can only be opened while it is on screen")
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL_ID,
            UiText.of(context, "闹钟与计时", "Alarms and timers"), NotificationManager.IMPORTANCE_HIGH))
        val pending = PendingIntent.getActivity(context, intent.hashCode(), intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle(notificationTitle)
            .setContentText(label.ifBlank { UiText.of(context, "来自 Agent Workspace", "From Agent Workspace") })
            .setContentIntent(pending)
            .setAutoCancel(true)
            .build()
        manager.notify(notificationTitle.hashCode(), notification)
        return JSONObject().put("ok", true).put("delivered", "notification").toString()
    }

    private fun appOnScreen(context: Context): Boolean {
        val manager = context.getSystemService(ActivityManager::class.java) ?: return false
        return manager.runningAppProcesses.orEmpty().any {
            it.processName == context.packageName &&
                it.importance <= ActivityManager.RunningAppProcessInfo.IMPORTANCE_FOREGROUND
        }
    }

    // ---- calendar ----------------------------------------------------------------------------

    @JvmStatic
    fun calendarAccess(context: Context): JSONObject = JSONObject()
        .put("read", granted(context, Manifest.permission.READ_CALENDAR))
        .put("write", granted(context, Manifest.permission.WRITE_CALENDAR))

    private fun granted(context: Context, permission: String) =
        ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

    @JvmStatic
    fun listEvents(requestJson: String): String = guarded {
        val context = context()
        if (!granted(context, Manifest.permission.READ_CALENDAR))
            return@guarded failure("permission_required", "Calendar access is off")
        val request = JSONObject(requestJson)
        val zone = ZoneId.systemDefault()
        val first = if (request.has("start_date")) LocalDate.parse(request.getString("start_date")) else LocalDate.now(zone)
        val days = request.optInt("days", 1)
        require(days in 1..62) { "Ask for at most 62 days of events" }
        val begin = first.atStartOfDay(zone).toInstant().toEpochMilli()
        val end = first.plusDays(days.toLong()).atStartOfDay(zone).toInstant().toEpochMilli()
        val uri = CalendarContract.Instances.CONTENT_URI.buildUpon().also {
            ContentUris.appendId(it, begin)
            ContentUris.appendId(it, end)
        }.build()
        val projection = arrayOf(
            CalendarContract.Instances.TITLE, CalendarContract.Instances.BEGIN, CalendarContract.Instances.END,
            CalendarContract.Instances.ALL_DAY, CalendarContract.Instances.EVENT_LOCATION,
            CalendarContract.Instances.DESCRIPTION, CalendarContract.Instances.CALENDAR_DISPLAY_NAME,
        )
        val events = JSONArray()
        var more = false
        context.contentResolver.query(uri, projection, "${CalendarContract.Instances.VISIBLE} = 1", null,
            "${CalendarContract.Instances.BEGIN} ASC")?.use { cursor ->
            while (cursor.moveToNext()) {
                if (events.length() >= 100) { more = true; break }
                val allDay = cursor.getInt(3) == 1
                // All-day events are stored as UTC midnights.
                val eventZone = if (allDay) ZoneOffset.UTC else zone
                val format = if (allDay) DateTimeFormatter.ISO_LOCAL_DATE else DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")
                val start = java.time.Instant.ofEpochMilli(cursor.getLong(1)).atZone(eventZone)
                val finish = java.time.Instant.ofEpochMilli(cursor.getLong(2)).atZone(eventZone)
                events.put(JSONObject()
                    .put("title", cursor.getString(0).orEmpty().take(200))
                    .put("start", start.format(format))
                    .put("end", (if (allDay) finish.minusDays(1) else finish).format(format))
                    .put("all_day", allDay)
                    .put("location", cursor.getString(4)?.take(200) ?: JSONObject.NULL)
                    .put("notes", cursor.getString(5)?.take(300) ?: JSONObject.NULL)
                    .put("calendar", cursor.getString(6)?.take(80) ?: JSONObject.NULL))
            }
        }
        JSONObject().put("ok", true).put("events", events).put("truncated", more).toString()
    }

    @JvmStatic
    fun addEvent(requestJson: String): String = guarded {
        val context = context()
        if (!granted(context, Manifest.permission.WRITE_CALENDAR) || !granted(context, Manifest.permission.READ_CALENDAR))
            return@guarded failure("permission_required", "Calendar access is off")
        val request = JSONObject(requestJson)
        val title = request.getString("title").trim().take(200)
        require(title.isNotEmpty()) { "An event needs a title" }
        val allDay = request.optBoolean("all_day", false)
        val zone = ZoneId.systemDefault()
        val start: Long
        val end: Long
        if (allDay) {
            val day = LocalDate.parse(request.getString("start").take(10))
            val last = if (request.has("end")) LocalDate.parse(request.getString("end").take(10)) else day
            require(!last.isBefore(day)) { "The event ends before it starts" }
            start = day.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()
            end = last.plusDays(1).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()
        } else {
            val begin = LocalDateTime.parse(request.getString("start").replace(' ', 'T'))
            val finish = if (request.has("end")) LocalDateTime.parse(request.getString("end").replace(' ', 'T'))
                else begin.plusHours(1)
            require(finish.isAfter(begin)) { "The event ends before it starts" }
            start = begin.atZone(zone).toInstant().toEpochMilli()
            end = finish.atZone(zone).toInstant().toEpochMilli()
        }
        val calendar = writableCalendar(context)
            ?: return@guarded failure("no_calendar", "No calendar on this phone accepts new events; add a calendar account first")
        val values = ContentValues().apply {
            put(CalendarContract.Events.CALENDAR_ID, calendar.first)
            put(CalendarContract.Events.TITLE, title)
            put(CalendarContract.Events.DTSTART, start)
            put(CalendarContract.Events.DTEND, end)
            put(CalendarContract.Events.ALL_DAY, if (allDay) 1 else 0)
            put(CalendarContract.Events.EVENT_TIMEZONE, if (allDay) "UTC" else zone.id)
            request.optString("location").take(200).takeIf { it.isNotBlank() }
                ?.let { put(CalendarContract.Events.EVENT_LOCATION, it) }
            request.optString("notes").take(2000).takeIf { it.isNotBlank() }
                ?.let { put(CalendarContract.Events.DESCRIPTION, it) }
        }
        val inserted = context.contentResolver.insert(CalendarContract.Events.CONTENT_URI, values)
            ?: return@guarded failure("insert_failed", "The calendar did not accept the event")
        val eventId = ContentUris.parseId(inserted)
        if (request.has("reminder_minutes")) {
            val minutes = request.getInt("reminder_minutes")
            require(minutes in 0..40320) { "Reminder is out of range" }
            context.contentResolver.insert(CalendarContract.Reminders.CONTENT_URI, ContentValues().apply {
                put(CalendarContract.Reminders.EVENT_ID, eventId)
                put(CalendarContract.Reminders.MINUTES, minutes)
                put(CalendarContract.Reminders.METHOD, CalendarContract.Reminders.METHOD_ALERT)
            })
        }
        JSONObject().put("ok", true).put("event_id", eventId).put("calendar", calendar.second).toString()
    }

    /** The primary writable, visible calendar, else the first one; (id, display name). */
    private fun writableCalendar(context: Context): Pair<Long, String>? {
        val projection = arrayOf(CalendarContract.Calendars._ID, CalendarContract.Calendars.CALENDAR_DISPLAY_NAME)
        val selection = "${CalendarContract.Calendars.VISIBLE} = 1 AND " +
            "${CalendarContract.Calendars.CALENDAR_ACCESS_LEVEL} >= ${CalendarContract.Calendars.CAL_ACCESS_CONTRIBUTOR}"
        return context.contentResolver.query(CalendarContract.Calendars.CONTENT_URI, projection, selection, null,
            "${CalendarContract.Calendars.IS_PRIMARY} DESC, ${CalendarContract.Calendars._ID} ASC")?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getLong(0) to (cursor.getString(1) ?: "") else null
        }
    }

    private inline fun guarded(block: () -> String): String = try {
        block()
    } catch (failure: SecurityException) {
        failure("permission_required", "Android refused access: ${failure.message?.take(200)}")
    } catch (failure: Exception) {
        failure("invalid_request", failure.message?.take(300) ?: "Clock or calendar request failed")
    }
}
