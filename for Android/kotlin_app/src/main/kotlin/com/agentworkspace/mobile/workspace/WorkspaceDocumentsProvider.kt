package com.agentworkspace.mobile.workspace

import com.agentworkspace.mobile.UiText

import android.content.Context
import android.content.ContentResolver
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.os.Bundle
import android.os.CancellationSignal
import android.os.Handler
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.os.SystemClock
import android.provider.DocumentsContract
import android.provider.DocumentsProvider
import com.agentworkspace.mobile.R
import com.agentworkspace.mobile.embedded.LocalEngineClient
import org.json.JSONObject
import java.io.File
import java.io.FileNotFoundException
import java.util.Locale

/** A read-only SAF view. The authenticated gateway retains ownership of path checks. */
class WorkspaceDocumentsProvider : DocumentsProvider() {
    private lateinit var gateway: WorkspaceDocumentsGateway
    private fun ui(zh: String, en: String) = UiText.of(requireNotNull(context), zh, en)

    override fun onCreate(): Boolean {
        gateway = WorkspaceDocumentsGateway(requireNotNull(context))
        return true
    }

    override fun queryRoots(projection: Array<out String>?): Cursor {
        val cursor = DocumentsCursor(projection ?: ROOT_COLUMNS)
        try {
            gateway.workspaces().forEach { workspace ->
                cursor.add(mapOf(
                    DocumentsContract.Root.COLUMN_ROOT_ID to workspace.id,
                    DocumentsContract.Root.COLUMN_DOCUMENT_ID to WorkspaceDocumentId.root(workspace.id).value,
                    DocumentsContract.Root.COLUMN_TITLE to "Agent Workspace · ${workspace.name}",
                    DocumentsContract.Root.COLUMN_SUMMARY to ui("工作区文件和附件（仅供查看）", "Workspace files and attachments (view only)"),
                    DocumentsContract.Root.COLUMN_FLAGS to (DocumentsContract.Root.FLAG_LOCAL_ONLY or DocumentsContract.Root.FLAG_SUPPORTS_IS_CHILD or DocumentsContract.Root.FLAG_SUPPORTS_SEARCH),
                    DocumentsContract.Root.COLUMN_MIME_TYPES to "*/*",
                    DocumentsContract.Root.COLUMN_QUERY_ARGS to DocumentsContract.QUERY_ARG_DISPLAY_NAME,
                    DocumentsContract.Root.COLUMN_ICON to R.drawable.ic_launcher,
                ))
            }
        } catch (_: Exception) {
            cursor.information.putString(DocumentsContract.EXTRA_ERROR, engineRequired(requireNotNull(context)))
        }
        context?.let { cursor.setNotificationUri(it.contentResolver, DocumentsContract.buildRootsUri(authority(it))) }
        return cursor
    }

    // SDK 35 marks Bundle non-null although its final route passes null for
    // legacy resolver calls. Match the JVM signature while accepting that value.
    @Suppress("NOTHING_TO_OVERRIDE", "ACCIDENTAL_OVERRIDE")
    override fun querySearchDocuments(rootId: String, projection: Array<out String?>?, queryArgs: Bundle?): Cursor {
        val columns = projection?.map { requireNotNull(it) }?.toTypedArray()
        val query = queryArgs?.getString(DocumentsContract.QUERY_ARG_DISPLAY_NAME)
        if (query == null) {
            return DocumentsCursor(columns ?: DOCUMENT_COLUMNS).apply {
                // The framework route discards the legacy URI query before
                // calling this overload, so its search term cannot be recovered.
                information.putString(DocumentsContract.EXTRA_ERROR, legacySearchUnavailable(requireNotNull(context)))
            }
        }
        return querySearchDocuments(rootId, query, columns).apply {
            extras.putStringArray(ContentResolver.EXTRA_HONORED_ARGS, arrayOf(DocumentsContract.QUERY_ARG_DISPLAY_NAME))
        }
    }

    override fun queryDocument(documentId: String, projection: Array<out String>?): Cursor = checkedDocument {
        val document = gateway.document(WorkspaceDocumentId.parse(documentId))
        DocumentsCursor(projection ?: DOCUMENT_COLUMNS).apply { addDocument(document) }
    }

    override fun queryChildDocuments(parentDocumentId: String, projection: Array<out String>?, sortOrder: String?): Cursor = checkedDocument {
        val parent = WorkspaceDocumentId.parse(parentDocumentId)
        val listing = gateway.children(parent)
        DocumentsCursor(projection ?: DOCUMENT_COLUMNS).apply {
            listing.documents.forEach(::addDocument)
            if (listing.truncated) information.putString(DocumentsContract.EXTRA_INFO,
                ui("此目录较大，仅显示部分文件；请在 Agent 中整理目录后刷新", "This folder is large; only some files are shown. Tidy it in Agent and refresh"))
        }
    }

    override fun querySearchDocuments(rootId: String, query: String, projection: Array<out String>?): Cursor {
        val cursor = DocumentsCursor(projection ?: DOCUMENT_COLUMNS)
        try {
            val root = WorkspaceDocumentId.root(rootId)
            val registeredRoot = gateway.workspace(rootId)
            require(query.length <= 2048 && query.none(Char::isISOControl)) { "Invalid file name query" }
            if (query.isBlank()) {
                cursor.information.putString(DocumentsContract.EXTRA_INFO, ui("请输入要搜索的文件名", "Enter a file name to search for"))
                return cursor
            }
            val queue = ArrayDeque<Pair<WorkspaceDocumentId, Int>>().apply { add(root to 0) }
            var directories = 0
            var examinedEntries = 0
            var matches = 0
            var truncated = false
            val deadline = SystemClock.elapsedRealtime() + SEARCH_MAX_MILLIS
            search@ while (queue.isNotEmpty()) {
                if (directories >= SEARCH_MAX_DIRECTORIES || examinedEntries >= SEARCH_MAX_ENTRIES || SystemClock.elapsedRealtime() >= deadline) {
                    truncated = true
                    break
                }
                val (directory, depth) = queue.removeFirst()
                val listing = gateway.children(directory, SEARCH_MAX_ENTRIES - examinedEntries, registeredRoot)
                directories++
                examinedEntries += listing.examinedEntries
                truncated = truncated || listing.truncated
                for (document in listing.documents) {
                    if (document.name.contains(query, ignoreCase = true)) {
                        cursor.addDocument(document)
                        matches++
                        if (matches >= SEARCH_MAX_MATCHES) {
                            truncated = true
                            break@search
                        }
                    }
                    if (document.directory) {
                        // A returned document's depth is its number of path
                        // components. Directory contents beyond depth 8 are
                        // not visited, even if they would have matched.
                        if (depth + 1 < SEARCH_MAX_DEPTH) queue.add(document.id to depth + 1)
                        else truncated = true
                    }
                }
            }
            if (truncated) cursor.information.putString(DocumentsContract.EXTRA_INFO,
                ui("搜索结果不完整：目录较大、层级较深、匹配较多或搜索耗时较长，部分文件未显示。请在工作区内浏览目标文件夹。", "Search results are incomplete: the folder is large or deep, there are many matches, or the search took too long. Browse the target folder in the workspace."))
        } catch (failure: Exception) {
            cursor.information.putString(DocumentsContract.EXTRA_ERROR,
                if (failure is FileNotFoundException) failure.message ?: engineRequired(requireNotNull(context)) else ui("搜索未完成。$ENGINE_REQUIRED", "Search did not finish. $ENGINE_REQUIRED_EN"))
        }
        return cursor
    }

    override fun isChildDocument(parentDocumentId: String, documentId: String): Boolean = try {
        val parent = WorkspaceDocumentId.parse(parentDocumentId)
        val child = WorkspaceDocumentId.parse(documentId)
        if (parent.workspaceId != child.workspaceId || parent == child) false
        else if (parent.path.isNotEmpty() && !child.path.startsWith(parent.path + "/")) false
        else gateway.document(parent).directory && gateway.document(child).id == child
    } catch (_: Exception) { false }

    override fun openDocument(documentId: String, mode: String, signal: CancellationSignal?): ParcelFileDescriptor = checkedDocument {
        if (mode != "r") throw FileNotFoundException(ui("此工作区入口仅支持读取；请在 Agent 中编辑文件", "This workspace entry is read-only; edit files in Agent"))
        signal?.throwIfCanceled()
        val document = gateway.document(WorkspaceDocumentId.parse(documentId))
        if (document.directory) throw FileNotFoundException(ui("文件夹不能作为文件打开", "A folder cannot be opened as a file"))
        val cached = gateway.download(document)
        val directory = requireNotNull(cached.file.parentFile)
        val pin = WorkspaceFileCache.pin(directory)
        try {
            signal?.throwIfCanceled()
            // Seekable descriptors also work with PDF readers. This cache copy
            // belongs to this descriptor, so it need not occupy the share cache
            // after the external reader has closed it.
            ParcelFileDescriptor.open(cached.file, ParcelFileDescriptor.MODE_READ_ONLY,
                Handler(Looper.getMainLooper())) {
                pin.close()
                WorkspaceFileCache.discard(directory)
            }
        } catch (failure: Exception) {
            pin.close()
            WorkspaceFileCache.discard(directory)
            throw failure
        }
    }

    private inline fun <T> checkedDocument(block: () -> T): T = try { block() }
    catch (failure: FileNotFoundException) { throw failure }
    catch (failure: android.os.OperationCanceledException) { throw failure }
    catch (_: Exception) { throw FileNotFoundException(ui("文件无法读取。$ENGINE_REQUIRED", "The file cannot be read. $ENGINE_REQUIRED_EN")) }

    private class DocumentsCursor(columns: Array<out String>) : MatrixCursor(columns) {
        val information = Bundle()
        override fun getExtras(): Bundle = information
        fun add(values: Map<String, Any?>) { addRow(columnNames.map { values[it] }.toTypedArray()) }
        fun addDocument(document: WorkspaceDocument) = add(mapOf(
            DocumentsContract.Document.COLUMN_DOCUMENT_ID to document.id.value,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME to document.name,
            DocumentsContract.Document.COLUMN_MIME_TYPE to document.mimeType,
            DocumentsContract.Document.COLUMN_FLAGS to 0,
            DocumentsContract.Document.COLUMN_SIZE to if (document.directory) null else document.size,
            DocumentsContract.Document.COLUMN_LAST_MODIFIED to null,
        ))
    }

    companion object {
        const val ENGINE_REQUIRED = "请先打开 Agent 并启动引擎，再返回文件管理器重试"
        const val LEGACY_SEARCH_UNAVAILABLE = "此文件管理器使用了旧版搜索接口，系统未传递搜索词；请使用支持系统文档搜索的文件管理器，或浏览工作区目录"
        const val ENGINE_REQUIRED_EN = "Open Agent and start the engine, then return to the file manager and try again"
        const val LEGACY_SEARCH_UNAVAILABLE_EN = "This file manager uses the old search interface and the system did not pass the search term; use a file manager that supports system document search, or browse the workspace"
        fun engineRequired(context: Context) = UiText.of(context, ENGINE_REQUIRED, ENGINE_REQUIRED_EN)
        fun legacySearchUnavailable(context: Context) = UiText.of(context, LEGACY_SEARCH_UNAVAILABLE, LEGACY_SEARCH_UNAVAILABLE_EN)
        private const val SEARCH_MAX_DIRECTORIES = 64
        private const val SEARCH_MAX_ENTRIES = 1000
        private const val SEARCH_MAX_MATCHES = 100
        private const val SEARCH_MAX_DEPTH = 8
        private const val SEARCH_MAX_MILLIS = 15_000L
        fun authority(context: Context): String = context.packageName + ".workspace-documents"
        private val ROOT_COLUMNS = arrayOf(DocumentsContract.Root.COLUMN_ROOT_ID,
            DocumentsContract.Root.COLUMN_DOCUMENT_ID, DocumentsContract.Root.COLUMN_TITLE,
            DocumentsContract.Root.COLUMN_SUMMARY, DocumentsContract.Root.COLUMN_FLAGS,
            DocumentsContract.Root.COLUMN_MIME_TYPES, DocumentsContract.Root.COLUMN_QUERY_ARGS, DocumentsContract.Root.COLUMN_ICON)
        private val DOCUMENT_COLUMNS = arrayOf(DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE,
            DocumentsContract.Document.COLUMN_FLAGS, DocumentsContract.Document.COLUMN_SIZE,
            DocumentsContract.Document.COLUMN_LAST_MODIFIED)
    }
}

internal data class WorkspaceDocumentId private constructor(val workspaceId: String, val path: String) {
    val value: String get() = "$workspaceId:$path"
    companion object {
        private val workspacePattern = Regex("[A-Za-z0-9._-]{1,128}")
        private val privateDirectories = setOf(".git", ".venv", "venv", "node_modules", "__pycache__",
            ".pytest_cache", ".mypy_cache", ".ruff_cache", ".agent", ".agent-workspace", ".agent_workspace", ".agent-upload-request",
            ".aws", ".azure", ".docker", ".kube", ".ssh", "gcloud", "local-models", "native-model-imports")
        private val privateNames = setOf(".env", ".envrc", ".git-credentials", ".netrc", ".npmrc", ".pypirc",
            "_netrc", "credentials", "credentials.json", "id_dsa", "id_ecdsa", "id_ed25519", "id_rsa",
            "id_xmss", "known_hosts", "secrets.json", "terraform.rc", "serve.token", "agent.db",
            "mobile-workspaces-v1.json", "session-presentation.json", "mobile-extensions.json",
            "mobile-management.db", "mobile-schedules.json")
        private val privateSuffixes = setOf(".jks", ".key", ".keystore", ".p12", ".pem", ".pfx", ".ppk")

        fun root(workspaceId: String): WorkspaceDocumentId = child(workspaceId, "")
        fun child(workspaceId: String, path: String): WorkspaceDocumentId {
            require(workspacePattern.matches(workspaceId)) { "Invalid workspace identity" }
            require(path.length <= 2048 && !path.startsWith('/') && path.none { it.isISOControl() || it in "\\:" }) {
                "Invalid workspace document path"
            }
            if (path.isNotEmpty()) {
                val parts = path.split('/')
                require(parts.all { it.isNotEmpty() && it != "." && it != ".." && it.lowercase(Locale.ROOT) !in privateDirectories }) {
                    "Private and parent paths cannot be opened"
                }
                val name = parts.last().lowercase(Locale.ROOT)
                require(name !in privateNames && !name.startsWith(".env.") && privateSuffixes.none { name.endsWith(it) } &&
                    privateNames.none { name == "$it-wal" || name == "$it-shm" || name == "$it-journal" }) {
                    "Private files cannot be opened"
                }
            }
            return WorkspaceDocumentId(workspaceId, path)
        }
        fun parse(value: String): WorkspaceDocumentId {
            require(value.length <= 2177 && ':' in value) { "Invalid workspace document identity" }
            return child(value.substringBefore(':'), value.substringAfter(':'))
        }
    }
}

internal data class WorkspaceDocumentRoot(val id: String, val name: String)
internal data class WorkspaceDocument(val id: WorkspaceDocumentId, val name: String, val directory: Boolean, val size: Long) {
    val mimeType: String get() = if (directory) DocumentsContract.Document.MIME_TYPE_DIR else WorkspaceFileMime.vetted(id.path, null)
}
internal data class WorkspaceDocumentListing(val documents: List<WorkspaceDocument>, val truncated: Boolean, val examinedEntries: Int)

internal class WorkspaceDocumentsGateway(private val context: Context,
    tokenFile: File = File(context.filesDir, "serve.token"), baseUrl: String = "http://127.0.0.1:8080") {
    private val client = LocalEngineClient(context, tokenFile, baseUrl)
    private val downloads = WorkspaceFileDownloadStore(context, tokenFile, baseUrl)

    fun workspaces(): List<WorkspaceDocumentRoot> {
        val rows = client.request("GET", "/mobile/workspaces").getJSONArray("workspaces")
        val roots = (0 until rows.length()).map { index ->
            val row = rows.getJSONObject(index)
            val id = row.getString("id")
            WorkspaceDocumentId.root(id)
            val name = row.getString("name")
            require(name.isNotBlank() && name.none(Char::isISOControl))
            val displayEnd = name.offsetByCodePoints(0, minOf(120, name.codePointCount(0, name.length)))
            WorkspaceDocumentRoot(id, name.substring(0, displayEnd))
        }
        require(roots.map { it.id }.distinct().size == roots.size)
        return roots
    }

    fun workspace(id: String): WorkspaceDocumentRoot = workspaces().singleOrNull { it.id == id }
        ?: throw FileNotFoundException(UiText.of(context, "此工作区已不存在，请在 Agent 中刷新工作区", "This workspace no longer exists; refresh workspaces in Agent"))

    fun children(parent: WorkspaceDocumentId, maxEntries: Int = 500, registeredRoot: WorkspaceDocumentRoot? = null): WorkspaceDocumentListing {
        require(maxEntries > 0)
        if (registeredRoot == null) workspace(parent.workspaceId)
        else require(registeredRoot.id == parent.workspaceId) { "Workspace identity does not match the directory" }
        val route = Uri.Builder().path("/mobile/workspace/files").appendQueryParameter("workspace_id", parent.workspaceId)
            .appendQueryParameter("path", parent.path).build().toString()
        val listing = client.request("GET", route)
        require(listing.getString("path") == parent.path)
        val entries = listing.getJSONArray("files")
        val examinedEntries = minOf(entries.length(), maxEntries)
        val documents = (0 until examinedEntries).mapNotNull { index ->
            val entry = entries.getJSONObject(index)
            val path = entry.getString("path")
            val id = runCatching { WorkspaceDocumentId.child(parent.workspaceId, path) }.getOrNull() ?: return@mapNotNull null
            if (path.isEmpty() || path.substringBeforeLast('/', "") != parent.path) return@mapNotNull null
            val name = entry.getString("name")
            if (name != path.substringAfterLast('/')) return@mapNotNull null
            val type = entry.getString("type")
            if (type !in setOf("directory", "file")) return@mapNotNull null
            val size = entry.getLong("size")
            if (size < 0) return@mapNotNull null
            WorkspaceDocument(id, name, type == "directory", size)
        }
        require(documents.map { it.id }.distinct().size == documents.size)
        return WorkspaceDocumentListing(documents, listing.optBoolean("truncated") || examinedEntries < entries.length(), examinedEntries)
    }

    fun document(id: WorkspaceDocumentId): WorkspaceDocument {
        val root = workspace(id.workspaceId)
        if (id.path.isEmpty()) return WorkspaceDocument(id, root.name, true, 0)
        return children(WorkspaceDocumentId.child(id.workspaceId, id.path.substringBeforeLast('/', "")))
            .documents.singleOrNull { it.id == id } ?: throw FileNotFoundException(UiText.of(context, "文件已不存在，请刷新工作区", "The file no longer exists; refresh the workspace"))
    }

    fun download(document: WorkspaceDocument): CachedWorkspaceFile = downloads.download(WorkspaceFileRequest(
        "documents-read", "open", document.id.path, null, document.mimeType, document.id.workspaceId))
}
