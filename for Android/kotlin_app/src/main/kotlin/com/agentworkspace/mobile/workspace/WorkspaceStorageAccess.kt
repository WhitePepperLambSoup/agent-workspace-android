package com.agentworkspace.mobile.workspace

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.storage.StorageManager
import android.provider.DocumentsContract
import android.provider.Settings
import org.json.JSONObject
import java.io.File

object WorkspaceStorageAccess {
    val legacyPermissions = arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE, Manifest.permission.WRITE_EXTERNAL_STORAGE)

    fun granted(context: Context): Boolean = if (Build.VERSION.SDK_INT >= 30) {
        Environment.isExternalStorageManager()
    } else {
        (Build.VERSION.SDK_INT < 29 || Environment.isExternalStorageLegacy()) &&
            legacyPermissions.all { context.checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }
    }

    fun status(context: Context): String {
        val granted = granted(context)
        return JSONObject().put("granted", granted).put("required", !granted).toString()
    }

    fun settingsIntent(context: Context): Intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
        Uri.parse("package:${context.packageName}"))

    fun resolveFolder(context: Context, uri: Uri): File {
        require(uri.scheme == "content" && DocumentsContract.isTreeUri(uri)) { "系统返回了无效的文件夹位置" }
        return WorkspaceFolderPath.resolve(uri.authority, DocumentsContract.getTreeDocumentId(uri), volumeRoots(context))
    }

    @Suppress("DEPRECATION")
    private fun volumeRoots(context: Context): Map<String, File> {
        val roots = mutableMapOf("primary" to Environment.getExternalStorageDirectory())
        if (Build.VERSION.SDK_INT >= 30) {
            context.getSystemService(StorageManager::class.java).storageVolumes.forEach { volume ->
                volume.directory?.let { directory ->
                    if (volume.isPrimary) roots["primary"] = directory
                    else volume.uuid?.let { roots[it] = directory }
                }
            }
        } else {
            context.getExternalFilesDirs(null).filterNotNull().forEach { directory ->
                val root = directory.parentFile?.parentFile?.parentFile?.parentFile ?: return@forEach
                if (File(root, "Android/data/${context.packageName}/files").canonicalFile == directory.canonicalFile) {
                    roots[root.name] = root
                }
            }
        }
        return roots
    }
}
