package com.agentworkspace.mobile.localmodels

import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.os.Process
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Checks the GPU in a process of its own (":gpucheck", see AndroidManifest.xml) before the engine
 * uses it: the first GPU buffer makes ggml compile every OpenCL kernel, and a driver that cannot
 * ends the process. The result, or the marker the native code writes as the process ends, tells
 * LocalModelBridge whether to use the GPU. Compiled kernels stay cached for the engine.
 */
class LocalModelGpuCheckService : Service() {
    private val running = AtomicBoolean(false)

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (running.compareAndSet(false, true)) {
            Thread({
                val check = LocalModelBridge.runGpuCheck(applicationContext)
                runCatching { LocalModelGpu.writeCheck(LocalModelBridge.gpuCheckFile(applicationContext), check) }
                stopSelf()
                // ggml keeps its GPU context and buffers for the life of the process.
                Process.killProcess(Process.myPid())
            }, "local-model-gpu-check").start()
        }
        return START_NOT_STICKY
    }
}
