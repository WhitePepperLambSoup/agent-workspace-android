package com.agentworkspace.mobile.automation

import android.app.ActivityManager
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

    /**
     * [automatic]: the service paused itself, not the user; [reason] says why when it is not an
     * action Android rejected ([INTERRUPTED]: Android asked accessibility services to stop).
     */
    @Synchronized
    fun set(context: Context, paused: Boolean, takeover: Boolean, automatic: Boolean = false, reason: String? = null): JSONObject {
        // Both the UI and engine process can change control state.
        return locked(context) {
            val state = JSONObject().put("paused", paused).put("takeover_requested", takeover)
                .put("automatic", paused && automatic)
                .put("updated_at_ms", System.currentTimeMillis())
                .put("revision", UUID.randomUUID().toString())
            if (paused && automatic && reason != null) state.put("reason", reason)
            write(atomic(context, "control.json"), state)
            state
        }
    }

    const val INTERRUPTED = "interrupted"

    /** What the agent is told when automation is paused, by who or what paused it. */
    fun pausedMessage(control: JSONObject): String {
        val cause = when {
            !control.optBoolean("automatic") -> "The user paused automation. "
            control.optString("reason") == INTERRUPTED ->
                "Automation paused itself because Android asked accessibility services to stop (another app can ask). "
            else -> "Automation paused itself after an action Android rejected or did not confirm. "
        }
        // Said plainly so the agent stops instead of trying to reach the phone some other way.
        return cause + "Stop and tell the user; do not try another way to operate the phone. They can check the screen " +
            "and resume it (Retry in the phone control window, or Resume in Agent Workspace)."
    }

    /**
     * Written once when the accessibility service connects and once when it goes. It used to be
     * rewritten (locked, fsynced) every 2 s on the main thread for as long as the service ran.
     */
    @Synchronized
    fun connected(context: Context, connected: Boolean) {
        runCatching {
            val pid = Process.myPid()
            locked(context) {
                write(atomic(context, "connection.json"), JSONObject()
                    .put("connected", connected).put("elapsed_ms", SystemClock.elapsedRealtime())
                    .put("pid", pid).put("process", runningProcesses(context)[pid] ?: JSONObject.NULL))
            }
        }
    }

    /** Whether the service is connected, asked from another of the app's processes. */
    @Synchronized
    fun hasLiveConnection(context: Context): Boolean = runCatching {
        val value = locked(context) { read(atomic(context, "connection.json")) }
        liveConnection(value, SystemClock.elapsedRealtime(), runningProcesses(context)::get)
    }.getOrDefault(false)

    /**
     * A crash skips the "gone" write, so the process that wrote "connected" must still run, under
     * the same name (a process id can be given again). [processName]: the app's running process
     * with an id, if any.
     */
    fun liveConnection(value: JSONObject, nowElapsed: Long, processName: (Int) -> String?): Boolean {
        val since = value.optLong("elapsed_ms", -1)
        val running = processName(value.optInt("pid", -1)) ?: return false
        val writer = value.optString("process").takeIf { value.has("process") && !value.isNull("process") }
        // elapsedRealtime counts from boot: a larger value was written before the phone restarted.
        return value.optBoolean("connected") && since in 0L..nowElapsed && (writer == null || writer == running)
    }

    private fun runningProcesses(context: Context): Map<Int, String> =
        (context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).runningAppProcesses.orEmpty()
            .associate { it.pid to it.processName }
}
