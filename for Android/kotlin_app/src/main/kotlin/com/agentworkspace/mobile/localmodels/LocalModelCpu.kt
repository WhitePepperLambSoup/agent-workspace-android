package com.agentworkspace.mobile.localmodels

/** Chooses the native inference library built for this CPU (see src/main/cpp/CMakeLists.txt). */
object LocalModelCpu {
    const val BASELINE_LIBRARY = "agent_qwen"
    const val DOTPROD_LIBRARY = "agent_qwen_dotprod"

    /**
     * The dot-product build uses ARMv8.2 dot product and FP16 vector instructions, which
     * crash a core without them. It is chosen only when every core lists both features.
     */
    fun library(abi: String?, cpuinfo: String?): String {
        if (abi != "arm64-v8a" || cpuinfo == null) return BASELINE_LIBRARY
        val cores = Regex("(?m)^Features\\s*:(.*)$").findAll(cpuinfo)
            .map { it.groupValues[1].trim().split(Regex("\\s+")).toSet() }.toList()
        val supported = cores.isNotEmpty() && cores.all { "asimddp" in it && "asimdhp" in it }
        return if (supported) DOTPROD_LIBRARY else BASELINE_LIBRARY
    }
}
