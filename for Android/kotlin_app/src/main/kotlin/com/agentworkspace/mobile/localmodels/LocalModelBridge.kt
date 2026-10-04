package com.agentworkspace.mobile.localmodels

import android.app.ActivityManager
import android.content.Context
import com.agentworkspace.mobile.embedded.MobileProviderSettings
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.file.Files

/** A single private CPU inference engine. This bridge never starts an HTTP server. */
object LocalModelBridge {
    const val ENGINE_REVISION = "7fe450e19305b828c199d602c23a8337aaa1f03b"
    private val supportedIds = setOf("qwen3-0.6b-q4-k-m", "qwen3-1.7b-q4-k-m",
        "qwen3-0.6b-q8-0", "qwen3-1.7b-q8-0", "qwen3.5-0.8b-q4-k-m", "qwen3.5-0.8b-q8-0",
        "qwen3.5-2b-q4-k-m", "qwen3.5-2b-q8-0") + listOfNotNull(TrainedLocalModel.spec?.id)
    @Volatile private var applicationContext: Context? = null
    @Volatile private var modelRoot: File? = null
    @Volatile private var libraryLoaded = false
    @Volatile private var initializationError: String? = null
    @Volatile private var runtimeSettings = LocalModelPerformance.Settings()

    @JvmStatic fun configureRuntime(settingsJson: String) {
        runtimeSettings = LocalModelPerformance.settings(JSONObject(settingsJson))
    }
    private data class Projection(val id: String, val bytes: Long, val sha256: String)
    private val smallVision = Projection("qwen3.5-0.8b-vision-f16", 204987232L,
        "56e4c6cfe73b0c82e3e82bc518d7591997e61d81f723fc41a586f4fa69ea2453")
    private val mediumVision = Projection("qwen3.5-2b-vision-f16", 668227264L,
        "7035e9cb8d7c6a9681d07eef9a364783e86ea4cd73faab2eabb4f43a101830c7")

    @JvmStatic @Synchronized
    fun initialize(context: Context) {
        val app = context.applicationContext
        val files = app.filesDir.canonicalFile
        val root = File(files, "agent-data/local-models")
        if (applicationContext != null && modelRoot == root && initializationError == null) return
        try {
            check(root.mkdirs() || root.isDirectory) { "Private model directory is unavailable" }
            check(root.canonicalPath == root.absolutePath && root.canonicalPath.startsWith(files.path + File.separator))
                { "Private model directory is outside app storage" }
            if (!libraryLoaded) {
                System.loadLibrary("agent_qwen")
                libraryLoaded = true
            }
            val result = JSONObject(nativeInitialize(root.path.toByteArray(Charsets.UTF_8))
                .toString(Charsets.UTF_8))
            check(!result.has("error")) { "Native inference initialization failed" }
            modelRoot = root
            applicationContext = app
            initializationError = null
        } catch (_: LinkageError) {
            initializationError = "Native CPU inference library is unavailable for this Android build"
        } catch (_: Exception) {
            initializationError = "Private model storage or native inference initialization failed"
        }
    }

    @JvmStatic
    fun status(): String {
        if (applicationContext == null || !libraryLoaded || initializationError != null) {
            return JSONObject().put("available", false).put("engine", "llama.cpp")
                .put("engine_revision", ENGINE_REVISION)
                .put("model_root", modelRoot?.path ?: JSONObject.NULL)
                .put("loaded_model", JSONObject.NULL).put("generating", false)
                .put("supports_vision", false)
                .put("context_size", 0)
                .put("last_generation", JSONObject.NULL)
                .put("last_error", initializationError ?: "Native inference has not been initialized")
                .toString()
        }
        return nativeStatus().toString(Charsets.UTF_8)
    }

    private class RequestError(val code: String, message: String) : RuntimeException(message)
    private fun error(code: String, message: String) = JSONObject()
        .put("error", JSONObject().put("code", code).put("message", message)).toString()

    private fun boundedInteger(request: JSONObject, key: String, minimum: Int, maximum: Int): Int {
        val value = request.opt(key)
        if (value !is Int && value !is Long) throw RequestError("invalid_request", "Invalid $key")
        val number = (value as Number).toLong()
        if (number !in minimum.toLong()..maximum.toLong())
            throw RequestError("invalid_request", "$key is outside the supported phone limits")
        return number.toInt()
    }

    private fun installedDigest(weights: File, id: String): String? = try {
        val marker = File(weights.parentFile, "installed.json")
        if (!marker.isFile || marker.length() !in 1L..8192L ||
            Files.isSymbolicLink(marker.toPath())) null
        else {
            val value = JSONObject(marker.readText(Charsets.UTF_8))
            if (value.optString("model_id") == id && value.optLong("size", -1) == weights.length())
                value.optString("sha256").takeIf { it.matches(Regex("[a-f0-9]{64}")) }
            else null
        }
    } catch (_: Exception) { null }

    private fun privateModelPath(context: Context, root: File, id: String, path: Any?,
        code: String = "invalid_model_path"): File {
        val expected = File(root, "$id/model.gguf")
        val appAlias = File(context.filesDir.absoluteFile, "agent-data/local-models/$id/model.gguf")
        val requested = if (path is String) File(path).absoluteFile else null
        if (requested == null || (requested != expected && requested != appAlias) ||
            requested.canonicalFile != expected || expected.canonicalFile != expected ||
            Files.isSymbolicLink(expected.toPath()) || Files.isSymbolicLink(expected.parentFile!!.toPath()) ||
            Files.isSymbolicLink(requested.toPath()) || Files.isSymbolicLink(requested.parentFile!!.toPath()))
            throw RequestError(code, "Local Qwen model files must stay in private app storage")
        return expected
    }

    private fun availableSwapBytes(): Long = try {
        LocalModelContext.freeSwapBytes(File("/proc/meminfo").readText(Charsets.US_ASCII))
    } catch (_: Exception) { 0L }

    private fun installedVisionProjectionBytes(context: Context, root: File, modelId: String): Long = try {
        val projection = when {
            modelId.startsWith("qwen3.5-0.8b-") -> smallVision
            modelId.startsWith("qwen3.5-2b-") -> mediumVision
            else -> null
        }
        if (projection == null) 0L else {
            val file = privateModelPath(context, root, projection.id,
                File(root, "${projection.id}/model.gguf").absolutePath, "invalid_projection_path")
            if (file.isFile && file.length() == projection.bytes &&
                installedDigest(file, projection.id) == projection.sha256) projection.bytes else 0L
        }
    } catch (_: Exception) { 0L }

    /** Text planning by default; image planning includes its projector allocation. */
    @JvmStatic @JvmOverloads
    fun contextPlan(modelId: String, requestedTokens: Int = 0,
                    memoryMode: String = "balanced", needsVision: Boolean = false): String {
        val context = applicationContext
        val root = modelRoot
        if (context == null || root == null || !libraryLoaded || initializationError != null)
            return error("engine_unavailable", initializationError ?: "Native inference has not been initialized")
        try {
            if (modelId !in supportedIds || (memoryMode != "balanced" && memoryMode != "extended"))
                throw RequestError("invalid_request", "Invalid local model or memory mode")
            val maximum = LocalModelContext.modelMaximumTokens(modelId)
            if (requestedTokens != 0 && requestedTokens !in LocalModelContext.MIN_CONTEXT_TOKENS..maximum)
                throw RequestError("invalid_request", "Configured context is outside the model limits")
            val weights = privateModelPath(context, root, modelId,
                File(root, "$modelId/model.gguf").absolutePath)
            if (!weights.isFile || weights.length() !in 16L..(3L * 1024 * 1024 * 1024))
                throw RequestError("model_not_installed", "The selected local Qwen model is not installed")
            val memory = ActivityManager.MemoryInfo()
            (context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).getMemoryInfo(memory)
            val loaded = JSONObject(status()).optString("loaded_model").takeIf { it in supportedIds }
            // Python constructs the provider before a request has any images.
            // Installed vision capability must not reduce its text capacity.
            // Actual image generation independently verifies and budgets the
            // projector; callers can also request an explicit image plan.
            if (needsVision && !modelId.startsWith("qwen3.5-"))
                throw RequestError("unsupported_vision", "Select Qwen3.5 to read local images")
            val projectionBytes = if (needsVision)
                installedVisionProjectionBytes(context, root, modelId) else 0L
            if (needsVision && projectionBytes == 0L)
                throw RequestError("projection_not_installed",
                    "Install and verify the matching local Qwen vision projection to read images")
            // Vocabulary-only metadata inspection is cheap and shares the
            // native engine try-lock. Busy engines keep the declared family
            // range; generation always rechecks the actual GGUF maximum.
            val tokenMetadata = JSONObject(countPromptTokens(modelId, " "))
            val installedMaximum = tokenMetadata.optInt("model_max_context_tokens", 0)
                .takeIf { it >= LocalModelContext.MIN_CONTEXT_TOKENS } ?: 0
            val plan = LocalModelContext.plan(modelId, weights.length(), installedDigest(weights, modelId),
                loaded, requestedTokens, memory.availMem, availableSwapBytes(), memory.lowMemory, memoryMode,
                projectionBytes, installedMaximum, needsVision)
            val measured = JSONObject(status()).optJSONObject("last_generation")
            val result = JSONObject()
                .put("context_size", plan.contextTokens)
                .put("configured_context_tokens", plan.configuredTokens)
                .put("model_max_context_tokens", plan.modelMaximumTokens)
                .put("recommended_context_tokens", plan.recommendedTokens)
                .put("available_ram_bytes", plan.availableRamBytes)
                .put("available_swap_bytes", plan.availableSwapBytes)
                .put("required_ram_bytes", plan.requiredBytes)
                .put("ram_headroom_bytes", LocalModelMemory.RAM_HEADROOM_BYTES)
                .put("vision_reserve_bytes", plan.visionReserveBytes)
                .put("planning_input_type", if (needsVision) "images" else "text")
                .put("physical_compute_reserve_bytes", LocalModelMemory.TEXT_COMPUTE_RESERVE_BYTES +
                    if (plan.visionReserveBytes > 0) LocalModelMemory.VISION_COMPUTE_RESERVE_BYTES else 0L)
                .put("memory_mode", plan.memoryMode)
                .put("supported_context_tokens", JSONArray(plan.supportedContextTokens))
                .put("feasible", plan.feasible)
                .put("memory_estimate_advisory", requestedTokens > 0)
                .put("recommended_threads", LocalModelPerformance.threads(0, Runtime.getRuntime().availableProcessors()))
                .put("recommended_timeout_seconds", LocalModelPerformance.timeoutSeconds(0, plan.contextTokens, measured))
                .put("recommendation_basis", "available_physical_ram_and_model_limit; timeout projects measured rates when available")
                .put("automatic_recommendation_memory_mode", "balanced")
                .put("automatic_recommendation_uses_swap", false)
                .put("model_context_limit_source", if (installedMaximum > 0) "installed_gguf_metadata" else "declared_model_family")
            if (requestedTokens > 0 && !plan.feasible)
                result.put("reason", "当前内存估算偏紧；将尝试所选上下文，实际分配失败时会明确提示。")
            if (requestedTokens == 0 && !plan.feasible)
                result.put("error", JSONObject().put("code", "insufficient_memory")
                    .put("message", "Not enough available memory for a local model context"))
            return result.toString()
        } catch (failure: RequestError) {
            return error(failure.code, failure.message ?: "Invalid local context request")
        } catch (_: Exception) {
            return error("invalid_request", "Local context planning is unavailable")
        }
    }

    @JvmStatic
    fun generate(requestJson: String): String = generateInternal(requestJson, benchmark = false)

    internal fun generateBenchmark(requestJson: String): String = generateInternal(requestJson, benchmark = true)

    /** Actual GGUF vocabulary count; never allocates an inference context. */
    @JvmStatic fun countPromptTokens(modelId: String, prompt: String): String {
        val context = applicationContext
        val root = modelRoot
        if (context == null || root == null || !libraryLoaded || initializationError != null)
            return error("engine_unavailable", "Native inference has not been initialized")
        return try {
            if (modelId !in supportedIds || prompt.isEmpty() || prompt.toByteArray(Charsets.UTF_8).size > LocalModelContext.MAX_TOKENIZER_PROMPT_BYTES)
                throw RequestError("invalid_request", "Invalid local tokenizer input")
            val weights = privateModelPath(context, root, modelId, File(root, "$modelId/model.gguf").absolutePath)
            if (!weights.isFile || installedDigest(weights, modelId) != MobileProviderSettings.expectedLocalModelDigest(modelId))
                throw RequestError("model_not_installed", "Install and verify the selected private Qwen model first")
            val request = JSONObject().put("model_id", modelId).put("model_path", weights.absolutePath).put("prompt", prompt)
            val encoded = request.toString().toByteArray(Charsets.UTF_8)
            if (encoded.size > LocalModelContext.MAX_TOKENIZER_REQUEST_BYTES)
                throw RequestError("invalid_request", "Local tokenizer transport request is too large")
            nativeCountPromptTokens(encoded).toString(Charsets.UTF_8)
        } catch (failure: RequestError) { error(failure.code, failure.message ?: "Invalid tokenizer request") }
        catch (_: OutOfMemoryError) { error("insufficient_memory", "Tokenizer allocation failed") }
        catch (_: Exception) { error("invalid_request", "Local tokenizer request is invalid") }
    }

    private fun generateInternal(requestJson: String, benchmark: Boolean): String {
        val context = applicationContext
        val root = modelRoot
        if (context == null || root == null || !libraryLoaded || initializationError != null)
            return error("engine_unavailable", initializationError ?: "Native inference has not been initialized")
        try {
            if (requestJson.length > 32 * 1024 * 1024 ||
                requestJson.toByteArray(Charsets.UTF_8).size > 32 * 1024 * 1024)
                throw RequestError("invalid_request", "Native inference request is too large")
            val request = JSONObject(requestJson)
            boundedInteger(request, "version", 1, 1)
            val id = request.opt("model_id")
            if (id !is String || id !in supportedIds)
                throw RequestError("invalid_request", "Select a supported small Qwen model")
            val requestId = request.opt("request_id")
            if (requestId !is String || !requestId.matches(Regex("[A-Za-z0-9_-]{1,80}")))
                throw RequestError("invalid_request", "Invalid native inference request ID")
            val nContext = boundedInteger(request, "context_size", LocalModelContext.MIN_CONTEXT_TOKENS,
                LocalModelContext.modelMaximumTokens(id))
            val nPredict = boundedInteger(request, "max_output_tokens", 1, LocalModelContext.MAX_OUTPUT_TOKENS)
            val memoryMode = if (request.has("memory_mode")) request.opt("memory_mode") else "balanced"
            if (memoryMode !is String || (memoryMode != "balanced" && memoryMode != "extended"))
                throw RequestError("invalid_request", "Invalid local memory mode")
            request.put("memory_mode", memoryMode)
            if (nPredict >= nContext)
                throw RequestError("context_exceeded", "Local output allowance leaves no room for the prompt")
            if (!benchmark) {
                request.put("threads", LocalModelPerformance.threads(runtimeSettings.threads,
                    Runtime.getRuntime().availableProcessors()))
                request.put("generation_timeout_ms", LocalModelPerformance.timeoutSeconds(
                    runtimeSettings.timeoutSeconds, nContext, JSONObject(status()).optJSONObject("last_generation")) * 1000)
            }
            boundedInteger(request, "threads", 1, LocalModelPerformance.MAX_THREADS)
            if (!request.has("generation_timeout_ms")) request.put("generation_timeout_ms", 180000)
            boundedInteger(request, "generation_timeout_ms", 1, LocalModelPerformance.MAX_TIMEOUT_SECONDS * 1000)
            val prompt = request.opt("prompt")
            if (prompt !is String || prompt.isEmpty() ||
                prompt.toByteArray(Charsets.UTF_8).size > LocalModelContext.MAX_PROMPT_BYTES)
                throw RequestError("invalid_request", "Local Qwen prompt is empty or too large")
            val rawTemperature = request.opt("temperature")
            if (rawTemperature !is Number || !rawTemperature.toDouble().isFinite() ||
                rawTemperature.toDouble() !in 0.0..2.0)
                throw RequestError("invalid_request", "Invalid local Qwen temperature")
            val path = request.opt("model_path")
            // Android exposes the app's own filesDir under /data/user/0 while
            // Java canonicalFile may spell the same private inode /data/data.
            // Accept only the OS-provided app path or our canonical root, then
            // pass the canonical spelling to JNI. Model/file symlinks remain
            // forbidden under either spelling.
            val expected = privateModelPath(context, root, id, path)
            request.put("model_path", expected.absolutePath)
            if (!expected.isFile || expected.length() !in 16L..(3L * 1024 * 1024 * 1024))
                throw RequestError("model_not_installed", "The selected local Qwen model is not installed")
            val state = JSONObject(status())
            if (state.optBoolean("generating"))
                throw RequestError("engine_busy", "Another local Qwen generation is running")
            val memory = ActivityManager.MemoryInfo()
            (context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).getMemoryInfo(memory)
            // Python verifies the actual file against this pinned SHA before
            // calling JNI. Only its matching install marker and file size may
            // use the measured hybrid shape; all other files retain the broad
            // Qwen3 cache allowance. Switching counts the new weights in full.
            var required = LocalModelMemory.estimate(id, expected.length(), nContext,
                state.optString("loaded_model"), installedDigest(expected, id)).requiredBytes
            if (request.has("images"))
                throw RequestError("invalid_image", "Local image RGB metadata is internal to the bridge")
            val imageCount = try { LocalModelImages.count(request) }
                catch (_: IllegalArgumentException) {
                    throw RequestError("invalid_image", "Attach one to four supported local images")
                }
            if (imageCount > 0) {
                val projection = when {
                    id.startsWith("qwen3.5-0.8b-") -> smallVision
                    id.startsWith("qwen3.5-2b-") -> mediumVision
                    else -> throw RequestError("unsupported_vision", "Select Qwen3.5 to read local images")
                }
                val projectionFile = privateModelPath(context, root, projection.id,
                    request.opt("projection_path"), "invalid_projection_path")
                if (!projectionFile.isFile || projectionFile.length() != projection.bytes ||
                    installedDigest(projectionFile, projection.id) != projection.sha256)
                    throw RequestError("projection_not_installed",
                        "Install and verify the matching local Qwen vision projection to read images")
                request.put("projection_path", projectionFile.absolutePath)
                required = LocalModelMemory.visionRequiredBytes(required, projection.bytes)
            }
            val swap = if (memoryMode == "extended") availableSwapBytes() else 0L
            val physicalCompute = LocalModelMemory.TEXT_COMPUTE_RESERVE_BYTES +
                if (imageCount > 0) LocalModelMemory.VISION_COMPUTE_RESERVE_BYTES else 0L
            val estimateFeasible = LocalModelMemory.canLoad(memory.lowMemory, memory.availMem, required, swap, memoryMode,
                physicalComputeReserveBytes = physicalCompute)
            if (!LocalModelPerformance.mayAttemptAllocation(benchmark || runtimeSettings.contextTokens > 0, estimateFeasible))
                throw RequestError("insufficient_memory", "Not enough available memory for this model and context; choose a smaller context or model")
            val images = try { LocalModelImages.prepare(request) }
                catch (_: IllegalArgumentException) {
                    throw RequestError("invalid_image", "Local image file, format, encoding or dimensions are invalid")
                }
            val nativeRequest = request.toString().toByteArray(Charsets.UTF_8)
            if (nativeRequest.size > LocalModelContext.MAX_REQUEST_BYTES)
                throw RequestError("invalid_request", "Native inference request is too large")
            return nativeGenerate(nativeRequest, images)
                .toString(Charsets.UTF_8)
        } catch (failure: RequestError) {
            return error(failure.code, failure.message ?: "Invalid local inference request")
        } catch (_: OutOfMemoryError) {
            return error("insufficient_memory", "Not enough free memory for local Qwen generation")
        } catch (_: Exception) {
            return error("invalid_request", "Local Qwen request or model file is invalid")
        }
    }

    /** Request-scoped cancellation also remembers a cancellation before a worker enters JNI. */
    @JvmStatic fun cancelRequest(requestId: String) {
        if (libraryLoaded && requestId.matches(Regex("[A-Za-z0-9_-]{1,80}")))
            nativeCancel(requestId.toByteArray(Charsets.UTF_8))
    }

    @JvmStatic fun cancel() {
        if (libraryLoaded) nativeCancel(ByteArray(0))
    }

    /** Call from a worker: cancels active work, waits for CPU abort, then frees weights. */
    @JvmStatic fun unload() {
        if (libraryLoaded) {
            cancel()
            nativeUnload()
        }
    }

    // UTF-8 byte arrays avoid JNI modified UTF-8 corrupting emoji and supplementary characters.
    private external fun nativeInitialize(root: ByteArray): ByteArray
    private external fun nativeStatus(): ByteArray
    private external fun nativeGenerate(request: ByteArray, images: Array<ByteArray>): ByteArray
    private external fun nativeCountPromptTokens(request: ByteArray): ByteArray
    private external fun nativeCancel(requestId: ByteArray)
    private external fun nativeUnload()
}
