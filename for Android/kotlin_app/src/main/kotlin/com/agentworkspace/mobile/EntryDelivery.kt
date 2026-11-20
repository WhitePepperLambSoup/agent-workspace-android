package com.agentworkspace.mobile

import android.content.Intent

/** Whether the console acts on what its launch intent asks for (an expert-team share, voice input). */
internal object EntryDelivery {
    /**
     * Only the first delivery does. A recreation (dark mode, language, font size) restores saved
     * state and sees the same intent again; a launch from recents replays the original intent.
     */
    fun first(restored: Boolean, flags: Int): Boolean =
        !restored && (flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY) == 0
}
