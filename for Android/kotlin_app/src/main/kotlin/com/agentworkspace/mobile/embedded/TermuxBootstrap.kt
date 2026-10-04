package com.agentworkspace.mobile.embedded

import android.content.Context
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipInputStream

/** Installs the versioned application sources; Python is supplied by Chaquopy. */
object TermuxBootstrap {

    private const val AGENT_CODE_ASSET_NAME = "agent_code.zip"
    private const val MARKER_FILE_NAME = ".bootstrap_completed"

    fun isInstalled(context: Context): Boolean {
        val marker = File(context.filesDir, MARKER_FILE_NAME)
        val entrypoint = File(context.filesDir, "agent/for Android/entrypoint.py")
        val gateway = File(context.filesDir, "agent/for Android/mobile_gateway.py")
        return marker.isFile && entrypoint.isFile && gateway.isFile &&
            runCatching { marker.readText() == installationVersion(context) }.getOrDefault(false)
    }

    fun installSync(context: Context, onProgress: (String) -> Unit = {}) {
        val filesDir = context.filesDir
        val homeDir = File(filesDir, "home")
        val agentDir = File(filesDir, "agent")

        onProgress(com.agentworkspace.mobile.UiText.of(context, "正在创建私有运行目录...", "Creating the private runtime folder..."))
        homeDir.mkdirs()
        agentDir.mkdirs()
        File(filesDir, MARKER_FILE_NAME).delete()
        onProgress(com.agentworkspace.mobile.UiText.of(context, "正在更新本地服务...", "Updating the local service..."))
        unzipAsset(context, AGENT_CODE_ASSET_NAME, agentDir)
        check(File(agentDir, "for Android/mobile_gateway.py").isFile) {
            "The application archive is missing the mobile gateway"
        }
        File(filesDir, MARKER_FILE_NAME).writeText(installationVersion(context))
    }

    @Suppress("DEPRECATION")
    private fun installationVersion(context: Context): String {
        val updateTime = context.packageManager.getPackageInfo(context.packageName, 0).lastUpdateTime
        return "CHAQUOPY=1\nAPK_UPDATE=$updateTime"
    }

    private fun unzipAsset(context: Context, assetName: String, targetDir: File) {
        context.assets.open(assetName).use { inputStream ->
            ZipInputStream(inputStream).use { zip ->
                var entry = zip.nextEntry
                val buffer = ByteArray(8192)
                while (entry != null) {
                    val destFile = File(targetDir, entry.name)
                    val canonicalDest = destFile.canonicalPath
                    val canonicalTarget = targetDir.canonicalPath
                    if (!canonicalDest.startsWith(canonicalTarget + File.separator) && canonicalDest != canonicalTarget) {
                        throw SecurityException("Zip entry attempted directory traversal: ${entry.name}")
                    }
                    if (entry.isDirectory) {
                        destFile.mkdirs()
                    } else {
                        destFile.parentFile?.mkdirs()
                        FileOutputStream(destFile).use { out ->
                            var len: Int
                            while (zip.read(buffer).also { len = it } > 0) {
                                out.write(buffer, 0, len)
                            }
                        }
                        if (destFile.parentFile?.name in listOf("bin", "applets") || destFile.name.endsWith(".sh") || destFile.name.endsWith(".py")) {
                            destFile.setExecutable(true, false)
                            destFile.setReadable(true, false)
                        }
                    }
                    zip.closeEntry()
                    entry = zip.nextEntry
                }
            }
        }
    }
}
