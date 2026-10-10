package com.agentworkspace.mobile.voice

import android.content.Context
import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.os.SystemClock
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteOrder

/**
 * Transcribes an audio file for the agent's transcribe_audio tool (engine process). Any format the
 * phone can decode works (m4a/AAC, mp3, wav, ogg/opus, amr, flac, and the audio of mp4 videos);
 * WeChat's .silk voice notes do not. The audio streams through: decode, convert to 16 kHz mono,
 * cut into utterances, recognize each, so an hour of audio never sits in memory at once.
 */
object AudioTranscriber {
    @Volatile private var applicationContext: Context? = null
    private const val TIMEOUT_US = 10_000L

    @JvmStatic
    fun initialize(context: Context) { applicationContext = context.applicationContext }

    @JvmStatic
    fun status(): String = OfflineSpeech.status(context()).put("ok", true).toString()

    /**
     * request: path (absolute, inside the workspace; the Python tool checked it), start_seconds,
     * max_seconds (audio to cover in this call) and deadline_seconds (wall-clock budget).
     */
    @JvmStatic
    fun transcribe(requestJson: String): String = try {
        val request = JSONObject(requestJson)
        transcribe(File(request.getString("path")), request.optDouble("start_seconds", 0.0),
            request.optDouble("max_seconds", 1800.0), request.optDouble("deadline_seconds", 900.0)).put("ok", true).toString()
    } catch (failure: OfflineSpeech.Unavailable) {
        JSONObject().put("ok", false).put("code", failure.code).put("error", failure.message).toString()
    } catch (failure: Exception) {
        JSONObject().put("ok", false).put("code", "transcription_failed")
            .put("error", failure.message ?: failure.javaClass.simpleName).toString()
    }

    private fun context(): Context = applicationContext ?: error("Speech recognition is not initialized")

    private class Segment(val start: Double, val end: Double, val text: String)

    private fun transcribe(file: File, startSeconds: Double, maxSeconds: Double, deadlineSeconds: Double): JSONObject {
        val context = context()
        val started = SystemClock.elapsedRealtime()
        require(file.isFile) { "The audio file does not exist" }
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        val vad = OfflineSpeech.newVad(context)
        try {
            extractor.setDataSource(file.absolutePath)
            val track = (0 until extractor.trackCount).firstOrNull {
                extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true
            } ?: throw IllegalArgumentException("The file has no audio track")
            extractor.selectTrack(track)
            val input = extractor.getTrackFormat(track)
            val mime = input.getString(MediaFormat.KEY_MIME)!!
            val totalSeconds = if (input.containsKey(MediaFormat.KEY_DURATION)) input.getLong(MediaFormat.KEY_DURATION) / 1e6 else null
            val begin = startSeconds.coerceAtLeast(0.0)
            if (begin > 0) extractor.seekTo((begin * 1e6).toLong(), MediaExtractor.SEEK_TO_PREVIOUS_SYNC)
            codec = try {
                MediaCodec.createDecoderByType(mime)
            } catch (_: Exception) {
                throw IllegalArgumentException("This phone cannot decode $mime audio")
            }
            codec.configure(input, null, null, 0)
            codec.start()

            val segments = ArrayList<Segment>()
            var sampleRate = input.getInteger(MediaFormat.KEY_SAMPLE_RATE)
            var channels = input.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
            var floatPcm = false
            var resampler = AudioPcm.Resampler(sampleRate, OfflineSpeech.SAMPLE_RATE)
            // Output position in 16 kHz samples, counted from [begin]; decoding may start a little
            // earlier (at a sync point), which is skipped by presentation time.
            var produced = 0L
            val limit = (maxSeconds * OfflineSpeech.SAMPLE_RATE).toLong()
            val info = MediaCodec.BufferInfo()
            // What was fed to the detector, which counts its positions from the same start.
            val history = AudioPcm.History(OfflineSpeech.SAMPLE_RATE * 25)
            var inputDone = false
            var outputDone = false
            var stoppedEarly = false
            fun collect() {
                while (!vad.empty()) {
                    val segment = vad.front()
                    val samples = OfflineSpeech.padded(history, segment)
                    vad.pop()
                    val text = OfflineSpeech.recognize(context, samples)
                    val from = begin + segment.start.toDouble() / OfflineSpeech.SAMPLE_RATE
                    if (text.isNotEmpty()) segments.add(Segment(from, from + segment.samples.size.toDouble() / OfflineSpeech.SAMPLE_RATE, text))
                }
            }
            while (!outputDone) {
                if (!inputDone) {
                    val index = codec.dequeueInputBuffer(TIMEOUT_US)
                    if (index >= 0) {
                        val buffer = codec.getInputBuffer(index)!!
                        val size = extractor.readSampleData(buffer, 0)
                        if (size < 0) {
                            codec.queueInputBuffer(index, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            codec.queueInputBuffer(index, 0, size, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }
                val index = codec.dequeueOutputBuffer(info, TIMEOUT_US)
                if (index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    val format = codec.outputFormat
                    sampleRate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                    channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                    floatPcm = format.containsKey(MediaFormat.KEY_PCM_ENCODING) &&
                        format.getInteger(MediaFormat.KEY_PCM_ENCODING) == AudioFormat.ENCODING_PCM_FLOAT
                    resampler = AudioPcm.Resampler(sampleRate, OfflineSpeech.SAMPLE_RATE)
                    continue
                }
                if (index < 0) continue
                if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) outputDone = true
                val buffer = codec.getOutputBuffer(index)!!.order(ByteOrder.nativeOrder())
                buffer.position(info.offset)
                buffer.limit(info.offset + info.size)
                var mono = if (floatPcm) {
                    val floats = FloatArray(info.size / 4)
                    buffer.asFloatBuffer().get(floats)
                    FloatArray(floats.size / channels) { frame ->
                        var sum = 0f
                        for (channel in 0 until channels) sum += floats[frame * channels + channel]
                        sum / channels
                    }
                } else {
                    val shorts = ShortArray(info.size / 2)
                    buffer.asShortBuffer().get(shorts)
                    AudioPcm.monoFromPcm16(shorts, shorts.size, channels)
                }
                codec.releaseOutputBuffer(index, false)
                // Drop what precedes the requested start (decoding resumes at a sync point).
                val chunkStart = info.presentationTimeUs / 1e6
                if (chunkStart < begin && mono.isNotEmpty()) {
                    val skip = ((begin - chunkStart) * sampleRate).toInt().coerceIn(0, mono.size)
                    mono = mono.copyOfRange(skip, mono.size)
                }
                // At the end of the file the resampler also hands over what its filter held back.
                val samples = if (outputDone) resampler.process(mono) + resampler.flush() else resampler.process(mono)
                var usable = samples
                if (produced + samples.size > limit) usable = samples.copyOf((limit - produced).toInt().coerceAtLeast(0))
                produced += usable.size
                // Feed the detector whole windows, the size it works in.
                var offset = 0
                while (offset < usable.size) {
                    val end = minOf(usable.size, offset + OfflineSpeech.VAD_WINDOW)
                    val window = usable.copyOfRange(offset, end)
                    history.append(window)
                    vad.acceptWaveform(window)
                    offset = end
                }
                collect()
                if (produced >= limit || SystemClock.elapsedRealtime() - started > deadlineSeconds * 1000) {
                    stoppedEarly = !outputDone
                    break
                }
            }
            var covered = produced.toDouble() / OfflineSpeech.SAMPLE_RATE
            val reachedEnd = !stoppedEarly && (totalSeconds == null || begin + covered >= totalSeconds - 0.5)
            if (reachedEnd || segments.isEmpty()) {
                vad.flush()
                collect()
            } else {
                // Stopped at the limit: leave the utterance in progress to the next call, which
                // starts at the last pause, so no sentence is cut in two.
                covered = segments.last().end - begin
            }
            return JSONObject()
                .put("text", AudioPcm.join(segments.map { it.text }))
                .put("segments", JSONArray(segments.map {
                    JSONObject().put("start", round(it.start)).put("end", round(it.end)).put("text", it.text)
                }))
                .put("start_seconds", round(begin))
                .put("covered_seconds", round(covered))
                .put("total_seconds", totalSeconds?.let { round(it) } ?: JSONObject.NULL)
                .put("complete", reachedEnd)
                .put("next_start_seconds", if (reachedEnd) JSONObject.NULL else round(begin + covered))
                .put("model", "SenseVoice Small (FunAudioLLM), offline")
        } finally {
            runCatching { codec?.stop() }
            runCatching { codec?.release() }
            extractor.release()
            vad.release()
        }
    }

    private fun round(value: Double): Double = Math.round(value * 10) / 10.0
}
