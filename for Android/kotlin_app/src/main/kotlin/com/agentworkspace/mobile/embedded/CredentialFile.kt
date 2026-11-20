package com.agentworkspace.mobile.embedded

import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.RandomAccessFile
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/**
 * Stored credentials (target to ciphertext) in one file that the app's process and :engine read every
 * time and change under a file lock. SharedPreferences keeps a table per process and a commit writes
 * that whole table back, so one process's save dropped what the other had saved since: a pairing token,
 * or an API key.
 *
 * The first use on a phone copies the old store's values as they are (the ciphertext does not change)
 * and reads the copy back before relying on it. Until that has worked the old store stays in charge;
 * afterwards this file is, and the old store is still kept current for a build that only knows that one.
 */
internal class CredentialFile(
    private val file: File,
    private val old: OldStore,
    private val writeFile: (File, ByteArray) -> Unit = ::writeDurably,
) {
    interface OldStore {
        fun all(): Map<String, String>
        fun put(target: String, value: String)
        fun remove(target: String)
    }

    fun get(target: String): String? = readable()[target]

    fun targets(): List<String> = readable().keys.sorted()

    fun put(target: String, value: String) {
        if (update { it + (target to value) }) runCatching { old.put(target, value) } else old.put(target, value)
    }

    /** Whether there was such a credential. */
    fun remove(target: String): Boolean {
        var existed = false
        val updated = update { current -> existed = target in current; current - target }
        if (updated) runCatching { old.remove(target) } else {
            existed = target in old.all()
            old.remove(target)
        }
        return existed
    }

    private fun readable(): Map<String, String> = try { locked { values() } } catch (_: IOException) { null } ?: old.all()

    /** False when this file has not taken over yet: the change is the old store's. */
    private fun update(change: (Map<String, String>) -> Map<String, String>): Boolean = locked {
        val current = values() ?: return@locked false
        writeFile(file, encode(change(current)))
        true
    }

    /** What the file holds; on the first use, or after finding it unreadable, the old store's copy. Null when that failed. */
    private fun values(): Map<String, String>? {
        if (file.exists()) {
            runCatching { decode(file.readBytes()) }.getOrNull()?.let { return it }
            // Kept for whoever looks into it; the old store has been kept current.
            runCatching { Files.move(file.toPath(), File(file.path + ".unreadable").toPath(), StandardCopyOption.REPLACE_EXISTING) }
            if (file.exists()) return null
        }
        return try {
            val copied = old.all()
            writeFile(file, encode(copied))
            if (decode(file.readBytes()) == copied) copied else { file.delete(); null }
        } catch (_: Exception) {
            file.delete()
            null
        }
    }

    private fun <T> locked(action: () -> T): T = synchronized(LOCAL_LOCK) {
        file.parentFile?.mkdirs()
        RandomAccessFile(File(file.path + ".lock"), "rw").use { lock ->
            lock.channel.lock().use { action() }
        }
    }

    companion object {
        private val LOCAL_LOCK = Any()

        private fun encode(values: Map<String, String>): ByteArray =
            JSONObject().put("values", JSONObject(values)).toString().toByteArray(Charsets.UTF_8)

        private fun decode(bytes: ByteArray): Map<String, String> {
            val values = JSONObject(String(bytes, Charsets.UTF_8)).getJSONObject("values")
            return values.keys().asSequence().associateWith { values.getString(it) }
        }

        /** The new bytes on disk first, then in place at once: a crash leaves the old file or the new one. */
        internal fun writeDurably(file: File, bytes: ByteArray) {
            val partial = File(file.path + ".partial")
            FileOutputStream(partial).use { stream ->
                stream.write(bytes)
                stream.fd.sync()
            }
            Files.move(partial.toPath(), file.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
        }
    }
}
