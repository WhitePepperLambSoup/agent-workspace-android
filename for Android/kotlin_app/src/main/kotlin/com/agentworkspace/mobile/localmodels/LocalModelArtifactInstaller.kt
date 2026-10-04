package com.agentworkspace.mobile.localmodels

import java.io.File
import java.io.FileOutputStream
import java.io.InputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import org.json.JSONObject

object LocalModelArtifactInstaller {
    data class Spec(val id: String, val bytes: Long, val sha256: String, val revision: String)

    /** Publish an entire verified install directory; failures leave existing files untouched. */
    @Synchronized
    fun install(root: File, spec: Spec, source: InputStream) {
        require(spec.id.matches(Regex("[a-z0-9][a-z0-9.-]{0,95}")) &&
            spec.sha256.matches(Regex("[a-f0-9]{64}")) &&
            spec.revision.matches(Regex("[a-f0-9]{40}")) &&
            spec.bytes in 16L..(3L * 1024 * 1024 * 1024)) { "模型安装记录无效" }
        require(root.isDirectory && root.absoluteFile == root.canonicalFile &&
            !Files.isSymbolicLink(root.toPath())) { "本地模型目录不可用" }
        val target = File(root, spec.id)
        require(!target.exists() && !Files.isSymbolicLink(target.toPath())) {
            "此模型已有安装目录，请先在模型菜单移除旧文件"
        }
        val temporary = Files.createTempDirectory(root.toPath(), ".model-import-").toFile()
        try {
            val weights = File(temporary, "model.gguf")
            val digest = MessageDigest.getInstance("SHA-256")
            val signature = ByteArray(4)
            var total = 0L
            FileOutputStream(weights).use { output ->
                val buffer = ByteArray(1024 * 1024)
                while (true) {
                    val count = source.read(buffer)
                    if (count < 0) break
                    if (count == 0) continue
                    require(count.toLong() <= spec.bytes - total) { "模型文件大于预期大小" }
                    if (total < signature.size) {
                        System.arraycopy(buffer, 0, signature, total.toInt(),
                            minOf(count, signature.size - total.toInt()))
                    }
                    digest.update(buffer, 0, count)
                    output.write(buffer, 0, count)
                    total += count
                }
                output.fd.sync()
            }
            require(total == spec.bytes && signature.contentEquals("GGUF".toByteArray())) {
                "模型文件不完整或格式错误"
            }
            require(digest.digest().joinToString("") { "%02x".format(it) } == spec.sha256) {
                "模型文件校验失败，请选择此版本对应的训练模型"
            }
            val metadata = JSONObject().put("model_id", spec.id).put("size", spec.bytes)
                .put("sha256", spec.sha256).put("revision", spec.revision)
                .put("local_artifact", true).toString().toByteArray(Charsets.UTF_8)
            FileOutputStream(File(temporary, "installed.json")).use { output ->
                output.write(metadata)
                output.fd.sync()
            }
            // Both files become visible together on the private-storage filesystem.
            Files.move(temporary.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE)
        } finally {
            if (temporary.exists()) temporary.deleteRecursively()
        }
    }
}
