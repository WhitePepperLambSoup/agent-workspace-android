package com.agentworkspace.mobile.voice

import android.content.Context
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import com.k2fsa.sherpa.onnx.FeatureConfig
import com.k2fsa.sherpa.onnx.OfflineModelConfig
import com.k2fsa.sherpa.onnx.OfflineRecognizer
import com.k2fsa.sherpa.onnx.OfflineRecognizerConfig
import com.k2fsa.sherpa.onnx.OfflineSenseVoiceModelConfig
import com.k2fsa.sherpa.onnx.SileroVadModelConfig
import com.k2fsa.sherpa.onnx.SpeechSegment
import com.k2fsa.sherpa.onnx.Vad
import com.k2fsa.sherpa.onnx.VadModelConfig
import org.json.JSONObject
import java.io.File
import java.nio.file.Files

/**
 * Offline speech recognition: SenseVoice Small (downloaded on the Local models page) through the
 * sherpa-onnx runtime bundled for arm64. Audio never leaves the phone.
 *
 * The recognizer holds about 250 MB, so it loads on first use and is released after a minute
 * without use. Recognition runs on the caller's thread; callers keep it off the main thread.
 */
object OfflineSpeech {
    const val MODEL_ID = "sensevoice-small-int8"
    const val SAMPLE_RATE = 16000
    // The catalog entry (mobile_model_catalog.SPEECH_CATALOG); the Python downloader checked the
    // full SHA-256 before writing installed.json.
    private const val MODEL_SIZE = 239233841L
    private const val MODEL_SHA256 = "c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51"
    private const val TOKENS_ASSET = "speech/sensevoice-tokens.txt"
    private const val TOKENS_SIZE = 315894L
    private const val VAD_ASSET = "speech/silero_vad.onnx"
    private const val IDLE_RELEASE_MS = 60_000L

    // Its own thread: releasing waits for the lock, which a loading recognizer holds for a second.
    private val handler by lazy { Handler(HandlerThread("offline-speech").apply { start() }.looper) }
    private var recognizer: OfflineRecognizer? = null
    private var lastUse = 0L
    private var active = 0
    private val releaseWhenIdle = object : Runnable {
        override fun run() {
            synchronized(this@OfflineSpeech) {
                if (active > 0 || SystemClock.elapsedRealtime() - lastUse < IDLE_RELEASE_MS) {
                    handler.postDelayed(this, IDLE_RELEASE_MS)
                    return
                }
                recognizer?.release()
                recognizer = null
            }
        }
    }

    class Unavailable(val code: String, message: String) : Exception(message)

    /** The runtime ships for arm64 only; elsewhere the phone's own recognizer is used. */
    fun runtimeAvailable(context: Context): Boolean =
        File(context.applicationInfo.nativeLibraryDir, "libsherpa-onnx-jni.so").isFile

    fun modelFile(context: Context): File? {
        val directory = File(context.filesDir, "agent-data/local-models/$MODEL_ID")
        val weights = File(directory, "model.onnx")
        val marker = File(directory, "installed.json")
        return try {
            if (!weights.isFile || weights.length() != MODEL_SIZE || !marker.isFile || marker.length() > 8192 ||
                Files.isSymbolicLink(weights.toPath()) || Files.isSymbolicLink(marker.toPath()) ||
                Files.isSymbolicLink(directory.toPath())) return null
            val installed = JSONObject(marker.readText(Charsets.UTF_8))
            if (installed.optString("model_id") == MODEL_ID && installed.optLong("size", -1) == MODEL_SIZE &&
                installed.optString("sha256") == MODEL_SHA256) weights else null
        } catch (_: Exception) {
            null
        }
    }

    fun status(context: Context): JSONObject {
        val runtime = runtimeAvailable(context)
        val installed = runtime && modelFile(context) != null
        return JSONObject().put("runtime_available", runtime).put("model_installed", installed)
            .put("available", installed).put("model_id", MODEL_ID)
    }

    /** Text spoken in [samples] (16 kHz mono, -1..1). Empty when nothing was recognized. */
    fun recognize(context: Context, samples: FloatArray): String {
        if (samples.isEmpty()) return ""
        val engine = synchronized(this) { recognizer(context).also { active++ } }
        try {
            val stream = engine.createStream()
            try {
                stream.acceptWaveform(samples, SAMPLE_RATE)
                engine.decode(stream)
                return engine.getResult(stream).text.trim()
            } finally {
                stream.release()
            }
        } finally {
            synchronized(this) { active--; touch() }
        }
    }

    /**
     * A voice activity detector for one recording or file; the caller releases it. A pause of
     * [minSilenceSeconds] ends an utterance: shorter cuts mid-phrase more often, which costs the
     * recognizer context and punctuation (a 0.4 s threshold split "客户反馈" on a recording).
     */
    fun newVad(context: Context, minSilenceSeconds: Float = 0.8f, maxSpeechSeconds: Float = 20f): Vad {
        ensureAvailable(context)
        return Vad(context.assets, VadModelConfig(
            sileroVadModelConfig = SileroVadModelConfig(
                model = VAD_ASSET,
                threshold = 0.5f,
                minSilenceDuration = minSilenceSeconds,
                minSpeechDuration = 0.25f,
                windowSize = VAD_WINDOW,
                maxSpeechDuration = maxSpeechSeconds,
            ),
            sampleRate = SAMPLE_RATE,
            numThreads = 1,
        ))
    }

    const val VAD_WINDOW = 512
    // Audio added around each detected utterance (see AudioPcm.History).
    private const val PADDING = SAMPLE_RATE * 3 / 10

    /** [segment] with [PADDING] of the surrounding audio from [history], when it still has it. */
    fun padded(history: AudioPcm.History, segment: SpeechSegment): FloatArray {
        val start = segment.start.toLong()
        val padded = history.slice(start - PADDING, start + segment.samples.size + PADDING)
        return if (padded.size >= segment.samples.size) padded else segment.samples
    }

    private fun ensureAvailable(context: Context) {
        if (!runtimeAvailable(context)) throw Unavailable("unsupported_device",
            "Offline speech recognition is available on 64-bit ARM phones only")
        if (modelFile(context) == null) throw Unavailable("model_missing",
            "Download the SenseVoice speech model in Local models first")
    }

    @Synchronized
    private fun recognizer(context: Context): OfflineRecognizer {
        ensureAvailable(context)
        recognizer?.let { return it }
        val tokens = File(context.filesDir, "speech/sensevoice-tokens.txt")
        if (!tokens.isFile || tokens.length() != TOKENS_SIZE) {
            tokens.parentFile?.mkdirs()
            val temporary = File(tokens.parentFile, tokens.name + ".tmp")
            context.assets.open(TOKENS_ASSET).use { input -> temporary.outputStream().use { input.copyTo(it) } }
            if (!temporary.renameTo(tokens)) throw IllegalStateException("Cannot prepare the speech model's token list")
        }
        val config = OfflineRecognizerConfig(
            featConfig = FeatureConfig(sampleRate = SAMPLE_RATE, featureDim = 80),
            modelConfig = OfflineModelConfig(
                senseVoice = OfflineSenseVoiceModelConfig(
                    model = modelFile(context)!!.absolutePath,
                    language = "",
                    useInverseTextNormalization = true,
                ),
                tokens = tokens.absolutePath,
                numThreads = recognitionThreads(),
                provider = "cpu",
            ),
        )
        return OfflineRecognizer(null, config).also {
            recognizer = it
            touch()
        }
    }

    @Synchronized
    private fun touch() {
        lastUse = SystemClock.elapsedRealtime()
        handler.removeCallbacks(releaseWhenIdle)
        handler.postDelayed(releaseWhenIdle, IDLE_RELEASE_MS)
    }

    /** Releases the recognizer as soon as no recognition is running (Android asked to trim memory). */
    fun release() {
        handler.post {
            synchronized(this) {
                if (active > 0) return@post
                handler.removeCallbacks(releaseWhenIdle)
                recognizer?.release()
                recognizer = null
            }
        }
    }

    private fun recognitionThreads(): Int = Runtime.getRuntime().availableProcessors().coerceIn(1, 8).let { (it / 2).coerceIn(1, 4) }
}
