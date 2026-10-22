package com.agentworkspace.mobile.capabilities

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import org.json.JSONObject
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.PublicKey
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.security.spec.X509EncodedKeySpec
import java.util.Base64

/**
 * Signatures on share codes (a shortcut shared as text). Each install signs with its own key in
 * the Android Keystore (it never leaves the phone); a code carries the public key, so whoever
 * imports it sees that it was not changed after signing and a short fingerprint of the key that
 * signed it. Comparing the fingerprint with the sender (in person, on a call) tells who made it.
 */
object ShareSignature {
    private const val ALIAS = "agent-share-signing"
    private const val ALGORITHM = "SHA256withECDSA"
    private val encoder = Base64.getUrlEncoder().withoutPadding()
    private val decoder = Base64.getUrlDecoder()

    private fun ownKey(): Pair<PrivateKey, PublicKey> {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getEntry(ALIAS, null) as? KeyStore.PrivateKeyEntry)?.let { return it.privateKey to it.certificate.publicKey }
        val generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore")
        generator.initialize(KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_SIGN)
            .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
            .setDigests(KeyProperties.DIGEST_SHA256).build())
        return generator.generateKeyPair().let { it.private to it.public }
    }

    /** This install's public key and its fingerprint. */
    @JvmStatic
    fun identity(): String = runCatching {
        val key = encoder.encodeToString(ownKey().second.encoded)
        JSONObject().put("ok", true).put("public_key", key).put("fingerprint", fingerprint(key))
    }.getOrElse { JSONObject().put("ok", false).put("error", it.message?.take(200)) }.toString()

    @JvmStatic
    fun sign(text: String): String = runCatching {
        val (private, public) = ownKey()
        val signature = Signature.getInstance(ALGORITHM).run {
            initSign(private)
            update(text.toByteArray(Charsets.UTF_8))
            sign()
        }
        val key = encoder.encodeToString(public.encoded)
        JSONObject().put("ok", true).put("signature", encoder.encodeToString(signature))
            .put("public_key", key).put("fingerprint", fingerprint(key))
    }.getOrElse { JSONObject().put("ok", false).put("error", it.message?.take(200)) }.toString()

    /** Whether [signature] over [text] was made with [publicKey]; false for anything malformed. */
    @JvmStatic
    fun verify(text: String, signature: String, publicKey: String): Boolean = runCatching {
        val key = KeyFactory.getInstance("EC").generatePublic(X509EncodedKeySpec(decoder.decode(publicKey)))
        Signature.getInstance(ALGORITHM).run {
            initVerify(key)
            update(text.toByteArray(Charsets.UTF_8))
            verify(decoder.decode(signature))
        }
    }.getOrDefault(false)

    /** The first 6 bytes of the key's SHA-256, as "AB12-CD34-EF56": short enough to read aloud. */
    @JvmStatic
    fun fingerprint(publicKey: String): String = runCatching {
        MessageDigest.getInstance("SHA-256").digest(decoder.decode(publicKey)).take(6)
            .joinToString("") { "%02X".format(it) }.chunked(4).joinToString("-")
    }.getOrDefault("")
}
