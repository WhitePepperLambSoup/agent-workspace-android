package com.agentworkspace.mobile.entry

import android.content.Context
import android.content.Intent
import android.content.pm.ShortcutInfo
import android.content.pm.ShortcutManager
import android.graphics.drawable.Icon
import com.agentworkspace.mobile.R
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.WebUiActivity

/**
 * Ways into the app from anywhere on the phone: the quick settings tile, the floating ball and the
 * launcher shortcuts all open a fresh conversation with the input ready ("quick ask").
 */
object QuickEntry {
    const val ACTION_QUICK_ASK = "com.agentworkspace.mobile.QUICK_ASK"
    const val EXTRA_MODE = "quick_mode"
    const val EXTRA_SHARE_BATCH = "quick_share_batch"
    const val EXTRA_NOTE_TOKEN = "quick_note_token"
    val MODES = setOf("text", "voice", "camera", "screen")
    private const val NOTE_PREFERENCES = "voice-note"

    fun intent(context: Context, mode: String = "text", shareBatch: String? = null): Intent =
        Intent(context, WebUiActivity::class.java)
            .setAction(ACTION_QUICK_ASK)
            .putExtra(EXTRA_MODE, if (mode in MODES) mode else "text")
            .apply { if (shareBatch != null) putExtra(EXTRA_SHARE_BATCH, shareBatch) }
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)

    /**
     * A finished voice note: the page submits it without waiting for the user. Other apps can
     * open the quick ask too, so the "note" mode needs a one-time token only this app knows.
     */
    fun voiceNoteIntent(context: Context, shareBatch: String): Intent {
        val token = java.util.UUID.randomUUID().toString()
        context.getSharedPreferences(NOTE_PREFERENCES, Context.MODE_PRIVATE).edit().putString("token", token).commit()
        return intent(context, "text", shareBatch).putExtra(EXTRA_MODE, "note").putExtra(EXTRA_NOTE_TOKEN, token)
    }

    /** The mode a quick ask asked for; "note" only with this app's unused token. */
    fun acceptedMode(context: Context, incoming: Intent): String {
        val mode = incoming.getStringExtra(EXTRA_MODE)
        if (mode != "note") return mode?.takeIf { it in MODES } ?: "text"
        val preferences = context.getSharedPreferences(NOTE_PREFERENCES, Context.MODE_PRIVATE)
        val expected = preferences.getString("token", null)
        val given = incoming.getStringExtra(EXTRA_NOTE_TOKEN)
        if (expected == null || given != expected) return "text"
        preferences.edit().remove("token").commit()
        return "note"
    }

    fun voiceNoteActivity(context: Context): Intent = Intent(context, VoiceNoteActivity::class.java)
        .setAction(Intent.ACTION_VIEW)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    /** Long-press shortcuts on the launcher icon, labelled in the app's current language. */
    fun publishShortcuts(context: Context) {
        val manager = context.getSystemService(ShortcutManager::class.java) ?: return
        // The white sparkle is for tinted system surfaces; launcher menus are light, so use the app icon.
        val icon = Icon.createWithResource(context, R.drawable.ic_launcher)
        fun shortcut(id: String, mode: String, zh: String, en: String) = ShortcutInfo.Builder(context, id)
            .setShortLabel(UiText.of(context, zh, en))
            .setIcon(icon)
            .setIntent(intent(context, mode))
            .build()
        runCatching {
            manager.dynamicShortcuts = listOf(
                shortcut("quick-ask", "text", "新对话", "New chat"),
                shortcut("quick-voice", "voice", "语音提问", "Ask by voice"),
                shortcut("quick-camera", "camera", "拍照提问", "Ask about a photo"),
                ShortcutInfo.Builder(context, "voice-note")
                    .setShortLabel(UiText.of(context, "录音速记", "Voice note"))
                    .setIcon(icon)
                    .setIntent(voiceNoteActivity(context))
                    .build(),
            )
        }
    }
}
