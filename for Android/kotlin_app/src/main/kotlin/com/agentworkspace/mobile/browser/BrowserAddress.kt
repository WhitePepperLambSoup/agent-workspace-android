package com.agentworkspace.mobile.browser

import java.net.InetAddress
import java.net.URLDecoder

/**
 * Which addresses the agent's browser may load: http(s), and never the engine's port on this phone,
 * however the address is written. Chromium reads 127.1, 2130706433, 0x7f000001, [::ffff:127.0.0.1],
 * %31%32%37.0.0.1 and "localhost." as this phone, so the host is read the way it reads it. (A name
 * that a DNS server answers with 127.0.0.1 is not caught here.)
 */
internal object BrowserAddress {
    fun allowed(url: String, enginePort: Int): Boolean = webAddress(url) != null && !engine(url, enginePort)

    /** Whether an http(s) address goes to the engine's port on this phone. */
    fun engine(url: String, enginePort: Int): Boolean {
        val (scheme, host, port) = webAddress(url) ?: return false
        val effective = port ?: if (scheme == "https") 443 else 80
        return effective == enginePort && thisPhone(host)
    }

    /** Scheme, host (brackets kept for IPv6) and port of an http(s) address; null for anything else. */
    private fun webAddress(url: String): Triple<String, String, Int?>? {
        val scheme = url.substringBefore(':', "").lowercase()
        if (scheme != "http" && scheme != "https") return null
        // Chromium takes a backslash for a slash in these addresses, and any number of slashes.
        val rest = url.substring(scheme.length + 1).replace('\\', '/').trimStart('/')
        val authority = rest.substringBefore('/').substringBefore('?').substringBefore('#').substringAfterLast('@')
        val host: String
        val portText: String
        if (authority.startsWith("[")) {
            host = authority.substringBefore(']') + "]"
            portText = authority.substringAfter(']', "").removePrefix(":")
        } else {
            host = authority.substringBeforeLast(':')
            portText = if (authority.contains(':')) authority.substringAfterLast(':') else ""
        }
        if (host.isEmpty()) return null
        val port = if (portText.isEmpty()) null else portText.toIntOrNull()?.takeIf { it in 0..65535 } ?: return null
        return Triple(scheme, host, port)
    }

    fun thisPhone(rawHost: String): Boolean {
        val decoded = runCatching { URLDecoder.decode(rawHost.replace("+", "%2B"), "UTF-8") }.getOrDefault(rawHost)
        val host = decoded.lowercase().trimEnd('.')
        if (host == "localhost" || host.endsWith(".localhost")) return true
        if (host.startsWith("[") && host.endsWith("]")) {
            // A literal, read without asking DNS (only its own characters are let through).
            // ::ffff:127.0.0.1 comes back as 127.0.0.1.
            val literal = host.trim('[', ']')
            if (!literal.contains(':') || literal.any { !(it.isDigit() || it in 'a'..'f' || it == ':' || it == '.') }) return false
            val address = runCatching { InetAddress.getByName(literal) }.getOrNull() ?: return false
            return address.isLoopbackAddress || address.isAnyLocalAddress
        }
        val value = ipv4(host) ?: return false
        return value ushr 24 == 127L || value == 0L
    }

    /** An IPv4 address in any form Chromium accepts (1 to 4 parts, decimal, octal or hex), or null. */
    private fun ipv4(host: String): Long? {
        val parts = host.split('.')
        if (parts.isEmpty() || parts.size > 4) return null
        val numbers = parts.map { part ->
            when {
                part.isEmpty() || !part.all { it.isLetterOrDigit() } -> return null
                part.startsWith("0x") || part.startsWith("0X") ->
                    if (part.length == 2) 0L else part.substring(2).toLongOrNull(16)
                part.length > 1 && part.startsWith("0") -> part.substring(1).toLongOrNull(8)
                else -> part.toLongOrNull(10)
            } ?: return null
        }
        if (numbers.dropLast(1).any { it > 255 }) return null
        val last = numbers.last()
        if (last >= 1L shl (8 * (5 - numbers.size))) return null
        var value = last
        numbers.dropLast(1).forEachIndexed { index, number -> value += number shl (8 * (3 - index)) }
        return value
    }
}
