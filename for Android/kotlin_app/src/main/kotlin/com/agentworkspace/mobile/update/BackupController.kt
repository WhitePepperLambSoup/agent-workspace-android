package com.agentworkspace.mobile.update

import android.content.Context
import android.net.Uri
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.automation.BlockedApps
import com.agentworkspace.mobile.embedded.EngineHttp
import com.agentworkspace.mobile.embedded.MobileProviderSettings
import com.agentworkspace.mobile.embedded.ProviderEndpoints
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.lang.ref.WeakReference
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

/** What to do about a staged restore when a screen opens, on plain values so it can be tested without a phone. */
internal object RestoreResume {
    enum class Action { NOTHING, RESTART, FINISH, DISCARD }

    /** Asked for this long ago at most, it is still what the user wants; later they have gone on without it. */
    private const val STILL_WANTED_MS = 15 * 60_000L

    /** [running]: this process is still seeing that restore through. [confirmed]: the app took it up, only the restart is left. */
    fun decide(ready: Boolean, confirmed: Boolean, running: Boolean, ageMs: Long): Action = when {
        !ready || running -> Action.NOTHING
        confirmed -> Action.RESTART
        ageMs <= STILL_WANTED_MS -> Action.FINISH
        else -> Action.DISCARD
    }
}

/**
 * The app's own preferences in a backup (settings/app.json), on plain values so it can be tested
 * without a phone. The file comes from wherever the user picked it, and was written straight into the
 * preferences: a Long or Float came back as an Int (JSON keeps no type), and provider settings no save
 * would accept (a plain-HTTP public address, an unknown protocol) kept the engine from starting.
 */
internal object BackupPreferences {
    private const val PROVIDER = "agent-workspace-provider"
    private const val PROFILES = "agent-workspace-provider-profiles"

    /**
     * [values] with the risky settings a restore does not put back set to their safe value, and which
     * those were: "full_access" (back to the workspace mode) and "allow_lan_http" (plain HTTP to the
     * local network, off). A backup file can come from anywhere; the user turns them on again in settings.
     */
    fun lowered(name: String, values: JSONObject): Pair<JSONObject, List<String>> {
        val safe = JSONObject(values.toString())
        val lowered = mutableListOf<String>()
        when (name) {
            PROVIDER -> {
                if (safe.opt("autonomy") == "full_access") { safe.put("autonomy", "workspace"); lowered += "full_access" }
                if ((safe.opt("allow_lan_http") as? String)?.toBooleanStrictOrNull() == true) {
                    safe.put("allow_lan_http", "false")
                    lowered += "allow_lan_http"
                }
            }
            PROFILES -> {
                val profiles = (safe.opt("profiles") as? String)?.let { runCatching { org.json.JSONArray(it) }.getOrNull() }
                if (profiles != null) {
                    var changed = false
                    for (index in 0 until profiles.length()) {
                        val profile = profiles.optJSONObject(index) ?: continue
                        if (profile.optBoolean("allow_lan_http", false)) { profile.put("allow_lan_http", false); changed = true }
                    }
                    if (changed) { safe.put("profiles", profiles.toString()); lowered += "allow_lan_http" }
                }
            }
        }
        return safe to lowered
    }

    private val PACKAGE = Regex("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z0-9_]+)+")

    /**
     * The apps the agent may not read or operate after a restore: those blocked on this phone now,
     * and those the backup blocked. A restore only adds to the list, so it never leaves the phone
     * less protected than it is (a backup from an older phone could otherwise unblock a bank app).
     */
    fun blockedApps(current: Set<String>, backup: org.json.JSONArray?): Set<String> {
        val restored = (0 until minOf(backup?.length() ?: 0, 500)).mapNotNull { backup?.optString(it) }
            .filter { it.length <= 255 && PACKAGE.matches(it) }
        return current + restored
    }

    /** Each value's type, kept beside the values: "string", "boolean", "int", "long" or "float". */
    fun types(values: Map<String, *>): JSONObject = JSONObject().apply {
        values.forEach { (key, value) ->
            when (value) {
                is String -> put(key, "string")
                is Boolean -> put(key, "boolean")
                is Int -> put(key, "int")
                is Long -> put(key, "long")
                is Float -> put(key, "float")
            }
        }
    }

    /** The values to put back, each as its own type; a backup from before types were kept guesses as it always did. */
    fun entries(values: JSONObject, types: JSONObject?): List<Pair<String, Any>> = values.keys().asSequence().mapNotNull { key ->
        val value = values.get(key)
        val typed: Any? = when (types?.optString(key)) {
            "string" -> value as? String
            "boolean" -> value as? Boolean
            "int" -> (value as? Number)?.toInt()
            "long" -> (value as? Number)?.toLong()
            "float" -> (value as? Number)?.toFloat()
            else -> when (value) {
                is String, is Boolean -> value
                is Number -> if (key.endsWith("_ms")) value.toLong() else value.toInt()
                else -> null
            }
        }
        typed?.let { key to it }
    }.toList()

    /** Whether [name]'s restored values pass the checks a save makes (MobileProviderSettings.save). */
    fun acceptable(name: String, values: JSONObject): Boolean {
        if (name != PROVIDER) return true
        fun text(key: String, fallback: String) = if (values.has(key)) values.opt(key) as? String else fallback
        val protocol = text("protocol", "openai-compatible") ?: return false
        val baseUrl = text("base_url", "https://api.openai.com/v1") ?: return false
        val model = text("model", "gpt-6-sol") ?: return false
        val autonomy = text("autonomy", "workspace") ?: return false
        val lanHttp = text("allow_lan_http", "false")?.toBooleanStrictOrNull() ?: return false
        val uri = runCatching { java.net.URI(baseUrl) }.getOrNull() ?: return false
        return protocol in MobileProviderSettings.protocols && autonomy in MobileProviderSettings.autonomies &&
            model.isNotBlank() && model.length <= 256 &&
            uri.scheme in listOf("http", "https") && !uri.host.isNullOrBlank() &&
            uri.userInfo == null && uri.query == null && uri.fragment == null &&
            ProviderEndpoints.allowed(uri.scheme, uri.host, lanHttp)
    }
}

/**
 * A restore outlives the screen that started it: the engine may unpack for minutes, and Android may
 * rebuild or close the screen meanwhile. It reports to the screen showing by then.
 */
private object RestoreRun {
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    @Volatile var running = false
    @Volatile var screen: WeakReference<BackupController>? = null
}

/**
 * Backup and restore from the Settings page. The engine writes and checks the archive (it owns the
 * databases); this side adds the app's own settings, lets the user pick where the file goes or
 * comes from, and restarts the engine after a restore. API keys are never part of a backup.
 * With a passphrase the zip is locked (BackupCrypto) before it is saved, and restoring such a file
 * asks for it. Progress reaches the page as `agent-backup` events.
 *
 * The engine only staged a restore until this side confirms it (mobile_backup.CONFIRMED_MARKER), so an
 * engine restart never swaps in a backup the app did not hear about. When the process died in between,
 * [finishInterrupted] takes it up the next time a screen opens.
 */
class BackupController(
    private val activity: ComponentActivity,
    private val scope: CoroutineScope,
    private val dispatch: (JSONObject) -> Unit,
    private val restartEngine: () -> Unit,
) {
    init { RestoreRun.screen = WeakReference(this) }

    private var pendingArchive: File? = null
    // A locked backup picked for restoring, waiting for its passphrase.
    private var pendingLocked: File? = null

    private val saveLauncher = activity.registerForActivityResult(ActivityResultContracts.CreateDocument("application/zip")) { target ->
        saveTo(target)
    }
    private val saveLockedLauncher = activity.registerForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { target ->
        saveTo(target)
    }

    private fun saveTo(target: Uri?) {
        val archive = pendingArchive
        pendingArchive = null
        if (target == null || archive == null) { dispatch(state("cancelled")); return }
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
            archive.delete()
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
        val types = JSONObject()
        for (name in preferenceFiles) {
            val values = JSONObject()
            val all = context.getSharedPreferences(name, Context.MODE_PRIVATE).all
            all.forEach { (key, value) ->
                if (value is String || value is Boolean || value is Int || value is Long || value is Float) values.put(key, value)
            }
            preferences.put(name, values)
            types.put(name, BackupPreferences.types(all))
        }
        val version = runCatching { context.packageManager.getPackageInfo(context.packageName, 0).versionName }.getOrNull()
        return JSONObject().put("version", 1).put("app_version", version).put("preferences", preferences)
            .put("types", types)
            // The apps the agent may not read or operate: a safety setting, which a new phone
            // restored from this backup must keep (it lives in a file of its own, not the preferences).
            .put("blocked_apps", org.json.JSONArray(BlockedApps.packages(context).sorted()))
    }

    /**
     * [skipped]: the preference files left as they were because the backup's values would not pass a save.
     * [lowered]: the risky settings put back at their safe value instead (BackupPreferences.lowered).
     */
    private class RestoredSettings(val skipped: List<String>, val lowered: List<String>)

    private fun restoreAppSettings(context: Context, settings: JSONObject?): RestoredSettings {
        val current = BlockedApps.packages(context)
        val blocked = BackupPreferences.blockedApps(current, settings?.optJSONArray("blocked_apps"))
        if (blocked != current) BlockedApps.save(context, blocked)
        val preferences = settings?.optJSONObject("preferences") ?: return RestoredSettings(emptyList(), emptyList())
        val types = settings.optJSONObject("types")
        val skipped = mutableListOf<String>()
        val lowered = mutableListOf<String>()
        for (name in preferenceFiles) {
            val (values, risky) = BackupPreferences.lowered(name, preferences.optJSONObject(name) ?: continue)
            lowered += risky
            // Checked as it will be written: a LAN address left without its HTTP switch is not taken.
            if (!BackupPreferences.acceptable(name, values)) { skipped += name; continue }
            val editor = context.getSharedPreferences(name, Context.MODE_PRIVATE).edit().clear()
            for ((key, value) in BackupPreferences.entries(values, types?.optJSONObject(name))) {
                when (value) {
                    is String -> editor.putString(key, value)
                    is Boolean -> editor.putBoolean(key, value)
                    is Int -> editor.putInt(key, value)
                    is Long -> editor.putLong(key, value)
                    is Float -> editor.putFloat(key, value)
                }
            }
            editor.commit()
        }
        return RestoredSettings(skipped, lowered.distinct())
    }

    /** The "restored" event: the page's own settings, and what of the app's was not put back as it was. */
    private fun restored(web: JSONObject, settings: RestoredSettings) = state("restored").put("web", web)
        .put("skipped_settings", org.json.JSONArray(settings.skipped))
        .put("lowered_settings", org.json.JSONArray(settings.lowered))

    // ---- create ----

    fun create(webSettings: String, passphrase: String? = null) {
        val web = runCatching { JSONObject(webSettings) }.getOrDefault(JSONObject())
        val lock = passphrase?.takeIf { it.isNotEmpty() }?.toCharArray()
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
                    val summary = checkNotNull(finished)
                    if (lock == null) return@runCatching output to summary
                    val locked = File(folder, output.name.removeSuffix(".zip") + ".awbackup")
                    try { BackupCrypto.encrypt(output, locked, lock) } finally { lock.fill(' '); output.delete() }
                    locked to summary.put("size", locked.length()).put("locked", true)
                }
            }
            result.onSuccess { (archive, summary) ->
                dispatch(state("saving").put("summary", summary))
                pendingArchive = archive
                val launcher = if (archive.name.endsWith(".awbackup")) saveLockedLauncher else saveLauncher
                runCatching { launcher.launch(archive.name) }.onFailure {
                    pendingArchive = null
                    dispatch(state("failed").put("error", "No file manager is available to save the backup"))
                }
            }.onFailure { dispatch(state("failed").put("error", it.message ?: "The backup failed")) }
        }
    }

    // ---- restore ----

    fun restore() {
        // The last one is still being unpacked: it went on while this screen was rebuilt.
        if (RestoreRun.running) { dispatch(state("restoring")); return }
        runCatching { openLauncher.launch(arrayOf("application/zip", "application/x-zip-compressed", "application/octet-stream")) }
            .onFailure { dispatch(state("failed").put("error", "No file manager is available to pick a backup")) }
    }

    private suspend fun restoreFrom(source: Uri) {
        dispatch(state("restoring"))
        pendingLocked = null
        val copied = withContext(Dispatchers.IO) {
            runCatching {
                val folder = File(activity.cacheDir, "backup-restore").apply { deleteRecursively(); mkdirs() }
                val copy = File(folder, "incoming.bin")
                val input = activity.contentResolver.openInputStream(source) ?: error("The selected backup cannot be read")
                input.use { stream -> copy.outputStream().use { stream.copyTo(it) } }
                copy
            }
        }
        val copy = copied.getOrElse { dispatch(state("failed").put("error", it.message ?: "The backup could not be read")); return }
        if (withContext(Dispatchers.IO) { BackupCrypto.isEncrypted(copy) }) {
            // Locked: the page asks for the passphrase (restoreWithPassphrase).
            pendingLocked = copy
            dispatch(state("passphrase_required"))
            return
        }
        finishRestore(copy)
    }

    /** The passphrase of the locked backup picked last; a wrong one can be tried again. */
    fun restoreWithPassphrase(passphrase: String) {
        val locked = pendingLocked ?: run { dispatch(state("failed").put("error", "Pick the backup again")); return }
        dispatch(state("restoring"))
        scope.launch {
            val opened = withContext(Dispatchers.IO) {
                runCatching {
                    val plain = File(locked.parentFile, "incoming.zip")
                    val key = passphrase.toCharArray()
                    try { BackupCrypto.decrypt(locked, plain, key) } finally { key.fill(' ') }
                    plain
                }
            }
            opened.onSuccess { plain ->
                pendingLocked = null
                locked.delete()
                finishRestore(plain)
            }.onFailure {
                File(locked.parentFile, "incoming.zip").delete()
                dispatch(state(if (it is BackupCrypto.WrongPassphrase) "passphrase_wrong" else "failed")
                    .put("error", it.message ?: "The backup could not be opened"))
            }
        }
    }

    private fun finishRestore(copy: File) {
        val context = activity.applicationContext
        fun showing() = RestoreRun.screen?.get()?.takeUnless { it.activity.isDestroyed }
        RestoreRun.running = true
        RestoreRun.scope.launch {
            try {
                val result = withContext(Dispatchers.IO) {
                    runCatching {
                        val reply = EngineHttp.request(context, "POST", "/mobile/backup/restore",
                            JSONObject().put("path", copy.absolutePath), readTimeoutMs = 10 * 60_000)
                        copy.delete()
                        check(reply.ok) { reply.error }
                        val settings = reply.body.optJSONObject("settings") ?: JSONObject()
                        val restoredSettings = restoreAppSettings(context, settings.optJSONObject("app"))
                        confirmStaged(context)
                        (settings.optJSONObject("web") ?: JSONObject()) to restoredSettings
                    }
                }
                result.onSuccess { (web, restoredSettings) ->
                    showing()?.dispatch?.invoke(restored(web, restoredSettings))
                    // Give the page a moment to write its settings, then swap the data in by restarting.
                    // With no screen left, the next one to open does it (finishInterrupted).
                    delay(800)
                    showing()?.restartEngine?.invoke()
                }.onFailure { showing()?.dispatch?.invoke(state("failed").put("error", it.message ?: "The backup could not be restored")) }
            } finally {
                RestoreRun.running = false
            }
        }
    }

    private fun staging(context: Context) = File(context.filesDir, "restore-staging")

    /** From here on the next engine start swaps the backup in; mobile_backup.CONFIRMED_MARKER. */
    private fun confirmStaged(context: Context) {
        File(staging(context), "CONFIRMED").writeText(System.currentTimeMillis().toString())
    }

    /**
     * A restore whose screen was gone when it became ready: finished now if it is recent, dropped with a
     * word to the user if not. Called before the engine is started and on coming back to the app; true
     * when the engine has to restart to swap the backup in.
     */
    fun finishInterrupted(): Boolean {
        val staged = staging(activity)
        val ready = File(staged, "READY")
        return when (RestoreResume.decide(ready.isFile, File(staged, "CONFIRMED").isFile, RestoreRun.running,
            System.currentTimeMillis() - ready.lastModified())) {
            RestoreResume.Action.NOTHING -> false
            RestoreResume.Action.RESTART -> true
            RestoreResume.Action.DISCARD -> {
                staged.deleteRecursively()
                Toast.makeText(activity, UiText.of(activity, "上次的恢复没有完成，数据没有变化。需要的话请重新恢复。",
                    "The last restore did not finish and nothing changed. Restore again if you still want it."), Toast.LENGTH_LONG).show()
                false
            }
            RestoreResume.Action.FINISH -> {
                fun settings(name: String) = runCatching { JSONObject(File(staged, "settings/$name").readText()) }.getOrNull()
                val restoredSettings = restoreAppSettings(activity, settings("app.json"))
                confirmStaged(activity)
                dispatch(restored(settings("web.json") ?: JSONObject(), restoredSettings))
                true
            }
        }
    }
}
