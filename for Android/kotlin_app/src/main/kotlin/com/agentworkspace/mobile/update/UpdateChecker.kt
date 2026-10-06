package com.agentworkspace.mobile.update

import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.core.content.FileProvider
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/** One published GitHub release that carries an installable APK. */
data class ReleaseInfo(
    val version: String,
    val notes: String,
    val pageUrl: String,
    val apkUrl: String,
    val apkName: String,
    val apkSize: Long,
    val sha256: String?,
)

/**
 * Over-the-air updates from the project's GitHub releases. The APK is only offered to Android's
 * installer after its SHA-256 matches the release, it is this app, its version is newer and it is
 * signed with the same key as the installed app (Android enforces the last point again on install).
 */
object UpdateChecker {
    const val REPOSITORY = "WhitePepperLambSoup/agent-workspace-android"
    const val RELEASES_PAGE = "https://github.com/$REPOSITORY/releases"
    /** The export provider only serves files inside UUID-named folders under generated-files. */
    private const val UPDATE_FOLDER = "0d1a6000-0000-4000-8000-000000000002"
    private const val PREFERENCES = "app-updates"
    private const val AUTO_CHECK_INTERVAL_MS = 24L * 60 * 60 * 1000
    private const val MAX_APK_BYTES = 512L * 1024 * 1024
    private val SHA256_IN_NOTES = Regex("(?i)sha-?256[^0-9a-f]{0,80}([0-9a-f]{64})")

    private fun preferences(context: Context) = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)

    fun autoCheckEnabled(context: Context) = preferences(context).getBoolean("auto_check", true)

    fun setAutoCheck(context: Context, enabled: Boolean) {
        preferences(context).edit().putBoolean("auto_check", enabled).apply()
    }

    fun dueForAutoCheck(context: Context): Boolean =
        autoCheckEnabled(context) && System.currentTimeMillis() - preferences(context).getLong("last_check_ms", 0) >= AUTO_CHECK_INTERVAL_MS

    fun markChecked(context: Context, latest: String?) {
        preferences(context).edit().putLong("last_check_ms", System.currentTimeMillis())
            .apply { if (latest != null) putString("latest_version", latest) }.apply()
    }

    fun skippedVersion(context: Context): String? = preferences(context).getString("skipped_version", null)

    fun skip(context: Context, version: String) { preferences(context).edit().putString("skipped_version", version).apply() }

    fun installedVersion(context: Context): String =
        runCatching { context.packageManager.getPackageInfo(context.packageName, 0).versionName }.getOrNull() ?: "0"

    fun statusJson(context: Context): String = JSONObject()
        .put("version", installedVersion(context))
        .put("autoCheck", autoCheckEnabled(context))
        .put("lastCheckedMs", preferences(context).getLong("last_check_ms", 0))
        .put("latestVersion", preferences(context).getString("latest_version", "") ?: "")
        .put("releasesPage", RELEASES_PAGE)
        .toString()

    /** The newest non-draft, non-prerelease release. Network call: never on the main thread. */
    fun fetchLatest(): ReleaseInfo {
        val connection = URL("https://api.github.com/repos/$REPOSITORY/releases/latest").openConnection() as HttpURLConnection
        val body = try {
            connection.connectTimeout = 15000
            connection.readTimeout = 20000
            connection.setRequestProperty("Accept", "application/vnd.github+json")
            connection.setRequestProperty("User-Agent", "AgentWorkspace-Android")
            when (val code = connection.responseCode) {
                200 -> connection.inputStream.bufferedReader().use { it.readText() }
                404 -> throw IOException("no published release")
                403, 429 -> throw IOException("GitHub rate limit reached; try again later")
                else -> throw IOException("GitHub answered HTTP $code")
            }
        } finally {
            connection.disconnect()
        }
        val release = JSONObject(body)
        val notes = release.optString("body")
        val assets = release.optJSONArray("assets")
        var apk: JSONObject? = null
        for (index in 0 until (assets?.length() ?: 0)) {
            val asset = assets!!.getJSONObject(index)
            if (asset.optString("name").endsWith(".apk", ignoreCase = true)) { apk = asset; break }
        }
        apk ?: throw IOException("the latest release has no APK")
        val digest = apk.optString("digest").takeIf { it.startsWith("sha256:") }?.removePrefix("sha256:")
            ?: SHA256_IN_NOTES.find(notes)?.groupValues?.get(1)
        return ReleaseInfo(
            version = release.optString("tag_name").ifBlank { release.optString("name") }.removePrefix("v").removePrefix("V"),
            notes = notes,
            pageUrl = release.optString("html_url").ifBlank { RELEASES_PAGE },
            apkUrl = apk.getString("browser_download_url"),
            apkName = apk.getString("name"),
            apkSize = apk.optLong("size"),
            sha256 = digest?.lowercase(),
        )
    }

    /** Numeric comparison of dotted versions; "1.0.10" is newer than "1.0.9". Suffixes are ignored. */
    fun isNewer(candidate: String, installed: String): Boolean {
        fun parts(value: String) = value.trim().removePrefix("v").substringBefore('-').substringBefore('+')
            .split('.').map { it.toIntOrNull() ?: 0 }
        val a = parts(candidate)
        val b = parts(installed)
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }
            val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }

    /** Download into the private export cache, checking size and SHA-256 as the bytes arrive. */
    fun download(context: Context, release: ReleaseInfo, progress: (Long, Long) -> Unit, cancelled: () -> Boolean): File {
        val expected = release.sha256 ?: throw IOException("the release does not publish a SHA-256 for its APK")
        val folder = File(context.cacheDir, "generated-files/$UPDATE_FOLDER").apply {
            deleteRecursively()
            mkdirs()
        }
        val safeName = release.apkName.replace(Regex("[^A-Za-z0-9._-]"), "_")
        val partial = File(folder, "$safeName.part")
        val connection = URL(release.apkUrl).openConnection() as HttpURLConnection
        val digest = MessageDigest.getInstance("SHA-256")
        try {
            connection.connectTimeout = 15000
            connection.readTimeout = 30000
            connection.setRequestProperty("User-Agent", "AgentWorkspace-Android")
            if (connection.responseCode != 200) throw IOException("download answered HTTP ${connection.responseCode}")
            val total = connection.contentLengthLong.takeIf { it > 0 } ?: release.apkSize
            if (total > MAX_APK_BYTES) throw IOException("the APK is unexpectedly large")
            var received = 0L
            connection.inputStream.use { input ->
                partial.outputStream().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        if (cancelled()) throw IOException("cancelled")
                        val count = input.read(buffer)
                        if (count < 0) break
                        received += count
                        if (received > MAX_APK_BYTES) throw IOException("the APK is unexpectedly large")
                        output.write(buffer, 0, count)
                        digest.update(buffer, 0, count)
                        progress(received, total)
                    }
                }
            }
        } catch (failure: Exception) {
            folder.deleteRecursively()
            throw failure
        } finally {
            connection.disconnect()
        }
        val actual = digest.digest().joinToString("") { "%02x".format(it) }
        if (actual != expected) {
            folder.deleteRecursively()
            throw IOException("the downloaded APK does not match the release SHA-256")
        }
        return File(folder, safeName).also { if (!partial.renameTo(it)) throw IOException("could not finish the download") }
    }

    /** Why this APK must not be installed over the running app, or null when it is a valid update. */
    fun verify(context: Context, apk: File): String? {
        val manager = context.packageManager
        val flags = if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES else @Suppress("DEPRECATION") PackageManager.GET_SIGNATURES
        val archive = manager.getPackageArchiveInfo(apk.absolutePath, flags) ?: return "the file is not a valid APK"
        if (archive.packageName != context.packageName) return "the APK belongs to another app"
        val installed = manager.getPackageInfo(context.packageName, flags)
        if (versionCode(archive) <= versionCode(installed)) return "the APK is not newer than the installed app"
        val expected = signers(installed)
        val actual = signers(archive)
        // A rotated key keeps the old certificate in its history, so the installed signer must be among the new ones.
        if (expected.isEmpty() || !actual.containsAll(expected)) return "the APK is signed with a different key"
        return null
    }

    fun installIntent(context: Context, apk: File): Intent {
        val uri: Uri = FileProvider.getUriForFile(context, "${context.packageName}.workspace-files", apk)
        return Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
    }

    private fun versionCode(info: PackageInfo): Long =
        if (Build.VERSION.SDK_INT >= 28) info.longVersionCode else @Suppress("DEPRECATION") info.versionCode.toLong()

    private fun signers(info: PackageInfo): Set<String> {
        val signatures = if (Build.VERSION.SDK_INT >= 28) {
            val signing = info.signingInfo ?: return emptySet()
            if (signing.hasMultipleSigners()) signing.apkContentsSigners else signing.signingCertificateHistory
        } else {
            @Suppress("DEPRECATION") info.signatures
        } ?: return emptySet()
        return signatures.map { signature ->
            MessageDigest.getInstance("SHA-256").digest(signature.toByteArray()).joinToString("") { "%02x".format(it) }
        }.toSet()
    }
}
