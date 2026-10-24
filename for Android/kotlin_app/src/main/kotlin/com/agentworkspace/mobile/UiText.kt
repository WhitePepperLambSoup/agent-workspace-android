package com.agentworkspace.mobile

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.util.Locale

/**
 * Native text follows the same language choice as the web UI ("auto" follows the system).
 * The web page reports the preference through AndroidBridge.setUiLanguage.
 */
object UiText {
    private const val PREFERENCES = "agent_ui"
    private const val LANGUAGE = "language"
    // The bubble's panel and other :engine windows live in another process, whose copy of the
    // preferences is not refreshed: the choice is also kept in a file that is read each time.
    private const val FILE = "ui_language"
    // Native text has no Traditional Chinese copy yet: "zh-Hant" shows the Chinese wording.
    private val choices = setOf("auto", "zh", "zh-Hant", "en", "ja", "ko")
    private val HOLE = Regex("""\{(\d+)\}""")

    fun setPreference(context: Context, value: String) {
        if (value !in choices) return
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit().putString(LANGUAGE, value).apply()
        runCatching { File(context.filesDir, FILE).writeText(value) }
    }

    private fun preference(context: Context): String? =
        runCatching { File(context.filesDir, FILE).takeIf { it.isFile }?.readText()?.trim() }.getOrNull()
            ?.takeIf { it in choices }
            ?: context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).getString(LANGUAGE, "auto")

    /** "zh", "en", "ja" or "ko": the wording native text uses. */
    fun language(context: Context): String = when (val value = preference(context)) {
        "zh", "zh-Hant" -> "zh"
        "en", "ja", "ko" -> value
        else -> when (Locale.getDefault().language) {
            Locale.CHINESE.language -> "zh"
            Locale.JAPANESE.language -> "ja"
            Locale.KOREAN.language -> "ko"
            else -> "en"
        }
    }

    /** Picks the wording for user-visible native text; Japanese and Korean are looked up by the English. */
    fun of(context: Context, zh: String, en: String): String = when (val language = language(context)) {
        "zh" -> zh
        "en" -> en
        else -> catalog(context, language).translate(en)
    }

    // Japanese and Korean: res/raw/ui_text_ja.json and ui_text_ko.json map each English wording to its
    // translation. A Kotlin string template is written with {0}, {1}... and matches the filled-in text.
    // generate_ja_ko.py checks that every wording of the sources is there.
    @Volatile private var loaded: Pair<String, Catalog>? = null

    private fun catalog(context: Context, language: String): Catalog {
        loaded?.let { (cached, catalog) -> if (cached == language) return catalog }
        val id = if (language == "ja") R.raw.ui_text_ja else R.raw.ui_text_ko
        val source = runCatching {
            context.resources.openRawResource(id).bufferedReader().use { it.readText() }
        }.getOrDefault("{}")
        return Catalog.parse(source).also { loaded = language to it }
    }

    internal class Catalog private constructor(
        private val plain: Map<String, String>,
        private val templates: List<Template>,
    ) {
        private class Template(val pattern: Regex, val holes: List<Int>, val text: String, val fixed: Int)

        fun translate(en: String): String {
            plain[en]?.let { return it }
            for (template in templates) {
                val match = template.pattern.matchEntire(en) ?: continue
                // A filled-in value that is itself a known wording (such as a shared English constant) is translated too.
                return HOLE.replace(template.text) { hole ->
                    val index = template.holes.indexOf(hole.groupValues[1].toInt())
                    if (index < 0) hole.value else match.groupValues[index + 1].let { plain[it] ?: it }
                }
            }
            return en
        }

        companion object {
            fun parse(source: String): Catalog {
                val json = runCatching { JSONObject(source) }.getOrDefault(JSONObject())
                val plain = HashMap<String, String>()
                val templates = ArrayList<Template>()
                for (key in json.keys()) {
                    val text = json.optString(key)
                    if (!HOLE.containsMatchIn(key)) {
                        plain[key] = text
                        continue
                    }
                    // A key that is only placeholders would match anything.
                    val fixed = key.replace(HOLE, "")
                    if (fixed.none { it.isLetter() }) continue
                    val holes = HOLE.findAll(key).map { it.groupValues[1].toInt() }.toList()
                    val pattern = key.split(HOLE).joinToString("(.*?)") { Regex.escape(it) }
                    templates += Template(Regex(pattern, RegexOption.DOT_MATCHES_ALL), holes, text, fixed.length)
                }
                // The longest fixed wording first, so "Shortcut “{0}” done" is tried before "Shortcut: {0}".
                templates.sortByDescending { it.fixed }
                return Catalog(plain, templates)
            }
        }
    }
}

