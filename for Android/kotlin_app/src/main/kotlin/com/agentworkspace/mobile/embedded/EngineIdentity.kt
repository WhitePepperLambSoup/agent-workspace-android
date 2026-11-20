package com.agentworkspace.mobile.embedded

import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64
import java.util.concurrent.ConcurrentHashMap
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * Challenge-response with the local engine before its token, an API key or a user's file leaves the
 * app. The engine listens on 127.0.0.1, where any app on the phone may open a port: when the system
 * kills the engine process its serve.token stays behind, and another app can take 8080 (or the port
 * serve.port names). Only the engine that published serve.token can answer the challenge (an
 * HMAC-SHA256 under that token), so every native client asks before it sends a request that
 * carries the token. Only the console's start-up asked before; the other clients sent the token,
 * a model change's API key and shared files to whatever held the port.
 */
object EngineIdentity {
    private val CONTEXT = "agent-workspace-mobile-identity-v1\n".toByteArray(Charsets.US_ASCII)
    /** How long an answer is trusted, so that a burst of requests (a poll, a download) asks once. */
    private const val TRUSTED_NANOS = 3_000_000_000L
    private val answered = ConcurrentHashMap<String, Long>()
    private val random = SecureRandom()

    class Unverified : IOException("The local engine could not be verified; try again when it is running")

    fun newChallenge(): String = Base64.getUrlEncoder().withoutPadding()
        .encodeToString(ByteArray(32).also { random.nextBytes(it) })

    /** What the engine answers for [challenge]: mobile_gateway.identity_proof. */
    fun proof(token: String, challenge: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(token.toByteArray(Charsets.UTF_8), "HmacSHA256"))
        return mac.doFinal(CONTEXT + challenge.toByteArray(Charsets.US_ASCII)).joinToString("") { "%02x".format(it) }
    }

    /** Asks the process at [baseUrl] now, whatever an earlier answer was. */
    fun answers(baseUrl: String, token: String, timeoutMs: Int = 1000): Boolean {
        val key = key(baseUrl, token)
        val challenge = newChallenge()
        val ok = runCatching {
            val connection = URL("$baseUrl/mobile/identity?challenge=$challenge").openConnection() as HttpURLConnection
            try {
                connection.instanceFollowRedirects = false
                connection.useCaches = false
                connection.connectTimeout = timeoutMs
                connection.readTimeout = timeoutMs
                if (connection.responseCode != 200) return@runCatching false
                val body = connection.inputStream.use { input ->
                    val buffer = ByteArray(4096)
                    var size = 0
                    while (size < buffer.size) {
                        val count = input.read(buffer, size, buffer.size - size)
                        if (count < 0) break
                        size += count
                    }
                    String(buffer, 0, size, Charsets.UTF_8)
                }
                val proof = JSONObject(body).optString("proof")
                MessageDigest.isEqual(proof(token, challenge).toByteArray(Charsets.US_ASCII), proof.toByteArray(Charsets.UTF_8))
            } finally {
                connection.disconnect()
            }
        }.getOrDefault(false)
        if (ok) {
            if (answered.size > 16) answered.clear()
            answered[key] = System.nanoTime()
        } else {
            answered.remove(key)
        }
        return ok
    }

    /** True when the engine at [baseUrl] proved it holds [token] within the last few seconds, or does now. */
    fun verify(baseUrl: String, token: String, timeoutMs: Int = 3000): Boolean {
        val at = answered[key(baseUrl, token)]
        if (at != null && (System.nanoTime() - at) in 0L until TRUSTED_NANOS) return true
        return answers(baseUrl, token, timeoutMs)
    }

    /** Throws [Unverified] (an IOException: the engine counts as unreachable) unless [verify] passes. */
    fun require(baseUrl: String, token: String, timeoutMs: Int = 3000) {
        if (!verify(baseUrl, token, timeoutMs)) throw Unverified()
    }

    /** A request to [baseUrl] failed to connect: ask again before the next one carries the token. */
    fun forget(baseUrl: String, token: String) {
        answered.remove(key(baseUrl, token))
    }

    private fun key(baseUrl: String, token: String) = "$baseUrl\n$token"
}
