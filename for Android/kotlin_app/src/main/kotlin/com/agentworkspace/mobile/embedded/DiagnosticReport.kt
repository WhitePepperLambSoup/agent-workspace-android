package com.agentworkspace.mobile.embedded

import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.os.Build
import android.webkit.WebView
import androidx.core.content.FileProvider
import java.io.File
import java.io.RandomAccessFile
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * One text file a user can send when the engine misbehaves: app and device versions, engine and
 * background status, the engine's own logs (restarts, stalls, request errors) and this app's recent
 * system log. The engine token and every stored API key are masked before the file is written.
 */
object DiagnosticReport {
    private const val LOG_TAIL_BYTES = 192 * 1024
    private const val SYSTEM_LOG_BYTES = 384 * 1024
    private val ENGINE_LOGS = listOf(
        "engine-restarts.log", "engine-stalls.log", "engine-stalls.log.1",
        "gateway-errors.log", "gateway-errors.log.1",
    )

    fun write(context: Context): File {
        val report = buildString {
            appendLine("Agent Workspace diagnostics")
            appendLine("Generated: ${timestamp("yyyy-MM-dd HH:mm:ss Z")}")
            appendLine("App: ${appVersion(context)}")
            appendLine("Device: ${Build.MANUFACTURER} ${Build.MODEL}, Android ${Build.VERSION.RELEASE} (SDK ${Build.VERSION.SDK_INT})")
            appendLine("WebView: ${runCatching { WebView.getCurrentWebViewPackage()?.versionName }.getOrNull() ?: "unknown"}")
            section("Engine and background status") { EngineRecovery.status(context) }
            val logs = File(context.filesDir, "agent-data/logs")
            for (name in ENGINE_LOGS) {
                val file = File(logs, name)
                if (file.isFile) section(name) { tail(file, LOG_TAIL_BYTES) }
            }
            if (ENGINE_LOGS.none { File(logs, it).isFile }) section("Engine logs") { "No engine restarts, stalls or request errors recorded." }
            section("App system log (this app only, most recent)") { systemLog() }
        }
        val dir = File(context.cacheDir, "generated-files/diagnostics").apply {
            mkdirs()
            listFiles()?.forEach { it.delete() } // keep only the newest report
        }
        return File(dir, "agent-diagnostics-${timestamp("yyyyMMdd-HHmmss")}.txt").apply {
            writeText(redact(report, secrets(context)))
        }
    }

    fun share(context: Context, report: File) {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.workspace-files", report)
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_SUBJECT, report.name)
            clipData = ClipData.newRawUri(report.name, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(send, report.name).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
        })
    }

    /** Values that must never leave the phone: the engine token and every stored credential. */
    private fun secrets(context: Context): List<String> {
        val values = mutableListOf<String>()
        runCatching { File(context.filesDir, "serve.token").readText().trim() }.getOrNull()?.let(values::add)
        runCatching {
            EmbeddedSecrets.initialize(context)
            EmbeddedSecrets.listCredentials().mapNotNullTo(values) { EmbeddedSecrets.getCredential(it) }
        }
        return values.filter { it.length >= 6 }.distinct().sortedByDescending { it.length }
    }

    internal fun redact(text: String, secrets: List<String>): String {
        var result = text
        for (secret in secrets) result = result.replace(secret, "[redacted]")
        return result
            .replace(Regex("(?i)(Bearer\\s+)[A-Za-z0-9._~+/=-]{8,}"), "$1[redacted]")
            .replace(Regex("(?i)([?&](?:token|api_key|key)=)[^&\\s\"']+"), "$1[redacted]")
            .replace(Regex("\\bsk-[A-Za-z0-9_-]{12,}"), "sk-[redacted]")
    }

    private fun StringBuilder.section(title: String, body: () -> String) {
        appendLine()
        appendLine("===== $title =====")
        appendLine(runCatching(body).getOrElse { "(unavailable: ${it.javaClass.simpleName})" }.trimEnd())
    }

    private fun tail(file: File, limit: Int): String = RandomAccessFile(file, "r").use { input ->
        val start = (input.length() - limit).coerceAtLeast(0)
        input.seek(start)
        val bytes = ByteArray((input.length() - start).toInt())
        input.readFully(bytes)
        (if (start > 0) "… (earlier lines omitted)\n" else "") + String(bytes, Charsets.UTF_8)
    }

    /** Android only lets an app read its own log lines, which covers both app processes and Python's stderr. */
    private fun systemLog(): String {
        val process = ProcessBuilder("logcat", "-d", "-v", "time", "-t", "3000").redirectErrorStream(true).start()
        val text = process.inputStream.bufferedReader().use { it.readText() }
        process.waitFor()
        return if (text.length > SYSTEM_LOG_BYTES) "… (earlier lines omitted)\n" + text.takeLast(SYSTEM_LOG_BYTES) else text
    }

    private fun appVersion(context: Context): String = runCatching {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        "${info.versionName} (${if (Build.VERSION.SDK_INT >= 28) info.longVersionCode else @Suppress("DEPRECATION") info.versionCode.toLong()})"
    }.getOrDefault("unknown")

    private fun timestamp(pattern: String) = SimpleDateFormat(pattern, Locale.US).format(Date())
}
