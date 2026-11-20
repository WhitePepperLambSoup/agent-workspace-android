package com.agentworkspace.mobile.automation

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import org.json.JSONObject
import java.io.File

/**
 * 长辈模式 (mobile_elder.py): while it is on, the agent does not read or operate the screens many
 * scams on older people need: Android's app installer (installing or removing an app), apps that let
 * someone else see and use the phone (remote control, screen sharing in meetings), and the settings
 * that hand the phone over (accessibility, device admin, unknown apps, developer options and USB or
 * wireless debugging). Refused, never asked: the older person is not asked to approve anything. The
 * user's own taps are not affected.
 */
internal object ElderGuard {
    private val installers = setOf(
        "com.android.packageinstaller", "com.google.android.packageinstaller", "com.miui.packageinstaller",
        "com.samsung.android.packageinstaller", "com.oplus.appdetail", "com.coloros.packageinstaller",
    )
    // 向日葵, ToDesk, TeamViewer, AnyDesk, RustDesk, Splashtop, Microsoft Remote Desktop, AirDroid, Chrome
    // Remote Desktop, RealVNC; and meetings whose screen sharing such scams use: 腾讯会议, Zoom, 钉钉.
    private val remoteControl = listOf(
        "com.oray.sunlogin", "youqu.android.todesk", "com.teamviewer.", "com.anydesk.", "com.carriez.flutter_hbb",
        "com.splashtop.", "com.microsoft.rdc.", "com.sand.airdroid", "com.google.chromeremotedesktop",
        "com.realvnc.", "com.tencent.wemeet.", "us.zoom.", "com.alibaba.android.rimet",
    )
    // Rows in Settings that hand the phone over (spaces removed): accessibility, device admin, installing
    // from unknown sources, reading notifications, developer options and debugging.
    private val permissionRows = Regex(
        "无障碍|设备管理|未知应用|未知来源|通知使用权|通知访问|开发者|无线调试|USB调试|" +
            // Tapped seven times, the version row turns developer options on.
            "版本号|MIUI版本|" +
            "(?i)(accessibility|deviceadmin|unknownapps|unknownsources|notificationaccess|developer|wirelessdebugging|" +
            "usbdebugging|buildnumber|miuiversion)"
    )
    // Words only the developer options page shows: its switches carry no words of their own.
    private val developerPage = Regex("无线调试|USB调试|(?i)(wirelessdebugging|usbdebugging)")
    private val settingsApps = listOf("settings", "permissioncontroller", "securitycenter", "safecenter")
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

    /**
     * The phone's own app installer and uninstaller, whatever the maker named them: the system apps
     * that take an install or uninstall request (only an installer does).
     */
    fun installerPackages(manager: PackageManager): Set<String> = runCatching {
        listOf(
            Intent(Intent.ACTION_INSTALL_PACKAGE, Uri.parse("package:agent.invalid")),
            @Suppress("DEPRECATION") Intent(Intent.ACTION_UNINSTALL_PACKAGE, Uri.parse("package:agent.invalid")),
            Intent(Intent.ACTION_DELETE, Uri.parse("package:agent.invalid")),
        ).flatMap { manager.queryIntentActivities(it, PackageManager.MATCH_SYSTEM_ONLY) }
            .mapNotNull { it.activityInfo?.packageName }.toSet()
    }.getOrDefault(emptySet())

    /** [found]: installers found on this phone ([installerPackages]), beside the known ones. */
    fun guarded(packageName: String?, found: Set<String> = emptySet()): Boolean =
        packageName != null && (packageName in installers || packageName in found || remoteControl.any { packageName.startsWith(it) })

    /** The words of a pressed row in a settings app that grants such a power, or null. */
    fun permissionRow(packageName: String?, pressed: Iterable<String?>): String? {
        if (!settingsApp(packageName)) return null
        return pressed.filterNotNull().firstOrNull { permissionRows.containsMatchIn(it.filterNot(Char::isWhitespace)) }
    }

    /** What shows a settings app is on the developer options page, where nothing is pressed; or null. */
    fun permissionPage(packageName: String?, screen: Iterable<String?>): String? {
        if (!settingsApp(packageName)) return null
        return screen.filterNotNull().firstOrNull { developerPage.containsMatchIn(it.filterNot(Char::isWhitespace)) }
    }

    private fun settingsApp(packageName: String?): Boolean {
        val app = packageName?.lowercase() ?: return false
        return settingsApps.any { it in app }
    }
}
