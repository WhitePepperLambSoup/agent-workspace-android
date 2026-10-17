package com.agentworkspace.mobile.embedded

import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.InputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.net.URL

/**
 * A plain HTTP/1.1 GET over a socket, for a private-network server the user allowed (Ollama on a
 * computer at home). Android's network policy keeps the platform HTTP stack off cleartext for
 * everything but this phone, and that stays so; only this path reads such a server. No redirects
 * are followed: the caller treats 3xx like any other answer.
 */
object PlainHttp {
    class TooLarge : IOException("response too large")

    private const val MAX_LINE = 8 * 1024
    private const val MAX_HEADERS = 100

    /** The status and body of `GET url`; at most [maxBytes] of body. */
    fun get(url: URL, headers: Map<String, String>, maxBytes: Int, connectMillis: Int = 8000, readMillis: Int = 15000): Pair<Int, ByteArray> {
        require(url.protocol == "http") { "plain HTTP only" }
        val port = if (url.port > 0) url.port else 80
        Socket().use { socket ->
            socket.connect(InetSocketAddress(url.host, port), connectMillis)
            socket.soTimeout = readMillis
            val path = url.path.ifEmpty { "/" } + (url.query?.let { "?$it" } ?: "")
            val host = if (url.port > 0) "${url.host}:${url.port}" else url.host
            val request = StringBuilder("GET $path HTTP/1.1\r\nHost: $host\r\nAccept: application/json\r\n")
                .append("Connection: close\r\nUser-Agent: AgentWorkspace\r\n")
            headers.forEach { (name, value) ->
                require(name.none { it == '\r' || it == '\n' } && value.none { it == '\r' || it == '\n' }) { "invalid header" }
                request.append(name).append(": ").append(value).append("\r\n")
            }
            request.append("\r\n")
            socket.getOutputStream().apply { write(request.toString().toByteArray(Charsets.UTF_8)); flush() }
            return read(BufferedInputStream(socket.getInputStream()), maxBytes)
        }
    }

    /** Parses one response: status line, headers, then a sized, chunked or until-close body. */
    internal fun read(input: InputStream, maxBytes: Int): Pair<Int, ByteArray> {
        val statusLine = line(input) ?: throw IOException("no response")
        val status = Regex("""HTTP/1\.[01] (\d{3})(?: .*)?""").matchEntire(statusLine)?.groupValues?.get(1)?.toInt()
            ?: throw IOException("not an HTTP response")
        val fields = mutableMapOf<String, String>()
        repeat(MAX_HEADERS) {
            val header = line(input) ?: throw IOException("headers cut short")
            if (header.isEmpty()) {
                val chunked = fields["transfer-encoding"]?.contains("chunked", ignoreCase = true) == true
                val length = fields["content-length"]?.trim()?.toLongOrNull()
                val body = when {
                    chunked -> chunked(input, maxBytes)
                    length != null -> exactly(input, length, maxBytes)
                    else -> untilClose(input, maxBytes)
                }
                return status to body
            }
            val colon = header.indexOf(':')
            if (colon > 0) fields[header.substring(0, colon).trim().lowercase()] = header.substring(colon + 1).trim()
        }
        throw IOException("too many headers")
    }

    private fun line(input: InputStream): String? {
        val bytes = ByteArrayOutputStream()
        while (true) {
            val next = input.read()
            if (next < 0) return if (bytes.size() == 0) null else bytes.toString(Charsets.ISO_8859_1.name())
            if (next == '\n'.code) break
            bytes.write(next)
            if (bytes.size() > MAX_LINE) throw IOException("line too long")
        }
        return bytes.toString(Charsets.ISO_8859_1.name()).removeSuffix("\r")
    }

    private fun exactly(input: InputStream, length: Long, maxBytes: Int): ByteArray {
        if (length > maxBytes) throw TooLarge()
        val body = ByteArray(length.toInt())
        var read = 0
        while (read < body.size) {
            val count = input.read(body, read, body.size - read)
            if (count < 0) throw IOException("body cut short")
            read += count
        }
        return body
    }

    private fun untilClose(input: InputStream, maxBytes: Int): ByteArray {
        val output = ByteArrayOutputStream()
        val buffer = ByteArray(64 * 1024)
        while (true) {
            val count = input.read(buffer)
            if (count < 0) return output.toByteArray()
            output.write(buffer, 0, count)
            if (output.size() > maxBytes) throw TooLarge()
        }
    }

    private fun chunked(input: InputStream, maxBytes: Int): ByteArray {
        val output = ByteArrayOutputStream()
        while (true) {
            val size = line(input)?.substringBefore(';')?.trim()?.toLongOrNull(16) ?: throw IOException("bad chunk")
            if (size == 0L) {
                while (line(input)?.isNotEmpty() == true) Unit // trailers
                return output.toByteArray()
            }
            if (output.size() + size > maxBytes) throw TooLarge()
            output.write(exactly(input, size, maxBytes))
            line(input) // the CRLF after each chunk
        }
    }
}
