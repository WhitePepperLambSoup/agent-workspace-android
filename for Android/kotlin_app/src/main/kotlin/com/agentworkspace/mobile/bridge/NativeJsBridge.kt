package com.agentworkspace.mobile.bridge

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.webkit.JavascriptInterface
import android.widget.Toast
import com.agentworkspace.mobile.embedded.MobileProviderSettings
import com.agentworkspace.mobile.embedded.TaskNotificationPublisher
import com.agentworkspace.mobile.embedded.TaskNotificationSettings
import com.agentworkspace.mobile.embedded.EngineLifecycleState
import com.agentworkspace.mobile.embedded.EngineRecovery
import com.agentworkspace.mobile.embedded.ProviderChangeCoordinator
import com.agentworkspace.mobile.embedded.ProviderSettingsChange
import com.agentworkspace.mobile.embedded.ProviderProfiles
import com.agentworkspace.mobile.automation.AndroidSystemBridge
import com.agentworkspace.mobile.entry.FloatingBallService
import com.agentworkspace.mobile.entry.QuickEntry
import com.agentworkspace.mobile.notifications.AgentNotificationListener
import com.agentworkspace.mobile.localmodels.TrainedLocalModel
import com.agentworkspace.mobile.workspace.WorkspaceStorageAccess
import com.agentworkspace.mobile.workspace.WorkspaceDocumentsAccess
import org.json.JSONObject

/**
 * 原生交互桥梁：注入至 Android WebView 的 window.AndroidBridge 中。
 * 提供移动设备专有的振动触感、系统原生分享、剪贴板交互与电量状态读取。
 */
class NativeJsBridge(
    private val context: Context,
    private val openSettingsAction: () -> Unit = {},
    private val settingsChangedAction: () -> Unit = {},
    private val requestNotificationPermissionAction: () -> Unit = {},
    private val notificationSettingsChangedAction: () -> Unit = {},
    private val requestVoiceInputAction: () -> Unit = {},
    private val restartEngineAction: () -> Unit = {},
    private val reconnectEngineAction: () -> Unit = {},
    private val exportLogsAction: (() -> Unit)? = null,
    private val backupCreateAction: ((String) -> Unit)? = null,
    private val backupRestoreAction: (() -> Unit)? = null,
    private val checkUpdatesAction: () -> Unit = {},
    private val stopEngineAction: () -> Unit = {},
    private val openNotificationSettingsAction: () -> Unit = {
        context.startActivity(TaskNotificationSettings.systemSettingsIntent(context))
    },
    private val providerChangeAction: (Boolean, () -> Unit) -> Unit = { requireLocalEngine, save ->
        ProviderSettingsChange.apply(context, requireLocalEngine, save)
    },
    private val importLocalModelAction: (String) -> Unit = {},
    private val workspaceFileActionHandler: (String) -> String = {
        JSONObject().put("ok", false).put("error", "The workspace file action is unavailable").toString()
    },
    private val workspaceFolderPicker: () -> String = {
        JSONObject().put("ok", false).put("error", "The workspace folder picker is unavailable").toString()
    },
    private val workspaceStorageAccessAction: () -> Unit = {},
    private val workspaceBrowserAction: (String) -> String = { WorkspaceDocumentsAccess.open(context, it) },
    private val shareInboxReader: () -> String = { unavailableShareInbox() },
    private val shareInboxConfirmation: (String) -> String = { unavailableShareInbox() },
    private val shareInboxDiscard: (String) -> String = { unavailableShareInbox() },
    private val shareInboxAcknowledgement: (String) -> String = { unavailableShareInbox() },
    private val shareInboxFilePicker: () -> String = { unavailableShareInbox() },
    private val shareInboxCameraCapture: () -> String = { unavailableShareInbox() },
    private val systemBarsAction: (Boolean, Int) -> Unit = { _, _ -> },
    private val requestTileAction: (() -> String)? = null,
    private val keepScreenOnAction: (Boolean) -> Unit = {},
) {
    /** The web UI's language choice ("auto", "zh" or "en") for native dialogs, notifications and toasts. */
    @JavascriptInterface
    fun setUiLanguage(value: String) {
        com.agentworkspace.mobile.UiText.setPreference(context, value)
        QuickEntry.publishShortcuts(context)
    }

    /** Floating ball and quick settings tile state for Settings → Global entry. */
    @JavascriptInterface
    fun getGlobalEntry(): String = JSONObject()
        .put("ok", true)
        .put("floating_ball", FloatingBallService.isEnabled(context))
        .put("overlay_permission", FloatingBallService.canDraw(context))
        .put("tile_request", requestTileAction != null && Build.VERSION.SDK_INT >= 33)
        .toString()

    /** Turning the ball on without "display over other apps" opens that system setting first. */
    @JavascriptInterface
    fun setFloatingBall(enabled: Boolean): String {
        val needsPermission = FloatingBallService.setEnabled(context, enabled)
        if (needsPermission) Handler(Looper.getMainLooper()).post {
            runCatching {
                context.startActivity(Intent(android.provider.Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:${context.packageName}")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }.onFailure {
                showToast(com.agentworkspace.mobile.UiText.of(context, "无法打开悬浮窗权限设置", "Could not open the overlay permission setting"))
            }
        }
        return JSONObject().put("ok", true).put("permission_required", needsPermission).toString()
    }

    /** Whether the user granted notification access (needed for notification rules). */
    @JavascriptInterface
    fun getNotificationAccess(): String = JSONObject().put("ok", true)
        .put("granted", AgentNotificationListener.accessGranted(context)).toString()

    @JavascriptInterface
    fun openNotificationAccessSettings() {
        Handler(Looper.getMainLooper()).post {
            runCatching { context.startActivity(AgentNotificationListener.accessSettingsIntent(context)) }
                .recoverCatching {
                    context.startActivity(Intent(android.provider.Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                }
        }
    }

    /** Apps on the home screen, to pick which app's notifications a rule follows. */
    @JavascriptInterface
    fun listApps(): String {
        val manager = context.packageManager
        val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val apps = org.json.JSONArray()
        runCatching { manager.queryIntentActivities(launcher, 0) }.getOrDefault(emptyList())
            .map { it.activityInfo.packageName to it.loadLabel(manager).toString() }
            .filter { (name, _) -> name != context.packageName }
            .distinctBy { it.first }
            .sortedWith(compareBy(java.text.Collator.getInstance()) { it.second })
            .forEach { (name, label) -> apps.put(JSONObject().put("package", name).put("label", label.take(80))) }
        return JSONObject().put("ok", true).put("apps", apps).toString()
    }

    /** Android 13+: ask the system to add the "Ask Agent" tile to quick settings. */
    @JavascriptInterface
    fun requestQuickSettingsTile(): String = requestTileAction?.invoke()
        ?: JSONObject().put("ok", false).put("error", "unsupported").toString()

    /** Lets the page match the status and navigation bar areas to its light or dark surface color. */
    @JavascriptInterface
    fun setSystemBarsAppearance(dark: Boolean, color: String) {
        if (!SYSTEM_BAR_COLOR.matches(color)) return
        val parsed = android.graphics.Color.parseColor(color)
        Handler(Looper.getMainLooper()).post { systemBarsAction(dark, parsed) }
    }

    /**
     * Keeps the screen on while a task runs on the phone's own model. Some phones (ZTE's
     * DefendManagerService) kill a large engine process once its app is no longer on a lit
     * screen, which ended long local tasks when the screen timed out. Only applies while the
     * conversation window is visible.
     */
    @JavascriptInterface
    fun setKeepScreenOn(enabled: Boolean) {
        Handler(Looper.getMainLooper()).post { keepScreenOnAction(enabled) }
    }

    @JavascriptInterface
    fun getShareInbox(): String = shareInboxReader()

    @JavascriptInterface
    fun confirmShareInbox(requestJson: String): String = shareInboxConfirmation(requestJson)

    @JavascriptInterface
    fun discardShareInbox(requestJson: String): String = shareInboxDiscard(requestJson)

    @JavascriptInterface
    fun ackShareInbox(requestJson: String): String = shareInboxAcknowledgement(requestJson)

    @JavascriptInterface
    fun pickShareInboxFiles(): String = shareInboxFilePicker()

    /** Take a photo with the camera app and add it to the share inbox. */
    @JavascriptInterface
    fun captureShareInboxPhoto(): String = shareInboxCameraCapture()

    @JavascriptInterface
    fun workspaceFileAction(requestJson: String): String = workspaceFileActionHandler(requestJson)

    @JavascriptInterface
    fun pickWorkspaceFolder(): String = workspaceFolderPicker()

    @JavascriptInterface
    fun openWorkspaceBrowser(workspaceId: String): String = workspaceBrowserAction(workspaceId)

    @JavascriptInterface
    fun recommendedWorkspaceFolder(name: String): String = WorkspaceDocumentsAccess.recommendedFolder(name)

    @JavascriptInterface
    fun refreshWorkspaceDocuments() = WorkspaceDocumentsAccess.refresh(context)

    @JavascriptInterface
    fun workspaceStorageStatus(): String = WorkspaceStorageAccess.status(context)

    @JavascriptInterface
    fun requestWorkspaceStorageAccess() {
        Handler(Looper.getMainLooper()).post { workspaceStorageAccessAction() }
    }

    @JavascriptInterface
    fun ensureEngineRunning() { EngineRecovery.enqueue(context) }

    @JavascriptInterface
    fun getEngineStatus(): String = EngineLifecycleState(context).statusJson()

    @JavascriptInterface
    fun getBackgroundStatus(): String = EngineRecovery.status(context)

    /** Build the diagnostics file off the UI thread, then open the share sheet. Returns at once. */
    @JavascriptInterface
    fun shareDiagnostics(): String {
        Thread {
            val result = runCatching { com.agentworkspace.mobile.embedded.DiagnosticReport.write(context) }
            Handler(Looper.getMainLooper()).post {
                result.onSuccess { report ->
                    runCatching { com.agentworkspace.mobile.embedded.DiagnosticReport.share(context, report) }
                        .onFailure { Toast.makeText(context, com.agentworkspace.mobile.UiText.of(context, "无法打开分享面板", "Could not open the share sheet"), Toast.LENGTH_SHORT).show() }
                }.onFailure { Toast.makeText(context, com.agentworkspace.mobile.UiText.of(context, "诊断日志生成失败", "Could not create the diagnostics file"), Toast.LENGTH_SHORT).show() }
            }
        }.apply { name = "agent-diagnostics"; isDaemon = true }.start()
        return "{\"ok\":true}"
    }

    /** Share, save, or report the diagnostics on GitHub (native chooser); falls back to sharing. */
    @JavascriptInterface
    fun exportDiagnostics(): String {
        val action = exportLogsAction ?: return shareDiagnostics()
        Handler(Looper.getMainLooper()).post { action() }
        return "{\"ok\":true}"
    }

    /** Back up conversations, workspace and settings; progress arrives as `agent-backup` events. */
    @JavascriptInterface
    fun createBackup(webSettings: String): String {
        val action = backupCreateAction ?: return JSONObject().put("ok", false).put("error", "备份不可用").toString()
        if (webSettings.length > 4 * 1024 * 1024) return JSONObject().put("ok", false).put("error", "界面设置太大").toString()
        Handler(Looper.getMainLooper()).post { action(webSettings) }
        return JSONObject().put("ok", true).toString()
    }

    /** Pick a backup file and restore it (the engine restarts to finish). */
    @JavascriptInterface
    fun restoreBackup(): String {
        val action = backupRestoreAction ?: return JSONObject().put("ok", false).put("error", "恢复不可用").toString()
        Handler(Looper.getMainLooper()).post { action() }
        return JSONObject().put("ok", true).toString()
    }

    /** compat.js: the page found this WebView too old for the console. */
    @JavascriptInterface
    fun openWebViewUpdate() {
        Handler(Looper.getMainLooper()).post { com.agentworkspace.mobile.WebViewSupport.openUpdate(context) }
    }

    @JavascriptInterface
    fun getUpdateSettings(): String = com.agentworkspace.mobile.update.UpdateChecker.statusJson(context)

    @JavascriptInterface
    fun setAutoUpdateCheck(enabled: Boolean) = com.agentworkspace.mobile.update.UpdateChecker.setAutoCheck(context, enabled)

    @JavascriptInterface
    fun checkForUpdates() { Handler(Looper.getMainLooper()).post { checkUpdatesAction() } }

    @JavascriptInterface
    fun openBatteryOptimizationSettings() {
        Handler(Looper.getMainLooper()).post {
            runCatching { context.startActivity(EngineRecovery.batterySettingsIntent(context)) }
                .onFailure { runCatching { context.startActivity(EngineRecovery.appSettingsIntent(context)) } }
        }
    }

    @JavascriptInterface
    fun openAppSettings() {
        Handler(Looper.getMainLooper()).post {
            runCatching { context.startActivity(EngineRecovery.appSettingsIntent(context)) }
        }
    }

    @JavascriptInterface
    fun openAppBackgroundSettings() = openAppSettings()

    private fun changeProvider(requireLocalEngine: Boolean, save: () -> Unit): String = try {
        providerChangeAction(requireLocalEngine, save)
        Handler(Looper.getMainLooper()).post { settingsChangedAction() }
        JSONObject().put("ok", true).toString()
    } catch (error: Exception) {
        val recovery = error as? ProviderChangeCoordinator.Failure
        if (recovery?.restartRequested == true) Handler(Looper.getMainLooper()).post { settingsChangedAction() }
        JSONObject().put("ok", false)
            .put("restart_requested", recovery?.restartRequested == true)
            .put("settings_saved", recovery?.settingsSaved == true)
            .put("error", if (error is IllegalArgumentException || error is IllegalStateException)
                error.message ?: "无法保存模型设置" else "无法保存模型设置").toString()
    }

    @JavascriptInterface
    fun selectLocalModel(modelId: String): String {
        if (modelId !in MobileProviderSettings.embeddedQwenModels) {
            return JSONObject().put("ok", false).put("error", "未知本机模型").toString()
        }
        return changeProvider(true) { MobileProviderSettings.selectLocalModel(context, modelId) }
    }

    @JavascriptInterface
    fun importLocalModel(modelId: String): String {
        if (TrainedLocalModel.spec?.id != modelId) {
            return JSONObject().put("ok", false).put("error", "此训练模型未包含在当前版本中").toString()
        }
        Handler(Looper.getMainLooper()).post { importLocalModelAction(modelId) }
        return JSONObject().put("ok", true).toString()
    }

    @JavascriptInterface
    fun restorePreviousProvider(): String = changeProvider(false) {
        MobileProviderSettings.restorePreviousProvider(context)
    }

    @JavascriptInterface
    fun requestVoiceInput() { Handler(Looper.getMainLooper()).post { requestVoiceInputAction() } }

    @JavascriptInterface
    fun restartEngine() { Handler(Looper.getMainLooper()).post { restartEngineAction() } }

    /** Re-establish the page's link to the engine: start or revive it if needed, then reload with its current token. */
    @JavascriptInterface
    fun reconnectEngine() { Handler(Looper.getMainLooper()).post { reconnectEngineAction() } }

    @JavascriptInterface
    fun stopEngine() { Handler(Looper.getMainLooper()).post { stopEngineAction() } }

    @JavascriptInterface
    fun openAccessibilitySettings() { Handler(Looper.getMainLooper()).post { AndroidSystemBridge.openAccessibilitySettings(context) } }

    @JavascriptInterface
    fun setSystemPaused(paused: Boolean): String = AndroidSystemBridge.setPaused(context, paused)

    @JavascriptInterface
    fun requestSystemTakeover(): String = AndroidSystemBridge.requestTakeover(context)

    @JavascriptInterface
    fun getNotificationSettings(): String = TaskNotificationSettings(context).toJson(context)

    @JavascriptInterface
    fun setTaskNotificationsEnabled(enabled: Boolean) {
        TaskNotificationSettings(context).setEnabled(enabled)
        if (!enabled) TaskNotificationPublisher(context).cancelAllTasks()
        Handler(Looper.getMainLooper()).post {
            if (enabled) requestNotificationPermissionAction()
            notificationSettingsChangedAction()
        }
    }

    @JavascriptInterface
    fun openNotificationSettings() {
        Handler(Looper.getMainLooper()).post { openNotificationSettingsAction() }
    }

    @JavascriptInterface
    fun getProviderSettings(): String = MobileProviderSettings.load(context).toPublicJson()

    private fun localModelControl(method: String, settings: String = "{}"): String = try {
        require(settings.length <= 4096)
        context.contentResolver.call(Uri.parse("content://${context.packageName}.local-model-control"),
            method, null, Bundle().apply { putString("settings", settings) })?.getString("result")
            ?: JSONObject().put("ok", false).put("error", "本机引擎尚未就绪").toString()
    } catch (failure: Exception) {
        JSONObject().put("ok", false).put("error", failure.message ?: "本机设备操作失败").toString()
    }

    @JavascriptInterface fun getLocalModelDeviceStatus(settings: String): String = localModelControl("status", settings)
    @JavascriptInterface fun startLocalModelBenchmark(settings: String): String = localModelControl("start", settings)
    @JavascriptInterface fun cancelLocalModelBenchmark(): String = localModelControl("cancel")

    @JavascriptInterface
    fun applyRuntimeSettings(settingsJson: String): String {
        // Model, reasoning effort and context summary apply to the running engine; other settings
        // (execution mode, on-device model tuning) still restart it.
        val hot = runCatching {
            val update = JSONObject(settingsJson)
            val current = MobileProviderSettings.load(context)
            val keys = update.keys().asSequence().toSet()
            if (keys.isEmpty() || !setOf("model", "reasoning_effort", "autonomy", "context_summary_enabled").containsAll(keys) ||
                (update.has("autonomy") && update.optString("autonomy") != current.autonomy)) return@runCatching null
            val model = update.optString("model", current.model).trim()
            if (model.isEmpty() || model.length > 256) return@runCatching null
            val summary = if (update.has("context_summary_enabled")) update.getBoolean("context_summary_enabled") else null
            ProviderSettingsChange.applyWithoutRestart(context, current.protocol, current.baseUrl, model,
                update.optString("reasoning_effort", current.reasoningEffort), summary)
        }
        hot.exceptionOrNull()?.let { error ->
            return JSONObject().put("ok", false).put("error", error.message ?: "无法保存模型设置").toString()
        }
        if (hot.getOrNull() == true) return JSONObject().put("ok", true).put("restarting", false).toString()
        return changeProvider(false) { MobileProviderSettings.applyRuntimeSettings(context, settingsJson) }
    }

    @JavascriptInterface
    fun getProviderProfiles(): String = runCatching { ProviderProfiles.snapshot(context) }
        .getOrElse { JSONObject().put("ok", false).put("error", it.message ?: "无法读取模型配置").toString() }

    @JavascriptInterface
    fun saveProviderProfile(name: String): String = runCatching { ProviderProfiles.saveCurrent(context, name) }
        .getOrElse { JSONObject().put("ok", false).put("error", it.message ?: "无法保存模型配置").toString() }

    @JavascriptInterface
    fun deleteProviderProfile(id: String): String = runCatching { ProviderProfiles.delete(context, id) }
        .getOrElse { JSONObject().put("ok", false).put("error", it.message ?: "无法删除模型配置").toString() }

    /** Switch to a saved profile: in place for cloud providers, through a restart for the on-device model. */
    @JavascriptInterface
    fun switchProviderProfile(id: String): String {
        val profile = runCatching { ProviderProfiles.get(context, id) }.getOrElse {
            return JSONObject().put("ok", false).put("error", it.message ?: "未知模型配置").toString()
        }
        val protocol = profile.getString("protocol")
        val baseUrl = profile.getString("base_url")
        val model = profile.getString("model")
        val effort = profile.optString("reasoning_effort", "auto")
        val local = baseUrl.trimEnd('/') == MobileProviderSettings.EMBEDDED_QWEN_BASE_URL
        if (!local) {
            val hot = runCatching { ProviderSettingsChange.applyWithoutRestart(context, protocol, baseUrl, model, effort) }
            hot.exceptionOrNull()?.let { error ->
                return JSONObject().put("ok", false).put("error", error.message ?: "无法切换模型").toString()
            }
            if (hot.getOrNull() == true) return JSONObject().put("ok", true).put("restarting", false).toString()
        }
        return changeProvider(local) {
            if (local) MobileProviderSettings.selectLocalModel(context, model)
            else MobileProviderSettings.save(context, protocol, baseUrl, model, null, false,
                effort.takeIf { it in MobileProviderSettings.reasoningEfforts(protocol, baseUrl, model) } ?: "auto")
        }
    }

    @JavascriptInterface
    fun openSettings() {
        Handler(Looper.getMainLooper()).post { openSettingsAction() }
    }

    @JavascriptInterface
    fun vibrate(milliseconds: Long) {
        val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            (context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as android.os.VibratorManager).defaultVibrator
        } else {
            @Suppress("DEPRECATION") (context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator)
        }
        // Pages ask for short taps only; never let one hold the motor on.
        vibrator.vibrate(VibrationEffect.createOneShot(milliseconds.coerceIn(1L, 200L), VibrationEffect.DEFAULT_AMPLITUDE))
    }

    @JavascriptInterface
    fun showToast(message: String) {
        Handler(Looper.getMainLooper()).post {
            Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
        }
    }

    @JavascriptInterface
    fun copyToClipboard(text: String) {
        val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        cm.setPrimaryClip(ClipData.newPlainText("AgentWorkspace", text))
        showToast(com.agentworkspace.mobile.UiText.of(context, "已复制到剪贴板", "Copied to clipboard"))
    }

    @JavascriptInterface
    fun shareText(title: String, content: String) {
        val shareIntent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, title)
            putExtra(Intent.EXTRA_TEXT, content)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        context.startActivity(Intent.createChooser(shareIntent, title).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        })
    }

    @JavascriptInterface
    fun openExternal(url: String) {
        try {
            val uri = Uri.parse(url)
            val scheme = uri.scheme?.lowercase()
            if (scheme != "http" && scheme != "https") {
                showToast(com.agentworkspace.mobile.UiText.of(context, "拒绝打开不受支持的链接协议", "This link type cannot be opened"))
                return
            }
            val intent = Intent(Intent.ACTION_VIEW, uri).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            showToast(com.agentworkspace.mobile.UiText.of(context, "无法打开外部链接: ${e.message}", "Could not open the link: ${e.message}"))
        }
    }

    @JavascriptInterface
    fun getBatteryLevel(): Int {
        val bm = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        return bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
    }
}

private val SYSTEM_BAR_COLOR = Regex("^#[0-9a-fA-F]{6}$")

private fun unavailableShareInbox(): String =
    JSONObject().put("ok", false).put("error", "请从工作区页面打开分享收件箱").toString()
