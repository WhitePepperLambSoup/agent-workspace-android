package com.agentworkspace.mobile.browser

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.view.View
import android.webkit.CookieManager
import android.webkit.JsPromptResult
import android.webkit.JsResult
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebStorage
import android.webkit.WebView
import android.webkit.WebViewClient
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.util.concurrent.Callable
import java.util.concurrent.CountDownLatch
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/**
 * The agent's own browser: one invisible WebView in the engine process, driven by the `browser`
 * tools. Pages get no JavaScript bridge, only http(s) pages load, and the app's own local port is
 * off limits. It keeps its own cookies, separate from the app's console.
 *
 * Every call blocks a worker thread while the WebView work runs on the main thread.
 */
object AgentBrowser {
    private const val PAGE_TIMEOUT_MS = 30_000L
    private const val SETTLE_MS = 600L
    private const val MAX_SCRIPT_RESULT = 1_000_000
    private val main = Handler(Looper.getMainLooper())
    private lateinit var context: Context
    private var view: WebView? = null
    @Volatile private var loading = false
    @Volatile private var lastFinished = 0L
    @Volatile private var mainFrameError: String? = null
    @Volatile private var lastDialog: String? = null
    @Volatile private var blocked: String? = null

    /** Called on the engine process's main thread before anything there touches WebView. */
    @JvmStatic
    fun initialize(appContext: Context) {
        context = appContext.applicationContext
        // Its own profile, apart from the console's: required before the first WebView in this process.
        if (Build.VERSION.SDK_INT >= 28) runCatching { WebView.setDataDirectorySuffix("agent-browser") }
    }

    @JvmStatic
    fun execute(requestJson: String): String = try {
        check(Looper.myLooper() != Looper.getMainLooper()) { "The browser runs on an engine worker thread" }
        val request = JSONObject(requestJson)
        when (val action = request.optString("action")) {
            "navigate" -> navigate(request.optString("url"), request.optLong("timeout_ms", PAGE_TIMEOUT_MS))
            "open_file" -> openFile(request.optString("root"), request.optString("path"))
            "back" -> back()
            "evaluate" -> evaluate(request.optString("script"), request.optLong("timeout_ms", 10_000L))
            "settle" -> { settle(request.optLong("max_ms", 15_000L)); state() }
            "screenshot" -> screenshot()
            "state" -> state()
            "clear" -> clear()
            "close" -> { close(); JSONObject().put("ok", true) }
            else -> failure("unsupported_action", "Unsupported browser action: $action")
        }.toString()
    } catch (error: Exception) {
        failure("browser_error", error.message ?: error.javaClass.simpleName).toString()
    }

    private fun failure(code: String, message: String): JSONObject =
        JSONObject().put("ok", false).put("error", JSONObject().put("code", code).put("message", message))

    private fun <T> onMain(timeoutMs: Long = 5_000L, block: () -> T): T {
        val task = FutureTask(Callable { block() })
        main.post(task)
        return task.get(timeoutMs, TimeUnit.MILLISECONDS)
    }

    /**
     * Workspace files open on a private https origin served straight from the opened file's folder
     * (never above it), so pages the agent wrote load with their images, scripts and styles.
     */
    private const val FILE_HOST = "workspace.agent-browser.invalid"
    @Volatile private var fileRoot: File? = null

    private fun openFile(root: String, path: String): JSONObject {
        val folder = runCatching { File(root).canonicalFile }.getOrNull()
            ?: return failure("bad_path", "The folder is unavailable")
        val target = runCatching { File(folder, path).canonicalFile }.getOrNull()
        if (target == null || !target.isFile || !target.path.startsWith(folder.path + File.separator)) {
            return failure("bad_path", "The file is not inside the opened folder")
        }
        fileRoot = folder
        val relative = target.path.substring(folder.path.length + 1).split(File.separatorChar)
            .joinToString("/") { Uri.encode(it) }
        return navigate("https://$FILE_HOST/$relative", PAGE_TIMEOUT_MS)
    }

    private fun serveFile(uri: Uri): WebResourceResponse? {
        if (uri.host != FILE_HOST) return null
        val root = fileRoot ?: return notFound()
        val decoded = uri.pathSegments.joinToString(File.separator)
        val file = runCatching { File(root, decoded).canonicalFile }.getOrNull()
        if (file == null || !file.isFile || !file.path.startsWith(root.path + File.separator) || sensitive(file.name)) {
            return notFound()
        }
        val type = android.webkit.MimeTypeMap.getSingleton()
            .getMimeTypeFromExtension(file.extension.lowercase()) ?: when (file.extension.lowercase()) {
                "js", "mjs" -> "text/javascript"
                "json" -> "application/json"
                "svg" -> "image/svg+xml"
                "wasm" -> "application/wasm"
                else -> "application/octet-stream"
            }
        val textual = type.startsWith("text/") || type in setOf("application/json", "image/svg+xml", "text/javascript")
        return WebResourceResponse(type, if (textual) "UTF-8" else null, 200, "OK",
            mapOf("Cache-Control" to "no-store"), file.inputStream())
    }

    private fun sensitive(name: String): Boolean {
        val lower = name.lowercase()
        return lower.startsWith(".env") || lower.endsWith(".key") || lower.endsWith(".pem") ||
            lower.endsWith(".p12") || lower.endsWith(".jks") || lower == "id_rsa" || lower == "id_ed25519"
    }

    private fun notFound() = WebResourceResponse("text/plain", "UTF-8", 404, "Not Found",
        mapOf("Cache-Control" to "no-store"), java.io.ByteArrayInputStream(ByteArray(0)))

    /** http(s) only, and never this app's own engine port. */
    private fun allowed(url: String): Boolean {
        val uri = runCatching { Uri.parse(url) }.getOrNull() ?: return false
        val scheme = uri.scheme?.lowercase()
        if (scheme != "http" && scheme != "https") return false
        val host = uri.host?.lowercase()?.trim('[', ']') ?: return false
        val port = if (uri.port != -1) uri.port else if (scheme == "https") 443 else 80
        val local = host == "localhost" || host == "127.0.0.1" || host == "::1" || host == "0.0.0.0"
        return !(local && port == 8080)
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun webView(): WebView = onMain(15_000L) {
        view ?: run {
            val metrics = context.resources.displayMetrics
            WebView(context).apply {
                setBackgroundColor(Color.WHITE)
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.allowFileAccess = false
                settings.allowContentAccess = false
                settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
                settings.javaScriptCanOpenWindowsAutomatically = false
                settings.setSupportMultipleWindows(false)
                settings.mediaPlaybackRequiresUserGesture = true
                settings.loadWithOverviewMode = true
                settings.useWideViewPort = true
                setLayerType(View.LAYER_TYPE_SOFTWARE, null)
                webViewClient = object : WebViewClient() {
                    override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? =
                        serveFile(request.url)

                    override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                        val target = request.url.toString()
                        if (allowed(target)) return false
                        blocked = target.take(300)
                        return true
                    }

                    override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
                        loading = true
                        mainFrameError = null
                    }

                    override fun onPageFinished(view: WebView, url: String?) {
                        loading = false
                        lastFinished = System.currentTimeMillis()
                    }

                    override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                        if (request.isForMainFrame) mainFrameError = "${error.errorCode}: ${error.description}"
                    }
                }
                webChromeClient = object : WebChromeClient() {
                    // No one is looking at this page: accept alerts, decline confirms and prompts.
                    override fun onJsAlert(view: WebView, url: String?, message: String?, result: JsResult): Boolean {
                        lastDialog = "alert: ${message.orEmpty().take(500)}"
                        result.confirm()
                        return true
                    }

                    override fun onJsConfirm(view: WebView, url: String?, message: String?, result: JsResult): Boolean {
                        lastDialog = "confirm (declined): ${message.orEmpty().take(500)}"
                        result.cancel()
                        return true
                    }

                    override fun onJsPrompt(view: WebView, url: String?, message: String?, defaultValue: String?, result: JsPromptResult): Boolean {
                        lastDialog = "prompt (declined): ${message.orEmpty().take(500)}"
                        result.cancel()
                        return true
                    }
                }
                val width = metrics.widthPixels.coerceIn(320, 1440)
                val height = metrics.heightPixels.coerceIn(480, 3200)
                measure(View.MeasureSpec.makeMeasureSpec(width, View.MeasureSpec.EXACTLY),
                    View.MeasureSpec.makeMeasureSpec(height, View.MeasureSpec.EXACTLY))
                layout(0, 0, width, height)
            }.also { view = it }
        }
    }

    /** Waits for the page to finish loading and stay quiet briefly; returns false on timeout. */
    private fun settle(maxMs: Long): Boolean {
        val deadline = System.currentTimeMillis() + maxMs.coerceIn(100L, PAGE_TIMEOUT_MS)
        while (System.currentTimeMillis() < deadline) {
            val quiet = !loading && System.currentTimeMillis() - lastFinished >= SETTLE_MS
            if (quiet && onMain { view?.progress ?: 100 } >= 100) return true
            Thread.sleep(100)
        }
        return false
    }

    private fun navigate(url: String, timeoutMs: Long): JSONObject {
        if (!allowed(url)) return failure("blocked_url", "Only http and https pages can be opened (not this app's own port)")
        val browser = webView()
        blocked = null
        loading = true
        onMain { browser.loadUrl(url) }
        val finished = settle(timeoutMs)
        return state().put("timed_out", !finished)
    }

    private fun back(): JSONObject {
        val browser = webView()
        val moved = onMain { if (browser.canGoBack()) { browser.goBack(); true } else false }
        if (moved) { loading = true; settle(PAGE_TIMEOUT_MS) }
        return state().put("moved", moved)
    }

    private fun evaluate(script: String, timeoutMs: Long): JSONObject {
        require(script.isNotBlank() && script.length <= 200_000) { "The script is empty or too long" }
        val browser = webView()
        val result = AtomicReference<String?>(null)
        val done = CountDownLatch(1)
        onMain { browser.evaluateJavascript(script) { value -> result.set(value); done.countDown() } }
        if (!done.await(timeoutMs.coerceIn(500L, 30_000L), TimeUnit.MILLISECONDS)) {
            return failure("script_timeout", "The page did not answer in time")
        }
        val raw = result.get() ?: "null"
        if (raw.length > MAX_SCRIPT_RESULT) return failure("result_too_large", "The page returned too much data")
        // evaluateJavascript returns the value as JSON text.
        return state().put("value", raw)
    }

    private fun state(): JSONObject {
        val (url, title, canGoBack) = onMain {
            val browser = view
            Triple(browser?.url.orEmpty(), browser?.title.orEmpty(), browser?.canGoBack() == true)
        }
        return JSONObject().put("ok", true)
            .put("url", url)
            .put("title", title)
            .put("loading", loading)
            .put("can_go_back", canGoBack)
            .apply {
                mainFrameError?.let { put("load_error", it) }
                lastDialog?.let { put("dialog", it); lastDialog = null }
                blocked?.let { put("blocked_navigation", it); blocked = null }
            }
    }

    private fun screenshot(): JSONObject {
        val browser = view ?: return failure("no_page", "Open a page first")
        val bitmap = onMain(10_000L) {
            val image = Bitmap.createBitmap(browser.width, browser.height, Bitmap.Config.ARGB_8888)
            image.eraseColor(Color.WHITE)
            browser.draw(Canvas(image))
            image
        }
        try {
            val factor = minOf(1.0, 1600.0 / maxOf(bitmap.width, bitmap.height))
            val scaled = if (factor < 1.0) Bitmap.createScaledBitmap(bitmap,
                maxOf(1, (bitmap.width * factor).toInt()), maxOf(1, (bitmap.height * factor).toInt()), true) else bitmap
            try {
                val directory = File(context.filesDir, "workspace/automation/screenshots").apply { check(mkdirs() || isDirectory) }
                val name = "browser-${UUID.randomUUID()}.png"
                val output = File(directory, name)
                FileOutputStream(output).use { stream -> check(scaled.compress(Bitmap.CompressFormat.PNG, 100, stream)) }
                directory.listFiles()?.filter { it.name.startsWith("browser-") && it.extension == "png" }
                    ?.sortedByDescending { it.lastModified() }?.drop(20)?.forEach { it.delete() }
                return state().put("screenshot", JSONObject()
                    .put("path", "automation/screenshots/$name")
                    .put("absolute_path", output.absolutePath)
                    .put("media_type", "image/png")
                    .put("width", scaled.width).put("height", scaled.height)
                    .put("blank", uniform(scaled)))
            } finally { if (scaled !== bitmap) scaled.recycle() }
        } finally { bitmap.recycle() }
    }

    /** A one-color image: some phones cannot draw a WebView that is not on screen. */
    private fun uniform(image: Bitmap): Boolean {
        val first = image.getPixel(0, 0)
        for (row in 0 until 64) for (column in 0 until 48) {
            val x = (image.width - 1) * column / 47
            val y = (image.height - 1) * row / 63
            if (image.getPixel(x, y) != first) return false
        }
        return true
    }

    /** Forgets cookies, storage and history, e.g. after signing in somewhere for one task. */
    private fun clear(): JSONObject {
        close()
        onMain {
            CookieManager.getInstance().removeAllCookies(null)
            CookieManager.getInstance().flush()
            WebStorage.getInstance().deleteAllData()
        }
        return JSONObject().put("ok", true)
    }

    private fun close() {
        onMain {
            view?.apply { stopLoading(); loadUrl("about:blank"); clearHistory(); destroy() }
            view = null
        }
        loading = false
    }
}
