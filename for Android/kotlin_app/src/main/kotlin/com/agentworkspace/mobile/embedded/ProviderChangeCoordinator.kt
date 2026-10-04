package com.agentworkspace.mobile.embedded

/** Serializes settings saves under the engine's task/maintenance reservation. */
class ProviderChangeCoordinator {
    data class Reply(val state: String, val restartRequired: Boolean)

    /** Outcome of releasing a reservation held by a temporary native operation. */
    data class TemporaryRelease(
        val released: Boolean,
        val recoveryRequired: Boolean,
        val restartRequested: Boolean,
    )

    interface Client {
        fun prepare(requireLocalEngine: Boolean): String
        fun commit(lease: String): Reply
        fun status(lease: String): Reply
        fun isCurrent(): Boolean
    }

    class Failure(message: String, cause: Throwable? = null,
                  val restartRequested: Boolean = false, val settingsSaved: Boolean = false) :
        IllegalStateException(message, cause)

    private data class Pending(val client: Client, val lease: String, var settingsSaved: Boolean = false)
    private var pending: Pending? = null

    /** Release a probe lease; lost abort replies cannot justify interrupting a new task. */
    fun releaseTemporary(
        isCurrent: () -> Boolean,
        abort: () -> Reply,
        status: () -> Reply,
        restart: () -> Unit,
    ): TemporaryRelease {
        if (!isCurrent()) return TemporaryRelease(true, false, false)

        var reply: Reply? = null
        var attempts = 0
        while (attempts < 3 && reply == null) {
            attempts++
            if (!isCurrent()) return TemporaryRelease(true, false, false)
            try {
                reply = abort()
            } catch (_: Exception) {
                try { reply = status() } catch (_: Exception) { }
            }
            if (reply?.state !in setOf("aborted", "committed", "expired", "unknown")) reply = null
        }

        return when {
            reply?.state == "aborted" -> TemporaryRelease(true, false, false)
            reply?.state in setOf("committed", "expired") && reply?.restartRequired == true -> {
                if (!isCurrent()) return TemporaryRelease(true, false, false)
                try {
                    restart()
                    TemporaryRelease(false, true, true)
                } catch (_: Exception) {
                    TemporaryRelease(false, true, false)
                }
            }
            else -> TemporaryRelease(false, true, false)
        }
    }

    @Synchronized
    fun change(client: Client, requireLocalEngine: Boolean, save: () -> Unit, restart: () -> Unit) {
        val previous = pending
        if (previous != null) {
            // Recover an earlier save before another UI entrypoint can overwrite it.
            val recovery = if (previous.client.isCurrent()) previous else {
                prepare(client, false).also { it.settingsSaved = previous.settingsSaved }
            }
            pending = recovery
            finish(recovery, restart, null)
            throw Failure("上次设置正在恢复，请等待引擎重新连接后再修改", restartRequested = true,
                settingsSaved = recovery.settingsSaved)
        }

        val reservation = prepare(client, requireLocalEngine)
        pending = reservation
        var saveFailure: Exception? = null
        try {
            save()
            reservation.settingsSaved = true
        } catch (error: Exception) {
            // A credential or preferences write may have succeeded before the error.
            saveFailure = error
        }
        finish(reservation, restart, saveFailure)
    }

    private fun prepare(client: Client, requireLocalEngine: Boolean): Pending = try {
        val lease = client.prepare(requireLocalEngine)
        check(lease.isNotBlank()) { "The engine returned an invalid provider reservation" }
        Pending(client, lease)
    } catch (error: Exception) {
        throw Failure("无法预留模型设置变更；请先连接引擎并完成执行中及排队的任务", error)
    }

    private fun finish(reservation: Pending, restart: () -> Unit, saveFailure: Exception?) {
        checkCurrent(reservation)
        var confirmed: Reply? = null
        var responseFailure: Exception? = null
        for (attempt in 0 until 3) {
            checkCurrent(reservation)
            try {
                confirmed = reservation.client.commit(reservation.lease)
            } catch (error: Exception) {
                responseFailure = error
                try {
                    confirmed = reservation.client.status(reservation.lease)
                } catch (statusError: Exception) {
                    responseFailure = statusError
                }
            }
            if (confirmed?.state in setOf("committed", "expired", "aborted", "unknown")) break
        }
        checkCurrent(reservation)
        if (confirmed != null && (confirmed.state in setOf("aborted", "unknown") ||
            (confirmed.state in setOf("committed", "expired") && !confirmed.restartRequired))) {
            throw Failure("设置预留状态无法确认，请先重新连接引擎", responseFailure,
                settingsSaved = reservation.settingsSaved)
        }
        // No abort was sent. A prepared, committed, or expired lease retains exclusive
        // admission even when all replies were lost. Restart is fenced again in the service.
        try {
            restart()
        } catch (error: Exception) {
            throw Failure("设置恢复需要重启引擎，请点击重启后再修改设置", error,
                settingsSaved = reservation.settingsSaved)
        }
        pending = null
        if (saveFailure != null) {
            throw Failure("设置未完全保存，引擎正在重新连接：${saveFailure.message ?: "保存失败"}", saveFailure,
                restartRequested = true, settingsSaved = false)
        }
        if (confirmed?.state == "expired") {
            throw Failure("设置保存期间预留已过期，引擎正在恢复；请重新连接后确认设置",
                restartRequested = true, settingsSaved = reservation.settingsSaved)
        }
        if (confirmed?.state != "committed") {
            throw Failure("设置已保存，但未收到提交确认；引擎正在恢复，请重新连接后确认设置", responseFailure,
                restartRequested = true, settingsSaved = reservation.settingsSaved)
        }
    }

    private fun checkCurrent(reservation: Pending) {
        if (!reservation.client.isCurrent()) {
            throw Failure("保存期间引擎已更换，请先重新连接；后续修改将先恢复已保存的设置",
                settingsSaved = reservation.settingsSaved)
        }
    }
}
