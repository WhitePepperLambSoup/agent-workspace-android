package com.agentworkspace.mobile.voice

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.sin
import kotlin.math.sqrt

/** Small PCM conversions for speech recognition, which wants 16 kHz mono floats in -1..1. */
object AudioPcm {
    /** The first [count] interleaved 16-bit samples, averaged across [channels] into mono floats. */
    fun monoFromPcm16(samples: ShortArray, count: Int, channels: Int): FloatArray {
        require(channels >= 1) { "channels" }
        val frames = count / channels
        val mono = FloatArray(frames)
        for (frame in 0 until frames) {
            var sum = 0f
            for (channel in 0 until channels) sum += samples[frame * channels + channel]
            mono[frame] = sum / channels / 32768f
        }
        return mono
    }

    /** Root mean square level of [samples], 0..1. */
    fun level(samples: FloatArray, count: Int = samples.size): Float {
        if (count <= 0) return 0f
        var sum = 0.0
        for (index in 0 until count) sum += samples[index] * samples[index]
        return sqrt(sum / count).toFloat().coerceIn(0f, 1f)
    }

    /**
     * Converts a stream of mono chunks from one sample rate to another, keeping its position across
     * chunks: a Kaiser-windowed sinc low-pass filter evaluated at each output position, cutting off
     * just below the lower of the two Nyquist frequencies. A cruder filter (averaging neighbours)
     * left enough aliasing at 22.05 kHz for the recognizer to hear "torow" for "tomorrow".
     * The kernel is tabulated at [PHASES] sub-sample offsets and interpolated between them.
     */
    class Resampler(private val from: Int, private val to: Int) {
        init { require(from > 0 && to > 0) { "sample rates" } }

        private val step = from.toDouble() / to
        // Cut-off as a fraction of the source Nyquist frequency.
        private val cutoff = minOf(1.0, to.toDouble() / from) * 0.95
        // Source samples on each side of an output position that the kernel reaches.
        private val half = ceil(ZERO_CROSSINGS / cutoff).toInt()
        private val table = kernelTable(half, cutoff)
        private var history = FloatArray(0)  // source samples the next outputs still need
        private var position = 0.0          // next output position within history
        private var consumed = 0L           // input samples so far
        private var produced = 0L           // output samples so far

        fun process(input: FloatArray): FloatArray {
            if (from == to) return input.copyOf()
            consumed += input.size
            val source = if (history.isEmpty()) input else history + input
            val output = FloatArray(max(0, ((source.size - position) / step).toInt()) + 2)
            var count = 0
            while (count < output.size) {
                val center = floor(position).toInt()
                if (center + half >= source.size) break
                val fraction = position - center
                var acc = 0f
                var weight = 0f
                for (offset in -half + 1..half) {
                    val index = center + offset
                    if (index < 0) continue
                    // Distance from the output position, in source samples, to the table.
                    val at = (offset - fraction + half) * PHASES
                    val slot = floor(at).toInt()
                    val blend = (at - slot).toFloat()
                    val coefficient = table[slot] * (1 - blend) + table[minOf(slot + 1, table.size - 1)] * blend
                    acc += source[index] * coefficient
                    weight += coefficient
                }
                output[count++] = if (weight != 0f) acc / weight else 0f
                position += step
            }
            val keepFrom = (floor(position).toInt() - half).coerceIn(0, source.size)
            history = source.copyOfRange(keepFrom, source.size)
            position -= keepFrom
            produced += count
            return output.copyOf(count)
        }

        /** The output still held back for the filter's look-ahead, at the end of the stream. */
        fun flush(): FloatArray {
            if (from == to) return FloatArray(0)
            // Exactly as many samples as the input's duration calls for; zeros stand in for the
            // look-ahead past the end.
            val owed = (ceil(consumed / step).toLong() - produced).coerceAtLeast(0).toInt()
            if (owed == 0) return FloatArray(0)
            val tail = process(FloatArray(half + 1)).copyOf(owed)
            history = FloatArray(0)
            position = 0.0
            consumed = 0
            produced = 0
            return tail
        }

        private companion object {
            const val ZERO_CROSSINGS = 16
            const val PHASES = 64
            const val BETA = 8.0

            /** The windowed sinc at every 1/PHASES sample from -half to +half. */
            fun kernelTable(half: Int, cutoff: Double): FloatArray {
                val size = 2 * half * PHASES + 1
                val norm = besselI0(BETA)
                return FloatArray(size) { slot ->
                    val x = slot.toDouble() / PHASES - half
                    val argument = x * cutoff
                    val sinc = if (abs(argument) < 1e-9) 1.0 else sin(PI * argument) / (PI * argument)
                    val r = x / half
                    val window = besselI0(BETA * sqrt(max(0.0, 1 - r * r))) / norm
                    (cutoff * sinc * window).toFloat()
                }
            }

            fun besselI0(x: Double): Double {
                var total = 1.0
                var term = 1.0
                var k = 1
                while (term > 1e-12 * total) {
                    term *= (x / (2 * k)) * (x / (2 * k))
                    total += term
                    k++
                }
                return total
            }
        }
    }
    /**
     * The most recent [capacity] samples of a stream, addressed by their position in the whole
     * stream. Utterances cut by the voice activity detector are padded from it: a little audio
     * before the detected start keeps a soft first syllable, and the recognizer reads digits and
     * punctuation better with some context.
     */
    class History(private val capacity: Int) {
        init { require(capacity > 0) { "capacity" } }

        private val ring = FloatArray(capacity)
        var total = 0L
            private set

        fun append(samples: FloatArray) {
            for (sample in samples) {
                ring[(total % capacity).toInt()] = sample
                total++
            }
        }

        /** Samples [from, to) of the stream, limited to what is still kept. */
        fun slice(from: Long, to: Long): FloatArray {
            val start = maxOf(from, total - capacity, 0L)
            val end = minOf(to, total)
            if (end <= start) return FloatArray(0)
            return FloatArray((end - start).toInt()) { ring[((start + it) % capacity).toInt()] }
        }
    }

    /** Joins recognized pieces, spacing Latin words apart but not Chinese or Japanese text. */
    fun join(pieces: List<String>): String {
        val text = StringBuilder()
        for (piece in pieces.map { it.trim() }.filter { it.isNotEmpty() }) {
            if (text.isNotEmpty() && needsSpace(text[text.length - 1], piece[0])) text.append(' ')
            text.append(piece)
        }
        return text.toString()
    }

    private fun needsSpace(before: Char, after: Char): Boolean =
        (before.isLetterOrDigit() || before in ".,!?;:") && before.code < 0x2E80 &&
            after.isLetterOrDigit() && after.code < 0x2E80

    /** True when the absolute peak of [samples] is below [threshold]: no usable sound at all. */
    fun silent(samples: FloatArray, threshold: Float = 0.003f): Boolean = samples.all { abs(it) < threshold }
}
