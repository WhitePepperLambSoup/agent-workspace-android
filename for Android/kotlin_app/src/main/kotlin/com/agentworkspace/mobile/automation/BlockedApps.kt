package com.agentworkspace.mobile.automation

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * Apps the user does not let the agent read or operate (a bank, a payment app). Kept in a file, not
 * preferences: the settings page writes it in the app's process and the accessibility service, in
 * :engine, reads it (preferences loaded there earlier would not see the change).
 */
object BlockedApps {
    private const val FILE = "automation/blocked-apps.json"
    @Volatile private var cached: Pair<Long, Set<String>> = -1L to emptySet()

    private fun file(context: Context) = File(context.filesDir, FILE)

    fun packages(context: Context): Set<String> {
        val source = file(context)
        val modified = if (source.isFile) source.lastModified() else 0L
        cached.takeIf { it.first == modified }?.let { return it.second }
        val packages = runCatching {
            val list = JSONObject(source.readText()).getJSONArray("packages")
            (0 until list.length()).map { list.getString(it) }.filter { it.isNotBlank() }.toSet()
        }.getOrDefault(emptySet())
        cached = modified to packages
        return packages
    }

    fun save(context: Context, packages: Collection<String>) {
        val target = file(context)
        target.parentFile?.mkdirs()
        val partial = File(target.path + ".partial")
        partial.writeText(JSONObject().put("packages", JSONArray(packages.distinct().sorted())).toString())
        check(partial.renameTo(target)) { "Could not save the list" }
        cached = -1L to emptySet()
    }

    fun blocked(context: Context, packageName: String?): Boolean =
        packageName != null && packageName in packages(context)
}
