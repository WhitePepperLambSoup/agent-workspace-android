package com.agentworkspace.mobile.workspace

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.DocumentsContract
import android.widget.Toast
import org.json.JSONObject
import java.io.File

object WorkspaceDocumentsAccess {
    fun open(context: Context, workspaceId: String, canOpen: () -> Boolean = { true }): String = try {
        check(canOpen()) { "The workspace page is no longer active" }
        WorkspaceDocumentId.root(workspaceId)
        WorkspaceDocumentsGateway(context).workspace(workspaceId)
        refresh(context)
        Handler(Looper.getMainLooper()).post {
            if (!canOpen()) return@post
            try { context.startActivity(browseIntent(context, workspaceId)) }
            catch (_: ActivityNotFoundException) {
                runCatching { context.startActivity(pickerIntent(context, workspaceId)) }
                    .onFailure { Toast.makeText(context, "此设备没有可用的系统文件浏览器，请使用应用内文件页", Toast.LENGTH_LONG).show() }
            } catch (_: Exception) {
                Toast.makeText(context, "无法打开系统文件浏览器，请使用应用内文件页", Toast.LENGTH_LONG).show()
            }
        }
        JSONObject().put("ok", true).put("queued", true).toString()
    } catch (_: Exception) {
        JSONObject().put("ok", false).put("error", WorkspaceDocumentsProvider.ENGINE_REQUIRED).toString()
    }

    fun refresh(context: Context) {
        context.contentResolver.notifyChange(DocumentsContract.buildRootsUri(WorkspaceDocumentsProvider.authority(context)), null)
    }

    fun browseIntent(context: Context, workspaceId: String): Intent {
        WorkspaceDocumentId.root(workspaceId)
        return Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(DocumentsContract.buildRootUri(WorkspaceDocumentsProvider.authority(context), workspaceId), DocumentsContract.Root.MIME_TYPE_ITEM)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
    }

    fun pickerIntent(context: Context, workspaceId: String): Intent {
        val id = WorkspaceDocumentId.root(workspaceId)
        return Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
            putExtra(DocumentsContract.EXTRA_INITIAL_URI, DocumentsContract.buildDocumentUri(WorkspaceDocumentsProvider.authority(context), id.value))
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
    }

    fun recommendedFolder(name: String): String = try {
        val folder = name.trim().replace(Regex("[\\\\/:*?\"<>|\\p{Cc}]"), "_").trim('.', ' ').take(80).ifEmpty { "项目" }
        @Suppress("DEPRECATION")
        val documents = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS)
        val path = File(File(documents, "AgentWorkspace"), folder).absolutePath
        JSONObject().put("ok", true).put("path", path).toString()
    } catch (_: Exception) {
        JSONObject().put("ok", false).put("error", "无法读取公共文档目录，请手动选择文件夹").toString()
    }
}
