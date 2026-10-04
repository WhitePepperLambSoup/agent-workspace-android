package com.agentworkspace.mobile

import android.annotation.SuppressLint
import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.ActivityNotFoundException
import android.content.res.Configuration
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.text.Editable
import android.text.TextWatcher
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.webkit.*
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import android.widget.ArrayAdapter
import android.widget.AutoCompleteTextView
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import com.agentworkspace.mobile.bridge.NativeJsBridge
import com.agentworkspace.mobile.embedded.TermuxBootstrap
import com.agentworkspace.mobile.embedded.TermuxDaemonService
import com.agentworkspace.mobile.embedded.MobileProviderSettings
import com.agentworkspace.mobile.embedded.ProviderChangeCoordinator
import com.agentworkspace.mobile.embedded.ProviderSettingsChange
import com.agentworkspace.mobile.embedded.TaskNotificationPublisher
import com.agentworkspace.mobile.embedded.TaskNotificationSettings
import com.agentworkspace.mobile.voice.MobileVoiceInput
import com.agentworkspace.mobile.localmodels.LocalModelArtifactInstaller
import com.agentworkspace.mobile.localmodels.TrainedLocalModel
import com.agentworkspace.mobile.workspace.WorkspaceFileActionController
import com.agentworkspace.mobile.workspace.WorkspaceStorageAccess
import com.agentworkspace.mobile.sharing.ShareInboxController
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import android.content.pm.PackageManager
import kotlinx.coroutines.*
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URI
import java.util.ArrayDeque
import java.util.UUID
import kotlin.math.max
import kotlin.math.roundToInt

/**
 * 核心 Activity：全屏 Chromium WebView 宿主，作为 Agent Workspace 的主交互控制台。
 * 支持系统软键盘自动调整、原生文件选择器 (onShowFileChooser) 与 Logcat 诊断。
 */
class WebUiActivity : ComponentActivity() {

    companion object {
        private const val BASE_URL = "http://127.0.0.1:8080"
        private val IDENTITY_CONTEXT = "agent-workspace-mobile-identity-v1\n".toByteArray(Charsets.US_ASCII)
        /** Consecutive failed identity checks (about 0.5–1.5 s each) before the engine process is replaced. */
        private const val ENGINE_UNRESPONSIVE_ATTEMPTS = 16
        /** Waits (0.5 s each) for a start-up to publish its token before the engine process is replaced. */
        private const val ENGINE_MISSING_TOKEN_ATTEMPTS = 100
    }

    /** The token the loaded console page uses; a different serve.token means the engine was restarted. */
    private var loadedEngineToken: String? = null
    private var resumeCheckJob: Job? = null

    private lateinit var rootLayout: FrameLayout
    private var pageDark = false
    private lateinit var webView: WebView
    private lateinit var loadingContainer: FrameLayout
    private lateinit var statusText: TextView
    private lateinit var retryButton: Button
    private lateinit var settingsButton: Button
    private var fileUploadCallback: ValueCallback<Array<Uri>>? = null
    private val activityScope = CoroutineScope(Dispatchers.Main + Job())
    private var initializationJob: Job? = null
    private val sharedTexts = ArrayDeque<String>()
    private val shareHandler = Handler(Looper.getMainLooper())
    private var deliveringShare = false
    private var pendingSessionId: String? = null
    private var deliveringSession = false
    private var notificationPermissionInFlight = false
    private var voicePending = false
    private var trainedModelImportPending = false
    private lateinit var workspaceFileActions: WorkspaceFileActionController
    @Volatile private var trustedWorkspacePage = false
    private val workspaceFileResults = ArrayDeque<JSONObject>()
    private var savedWorkspaceFilePicker = false
    private val workspaceFolderLock = Any()
    @Volatile private var workspaceFolderPicking = false
    private var workspaceFolderAwaitingStorage = false
    @Volatile private var workspaceStoragePermissionInFlight = false
    private val workspaceFolderResults = ArrayDeque<JSONObject>()
    private var pendingWorkspaceFolderUri: String? = null
    private lateinit var shareInbox: ShareInboxController
    private val shareInboxListener: () -> Unit = { dispatchShareInboxChanged() }
    private val shareInboxPickerLock = Any()
    @Volatile private var shareInboxPickerPending = false
    private var incomingShareBatchId = UUID.randomUUID().toString()

    private val shareInboxFilePicker = registerForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        synchronized(shareInboxPickerLock) { shareInboxPickerPending = false }
        uris.forEach { uri -> runCatching { contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) } }
        if (uris.isNotEmpty()) shareInbox.captureFiles(uris)
        else dispatchShareInboxChanged()
    }

    private fun shareInboxAccess(action: () -> String): String =
        if (!trustedWorkspacePage || isDestroyed || isFinishing) ShareInboxController.failure("请从工作区页面打开分享收件箱")
        else action()

    private fun queueShareInboxFilePicker(): String = shareInboxAccess {
        synchronized(shareInboxPickerLock) {
            if (shareInboxPickerPending) return@shareInboxAccess ShareInboxController.failure("请先完成当前文件选择")
            shareInboxPickerPending = true
        }
        shareHandler.post {
            if (!trustedWorkspacePage || isDestroyed || isFinishing) {
                synchronized(shareInboxPickerLock) { shareInboxPickerPending = false }
            } else try { shareInboxFilePicker.launch(arrayOf("*/*")) }
            catch (_: Exception) {
                synchronized(shareInboxPickerLock) { shareInboxPickerPending = false }
                android.widget.Toast.makeText(this, UiText.of(this, "无法打开系统文件选择器", "Could not open the system file picker"), android.widget.Toast.LENGTH_SHORT).show()
            }
        }
        JSONObject().put("ok", true).put("queued", true).toString()
    }

    private fun dispatchShareInboxChanged() {
        if (!::webView.isInitialized || isDestroyed || !trustedWorkspacePage ||
            !isTrustedConsoleUrl(webView.url ?: return)) return
        webView.evaluateJavascript("window.dispatchEvent(new Event('agent-share-inbox-changed'));", null)
    }

    private val workspaceFolderPicker = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri == null) {
            completeWorkspaceFolderSelection(JSONObject().put("path", "").put("cancelled", true))
        } else resolveWorkspaceFolder(uri)
    }

    private fun resolveWorkspaceFolder(uri: Uri) {
        pendingWorkspaceFolderUri = uri.toString()
        activityScope.launch {
            val result = runCatching {
                withContext(Dispatchers.IO) {
                    val directory = WorkspaceStorageAccess.resolveFolder(this@WebUiActivity, uri)
                    runCatching { contentResolver.takePersistableUriPermission(uri,
                        Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION) }
                    directory.path
                }
            }.onFailure { if (it is CancellationException) throw it }.fold(
                onSuccess = { JSONObject().put("path", it) },
                onFailure = { JSONObject().put("path", "").put("error", if (it is IllegalArgumentException)
                    it.message ?: "无法使用所选文件夹" else "无法访问所选文件夹，请检查存储权限") },
            )
            completeWorkspaceFolderSelection(result)
        }
    }

    private val workspaceStorageSettingsLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        onWorkspaceStorageAccessResult()
    }

    private val workspaceStoragePermissionLauncher = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        onWorkspaceStorageAccessResult()
    }

    private fun queueWorkspaceFolderPicker(): String {
        synchronized(workspaceFolderLock) {
            if (!trustedWorkspacePage || isDestroyed || isFinishing) {
                return JSONObject().put("ok", false).put("error", "请从工作区页面选择文件夹").toString()
            }
            if (workspaceFolderPicking || workspaceStoragePermissionInFlight) {
                return JSONObject().put("ok", false).put("error", "请先完成当前文件夹选择或存储授权").toString()
            }
            workspaceFolderPicking = true
        }
        Handler(Looper.getMainLooper()).post {
            if (!trustedWorkspacePage || isDestroyed || isFinishing) {
                completeWorkspaceFolderSelection(JSONObject().put("path", "").put("error", "工作区页面已关闭"))
            } else if (!WorkspaceStorageAccess.granted(this)) {
                workspaceFolderAwaitingStorage = true
                requestWorkspaceStorageAccess()
            } else launchWorkspaceFolderPicker()
        }
        return JSONObject().put("ok", true).toString()
    }

    private fun launchWorkspaceFolderPicker() {
        try { workspaceFolderPicker.launch(null) }
        catch (_: Exception) {
            completeWorkspaceFolderSelection(JSONObject().put("path", "").put("error", "无法打开系统文件夹选择器"))
        }
    }

    private fun requestWorkspaceStorageAccess() {
        if (!trustedWorkspacePage || isDestroyed || isFinishing || workspaceStoragePermissionInFlight) return
        if (WorkspaceStorageAccess.granted(this)) {
            onWorkspaceStorageAccessResult()
            return
        }
        workspaceStoragePermissionInFlight = true
        try {
            if (Build.VERSION.SDK_INT >= 30) {
                try { workspaceStorageSettingsLauncher.launch(WorkspaceStorageAccess.settingsIntent(this)) }
                catch (_: ActivityNotFoundException) {
                    workspaceStorageSettingsLauncher.launch(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
                }
            } else workspaceStoragePermissionLauncher.launch(WorkspaceStorageAccess.legacyPermissions)
        } catch (_: Exception) {
            workspaceStoragePermissionInFlight = false
            if (workspaceFolderAwaitingStorage) {
                workspaceFolderAwaitingStorage = false
                completeWorkspaceFolderSelection(JSONObject().put("path", "").put("error", "无法打开系统存储授权，请在应用设置中授予文件访问权限"))
            } else NativeJsBridge(this).showToast(UiText.of(this, "无法打开系统存储授权，请在应用设置中授予文件访问权限", "Could not open storage permission; grant file access in app settings"))
        }
    }

    private fun onWorkspaceStorageAccessResult() {
        workspaceStoragePermissionInFlight = false
        dispatchWorkspaceStorageChanged()
        if (!workspaceFolderAwaitingStorage) return
        workspaceFolderAwaitingStorage = false
        if (WorkspaceStorageAccess.granted(this)) launchWorkspaceFolderPicker()
        else completeWorkspaceFolderSelection(JSONObject().put("path", "").put("error", "未授予公共文件夹访问权限；可改用应用内工作区"))
    }

    private fun completeWorkspaceFolderSelection(result: JSONObject) {
        synchronized(workspaceFolderLock) { workspaceFolderPicking = false }
        workspaceFolderAwaitingStorage = false
        pendingWorkspaceFolderUri = null
        if (isDestroyed) return
        if (workspaceFolderResults.size >= 4) workspaceFolderResults.removeFirst()
        workspaceFolderResults.addLast(result)
        deliverWorkspaceFolderResults()
    }

    private fun deliverWorkspaceFolderResults() {
        if (!::webView.isInitialized || isDestroyed || !trustedWorkspacePage ||
            !isTrustedConsoleUrl(webView.url ?: return)) return
        while (workspaceFolderResults.isNotEmpty()) {
            val result = workspaceFolderResults.removeFirst()
            webView.evaluateJavascript("window.dispatchEvent(new CustomEvent('agent-workspace-folder-selected'," +
                "{detail:JSON.parse(${JSONObject.quote(result.toString())})}));", null)
        }
    }

    private fun dispatchWorkspaceStorageChanged() {
        if (!::webView.isInitialized || isDestroyed || !trustedWorkspacePage ||
            !isTrustedConsoleUrl(webView.url ?: return)) return
        webView.evaluateJavascript("window.dispatchEvent(new Event('agent-workspace-storage-changed'));", null)
    }

    private val workspaceSaveLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (::workspaceFileActions.isInitialized) workspaceFileActions.onSaveResult(
            if (result.resultCode == Activity.RESULT_OK) result.data?.data else null)
    }

    private val workspaceShareLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        if (::workspaceFileActions.isInitialized) workspaceFileActions.onShareResult()
    }

    private fun notifyWorkspaceFileAction(result: JSONObject) {
        if (isDestroyed) return
        if (workspaceFileResults.size >= 8) workspaceFileResults.removeFirst()
        workspaceFileResults.addLast(result)
        deliverWorkspaceFileResults()
    }

    private fun deliverWorkspaceFileResults() {
        if (!::webView.isInitialized || isDestroyed || !isTrustedConsoleUrl(webView.url ?: return)) return
        if (!trustedWorkspacePage) return
        while (workspaceFileResults.isNotEmpty()) {
            val result = workspaceFileResults.removeFirst()
            webView.evaluateJavascript(
                "window.dispatchEvent(new CustomEvent('agent-workspace-file-action',{detail:JSON.parse(${JSONObject.quote(result.toString())})}));", null)
        }
    }

    private val trainedModelPicker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri == null) {
            trainedModelImportPending = false
            notifyModelImport(JSONObject().put("ok", false).put("cancelled", true).put("error", "已取消导入"))
        } else activityScope.launch {
            notifyModelImport(JSONObject().put("ok", false).put("cancelled", true).put("error", "正在导入并校验模型文件…"))
            val outcome = runCatching {
                withContext(Dispatchers.IO) {
                    val spec = TrainedLocalModel.spec ?: error("此版本没有训练模型安装记录")
                    val files = filesDir.canonicalFile
                    val root = File(files, "agent-data/local-models")
                    require(root.canonicalFile == root && (root.isDirectory || root.mkdirs())) { "本地模型目录不可用" }
                    contentResolver.openInputStream(uri)?.use { LocalModelArtifactInstaller.install(root, spec, it) }
                        ?: error("无法读取模型文件")
                }
            }
            trainedModelImportPending = false
            notifyModelImport(outcome.fold(
                onSuccess = { JSONObject().put("ok", true).put("model_id", TrainedLocalModel.ID) },
                onFailure = { JSONObject().put("ok", false).put("error", it.message ?: "模型导入失败") },
            ))
        }
    }

    private fun requestModelImport(modelId: String) {
        if (modelId != TrainedLocalModel.spec?.id || trainedModelImportPending) {
            notifyModelImport(JSONObject().put("ok", false).put("error", "请等待当前导入完成"))
            return
        }
        trainedModelImportPending = true
        try { trainedModelPicker.launch(arrayOf("application/octet-stream", "*/*")) }
        catch (_: Exception) {
            trainedModelImportPending = false
            notifyModelImport(JSONObject().put("ok", false).put("error", "无法打开系统文件选择器"))
        }
    }

    private fun notifyModelImport(result: JSONObject) {
        if (!::webView.isInitialized) return
        webView.evaluateJavascript(
            "window.dispatchEvent(new CustomEvent('agent-local-model-imported',{detail:JSON.parse(${JSONObject.quote(result.toString())})}));", null)
    }

    private val voiceInputLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        MobileVoiceInput.draftFromResult(result.resultCode, result.data)?.let {
            sharedTexts.addLast(it)
            deliverSharedText()
        }
    }

    private val notificationPermissionLauncher = registerForActivityResult(ActivityResultContracts.RequestPermission()) {
        notificationPermissionInFlight = false
        dispatchNotificationSettingsChanged()
    }

    // 注册原生文件选择器启动协议
    private val filePickerLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val intent = result.data
            val results: Array<Uri>? = when {
                intent?.clipData != null -> {
                    val clip = intent.clipData!!
                    Array(clip.itemCount) { i -> clip.getItemAt(i).uri }
                }
                intent?.data != null -> arrayOf(intent.data!!)
                else -> null
            }
            fileUploadCallback?.onReceiveValue(results)
        } else {
            fileUploadCallback?.onReceiveValue(null)
        }
        fileUploadCallback = null
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        shareInbox = ShareInboxController.get(this)
        shareInbox.addListener(shareInboxListener)
        incomingShareBatchId = savedInstanceState?.getString("incoming-share-batch-id") ?: UUID.randomUUID().toString()
        shareInboxPickerPending = savedInstanceState?.getBoolean("share-inbox-picker-pending", false) ?: false
        workspaceFolderPicking = savedInstanceState?.getBoolean("workspace-folder-picking", false) ?: false
        workspaceFolderAwaitingStorage = savedInstanceState?.getBoolean("workspace-folder-awaiting-storage", false) ?: false
        workspaceStoragePermissionInFlight = savedInstanceState?.getBoolean("workspace-storage-permission-in-flight", false) ?: false
        savedInstanceState?.getStringArrayList("workspace-folder-results")?.forEach {
            runCatching { JSONObject(it) }.getOrNull()?.let(workspaceFolderResults::addLast)
        }
        savedInstanceState?.getString("workspace-folder-uri")?.let { resolveWorkspaceFolder(Uri.parse(it)) }
        WindowCompat.setDecorFitsSystemWindows(window, false)
        workspaceFileActions = WorkspaceFileActionController(this, activityScope,
            trustedPage = { trustedWorkspacePage && !isDestroyed && !isFinishing },
            notifyResult = { notifyWorkspaceFileAction(it) },
            launchShare = { workspaceShareLauncher.launch(it) },
            launchSave = { workspaceSaveLauncher.launch(it) },
            launchOpen = { startActivity(it) },
        ).apply { restoreSave(savedInstanceState?.getBundle("workspace-file-save")) }

        // Until the page reports its theme, follow the system setting so startup does not flash.
        val startupDark = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        val startupColor = Color.parseColor(if (startupDark) "#161C1B" else "#FFFFFF")
        rootLayout = FrameLayout(this).apply {
            setBackgroundColor(startupColor)
        }
        ViewCompat.setOnApplyWindowInsetsListener(rootLayout) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            val keyboard = insets.getInsets(WindowInsetsCompat.Type.ime())
            view.setPadding(bars.left, bars.top, bars.right, max(bars.bottom, keyboard.bottom))
            WindowInsetsCompat.CONSUMED
        }

        // Debug builds only: lets contributors inspect the console page from chrome://inspect.
        if (applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE != 0) {
            WebView.setWebContentsDebuggingEnabled(true)
        }
        webView = WebView(this).apply {
            layoutParams = FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            visibility = View.INVISIBLE
            setBackgroundColor(startupColor)

            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                useWideViewPort = true
                loadWithOverviewMode = true
                // The console is an app screen, not a document: no pinch zoom (text size is a setting).
                setSupportZoom(false)
                builtInZoomControls = false
                displayZoomControls = false
                allowFileAccess = false
                allowContentAccess = true
                textZoom = (resources.configuration.fontScale * 100).roundToInt().coerceAtLeast(1)
            }

            addJavascriptInterface(NativeJsBridge(
                this@WebUiActivity,
                openSettingsAction = { showProviderSettings() },
                settingsChangedAction = { initAndLaunchEngine(previousEngineToken = ProviderSettingsChange.previousEngineToken()) },
                requestNotificationPermissionAction = { requestTaskNotificationPermissionOnce() },
                notificationSettingsChangedAction = { dispatchNotificationSettingsChanged() },
                requestVoiceInputAction = { launchVoiceInput() },
                restartEngineAction = { initAndLaunchEngine(restart = true) },
                reconnectEngineAction = { reconnectEngine() },
                stopEngineAction = {
                    startService(Intent(this@WebUiActivity, TermuxDaemonService::class.java).setAction(TermuxDaemonService.ACTION_STOP))
                    statusText.text = UiText.of(this@WebUiActivity, "引擎已停止", "Engine stopped")
                    loadingContainer.visibility = View.VISIBLE
                    webView.visibility = View.INVISIBLE
                    retryButton.visibility = View.VISIBLE
                },
                importLocalModelAction = { requestModelImport(it) },
                workspaceFileActionHandler = { workspaceFileActions.queue(it) },
                workspaceFolderPicker = { queueWorkspaceFolderPicker() },
                workspaceStorageAccessAction = { requestWorkspaceStorageAccess() },
                workspaceBrowserAction = { workspaceId ->
                    com.agentworkspace.mobile.workspace.WorkspaceDocumentsAccess.open(this@WebUiActivity, workspaceId) {
                        trustedWorkspacePage && !isDestroyed && !isFinishing
                    }
                },
                shareInboxReader = { shareInboxAccess { shareInbox.snapshot() } },
                shareInboxConfirmation = { raw -> shareInboxAccess { shareInbox.confirm(raw) } },
                shareInboxDiscard = { raw -> shareInboxAccess { shareInbox.discard(raw) } },
                shareInboxAcknowledgement = { raw -> shareInboxAccess { shareInbox.acknowledge(raw) } },
                shareInboxFilePicker = { queueShareInboxFilePicker() },
                systemBarsAction = { dark, color -> applySystemBars(dark, color) },
            ), "AndroidBridge")

            webChromeClient = object : WebChromeClient() {
                override fun onShowFileChooser(
                    webView: WebView?,
                    filePathCallback: ValueCallback<Array<Uri>>?,
                    fileChooserParams: FileChooserParams?
                ): Boolean {
                    fileUploadCallback?.onReceiveValue(null)
                    fileUploadCallback = filePathCallback

                    val intent = fileChooserParams?.createIntent() ?: Intent(Intent.ACTION_GET_CONTENT).apply {
                        type = "*/*"
                        addCategory(Intent.CATEGORY_OPENABLE)
                    }
                    if (fileChooserParams?.mode == FileChooserParams.MODE_OPEN_MULTIPLE) {
                        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                    }
                    try {
                        filePickerLauncher.launch(intent)
                    } catch (e: Exception) {
                        fileUploadCallback?.onReceiveValue(null)
                        fileUploadCallback = null
                        return true
                    }
                    return true
                }

                // The default WebView dialogs are titled with the page URL ("127.0.0.1:8080").
                override fun onJsAlert(view: WebView?, url: String?, message: String?, result: JsResult?): Boolean {
                    showPageDialog(url, message, result, confirm = false)
                    return true
                }

                override fun onJsConfirm(view: WebView?, url: String?, message: String?, result: JsResult?): Boolean {
                    showPageDialog(url, message, result, confirm = true)
                    return true
                }

                override fun onJsPrompt(
                    view: WebView?, url: String?, message: String?, defaultValue: String?, result: JsPromptResult?
                ): Boolean {
                    if (result == null) return true
                    if (url == null || !isTrustedConsoleUrl(url) || isDestroyed || isFinishing) { result.cancel(); return true }
                    val input = EditText(this@WebUiActivity).apply { setText(defaultValue.orEmpty()); setSingleLine() }
                    AlertDialog.Builder(this@WebUiActivity, pageDialogTheme())
                        .setMessage(message.orEmpty())
                        .setView(input)
                        .setPositiveButton(UiText.of(this@WebUiActivity, "确定", "OK")) { _, _ -> result.confirm(input.text.toString()) }
                        .setNegativeButton(UiText.of(this@WebUiActivity, "取消", "Cancel")) { _, _ -> result.cancel() }
                        .setOnCancelListener { result.cancel() }
                        .show()
                    return true
                }

                override fun onConsoleMessage(consoleMessage: ConsoleMessage?): Boolean {
                    consoleMessage?.let {
                        Log.d("AgentWebUI", "[${it.messageLevel()}] ${it.message()} -- line ${it.lineNumber()}")
                    }
                    return true
                }
            }

            webViewClient = object : WebViewClient() {
                override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                    trustedWorkspacePage = false
                    super.onPageStarted(view, url, favicon)
                }

                override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean =
                    request?.url?.toString()?.let { handleNavigation(it) } ?: true

                @Suppress("DEPRECATION")
                override fun shouldOverrideUrlLoading(view: WebView?, url: String?): Boolean =
                    url?.let { handleNavigation(it) } ?: true

                override fun onPageFinished(view: WebView?, url: String?) {
                    super.onPageFinished(view, url)
                    trustedWorkspacePage = url != null && isTrustedConsoleUrl(url)
                    if (url != null && isLocalConsoleUrl(url)) {
                        loadingContainer.visibility = View.GONE
                        webView.visibility = View.VISIBLE
                        if (isTrustedConsoleUrl(url)) {
                            deliverWorkspaceFileResults()
                            deliverWorkspaceFolderResults()
                            dispatchWorkspaceStorageChanged()
                            dispatchShareInboxChanged()
                            deliverSessionNavigation()
                            deliverSharedText()
                            if (voicePending) { voicePending = false; launchVoiceInput() }
                            requestTaskNotificationPermissionOnce()
                        }
                    }
                }

                override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                    super.onReceivedError(view, request, error)
                    if (request?.isForMainFrame == true) {
                        statusText.text = UiText.of(this@WebUiActivity, "本地连接失败，正在等待守护进程唤醒...", "Local connection failed; waiting for the service to wake...")
                        retryButton.visibility = View.VISIBLE
                    }
                }
            }
        }

        // 加载与过渡界面
        loadingContainer = FrameLayout(this).apply {
            layoutParams = FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            val pb = ProgressBar(this@WebUiActivity).apply {
                layoutParams = FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, android.view.Gravity.CENTER)
            }
            statusText = TextView(this@WebUiActivity).apply {
                text = UiText.of(this@WebUiActivity, "正在初始化运行环境...", "Initializing the runtime...")
                setTextColor(if (startupDark) Color.WHITE else Color.parseColor("#18201E"))
                textSize = 14f
                layoutParams = FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, android.view.Gravity.CENTER).apply {
                    topMargin = 140
                }
            }
            retryButton = Button(this@WebUiActivity).apply {
                text = UiText.of(this@WebUiActivity, "重试连接", "Retry")
                visibility = View.GONE
                layoutParams = FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, android.view.Gravity.CENTER).apply {
                    topMargin = 260
                }
                setOnClickListener {
                    visibility = View.GONE
                    statusText.text = UiText.of(this@WebUiActivity, "正在重新连接...", "Reconnecting...")
                    initAndLaunchEngine()
                }
            }
            settingsButton = Button(this@WebUiActivity).apply {
                text = UiText.of(this@WebUiActivity, "模型设置", "Model settings")
                layoutParams = FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                    android.view.Gravity.TOP or android.view.Gravity.END
                ).apply {
                    topMargin = 20
                    rightMargin = 20
                }
                setOnClickListener { showProviderSettings() }
            }
            addView(pb)
            addView(statusText)
            addView(retryButton)
            addView(settingsButton)
        }

        rootLayout.addView(webView)
        rootLayout.addView(loadingContainer)
        setContentView(rootLayout)
        ViewCompat.requestApplyInsets(rootLayout)
        applySystemBars(startupDark, startupColor)

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                // handleBack walks file -> sub page -> menu; older pages only expose closeMenu.
                webView.evaluateJavascript(
                    "(function(){try{const ui=window.AgentMobileUi;return (ui&&ui.handleBack?ui.handleBack():ui?.closeMenu?.())===true;}catch(e){return false;}})()"
                ) { handled ->
                    if (handled != "true" && !isDestroyed && !isFinishing) {
                        if (webView.canGoBack()) webView.goBack() else moveTaskToBack(true)
                    }
                }
            }
        })

        pendingSessionId = savedInstanceState?.getString("pending-session-id")
        savedInstanceState?.getStringArrayList("pending-shared-texts")?.forEach(sharedTexts::addLast)
        queueSessionNavigation(intent)
        shareInbox.captureIntent(intent, incomingShareBatchId)
        voicePending = intent?.getBooleanExtra("voice_input", false) == true || intent?.action in listOf(Intent.ACTION_ASSIST, Intent.ACTION_VOICE_COMMAND)
        initAndLaunchEngine()
    }

    private fun pageDialogTheme(): Int =
        if (pageDark) android.R.style.Theme_DeviceDefault_Dialog_Alert else android.R.style.Theme_DeviceDefault_Light_Dialog_Alert

    /** Console confirm/alert as an app dialog; pages other than the trusted console get none. */
    private fun showPageDialog(url: String?, message: String?, result: JsResult?, confirm: Boolean) {
        if (result == null) return
        if (url == null || !isTrustedConsoleUrl(url) || isDestroyed || isFinishing) { result.cancel(); return }
        val builder = AlertDialog.Builder(this, pageDialogTheme())
            .setMessage(message.orEmpty())
            .setPositiveButton(UiText.of(this, "确定", "OK")) { _, _ -> result.confirm() }
            .setOnCancelListener { result.cancel() }
        if (confirm) builder.setNegativeButton(UiText.of(this, "取消", "Cancel")) { _, _ -> result.cancel() }
        builder.show()
    }

    /** Paints the inset areas behind the status and navigation bars and picks readable bar icons. */
    @Suppress("DEPRECATION")
    private fun applySystemBars(dark: Boolean, color: Int) {
        if (isDestroyed || isFinishing) return
        pageDark = dark
        rootLayout.setBackgroundColor(color)
        webView.setBackgroundColor(color)
        // Android 15 ignores these and shows the root background through transparent bars.
        window.statusBarColor = color
        window.navigationBarColor = color
        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = !dark
            isAppearanceLightNavigationBars = !dark
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        queueSessionNavigation(intent)
        incomingShareBatchId = UUID.randomUUID().toString()
        shareInbox.captureIntent(intent, incomingShareBatchId)
        if (intent.getBooleanExtra("voice_input", false) || intent.action in listOf(Intent.ACTION_ASSIST, Intent.ACTION_VOICE_COMMAND)) {
            if (webView.visibility == View.VISIBLE) launchVoiceInput() else voicePending = true
        }
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        if (::webView.isInitialized) {
            webView.settings.textZoom = (newConfig.fontScale * 100).roundToInt().coerceAtLeast(1)
            (webView.parent as? View)?.let(ViewCompat::requestApplyInsets)
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString("incoming-share-batch-id", incomingShareBatchId)
        outState.putBoolean("share-inbox-picker-pending", shareInboxPickerPending)
        outState.putString("pending-session-id", pendingSessionId)
        outState.putStringArrayList("pending-shared-texts", ArrayList(sharedTexts))
        outState.putBoolean("workspace-folder-picking", workspaceFolderPicking)
        outState.putBoolean("workspace-folder-awaiting-storage", workspaceFolderAwaitingStorage)
        outState.putBoolean("workspace-storage-permission-in-flight", workspaceStoragePermissionInFlight)
        outState.putStringArrayList("workspace-folder-results", ArrayList(workspaceFolderResults.map { it.toString() }))
        outState.putString("workspace-folder-uri", pendingWorkspaceFolderUri)
        if (::workspaceFileActions.isInitialized) workspaceFileActions.saveState()?.let {
            outState.putBundle("workspace-file-save", it)
            savedWorkspaceFilePicker = true
        }
        super.onSaveInstanceState(outState)
    }

    override fun onResume() {
        super.onResume()
        if (::webView.isInitialized) {
            webView.onResume()
            dispatchNotificationSettingsChanged()
            dispatchWorkspaceStorageChanged()
            dispatchShareInboxChanged()
            deliverWorkspaceFolderResults()
            deliverSessionNavigation()
            deliverSharedText()
            checkEngineOnResume()
        }
    }

    override fun onPause() {
        if (::webView.isInitialized) webView.onPause()
        super.onPause()
    }

    private fun requestTaskNotificationPermissionOnce() {
        if (Build.VERSION.SDK_INT < 33 || notificationPermissionInFlight || isFinishing || isDestroyed ||
            !TaskNotificationSettings(this).isEnabled() || ContextCompat.checkSelfPermission(
                this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) return
        val preferences = getSharedPreferences("agent-notification-permission", MODE_PRIVATE)
        if (preferences.getBoolean("requested", false)) return
        if (!preferences.edit().putBoolean("requested", true).commit()) return
        notificationPermissionInFlight = true
        notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
    }

    private fun dispatchNotificationSettingsChanged() {
        if (!::webView.isInitialized || isDestroyed || !isTrustedConsoleUrl(webView.url ?: return)) return
        webView.evaluateJavascript("window.dispatchEvent(new Event('agent-notification-settings-changed'));", null)
    }

    private fun queueSessionNavigation(incoming: Intent?) {
        if (incoming == null || incoming.action !in setOf(TaskNotificationPublisher.ACTION_OPEN_TASK,
                "com.agentworkspace.mobile.OPEN_SCHEDULE")) return
        val session = runCatching { incoming.getStringExtra(TaskNotificationPublisher.EXTRA_SESSION_ID) }
            .getOrNull()?.trim()?.takeIf { it.isNotEmpty() && it.length <= 256 } ?: return
        incoming.removeExtra(TaskNotificationPublisher.EXTRA_SESSION_ID)
        pendingSessionId = session
        deliverSessionNavigation()
    }

    private fun deliverSessionNavigation() {
        val session = pendingSessionId ?: return
        if (deliveringSession || isDestroyed || isFinishing || webView.visibility != View.VISIBLE ||
            !isTrustedConsoleUrl(webView.url ?: return)) return
        deliveringSession = true
        val script = """
            (function(){
                var selector = document.getElementById('sessionSelector');
                if (!selector || selector.disabled || !selector.value) return false;
                return window.AgentMobileUi?.openSession?.(${JSONObject.quote(session)}) === true;
            })()
        """.trimIndent()
        webView.evaluateJavascript(script) { accepted ->
            deliveringSession = false
            if (isDestroyed || isFinishing) return@evaluateJavascript
            if (pendingSessionId != session) {
                deliverSessionNavigation()
            } else if (accepted == "true") {
                pendingSessionId = null
                deliverSharedText()
            } else {
                shareHandler.postDelayed({ deliverSessionNavigation() }, 500)
            }
        }
    }

    private fun isTrustedConsoleUrl(url: String): Boolean =
        isLocalConsoleUrl(url) && runCatching { URI(url).path == "/console" }.getOrDefault(false)

    private fun deliverSharedText() {
        if (deliveringShare || pendingSessionId != null || sharedTexts.isEmpty() || webView.visibility != View.VISIBLE ||
            !isTrustedConsoleUrl(webView.url ?: return)) return
        val shared = sharedTexts.peekFirst() ?: return
        deliveringShare = true
        val script = "(function(){return window.AgentMobileUi?.receiveSharedText(${JSONObject.quote(shared)}) === true;})()"
        webView.evaluateJavascript(script) { accepted ->
            deliveringShare = false
            if (isDestroyed) return@evaluateJavascript
            if (accepted == "true") {
                sharedTexts.removeFirst()
                deliverSharedText()
            } else if (sharedTexts.isNotEmpty()) {
                shareHandler.postDelayed({ deliverSharedText() }, 500)
            }
        }
    }

    private fun showProviderSettings() {
        val current = MobileProviderSettings.load(this)
        val padding = (20 * resources.displayMetrics.density).toInt()
        val fields = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(padding, padding / 2, padding, padding / 2)
        }
        val presets = MobileProviderSettings.providerPresets
        var selectedPreset = MobileProviderSettings.presetIndex(current.protocol, current.baseUrl)
        val provider = Spinner(this).apply {
            contentDescription = UiText.of(this@WebUiActivity, "模型服务商", "Model provider")
            adapter = ArrayAdapter(
                this@WebUiActivity,
                android.R.layout.simple_spinner_dropdown_item,
                presets.map { it.name }
            )
            setSelection(selectedPreset)
        }
        val baseUrl = EditText(this).apply {
            hint = UiText.of(this@WebUiActivity, "API 地址", "API address")
            contentDescription = UiText.of(this@WebUiActivity, "API 地址", "API address")
            inputType = android.text.InputType.TYPE_CLASS_TEXT or
                android.text.InputType.TYPE_TEXT_VARIATION_URI
            setSingleLine(true)
            setText(current.baseUrl)
        }
        val model = AutoCompleteTextView(this).apply {
            hint = UiText.of(this@WebUiActivity, "模型名称", "Model name")
            contentDescription = UiText.of(this@WebUiActivity, "模型名称", "Model name")
            inputType = android.text.InputType.TYPE_CLASS_TEXT or
                android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
            setSingleLine(true)
            setText(current.model)
            threshold = 0
            setCompoundDrawablesRelativeWithIntrinsicBounds(0, 0, android.R.drawable.arrow_down_float, 0)
            setAdapter(ArrayAdapter(
                this@WebUiActivity,
                android.R.layout.simple_dropdown_item_1line,
                presets[selectedPreset].models,
            ))
            setOnClickListener {
                (adapter as? android.widget.Filterable)?.filter?.filter(null) {
                    if (isAttachedToWindow) showDropDown()
                }
            }
        }
        var effortOptions = MobileProviderSettings.reasoningEfforts(current.protocol, current.baseUrl, current.model)
        fun effortLabel(value: String) = when (value) {
            "auto" -> UiText.of(this@WebUiActivity, "自动", "Auto")
            "none" -> UiText.of(this@WebUiActivity, "关闭", "Off")
            "low" -> UiText.of(this@WebUiActivity, "低", "Low")
            "medium" -> UiText.of(this@WebUiActivity, "中", "Medium")
            "high" -> UiText.of(this@WebUiActivity, "高", "High")
            "xhigh" -> UiText.of(this@WebUiActivity, "很高", "Very high")
            else -> UiText.of(this@WebUiActivity, "最高", "Max")
        }
        val effort = Spinner(this).apply {
            contentDescription = UiText.of(this@WebUiActivity, "思考程度", "Reasoning effort")
            adapter = ArrayAdapter(this@WebUiActivity, android.R.layout.simple_spinner_dropdown_item,
                effortOptions.map { effortLabel(it) })
            setSelection(effortOptions.indexOf(current.reasoningEffort).coerceAtLeast(0))
        }
        fun refreshEffortOptions() {
            val selected = effortOptions.getOrNull(effort.selectedItemPosition) ?: "auto"
            effortOptions = MobileProviderSettings.reasoningEfforts(
                presets[provider.selectedItemPosition].protocol, baseUrl.text.toString().trim(), model.text.toString().trim()
            )
            effort.adapter = ArrayAdapter(this@WebUiActivity, android.R.layout.simple_spinner_dropdown_item,
                effortOptions.map { effortLabel(it) })
            effort.setSelection(effortOptions.indexOf(selected).coerceAtLeast(0))
            effort.isEnabled = effortOptions.size > 1
        }
        val refreshWatcher = object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
            override fun afterTextChanged(s: Editable?) = refreshEffortOptions()
        }
        baseUrl.addTextChangedListener(refreshWatcher)
        model.addTextChangedListener(refreshWatcher)
        provider.onItemSelectedListener = object : android.widget.AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(parent: android.widget.AdapterView<*>?) = Unit
            override fun onItemSelected(parent: android.widget.AdapterView<*>?, view: View?, position: Int, id: Long) {
                val preset = presets[position]
                if (position != selectedPreset && preset.baseUrl != null) {
                    baseUrl.setText(preset.baseUrl)
                    model.setText(preset.models.firstOrNull().orEmpty(), false)
                }
                selectedPreset = position
                model.setAdapter(ArrayAdapter(this@WebUiActivity,
                    android.R.layout.simple_dropdown_item_1line, preset.models))
                refreshEffortOptions()
            }
        }
        val modeLabels = listOf(UiText.of(this@WebUiActivity, "工作区", "Workspace"), "YOLO", UiText.of(this@WebUiActivity, "完全访问", "Full access"))
        val autonomy = Spinner(this).apply {
            contentDescription = UiText.of(this@WebUiActivity, "执行模式", "Execution mode")
            adapter = ArrayAdapter(this@WebUiActivity, android.R.layout.simple_spinner_dropdown_item, modeLabels)
            setSelection(MobileProviderSettings.autonomies.indexOf(current.autonomy).coerceAtLeast(0))
        }
        val apiKey = EditText(this).apply {
            hint = if (current.apiKey.isNullOrBlank()) "API Key" else UiText.of(this@WebUiActivity, "API Key（留空则保留）", "API key (leave blank to keep)")
            inputType = android.text.InputType.TYPE_CLASS_TEXT or
                android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        val removeKey = CheckBox(this).apply {
            text = UiText.of(this@WebUiActivity, "删除已有 API Key", "Delete saved API key")
            visibility = if (current.apiKey.isNullOrBlank()) View.GONE else View.VISIBLE
        }
        fields.addView(provider)
        fields.addView(baseUrl)
        fields.addView(model)
        fields.addView(TextView(this).apply { text = UiText.of(this@WebUiActivity, "思考程度", "Reasoning effort") })
        fields.addView(effort)
        fields.addView(TextView(this).apply { text = UiText.of(this@WebUiActivity, "执行模式", "Execution mode") })
        fields.addView(autonomy)
        fields.addView(apiKey)
        fields.addView(removeKey)
        val scroll = ScrollView(this).apply { addView(fields) }
        val dialog = AlertDialog.Builder(this)
            .setTitle(UiText.of(this@WebUiActivity, "模型设置", "Model settings"))
            .setView(scroll)
            .setNegativeButton(UiText.of(this@WebUiActivity, "取消", "Cancel"), null)
            .setPositiveButton(UiText.of(this@WebUiActivity, "保存", "Save"), null)
            .create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                val selectedProtocol = presets[provider.selectedItemPosition].protocol
                val selectedBase = baseUrl.text.toString().trim()
                val selectedModel = model.text.toString().trim()
                val selectedKey = apiKey.text.toString().trim().takeIf { it.isNotEmpty() }
                val deleteKey = removeKey.isChecked
                val selectedEffort = effortOptions[effort.selectedItemPosition]
                val selectedAutonomy = MobileProviderSettings.autonomies[autonomy.selectedItemPosition]
                val saveButton = dialog.getButton(AlertDialog.BUTTON_POSITIVE)
                saveButton.isEnabled = false
                activityScope.launch {
                    try {
                        // Finish the reserved save/restart even if the Activity closes during weight hashing.
                        withContext(Dispatchers.IO + NonCancellable) {
                            ProviderSettingsChange.apply(this@WebUiActivity,
                                selectedBase.trimEnd('/') == MobileProviderSettings.EMBEDDED_QWEN_BASE_URL) {
                                MobileProviderSettings.save(this@WebUiActivity, selectedProtocol,
                                    selectedBase, selectedModel, selectedKey, deleteKey, selectedEffort, selectedAutonomy)
                            }
                        }
                        dialog.dismiss()
                        initAndLaunchEngine(previousEngineToken = ProviderSettingsChange.previousEngineToken())
                    } catch (error: CancellationException) {
                        throw error
                    } catch (error: Exception) {
                        android.widget.Toast.makeText(this@WebUiActivity, error.message ?: UiText.of(this@WebUiActivity, "保存失败", "Save failed"),
                            android.widget.Toast.LENGTH_LONG).show()
                        if ((error as? ProviderChangeCoordinator.Failure)?.restartRequested == true) {
                            initAndLaunchEngine(previousEngineToken = ProviderSettingsChange.previousEngineToken())
                        }
                    } finally {
                        if (dialog.isShowing) saveButton.isEnabled = true
                    }
                }
            }
        }
        dialog.show()
    }

    private fun initAndLaunchEngine(restart: Boolean = false, previousEngineToken: String? = null) {
        initializationJob?.cancel()
        loadingContainer.visibility = View.VISIBLE
        webView.visibility = View.INVISIBLE
        retryButton.visibility = View.GONE
        initializationJob = activityScope.launch {
            try {
                if (!TermuxBootstrap.isInstalled(this@WebUiActivity)) {
                    statusText.text = UiText.of(this@WebUiActivity, "正在准备本地服务...", "Preparing the local service...")
                    withContext(Dispatchers.IO) {
                        TermuxBootstrap.installSync(this@WebUiActivity) { msg ->
                            activityScope.launch { statusText.text = msg }
                        }
                    }
                }

                statusText.text = UiText.of(this@WebUiActivity, "正在启动本地 Agent 守护引擎...", "Starting the local Agent engine...")
                val provider = withContext(Dispatchers.IO) {
                    File(filesDir, TermuxDaemonService.STARTUP_FAILURE_FILE).delete()
                    if (restart) File(filesDir, "serve.token").delete()
                    MobileProviderSettings.load(this@WebUiActivity).toJson()
                }
                val daemonIntent = Intent(this@WebUiActivity, TermuxDaemonService::class.java).apply {
                    putExtra(TermuxDaemonService.EXTRA_PROVIDER_CONFIGURATION, provider)
                    if (restart) action = TermuxDaemonService.ACTION_RESTART
                }
                startForegroundService(daemonIntent)

                statusText.text = UiText.of(this@WebUiActivity, "正在连接本地 WebUI 控制台...", "Connecting to the local console...")
                val consoleUrl = withContext(Dispatchers.IO) {
                    var ready = false
                    var attempts = 0
                    var token: String? = null
                    // An engine that keeps failing to prove its identity is wedged (or a stalled old
                    // instance still holds the port). It lives in its own process, so reopening the
                    // app never clears it; replace that process once instead of waiting forever.
                    var unanswered = 0
                    var tokenless = 0
                    var revived = false
                    while (!ready && attempts < 120) {
                        attempts++
                        if (File(filesDir, TermuxDaemonService.STARTUP_FAILURE_FILE).isFile) {
                            if (!revived) {
                                revived = true
                                withContext(Dispatchers.Main) { statusText.text = UiText.of(this@WebUiActivity, "正在重新启动本地引擎...", "Restarting the local engine...") }
                                replaceEngineProcess(daemonIntent, "startup failed")
                                attempts = 0
                                unanswered = 0
                                continue
                            }
                            throw IllegalStateException(UiText.of(this@WebUiActivity, "本地 Python 服务启动失败", "The local Python service failed to start"))
                        }
                        token = readServeToken()
                        if (token.isNullOrEmpty() || token == previousEngineToken) {
                            withContext(Dispatchers.Main) {
                                statusText.text = if (token == previousEngineToken && token != null)
                                    UiText.of(this@WebUiActivity, "正在等待引擎重新启动...", "Waiting for the engine to restart...") else UiText.of(this@WebUiActivity, "正在等待本地服务凭据...", "Waiting for the local service credentials...")
                            }
                            // A normal start publishes its token within seconds; none after ~50 s means
                            // the engine process is gone or stuck before binding.
                            unanswered = 0
                            if (++tokenless >= ENGINE_MISSING_TOKEN_ATTEMPTS && !revived) {
                                revived = true
                                withContext(Dispatchers.Main) { statusText.text = UiText.of(this@WebUiActivity, "正在重新启动本地引擎...", "Restarting the local engine...") }
                                replaceEngineProcess(daemonIntent, "no engine token")
                                attempts = 0
                                tokenless = 0
                                continue
                            }
                        } else if (!verifyEngineIdentity(token)) {
                            // Something answers on the port without our secret, or nothing answers yet.
                            // Never send it the token; keep waiting for our own engine.
                            withContext(Dispatchers.Main) { statusText.text = UiText.of(this@WebUiActivity, "正在确认本地服务身份...", "Verifying the local service...") }
                            tokenless = 0
                            if (++unanswered >= ENGINE_UNRESPONSIVE_ATTEMPTS && !revived) {
                                revived = true
                                withContext(Dispatchers.Main) { statusText.text = UiText.of(this@WebUiActivity, "本地引擎没有响应，正在重新启动...", "The local engine is not responding; restarting it...") }
                                replaceEngineProcess(daemonIntent, "identity unanswered")
                                attempts = 0
                                unanswered = 0
                                continue
                            }
                        } else {
                            unanswered = 0
                            val conn = URL("$BASE_URL/health").openConnection() as HttpURLConnection
                            try {
                                conn.setRequestProperty("Authorization", "Bearer $token")
                                conn.connectTimeout = 1000
                                conn.readTimeout = 1000
                                ready = conn.responseCode in 200..399
                            } catch (e: IOException) {
                                Log.d("AgentWebUI", "Local Agent health check failed", e)
                            } finally {
                                conn.disconnect()
                            }
                        }
                        if (!ready) {
                            delay(500)
                        }
                    }
                    if (ready && !token.isNullOrEmpty()) {
                        "$BASE_URL/console?token=${Uri.encode(token)}"
                    } else {
                        null
                    }
                }

                if (consoleUrl != null) {
                    loadedEngineToken = Uri.parse(consoleUrl).getQueryParameter("token")
                    webView.loadUrl(consoleUrl)
                } else {
                    statusText.text = UiText.of(this@WebUiActivity, "本地 Agent 服务启动超时，请点击重试", "The local Agent service timed out; tap Retry")
                    retryButton.visibility = View.VISIBLE
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e("AgentWebUI", "Failed to initialize local Agent", e)
                statusText.text = UiText.of(this@WebUiActivity, "本地 Agent 初始化失败: ${e.message ?: e.javaClass.simpleName}", "Could not initialize the local Agent: ${e.message ?: e.javaClass.simpleName}")
                retryButton.visibility = View.VISIBLE
            }
        }
    }


    /**
     * The page lost the engine (it died, was restarted with a new token, or stopped answering).
     * Re-run the normal start-up path: it starts the service if needed, replaces an engine process
     * that does not answer, and reloads the console with the engine's current token. Drafts and the
     * running task survive the reload (drafts are stored locally, tasks live in the engine).
     */
    private fun reconnectEngine() {
        if (initializationJob?.isActive == true || isFinishing || isDestroyed) return
        initAndLaunchEngine()
    }

    /** Coming back to the app: if the engine behind the open page changed or stopped answering, reconnect. */
    private fun checkEngineOnResume() {
        val expected = loadedEngineToken ?: return
        if (initializationJob?.isActive == true || resumeCheckJob?.isActive == true || webView.visibility != View.VISIBLE) return
        resumeCheckJob = activityScope.launch {
            val healthy = withContext(Dispatchers.IO) {
                // A busy engine still answers the identity route at once; allow a few tries for a slow wake-up.
                repeat(3) {
                    val token = readServeToken()
                    if (token != null && token != expected) return@withContext false
                    if (token != null && verifyEngineIdentity(token)) return@withContext true
                    delay(1000)
                }
                false
            }
            if (!healthy) {
                Log.w("AgentWebUI", "The engine behind the open console changed or stopped answering; reconnecting")
                reconnectEngine()
            }
        }
    }

    /**
     * Kill the :engine process (same app, so this is permitted) and start the service in a fresh one.
     * Used only when the engine cannot prove its identity or failed to start; a running task is then
     * reported as interrupted and can be resumed.
     */
    private suspend fun replaceEngineProcess(daemonIntent: Intent, reason: String) {
        Log.w("AgentWebUI", "Replacing the engine process: $reason")
        val engineProcess = "$packageName:engine"
        val activities = getSystemService(ACTIVITY_SERVICE) as android.app.ActivityManager
        activities.runningAppProcesses.orEmpty()
            .filter { it.processName == engineProcess }
            .forEach { android.os.Process.killProcess(it.pid) }
        File(filesDir, "serve.token").delete()
        File(filesDir, TermuxDaemonService.STARTUP_FAILURE_FILE).delete()
        runCatching {
            File(filesDir, "agent-data/logs").mkdirs()
            File(filesDir, "agent-data/logs/engine-restarts.log")
                .appendText("${java.time.Instant.now()} replaced engine process: $reason\n")
        }
        // Give Android a moment to reap the old process before the service starts a new one.
        delay(1500)
        withContext(Dispatchers.Main) { startForegroundService(daemonIntent) }
    }

    /**
     * Challenge-response with the engine before the token leaves the app: another process holding
     * 127.0.0.1:8080 cannot compute the HMAC because it never sees the private serve.token.
     */
    private fun verifyEngineIdentity(token: String): Boolean {
        val challenge = ByteArray(32).also { java.security.SecureRandom().nextBytes(it) }
            .let { android.util.Base64.encodeToString(it, android.util.Base64.URL_SAFE or android.util.Base64.NO_WRAP or android.util.Base64.NO_PADDING) }
        val conn = URL("$BASE_URL/mobile/identity?challenge=$challenge").openConnection() as HttpURLConnection
        return try {
            conn.connectTimeout = 1000
            conn.readTimeout = 1000
            conn.instanceFollowRedirects = false
            if (conn.responseCode != 200) return false
            val body = conn.inputStream.use { input ->
                val buffer = ByteArray(4096)
                var size = 0
                while (size < buffer.size) {
                    val count = input.read(buffer, size, buffer.size - size)
                    if (count < 0) break
                    size += count
                }
                String(buffer, 0, size, Charsets.UTF_8)
            }
            val proof = JSONObject(body).optString("proof")
            val mac = javax.crypto.Mac.getInstance("HmacSHA256")
            mac.init(javax.crypto.spec.SecretKeySpec(token.toByteArray(Charsets.UTF_8), "HmacSHA256"))
            val expected = mac.doFinal(IDENTITY_CONTEXT + challenge.toByteArray(Charsets.US_ASCII))
                .joinToString("") { "%02x".format(it) }
            java.security.MessageDigest.isEqual(expected.toByteArray(), proof.toByteArray())
        } catch (e: Exception) {
            Log.d("AgentWebUI", "Local Agent identity check failed", e)
            false
        } finally {
            conn.disconnect()
        }
    }

    private fun readServeToken(): String? {
        val tokenFile = File(filesDir, "serve.token")
        if (!tokenFile.isFile) return null
        return runCatching { tokenFile.readText(Charsets.UTF_8).trim() }
            .getOrNull()
            ?.takeIf { it.isNotEmpty() }
    }

    private fun launchVoiceInput() {
        if (!MobileVoiceInput.isAvailable(this)) {
            android.widget.Toast.makeText(this, UiText.of(this@WebUiActivity, "手机没有可用的语音识别服务", "No speech recognition service is available on this phone"), android.widget.Toast.LENGTH_SHORT).show()
            return
        }
        runCatching { voiceInputLauncher.launch(MobileVoiceInput.recognizerIntent()) }
            .onFailure { android.widget.Toast.makeText(this, UiText.of(this@WebUiActivity, "无法启动语音识别", "Could not start speech recognition"), android.widget.Toast.LENGTH_SHORT).show() }
    }

    private fun isLocalConsoleUrl(url: String): Boolean = runCatching {
        val uri = URI(url)
        uri.scheme == "http" && uri.host == "127.0.0.1" && uri.port == 8080 && uri.userInfo == null
    }.getOrDefault(false)

    private fun handleNavigation(url: String): Boolean {
        if (isLocalConsoleUrl(url)) return false
        val uri = runCatching { URI(url) }.getOrNull()
        if (uri?.scheme in listOf("http", "https") && !uri?.host.isNullOrBlank() && uri?.userInfo == null) {
            NativeJsBridge(this).openExternal(url)
        } else {
            android.widget.Toast.makeText(this, UiText.of(this@WebUiActivity, "链接地址不受支持", "This link is not supported"), android.widget.Toast.LENGTH_SHORT).show()
        }
        return true
    }

    override fun onDestroy() {
        if (::shareInbox.isInitialized) shareInbox.removeListener(shareInboxListener)
        if (::workspaceFileActions.isInitialized) workspaceFileActions.close(preserveSave = savedWorkspaceFilePicker && !isFinishing)
        trustedWorkspacePage = false
        fileUploadCallback?.onReceiveValue(null)
        fileUploadCallback = null
        shareHandler.removeCallbacksAndMessages(null)
        if (::webView.isInitialized) {
            (webView.parent as? ViewGroup)?.removeView(webView)
            webView.stopLoading()
            webView.onPause()
            webView.removeJavascriptInterface("AndroidBridge")
            webView.destroy()
        }
        super.onDestroy()
        activityScope.cancel()
    }
}
