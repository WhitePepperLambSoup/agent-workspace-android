package com.agentworkspace.mobile.workspace

import android.app.PendingIntent
import android.content.ActivityNotFoundException
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.Build
import android.os.Bundle
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.runInterruptible
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.Closeable
import java.io.File
import java.util.UUID

class WorkspaceFileActionController(
    private val context: Context,
    private val scope: CoroutineScope,
    private val trustedPage: () -> Boolean,
    private val notifyResult: (JSONObject) -> Unit,
    private val launchShare: (Intent) -> Unit,
    private val launchSave: (Intent) -> Unit,
    private val launchOpen: (Intent) -> Unit,
    private val store: WorkspaceFileDownloadStore = WorkspaceFileDownloadStore(context),
) : Closeable {
    private class Pending(val request: WorkspaceFileRequest) {
        var cached: CachedWorkspaceFile? = null
        var lease: Closeable? = null
        var completed = false
        var chosen = false
        var handedToExternalApp = false
    }

    private val lock = Any()
    private val pending = linkedMapOf<String, Pending>()
    private var closed = false
    private var saving: Pending? = null
    private var sharing: Pending? = null
    private var chooserReceiver: BroadcastReceiver? = null
    private var chooserCallback: PendingIntent? = null
    private var pickerOwner: Pending? = null

    fun queue(requestJson: String): String {
        val request = try { WorkspaceFileRequest.parse(requestJson) }
        catch (failure: IllegalArgumentException) { return rejected(failure.message ?: "Invalid file action") }
        val action = Pending(request)
        synchronized(lock) {
            if (closed || !scope.isActive || !trustedPage()) return rejected("File actions require the trusted workspace console")
            if (pending.containsKey(request.requestId)) return rejected("This file request is already running")
            if (pickerOwner != null) return rejected("Finish the current system file action before starting another")
            if (pending.size >= 4) return rejected("Several file actions are running; wait for one to finish")
            pending[request.requestId] = action
            if (request.action in setOf("share", "save")) pickerOwner = action
        }
        scope.launch {
            try {
                check(trustedPage()) { "The workspace console is no longer active" }
                synchronized(lock) {
                    check(pickerOwner == null || pickerOwner === action) { "Finish the current system file action before starting another" }
                }
                val cached = withContext(Dispatchers.IO) { runInterruptible { store.download(request) } }
                action.cached = cached
                action.lease = WorkspaceFileCache.pin(cached.file.parentFile!!)
                check(trustedPage()) { "The workspace console is no longer active" }
                synchronized(lock) {
                    check(pickerOwner == null || pickerOwner === action) { "Finish the current system file action before starting another" }
                }
                when (request.action) {
                    "open" -> {
                        launchOpen(WorkspaceFileIntents.open(context, cached))
                        action.handedToExternalApp = true
                        finish(action, request.result(true))
                    }
                    "share" -> {
                        sharing = action
                        launchShare(shareChooser(action, cached))
                        action.handedToExternalApp = true
                    }
                    "save" -> {
                        saving = action
                        launchSave(WorkspaceFileIntents.save(cached))
                    }
                }
            } catch (failure: CancellationException) {
                finish(action, request.result(false, "File action cancelled", cancelled = true))
                throw failure
            } catch (failure: Exception) {
                if (saving === action) saving = null
                if (sharing === action) { sharing = null; clearChooserCallback() }
                releasePicker(action)
                finish(action, request.result(false, publicError(failure)))
            }
        }
        return JSONObject().put("ok", true).toString()
    }

    fun onSaveResult(uri: Uri?) {
        val action = saving ?: return
        saving = null
        if (uri == null) {
            finish(action, action.request.result(false, "Saving was cancelled", cancelled = true))
            return
        }
        scope.launch {
            try {
                val cached = action.cached ?: error("The downloaded file is unavailable")
                withContext(Dispatchers.IO) { runInterruptible { store.save(cached, uri) } }
                finish(action, action.request.result(true))
            } catch (failure: CancellationException) {
                finish(action, action.request.result(false, "Saving was cancelled", cancelled = true))
                throw failure
            } catch (failure: Exception) {
                finish(action, action.request.result(false, publicError(failure)))
            }
        }
    }

    fun onShareResult() {
        val action = sharing ?: return
        // The chooser selection broadcast and activity result can arrive in either order.
        scope.launch {
            delay(350)
            if (sharing !== action) return@launch
            sharing = null
            clearChooserCallback()
            releasePicker(action)
            if (!action.completed) finish(action, action.request.result(action.chosen,
                if (action.chosen) null else "Sharing was cancelled", cancelled = !action.chosen))
        }
    }

    private fun shareChooser(action: Pending, cached: CachedWorkspaceFile): Intent {
        val broadcastAction = context.packageName + ".WORKSPACE_FILE_CHOSEN." + UUID.randomUUID()
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(owner: Context?, intent: Intent?) {
                if (intent?.action != broadcastAction || sharing !== action) return
                if (!intent.hasExtra(Intent.EXTRA_CHOSEN_COMPONENT)) return
                action.chosen = true
                finish(action, action.request.result(true))
            }
        }
        ContextCompat.registerReceiver(context, receiver, IntentFilter(broadcastAction), ContextCompat.RECEIVER_NOT_EXPORTED)
        chooserReceiver = receiver
        val flags = PendingIntent.FLAG_CANCEL_CURRENT or
            if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0
        val callback = PendingIntent.getBroadcast(context, UUID.randomUUID().hashCode(),
            Intent(broadcastAction).setPackage(context.packageName), flags)
        chooserCallback = callback
        return Intent.createChooser(WorkspaceFileIntents.share(context, cached), "Share file", callback.intentSender)
    }

    fun saveState(): Bundle? {
        val action = saving ?: return null
        val cached = action.cached ?: return null
        val request = action.request
        return Bundle().apply {
            putString("request", JSONObject().put("request_id", request.requestId).put("action", request.action)
                .put("path", request.path).put("sha256", request.sha256 ?: JSONObject.NULL).put("mime_type", request.mimeType)
                .apply { request.workspaceId?.let { put("workspace_id", it) } }.toString())
            putString("directory", cached.file.parentFile!!.name)
            putString("filename", cached.file.name)
            putString("sha256", cached.sha256)
            putLong("size", cached.size)
        }
    }

    fun restoreSave(state: Bundle?) {
        if (state == null) return
        runCatching {
            val request = WorkspaceFileRequest.parse(state.getString("request") ?: return)
            require(request.action == "save")
            val directory = state.getString("directory") ?: return
            val filename = state.getString("filename") ?: return
            val file = WorkspaceFileCache.checkedFile(context, File(File(WorkspaceFileCache.root(context), directory), filename))
            val sha = state.getString("sha256") ?: return
            val size = state.getLong("size", -1)
            require(Regex("[a-f0-9]{64}").matches(sha) && size >= 0 && file.isFile && file.length() == size)
            val action = Pending(request).apply {
                cached = CachedWorkspaceFile(file, request.mimeType, sha, size)
                lease = WorkspaceFileCache.pin(file.parentFile!!)
            }
            synchronized(lock) { pending[request.requestId] = action }
            saving = action
            pickerOwner = action
        }
    }

    private fun finish(action: Pending, result: JSONObject) {
        synchronized(lock) {
            if (action.completed) return
            action.completed = true
            pending.remove(action.request.requestId)
        }
        action.lease?.close()
        action.lease = null
        if (action.request.action == "save" || !action.handedToExternalApp) {
            action.cached?.file?.parentFile?.let(WorkspaceFileCache::discard)
        }
        if (sharing !== action) releasePicker(action)
        notifyResult(result)
    }

    private fun releasePicker(action: Pending) {
        synchronized(lock) { if (pickerOwner === action) pickerOwner = null }
    }

    private fun clearChooserCallback() {
        chooserReceiver?.let { runCatching { context.unregisterReceiver(it) } }
        chooserReceiver = null
        chooserCallback?.cancel()
        chooserCallback = null
    }

    override fun close() = close(preserveSave = false)

    fun close(preserveSave: Boolean) {
        val remaining = synchronized(lock) {
            closed = true
            pending.values.toList()
        }
        remaining.forEach {
            if (preserveSave && it === saving) {
                synchronized(lock) { it.completed = true; pending.remove(it.request.requestId) }
                it.lease?.close()
                it.lease = null
            } else finish(it, it.request.result(false, "File action cancelled", cancelled = true))
        }
        saving = null
        sharing = null
        synchronized(lock) { pickerOwner = null }
        clearChooserCallback()
    }

    private fun rejected(error: String): String = JSONObject().put("ok", false).put("error", error).toString()

    private fun publicError(failure: Exception): String = when (failure) {
        is ActivityNotFoundException -> "No installed app can handle this file; try saving or sharing it"
        is IllegalArgumentException, is IllegalStateException -> failure.message ?: "The file action could not be completed"
        is java.io.IOException -> if (failure.javaClass == java.io.IOException::class.java)
            failure.message ?: "The file transfer failed; try again" else "The file transfer failed; try again"
        is SecurityException -> "The system did not grant access to this file action"
        else -> "The file action could not be completed; try again"
    }
}
