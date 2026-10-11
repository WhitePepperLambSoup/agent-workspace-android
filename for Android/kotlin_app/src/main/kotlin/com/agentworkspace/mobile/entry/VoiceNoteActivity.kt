package com.agentworkspace.mobile.entry

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.media.MediaRecorder
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.FileProvider
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.sharing.ShareInboxController
import com.agentworkspace.mobile.voice.OfflineSpeech
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

/**
 * Voice note: records until the user taps Done, then hands the recording to a new conversation
 * that transcribes it on the phone, writes minutes and adds them to the knowledge base. The audio
 * goes through the attachment inbox like a circled screenshot and never leaves the phone.
 */
class VoiceNoteActivity : Activity() {
    private var recorder: MediaRecorder? = null
    private var output: File? = null
    private var startedAt = 0L
    private var handedOff = false
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var elapsed: TextView
    private lateinit var status: TextView
    private val tick = object : Runnable {
        override fun run() {
            if (recorder == null) return
            elapsed.text = clock(SystemClock.elapsedRealtime() - startedAt)
            handler.postDelayed(this, 500)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(layout())
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) start()
        else requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), REQUEST_MICROPHONE)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != REQUEST_MICROPHONE) return
        if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) start()
        else status.text = UiText.of(this, "需要麦克风权限才能录音。", "Recording needs microphone access.")
    }

    private fun start() {
        if (recorder != null) return
        val folder = File(cacheDir, "camera").apply { mkdirs() }
        val stamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
        val file = File(folder, UiText.of(this, "录音速记-$stamp.m4a", "voice-note-$stamp.m4a"))
        val media = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(this) else @Suppress("DEPRECATION") MediaRecorder()
        try {
            // 16 kHz mono speech: what the offline recognizer uses, about 15 MB an hour.
            media.setAudioSource(MediaRecorder.AudioSource.MIC)
            media.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            media.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            media.setAudioChannels(1)
            media.setAudioSamplingRate(16000)
            media.setAudioEncodingBitRate(32000)
            media.setMaxDuration(MAX_MILLIS)
            media.setOutputFile(file.absolutePath)
            media.setOnInfoListener { _, what, _ ->
                if (what == MediaRecorder.MEDIA_RECORDER_INFO_MAX_DURATION_REACHED) done()
            }
            media.prepare()
            media.start()
        } catch (error: Exception) {
            media.release()
            file.delete()
            status.text = UiText.of(this, "无法开始录音：", "Could not start recording: ") + (error.message ?: error.javaClass.simpleName)
            return
        }
        recorder = media
        output = file
        startedAt = SystemClock.elapsedRealtime()
        handler.post(tick)
        status.text = if (OfflineSpeech.status(this).optBoolean("available")) {
            UiText.of(this, "正在录音。说完点「完成」，会在手机上转写并整理成纪要。",
                "Recording. Tap Done when finished; it is transcribed on the phone and turned into minutes.")
        } else {
            UiText.of(this, "正在录音。转写需要离线语音模型：完成前可以先去「本地模型」下载 SenseVoice。",
                "Recording. Transcription needs the offline speech model: download SenseVoice in Local models.")
        }
    }

    /** Stops the recorder; false when nothing usable was recorded. */
    private fun stopRecorder(): Boolean {
        val media = recorder ?: return false
        recorder = null
        handler.removeCallbacks(tick)
        return try {
            media.stop()
            true
        } catch (_: RuntimeException) {
            false // stopped before any audio arrived
        } finally {
            media.release()
        }
    }

    private fun done() {
        if (handedOff) return
        val duration = SystemClock.elapsedRealtime() - startedAt
        val file = output
        if (!stopRecorder() || file == null || !file.isFile || duration < MIN_MILLIS) {
            file?.delete()
            Toast.makeText(this, UiText.of(this, "录音太短，没有保存", "Too short; nothing was saved"), Toast.LENGTH_SHORT).show()
            finish()
            return
        }
        handedOff = true
        val batch = UUID.randomUUID().toString()
        ShareInboxController.get(this).captureFiles(listOf(FileProvider.getUriForFile(this, "$packageName.camera", file)), batch)
        startActivity(QuickEntry.voiceNoteIntent(this, batch))
        finish()
    }

    private fun cancel() {
        handedOff = true
        stopRecorder()
        output?.delete()
        finish()
    }

    override fun onStop() {
        super.onStop()
        // The microphone stops for apps in the background: leaving keeps what was recorded.
        if (recorder != null && !isChangingConfigurations) done()
    }

    override fun onDestroy() {
        if (!handedOff) {
            stopRecorder()
            output?.delete()
        }
        super.onDestroy()
    }

    private fun layout(): View {
        val dark = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        val text = if (dark) Color.WHITE else 0xFF18201E.toInt()
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(24), dp(22), dp(24), dp(18))
            background = GradientDrawable().apply {
                cornerRadius = dp(24).toFloat()
                setColor(if (dark) 0xFF1F2725.toInt() else Color.WHITE)
                setStroke(1, if (dark) 0x33FFFFFF else 0x22000000)
            }
            elevation = dp(8).toFloat()
        }
        card.addView(TextView(this).apply {
            this.text = UiText.of(this@VoiceNoteActivity, "录音速记", "Voice note")
            textSize = 18f
            setTextColor(text)
            paint.isFakeBoldText = true
        })
        elapsed = TextView(this).apply {
            this.text = clock(0)
            textSize = 40f
            setTextColor(0xFFDC2626.toInt())
            setPadding(0, dp(14), 0, dp(8))
        }
        card.addView(elapsed)
        status = TextView(this).apply {
            textSize = 14f
            setTextColor(if (dark) 0xCCFFFFFF.toInt() else 0xFF4B5653.toInt())
            gravity = Gravity.CENTER
            setPadding(0, 0, 0, dp(18))
        }
        card.addView(status, LinearLayout.LayoutParams(dp(280), ViewGroup.LayoutParams.WRAP_CONTENT))
        val buttons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        buttons.addView(button(UiText.of(this, "取消", "Cancel"), primary = false, dark = dark) { cancel() })
        buttons.addView(View(this), LinearLayout.LayoutParams(dp(12), 1))
        buttons.addView(button(UiText.of(this, "完成", "Done"), primary = true, dark = dark) { done() })
        card.addView(buttons)
        return FrameLayout(this).apply {
            setBackgroundColor(0x99000000.toInt())
            setOnClickListener { } // a tap beside the card must not end the recording
            addView(card, FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER))
        }
    }

    private fun button(label: String, primary: Boolean, dark: Boolean, action: () -> Unit) = TextView(this).apply {
        text = label
        textSize = 16f
        gravity = Gravity.CENTER
        setTextColor(if (primary) Color.WHITE else if (dark) Color.WHITE else 0xFF18201E.toInt())
        setPadding(dp(28), dp(12), dp(28), dp(12))
        background = GradientDrawable().apply {
            cornerRadius = dp(22).toFloat()
            setColor(if (primary) 0xFF0F766E.toInt() else if (dark) 0x33FFFFFF else 0x14000000)
        }
        setOnClickListener { action() }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun clock(millis: Long): String {
        val seconds = millis / 1000
        return "%02d:%02d".format(seconds / 60, seconds % 60)
    }

    companion object {
        private const val REQUEST_MICROPHONE = 41
        private const val MIN_MILLIS = 1_500L
        private const val MAX_MILLIS = 60 * 60 * 1000 // one hour
    }
}
