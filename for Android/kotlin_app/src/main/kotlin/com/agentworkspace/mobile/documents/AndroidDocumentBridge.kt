package com.agentworkspace.mobile.documents

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.graphics.pdf.PdfRenderer
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.system.Os
import android.system.OsConstants
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import com.google.android.gms.tasks.Tasks
import com.google.android.gms.tasks.Task
import com.google.mlkit.common.sdkinternal.MlKitContext
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.Text
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.FilterOutputStream
import java.io.OutputStream
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.SimpleFileVisitor
import java.nio.file.StandardCopyOption
import java.nio.file.attribute.BasicFileAttributes
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executor
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException
import java.util.concurrent.locks.ReentrantLock
import kotlin.math.ceil
import kotlin.math.max
import kotlin.math.min

/** Worker-only PDF rendering, offline OCR and Unicode layout in disposable private job directories. */
object AndroidDocumentBridge {
    private const val MAX_IMAGE_BYTES = 5L * 1024 * 1024
    private const val MAX_RENDER_PAGES = 8
    private const val MAX_DIMENSION = 1600
    private const val MAX_TEXT_CHARS = 262144
    private const val MAX_OUTPUT_PAGES = 200
    private const val MAX_REQUEST_BYTES = 2 * 1024 * 1024
    private val JOB_ID = Regex("[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")
    private val jobs = ConcurrentHashMap<String, Job>()
    private class Job(val root: File) { val lock = ReentrantLock() }
    private class DocumentError(val code: String, message: String) : RuntimeException(message)
    @Volatile private var tempRoot: File? = null
    @Volatile private var initializationError: String? = null

    @JvmStatic @Synchronized
    fun initialize(context: Context) {
        try {
            val cache = context.applicationContext.cacheDir.canonicalFile
            val root = File(cache, "native-document-tools")
            require(!Files.isSymbolicLink(root.toPath()) && root.canonicalFile == root)
            check(root.mkdirs() || root.isDirectory)
            // The default process may already have the ML Kit initializer provider; :engine has none.
            MlKitContext.initializeIfNeeded(context.applicationContext)
            tempRoot = root
            initializationError = null
        } catch (_: Exception) {
            tempRoot = null
            initializationError = "Private PDF and OCR tools could not be initialized"
        }
    }

    @JvmStatic
    fun status(): String = JSONObject().put("available", tempRoot != null)
        .put("render_pdf", tempRoot != null).put("create_pdf", tempRoot != null)
        .put("ocr", tempRoot != null).put("ocr_engine", "mlkit_bundled_chinese")
        .put("ocr_offline", true).put("temp_root", tempRoot?.path ?: JSONObject.NULL)
        .put("reason", initializationError ?: JSONObject.NULL)
        .put("limits", JSONObject().put("max_input_bytes", JSONObject.NULL)
            .put("max_output_bytes", JSONObject.NULL).put("max_image_bytes", MAX_IMAGE_BYTES)
            .put("max_render_pages", MAX_RENDER_PAGES).put("max_dimension", MAX_DIMENSION)
            .put("max_text_chars", MAX_TEXT_CHARS).put("max_output_pages", MAX_OUTPUT_PAGES))
        .toString()

    @JvmStatic @Synchronized
    fun start_job(): String = try {
        val root = checkedRoot()
        if (jobs.size >= 32) throw DocumentError("job_limit", "Release finished PDF jobs before starting another")
        val id = UUID.randomUUID().toString()
        val directory = File(root, id)
        check(directory.mkdir())
        val job = Job(directory)
        jobs[id] = job
        success(id).put("job_id", id).put("root", directory.path).toString()
    } catch (problem: DocumentError) { failure(problem.code, problem.message).toString() }
    catch (_: Exception) { failure("storage_error", "Private PDF job storage is unavailable").toString() }

    @JvmStatic
    fun execute(raw: String): String {
        if (Looper.myLooper() == Looper.getMainLooper())
            return failure("main_thread", "PDF and OCR operations require an engine worker thread").toString()
        var id: String? = null
        return try {
            if (raw.toByteArray(Charsets.UTF_8).size > MAX_REQUEST_BYTES)
                throw DocumentError("invalid_arguments", "PDF request exceeds the size limit")
            val request = JSONObject(raw)
            id = text(request, "request_id", 36)
            val job = checkedJob(id)
            if (!job.lock.tryLock()) throw DocumentError("job_busy", "This PDF job is already running")
            try {
                checkedJob(id)
                when (text(request, "action", 32)) {
                    "render_pdf" -> render(job, id, request)
                    "create_pdf" -> create(job, id, request)
                    else -> throw DocumentError("invalid_arguments", "Unsupported PDF action")
                }.toString()
            } finally { job.lock.unlock() }
        } catch (problem: DocumentError) { failure(problem.code, problem.message, id).toString() }
        catch (_: SecurityException) { failure("encrypted_pdf", "This PDF is encrypted or access is denied", id).toString() }
        catch (_: OutOfMemoryError) { failure("insufficient_memory", "PDF allocation failed; render fewer or smaller pages", id).toString() }
        catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
            failure("cancelled", "PDF operation was interrupted", id).toString()
        }
        catch (_: Exception) { failure("invalid_pdf", "PDF data or document request could not be processed", id).toString() }
    }

    @JvmStatic
    fun release(jobId: String): String = try {
        if (!JOB_ID.matches(jobId)) throw DocumentError("invalid_arguments", "Invalid PDF job identifier")
        val job = jobs[jobId]
        if (job == null) success(jobId).put("released", false).toString() else {
            if (!job.lock.tryLock()) throw DocumentError("job_busy", "Wait for the PDF worker before releasing its files")
            try {
                val root = checkedRoot()
                if (job.root.parentFile != root || job.root.name != jobId)
                    throw DocumentError("unsafe_path", "PDF job directory escaped private storage")
                // walkFileTree does not follow links, including a substituted job root.
                if (Files.exists(job.root.toPath(), LinkOption.NOFOLLOW_LINKS)) {
                    Files.walkFileTree(job.root.toPath(), object : SimpleFileVisitor<java.nio.file.Path>() {
                        override fun visitFile(file: java.nio.file.Path, attrs: BasicFileAttributes): java.nio.file.FileVisitResult {
                            Files.delete(file)
                            return java.nio.file.FileVisitResult.CONTINUE
                        }
                        override fun postVisitDirectory(dir: java.nio.file.Path, error: java.io.IOException?): java.nio.file.FileVisitResult {
                            if (error != null) throw error
                            Files.delete(dir)
                            return java.nio.file.FileVisitResult.CONTINUE
                        }
                    })
                }
                jobs.remove(jobId, job)
                success(jobId).put("released", true).toString()
            } finally { job.lock.unlock() }
        }
    } catch (problem: DocumentError) { failure(problem.code, problem.message).toString() }
    catch (_: Exception) { failure("storage_error", "Private PDF job files could not be released").toString() }

    private fun checkedRoot(): File {
        val root = tempRoot ?: throw DocumentError("unavailable", initializationError ?: "Initialize PDF tools first")
        if (Files.isSymbolicLink(root.toPath()) || root.canonicalFile != root || !root.isDirectory)
            throw DocumentError("unsafe_path", "Private PDF storage is unavailable")
        return root
    }

    private fun checkedJob(id: String): Job {
        if (!JOB_ID.matches(id)) throw DocumentError("invalid_arguments", "Invalid PDF job identifier")
        val job = jobs[id] ?: throw DocumentError("unknown_job", "The PDF job is missing or has been released")
        val root = checkedRoot()
        if (job.root.parentFile != root || job.root.name != id || Files.isSymbolicLink(job.root.toPath()) ||
            job.root.canonicalFile != job.root || !job.root.isDirectory)
            throw DocumentError("unsafe_path", "PDF job directory escaped private storage")
        return job
    }

    private fun checkedFile(job: Job, name: String): File {
        val file = File(job.root, name)
        if (Files.isSymbolicLink(file.toPath()) || file.canonicalFile != file || file.parentFile != job.root)
            throw DocumentError("unsafe_path", "PDF file path escaped its private job")
        return file
    }

    private fun readPdf(job: Job): ParcelFileDescriptor {
        val file = checkedFile(job, "input.pdf")
        if (!Files.exists(file.toPath(), LinkOption.NOFOLLOW_LINKS))
            throw DocumentError("missing_input", "Stage a PDF as the job's input.pdf")
        val before = Os.lstat(file.path)
        if (!OsConstants.S_ISREG(before.st_mode) || before.st_nlink != 1L)
            throw DocumentError("unsafe_path", "PDF input must be a private regular file without links")
        if (before.st_size < 1)
            throw DocumentError("invalid_pdf", "PDF input must not be empty")
        val descriptor = Os.open(file.path, OsConstants.O_RDONLY or OsConstants.O_NOFOLLOW or OsConstants.O_CLOEXEC, 0)
        try {
            val stat = Os.fstat(descriptor)
            val after = Os.lstat(file.path)
            if (!OsConstants.S_ISREG(stat.st_mode) || !OsConstants.S_ISREG(after.st_mode) ||
                stat.st_nlink != 1L || after.st_nlink != 1L ||
                stat.st_dev != before.st_dev || stat.st_ino != before.st_ino ||
                stat.st_dev != after.st_dev || stat.st_ino != after.st_ino ||
                stat.st_size != before.st_size || stat.st_size != after.st_size || stat.st_size < 1)
                throw DocumentError("unsafe_path", "PDF input changed during opening or is linked outside its private job")
            checkedFile(job, "input.pdf")
            return ParcelFileDescriptor.dup(descriptor)
        } finally { Os.close(descriptor) }
    }

    private fun render(job: Job, id: String, request: JSONObject): JSONObject {
        fields(request, setOf("pages", "start_page", "max_pages", "max_dimension", "ocr"))
        if (request.has("pages") && (request.has("start_page") || request.has("max_pages")))
            throw DocumentError("invalid_arguments", "Use explicit pages or a start_page range")
        val dimension = integer(request, "max_dimension", 1600, 128, MAX_DIMENSION)
        val ocr = if (!request.has("ocr")) false else request.get("ocr").let {
            if (it !is Boolean) throw DocumentError("invalid_arguments", "ocr must be a boolean")
            it
        }
        val outputs = JSONArray()
        val descriptor = readPdf(job)
        try {
            PdfRenderer(descriptor).use { renderer ->
                val total = renderer.pageCount
                if (total < 1) throw DocumentError("invalid_pdf", "PDF has no renderable pages")
                val explicit = request.has("pages")
                val pages = if (explicit) {
                    val values = request.optJSONArray("pages")
                        ?: throw DocumentError("invalid_arguments", "pages must be a list of page numbers")
                    if (values.length() !in 1..MAX_RENDER_PAGES)
                        throw DocumentError("invalid_arguments", "Render from one to eight pages per call")
                    (0 until values.length()).map { index ->
                        val value = values.get(index)
                        if (value !is Int && value !is Long)
                            throw DocumentError("invalid_page", "PDF page numbers must be integers")
                        val page = (value as Number).toLong()
                        if (page !in 1..total.toLong()) throw DocumentError("invalid_page", "PDF page number is out of range")
                        page.toInt()
                    }.also { if (it.distinct().size != it.size) throw DocumentError("invalid_page", "Page numbers must be unique") }
                } else {
                    val start = integer(request, "start_page", 1, 1, total, "invalid_page")
                    val count = integer(request, "max_pages", MAX_RENDER_PAGES, 1, MAX_RENDER_PAGES)
                    (start..min(total, start + count - 1)).toList()
                }
                val pageFiles = pages.associateWith { number ->
                    checkedFile(job, "page-$number.png").also { file ->
                        if (Files.exists(file.toPath(), LinkOption.NOFOLLOW_LINKS))
                            throw DocumentError("output_exists", "Use a new PDF job to render a page again")
                    }
                }
                pages.forEach { number ->
                    interrupted()
                    renderer.openPage(number - 1).use { page ->
                        if (page.width <= 0 || page.height <= 0)
                            throw DocumentError("invalid_pdf", "PDF page dimensions are invalid")
                        val scale = dimension.toDouble() / max(page.width, page.height)
                        val width = max(1, min(dimension, ceil(page.width * scale).toInt()))
                        val height = max(1, min(dimension, ceil(page.height * scale).toInt()))
                        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
                        var recycle = true
                        try {
                            bitmap.eraseColor(Color.WHITE)
                            page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                            val file = pageFiles.getValue(number)
                            exclusiveOutput(file, MAX_IMAGE_BYTES).use {
                                if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, it))
                                    throw DocumentError("render_failed", "PDF page could not be encoded")
                            }
                            val output = JSONObject().put("path", file.path).put("page", number)
                                .put("width", width).put("height", height).put("bytes", file.length())
                                .put("media_type", "image/png")
                            if (ocr) {
                                val recognizer = TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build())
                                var pendingTask: Task<Text>? = null
                                try {
                                    val task = recognizer.process(InputImage.fromBitmap(bitmap, 0))
                                    pendingTask = task
                                    val text = Tasks.await(task, 30, TimeUnit.SECONDS).text
                                    output.put("ocr_text", text).put("ocr_engine", "mlkit_bundled_chinese")
                                } catch (_: TimeoutException) {
                                    throw DocumentError("ocr_timeout", "Offline Chinese OCR timed out on this page")
                                } finally {
                                    val task = pendingTask
                                    if (task == null || task.isComplete) recognizer.close() else {
                                        // ML Kit may still use the bitmap after await timed out or was interrupted.
                                        recycle = false
                                        task.addOnCompleteListener(Executor { it.run() }) {
                                            recognizer.close()
                                            bitmap.recycle()
                                        }
                                    }
                                }
                            } else output.put("ocr_text", JSONObject.NULL)
                            outputs.put(output)
                        } finally { if (recycle) bitmap.recycle() }
                    }
                }
                val next = if (!explicit && pages.last() < total) pages.last() + 1 else null
                return success(id).put("total_pages", total).put("next_page", next ?: JSONObject.NULL)
                    .put("outputs", outputs).put("ocr", ocr)
            }
        } finally { descriptor.close() }
    }

    private fun create(job: Job, id: String, request: JSONObject): JSONObject {
        fields(request, setOf("title", "content", "page_size", "font_size"))
        val content = text(request, "content", MAX_TEXT_CHARS)
        val title = if (request.has("title")) text(request, "title", 1024, allowEmpty = true) else ""
        val paper = if (request.has("page_size")) text(request, "page_size", 16) else "A4"
        if (paper != "A4") throw DocumentError("invalid_arguments", "PDF generation supports A4 pages")
        val font = integer(request, "font_size", 12, 8, 28)
        val text = (if (title.isEmpty()) "" else "$title\n\n") + content.replace("\r\n", "\n").replace('\r', '\n')
        val paint = TextPaint(Paint.ANTI_ALIAS_FLAG or Paint.SUBPIXEL_TEXT_FLAG).apply {
            color = Color.BLACK
            textSize = font.toFloat()
            typeface = pdfFont.first
        }
        val layout = StaticLayout.Builder.obtain(text, 0, text.length, paint, 523)
            .setAlignment(Layout.Alignment.ALIGN_NORMAL).setIncludePad(true)
            .setLineSpacing(2f, 1.15f).setBreakStrategy(Layout.BREAK_STRATEGY_HIGH_QUALITY).build()
        val ranges = mutableListOf<Pair<Int, Int>>()
        var line = 0
        while (line < layout.lineCount) {
            val first = line
            val top = layout.getLineTop(first)
            while (line < layout.lineCount && layout.getLineBottom(line) - top <= 770) line++
            if (line == first) throw DocumentError("layout_error", "PDF line is taller than the printable area")
            ranges.add(first to line)
            if (ranges.size > MAX_OUTPUT_PAGES) throw DocumentError("page_limit", "PDF content exceeds 200 pages")
        }
        val output = checkedFile(job, "output.pdf")
        if (Files.exists(output.toPath(), LinkOption.NOFOLLOW_LINKS))
            throw DocumentError("output_exists", "Use a new PDF job for another generated document")
        val pending = checkedFile(job, "output.pending")
        val document = PdfDocument()
        try {
            ranges.forEachIndexed { index, range ->
                interrupted()
                val page = document.startPage(PdfDocument.PageInfo.Builder(595, 842, index + 1).create())
                val canvas = page.canvas
                try {
                    canvas.drawColor(Color.WHITE)
                    canvas.save()
                    canvas.translate(36f, 36f)
                    val top = layout.getLineTop(range.first)
                    val bottom = layout.getLineBottom(range.second - 1)
                    canvas.clipRect(0f, 0f, 523f, (bottom - top).toFloat())
                    canvas.translate(0f, -top.toFloat())
                    layout.draw(canvas)
                    canvas.restore()
                } finally { document.finishPage(page) }
            }
            exclusiveOutput(pending).use(document::writeTo)
            interrupted()
            checkedFile(job, "output.pdf")
            Files.move(pending.toPath(), output.toPath(), StandardCopyOption.ATOMIC_MOVE)
            return success(id).put("total_pages", ranges.size).put("page_size", "A4")
                .put("outputs", JSONArray().put(JSONObject().put("path", output.path)
                    .put("media_type", "application/pdf").put("bytes", output.length())))
                .put("font", pdfFont.second).put("unicode_layout", true)
        } finally {
            document.close()
            Files.deleteIfExists(pending.toPath())
        }
    }

    /**
     * The PDF writer embeds the fonts it draws with. Vendor system fonts (ZTE's HYZhengYuan, for one) may
     * forbid subsetting, so a four-page Chinese PDF carried the whole 15 MB font. AOSP's Noto Sans CJK
     * allows subsetting; its Simplified Chinese face comes first and the system font covers the rest.
     */
    private val pdfFont: Pair<Typeface, String> by lazy {
        val system = Typeface.create("sans-serif", Typeface.NORMAL) to "system_sans_serif_with_fallback"
        val noto = File("/system/fonts/NotoSansCJK-Regular.ttc")
        if (android.os.Build.VERSION.SDK_INT < 29 || !noto.isFile) return@lazy system
        runCatching {
            // Face 2 of the collection is Simplified Chinese (as in AOSP's fonts.xml).
            val family = android.graphics.fonts.FontFamily.Builder(
                android.graphics.fonts.Font.Builder(noto).setTtcIndex(2).build()).build()
            Typeface.CustomFallbackBuilder(family).setSystemFallback("sans-serif").build() to
                "noto_sans_cjk_sc_with_system_fallback"
        }.getOrDefault(system)
    }

    private fun exclusiveOutput(file: File, limit: Long? = null): OutputStream {
        val descriptor = Os.open(file.path, OsConstants.O_WRONLY or OsConstants.O_CREAT or OsConstants.O_EXCL or
            OsConstants.O_NOFOLLOW or OsConstants.O_CLOEXEC, 384)
        return object : FilterOutputStream(FileOutputStream(descriptor)) {
            private var count = 0L
            override fun write(value: Int) {
                if (limit != null && count + 1 > limit)
                    throw DocumentError("output_limit", "PDF page image exceeds its size limit")
                out.write(value)
                count++
            }
            override fun write(buffer: ByteArray, offset: Int, length: Int) {
                if (limit != null && count + length > limit)
                    throw DocumentError("output_limit", "PDF page image exceeds its size limit")
                out.write(buffer, offset, length)
                count += length
            }
        }
    }

    private fun fields(request: JSONObject, allowed: Set<String>) {
        if (request.keys().asSequence().any { it != "action" && it != "request_id" && it !in allowed })
            throw DocumentError("invalid_arguments", "Unexpected PDF request field or path override")
    }

    private fun text(request: JSONObject, key: String, limit: Int, allowEmpty: Boolean = false): String {
        val value = request.opt(key)
        if (value !is String || (!allowEmpty && value.isEmpty()) || '\u0000' in value || value.codePointCount(0, value.length) > limit)
            throw DocumentError("invalid_arguments", "$key must be bounded Unicode text")
        return value
    }

    private fun integer(request: JSONObject, key: String, default: Int, minimum: Int, maximum: Int,
        code: String = "invalid_arguments"): Int {
        if (!request.has(key)) return default
        val value = request.get(key)
        if (value !is Int && value !is Long) throw DocumentError(code, "$key must be an integer")
        val number = (value as Number).toLong()
        if (number !in minimum.toLong()..maximum.toLong()) throw DocumentError(code, "$key is outside its allowed range")
        return number.toInt()
    }

    private fun interrupted() {
        if (Thread.currentThread().isInterrupted) throw InterruptedException("PDF worker interrupted")
    }
    private fun success(id: String) = JSONObject().put("ok", true).put("request_id", id)
    private fun failure(code: String, message: String?, id: String? = null) = JSONObject().put("ok", false)
        .put("request_id", id ?: JSONObject.NULL).put("error", JSONObject().put("code", code).put("message", message))
}
