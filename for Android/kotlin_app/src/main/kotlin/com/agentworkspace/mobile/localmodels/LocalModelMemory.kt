package com.agentworkspace.mobile.localmodels

/** Conservative CPU allocation budget for pinned models and fresh contexts. */
object LocalModelMemory {
    private const val MIB = 1024L * 1024
    const val RAM_HEADROOM_BYTES = 512 * MIB
    const val TEXT_COMPUTE_RESERVE_BYTES = 384 * MIB
    /**
     * Without flash attention the attention graph grows with the context. Measured on a ZTE
     * A2022P with Qwen3.5 2B Q4 at 65,536 tokens: 1.58 GB of anonymous memory for KV (768 MiB),
     * recurrent state and compute, i.e. about 384 MiB plus 6 KiB per context token for compute.
     */
    const val COMPUTE_BYTES_PER_TOKEN = 6L * 1024
    const val VISION_COMPUTE_RESERVE_BYTES = 256 * MIB
    private data class PinnedWeights(val bytes: Long, val sha256: String)
    private val hybridWeights = mutableMapOf(
        "qwen3.5-0.8b-q4-k-m" to PinnedWeights(532517120L,
            "bd258782e35f7f458f8aced1adc053e6e92e89bc735ba3be89d38a06121dc517"),
        "qwen3.5-0.8b-q8-0" to PinnedWeights(811843840L,
            "0ad885ffd4bb022fc4f0d33a3308fa108ef8613159d3b3a67e23abca056b7a6c"),
        "qwen3.5-2b-q4-k-m" to PinnedWeights(1280835840L,
            "aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223"),
        "qwen3.5-2b-q8-0" to PinnedWeights(2012012800L,
            "1b04acba824817554f4ce23639bc8495ff70453b8fcb047900c731521021f2c1"),
    ).apply {
        TrainedLocalModel.spec?.let { put(it.id, PinnedWeights(it.bytes, it.sha256)) }
    }

    data class Estimate(
        val weightsBytes: Long,
        val paddedContextTokens: Int,
        val kvBytes: Long,
        val recurrentReserveBytes: Long,
        val computeReserveBytes: Long,
        val verifiedHybridShape: Boolean,
    ) {
        val requiredBytes get() = Math.addExact(Math.addExact(weightsBytes, kvBytes),
            Math.addExact(recurrentReserveBytes, computeReserveBytes))
    }

    fun estimate(
        modelId: String,
        modelBytes: Long,
        contextTokens: Int,
        @Suppress("UNUSED_PARAMETER") loadedModelId: String?,
        installedSha256: String?,
    ): Estimate {
        val maximum = if (modelId.startsWith("qwen3.5-")) 262144 else 32768
        require(contextTokens in 512..maximum) { "Context is outside the model limits" }
        require(modelBytes in 16L..(3L * 1024 * MIB)) { "Weights exceed the phone file limits" }
        val pinned = hybridWeights[modelId]
        val verified = pinned != null && pinned.bytes == modelBytes && pinned.sha256 == installedSha256
        // Pinned llama.cpp pads CPU contexts to 256 tokens. Both Qwen3.5
        // families have six full-attention layers, two KV heads and 256-wide
        // K/V. F16 caches cost 6 * 2 * (256 + 256) * 2 = 12 KiB/token.
        val padded = (((contextTokens.toLong() + 255) / 256) * 256).toInt()
        val kv = padded * if (verified) 12L * 1024 else 128L * 1024
        // The other 18 layers use a context-independent F32 recurrent state:
        // 18 * 4 * ((4 - 1) * (2048 + 2 * 16 * 128) + 128 * 2048)
        // = 20,201,472 bytes at n_seq_max=1, n_rs_seq=0. Reserve over 3x.
        val recurrent = if (verified) 64 * MIB else 0L
        // Weights are memory-mapped. Once loaded, their pages sit in the file cache that Android
        // reports as available memory, so they are charged whether or not the model is loaded;
        // treating loaded weights as free counted the same pages twice.
        return Estimate(
            weightsBytes = modelBytes,
            paddedContextTokens = padded,
            kvBytes = kv,
            recurrentReserveBytes = recurrent,
            computeReserveBytes = TEXT_COMPUTE_RESERVE_BYTES + padded * COMPUTE_BYTES_PER_TOKEN,
            verifiedHybridShape = verified,
        )
    }

    fun canLoad(lowMemory: Boolean, availableBytes: Long, requiredBytes: Long): Boolean =
        !lowMemory && availableBytes >= 0 && requiredBytes >= 0 && availableBytes >= requiredBytes

    /** Extended mode uses measured free swap without giving up the physical working set. */
    fun canLoad(lowMemory: Boolean, availableBytes: Long, requiredBytes: Long,
                availableSwapBytes: Long, memoryMode: String,
                ramReserveBytes: Long = RAM_HEADROOM_BYTES,
                physicalComputeReserveBytes: Long = TEXT_COMPUTE_RESERVE_BYTES): Boolean {
        require(memoryMode == "balanced" || memoryMode == "extended") { "Invalid memory mode" }
        require(availableBytes >= 0 && requiredBytes >= 0 && availableSwapBytes >= 0 &&
            physicalComputeReserveBytes >= 0 &&
            ramReserveBytes in 0..(Long.MAX_VALUE - physicalComputeReserveBytes)) { "Invalid memory estimate" }
        if (lowMemory || availableBytes < ramReserveBytes) return false
        val usableRam = availableBytes - ramReserveBytes
        if (memoryMode == "balanced") return usableRam >= requiredBytes
        // Keep graph evaluation and Android headroom in physical memory. Use a
        // subtraction comparison so enormous OS values cannot overflow a sum.
        if (availableBytes < ramReserveBytes + physicalComputeReserveBytes) return false
        return usableRam >= requiredBytes || availableSwapBytes >= requiredBytes - usableRam
    }

    /** Projectors are released after every call; always count their full CPU weights. */
    fun visionRequiredBytes(textRequiredBytes: Long, projectionBytes: Long): Long {
        require(textRequiredBytes >= 0 && projectionBytes in 16L..(1024 * MIB))
        // Image input is at most 512 pixels per edge and 256 output tokens per
        // image. Keep separate space for encoder graphs, bitmap conversion and
        // temporary embeddings in addition to the text compute reserve.
        require(textRequiredBytes <= Long.MAX_VALUE - projectionBytes - VISION_COMPUTE_RESERVE_BYTES) {
            "Vision memory estimate overflow"
        }
        return textRequiredBytes + projectionBytes + VISION_COMPUTE_RESERVE_BYTES
    }
}
