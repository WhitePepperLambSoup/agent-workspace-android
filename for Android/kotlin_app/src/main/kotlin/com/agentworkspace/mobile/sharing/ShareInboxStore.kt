package com.agentworkspace.mobile.sharing

import android.util.AtomicFile
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.nio.file.LinkOption
import java.util.UUID

internal data class InboxSource(val name: String, val uri: String? = null,
    val mediaType: String = "text/plain", val size: Long = -1, val text: String? = null)

internal data class InboxItem(
    val id: String, val batchId: String, val name: String, val kind: String, val state: String,
    val mediaType: String, val size: Long = -1, val sha256: String = "", val text: String? = null,
    val sourceUri: String? = null, val sourceSize: Long = -1,
    val workspaceId: String? = null, val sessionId: String? = null,
    val confirmationId: String? = null, val attachment: String? = null,
    val error: String? = null, val uncertain: Boolean = false,
) {
    val uploadRequestId: String get() = "share-$id"

    fun json(privateFields: Boolean = false): JSONObject = JSONObject().put("id", id).put("batch_id", batchId)
        .put("name", name).put("kind", kind).put("state", state).put("media_type", mediaType)
        .put("size", size).put("sha256", sha256).apply {
            text?.let { put("text", it) }
            workspaceId?.let { put("workspace_id", it) }
            sessionId?.let { put("session_id", it) }
            if (workspaceId != null && sessionId != null) {
                put("target", JSONObject().put("workspace_id", workspaceId).put("session_id", sessionId))
            }
            confirmationId?.let { put("request_id", it) }
            attachment?.let { put("attachment", JSONObject(it)) }
            error?.let { put("error", it) }
            if (uncertain) put("uncertain", true)
            if (privateFields) {
                sourceUri?.let { put("source_uri", it) }
                put("source_size", sourceSize)
            }
        }

    companion object {
        fun parse(value: JSONObject): InboxItem {
            fun optional(key: String) = value.opt(key) as? String
            val id = value.getString("id")
            require(validId(id) && validId(value.getString("batch_id"))) { "Invalid inbox identity" }
            val kind = value.getString("kind")
            val state = value.getString("state")
            require(kind in setOf("file", "text") && state in setOf("staging", "pending", "importing", "ready", "error"))
            val name = value.getString("name")
            require(name == ShareInboxFiles.safeName(name)) { "Invalid inbox filename" }
            val sha = value.optString("sha256")
            require(sha.isEmpty() || sha.matches(Regex("[0-9a-f]{64}"))) { "Invalid inbox digest" }
            return InboxItem(id, value.getString("batch_id"), name, kind, state, value.getString("media_type"),
                value.optLong("size", -1), sha, optional("text"), optional("source_uri"), value.optLong("source_size", -1),
                optional("workspace_id"), optional("session_id"), optional("request_id"),
                value.optJSONObject("attachment")?.toString(), optional("error"), value.optBoolean("uncertain"))
        }

        fun validId(id: String) = id.matches(Regex("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"))
    }
}

/** Only this private store owns staged files; workspace files never enter its cleanup paths. */
internal class ShareInboxStore(val root: File) {
    private val lock = Any()
    private val metadata = AtomicFile(File(root, "inbox.json"))
    private var items = emptyList<InboxItem>()
    private var batches = emptySet<String>()
    private var storageWarning: String? = null

    init {
        check(root.canonicalFile == root.absoluteFile && (root.isDirectory || root.mkdirs()) &&
            !Files.isSymbolicLink(root.toPath())) { "分享收件箱目录不可用" }
        checkMetadataPaths()
        val stored = try { metadata.openRead() } catch (missing: java.io.FileNotFoundException) {
            if (metadata.baseFile.exists()) throw missing else null
        }
        stored?.use { input ->
            val bytes = input.readBytesLimited(MAX_METADATA_BYTES)
            val document = JSONObject(String(bytes, Charsets.UTF_8))
            require(document.getInt("version") == 1) { "Unsupported inbox version" }
            items = document.getJSONArray("items").let { values ->
                (0 until values.length()).map { InboxItem.parse(values.getJSONObject(it)) }
            }
            require(items.map { it.id }.distinct().size == items.size)
            batches = document.getJSONArray("batches").let { values ->
                (0 until values.length()).map { values.getString(it).also { id -> require(InboxItem.validId(id)) } }.toSet()
            }
            val recovered = items.map { item -> when (item.state) {
                "staging" -> item.copy(state = "error", error = "文件接收曾被中断，请重试或重新分享")
                "importing" -> item.copy(state = "error", uncertain = item.kind == "file",
                    error = "导入曾被中断，请重试以核实结果")
                else -> item
            } }
            if (recovered != items) {
                try { commit(recovered, batches) }
                catch (_: Exception) {
                    items = recovered
                    storageWarning = "收件恢复状态暂未保存；文件和记录已保留，请释放设备存储空间后重试"
                }
            }
        }
    }

    fun snapshot(): String = synchronized(lock) {
        JSONObject().put("ok", true).put("version", 1)
            .put("items", JSONArray(items.map { it.json() })).apply {
                storageWarning?.let { put("capture_error", it) }
            }.toString()
    }

    fun capture(batchId: String, sources: List<InboxSource>): List<InboxItem> = synchronized(lock) {
        require(InboxItem.validId(batchId))
        if (batchId in batches) return emptyList()
        val additions = sources.map { source ->
            InboxItem(UUID.randomUUID().toString(), batchId, ShareInboxFiles.safeName(source.name),
                if (source.uri == null) "text" else "file", if (source.uri == null) "pending" else "staging",
                source.mediaType, if (source.uri == null) source.text!!.toByteArray(Charsets.UTF_8).size.toLong() else source.size,
                text = source.text, sourceUri = source.uri, sourceSize = source.size)
        }
        if (additions.isNotEmpty()) commit(items + additions, batches + batchId, reserveTransitions = true)
        additions
    }

    fun item(id: String): InboxItem? = synchronized(lock) { items.find { it.id == id } }

    fun update(id: String, change: (InboxItem) -> InboxItem): InboxItem? = synchronized(lock) {
        val index = items.indexOfFirst { it.id == id }
        if (index < 0) return null
        val updated = change(items[index])
        require(updated.id == id && updated.batchId == items[index].batchId)
        commit(items.toMutableList().apply { set(index, updated) }, batches)
        updated
    }

    fun bind(request: InboxConfirmation): List<InboxItem> = synchronized(lock) {
        val chosen = request.itemIds.map { id -> items.find { it.id == id } ?: error("收件项不存在或已处理") }
        chosen.forEach { item ->
            require(item.state != "staging") { "请等待文件接收完成" }
            require(item.workspaceId == null || item.workspaceId == request.workspaceId && item.sessionId == request.sessionId) {
                "已确认的收件项必须重试原工作区和会话"
            }
        }
        val runnable = chosen.filter { it.state !in setOf("ready", "importing") }.map { it.id }.toSet()
        val modified = items.map { item -> if (item.id in runnable) {
            item.copy(state = "importing", workspaceId = request.workspaceId, sessionId = request.sessionId,
                confirmationId = request.requestId, error = null)
        } else item }
        commit(modified, batches)
        modified.filter { it.id in runnable }
    }

    fun remove(ids: Set<String>, acknowledge: Boolean, completedFailures: Set<String> = emptySet()) = synchronized(lock) {
        val selected = items.filter { it.id in ids }
        require(selected.none { it.state in setOf("staging", "importing") && it.id !in completedFailures }) { "请等待当前收件操作完成" }
        if (acknowledge) require(selected.all { it.state == "ready" }) { "只有已导入并追加的收件项可以确认完成" }
        commit(items.filterNot { it.id in ids }, batches)
        selected.forEach { item ->
            file(item.id).delete()
            partial(item.id).delete()
        }
    }

    fun file(id: String): File { require(InboxItem.validId(id)); return File(root, "$id.file") }
    fun partial(id: String): File { require(InboxItem.validId(id)); return File(root, "$id.partial") }

    private fun commit(nextItems: List<InboxItem>, nextBatches: Set<String>, reserveTransitions: Boolean = false) {
        checkMetadataPaths()
        val bytes = JSONObject().put("version", 1).put("items", JSONArray(nextItems.map { it.json(true) }))
            .put("batches", JSONArray(nextBatches.toList())).toString().toByteArray(Charsets.UTF_8)
        val reserve = if (reserveTransitions) 128 * 1024L + 4096L * nextItems.count { it.state != "ready" } else 0L
        check(bytes.size.toLong() + reserve <= MAX_METADATA_BYTES) { "收件箱记录已满，请处理待确认文件后重试" }
        if (root.usableSpace < bytes.size) throw IOException("设备存储空间不足")
        val output = metadata.startWrite()
        try {
            output.write(bytes)
            output.fd.sync()
            metadata.finishWrite(output)
            check(metadata.openRead().use { it.readBytesLimited(MAX_METADATA_BYTES).contentEquals(bytes) }) {
                "收件箱记录无法确认已保存"
            }
        } catch (failure: Exception) {
            metadata.failWrite(output)
            throw failure
        }
        items = nextItems
        batches = nextBatches
        storageWarning = null
    }

    private fun checkMetadataPaths() {
        check(root.canonicalFile == root.absoluteFile && !Files.isSymbolicLink(root.toPath()))
        listOf("inbox.json", "inbox.json.bak", "inbox.json.new").forEach { name ->
            val file = File(root, name)
            check(!Files.exists(file.toPath(), LinkOption.NOFOLLOW_LINKS) ||
                Files.isRegularFile(file.toPath(), LinkOption.NOFOLLOW_LINKS) && file.canonicalFile == file) {
                "分享收件箱记录不可用"
            }
        }
    }

    companion object {
        const val MAX_METADATA_BYTES = 4 * 1024 * 1024
    }
}

internal data class InboxConfirmation(val requestId: String, val workspaceId: String, val sessionId: String, val itemIds: Set<String>) {
    companion object {
        fun parse(raw: String): InboxConfirmation {
            require(raw.toByteArray(Charsets.UTF_8).size <= ShareInboxStore.MAX_METADATA_BYTES) { "收件确认请求过大" }
            val payload = JSONObject(raw)
            require(payload.keys().asSequence().all { it in setOf("request_id", "workspace_id", "session_id", "item_ids") })
            fun identity(key: String): String = (payload.opt(key) as? String)?.also {
                require(it.matches(Regex("[A-Za-z0-9._:-]{1,256}"))) { "无效的 $key" }
            } ?: throw IllegalArgumentException("缺少 $key")
            val requestId = identity("request_id").also { require(it.matches(Regex("[A-Za-z0-9._-]{1,128}"))) }
            return InboxConfirmation(requestId, identity("workspace_id"), identity("session_id"), itemIds(payload))
        }

        fun itemIds(payload: JSONObject): Set<String> = payload.getJSONArray("item_ids").let { values ->
            require(values.length() > 0) { "请选择收件项" }
            (0 until values.length()).map { values.getString(it).also { id -> require(InboxItem.validId(id)) } }.toSet()
        }
    }
}

internal fun java.io.InputStream.readBytesLimited(limit: Int): ByteArray {
    val output = java.io.ByteArrayOutputStream()
    val buffer = ByteArray(8192)
    while (true) {
        val count = read(buffer)
        if (count < 0) break
        if (count == 0) continue
        check(output.size().toLong() + count <= limit) { "响应或收件箱记录过大" }
        output.write(buffer, 0, count)
    }
    return output.toByteArray()
}
