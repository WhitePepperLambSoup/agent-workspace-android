package com.agentworkspace.mobile.localmodels

/** Device-independent context policy; the bridge supplies current OS memory. */
object LocalModelContext {
    const val MIN_CONTEXT_TOKENS = 512
    const val MAX_OUTPUT_TOKENS = 8192
    const val MAX_PROMPT_BYTES = 4 * 1024 * 1024
    const val MAX_REQUEST_BYTES = 8 * 1024 * 1024
    const val MAX_TOKENIZER_PROMPT_BYTES = 32 * 1024 * 1024
    const val MAX_TOKENIZER_REQUEST_BYTES = 64 * 1024 * 1024
    private const val AUTO_CONTEXT_FLOOR = 4096
    private val choices = listOf(512, 4096, 8192, 16384, 32768, 65536, 131072, 262144)

    data class Plan(
        val contextTokens: Int,
        val configuredTokens: Int,
        val modelMaximumTokens: Int,
        val recommendedTokens: Int,
        val availableRamBytes: Long,
        val availableSwapBytes: Long,
        val requiredBytes: Long,
        val memoryMode: String,
        val supportedContextTokens: List<Int>,
        val feasible: Boolean,
        val visionReserveBytes: Long,
    )

    fun modelMaximumTokens(modelId: String): Int = when {
        modelId == TrainedLocalModel.ID -> 262144
        Regex("qwen3\\.5-(0\\.8b|2b)-(q4-k-m|q8-0)").matches(modelId) -> 262144
        Regex("qwen3-(0\\.6b|1\\.7b)-(q4-k-m|q8-0)").matches(modelId) -> 32768
        else -> throw IllegalArgumentException("Select a supported local Qwen model")
    }

    fun plan(modelId: String, modelBytes: Long, installedSha256: String?, loadedModelId: String?,
              requestedTokens: Int, availableRamBytes: Long, availableSwapBytes: Long,
              lowMemory: Boolean, memoryMode: String, visionProjectionBytes: Long = 0,
              installedModelMaximumTokens: Int = 0, needsVision: Boolean = false): Plan {
        val familyMaximum = modelMaximumTokens(modelId)
        require(installedModelMaximumTokens == 0 || installedModelMaximumTokens >= MIN_CONTEXT_TOKENS)
        val maximum = if (installedModelMaximumTokens > 0) minOf(familyMaximum, installedModelMaximumTokens) else familyMaximum
        require(requestedTokens == 0 || requestedTokens in MIN_CONTEXT_TOKENS..maximum) {
            "Configured context is outside the model limits"
        }
        require(memoryMode == "balanced" || memoryMode == "extended") { "Invalid memory mode" }
        require(availableRamBytes >= 0 && availableSwapBytes >= 0) { "Invalid available memory" }
        require(visionProjectionBytes == 0L || modelId.startsWith("qwen3.5-")) {
            "This model does not support a vision projection"
        }
        require(!needsVision || visionProjectionBytes > 0L) {
            "Image planning requires an installed vision projection"
        }
        // Installation is capability metadata. Only requests with images load
        // the projector and its encoder graphs in the generation bridge.
        val visionReserve = if (!needsVision || visionProjectionBytes == 0L) 0L
                            else LocalModelMemory.visionRequiredBytes(0, visionProjectionBytes)
        val physicalCompute = LocalModelMemory.TEXT_COMPUTE_RESERVE_BYTES +
            if (visionReserve > 0) LocalModelMemory.VISION_COMPUTE_RESERVE_BYTES else 0L
        val supported = choices.filter { it <= maximum }
        fun required(tokens: Int): Long {
            val text = LocalModelMemory.estimate(
                modelId, modelBytes, tokens, loadedModelId, installedSha256).requiredBytes
            return if (visionReserve > 0) LocalModelMemory.visionRequiredBytes(text, visionProjectionBytes) else text
        }
        fun feasible(tokens: Int) = LocalModelMemory.canLoad(lowMemory, availableRamBytes,
            required(tokens), availableSwapBytes, memoryMode, physicalComputeReserveBytes = physicalCompute)
        // Automatic selection retains a physical RAM recommendation in both
        // memory modes. Explicit extended contexts may use current free swap,
        // subject to the separate physical compute working-set requirement.
        val recommended = supported.asReversed().firstOrNull {
            it >= AUTO_CONTEXT_FLOOR && LocalModelMemory.canLoad(lowMemory, availableRamBytes,
                required(it), 0, "balanced", physicalComputeReserveBytes = physicalCompute)
        } ?: 0
        // An infeasible auto plan is explicit. The bridge reports a memory error
        // rather than presenting this minimum fallback as a usable context.
        val selected = if (requestedTokens == 0) recommended.takeIf { it > 0 } ?: MIN_CONTEXT_TOKENS
                       else requestedTokens
        return Plan(selected, requestedTokens, maximum, recommended, availableRamBytes,
            availableSwapBytes, required(selected), memoryMode, supported,
            feasible(selected) && (requestedTokens > 0 || recommended > 0), visionReserve)
    }

    /** SwapTotal is not available RAM; only the current SwapFree field is counted. */
    fun freeSwapBytes(meminfo: String): Long {
        val line = meminfo.lineSequence().firstOrNull { it.startsWith("SwapFree:") } ?: return 0
        val match = Regex("SwapFree:\\s+(\\d+)\\s+kB\\s*").matchEntire(line) ?: return 0
        val kib = match.groupValues[1].toLongOrNull() ?: return 0
        return if (kib <= Long.MAX_VALUE / 1024) kib * 1024 else 0
    }
}
