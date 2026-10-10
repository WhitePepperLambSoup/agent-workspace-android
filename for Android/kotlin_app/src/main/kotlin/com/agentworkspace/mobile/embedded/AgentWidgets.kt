package com.agentworkspace.mobile.embedded

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.text.format.DateFormat
import android.view.View
import android.widget.RemoteViews
import com.agentworkspace.mobile.R
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.entry.QuickEntry
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** What the task widget shows: the task that needs the user, else a running one, else the latest. */
data class WidgetTaskSummary(val featured: TaskNotificationSnapshot?, val active: Int, val waiting: Int) {
    companion object {
        fun of(tasks: List<TaskNotificationSnapshot>): WidgetTaskSummary {
            fun recency(task: TaskNotificationSnapshot) = task.updatedAtMillis ?: task.createdAtMillis ?: 0L
            val waiting = tasks.filter { it.state == "waiting_approval" }
            val active = tasks.filter { it.state == "running" || it.state == "queued" }
            val featured = waiting.maxByOrNull(::recency) ?: active.maxByOrNull(::recency) ?: tasks.maxByOrNull(::recency)
            return WidgetTaskSummary(featured, active.size, waiting.size)
        }
    }
}

/** A quick task as the composer stores it; the widget opens a new conversation with its prompt. */
data class WidgetQuickTask(val title: String, val detail: String, val prompt: String)

/**
 * Home screen widgets: quick ask (a search-bar-like entry), task status, and the composer's quick tasks.
 *
 * Launchers redraw widgets while the app is not running, so each widget renders from a small file:
 * the engine service writes the task summary when what it shows changes, and the page writes the
 * quick tasks whenever the user edits them. Nothing polls on the widgets' behalf.
 */
object AgentWidgets {
    private const val TASKS_FILE = "widget-tasks.json"
    private const val QUICK_TASKS_FILE = "widget-quick-tasks.json"
    private const val STYLE_FILE = "widget-style.json"
    private const val MAX_QUICK_TASKS = 4
    private val engineAlive = setOf("starting", "ready", "running", "waiting_approval", "recovering")

    // ----- Task summary, written by the engine service -----

    /** Called on every task poll; the task widgets redraw only when what they show changed. */
    fun publishTasks(context: Context, tasks: List<TaskNotificationSnapshot>) {
        val next = summaryJson(WidgetTaskSummary.of(tasks))
        val file = CrossProcessJsonFile(File(context.filesDir, TASKS_FILE))
        val current = runCatching { file.read().optJSONObject("summary") }.getOrNull()
        if (current?.toString() == next.toString()) return
        runCatching { file.update { JSONObject().put("summary", next) } }
        refresh(context, AgentTaskWidgetProvider::class.java)
    }

    /** The engine started, stopped or failed: task widgets show it (and stop claiming a task runs). */
    fun engineStateChanged(context: Context) = refresh(context, AgentTaskWidgetProvider::class.java)

    private fun summaryJson(summary: WidgetTaskSummary): JSONObject {
        val value = JSONObject().put("active", summary.active).put("waiting", summary.waiting)
        summary.featured?.let { task ->
            value.put("task", JSONObject()
                .put("task_id", task.taskId).put("session_id", task.sessionId).put("state", task.state)
                .put("preview", task.preview)
                .put("at_ms", task.updatedAtMillis ?: task.createdAtMillis ?: 0L))
        }
        return value
    }

    private fun readSummary(context: Context): JSONObject =
        runCatching { CrossProcessJsonFile(File(context.filesDir, TASKS_FILE)).read().optJSONObject("summary") }
            .getOrNull() ?: JSONObject()

    // ----- Quick tasks, written by the page -----

    /** The page reports its quick tasks (JSON array of {title, detail, prompt}); the first four are shown. */
    fun saveQuickTasks(context: Context, json: String): Boolean {
        val parsed = runCatching { JSONArray(json) }.getOrNull() ?: return false
        val tasks = JSONArray()
        for (index in 0 until parsed.length()) {
            val item = parsed.optJSONObject(index) ?: continue
            val title = item.optString("title").trim().take(20)
            val prompt = item.optString("prompt").take(4000)
            if (title.isEmpty() || prompt.isBlank()) continue
            tasks.put(JSONObject().put("title", title).put("detail", item.optString("detail").trim().take(40))
                .put("prompt", prompt))
            if (tasks.length() == MAX_QUICK_TASKS) break
        }
        val file = CrossProcessJsonFile(File(context.filesDir, QUICK_TASKS_FILE))
        if (runCatching { file.read().optJSONArray("tasks")?.toString() }.getOrNull() == tasks.toString()) return true
        runCatching { file.update { JSONObject().put("tasks", tasks) } }.onFailure { return false }
        refresh(context, AgentQuickTasksWidgetProvider::class.java)
        return true
    }

    private fun quickTasks(context: Context): List<WidgetQuickTask> {
        val stored = runCatching { CrossProcessJsonFile(File(context.filesDir, QUICK_TASKS_FILE)).read().optJSONArray("tasks") }
            .getOrNull() ?: return defaultQuickTasks(context)
        return (0 until stored.length()).mapNotNull { stored.optJSONObject(it) }.map {
            WidgetQuickTask(it.optString("title"), it.optString("detail"), it.optString("prompt"))
        }
    }

    /** Until the app has run once, the composer's default quick tasks. */
    private fun defaultQuickTasks(context: Context): List<WidgetQuickTask> = listOf(
        WidgetQuickTask(UiText.of(context, "总结要点", "Summarize"), UiText.of(context, "文档、网页或聊天记录", "Docs, pages or chats"),
            UiText.of(context, "总结下面内容的要点，并列出需要我跟进的事项：\n", "Summarize the key points below and list anything I need to follow up on:\n")),
        WidgetQuickTask(UiText.of(context, "翻译润色", "Translate"), UiText.of(context, "中英互译，语气自然", "Chinese ↔ English, natural tone"),
            UiText.of(context, "把下面的内容翻译成英文，语气自然：\n", "Translate the following between Chinese and English, keeping the tone natural:\n")),
        WidgetQuickTask(UiText.of(context, "做个网页", "Make a web page"), UiText.of(context, "生成可直接预览的页面", "A page you can preview"),
            UiText.of(context, "做一个单页网页（HTML），主题是：", "Make a single-page website (HTML) about: ")),
        WidgetQuickTask(UiText.of(context, "分析数据", "Analyze data"), UiText.of(context, "表格或 CSV 出结论与图表", "Findings and a chart from a sheet or CSV"),
            UiText.of(context, "分析附件里的数据，给出关键结论并画一张图表：", "Analyze the data in the attachment, give the key findings and draw a chart: ")),
    )

    // ----- Style, written by the page -----

    /** The app's style ("glass" or "solid"); widgets follow it. Redraws only when it changes. */
    fun setStyle(context: Context, style: String) {
        val next = if (style == "glass") "glass" else "solid"
        val file = CrossProcessJsonFile(File(context.filesDir, STYLE_FILE))
        if (runCatching { file.read().optString("style", "solid") }.getOrNull() == next) return
        runCatching { file.update { JSONObject().put("style", next) } }.onFailure { return }
        refreshAll(context)
    }

    private fun glass(context: Context): Boolean =
        runCatching { CrossProcessJsonFile(File(context.filesDir, STYLE_FILE)).read().optString("style") == "glass" }
            .getOrDefault(false)

    private fun background(view: RemoteViews, drawable: Int, vararg ids: Int) =
        ids.forEach { view.setInt(it, "setBackgroundResource", drawable) }

    // ----- Rendering -----

    fun refresh(context: Context, provider: Class<out AppWidgetProvider>) {
        runCatching {
            val manager = AppWidgetManager.getInstance(context) ?: return
            val ids = manager.getAppWidgetIds(ComponentName(context, provider))
            if (ids.isEmpty()) return
            ids.forEach { id -> manager.updateAppWidget(id, views(context, provider, id)) }
        }.onFailure { android.util.Log.w("AgentWidgets", "Widget refresh failed: ${it.javaClass.simpleName}") }
    }

    /** Every widget, for example after the app language changed. */
    fun refreshAll(context: Context) {
        refresh(context, AgentWidgetProvider::class.java)
        refresh(context, AgentTaskWidgetProvider::class.java)
        refresh(context, AgentQuickTasksWidgetProvider::class.java)
    }

    fun views(context: Context, provider: Class<out AppWidgetProvider>, id: Int): RemoteViews = when (provider) {
        AgentTaskWidgetProvider::class.java -> taskViews(context, id)
        AgentQuickTasksWidgetProvider::class.java -> quickTaskViews(context, id)
        else -> quickAskViews(context, id)
    }

    private fun activity(context: Context, id: Int, slot: Int, intent: Intent): PendingIntent =
        // One request code per widget and button: PendingIntents that differ only in extras would merge.
        PendingIntent.getActivity(context, id * 16 + slot, intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    private fun askButtons(context: Context, view: RemoteViews, id: Int, field: Int, label: Int, voice: Int, camera: Int) {
        view.setTextViewText(label, UiText.of(context, "问 Agent…", "Ask Agent…"))
        view.setOnClickPendingIntent(field, activity(context, id, 0, QuickEntry.intent(context, "text")))
        view.setOnClickPendingIntent(voice, activity(context, id, 1, QuickEntry.intent(context, "voice")))
        view.setOnClickPendingIntent(camera, activity(context, id, 2, QuickEntry.intent(context, "camera")))
        view.setContentDescription(field, UiText.of(context, "新对话", "New chat"))
        view.setContentDescription(voice, UiText.of(context, "语音提问", "Ask by voice"))
        view.setContentDescription(camera, UiText.of(context, "拍照提问", "Ask about a photo"))
    }

    private fun quickAskViews(context: Context, id: Int): RemoteViews =
        RemoteViews(context.packageName, R.layout.agent_widget).also {
            askButtons(context, it, id, R.id.widget_open, R.id.widget_hint, R.id.widget_voice, R.id.widget_camera)
            if (glass(context)) {
                background(it, R.drawable.widget_glass_pill, R.id.widget_open)
                background(it, R.drawable.widget_glass_round, R.id.widget_voice, R.id.widget_camera)
            }
        }

    private fun taskViews(context: Context, id: Int): RemoteViews {
        val view = RemoteViews(context.packageName, R.layout.agent_task_widget)
        askButtons(context, view, id, R.id.task_new, R.id.task_new_label, R.id.task_voice, R.id.task_camera)
        if (glass(context)) {
            background(view, R.drawable.widget_glass_panel, android.R.id.background)
            background(view, R.drawable.widget_glass_inner, R.id.task_new, R.id.task_voice, R.id.task_camera)
        }
        val summary = readSummary(context)
        val engine = runCatching { JSONObject(EngineLifecycleState(context).statusJson()).optString("state") }.getOrDefault("")
        val alive = engine in engineAlive
        val waiting = summary.optInt("waiting")
        val active = summary.optInt("active")
        val (chip, chipView) = when {
            !alive -> UiText.of(context, "引擎未运行", "Engine stopped") to R.id.task_chip_muted
            waiting > 0 -> UiText.of(context, "待批准 $waiting", "$waiting to approve") to R.id.task_chip_warning
            active > 0 -> UiText.of(context, "执行中 $active", "$active running") to R.id.task_chip_accent
            else -> UiText.of(context, "就绪", "Ready") to R.id.task_chip_accent
        }
        showOne(view, chipView, chip, R.id.task_chip_accent, R.id.task_chip_warning, R.id.task_chip_muted)

        val task = summary.optJSONObject("task")
        if (task == null) {
            view.setTextViewText(R.id.task_title, UiText.of(context, "还没有任务", "No tasks yet"))
            showOne(view, R.id.task_meta, UiText.of(context, "点下面的输入框，开始第一个任务", "Tap the field below to start one"),
                R.id.task_meta, R.id.task_meta_warning, R.id.task_meta_danger)
            view.setOnClickPendingIntent(R.id.task_open, activity(context, id, 3, QuickEntry.intent(context, "text")))
            return view
        }
        val state = task.optString("state")
        // A stopped engine runs nothing; its unfinished tasks resume or end when the app opens again.
        val unfinished = state in setOf("queued", "running", "waiting_approval")
        val label = when {
            unfinished && !alive -> UiText.of(context, "已暂停，打开应用继续", "Paused, open the app to continue")
            state == "waiting_approval" -> UiText.of(context, "等待你批准", "Waiting for your approval")
            state == "running" -> UiText.of(context, "执行中", "Running")
            state == "queued" -> UiText.of(context, "排队中", "Queued")
            state == "succeeded" -> UiText.of(context, "已完成", "Done")
            state == "failed" -> UiText.of(context, "失败", "Failed")
            state == "cancelled" -> UiText.of(context, "已停止", "Stopped")
            else -> UiText.of(context, "已中断", "Interrupted")
        }
        val time = task.optLong("at_ms").takeIf { it > 0 }?.let { timeLabel(context, it) }
        view.setTextViewText(R.id.task_title, task.optString("preview").ifBlank { UiText.of(context, "（无标题任务）", "(Untitled task)") })
        val metaView = when {
            state == "waiting_approval" && alive -> R.id.task_meta_warning
            state == "failed" -> R.id.task_meta_danger
            else -> R.id.task_meta
        }
        showOne(view, metaView, listOfNotNull(label, time).joinToString(" · "),
            R.id.task_meta, R.id.task_meta_warning, R.id.task_meta_danger)
        val snapshot = TaskNotificationSnapshot(task.optString("task_id"), task.optString("session_id"), state, "", null, null, 0)
        view.setOnClickPendingIntent(R.id.task_open, PendingIntent.getActivity(context, id * 16 + 3,
            TaskNotificationPublisher.navigationIntent(context, snapshot),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
        return view
    }

    /**
     * Colours come from the layout, where the launcher resolves them for its light or dark mode; a
     * colour set from code is fixed in the app's configuration. So each colour is its own view.
     */
    private fun showOne(view: RemoteViews, shown: Int, text: CharSequence, vararg variants: Int) {
        variants.forEach { view.setViewVisibility(it, if (it == shown) View.VISIBLE else View.GONE) }
        view.setTextViewText(shown, text)
    }

    private fun timeLabel(context: Context, millis: Long): String {
        val zone = ZoneId.systemDefault()
        val moment = Instant.ofEpochMilli(millis).atZone(zone)
        val english = UiText.isEnglish(context)
        val clock = if (DateFormat.is24HourFormat(context)) "HH:mm" else if (english) "h:mm a" else "a h:mm"
        val pattern = when {
            moment.toLocalDate() == LocalDate.now(zone) -> clock
            english -> "MMM d, $clock"
            else -> "M月d日 $clock"
        }
        return moment.format(DateTimeFormatter.ofPattern(pattern, if (english) Locale.ENGLISH else Locale.CHINESE))
    }

    private val tileIds = listOf(
        Triple(R.id.quick_task_1, R.id.quick_task_1_title, R.id.quick_task_1_detail),
        Triple(R.id.quick_task_2, R.id.quick_task_2_title, R.id.quick_task_2_detail),
        Triple(R.id.quick_task_3, R.id.quick_task_3_title, R.id.quick_task_3_detail),
        Triple(R.id.quick_task_4, R.id.quick_task_4_title, R.id.quick_task_4_detail),
    )

    private fun quickTaskViews(context: Context, id: Int): RemoteViews {
        val view = RemoteViews(context.packageName, R.layout.agent_quick_tasks_widget)
        view.setTextViewText(R.id.quick_tasks_title, UiText.of(context, "常用任务", "Quick tasks"))
        view.setOnClickPendingIntent(R.id.quick_tasks_new, activity(context, id, 0, QuickEntry.intent(context, "text")))
        view.setContentDescription(R.id.quick_tasks_new, UiText.of(context, "新对话", "New chat"))
        if (glass(context)) {
            background(view, R.drawable.widget_glass_panel, android.R.id.background)
            background(view, R.drawable.widget_glass_inner, R.id.quick_tasks_new)
            background(view, R.drawable.widget_glass_tile, *tileIds.map { it.first }.toIntArray())
        }
        val tasks = quickTasks(context)
        tileIds.forEachIndexed { index, (tile, title, detail) ->
            val task = tasks.getOrNull(index)
            // Keep the grid's shape: a missing tile leaves its place empty.
            view.setViewVisibility(tile, if (task == null) View.INVISIBLE else View.VISIBLE)
            if (task == null) return@forEachIndexed
            view.setTextViewText(title, task.title)
            view.setTextViewText(detail, task.detail)
            view.setViewVisibility(detail, if (task.detail.isBlank()) View.GONE else View.VISIBLE)
            // The prompt is only filled in: the user finishes it and decides to send.
            val intent = QuickEntry.intent(context, "text").putExtra(Intent.EXTRA_TEXT, task.prompt)
            view.setOnClickPendingIntent(tile, activity(context, id, 4 + index, intent))
        }
        view.setViewVisibility(R.id.quick_tasks_row_2, if (tasks.size > 2) View.VISIBLE else View.GONE)
        return view
    }

    /** Asks the launcher to place a widget (Settings → Global entry). */
    fun requestPin(context: Context, kind: String): Boolean {
        val provider = when (kind) {
            "tasks" -> AgentTaskWidgetProvider::class.java
            "quick_tasks" -> AgentQuickTasksWidgetProvider::class.java
            "ask" -> AgentWidgetProvider::class.java
            else -> return false
        }
        val manager = AppWidgetManager.getInstance(context) ?: return false
        if (!manager.isRequestPinAppWidgetSupported) return false
        return runCatching { manager.requestPinAppWidget(ComponentName(context, provider), Bundle(), null) }.getOrDefault(false)
    }

    fun pinSupported(context: Context): Boolean =
        runCatching { AppWidgetManager.getInstance(context)?.isRequestPinAppWidgetSupported == true }.getOrDefault(false)
}

/** Quick ask: a search-bar-like field (new conversation), voice and photo. */
class AgentWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        ids.forEach { manager.updateAppWidget(it, AgentWidgets.views(context, AgentWidgetProvider::class.java, it)) }
    }

    companion object {
        /** The original widget's entry: opens the app, optionally straight into voice input. */
        @JvmStatic
        fun entryIntent(context: Context, voice: Boolean): Intent =
            Intent(context, com.agentworkspace.mobile.WebUiActivity::class.java)
                .setAction(if (voice) Intent.ACTION_VOICE_COMMAND else Intent.ACTION_MAIN)
                .putExtra(com.agentworkspace.mobile.voice.MobileVoiceInput.EXTRA_VOICE_INPUT, voice)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
    }
}

/** Task status: the task that needs the user or ran last, and the engine's state. */
class AgentTaskWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        ids.forEach { manager.updateAppWidget(it, AgentWidgets.views(context, AgentTaskWidgetProvider::class.java, it)) }
    }
}

/** The composer's quick tasks; each opens a new conversation with its prompt filled in. */
class AgentQuickTasksWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        ids.forEach { manager.updateAppWidget(it, AgentWidgets.views(context, AgentQuickTasksWidgetProvider::class.java, it)) }
    }
}
