package com.agentworkspace.mobile.voice

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import com.agentworkspace.mobile.UiText
import com.k2fsa.sherpa.onnx.Vad
import java.util.concurrent.Executors
import kotlin.math.max

/**
 * One offline voice input: records the microphone until the speaker pauses (or [finish]), cuts the
 * speech into utterances with the voice activity detector and recognizes each as it ends, so the
 * text appears while the user is still talking. Callbacks arrive on the main thread.
 */
class OfflineVoiceSession(context: Context, private val listener: Listener) {
    interface Listener {
        fun onLevel(level: Float)
        fun onText(text: String)
        fun onRecognizing()
        fun onFinished(text: String, heardSpeech: Boolean)
        fun onError(message: String)
    }

    companion object {
        const val MAX_SECONDS = 60
        // How long a pause after speech ends the recording.
        private const val END_SILENCE_MS = 1800L
        private const val NO_SPEECH_MS = 8000L
        private const val CHUNK = OfflineSpeech.VAD_WINDOW
    }

    private val context = context.applicationContext
    private val main = Handler(Looper.getMainLooper())
    private val recognition = Executors.newSingleThreadExecutor { Thread(it, "offline-voice-recognition") }
    private val pieces = ArrayList<String>()  // recognition thread only
    // The recording so far (up to the longest utterance plus padding), recording thread only.
    private val history = AudioPcm.History(OfflineSpeech.SAMPLE_RATE * 25)
    @Volatile private var stopping = false
    @Volatile private var cancelled = false

    fun start() {
        // Load the recognizer while the user starts speaking (about a second on a phone).
        recognition.execute { runCatching { OfflineSpeech.recognize(context, FloatArray(CHUNK)) } }
        Thread({ record() }, "offline-voice-recording").start()
    }

    /** Stop listening and return what was said. */
    fun finish() { stopping = true }

    /** Stop listening and discard everything. */
    fun cancel() {
        cancelled = true
        stopping = true
    }

    @SuppressLint("MissingPermission")  // the activity holds RECORD_AUDIO before starting a session
    private fun record() {
        val rate = OfflineSpeech.SAMPLE_RATE
        val minimum = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val recorder = try {
            AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, rate, AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT, max(minimum, rate))  // half a second of 16-bit samples
        } catch (_: Exception) {
            null
        }
        if (recorder == null || recorder.state != AudioRecord.STATE_INITIALIZED) {
            recorder?.release()
            fail(UiText.of(context, "无法打开麦克风", "Could not open the microphone"))
            return
        }
        val vad = try {
            // A little shorter than for files, so text appears while the user is still talking.
            OfflineSpeech.newVad(context, minSilenceSeconds = 0.6f)
        } catch (failure: Exception) {
            recorder.release()
            fail(failure.message ?: UiText.of(context, "离线语音识别不可用", "Offline speech recognition is unavailable"))
            return
        }
        var heard = false
        var failed = false
        try {
            recorder.startRecording()
            if (recorder.recordingState != AudioRecord.RECORDSTATE_RECORDING) {
                fail(UiText.of(context, "麦克风正被其他应用使用", "Another app is using the microphone"))
                failed = true
            }
            val buffer = ShortArray(CHUNK)
            val started = SystemClock.elapsedRealtime()
            var lastSpeech = started
            while (!stopping) {
                val read = recorder.read(buffer, 0, buffer.size)
                if (read < 0) {
                    fail(UiText.of(context, "录音中断", "Recording stopped unexpectedly"))
                    failed = true
                    break
                }
                if (read == 0) continue
                val chunk = AudioPcm.monoFromPcm16(buffer, read, 1)
                val level = AudioPcm.level(chunk)
                main.post { if (!cancelled) listener.onLevel(level) }
                history.append(chunk)
                vad.acceptWaveform(chunk)
                val now = SystemClock.elapsedRealtime()
                if (vad.isSpeechDetected()) {
                    heard = true
                    lastSpeech = now
                }
                drain(vad)
                if (heard && now - lastSpeech > END_SILENCE_MS) break
                if (!heard && now - started > NO_SPEECH_MS) break
                if (now - started > MAX_SECONDS * 1000L) break
            }
        } finally {
            runCatching { recorder.stop() }
            recorder.release()
        }
        if (cancelled || failed) {
            vad.release()
            recognition.shutdownNow()
            return
        }
        main.post { if (!cancelled) listener.onRecognizing() }
        vad.flush()
        drain(vad)
        vad.release()
        val spoke = heard
        recognition.execute {
            val text = AudioPcm.join(pieces)
            main.post { if (!cancelled) listener.onFinished(text, spoke || text.isNotEmpty()) }
        }
        recognition.shutdown()
    }

    private fun drain(vad: Vad) {
        while (!vad.empty()) {
            val samples = OfflineSpeech.padded(history, vad.front())
            vad.pop()
            recognition.execute {
                if (cancelled) return@execute
                try {
                    val text = OfflineSpeech.recognize(context, samples)
                    if (text.isNotEmpty()) {
                        pieces.add(text)
                        val sofar = AudioPcm.join(pieces)
                        main.post { if (!cancelled) listener.onText(sofar) }
                    }
                } catch (failure: Exception) {
                    fail(failure.message ?: UiText.of(context, "识别失败", "Recognition failed"))
                }
            }
        }
    }

    private fun fail(message: String) {
        stopping = true
        main.post { if (!cancelled) listener.onError(message) }
    }
}
