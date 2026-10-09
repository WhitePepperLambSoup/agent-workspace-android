package com.agentworkspace.mobile.localmodels

import org.json.JSONObject
import kotlin.math.ceil

/** Settings and measured-rate calculations independent of Android and JNI. */
object LocalModelPerformance {
    const val MAX_THREADS = 64
    const val MAX_TIMEOUT_SECONDS = 7200
    data class Settings(val contextTokens: Int = 0, val threads: Int = 0, val timeoutSeconds: Int = 0)

    fun integer(value: JSONObject, key: String, maximum: Int, fallback: Int = 0): Int {
        if (!value.has(key)) return fallback
        val raw = value.opt(key)
        require(raw is Int && raw in 0..maximum) { "Invalid $key" }
        return raw
    }

    fun settings(value: JSONObject) = Settings(
        integer(value, "local_context_tokens", 262144),
        integer(value, "local_threads", MAX_THREADS),
        integer(value, "local_timeout_seconds", MAX_TIMEOUT_SECONDS),
    )

    fun threads(configured: Int, processors: Int): Int {
        require(configured in 0..MAX_THREADS)
        val available = processors.coerceIn(1, MAX_THREADS)
        return if (configured == 0) minOf(4, available) else minOf(configured, available)
    }

    /** PowerManager.THERMAL_STATUS_* values, kept here so the rule runs without Android. */
    const val THERMAL_STATUS_MODERATE = 2
    const val THERMAL_STATUS_SEVERE = 3

    // On a Snapdragon 888 one long 2B task at 4 threads held the big cores at 95 °C until
    // Android raised its overheat warning. That phone's thermal HAL defines no MODERATE
    // level (status jumps from NONE to SEVERE), so also follow the thermal headroom,
    // where 1.0 is SEVERE (skin 55 °C there, 0.6 ≈ 43 °C, 0.75 ≈ 47.5 °C). Back off
    // early so work continues while the phone cools: half the threads first, then a
    // single thread. With half the threads a long write still climbed to 50 °C on the
    // charger, so one thread takes over below that. Headroom is NaN when unknown.
    fun thermalThreads(threads: Int, thermalStatus: Int, headroom: Float = Float.NaN): Int = when {
        thermalStatus >= THERMAL_STATUS_SEVERE || headroom >= 0.75f -> 1
        thermalStatus >= THERMAL_STATUS_MODERATE || headroom >= 0.6f -> maxOf(1, threads / 2)
        else -> threads
    }

    fun timeoutSeconds(configured: Int, contextTokens: Int, measured: JSONObject? = null): Int {
        require(configured in 0..MAX_TIMEOUT_SECONDS)
        if (configured > 0) return configured
        // The recommendation projects a full selected context from measured
        // rates. It is not a claim that a full context was tested.
        val promptRate = measured?.optDouble("prompt_tokens_per_second", Double.NaN) ?: Double.NaN
        val outputRate = measured?.optDouble("tokens_per_second", Double.NaN) ?: Double.NaN
        val promptSeconds = if (promptRate.isFinite() && promptRate > 0) contextTokens / promptRate
            else contextTokens.coerceAtLeast(4096) / 16.0
        val outputSeconds = if (outputRate.isFinite() && outputRate > 0) 4096 / outputRate else 614.4
        return ceil(60 + 1.5 * (promptSeconds + outputSeconds)).toInt().coerceIn(180, MAX_TIMEOUT_SECONDS)
    }

    fun mayAttemptAllocation(manualContext: Boolean, estimateFeasible: Boolean) = manualContext || estimateFeasible

    fun memoryFields(procStatus: String): Pair<Long?, Long?> {
        fun bytes(name: String): Long? {
            val match = Regex("(?m)^$name:\\s+(\\d+)\\s+kB\\s*$").find(procStatus) ?: return null
            val kib = match.groupValues[1].toLongOrNull() ?: return null
            return if (kib <= Long.MAX_VALUE / 1024) kib * 1024 else null
        }
        return bytes("VmRSS") to bytes("VmHWM")
    }
}
