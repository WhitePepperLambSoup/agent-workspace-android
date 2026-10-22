package com.agentworkspace.mobile.workspace

import android.annotation.SuppressLint
import android.app.ActivityManager
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.lifecycle.lifecycleScope
import androidx.webkit.ScriptHandler
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.agentworkspace.mobile.UiText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayInputStream

/**
 * A home-screen tool (HomeTools), opened from its shortcut as an app of its own in the recent apps.
 * It runs as the HTML preview does: no bridge to the app, nothing from the network, no workers or
 * peer connections. Unlike the preview, each tool has an origin of its own, so its localStorage lasts.
 */
class ToolActivity : ComponentActivity() {
    private lateinit var webView: WebView
    private lateinit var status: TextView
    private var guard: ScriptHandler? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val container = FrameLayout(this).apply { setBackgroundColor(Color.WHITE) }
        status = TextView(this).apply {
            setTextColor(Color.DKGRAY)
            setPadding(48, 48, 48, 48)
            gravity = Gravity.CENTER
            visibility = View.GONE
        }
        webView = WebView(this).apply {
            settings.apply {
                javaScriptEnabled = false
                domStorageEnabled = true
                allowFileAccess = false
                allowContentAccess = false
                blockNetworkLoads = true
                cacheMode = WebSettings.LOAD_NO_CACHE
                javaScriptCanOpenWindowsAutomatically = false
                setSupportMultipleWindows(false)
            }
            webChromeClient = object : WebChromeClient() {
                override fun onPermissionRequest(request: android.webkit.PermissionRequest) = request.deny()
                override fun onGeolocationPermissionsShowPrompt(origin: String?, callback: android.webkit.GeolocationPermissions.Callback?) {
                    callback?.invoke(origin, false, false)
                }
            }
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?) = true
                @Deprecated("Deprecated in Java")
                override fun shouldOverrideUrlLoading(view: WebView?, url: String?) = true
                override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?) = blocked(request?.url)
                @Deprecated("Deprecated in Java")
                override fun shouldInterceptRequest(view: WebView?, url: String?) = blocked(Uri.parse(url.orEmpty()))
            }
        }
        container.addView(webView, FrameLayout.LayoutParams(-1, -1))
        container.addView(status, FrameLayout.LayoutParams(-1, -1))
        setContentView(container)
        open(HomeTools.validId(intent?.data?.host))
    }

    private fun open(id: String?) {
        val tool = id?.let { HomeTools.get(this, it) }
        if (tool == null) {
            fail(UiText.of(this, "这个小工具已经删除了", "This tool has been removed"))
            return
        }
        title = tool.name
        @Suppress("DEPRECATION")
        setTaskDescription(ActivityManager.TaskDescription(tool.name))
        // The guard has to run before the page's own scripts; without it the page stays off.
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT) || runCatching {
                guard = WebViewCompat.addDocumentStartJavaScript(webView, GUARD, setOf(HomeTools.origin(tool.id)))
            }.isFailure) {
            fail(UiText.of(this, "这台手机的 WebView 版本太旧，不能安全地运行小工具", "This phone's WebView is too old to run tools safely"))
            return
        }
        webView.settings.javaScriptEnabled = true
        lifecycleScope.launch {
            val html = withContext(Dispatchers.IO) { runCatching { HomeTools.page(this@ToolActivity, tool.id).readText() }.getOrNull() }
            if (isFinishing || isDestroyed) return@launch
            if (html == null) { fail(UiText.of(this@ToolActivity, "读不到这个小工具", "This tool could not be read")); return@launch }
            webView.loadDataWithBaseURL(HomeTools.origin(tool.id) + "/", withPolicy(html), "text/html", "UTF-8", null)
        }
    }

    /** The page with the policy first in it, after its doctype (before it, the page would lose standards mode). */
    private fun withPolicy(html: String): String {
        val head = "<meta http-equiv=\"Content-Security-Policy\" content=\"$POLICY\">" +
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        val doctype = Regex("^\\uFEFF?\\s*<!doctype[^>]*>", RegexOption.IGNORE_CASE).find(html)
            ?: return "<!doctype html>$head$html"
        return html.substring(0, doctype.range.last + 1) + head + html.substring(doctype.range.last + 1)
    }

    private fun blocked(uri: Uri?): WebResourceResponse? {
        if (uri?.scheme?.lowercase() in setOf("data", "blob", "about")) return null
        return WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", mapOf("Cache-Control" to "no-store"),
            ByteArrayInputStream(ByteArray(0)))
    }

    private fun fail(message: String) {
        status.text = message
        status.visibility = View.VISIBLE
        webView.visibility = View.INVISIBLE
    }

    override fun onDestroy() {
        guard?.remove()
        guard = null
        webView.stopLoading()
        webView.destroy()
        super.onDestroy()
    }

    companion object {
        private const val POLICY = "default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' data: blob:; " +
            "style-src 'unsafe-inline' data: blob:; img-src data: blob:; font-src data: blob:; media-src data: blob:; " +
            "connect-src 'none'; object-src 'none'; worker-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'"
        private const val GUARD = """
            (() => {
              const blocked = ['RTCPeerConnection', 'webkitRTCPeerConnection', 'RTCDataChannel', 'RTCIceTransport',
                'RTCDtlsTransport', 'RTCSctpTransport', 'RTCRtpSender', 'RTCRtpReceiver', 'RTCRtpTransceiver',
                'Worker', 'SharedWorker', 'WebSocket', 'EventSource', 'WebTransport'];
              for (const name of blocked) {
                Object.defineProperty(globalThis, name, { value: undefined, writable: false, configurable: false });
              }
              Object.defineProperty(globalThis.navigator, 'serviceWorker', { value: undefined, writable: false, configurable: false });
            })();
        """
    }
}
