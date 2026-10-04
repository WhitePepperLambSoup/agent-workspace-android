package com.agentworkspace.mobile.embedded

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

object EmbeddedSecrets {
    private const val KEY_ALIAS = "agent-workspace-embedded-v1"
    private const val PREFERENCES = "agent-workspace-encrypted-credentials"
    private lateinit var applicationContext: Context

    @JvmStatic
    @Synchronized
    fun initialize(context: Context) {
        applicationContext = context.applicationContext
        key()
    }

    @JvmStatic
    @Synchronized
    fun getCredential(target: String): String? {
        val value = preferences().getString(target, null) ?: return null
        return decrypt(Base64.decode(value, Base64.NO_WRAP), target.toByteArray())
            .toString(Charsets.UTF_8)
    }

    @JvmStatic
    @Synchronized
    fun setCredential(target: String, value: String) {
        val protected = encrypt(value.toByteArray(), target.toByteArray())
        check(preferences().edit().putString(
            target, Base64.encodeToString(protected, Base64.NO_WRAP)
        ).commit()) { "Failed to save encrypted credential" }
    }

    @JvmStatic
    @Synchronized
    fun deleteCredential(target: String): Boolean {
        val existed = preferences().contains(target)
        check(preferences().edit().remove(target).commit()) { "Failed to delete credential" }
        return existed
    }

    @JvmStatic
    @Synchronized
    fun listCredentials(): Array<String> = preferences().all.keys.sorted().toTypedArray()

    @JvmStatic
    @Synchronized
    fun protectBase64(data: String, entropy: String): String {
        val aad = Base64.decode(entropy, Base64.NO_WRAP)
        require(aad.isNotEmpty()) { "Protection context may not be empty" }
        return Base64.encodeToString(
            encrypt(Base64.decode(data, Base64.NO_WRAP), aad), Base64.NO_WRAP
        )
    }

    @JvmStatic
    @Synchronized
    fun unprotectBase64(data: String, entropy: String): String {
        val aad = Base64.decode(entropy, Base64.NO_WRAP)
        require(aad.isNotEmpty()) { "Protection context may not be empty" }
        return Base64.encodeToString(
            decrypt(Base64.decode(data, Base64.NO_WRAP), aad), Base64.NO_WRAP
        )
    }

    private fun preferences() = applicationContext.getSharedPreferences(
        PREFERENCES, Context.MODE_PRIVATE
    )

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(
                KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            ).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build())
        }.generateKey()
    }

    private fun encrypt(data: ByteArray, aad: ByteArray): ByteArray {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        cipher.updateAAD(aad)
        return byteArrayOf(1) + cipher.iv + cipher.doFinal(data)
    }

    private fun decrypt(data: ByteArray, aad: ByteArray): ByteArray {
        require(data.size >= 29 && data[0] == 1.toByte()) { "Invalid encrypted data" }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, data.copyOfRange(1, 13)))
        cipher.updateAAD(aad)
        return cipher.doFinal(data.copyOfRange(13, data.size))
    }
}
