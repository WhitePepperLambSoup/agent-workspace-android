// From sherpa-onnx v1.13.8 (https://github.com/k2-fsa/sherpa-onnx, sherpa-onnx/kotlin-api),
// Apache License 2.0, Copyright (c) Xiaomi Corporation and the sherpa-onnx authors.
// The example getVadModelConfig() at the end is left out: the prebuilt libsherpa-onnx-jni.so binds to these exact names.
// Copyright (c)  2023  Xiaomi Corporation
package com.k2fsa.sherpa.onnx

import android.content.res.AssetManager

data class SileroVadModelConfig(
    var model: String = "",
    var threshold: Float = 0.5F,
    var minSilenceDuration: Float = 0.25F,
    var minSpeechDuration: Float = 0.25F,
    var windowSize: Int = 512,
    var maxSpeechDuration: Float = 5.0F,
)

data class TenVadModelConfig(
    var model: String = "",
    var threshold: Float = 0.5F,
    var minSilenceDuration: Float = 0.25F,
    var minSpeechDuration: Float = 0.25F,
    var windowSize: Int = 256,
    var maxSpeechDuration: Float = 5.0F,
)

data class VadModelConfig(
    var sileroVadModelConfig: SileroVadModelConfig = SileroVadModelConfig(),
    var tenVadModelConfig: TenVadModelConfig = TenVadModelConfig(),
    var sampleRate: Int = 16000,
    var numThreads: Int = 1,
    var provider: String = "cpu",
    var debug: Boolean = false,
)

class SpeechSegment(val start: Int, val samples: FloatArray)

class Vad(
    assetManager: AssetManager? = null,
    var config: VadModelConfig,
) {
    private var ptr: Long

    init {
        if (assetManager != null) {
            ptr = newFromAsset(assetManager, config)
        } else {
            ptr = newFromFile(config)
        }
        require(ptr != 0L) {
            "Invalid VadConfig: failed to create native Vad"
        }
    }

    protected fun finalize() {
        if (ptr != 0L) {
            delete(ptr)
            ptr = 0
        }
    }

    fun release() = finalize()

    fun compute(samples: FloatArray): Float = compute(ptr, samples)


    fun acceptWaveform(samples: FloatArray) = acceptWaveform(ptr, samples)

    fun empty(): Boolean = empty(ptr)
    fun pop() = pop(ptr)

    fun front(): SpeechSegment {
        return front(ptr)
    }

    fun clear() = clear(ptr)

    fun isSpeechDetected(): Boolean = isSpeechDetected(ptr)

    fun reset() = reset(ptr)

    fun flush() = flush(ptr)

    private external fun delete(ptr: Long)

    private external fun newFromAsset(
        assetManager: AssetManager,
        config: VadModelConfig,
    ): Long

    private external fun newFromFile(
        config: VadModelConfig,
    ): Long

    private external fun acceptWaveform(ptr: Long, samples: FloatArray)
    private external fun compute(ptr: Long, samples: FloatArray): Float

    private external fun empty(ptr: Long): Boolean
    private external fun pop(ptr: Long)
    private external fun clear(ptr: Long)
    private external fun front(ptr: Long): SpeechSegment
    private external fun isSpeechDetected(ptr: Long): Boolean
    private external fun reset(ptr: Long)
    private external fun flush(ptr: Long)

    companion object {
        init {
            System.loadLibrary("sherpa-onnx-jni")
        }
    }
}
