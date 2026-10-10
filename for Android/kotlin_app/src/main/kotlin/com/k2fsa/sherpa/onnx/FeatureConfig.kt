// From sherpa-onnx v1.13.8 (https://github.com/k2-fsa/sherpa-onnx, sherpa-onnx/kotlin-api),
// Apache License 2.0, Copyright (c) Xiaomi Corporation and the sherpa-onnx authors.
// Unmodified except where noted: the prebuilt libsherpa-onnx-jni.so binds to these exact names.
package com.k2fsa.sherpa.onnx

data class FeatureConfig(
    var sampleRate: Int = 16000,
    var featureDim: Int = 80,
    var dither: Float = 0.0f
)

fun getFeatureConfig(sampleRate: Int, featureDim: Int): FeatureConfig {
    return FeatureConfig(sampleRate = sampleRate, featureDim = featureDim)
}
