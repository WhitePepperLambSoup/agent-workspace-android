package com.agentworkspace.mobile.workspace

import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.content.FileProvider

object WorkspaceFileIntents {
    private fun uri(context: Context, file: CachedWorkspaceFile): Uri {
        WorkspaceFileCache.checkedFile(context, file.file)
        WorkspaceFileCache.retain(file.file)
        return FileProvider.getUriForFile(context, context.packageName + ".workspace-files", file.file)
    }

    fun open(context: Context, file: CachedWorkspaceFile): Intent {
        val content = uri(context, file)
        if (file.mimeType == "text/html") {
            return Intent(context, WorkspaceHtmlPreviewActivity::class.java).apply {
                data = content
                putExtra(WorkspaceHtmlPreviewActivity.EXTRA_SHA256, file.sha256)
                putExtra(WorkspaceHtmlPreviewActivity.EXTRA_SIZE, file.size)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
        }
        return Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(content, file.mimeType)
            clipData = ClipData.newRawUri(file.file.name, content)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
    }

    /**
     * Second try when no app claims the exact type (text/markdown, text/x-python ... have no viewer
     * on many phones): offer every app that opens plain text, or any file, and let the user choose.
     */
    fun openWithAnyViewer(context: Context, file: CachedWorkspaceFile): Intent {
        val content = uri(context, file)
        val textual = file.mimeType.startsWith("text/") ||
            file.mimeType in setOf("application/json", "application/xml", "application/javascript", "application/x-yaml", "application/toml")
        val view = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(content, if (textual) "text/plain" else "*/*")
            clipData = ClipData.newRawUri(file.file.name, content)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        return Intent.createChooser(view, file.file.name).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }

    fun share(context: Context, file: CachedWorkspaceFile): Intent {
        val content = uri(context, file)
        return Intent(Intent.ACTION_SEND).apply {
            type = file.mimeType
            putExtra(Intent.EXTRA_STREAM, content)
            clipData = ClipData.newRawUri(file.file.name, content)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
    }

    fun save(file: CachedWorkspaceFile): Intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
        addCategory(Intent.CATEGORY_OPENABLE)
        type = file.mimeType
        putExtra(Intent.EXTRA_TITLE, file.file.name)
    }
}
