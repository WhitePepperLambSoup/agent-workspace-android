// From sherpa-onnx v1.13.8 (https://github.com/k2-fsa/sherpa-onnx, sherpa-onnx/kotlin-api),
// Apache License 2.0, Copyright (c) Xiaomi Corporation and the sherpa-onnx authors.
// Unmodified except where noted: the prebuilt libsherpa-onnx-jni.so binds to these exact names.
package com.k2fsa.sherpa.onnx

data class QnnConfig(
    var backendLib: String = "",
    var contextBinary: String = "",
    var systemLib: String = "",
)
