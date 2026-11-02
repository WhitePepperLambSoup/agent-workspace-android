package com.agentworkspace.mobile.browser

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.os.Handler
import android.os.Looper
import android.view.View
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.webkit.ScriptHandler
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.agentworkspace.mobile.workspace.WorkspaceHtmlPreviewActivity
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.File
import java.io.FileOutputStream
import java.util.Collections
import java.util.UUID
import java.util.concurrent.Callable
import java.util.concurrent.CountDownLatch
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/**
 * check_page on the phone: an HTML file of the workspace drawn as the user's preview draws it
 * (WorkspaceHtmlPreviewActivity: isolated, offline, inline scripts and styles only), off screen at
 * the phone's size, with what went wrong: console errors and warnings, uncaught exceptions, the
 * resources the preview blocks, and how much of the page shows. Runs on an engine worker thread;
 * its WebView lives on the main thread for the one check.
 */
internal object PageCheck {
    private const val MAX_HTML_BYTES = 32L * 1024 * 1024
    private const val LOAD_MS = 15_000L
    private const val PROBE_MS = 8_000L
    private const val MAX_ITEMS = 30
    private const val MAX_TEXT = 300
    private const val PROBE = "__agent_page_check__"

    // In the page itself (the preview's sandboxed frame): what it shows once it has settled.
    private const val PROBE_SCRIPT = "<script>(() => { const report = () => { try {" +
        " const body = document.body; let visible = 0;" +
        " for (const el of (body ? body.querySelectorAll('*') : [])) { const box = el.getBoundingClientRect();" +
        "  if (box.width > 0 && box.height > 0) visible++; if (visible > 500) break; }" +
        " console.info('$PROBE' + JSON.stringify({ title: document.title || '', text: body ? (body.innerText || '').trim().length : 0," +
        "  visible, height: document.documentElement.scrollHeight, wide: document.documentElement.scrollWidth > innerWidth + 1 }));" +
        " } catch (e) { console.info('$PROBE' + JSON.stringify({ error: String(e) })); } };" +
        " addEventListener('load', () => setTimeout(report, 800)); })();</script>"

    private val main = Handler(Looper.getMainLooper())

    private fun <T> onMain(timeoutMs: Long = 10_000L, block: () -> T): T {
        val task = FutureTask(Callable { block() })
        main.post(task)
        return task.get(timeoutMs, TimeUnit.MILLISECONDS)
    }

    private fun failure(code: String, message: String): JSONObject =
        JSONObject().put("ok", false).put("error", JSONObject().put("code", code).put("message", message))

    @SuppressLint("SetJavaScriptEnabled")
    fun run(context: Context, root: String, path: String): JSONObject {
        check(Looper.myLooper() != Looper.getMainLooper()) { "The page check runs on an engine worker thread" }
        val folder = runCatching { File(root).canonicalFile }.getOrNull()
            ?: return failure("bad_path", "The workspace is unavailable")
        val file = runCatching { File(folder, path).canonicalFile }.getOrNull()
        if (file == null || !file.isFile || !file.path.startsWith(folder.path + File.separator)) {
            return failure("bad_path", "The file is not in the workspace")
        }
        if (file.extension.lowercase() !in setOf("html", "htm")) return failure("not_html", "Only .html files can be checked")
        if (file.length() > MAX_HTML_BYTES) return failure("too_large", "The page is larger than the preview opens")
        val html = file.readText(Charsets.UTF_8)

        val console = Collections.synchronizedList(mutableListOf<JSONObject>())
        val blocked = Collections.synchronizedSet(LinkedHashSet<String>())
        val navigations = Collections.synchronizedSet(LinkedHashSet<String>())
        val probe = AtomicReference<String?>(null)
        val finished = CountDownLatch(1)
        val probed = CountDownLatch(1)
        val metrics = context.resources.displayMetrics
        val width = metrics.widthPixels.coerceIn(320, 1440)
        val height = metrics.heightPixels.coerceIn(480, 3200)
        var view: WebView? = null
        var guard: ScriptHandler? = null
        try {
            val scripts = onMain {
                val browser = WebView(context).apply {
                    setBackgroundColor(Color.WHITE)
                    setLayerType(View.LAYER_TYPE_SOFTWARE, null)
                    settings.apply {
                        domStorageEnabled = false
                        allowFileAccess = false
                        allowContentAccess = false
                        blockNetworkLoads = true
                        cacheMode = WebSettings.LOAD_NO_CACHE
                        javaScriptCanOpenWindowsAutomatically = false
                        setSupportMultipleWindows(false)
                        mediaPlaybackRequiresUserGesture = true
                    }
                    webChromeClient = object : WebChromeClient() {
                        override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                            val text = message.message().orEmpty()
                            if (text.startsWith(PROBE)) {
                                probe.set(text.removePrefix(PROBE))
                                probed.countDown()
                            } else if (console.size < MAX_ITEMS * 2) {
                                val level = when (message.messageLevel()) {
                                    ConsoleMessage.MessageLevel.ERROR -> "error"
                                    ConsoleMessage.MessageLevel.WARNING -> "warning"
                                    else -> null
                                }
                                // The preview's two documents report a refused load each: once is enough.
                                val shown = text.take(MAX_TEXT)
                                if (level != null && synchronized(console) { console.none { it.optString("text") == shown } }) {
                                    console.add(JSONObject().put("level", level).put("text", shown).put("line", message.lineNumber()))
                                }
                            }
                            return true
                        }

                        override fun onPermissionRequest(request: android.webkit.PermissionRequest) = request.deny()
                    }
                    webViewClient = object : WebViewClient() {
                        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                            navigations.add(request.url.toString().take(MAX_TEXT))
                            return true
                        }

                        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                            val scheme = request.url.scheme?.lowercase()
                            if (scheme in setOf("data", "blob", "about")) return null
                            if (blocked.size < MAX_ITEMS) blocked.add(request.url.toString().take(MAX_TEXT))
                            return WebResourceResponse("text/plain", "UTF-8", 403, "Blocked",
                                mapOf("Cache-Control" to "no-store"), ByteArrayInputStream(ByteArray(0)))
                        }

                        override fun onPageFinished(view: WebView, url: String?) { finished.countDown() }
                    }
                    measure(View.MeasureSpec.makeMeasureSpec(width, View.MeasureSpec.EXACTLY),
                        View.MeasureSpec.makeMeasureSpec(height, View.MeasureSpec.EXACTLY))
                    layout(0, 0, width, height)
                }
                view = browser
                // As the preview: scripts run only where the guard can go in before them.
                val canRun = WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT) && runCatching {
                    guard = WebViewCompat.addDocumentStartJavaScript(browser, WorkspaceHtmlPreviewActivity.DOCUMENT_START_GUARD, setOf("*"))
                }.isSuccess
                browser.settings.javaScriptEnabled = canRun
                browser.loadDataWithBaseURL(WorkspaceHtmlPreviewActivity.BASE_ORIGIN,
                    WorkspaceHtmlPreviewActivity.isolatedDocument(PROBE_SCRIPT + html), "text/html", "UTF-8", null)
                canRun
            }
            val loaded = finished.await(LOAD_MS, TimeUnit.MILLISECONDS)
            if (scripts) probed.await(PROBE_MS, TimeUnit.MILLISECONDS) else Thread.sleep(1_000L)
            val browser = checkNotNull(view)
            val image = onMain {
                Bitmap.createBitmap(browser.width, browser.height, Bitmap.Config.ARGB_8888).also {
                    it.eraseColor(Color.WHITE)
                    browser.draw(Canvas(it))
                }
            }
            val screenshot = try { save(context, image) } finally { image.recycle() }
            return JSONObject().put("ok", true)
                .put("file", path)
                .put("viewport", "${width}x$height")
                .put("loaded", loaded)
                .put("scripts_run", scripts)
                .put("page", probe.get()?.let { runCatching { JSONObject(it) }.getOrNull() } ?: JSONObject.NULL)
                .put("console", JSONArray(synchronized(console) { console.take(MAX_ITEMS) }))
                .put("blocked", JSONArray(synchronized(blocked) { blocked.toList() }))
                .put("navigations", JSONArray(synchronized(navigations) { navigations.toList() }))
                .put("screenshot", screenshot)
        } finally {
            runCatching {
                onMain {
                    guard?.remove()
                    view?.apply { stopLoading(); destroy() }
                }
            }
        }
    }

    private fun save(context: Context, image: Bitmap): JSONObject {
        val factor = minOf(1.0, 1600.0 / maxOf(image.width, image.height))
        val scaled = if (factor < 1.0) Bitmap.createScaledBitmap(image,
            maxOf(1, (image.width * factor).toInt()), maxOf(1, (image.height * factor).toInt()), true) else image
        try {
            val directory = File(context.filesDir, "workspace/automation/screenshots").apply { check(mkdirs() || isDirectory) }
            val name = "page-check-${UUID.randomUUID()}.png"
            val output = File(directory, name)
            FileOutputStream(output).use { stream -> check(scaled.compress(Bitmap.CompressFormat.PNG, 100, stream)) }
            directory.listFiles()?.filter { it.name.startsWith("page-check-") && it.extension == "png" }
                ?.sortedByDescending { it.lastModified() }?.drop(20)?.forEach { it.delete() }
            return JSONObject().put("path", "automation/screenshots/$name").put("absolute_path", output.absolutePath)
                .put("media_type", "image/png").put("width", scaled.width).put("height", scaled.height)
        } finally { if (scaled !== image) scaled.recycle() }
    }
}
