package com.agentworkspace.mobile

import android.content.Context
import java.util.Locale

/**
 * Native text follows the same language choice as the web UI ("auto" follows the system).
 * The web page reports the preference through AndroidBridge.setUiLanguage.
 */
object UiText {
    private const val PREFERENCES = "agent_ui"
    private const val LANGUAGE = "language"
    // Native text has no Traditional Chinese copy yet: "zh-Hant" shows the Chinese wording.
    private val choices = setOf("auto", "zh", "zh-Hant", "en")

    fun setPreference(context: Context, value: String) {
        if (value !in choices) return
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit().putString(LANGUAGE, value).apply()
    }

    fun isEnglish(context: Context): Boolean {
        val preference = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).getString(LANGUAGE, "auto")
        return when (preference) {
            "en" -> true
            "zh", "zh-Hant" -> false
            else -> Locale.getDefault().language != Locale.CHINESE.language
        }
    }

    /** Picks the Chinese or English wording for user-visible native text. */
    fun of(context: Context, zh: String, en: String): String = if (isEnglish(context)) en else zh
}
