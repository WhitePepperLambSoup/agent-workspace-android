package com.agentworkspace.mobile.embedded

import android.app.ActivityManager
import android.app.ApplicationExitInfo
import android.content.Context
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.RandomAccessFile
import java.time.Instant

/**
 * Why this app's processes ended last time (Android 11+ keeps the reasons): an update, the user
 * swiping the app away, the system reclaiming memory, a phone maker's power manager, a crash. Read
 * at the next start and appended to agent-data/logs/process-exits.log, so a report can tell a
 * replaced engine from one the system killed.
 */
object ProcessExits {
    const val NAME = "process-exits.log"
    private const val MAX_BYTES = 64 * 1024
    private const val SEEN = "process-exits.seen"
    /** A day: what counts as "recently" for the background-running prompt. */
    private const val RECENT_MS = 24 * 60 * 60 * 1000L

    /** Reasons that mean Android or the phone maker ended the process, not the user or an update. */
    private val SYSTEM_KILLS = setOf("low_memory", "signaled", "freezer", "excessive_resource_usage", "other", "anr")

    fun file(context: Context): File = File(context.filesDir, "agent-data/logs/$NAME")

    /** Records exits not seen before; returns them. Safe to call from both app processes. */
    fun record(context: Context): List<JSONObject> {
        if (Build.VERSION.SDK_INT < 30) return emptyList()
        return runCatching {
            val logs = File(context.filesDir, "agent-data/logs").apply { mkdirs() }
            RandomAccessFile(File(logs, "process-exits.lock"), "rw").use { lock ->
                lock.channel.lock().use {
                    val seenFile = File(logs, SEEN)
                    val seen = seenFile.takeIf { it.isFile }?.readText()?.trim()?.toLongOrNull() ?: 0L
                    val manager = context.getSystemService(ActivityManager::class.java)
                    val fresh = manager.getHistoricalProcessExitReasons(context.packageName, 0, 32)
                        .filter { it.timestamp > seen }.sortedBy { it.timestamp }.map(::describe)
                    if (fresh.isNotEmpty()) {
                        val log = file(context)
                        if (log.isFile && log.length() > MAX_BYTES) log.renameTo(File(logs, "$NAME.1"))
                        log.appendText(fresh.joinToString("") { line(it) + "\n" })
                        seenFile.writeText(fresh.last().getLong("timestamp").toString())
                    }
                    fresh
                }
            }
        }.getOrDefault(emptyList())
    }

    /** The engine process ended by the system (not the user, not an update) within the last day. */
    fun recentSystemKills(context: Context, now: Long = System.currentTimeMillis()): JSONArray {
        val result = JSONArray()
        val log = file(context)
        if (!log.isFile) return result
        runCatching {
            log.readLines().mapNotNull { runCatching { JSONObject(it.substringAfter(' ')) }.getOrNull() }
                .filter { now - it.optLong("timestamp") in 0..RECENT_MS }
                .filter { it.optString("process").endsWith(":engine") && it.optString("reason") in SYSTEM_KILLS }
                .forEach { result.put(it) }
        }
        return result
    }

    internal fun line(exit: JSONObject): String = "${Instant.ofEpochMilli(exit.optLong("timestamp"))} $exit"

    private fun describe(info: ApplicationExitInfo): JSONObject = JSONObject()
        .put("timestamp", info.timestamp)
        .put("process", info.processName)
        .put("reason", reasonName(info.reason))
        .put("status", info.status)
        .put("importance", importanceName(info.importance))
        .put("pss_mb", info.pss / 1024)
        .put("rss_mb", info.rss / 1024)
        .apply { info.description?.takeIf { it.isNotBlank() }?.let { put("description", it.take(200)) } }

    internal fun reasonName(reason: Int): String = when (reason) {
        ApplicationExitInfo.REASON_EXIT_SELF -> "exit_self"
        ApplicationExitInfo.REASON_SIGNALED -> "signaled"
        ApplicationExitInfo.REASON_LOW_MEMORY -> "low_memory"
        ApplicationExitInfo.REASON_CRASH -> "crash"
        ApplicationExitInfo.REASON_CRASH_NATIVE -> "crash_native"
        ApplicationExitInfo.REASON_ANR -> "anr"
        ApplicationExitInfo.REASON_INITIALIZATION_FAILURE -> "initialization_failure"
        ApplicationExitInfo.REASON_PERMISSION_CHANGE -> "permission_change"
        ApplicationExitInfo.REASON_EXCESSIVE_RESOURCE_USAGE -> "excessive_resource_usage"
        ApplicationExitInfo.REASON_USER_REQUESTED -> "user_requested"
        ApplicationExitInfo.REASON_USER_STOPPED -> "user_stopped"
        ApplicationExitInfo.REASON_DEPENDENCY_DIED -> "dependency_died"
        ApplicationExitInfo.REASON_OTHER -> "other"
        // Added in Android 14, after the SDK constants above.
        14 -> "freezer"
        15 -> "package_state_change"
        16 -> "package_updated"
        else -> "unknown_$reason"
    }

    private fun importanceName(importance: Int): String = when {
        importance <= ActivityManager.RunningAppProcessInfo.IMPORTANCE_FOREGROUND -> "foreground"
        importance <= ActivityManager.RunningAppProcessInfo.IMPORTANCE_FOREGROUND_SERVICE -> "foreground_service"
        importance <= ActivityManager.RunningAppProcessInfo.IMPORTANCE_VISIBLE -> "visible"
        importance <= ActivityManager.RunningAppProcessInfo.IMPORTANCE_SERVICE -> "service"
        importance <= ActivityManager.RunningAppProcessInfo.IMPORTANCE_CACHED -> "cached"
        else -> "gone"
    }
}
