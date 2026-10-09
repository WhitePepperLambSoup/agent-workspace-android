package com.agentworkspace.mobile.workspace

import android.annotation.SuppressLint
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.text.TextUtils
import android.view.View
import android.view.Gravity
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.webkit.ScriptHandler
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.security.MessageDigest

/**
 * Runs generated HTML in a deliberately isolated WebView. It receives no
 * JavascriptInterface and its invalid base origin cannot reach the local app.
 */
class WorkspaceHtmlPreviewActivity : ComponentActivity() {
    companion object {
        const val EXTRA_SHA256 = "workspace_html_sha256"
        const val EXTRA_SIZE = "workspace_html_size"
        private const val MAX_HTML_BYTES = 32L * 1024 * 1024
        private const val BASE_ORIGIN = "https://workspace-html.invalid/"
        private const val DOCUMENT_START_GUARD = """
            (() => {
              const blocked = [
                'RTCPeerConnection', 'webkitRTCPeerConnection',
                'RTCDataChannel', 'RTCIceTransport', 'RTCDtlsTransport',
                'RTCSctpTransport', 'RTCRtpSender', 'RTCRtpReceiver',
                'RTCRtpTransceiver', 'Worker', 'SharedWorker', 'WebSocket',
                'EventSource', 'WebTransport'
              ];
              for (const name of blocked) {
                Object.defineProperty(globalThis, name, {
                  value: undefined, writable: false, configurable: false
                });
              }
              Object.defineProperty(globalThis.navigator, 'serviceWorker', {
                value: undefined, writable: false, configurable: false
              });
            })();
        """

        // Generated pages often keep their state in localStorage, which the sandbox's opaque
        // origin rejects with a SecurityError, so a to-do page could not even add an item.
        // Each preview gets in-memory storage that lasts while it is open; nothing reaches the app.
        // tests/html_preview_storage.test.cjs runs this script (between the markers).
        internal const val STORAGE_SHIM = /* storage-shim-start */ """
            (() => {
              const storage = () => {
                const items = new Map();
                const api = {
                  get length() { return items.size; },
                  key(index) { const keys = Array.from(items.keys()); return index >= 0 && index < keys.length ? keys[index] : null; },
                  getItem(key) { key = String(key); return items.has(key) ? items.get(key) : null; },
                  setItem(key, value) { items.set(String(key), String(value)); },
                  removeItem(key) { items.delete(String(key)); },
                  clear() { items.clear(); }
                };
                return new Proxy(api, {
                  get(target, name, receiver) {
                    if (typeof name === 'symbol' || name in target) return Reflect.get(target, name, receiver);
                    return items.has(name) ? items.get(name) : undefined;
                  },
                  set(target, name, value) {
                    if (typeof name === 'symbol' || name in target) return false;
                    target.setItem(name, value);
                    return true;
                  },
                  deleteProperty(target, name) { if (typeof name !== 'symbol') target.removeItem(name); return true; },
                  has(target, name) { return name in target || items.has(String(name)); },
                  ownKeys() { return Array.from(items.keys()); },
                  getOwnPropertyDescriptor(target, name) {
                    return typeof name !== 'symbol' && items.has(name)
                      ? { value: items.get(name), writable: true, enumerable: true, configurable: true }
                      : undefined;
                  }
                });
              };
              for (const name of ['localStorage', 'sessionStorage']) {
                try { Object.defineProperty(window, name, { value: storage(), configurable: true }); } catch (e) {}
              }
            })();
        """ /* storage-shim-end */
    }

    private lateinit var webView: WebView
    private lateinit var status: TextView
    private var documentStartScript: ScriptHandler? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val container = FrameLayout(this).apply { setBackgroundColor(Color.WHITE) }
        status = TextView(this).apply {
            text = "Loading preview..."
            setTextColor(Color.DKGRAY)
            setPadding(32, 32, 32, 32)
        }
        container.addView(status, FrameLayout.LayoutParams(-1, -1))
        webView = WebView(this).apply {
            visibility = View.INVISIBLE
            settings.apply {
                javaScriptEnabled = false
                domStorageEnabled = false
                allowFileAccess = false
                allowContentAccess = false
                // File-URL cross access stays at its secure default (off); the page never loads from file URLs.
                blockNetworkLoads = true
                cacheMode = WebSettings.LOAD_NO_CACHE
                javaScriptCanOpenWindowsAutomatically = false
                setSupportMultipleWindows(false)
            }
            webChromeClient = object : WebChromeClient() {
                override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                    if (message.messageLevel() == ConsoleMessage.MessageLevel.ERROR) {
                        android.util.Log.w("WorkspaceHtmlPreview", "${message.message()} @${message.lineNumber()}")
                        status.text = "Preview error: " + message.message().take(240)
                        status.layoutParams = FrameLayout.LayoutParams(-1, -2, Gravity.BOTTOM)
                        status.setBackgroundColor(Color.WHITE)
                        status.visibility = View.VISIBLE
                        status.bringToFront()
                    }
                    return true
                }

                override fun onPermissionRequest(request: android.webkit.PermissionRequest) {
                    request.deny()
                }

                override fun onGeolocationPermissionsShowPrompt(origin: String?, callback: android.webkit.GeolocationPermissions.Callback?) {
                    callback?.invoke(origin, false, false)
                }
            }
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                    return true
                }

                @Suppress("DEPRECATION")
                override fun shouldOverrideUrlLoading(view: WebView?, url: String?): Boolean {
                    return true
                }

                override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse? =
                    blockedResource(request?.url)

                @Suppress("DEPRECATION")
                override fun shouldInterceptRequest(view: WebView?, url: String?): WebResourceResponse? =
                    blockedResource(Uri.parse(url.orEmpty()))
            }
        }
        container.addView(webView, FrameLayout.LayoutParams(-1, -1))
        setContentView(container)
        webView.settings.javaScriptEnabled = enableInteractiveJavaScript()
        loadPreview(intent?.data, intent?.getStringExtra(EXTRA_SHA256), intent?.getLongExtra(EXTRA_SIZE, -1L) ?: -1L)
    }

    private fun enableInteractiveJavaScript(): Boolean {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) return false
        return runCatching {
            documentStartScript = WebViewCompat.addDocumentStartJavaScript(webView,
                DOCUMENT_START_GUARD, setOf("*"))
            true
        }.getOrElse { false }
    }

    private fun blockedResource(uri: Uri?): WebResourceResponse? {
        val scheme = uri?.scheme?.lowercase()
        if (scheme in setOf("data", "blob", "about")) return null
        return WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", mapOf("Cache-Control" to "no-store"),
            ByteArrayInputStream(ByteArray(0)))
    }

    private fun loadPreview(uri: Uri?, expectedSha: String?, expectedSize: Long) {
        if (uri == null || expectedSha == null || !Regex("[a-f0-9]{64}").matches(expectedSha) ||
            expectedSize !in 0..MAX_HTML_BYTES || uri.scheme != "content") {
            fail("This HTML preview is unavailable")
            return
        }
        lifecycleScope.launch {
            try {
                val html = withContext(Dispatchers.IO) {
                    val file = WorkspaceFileCache.uriFile(this@WorkspaceHtmlPreviewActivity, uri)
                    check(file.length() == expectedSize) { "The generated HTML changed" }
                    val bytes = contentResolver.openInputStream(uri)?.use { input ->
                        val output = ByteArrayOutputStream()
                        val buffer = ByteArray(65536)
                        var size = 0L
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            size += count
                            check(size <= expectedSize && size <= MAX_HTML_BYTES) { "The generated HTML changed" }
                            output.write(buffer, 0, count)
                        }
                        val value = output.toByteArray()
                        check(value.size.toLong() == expectedSize) { "The generated HTML changed" }
                        value
                    } ?: throw IOException("The generated HTML could not be read")
                    check(MessageDigest.getInstance("SHA-256").digest(bytes).hex() == expectedSha) {
                        "The generated HTML changed"
                    }
                    bytes.toString(Charsets.UTF_8)
                }
                if (isFinishing || isDestroyed) return@launch
                if (webView.settings.javaScriptEnabled) status.visibility = View.GONE
                else {
                    status.text = "Static preview: this WebView cannot safely run interactive HTML"
                    status.layoutParams = FrameLayout.LayoutParams(-1, -2, Gravity.BOTTOM)
                    status.setBackgroundColor(Color.WHITE)
                    status.visibility = View.VISIBLE
                    status.bringToFront()
                }
                webView.visibility = View.VISIBLE
                webView.loadDataWithBaseURL(BASE_ORIGIN, isolatedDocument(html), "text/html", "UTF-8", null)
            } catch (failure: Exception) {
                if (!isFinishing && !isDestroyed) fail("Unable to open this HTML preview")
            }
        }
    }

    private fun fail(message: String) {
        status.text = message
        status.visibility = View.VISIBLE
        if (::webView.isInitialized) webView.visibility = View.INVISIBLE
    }

    private fun isolatedDocument(html: String): String {
        // The opaque sandbox origin keeps generated scripts away from the parent
        // and fresh child realms; the child policy is parsed before generated tags.
        val policy = "default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' data: blob:; " +
            "style-src 'unsafe-inline' data: blob:; img-src data: blob:; font-src data: blob:; " +
            "media-src data: blob:; connect-src 'none'; object-src 'none'; " +
            "worker-src 'none'; form-action 'none'; base-uri 'none'"
        val isolation = "<meta http-equiv=\"Content-Security-Policy\" content=\"$policy; frame-src 'none'\">" +
            "<script>for(const name of ['RTCPeerConnection','webkitRTCPeerConnection']){" +
            "try{Object.defineProperty(window,name,{value:undefined,writable:false,configurable:false});}catch(e){}}" +
            "</script><script>$STORAGE_SHIM</script>"
        val document = TextUtils.htmlEncode("<!doctype html>$isolation$html")
        return "<!doctype html><html><head><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" +
            "<meta http-equiv=\"Content-Security-Policy\" content=\"$policy; frame-src 'self' about:\">" +
            "<style>html,body{margin:0;width:100%;height:100%;overflow:hidden}" +
            "iframe{display:block;border:0;width:100%;height:100%}</style></head><body>" +
            "<iframe title=\"HTML preview\" sandbox=\"allow-scripts\" referrerpolicy=\"no-referrer\" srcdoc=\"$document\"></iframe>" +
            "</body></html>"
    }

    override fun onDestroy() {
        documentStartScript?.remove()
        documentStartScript = null
        if (::webView.isInitialized) {
            webView.stopLoading()
            webView.destroy()
        }
        super.onDestroy()
    }
}

private fun ByteArray.hex(): String = joinToString("") { "%02x".format(it) }
