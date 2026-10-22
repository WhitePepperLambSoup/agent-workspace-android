package com.agentworkspace.mobile.automation

import android.content.Context
import org.json.JSONObject
import java.io.File

/**
 * 长辈模式 (mobile_elder.py): while it is on, the agent does not read or operate the screens many
 * scams on older people need: Android's app installer (installing or removing an app) and
 * remote-control apps that let someone else see and use the phone. Refused, never asked: the older
 * person is not asked to approve anything. The user's own taps are not affected.
 */
internal object ElderGuard {
    private val installers = setOf(
        "com.android.packageinstaller", "com.google.android.packageinstaller", "com.miui.packageinstaller",
        "com.samsung.android.packageinstaller", "com.oplus.appdetail", "com.coloros.packageinstaller",
    )
    // 向日葵, ToDesk, TeamViewer, AnyDesk, RustDesk, Splashtop, Microsoft Remote Desktop.
    private val remoteControl = listOf(
        "com.oray.sunlogin", "youqu.android.todesk", "com.teamviewer.", "com.anydesk.", "com.carriez.flutter_hbb",
        "com.splashtop.", "com.microsoft.rdc.",
    )
    @Volatile private var cached: Pair<Long, Boolean> = -1L to false

    /** Whether the mode is on (its settings file, read again only when it changed). */
    fun on(context: Context): Boolean {
        val file = File(context.filesDir, "agent-data/elder-mode.json")
        val modified = if (file.isFile) file.lastModified() else 0L
        cached.takeIf { it.first == modified }?.let { return it.second }
        val enabled = modified != 0L && runCatching { JSONObject(file.readText()).optBoolean("enabled") }.getOrDefault(false)
        cached = modified to enabled
        return enabled
    }

    fun guarded(packageName: String?): Boolean =
        packageName != null && (packageName in installers || remoteControl.any { packageName.startsWith(it) })
}
