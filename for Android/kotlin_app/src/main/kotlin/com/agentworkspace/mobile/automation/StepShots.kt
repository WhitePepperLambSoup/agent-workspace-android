package com.agentworkspace.mobile.automation

import android.content.Context
import android.graphics.Bitmap
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * Step replay: a small picture of the screen after each action the agent took in a task, with what
 * the action was, so the user can look back at what it did. Kept in agent-data/step-shots/<task>/
 * (read by mobile_step_shots.py): the 20 latest tasks, none older than 7 days. Screens with
 * password or other protected content are never kept.
 */
internal object StepShots {
    private const val KEEP_TASKS = 20
    private const val KEEP_MILLIS = 7L * 24 * 3600 * 1000
    private const val WIDTH = 360

    private fun root(context: Context) = File(context.filesDir, "agent-data/step-shots")

    @Synchronized
    fun save(context: Context, task: String, index: Int, label: String, screen: Bitmap) {
        val folder = File(root(context), task).apply { mkdirs() }
        val scale = WIDTH.toFloat() / screen.width
        val small = Bitmap.createScaledBitmap(screen, WIDTH, (screen.height * scale).toInt().coerceAtLeast(1), true)
        try {
            File(folder, "%02d.jpg".format(index)).outputStream().use { small.compress(Bitmap.CompressFormat.JPEG, 70, it) }
        } finally { if (small !== screen) small.recycle() }
        val labels = File(folder, "steps.json")
        val list = runCatching { JSONArray(labels.readText()) }.getOrDefault(JSONArray())
        list.put(JSONObject().put("index", index).put("label", label.take(120)).put("at", System.currentTimeMillis()))
        labels.writeText(list.toString())
    }

    /** Older tasks go: beyond the 20 latest, or a week old. */
    @Synchronized
    fun prune(context: Context) {
        val folders = root(context).listFiles()?.filter { it.isDirectory }?.sortedByDescending { it.lastModified() } ?: return
        val now = System.currentTimeMillis()
        folders.forEachIndexed { position, folder ->
            if (position >= KEEP_TASKS || now - folder.lastModified() > KEEP_MILLIS) folder.deleteRecursively()
        }
    }
}
