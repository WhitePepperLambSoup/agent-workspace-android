package com.agentworkspace.mobile

import android.content.Context
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
    private val choices = setOf("auto", "zh", "zh-Hant", "en")

    fun setPreference(context: Context, value: String) {
        if (value !in choices) return
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit().putString(LANGUAGE, value).apply()
        runCatching { File(context.filesDir, FILE).writeText(value) }
    }

    private fun preference(context: Context): String? =
        runCatching { File(context.filesDir, FILE).takeIf { it.isFile }?.readText()?.trim() }.getOrNull()
            ?.takeIf { it in choices }
            ?: context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).getString(LANGUAGE, "auto")

    fun isEnglish(context: Context): Boolean = when (preference(context)) {
        "en" -> true
        "zh", "zh-Hant" -> false
        else -> Locale.getDefault().language != Locale.CHINESE.language
    }

    /** Picks the Chinese or English wording for user-visible native text. */
    fun of(context: Context, zh: String, en: String): String = if (isEnglish(context)) en else zh
}
