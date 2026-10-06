package com.agentworkspace.mobile.update

import android.app.AlertDialog
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import com.agentworkspace.mobile.UiText
import com.agentworkspace.mobile.embedded.DiagnosticReport
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/**
 * Native help actions that work even when the engine never starts: exporting diagnostics (share,
 * save, or report on GitHub) and checking GitHub for a newer release. Create it while the activity
 * is being constructed so its document launcher is registered in time.
 */
class AppSupportController(
    private val activity: ComponentActivity,
    private val scope: CoroutineScope,
    private val dialogTheme: () -> Int,
) {
    private var reportToSave: File? = null
    private var pendingInstall: File? = null
    private var updateJob: Job? = null

    private val saveLauncher = activity.registerForActivityResult(ActivityResultContracts.CreateDocument("text/plain")) { target ->
        val report = reportToSave
        reportToSave = null
        if (target == null || report == null) return@registerForActivityResult
        scope.launch {
            val saved = withContext(Dispatchers.IO) { runCatching { DiagnosticReport.saveTo(activity, report, target) }.isSuccess }
            toast(if (saved) tr("日志已保存", "Log saved") else tr("日志保存失败", "Could not save the log"))
        }
    }

    private fun tr(zh: String, en: String) = UiText.of(activity, zh, en)

    private fun toast(message: String) = Toast.makeText(activity, message, Toast.LENGTH_LONG).show()

    private fun usable() = !activity.isFinishing && !activity.isDestroyed

    // ---- Diagnostics ----

    fun showLogExport() {
        if (!usable()) return
        val options = arrayOf(
            tr("分享日志文件", "Share the log file"),
            tr("保存到手机", "Save to this phone"),
            tr("提交到 GitHub（公开 Issue）", "Report on GitHub (public issue)"),
        )
        AlertDialog.Builder(activity, dialogTheme())
            .setTitle(tr("导出诊断日志", "Export diagnostics"))
            .setItems(options) { _, which ->
                when (which) {
                    0 -> withReport { DiagnosticReport.share(activity, it) }
                    1 -> withReport { report ->
                        reportToSave = report
                        runCatching { saveLauncher.launch(report.name) }
                            .onFailure { reportToSave = null; toast(tr("手机没有可用的文件管理器", "No file manager is available")) }
                    }
                    else -> confirmGitHubReport()
                }
            }
            .setNegativeButton(tr("取消", "Cancel"), null)
            .show()
    }

    private fun withReport(action: (File) -> Unit) {
        scope.launch {
            val report = withContext(Dispatchers.IO) { runCatching { DiagnosticReport.write(activity) } }
            report.onSuccess { file ->
                runCatching { action(file) }.onFailure { toast(tr("无法打开分享面板", "Could not open the share sheet")) }
            }.onFailure { toast(tr("诊断日志生成失败", "Could not create the diagnostics file")) }
        }
    }

    private fun confirmGitHubReport() {
        AlertDialog.Builder(activity, dialogTheme())
            .setTitle(tr("提交到 GitHub", "Report on GitHub"))
            .setMessage(tr(
                "将在浏览器打开项目的新建 Issue 页面，并预填版本、设备和最近的启动日志（密钥与令牌已打码）。\n\nIssue 是公开的，提交前请检查内容；需要登录 GitHub。完整日志可先“保存到手机”，再拖进 Issue 作为附件。",
                "Opens a new issue on the project's GitHub page in your browser, prefilled with versions, device and recent start-up logs (keys and tokens are masked).\n\nIssues are public, so review the text before submitting; a GitHub sign-in is required. To include the full log, save it to the phone first and attach it to the issue."
            ))
            .setPositiveButton(tr("继续", "Continue")) { _, _ ->
                scope.launch {
                    val uri = withContext(Dispatchers.IO) { runCatching { DiagnosticReport.issueUri(activity) }.getOrNull() }
                    if (uri == null) { toast(tr("诊断日志生成失败", "Could not create the diagnostics file")); return@launch }
                    openBrowser(uri)
                }
            }
            .setNegativeButton(tr("取消", "Cancel"), null)
            .show()
    }

    private fun openBrowser(uri: Uri) {
        try {
            activity.startActivity(Intent(Intent.ACTION_VIEW, uri).addCategory(Intent.CATEGORY_BROWSABLE))
        } catch (_: ActivityNotFoundException) {
            toast(tr("手机没有可用的浏览器", "No browser is available"))
        }
    }

    // ---- Updates ----

    /** Once a day, a few seconds after launch, quietly ask GitHub for a newer release. */
    fun autoCheckIfDue() {
        if (!UpdateChecker.dueForAutoCheck(activity)) return
        scope.launch {
            delay(8000)
            if (updateJob?.isActive != true) check(manual = false)
        }
    }

    fun checkNow() {
        if (updateJob?.isActive == true) { toast(tr("正在检查或下载更新", "An update check is already running")); return }
        check(manual = true)
    }

    private fun check(manual: Boolean) {
        val waiting = if (manual && usable()) AlertDialog.Builder(activity, dialogTheme())
            .setMessage(tr("正在检查 GitHub 上的新版本...", "Checking GitHub for a new version..."))
            .setCancelable(true)
            .show() else null
        updateJob = scope.launch {
            val result = withContext(Dispatchers.IO) { runCatching { UpdateChecker.fetchLatest() } }
            waiting?.dismiss()
            val installed = UpdateChecker.installedVersion(activity)
            result.onSuccess { release ->
                UpdateChecker.markChecked(activity, release.version)
                when {
                    !UpdateChecker.isNewer(release.version, installed) ->
                        if (manual) toast(tr("已是最新版本 $installed", "You have the latest version ($installed)"))
                    !manual && UpdateChecker.skippedVersion(activity) == release.version -> Unit
                    else -> offer(release, installed, manual)
                }
            }.onFailure { failure ->
                if (failure is CancellationException) throw failure
                if (manual && usable()) AlertDialog.Builder(activity, dialogTheme())
                    .setTitle(tr("检查更新失败", "Update check failed"))
                    .setMessage(failure.message ?: failure.javaClass.simpleName)
                    .setPositiveButton(tr("打开发布页", "Open releases")) { _, _ -> openBrowser(Uri.parse(UpdateChecker.RELEASES_PAGE)) }
                    .setNegativeButton(tr("关闭", "Close"), null)
                    .show()
            }
        }
    }

    private fun offer(release: ReleaseInfo, installed: String, manual: Boolean) {
        if (!usable()) return
        val size = if (release.apkSize > 0) " · %.1f MB".format(release.apkSize / 1048576.0) else ""
        val notes = plainNotes(release.notes)
        val builder = AlertDialog.Builder(activity, dialogTheme())
            .setTitle(tr("发现新版本 v${release.version}", "Version ${release.version} is available"))
            .setMessage(tr("当前版本 $installed$size", "Installed: $installed$size") + if (notes.isEmpty()) "" else "\n\n$notes")
            .setPositiveButton(tr("下载并安装", "Download and install")) { _, _ -> download(release) }
            .setNegativeButton(tr("稍后", "Later"), null)
        if (!manual) builder.setNeutralButton(tr("跳过此版本", "Skip this version")) { _, _ -> UpdateChecker.skip(activity, release.version) }
        else builder.setNeutralButton(tr("发布页", "Release page")) { _, _ -> openBrowser(Uri.parse(release.pageUrl)) }
        builder.show()
    }

    private fun plainNotes(markdown: String): String = markdown.lines()
        .map { it.replace(Regex("^#+\\s*"), "").replace("**", "").replace("`", "").trimEnd() }
        .filterNot { it.startsWith("|") || it.startsWith("<") }
        .joinToString("\n").replace(Regex("\n{3,}"), "\n\n").trim()
        .let { if (it.length > 1500) it.take(1500).trimEnd() + "\n…" else it }

    private fun download(release: ReleaseInfo) {
        if (!usable()) return
        val bar = ProgressBar(activity, null, android.R.attr.progressBarStyleHorizontal).apply { max = 1000 }
        val label = TextView(activity).apply { text = tr("正在连接...", "Connecting...") }
        val padding = (20 * activity.resources.displayMetrics.density).toInt()
        val content = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(padding, padding / 2, padding, 0)
            addView(bar)
            addView(label)
        }
        var cancelled = false
        val dialog = AlertDialog.Builder(activity, dialogTheme())
            .setTitle(tr("正在下载 v${release.version}", "Downloading ${release.version}"))
            .setView(content)
            .setCancelable(false)
            .setNegativeButton(tr("取消", "Cancel")) { _, _ -> cancelled = true }
            .show()
        updateJob = scope.launch {
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    var lastUpdate = 0L
                    val apk = UpdateChecker.download(activity, release, { received, total ->
                        val now = System.currentTimeMillis()
                        if (now - lastUpdate >= 200 || received == total) {
                            lastUpdate = now
                            scope.launch {
                                if (total > 0) bar.progress = (received * 1000 / total).toInt() else bar.isIndeterminate = true
                                label.text = "%.1f / %.1f MB".format(received / 1048576.0, total.coerceAtLeast(received) / 1048576.0)
                            }
                        }
                    }, { cancelled })
                    UpdateChecker.verify(activity, apk)?.let { problem -> apk.parentFile?.deleteRecursively(); error(problem) }
                    apk
                }
            }
            if (dialog.isShowing) dialog.dismiss()
            result.onSuccess { install(it) }.onFailure { failure ->
                if (failure is CancellationException) throw failure
                if (!cancelled && usable()) AlertDialog.Builder(activity, dialogTheme())
                    .setTitle(tr("更新失败", "Update failed"))
                    .setMessage((failure.message ?: failure.javaClass.simpleName) + tr("\n\n也可以在发布页手动下载安装。", "\n\nYou can also download it from the release page."))
                    .setPositiveButton(tr("打开发布页", "Open releases")) { _, _ -> openBrowser(Uri.parse(release.pageUrl)) }
                    .setNegativeButton(tr("关闭", "Close"), null)
                    .show()
            }
        }
    }

    private fun install(apk: File) {
        if (!usable()) return
        if (Build.VERSION.SDK_INT >= 26 && !activity.packageManager.canRequestPackageInstalls()) {
            pendingInstall = apk
            AlertDialog.Builder(activity, dialogTheme())
                .setTitle(tr("需要安装权限", "Permission needed"))
                .setMessage(tr(
                    "新版本已下载并校验通过。请在接下来的系统页面中允许 Agent Workspace “安装未知应用”，返回后会继续安装。",
                    "The new version is downloaded and verified. Allow Agent Workspace to install unknown apps on the next screen; installation continues when you come back."
                ))
                .setPositiveButton(tr("去设置", "Open settings")) { _, _ ->
                    runCatching {
                        activity.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${activity.packageName}")))
                    }.onFailure { toast(tr("无法打开系统设置", "Could not open system settings")) }
                }
                .setNegativeButton(tr("取消", "Cancel")) { _, _ -> pendingInstall = null }
                .show()
            return
        }
        pendingInstall = null
        runCatching { activity.startActivity(UpdateChecker.installIntent(activity, apk)) }
            .onFailure { toast(tr("无法打开系统安装器", "Could not open the system installer")) }
    }

    /** Back from the "install unknown apps" screen: continue a verified update once it is allowed. */
    fun onResume() {
        val apk = pendingInstall ?: return
        if (Build.VERSION.SDK_INT >= 26 && !activity.packageManager.canRequestPackageInstalls()) return
        if (apk.isFile) install(apk) else pendingInstall = null
    }
}
