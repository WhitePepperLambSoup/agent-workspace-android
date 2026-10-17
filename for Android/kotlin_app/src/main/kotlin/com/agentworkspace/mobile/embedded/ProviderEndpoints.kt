package com.agentworkspace.mobile.embedded

/**
 * Which provider addresses may use plain HTTP: this phone always; a private network address (a
 * computer at home running Ollama) only when the user turned on "Allow local network HTTP".
 * Public addresses always need HTTPS. The engine applies the same rule (agent_workspace.config).
 */
object ProviderEndpoints {
    private val ipv4 = Regex("""(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})""")
    // fc00::/7, unique local IPv6 addresses: the first hextet starts with fc or fd.
    private val uniqueLocal = Regex("""f[cd][0-9a-f]{0,2}:.*""")

    /** An IP literal in a private range (192.168/16, 10/8, 172.16/12, fc00::/7); names never count. */
    fun isPrivateLanHost(host: String?): Boolean {
        val value = host?.trim()?.removePrefix("[")?.removeSuffix("]")?.lowercase() ?: return false
        ipv4.matchEntire(value)?.let { match ->
            val octets = match.groupValues.drop(1).map { it.toInt() }
            if (octets.any { it > 255 }) return false
            return octets[0] == 10 || (octets[0] == 172 && octets[1] in 16..31) ||
                (octets[0] == 192 && octets[1] == 168)
        }
        return uniqueLocal.matches(value)
    }

    fun isLoopbackHost(host: String?): Boolean = host in listOf("localhost", "127.0.0.1", "::1", "[::1]")

    /** HTTPS anywhere; plain HTTP on this phone, or on a private address when [allowLanHttp]. */
    fun allowed(scheme: String?, host: String?, allowLanHttp: Boolean): Boolean =
        scheme == "https" || (scheme == "http" && (isLoopbackHost(host) || (allowLanHttp && isPrivateLanHost(host))))
}
