package com.agentworkspace.mobile.embedded

import android.annotation.SuppressLint
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.os.SystemClock
import android.provider.Settings
import android.util.AtomicFile
import com.agentworkspace.mobile.UiText
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * Keeping the engine running on phones whose system freezes or cuts off apps it does not know.
 *
 * The engine runs in its own process behind a foreground notification, which stock Android leaves
 * alone. Several makers' power managers still freeze it or cut its network unless the user allows
 * the app to run in the background; a user on such a phone then sees every reply crawl or fail
 * whichever model they pick (an Honor user reported exactly that). On the ZTE test phone the
 * system's CpuFreezerManagerService logged "doNetworkLimit" for the app as the screen dozed.
 */
object BackgroundRunGuide {
    /** A pause of the engine process this long is recorded (with whether the screen was on). */
    const val PAUSE_MS = 4_000L
    private const val MAX_PAUSES = 20

    private data class Maker(val names: Set<String>, val zh: String, val en: String,
                             val stepsZh: String, val stepsEn: String, val autoStart: List<ComponentName>)

    private fun component(packageName: String, className: String) = ComponentName(packageName, className)

    private val makers = listOf(
        Maker(setOf("honor"), "荣耀", "Honor",
            "设置 → 应用和服务 → 应用启动管理 → Agent Workspace：关掉「自动管理」，打开「允许自启动」「允许关联启动」「允许后台活动」。",
            "Settings → Apps & services → App launch → Agent Workspace: turn off Manage automatically and allow auto-launch, secondary launch and run in background.",
            listOf(component("com.hihonor.systemmanager", "com.hihonor.systemmanager.startupmgr.ui.StartupNormalAppListActivity"),
                component("com.huawei.systemmanager", "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity"))),
        Maker(setOf("huawei"), "华为", "Huawei",
            "设置 → 应用和服务 → 应用启动管理 → Agent Workspace：关掉「自动管理」，打开「允许自启动」「允许关联启动」「允许后台活动」。",
            "Settings → Apps & services → App launch → Agent Workspace: turn off Manage automatically and allow auto-launch, secondary launch and run in background.",
            listOf(component("com.huawei.systemmanager", "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity"),
                component("com.huawei.systemmanager", "com.huawei.systemmanager.appcontrol.activity.StartupAppControlActivity"),
                component("com.huawei.systemmanager", "com.huawei.systemmanager.optimize.process.ProtectActivity"))),
        Maker(setOf("xiaomi", "redmi", "poco"), "小米", "Xiaomi",
            "设置 → 应用设置 → 应用管理 → Agent Workspace：打开「自启动」，「省电策略」选「无限制」。",
            "Settings → Apps → Manage apps → Agent Workspace: turn on Autostart and set Battery saver to No restrictions.",
            listOf(component("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity"))),
        Maker(setOf("oppo", "realme", "oneplus"), "OPPO / 一加 / realme", "OPPO / OnePlus / realme",
            "设置 → 应用 → 应用管理 → Agent Workspace → 耗电管理：打开「允许完全后台行为」「允许自启动」「允许关联启动」。",
            "Settings → Apps → App management → Agent Workspace → Battery usage: allow full background activity, auto launch and launch by other apps.",
            listOf(component("com.coloros.safecenter", "com.coloros.safecenter.permission.startup.StartupAppListActivity"),
                component("com.coloros.safecenter", "com.coloros.safecenter.startupapp.StartupAppListActivity"),
                component("com.oppo.safe", "com.oppo.safe.permission.startup.StartupAppListActivity"),
                component("com.oneplus.security", "com.oneplus.security.chainlaunch.view.ChainLaunchAppListActivity"))),
        Maker(setOf("vivo", "iqoo"), "vivo / iQOO", "vivo / iQOO",
            "设置 → 电池 → 后台耗电管理 → Agent Workspace：选「允许后台高耗电」；i 管家 → 应用管理 → 自启动：打开 Agent Workspace。",
            "Settings → Battery → Background power consumption → Agent Workspace: allow high background power use; i Manager → App manager → Autostart: turn on Agent Workspace.",
            listOf(component("com.vivo.permissionmanager", "com.vivo.permissionmanager.activity.BgStartUpManagerActivity"),
                component("com.iqoo.secure", "com.iqoo.secure.ui.phoneoptimize.BgStartUpManager"))),
        Maker(setOf("meizu"), "魅族", "Meizu",
            "手机管家 → 权限管理 → 后台管理 → Agent Workspace：选「允许后台运行」。",
            "Phone Manager → Permissions → Background management → Agent Workspace: allow running in the background.",
            emptyList()),
        Maker(setOf("zte", "nubia"), "中兴 / 努比亚", "ZTE / nubia",
            "设置 → 电池 → 应用耗电管理（或「后台管控」）→ Agent Workspace：选「允许后台运行」，并打开「自启动」。",
            "Settings → Battery → App power management (or Background control) → Agent Workspace: allow running in the background and auto-start.",
            emptyList()),
        Maker(setOf("samsung"), "三星", "Samsung",
            "设置 → 电池 → 后台使用限制：先看「深度休眠应用」名单，有 Agent Workspace 就移出来（在这个名单里的应用在后台完全不能运行）；再把它加到「永不休眠的应用」。",
            "Settings → Battery → Background usage limits: first check Deep sleeping apps and take Agent Workspace off that list (apps there never run in the background); then add it to Never sleeping apps.",
            emptyList()),
    )

    private fun maker(): Maker? {
        val names = setOf(Build.MANUFACTURER.lowercase(), Build.BRAND.lowercase())
        return makers.firstOrNull { maker -> maker.names.any { it in names } }
    }

    private fun exempt(context: Context) = (context.getSystemService(Context.POWER_SERVICE) as PowerManager)
        .isIgnoringBatteryOptimizations(context.packageName)

    private fun pauseFile(context: Context) = AtomicFile(File(context.filesDir, "engine-pauses.json"))

    fun pauses(context: Context): JSONArray = try {
        JSONArray(pauseFile(context).openRead().use { it.readBytes().toString(Charsets.UTF_8) })
    } catch (_: Exception) { JSONArray() }

    @Synchronized private fun recordPause(context: Context, pausedMs: Long, interactive: Boolean) {
        val previous = pauses(context)
        val kept = JSONArray()
        val start = maxOf(0, previous.length() - (MAX_PAUSES - 1))
        for (index in start until previous.length()) kept.put(previous.get(index))
        kept.put(JSONObject().put("at_ms", System.currentTimeMillis()).put("seconds", pausedMs / 1000)
            .put("screen_on", interactive))
        val file = pauseFile(context)
        val stream = try { file.startWrite() } catch (_: Exception) { return }
        try {
            stream.write(kept.toString().toByteArray(Charsets.UTF_8))
            file.finishWrite(stream)
        } catch (_: Exception) { file.failWrite(stream) }
    }

    @Volatile private var monitor: Thread? = null

    /**
     * Runs in the engine process. A frozen process stops all its threads, so a one-second sleep
     * that wakes much later (in uptime, which excludes the phone's own deep sleep) means the
     * system held the engine.
     */
    @Synchronized fun startPauseMonitor(context: Context) {
        if (monitor?.isAlive == true) return
        val app = context.applicationContext
        val power = app.getSystemService(Context.POWER_SERVICE) as PowerManager
        monitor = Thread({
            var last = SystemClock.uptimeMillis()
            var screenWasOn = power.isInteractive
            while (true) {
                try { Thread.sleep(1000) } catch (_: InterruptedException) { return@Thread }
                val now = SystemClock.uptimeMillis()
                val paused = now - last - 1000
                val screenOn = power.isInteractive
                last = now
                // Thawed as the screen came on is a screen-off pause; only on before and after counts as on.
                if (paused >= PAUSE_MS) runCatching { recordPause(app, paused, screenWasOn && screenOn) }
                screenWasOn = screenOn
            }
        }, "engine-pause-monitor").apply { isDaemon = true; start() }
    }

    /** What the app shows: the maker's own steps, whether battery optimization still applies, recent pauses. */
    fun state(context: Context): JSONObject {
        val maker = maker()
        return JSONObject()
            .put("maker", maker?.let { UiText.of(context, it.zh, it.en) } ?: Build.MANUFACTURER)
            .put("strict_maker", maker != null)
            .put("battery_optimization_exempt", exempt(context))
            .put("steps", maker?.let { UiText.of(context, it.stepsZh, it.stepsEn) } ?: JSONObject.NULL)
            .put("auto_start_page", maker?.autoStart?.any { resolves(context, it) } == true)
            .put("pauses", pauses(context))
            // The engine ended by Android or the phone maker in the last day: the chat asks for
            // background running right away instead of waiting for the user to notice.
            .put("recent_engine_kills", ProcessExits.recentSystemKills(context))
    }

    private fun resolves(context: Context, component: ComponentName) = try {
        context.packageManager.getActivityInfo(component, 0).exported
    } catch (_: Exception) { false }

    /** Android's own "allow in the background" question; the battery settings list where that is refused. */
    @SuppressLint("BatteryLife")  // Not a Play app; the engine needs it on strict phones.
    fun requestBatteryExemption(context: Context): Boolean {
        if (exempt(context)) return true
        val ask = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${context.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try { context.startActivity(ask); true } catch (_: Exception) {
            runCatching { context.startActivity(EngineRecovery.batterySettingsIntent(context)) }.isSuccess
        }
    }

    /** The maker's auto-start or app-launch page; the app's own settings page otherwise. */
    fun openAutoStart(context: Context): Boolean {
        for (component in maker()?.autoStart.orEmpty()) {
            if (!resolves(context, component)) continue
            val opened = runCatching {
                context.startActivity(Intent().setComponent(component).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }.isSuccess
            if (opened) return true
        }
        return runCatching { context.startActivity(EngineRecovery.appSettingsIntent(context)) }.isSuccess
    }
}
