package com.agentworkspace.mobile.embedded

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import com.agentworkspace.mobile.WebUiActivity
import com.agentworkspace.mobile.automation.AndroidSystemBridge
import com.agentworkspace.mobile.capabilities.AndroidTextToSpeech
import com.agentworkspace.mobile.documents.AndroidDocumentBridge
import com.agentworkspace.mobile.localmodels.LocalModelBridge
import com.agentworkspace.mobile.toolchain.AndroidToolchainBridge
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * 托管内置 Python 引擎的后台服务。
 */
class TermuxDaemonService : Service() {

    companion object {
        const val ACTION_RESTART = "com.agentworkspace.mobile.RESTART_ENGINE"
        const val ACTION_STOP = "com.agentworkspace.mobile.STOP_ENGINE"
        const val EXTRA_PROVIDER_CONFIGURATION = "provider-configuration"
        const val EXTRA_EXPECTED_ENGINE_TOKEN = "expected-engine-token"
        const val STARTUP_FAILURE_FILE = "engine.failed"
        private const val NOTIFICATION_ID = 2001
        private val engineMutex = Mutex()

        /**
         * Start (or deliver an intent to) the engine service. A visible app starts it as an
         * ordinary service, which then promotes itself to the foreground: if Android refuses the
         * foreground notification, the engine keeps running while the app is open instead of
         * the process being killed for a broken startForegroundService promise. Callers in the
         * background still need startForegroundService.
         */
        @JvmStatic
        fun start(context: Context, intent: Intent) {
            try {
                context.startService(intent)
            } catch (_: IllegalStateException) {
                context.startForegroundService(intent)
            }
        }
        @Volatile private var currentEngineJob: Job? = null
    }

    private var wakeLock: PowerManager.WakeLock? = null
    private var engineJob: Job? = null
    private var readinessJob: Job? = null
    private var notificationJob: Job? = null
    private lateinit var lifecycleState: EngineLifecycleState
    @Volatile private var engineReady = false
    @Volatile private var serviceClosing = false
    @Volatile private var engineRestarting = false
    @Volatile private var activeProviderConfiguration: String? = null
    @Volatile private var runningServices = 0
    @Volatile private var servicesKeepAwake = false
    private var lastReportedState: String? = null
    private var lastStateHeartbeat = 0L
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        lifecycleState = EngineLifecycleState(this)
        MobileScheduleCoordinator.initialize(this)
        AndroidSystemBridge.initialize(this)
        AndroidTextToSpeech.initialize(this)
        AndroidDocumentBridge.initialize(this)
        AndroidToolchainBridge.initialize(this)
        LocalModelBridge.initialize(this)
        com.agentworkspace.mobile.browser.AgentBrowser.initialize(this)

        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "AgentWorkspace::TermuxDaemonLock").apply {
            setReferenceCounted(false)
            acquire(30000L)
        }

        goForeground(buildNotification(com.agentworkspace.mobile.UiText.of(this@TermuxDaemonService, "Agent 内置引擎正在启动...", "Agent engine starting...")))
        notificationJob = serviceScope.launch {
            TaskNotificationMonitor(
                this@TermuxDaemonService,
                taskStateListener = ::observeTasks,
                servicesListener = { running, keepAwake ->
                    runningServices = running
                    servicesKeepAwake = keepAwake
                },
            ).run()
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            serviceClosing = true
            lifecycleState.markStoppedByUser()
            EngineRecovery.cancel(this)
            EngineRecovery.clearLaunchNotification(this)
            MobileScheduleCoordinator(this).restoreAlarms()
            releaseWakeLock()
            stopPython()
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }
        val userInitiated = intent != null && intent.action != EngineRecovery.ACTION_RECOVER
        if (!lifecycleState.beginStart(userInitiated)) {
            EngineStartupLog.append(this, "service: automatic start skipped (stopped by the user or waiting for the app)")
            serviceClosing = true
            releaseWakeLock()
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }
        MobileScheduleCoordinator(this).restoreAlarms()
        EngineRecovery.ensurePeriodic(this)
        startEmbeddedEngine(
            intent?.action == ACTION_RESTART || intent?.action == EngineRecovery.ACTION_RECOVER,
            intent?.getStringExtra(EXTRA_PROVIDER_CONFIGURATION),
            intent?.getStringExtra(EXTRA_EXPECTED_ENGINE_TOKEN)
        )
        return START_STICKY
    }

    private fun startEmbeddedEngine(restart: Boolean, providerConfiguration: String?, expectedEngineToken: String?) {
        serviceScope.launch {
            try {
                engineMutex.withLock {
                    if (expectedEngineToken != null) {
                        val currentToken = runCatching { File(filesDir, "serve.token").readText().trim() }.getOrNull()
                        if (expectedEngineToken.isBlank() || currentToken != expectedEngineToken) return@withLock
                    }
                    if (engineJob?.isActive == true && !restart) return@withLock
                    if (serviceClosing) return@withLock
                    readinessJob?.cancel()
                    engineReady = false
                    engineRestarting = true
                    val previous = currentEngineJob
                    if (previous != null && !previous.isCompleted) {
                        EngineStartupLog.append(this@TermuxDaemonService, "service: stopping the previous engine")
                        stopPython()
                        val stopped = withTimeoutOrNull(10000) {
                            previous.join()
                            true
                        } == true
                        if (!stopped) replaceStalledEngineProcess()
                    }
                    LocalModelBridge.unload()
                    if (serviceClosing) return@withLock
                    engineRestarting = false
                    updateNotification(com.agentworkspace.mobile.UiText.of(this@TermuxDaemonService, "Agent 内置引擎正在启动...", "Agent engine starting..."))
                    reportEngineState("starting")
                    File(filesDir, STARTUP_FAILURE_FILE).delete()
                    EmbeddedSecrets.initialize(this@TermuxDaemonService)
                    val configuration = providerConfiguration
                        ?: activeProviderConfiguration
                        ?: MobileProviderSettings.load(this@TermuxDaemonService).toJson()
                    LocalModelBridge.configureRuntime(configuration)
                    if (!Python.isStarted()) {
                        // The first start after an install or update unpacks the Python runtime and can take a while.
                        EngineStartupLog.append(this@TermuxDaemonService, "service: starting the Python runtime")
                        Python.start(AndroidPlatform(this@TermuxDaemonService))
                        EngineStartupLog.append(this@TermuxDaemonService, "service: Python runtime started")
                    }
                    File(filesDir, "serve.token").delete()
                    activeProviderConfiguration = configuration
                    engineJob = serviceScope.launch {
                        try {
                            Python.getInstance().getModule("mobile_embedded")
                                .callAttr("run", filesDir.absolutePath, configuration)
                        } catch (e: CancellationException) {
                            throw e
                        } catch (e: Exception) {
                            android.util.Log.e("AgentEmbedded", "Embedded Python failed", e)
                            EngineStartupLog.append(this@TermuxDaemonService, "service: engine ended with ${e.javaClass.simpleName}: ${e.message.orEmpty().lineSequence().firstOrNull().orEmpty().take(300)}")
                            runCatching { File(filesDir, STARTUP_FAILURE_FILE).writeText(e.javaClass.simpleName) }
                            lifecycleState.mark("failed", "The embedded engine failed to start")
                            releaseWakeLock()
                            updateNotification(com.agentworkspace.mobile.UiText.of(this@TermuxDaemonService, "Agent 引擎启动失败", "Agent engine failed to start"))
                        } finally {
                            engineReady = false
                            releaseWakeLock()
                            if (!serviceClosing && !engineRestarting && !File(filesDir, STARTUP_FAILURE_FILE).isFile) {
                                lifecycleState.mark("interrupted", "The engine stopped; reopen the app to recover tasks")
                            }
                            if (!serviceClosing && !engineRestarting) EngineRecovery.enqueue(this@TermuxDaemonService, 60)
                        }
                    }
                    currentEngineJob = engineJob
                    readinessJob = serviceScope.launch { awaitReadyEngine() }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                engineRestarting = false
                android.util.Log.e("AgentEmbedded", "Failed to initialize embedded Python", e)
                EngineStartupLog.append(this@TermuxDaemonService, "service: Python failed to initialize: ${e.javaClass.simpleName}: ${e.message.orEmpty().take(300)}")
                runCatching { File(filesDir, STARTUP_FAILURE_FILE).writeText(e.javaClass.simpleName) }
                lifecycleState.mark("failed", "The embedded engine failed to initialize")
                releaseWakeLock()
                updateNotification(com.agentworkspace.mobile.UiText.of(this@TermuxDaemonService, "Agent 引擎启动失败", "Agent engine failed to start"))
                EngineRecovery.enqueue(this@TermuxDaemonService, 60)
            }
        }
    }

    private suspend fun awaitReadyEngine() {
        repeat(120) {
            if (engineJob?.isActive != true || File(filesDir, STARTUP_FAILURE_FILE).isFile) return
            val token = runCatching { File(filesDir, "serve.token").readText().trim() }
                .getOrNull()
            if (!token.isNullOrEmpty()) {
                val healthy = runCatching {
                    val connection = URL("http://127.0.0.1:8080/health").openConnection() as HttpURLConnection
                    try {
                        connection.setRequestProperty("Authorization", "Bearer $token")
                        connection.connectTimeout = 1000
                        connection.readTimeout = 1000
                        connection.responseCode in 200..299
                    } finally {
                        connection.disconnect()
                    }
                }.getOrDefault(false)
                if (healthy) {
                    engineReady = true
                    reportEngineState("ready")
                    EngineRecovery.clearLaunchNotification(this@TermuxDaemonService)
                    releaseWakeLock()
                    runCatching { EngineRecovery.reconcileSchedules(this@TermuxDaemonService) }
                        .onFailure { if (it is CancellationException) throw it }
                    return
                }
            }
            delay(500)
        }
    }

    /**
     * The previous engine ignored its stop request. Left alone it lingers half-stopped: its HTTP server
     * may already be closed (every request fails) while its job still counts as running, so nothing
     * ever starts a new one and the app waits on the identity check forever. Python threads cannot be
     * killed individually, so end this whole :engine process; the sticky service and the app's start-up
     * path bring up a clean engine in a new process.
     */
    private fun replaceStalledEngineProcess(): Nothing {
        android.util.Log.e("AgentEmbedded", "The previous embedded engine did not stop; replacing the engine process")
        runCatching {
            File(filesDir, "agent-data/logs").mkdirs()
            File(filesDir, "agent-data/logs/engine-restarts.log")
                .appendText("${java.time.Instant.now()} previous engine did not stop within 10 s; engine process replaced\n")
        }
        File(filesDir, "serve.token").delete()
        runCatching { lifecycleState.mark("interrupted", "The engine did not stop in time and was restarted") }
        android.os.Process.killProcess(android.os.Process.myPid())
        throw IllegalStateException("The previous embedded engine did not stop")
    }

    private fun stopPython() {
        LocalModelBridge.cancel()
        if (Python.isStarted()) {
            runCatching { Python.getInstance().getModule("mobile_embedded").callAttr("stop") }
                .onFailure { android.util.Log.e("AgentEmbedded", "Failed to stop Python", it) }
        }
    }

    @Synchronized
    private fun observeTasks(tasks: List<TaskNotificationSnapshot>?) {
        if (serviceClosing || !engineReady) return
        val states = tasks?.map { it.state }
        val active = states?.any { it == "queued" || it == "running" } == true
        // Services keep the CPU awake with the screen off only when the user turned that on.
        val awake = active || (runningServices > 0 && servicesKeepAwake)
        if (awake) wakeLock?.acquire(60000L) else releaseWakeLock()
        val state = when {
            states == null -> "recovering"
            active -> "running"
            "waiting_approval" in states -> "waiting_approval"
            else -> "ready"
        }
        reportEngineState(state)
    }

    @Synchronized
    private fun reportEngineState(state: String) {
        val now = System.currentTimeMillis()
        val services = runningServices
        val key = "$state:$services"
        if (key != lastReportedState || now - lastStateHeartbeat >= 15000) {
            lifecycleState.mark(state)
            lastReportedState = key
            lastStateHeartbeat = now
            val base = when (state) {
                "running" -> com.agentworkspace.mobile.UiText.of(this@TermuxDaemonService, "Agent 正在执行任务", "Agent is running a task")
                "waiting_approval" -> com.agentworkspace.mobile.UiText.of(this@TermuxDaemonService, "Agent 任务等待批准", "Agent task awaiting approval")
                "recovering" -> com.agentworkspace.mobile.UiText.of(this@TermuxDaemonService, "Agent 正在恢复连接", "Agent is reconnecting")
                "starting" -> com.agentworkspace.mobile.UiText.of(this@TermuxDaemonService, "Agent 内置引擎正在启动...", "Agent engine starting...")
                else -> com.agentworkspace.mobile.UiText.of(this@TermuxDaemonService, "Agent 内置引擎已就绪", "Agent engine ready")
            }
            val text = if (services > 0 && state != "starting") base + com.agentworkspace.mobile.UiText.of(
                this@TermuxDaemonService, " · $services 个后台服务运行中", " · $services service(s) running"
            ) else base
            updateNotification(text)
        }
    }

    @Synchronized
    private fun releaseWakeLock() { wakeLock?.let { if (it.isHeld) it.release() } }

    private fun updateNotification(text: String) {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(2001, buildNotification(text))
    }

    private fun buildNotification(text: String): Notification {
        val launchIntent = Intent(this, WebUiActivity::class.java).apply {
            action = Intent.ACTION_MAIN
            addCategory(Intent.CATEGORY_LAUNCHER)
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val openApp = PendingIntent.getActivity(
            this, 2001, launchIntent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val stopEngine = PendingIntent.getService(this, 2002,
            Intent(this, TermuxDaemonService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return NotificationCompat.Builder(this, "termux_daemon_channel")
            .setContentTitle(com.agentworkspace.mobile.UiText.of(this@TermuxDaemonService, "Agent Workspace 引擎", "Agent Workspace engine"))
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setContentIntent(openApp)
            .setOngoing(true)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, com.agentworkspace.mobile.UiText.of(this@TermuxDaemonService, "停止引擎", "Stop engine"), stopEngine)
            .build()
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel("termux_daemon_channel", com.agentworkspace.mobile.UiText.of(this@TermuxDaemonService, "Agent 守护进程", "Agent engine"), NotificationManager.IMPORTANCE_LOW)
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(channel)
    }

    override fun onDestroy() {
        val unexpected = !serviceClosing
        if (unexpected) runCatching {
            lifecycleState.mark("interrupted", "The Android service stopped; reopen the app to recover tasks")
        }
        serviceClosing = true
        notificationJob?.cancel()
        readinessJob?.cancel()
        stopPython()
        val stoppingJob = engineJob
        super.onDestroy()
        serviceScope.cancel()
        // Native unload may wait for CPU inference to abort, so keep it off the main thread.
        CoroutineScope(Dispatchers.IO + SupervisorJob()).launch {
            engineMutex.withLock {
                if (currentEngineJob === stoppingJob && withTimeoutOrNull(10000) {
                    stoppingJob?.join()
                    true
                } == true) {
                    LocalModelBridge.unload()
                    currentEngineJob = null
                }
            }
        }
        if (unexpected) EngineRecovery.enqueue(this, 60)
        releaseWakeLock()
        AndroidTextToSpeech.shutdown()
    }

    /**
     * The engine is a long-running local server, Android's "special use" foreground type. The
     * dataSync type it used before is capped at 6 hours a day from Android 15: once that budget
     * was spent, startForeground threw and the engine crashed on every start, so the app could
     * not open at all. If Android still refuses (OEM limits), the engine runs as an ordinary
     * service while the app is open rather than crashing.
     */
    private fun goForeground(notification: Notification) {
        try {
            if (android.os.Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIFICATION_ID, notification,
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
        } catch (failure: Exception) {
            android.util.Log.w("AgentEngine", "Android refused the foreground notification; running while the app is open", failure)
            runCatching {
                File(filesDir, "agent-data/logs").mkdirs()
                File(filesDir, "agent-data/logs/engine-restarts.log").appendText(
                    "${java.time.Instant.now()} foreground refused: ${failure.javaClass.simpleName}: ${failure.message}\n")
            }
        }
    }

    override fun onTimeout(startId: Int, fgsType: Int) {
        serviceClosing = true
        runCatching { lifecycleState.markForegroundLimited() }
        EngineRecovery.cancel(this)
        EngineRecovery.showLaunchRequired(this, com.agentworkspace.mobile.UiText.of(this@TermuxDaemonService, "Android 已限制后台执行，请打开应用恢复", "Android restricted background work; open the app to resume"))
        notificationJob?.cancel()
        readinessJob?.cancel()
        releaseWakeLock()
        stopPython()
        try { stopForeground(STOP_FOREGROUND_REMOVE) }
        finally { stopSelf() }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onTaskRemoved(rootIntent: Intent?) {
        if (!serviceClosing) EngineRecovery.enqueue(this, 60)
        super.onTaskRemoved(rootIntent)
    }
}
