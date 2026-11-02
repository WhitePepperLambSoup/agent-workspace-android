package com.agentworkspace.mobile.embedded

import android.content.Context
import java.io.File

/**
 * Where the local engine listens. It takes 8080, or the next free port up to 8089 when another app
 * holds 8080 (a web server in Termux, a proxy), and writes the one it took to serve.port before it
 * publishes serve.token.
 */
object EngineAddress {
    const val DEFAULT_PORT = 8080
    val PORTS = DEFAULT_PORT until DEFAULT_PORT + 10

    fun port(filesDir: File): Int = runCatching { File(filesDir, "serve.port").readText().trim().toInt() }
        .getOrNull()?.takeIf { it in PORTS } ?: DEFAULT_PORT

    fun port(context: Context): Int = port(context.filesDir)

    fun baseUrl(filesDir: File): String = "http://127.0.0.1:${port(filesDir)}"

    fun baseUrl(context: Context): String = baseUrl(context.filesDir)
}
