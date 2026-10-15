package com.agentworkspace.mobile

import android.app.Activity
import android.app.KeyguardManager
import android.content.Context
import android.hardware.biometrics.BiometricManager
import android.hardware.biometrics.BiometricPrompt
import android.os.Build
import android.os.CancellationSignal
import android.os.SystemClock
import org.json.JSONObject

/**
 * The app lock the user can turn on: conversations, memory and API settings are all on this
 * phone, so opening the app again after a while asks for the fingerprint, face or the screen lock
 * (Android 9+, the system's own prompt). Off by default.
 */
object AppLock {
    private const val PREFS = "app_lock"
    private val DELAYS = listOf(0, 1, 5)

    fun available(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < 28) return false
        if (Build.VERSION.SDK_INT >= 30) {
            val manager = context.getSystemService(BiometricManager::class.java) ?: return false
            return manager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_WEAK or
                BiometricManager.Authenticators.DEVICE_CREDENTIAL) == BiometricManager.BIOMETRIC_SUCCESS
        }
        return context.getSystemService(KeyguardManager::class.java)?.isDeviceSecure == true
    }

    fun enabled(context: Context): Boolean =
        available(context) && context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean("enabled", false)

    /** Minutes away from the app before it locks again (0: every time). */
    fun delayMinutes(context: Context): Int =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getInt("delay_minutes", 1).takeIf { it in DELAYS } ?: 1

    fun state(context: Context): String = JSONObject()
        .put("available", available(context))
        .put("enabled", enabled(context))
        .put("delay_minutes", delayMinutes(context))
        .put("minimum_android", 9).toString()

    fun save(context: Context, enabled: Boolean, delayMinutes: Int) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putBoolean("enabled", enabled)
            .putInt("delay_minutes", delayMinutes.takeIf { it in DELAYS } ?: 1).apply()
    }

    /** Whether coming back now needs unlocking: [leftAt] is when the app was last left (elapsed time). */
    fun due(context: Context, leftAt: Long?): Boolean {
        if (!enabled(context)) return false
        if (leftAt == null) return true
        return SystemClock.elapsedRealtime() - leftAt >= delayMinutes(context) * 60_000L
    }

    /** The system prompt; [done] gets true once the user is through, false if they cancel or fail. */
    fun authenticate(activity: Activity, done: (Boolean) -> Unit) {
        if (Build.VERSION.SDK_INT < 28) { done(true); return }
        val builder = BiometricPrompt.Builder(activity)
            .setTitle(UiText.of(activity, "解锁 Agent Workspace", "Unlock Agent Workspace"))
            .setSubtitle(UiText.of(activity, "验证指纹、面容或锁屏密码", "Use your fingerprint, face or screen lock"))
        if (Build.VERSION.SDK_INT >= 30) {
            builder.setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_WEAK or
                BiometricManager.Authenticators.DEVICE_CREDENTIAL)
        } else {
            @Suppress("DEPRECATION")
            builder.setDeviceCredentialAllowed(true)
        }
        builder.build().authenticate(CancellationSignal(), activity.mainExecutor, object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult?) = done(true)
            override fun onAuthenticationError(errorCode: Int, errString: CharSequence?) = done(false)
        })
    }
}
