package com.agentworkspace.mobile.automation

import android.annotation.SuppressLint
import android.content.AttributionSource
import android.content.Context
import android.content.ContextWrapper
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import java.io.ByteArrayOutputStream
import java.util.concurrent.TimeUnit
import kotlin.system.exitProcess

/**
 * The background screen's service. Shizuku runs it with shell privileges in a process of its own
 * (a user service, see [BackgroundScreen]): it creates an off-screen display, keeps its newest
 * picture, and starts apps, presses keys and moves tasks on that display with the system's own
 * `am` and `input` commands. Nothing here reaches the phone's own screen, except [bringToFront]
 * when the user asks for the app.
 */
class BackgroundScreenService() : IBackgroundScreen.Stub() {
    private var base: Context? = null

    /** Shizuku passes a context when the class has this constructor. */
    constructor(context: Context) : this() { base = context }

    private val thread = HandlerThread("background-screen").apply { start() }
    private val lock = Any()
    private var display: VirtualDisplay? = null
    private var reader: ImageReader? = null
    private var newest: Image? = null
    private var width = 0
    private var height = 0

    /** The display's owner must be the shell, whose rights Shizuku lends. */
    private class ShellContext(base: Context) : ContextWrapper(base) {
        override fun getPackageName(): String = SHELL
        override fun getOpPackageName(): String = SHELL
        override fun getApplicationContext(): Context = this
        @SuppressLint("NewApi")
        override fun getAttributionSource(): AttributionSource =
            AttributionSource.Builder(SHELL_UID).setPackageName(SHELL).build()
    }

    override fun destroy() {
        close()
        exitProcess(0)
    }

    override fun open(width: Int, height: Int, densityDpi: Int): Int = synchronized(lock) {
        display?.let { return it.display.displayId }
        require(width in 200..4096 && height in 200..4096 && densityDpi in 80..800)
        val imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 3)
        // Frames are taken as they come; the newest is kept (a still screen sends none).
        imageReader.setOnImageAvailableListener({ source ->
            val image = runCatching { source.acquireLatestImage() }.getOrNull() ?: return@setOnImageAvailableListener
            synchronized(lock) {
                newest?.close()
                newest = image
            }
        }, Handler(thread.looper))
        val manager = displayManager()
        var created: VirtualDisplay? = null
        for (flags in flagSets()) {
            created = runCatching {
                manager.createVirtualDisplay("Agent Workspace", width, height, densityDpi, imageReader.surface, flags)
            }.getOrNull()
            if (created != null) break
        }
        if (created == null) {
            imageReader.close()
            return -1
        }
        display = created
        reader = imageReader
        this.width = width
        this.height = height
        created.display.displayId
    }

    override fun close() {
        synchronized(lock) {
            runCatching { display?.release() }
            runCatching { newest?.close() }
            runCatching { reader?.close() }
            display = null
            newest = null
            reader = null
        }
    }

    override fun picture(maxEdge: Int, quality: Int): ByteArray? {
        val bitmap = synchronized(lock) {
            val image = newest ?: return null
            val plane = image.planes[0]
            val buffer = plane.buffer.also { it.rewind() }
            val padded = plane.rowStride / plane.pixelStride
            val full = Bitmap.createBitmap(padded, height, Bitmap.Config.ARGB_8888)
            full.copyPixelsFromBuffer(buffer)
            if (padded == width) full else Bitmap.createBitmap(full, 0, 0, width, height).also { full.recycle() }
        }
        val scale = minOf(1f, maxEdge.coerceIn(200, 4096).toFloat() / maxOf(width, height))
        val sized = if (scale < 1f) {
            Bitmap.createScaledBitmap(bitmap, (width * scale).toInt(), (height * scale).toInt(), true).also { bitmap.recycle() }
        } else bitmap
        return ByteArrayOutputStream().use { out ->
            sized.compress(Bitmap.CompressFormat.JPEG, quality.coerceIn(30, 95), out)
            sized.recycle()
            out.toByteArray()
        }
    }

    override fun start(intentUri: String?): String {
        val id = currentId() ?: return "no background screen"
        if (intentUri == null || !intentUri.startsWith("intent:") || intentUri.length > 4000 || '\u0000' in intentUri) {
            return "invalid intent"
        }
        // One argument, never through a shell: nothing in it is run as a command.
        val output = run(listOf("am", "start", "--display", id.toString(), intentUri))
        return if (output.lines().any { it.startsWith("Error") || it.contains("Exception") }) output.take(500) else ""
    }

    override fun key(keyCode: Int): String {
        val id = currentId() ?: return "no background screen"
        if (keyCode !in 1..400) return "invalid key"
        return run(listOf("input", "-d", id.toString(), "keyevent", keyCode.toString())).take(500)
    }

    override fun bringToFront(): String {
        val id = currentId() ?: return "no background screen"
        // `am stack list` names each root task and its display; the first on ours is its top task.
        val task = run(listOf("am", "stack", "list")).lines().firstNotNullOfOrNull { line ->
            val match = TASK_LINE.find(line) ?: return@firstNotNullOfOrNull null
            match.groupValues[1].takeIf { match.groupValues[2] == id.toString() }
        } ?: return "nothing is open on the background screen"
        val output = run(listOf("am", "display", "move-stack", task, "0"))
        return if (output.contains("Error") || output.contains("Exception")) output.take(500) else ""
    }

    private fun currentId(): Int? = synchronized(lock) { display?.display?.displayId }

    private fun run(command: List<String>): String = try {
        val process = ProcessBuilder(command).redirectErrorStream(true).start()
        val text = process.inputStream.bufferedReader().readText()
        if (!process.waitFor(15, TimeUnit.SECONDS)) process.destroy()
        text.trim()
    } catch (error: Exception) {
        "Error: $error"
    }

    @SuppressLint("PrivateApi", "DiscouragedPrivateApi")
    private fun displayManager(): DisplayManager {
        val context = ShellContext(base ?: systemContext())
        val constructor = DisplayManager::class.java.getDeclaredConstructor(Context::class.java)
        constructor.isAccessible = true
        return constructor.newInstance(context)
    }

    @SuppressLint("PrivateApi", "DiscouragedPrivateApi")
    private fun systemContext(): Context {
        val threadClass = Class.forName("android.app.ActivityThread")
        val current = threadClass.getDeclaredMethod("currentActivityThread").invoke(null)
            ?: threadClass.getDeclaredConstructor().also { it.isAccessible = true }.newInstance().also { created ->
                threadClass.getDeclaredField("sCurrentActivityThread").also { it.isAccessible = true }.set(null, created)
            }
        val getSystemContext = threadClass.getDeclaredMethod("getSystemContext").also { it.isAccessible = true }
        return getSystemContext.invoke(current) as Context
    }

    companion object {
        private const val SHELL = "com.android.shell"
        private const val SHELL_UID = 2000
        // "RootTask id=291 ... displayId=7" (Android 12+) or "Stack id=12 ... displayId=7".
        private val TASK_LINE = Regex("""(?:RootTask|Stack) id=(\d+).*?displayId=(\d+)""")

        // PUBLIC | PRESENTATION | OWN_CONTENT_ONLY | SUPPORTS_TOUCH | ROTATES_WITH_CONTENT |
        // DESTROY_CONTENT_ON_REMOVAL; newer Android versions also let the shell make it trusted, give
        // it its own focus and keep it from taking the phone screen's top focus. Tried richest first.
        private fun flagSets(): List<Int> {
            val base = 1 or 2 or 8 or 64 or 128 or 256
            val trusted = base or (1 shl 10)
            val grouped = trusted or (1 shl 11) or (1 shl 12) or (1 shl 13)
            val focused = grouped or (1 shl 14) or (1 shl 15)
            return when {
                Build.VERSION.SDK_INT >= 34 -> listOf(focused or (1 shl 16), focused, grouped, trusted, base)
                Build.VERSION.SDK_INT >= 33 -> listOf(grouped, trusted, base)
                else -> listOf(trusted, base)
            }
        }
    }
}
