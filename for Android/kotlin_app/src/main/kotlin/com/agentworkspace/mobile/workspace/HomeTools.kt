package com.agentworkspace.mobile.workspace

import android.content.Context
import android.content.Intent
import android.content.pm.ShortcutInfo
import android.content.pm.ShortcutManager
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.drawable.Icon
import android.net.Uri
import android.text.Html
import android.webkit.WebStorage
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

/**
 * Small tools on the home screen: a single-file HTML page the agent made (a converter, a tracker), kept
 * as a copy in the app and opened by its own shortcut in [ToolActivity], offline and away from the
 * app. Each tool has its own web origin, so what it keeps in localStorage stays with it.
 */
object HomeTools {
    const val SCHEME = "agentworkspace-tool"
    private const val MAX_HTML_BYTES = 2L * 1024 * 1024
    private const val MAX_TOOLS = 50
    private val idPattern = Regex("[a-f0-9]{16}")
    private val palette = intArrayOf(0xFF1A73E8.toInt(), 0xFF188038.toInt(), 0xFFE37400.toInt(), 0xFFA142F4.toInt(),
        0xFFD93025.toInt(), 0xFF007B83.toInt(), 0xFF5F6368.toInt(), 0xFFC5221F.toInt())

    class Tool(val id: String, val name: String, val createdAt: Long, val source: String) {
        fun json(): JSONObject = JSONObject().put("id", id).put("name", name).put("created_at", createdAt).put("source", source)
    }

    private fun root(context: Context) = File(context.filesDir, "home-tools")

    fun validId(id: String?): String? = id?.takeIf { idPattern.matches(it) }

    fun origin(id: String) = "https://tool-$id.invalid"

    fun page(context: Context, id: String): File = File(File(root(context), id), "index.html")

    /** A copy of the page as a tool; the same page added again is the same tool. */
    @Synchronized
    fun install(context: Context, html: File, sourcePath: String): Tool {
        require(html.isFile && html.length() in 1..MAX_HTML_BYTES) { "A home-screen tool is one HTML file of at most 2 MB" }
        val bytes = html.readBytes()
        val id = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }.take(16)
        val folder = File(root(context), id)
        if (!folder.isDirectory) require(list(context).size < MAX_TOOLS) { "Remove a tool first: at most $MAX_TOOLS are kept" }
        folder.mkdirs()
        File(folder, "index.html").writeBytes(bytes)
        val tool = Tool(id, nameOf(bytes.toString(Charsets.UTF_8), sourcePath), System.currentTimeMillis(), sourcePath.take(300))
        File(folder, "tool.json").writeText(tool.json().toString())
        return tool
    }

    /** The page's own title, or its file name. */
    internal fun nameOf(html: String, path: String): String {
        val title = Regex("<title[^>]*>(.*?)</title>", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))
            .find(html.take(65536))?.groupValues?.get(1)
            ?.let { Html.fromHtml(it, Html.FROM_HTML_MODE_LEGACY).toString() }
            ?.replace(Regex("\\s+"), " ")?.trim()
        val name = title?.takeIf { it.isNotEmpty() } ?: path.substringAfterLast('/').substringBeforeLast('.')
        return name.ifBlank { "Tool" }.take(24)
    }

    fun get(context: Context, id: String): Tool? {
        val valid = validId(id) ?: return null
        return runCatching {
            val data = JSONObject(File(File(root(context), valid), "tool.json").readText())
            Tool(valid, data.getString("name"), data.optLong("created_at"), data.optString("source"))
        }.getOrNull()?.takeIf { page(context, valid).isFile }
    }

    fun list(context: Context): List<Tool> =
        root(context).listFiles()?.mapNotNull { get(context, it.name) }?.sortedByDescending { it.createdAt }.orEmpty()

    fun listJson(context: Context): String = JSONObject().put("tools", JSONArray(list(context).map { it.json() })).toString()

    @Synchronized
    fun delete(context: Context, id: String) {
        val tool = get(context, id) ?: return
        File(root(context), tool.id).deleteRecursively()
        WebStorage.getInstance().deleteOrigin(origin(tool.id) + "/")
        runCatching {
            context.getSystemService(ShortcutManager::class.java)?.disableShortcuts(listOf(shortcutId(tool.id)),
                com.agentworkspace.mobile.UiText.of(context, "这个小工具已经删除了", "This tool has been removed"))
        }
    }

    fun openIntent(context: Context, id: String): Intent = Intent(context, ToolActivity::class.java)
        .setAction(Intent.ACTION_VIEW)
        .setData(Uri.parse("$SCHEME://$id"))
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NEW_DOCUMENT)

    private fun shortcutId(id: String) = "tool-$id"

    /** Asks the launcher to pin the tool's shortcut; false when it cannot. */
    fun pin(context: Context, tool: Tool): Boolean {
        val manager = context.getSystemService(ShortcutManager::class.java) ?: return false
        if (!manager.isRequestPinShortcutSupported) return false
        val shortcut = ShortcutInfo.Builder(context, shortcutId(tool.id))
            .setShortLabel(tool.name)
            .setLongLabel(tool.name)
            .setIcon(Icon.createWithAdaptiveBitmap(icon(tool)))
            .setIntent(openIntent(context, tool.id))
            .build()
        // Pinned before: the launcher keeps it, with the label and icon brought up to date.
        if (manager.pinnedShortcuts.any { it.id == shortcut.id }) {
            manager.enableShortcuts(listOf(shortcut.id))
            manager.updateShortcuts(listOf(shortcut))
        }
        return manager.requestPinShortcut(shortcut, null)
    }

    /** The tool's first letter on a color of its own, drawn for an adaptive icon (108 dp, 72 dp shown). */
    private fun icon(tool: Tool): Bitmap {
        val size = 432
        val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        canvas.drawColor(palette[(tool.id.take(8).toLong(16) % palette.size).toInt()])
        val letter = tool.name.trim().let { name -> name.codePointAt(0).let { String(Character.toChars(it)) } }.uppercase()
        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = size * 0.34f
            typeface = Typeface.DEFAULT_BOLD
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText(letter, size / 2f, size / 2f - (paint.ascent() + paint.descent()) / 2, paint)
        return bitmap
    }
}
