package com.agentworkspace.mobile.embedded

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.URLEncoder
import java.security.MessageDigest

/**
 * The models a provider offers, read from its own model list (OpenAI-compatible `/models`,
 * Anthropic `/v1/models`, Gemini `models`, Ollama `/api/tags`) once the address and key are in, as
 * mainstream chat apps do. Capability tags come only from what the provider says about a model
 * (OpenRouter's modalities and parameters, Gemini's limits); nothing is guessed from names.
 *
 * The key goes only to the address the user entered: redirects are not followed.
 */
object ProviderModelCatalog {
    data class Model(
        val id: String,
        val name: String? = null,
        val contextTokens: Int? = null,
        val vision: Boolean? = null,
        val tools: Boolean? = null,
        val reasoning: Boolean? = null,
        val created: Long? = null,
    ) {
        fun json(): JSONObject = JSONObject().put("id", id).apply {
            name?.let { put("name", it) }
            contextTokens?.let { put("context_tokens", it) }
            vision?.let { put("vision", it) }
            tools?.let { put("tools", it) }
            reasoning?.let { put("reasoning", it) }
        }

        companion object {
            fun from(value: JSONObject) = Model(
                value.getString("id"), value.optString("name").ifBlank { null },
                value.optInt("context_tokens", 0).takeIf { it > 0 },
                if (value.has("vision")) value.getBoolean("vision") else null,
                if (value.has("tools")) value.getBoolean("tools") else null,
                if (value.has("reasoning")) value.getBoolean("reasoning") else null,
            )
        }
    }

    /** A list read some time ago, kept so the dialog and the model sheet open with it at once. */
    data class Listing(val models: List<Model>, val fetchedAt: Long)

    /** A failure in both languages; [fetch] throws it in the app's language. */
    class Failure(val zh: String, val en: String = zh) : Exception(zh)

    private const val DIRECTORY = "provider-models"
    private const val MAX_MODELS = 600
    private const val MAX_BYTES = 8 * 1024 * 1024
    private const val MAX_PAGES = 5

    // Not chat models: embeddings, speech, image and video generation, moderation, reranking.
    private val notChat = listOf(
        "embed", "tts", "whisper", "dall-e", "moderation", "rerank", "transcribe", "gpt-image", "sora",
        "speech", "text-to-image",
    )

    fun isChatModel(id: String): Boolean = notChat.none { id.lowercase().contains(it) }

    private fun key(protocol: String, baseUrl: String): String =
        MessageDigest.getInstance("SHA-256").digest("$protocol ${baseUrl.trimEnd('/').lowercase()}".toByteArray())
            .joinToString("") { "%02x".format(it) }

    // A file per provider address rather than shared preferences: the phone control panel reads the
    // list in the engine process, where preferences loaded earlier would not see a newer list.
    private fun file(context: Context, protocol: String, baseUrl: String) =
        java.io.File(java.io.File(context.filesDir, DIRECTORY), "${key(protocol, baseUrl)}.json")

    fun cached(context: Context, protocol: String, baseUrl: String): Listing? = runCatching {
        val source = file(context, protocol, baseUrl).takeIf { it.isFile && it.length() <= MAX_BYTES } ?: return null
        val value = JSONObject(source.readText())
        val models = value.getJSONArray("models")
        Listing((0 until models.length()).map { Model.from(models.getJSONObject(it)) }, value.getLong("fetched_at"))
    }.getOrNull()

    private fun remember(context: Context, protocol: String, baseUrl: String, models: List<Model>) {
        val value = JSONObject().put("fetched_at", System.currentTimeMillis())
            .put("models", JSONArray().apply { models.forEach { put(it.json()) } })
        val target = file(context, protocol, baseUrl)
        target.parentFile?.mkdirs()
        val partial = java.io.File(target.path + ".partial")
        partial.writeText(value.toString())
        check(partial.renameTo(target)) { "Could not keep the model list" }
    }

    /**
     * Reads the provider's list (blocking; call off the main thread) and keeps it for next time.
     * [allowLanHttp]: plain HTTP to a private-network address, as chosen in the model settings.
     */
    fun fetch(context: Context, protocol: String, baseUrl: String, apiKey: String?, allowLanHttp: Boolean = false): List<Model> = try {
        read(context, protocol, baseUrl, apiKey, allowLanHttp)
    } catch (failure: Failure) {
        val text = com.agentworkspace.mobile.UiText.of(context, failure.zh, failure.en)
        throw Failure(text, text)
    }

    private fun read(context: Context, protocol: String, baseUrl: String, apiKey: String?, allowLanHttp: Boolean): List<Model> {
        val base = baseUrl.trim().trimEnd('/')
        val uri = runCatching { URI(base) }.getOrNull() ?: throw Failure("地址无效", "Invalid address")
        if (uri.scheme !in listOf("http", "https") || uri.host.isNullOrBlank() || uri.userInfo != null ||
            uri.query != null || uri.fragment != null) throw Failure("请填写完整的 http(s) 地址", "Enter a full http(s) address")
        if (!ProviderEndpoints.allowed(uri.scheme, uri.host, allowLanHttp)) {
            throw if (ProviderEndpoints.isPrivateLanHost(uri.host)) {
                Failure("这是局域网地址：勾选「允许局域网 HTTP」后才能用 http 连接", "This is a local network address: turn on Allow local network HTTP to connect over http")
            } else {
                Failure("远程地址需要 HTTPS", "Remote addresses need HTTPS")
            }
        }
        if (base == MobileProviderSettings.EMBEDDED_QWEN_BASE_URL) throw Failure("本机模型在「本地模型」里下载和选择", "On-device models are downloaded and chosen under Local models")
        val key = apiKey?.trim()?.ifEmpty { null } ?: runCatching {
            MobileProviderSettings.apiKeyFor(context, protocol, base)
        }.getOrNull()
        val models = when (protocol) {
            "anthropic" -> anthropic(base, key)
            "gemini" -> gemini(base, key)
            "ollama" -> ollama(base)
            else -> openAi(base, key)
        }.filter { isChatModel(it.id) }.distinctBy { it.id }.take(MAX_MODELS)
        if (models.isEmpty()) throw Failure("服务没有列出可用于对话的模型，请手动填写模型名称", "The service lists no chat models; type the model name")
        remember(context, protocol, base, models)
        return models
    }

    private val unknownFormat get() = Failure("服务返回的模型列表格式无法识别", "The service's model list is in an unknown format")

    private fun openAi(base: String, key: String?): List<Model> =
        parseOpenAi(get("$base/models", key?.let { mapOf("Authorization" to "Bearer $it") } ?: emptyMap()))

    /** An OpenAI-compatible list; OpenRouter (and services copying it) describe each model too. */
    internal fun parseOpenAi(body: JSONObject): List<Model> {
        val data = body.optJSONArray("data") ?: body.optJSONArray("models") ?: throw unknownFormat
        val models = (0 until data.length()).mapNotNull { data.optJSONObject(it) }.mapNotNull { item ->
            val id = item.optString("id").ifBlank { item.optString("name") }.takeIf { it.isNotBlank() && it.length <= 256 }
                ?: return@mapNotNull null
            val modalities = item.optJSONObject("architecture")?.optJSONArray("input_modalities")
            val parameters = item.optJSONArray("supported_parameters")
            fun has(array: JSONArray?, value: String) = array != null && (0 until array.length()).any { array.optString(it) == value }
            Model(
                id, item.optString("name").takeIf { it.isNotBlank() && it != id },
                item.optInt("context_length", 0).takeIf { it > 0 },
                modalities?.let { has(it, "image") },
                parameters?.let { has(it, "tools") },
                parameters?.let { has(it, "reasoning") || has(it, "include_reasoning") },
                item.optLong("created", 0).takeIf { it > 0 },
            )
        }
        // Newest first when the service dates its models (OpenAI, OpenRouter); its own order otherwise.
        return if (models.count { it.created != null } > models.size / 2) models.sortedByDescending { it.created ?: 0 } else models
    }

    private fun anthropic(base: String, key: String?): List<Model> {
        val headers = mapOf("anthropic-version" to "2023-06-01") + (key?.let { mapOf("x-api-key" to it) } ?: emptyMap())
        val models = mutableListOf<Model>()
        var after: String? = null
        repeat(MAX_PAGES) {
            val (page, next) = parseAnthropicPage(get("$base/models?limit=1000" +
                (after?.let { "&after_id=" + URLEncoder.encode(it, "UTF-8") } ?: ""), headers))
            models += page
            after = next ?: return models
        }
        return models
    }

    /** One page of Anthropic's list, and the id to continue after when there is more. */
    internal fun parseAnthropicPage(body: JSONObject): Pair<List<Model>, String?> {
        val data = body.optJSONArray("data") ?: throw unknownFormat
        val models = (0 until data.length()).mapNotNull { data.optJSONObject(it) }.mapNotNull { item ->
            item.optString("id").takeIf { it.isNotBlank() }?.let { Model(it, item.optString("display_name").ifBlank { null }) }
        }
        val next = body.optString("last_id").takeIf { body.optBoolean("has_more") && data.length() > 0 && it.isNotBlank() }
        return models to next
    }

    private fun gemini(base: String, key: String?): List<Model> {
        val headers = key?.let { mapOf("x-goog-api-key" to it) } ?: emptyMap()
        val models = mutableListOf<Model>()
        var token: String? = null
        repeat(MAX_PAGES) {
            val (page, next) = parseGeminiPage(get("$base/models?pageSize=1000" +
                (token?.let { "&pageToken=" + URLEncoder.encode(it, "UTF-8") } ?: ""), headers))
            models += page
            token = next ?: return models
        }
        return models
    }

    /** One page of Gemini's list (chat models only), and the token of the next page. */
    internal fun parseGeminiPage(body: JSONObject): Pair<List<Model>, String?> {
        val data = body.optJSONArray("models") ?: throw unknownFormat
        val models = (0 until data.length()).mapNotNull { data.optJSONObject(it) }.mapNotNull { item ->
            val methods = item.optJSONArray("supportedGenerationMethods")
            if (methods != null && (0 until methods.length()).none { methods.optString(it) == "generateContent" }) return@mapNotNull null
            val id = item.optString("name").removePrefix("models/").takeIf { it.isNotBlank() } ?: return@mapNotNull null
            Model(id, item.optString("displayName").ifBlank { null },
                item.optInt("inputTokenLimit", 0).takeIf { it > 0 },
                reasoning = if (item.has("thinking")) item.optBoolean("thinking") else null)
        }
        return models to body.optString("nextPageToken").ifBlank { null }
    }

    private fun ollama(base: String): List<Model> =
        parseOllama(get("${base.removeSuffix("/v1").removeSuffix("/api")}/api/tags", emptyMap()))

    internal fun parseOllama(body: JSONObject): List<Model> {
        val data = body.optJSONArray("models") ?: throw unknownFormat
        return (0 until data.length()).mapNotNull { data.optJSONObject(it)?.optString("name")?.takeIf { name -> name.isNotBlank() } }
            .map { Model(it) }
    }

    private fun get(address: String, headers: Map<String, String>): JSONObject {
        val url = URL(address)
        // Android's network policy keeps the platform HTTP stack off plain HTTP except to this phone
        // (and it stays that way for everything else); a private-network server the user allowed is
        // read over a plain socket instead.
        if (url.protocol == "http" && !ProviderEndpoints.isLoopbackHost(url.host)) {
            val (status, body) = try { PlainHttp.get(url, headers, MAX_BYTES) } catch (error: PlainHttp.TooLarge) {
                throw Failure("模型列表太大", "The model list is too large")
            } catch (error: Exception) {
                throw Failure("无法连接：${error.message ?: error.javaClass.simpleName}", "Could not connect: ${error.message ?: error.javaClass.simpleName}")
            }
            return answer(status) { body }
        }
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 8000
            readTimeout = 15000
            // The key belongs to the address the user entered, never to wherever it redirects.
            instanceFollowRedirects = false
            setRequestProperty("Accept", "application/json")
            headers.forEach { (name, value) -> setRequestProperty(name, value) }
        }
        try {
            val status = try { connection.responseCode } catch (error: Exception) {
                throw Failure("无法连接：${error.message ?: error.javaClass.simpleName}", "Could not connect: ${error.message ?: error.javaClass.simpleName}")
            }
            return answer(status) {
                val output = ByteArrayOutputStream()
                connection.inputStream.use { input ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        output.write(buffer, 0, count)
                        if (output.size() > MAX_BYTES) throw Failure("模型列表太大", "The model list is too large")
                    }
                }
                output.toByteArray()
            }
        } finally {
            connection.disconnect()
        }
    }

    /** What every answer goes through, whichever way it was read: redirects, keys, no list, JSON. */
    private fun answer(status: Int, body: () -> ByteArray): JSONObject {
        when {
            status in 300..399 -> throw Failure("地址发生了跳转（HTTP $status），请填写最终的 API 地址", "The address redirects (HTTP $status); enter the final API address")
            status == 401 || status == 403 -> throw Failure("API Key 无效或没有权限（HTTP $status）", "The API key is invalid or not allowed (HTTP $status)")
            status == 404 || status == 405 -> throw Failure("这个服务没有模型列表接口，请手动填写模型名称", "This service has no model list; type the model name")
            status !in 200..299 -> throw Failure("服务返回 HTTP $status", "The service answered HTTP $status")
        }
        val bytes = body()
        return runCatching { JSONObject(String(bytes, Charsets.UTF_8)) }
            .getOrElse { throw Failure("服务返回的不是模型列表（不是 JSON）", "The service did not answer with a model list (not JSON)") }
    }
}
