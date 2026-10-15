package android.print

import android.os.CancellationSignal
import android.os.ParcelFileDescriptor

/**
 * Writes a print adapter's document (a WebView's page) to a PDF file, without the system print
 * dialog. The SDK gives the layout and write callbacks no public constructor; classes in this
 * package can call it, and it is public at run time.
 */
object AgentPdfPrint {
    /** Main thread. [done] gets null on success or why it failed; [output] is closed either way. */
    fun write(adapter: PrintDocumentAdapter, attributes: PrintAttributes, output: ParcelFileDescriptor,
        cancel: CancellationSignal, done: (String?) -> Unit) {
        var finished = false
        fun finish(error: String?) {
            if (finished) return
            finished = true
            runCatching { output.close() }
            runCatching { adapter.onFinish() }
            done(error)
        }
        try {
            adapter.onStart()
            adapter.onLayout(null, attributes, cancel, object : PrintDocumentAdapter.LayoutResultCallback() {
                override fun onLayoutFinished(info: PrintDocumentInfo, changed: Boolean) {
                    try {
                        adapter.onWrite(arrayOf(PageRange.ALL_PAGES), output, cancel, object : PrintDocumentAdapter.WriteResultCallback() {
                            override fun onWriteFinished(pages: Array<out PageRange>) = finish(null)
                            override fun onWriteFailed(error: CharSequence?) = finish(error?.toString() ?: "the page could not be written")
                            override fun onWriteCancelled() = finish("cancelled")
                        })
                    } catch (error: Exception) { finish(error.message ?: "the page could not be written") }
                }
                override fun onLayoutFailed(error: CharSequence?) = finish(error?.toString() ?: "the page could not be laid out")
                override fun onLayoutCancelled() = finish("cancelled")
            }, null)
        } catch (error: Throwable) {
            // Should a phone's Android refuse the callbacks, the caller falls back to plain text.
            finish(error.message ?: error.javaClass.simpleName)
        }
    }
}
