package com.agentworkspace.mobile.capabilities

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import org.json.JSONObject
import org.json.JSONArray
import java.util.Locale

/** Android speech engine hosted in the same process as embedded Python. */
object AndroidTextToSpeech {
    private val mainHandler = Handler(Looper.getMainLooper())
    private val lock = Any()
    private var engine: TextToSpeech? = null
    private var initialized = false
    private var ready = false
    private var reason = "Android TTS has not been initialized"
    private var activeUtterance: String? = null
    private var generation = 0L
    private var selectedLocale: String? = null
    private var selectedVoice: String? = null
    private var voiceLocale: String? = null
    private var networkRequired: Boolean? = null
    private var voiceFeatures = emptySet<String>()
    private var lastError: JSONObject? = null
    private val utterances = LinkedHashMap<String, Pair<String, String?>>()

    @JvmStatic
    fun initialize(context: Context) {
        val initializingGeneration = synchronized(lock) {
            if (initialized) return
            initialized = true
            ready = false
            reason = "Android TTS is initializing"
            selectedLocale = Locale.getDefault().toLanguageTag()
            selectedVoice = null
            voiceLocale = null
            networkRequired = null
            voiceFeatures = emptySet()
            lastError = null
            ++generation
        }
        mainHandler.post {
            synchronized(lock) {
                if (!initialized || generation != initializingGeneration) return@post
            }
            val created = TextToSpeech(context.applicationContext) { status ->
                mainHandler.post {
                    synchronized(lock) {
                        val current = engine
                        if (!initialized || current == null || generation != initializingGeneration) return@synchronized
                        if (status != TextToSpeech.SUCCESS || current.engines.isEmpty()) {
                            ready = false
                            reason = "Install or enable an Android text-to-speech engine"
                            return@synchronized
                        }
                        val language = current.setLanguage(Locale.getDefault())
                        val voice = current.voice
                        selectedVoice = voice?.name
                        voiceLocale = voice?.locale?.toLanguageTag()
                        networkRequired = voice?.isNetworkConnectionRequired
                        voiceFeatures = voice?.features?.toSet() ?: emptySet()
                        if (language == TextToSpeech.LANG_MISSING_DATA || language == TextToSpeech.LANG_NOT_SUPPORTED) {
                            ready = false
                            reason = "Install voice data for the device language in Android TTS settings"
                            return@synchronized
                        }
                        ready = true
                        reason = ""
                    }
                }
            }
            synchronized(lock) {
                if (!initialized || generation != initializingGeneration) {
                    created.shutdown()
                    return@post
                }
                engine = created
            }
            created.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) = update(initializingGeneration, utteranceId, "speaking", null)
                override fun onDone(utteranceId: String?) = update(initializingGeneration, utteranceId, "completed", null)
                @Suppress("DEPRECATION")
                override fun onError(utteranceId: String?) = update(initializingGeneration, utteranceId, "failed", "Android TTS engine failed")
                override fun onError(utteranceId: String?, errorCode: Int) = update(initializingGeneration,
                    utteranceId, "failed", "Android TTS error $errorCode", errorCode)
                override fun onStop(utteranceId: String?, interrupted: Boolean) = update(initializingGeneration,
                    utteranceId, "cancelled", "Speech was stopped")
            })
        }
    }

    private fun update(sourceGeneration: Long, requestId: String?, state: String, error: String?, errorCode: Int? = null) {
        if (requestId == null) return
        synchronized(lock) {
            if (generation != sourceGeneration || utterances[requestId]?.first !in setOf("pending", "speaking")) return
            utterances[requestId] = state to error
            if (state == "failed") lastError = JSONObject().put("code", errorCode ?: JSONObject.NULL)
                .put("message", error ?: "Android TTS engine failed").put("at_ms", System.currentTimeMillis())
            if (state != "speaking" && activeUtterance == requestId) activeUtterance = null
        }
    }

    @JvmStatic
    fun getStatusJson(): String = synchronized(lock) {
        JSONObject().put("initialized", initialized).put("ready", ready)
            .put("reason", if (ready) JSONObject.NULL else reason)
            .put("engine", engine?.defaultEngine ?: JSONObject.NULL)
            .put("locale", selectedLocale ?: JSONObject.NULL)
            .put("voice", selectedVoice ?: JSONObject.NULL).put("voice_locale", voiceLocale ?: JSONObject.NULL)
            .put("network_required", networkRequired ?: JSONObject.NULL)
            .put("features", JSONArray(voiceFeatures.sorted()))
            .put("last_error", lastError ?: JSONObject.NULL).toString()
    }

    @JvmStatic fun diagnosticString(): String = getStatusJson()

    @JvmStatic
    fun startSpeak(requestId: String, text: String): String {
        val speakingGeneration = synchronized(lock) {
            if (!ready || engine == null) return JSONObject().put("accepted", false).put("reason", reason).toString()
            if (!requestId.matches(Regex("[a-zA-Z0-9-]{1,64}")) || text.isEmpty() || text.length > 2000 || text.contains('\u0000')) {
                return JSONObject().put("accepted", false).put("reason", "Invalid bounded speech request").toString()
            }
            if (activeUtterance != null) return JSONObject().put("accepted", false).put("reason", "Android speech is already in progress").toString()
            while (utterances.size >= 64) utterances.remove(utterances.keys.first())
            utterances[requestId] = "pending" to null
            activeUtterance = requestId
            generation
        }
        mainHandler.post {
            synchronized(lock) {
                if (generation != speakingGeneration || activeUtterance != requestId) return@synchronized
                val result = engine?.speak(text, TextToSpeech.QUEUE_FLUSH, null, requestId)
                if (result != TextToSpeech.SUCCESS) update(speakingGeneration, requestId,
                    "failed", "Android TTS could not start speech", result)
            }
        }
        return JSONObject().put("accepted", true).toString()
    }

    @JvmStatic
    fun getUtteranceStatus(requestId: String): String = synchronized(lock) {
        val status = utterances[requestId] ?: ("unknown" to "Speech request is unknown")
        JSONObject().put("state", status.first).put("reason", status.second ?: JSONObject.NULL).toString()
    }

    @JvmStatic
    fun stop(requestId: String) {
        synchronized(lock) {
            if (activeUtterance == requestId) {
                activeUtterance = null
                utterances[requestId] = "cancelled" to "Speech was stopped"
                mainHandler.post { synchronized(lock) { if (activeUtterance == null) engine?.stop() } }
            } else {
                utterances.remove(requestId)
            }
        }
    }

    @JvmStatic
    fun shutdown() {
        val closing = synchronized(lock) {
            generation++
            initialized = false
            ready = false
            reason = "Android TTS is stopped"
            activeUtterance = null
            utterances.clear()
            val previous = engine
            engine = null
            previous
        }
        mainHandler.post {
            closing?.stop()
            closing?.shutdown()
        }
    }
}
