package com.agentworkspace.mobile.devices

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import java.io.File
import java.security.SecureRandom
import org.json.JSONArray
import org.json.JSONObject

/**
 * Files picked, photographed or shared to "Send to computer" (docs/DEVICE_LINK_V2.md 2.7): copied into
 * files/to-computer under a random name (the original name goes with it to the page), where the engine
 * (mobile_link) sends them from and deletes them once sent. Nothing here leaves the phone; the page
 * shows the files and the user sends them.
 */
object ComputerSend {
    const val FOLDER = "to-computer"
    const val MAX_FILE_BYTES = 100L * 1024 * 1024
    private const val MAX_FILES = 50
    private const val KEEP_MILLIS = 24L * 60 * 60 * 1000
    private val random = SecureRandom()

    fun folder(context: Context): File = File(context.filesDir, FOLDER).apply { mkdirs() }

    /** A file name without folders or characters other systems refuse. */
    fun safeName(raw: String?): String {
        val name = (raw ?: "").replace('\\', '/').substringAfterLast('/')
            .filter { it.code >= 32 && it !in "<>:\"|?*" }.trim().trimStart('.')
        return name.take(180).ifEmpty { "file" }
    }

    /** A staged copy's own name: random hex and the original extension (the original name travels apart). */
    private fun stagedName(name: String): String {
        val random = ByteArray(8).also(random::nextBytes).joinToString("") { "%02x".format(it) }
        val extension = name.substringAfterLast('.', "").filter { it.isLetterOrDigit() && it.code < 128 }.take(10)
        return if (extension.isEmpty()) random else "$random.$extension"
    }

    /** Staged files left by a send that never happened are removed after a day. */
    private fun sweep(folder: File) {
        val cutoff = System.currentTimeMillis() - KEEP_MILLIS
        folder.listFiles()?.filter { it.isFile && it.lastModified() < cutoff }?.forEach { it.delete() }
    }

    private fun describe(context: Context, uri: Uri): Pair<String, Long> {
        var name: String? = null
        var size = -1L
        runCatching {
            context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)
                ?.use { cursor ->
                    if (cursor.moveToFirst()) {
                        cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME).takeIf { it >= 0 }?.let { name = cursor.getString(it) }
                        cursor.getColumnIndex(OpenableColumns.SIZE).takeIf { it >= 0 && !cursor.isNull(it) }?.let { size = cursor.getLong(it) }
                    }
                }
        }
        return safeName(name ?: uri.lastPathSegment) to size
    }

    /** Copies [uris] (and an existing [photo], moved) into the staging folder: {"ok", "files", "errors"}. */
    fun stage(context: Context, uris: List<Uri>, photo: File? = null): JSONObject {
        val folder = folder(context)
        sweep(folder)
        val files = JSONArray()
        val errors = JSONArray()
        photo?.let { taken ->
            val target = File(folder, stagedName(taken.name))
            if (taken.renameTo(target) || runCatching { taken.copyTo(target); taken.delete() }.isSuccess) {
                files.put(JSONObject().put("staged", target.name).put("name", safeName(taken.name)).put("size", target.length()))
            } else errors.put(safeName(taken.name))
        }
        for (uri in uris.distinct().take(MAX_FILES)) {
            val (name, declared) = describe(context, uri)
            if (declared > MAX_FILE_BYTES) { errors.put("$name: > 100 MiB"); continue }
            val target = File(folder, stagedName(name))
            try {
                var copied = 0L
                context.contentResolver.openInputStream(uri)?.use { input ->
                    target.outputStream().use { output ->
                        val buffer = ByteArray(64 * 1024)
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            copied += count
                            if (copied > MAX_FILE_BYTES) throw IllegalStateException("> 100 MiB")
                            output.write(buffer, 0, count)
                        }
                    }
                } ?: throw IllegalStateException("unreadable")
                files.put(JSONObject().put("staged", target.name).put("name", name).put("size", copied))
            } catch (failure: Exception) {
                target.delete()
                errors.put("$name: ${failure.message ?: "unreadable"}")
            }
        }
        if (uris.size > MAX_FILES) errors.put("only the first $MAX_FILES files")
        return JSONObject().put("ok", files.length() > 0).put("files", files).put("errors", errors)
    }

    /** Removes staged files the user took out of a send before sending. */
    fun discard(context: Context, names: List<String>) {
        val folder = folder(context)
        names.filter { Regex("[A-Za-z0-9._-]{1,200}").matches(it) }.forEach { File(folder, it).delete() }
    }
}
