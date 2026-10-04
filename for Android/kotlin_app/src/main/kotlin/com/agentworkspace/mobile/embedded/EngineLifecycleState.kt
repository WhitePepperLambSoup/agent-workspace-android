package com.agentworkspace.mobile.embedded

import android.content.Context
import android.util.AtomicFile
import org.json.JSONObject
import java.io.File
import java.io.RandomAccessFile

internal class CrossProcessJsonFile(file: File) {
    private val storage = AtomicFile(file)

    fun read(): JSONObject = withLock { readUnlocked() }

    fun update(change: (JSONObject) -> JSONObject): JSONObject = withLock {
        val next = change(readUnlocked())
        val stream = storage.startWrite()
        try {
            stream.write(next.toString().toByteArray(Charsets.UTF_8))
            storage.finishWrite(stream)
        } catch (error: Exception) {
            storage.failWrite(stream)
            throw error
        }
        next
    }

    private fun readUnlocked(): JSONObject {
        if (!storage.baseFile.exists()) return JSONObject()
        return try {
            JSONObject(String(storage.readFully(), Charsets.UTF_8))
        } catch (error: Exception) {
            throw IllegalStateException("Local Android state is corrupt; preserve it before repair", error)
        }
    }

    private fun <T> withLock(action: () -> T): T = synchronized(localLock) {
        storage.baseFile.parentFile?.mkdirs()
        RandomAccessFile(File(storage.baseFile.path + ".lock"), "rw").use { file ->
            file.channel.lock().use { action() }
        }
    }

    companion object { private val localLock = Any() }
}

class EngineLifecycleState @JvmOverloads constructor(context: Context,
    storageFile: File = File(context.filesDir, "engine-lifecycle.json")) {
    private val storage = CrossProcessJsonFile(storageFile)

    fun isManuallyStopped(): Boolean = storage.read().optBoolean("manually_stopped")

    fun markUserStarted() { storage.update { it.put("manually_stopped", false) } }

    /** Automatic starts never override Stop or Android's foreground timeout. */
    fun beginStart(userInitiated: Boolean): Boolean {
        var allowed = false
        storage.update { state ->
            if (userInitiated) {
                state.put("manually_stopped", false).put("requires_user_launch", false)
                    .put("recovery_attempts", 0).put("last_recovery_attempt_ms", 0)
                allowed = true
            } else {
                allowed = !state.optBoolean("manually_stopped") && !state.optBoolean("requires_user_launch")
            }
            state
        }
        return allowed
    }

    fun reserveAutomaticRecovery(nowMillis: Long): Boolean {
        var reserved = false
        storage.update { state ->
            val attempts = state.optInt("recovery_attempts")
            val previous = state.optLong("last_recovery_attempt_ms")
            when {
                state.optBoolean("manually_stopped") || state.optBoolean("requires_user_launch") -> Unit
                attempts >= 3 -> state.put("requires_user_launch", true)
                    .put("reason", "Automatic recovery reached its limit; open the app to recover")
                previous > 0 && nowMillis - previous < 60000L -> Unit
                else -> {
                    state.put("recovery_attempts", attempts + 1).put("last_recovery_attempt_ms", nowMillis)
                        .put("state", "recovery_requested").put("updated_at_ms", nowMillis)
                        .put("reason", "A bounded Android service recovery was requested; existing task outcomes remain authoritative")
                    reserved = true
                }
            }
            state
        }
        return reserved
    }

    fun markForegroundLimited() {
        storage.update { state ->
            state.put("state", "paused_by_system").put("requires_user_launch", true)
                .put("updated_at_ms", System.currentTimeMillis())
                .put("reason", "Android limited foreground execution; open the app to resume. Automatic restart is suppressed.")
        }
    }

    fun markLaunchRequired(reason: String) {
        storage.update { state ->
            state.put("state", "launch_required").put("requires_user_launch", true)
                .put("reason", reason).put("updated_at_ms", System.currentTimeMillis())
        }
    }

    fun markStoppedByUser() { mark("stopped", "Stopped by user", manuallyStopped = true) }

    fun mark(state: String, reason: String? = null, manuallyStopped: Boolean? = null) {
        storage.update {
            it.put("state", state).put("reason", reason ?: JSONObject.NULL)
                .put("updated_at_ms", System.currentTimeMillis())
            if (manuallyStopped != null) it.put("manually_stopped", manuallyStopped)
            if (state in setOf("ready", "running", "waiting_approval")) {
                it.put("last_healthy_at_ms", System.currentTimeMillis())
                    .put("recovery_attempts", 0).put("requires_user_launch", false)
            }
            it
        }
    }

    fun statusJson(): String {
        val status = storage.read()
        val state = status.optString("state", "stopped")
        if (!status.optBoolean("manually_stopped") && state in setOf("starting", "ready", "running", "waiting_approval", "recovering") &&
            System.currentTimeMillis() - status.optLong("updated_at_ms") > 90000L) {
            status.put("state", "paused_by_system")
                .put("reason", "The engine heartbeat is stale; reopen the app to recover tasks.")
        }
        return status.put("manually_stopped", status.optBoolean("manually_stopped"))
            .put("requires_user_launch", status.optBoolean("requires_user_launch"))
            .put("recovery_attempts", status.optInt("recovery_attempts"))
            .put("state", status.optString("state", "stopped")).toString()
    }
}
