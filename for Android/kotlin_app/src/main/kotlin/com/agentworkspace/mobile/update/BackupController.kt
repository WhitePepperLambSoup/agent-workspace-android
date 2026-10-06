package com.agentworkspace.mobile.update

import android.content.Context
import android.net.Uri
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import com.agentworkspace.mobile.embedded.EngineHttp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

/**
 * Backup and restore from the Settings page. The engine writes and checks the archive (it owns the
 * databases); this side adds the app's own settings, lets the user pick where the file goes or
 * comes from, and restarts the engine after a restore. API keys are never part of a backup.
 * Progress reaches the page as `agent-backup` events.
 */
class BackupController(
    private val activity: ComponentActivity,
    private val scope: CoroutineScope,
    private val dispatch: (JSONObject) -> Unit,
    private val restartEngine: () -> Unit,
) {
    private var pendingArchive: File? = null

    private val saveLauncher = activity.registerForActivityResult(ActivityResultContracts.CreateDocument("application/zip")) { target ->
        val archive = pendingArchive
        pendingArchive = null
        if (target == null || archive == null) { dispatch(state("cancelled")); return@registerForActivityResult }
        scope.launch {
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    val output = activity.contentResolver.openOutputStream(target, "wt") ?: error("The selected location cannot be written")
                    output.use { stream -> archive.inputStream().use { it.copyTo(stream) } }
                    archive.length()
                }
            }
            result.onSuccess { dispatch(state("saved").put("size", it)) }
                .onFailure { dispatch(state("failed").put("error", it.message ?: "Could not save the backup")) }
        }
    }

    private val openLauncher = activity.registerForActivityResult(ActivityResultContracts.OpenDocument()) { source ->
        if (source == null) { dispatch(state("cancelled")); return@registerForActivityResult }
        scope.launch { restoreFrom(source) }
    }

    private fun state(value: String) = JSONObject().put("state", value)

    // ---- settings that live in the app rather than the engine ----

    private val preferenceFiles = listOf("agent-workspace-provider", "agent-workspace-provider-profiles", "app-updates")

    private fun appSettings(context: Context): JSONObject {
        val preferences = JSONObject()
        for (name in preferenceFiles) {
            val values = JSONObject()
            context.getSharedPreferences(name, Context.MODE_PRIVATE).all.forEach { (key, value) ->
                if (value is String || value is Boolean || value is Int || value is Long || value is Float) values.put(key, value)
            }
            preferences.put(name, values)
        }
        val version = runCatching { context.packageManager.getPackageInfo(context.packageName, 0).versionName }.getOrNull()
        return JSONObject().put("version", 1).put("app_version", version).put("preferences", preferences)
    }

    private fun restoreAppSettings(context: Context, settings: JSONObject?) {
        val preferences = settings?.optJSONObject("preferences") ?: return
        for (name in preferenceFiles) {
            val values = preferences.optJSONObject(name) ?: continue
            val editor = context.getSharedPreferences(name, Context.MODE_PRIVATE).edit().clear()
            values.keys().forEach { key ->
                when (val value = values.get(key)) {
                    is String -> editor.putString(key, value)
                    is Boolean -> editor.putBoolean(key, value)
                    is Number -> if (key.endsWith("_ms")) editor.putLong(key, value.toLong()) else editor.putInt(key, value.toInt())
                }
            }
            editor.commit()
        }
    }

    // ---- create ----

    fun create(webSettings: String) {
        val web = runCatching { JSONObject(webSettings) }.getOrDefault(JSONObject())
        dispatch(state("creating"))
        scope.launch {
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    val folder = File(activity.cacheDir, "generated-files/${UUID.randomUUID()}").apply { mkdirs() }
                    val stamp = SimpleDateFormat("yyyyMMdd-HHmm", Locale.US).format(Date())
                    val output = File(folder, "agent-workspace-backup-$stamp.zip")
                    val started = EngineHttp.request(activity, "POST", "/mobile/backup/create", JSONObject()
                        .put("output", output.absolutePath).put("app_settings", appSettings(activity)).put("web_settings", web))
                    check(started.ok) { started.error }
                    val job = started.body.getString("job_id")
                    val deadline = System.currentTimeMillis() + 30 * 60_000L
                    var finished: JSONObject? = null
                    while (finished == null) {
                        delay(500)
                        val status = EngineHttp.request(activity, "GET", "/mobile/backup/status?job_id=${Uri.encode(job)}")
                        check(status.ok) { status.error }
                        when (status.body.optString("state")) {
                            "done" -> finished = status.body
                            "failed" -> error(status.body.optString("error").ifBlank { "The backup failed" })
                        }
                        check(System.currentTimeMillis() < deadline) { "The backup took too long" }
                    }
                    output to finished
                }
            }
            result.onSuccess { (archive, summary) ->
                dispatch(state("saving").put("summary", summary))
                pendingArchive = archive
                runCatching { saveLauncher.launch(archive.name) }.onFailure {
                    pendingArchive = null
                    dispatch(state("failed").put("error", "No file manager is available to save the backup"))
                }
            }.onFailure { dispatch(state("failed").put("error", it.message ?: "The backup failed")) }
        }
    }

    // ---- restore ----

    fun restore() {
        runCatching { openLauncher.launch(arrayOf("application/zip", "application/x-zip-compressed", "application/octet-stream")) }
            .onFailure { dispatch(state("failed").put("error", "No file manager is available to pick a backup")) }
    }

    private suspend fun restoreFrom(source: Uri) {
        dispatch(state("restoring"))
        val result = withContext(Dispatchers.IO) {
            runCatching {
                val folder = File(activity.cacheDir, "backup-restore").apply { deleteRecursively(); mkdirs() }
                val copy = File(folder, "incoming.zip")
                val input = activity.contentResolver.openInputStream(source) ?: error("The selected backup cannot be read")
                input.use { stream -> copy.outputStream().use { stream.copyTo(it) } }
                val reply = EngineHttp.request(activity, "POST", "/mobile/backup/restore",
                    JSONObject().put("path", copy.absolutePath), readTimeoutMs = 10 * 60_000)
                copy.delete()
                check(reply.ok) { reply.error }
                val settings = reply.body.optJSONObject("settings") ?: JSONObject()
                restoreAppSettings(activity, settings.optJSONObject("app"))
                settings.optJSONObject("web") ?: JSONObject()
            }
        }
        result.onSuccess { web ->
            dispatch(state("restored").put("web", web))
            // Give the page a moment to write its settings, then swap the data in by restarting.
            delay(800)
            restartEngine()
        }.onFailure { dispatch(state("failed").put("error", it.message ?: "The backup could not be restored")) }
    }
}
