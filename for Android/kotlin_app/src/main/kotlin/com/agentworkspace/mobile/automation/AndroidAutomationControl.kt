package com.agentworkspace.mobile.automation

import android.content.Context
import android.os.Process
import android.os.SystemClock
import android.util.AtomicFile
import org.json.JSONObject
import java.io.File
import java.io.RandomAccessFile
import java.util.UUID

internal object AndroidAutomationControl {
    private fun directory(context: Context): File = File(context.filesDir, "automation-control").apply {
        check(mkdirs() || isDirectory) { "Automation control directory is unavailable" }
    }

    private fun atomic(context: Context, name: String): AtomicFile = AtomicFile(File(directory(context), name))

    private fun read(file: AtomicFile): JSONObject {
        if (!file.baseFile.exists()) return JSONObject()
        return file.openRead().bufferedReader().use { reader ->
            val value = reader.readText()
            require(value.length <= 4096) { "Automation control data is too large" }
            JSONObject(value)
        }
    }

    private fun write(file: AtomicFile, value: JSONObject) {
        val stream = file.startWrite()
        try {
            stream.write(value.toString().toByteArray(Charsets.UTF_8))
            file.finishWrite(stream)
        } catch (error: Throwable) {
            file.failWrite(stream)
            throw error
        }
    }

    private fun <T> locked(context: Context, operation: () -> T): T {
        RandomAccessFile(File(directory(context), "control.lock"), "rw").use { handle ->
            handle.channel.lock().use { return operation() }
        }
    }

    @Synchronized
    fun readState(context: Context): JSONObject = runCatching {
        locked(context) { read(atomic(context, "control.json")) }
    }.getOrElse {
        JSONObject().put("paused", true).put("takeover_requested", true)
    }

    @Synchronized
    fun set(context: Context, paused: Boolean, takeover: Boolean): JSONObject {
        // Both the UI and engine process can change control state.
        return locked(context) {
            val state = JSONObject().put("paused", paused).put("takeover_requested", takeover)
                .put("updated_at_ms", System.currentTimeMillis())
                .put("revision", UUID.randomUUID().toString())
            write(atomic(context, "control.json"), state)
            state
        }
    }

    @Synchronized
    fun connected(context: Context, connected: Boolean) {
        runCatching {
            locked(context) {
                write(atomic(context, "connection.json"), JSONObject()
                    .put("connected", connected).put("elapsed_ms", SystemClock.elapsedRealtime())
                    .put("pid", Process.myPid()))
            }
        }
    }

    @Synchronized
    fun hasRecentConnection(context: Context): Boolean = runCatching {
        locked(context) {
            val value = read(atomic(context, "connection.json"))
            val age = SystemClock.elapsedRealtime() - value.optLong("elapsed_ms", -1)
            value.optBoolean("connected") && age in 0L..10000L
        }
    }.getOrDefault(false)
}
