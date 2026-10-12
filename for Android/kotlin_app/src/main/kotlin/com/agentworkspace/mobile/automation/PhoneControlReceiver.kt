package com.agentworkspace.mobile.automation

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.widget.Toast
import com.agentworkspace.mobile.UiText

/**
 * The floating bubble (main process) opens the phone control panel here, in :engine, where the
 * accessibility service that owns the panel runs.
 */
class PhoneControlReceiver : BroadcastReceiver() {
    companion object {
        const val ACTION_OPEN = "com.agentworkspace.mobile.action.OPEN_PHONE_PANEL"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION_OPEN) return
        val service = AndroidSystemBridge.service
        android.util.Log.i("PhoneControlPanel", "Open requested; accessibility service connected: ${service != null}")
        if (service == null) {
            // Turned on in settings but not connected: Android stops a service whose process ended
            // unexpectedly (the engine was restarted) until it is switched off and on again.
            val switchedOn = android.provider.Settings.Secure.getString(context.contentResolver,
                android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES).orEmpty()
                .split(':').any { it.endsWith("/com.agentworkspace.mobile.automation.AgentAccessibilityService") ||
                    it.endsWith("/.automation.AgentAccessibilityService") }
            Toast.makeText(context, if (switchedOn) UiText.of(context, "系统暂停了 Agent Workspace 的无障碍服务：请在列表里把它关掉再打开",
                    "Android paused the Agent Workspace accessibility service: switch it off and on again in the list")
                else UiText.of(context, "请先在系统设置里开启 Agent Workspace 的无障碍服务",
                    "Turn on the Agent Workspace accessibility service in system settings first"), Toast.LENGTH_LONG).show()
            AndroidSystemBridge.openAccessibilitySettings(context)
            context.sendBroadcast(Intent(PhoneControlPanel.ACTION_PANEL_CLOSED).setPackage(context.packageName))
            return
        }
        service.openControlPanel()
    }
}
