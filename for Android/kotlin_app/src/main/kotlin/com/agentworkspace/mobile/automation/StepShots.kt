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
 * password or other protected content are never kept; such a step keeps only what was done.
 *
 * Each step also keeps when it was done and where it touched the screen (fractions of it), so a
 * tutorial can mark that spot on the picture taken before it (mobile_step_shots.tutorial_frames).
 */
internal object StepShots {
    private const val KEEP_TASKS = 20
    private const val KEEP_MILLIS = 7L * 24 * 3600 * 1000
    private const val WIDTH = 480

    internal class Step(val index: Int, val label: String, val acted: Long, val point: Pair<Float, Float>?)

    private fun root(context: Context) = File(context.filesDir, "agent-data/step-shots")

    /**
     * [screen] is null when the step could not be pictured; [shotAt] is when it was. [covers]: where
     * small floating windows were on it (left, top, right, bottom as fractions).
     */
    @Synchronized
    fun save(context: Context, task: String, step: Step, screen: Bitmap?, shotAt: Long, covers: List<FloatArray> = emptyList()) {
        val folder = File(root(context), task).apply { mkdirs() }
        if (screen != null) {
            val scale = WIDTH.toFloat() / screen.width
            val small = Bitmap.createScaledBitmap(screen, WIDTH, (screen.height * scale).toInt().coerceAtLeast(1), true)
            try {
                File(folder, "%02d.jpg".format(step.index)).outputStream().use { small.compress(Bitmap.CompressFormat.JPEG, 72, it) }
            } finally { if (small !== screen) small.recycle() }
        }
        val labels = File(folder, "steps.json")
        val list = runCatching { JSONArray(labels.readText()) }.getOrDefault(JSONArray())
        val entry = JSONObject().put("index", step.index).put("label", step.label.take(120))
            .put("acted", step.acted).put("at", shotAt)
        step.point?.let { (x, y) -> entry.put("x", x.toDouble()).put("y", y.toDouble()) }
        if (screen == null) entry.put("picture", false)
        if (covers.isNotEmpty()) entry.put("covers", JSONArray().apply {
            covers.take(6).forEach { box -> put(JSONArray().apply { box.forEach { put(it.toDouble()) } }) }
        })
        list.put(entry)
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
