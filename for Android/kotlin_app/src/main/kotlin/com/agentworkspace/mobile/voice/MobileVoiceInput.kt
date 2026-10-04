package com.agentworkspace.mobile.voice

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.speech.RecognizerIntent

/** Uses an external recognizer; the app receives a draft without recording audio itself. */
object MobileVoiceInput {
    const val EXTRA_VOICE_INPUT = "voice_input"

    @JvmStatic
    fun recognizerIntent(): Intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
        .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)

    @JvmStatic
    fun isAvailable(context: Context): Boolean = recognizerIntent().resolveActivity(context.packageManager) != null

    @JvmStatic
    fun draftFromResult(resultCode: Int, data: Intent?): String? {
        if (resultCode != Activity.RESULT_OK) return null
        return data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()
            ?.trim()?.take(32768)?.takeIf { it.isNotEmpty() }
    }

    @JvmStatic
    fun requestedBy(intent: Intent?): Boolean = intent?.getBooleanExtra(EXTRA_VOICE_INPUT, false) == true ||
        intent?.action == Intent.ACTION_ASSIST || intent?.action == Intent.ACTION_VOICE_COMMAND
}
