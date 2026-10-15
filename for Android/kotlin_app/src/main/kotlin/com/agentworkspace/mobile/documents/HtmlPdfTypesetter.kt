package com.agentworkspace.mobile.documents

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Color
import android.os.CancellationSignal
import android.os.Handler
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.os.SystemClock
import android.print.AgentPdfPrint
import android.print.PrintAttributes
import android.view.View
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import org.json.JSONObject
import org.json.JSONTokener
import java.io.ByteArrayInputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/**
 * Typesets Markdown or a LaTeX document (math by KaTeX) into a vector A4 PDF: an invisible WebView
 * renders the app's own page (assets/web/pdf/typeset.html) and Android's printing writes it out.
 * Phones have no TeX installation; this is how create_pdf still prints formulas properly.
 *
 * The page loads only from the app's assets on a private https origin: every other request,
 * including any address written in the document, gets nothing.
 */
internal object HtmlPdfTypesetter {
    private const val HOST = "typeset.agent-pdf.invalid"
    private val main = Handler(Looper.getMainLooper())

    class Failure(message: String) : RuntimeException(message)

    /**
     * Blocks a worker thread until [request] (format, title, content, font_size) is printed into
     * [output] (closed afterwards). Returns the page's report, such as how many formulas failed.
     */
    fun typeset(context: Context, request: JSONObject, output: ParcelFileDescriptor, timeoutMs: Long): JSONObject {
        check(Looper.myLooper() != Looper.getMainLooper()) { "Typesetting waits for the main thread" }
        val view = AtomicReference<WebView?>()
        val deadline = SystemClock.elapsedRealtime() + timeoutMs
        val cancel = CancellationSignal()
        try {
            onMain(10_000) { view.set(createView(context, request.toString())) }
            // The page reports when the document is in and its fonts have loaded.
            var report: JSONObject? = null
            while (report == null) {
                if (SystemClock.elapsedRealtime() > deadline) throw Failure("Typesetting timed out")
                if (Thread.currentThread().isInterrupted) throw InterruptedException()
                Thread.sleep(150)
                val state = AtomicReference<String?>()
                val read = CountDownLatch(1)
                main.post {
                    val current = view.get()
                    if (current == null) read.countDown()
                    else current.evaluateJavascript("JSON.stringify(window.__pdfState || null)") { value -> state.set(value); read.countDown() }
                }
                read.await(5, TimeUnit.SECONDS)
                val decoded = state.get()?.let { runCatching { JSONTokener(it).nextValue() }.getOrNull() }
                if (decoded is String && decoded != "null") report = JSONObject(decoded)
            }
            android.util.Log.i("PdfTypeset", "page report: ${report.toString().take(600)}")
            if (!report.optBoolean("ok")) throw Failure("The document could not be typeset: ${report.optString("error").take(300)}")
            val printed = CountDownLatch(1)
            val failure = AtomicReference<String?>()
            main.post {
                val current = view.get()
                if (current == null) { failure.set("The page closed"); printed.countDown(); return@post }
                val attributes = PrintAttributes.Builder()
                    .setMediaSize(PrintAttributes.MediaSize.ISO_A4)
                    .setResolution(PrintAttributes.Resolution("pdf", "pdf", 600, 600))
                    .setColorMode(PrintAttributes.COLOR_MODE_COLOR)
                    // The page's own @page margins apply.
                    .setMinMargins(PrintAttributes.Margins.NO_MARGINS)
                    .build()
                AgentPdfPrint.write(current.createPrintDocumentAdapter("document"), attributes, output, cancel) { error ->
                    failure.set(error)
                    printed.countDown()
                }
            }
            val remaining = deadline - SystemClock.elapsedRealtime()
            if (!printed.await(remaining.coerceAtLeast(1), TimeUnit.MILLISECONDS)) {
                cancel.cancel()
                throw Failure("Printing the PDF timed out")
            }
            failure.get()?.let { throw Failure("Printing the PDF failed: ${it.take(300)}") }
            return report
        } finally {
            runCatching { output.close() }
            main.post { view.getAndSet(null)?.destroy() }
        }
    }

    private fun <T> onMain(timeoutMs: Long, block: () -> T): T {
        val result = AtomicReference<Result<T>>()
        val done = CountDownLatch(1)
        main.post { result.set(runCatching(block)); done.countDown() }
        if (!done.await(timeoutMs, TimeUnit.MILLISECONDS)) throw Failure("The main thread did not answer")
        return result.get().getOrThrow()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun createView(context: Context, document: String): WebView = WebView(context).apply {
        setBackgroundColor(Color.WHITE)
        settings.javaScriptEnabled = true
        settings.allowFileAccess = false
        settings.allowContentAccess = false
        settings.domStorageEnabled = false
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
        settings.javaScriptCanOpenWindowsAutomatically = false
        settings.setSupportMultipleWindows(false)
        settings.useWideViewPort = true
        settings.loadWithOverviewMode = false
        settings.textZoom = 100
        webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse =
                serve(context, request, document)

            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean = true
        }
        val metrics = context.resources.displayMetrics
        val width = (800 * metrics.density).toInt()
        measure(View.MeasureSpec.makeMeasureSpec(width, View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec(width * 3 / 2, View.MeasureSpec.EXACTLY))
        layout(0, 0, width, width * 3 / 2)
        loadUrl("https://$HOST/pdf/typeset.html")
    }

    /** The page, its script, styles and fonts from the app's assets, and the document itself; nothing else. */
    private fun serve(context: Context, request: WebResourceRequest, document: String): WebResourceResponse {
        val uri = request.url
        val path = uri.path.orEmpty().trimStart('/')
        if (uri.scheme != "https" || uri.host != HOST || request.method != "GET" || ".." in path) return missing()
        if (path == "pdf/document.json") {
            return WebResourceResponse("application/json", "UTF-8", 200, "OK", mapOf("Cache-Control" to "no-store"),
                ByteArrayInputStream(document.toByteArray(Charsets.UTF_8)))
        }
        val allowed = path == "pdf/typeset.html" || path == "pdf/typeset.js" || path == "pdf/katex.min.css" ||
            path == "static/mobile-vendor.js" || (path.startsWith("pdf/fonts/") && path.endsWith(".woff2") && path.count { it == '/' } == 2)
        if (!allowed) return missing()
        val type = when (path.substringAfterLast('.')) {
            "html" -> "text/html"
            "js" -> "text/javascript"
            "css" -> "text/css"
            else -> "font/woff2"
        }
        return runCatching {
            WebResourceResponse(type, if (type == "font/woff2") null else "UTF-8", 200, "OK",
                mapOf("Cache-Control" to "no-store"), context.assets.open("web/$path"))
        }.getOrElse { error ->
            android.util.Log.w("PdfTypeset", "asset $path: $error")
            missing()
        }
    }

    private fun missing() = WebResourceResponse("text/plain", "UTF-8", 404, "Not Found",
        mapOf("Cache-Control" to "no-store"), ByteArrayInputStream(ByteArray(0)))
}
