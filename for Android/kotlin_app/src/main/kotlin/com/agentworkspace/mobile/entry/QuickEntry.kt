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
    val MODES = setOf("text", "voice", "camera", "screen")

    fun intent(context: Context, mode: String = "text", shareBatch: String? = null): Intent =
        Intent(context, WebUiActivity::class.java)
            .setAction(ACTION_QUICK_ASK)
            .putExtra(EXTRA_MODE, if (mode in MODES) mode else "text")
            .apply { if (shareBatch != null) putExtra(EXTRA_SHARE_BATCH, shareBatch) }
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)

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
            )
        }
    }
}
