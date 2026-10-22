package com.agentworkspace.mobile.capabilities

import android.app.AppOpsManager
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import com.agentworkspace.mobile.automation.PopupWatch
import org.json.JSONArray
import org.json.JSONObject

/**
 * 应用体检 (looking for rogue apps): what each installed app is allowed to do and how it got here,
 * for mobile_app_audit.py to weigh. Only facts Android tells any app with QUERY_ALL_PACKAGES; no
 * root, no scanning of files. Also opens the system pages that undo something: the uninstall
 * confirmation (the user confirms it there), an app's details, its notifications, the overlay,
 * accessibility, device admin and battery pages.
 */
object AppAudit {
    /** Opens the app at 应用体检 (WebUiActivity), from the notification below. */
    const val ACTION_OPEN = "com.agentworkspace.mobile.OPEN_APP_CHECK"
    private const val CHANNEL = "agent_app_check"

    @Volatile private var context: Context? = null

    @JvmStatic fun initialize(context: Context) { this.context = context.applicationContext }

    private val interesting = mapOf(
        "android.permission.READ_SMS" to "sms", "android.permission.RECEIVE_SMS" to "sms", "android.permission.SEND_SMS" to "sms",
        "android.permission.READ_CALL_LOG" to "call_log", "android.permission.WRITE_CALL_LOG" to "call_log",
        "android.permission.READ_CONTACTS" to "contacts",
        "android.permission.ACCESS_FINE_LOCATION" to "location", "android.permission.ACCESS_COARSE_LOCATION" to "location",
        "android.permission.ACCESS_BACKGROUND_LOCATION" to "background_location",
        "android.permission.RECORD_AUDIO" to "microphone", "android.permission.CAMERA" to "camera",
        "android.permission.READ_PHONE_STATE" to "phone", "android.permission.CALL_PHONE" to "call",
    )

    @JvmStatic
    fun execute(raw: String): String {
        val app = context ?: return fail("unavailable", "The app check is not ready")
        return try {
            val request = JSONObject(raw)
            when (request.optString("action")) {
                "scan" -> scan(app)
                "popups" -> JSONObject().put("ok", true).put("popups", PopupWatch.records(app)).put("watching", PopupWatch.enabled(app))
                "watch" -> { PopupWatch.setEnabled(app, request.optBoolean("enabled")); JSONObject().put("ok", true).put("watching", PopupWatch.enabled(app)) }
                // Both wordings come along; the app's language picks one.
                "notify" -> notify(app,
                    com.agentworkspace.mobile.UiText.of(app, request.optString("title_zh"), request.optString("title_en")).take(80),
                    com.agentworkspace.mobile.UiText.of(app, request.optString("text_zh"), request.optString("text_en")).take(300))
                "uninstall" -> uninstall(app, packageOf(app, request))
                "open" -> open(app, packageOf(app, request), request.optString("page"))
                else -> JSONObject(fail("invalid_arguments", "Unknown action"))
            }.toString()
        } catch (error: Exception) {
            fail("failed", error.message ?: error.javaClass.simpleName)
        }
    }

    private fun fail(code: String, message: String): String =
        JSONObject().put("ok", false).put("code", code).put("error", message).toString()

    /** An installed app other than this one, or an error. */
    private fun packageOf(app: Context, request: JSONObject): String {
        val name = request.optString("package_name")
        require(Regex("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z0-9_]+)+").matches(name) && name.length <= 255) { "package_name is not an app id" }
        require(name != app.packageName) { "That is this app" }
        app.packageManager.getApplicationInfo(name, 0)
        return name
    }

    private fun enabledComponents(app: Context, key: String): Set<String> =
        (Settings.Secure.getString(app.contentResolver, key) ?: "").split(':')
            .mapNotNull { ComponentName.unflattenFromString(it)?.packageName }.toSet()

    @Suppress("DEPRECATION")
    private fun installed(manager: PackageManager): List<PackageInfo> =
        if (Build.VERSION.SDK_INT >= 33) manager.getInstalledPackages(PackageManager.PackageInfoFlags.of(PackageManager.GET_PERMISSIONS.toLong()))
        else manager.getInstalledPackages(PackageManager.GET_PERMISSIONS)

    /** The app that installed [name], and the one that asked for it (a browser handing an APK to Android's installer). */
    @Suppress("DEPRECATION")
    private fun installer(manager: PackageManager, name: String): Pair<String?, String?> = runCatching {
        if (Build.VERSION.SDK_INT >= 30) manager.getInstallSourceInfo(name).let { it.installingPackageName to it.initiatingPackageName }
        else manager.getInstallerPackageName(name) to null
    }.getOrDefault(null to null)

    private fun label(manager: PackageManager, name: String?): Any =
        name?.let { runCatching { manager.getApplicationLabel(manager.getApplicationInfo(it, 0)).toString().take(80) }.getOrNull() }
            ?: JSONObject.NULL

    private fun scan(app: Context): JSONObject {
        val manager = app.packageManager
        val launchable = manager.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER), 0)
            .map { it.activityInfo.packageName }.toSet()
        val accessibility = enabledComponents(app, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
        val listeners = enabledComponents(app, "enabled_notification_listeners")
        val admins = runCatching { app.getSystemService(DevicePolicyManager::class.java)?.activeAdmins?.map { it.packageName }?.toSet() }
            .getOrNull().orEmpty()
        val power = app.getSystemService(PowerManager::class.java)
        val operations = app.getSystemService(AppOpsManager::class.java)
        val apps = JSONArray()
        for (info in installed(manager)) {
            val application = info.applicationInfo ?: continue
            // Apps that came with the phone cannot be removed the normal way; the check is for installed ones.
            if (application.flags and android.content.pm.ApplicationInfo.FLAG_SYSTEM != 0 || info.packageName == app.packageName) continue
            val name = info.packageName
            val requested = info.requestedPermissions?.toList().orEmpty()
            val granted = requested.filterIndexed { index, _ ->
                (info.requestedPermissionsFlags?.getOrNull(index) ?: 0) and PackageInfo.REQUESTED_PERMISSION_GRANTED != 0
            }
            fun operation(operation: String): Int? = runCatching {
                @Suppress("DEPRECATION")
                if (Build.VERSION.SDK_INT >= 29) operations?.unsafeCheckOpNoThrow(operation, application.uid, name)
                else operations?.checkOpNoThrow(operation, application.uid, name)
            }.getOrNull()
            fun allowed(operation: String, permission: String): Boolean = when (operation(operation)) {
                AppOpsManager.MODE_ALLOWED -> true
                AppOpsManager.MODE_DEFAULT -> manager.checkPermission(permission, name) == PackageManager.PERMISSION_GRANTED
                else -> false
            }
            val (installer, initiator) = installer(manager, name)
            apps.put(JSONObject()
                .put("package", name)
                .put("label", application.loadLabel(manager).toString().take(80))
                .put("version", info.versionName ?: "")
                .put("installer", installer ?: JSONObject.NULL)
                .put("installer_label", label(manager, installer))
                .put("initiator", initiator ?: JSONObject.NULL)
                .put("initiator_label", label(manager, initiator))
                .put("first_install", info.firstInstallTime)
                .put("last_update", info.lastUpdateTime)
                .put("target_sdk", application.targetSdkVersion)
                .put("launcher", name in launchable)
                .put("enabled", application.enabled)
                .put("permissions", JSONArray(granted.mapNotNull { interesting[it] }.distinct()))
                .put("overlay", "android.permission.SYSTEM_ALERT_WINDOW" in requested &&
                    allowed(AppOpsManager.OPSTR_SYSTEM_ALERT_WINDOW, "android.permission.SYSTEM_ALERT_WINDOW"))
                .put("install_others", "android.permission.REQUEST_INSTALL_PACKAGES" in requested &&
                    allowed("android:request_install_packages", "android.permission.REQUEST_INSTALL_PACKAGES"))
                .put("usage_access", "android.permission.PACKAGE_USAGE_STATS" in requested &&
                    allowed(AppOpsManager.OPSTR_GET_USAGE_STATS, "android.permission.PACKAGE_USAGE_STATS"))
                .put("accessibility", name in accessibility)
                .put("notification_listener", name in listeners)
                .put("device_admin", name in admins)
                .put("battery_unrestricted", power?.isIgnoringBatteryOptimizations(name) == true)
                .put("boot", "android.permission.RECEIVE_BOOT_COMPLETED" in requested))
        }
        val popups = PopupWatch.records(app)
        // The apps that were in front when something popped up (a home screen, a game).
        val labels = JSONObject()
        for (index in 0 until popups.length()) {
            val over = popups.getJSONObject(index).optString("over")
            if (over.isNotEmpty() && !labels.has(over)) labels.put(over, label(manager, over))
        }
        return JSONObject().put("ok", true).put("apps", apps).put("popups", popups).put("labels", labels)
            .put("watching", PopupWatch.enabled(app)).put("scanned_at", System.currentTimeMillis())
            // Pop-ups are seen through the accessibility service: off, nothing is recorded.
            .put("watch_ready", com.agentworkspace.mobile.automation.AndroidSystemBridge.service != null)
    }

    /** A newly installed or changed app worth a look (mobile_app_audit.watch); tapping opens the check. */
    private fun notify(app: Context, title: String, text: String): JSONObject {
        require(title.isNotBlank()) { "title is required" }
        if (!androidx.core.app.NotificationManagerCompat.from(app).areNotificationsEnabled()) {
            return JSONObject().put("ok", true).put("posted", false)
        }
        val manager = app.getSystemService(android.app.NotificationManager::class.java)
        manager.createNotificationChannel(android.app.NotificationChannel(CHANNEL,
            com.agentworkspace.mobile.UiText.of(app, "应用体检", "App check"), android.app.NotificationManager.IMPORTANCE_DEFAULT))
        val open = Intent(app, com.agentworkspace.mobile.WebUiActivity::class.java).setAction(ACTION_OPEN)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        manager.notify("agent-app-check", 3020, androidx.core.app.NotificationCompat.Builder(app, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(androidx.core.app.NotificationCompat.BigTextStyle().bigText(text))
            .setAutoCancel(true)
            .setContentIntent(android.app.PendingIntent.getActivity(app, 3020, open,
                android.app.PendingIntent.FLAG_IMMUTABLE or android.app.PendingIntent.FLAG_UPDATE_CURRENT))
            .build())
        return JSONObject().put("ok", true).put("posted", true)
    }

    /** Android's own confirmation; nothing is removed unless the user taps OK there. */
    private fun uninstall(app: Context, name: String): JSONObject {
        app.startActivity(Intent(Intent.ACTION_DELETE, Uri.parse("package:$name")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        return JSONObject().put("ok", true).put("opened", "uninstall")
    }

    private fun open(app: Context, name: String, page: String): JSONObject {
        val target = Uri.parse("package:$name")
        val details = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, target)
        val choices = when (page) {
            "info" -> listOf(details)
            "notifications" -> listOf(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, name))
            "overlay" -> listOf(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, target))
            "install_others" -> listOf(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, target))
            "usage_access" -> listOf(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
            "notification_access" -> listOf(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            "accessibility" -> listOf(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            // The device admin list has no public action: Android's own screen, else security settings.
            "device_admin" -> listOf(
                Intent().setClassName("com.android.settings", "com.android.settings.Settings\$DeviceAdminSettingsActivity"),
                Intent(Settings.ACTION_SECURITY_SETTINGS))
            "battery" -> listOf(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
            else -> throw IllegalArgumentException("page must be info, notifications, overlay, install_others, usage_access, " +
                "notification_access, accessibility, device_admin or battery")
        }
        // A maker's settings may lack a page: the app's details always exist.
        val opened = (choices + details).firstOrNull { intent ->
            runCatching { app.startActivity(Intent(intent).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }.isSuccess
        }
        return JSONObject().put("ok", opened != null).put("opened", if (opened === details && page != "info") "info" else page)
    }
}
