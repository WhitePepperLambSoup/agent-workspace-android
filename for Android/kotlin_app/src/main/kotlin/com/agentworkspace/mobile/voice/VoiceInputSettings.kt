package com.agentworkspace.mobile.voice

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import org.json.JSONObject

/** Which recognizer the microphone button uses (Local models page → offline speech recognition). */
object VoiceInputSettings {
    private const val PREFERENCES = "agent-voice-input"
    private const val PREFER_OFFLINE = "prefer_offline"

    /** On by default: once the model is downloaded, voice input stays on the phone. */
    fun preferOffline(context: Context): Boolean =
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).getBoolean(PREFER_OFFLINE, true)

    fun setPreferOffline(context: Context, value: Boolean) {
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit().putBoolean(PREFER_OFFLINE, value).apply()
    }

    fun useOffline(context: Context): Boolean =
        preferOffline(context) && OfflineSpeech.runtimeAvailable(context) && OfflineSpeech.modelFile(context) != null

    fun json(context: Context): JSONObject = OfflineSpeech.status(context)
        .put("ok", true)
        .put("prefer_offline", preferOffline(context))
        .put("uses_offline", useOffline(context))
        .put("system_available", MobileVoiceInput.isAvailable(context))
        .put("microphone_granted", context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED)
}
