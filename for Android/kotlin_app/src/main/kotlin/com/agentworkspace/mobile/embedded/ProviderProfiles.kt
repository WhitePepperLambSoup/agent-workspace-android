package com.agentworkspace.mobile.embedded

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/**
 * Saved model configurations (provider, address, model, reasoning effort) to switch between.
 * A profile never holds an API key: keys stay in the Keystore under each provider address
 * (MobileProviderSettings), so two profiles for the same provider share its key.
 */
object ProviderProfiles {
    private const val PREFERENCES = "agent-workspace-provider-profiles"
    private const val KEY = "profiles"
    private const val MAX_PROFILES = 20

    private fun read(context: Context): List<JSONObject> {
        val raw = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).getString(KEY, "[]")
        val array = runCatching { JSONArray(raw) }.getOrDefault(JSONArray())
        return (0 until array.length()).mapNotNull { array.optJSONObject(it) }
            .filter { it.optString("id").isNotBlank() && it.optString("protocol") in MobileProviderSettings.protocols &&
                it.optString("base_url").isNotBlank() && it.optString("model").isNotBlank() }
    }

    private fun write(context: Context, profiles: List<JSONObject>) {
        check(context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
            .putString(KEY, JSONArray(profiles).toString()).commit()) { "Failed to save model profiles" }
    }

    private fun sameTarget(profile: JSONObject, protocol: String, baseUrl: String, model: String) =
        profile.optString("protocol") == protocol &&
            profile.optString("base_url").trimEnd('/').equals(baseUrl.trimEnd('/'), ignoreCase = true) &&
            profile.optString("model") == model

    /** Every profile with whether its provider has a key and whether it is the one in use. */
    fun snapshot(context: Context): String {
        val current = MobileProviderSettings.load(context)
        val profiles = JSONArray()
        read(context).forEach { profile ->
            val protocol = profile.getString("protocol")
            val baseUrl = profile.getString("base_url")
            profiles.put(JSONObject(profile.toString())
                .put("has_api_key", !MobileProviderSettings.apiKeyFor(context, protocol, baseUrl).isNullOrBlank())
                .put("local", baseUrl.trimEnd('/') == MobileProviderSettings.EMBEDDED_QWEN_BASE_URL)
                .put("active", sameTarget(profile, current.protocol, current.baseUrl, current.model)))
        }
        return JSONObject().put("ok", true).put("profiles", profiles)
            .put("max_profiles", MAX_PROFILES)
            .put("current", JSONObject().put("protocol", current.protocol).put("base_url", current.baseUrl)
                .put("model", current.model).put("reasoning_effort", current.reasoningEffort))
            .toString()
    }

    /** Save the configuration in use under a name (an existing profile for the same model is renamed). */
    fun saveCurrent(context: Context, name: String): String = synchronized(this) {
        val label = name.trim().take(40)
        require(label.isNotEmpty()) { "Give the profile a name" }
        val current = MobileProviderSettings.load(context)
        val profiles = read(context).toMutableList()
        val existing = profiles.firstOrNull { sameTarget(it, current.protocol, current.baseUrl, current.model) }
        if (existing != null) {
            existing.put("name", label).put("reasoning_effort", current.reasoningEffort)
        } else {
            require(profiles.size < MAX_PROFILES) { "At most $MAX_PROFILES model profiles can be saved" }
            profiles.add(JSONObject().put("id", UUID.randomUUID().toString()).put("name", label)
                .put("protocol", current.protocol).put("base_url", current.baseUrl)
                .put("model", current.model).put("reasoning_effort", current.reasoningEffort))
        }
        write(context, profiles)
        snapshot(context)
    }

    fun delete(context: Context, id: String): String = synchronized(this) {
        write(context, read(context).filterNot { it.optString("id") == id })
        snapshot(context)
    }

    fun get(context: Context, id: String): JSONObject =
        read(context).firstOrNull { it.optString("id") == id } ?: throw IllegalArgumentException("Unknown model profile")
}
