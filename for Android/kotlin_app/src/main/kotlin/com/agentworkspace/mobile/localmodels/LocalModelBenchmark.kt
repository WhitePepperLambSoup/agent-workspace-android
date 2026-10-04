package com.agentworkspace.mobile.localmodels

import android.content.Context
import android.content.Intent
import android.util.AtomicFile
import com.agentworkspace.mobile.embedded.EngineRecovery
import com.agentworkspace.mobile.embedded.LocalEngineClient
import com.agentworkspace.mobile.embedded.ProviderChangeCoordinator
import com.agentworkspace.mobile.embedded.TermuxDaemonService
import org.json.JSONObject
import java.io.File
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong

/** One optional, bounded device test in the existing engine process. */
object LocalModelBenchmark {
    private val worker = Executors.newSingleThreadExecutor()
    private val sampler = Executors.newSingleThreadScheduledExecutor()
    @Volatile private var activeId: String? = null
    @Volatile private var cancelled = false
    @Volatile private var report: String? = null
    private fun file(context: Context) = AtomicFile(File(context.filesDir, "local-model-device-test.json"))

    private fun save(context: Context, value: JSONObject) {
        report = value.toString()
        val storage = file(context)
        var stream: java.io.FileOutputStream? = null
        try {
            stream = storage.startWrite()
            stream.write(report!!.toByteArray(Charsets.UTF_8))
            storage.finishWrite(stream)
        } catch (_: Exception) { if (stream != null) storage.failWrite(stream) }
    }

    fun status(context: Context): JSONObject {
        val current = report
        val value = try {
            JSONObject(current ?: file(context).openRead().use { stream ->
                val bytes = stream.readBytes()
                require(bytes.size <= 65536)
                bytes.toString(Charsets.UTF_8)
            })
        } catch (_: Exception) { JSONObject().put("state", "idle") }
        if (activeId == null && value.optString("state") in setOf("queued", "running", "cancelling"))
            value.put("state", "interrupted").put("error", "引擎曾中断；这次测试未完成")
        val native = JSONObject(LocalModelBridge.status())
        if (activeId != null) value.put("phase", native.optString("generation_phase", "waiting"))
        return value
    }

    @Synchronized fun start(context: Context, options: JSONObject): JSONObject {
        check(activeId == null) { "已有设备测试正在运行" }
        require(options.keys().asSequence().all { it in setOf("model_id", "context_tokens", "memory_mode", "threads", "timeout_seconds") })
        val model = options.getString("model_id")
        val maximum = LocalModelContext.modelMaximumTokens(model)
        val configured = LocalModelPerformance.integer(options, "context_tokens", maximum)
        require(configured == 0 || configured >= LocalModelContext.MIN_CONTEXT_TOKENS)
        val memoryMode = options.optString("memory_mode", "balanced")
        require(memoryMode in setOf("balanced", "extended"))
        val threads = LocalModelPerformance.integer(options, "threads", LocalModelPerformance.MAX_THREADS)
        val timeout = LocalModelPerformance.integer(options, "timeout_seconds", LocalModelPerformance.MAX_TIMEOUT_SECONDS)
        val id = "bench_${UUID.randomUUID().toString().replace("-", "")}"
        activeId = id
        cancelled = false
        val initial = JSONObject().put("state", "queued").put("request_id", id)
            .put("model_id", model).put("selected_context_tokens", configured)
            .put("configured_threads", threads).put("configured_timeout_seconds", timeout)
            .put("test_timeout_seconds", 90).put("tested_full_context", false)
            .put("started_at_ms", System.currentTimeMillis())
        save(context, initial)
        worker.execute { run(context.applicationContext, initial, model, configured, memoryMode, threads) }
        return JSONObject().put("ok", true).put("benchmark", initial)
    }

    @Synchronized fun cancel(context: Context): JSONObject {
        val id = activeId
        if (id != null) {
            cancelled = true
            LocalModelBridge.cancelRequest(id)
            save(context, status(context).put("state", "cancelling"))
        }
        return JSONObject().put("ok", true).put("benchmark", status(context))
    }

    private fun run(context: Context, initial: JSONObject, model: String, configured: Int,
                    memoryMode: String, requestedThreads: Int) {
        val result = JSONObject(initial.toString())
        val tokenFile = File(context.filesDir, "serve.token")
        val token = runCatching { tokenFile.readText().trim() }.getOrNull()
        val http = LocalEngineClient(context, fixedToken = token)
        var lease: String? = null
        val peak = AtomicLong(-1)
        var memorySampling: java.util.concurrent.ScheduledFuture<*>? = null
        fun sample(): Pair<Long?, Long?> = try {
            LocalModelPerformance.memoryFields(File("/proc/self/status").readText(Charsets.US_ASCII))
                .also { it.first?.let { rss -> peak.updateAndGet { previous -> maxOf(previous, rss) } } }
        } catch (_: Exception) { null to null }
        try {
            check(!token.isNullOrEmpty()) { "请先启动并连接本地 Agent 引擎" }
            val reservation = http.request("POST", "/mobile/provider-change/prepare",
                JSONObject().put("require_local_engine", true))
            check(reservation.optBoolean("ok")) { "请先完成当前及排队任务" }
            val preparedLease = reservation.opt("lease_id")
            if (preparedLease !is String || !preparedLease.matches(Regex("[A-Za-z0-9_-]{1,80}")))
                throw LocalEngineClient.RequestOutcomeUnknown("资源预留成功，但未收到有效的预留编号")
            lease = preparedLease
            if (cancelled) {
                result.put("state", "cancelled")
            } else {
                val plan = JSONObject(LocalModelBridge.contextPlan(model, configured, memoryMode))
                check(!plan.has("error")) { plan.optJSONObject("error")?.optString("message") ?: "无法推荐上下文" }
                val contextTokens = plan.getInt("context_size")
                val cpuThreads = LocalModelPerformance.threads(requestedThreads, Runtime.getRuntime().availableProcessors())
                result.put("state", "running").put("planned_context_tokens", contextTokens)
                    .put("actual_threads", cpuThreads).put("memory_estimate_feasible", plan.optBoolean("feasible"))
                val before = sample()
                result.put("rss_before_bytes", before.first ?: JSONObject.NULL)
                    .put("process_vmhwm_before_bytes", before.second ?: JSONObject.NULL)
                memorySampling = sampler.scheduleAtFixedRate({ sample() }, 0, 50, TimeUnit.MILLISECONDS)
                save(context, result)
                val prompt = "<|im_start|>system\nYou are a helpful assistant. Summarize text directly without using tools.<|im_end|>\n" +
                    "<|im_start|>user\nSummarize this daily task list in a short paragraph.\n" +
                    (1..32).joinToString("\n") { "Task $it: review the notes, check the result and prepare the next step." } +
                    "\nWrite a useful summary in about 100 words.<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
                val request = JSONObject().put("version", 1).put("request_id", result.getString("request_id"))
                    .put("model_id", model).put("model_path", File(context.filesDir, "agent-data/local-models/$model/model.gguf").absolutePath)
                    .put("prompt", prompt).put("context_size", contextTokens).put("max_output_tokens", 64)
                    .put("memory_mode", memoryMode).put("threads", cpuThreads)
                    .put("temperature", 0).put("generation_timeout_ms", 90000)
                val response = JSONObject(LocalModelBridge.generateBenchmark(request.toString()))
                val measured = JSONObject(LocalModelBridge.status()).optJSONObject("last_generation")
                    ?.takeIf { it.optString("request_id") == result.getString("request_id") }
                for (key in listOf("prompt_tokens", "generated_tokens", "first_token_ms", "elapsed_ms", "finish_reason"))
                    result.put(key, response.opt(key) ?: JSONObject.NULL)
                for (key in listOf("actual_context_size", "prompt_evaluation_ms", "prompt_tokens_per_second", "tokens_per_second"))
                    result.put(key, measured?.opt(key) ?: JSONObject.NULL)
                val state = when {
                    cancelled || response.optBoolean("cancelled") -> "cancelled"
                    response.has("error") -> "failed"
                    response.optInt("generated_tokens") <= 0 -> "failed"
                    else -> "completed"
                }
                result.put("state", state)
                response.optJSONObject("error")?.let { result.put("error", it.optString("message", "测试未完成")) }
            }
        } catch (failure: Exception) {
            result.put("state", if (cancelled) "cancelled" else "failed")
                .put("error", failure.message ?: "无法完成设备测试")
            if (lease == null && failure is LocalEngineClient.RequestOutcomeUnknown)
                result.put("reservation_released", false).put("recovery_required", true)
                    .put("reservation_state", "unknown")
        } finally {
            memorySampling?.cancel(false)
            val after = sample()
            result.put("rss_after_bytes", after.first ?: JSONObject.NULL)
                .put("run_sampled_peak_rss_bytes", peak.get().takeIf { it >= 0 } ?: JSONObject.NULL)
                .put("process_vmhwm_after_bytes", after.second ?: JSONObject.NULL)
                .put("memory_sample_interval_ms", 50)
                .put("memory_peak_scope", "run_sampled_rss; VmHWM is process_lifetime")
                .put("completed_at_ms", System.currentTimeMillis())
                .put("preferences_changed", false)
            if (lease != null) {
                fun operation(name: String): ProviderChangeCoordinator.Reply {
                    val reply = http.request("POST", "/mobile/provider-change/$name",
                        JSONObject().put("lease_id", lease))
                    return ProviderChangeCoordinator.Reply(reply.getString("state"),
                        reply.optBoolean("restart_required"))
                }
                val release = ProviderChangeCoordinator().releaseTemporary(
                    isCurrent = { !token.isNullOrEmpty() &&
                        runCatching { tokenFile.readText().trim() == token }.getOrDefault(false) },
                    abort = { operation("abort") },
                    status = { operation("status") },
                    restart = {
                        context.startForegroundService(Intent(context, TermuxDaemonService::class.java)
                            .setAction(EngineRecovery.ACTION_RECOVER)
                            .putExtra(TermuxDaemonService.EXTRA_EXPECTED_ENGINE_TOKEN, token))
                    },
                )
                result.put("reservation_released", release.released)
                    .put("recovery_required", release.recoveryRequired)
                    .put("restart_requested", release.restartRequested)
            }
            if (result.optBoolean("recovery_required") && !result.optBoolean("restart_requested"))
                runCatching { EngineRecovery.enqueue(context, 1) }
            synchronized(this) {
                save(context, result)
                activeId = null
            }
        }
    }
}
