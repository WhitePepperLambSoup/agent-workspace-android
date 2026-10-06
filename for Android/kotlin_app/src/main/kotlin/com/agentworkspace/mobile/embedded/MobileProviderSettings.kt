package com.agentworkspace.mobile.embedded

import com.agentworkspace.mobile.localmodels.TrainedLocalModel
import com.agentworkspace.mobile.localmodels.LocalModelPerformance

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.net.URI
import java.io.File
import java.nio.file.Files
import java.security.MessageDigest

data class MobileProviderPreset(
    val name: String,
    val protocol: String,
    val baseUrl: String?,
    val models: List<String>,
)

data class MobileProviderSettings(
    val protocol: String = "openai-compatible",
    val baseUrl: String = "https://api.openai.com/v1",
    val model: String = "gpt-6-sol",
    val apiKey: String? = null,
    val reasoningEffort: String = "auto",
    val autonomy: String = "workspace",
    val localContextTokens: Int = 0,
    val localMemoryMode: String = "balanced",
    val localThreads: Int = 0,
    val localTimeoutSeconds: Int = 0,
    val contextSummaryEnabled: Boolean = defaultContextSummaryEnabled(baseUrl),
) {
    fun toJson(): String = JSONObject().apply {
        put("id", protocol)
        put("protocol", protocol)
        put("base_url", baseUrl)
        put("model", model)
        put("reasoning_effort", reasoningEffort)
        put("autonomy", autonomy)
        put("local_context_tokens", localContextTokens)
        put("local_memory_mode", localMemoryMode)
        put("local_threads", localThreads)
        put("local_timeout_seconds", localTimeoutSeconds)
        put("context_summary_enabled", contextSummaryEnabled)
        if (!apiKey.isNullOrBlank()) put("api_key", apiKey)
    }.toString()

    fun toPublicJson(): String = JSONObject().apply {
        put("protocol", protocol)
        put("base_url", baseUrl)
        put("model", model)
        put("reasoning_effort", reasoningEffort)
        put("autonomy", autonomy)
        put("local_context_tokens", localContextTokens)
        put("local_memory_mode", localMemoryMode)
        put("local_threads", localThreads)
        put("local_timeout_seconds", localTimeoutSeconds)
        put("context_summary_enabled", contextSummaryEnabled)
        put("context_summary_experimental", experimentalContextSummary(baseUrl))
        put("local_context_min_tokens", 512)
        put("local_context_max_tokens", 262144)
        put("local_max_threads", LocalModelPerformance.MAX_THREADS)
        put("local_max_timeout_seconds", LocalModelPerformance.MAX_TIMEOUT_SECONDS)
        put("local_context_options", JSONArray(localContextOptions))
        put("local_memory_modes", JSONArray(localMemoryModes))
        put("has_api_key", !apiKey.isNullOrBlank())
        val models = (providerPresets[presetIndex(protocol, baseUrl)].models + model).distinct()
        put("models", JSONArray(models))
        put("model_efforts", JSONObject().apply {
            models.forEach { put(it, JSONArray(reasoningEfforts(protocol, baseUrl, it))) }
        })
    }.toString()

    companion object {
        val protocols = arrayOf("openai-compatible", "anthropic", "gemini", "ollama")
        val autonomies = listOf("workspace", "yolo", "full_access")
        val localContextOptions = listOf(0, 4096, 8192, 16384, 32768, 65536, 131072, 262144)
        val localMemoryModes = listOf("balanced", "extended")
        private fun validLocalContext(tokens: Int) = tokens == 0 || tokens in 512..262144
        private val thinkingLevels = listOf("low", "medium", "high", "xhigh", "max")
        private val openAiModels = listOf(
            "gpt-6-sol", "gpt-6-luna", "gpt-6-astra",
            "gpt-5.6-sol",
            "gpt-5.6-terra",
            "gpt-5.6-luna",
        )
        private val anthropicModels = listOf(
            "claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-1",
            "claude-opus-5", "claude-fable-5",
        )
        private val geminiModels = listOf("gemini-3.8-flash", "gemini-3.7-flash")
        private val deepSeekModels = listOf("deepseek-flash", "deepseek-v4-pro")
        private val grokModels = listOf("grok-4.7", "grok-4.6")
        private val qwenModels = listOf(
            "qwen3.8-max", "qwen3.8-max-0902", "qwen3.8-flash", "qwen3.7-plus",
        )
        private val kimiModels = listOf(
            "kimi-k3", "kimi-k2.7-code", "kimi-k2.7-code-highspeed", "kimi-k2.6",
        )
        private val glmModels = listOf(
            "glm-5.3", "glm-5.3-flash", "glm-5.3-flashx", "glm-5.2",
        )
        private val miniMaxModels = listOf(
            "MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.7-highspeed",
            "MiniMax-M2.5", "MiniMax-M2.5-highspeed", "MiniMax-M2.1",
            "MiniMax-M2.1-highspeed", "MiniMax-M2",
        )
        private val mistralModels = listOf(
            "zai-glm-5-3", "zai-glm-5-2", "zai-glm-5", "zai-glm-latest",
            "mistral-medium-3-5", "mistral-medium-3", "mistral-medium-latest",
            "mistral-small-2603", "mistral-small-latest",
            "mistral-large-2512", "mistral-large-latest",
            "ministral-14b-2512", "ministral-8b-2512", "ministral-3b-2512",
            "ministral-14b-latest", "ministral-8b-latest", "ministral-3b-latest",
        )
        private val cohereModels = listOf(
            "command-a-plus-05-2026", "command-a-03-2025",
            "command-a-reasoning-08-2025", "command-r7b-12-2024",
            "command-r-08-2024", "command-r-plus-08-2024",
        )
        private val ollamaModels = listOf(
            "qwen3-coder:latest", "qwen3:latest", "deepseek-r1:latest", "gemma3:latest",
        )
        const val EMBEDDED_QWEN_BASE_URL = "http://127.0.0.1:8080/embedded-qwen/v1"
        fun experimentalContextSummary(baseUrl: String): Boolean =
            baseUrl.trimEnd('/') == EMBEDDED_QWEN_BASE_URL
        fun defaultContextSummaryEnabled(baseUrl: String): Boolean = !experimentalContextSummary(baseUrl)
        val embeddedQwenModels = listOf(
            "qwen3.5-0.8b-q4-k-m", "qwen3.5-0.8b-q8-0",
            "qwen3.5-2b-q4-k-m", "qwen3.5-2b-q8-0",
            "qwen3-0.6b-q4-k-m", "qwen3-0.6b-q8-0",
            "qwen3-1.7b-q4-k-m", "qwen3-1.7b-q8-0",
        ) + listOfNotNull(TrainedLocalModel.spec?.id)
        private val embeddedQwenDigests = listOf(
            "bd258782e35f7f458f8aced1adc053e6e92e89bc735ba3be89d38a06121dc517",
            "0ad885ffd4bb022fc4f0d33a3308fa108ef8613159d3b3a67e23abca056b7a6c",
            "aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223",
            "1b04acba824817554f4ce23639bc8495ff70453b8fcb047900c731521021f2c1",
            "ac2d97712095a558e31573f62f466a3f9d93990898b0ec79d7c974c1780d524a",
            "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031",
            "b139949c5bd74937ad8ed8c8cf3d9ffb1e99c866c823204dc42c0d91fa181897",
            "061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a",
        ) + listOfNotNull(TrainedLocalModel.spec?.sha256)

        fun expectedLocalModelDigest(model: String): String? = embeddedQwenModels.indexOf(model)
            .takeIf { it >= 0 }?.let { embeddedQwenDigests[it] }
        private val cloudModels = (
            openAiModels + anthropicModels + geminiModels + deepSeekModels + grokModels +
                qwenModels + kimiModels + glmModels + miniMaxModels + mistralModels + cohereModels +
                listOf("deepseek-v4-pro-0813")
            ).distinct()
        private val modelsByProtocol = mapOf(
            "openai-compatible" to cloudModels,
            "anthropic" to anthropicModels,
            "gemini" to geminiModels,
            "ollama" to ollamaModels,
        )
        val providerPresets = listOf(
            MobileProviderPreset("OpenAI", "openai-compatible", "https://api.openai.com/v1", openAiModels),
            MobileProviderPreset("DeepSeek", "openai-compatible", "https://api.deepseek.com", deepSeekModels),
            MobileProviderPreset("Anthropic", "anthropic", "https://api.anthropic.com/v1", anthropicModels),
            MobileProviderPreset("Gemini", "gemini", "https://generativelanguage.googleapis.com/v1beta", geminiModels),
            MobileProviderPreset("xAI", "openai-compatible", "https://api.x.ai/v1", grokModels),
            MobileProviderPreset("Qwen (China)", "openai-compatible", "https://dashscope.aliyuncs.com/compatible-mode/v1", qwenModels),
            MobileProviderPreset("Qwen (International)", "openai-compatible", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", qwenModels),
            MobileProviderPreset("Kimi", "openai-compatible", "https://api.moonshot.ai/v1", kimiModels),
            MobileProviderPreset("GLM (Z.AI)", "openai-compatible", "https://api.z.ai/api/paas/v4", glmModels),
            MobileProviderPreset("GLM (China)", "openai-compatible", "https://open.bigmodel.cn/api/paas/v4", glmModels),
            MobileProviderPreset("MiniMax", "openai-compatible", "https://api.minimax.io/v1", miniMaxModels),
            MobileProviderPreset("Mistral", "openai-compatible", "https://api.mistral.ai/v1", mistralModels),
            MobileProviderPreset("Cohere", "openai-compatible", "https://api.cohere.ai/compatibility/v1", cohereModels),
            MobileProviderPreset("Ollama", "ollama", "http://127.0.0.1:11434", ollamaModels),
            MobileProviderPreset("本机 Qwen", "openai-compatible", EMBEDDED_QWEN_BASE_URL, embeddedQwenModels),
        ) + protocols.map { protocol ->
            val name = when (protocol) {
                "openai-compatible" -> "OpenAI"
                "anthropic" -> "Anthropic"
                "gemini" -> "Gemini"
                else -> "Ollama"
            }
            MobileProviderPreset("Custom ($name)", protocol, null, modelSuggestions(protocol))
        }
        private const val PREFERENCES = "agent-workspace-provider"

        private fun verifyLocalWeights(context: Context, model: String) {
            val index = embeddedQwenModels.indexOf(model)
            require(index >= 0) { "选择受支持的本机 Qwen 模型" }
            val files = context.filesDir.canonicalFile
            val root = File(files, "agent-data/local-models")
            val directory = File(root, model)
            val weights = File(directory, "model.gguf")
            val marker = File(directory, "installed.json")
            require(root.canonicalFile == root && directory.canonicalFile == directory &&
                weights.canonicalFile == weights && marker.canonicalFile == marker &&
                !Files.isSymbolicLink(weights.toPath()) && !Files.isSymbolicLink(marker.toPath()) &&
                marker.isFile && marker.length() <= 4096 && weights.isFile) {
                "请先在本地模型菜单下载并校验模型"
            }
            val metadata = JSONObject(marker.readText())
            require(metadata.optString("model_id") == model &&
                metadata.optString("sha256") == embeddedQwenDigests[index] &&
                metadata.optLong("size") == weights.length()) { "模型安装记录校验失败" }
            val digest = MessageDigest.getInstance("SHA-256")
            weights.inputStream().buffered(1024 * 1024).use { input ->
                val buffer = ByteArray(1024 * 1024)
                while (true) { val count = input.read(buffer); if (count < 0) break; digest.update(buffer, 0, count) }
            }
            require(digest.digest().joinToString("") { "%02x".format(it) } == embeddedQwenDigests[index]) {
                "模型文件校验失败，请重新下载"
            }
        }

        fun selectLocalModel(context: Context, modelId: String) = synchronized(this) {
            val current = load(context)
            save(context, "openai-compatible", EMBEDDED_QWEN_BASE_URL, modelId, null, false,
                "auto", current.autonomy)
            load(context)
        }

        fun restorePreviousProvider(context: Context) = synchronized(this) {
            val value = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
                .getString("previous_remote", null)
                ?: throw IllegalStateException("尚无原模型配置")
            val previous = JSONObject(value)
            val base = previous.getString("base_url")
            require(base.trimEnd('/') != EMBEDDED_QWEN_BASE_URL) { "原模型配置无效" }
            save(context, previous.getString("protocol"), base, previous.getString("model"),
                null, false, previous.optString("reasoning_effort", "auto"),
                previous.optString("autonomy", "workspace"))
            load(context)
        }

        fun reasoningEfforts(protocol: String, baseUrl: String, model: String): List<String> {
            val uri = runCatching { URI(baseUrl) }.getOrNull()
            val officialHttps = uri?.scheme == "https" && uri.port in listOf(-1, 443)
            fun matches(vararg names: String) = names.any { model == it || model.startsWith("$it-") }
            if (protocol == "openai-compatible" && officialHttps && uri?.host == "api.openai.com") {
                if (matches("gpt-6-astra")) return listOf("auto") + thinkingLevels
                if (matches("gpt-6-sol", "gpt-6-luna", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")) {
                    return listOf("auto", "none") + thinkingLevels
                }
            }
            if (protocol == "openai-compatible" && officialHttps && uri?.host == "api.deepseek.com" &&
                matches("deepseek-flash", "deepseek-v4-pro")) {
                return listOf("auto", "none", "low", "high", "max")
            }
            if (protocol == "anthropic" && matches("claude-fable-5", "claude-opus-5", "claude-sonnet-5-5")) {
                return listOf("auto") + thinkingLevels
            }
            return listOf("auto")
        }

        fun modelSuggestions(protocol: String): List<String> =
            modelsByProtocol[protocol] ?: emptyList()

        fun presetIndex(protocol: String, baseUrl: String): Int {
            val known = providerPresets.indexOfFirst {
                it.protocol == protocol && it.baseUrl != null &&
                    it.baseUrl.trimEnd('/').equals(baseUrl.trimEnd('/'), ignoreCase = true)
            }
            if (known >= 0) return known
            return providerPresets.indexOfFirst { it.protocol == protocol && it.baseUrl == null }
                .coerceAtLeast(0)
        }

        fun load(context: Context): MobileProviderSettings {
            EmbeddedSecrets.initialize(context)
            val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            val defaults = MobileProviderSettings()
            val protocol = preferences.getString("protocol", defaults.protocol)!!
            val baseUrl = preferences.getString("base_url", defaults.baseUrl)!!
            val model = preferences.getString("model", defaults.model)!!
            val effort = preferences.getString("reasoning_effort", "auto")
                ?.takeIf { it in reasoningEfforts(protocol, baseUrl, model) } ?: "auto"
            val autonomy = preferences.getString("autonomy", "workspace")
                ?.takeIf { it in autonomies } ?: "workspace"
            val contextTokens = preferences.getString("local_context_tokens", "0")
                ?.toIntOrNull()?.takeIf { validLocalContext(it) } ?: 0
            val memoryMode = preferences.getString("local_memory_mode", "balanced")
                ?.takeIf { it in localMemoryModes } ?: "balanced"
            return MobileProviderSettings(
                protocol, baseUrl, model,
                EmbeddedSecrets.getCredential(credentialTarget(protocol, baseUrl)), effort, autonomy,
                contextTokens, memoryMode,
                preferences.getString("local_threads", "0")?.toIntOrNull()
                    ?.takeIf { it in 0..LocalModelPerformance.MAX_THREADS } ?: 0,
                preferences.getString("local_timeout_seconds", "0")?.toIntOrNull()
                    ?.takeIf { it in 0..LocalModelPerformance.MAX_TIMEOUT_SECONDS } ?: 0,
                preferences.getString("context_summary_enabled", null)?.toBooleanStrictOrNull()
                    ?: defaultContextSummaryEnabled(baseUrl),
            )
        }

        fun validateLocalContext(baseUrl: String, model: String, contextTokens: Int) {
            require(validLocalContext(contextTokens)) { "Invalid local context size" }
            if (baseUrl.trimEnd('/') != EMBEDDED_QWEN_BASE_URL) return
            require(model in embeddedQwenModels) { "Select a supported downloaded Qwen model" }
            val maximum = if (model.startsWith("qwen3.5-")) 262144 else 32768
            require(contextTokens == 0 || contextTokens <= maximum) {
                "Qwen3 本地上下文最多 32768 token。请先选择自动或不超过 32K。Qwen3.5 可选择到 262144 token。"
            }
        }

        fun save(context: Context, protocol: String, baseUrl: String, model: String,
                 newApiKey: String?, deleteApiKey: Boolean,
                 reasoningEffort: String? = null, autonomy: String? = null,
                 localContextTokens: Int? = null, localMemoryMode: String? = null,
                 localThreads: Int? = null, localTimeoutSeconds: Int? = null,
                 contextSummaryEnabled: Boolean? = null) {
            require(protocol in protocols) { "Invalid provider protocol" }
            require(model.isNotBlank() && model.length <= 256) { "Invalid model name" }
            require(localContextTokens == null || validLocalContext(localContextTokens)) {
                "Invalid local context size"
            }
            require(localMemoryMode == null || localMemoryMode in localMemoryModes) {
                "Invalid local memory mode"
            }
            require(localThreads == null || localThreads in 0..LocalModelPerformance.MAX_THREADS) { "Invalid local threads" }
            require(localTimeoutSeconds == null || localTimeoutSeconds in 0..LocalModelPerformance.MAX_TIMEOUT_SECONDS) { "Invalid local timeout" }
            val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            val contextTokens = localContextTokens ?: preferences.getString("local_context_tokens", "0")
                ?.toIntOrNull()?.takeIf { validLocalContext(it) } ?: 0
            validateLocalContext(baseUrl, model, contextTokens)
            if (baseUrl.trimEnd('/') == EMBEDDED_QWEN_BASE_URL) {
                require(protocol == "openai-compatible" && model in embeddedQwenModels) {
                    "Select a supported downloaded Qwen model"
                }
                verifyLocalWeights(context, model)
            }
            val uri = URI(baseUrl)
            require(uri.scheme in listOf("http", "https") && !uri.host.isNullOrBlank()) {
                "Use an absolute HTTP(S) endpoint"
            }
            require(uri.userInfo == null && uri.query == null && uri.fragment == null) {
                "Endpoint may not contain credentials, query parameters, or a fragment"
            }
            require(uri.scheme == "https" || uri.host in listOf("localhost", "127.0.0.1", "::1", "[::1]")) {
                "Remote endpoints require HTTPS"
            }
            if (baseUrl.trimEnd('/') == EMBEDDED_QWEN_BASE_URL) {
                val previous = load(context)
                if (previous.baseUrl.trimEnd('/') != EMBEDDED_QWEN_BASE_URL) {
                    check(preferences.edit().putString("previous_remote", previous.toPublicJson())
                        .commit()) { "Failed to preserve previous provider settings" }
                }
            }
            val supported = reasoningEfforts(protocol, baseUrl, model)
            val effort = reasoningEffort ?: preferences.getString("reasoning_effort", "auto")
                ?.takeIf { it in supported } ?: "auto"
            require(effort in supported) { "Unsupported reasoning effort for this model" }
            val mode = autonomy ?: preferences.getString("autonomy", "workspace")
                ?.takeIf { it in autonomies } ?: "workspace"
            require(mode in autonomies) { "Invalid execution mode" }
            val memoryMode = localMemoryMode ?: preferences.getString("local_memory_mode", "balanced")
                ?.takeIf { it in localMemoryModes } ?: "balanced"
            val performance = load(context)
            EmbeddedSecrets.initialize(context)
            val target = credentialTarget(protocol, baseUrl)
            if (deleteApiKey) EmbeddedSecrets.deleteCredential(target)
            else if (!newApiKey.isNullOrBlank()) EmbeddedSecrets.setCredential(target, newApiKey)
            val editor = preferences.edit()
                .putString("protocol", protocol)
                .putString("base_url", baseUrl)
                .putString("model", model)
                .putString("reasoning_effort", effort)
                .putString("autonomy", mode)
                .putString("local_context_tokens", contextTokens.toString())
                .putString("local_memory_mode", memoryMode)
                .putString("local_threads", (localThreads ?: performance.localThreads).toString())
                .putString("local_timeout_seconds", (localTimeoutSeconds ?: performance.localTimeoutSeconds).toString())
            if (contextSummaryEnabled != null) {
                editor.putString("context_summary_enabled", contextSummaryEnabled.toString())
            }
            check(editor.commit()) { "Failed to save provider settings" }
        }

        fun applyRuntimeSettings(context: Context, settingsJson: String): MobileProviderSettings = synchronized(this) {
            require(settingsJson.length <= 4096) { "Settings payload is too large" }
            val update = JSONObject(settingsJson)
            val allowed = setOf("model", "reasoning_effort", "autonomy", "local_context_tokens", "local_memory_mode", "local_threads", "local_timeout_seconds", "context_summary_enabled")
            require(update.keys().asSequence().all { it in allowed }) { "Unsupported settings field" }
            val current = load(context)
            fun setting(name: String, fallback: String): String {
                if (!update.has(name)) return fallback
                return (update.get(name) as? String)?.trim()
                    ?: throw IllegalArgumentException("Invalid settings value")
            }
            val model = setting("model", current.model)
            val contextTokens = if (update.has("local_context_tokens")) {
                val value = update.get("local_context_tokens")
                require(value is Int && validLocalContext(value)) { "Invalid local context size" }
                value
            } else current.localContextTokens
            val memoryMode = setting("local_memory_mode", current.localMemoryMode)
            require(memoryMode in localMemoryModes) { "Invalid local memory mode" }
            val threads = LocalModelPerformance.integer(update, "local_threads", LocalModelPerformance.MAX_THREADS, current.localThreads)
            val timeout = LocalModelPerformance.integer(update, "local_timeout_seconds", LocalModelPerformance.MAX_TIMEOUT_SECONDS, current.localTimeoutSeconds)
            val summaryEnabled = if (update.has("context_summary_enabled")) {
                update.get("context_summary_enabled") as? Boolean
                    ?: throw IllegalArgumentException("Invalid context summary setting")
            } else null
            val supported = reasoningEfforts(current.protocol, current.baseUrl, model)
            val effort = if (update.has("reasoning_effort")) {
                setting("reasoning_effort", current.reasoningEffort)
            } else {
                current.reasoningEffort.takeIf { it in supported } ?: "auto"
            }
            save(context, current.protocol, current.baseUrl, model, null, false,
                effort, setting("autonomy", current.autonomy), contextTokens, memoryMode, threads, timeout,
                summaryEnabled)
            load(context)
        }

        /** The API key stored for this provider address, if any (keys are kept per address). */
        fun apiKeyFor(context: Context, protocol: String, baseUrl: String): String? {
            EmbeddedSecrets.initialize(context)
            return EmbeddedSecrets.getCredential(credentialTarget(protocol, baseUrl))
        }

        private fun credentialTarget(protocol: String, baseUrl: String): String {
            val uri = URI(baseUrl)
            val port = if (uri.port >= 0) uri.port else if (uri.scheme == "https") 443 else 80
            val origin = "${uri.scheme}://${uri.host.lowercase()}:$port"
            val hash = MessageDigest.getInstance("SHA-256").digest(origin.toByteArray())
                .joinToString("") { "%02x".format(it) }
            return "mobile-provider/$protocol/$hash"
        }
    }
}
