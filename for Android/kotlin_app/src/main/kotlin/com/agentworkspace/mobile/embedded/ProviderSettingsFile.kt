package com.agentworkspace.mobile.embedded

import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.RandomAccessFile
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/**
 * The provider settings as either process last saved them (KA-001). SharedPreferences are read once
 * per process and never again, so :engine went on with the values it first saw and could hand them
 * to an engine it restarted. Every save writes the preferences and then this file; reads take this
 * file, read each time under its lock, unless the preferences file is newer (a backup restored it,
 * or an older build saved): then the preferences, as before.
 */
internal class ProviderSettingsFile(
    private val file: File,
    private val preferencesFile: File,
    private val preferences: Preferences,
) {
    interface Preferences {
        fun all(): Map<String, String>
        fun write(values: Map<String, String>): Boolean
    }

    fun read(): MutableMap<String, String> {
        if (file.exists() && file.lastModified() >= preferencesFile.lastModified()) {
            runCatching { locked { JSONObject(file.readText(Charsets.UTF_8)) } }.getOrNull()?.let { json ->
                return json.keys().asSequence().filter { json.opt(it) is String }
                    .associateWith { json.getString(it) }.toMutableMap()
            }
        }
        return preferences.all().toMutableMap()
    }

    fun write(values: Map<String, String>) {
        check(preferences.write(values)) { "Failed to save provider settings" }
        // Without the copy the preferences, now the newer file, are read as before.
        runCatching {
            locked {
                val partial = File(file.path + ".partial")
                FileOutputStream(partial).use { stream ->
                    stream.write(JSONObject(values).toString().toByteArray(Charsets.UTF_8))
                    stream.fd.sync()
                }
                Files.move(partial.toPath(), file.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
            }
        }
    }

    private fun <T> locked(action: () -> T): T = synchronized(localLock) {
        file.parentFile?.mkdirs()
        RandomAccessFile(File(file.path + ".lock"), "rw").use { lock -> lock.channel.lock().use { action() } }
    }

    private companion object { val localLock = Any() }
}
