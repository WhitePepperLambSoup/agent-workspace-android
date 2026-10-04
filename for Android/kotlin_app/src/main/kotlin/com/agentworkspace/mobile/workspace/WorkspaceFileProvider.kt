package com.agentworkspace.mobile.workspace

import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.os.ParcelFileDescriptor
import androidx.core.content.FileProvider
import java.io.FileNotFoundException

class WorkspaceFileProvider : FileProvider() {
    override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
        if (mode != "r") throw FileNotFoundException("Workspace artifacts are read-only")
        val owner = context ?: throw FileNotFoundException("The export provider is unavailable")
        val file = WorkspaceFileCache.uriFile(owner, uri)
        val lease = WorkspaceFileCache.pin(file.parentFile!!)
        try {
            WorkspaceFileCache.retain(file)
            return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY,
                Handler(Looper.getMainLooper())) { lease.close() }
        } catch (failure: Exception) {
            lease.close()
            throw failure
        }
    }

    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int =
        throw SecurityException("Workspace artifacts are read-only")
}
