package com.agentworkspace.mobile.sharing

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONObject
import java.io.File
import java.nio.file.Files
import java.nio.file.LinkOption
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.CopyOnWriteArraySet
import java.util.concurrent.ConcurrentHashMap

/** Application lifetime queue: leaving or rotating the Activity does not cancel staged uploads. */
class ShareInboxController private constructor(private val context: Context) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val transfers = Mutex()
    private val mainHandler = Handler(Looper.getMainLooper())
    private val listeners = CopyOnWriteArraySet<() -> Unit>()
    private val unsavedFailures = ConcurrentHashMap<String, Pair<String, Boolean>>()
    private val store by lazy { ShareInboxStore(File(context.filesDir.canonicalFile, "share-inbox-v1")) }
    private val uploader = ShareInboxUpload(File(context.filesDir, "serve.token"))
    @Volatile private var captureFailure: String? = null

    fun addListener(listener: () -> Unit) { listeners.add(listener) }
    fun removeListener(listener: () -> Unit) { listeners.remove(listener) }

    fun snapshot(): String = try {
        val result = JSONObject(store.snapshot())
        result.getJSONArray("items").let { items -> for (index in 0 until items.length()) {
            val item = items.getJSONObject(index)
            unsavedFailures[item.getString("id")]?.let { error ->
                item.put("state", "error").put("error", error.first).put("uncertain", error.second)
            }
        } }
        captureFailure?.let { result.put("capture_error", it) }
        result.toString()
    } catch (_: Exception) { failure("无法读取分享收件箱；现有记录已保留") }

    fun captureIntent(intent: Intent?, batchId: String) {
        if (intent?.action !in setOf(Intent.ACTION_SEND, Intent.ACTION_SEND_MULTIPLE)) return
        val sources = runCatching { ShareInboxIntents.readWithWarning(intent ?: return) }.getOrElse {
            captureFailure = "分享内容格式无法读取，请重新分享"
            changed()
            return
        }
        capture(sources.uris, sources.text, sources.mediaType, batchId, sources.warning)
    }

    fun captureFiles(uris: List<Uri>, batchId: String = UUID.randomUUID().toString()) = capture(uris, null, null, batchId)

    private fun capture(uris: List<Uri>, text: String?, defaultType: String?, batchId: String, warning: String? = null) {
        scope.launch {
            try {
                require(uris.isNotEmpty() || text != null) { "分享内容不可读取" }
                val sources = mutableListOf<InboxSource>()
                text?.let { sources.add(InboxSource("分享的文字.txt", text = it)) }
                uris.distinct().forEach { uri -> sources.add(source(uri, defaultType)) }
                val added = store.capture(batchId, sources)
                captureFailure = warning
                changed()
                added.filter { it.kind == "file" }.forEach { item ->
                    try {
                        val staged = stage(item)
                        store.update(item.id) { it.copy(state = "pending", size = staged.size, sha256 = staged.sha256, error = null) }
                    } catch (_: Exception) {
                        rememberFailure(item.id, "无法接收或保存此文件，请检查存储空间后重试", false)
                    }
                    changed()
                }
            } catch (_: Exception) {
                captureFailure = "分享内容未能保存，请检查存储空间后重新分享"
                changed()
            }
        }
    }

    fun confirm(raw: String): String = try {
        val request = InboxConfirmation.parse(raw)
        persistFailures(request.itemIds)
        val jobs = store.bind(request)
        changed()
        if (jobs.isNotEmpty()) scope.launch {
            transfers.withLock {
                jobs.forEach { job -> transfer(job.id) }
            }
        }
        JSONObject().put("ok", true).put("queued", true).put("request_id", request.requestId).toString()
    } catch (error: Exception) { failure(if (error is IllegalArgumentException || error is IllegalStateException)
        error.message ?: "无法确认收件项" else "无法保存收件确认，请检查设备存储空间") }

    fun discard(raw: String): String = remove(raw, false)
    fun acknowledge(raw: String): String = remove(raw, true)

    private fun remove(raw: String, acknowledge: Boolean): String = try {
        require(raw.toByteArray(Charsets.UTF_8).size <= ShareInboxStore.MAX_METADATA_BYTES)
        val payload = JSONObject(raw)
        require(payload.keys().asSequence().all { it == "item_ids" })
        val ids = InboxConfirmation.itemIds(payload)
        if (acknowledge) persistFailures(ids)
        store.remove(ids, acknowledge, unsavedFailures.keys.toSet())
        ids.forEach { unsavedFailures.remove(it) }
        changed()
        JSONObject().put("ok", true).toString()
    } catch (error: Exception) { failure(if (error is IllegalArgumentException || error is IllegalStateException)
        error.message ?: "无法处理收件项" else "无法保存收件箱记录，请稍后重试") }

    private fun transfer(id: String) {
        val selected = store.item(id)?.takeIf { it.state == "importing" } ?: return
        var imported = false
        try {
            uploader.validateTarget(selected.workspaceId!!, selected.sessionId!!)
            val ready = if (selected.kind == "file") {
                val staged = stage(selected)
                store.update(id) { it.copy(size = staged.size, sha256 = staged.sha256) } ?: return
            } else selected
            val attachment = if (ready.kind == "file") {
                val receipt = uploader.upload(ready, store.file(id))
                imported = true
                receipt.toString()
            } else null
            store.update(id) { it.copy(state = "ready", attachment = attachment, error = null, uncertain = false, sourceUri = null) }
        } catch (failure: Exception) {
            val uncertain = selected.uncertain || imported || (failure as? InboxTransferFailure)?.uncertain == true
            rememberFailure(id, when (failure) {
                    is InboxTransferFailure -> failure.message
                    is IllegalArgumentException -> "所选工作区或会话无效，请检查目标后重试"
                    else -> if (uncertain) "导入结果尚未确认，重试会核实同一次请求" else "文件导入失败，请检查服务或存储空间后重试"
                } ?: "文件导入失败，请重试", uncertain)
        }
        changed()
    }

    private fun stage(item: InboxItem): StagedShareFile {
        val file = store.file(item.id)
        if (Files.exists(file.toPath(), LinkOption.NOFOLLOW_LINKS)) {
            check(Files.isRegularFile(file.toPath(), LinkOption.NOFOLLOW_LINKS) && file.canonicalFile == file)
            val digest = MessageDigest.getInstance("SHA-256")
            var size = 0L
            file.inputStream().use { input ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    if (count == 0) continue
                    digest.update(buffer, 0, count)
                    size += count
                }
            }
            val sha = ShareInboxUpload.hex(digest.digest())
            check((item.sha256.isEmpty() || sha == item.sha256) && (item.sourceSize < 0 || size == item.sourceSize))
            return StagedShareFile(file, size, sha)
        }
        val partial = store.partial(item.id)
        if (Files.exists(partial.toPath(), LinkOption.NOFOLLOW_LINKS)) {
            check(Files.isRegularFile(partial.toPath(), LinkOption.NOFOLLOW_LINKS) && partial.canonicalFile == partial && partial.delete())
        }
        val uri = Uri.parse(item.sourceUri ?: error("需要重新分享此文件"))
        require(uri.scheme == "content")
        val stream = context.contentResolver.openInputStream(uri) ?: error("无法读取分享文件")
        return stream.use { ShareInboxFiles.copy(store.root, item.id, it, item.sourceSize) }
    }

    private fun source(uri: Uri, defaultType: String?): InboxSource {
        require(uri.scheme == "content")
        var name = uri.lastPathSegment ?: "shared-file"
        var size = -1L
        runCatching {
            context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val nameColumn = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    val sizeColumn = cursor.getColumnIndex(OpenableColumns.SIZE)
                    if (nameColumn >= 0 && !cursor.isNull(nameColumn)) name = cursor.getString(nameColumn)
                    if (sizeColumn >= 0 && !cursor.isNull(sizeColumn)) size = cursor.getLong(sizeColumn).coerceAtLeast(-1L)
                }
            }
        }
        val supplied = runCatching { context.contentResolver.getType(uri) }.getOrNull() ?: defaultType
        val mime = supplied?.lowercase(java.util.Locale.ROOT)?.takeIf {
            it.length <= 128 && it.matches(Regex("[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+"))
        } ?: "application/octet-stream"
        return InboxSource(ShareInboxFiles.safeName(name), uri.toString(), mime, size)
    }

    private fun changed() { mainHandler.post { listeners.forEach { runCatching { it() } } } }

    private fun rememberFailure(id: String, message: String, uncertain: Boolean) {
        try {
            store.update(id) { it.copy(state = "error", error = message, uncertain = uncertain) }
            unsavedFailures.remove(id)
        } catch (_: Exception) {
            unsavedFailures[id] = message to uncertain
            captureFailure = "无法保存收件状态；文件已保留，请释放存储空间后重试"
        }
    }

    private fun persistFailures(ids: Set<String>) {
        ids.forEach { id -> unsavedFailures[id]?.let { failed ->
            store.update(id) { it.copy(state = "error", error = failed.first, uncertain = failed.second) }
            unsavedFailures.remove(id, failed)
        } }
        if (unsavedFailures.isEmpty()) captureFailure = null
    }

    companion object {
        @Volatile private var instance: ShareInboxController? = null
        fun get(context: Context): ShareInboxController = instance ?: synchronized(this) {
            instance ?: ShareInboxController(context.applicationContext).also { instance = it }
        }
        fun failure(message: String): String = JSONObject().put("ok", false).put("error", message).toString()
    }
}

internal object ShareInboxIntents {
    data class Sources(val uris: List<Uri>, val text: String?, val mediaType: String?, val warning: String?)

    fun read(intent: Intent): Triple<List<Uri>, String?, String?> = readWithWarning(intent).let { Triple(it.uris, it.text, it.mediaType) }

    fun readWithWarning(intent: Intent): Sources {
        val streams = LinkedHashSet<Uri>()
        var malformed = false
        fun add(uri: Uri?) {
            if (uri?.scheme == "content") streams.add(uri)
            else if (uri != null) malformed = true
        }
        runCatching {
            if (intent.action == Intent.ACTION_SEND_MULTIPLE) {
                val values = if (Build.VERSION.SDK_INT >= 33) intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
                    else @Suppress("DEPRECATION") intent.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM)
                values?.forEach(::add)
                if (values == null && intent.hasExtra(Intent.EXTRA_STREAM)) malformed = true
            } else {
                val value = if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
                    else @Suppress("DEPRECATION") intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
                add(value)
                if (value == null && intent.hasExtra(Intent.EXTRA_STREAM)) malformed = true
            }
        }.onFailure { malformed = true }
        runCatching { intent.clipData?.let { clip -> for (index in 0 until clip.itemCount) add(clip.getItemAt(index).uri) } }
            .onFailure { malformed = true }
        add(intent.data)
        val rawText = runCatching { intent.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString() }.onFailure { malformed = true }.getOrNull()
        if (rawText == null && intent.hasExtra(Intent.EXTRA_TEXT)) malformed = true
        val text = cleanText(rawText)
        return Sources(streams.toList(), text, intent.type,
            if (malformed) "部分分享内容无法读取；可读取的内容已保留，请重新分享缺少的文件" else null)
    }

    fun cleanText(raw: String?): String? {
        if (raw == null) return null
        val cleaned = raw.replace("\r\n", "\n").replace('\r', '\n')
            .filter { it == '\n' || it == '\t' || !Character.isISOControl(it) }
        if (cleaned.isBlank()) return null
        return cleaned
    }
}
