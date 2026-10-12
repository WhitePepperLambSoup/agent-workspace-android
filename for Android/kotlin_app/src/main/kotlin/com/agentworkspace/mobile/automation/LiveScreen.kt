package com.agentworkspace.mobile.automation

import android.content.Context
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import android.util.DisplayMetrics
import android.view.Display
import kotlin.math.max
import kotlin.math.roundToInt

/**
 * The screen as it is right now, for the agent's screenshots: with the user's screen capture
 * consent (LiveScreenService) the display is mirrored at a reduced size and the newest frame is
 * always kept. A screenshot is then a copy of that frame: it does not wait for Android's
 * accessibility screenshot (rate limited, Android 11+), is not refused because something on the
 * screen moved, and still exists when the screen is static and no new frame arrives.
 * Lives in the :engine process, next to AgentAccessibilityService.
 */
internal object LiveScreen {
    /** Longest side of the mirrored frames; models scale screenshots down further anyway. */
    private const val MAX_EDGE = 1600

    data class Frame(val bitmap: Bitmap, val screenWidth: Int, val screenHeight: Int, val ageMs: Long)

    private val lock = Any()
    private var projection: MediaProjection? = null
    private var display: VirtualDisplay? = null
    private var reader: ImageReader? = null
    private var latest: Image? = null
    private var latestAt = 0L
    private var thread: HandlerThread? = null
    private var screen = Pair(0, 0)
    private var displayListener: DisplayManager.DisplayListener? = null
    private var displayManager: DisplayManager? = null
    private var stopped: (() -> Unit)? = null
    @Volatile var lastUse = 0L
        private set

    val active: Boolean get() = synchronized(lock) { display != null }

    fun start(context: Context, granted: MediaProjection, onStopped: () -> Unit) {
        stop()
        val worker = HandlerThread("agent-live-screen").apply { start() }
        val frames = Handler(worker.looper)
        synchronized(lock) {
            thread = worker
            projection = granted
            stopped = onStopped
            lastUse = SystemClock.elapsedRealtime()
        }
        // Required before createVirtualDisplay on Android 14; Android may also end the capture itself.
        granted.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() { stop() }
        }, frames)
        val displays = context.getSystemService(DisplayManager::class.java)
        val (width, height, density) = size(displays)
        val first = reader(width, height, frames)
        // Before mirroring starts: a static screen sends a single frame, which must not be dropped.
        synchronized(lock) { reader = first; displayManager = displays }
        val mirror = granted.createVirtualDisplay("agent-live-screen", width, height, density,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, first.surface, null, frames)
            ?: throw IllegalStateException("Android did not mirror the screen")
        // Turning the phone resizes the mirror, so frames keep the screen's shape.
        val listener = object : DisplayManager.DisplayListener {
            override fun onDisplayAdded(displayId: Int) {}
            override fun onDisplayRemoved(displayId: Int) {}
            override fun onDisplayChanged(displayId: Int) {
                if (displayId != Display.DEFAULT_DISPLAY) return
                val (w, h, dpi) = size(displays)
                synchronized(lock) {
                    val current = display ?: return
                    val old = reader ?: return
                    if (old.width == w && old.height == h) return
                    val next = reader(w, h, frames)
                    current.resize(w, h, dpi)
                    current.surface = next.surface
                    latest?.close(); latest = null
                    old.close()
                    reader = next
                }
            }
        }
        displays.registerDisplayListener(listener, frames)
        synchronized(lock) {
            display = mirror
            displayListener = listener
        }
    }

    /** A copy of the newest frame, or null when the live screen is off or no frame arrived yet. */
    fun frame(): Frame? = synchronized(lock) {
        val image = latest ?: return null
        lastUse = SystemClock.elapsedRealtime()
        Frame(image.toBitmap(), screen.first, screen.second, SystemClock.elapsedRealtime() - latestAt)
    }

    fun stop() {
        val ended: (() -> Unit)?
        val owned: Pair<HandlerThread?, MediaProjection?>
        synchronized(lock) {
            if (projection == null && display == null) return
            displayListener?.let { listener -> runCatching { displayManager?.unregisterDisplayListener(listener) } }
            displayListener = null; displayManager = null
            display?.release(); display = null
            latest?.close(); latest = null
            reader?.close(); reader = null
            ended = stopped; stopped = null
            owned = thread to projection
            thread = null; projection = null
        }
        runCatching { owned.second?.stop() }
        owned.first?.quitSafely()
        ended?.invoke()
    }

    fun idleMs(): Long = SystemClock.elapsedRealtime() - lastUse

    private fun size(displays: DisplayManager): Triple<Int, Int, Int> {
        val metrics = DisplayMetrics()
        @Suppress("DEPRECATION")
        displays.getDisplay(Display.DEFAULT_DISPLAY).getRealMetrics(metrics)
        synchronized(lock) { screen = metrics.widthPixels to metrics.heightPixels }
        val scale = minOf(1.0, MAX_EDGE.toDouble() / max(metrics.widthPixels, metrics.heightPixels))
        return Triple((metrics.widthPixels * scale).roundToInt().coerceAtLeast(1),
            (metrics.heightPixels * scale).roundToInt().coerceAtLeast(1), metrics.densityDpi)
    }

    private fun reader(width: Int, height: Int, frames: Handler): ImageReader =
        ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 3).apply {
            setOnImageAvailableListener({ source ->
                val image = runCatching { source.acquireLatestImage() }.getOrNull() ?: return@setOnImageAvailableListener
                synchronized(lock) {
                    if (source !== reader) { image.close(); return@synchronized }
                    // Keeping only the newest frame leaves the other buffers free for the next ones.
                    latest?.close()
                    latest = image
                    latestAt = SystemClock.elapsedRealtime()
                }
            }, frames)
        }

    private fun Image.toBitmap(): Bitmap {
        val plane = planes[0]
        val stride = plane.pixelStride
        // Rows can be wider than the image; copy the padded rows, then cut the padding off.
        val padded = Bitmap.createBitmap(plane.rowStride / stride, height, Bitmap.Config.ARGB_8888)
        plane.buffer.rewind()
        padded.copyPixelsFromBuffer(plane.buffer)
        if (padded.width == width) return padded
        return Bitmap.createBitmap(padded, 0, 0, width, height).also { padded.recycle() }
    }
}
