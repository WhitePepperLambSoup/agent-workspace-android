package com.agentworkspace.mobile.localmodels

import org.json.JSONObject
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/**
 * When the local model runs on the GPU. The GPU library (agent_qwen_opencl, see
 * src/main/cpp/CMakeLists.txt) is the dot-product CPU build plus ggml's OpenCL backend for
 * Qualcomm Adreno GPUs, using the phone's own OpenCL driver.
 *
 * Only Adreno 7xx/8xx and Snapdragon X GPUs are used. On the test phone's Adreno 660 (Snapdragon
 * 888) the driver's compiler ran out of memory on ggml's F16 matrix kernels and ended the process;
 * llama.cpp likewise lists only newer Adreno GPUs and expects phone Adreno 6xx drivers to fail.
 * Before the engine first uses a GPU, LocalModelGpuCheckService compiles every kernel in a
 * process of its own, so a driver that fails there never takes the engine down.
 */
object LocalModelGpu {
    const val LIBRARY = "agent_qwen_opencl"
    const val ALL_LAYERS = 999
    const val MINIMUM_ADRENO = 700
    /** A check that has not reported by then was killed (for example by Android for memory). */
    const val CHECK_TIMEOUT_MS = 10 * 60 * 1000L
    val modes = listOf("auto", "cpu")

    /** The GPU library carries the dot-product CPU code too, so that CPU is required. */
    fun mayLoad(cpuLibrary: String, failed: Boolean) =
        cpuLibrary == LocalModelCpu.DOTPROD_LIBRARY && !failed

    /** The model number in an OpenCL name such as "QUALCOMM Adreno(TM) 740" or "OpenCL 3.0 Adreno(TM) 830". */
    fun adrenoModel(vararg names: String?): Int? = names.firstNotNullOfOrNull { name ->
        name?.let { Regex("Adreno[^0-9]{0,8}([0-9]{3})\\b").find(it)?.groupValues?.get(1)?.toIntOrNull() }
    }

    /** Snapdragon X laptops' GPUs report "X1-85" and similar instead of an Adreno number. */
    private fun adrenoX(vararg names: String?) = names.any { it != null && Regex("Adreno.{0,8}\\bX[0-9]").containsMatchIn(it) }

    fun supported(device: JSONObject?): Boolean {
        if (device == null) return false
        val names = arrayOf(device.optString("version"), device.optString("description"))
        val model = adrenoModel(*names)
        return (model != null && model >= MINIMUM_ADRENO) || adrenoX(*names)
    }

    /** "QUALCOMM Adreno(TM)" with version "OpenCL 2.0 Adreno(TM) 660" → "Adreno 660", for status text. */
    fun displayName(device: JSONObject?): String? {
        if (device == null) return null
        val model = adrenoModel(device.optString("version"), device.optString("description"))
        return if (model != null) "Adreno $model" else device.optString("description").takeIf { it.isNotBlank() }
    }

    /** The result LocalModelGpuCheckService left for this install and system image. */
    data class Check(val identity: String, val ok: Boolean, val message: String?) {
        fun json(): JSONObject = JSONObject().put("identity", identity).put("ok", ok)
            .put("message", message ?: JSONObject.NULL)
    }

    /**
     * Whether generations may use the GPU: "available", or why not. [checkStartedAt] is when this
     * engine process started a check (null: none started).
     */
    fun state(device: JSONObject?, identity: String, check: Check?, checkStartedAt: Long?, now: Long): String = when {
        device == null -> "no_supported_gpu"
        !supported(device) -> "unsupported_gpu"
        check?.identity == identity -> if (check.ok) "available" else "check_failed"
        checkStartedAt == null -> "unchecked"
        now - checkStartedAt < CHECK_TIMEOUT_MS -> "checking"
        else -> "check_failed"
    }

    /** GPU layers for one generation; 0 keeps it on the CPU. */
    fun layers(mode: String, state: String) = if (mode != "cpu" && state == "available") ALL_LAYERS else 0

    /**
     * Saved choice, an engine failure and the GPU an earlier start found, in a file because the
     * app and engine processes both read it.
     */
    data class Saved(val mode: String = "auto", val failure: JSONObject? = null, val gpu: JSONObject? = null) {
        fun json(): JSONObject = JSONObject().put("mode", mode).put("failure", failure ?: JSONObject.NULL)
            .put("gpu", gpu ?: JSONObject.NULL)

        /** A failure recorded by another app build or system image is retried. */
        fun failedFor(identity: String) = failure?.optString("identity") == identity

        /**
         * This install found no GPU it supports ("no_supported_gpu" or "unsupported_gpu"), or
         * null. Such phones then start with a CPU library, as they did before GPU support.
         */
        fun unsupportedFor(identity: String): String? = gpu?.takeIf { it.optString("identity") == identity }
            ?.optString("state")?.takeIf { it == "no_supported_gpu" || it == "unsupported_gpu" }
    }

    /** What to remember about [device] (null: the driver listed no GPU ggml accepts). */
    fun found(device: JSONObject?, identity: String): JSONObject = JSONObject().put("identity", identity)
        .put("state", when { device == null -> "no_supported_gpu"; supported(device) -> "supported"; else -> "unsupported_gpu" })
        .put("name", displayName(device) ?: JSONObject.NULL)

    private fun readObject(file: File): JSONObject? = try {
        if (!file.isFile || file.length() > 16384) null else JSONObject(file.readText(Charsets.UTF_8))
    } catch (_: Exception) { null }

    private fun writeObject(file: File, value: JSONObject) {
        val temporary = File(file.parentFile, "${file.name}.tmp")
        temporary.writeText(value.toString(), Charsets.UTF_8)
        Files.move(temporary.toPath(), file.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE)
    }

    fun read(file: File): Saved = readObject(file)?.let {
        Saved(it.optString("mode").takeIf { mode -> mode in modes } ?: "auto", it.optJSONObject("failure"),
            it.optJSONObject("gpu"))
    } ?: Saved()

    fun write(file: File, saved: Saved) = writeObject(file, saved.json())

    /**
     * This install's check result: what the check process wrote, or a failure from the marker its
     * native code leaves when the driver ends it. Null while a check runs or when none ran.
     */
    fun readCheck(file: File, marker: File, identity: String): Check? {
        val value = readObject(file) ?: return null
        if (value.optString("identity") != identity) return null
        if (value.optBoolean("running")) {
            if (!marker.isFile) return null
            val message = try { marker.readText(Charsets.UTF_8).take(500).trim() } catch (_: Exception) { "" }
            return Check(identity, false, message.ifEmpty { "The GPU check process stopped" })
        }
        return Check(identity, value.optBoolean("ok"),
            value.optString("message").takeIf { it.isNotEmpty() && !value.isNull("message") })
    }

    /** Before starting a check: its marker, if any, is from an earlier check. */
    fun startCheck(file: File, marker: File, identity: String) {
        marker.delete()
        writeObject(file, JSONObject().put("identity", identity).put("running", true))
    }

    fun writeCheck(file: File, check: Check) = writeObject(file, check.json())

    /**
     * Turns an abort marker left by the native engine into a saved failure; returns the updated
     * state. The marker exists only when ggml ended the engine during GPU work.
     */
    fun takeAbort(marker: File, saved: Saved, identity: String, now: Long): Saved {
        if (!marker.isFile) return saved
        val message = try { marker.readText(Charsets.UTF_8).take(500).trim() } catch (_: Exception) { "" }
        marker.delete()
        return saved.copy(failure = JSONObject().put("identity", identity).put("failed_at_ms", now)
            .put("message", message.ifEmpty { "The engine stopped while the GPU library was in use" }))
    }
}
