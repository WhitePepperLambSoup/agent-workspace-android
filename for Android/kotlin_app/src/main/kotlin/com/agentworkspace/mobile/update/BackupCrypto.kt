package com.agentworkspace.mobile.update

import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.EOFException
import java.io.File
import java.io.InputStream
import java.nio.ByteBuffer
import java.security.SecureRandom
import javax.crypto.AEADBadTagException
import javax.crypto.Cipher
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec

/**
 * A backup locked with a passphrase: the zip encrypted with AES-256-GCM in 1 MiB chunks, the key
 * derived from the passphrase with PBKDF2-HMAC-SHA256. Every chunk is authenticated with its number
 * and whether it is the last, so a changed, reordered or cut-off file fails to open, as does a wrong
 * passphrase. Nothing of the passphrase is stored; forgetting it means the backup cannot be opened.
 *
 * Layout: "AWBKENC1", version 1, iterations (int), salt (16), nonce prefix (8); then chunks of
 * [last (1 byte)] [length (int)] [ciphertext with tag]. Nonce = prefix + chunk number.
 */
internal object BackupCrypto {
    private val MAGIC = "AWBKENC1".toByteArray(Charsets.US_ASCII)
    private const val VERSION: Byte = 1
    private const val ITERATIONS = 310_000
    private const val CHUNK = 1 shl 20
    private const val HEADER = 8 + 1 + 4 + 16 + 8

    class WrongPassphrase : Exception("wrong passphrase or damaged backup")

    fun isEncrypted(file: File): Boolean = file.inputStream().use { input ->
        val head = ByteArray(MAGIC.size)
        readFully(input, head) && head.contentEquals(MAGIC)
    }

    private fun readFully(input: InputStream, buffer: ByteArray): Boolean {
        var read = 0
        while (read < buffer.size) {
            val count = input.read(buffer, read, buffer.size - read)
            if (count < 0) return false
            read += count
        }
        return true
    }

    private fun key(passphrase: CharArray, salt: ByteArray, iterations: Int): SecretKeySpec {
        val spec = PBEKeySpec(passphrase, salt, iterations, 256)
        try {
            return SecretKeySpec(SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded, "AES")
        } finally { spec.clearPassword() }
    }

    private fun cipher(mode: Int, key: SecretKeySpec, header: ByteArray, prefix: ByteArray, index: Int, last: Boolean): Cipher =
        Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(mode, key, GCMParameterSpec(128, ByteBuffer.allocate(12).put(prefix).putInt(index).array()))
            updateAAD(header)
            updateAAD(ByteBuffer.allocate(5).putInt(index).put(if (last) 1 else 0).array())
        }

    fun encrypt(source: File, target: File, passphrase: CharArray) {
        require(passphrase.isNotEmpty()) { "passphrase is empty" }
        val random = SecureRandom()
        val salt = ByteArray(16).also(random::nextBytes)
        val prefix = ByteArray(8).also(random::nextBytes)
        val header = ByteBuffer.allocate(HEADER).put(MAGIC).put(VERSION).putInt(ITERATIONS).put(salt).put(prefix).array()
        val key = key(passphrase, salt, ITERATIONS)
        source.inputStream().buffered().use { input ->
            DataOutputStream(target.outputStream().buffered()).use { output ->
                output.write(header)
                var index = 0
                var current = ByteArray(CHUNK)
                var size = fill(input, current)
                while (true) {
                    // Read one ahead to know which chunk is the last.
                    val next = ByteArray(CHUNK)
                    val nextSize = if (size == CHUNK) fill(input, next) else 0
                    val last = nextSize == 0
                    val sealed = cipher(Cipher.ENCRYPT_MODE, key, header, prefix, index, last).doFinal(current, 0, size)
                    output.writeByte(if (last) 1 else 0)
                    output.writeInt(sealed.size)
                    output.write(sealed)
                    if (last) break
                    index += 1
                    current = next
                    size = nextSize
                }
            }
        }
    }

    private fun fill(input: InputStream, buffer: ByteArray): Int {
        var read = 0
        while (read < buffer.size) {
            val count = input.read(buffer, read, buffer.size - read)
            if (count < 0) break
            read += count
        }
        return read
    }

    fun decrypt(source: File, target: File, passphrase: CharArray) {
        DataInputStream(source.inputStream().buffered()).use { input ->
            val header = ByteArray(HEADER)
            if (!readFully(input, header)) throw WrongPassphrase()
            val buffer = ByteBuffer.wrap(header)
            val magic = ByteArray(MAGIC.size).also { buffer.get(it) }
            require(magic.contentEquals(MAGIC)) { "not an encrypted backup" }
            require(buffer.get() == VERSION) { "this backup was made by a newer version of the app; update first" }
            val iterations = buffer.getInt()
            require(iterations in 10_000..10_000_000) { "damaged backup" }
            val salt = ByteArray(16).also { buffer.get(it) }
            val prefix = ByteArray(8).also { buffer.get(it) }
            val key = key(passphrase, salt, iterations)
            target.outputStream().buffered().use { output ->
                var index = 0
                while (true) {
                    // A file cut short reads as damaged, like a wrong passphrase.
                    val last = try { input.readByte().toInt() == 1 } catch (_: EOFException) { throw WrongPassphrase() }
                    val length = try { input.readInt() } catch (_: EOFException) { throw WrongPassphrase() }
                    if (length !in 16..(CHUNK + 16)) throw WrongPassphrase()
                    val sealed = ByteArray(length)
                    try { input.readFully(sealed) } catch (_: EOFException) { throw WrongPassphrase() }
                    val plain = try {
                        cipher(Cipher.DECRYPT_MODE, key, header, prefix, index, last).doFinal(sealed)
                    } catch (_: AEADBadTagException) { throw WrongPassphrase() }
                    output.write(plain)
                    if (last) break
                    index += 1
                }
            }
            if (input.read() != -1) throw WrongPassphrase()
        }
    }
}
