package com.agentworkspace.mobile

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import android.webkit.WebView

/**
 * The console is a web page, so the phone's WebView sets the floor: its scripts use optional
 * chaining (`?.`, `??`), which needs Chromium 80 or newer. Phones that never received WebView
 * updates (common without Google Play) can be older, and some ROMs ship it disabled.
 */
object WebViewSupport {
    const val MIN_CHROMIUM = 80
    private const val DEFAULT_PROVIDER = "com.google.android.webview"
    private val CHROMIUM_VERSION = Regex("""Chrome/(\d+)""")

    fun chromiumMajor(userAgent: String?): Int? =
        userAgent?.let { CHROMIUM_VERSION.find(it)?.groupValues?.get(1)?.toIntOrNull() }

    /** The package that provides WebView on this phone (Google, a vendor build, or Chrome itself). */
    fun providerPackage(): String? = runCatching { WebView.getCurrentWebViewPackage()?.packageName }.getOrNull()

    /**
     * Open somewhere the user can update or enable WebView: the app store page (market:// is also
     * handled by vendor stores such as Xiaomi, Huawei, OPPO and vivo), then Google Play on the web,
     * then the system app settings page where a disabled WebView can be turned back on.
     */
    fun openUpdate(context: Context, provider: String? = providerPackage()) {
        val target = provider ?: DEFAULT_PROVIDER
        val candidates = listOf(
            Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=$target")),
            Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=$target")),
            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$target")),
            Intent(Settings.ACTION_MANAGE_APPLICATIONS_SETTINGS),
        )
        for (intent in candidates) {
            try {
                context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                return
            } catch (_: ActivityNotFoundException) {
            } catch (_: SecurityException) {
            }
        }
    }
}
