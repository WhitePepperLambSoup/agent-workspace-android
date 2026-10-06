package com.agentworkspace.mobile.embedded

import android.content.Context
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * agent-data/logs/engine-startup.log: one line per start-up step, written by the service (Python
 * runtime start) and by the engine itself (runtime build, task recovery, server bind). The app reads
 * it to tell a slow start that is still progressing from one that is stuck, and to show the last step.
 */
object EngineStartupLog {
    const val NAME = "engine-startup.log"
    private const val MAX_BYTES = 128 * 1024

    fun file(context: Context): File = File(context.filesDir, "agent-data/logs/$NAME")

    fun append(context: Context, message: String) {
        runCatching {
            val log = file(context)
            log.parentFile?.mkdirs()
            if (log.isFile && log.length() > MAX_BYTES) log.renameTo(File(log.parentFile, "$NAME.1"))
            val time = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date())
            log.appendText("$time [${android.os.Process.myPid()}] $message\n")
        }
    }

    /** Changes whenever a step is logged; 0 when nothing has been logged yet. */
    fun progressMark(context: Context): Long = runCatching { file(context).let { if (it.isFile) it.lastModified() + it.length() else 0L } }.getOrDefault(0L)

    /** The latest step without its timestamp and pid, e.g. "recovering interrupted tasks". */
    fun lastStep(context: Context): String? = runCatching {
        val log = file(context)
        if (!log.isFile) return@runCatching null
        val tail = java.io.RandomAccessFile(log, "r").use { input ->
            val start = (input.length() - 2048).coerceAtLeast(0)
            input.seek(start)
            ByteArray((input.length() - start).toInt()).also(input::readFully)
        }
        String(tail, Charsets.UTF_8).lineSequence().lastOrNull { it.isNotBlank() }
            ?.substringAfter("] ", "")?.trim()?.takeIf { it.isNotEmpty() }?.take(160)
    }.getOrNull()
}
