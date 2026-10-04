package com.agentworkspace.mobile.toolchain

import android.content.Context
import android.net.ConnectivityManager
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

/** Read-only launcher discovery. A downloaded rootfs is usable only after Python's probes. */
object AndroidToolchainBridge {
    @Volatile private var applicationContext: Context? = null

    @JvmStatic fun initialize(context: Context) { applicationContext = context.applicationContext }

    @JvmStatic fun status(): String {
        val context = applicationContext ?: return JSONObject().put("available", false)
            .put("reason", "The Android toolchain bridge is not initialized").toString()
        val abi = Build.SUPPORTED_ABIS.firstOrNull { it == "arm64-v8a" || it == "x86_64" }
        val result = JSONObject().put("available", false).put("abi", abi ?: JSONObject.NULL)
            .put("architecture", if (abi == "arm64-v8a") "aarch64" else abi ?: JSONObject.NULL)
            .put("api_level", Build.VERSION.SDK_INT)
            .put("native_library_dir", context.applicationInfo.nativeLibraryDir)
            .put("execution_location", "apk_native_library_dir")
        try {
            check(abi != null) { "The optional toolchain supports arm64-v8a and x86_64" }
            val manifest = context.assets.open("toolchain/launchers.json").bufferedReader().use {
                JSONObject(it.readText())
            }.getJSONObject("abis").getJSONObject(abi)
            val directory = File(context.applicationInfo.nativeLibraryDir).canonicalFile
            val files = manifest.getJSONObject("files")
            files.keys().forEach { name ->
                check(Regex("lib[a-zA-Z0-9_-]+\\.so").matches(name)) { "Invalid packaged launcher name" }
                val file = File(directory, name).canonicalFile
                val expected = files.getJSONObject(name)
                check(file.parentFile == directory && file.isFile && file.canExecute() &&
                    file.length() == expected.getLong("size") && sha256(file) == expected.getString("sha256")) {
                    "The packaged toolchain launcher failed its integrity check"
                }
            }
            val dns = JSONArray()
            runCatching {
                val connectivity = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
                connectivity.activeNetwork?.let { connectivity.getLinkProperties(it) }
                    ?.dnsServers?.forEach { address -> address.hostAddress?.let { dns.put(it) } }
            }
            result.put("available", true).put("reason", JSONObject.NULL)
                .put("launcher", File(directory, "libagent_proot.so").absolutePath)
                .put("loader", File(directory, "libagent_proot_loader.so").absolutePath)
                .put("proot_version", "5.1.107.95").put("dns_servers", dns)
        } catch (_: Exception) {
            result.put("reason", "Verified native PRoot launchers are unavailable; rebuild the toolchain assets")
        }
        return result.toString()
    }

    /** Harmless actual ELF startup probe; it creates no conversations or toolchain state. */
    @JvmStatic fun launcherProbe(): String {
        val current = JSONObject(status())
        if (!current.optBoolean("available")) return current.put("executed", false).toString()
        return try {
            val process = ProcessBuilder(current.getString("launcher"), "--version").apply {
                redirectErrorStream(true)
                environment().clear()
                environment()["LD_LIBRARY_PATH"] = current.getString("native_library_dir")
                environment()["PROOT_LOADER"] = current.getString("loader")
            }.start()
            val bytes = java.io.ByteArrayOutputStream()
            val reader = Thread {
                process.inputStream.use { input ->
                    val buffer = ByteArray(1024)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        synchronized(bytes) {
                            val remaining = 8192 - bytes.size()
                            if (remaining > 0) bytes.write(buffer, 0, minOf(count, remaining))
                        }
                    }
                }
            }.apply { isDaemon = true; start() }
            val completed = process.waitFor(5, TimeUnit.SECONDS)
            if (!completed) process.destroyForcibly()
            reader.join(1000)
            JSONObject().put("executed", true).put("ok", completed && process.exitValue() == 0)
                .put("timed_out", !completed).put("stdout", synchronized(bytes) { bytes.toString("UTF-8") })
                .put("exit_code", if (completed) process.exitValue() else JSONObject.NULL).toString()
        } catch (_: Exception) {
            JSONObject().put("ok", false).put("executed", false)
                .put("reason", "The packaged PRoot ELF could not execute on this Android system").toString()
        }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
