(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const i18n = window.MobileI18n;
  const t = i18n?.t || ((text, ...values) => String(text).replace(/\{(\d+)\}/g, (_, index) => String(values[index] ?? "")));
  const localizeError = i18n?.localizeError || ((message) => message);
  const ui = window.AgentMobileUi;
  const native = window.AndroidBridge;
  if (!ui) return;
  let generation = 0;
  let selectedHost = null;
  let remoteSessions = [];
  const remoteSessionTitles = new Map();
  let closed = false;
  let modelPoll = null;
  let toolchainPoll = null;
  let devicePoll = null;
  let deviceRecommendation = null;
  let deviceModels = [];
  let deviceEngineAvailable = false;
  let deviceBusyReason = t("正在读取本机状态");
  let deviceModelBusy = true;
  let deviceTestWasRunning = false;
  let stepSequence = 0;
  const stateNames = { available: t("可用"), pending: t("待发送"), sending: t("发送中"), submitted: t("已接收"), completed: t("已完成"), failed: t("失败"), cancelled: t("已取消"), uncertain: t("结果未知"), approved: t("已授权"), denied: t("已拒绝"), revoked: t("已撤销"), verified: t("已验证"), unverified: t("未验证"), running: t("运行中"), interrupted: t("已中断"), blocked: t("受阻"), success: t("目标已验证"), failure: t("失败"), takeover: t("已接管") };
  function status(id, message, error = false) { $(id).textContent = message || ""; $(id).classList.toggle("error", error); }
  // Catalog titles end in a Chinese note ("Qwen3.5 2B · Q4_K_M · 更多能力"), translated here.
  function modelTitle(title) {
    return String(title || "").split(" · ").map((part) => /[一-鿿]/.test(part) ? t(part) : part).join(" · "); // i18n-ignore: a character range
  }

  // Model download source: a per-device choice. Automatic tries the source nearest the user's
  // language first (ModelScope's mainland CDN for Chinese) and falls back to the other.
  const downloadSourceKey = "agent-model-download-source";
  function downloadSource(model) {
    const chosen = $("modelDownloadSource").value;
    const available = (model.download_sources || []).map((source) => source.id);
    return {
      source: available.includes(chosen) ? chosen : "auto",
      prefer: (window.MobileI18n?.language || "zh").startsWith("zh") ? "modelscope" : "huggingface",
    };
  }
  function sourceTitle(model) {
    return (model.download_sources || []).find((source) => source.id === model.source)?.title || "";
  }
  // A download the engine is working on, also while it waits for the network to come back.
  const activeDownloadStates = ["queued", "downloading", "waiting_network", "verifying"];
  // "Downloading · 68.1 MiB of 507.8 MiB · 190 KB/s · about 38 min": what came in and how long is left.
  function downloadState(model) {
    const names = { not_installed: t("未下载"), installed: t("已校验安装"), queued: t("等待下载"), downloading: t("下载中"),
      waiting_network: t("网络断了，恢复后自动继续"), verifying: t("校验中"), paused: t("已暂停"), failed: t("下载失败") };
    const name = names[model.state] || model.state;
    if (!["downloading", "waiting_network", "paused"].includes(model.state) || !model.downloaded_bytes) return name;
    const parts = [name, t("{0} / {1}", bytes(model.downloaded_bytes), bytes(model.size_bytes))];
    const speed = Number(model.bytes_per_second) || 0;
    if (model.state === "downloading" && speed > 0) {
      parts.push(speed >= 1024 ** 2 ? `${(speed / 1024 ** 2).toFixed(1)} MB/s` : `${Math.max(1, Math.round(speed / 1024))} KB/s`);
      const minutes = Math.ceil((model.size_bytes - model.downloaded_bytes) / speed / 60);
      parts.push(minutes <= 1 ? t("不到 1 分钟") : t("约 {0} 分钟", minutes));
    }
    if (model.state === "downloading" && sourceTitle(model)) parts.push(t("来源 {0}", sourceTitle(model)));
    return parts.join(" · ");
  }
  try {
    const saved = window.localStorage.getItem(downloadSourceKey);
    if (["auto", "modelscope", "huggingface"].includes(saved)) $("modelDownloadSource").value = saved;
  } catch { /* Storage can be unavailable; automatic stays selected. */ }
  $("modelDownloadSource").addEventListener("change", () => {
    try { window.localStorage.setItem(downloadSourceKey, $("modelDownloadSource").value); } catch {}
  });
  function icon(name) { return window.MobileUi?.iconMarkup(name) || ""; }
  function row(title, details = "") {
    const element = document.createElement("div"); element.className = "management-row";
    const body = document.createElement("div"); body.className = "management-row-body";
    const label = document.createElement("strong"); label.textContent = title;
    const detail = document.createElement("small"); detail.textContent = details;
    body.append(label, detail); element.append(body); return element;
  }
  function action(parent, symbol, label, handler) {
    const button = document.createElement("button"); button.type = "button"; button.className = "icon-button";
    button.title = label; button.setAttribute("aria-label", label); button.innerHTML = icon(symbol);
    button.addEventListener("click", async () => {
      if (button.disabled) return;
      const statusId = button.closest(".settings-page")?.querySelector(".page-status")?.id;
      button.disabled = true;
      try { await handler(); }
      catch (error) { if (!closed && statusId) status(statusId, error.message || t("操作失败"), true); }
      finally { if (button.isConnected) button.disabled = false; }
    });
    parent.append(button); return button;
  }
  function terms(id, values) {
    $(id).replaceChildren();
    for (const [name, value] of values) {
      const label = document.createElement("dt"); label.textContent = name;
      const content = document.createElement("dd"); content.textContent = value ?? t("未测量");
      $(id).append(label, content);
    }
  }
  function bytes(value) { return Number.isFinite(value) ? value >= 1024 ** 3 ? `${(value / 1024 ** 3).toFixed(2)} GiB` : `${(value / 1024 ** 2).toFixed(1)} MiB` : t("未测量"); }
  function namedAction(parent, symbol, label, handler) {
    const button = action(parent, symbol, label, handler);
    button.className = "button-secondary model-action";
    const text = document.createElement("span"); text.textContent = label; button.append(text);
    return button;
  }
  function setUnavailable(button, reason) {
    button.disabled = !!reason;
    button.title = reason || button.getAttribute("aria-label") || button.textContent.trim();
  }
  function nativeResult(method, ...args) {
    if (typeof native?.[method] !== "function") throw new Error(t("当前客户端不支持此操作，请更新 APK"));
    const value = JSON.parse(native[method](...args) || "{}");
    if (value.error || value.ok === false) throw new Error(localizeError(typeof value.error === "string" ? value.error : value.error?.message) || t("操作失败"));
    return value;
  }
  async function shareDocument(title, value, statusId) {
    const text = JSON.stringify(value, null, 2);
    if (typeof native?.shareText === "function") native.shareText(title, text);
    else if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
    else throw new Error(t("当前设备无法导出文本"));
    status(statusId, typeof native?.shareText === "function" ? t("已打开分享") : t("已复制到剪贴板"));
  }
  function stopPolls() { window.clearTimeout(modelPoll); window.clearTimeout(toolchainPoll); window.clearTimeout(servicesPoll); window.clearTimeout(knowledgePoll); window.clearTimeout(computerPoll); modelPoll = toolchainPoll = servicesPoll = knowledgePoll = computerPoll = null; }
  async function post(path, body) { return ui.apiJson(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); }
  function followTask(result, statusId, message) {
    if (ui.adoptTask(result.task)) ui.closeMenu();
    else status(statusId, t("{0}，可在任务中心查看", message));
  }
  function on(id, event, handler, statusId) {
    $(id).addEventListener(event, async (eventObject) => {
      if (event === "submit") eventObject.preventDefault();
      const button = event === "submit" ? eventObject.target.querySelector('button[type="submit"]') : eventObject.currentTarget;
      if (button?.disabled) return;
      if (button) button.disabled = true;
      try { await handler(eventObject); }
      catch (error) { if (!closed) status(statusId, error.message, true); }
      finally {
        if (button?.isConnected) {
          if (["btnStartLocalBenchmark", "btnCancelLocalBenchmark", "btnUseLocalRecommendation"].includes(button.id)) deviceStatus();
          // Usable again only while files wait to go (those that went have left the list).
          else if (button.id === "btnComputerSendFiles") button.disabled = !outgoing.length;
          else button.disabled = false;
        }
      }
    });
  }
  async function page(pageName, loader, statusId) {
    if (!ui.setSettingsPage(pageName)) return;
    stopPolls();
    const current = ++generation;
    status(statusId, t("读取中..."));
    try { await loader(() => !closed && current === generation && !$("settingsOverlay").hidden); }
    catch (error) { if (current === generation && !closed) status(statusId, error.message, true); }
  }

  // ---- Background operation: phone tasks on an off-screen display (needs Shizuku) ----
  const backgroundReasons = { needs_android_11: "需要 Android 11 或更高版本", shizuku_missing: "没有安装 Shizuku", shizuku_stopped: "Shizuku 没有运行（手机重启后需要重新启动 Shizuku）", shizuku_permission: "还没有授权本应用使用 Shizuku" }; // i18n-ignore: keys for t()
  function backgroundScreen(value) {
    $("backgroundScreenToggle").checked = value.enabled === true;
    $("backgroundScreenToggle").disabled = value.supported === false;
    $("btnBackgroundLook").hidden = !(value.enabled && !value.reason);
    $("btnBackgroundToFront").hidden = value.active !== true;
    const reason = value.reason ? t(backgroundReasons[value.reason] || backgroundReasons.shizuku_stopped) : "";
    status("backgroundScreenStatus", value.enabled ? (reason || (value.active ? t("后台屏幕已打开") : t("可以使用：对话里的手机任务会在后台进行"))) : reason,
      !!(value.enabled && reason));
    backgroundSetup(value);
  }
  // Setup steps, from installing Shizuku to letting this app use it; the first one not done is the
  // one to do now. Shown while something is missing; open by itself once the switch is on.
  function backgroundSetup(value) {
    const setup = $("backgroundSetup");
    setup.hidden = value.supported === false || !value.reason;
    if (setup.hidden) return;
    if (value.enabled) setup.open = true;
    const running = value.shizuku_running === true;
    const step = (name) => () => nativeResult("openShizukuStep", name);
    const steps = [
      { done: value.shizuku_installed || running, title: t("安装 Shizuku"), hint: t("Shizuku 把系统权限借给本应用，用来在后台屏幕上操作。从它的官网下载。"),
        actions: [[t("打开 Shizuku 官网"), () => openServiceUrl("https://shizuku.rikka.app/download/")]] },
      { done: value.developer_options === true || running, title: t("打开开发者选项"),
        hint: t("在「关于手机」里连续点「版本号」7 次（有的手机叫「软件版本号」），按提示输入锁屏密码。"), actions: [[t("打开关于手机"), step("device_info")]] },
      { done: value.wifi === true || running, title: t("连上 Wi‑Fi"), hint: t("Shizuku 通过无线调试启动，无线调试只在连着 Wi‑Fi 时能用。") },
      { done: running, title: t("启动 Shizuku"),
        hint: t("打开 Shizuku，点「通过无线调试启动」。第一次要先配对：按 Shizuku 的提示打开「开发者选项 → 无线调试 → 使用配对码配对设备」，把配对码填进 Shizuku 的通知里。手机重启后只需要重做这一步。"),
        actions: [[t("打开 Shizuku"), step("shizuku")], [t("打开开发者选项"), step("developer")]] },
      { done: value.permitted === true, title: t("允许本应用使用 Shizuku"), hint: t("Shizuku 会弹出询问，选「始终允许」。"),
        actions: [[t("授权 Shizuku"), async () => {
          backgroundScreen(await post("/mobile/background-screen", { action: "request_permission" }));
          setTimeout(() => { if (!closed) loadBackgroundScreen().catch(() => {}); }, 4000);
        }]] },
    ];
    const current = steps.findIndex((item) => !item.done);
    $("backgroundSetupList").replaceChildren(...steps.map((item, index) => {
      const row = document.createElement("li");
      row.className = item.done ? "done" : index === current ? "current" : "";
      const title = document.createElement("strong");
      title.textContent = item.done ? t("{0}（已完成）", item.title) : item.title;
      row.append(title);
      if (index === current) {
        const hint = document.createElement("p");
        hint.textContent = item.hint;
        row.append(hint);
        if (item.actions?.length) {
          const bar = document.createElement("div");
          bar.className = "page-toolbar";
          for (const [label, run] of item.actions) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "button-secondary";
            button.textContent = label;
            button.addEventListener("click", async () => {
              try { await run(); } catch (error) { status("backgroundScreenStatus", error.message, true); }
            });
            bar.append(button);
          }
          row.append(bar);
        }
      }
      return row;
    }));
  }
  async function loadBackgroundScreen(isCurrent = () => true) {
    const value = await ui.apiJson("/mobile/background-screen");
    if (isCurrent()) backgroundScreen(value);
  }
  // Back from Shizuku or the settings app: the steps move on by themselves.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && !closed && !$("settingsDoctor").hidden && !$("settingsOverlay").hidden) loadBackgroundScreen().catch(() => {});
  });

  async function doctor(isCurrent = () => true) {
    loadBackgroundScreen(isCurrent).catch(() => {});
    $("gpuReportSection").hidden = typeof native?.getGpuReport !== "function";
    const value = await ui.apiJson("/mobile/capabilities");
    if (!isCurrent()) return;
    const android = value.android || {};
    let engine = {};
    try { engine = JSON.parse(native?.getEngineStatus?.() || "{}"); } catch {}
    terms("doctorSummary", [[t("运行环境"), value.runtime], [t("引擎状态"), engine.state || t("已连接")], [t("系统操作"), android.enabled && android.connected ? t("已连接") : t("需要无障碍权限")], [t("截图"), android.live_screen_active ? t("实时画面") : android.screenshot_supported ? t("支持") : t("不可用")], [t("内存"), android.memory_total_bytes ? `${(android.memory_total_bytes / 1024 ** 3).toFixed(1)} GiB` : t("未测量")]]);
    $("liveScreenToggle").checked = !!android.live_screen_active;
    $("liveScreenToggle").disabled = typeof native?.startLiveScreen !== "function";
    $("systemPaused").checked = !!android.paused;
    $("systemPaused").disabled = typeof native?.setSystemPaused !== "function";
    $("btnAccessibilitySettings").disabled = typeof native?.openAccessibilitySettings !== "function";
    // Switched on in the system but not running (after an update or a crash), or switched off.
    const stalled = android.switched_on && !android.enabled;
    $("accessibilityRepair").hidden = android.enabled && android.connected || typeof native?.repairAccessibility !== "function";
    $("repairAccessibilityLabel").textContent = android.can_repair
      ? (stalled ? t("重新启用无障碍") : t("打开无障碍服务"))
      : (stalled ? t("去系统设置里重新打开") : t("去系统设置里打开"));
    $("accessibilityRepairHint").textContent = stalled
      ? (android.can_repair ? t("系统里无障碍开关是开着的，但服务没有运行（更新或崩溃后常见）。点下面关掉再打开。") : t("系统里无障碍开关是开着的，但服务没有运行（更新或崩溃后常见）。在系统设置里把 Agent Workspace 关掉再打开即可。"))
      : (android.can_repair ? t("无障碍服务没开，点下面直接打开。") : t("无障碍服务没开，手机操作需要它。"));
    $("btnTakeover").disabled = typeof native?.requestSystemTakeover !== "function";
    $("doctorTools").replaceChildren();
    for (const tool of value.tools || []) $("doctorTools").append(row(tool.name, tool.available ? t("可用") : localizeError(tool.reason) || t("不可用")));
    $("browserSection").hidden = !(value.tools || []).some((tool) => tool.name === "browser_view" && tool.available);
    status("doctorStatus", localizeError(android.reason) || "");
    let background = {};
    try { background = JSON.parse(native?.getBackgroundStatus?.() || "{}"); } catch {}
    const run = backgroundRunState();
    const pauses = (run?.pauses || []).filter((pause) => pause.screen_on);
    terms("backgroundSummary", [[t("电池优化"), background.battery_optimization_exempt ? t("已豁免") : t("系统默认")], [t("恢复状态"), background.engine?.requires_user_launch ? t("需要手动启动") : background.engine?.state || t("按系统条件恢复")], [t("后台限制"), background.background_restricted ? t("已限制") : t("未限制")], [t("完成通知"), background.notifications_enabled ? t("已开启") : t("未开启或未授权")],
      ...(run ? [[t("引擎被系统暂停（亮屏时）"), pauses.length ? t("{0} 次，最长 {1} 秒", pauses.length, Math.max(...pauses.map((pause) => pause.seconds || 0))) : t("没有记录")]] : [])]);
    $("btnBatterySettings").disabled = typeof native?.openBatteryOptimizationSettings !== "function";
    $("btnBackgroundSettings").disabled = typeof native?.openAppBackgroundSettings !== "function";
    $("backgroundSteps").hidden = !run?.steps;
    $("backgroundSteps").textContent = run?.steps ? t("{0}：{1}", run.maker, run.steps) : "";
    $("btnAllowBackground").hidden = !run || run.battery_optimization_exempt;
    $("btnAllowBackground").disabled = typeof native?.requestBackgroundRun !== "function";
    $("btnAutoStartSettings").hidden = !run?.strict_maker;
    $("autoStartLabel").textContent = run?.strict_maker ? t("{0}：应用启动管理 / 自启动", run.maker) : t("应用启动管理");
    $("btnAutoStartSettings").disabled = typeof native?.openAutoStartSettings !== "function";
    calendarAccess();
    blockedApps();
    await toolchain(isCurrent);
  }
  // Apps the agent may not read or use (a bank, a payment app); the list stays on the phone.
  let launcherApps = null;
  function parsed(raw) { try { const value = JSON.parse(raw || "[]"); return Array.isArray(value) ? value : []; } catch { return []; } }
  function blockedApps(list) {
    const supported = typeof native?.getBlockedApps === "function" && typeof native?.setBlockedApps === "function";
    $("blockedAppsSection").hidden = !supported;
    if (!supported) return;
    const apps = list || parsed(native.getBlockedApps());
    const container = $("blockedAppsList");
    container.replaceChildren();
    if (!apps.length) container.append(row(t("还没有"), t("AI 可以操作所有应用")));
    for (const app of apps) {
      const line = row(app.label || app.package, app.package);
      action(line, "x", t("移除"), () => blockedApps(parsed(native.setBlockedApps(JSON.stringify(apps.map((item) => item.package).filter((name) => name !== app.package))))));
      container.append(line);
    }
    if (!$("blockedAppPicker").hidden) blockedAppChoices();
  }
  function blockedAppChoices() {
    const blocked = new Set(parsed(native.getBlockedApps()).map((app) => app.package));
    const query = $("blockedAppSearch").value.trim().toLowerCase();
    const choices = (launcherApps || []).filter((app) => !blocked.has(app.package) &&
      (!query || app.label.toLowerCase().includes(query) || app.package.toLowerCase().includes(query))).slice(0, 60);
    const container = $("blockedAppChoices");
    container.replaceChildren();
    for (const app of choices) {
      const line = row(app.label, app.package);
      action(line, "plus", t("添加"), () => {
        blockedApps(parsed(native.setBlockedApps(JSON.stringify([...blocked, app.package]))));
        $("blockedAppPicker").hidden = true;
      });
      container.append(line);
    }
    if (!choices.length) container.append(row(t("没有找到应用"), ""));
  }
  // Alarms need no permission; reading and adding calendar events need the calendar one.
  function calendarAccess() {
    const supported = typeof native?.getCalendarAccess === "function";
    $("clockCalendarSection").hidden = !supported;
    if (!supported) return;
    let access = {};
    try { access = JSON.parse(native.getCalendarAccess() || "{}"); } catch {}
    const granted = access.read && access.write;
    $("calendarAccessState").textContent = granted ? t("已允许：AI 可以查看和添加日程") : t("未允许：点这里授权");
  }
  window.addEventListener("agent-calendar-access-changed", calendarAccess);
  // GPU compatibility report (Diagnostics): what people send in for the table of GPUs the local
  // model runs on. Made on request: reading the GPU may start the engine's GPU check.
  const gpuIssuesUrl = "https://github.com/WhitePepperLambSoup/agent-workspace-android/issues";
  let gpuReportText = "";
  // Short forms of acceleratorText for the report's table.
  const gpuReportStates = {
    available: t("用 GPU"), checking: t("正在检查 GPU，先用 CPU"), unchecked: t("还没检查 GPU，先用 CPU"),
    unknown: t("本机模型运行中，稍后再生成"), unsupported_gpu: t("GPU 驱动较旧，用 CPU"), no_supported_gpu: t("GPU 暂不支持，用 CPU"),
    check_failed: t("GPU 没通过检查，用 CPU"), driver_unavailable: t("GPU 驱动没有开放，用 CPU"), cpu_unsupported: t("处理器较旧，只用 CPU"),
    failed: t("GPU 曾出错，已改用 CPU"),
  };
  // The GPU as the browser engine names it: also Mali or PowerVR, which OpenCL here does not list.
  function webglRenderer() {
    try {
      const gl = document.createElement("canvas").getContext("webgl");
      if (!gl) return "";
      const info = gl.getExtension("WEBGL_debug_renderer_info");
      const name = gl.getParameter(info ? info.UNMASKED_RENDERER_WEBGL : gl.RENDERER);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
      return String(name || "").slice(0, 120);
    } catch { return ""; }
  }
  function gpuReport() {
    let value;
    try { value = nativeResult("getGpuReport"); } catch (error) { status("gpuReportStatus", error.message, true); return; }
    const device = value.device || {};
    const gpu = value.accelerator || {};
    const run = value.benchmark || {};
    let version = "";
    try { version = JSON.parse(native?.getUpdateSettings?.() || "{}").version || ""; } catch {}
    const renderer = webglRenderer();
    // Some makers already put their name in the model ("ZTE A2022P").
    const maker = String(device.manufacturer || "");
    const phone = String(device.model || "").toLowerCase().startsWith(maker.toLowerCase()) ? String(device.model || "")
      : [maker, device.model].filter(Boolean).join(" ");
    const android = `Android ${device.android || "?"} (API ${device.sdk || "?"})`;
    const speed = Number.isFinite(run.tokens_per_second) && run.state === "completed"
      ? `${run.accelerator === "gpu" ? "GPU" : "CPU"} · ${run.prompt_tokens_per_second?.toFixed(1) ?? "?"} / ${run.tokens_per_second.toFixed(1)} Token/s · ${run.model_id || ""}`.replace(/ · $/, "") : "";
    terms("gpuReportSummary", [
      [t("手机"), phone || t("未知")], [t("芯片"), device.soc || t("未知")], [t("系统"), android],
      [t("GPU（OpenCL）"), [gpu.gpu_description, gpu.gpu_version].filter(Boolean).join(" · ") || gpu.gpu || t("未读到")],
      [t("GPU（WebGL）"), renderer || t("未读到")],
      [t("本机模型"), gpuReportStates[gpu.gpu_state] || t("本机引擎尚未就绪")],
      [t("最近一次设备测试"), speed || t("还没有测过：在「本机模型」里运行设备测试后再生成")],
    ]);
    // Plain English keys, so reports in any language read the same.
    gpuReportText = [
      "Agent Workspace GPU report",
      `App: ${version || "?"}`, `Phone: ${phone || "?"}`, `SoC: ${device.soc || "?"}`, `System: ${android} · ${device.abi || "?"}`,
      `OpenCL GPU: ${[gpu.gpu_description, gpu.gpu_version].filter(Boolean).join(" · ") || "none"}`, `WebGL renderer: ${renderer || "?"}`,
      `GPU state: ${gpu.gpu_state || "?"} · mode ${gpu.mode || "?"} · library ${gpu.library || "?"} · CPU build ${value.cpu_build || "?"}`,
      ...(gpu.failure ? [`GPU failure: ${String(gpu.failure).slice(0, 300)}`] : []),
      `Device test: ${speed ? `${speed} (prompt / generation) · context ${run.actual_context_size || "?"}` : "not run"}`,
    ].join("\n");
    $("btnGpuReportCopy").hidden = false;
    $("btnGpuReportIssues").hidden = false;
    status("gpuReportStatus", "");
  }

  // Updates and logs had been at the bottom of 设备与工具, where users did not find them.
  async function about() {
    $("btnShareDiagnostics").disabled = typeof native?.shareDiagnostics !== "function";
    updates();
  }
  function updates() {
    let value = {};
    try { value = JSON.parse(native?.getUpdateSettings?.() || "{}"); } catch {}
    const supported = typeof native?.checkForUpdates === "function";
    $("btnCheckUpdates").disabled = !supported;
    $("autoUpdateToggle").disabled = typeof native?.setAutoUpdateCheck !== "function";
    $("autoUpdateToggle").checked = value.autoCheck !== false;
    const checked = value.lastCheckedMs ? new Date(value.lastCheckedMs).toLocaleString() : t("尚未检查");
    status("updateStatus", supported ? t("当前版本 {0} · 上次检查 {1}", value.version || "?", checked) : t("当前版本不支持应用内更新"));
    $("menuAboutSummary").textContent = value.version
      ? t("版本 {0} · 检查更新、导出诊断日志", value.version)
      : t("检查更新、导出诊断日志");
  }
  async function toolchain(isCurrent = () => true) {
    let value;
    try { value = await ui.apiJson("/mobile/toolchain"); }
    catch (error) { if (isCurrent()) status("toolchainStatus", error.message, true); return; }
    if (!isCurrent()) return;
    const tools = value.executables || value.tools || {};
    terms("toolchainSummary", [[t("状态"), value.available ? t("已验证可用") : value.state || t("未安装")], [t("下载进度"), `${bytes(value.downloaded_bytes || 0)} / ${bytes(value.total_bytes || value.download_size)}`], [t("已验证工具"), Object.keys(tools).join(t("、")) || t("尚未探测")]]);
    const active = ["downloading", "extracting", "probing", "cancelling"].includes(value.state);
    $("btnToolchainInstall").disabled = active || value.available || ui.context().activeTask;
    $("btnToolchainProbe").disabled = active || !value.installed;
    $("btnToolchainCancel").hidden = !active;
    $("btnToolchainRemove").hidden = !value.installed;
    $("btnToolchainRemove").disabled = active || ui.context().activeTask;
    $("btnToolchainRestart").hidden = !value.installed;
    $("btnToolchainRestart").disabled = typeof native?.restartEngine !== "function" || ui.context().activeTask;
    status("toolchainStatus", localizeError(value.reason || value.error) || "");
    window.clearTimeout(toolchainPoll);
    if (active) toolchainPoll = window.setTimeout(() => { if (!closed && !$("settingsDoctor").hidden && !$("settingsOverlay").hidden) toolchain(isCurrent); }, 2500);
  }
  // Skills page: packs from GitHub or a file; shown to the user before they are installed.
  let skillsPreview = null;
  // The engine explains skill problems in English with names and numbers in them.
  const skillErrorsZh = [
    [/^no skills found: a skill is a folder with a SKILL\.md file(.*)$/s, "没有找到技能：技能是一个含 SKILL.md 文件的文件夹$1"], // i18n-ignore: engine message
    [/^enter a GitHub repository as owner\/repo or its (?:github\.com )?link$/, "请输入 GitHub 仓库：owner/repo 或 github.com 链接"], // i18n-ignore: engine message
    [/^could not reach GitHub \((.*)\); check the network or try again$/, "连不上 GitHub（$1），请检查网络后重试"], // i18n-ignore: engine message
    [/^GitHub limited requests from this network for now; try again in an hour$/, "GitHub 暂时限制了这个网络的请求，请一小时后再试"], // i18n-ignore: engine message
    [/^GitHub answered HTTP (\d+)$/, "GitHub 返回了错误 $1"], // i18n-ignore: engine message
    [/^GitHub has no public repository (.+)$/, "GitHub 上没有公开仓库 $1"], // i18n-ignore: engine message
    [/^(.+) has no release (.+)$/, "$1 没有 Release $2"], // i18n-ignore: engine message
    [/^(.+) has no branch (.+)$/, "$1 没有分支 $2"], // i18n-ignore: engine message
    [/^the (?:download|file) is larger than (\d+) MB$/, "文件超过 $1 MB"], // i18n-ignore: engine message
    [/^the pack is larger than 64 MB unpacked$/, "技能包解压后超过 64 MB"], // i18n-ignore: engine message
    [/^the archive holds more than (\d+) files$/, "压缩包里的文件超过 $1 个"], // i18n-ignore: engine message
    [/^not a zip or tar\.gz archive$/, "不是 zip 或 tar.gz 压缩包"], // i18n-ignore: engine message
    [/^another skill download is still running$/, "还有一个技能包正在下载"], // i18n-ignore: engine message
    [/^that preview (?:expired|is not valid any more); fetch the pack again$/, "预览已失效，请重新获取"], // i18n-ignore: engine message
    [/^at most (\d+) skill packs can be installed$/, "最多安装 $1 个技能包"], // i18n-ignore: engine message
    [/^the repository has no releases any more$/, "仓库已经没有 Release 了"], // i18n-ignore: engine message
    [/^the new version names a different pack; remove this one and import it$/, "新版本是另一个技能包：请删除这个后重新导入"], // i18n-ignore: engine message
    [/^only packs from GitHub can be updated; import the new file instead$/, "只有来自 GitHub 的技能包能在线更新；请重新导入新文件"], // i18n-ignore: engine message
    [/^(.+): front matter needs a (name|description)$/, "$1：SKILL.md 开头缺少 $2"], // i18n-ignore: engine message
    [/^SKILL\.md must start with front matter.*$/s, "SKILL.md 必须以 --- 包住的 name、description 开头"], // i18n-ignore: engine message
    [/^the official skills have no release yet$/, "官方技能还没有发布"], // i18n-ignore: engine message
    [/^only SKILL\.md skills can be shared as a code$/, "只有 SKILL.md 格式的技能能用分享码分享"], // i18n-ignore: engine message
    [/^the skill is too large to share as a code; share its pack file instead$/, "技能太大，不能用分享码分享；请分享技能包文件"], // i18n-ignore: engine message
    [/^the share code (?:has no skill name|holds no SKILL\.md|holds a file that is not a skill text file|is too large)$/, "分享码里的技能不完整，不能导入"], // i18n-ignore: engine message
    [/^that skill is not in the pack$/, "技能包里没有这个技能"], // i18n-ignore: engine message
  ];
  function skillError(message) {
    const text = localizeError(message) || "";
    if (t("技能") === "Skills") return text;
    for (const [pattern, chinese] of skillErrorsZh) if (pattern.test(text)) return text.replace(pattern, chinese);
    return text;
  }
  function skillVersion(version) { return /^[0-9a-f]{40}$/.test(version || "") ? version.slice(0, 7) : version || ""; }
  function skillSource(source) {
    if (!source) return "";
    if (source.kind === "github") {
      const where = source.channel === "release" ? t("Release {0}", source.tag) : t("分支 {0} · {1}", source.branch, skillVersion(source.revision));
      return `github.com/${source.repo} · ${where}${source.subpath ? ` · ${source.subpath}` : ""}`;
    }
    if (source.kind === "shared") return source.signer ? t("分享码 · 签名指纹 {0}", source.signer) : t("分享码");
    return t("文件 {0}", source.file || "");
  }
  // What a pack's instructions talk about (mobile_skills skill_mentions), for the preview.
  const skillMentionLabels = { phone: "操作手机", messages: "发消息", payment: "付款、购买", delete: "删除或卸载", web: "上网", files: "写文件", personal: "联系人、位置、密码等个人信息", commands: "运行命令" }; // i18n-ignore: keys for t()

  // ---- Skill share codes: one skill as text, signed with this phone's key (ShareSignature.kt) ----
  const skillCodePrefix = "AW-SKILL-1.";
  function fromBase64Url(body) {
    const binary = atob(body.replace(/-/g, "+").replace(/_/g, "/"));
    return new TextDecoder().decode(Uint8Array.from(binary, (char) => char.charCodeAt(0)));
  }
  function skillCode(skill) {
    // Chunks keep String.fromCharCode under the argument limit for a large SKILL.md.
    const bytes = new TextEncoder().encode(JSON.stringify(skill));
    let binary = "";
    for (let index = 0; index < bytes.length; index += 8192) binary += String.fromCharCode(...bytes.subarray(index, index + 8192));
    const body = btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    const signed = nativeResult("signShareCode", `${skillCodePrefix}${body}`);
    return `${skillCodePrefix}${body}.${signed.public_key}.${signed.signature}`;
  }
  /** The skill in a code, and who signed it ({fingerprint, own}). Refuses changed codes. */
  function readSkillCode(text) {
    const code = String(text || "").replace(/\s+/g, "");
    const at = code.indexOf(skillCodePrefix);
    if (at < 0) throw new Error(t("这不是技能的分享码"));
    const [body, key, signature] = code.slice(at + skillCodePrefix.length).split(".");
    if (!body || !key || !signature) throw new Error(t("分享码不完整或被改动过"));
    if (typeof native?.verifyShareCode !== "function") throw new Error(t("这里核对不了签名：请在手机上的 App 里导入"));
    const check = JSON.parse(native.verifyShareCode(`${skillCodePrefix}${body}`, signature, key) || "{}");
    if (!check.valid) throw new Error(t("签名对不上：分享码在签名后被改动过"));
    let own = false;
    try { own = JSON.parse(native.shareIdentity?.() || "{}").public_key === key; } catch {}
    const skill = JSON.parse(fromBase64Url(body));
    if (!skill || typeof skill.name !== "string" || !skill.files || typeof skill.files["SKILL.md"] !== "string") throw new Error(t("分享码里没有技能"));
    return { skill, signer: { fingerprint: check.fingerprint, own } };
  }
  // The same list of known signers as shortcut share codes (87-shortcuts.js).
  function knownSigner(fingerprint) {
    try { return JSON.parse(localStorage.getItem("agent-share-authors-v1") || "{}")[fingerprint] || null; } catch { return null; }
  }
  function rememberSigner(fingerprint, name) {
    try {
      const known = JSON.parse(localStorage.getItem("agent-share-authors-v1") || "{}");
      if (!known[fingerprint]) known[fingerprint] = { name: String(name).slice(0, 40), at: Date.now() };
      localStorage.setItem("agent-share-authors-v1", JSON.stringify(known));
    } catch { /* Only a convenience. */ }
  }
  let sharedSigner = null;
  async function skillsJob(job, message) {
    if (message) status("skillsStatus", message);
    for (let attempt = 0; attempt < 300 && !closed; attempt++) {
      await new Promise((resolve) => window.setTimeout(resolve, 700));
      const value = await ui.apiJson(`/mobile/skills/job?id=${encodeURIComponent(job.job)}`);
      if (value.state === "running") continue;
      if (value.state === "failed") throw new Error(skillError(value.error) || t("操作失败"));
      return value.result;
    }
    throw new Error(t("等待超时，请稍后刷新"));
  }
  function showSkillsPreview(preview) {
    skillsPreview = preview;
    $("skillsPreview").hidden = !preview;
    if (!preview) return;
    $("skillsPreviewTitle").textContent = preview.replaces
      ? t("更新「{0}」：{1} → {2}", preview.name, skillVersion(preview.replaces.version), skillVersion(preview.version))
      : t("安装「{0}」{1}（{2} 个技能）", preview.name, skillVersion(preview.version), preview.skills.length);
    const signer = preview.source?.kind === "shared" ? sharedSigner : null;
    const known = signer && !signer.own ? knownSigner(signer.fingerprint) : null;
    const mentions = (preview.mentions || []).map((kind) => t(skillMentionLabels[kind] || kind));
    $("skillsPreviewSource").textContent = [preview.official ? "" : t("非官方技能，没有经过本项目测试。请确认来源可信、每个技能的用途都符合预期再安装。"),
      signer ? (signer.own ? t("签名：你自己的") : known ? t("签名：指纹 {0}，你导入过这个人的「{1}」", signer.fingerprint, known.name)
        : t("签名：指纹 {0}，第一次见到。可以请对方在「可复用流程」页看自己的指纹，核对一致再装", signer.fingerprint)) : "",
      mentions.length ? t("说明里提到：{0}。技能本身不执行操作，AI 的每一步仍按你的确认规则进行。", mentions.join(t("、"))) : "",
      skillSource(preview.source), preview.description].filter(Boolean).join("\n");
    $("skillsPreviewList").replaceChildren(...preview.skills.map((skill) => row(skill.name, skill.description)));
    $("skillsPreview").scrollIntoView({ block: "nearest" });
  }
  let skillsOfficialAsked = false;
  function renderOfficial(info, repo) {
    const button = $("btnSkillsOfficial");
    button.hidden = true;
    if (!info) { status("skillsOfficialStatus", t("读取中...")); return; }
    $("skillsOfficialList").replaceChildren(...(info.skills || []).map((skill) => {
      const element = row(skill.name, skill.description); element.classList.add("management-row-child"); return element;
    }));
    if (!info.available) {
      status("skillsOfficialStatus", info.installed_version
        ? t("已装 {0}（随应用预装），有新版本时会在这里更新", skillVersion(info.installed_version))
        : t("官方技能包还在准备中（github.com/{0} 还没有发布）", info.repo || repo));
      return;
    }
    const count = (info.skills || []).length;
    status("skillsOfficialStatus", info.installed_version
      ? info.update_available ? t("已安装 {0}，有新版本 {1}", info.installed_version, info.version) : t("已安装 {0}，是最新版本", info.installed_version)
      : count ? t("最新版本 {0}，共 {1} 个技能，都经过真机测试", info.version, count) : t("最新版本 {0}", info.version));
    button.hidden = !!info.installed_version && !info.update_available;
    $("skillsOfficialAction").textContent = info.installed_version ? t("更新到 {0}", info.version) : t("安装官方技能");
  }
  async function refreshOfficial(isCurrent, refresh) {
    try {
      const info = await skillsJob(await post("/mobile/skills/official", { refresh }), "");
      if (isCurrent()) renderOfficial(info);
    } catch (error) { if (isCurrent()) status("skillsOfficialStatus", t("读取官方技能失败：{0}", skillError(error.message)), true); }
  }
  async function skills(isCurrent = () => true, value = null) {
    value = value || await ui.apiJson("/mobile/skills");
    if (!isCurrent()) return;
    renderOfficial(value.official, value.official_repo);
    if (!skillsOfficialAsked && !(value.jobs || []).some((job) => job.state === "running")) {
      skillsOfficialAsked = true;
      void refreshOfficial(isCurrent, false);
    }
    $("skillsList").replaceChildren();
    for (const pack of value.packs || []) {
      const update = pack.update?.available ? t("\n有新版本 {0}", skillVersion(pack.update.version)) : pack.update?.error ? t("\n检查更新失败：{0}", skillError(pack.update.error)) : "";
      const mine = pack.source?.kind === "local";
      const origin = pack.official ? t("官方") : mine ? t("AI 按你的要求保存的技能，只在这台手机上") : t("非官方 · 未经测试");
      const item = row(mine ? pack.name : `${pack.name} ${skillVersion(pack.version)}`,
        mine ? origin : `${origin} · ${skillSource(pack.source)}${update}`);
      const toggle = document.createElement("input"); toggle.type = "checkbox"; toggle.checked = pack.enabled !== false; toggle.setAttribute("aria-label", t("启用 {0}", pack.name));
      toggle.addEventListener("change", async () => {
        toggle.disabled = true;
        try { await skills(isCurrent, await post("/mobile/skills/enable", { pack_id: pack.id, enabled: toggle.checked })); }
        catch (error) { toggle.checked = !toggle.checked; status("skillsStatus", skillError(error.message), true); }
        finally { if (toggle.isConnected) toggle.disabled = false; }
      });
      item.append(toggle);
      if (pack.update?.available) action(item, "download", t("更新到 {0}", skillVersion(pack.update.version)), async () => {
        const record = await skillsJob(await post("/mobile/skills/update", { pack_id: pack.id }), t("正在下载新版本…"));
        await skills(isCurrent);
        status("skillsStatus", t("已更新到 {0}", skillVersion(record?.version)));
      });
      action(item, "trash-2", t("删除技能包"), async () => {
        if (!window.confirm(t("删除技能包「{0}」？", pack.name))) return;
        await skills(isCurrent, await post("/mobile/skills/remove", { pack_id: pack.id }));
      });
      $("skillsList").append(item);
      const disabled = new Set(pack.disabled_skills || []);
      for (const skill of pack.skills || []) {
        const child = row(skill.name, skill.description);
        child.classList.add("management-row-child");
        const box = document.createElement("input"); box.type = "checkbox"; box.checked = !disabled.has(skill.id); box.disabled = pack.enabled === false;
        box.setAttribute("aria-label", t("启用 {0}", skill.name));
        box.addEventListener("change", async () => {
          box.disabled = true;
          try { await skills(isCurrent, await post("/mobile/skills/enable", { pack_id: pack.id, skill_id: skill.id, enabled: box.checked })); }
          catch (error) { box.checked = !box.checked; status("skillsStatus", skillError(error.message), true); }
        });
        child.append(box);
        if (skill.kind !== "toml" && typeof native?.signShareCode === "function") action(child, "share-2", t("分享技能"), async () => {
          const exported = await post("/mobile/skills/export", { pack_id: pack.id, skill_id: skill.id })
            .catch((error) => { throw new Error(skillError(error.message)); });
          const code = skillCode(exported);
          native.copyToClipboard?.(code);
          native.shareText?.(t("技能「{0}」", exported.name), code);
          status("skillsStatus", t("分享码已复制：对方在「技能 → 导入其他技能 → 粘贴分享码」里导入"));
        });
        if (mine) action(child, "trash-2", t("删除技能"), async () => {
          if (!window.confirm(t("删除技能「{0}」？", skill.name))) return;
          await skills(isCurrent, await post("/mobile/skills/delete-skill", { skill_id: skill.id }));
        });
        $("skillsList").append(child);
      }
    }
    const running = (value.jobs || []).some((job) => job.state === "running");
    if (!running) status("skillsStatus", (value.packs || []).length ? t("已安装 {0} 个技能包，{1} 个技能启用中", value.packs.length, (value.catalog || []).length) : t("还没有安装技能包"));
  }
  async function extensions(isCurrent = () => true) {
    const sessionId = ui.context().sessionId;
    if (!sessionId) throw new Error(t("请先选择会话"));
    const current = () => isCurrent() && ui.context().sessionId === sessionId;
    const value = await ui.apiJson(`/mobile/extensions?session_id=${encodeURIComponent(sessionId)}`);
    if (!current()) return;
    async function decide(path, fields) {
      if (!current()) { await extensions(); return; }
      await post(path, { ...fields, session_id: sessionId });
      if (current()) await extensions(isCurrent);
    }
    $("extensionsList").replaceChildren();
    for (const extension of value.extensions || []) {
      const item = row(extension.identifier, `${extension.kind} · ${stateNames[extension.status] || extension.status}\n${(extension.command || []).join(" ")}\n${extension.config_source || ""}`);
      if (extension.status !== "approved") {
        action(item, "check", t("批准此配置"), () => decide("/mobile/extensions/resolve", { request_id: extension.request_id, digest: extension.digest, allowed: true }));
        action(item, "x", t("拒绝此配置"), () => decide("/mobile/extensions/resolve", { request_id: extension.request_id, digest: extension.digest, allowed: false }));
      } else action(item, "shield", t("撤销授权"), () => decide("/mobile/extensions/revoke", { request_id: extension.request_id, digest: extension.digest }));
      $("extensionsList").append(item);
    }
    $("btnExtensionsRestart").hidden = !value.restart_required;
    $("btnExtensionsRestart").disabled = ui.context().activeTask || typeof native?.restartEngine !== "function";
    status("extensionsStatus", value.restart_required ? t("配置已保存，等待重启引擎") : value.extensions?.length ? "" : t("没有配置扩展"));
  }
  // ---- Memory: short notes about the user shared by every conversation ----
  let memoryEditing = null;
  let memoryLimits = { max_items: 30, max_chars: 200, prompt_budget_chars: 2000, auto_saves_per_task: 3 };
  function memoryMessage(error) {
    const text = String(error?.message || error || "");
    if (/already remembered/i.test(text)) return t("已经有一条相似的记忆了");
    if (/memory is full/i.test(text)) return t("记忆已满（{0} 条），请先删除不需要的", memoryLimits.max_items);
    if (/passwords, keys/i.test(text)) return t("记忆里不能保存密码、密钥、验证码或证件、卡号");
    if (/at most \d+ characters/i.test(text)) return t("每条记忆最多 {0} 字，请只写一件事", memoryLimits.max_chars);
    return text || t("操作失败");
  }
  function stopMemoryEdit() {
    memoryEditing = null;
    $("memoryContent").value = "";
    $("memoryTopic").value = "";
    $("memoryFormLabel").textContent = t("添加一条记忆");
    $("memorySubmitLabel").textContent = t("添加");
    $("btnCancelMemoryEdit").hidden = true;
  }
  // The Memory page: what the user is looking for, and the last list it showed.
  const memoryFilter = { query: "", topic: "" };
  let memoryValue = null;
  const memoryTopicNames = { profile: "个人信息", preferences: "偏好习惯", work: "工作", life: "生活", people: "家人朋友", projects: "项目", other: "其他" }; // i18n-ignore: keys for t()
  function memoryTopicLabel(topic) { return t(memoryTopicNames[topic] || memoryTopicNames.other); }
  // Like the engine's search: each word, and two-character pieces of Chinese words.
  function memoryMatches(item, query) {
    const fold = (text) => String(text || "").normalize("NFKC").toLowerCase().replace(/[\s\p{P}]/gu, "");
    const words = String(query || "").split(/\s+/).map(fold).filter(Boolean);
    if (!words.length) return true;
    const text = fold(item.content) + fold(memoryTopicLabel(item.topic));
    return words.some((word) => text.includes(word)
      || (/[\u4e00-\u9fff]/.test(word) && word.length > 2 && [...word].slice(0, -1).some((_, index) => text.includes(word.slice(index, index + 2)))));
  }
  async function memory(isCurrent = () => true, value = null) {
    const fresh = !value;
    value = value || await ui.apiJson("/mobile/memory");
    if (!isCurrent()) return;
    memoryLimits = { ...memoryLimits, ...(value.limits || {}) };
    $("memoryEnabledToggle").checked = value.enabled !== false;
    $("memoryAutoToggle").checked = value.auto !== false;
    $("memoryAutoToggle").disabled = value.enabled === false;
    $("memoryContent").maxLength = memoryLimits.max_chars;
    $("memoryHint").textContent = t("最多 {0} 条，每条不超过 {1} 字，按主题分类。对话时只带上最新的记忆（约 {2} 字以内），更早的由 AI 按需搜索；AI 每次任务最多自动记 {3} 条，相似的内容不会重复记，密码、验证码、证件和卡号一律不记。", memoryLimits.max_items, memoryLimits.max_chars, memoryLimits.prompt_budget_chars, memoryLimits.auto_saves_per_task);
    const items = Array.isArray(value.items) ? value.items : [];
    memoryValue = value;
    $("memoryCounter").textContent = `${items.length}/${memoryLimits.max_items}`;
    // Topic chips with counts; the chosen one (and the search words) narrow the list.
    const counts = value.topics || {};
    if (memoryFilter.topic && !counts[memoryFilter.topic]) memoryFilter.topic = "";
    $("memoryTopics").replaceChildren(...[["", t("全部"), items.length], ...Object.entries(counts).map(([key, count]) => [key, memoryTopicLabel(key), count])]
      .map(([key, label, count]) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "memory-topic";
        chip.textContent = `${label} ${count}`;
        chip.setAttribute("aria-pressed", String(memoryFilter.topic === key));
        chip.addEventListener("click", () => { memoryFilter.topic = key; memory(undefined, memoryValue); });
        return chip;
      }));
    $("memoryTopics").hidden = items.length < 2;
    $("memorySearch").parentElement.hidden = items.length < 2;
    const shown = items.filter((item) => (!memoryFilter.topic || item.topic === memoryFilter.topic) && memoryMatches(item, memoryFilter.query));
    $("memoryList").replaceChildren();
    for (const item of shown) {
      const when = item.updated_at ? new Date(item.updated_at).toLocaleString() : "";
      const element = row(item.content, `${memoryTopicLabel(item.topic)} · ${item.source === "auto" ? t("AI 记的") : t("你添加的")}${when ? ` · ${when}` : ""}`);
      element.classList.add("memory-row");
      action(element, "pencil", t("编辑"), () => {
        memoryEditing = item.id;
        $("memoryContent").value = item.content;
        $("memoryTopic").value = item.topic || "";
        $("memoryFormLabel").textContent = t("修改记忆");
        $("memorySubmitLabel").textContent = t("保存修改");
        $("btnCancelMemoryEdit").hidden = false;
        $("memoryContent").focus();
      });
      action(element, "trash-2", t("删除"), async () => {
        if (!window.confirm(t("删除这条记忆？"))) return;
        try { await memory(undefined, await post("/mobile/memory/delete", { id: item.id })); }
        catch (error) { throw new Error(memoryMessage(error)); }
        if (memoryEditing === item.id) stopMemoryEdit();
      });
      $("memoryList").append(element);
    }
    if (!items.length) {
      $("memoryList").append(row(t("还没有记忆"), value.enabled !== false && value.auto !== false
        ? t("聊天时 AI 会记下对以后有用的信息，你也可以在上面自己添加。") : t("你可以在上面自己添加。")));
    } else if (!shown.length) {
      $("memoryList").append(row(t("没有找到相关记忆"), t("换个说法，或者选「全部」看看。")));
    }
    $("btnClearMemory").disabled = !items.length;
    status("memoryStatus", value.enabled === false ? t("记忆已关闭：对话中不会使用，AI 也不会保存") : "");
    if (fresh) await appNotes(isCurrent).catch((error) => { if (isCurrent()) status("appNotesStatus", error.message || t("操作失败"), true); });
  }

  // ---- App notes: what earlier tasks learned in each app (mobile_app_notes) ----
  async function appNotes(isCurrent = () => true, value = null) {
    value = value || await ui.apiJson("/mobile/app-notes");
    if (!isCurrent()) return;
    $("appNotesToggle").checked = value.enabled !== false;
    $("appNotesList").replaceChildren();
    const apps = Array.isArray(value.apps) ? value.apps : [];
    for (const app of apps) {
      const taps = Array.isArray(app.taps) ? app.taps : [];
      const parts = [];
      if (app.notes?.length) parts.push(t("{0} 条说明", app.notes.length));
      if (taps.length) parts.push(t("{0} 个按钮", taps.length));
      const element = row(app.app || app.package_name, [app.app ? app.package_name : "", parts.join(" · ")].filter(Boolean).join("\n"));
      action(element, "trash-2", t("清除这个应用的经验"), async () => {
        if (!window.confirm(t("清除「{0}」的全部经验？", app.app || app.package_name))) return;
        await appNotes(undefined, await post("/mobile/app-notes", { action: "forget_app", package_name: app.package_name }));
      });
      $("appNotesList").append(element);
      for (const note of app.notes || []) {
        const child = row(note.text, note.saved_ms ? new Date(note.saved_ms).toLocaleString() : "");
        child.classList.add("management-row-child");
        action(child, "trash-2", t("删除"), async () => {
          await appNotes(undefined, await post("/mobile/app-notes", { action: "delete_note", package_name: app.package_name, id: note.id }));
        });
        $("appNotesList").append(child);
      }
    }
    status("appNotesStatus", value.enabled === false ? t("已关闭：不再记录，任务里也不会用到") : apps.length ? "" : t("还没有记下任何应用的经验"));
  }

  // ---- Knowledge base: the user's own documents, searched while they chat ----
  let knowledgePoll = null;
  let knowledgeUploading = false;
  const knowledgeStates = { queued: t("排队中"), indexing: t("正在读取"), ready: t("可用"), failed: t("添加失败") };
  function knowledgeMessage(error) {
    const text = String(error?.message || error || "");
    if (/unsupported document type/i.test(text)) return t("不支持这种文件，请添加 PDF、Word、Excel、EPUB、网页、Markdown 或文本文件");
    if (/larger than \d+ MiB/i.test(text)) return t("文件超过 100 MiB，请拆分后再添加");
    if (/knowledge base is full/i.test(text)) return t("知识库已满（300 份），请先删除不需要的文档");
    if (/file is empty/i.test(text)) return t("文件是空的");
    if (/of this knowledge base is being indexed/i.test(text)) return t("这个知识库里有文档正在读取，完成后再删除");
    if (/being indexed/i.test(text)) return t("这份文档正在读取，完成后再删除");
    if (/knowledge base named .* already exists/i.test(text)) return t("已有同名的知识库");
    if (/at most \d+ knowledge bases/i.test(text)) return t("知识库最多 30 个");
    if (/knowledge base name is required/i.test(text)) return t("请填写知识库名称");
    if (/knowledge base name has at most/i.test(text)) return t("知识库名称最多 40 个字");
    if (/default knowledge base cannot be removed/i.test(text)) return t("默认知识库不能删除");
    if (/no such knowledge base|there is no knowledge base/i.test(text)) return t("这个知识库已不存在，请刷新后再试");
    if (/turned off/i.test(text)) return t("知识库已关闭");
    // Saving a web page.
    if (/enter a web address/i.test(text)) return t("请填写网页地址");
    if (/web address is too long/i.test(text)) return t("网页地址太长");
    if (/not a web page or text/i.test(text)) return t("这个链接不是网页，请下载文件后再添加");
    if (/this page is empty/i.test(text)) return t("这个网页是空的");
    let match;
    if ((match = text.match(/^cannot save this page: (.*)$/))) {
      const reason = match[1];
      if (/private, local, reserved/.test(reason)) return t("只能保存公开网站的网页");
      if (/DNS resolution/.test(reason)) return t("找不到这个网站，请检查地址和网络");
      if (/requires an absolute HTTPS URL|permits only HTTPS port/.test(reason)) return t("只能保存 https 网页");
      if (/cross-origin redirects|redirect limit/.test(reason)) return t("这个链接跳转到了别的网站，请打开最终的网页后再分享");
      if (/media type is unsupported|charset is unsupported|compressed responses/.test(reason)) return t("这个链接不是可以保存的网页");
      const status = reason.match(/returned HTTP status (\d+)/);
      if (status) return t("网站返回错误 {0}", status[1]);
      if (/timed out/.test(reason)) return t("连接网站超时，请稍后再试");
      return t("无法保存这个网页：{0}", reason);
    }
    if ((match = text.match(/line (\d+) needs at least two words/))) return t("第 {0} 行至少要有两个词", match[1]);
    if ((match = text.match(/line (\d+) has a single character/))) return t("第 {0} 行有单个字，请写完整的词", match[1]);
    if ((match = text.match(/line (\d+) has a word longer/))) return t("第 {0} 行有超过 20 个字的词", match[1]);
    if (/at most \d+ synonym groups/.test(text)) return t("同义词最多 200 组");
    return text || t("操作失败");
  }
  // Reasons a document could not be read, and what was left out, as the engine reports them.
  function knowledgeText(text) {
    const value = String(text || "");
    let match;
    if ((match = value.match(/^(\d+) of (\d+) pages have no readable text \(blank or unrecognizable pages\).*?skipped: (.*)$/))) return t("{0}/{1} 页是空白页或认不出文字，已跳过：第 {2} 页", match[1], match[2], match[3]);
    if ((match = value.match(/^(\d+) of (\d+) pages have no readable text.*?skipped: (.*)$/))) return t("{0}/{1} 页没有可读取的文字（扫描页、空白页或无法识别的字体），已跳过：第 {2} 页", match[1], match[2], match[3]);
    if ((match = value.match(/^only the first ([\d,]+) characters were added/))) return t("只收录了前 {0} 个字符，其余部分请拆分文档后再添加", match[1]);
    if ((match = value.match(/^(\d+) scanned pages were read with on-device text recognition/))) return t("{0} 页扫描页用手机上的文字识别读取，人名和数字可能有识别错误", match[1]);
    if ((match = value.match(/^only the first (\d+) scanned pages were recognized/))) return t("只识别了前 {0} 页扫描页", match[1]);
    if ((match = value.match(/^on-device text recognition stopped: (.*)$/))) return t("文字识别中途停止：{0}", match[1]);
    if (/scanned PDFs need OCR|scanned PDFs need on-device text recognition/.test(value)) return t("没有读到文字。扫描版 PDF 需要文字识别，这台设备上不可用");
    if (/on-device text recognition found none/.test(value)) return t("没有读到文字，文字识别也没有认出内容");
    if (/^no text was found/.test(value)) return t("文档里没有读到文字");
    if (/password protected/.test(value)) return t("PDF 有密码保护，请先另存一份没有密码的副本");
    if (/^cannot open this PDF/.test(value)) return t("无法打开这个 PDF，文件可能已损坏");
    if (/looks binary/.test(value)) return t("这个文件不是文本格式");
    if (/EPUB/.test(value)) return t("无法读取这个 EPUB，文件可能已损坏");
    if (/interrupted/.test(value)) return t("读取被中断，请重新添加");
    if (/^could not read this document/.test(value)) return t("无法读取这份文档，文件可能已损坏");
    return value;
  }
  function knowledgeDetails(document) {
    // A saved web page also shows where it came from.
    const address = document.origin === "web" && document.origin_path ? `\n${document.origin_path}` : "";
    if (document.state === "indexing") return t("正在读取 {0}%", Math.round((document.progress || 0) * 100)) + address;
    if (document.state === "queued") return t("排队中") + address;
    if (document.state === "failed") return t("添加失败：{0}", knowledgeText(document.error)) + address;
    const parts = [t("{0} 段", document.passages)];
    if (document.pages) parts.push(t("{0} 页", document.pages));
    parts.push(document.size_bytes < 1024 ** 2 ? `${Math.max(1, Math.round(document.size_bytes / 1024))} KB` : bytes(document.size_bytes));
    const lines = [parts.join(" · ") + address];
    for (const warning of document.warnings || []) lines.push(knowledgeText(warning));
    return lines.join("\n");
  }
  // Knowledge bases ("collections"): the default one has no name until the user gives it one.
  let knowledgeCollections = [];
  let knowledgeFilter = "";  // the knowledge base shown on the page; "" shows all of them
  const knowledgeLabel = (collection) => collection?.name || (collection?.id === "default" ? t("默认") : String(collection?.id || ""));
  function knowledgeBases(collections) {
    $("knowledgeBaseList").replaceChildren();
    for (const collection of collections) {
      const element = row(knowledgeLabel(collection), t("{0} 份文档", collection.documents || 0));
      element.classList.add("knowledge-base-row");
      const toggle = document.createElement("label");
      toggle.className = "knowledge-base-default";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = collection.default_on !== false;
      input.addEventListener("change", async () => {
        input.disabled = true;
        try { await knowledge(undefined, await post("/mobile/knowledge/collections/default", { id: collection.id, default_on: input.checked })); }
        catch (error) { input.checked = !input.checked; status("knowledgeStatus", knowledgeMessage(error), true); }
        finally { if (input.isConnected) input.disabled = false; }
      });
      toggle.append(input, t("新对话默认使用"));
      action(element, "pencil", t("重命名"), async () => {
        const name = window.prompt(t("知识库名称"), knowledgeLabel(collection));
        if (name === null || !name.trim() || name.trim() === knowledgeLabel(collection)) return;
        try { await knowledge(undefined, await post("/mobile/knowledge/collections/rename", { id: collection.id, name: name.trim() })); }
        catch (error) { throw new Error(knowledgeMessage(error)); }
      });
      if (collection.id !== "default") {
        action(element, "trash-2", t("删除"), async () => {
          const question = collection.documents
            ? t("删除知识库“{0}”和其中的 {1} 份文档？", knowledgeLabel(collection), collection.documents)
            : t("删除知识库“{0}”？", knowledgeLabel(collection));
          if (!window.confirm(question)) return;
          try { await knowledge(undefined, await post("/mobile/knowledge/collections/delete", { id: collection.id })); }
          catch (error) { throw new Error(knowledgeMessage(error)); }
        });
      }
      element.append(toggle);
      $("knowledgeBaseList").append(element);
    }
  }
  function knowledgeFilterOptions(collections) {
    const select = $("knowledgeFilter");
    select.hidden = collections.length < 2;
    if (!collections.some((collection) => collection.id === knowledgeFilter)) knowledgeFilter = "";
    select.replaceChildren();
    for (const [value, label] of [["", t("全部知识库")], ...collections.map((collection) => [collection.id, knowledgeLabel(collection)])]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.append(option);
    }
    select.value = knowledgeFilter;
    const target = collections.find((collection) => collection.id === knowledgeFilter);
    $("knowledgeAddLabel").textContent = target && collections.length > 1 ? t("添加到“{0}”", knowledgeLabel(target)) : t("添加文档");
  }
  function knowledgeMove(document) {
    // Moving a document to another knowledge base: its own small picker.
    const select = window.document.createElement("select");
    select.className = "knowledge-move";
    select.setAttribute("aria-label", t("“{0}”所在的知识库", document.title));
    for (const collection of knowledgeCollections) {
      const option = window.document.createElement("option");
      option.value = collection.id;
      option.textContent = knowledgeLabel(collection);
      select.append(option);
    }
    select.value = document.collection_id || "default";
    select.addEventListener("change", async () => {
      select.disabled = true;
      try {
        await knowledge(undefined, await post("/mobile/knowledge/move", { id: document.id, collection_id: select.value }));
        status("knowledgeStatus", t("已把“{0}”移到“{1}”", document.title, knowledgeLabel(knowledgeCollections.find((item) => item.id === select.value))));
      } catch (error) {
        select.value = document.collection_id || "default";
        status("knowledgeStatus", knowledgeMessage(error), true);
      } finally { if (select.isConnected) select.disabled = false; }
    });
    return select;
  }
  async function knowledge(isCurrent = () => true, value = null) {
    value = value || await ui.apiJson("/mobile/knowledge");
    if (!isCurrent()) return;
    $("knowledgeEnabledToggle").checked = value.enabled !== false;
    $("knowledgeAutoToggle").checked = value.auto !== false;
    $("knowledgeAutoToggle").disabled = value.enabled === false;
    $("knowledgeSynonymsHint").textContent = t("换个说法也能找到：已内置 {0} 组常用说法，比如“房租”和“租金”、“坏了”和“维修”。也可以加上你自己的，每行一组，词之间用空格或逗号隔开。", value.builtin_synonym_groups || 0);
    if (document.activeElement !== $("knowledgeSynonyms")) $("knowledgeSynonyms").value = value.synonyms || "";
    knowledgeCollections = Array.isArray(value.collections) ? value.collections : [];
    knowledgeBases(knowledgeCollections);
    knowledgeFilterOptions(knowledgeCollections);
    const several = knowledgeCollections.length > 1;
    const allDocuments = Array.isArray(value.documents) ? value.documents : [];
    const documents = knowledgeFilter ? allDocuments.filter((document) => (document.collection_id || "default") === knowledgeFilter) : allDocuments;
    const ready = allDocuments.filter((document) => document.state === "ready").length;
    const shownReady = documents.filter((document) => document.state === "ready").length;
    $("knowledgeCounter").textContent = documents.length ? t("{0} 份可用", shownReady) : "";
    $("menuKnowledgeSummary").textContent = ready ? t("{0} 份文档", ready) : t("让 AI 查阅你的文档");
    $("knowledgeList").replaceChildren();
    for (const document of documents) {
      const element = row(document.title, knowledgeDetails(document));
      element.classList.add("knowledge-row");
      element.dataset.state = document.state;
      if (several && document.state !== "indexing") element.querySelector(".management-row-body").append(knowledgeMove(document));
      if (document.state !== "indexing") {
        action(element, "pencil", t("重命名"), async () => {
          const title = window.prompt(t("文档名称"), document.title);
          if (title === null || !title.trim() || title.trim() === document.title) return;
          try { await knowledge(undefined, await post("/mobile/knowledge/rename", { id: document.id, title: title.trim() })); }
          catch (error) { throw new Error(knowledgeMessage(error)); }
        });
        action(element, "trash-2", t("删除"), async () => {
          if (!window.confirm(t("从知识库删除“{0}”？", document.title))) return;
          try { await knowledge(undefined, await post("/mobile/knowledge/delete", { id: document.id })); }
          catch (error) { throw new Error(knowledgeMessage(error)); }
        });
      }
      $("knowledgeList").append(element);
    }
    if (!documents.length) {
      $("knowledgeList").append(knowledgeFilter
        ? row(t("这个知识库还没有文档"), t("点“添加到…”，从手机里选择文件；也可以把其他知识库的文档移过来。"))
        : row(t("还没有文档"), t("点“添加文档”，从手机里选择文件。")));
    }
    if (!knowledgeUploading) {
      status("knowledgeStatus", value.enabled === false ? t("知识库已关闭：对话中不会使用") : "");
    }
    void knowledgeChip();
    const semanticBusy = knowledgeSemantic(value.semantic);
    window.clearTimeout(knowledgePoll);
    if (semanticBusy || allDocuments.some((document) => document.state === "queued" || document.state === "indexing")) {
      knowledgePoll = window.setTimeout(() => {
        if (!closed && !$("settingsKnowledge").hidden && !$("settingsOverlay").hidden) knowledge(isCurrent).catch(() => {});
      }, 1500);
    }
  }
  // Searching by meaning (mobile_semantic): the switch, the model download and how far the
  // passages are. Returns whether something is still under way (the page then looks again).
  function knowledgeSemantic(semantic) {
    const section = $("knowledgeSemanticSection");
    section.hidden = !semantic;
    if (!semantic) return false;
    $("knowledgeSemanticToggle").checked = semantic.enabled !== false;
    const download = semantic.download || {};
    const downloading = ["queued", "downloading", "verifying"].includes(download.state);
    $("btnKnowledgeSemanticDownload").hidden = semantic.installed || downloading || semantic.enabled === false;
    $("btnKnowledgeSemanticRemove").hidden = !semantic.installed;
    let text = "";
    if (semantic.enabled === false) text = t("已关闭：只按关键词检索");
    else if (downloading) text = t("正在下载模型：{0}%", Math.round((download.progress || 0) * 100));
    else if (!semantic.installed) text = download.error ? t("下载没有完成：{0}", localizeError(download.error)) : t("还没有下载模型：现在只按关键词检索");
    else if (semantic.error) text = t("暂时只能按关键词检索：{0}", localizeError(semantic.error));
    else if (semantic.vectors < semantic.passages) text = t("正在整理文档（{0}/{1} 段），完成前先按关键词检索", semantic.vectors, semantic.passages);
    else text = semantic.passages ? t("已就绪：{0} 段文字可以按意思检索", semantic.passages) : t("已就绪：添加文档后就能按意思检索");
    status("knowledgeSemanticStatus", text, !!semantic.error || (!semantic.installed && !!download.error && !downloading));
    return semantic.enabled !== false && (downloading || (semantic.installed && !semantic.error && semantic.vectors < semantic.passages));
  }
  async function uploadKnowledgeFiles(files) {
    if (!files.length || knowledgeUploading) return;
    knowledgeUploading = true;
    $("btnKnowledgeAdd").disabled = true;
    const failures = [];
    const duplicates = [];
    const target = knowledgeFilter;
    try {
      for (const [index, file] of files.entries()) {
        status("knowledgeStatus", t("正在上传 {0}（{1}/{2}）", file.name, index + 1, files.length));
        try {
          const into = target ? `&collection=${encodeURIComponent(target)}` : "";
          const added = await ui.apiJson(`/mobile/knowledge/upload?filename=${encodeURIComponent(file.name)}${into}`, {
            method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file,
          });
          if (added?.duplicate) duplicates.push(added);
        } catch (error) { failures.push(t("{0}：{1}", file.name, knowledgeMessage(error))); }
      }
    } finally {
      knowledgeUploading = false;
      $("btnKnowledgeAdd").disabled = false;
    }
    if (closed) return;
    await knowledge();
    if (failures.length) status("knowledgeStatus", failures.join("\n"), true);
    else if (duplicates.length === 1 && knowledgeCollections.length > 1) {
      const where = knowledgeCollections.find((collection) => collection.id === (duplicates[0].collection_id || "default"));
      status("knowledgeStatus", t("这份文档已经在知识库“{0}”里了", knowledgeLabel(where)));
    }
    else if (duplicates.length) status("knowledgeStatus", t("{0} 份文档已经在知识库里了", duplicates.length));
    else status("knowledgeStatus", t("已添加，正在读取文档内容"));
  }
  async function searchKnowledge() {
    const query = $("knowledgeQuery").value.trim();
    $("knowledgeResults").replaceChildren();
    if (!query) return;
    const value = await post("/mobile/knowledge/search", { query, ...(knowledgeFilter ? { collections: [knowledgeFilter] } : {}) });
    const results = Array.isArray(value.results) ? value.results : [];
    for (const result of results) {
      const where = [result.document, result.page ? t("第 {0} 页", result.page) : "", result.section || "",
        result.match === "meaning" ? t("意思相近") : ""].filter(Boolean).join(" · ");
      const element = row(where, result.passage);
      element.classList.add("knowledge-result");
      $("knowledgeResults").append(element);
    }
    if (!results.length) $("knowledgeResults").append(row(t("没有找到相关段落"), t("换几个文档里会出现的关键词试试。")));
  }

  // ---- The knowledge bases of the open conversation: the composer chip and its page ----
  let chipRequest = 0;
  let conversationSelection = null;
  function renderKnowledgeChip(value) {
    const chip = $("btnKnowledgeChip");
    const available = Array.isArray(value.available) ? value.available : [];
    const chosen = new Set(Array.isArray(value.collections) ? value.collections : []);
    const used = available.filter((collection) => chosen.has(collection.id));
    // With a single knowledge base the chip only appears once a conversation chose otherwise.
    chip.hidden = value.enabled === false || (available.length < 2 && !value.explicit);
    $("knowledgeChipLabel").textContent = !used.length ? t("不用知识库")
      : used.length === available.length && available.length > 1 ? t("全部知识库")
      : used.length === 1 ? knowledgeLabel(used[0]) : t("{0} 个知识库", used.length);
    const title = t("本对话使用的知识库：{0}", used.length ? used.map(knowledgeLabel).join(t("、")) : t("无"));
    chip.title = title;
    chip.setAttribute("aria-label", title);
    chip.dataset.empty = String(!used.length);
    // A number only when the conversation leaves some knowledge bases out.
    $("knowledgeChipBadge").hidden = used.length === available.length;
    $("knowledgeChipBadge").textContent = String(used.length);
  }
  async function knowledgeChip() {
    const sessionId = ui.context().sessionId;
    const request = ++chipRequest;
    if (!sessionId) { $("btnKnowledgeChip").hidden = true; return; }
    let value;
    try { value = await ui.apiJson(`/mobile/knowledge/session?session_id=${encodeURIComponent(sessionId)}`); }
    catch { if (!closed && request === chipRequest) $("btnKnowledgeChip").hidden = true; return; }
    if (closed || request !== chipRequest || ui.context().sessionId !== sessionId) return;
    renderKnowledgeChip(value);
    if (!$("settingsConversationKnowledge").hidden && conversationSelection?.session_id === sessionId) await conversationKnowledge(undefined, value);
  }
  async function conversationKnowledge(isCurrent = () => true, value = null) {
    const sessionId = ui.context().sessionId;
    if (!sessionId) throw new Error(t("请先打开一个会话"));
    value = value || await ui.apiJson(`/mobile/knowledge/session?session_id=${encodeURIComponent(sessionId)}`);
    if (!isCurrent()) return;
    conversationSelection = value;
    renderKnowledgeChip(value);
    const chosen = new Set(value.collections || []);
    $("conversationKnowledgeList").replaceChildren();
    for (const collection of value.available || []) {
      const label = document.createElement("label");
      label.className = "toggle-row conversation-knowledge-row";
      const text = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = knowledgeLabel(collection);
      const count = document.createElement("small");
      count.textContent = t("{0} 份文档", collection.ready ?? collection.documents ?? 0);
      text.append(name, count);
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = chosen.has(collection.id);
      input.dataset.collection = collection.id;
      input.disabled = value.enabled === false;
      input.addEventListener("change", () => { void saveConversationKnowledge(); });
      label.append(text, input);
      $("conversationKnowledgeList").append(label);
    }
    $("btnConversationKnowledgeDefault").disabled = !value.explicit || value.enabled === false;
    status("conversationKnowledgeStatus", value.enabled === false ? t("知识库已关闭：对话中不会使用")
      : value.explicit ? "" : t("这个对话使用默认的知识库（在知识库页面可以设置哪些默认使用）"));
  }
  async function saveConversationKnowledge(collections) {
    const sessionId = conversationSelection?.session_id;
    if (!sessionId) return;
    const inputs = [...$("conversationKnowledgeList").querySelectorAll("input[type=checkbox]")];
    const chosen = collections === undefined ? inputs.filter((input) => input.checked).map((input) => input.dataset.collection) : collections;
    for (const input of inputs) input.disabled = true;
    try {
      await conversationKnowledge(undefined, await post("/mobile/knowledge/session", { session_id: sessionId, collections: chosen }));
      status("conversationKnowledgeStatus", t("已保存，从下一条消息开始生效"));
    } catch (error) {
      status("conversationKnowledgeStatus", knowledgeMessage(error), true);
      await conversationKnowledge().catch(() => {});
    }
  }

  // ---- Services: long-running programs the agent started (Android) ----
  let servicesPoll = null;
  const openServiceLogs = new Set();
  const serviceStates = { running: t("运行中"), exited: t("已结束"), failed: t("出错退出"), stopped: t("已停止"), interrupted: t("已中断") };
  const serviceReasons = { "engine stopped": t("引擎停止时一并停止"), "engine restarted": t("引擎重启时中断"), "stopped by the user": t("你停止了它"), "stopped by the agent": t("AI 停止了它"), restarting: t("正在重启") };
  function elapsed(value) {
    const start = Date.parse(value || "");
    if (!Number.isFinite(start)) return "";
    const minutes = Math.max(0, Math.floor((Date.now() - start) / 60000));
    return minutes < 60 ? t("{0} 分钟", minutes) : t("{0} 小时 {1} 分钟", Math.floor(minutes / 60), minutes % 60);
  }
  function serviceDetails(service) {
    const lines = [(service.argv || []).join(" ")];
    if (service.state === "running") lines.push(t("已运行 {0}", elapsed(service.started_at)));
    else {
      const code = service.state === "failed" && service.exit_code !== null && service.exit_code !== undefined ? t("退出码 {0}", service.exit_code) : "";
      const reason = String(service.reason || "").startsWith("autostart:") ? t("随引擎启动失败：{0}", service.reason.slice(10).trim()) : serviceReasons[service.reason] || "";
      lines.push([code, reason].filter(Boolean).join(" · "));
    }
    return lines.filter(Boolean).join("\n");
  }
  async function serviceLog(id, output) {
    const value = await ui.apiJson(`/mobile/services/logs?id=${encodeURIComponent(id)}&max_bytes=16384`);
    if (!output.isConnected) return;
    const following = output.scrollTop + output.clientHeight >= output.scrollHeight - 8;
    output.textContent = value.text || t("还没有输出");
    if (following) output.scrollTop = output.scrollHeight;
  }
  function openServiceUrl(url) {
    if (typeof native?.openExternal === "function") native.openExternal(url);
    else window.open(url, "_blank", "noopener");
  }
  async function services(isCurrent = () => true, value = null) {
    window.clearTimeout(servicesPoll);
    value = value || await ui.apiJson("/mobile/services");
    if (!isCurrent()) return;
    $("servicesKeepAwakeToggle").checked = value.keep_awake === true;
    $("menuServicesSummary").textContent = value.running ? t("{0} 个正在运行", value.running) : t("AI 启动的、一直运行的程序");
    const list = $("servicesList");
    const items = Array.isArray(value.services) ? value.services : [];
    const ids = new Set(items.map((service) => service.id));
    for (const element of [...list.children]) if (!ids.has(element.dataset.serviceId)) element.remove();
    for (const service of items) {
      let element = [...list.children].find((item) => item.dataset.serviceId === service.id);
      if (!element) {
        element = row(service.name);
        element.classList.add("service-row");
        element.dataset.serviceId = service.id;
        const actions = document.createElement("div");
        actions.className = "service-actions";
        element.append(actions);
        list.append(element);
      }
      element.dataset.state = service.state;
      const state = document.createElement("span");
      state.className = "service-state";
      state.textContent = serviceStates[service.state] || service.state;
      element.querySelector("strong").replaceChildren(`${service.name} · `, state);
      element.querySelector("small").textContent = serviceDetails(service);
      const signature = JSON.stringify([service.state, service.urls, service.autostart]);
      if (element.dataset.signature === signature) continue;
      element.dataset.signature = signature;
      const actions = element.querySelector(".service-actions");
      actions.replaceChildren();
      if (service.urls?.length) action(actions, "globe", t("在浏览器中打开 {0}", service.urls[0]), () => openServiceUrl(service.urls[0]));
      action(actions, "file-text", t("查看输出"), async () => {
        let output = element.querySelector(".management-output");
        if (output) { output.remove(); openServiceLogs.delete(service.id); return; }
        output = document.createElement("pre");
        output.className = "management-output";
        element.append(output);
        openServiceLogs.add(service.id);
        await serviceLog(service.id, output);
        output.scrollTop = output.scrollHeight;
      });
      if (service.state === "running") {
        action(actions, "square", t("停止"), async () => { await post("/mobile/services/stop", { id: service.id }); await services(); });
      } else {
        action(actions, "play", t("重新启动"), async () => { await post("/mobile/services/restart", { id: service.id }); await services(); });
        action(actions, "trash-2", t("删除"), async () => {
          if (!window.confirm(t("删除“{0}”和它的输出记录？", service.name))) return;
          openServiceLogs.delete(service.id);
          await services(undefined, await post("/mobile/services/remove", { id: service.id }));
        });
      }
      let autostart = element.querySelector(".service-autostart");
      if (!autostart) {
        autostart = document.createElement("label");
        autostart.className = "service-autostart";
        const box = document.createElement("input");
        box.type = "checkbox";
        const text = document.createElement("span");
        text.textContent = t("随引擎启动");
        autostart.append(box, text);
        element.insertBefore(autostart, element.querySelector(".management-output"));
        box.addEventListener("change", async () => {
          box.disabled = true;
          try { await post("/mobile/services/autostart", { id: service.id, enabled: box.checked }); }
          catch (error) { box.checked = !box.checked; status("servicesStatus", error.message, true); }
          finally { box.disabled = false; }
        });
      }
      autostart.querySelector("input").checked = service.autostart === true;
    }
    if (!items.length && !list.querySelector(".services-empty")) {
      const empty = row(t("还没有后台服务"), t("让 AI 运行一个网页服务、机器人或监听程序时，它会出现在这里。"));
      empty.classList.add("services-empty");
      list.append(empty);
    }
    for (const output of list.querySelectorAll(".management-output")) {
      const id = output.closest(".service-row")?.dataset.serviceId;
      if (id) serviceLog(id, output).catch(() => {});
    }
    status("servicesStatus", value.running ? t("{0} 个服务正在运行（最多 {1} 个）", value.running, value.max_running || 4) : "");
    servicesPoll = window.setTimeout(() => {
      if (!closed && !$("settingsServices").hidden && !$("settingsOverlay").hidden) services(isCurrent).catch((error) => status("servicesStatus", error.message, true));
    }, 3000);
  }

  // ---- Notification rules: tasks triggered by notifications from chosen apps (Android) ----
  $("btnNotificationRulesPage").hidden = typeof native?.getNotificationAccess !== "function";
  let notificationApps = null;
  const ruleLogStates = { started: t("已运行"), awaiting_confirmation: t("等你确认"), dismissed: t("已忽略"), cooldown: t("间隔太短，已跳过"), daily_limit: t("今天的次数已用完"), failed: t("启动失败") };
  function fillNotificationApps() {
    if (notificationApps) return;
    try { notificationApps = nativeResult("listApps").apps || []; } catch { notificationApps = []; }
    const select = $("notificationRuleApp");
    select.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = t("选择应用");
    select.append(placeholder);
    for (const app of notificationApps) {
      const option = document.createElement("option");
      option.value = app.package;
      option.textContent = app.label;
      select.append(option);
    }
    // Apps without a home-screen icon (some system and carrier apps) are entered by package name.
    const other = document.createElement("option");
    other.value = "__other__";
    other.textContent = t("其他应用（输入包名）");
    select.append(other);
  }
  async function notificationRules(isCurrent = () => true, value = null) {
    value = value || await ui.apiJson("/mobile/notification-rules");
    if (!isCurrent()) return;
    const access = nativeResult("getNotificationAccess");
    fillNotificationApps();
    $("notificationRulesToggle").checked = value.enabled === true;
    $("notificationAccessState").textContent = access.granted ? t("已开启") : t("未开启，点此到系统设置里开启");
    const list = $("notificationRuleList");
    list.replaceChildren();
    for (const rule of value.rules || []) {
      const details = [
        [t("来自 {0}", rule.app_label), rule.keywords?.length ? t("关键词：{0}", rule.keywords.join(t("、"))) : t("任何通知"), rule.confirm ? t("运行前先问我") : t("直接运行"), rule.enabled ? "" : t("已暂停")].filter(Boolean).join(" · "),
        rule.prompt,
      ].join("\n");
      const element = row(rule.name, details);
      element.classList.add("notification-rule-row");
      element.dataset.ruleId = rule.id;
      action(element, rule.enabled ? "pause" : "play", rule.enabled ? t("暂停这条规则") : t("启用这条规则"), async () => {
        await notificationRules(undefined, await post("/mobile/notification-rules/update", { id: rule.id, enabled: !rule.enabled }));
      });
      action(element, "trash-2", t("删除"), async () => {
        if (!window.confirm(t("删除规则“{0}”？", rule.name))) return;
        await notificationRules(undefined, await post("/mobile/notification-rules/delete", { id: rule.id }));
      });
      list.append(element);
    }
    if (!(value.rules || []).length) list.append(row(t("还没有规则"), t("在下面选一个应用，写下收到它的通知时要做什么。")));
    const log = $("notificationRuleLog");
    log.replaceChildren();
    for (const entry of (value.log || []).slice(0, 20)) {
      log.append(row(entry.rule_name, `${new Date(entry.at).toLocaleString()} · ${ruleLogStates[entry.status] || entry.status}`));
    }
    if (!(value.log || []).length) log.append(row(t("还没有触发记录")));
    status("notificationRulesStatus", value.enabled && !access.granted ? t("还没有通知使用权，规则不会触发") : "", value.enabled && !access.granted);
  }
  window.addEventListener("agent-global-entry-changed", () => {
    if (!closed && !$("settingsNotificationRules").hidden) notificationRules().catch((error) => status("notificationRulesStatus", error.message, true));
  });

  // ---- Global entry: floating ball, quick settings tile, launcher shortcuts (Android) ----
  $("btnGlobalEntryPage").hidden = typeof native?.getGlobalEntry !== "function";
  let ballPermissionAsked = false;
  async function globalEntry() {
    const value = nativeResult("getGlobalEntry");
    const on = value.floating_ball === true && value.overlay_permission === true;
    $("floatingBallToggle").checked = on;
    $("btnAddQuickTile").hidden = value.tile_request !== true;
    $("widgetPinSection").hidden = value.widget_pin !== true;
    const declined = ballPermissionAsked && !on;
    ballPermissionAsked = false;
    status("globalEntryStatus", declined ? t("没有获得“显示在其他应用上层”权限，悬浮球未开启") : "");
  }
  window.addEventListener("agent-global-entry-changed", () => {
    if (!closed && !$("settingsGlobalEntry").hidden) globalEntry().catch((error) => status("globalEntryStatus", error.message, true));
  });
  window.addEventListener("agent-tile-request", (event) => {
    const result = event.detail?.result;
    if (result === 2) status("globalEntryStatus", t("已添加到快捷设置"));
    else if (result === 1) status("globalEntryStatus", t("快捷设置里已经有“问 Agent”了"));
    else if (result === 0) status("globalEntryStatus", t("已取消"));
    else status("globalEntryStatus", t("无法自动添加，请从快捷开关的编辑页面手动拖入"), true);
  });

  // ---- Backup and restore (Android) ----
  // Interface settings worth carrying to another phone; drafts and session state are not.
  const backupStorageKeys = ["agent-mobile-preferences-v1", "agent-mobile-quick-tasks-v1", "agent-mobile-wallpaper-v1", "agent-mobile-runtime-v1"];
  $("btnBackupPage").hidden = typeof native?.createBackup !== "function";
  function backupSize(value) { return Number.isFinite(value) ? (value >= 1024 ** 2 ? `${(value / 1024 ** 2).toFixed(1)} MB` : `${Math.max(1, Math.round(value / 1024))} KB`) : ""; }
  async function backup() { status("backupStatus", ""); }
  window.addEventListener("agent-backup", (event) => {
    const detail = event.detail || {};
    const busy = ["creating", "saving", "restoring"].includes(detail.state);
    $("btnCreateBackup").disabled = busy;
    $("btnRestoreBackup").disabled = busy;
    if (detail.state === "creating") status("backupStatus", t("正在创建备份..."));
    else if (detail.state === "saving") status("backupStatus", t("备份已生成（{0}），请选择保存位置", backupSize(detail.summary?.size)));
    else if (detail.state === "saved") status("backupStatus", t("备份已保存（{0}）", backupSize(detail.size)));
    else if (detail.state === "passphrase_required" || detail.state === "passphrase_wrong") {
      // A locked backup (.awbackup): its passphrase, asked again after a wrong one.
      // "__agent_secret__": the app's dialog hides what is typed (WebUiActivity.onJsPrompt).
      const passphrase = window.prompt(detail.state === "passphrase_wrong" ? t("口令不对，或者备份文件已损坏。请再输入一次备份口令：") : t("这个备份已加密，请输入备份口令："), "__agent_secret__");
      if (!passphrase) { status("backupStatus", t("已取消")); $("btnCreateBackup").disabled = false; $("btnRestoreBackup").disabled = false; return; }
      const result = JSON.parse(native.restoreBackupPassphrase(passphrase));
      if (!result.ok) status("backupStatus", localizeError(result.error) || t("操作失败"), true);
    }
    else if (detail.state === "cancelled") status("backupStatus", t("已取消"));
    else if (detail.state === "restoring") status("backupStatus", t("正在检查并恢复备份..."));
    else if (detail.state === "failed") status("backupStatus", t("操作失败：{0}", localizeError(detail.error || "")), true);
    else if (detail.state === "restored") {
      for (const [key, value] of Object.entries(detail.web || {})) {
        if (backupStorageKeys.includes(key) && typeof value === "string") { try { window.localStorage.setItem(key, value); } catch {} }
      }
      status("backupStatus", t("已恢复，正在重启引擎以完成恢复..."));
    }
  });
  on("btnCreateBackup", "click", () => {
    const web = {};
    for (const key of backupStorageKeys) { try { const value = window.localStorage.getItem(key); if (value !== null) web[key] = value; } catch {} }
    const passphrase = $("backupPassphrase").value;
    if (passphrase !== $("backupPassphraseAgain").value) throw new Error(t("两次输入的口令不一样"));
    if (passphrase && typeof native.createLockedBackup !== "function") throw new Error(t("这个版本不能加密备份"));
    const result = JSON.parse(passphrase ? native.createLockedBackup(JSON.stringify(web), passphrase) : native.createBackup(JSON.stringify(web)));
    $("backupPassphrase").value = "";
    $("backupPassphraseAgain").value = "";
    if (!result.ok) throw new Error(localizeError(result.error) || t("操作失败"));
  }, "backupStatus");
  on("btnRestoreBackup", "click", () => {
    if (!window.confirm(t("恢复会用备份替换这台手机上的会话、记忆、工作区文件和设置（当前数据会保留一份），然后重启引擎。API 密钥不在备份里，恢复后需要重新填写。继续？"))) return;
    const result = JSON.parse(native.restoreBackup());
    if (!result.ok) throw new Error(localizeError(result.error) || t("操作失败"));
  }, "backupStatus");

  const scheduleStates = {
    scheduled: t("等待运行"), disabled: t("已暂停"), dispatching: t("正在提交"), submitted: t("已运行"),
    interrupted: t("提交被中断"), missed: t("错过了运行时间"), mode_required: t("当前模式不能运行"),
    skipped_busy: t("上一次还在运行，本次已跳过"), skipped_locked: t("手机锁着，本次已跳过"), failed: t("运行失败"),
    completed: t("已做完"),
  };
  const scheduleRepeats = { 3600: t("每小时"), 86400: t("每天"), 604800: t("每周") };

  function scheduleSummary(schedule) {
    const due = new Date(schedule.next_due_at || schedule.due_at);
    const when = Number.isNaN(due.getTime()) ? (schedule.next_due_at || schedule.due_at) : due.toLocaleString(i18n?.locale || "zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
    const repeat = (scheduleRepeats[schedule.repeat_seconds] ? ` · ${scheduleRepeats[schedule.repeat_seconds]}` : "") + (schedule.shortcut_id ? ` · ${t("快捷操作")}` : schedule.phone_control ? ` · ${t("操作手机")}` : "");
    const state = scheduleStates[schedule.last_status] || schedule.last_status || "";
    return `${schedule.enabled ? t("下次 {0}", when) : t("暂停")}${repeat}\n${state}${schedule.last_error ? ` · ${schedule.last_error}` : ""}`;
  }

  async function schedules(isCurrent = () => true) {
    const value = await ui.apiJson("/mobile/schedules"); if (!isCurrent()) return;
    $("schedulesList").replaceChildren();
    for (const schedule of value.schedules || []) {
      const item = row(schedule.title, scheduleSummary(schedule));
      const toggle = document.createElement("input"); toggle.type = "checkbox"; toggle.checked = schedule.enabled; toggle.setAttribute("aria-label", t("启用 {0}", schedule.title));
      toggle.addEventListener("change", async () => { toggle.disabled = true; try { await post("/mobile/schedules/update", { schedule_id: schedule.schedule_id, enabled: toggle.checked }); await schedules(); } catch (error) { toggle.checked = !toggle.checked; status("schedulesStatus", error.message, true); } finally { toggle.disabled = false; } });
      item.append(toggle);
      // The AI card widget shows this schedule's latest result on the home screen.
      action(item, "app-window", t("显示在桌面卡片"), async () => {
        await post("/mobile/widget-card", { session_id: schedule.session_id, title: schedule.title });
        let pinned = false;
        try { pinned = JSON.parse(native?.requestPinWidget?.("card") || "{}").ok === true; } catch { pinned = false; }
        status("schedulesStatus", pinned ? t("已设置：在弹出的窗口里把「AI 卡片」加到桌面，以后「{0}」的结果会显示在上面", schedule.title)
          : t("已设置：长按桌面空白处，从“小组件”里添加 Agent 的「AI 卡片」，以后「{0}」的结果会显示在上面", schedule.title));
      });
      action(item, "trash-2", t("删除定时任务"), async () => { if (!window.confirm(t("删除 {0}？", schedule.title))) return; await post("/mobile/schedules/delete", { schedule_id: schedule.schedule_id }); await schedules(); });
      $("schedulesList").append(item);
    }
    const mode = ui.context().settings.autonomy;
    $("btnSaveSchedule").disabled = false;
    // Scheduled runs approve their own network requests and tool calls; in workspace mode say
    // what still waits for the user.
    status("schedulesStatus", mode === "workspace" ? t("定时任务运行时自动允许本任务内的联网和工具调用；删除文件、写入长期记忆、操作其他应用仍会暂停并通知你批准。") : (value.status?.reason || ""));
  }
  // The name a desktop lists this phone under: the model from the WebView's user agent.
  function phoneName() {
    const model = /Android [^;)]*;\s*([^;)]+?)(?:\s+Build\/[^;)]*)?[;)]/.exec(navigator.userAgent || "")?.[1]?.trim();
    return model && model !== "K" ? model.slice(0, 60) : "Android";
  }
  // A computer's pairing link (its QR code, a scanner app, or pasted): the form shows what it holds
  // and nothing is paired until the user taps Pair.
  // The scanned or pasted pairing link: it also names the computer and its other addresses, so it is
  // what goes when the form still shows what it filled in.
  let pairingLink = null;
  async function fillFromPairingLink(text) {
    const parts = await post("/mobile/connections/link", { link: text });
    $("pairAddress").value = parts.url;
    $("pairCode").value = parts.code;
    $("pairFingerprint").value = parts.fingerprint || "";
    pairingLink = { text, url: parts.url, code: parts.code, fingerprint: parts.fingerprint || "" };
    $("pairTarget").hidden = false;
    $("pairTarget").textContent = t("要连接的电脑：{0}（{1}）。核对无误后点「配对」。", parts.name, parts.url);
    status("connectionsStatus", "");
  }
  window.AgentDeviceLink = {
    receive(link) {
      if (closed || typeof link !== "string" || !link) return false;
      if ($("settingsOverlay").hidden) ui.openMenu();
      $("btnConnectionsPage").click();
      void fillFromPairingLink(link).catch((error) => status("connectionsStatus", error.message, true));
      return true;
    },
    // A notification about a paired computer: its page, at the section the notification is about.
    openComputer(target) {
      if (closed || !target || typeof target.host_id !== "string") return false;
      if ($("settingsOverlay").hidden) ui.openMenu();
      void openComputer(target.host_id, target.section || "").catch((error) => {
        $("btnConnectionsPage").click(); status("connectionsStatus", error.message, true);
      });
      return true;
    },
    // Files or text shared to "Send to computer" from another app (staged by the app).
    receiveShare(share) {
      if (closed || !share || typeof share !== "object") return false;
      void takeShare(share).catch((error) => status("connectionsStatus", error.message, true));
      return true;
    },
  };
  window.addEventListener("agent-pairing-scan", (event) => {
    const detail = event.detail || {};
    if (detail.cancelled) { status("connectionsStatus", ""); return; }
    if (!detail.ok || !detail.text) {
      status("connectionsStatus", detail.camera === false
        ? t("没有在这张图片里找到二维码。换一张二维码完整、清楚的截图再试。")
        : t("没有在图片里找到二维码。靠近一点，让二维码占满大半个画面再拍一次。"), true);
      return;
    }
    void fillFromPairingLink(detail.text).catch((error) => status("connectionsStatus", error.message, true));
  });

  // ---- Paired computers (device link 2: docs/DEVICE_LINK_V2.md in the Android source) ----------
  const autonomyNames = { ask: t("每次询问"), workspace: t("工作区内自动"), yolo: t("自动批准一切"), full_access: t("完全访问") };
  const broadAutonomy = new Set(["yolo", "full_access"]);
  const scopeNames = { read: t("查看对话"), tasks: t("交任务"), approvals: t("审批"), broad_autonomy: t("向自动批准的对话交任务"), files: t("收发文件和文字"), knowledge: t("知识库") };
  const activityNames = { paired: t("配对"), task_sent: t("交了任务"), task_finished: t("任务完成"), approval_decided: t("审批"), turn_stopped: t("停止了电脑上的任务"),
    file_received: t("收到文件"), file_sent: t("发出文件"), text_received: t("收到文字"), text_sent: t("发出文字"), conversation_received: t("收到对话"), conversation_sent: t("发出对话"),
    job_sent: t("电脑发来请求"), job_received: t("收到电脑的请求"), job_accepted: t("接受了电脑的请求"), job_rejected: t("拒绝了电脑的请求"), job_finished: t("完成了电脑的请求"),
    job_failed: t("电脑的请求没有完成"), job_cancelled: t("电脑取消了请求"), knowledge_synced: t("同步了知识库"), wake_sent: t("发送了唤醒"), address_changed: t("换到新地址") };
  const jobStates = { waiting: t("等你决定"), accepted: t("已接受"), running: t("正在做"), succeeded: t("已完成"), failed: t("没有完成"), rejected: t("已拒绝"), expired: t("已过期"), cancelled: t("电脑已取消") };
  let computerPoll = null;
  let connectionsPoll = null;
  let computerState = null;
  let outgoing = [];
  let pendingShare = null;
  let knowledgeLists = null;
  let browsePath = "";
  function has(host, feature) { return (host?.features || []).includes(feature); }
  // A desktop of device link 1 does not report its scopes: what it did not refuse is allowed.
  function allowed(host, scope) { return !(host?.scopes || []).length || host.scopes.includes(scope); }
  function when(value) {
    const time = typeof value === "number" ? new Date(value * 1000) : new Date(value || "");
    return Number.isFinite(time.getTime()) ? time.toLocaleString(undefined, { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
  }
  function textButton(parent, symbol, label, handler, primary = false) {
    const button = namedAction(parent, symbol, label, handler);
    if (primary) button.className = "button-primary model-action";
    return button;
  }
  function requestId(prefix) { return window.crypto?.randomUUID?.() || `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`; }
  /** A choice to make before something goes to (or comes from) a computer: the risks in words, then buttons. */
  function choose(title, text, buttons) {
    return new Promise((resolve) => {
      const panel = $("computerConfirm");
      $("computerConfirmTitle").textContent = title;
      $("computerConfirmText").textContent = text;
      $("computerConfirmActions").replaceChildren(...buttons.map(([symbol, label, value, primary]) => {
        const button = document.createElement("button"); button.type = "button";
        button.className = primary ? "button-primary" : "button-secondary";
        button.innerHTML = icon(symbol);
        const caption = document.createElement("span"); caption.textContent = label; button.append(caption);
        button.addEventListener("click", () => { panel.hidden = true; resolve(value); });
        return button;
      }));
      panel.hidden = false;
      panel.scrollIntoView?.({ block: "center" });
    });
  }
  /** A long request (a transfer, a sync) runs on in the engine; this waits for it, saying so meanwhile. */
  async function waitOperation(started, statusId, message) {
    let state = started;
    status(statusId, message);
    for (let tries = 0; state?.state === "running" && tries < 1800 && !closed; tries++) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      state = await ui.apiJson(`/mobile/link/operation?id=${encodeURIComponent(state.operation_id)}`);
    }
    if (state?.state === "failed") throw new Error(localizeError(state.error) || t("操作失败"));
    if (state?.state !== "done") throw new Error(t("还在进行，稍后再来看结果"));
    return state.result;
  }

  async function connections(isCurrent = () => true, quiet = false) {
    const value = await ui.apiJson("/mobile/connections"); if (!isCurrent()) return;
    $("connectionsList").replaceChildren();
    if (!$("pairDeviceName").value) $("pairDeviceName").value = phoneName();
    for (const scanner of ["btnScanPairing", "btnPickPairing"]) $(scanner).hidden = typeof native?.scanPairingQr !== "function";
    $("nearbyComputers").hidden = typeof native?.discoverComputers !== "function";
    for (const host of value.hosts || []) {
      const link = host.link || {};
      const kind = host.api === "mobile" ? t("手机任务 API") : t("桌面 Serve API");
      const reach = host.api !== "mobile" ? "" : link.online ? t("在线") : link.error ? t("连不上") : t("还没连过");
      const waiting = [link.approvals ? t("{0} 项待审批", link.approvals) : "", link.jobs_waiting ? t("{0} 个请求待处理", link.jobs_waiting) : ""].filter(Boolean).join(" · ");
      const item = row(host.name, [[host.url, reach].filter(Boolean).join(" · "),
        host.fingerprint ? t("{0} · 证书已核对：{1}", kind, host.fingerprint.slice(0, 16)) : kind, waiting].filter(Boolean).join("\n"));
      action(item, "chevron-right", t("打开这台电脑"), async () => { await openComputer(host.host_id); });
      action(item, "trash-2", t("移除配对设备"), async () => removeComputer(host));
      $("connectionsList").append(item);
    }
    const hosts = value.hosts || [];
    // A refresh (quiet) leaves whatever the page says, such as a pairing that just went through.
    if (!quiet && pendingShare && hosts.length) status("connectionsStatus", t("选择要发给哪台电脑"));
    else if (!quiet) status("connectionsStatus", t("本机工作区：{0}", value.workspace || t("手机")));
    refreshRelay(hosts);
    watchConnections(hosts);
  }

  // While the list is open each computer's reach stays current: a few seconds after pairing (the
  // first read of a new computer takes a moment), then now and then.
  function watchConnections(hosts) {
    window.clearTimeout(connectionsPoll);
    connectionsPoll = null;
    const linked = hosts.filter((host) => host.api === "mobile");
    if (!linked.length) return;
    const unread = linked.some((host) => !host.link?.online && !host.link?.error);
    connectionsPoll = window.setTimeout(() => {
      connectionsPoll = null;
      if (closed || $("settingsOverlay").hidden || $("settingsConnections").hidden) return;
      connections(() => !closed && !$("settingsConnections").hidden, true).catch(() => {});
    }, unread ? 3000 : 20000);
  }

  async function removeComputer(host) {
    if (!window.confirm(t("移除 {0}？电脑上的这台手机也会被移除。", host.name))) return;
    let result = await post("/mobile/connections/remove", { host_id: host.host_id });
    if (result.ok === false && result.unsettled) {
      // Tasks handed to it whose result has not come back: removing it means they never will.
      if (!window.confirm(t("交给 {0} 的 {1} 个任务还没有结果，移除后就收不到了。仍然移除？", host.name, result.unsettled))) return;
      result = await post("/mobile/connections/remove", { host_id: host.host_id, force: true });
    }
    if (selectedHost?.host_id === host.host_id) { selectedHost = null; remoteSessions = []; }
    if ($("settingsComputer").hidden === false) { ui.setSettingsPage("connections"); }
    await connections();
    status("connectionsStatus", result.computer_told ? t("已移除 {0}", host.name)
      : t("已在手机上移除 {0}。电脑没连上，请在电脑的「手机连接」里也把这台手机移除。", host.name));
  }

  async function openComputer(hostId, section = "") {
    const listed = (await ui.apiJson("/mobile/connections")).hosts || [];
    const host = listed.find((item) => item.host_id === hostId);
    if (!host) throw new Error(t("这台电脑已经移除了"));
    if (!ui.setSettingsPage("computer")) return false;
    stopPolls();
    selectedHost = host; computerState = null; knowledgeLists = null; browsePath = "";
    remoteSessions = [];
    $("settingsTitle").textContent = host.name;
    for (const id of ["remoteHistory", "computerConfirm"]) $(id).hidden = true;
    $("computerBrowse").open = false; $("computerRemoteActivity").open = false;
    if (pendingShare) { const share = pendingShare; pendingShare = null; addOutgoing(share.files || []); if (share.text) $("computerTextInput").value = share.text; }
    renderOutgoing();
    status("computerStatus", t("读取中..."));
    const current = ++generation;
    const isCurrent = () => !closed && current === generation && !$("settingsOverlay").hidden && !$("settingsComputer").hidden
      && selectedHost?.host_id === hostId;
    // The computer's state first, then its conversations: an error reading those is the one to show.
    await renderComputer(isCurrent, true);
    await loadRemoteSessions(isCurrent);
    if (!isCurrent()) return true;
    pollComputer(isCurrent);
    const target = { approvals: "computerApprovals", jobs: "computerJobs", inbox: "computerInbox" }[section];
    if (target) window.setTimeout(() => $(target)?.scrollIntoView?.({ block: "start" }), 300);
    return true;
  }

  function pollComputer(isCurrent) {
    window.clearTimeout(computerPoll);
    computerPoll = window.setTimeout(async () => {
      if (!isCurrent()) return;
      try { await renderComputer(isCurrent, false); } catch { /* shown on the next successful read */ }
      if (isCurrent()) pollComputer(isCurrent);
    }, 5000);
  }

  async function loadRemoteSessions(isCurrent) {
    const host = selectedHost;
    let data = null;
    try { data = await ui.apiJson(`/mobile/connections/sessions?host_id=${encodeURIComponent(host.host_id)}`); }
    catch (error) { if (isCurrent()) status("computerStatus", error.message, true); }
    if (!isCurrent()) return;
    remoteSessions = Array.isArray(data?.sessions) ? data.sessions : [];
    for (const session of remoteSessions) if (session.title) remoteSessionTitles.set(session.id, session.title);
    const selector = $("remoteSessionSelector");
    const previous = selector.value;
    selector.replaceChildren();
    if (host.api === "mobile" && has(host, "conversations")) {
      const option = document.createElement("option"); option.value = ""; option.textContent = t("新对话"); selector.append(option);
    }
    for (const session of remoteSessions) {
      const option = document.createElement("option"); option.value = session.id;
      option.textContent = [session.title || session.id, broadAutonomy.has(session.autonomy) ? autonomyNames[session.autonomy] : "", session.running ? t("运行中") : ""].filter(Boolean).join(" · ");
      selector.append(option);
    }
    if ([...selector.options].some((option) => option.value === previous)) selector.value = previous;
    updateRemoteWorkspace();
    $("btnQueueHandoff").disabled = !data || !selector.options.length;
    renderRunning();
  }
  function selectedRemote() { const id = $("remoteSessionSelector").value; return id ? remoteSessions.find((item) => item.id === id) || null : null; }
  /** The settings the task would run under on the computer: the conversation's, or a new one's. */
  function targetAutonomy() {
    const session = selectedRemote();
    if (session) return session.autonomy || null;
    return $("remoteSessionSelector").value === "" ? selectedHost?.new_conversation_autonomy || null : null;
  }
  function updateRemoteWorkspace() {
    const session = selectedRemote();
    $("remoteWorkspace").textContent = session ? t("数据保存在 {0}：{1}", selectedHost?.name || t("远程设备"), session.workspace || "")
      : $("remoteSessionSelector").value === "" && $("remoteSessionSelector").options.length ? t("在 {0} 上新建一个对话", selectedHost?.name || t("电脑")) : "";
    const autonomy = targetAutonomy();
    const note = $("remoteAutonomy");
    note.hidden = !broadAutonomy.has(autonomy);
    if (note.hidden) return;
    note.textContent = !has(selectedHost, "autonomy_ack")
      ? t("这个对话在电脑上设为「{0}」，电脑上的版本还不接受手机交到这类对话的任务。", autonomyNames[autonomy])
      : allowed(selectedHost, "broad_autonomy")
        ? t("这个对话在电脑上设为「{0}」：交过去的任务会直接在电脑上执行，发送前会再提醒一次。", autonomyNames[autonomy])
        : t("这个对话在电脑上设为「{0}」。电脑还没允许这台手机往这类对话交任务：要在电脑的「手机连接」里给这台手机勾上这项权限。", autonomyNames[autonomy]);
  }

  async function renderComputer(isCurrent, first) {
    const host = selectedHost;
    const linked = host.api === "mobile";
    for (const id of ["computerApprovals", "computerJobs", "computerFiles", "computerText", "computerKnowledge", "computerRunning"]) if (!linked) $(id).hidden = true;
    $("computerInbox").hidden = !linked;
    if (!linked) {
      renderSummary({ host, online: null });
      renderDevice({ host, activity: [] });
      if (first) status("computerStatus", "");
      return;
    }
    const value = await ui.apiJson(`/mobile/link/computer?host_id=${encodeURIComponent(host.host_id)}`);
    if (!isCurrent()) return;
    computerState = value;
    selectedHost = { ...host, ...value.host, link: host.link };
    renderSummary(value);
    renderApprovals(value);
    renderJobs(value);
    renderInbox(value);
    renderSections(value);
    renderDevice(value);
    if (first) status("computerStatus", value.error ? localizeError(value.error) : "", !!value.error);
  }

  function renderSummary(value) {
    const host = value.host || selectedHost;
    const list = $("computerSummary"); list.replaceChildren();
    const moved = /^found at (\S+)$/.exec(value.error || "");
    const reach = value.online === null ? t("桌面 Serve API") : value.waking ? t("正在唤醒，等它上线…") : value.online ? t("在线")
      : moved ? t("在 {0} 找到了这台电脑", moved[1]) : value.error ? t("连不上") : t("正在连接…");
    const item = row(reach, [host.url, value.polled_at ? t("上次连上：{0}", when(value.polled_at)) : ""].filter(Boolean).join("\n"));
    if (moved) textButton(item, "link", t("换到这个地址"), async () => {
      await post("/mobile/link/use-address", { host_id: host.host_id, url: moved[1] });
      await post("/mobile/link/refresh", { host_id: host.host_id });
      status("computerStatus", t("已换到 {0}", moved[1]));
    });
    if (!value.online && host.wake && !value.waking) textButton(item, "zap", t("唤醒电脑"), async () => {
      const sent = await post("/mobile/link/wake", { host_id: host.host_id });
      status("computerStatus", t("已发送唤醒（{0} 个包），电脑上线后会通知你。只在手机和电脑在同一局域网时有效。", sent.sent));
    });
    list.append(item);
    // Phones that freeze apps with the screen off: the computer's approvals and requests wait until
    // the screen comes on. Said here, with the way to allow background running.
    const run = value.online === null ? null : backgroundRunState();
    if (run) {
      const now = Date.now();
      const lockedPause = (run.pauses || []).some((pause) => !pause.screen_on && now - pause.at_ms < 24 * 60 * 60 * 1000);
      const note = !run.battery_optimization_exempt && (run.strict_maker || lockedPause)
        ? row(t("锁屏时收不到电脑的消息"), t("锁屏后系统会暂停这个应用，这段时间电脑的审批、请求和任务完成通知都要等亮屏后才到。允许后台运行后，锁屏也能收到。"))
        : run.battery_optimization_exempt && lockedPause && run.steps
          ? row(t("锁屏时收不到电脑的消息"), t("锁屏时系统仍会暂停这个应用。还差一步：{0}", run.steps)) : null;
      if (note) {
        textButton(note, "shield", run.battery_optimization_exempt ? t("打开设置") : t("允许后台运行"), async () => {
          if (run.battery_optimization_exempt) native?.openAutoStartSettings?.(); else native?.requestBackgroundRun?.();
        });
        list.append(note);
      }
    }
  }

  function renderApprovals(value) {
    const host = selectedHost;
    const approvals = (value.approvals || []).filter((item) => item && item.request_id);
    $("computerApprovals").hidden = !(has(host, "approvals") && allowed(host, "approvals")) || !approvals.length;
    const list = $("computerApprovalList"); list.replaceChildren();
    for (const approval of approvals) {
      const item = row(approval.summary || approval.tool || t("一个操作"), [approval.tool ? t("工具：{0}", approval.tool) : "", remoteSessionTitles.get(approval.session_id) || ""].filter(Boolean).join(" · "));
      textButton(item, "check", t("允许"), async () => {
        await post("/mobile/link/approve", { host_id: host.host_id, request_id: approval.request_id, decision: "approve" });
        status("computerStatus", t("已允许"));
        await renderComputer(() => true, false);
      }, true);
      textButton(item, "x", t("拒绝"), async () => {
        await post("/mobile/link/approve", { host_id: host.host_id, request_id: approval.request_id, decision: "reject" });
        status("computerStatus", t("已拒绝"));
        await renderComputer(() => true, false);
      });
      list.append(item);
    }
  }

  function renderJobs(value) {
    const host = selectedHost;
    $("computerJobs").hidden = !has(host, "phone_jobs");
    $("computerJobsSetting").value = value.settings?.jobs || "ask";
    const list = $("computerJobList"); list.replaceChildren();
    for (const job of value.jobs || []) {
      const detail = [jobStates[job.state] || job.state, job.title ? t("来自对话「{0}」", job.title) : "", job.operate_phone ? t("要操作手机") : "", when(job.created_at)].filter(Boolean).join(" · ");
      const item = row(job.prompt.slice(0, 200), [detail, job.state === "failed" ? job.error || "" : ""].filter(Boolean).join("\n"));
      if (job.state === "waiting") {
        textButton(item, "x", t("拒绝"), async () => { await post("/mobile/link/job", { host_id: host.host_id, job_id: job.job_id, decision: "reject" }); await renderComputer(() => true, false); });
        textButton(item, "check", t("允许，每一步询问我"), async () => {
          await post("/mobile/link/job", { host_id: host.host_id, job_id: job.job_id, decision: "accept" });
          status("computerStatus", t("已接受，手机正在做"));
          await renderComputer(() => true, false);
        }, true);
        textButton(item, "shield", t("允许，放行这个任务的操作"), async () => {
          const choice = await choose(t("放行这个任务的操作"), t("这个任务里，点屏幕、在其他应用里输入等操作不再逐条询问。删除文件、发消息、卸载应用仍逐条询问；银行卡号、身份证号、验证码仍会拦下。"),
            [["check", t("放行并开始"), "go", true], ["x", t("取消"), "cancel"]]);
          if (choice !== "go") return;
          await post("/mobile/link/job", { host_id: host.host_id, job_id: job.job_id, decision: "accept", approve_all: true });
          status("computerStatus", t("已接受，手机正在做"));
          await renderComputer(() => true, false);
        });
      } else if (job.state === "succeeded" && job.result) {
        const result = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = t("结果");
        const body = document.createElement("pre"); body.className = "management-output"; body.textContent = job.result; result.append(summary, body); item.append(result);
      }
      list.append(item);
    }
  }

  function renderRunning() {
    const host = selectedHost;
    const running = remoteSessions.filter((session) => session.running);
    $("computerRunning").hidden = !running.length;
    const list = $("computerRunningList"); list.replaceChildren();
    for (const session of running) {
      const item = row(session.title || session.id, session.workspace || "");
      if (host?.api === "mobile" && has(host, "stop") && allowed(host, "tasks")) textButton(item, "square", t("停止"), async () => {
        if (!window.confirm(t("停止电脑上「{0}」正在做的事？", session.title || session.id))) return;
        await post("/mobile/link/stop", { host_id: host.host_id, session_id: session.id });
        status("computerStatus", t("已停止"));
        await loadRemoteSessions(() => selectedHost?.host_id === host.host_id);
      });
      list.append(item);
    }
  }

  const mimeTypes = { pdf: "application/pdf", jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", gif: "image/gif", webp: "image/webp", txt: "text/plain", md: "text/markdown",
    csv: "text/csv", html: "text/html", json: "application/json", zip: "application/zip", mp4: "video/mp4", mp3: "audio/mpeg",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation" };
  function openReceived(path, sha256) {
    if (typeof native?.workspaceFileAction !== "function" || !sha256) throw new Error(t("在「工作区文件」里打开：{0}", path));
    const type = mimeTypes[(path.split(".").pop() || "").toLowerCase()] || "application/octet-stream";
    const outcome = JSON.parse(native.workspaceFileAction(JSON.stringify({ request_id: requestId("open"), action: "open", path, sha256, mime_type: type })));
    if (!outcome.ok) throw new Error(localizeError(outcome.error) || t("无法打开文件"));
  }
  function copyText(text) {
    if (typeof native?.copyToClipboard === "function") native.copyToClipboard(text);
    else if (navigator.clipboard?.writeText) void navigator.clipboard.writeText(text);
    else throw new Error(t("当前设备无法复制"));
    status("computerStatus", t("已复制到剪贴板"));
  }

  function renderInbox(value) {
    const host = selectedHost;
    const entries = [
      ...(value.received || []).map((item) => ({ kind: "received", at: item.at, item })),
      ...(value.runs || []).map((item) => ({ kind: "run", at: Date.parse(item.updated_at || item.due_at || "") / 1000 || 0, item })),
      ...(value.turns || []).map((item) => ({ kind: "turn", at: Date.parse(item.finished_at || "") / 1000 || 0, item })),
    ].sort((a, b) => b.at - a.at).slice(0, 60);
    const list = $("computerInboxList"); list.replaceChildren();
    if (!entries.length) { list.append(row(t("还没有内容"), t("电脑发来的文件、文字和任务结果会出现在这里"))); return; }
    for (const { kind, item } of entries) {
      if (kind === "received") {
        if (item.state === "failed") {
          const failed = row(item.name || t("没有收到"), [t("没有收到"), item.error || ""].filter(Boolean).join(" · "));
          action(failed, "refresh-cw", t("重新接收"), async () => { await post("/mobile/link/retry-transfer", { host_id: host.host_id, transfer_id: item.transfer_id }); status("computerStatus", t("会在下次连上时重新接收")); });
          list.append(failed);
        } else if (item.kind === "file") {
          const received = row(item.name, [t("收到的文件"), when(item.at), item.path].filter(Boolean).join(" · "));
          textButton(received, "folder-open", t("打开"), async () => openReceived(item.path, item.sha256));
          list.append(received);
        } else if (item.kind === "text" || item.kind === "link") {
          const received = row(item.text.slice(0, 200), [item.kind === "link" ? t("收到的链接") : t("收到的文字"), when(item.at)].join(" · "));
          textButton(received, "copy", t("复制"), async () => copyText(item.text));
          if (item.kind === "link" && /^https?:\/\//i.test(item.text.trim()) && typeof native?.openExternal === "function") textButton(received, "globe", t("打开"), async () => { native.openExternal(item.text.trim()); });
          list.append(received);
        } else if (item.kind === "conversation") {
          const received = row(item.name || t("对话"), [t("收到的对话"), when(item.at)].join(" · "));
          textButton(received, "chevron-right", t("打开对话"), async () => { if (!ui.openSession(item.session_id)) throw new Error(t("目标会话不存在或已删除")); });
          list.append(received);
        }
      } else if (kind === "run") {
        const done = item.state === "succeeded";
        const entry = row(t("定时任务「{0}」", item.title || ""), [stateNames[item.state] || item.state, when(item.updated_at || item.due_at)].filter(Boolean).join(" · "));
        const text = done ? item.result : item.error;
        if (text) {
          const details = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = done ? t("结果") : t("原因");
          const body = document.createElement("pre"); body.className = "management-output"; body.textContent = text;
          details.append(summary, body); entry.append(details);
          details.addEventListener("toggle", () => { if (details.open && has(host, "inbox_read")) void post("/mobile/link/read-runs", { host_id: host.host_id, run_ids: [item.run_id] }).catch(() => {}); });
          if (done) textButton(entry, "send", t("在手机上继续"), async () => {
            if (!ui.quickAsk({ text: t("电脑上的定时任务「{0}」的结果：\n{1}\n\n", item.title || "", text.slice(0, 6000)) })) throw new Error(t("请稍后再试"));
          });
        }
        list.append(entry);
      } else {
        const entry = row(t("电脑上的任务：{0}", item.title || ""), [stateNames[item.state === "succeeded" ? "completed" : item.state] || item.state, when(item.finished_at), item.summary || ""].filter(Boolean).join(" · "));
        list.append(entry);
      }
    }
  }

  function renderSections(value) {
    const host = selectedHost;
    const files = has(host, "files") && allowed(host, "files");
    $("computerFiles").hidden = !files;
    $("computerText").hidden = !(has(host, "messages") && allowed(host, "files"));
    for (const [id, method] of [["btnComputerPickFiles", "pickForComputer"], ["btnComputerPickPhotos", "pickForComputer"], ["btnComputerCamera", "pickForComputer"]]) $(id).hidden = typeof native?.[method] !== "function";
    $("btnComputerPaste").hidden = typeof native?.readClipboardText !== "function";
    const knowledge = has(host, "knowledge") && allowed(host, "knowledge");
    $("computerKnowledge").hidden = !knowledge;
    if (knowledge) {
      const pairs = value.settings?.kb_pairs || [];
      const list = $("computerKnowledgePairs"); list.replaceChildren();
      const label = (side, id) => (knowledgeLists?.[side] || []).find((base) => base.id === id);
      for (const pair of pairs) {
        const computerBase = label("computer", pair.computer); const phoneBase = label("phone", pair.phone);
        const item = row(t("电脑：{0} ↔ 手机：{1}", computerBase ? computerBase.name || t("默认知识库") : pair.computer, phoneBase ? phoneBase.label : pair.phone), "");
        action(item, "x", t("取消对应"), async () => {
          await post("/mobile/link/kb-pairs", { host_id: host.host_id, pairs: pairs.filter((other) => other !== pair) });
          await renderComputer(() => true, false);
        });
        list.append(item);
      }
      const result = value.settings?.kb_result;
      $("computerKbResult").textContent = value.settings?.kb_synced_at
        ? t("上次同步：{0}，复制到手机 {1} 篇，复制到电脑 {2} 篇", when(value.settings.kb_synced_at), result?.to_phone ?? 0, result?.to_computer ?? 0)
          + ((result?.errors || []).length ? "\n" + result.errors.join("\n") : "")
        : "";
      if (!knowledgeLists) void loadKnowledgeLists();
    }
  }

  async function loadKnowledgeLists() {
    const host = selectedHost;
    knowledgeLists = { computer: [], phone: [] };
    try { knowledgeLists = await ui.apiJson(`/mobile/link/knowledge?host_id=${encodeURIComponent(host.host_id)}`); }
    catch (error) { status("computerStatus", error.message, true); return; }
    if (selectedHost?.host_id !== host.host_id) return;
    const fill = (id, items, text) => { $(id).replaceChildren(...items.map((item) => { const option = document.createElement("option"); option.value = item.id; option.textContent = text(item); return option; })); };
    fill("computerKbComputer", knowledgeLists.computer || [], (item) => t("{0}（{1}）", item.name || t("默认知识库"), item.documents));
    fill("computerKbPhone", knowledgeLists.phone || [], (item) => t("{0}（{1}）", item.label, item.documents));
    if (computerState) renderSections(computerState);
  }

  function renderDevice(value) {
    const host = value.host || selectedHost;
    terms("computerFacts", [
      [t("地址"), host.url],
      [t("权限"), (host.scopes || []).length ? host.scopes.map((scope) => scopeNames[scope] || scope).join(t("、")) : t("未报告")],
      [t("配对时间"), when(host.paired_at)],
      [t("上次连上"), host.last_ok_at ? when(host.last_ok_at) : t("还没连过")],
      ...(host.model ? [[t("电脑上的模型"), `${host.model.name} · ${host.model.location === "computer" ? t("在这台电脑上运行") : t("云端服务")}`]] : []),
      ...(host.workspace ? [[t("电脑上打开的文件夹"), host.workspace]] : []),
    ]);
    const addresses = $("computerAddresses"); addresses.replaceChildren();
    for (const address of host.addresses || []) {
      addresses.append(row(address.url, [address.kind === "tailscale" ? "Tailscale" : t("局域网"), address.usable ? t("连不上当前地址时会试它") : t("需要电脑开启 HTTPS")].join(" · ")));
    }
    const activity = $("computerActivity"); activity.replaceChildren();
    for (const entry of value.activity || []) activity.append(row(activityNames[entry.action] || entry.action, `${when(entry.at)} · ${entry.detail}`));
    if (!(value.activity || []).length) activity.append(row(t("还没有记录"), ""));
    $("computerRemoteActivity").hidden = !has(host, "device");
  }

  function addOutgoing(files) {
    for (const file of files || []) if (file?.staged && !outgoing.some((item) => item.staged === file.staged)) outgoing.push({ staged: file.staged, name: file.name || file.staged, size: file.size || 0 });
    renderOutgoing();
  }
  function renderOutgoing() {
    const list = $("computerOutgoing"); list.replaceChildren();
    for (const file of outgoing) {
      const item = row(file.name, bytes(file.size));
      action(item, "x", t("不发这个"), async () => {
        outgoing = outgoing.filter((other) => other !== file);
        if (typeof native?.discardComputerFiles === "function") native.discardComputerFiles(JSON.stringify([file.staged]));
        renderOutgoing();
      });
      list.append(item);
    }
    $("btnComputerSendFiles").disabled = !outgoing.length;
  }
  async function takeShare(share) {
    const listed = ((await ui.apiJson("/mobile/connections")).hosts || []).filter((host) => host.api === "mobile");
    if ($("settingsOverlay").hidden) ui.openMenu();
    if (!listed.length) {
      if (typeof native?.discardComputerFiles === "function") native.discardComputerFiles(JSON.stringify((share.files || []).map((file) => file.staged)));
      $("btnConnectionsPage").click();
      status("connectionsStatus", t("还没有配对的电脑。先在这里连接电脑，再分享一次。"), true);
      return;
    }
    if (listed.length === 1) { pendingShare = share; await openComputer(listed[0].host_id); }
    else { pendingShare = share; $("btnConnectionsPage").click(); }
    if ((share.errors || []).length) status(listed.length === 1 ? "computerStatus" : "connectionsStatus", t("有些内容没能读取：{0}", share.errors.join(t("；"))), true);
  }

  async function loadBrowse(path) {
    const host = selectedHost;
    const listing = await ui.apiJson(`/mobile/link/files?host_id=${encodeURIComponent(host.host_id)}&path=${encodeURIComponent(path)}`);
    if (selectedHost?.host_id !== host.host_id) return;
    browsePath = listing.path || "";
    $("computerPath").textContent = `/${browsePath}`;
    const list = $("computerFileList"); list.replaceChildren();
    if (browsePath) {
      const up = row("..", t("上一级"));
      action(up, "chevron-left", t("上一级"), async () => loadBrowse(browsePath.split("/").slice(0, -1).join("/")));
      list.append(up);
    }
    for (const entry of listing.entries || []) {
      const child = browsePath ? `${browsePath}/${entry.name}` : entry.name;
      const item = row(entry.name, entry.kind === "dir" ? t("文件夹") : [bytes(entry.size), when(entry.modified_at)].filter(Boolean).join(" · "));
      if (entry.kind === "dir") action(item, "chevron-right", t("打开文件夹"), async () => loadBrowse(child));
      else action(item, "download", t("下载到手机"), async () => {
        const result = await waitOperation(await post("/mobile/link/download", { host_id: host.host_id, path: child }), "computerStatus", t("正在下载 {0}...", entry.name));
        status("computerStatus", t("已存到 {0}", result.path));
        textButton(item, "folder-open", t("打开"), async () => openReceived(result.path, result.sha256));
      });
      list.append(item);
    }
    if (listing.truncated) list.append(row(t("只列出前 500 项"), ""));
  }

  /** "Continue on the computer" on the conversation page: shown when a computer can take conversations. */
  function refreshRelay(hosts) {
    const able = (hosts || []).filter((host) => host.api === "mobile" && has(host, "conversations") && allowed(host, "tasks"));
    $("relayToComputer").hidden = !able.length;
    $("relayComputer").replaceChildren(...able.map((host) => { const option = document.createElement("option"); option.value = host.host_id; option.textContent = host.name; return option; }));
  }
  // At page load the engine may still be starting: asked again a few times.
  (function loadRelay(attempt) {
    ui.apiJson("/mobile/connections").then((value) => { if (!closed) refreshRelay(value.hosts || []); })
      .catch(() => { if (!closed && attempt < 6) window.setTimeout(() => loadRelay(attempt + 1), 5000); });
  })(0);
  async function outbox(isCurrent = () => true) {
    const [value, linked] = await Promise.all([ui.apiJson("/mobile/outbox"), ui.apiJson("/mobile/connections").catch(() => ({}))]); if (!isCurrent()) return;
    const hostNames = new Map((linked.hosts || []).map(host => [host.host_id, host.name]));
    $("outboxList").replaceChildren();
    for (const delivery of value.deliveries || []) {
      // Which computer and conversation, by name: a conversation's id means nothing to the user.
      const where = [hostNames.get(delivery.host_id), remoteSessionTitles.get(delivery.payload?.session_id)].filter(Boolean);
      // A computer's running task says what it is doing now (device link 2).
      const now = delivery.state === "submitted" && delivery.activity ? t("正在：{0}", delivery.activity) : "";
      const item = row((delivery.payload?.prompt || "").slice(0, 100), `${[stateNames[delivery.state] || delivery.state, ...where].join(" · ")}\n${[now, delivery.error || ""].filter(Boolean).join("\n")}`);
      if (delivery.state === "pending") {
        action(item, "send", t("重试发送"), async () => { await post("/mobile/outbox/send", { delivery_id: delivery.delivery_id }); await outbox(); });
        action(item, "x", t("取消待发送"), async () => { await post("/mobile/outbox/cancel", { delivery_id: delivery.delivery_id }); await outbox(); });
      }
      if (["submitted", "uncertain"].includes(delivery.state)) action(item, "refresh-cw", t("核对远程状态"), async () => { await post("/mobile/outbox/reconcile", { delivery_id: delivery.delivery_id }); await outbox(); });
      if (delivery.result) { const result = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = t("结果"); const body = document.createElement("pre"); body.className = "management-output"; body.textContent = delivery.result; result.append(summary, body); item.append(result); }
      $("outboxList").append(item);
    }
    status("outboxStatus", value.deliveries?.length ? "" : t("没有待发送任务"));
  }
  async function workflows(isCurrent = () => true) {
    const value = await ui.apiJson("/mobile/workflows"); if (!isCurrent()) return;
    $("workflowsList").replaceChildren();
    for (const workflow of value.workflows || []) {
      const item = row(workflow.name, workflow.schema_version === 2 ? t("步骤回放 · {0} 步", workflow.steps?.length || 0) : workflow.prompt);
      action(item, "play", t("运行流程"), async () => { const context = ui.context(); if (context.activeTask) throw new Error(t("请等待当前任务结束")); const result = await post("/mobile/workflows/run", { workflow_id: workflow.workflow_id, session_id: context.sessionId, model: context.settings.model, reasoning_effort: context.settings.reasoning_effort }); followTask(result, "workflowsStatus", t("流程已提交")); });
      action(item, "pencil", t("编辑流程"), async () => { $("workflowForm").dataset.workflowId = workflow.workflow_id; $("workflowForm")._original = workflow; $("workflowName").value = workflow.name; $("workflowPrompt").value = workflow.prompt || ""; $("workflowPackage").value = workflow.preconditions?.package || ""; $("workflowExpectedPackage").value = workflow.assertions?.package || ""; $("workflowExpectedText").value = workflow.assertions?.text_contains || ""; $("workflowMode").value = workflow.schema_version === 2 ? "replay" : "goal"; $("workflowStepEditor").replaceChildren(); for (const step of workflow.steps || []) addWorkflowStep(step); setWorkflowMode(); });
      action(item, "download", t("导出流程"), async () => shareDocument(workflow.name, await ui.apiJson(`/mobile/workflows/export?workflow_id=${encodeURIComponent(workflow.workflow_id)}`), "workflowsStatus"));
      action(item, "trash-2", t("删除流程"), async () => { if (!window.confirm(t("删除 {0}？", workflow.name))) return; await post("/mobile/workflows/delete", { workflow_id: workflow.workflow_id }); await workflows(); });
      $("workflowsList").append(item);
    }
    $("workflowRuns").replaceChildren();
    for (const run of value.runs || []) {
      const steps = Array.isArray(run.steps) ? run.steps : [];
      const verifiedSteps = steps.filter(step => step.state === "verified").length;
      const progress = steps.length ? t(" · {0}/{1} 步已验证", verifiedSteps, steps.length) : "";
      const item = row(run.workflow?.name || run.task_id, `${stateNames[run.state] || run.state}${progress}\n${run.reason || ""}`);
      if (steps.length) { const detail = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = t("查看步骤记录"); const body = document.createElement("pre"); body.className = "management-output"; body.textContent = steps.map(step => t("{0}: {1} · {2} · {3} 次", step.step_id, step.state, step.action_outcome, step.attempts)).join("\n"); detail.append(summary, body); item.append(detail); }
      if (run.resume_available) action(item, "play", t("检查状态并恢复流程"), async () => { if (!window.confirm(t("检查当前界面后，从最后一个已确认的步骤继续？结果不明的操作无法重放。"))) return; const result = await post("/mobile/workflows/resume", { run_id: run.run_id, confirm_resume: true }); followTask(result, "workflowsStatus", t("流程恢复已提交")); });
      $("workflowRuns").append(item);
    }
    status("workflowsStatus", value.workflows?.length ? "" : t("还没有保存流程"));
  }
  function setWorkflowMode() {
    const replay = $("workflowMode").value === "replay";
    $("workflowPrompt").required = !replay; $("workflowPrompt").hidden = replay;
    document.querySelector('label[for="workflowPrompt"]').hidden = replay;
    $("workflowReplayEditor").hidden = !replay;
    if (replay && !$("workflowStepEditor").children.length) addWorkflowStep();
  }
  function addWorkflowStep(seed = null) {
    if ($("workflowStepEditor").children.length >= 100) throw new Error(t("流程最多 100 步"));
    const value = seed || { step_id: `step-${++stepSequence}-${Date.now()}`, action: "launch_app", package_name: "com.android.settings", preconditions: { package: "com.agentworkspace.mobile" }, postconditions: { package: "com.android.settings" }, timeout_ms: 5000, max_retries: 0 };
    const card = document.createElement("fieldset"); card.className = "workflow-step"; card._seed = value;
    const legend = document.createElement("legend"); legend.textContent = value.step_id; card.append(legend);
    function field(name, label, initial = "", choices = null) {
      const wrapper = document.createElement("label"); wrapper.textContent = label;
      const input = document.createElement(choices ? "select" : "input"); input.dataset.field = name;
      if (choices) for (const [optionValue, text] of choices) { const option = document.createElement("option"); option.value = optionValue; option.textContent = text; input.append(option); }
      else { input.type = "text"; input.maxLength = name === "text" ? 4096 : 500; }
      input.value = initial; wrapper.append(input); card.append(wrapper); return input;
    }
    const choice = field("action", t("操作"), value.action, [["launch_app", t("打开应用")], ["tap", t("点击控件")], ["type_text", t("输入文字")], ["back", t("返回")], ["home", t("回到桌面")]]);
    field("package_name", t("应用包名"), value.package_name);
    const selectorKey = ["resource_id", "text", "content_description"].find(key => value.selector?.[key]) || "resource_id";
    field("selector_key", t("查找控件方式"), selectorKey, [["resource_id", t("控件 ID")], ["text", t("控件文字")], ["content_description", t("无障碍描述")]]);
    field("selector_value", t("目标控件"), value.selector?.[selectorKey]);
    field("text", t("输入内容"), value.text);
    for (const [prefix, title] of [["pre", t("执行前")], ["post", t("执行后")]]) { const checks = value[prefix === "pre" ? "preconditions" : "postconditions"] || {}; field(`${prefix}_package`, t("{0}应用包名", title), checks.package); field(`${prefix}_text`, t("{0}页面文字", title), checks.text_contains); }
    function visibility() { for (const name of ["package_name", "selector_key", "selector_value", "text"]) { const input = card.querySelector(`[data-field="${name}"]`); input.parentElement.hidden = name === "package_name" ? choice.value !== "launch_app" : name === "text" ? choice.value !== "type_text" : !["tap", "type_text"].includes(choice.value); } }
    choice.addEventListener("change", visibility); visibility();
    namedAction(card, "trash-2", t("移除此步骤"), () => card.remove()); $("workflowStepEditor").append(card);
  }
  function workflowSteps() {
    return [...$("workflowStepEditor").children].map(card => {
      const value = name => card.querySelector(`[data-field="${name}"]`).value;
      const seed = card._seed; const actionName = value("action");
      const step = { step_id: seed.step_id, action: actionName, timeout_ms: seed.timeout_ms ?? 5000, max_retries: seed.max_retries ?? 0 };
      for (const [prefix, key] of [["pre", "preconditions"], ["post", "postconditions"]]) { const check = { ...seed[key] }; for (const [field, input] of [["package", `${prefix}_package`], ["text_contains", `${prefix}_text`]]) { if (value(input).trim()) check[field] = value(input).trim(); else delete check[field]; } if (!Object.keys(check).length) throw new Error(t("每个步骤都需要执行前和执行后的界面条件")); step[key] = check; }
      if (actionName === "launch_app") step.package_name = value("package_name").trim();
      if (["tap", "type_text"].includes(actionName)) {
        step.selector = { ...seed.selector };
        const originalKey = ["resource_id", "text", "content_description"].find(key => seed.selector?.[key]) || "resource_id";
        const selectedKey = value("selector_key");
        if (selectedKey !== originalKey) delete step.selector[originalKey];
        step.selector[selectedKey] = value("selector_value").trim();
      }
      if (actionName === "type_text") step.text = value("text");
      return step;
    });
  }
  async function evaluations(isCurrent = () => true) {
    const value = await ui.apiJson("/mobile/evaluations"); if (!isCurrent()) return;
    const report = await ui.apiJson("/mobile/evaluations/export").catch(() => null); if (!isCurrent()) return;
    const measured = report?.summary;
    terms("evaluationSummary", [[t("实测完成"), measured?.measured_finished || 0], [t("实测验证成功"), measured?.measured_successes || 0], [t("实测成功率"), measured?.measured_success_rate == null ? t("未测量") : `${(measured.measured_success_rate * 100).toFixed(1)}%`], [t("人工记录"), measured?.reviewed_records || 0]]);
    $("evaluationCases").replaceChildren();
    for (const scenario of value.scenarios || []) {
      const item = row(scenario.name, scenario.prompt);
      action(item, "play", t("运行评测任务"), async () => { const context = ui.context(); if (context.activeTask) throw new Error(t("请等待当前任务结束")); const result = await post("/mobile/evaluations/run", { scenario_id: scenario.scenario_id, session_id: context.sessionId, model: context.settings.model, reasoning_effort: context.settings.reasoning_effort }); followTask(result, "evaluationsStatus", t("评测任务已提交")); });
      $("evaluationCases").append(item);
    }
    $("evaluationRuns").replaceChildren();
    for (const run of value.runs || []) $("evaluationRuns").append(row(run.scenario_id, t("{0} · {1}\n{2} 步 · {3} s · ${4}", stateNames[run.outcome] || run.outcome, run.metadata?.model || "", run.metrics?.steps ?? t("未测量"), run.metrics?.elapsed_seconds ?? t("未测量"), run.metrics?.cost_usd ?? t("未测量"))));
    status("evaluationsStatus", value.runs?.length ? "" : t("尚无任务成功率记录"));
  }
  function deviceOptions() {
    return { model_id: $("localDeviceModelSelector").value, context_tokens: ui.readLocalContextDraft(),
      memory_mode: $("localMemorySelector").value, threads: Number($("localThreadsInput").value),
      timeout_seconds: Number($("localTimeoutInput").value) };
  }
  function deviceModelChoices(value) {
    deviceModels = value.models || [];
    const selector = $("localDeviceModelSelector");
    const previous = selector.value;
    const models = deviceModels.length ? deviceModels : value.route === "embedded_qwen"
      ? [{ model_id: value.model || ui.context().settings.model, title: value.model || ui.context().settings.model, installed: true }] : [];
    selector.replaceChildren(...models.map(model => {
      const option = document.createElement("option"); option.value = model.model_id;
      option.textContent = `${model.title || model.model_id}${model.installed ? "" : t(" · 未安装")}`; return option;
    }));
    const selected = models.find(model => model.model_id === previous)
      || models.find(model => model.model_id === value.model)
      || models.find(model => model.installed) || models[0];
    if (selected) selector.value = selected.model_id;
  }
  function acceleratorText(value) {
    const gpu = value.gpu || "GPU";
    const cpuOnly = value.mode === "cpu";
    switch (value.gpu_state) {
      case "available": return cpuOnly ? t("已选仅 CPU；这台手机的 {0} 也能运行本机模型。", gpu) : t("本机模型在 {0} 上运行（GPU 加速为测试功能；遇到问题可改用「仅 CPU」并反馈）。", gpu);
      case "checking": return t("正在检查 {0} 能否运行本机模型（第一次约需一两分钟），完成前使用 CPU。", gpu);
      case "unchecked": return cpuOnly ? t("已选仅 CPU。选择「自动」后会先检查 {0} 能否运行本机模型。", gpu) : t("将检查 {0} 能否运行本机模型，完成前使用 CPU。", gpu);
      case "unknown": return t("本机模型运行中，结束后显示 GPU 信息。");
      case "unsupported_gpu": return t("这台手机的 {0} 驱动较旧，不能运行本机模型，使用 CPU。GPU 加速支持 Adreno 7xx/8xx（如骁龙 8 Gen 1 及更新）。", gpu);
      case "no_supported_gpu": return t("这台手机的 GPU 暂不支持（GPU 加速支持高通骁龙 Adreno 7xx/8xx），使用 CPU。");
      case "check_failed": return t("{0} 没有通过检查，使用 CPU：{1}", gpu, value.failure || t("检查没有完成"));
      case "driver_unavailable": return t("这台手机没有向应用开放 GPU 驱动，使用 CPU。");
      case "cpu_unsupported": return t("这台手机的处理器较旧，只使用 CPU。");
      case "failed": return t("GPU 曾出错，已改用 CPU：{0}", value.failure || t("引擎意外停止"));
      default: return t("本机引擎尚未就绪");
    }
  }
  function renderAccelerator(value) {
    const selector = $("localAcceleratorSelector");
    const supported = typeof native?.setLocalModelAccelerator === "function";
    selector.disabled = !supported || !value;
    if (value?.mode) selector.value = value.mode;
    status("localAcceleratorStatus", !supported ? t("当前客户端不支持选择推理设备，请更新 APK") : value ? acceleratorText(value) : "");
    $("btnRetryLocalGpu").hidden = !(["failed", "check_failed"].includes(value?.gpu_state) && typeof native?.retryLocalModelGpu === "function");
  }
  function deviceStatus() {
    if (closed) return;
    window.clearTimeout(devicePoll);
    const options = deviceOptions();
    const selected = deviceModels.find(model => model.model_id === options.model_id);
    const missing = !options.model_id || (deviceModels.length && !selected?.installed);
    const unavailable = typeof native?.getLocalModelDeviceStatus !== "function" ? t("当前客户端不支持设备测试，请更新 APK")
      : !options.model_id ? t("请先下载并校验一个本机模型") : "";
    setUnavailable($("localDeviceModelSelector"), deviceModelBusy ? deviceBusyReason : unavailable);
    setUnavailable($("btnStartLocalBenchmark"), deviceModelBusy ? deviceBusyReason : unavailable || t("正在检查本机模型"));
    setUnavailable($("btnUseLocalRecommendation"), deviceModelBusy ? deviceBusyReason : unavailable || t("正在计算推荐值"));
    if (unavailable) { deviceRecommendation = null; terms("localDeviceRecommendation", []); status("localDeviceStatus", unavailable); return; }
    try {
      const value = nativeResult("getLocalModelDeviceStatus", JSON.stringify(options));
      renderAccelerator(value.accelerator);
      deviceRecommendation = value.recommendation || null;
      const recommended = deviceRecommendation;
      const planError = value.context_plan?.error;
      if (value.context_plan?.model_max_context_tokens > 0) $("localContextCustomInput").max = String(value.context_plan.model_max_context_tokens);
      terms("localDeviceRecommendation", recommended ? [[t("推荐上下文（容量估算）"), recommended.context_tokens > 0 ? `${recommended.context_tokens} Token` : t("暂无")],
        [t("推荐线程数"), recommended.threads], [t("推荐生成超时（时间估算）"), t("{0} 秒", recommended.timeout_seconds)]] : []);
      const run = value.benchmark || {}; const running = ["queued", "running", "cancelling"].includes(run.state);
      const testFinished = deviceTestWasRunning && !running;
      deviceTestWasRunning = running;
      ui.setLocalDeviceTestBusy(running);
      if (testFinished) {
        deviceModelBusy = true;
        deviceBusyReason = t("正在刷新测试后的引擎状态");
        ui.setLocalContextBusy(true);
        const current = generation;
        localModels(() => !closed && current === generation).catch(error => {
          if (!closed && current === generation) status("localModelsStatus", error.message, true);
        });
      }
      const busyReason = running ? t("设备测试进行中，可取消后继续") : deviceModelBusy ? deviceBusyReason : "";
      const modelReason = missing ? t("请先下载并校验所选本机模型") : !deviceEngineAvailable ? t("本机引擎尚未就绪，请检查本地引擎") : "";
      const planReason = planError ? (typeof planError === "string" ? planError : planError.message || t("暂时无法计算推荐值")) : "";
      setUnavailable($("localDeviceModelSelector"), busyReason);
      setUnavailable($("btnStartLocalBenchmark"), busyReason || modelReason || (typeof native?.startLocalModelBenchmark !== "function" ? t("当前客户端不支持设备测试，请更新 APK") : ""));
      setUnavailable($("btnCancelLocalBenchmark"), !running ? t("当前没有设备测试") : typeof native?.cancelLocalModelBenchmark !== "function" ? t("当前客户端不支持取消测试") : "");
      setUnavailable($("btnUseLocalRecommendation"), busyReason || modelReason || planReason || (!recommended?.context_tokens ? t("当前可用内存无法给出推荐值") : typeof native?.applyRuntimeSettings !== "function" ? t("请在 Android 应用中调整设置") : ""));
      const display = Number.isFinite(run.prompt_tokens) || run.state && run.state !== "idle";
      terms("localDeviceBenchmark", display ? [[t("测试状态"), { queued: t("准备中"), running: t("运行中"), cancelling: t("正在取消"), cancelled: t("已取消"), completed: t("已完成"), failed: t("未完成"), interrupted: t("已中断") }[run.state] || run.state],
        ...(run.accelerator ? [[t("推理设备"), run.accelerator === "gpu" ? `GPU · ${run.gpu || ""}`.replace(/ · $/, "") : "CPU"]] : []),
        ...(run.planned_context_tokens > 0 ? [[t("尝试的上下文"), `${run.planned_context_tokens} Token`]] : []),
        [t("分配的上下文"), Number.isInteger(run.actual_context_size) && run.actual_context_size > 0 ? `${run.actual_context_size} Token` : t("未分配")],
        [t("实际测试输入"), run.prompt_tokens == null ? t("未测量") : `${run.prompt_tokens} Token`],
        [t("实际生成输出"), run.generated_tokens == null ? t("未测量") : `${run.generated_tokens} Token`],
        [t("首 Token（含加载）"), run.first_token_ms == null || run.first_token_ms < 0 ? t("未测量") : `${run.first_token_ms} ms`],
        [t("输入处理速度"), Number.isFinite(run.prompt_tokens_per_second) ? `${run.prompt_tokens_per_second.toFixed(2)} Token/s` : t("未测量")],
        [t("生成速度"), Number.isFinite(run.tokens_per_second) ? `${run.tokens_per_second.toFixed(2)} Token/s` : t("未测量")],
        [t("本轮 RSS 采样峰值（50ms）"), bytes(run.run_sampled_peak_rss_bytes)],
        [t("进程历史峰值 VmHWM"), bytes(run.process_vmhwm_after_bytes)],
        [t("测试覆盖范围"), t("仅上述实际输入长度；完整所选上下文尚未实测")], [t("设置"), t("测试不会修改自定义设置")]] : []);
      status("localDeviceStatus", run.recovery_required ? t("测试预留已过期或释放状态未知，请重启引擎后继续") : run.error || busyReason || planReason || modelReason, !!run.error || !!run.recovery_required || !!planReason);
      if (running) devicePoll = window.setTimeout(deviceStatus, 750);
    } catch (error) {
      renderAccelerator(null);
      deviceRecommendation = null; terms("localDeviceRecommendation", []);
      setUnavailable($("btnUseLocalRecommendation"), error.message);
      setUnavailable($("btnStartLocalBenchmark"), error.message);
      status("localDeviceStatus", error.message, true);
    }
  }

  async function localModels(isCurrent = () => true) {
    const [value, capabilities] = await Promise.all([ui.apiJson("/mobile/local-models"), ui.apiJson("/mobile/capabilities")]); if (!isCurrent()) return;
    for (const model of [...(value.models || []), ...(value.vision_components || []), ...(value.speech_models || [])]) model.title = modelTitle(model.title);
    const engine = value.native_engine || {}; const measurement = value.measurement || {};
    deviceEngineAvailable = !!engine.available;
    deviceModelChoices(value);
    const profile = value.context_profile;
    const plan = value.context_plan;
    const contextStatus = value.local_context_status;
    const planPending = plan?.context_plan_ready === false || profile?.context_plan_ready === false;
    const planError = plan?.context_plan_error || profile?.context_plan_error || plan?.error;
    const capacityTerms = plan ? [
      [t("当前配置上下文"), planPending ? t("等待内存恢复") : `${plan.context_size} Token`],
      [t("模型支持上限"), `${plan.model_max_context_tokens} Token`],
      [t("本机推荐"), plan.recommended_context_tokens > 0 ? `${plan.recommended_context_tokens} Token` : t("暂无")],
      [t("内存模式"), plan.memory_mode === "extended" ? t("扩展") : t("平衡")],
      [t("可用交换内存"), bytes(plan.available_swap_bytes)],
    ] : profile?.active ? [[t("上下文上限"), planPending ? t("等待内存恢复") : `${profile.context_tokens} Token`]] : [];
    const outputTokens = contextStatus?.max_output_tokens ?? profile?.max_output_tokens;
    terms("localModelSummary", [[t("当前模型"), value.model], [t("当前推理"), value.route === "embedded_qwen" ? t("本机 CPU") : value.route === "local_endpoint" ? t("本地 HTTP 引擎") : t("远程模型")], [t("本机引擎"), engine.available ? t("llama.cpp 已就绪") : engine.last_error || t("未就绪")], ...(engine.cpu_build ? [[t("CPU 指令"), engine.cpu_build === "armv8.2-dotprod" ? t("ARMv8.2 点积加速") : t("通用 ARMv8")]] : []),...capacityTerms, ...(!planPending && outputTokens != null ? [[t("每轮输出上限"), `${outputTokens} Token`]] : []), [t("可用于模型的内存"), bytes(plan?.available_ram_bytes ?? capabilities.android?.memory_usable_bytes ?? capabilities.android?.memory_available_bytes)], [t("系统空闲内存"), bytes(plan?.system_available_ram_bytes ?? capabilities.android?.memory_available_bytes)], [t("可用存储"), bytes(value.storage_free_bytes)], [t("首 Token"), measurement.first_token_ms == null ? t("未测量") : `${measurement.first_token_ms} ms`], ...(measurement.prompt_cached_tokens == null || measurement.prompt_tokens == null ? [] : [[t("复用输入"), `${measurement.prompt_cached_tokens} / ${measurement.prompt_tokens} Token`]]), ...(Number.isFinite(measurement.prompt_tokens_per_second) ? [[t("输入处理速度"), `${measurement.prompt_tokens_per_second.toFixed(2)} Token/s`]] : []), ...(Number.isInteger(measurement.threads) ? [[t("推理线程"), Number.isInteger(measurement.threads_lowest) && measurement.threads_lowest < measurement.threads ? `${measurement.threads} → ${measurement.threads_lowest} · ${t("降温")}` : `${measurement.threads}`]] : []),[t("生成速度"), measurement.tokens_per_second == null ? t("未测量") : `${measurement.tokens_per_second.toFixed(2)} Token/s`], ...(measurement.tool_grammar ? [[t("工具调用约束"), measurement.tool_grammar === "lazy" ? t("已启用 · 纠正 {0} 次", measurement.tool_grammar_resamples || 0) : measurement.tool_grammar === "abandoned" ? t("本轮中途停用") : t("不可用")]] : [])]);
    $("localContextCustomInput").max = String(plan?.model_max_context_tokens || 262144);
    $("localContextHint").textContent = planPending
      ? t("{0}。设置仍可调整；下次推理前会重新检查内存。", planError?.message || t("当前可用内存不足"))
      : plan?.reason || (typeof native?.applyRuntimeSettings === "function"
      ? t("上下文按本机可用内存与模型上限决定。更改后会重启引擎。")
      : t("请在 Android 应用中更改本机上下文与内存模式"));
    const busy = !!(ui.context().activeTask || engine.generating || value.active_task_id || value.queued_tasks || value.maintenance);
    deviceModelBusy = busy;
    deviceBusyReason = value.maintenance ? t("引擎维护中，完成后即可操作") : busy ? t("任务正在运行或排队，请等待任务结束") : "";
    ui.setLocalContextBusy(busy);
    deviceStatus();
    setUnavailable($("btnProbeLocalModel"), "");
    setUnavailable($("btnUnloadLocalModel"), deviceBusyReason || (!engine.available ? t("本机引擎尚未就绪") : ""));
    setUnavailable($("btnRestoreCloudModel"), deviceBusyReason || (typeof native?.restorePreviousProvider !== "function" ? t("请在 Android 应用中恢复模型配置") : value.route !== "embedded_qwen" ? t("当前未启用本机模型") : ""));
    status("localModelControlStatus", deviceBusyReason || (!engine.available ? engine.last_error || t("本机引擎尚未就绪") : ""));
    const entries = [...(value.models || []), ...(value.vision_components || []), ...(value.speech_models || [])];
    const list = $("localModelList"); const speechList = $("speechModelList"); const activeDownload = entries.find(model => activeDownloadStates.includes(model.state)); const downloading = !!activeDownload;
    const ids = new Set();
    for (const model of entries) {
      const projection = model.kind === "vision_projection";
      // Speech recognition weights serve the microphone button, listed in their own section.
      const speech = model.kind === "speech_recognition";
      const home = speech ? speechList : list;
      ids.add(model.model_id);
      let card = [...home.children].find(item => item.dataset.modelId === model.model_id);
      if (!card) { card = row(model.title); card.classList.add("local-model-card"); card.dataset.modelId = model.model_id; const progress = document.createElement("progress"); progress.max = 1; progress.setAttribute("aria-label", t("{0}下载进度", model.title)); card.append(progress); const links = document.createElement("div"); links.className = "model-sources"; for (const [label, address] of [[t("模型主页"), model.source_page], [t("直接下载"), model.download_url]]) { try { const url = new URL(address); if (url.protocol !== "https:") continue; const link = document.createElement("a"); link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = label; links.append(link); } catch {} } card.append(links); const actions = document.createElement("div"); actions.className = "model-actions"; card.append(actions); home.append(card); }
      const vision = !projection && model.supports_vision ? t("\n图片理解：{0}", !engine.supports_vision ? t("需支持视觉的本机引擎") : model.vision_component_installed ? t("视觉组件已就绪") : t("请下载配套视觉组件")) : "";
      card.querySelector("small").textContent = `${model.publisher || ""} · ${model.local_artifact ? t("工具训练版 · 实验") : model.official_weights ? t("官方量化") : t("社区量化")} · ${model.license || ""}\n${bytes(model.size_bytes)}${projection ? t(" · 配套图片理解组件") : speech ? t(" · 中文、英文、日语、韩语、粤语") : t(" · 预计需 {0} 可用内存", bytes(model.minimum_available_ram_bytes))}${vision}\n${model.local_artifact && !model.installed ? t("请选择此版本对应的 GGUF 文件导入") : downloadState(model)}${model.error ? t("：{0}", localizeError(model.error)) : ""}`;
      const progress = card.querySelector("progress"); progress.hidden = ![...activeDownloadStates, "paused"].includes(model.state); progress.value = model.progress || 0;
      const signature = `${model.state}:${!!model.has_local_files}:${busy}:${!!engine.available}:${activeDownload?.model_id}:${value.model}:${value.route}`;
      if (card.dataset.signature !== signature) { card.dataset.signature = signature; const actions = card.querySelector(".model-actions"); actions.replaceChildren();
        if (["queued", "downloading", "waiting_network"].includes(model.state)) namedAction(actions, "pause", t("暂停下载"), async () => { await post("/mobile/local-models/cancel", { model_id: model.model_id }); await localModels(isCurrent); });
        else if (!model.installed && model.local_artifact) { const button = namedAction(actions, "folder-open", t("导入训练模型"), () => { nativeResult("importLocalModel", model.model_id); status("localModelsStatus", t("请选择训练模型文件，导入后将自动校验")); }); button.disabled = busy || typeof native?.importLocalModel !== "function"; }
        else if (!model.installed && model.state !== "verifying") { const button = namedAction(actions, "download", model.downloaded_bytes ? t("继续下载") : projection ? t("下载视觉组件") : speech ? t("下载语音模型") : t("下载模型"), async () => { await post("/mobile/local-models/download", { model_id: model.model_id, ...downloadSource(model) }); await localModels(isCurrent); }); setUnavailable(button, downloading ? t("{0} 正在{1}，完成或暂停后可下载", activeDownload.title || activeDownload.model_id, activeDownload.state === "verifying" ? t("校验") : t("下载")) : ""); }
        if (model.installed && !projection && !speech) { const button = namedAction(actions, "play", value.model === model.model_id && value.route === "embedded_qwen" ? t("当前模型") : t("使用此模型"), () => {
          nativeResult("selectLocalModel", model.model_id); status("localModelsStatus", t("模型配置已保存，正在切换引擎"));
          // After the restart the model reads its instructions once, ahead of the first message (app/27-setup.js).
          try { window.localStorage.setItem("agent-mobile-setup-pending-v1", JSON.stringify({ prepare: model.model_id })); } catch { /* it reads them with the first message instead */ }
        }); button.disabled = busy || !engine.available || typeof native?.selectLocalModel !== "function"; }
        if (model.has_local_files || model.installed || model.downloaded_bytes) { const button = namedAction(actions, "trash-2", projection ? t("移除视觉组件") : speech ? t("移除语音模型") : t("移除模型"), async () => { if (!window.confirm(t("移除 {0} 的已下载文件？", model.title))) return; await post("/mobile/local-models/remove", { model_id: model.model_id }); await localModels(isCurrent); }); button.disabled = busy || activeDownloadStates.includes(model.state); }
      }
      let actionStatus = card.querySelector(".model-action-status");
      if (!actionStatus) { actionStatus = document.createElement("p"); actionStatus.className = "model-action-status"; actionStatus.setAttribute("role", "status"); card.append(actionStatus); }
      actionStatus.textContent = !model.installed && downloading && model.model_id !== activeDownload.model_id ? t("{0} 正在{1}，完成或暂停后可下载", activeDownload.title || activeDownload.model_id, activeDownload.state === "verifying" ? t("校验") : t("下载")) : "";
      actionStatus.hidden = !actionStatus.textContent;
    }
    for (const card of [...list.children, ...speechList.children]) if (!ids.has(card.dataset.modelId)) card.remove();
    voiceInputSettings();
    status("localModelsStatus", "");
    window.clearTimeout(modelPoll);
    if (downloading || busy) modelPoll = window.setTimeout(() => { if (!closed && !$("settingsLocalModels").hidden && !$("settingsOverlay").hidden) localModels(isCurrent).catch(error => status("localModelsStatus", error.message, true)); }, 2000);
  }
  // The microphone button's recognizer (VoiceInputSettings.kt); only the Android app has one.
  function voiceInputSettings(value = null) {
    const row = $("offlineVoiceRow"), toggle = $("offlineVoiceToggle");
    if (!value) {
      if (typeof native?.getVoiceInputSettings !== "function") { row.hidden = true; status("offlineVoiceStatus", ""); return; }
      try { value = JSON.parse(native.getVoiceInputSettings()); } catch { row.hidden = true; return; }
    }
    row.hidden = false;
    toggle.checked = !!value.prefer_offline;
    toggle.disabled = !value.runtime_available;
    status("offlineVoiceStatus", !value.runtime_available ? t("这台设备不支持离线语音识别（需要 64 位 ARM 处理器），麦克风按钮使用系统语音识别")
      : !value.model_installed ? t("下载下面的语音模型后，麦克风按钮即可离线识别")
      : value.uses_offline ? t("麦克风按钮使用离线识别") : t("麦克风按钮使用系统语音识别"));
  }
  $("offlineVoiceToggle").addEventListener("change", () => {
    try { voiceInputSettings(JSON.parse(native.setVoiceInputPreferOffline($("offlineVoiceToggle").checked))); }
    catch (error) { status("offlineVoiceStatus", error.message || t("操作失败"), true); }
  });
  const pages = {
    About: ["about", about, "updateStatus"], Memory: ["memory", memory, "memoryStatus"], Knowledge: ["knowledge", knowledge, "knowledgeStatus"], Services: ["services", services, "servicesStatus"], GlobalEntry: ["globalEntry", globalEntry, "globalEntryStatus"], NotificationRules: ["notificationRules", notificationRules, "notificationRulesStatus"], Backup: ["backup", backup, "backupStatus"], Doctor: ["doctor", doctor, "doctorStatus"], Extensions: ["extensions", extensions, "extensionsStatus"], Skills: ["skills", skills, "skillsStatus"], Schedules: ["schedules", schedules, "schedulesStatus"], Connections: ["connections", connections, "connectionsStatus"], Outbox: ["outbox", outbox, "outboxStatus"], Workflows: ["workflows", workflows, "workflowsStatus"], Evaluations: ["evaluations", evaluations, "evaluationsStatus"], LocalModels: ["localModels", localModels, "localModelsStatus"],
  };
  for (const [name, [route, loader, statusId]] of Object.entries(pages)) on(`btn${name}Page`, "click", () => page(route, loader, statusId), statusId);

  // Menu search covers the menu rows and the labelled settings inside every page, so a setting
  // can be found without knowing which page holds it.
  const flat = (value) => (value || "").replace(/\s+/g, " ").trim();
  function shown(element, page) {
    for (let node = element; node && node !== page; node = node.parentElement) if (node.hidden) return false;
    return true;
  }
  function menuSearchEntries() {
    const entries = [];
    for (const button of $("settingsHome").querySelectorAll(".menu-section .menu-row")) {
      if (button.hidden || button.closest("[hidden]")) continue;
      const label = button.querySelector("span:not([data-icon])");
      entries.push({ button, title: flat(label?.childNodes[0]?.textContent), detail: flat(label?.querySelector("small")?.textContent), keywords: button.dataset.keywords || "" });
    }
    for (const page of document.querySelectorAll("#settingsScrollBody > .settings-page")) {
      const name = page.id.replace(/^settings/, "");
      const button = $(`btn${name}Page`);
      if (!button || button.hidden || button.closest("[hidden]") || page.id === "settingsHome") continue;
      const pageTitle = flat(button.querySelector("span:not([data-icon])")?.childNodes[0]?.textContent);
      const candidates = page.querySelectorAll(".management-section > strong, label, summary, .form-title, .menu-row > span:not([data-icon])");
      for (const target of candidates) {
        const title = flat(target.childNodes[0]?.textContent || target.textContent);
        if (!title || title === pageTitle || !shown(target, page)) continue;
        entries.push({ button, title, detail: pageTitle, keywords: "", target: target.closest("label, details, .management-section, .menu-row") || target });
      }
    }
    return entries;
  }
  function renderMenuSearch() {
    const terms = $("menuSearchInput").value.toLowerCase().split(/\s+/).filter(Boolean);
    const searching = terms.length > 0;
    const sections = [...$("settingsHome").querySelectorAll(".menu-section")];
    // Index while the sections are visible: hidden entries are left out on purpose.
    for (const section of sections) section.hidden = false;
    const entries = searching ? menuSearchEntries() : [];
    for (const section of sections) section.hidden = searching;
    const results = $("menuSearchResults");
    results.replaceChildren();
    results.hidden = !searching;
    $("menuSearchEmpty").hidden = true;
    if (!searching) return;
    const seen = new Set();
    const matches = entries.filter((entry) => {
      const text = `${entry.title} ${entry.detail} ${entry.keywords}`.toLowerCase();
      const key = `${entry.button.id}|${entry.title}`;
      if (seen.has(key) || !terms.every((term) => text.includes(term))) return false;
      seen.add(key);
      return true;
    }).sort((a, b) => Number(!!a.target) - Number(!!b.target)).slice(0, 30);
    for (const entry of matches) {
      const item = document.createElement("button");
      item.type = "button"; item.className = "menu-row";
      const symbol = document.createElement("span"); symbol.dataset.icon = entry.button.querySelector("[data-icon]")?.dataset.icon || "search"; symbol.innerHTML = icon(symbol.dataset.icon);
      const label = document.createElement("span"); label.textContent = entry.title;
      if (entry.detail) { const small = document.createElement("small"); small.textContent = entry.detail; label.append(small); }
      const chevron = document.createElement("span"); chevron.dataset.icon = "chevron-right"; chevron.innerHTML = icon("chevron-right");
      item.append(symbol, label, chevron);
      item.addEventListener("click", () => {
        entry.button.click();
        if (!entry.target) return;
        // The page renders its data asynchronously; scroll once it is on screen.
        window.setTimeout(() => {
          entry.target.scrollIntoView?.({ block: "center", behavior: "smooth" });
          entry.target.classList.add("search-hit");
          window.setTimeout(() => entry.target.classList.remove("search-hit"), 1600);
        }, 350);
      });
      results.append(item);
    }
    results.hidden = !matches.length;
    $("menuSearchEmpty").hidden = matches.length > 0;
  }
  // Updates and diagnostic logs need the Android app; a browser companion has neither.
  $("btnAboutPage").hidden = !native;
  $("menuSearchInput").addEventListener("input", renderMenuSearch);
  $("menuSearchInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") $("menuSearchResults").querySelector(".menu-row")?.click();
    if (event.key === "Escape" && $("menuSearchInput").value) { event.stopPropagation(); $("menuSearchInput").value = ""; renderMenuSearch(); }
  });
  // Back from a computer's page, the list shows what that page saw meanwhile (online, unreachable).
  new MutationObserver((records) => {
    const left = records.some((record) => record.oldValue === null);
    if (left && $("settingsComputer").hidden && !$("settingsConnections").hidden) {
      connections(() => !closed && !$("settingsConnections").hidden, true).catch(() => {});
    }
  }).observe($("settingsComputer"), { attributes: true, attributeFilter: ["hidden"], attributeOldValue: true });
  // A closed menu forgets its query, so the next open shows the full menu again.
  new MutationObserver(() => {
    if ($("settingsOverlay").hidden && $("menuSearchInput").value) { $("menuSearchInput").value = ""; renderMenuSearch(); }
  }).observe($("settingsOverlay"), { attributes: true, attributeFilter: ["hidden"] });
  updates();
  for (const [name, loader, statusId] of [["Doctor", doctor, "doctorStatus"], ["Extensions", extensions, "extensionsStatus"], ["Outbox", outbox, "outboxStatus"]]) on(`btn${name}Refresh`, "click", () => loader(), statusId);
  on("memoryForm", "submit", async () => {
    const content = $("memoryContent").value.trim();
    if (!content) return;
    const topic = $("memoryTopic").value || undefined;
    let value;
    try {
      value = memoryEditing
        ? await post("/mobile/memory/update", { id: memoryEditing, content, topic })
        : await post("/mobile/memory", { content, topic });
    } catch (error) { throw new Error(memoryMessage(error)); }
    stopMemoryEdit();
    await memory(undefined, value);
  }, "memoryStatus");
  on("btnCancelMemoryEdit", "click", () => stopMemoryEdit(), "memoryStatus");
  $("memorySearch").addEventListener("input", () => { memoryFilter.query = $("memorySearch").value; if (memoryValue) memory(undefined, memoryValue); });
  for (const [id, key] of [["memoryEnabledToggle", "enabled"], ["memoryAutoToggle", "auto"]]) {
    on(id, "change", async () => {
      try { await memory(undefined, await post("/mobile/memory/settings", { [key]: $(id).checked })); }
      catch (error) { $(id).checked = !$(id).checked; throw error; }
    }, "memoryStatus");
  }
  on("appNotesToggle", "change", async () => {
    try { await appNotes(undefined, await post("/mobile/app-notes", { action: "set_enabled", enabled: $("appNotesToggle").checked })); }
    catch (error) { $("appNotesToggle").checked = !$("appNotesToggle").checked; throw error; }
  }, "appNotesStatus");
  for (const [id, key] of [["knowledgeEnabledToggle", "enabled"], ["knowledgeAutoToggle", "auto"]]) {
    on(id, "change", async () => {
      try { await knowledge(undefined, await post("/mobile/knowledge/settings", { [key]: $(id).checked })); }
      catch (error) { $(id).checked = !$(id).checked; throw new Error(knowledgeMessage(error)); }
    }, "knowledgeStatus");
  }
  on("knowledgeSemanticToggle", "change", async () => {
    try { await knowledge(undefined, await post("/mobile/knowledge/semantic", { enabled: $("knowledgeSemanticToggle").checked })); }
    catch (error) { $("knowledgeSemanticToggle").checked = !$("knowledgeSemanticToggle").checked; throw new Error(knowledgeMessage(error)); }
  }, "knowledgeSemanticStatus");
  on("btnKnowledgeSemanticDownload", "click", async () => {
    // The same download as on the local models page (Hugging Face or ModelScope, checked against its SHA-256).
    await post("/mobile/local-models/download", { model_id: "embeddinggemma-300m-q8-0", source: "auto",
      prefer: downloadSource({}).prefer });
    await knowledge();
  }, "knowledgeSemanticStatus");
  on("btnKnowledgeSemanticRemove", "click", async () => {
    if (!window.confirm(t("移除按意思检索的模型？已整理好的文档要重新下载模型后才能再按意思检索。"))) return;
    await post("/mobile/local-models/remove", { model_id: "embeddinggemma-300m-q8-0" });
    await knowledge();
  }, "knowledgeSemanticStatus");
  $("btnKnowledgeAdd").addEventListener("click", () => { if (!knowledgeUploading) $("knowledgeFileInput").click(); });
  // A link shared into a conversation: offer to save the page to the knowledge base as well.
  let linkClip = "";
  let linkClipTimer = 0;
  const linkPattern = /(?:https?:\/\/|www\.)[^\s<>"'，。、；！？）】]+/i; // i18n-ignore: punctuation that ends a link
  function hideLinkClip() {
    window.clearTimeout(linkClipTimer);
    const notice = $("linkClipNotice");
    if (notice.hidden) return;
    const motion = window.MobileMotion;
    if (motion && motion.level() !== "off") motion.exit(notice, { transform: "translateY(6px)" });
    else notice.hidden = true;
  }
  window.addEventListener("agent-shared-text", (event) => {
    const text = typeof event.detail === "string" ? event.detail : "";
    if (closed || !linkPattern.test(text)) return;
    linkClip = text;
    window.clearTimeout(linkClipTimer);
    $("linkClipText").textContent = t("分享的网页可以存入知识库");
    $("btnLinkClipSkills").hidden = true;
    $("btnLinkClipSave").hidden = false;
    $("btnLinkClipSave").disabled = false;
    const notice = $("linkClipNotice");
    if (window.MobileMotion) window.MobileMotion.enter(notice, { transform: "translateY(10px) scale(.96)" }, { spring: "bouncy" });
    else notice.hidden = false;
  });
  $("btnLinkClipDismiss").addEventListener("click", hideLinkClip);
  // Background running: phone makers that freeze unknown apps make every reply crawl or fail,
  // whichever model is used. Ask once on such phones, and whenever the engine was just paused.
  const backgroundKey = "agent-background-notice";
  let backgroundStep = "";
  let backgroundLatestPause = 0;
  let backgroundLatestKill = 0;
  function backgroundSeen() { try { return JSON.parse(localStorage.getItem(backgroundKey) || "{}") || {}; } catch { return {}; } }
  function rememberBackground(change) { try { localStorage.setItem(backgroundKey, JSON.stringify({ ...backgroundSeen(), ...change })); } catch { /* per-viewer only */ } }
  function backgroundRunState() {
    if (typeof native?.getBackgroundRunState !== "function") return null;
    try { return JSON.parse(native.getBackgroundRunState()); } catch { return null; }
  }
  function checkBackgroundRun() {
    if (closed || document.hidden) return;
    const value = backgroundRunState();
    if (!value) return;
    const seen = backgroundSeen();
    const now = Date.now();
    const pauses = (value.pauses || []).filter((pause) => pause.screen_on && now - pause.at_ms < 15 * 60 * 1000
      && pause.at_ms > (seen.acknowledged_pause || 0));
    const recent = pauses[pauses.length - 1];
    // The engine process ended by Android or the phone maker (not the user or an update) in the last day.
    const kills = (value.recent_engine_kills || []).filter((exit) => exit.timestamp > (seen.acknowledged_kill || 0));
    backgroundLatestPause = Math.max(0, ...(value.pauses || []).map((pause) => pause.at_ms || 0));
    backgroundLatestKill = Math.max(0, ...(value.recent_engine_kills || []).map((exit) => exit.timestamp || 0));
    let text = "";
    backgroundStep = "";
    if (recent) {
      text = t("系统刚才把 Agent 引擎暂停了 {0} 秒，回复会因此变慢或失败。", recent.seconds);
      backgroundStep = value.battery_optimization_exempt ? "autostart" : "battery";
    } else if (kills.length && !(value.battery_optimization_exempt && seen.autostart_opened)) {
      text = t("最近一天 Agent 引擎被系统结束了 {0} 次，正在进行的任务会因此中断。", kills.length);
      backgroundStep = value.battery_optimization_exempt ? "autostart" : "battery";
    } else if (value.strict_maker && now - (seen.dismissed_at || 0) > 7 * 24 * 60 * 60 * 1000) {
      if (!value.battery_optimization_exempt) {
        text = t("{0}手机会限制应用在后台运行，AI 回复可能很慢或失败。", value.maker);
        backgroundStep = "battery";
      } else if (!seen.autostart_opened && value.steps) {
        text = t("还差一步：{0}", value.steps);
        backgroundStep = "autostart";
      }
    }
    const notice = $("backgroundNotice");
    if (!backgroundStep) { notice.hidden = true; return; }
    $("backgroundNoticeText").textContent = text;
    $("btnBackgroundFix").textContent = backgroundStep === "battery" ? t("允许后台运行") : t("打开设置");
    if (notice.hidden) {
      if (window.MobileMotion) window.MobileMotion.enter(notice, { transform: "translateY(10px) scale(.96)" }, { spring: "bouncy" });
      else notice.hidden = false;
    }
  }
  $("btnBackgroundFix").addEventListener("click", () => {
    if (backgroundStep === "battery") native?.requestBackgroundRun?.();
    else { native?.openAutoStartSettings?.(); rememberBackground({ autostart_opened: true }); }
    rememberBackground({ acknowledged_pause: backgroundLatestPause, acknowledged_kill: backgroundLatestKill });
    $("backgroundNotice").hidden = true;
  });
  $("btnBackgroundDismiss").addEventListener("click", () => {
    rememberBackground({ dismissed_at: Date.now(), acknowledged_pause: backgroundLatestPause, acknowledged_kill: backgroundLatestKill });
    $("backgroundNotice").hidden = true;
  });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) window.setTimeout(checkBackgroundRun, 600); });
  window.setTimeout(checkBackgroundRun, 1500);
  const backgroundPoll = window.setInterval(() => { if (closed) window.clearInterval(backgroundPoll); else checkBackgroundRun(); }, 15000);
  $("btnLinkClipSave").addEventListener("click", async () => {
    const button = $("btnLinkClipSave");
    button.disabled = true;
    $("linkClipText").textContent = t("正在保存网页...");
    try {
      const saved = await post("/mobile/knowledge/url", { url: linkClip });
      if (closed) return;
      button.hidden = true;
      $("linkClipText").textContent = saved.added?.duplicate ? t("这个网页已经在知识库里了") : t("已存入知识库，正在读取内容");
      linkClipTimer = window.setTimeout(hideLinkClip, 4000);
      if (!$("settingsKnowledge").hidden) knowledge(undefined, saved).catch(() => {});
    } catch (error) {
      if (closed) return;
      $("linkClipText").textContent = knowledgeMessage(error);
      button.disabled = false;
    }
  });
  // A web page: saved as it is now, into the knowledge base shown on the page.
  $("btnKnowledgeLink").addEventListener("click", () => {
    const form = $("knowledgeUrlForm");
    form.hidden = !form.hidden;
    if (!form.hidden) $("knowledgeUrlInput").focus();
  });
  $("btnKnowledgeUrlCancel").addEventListener("click", () => { $("knowledgeUrlForm").hidden = true; $("knowledgeUrlInput").value = ""; });
  $("knowledgeUrlForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const url = $("knowledgeUrlInput").value.trim();
    if (!url || knowledgeUploading) return;
    knowledgeUploading = true;
    $("btnKnowledgeUrlSave").disabled = true;
    status("knowledgeStatus", t("正在保存网页..."));
    let saved = null;
    try {
      saved = await post("/mobile/knowledge/url", { url, ...(knowledgeFilter ? { collection: knowledgeFilter } : {}) });
    } catch (error) { status("knowledgeStatus", knowledgeMessage(error), true); }
    finally {
      knowledgeUploading = false;
      $("btnKnowledgeUrlSave").disabled = false;
    }
    if (!saved || closed) return;
    $("knowledgeUrlInput").value = "";
    $("knowledgeUrlForm").hidden = true;
    await knowledge(undefined, saved);
    status("knowledgeStatus", saved.added?.duplicate ? t("这个网页已经在知识库里了") : t("已保存网页，正在读取内容"));
  });
  $("knowledgeFileInput").addEventListener("change", () => {
    const files = [...$("knowledgeFileInput").files];
    $("knowledgeFileInput").value = "";
    uploadKnowledgeFiles(files).catch((error) => { if (!closed) status("knowledgeStatus", knowledgeMessage(error), true); });
  });
  on("knowledgeSearchForm", "submit", searchKnowledge, "knowledgeStatus");
  $("knowledgeFilter").addEventListener("change", () => {
    knowledgeFilter = $("knowledgeFilter").value;
    $("knowledgeResults").replaceChildren();
    knowledge().catch((error) => { if (!closed) status("knowledgeStatus", knowledgeMessage(error), true); });
  });
  on("btnKnowledgeBaseCreate", "click", async () => {
    const name = window.prompt(t("新知识库的名称，例如“工作”或“学习”"), "");
    if (name === null || !name.trim()) return;
    let value;
    try { value = await post("/mobile/knowledge/collections/create", { name: name.trim() }); }
    catch (error) { throw new Error(knowledgeMessage(error)); }
    const created = (value.collections || []).find((collection) => collection.name === name.trim().replace(/\s+/g, " "));
    if (created) knowledgeFilter = created.id;  // show the new, empty knowledge base, ready for documents
    await knowledge(undefined, value);
    status("knowledgeStatus", t("已新建知识库“{0}”，可以往里添加文档了", name.trim()));
  }, "knowledgeStatus");
  $("btnKnowledgeChip").addEventListener("click", () => {
    if ($("settingsOverlay").hidden) ui.openMenu?.();
    page("conversationKnowledge", conversationKnowledge, "conversationKnowledgeStatus");
  });
  on("btnConversationKnowledgeDefault", "click", () => saveConversationKnowledge(null), "conversationKnowledgeStatus");
  $("btnConversationKnowledgeManage").addEventListener("click", () => page("knowledge", knowledge, "knowledgeStatus"));
  window.addEventListener("agent-session-changed", () => { void knowledgeChip(); });
  window.addEventListener("agent-knowledge-changed", () => { void knowledgeChip(); });
  if (ui.context().sessionId) void knowledgeChip();
  on("btnSaveKnowledgeSynonyms", "click", async () => {
    let saved;
    try { saved = await post("/mobile/knowledge/synonyms", { text: $("knowledgeSynonyms").value }); }
    catch (error) { throw new Error(knowledgeMessage(error)); }
    $("knowledgeSynonyms").blur();  // so the saved, tidied list replaces what was typed
    await knowledge(undefined, saved);
    status("knowledgeStatus", t("已保存同义词"));
  }, "knowledgeStatus");
  on("notificationRulesToggle", "change", async () => {
    const enabled = $("notificationRulesToggle").checked;
    try { await notificationRules(undefined, await post("/mobile/notification-rules/settings", { enabled })); }
    catch (error) { $("notificationRulesToggle").checked = !enabled; throw error; }
    if (enabled && !nativeResult("getNotificationAccess").granted) {
      native.openNotificationAccessSettings();
      status("notificationRulesStatus", t("请在系统设置里允许 Agent Workspace 读取通知，返回后规则就会生效"));
    }
  }, "notificationRulesStatus");
  on("btnNotificationAccess", "click", () => { native?.openNotificationAccessSettings?.(); }, "notificationRulesStatus");
  on("notificationRuleForm", "submit", async () => {
    const select = $("notificationRuleApp");
    if (!select.value) throw new Error(t("请选择一个应用"));
    const prompt = $("notificationRulePrompt").value.trim();
    if (!prompt) throw new Error(t("请写下收到通知时要做什么"));
    let packageName = select.value;
    let appLabel = select.selectedOptions[0]?.textContent || select.value;
    if (packageName === "__other__") {
      packageName = (window.prompt(t("输入应用的包名，例如 com.tencent.mm")) || "").trim();
      if (!packageName) return;
      if (!/^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$/.test(packageName)) throw new Error(t("包名格式不对，例如 com.tencent.mm"));
      appLabel = packageName;
    }
    const context = ui.context();
    const value = await post("/mobile/notification-rules", {
      package: packageName, app_label: appLabel,
      keywords: $("notificationRuleKeywords").value, prompt, confirm: $("notificationRuleConfirm").checked,
      session_id: context.sessionId, model: context.settings.model, reasoning_effort: context.settings.reasoning_effort,
    });
    select.value = "";
    $("notificationRuleKeywords").value = "";
    $("notificationRulePrompt").value = "";
    $("notificationRuleConfirm").checked = true;
    await notificationRules(undefined, value);
    status("notificationRulesStatus", value.enabled ? t("规则已添加") : t("规则已添加；打开上面的开关后才会生效"));
  }, "notificationRulesStatus");
  on("btnBrowserTest", "click", async () => {
    status("browserStatus", t("正在打开 example.com..."));
    const result = await post("/mobile/browser/test", {});
    const shot = result.screenshot || {};
    status("browserStatus", shot.blank
      ? t("网页已打开（{0}），但截图是空白的：这台手机不能给后台网页截图，AI 会改用读取文字", result.title || result.url)
      : t("浏览器正常：已打开“{0}”，截图 {1}×{2}", result.title || result.url, shot.width, shot.height));
  }, "browserStatus");
  on("btnBrowserClear", "click", async () => {
    if (!window.confirm(t("清除内置浏览器的登录状态、Cookie 和网站数据？"))) return;
    await post("/mobile/browser/clear", {});
    status("browserStatus", t("已清除浏览数据"));
  }, "browserStatus");
  on("floatingBallToggle", "change", async () => {
    const result = nativeResult("setFloatingBall", $("floatingBallToggle").checked);
    if (result.permission_required) {
      ballPermissionAsked = true;
      status("globalEntryStatus", t("请在打开的列表里找到 Agent Workspace，允许它“显示在其他应用上层”，返回后悬浮球就会出现"));
    } else await globalEntry();
  }, "globalEntryStatus");
  on("btnAddQuickTile", "click", () => { nativeResult("requestQuickSettingsTile"); }, "globalEntryStatus");
  for (const id of ["btnPinWidgetAsk", "btnPinWidgetTasks", "btnPinWidgetQuickTasks"]) {
    on(id, "click", () => {
      const asked = JSON.parse(native.requestPinWidget($(id).dataset.widget) || "{}").ok === true;
      // The launcher shows its own confirmation; a launcher without pinning needs the manual route.
      status("globalEntryStatus", asked ? t("请在弹出的窗口里确认添加") : t("无法自动添加，请长按桌面空白处，从“小组件”里添加"), !asked);
    }, "globalEntryStatus");
  }
  on("servicesKeepAwakeToggle", "change", async () => {
    try { await services(undefined, await post("/mobile/services/settings", { keep_awake: $("servicesKeepAwakeToggle").checked })); }
    catch (error) { $("servicesKeepAwakeToggle").checked = !$("servicesKeepAwakeToggle").checked; throw error; }
  }, "servicesStatus");
  on("btnClearMemory", "click", async () => {
    if (!window.confirm(t("清空全部记忆？这不能撤销。"))) return;
    stopMemoryEdit();
    await memory(undefined, await post("/mobile/memory/clear", {}));
  }, "memoryStatus");
  on("btnAccessibilitySettings", "click", () => native?.openAccessibilitySettings?.(), "doctorStatus");
  on("backgroundScreenToggle", "change", async () => {
    // Turning it on needs the user to read and accept the safety notice first.
    if ($("backgroundScreenToggle").checked && !window.confirm(t("开启后台操作前请确认：\n\n· 对话里的手机任务会在一块你看不到的屏幕上进行。\n· 需要 Shizuku 给本应用授予更高的系统权限；只在你自己的手机上开启，只给你信任的应用授权。\n· 需要审批的操作照样先问你；付款、转账一律不做；你设为禁止的应用，AI 不会读取或操作。\n· 可以随时在「设备与工具」里查看后台屏幕、移到前台或关闭。\n· 不使用时，建议在 Shizuku 里停止服务，并关闭无线调试。\n\n确定开启吗？"))) {
      $("backgroundScreenToggle").checked = false;
      return;
    }
    try { backgroundScreen(await post("/mobile/background-screen", { enabled: $("backgroundScreenToggle").checked })); }
    catch (error) { $("backgroundScreenToggle").checked = !$("backgroundScreenToggle").checked; throw error; }
    // Shizuku asks for permission in its own dialog; the answer shows a moment later.
    setTimeout(() => { if (!closed) loadBackgroundScreen().catch(() => {}); }, 4000);
  }, "backgroundScreenStatus");
  // Opens the background screen if needed and shows what is on it now.
  on("btnBackgroundLook", "click", async () => {
    const value = await post("/mobile/background-screen", { action: "open" });
    backgroundScreen(value);
    if (value.error) { status("backgroundScreenStatus", value.error, true); return; }
    await new Promise((resolve) => setTimeout(resolve, 600));
    const { jpeg_base64: picture } = await ui.apiJson("/mobile/background-screen/picture");
    $("backgroundScreenPicture").hidden = !picture;
    if (picture) $("backgroundScreenPicture").src = `data:image/jpeg;base64,${picture}`;
    else status("backgroundScreenStatus", t("后台屏幕已打开，还没有画面（上面没有打开应用）"));
  }, "backgroundScreenStatus");
  on("btnBackgroundToFront", "click", async () => {
    const value = await post("/mobile/background-screen", { action: "bring_to_front" });
    backgroundScreen(value);
    if (value.moved === false) status("backgroundScreenStatus", value.error || t("操作失败"), true);
  }, "backgroundScreenStatus");
  on("btnRepairAccessibility", "click", async () => {
    let result = {};
    try { result = JSON.parse(native?.repairAccessibility?.() || "{}"); } catch {}
    if (!result.ok) { status("doctorStatus", result.opened_settings ? t("在列表里找到 Agent Workspace，关掉再打开") : t("操作失败"), !result.opened_settings); return; }
    status("doctorStatus", t("已重新启用，正在确认…"));
    await new Promise((resolve) => setTimeout(resolve, 2500));
    if (!closed) await doctor();
  }, "doctorStatus");
  on("btnAddBlockedApp", "click", () => {
    const picker = $("blockedAppPicker");
    picker.hidden = !picker.hidden;
    if (picker.hidden) return;
    if (!launcherApps) launcherApps = parsed(native?.listLauncherApps?.());
    $("blockedAppSearch").value = "";
    blockedAppChoices();
    $("blockedAppSearch").focus();
  }, "doctorStatus");
  on("blockedAppSearch", "input", () => blockedAppChoices(), "doctorStatus");
  on("systemPaused", "change", async () => { native?.setSystemPaused?.($("systemPaused").checked); await doctor(); }, "doctorStatus");
  // Turning the live screen on goes through Android's consent dialog; the page follows its outcome.
  let livePoll = null;
  function followLiveScreen(wanted, tries = 0) {
    window.clearTimeout(livePoll);
    livePoll = window.setTimeout(async () => {
      if (closed || $("settingsDoctor").hidden || $("settingsOverlay").hidden) return;
      try { await doctor(); } catch { /* The next look or the refresh button reports it. */ }
      if ($("liveScreenToggle").checked !== wanted && tries < 20) followLiveScreen(wanted, tries + 1);
    }, 1500);
  }
  on("liveScreenToggle", "change", () => {
    const wanted = $("liveScreenToggle").checked;
    if (wanted) native?.startLiveScreen?.(); else native?.stopLiveScreen?.();
    followLiveScreen(wanted);
  }, "doctorStatus");
  on("btnTakeover", "click", async () => { native?.requestSystemTakeover?.(); await doctor(); }, "doctorStatus");
  on("btnObserveScreen", "click", async () => { const response = await post("/mobile/android-system", { action: "observe" }); $("systemObservation").hidden = false; $("systemObservation").textContent = JSON.stringify(response.observation || response, null, 2); }, "doctorStatus");
  on("btnBatterySettings", "click", () => native?.openBatteryOptimizationSettings?.(), "doctorStatus");
  on("btnBackgroundSettings", "click", () => native?.openAppBackgroundSettings?.(), "doctorStatus");
  on("btnAllowBackground", "click", () => native?.requestBackgroundRun?.(), "doctorStatus");
  async function skillCall(work) { try { return await work(); } catch (error) { throw new Error(skillError(error.message)); } }
  on("skillsImportForm", "submit", () => skillCall(async () => {
    const spec = $("skillsGithubInput").value.trim();
    if (!spec) throw new Error(t("请输入 GitHub 仓库，例如 owner/repo"));
    showSkillsPreview(null);
    showSkillsPreview(await skillsJob(await post("/mobile/skills/preview", { github: spec }), t("正在从 GitHub 获取…")));
    status("skillsStatus", t("请确认要安装的技能"));
  }), "skillsStatus");
  on("btnSkillsFile", "click", () => $("skillsFileInput").click(), "skillsStatus");
  $("skillsFileInput").addEventListener("change", async () => {
    const file = $("skillsFileInput").files?.[0];
    $("skillsFileInput").value = "";
    if (!file) return;
    showSkillsPreview(null);
    status("skillsStatus", t("正在读取 {0}…", file.name));
    try {
      showSkillsPreview(await ui.apiJson(`/mobile/skills/upload?filename=${encodeURIComponent(file.name)}`, {
        method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file,
      }));
      status("skillsStatus", t("请确认要安装的技能"));
    } catch (error) { status("skillsStatus", skillError(error.message) || t("操作失败"), true); }
  });
  on("btnSkillsInstall", "click", () => skillCall(async () => {
    if (!skillsPreview) return;
    const preview = skillsPreview;
    showSkillsPreview(null);
    await skills(undefined, await post("/mobile/skills/install", { token: preview.token }));
    $("skillsGithubInput").value = "";
    if (preview.source?.kind === "shared" && sharedSigner && !sharedSigner.own) rememberSigner(sharedSigner.fingerprint, preview.name);
    status("skillsStatus", t("已安装「{0}」，新对话里 AI 会按需使用这些技能", preview.name));
  }), "skillsStatus");
  on("btnSkillsCancel", "click", () => { showSkillsPreview(null); status("skillsStatus", ""); }, "skillsStatus");
  on("btnSkillsPasteCode", "click", async () => {
    const text = window.prompt(t("粘贴技能的分享码"), "");
    if (!text) return;
    showSkillsPreview(null);
    const read = readSkillCode(text);
    sharedSigner = read.signer;
    showSkillsPreview(await post("/mobile/skills/preview-shared", { name: read.skill.name, files: read.skill.files, signer: read.signer.fingerprint || null })
      .catch((error) => { throw new Error(skillError(error.message)); }));
    status("skillsStatus", t("请确认要安装的技能"));
  }, "skillsStatus");
  on("btnSkillsOfficial", "click", () => skillCall(async () => {
    const record = await skillsJob(await post("/mobile/skills/install-official", {}), t("正在下载官方技能…"));
    await skills();
    await refreshOfficial(() => !closed, false);
    status("skillsStatus", t("官方技能 {0} 已安装", skillVersion(record?.version)));
  }), "skillsStatus");
  on("btnSkillsCheckUpdates", "click", () => skillCall(async () => {
    await refreshOfficial(() => !closed, true);
    const packs = await skillsJob(await post("/mobile/skills/check-updates", {}), t("正在检查更新…"));
    await skills();
    const available = (packs || []).filter((pack) => pack.update?.available).length;
    status("skillsStatus", available ? t("{0} 个技能包有新版本", available) : t("技能包都是最新的"));
  }), "skillsStatus");
  // Quick import: a GitHub repository shared into the app opens the Skills page with it filled in.
  window.addEventListener("agent-shared-text", (event) => {
    const text = typeof event.detail === "string" ? event.detail : "";
    const match = text.match(/https?:\/\/github\.com\/[A-Za-z0-9-]+\/[A-Za-z0-9._-]+(?:\/(?:tree|releases\/tag)\/[^\s]+)?/);
    if (closed || !match) return;
    $("skillsGithubInput").value = match[0];
    $("linkClipText").textContent = t("这是 GitHub 仓库，可以作为技能包导入");
    $("btnLinkClipSave").hidden = true;
    const button = $("btnLinkClipSkills");
    button.hidden = false;
    const notice = $("linkClipNotice");
    if (notice.hidden) { if (window.MobileMotion) window.MobileMotion.enter(notice, { transform: "translateY(10px) scale(.96)" }, { spring: "bouncy" }); else notice.hidden = false; }
  });
  $("btnLinkClipSkills").addEventListener("click", () => {
    hideLinkClip();
    if ($("settingsOverlay").hidden) ui.openMenu?.();
    $("skillsImportSection").open = true;
    page("skills", skills, "skillsStatus");
  });
  on("btnAutoStartSettings", "click", () => { native?.openAutoStartSettings?.(); rememberBackground({ autostart_opened: true }); }, "doctorStatus");
  on("btnCalendarAccess", "click", () => native?.requestCalendarAccess?.(), "doctorStatus");
  on("btnGpuReport", "click", () => gpuReport(), "gpuReportStatus");
  on("btnGpuReportCopy", "click", async () => {
    if (typeof native?.copyToClipboard === "function") native.copyToClipboard(gpuReportText);
    else await navigator.clipboard.writeText(gpuReportText);
    status("gpuReportStatus", t("已复制：在 Issues 页面新建一个问题，粘贴进去就行。"));
  }, "gpuReportStatus");
  on("btnGpuReportIssues", "click", () => openServiceUrl(gpuIssuesUrl), "gpuReportStatus");
  on("btnShareDiagnostics", "click", () => {
    if (typeof native?.exportDiagnostics === "function") { native.exportDiagnostics(); status("diagnosticsStatus", t("请选择分享、保存到手机或提交到 GitHub")); return; }
    if (typeof native?.shareDiagnostics !== "function") throw new Error(t("当前版本不支持分享诊断日志"));
    native.shareDiagnostics(); status("diagnosticsStatus", t("正在生成诊断日志，稍后会打开分享面板"));
  }, "diagnosticsStatus");
  on("btnCheckUpdates", "click", () => { if (typeof native?.checkForUpdates !== "function") throw new Error(t("当前版本不支持应用内更新")); native.checkForUpdates(); status("updateStatus", t("正在检查 GitHub 上的新版本...")); setTimeout(updates, 15000); }, "updateStatus");
  on("autoUpdateToggle", "change", () => { native?.setAutoUpdateCheck?.($("autoUpdateToggle").checked); updates(); }, "updateStatus");
  for (const [name, operation] of [["Install", "install"], ["Probe", "probe"], ["Cancel", "cancel"], ["Remove", "remove"]]) on(`btnToolchain${name}`, "click", async () => { if (operation === "remove" && !window.confirm(t("移除下载的工具链？工作区文件会保留。"))) return; await post(`/mobile/toolchain/${operation}`, {}); await toolchain(); }, "toolchainStatus");
  on("btnToolchainRestart", "click", () => { if (ui.context().activeTask) throw new Error(t("请等待任务结束")); native?.restartEngine?.(); }, "toolchainStatus");
  on("btnExtensionsRestart", "click", () => { if (ui.context().activeTask) throw new Error(t("请等待当前任务结束")); native?.restartEngine?.(); status("extensionsStatus", t("引擎正在重启")); }, "extensionsStatus");
  on("scheduleForm", "submit", async () => {
    const context = ui.context(); const date = new Date($("scheduleDue").value);
    if (!Number.isFinite(date.getTime())) throw new Error(t("请选择执行时间"));
    await post("/mobile/schedules", { title: $("scheduleTitle").value.trim(), prompt: $("schedulePrompt").value.trim(), session_id: context.sessionId, model: context.settings.model, reasoning_effort: context.settings.reasoning_effort, due_at: date.toISOString(), repeat_seconds: $("scheduleRepeat").value ? Number($("scheduleRepeat").value) : null, enabled: true, ...($("schedulePhoneControl").checked ? { phone_control: true } : {}) });
    $("scheduleForm").reset(); await schedules();
  }, "schedulesStatus");
  // The morning briefing (2.0): a daily 8:00 task in a conversation of its own. It reads what needs
  // no screen (calendar, memory, the workspace, the web), so a locked phone does not skip it.
  on("btnBriefingPreset", "click", async () => {
    const context = ui.context();
    const session = await post("/sessions", { title: t("每日早报") });
    const due = new Date(); due.setHours(8, 0, 0, 0);
    if (due <= new Date()) due.setDate(due.getDate() + 1);
    await post("/mobile/schedules", { title: t("每日早报"), session_id: session.id, model: context.settings.model, reasoning_effort: context.settings.reasoning_effort,
      due_at: due.toISOString(), repeat_seconds: 86400, enabled: true,
      prompt: t("早上好，请给我做今天的早报，简短（不超过 250 字），没有内容的部分直接跳过：\n1. 今天和明天的日程（用日历工具查；没有日历权限就跳过）；\n2. 如果记忆里有我所在的城市，查一下今天的天气，说要不要带伞；\n3. 工作区里昨天的录音速记纪要（文件名含「录音速记」或「纪要」）的要点；\n4. 记忆里我提过的待办或近期要做的事。\n最后用一句话说今天最该先做的一件事。不要读取或复述任何验证码。") });
    await schedules();
    status("schedulesStatus", t("已添加：每天 8:00 在「每日早报」对话里给你简报，可以在上面暂停或删除"));
  }, "schedulesStatus");
  on("connectionForm", "submit", async () => {
    await post("/mobile/connections", { name: $("connectionName").value.trim(), url: $("connectionUrl").value.trim(), token: $("connectionToken").value, allow_lan: $("connectionAllowLan").checked, fingerprint: $("connectionFingerprint").value.trim() || null });
    $("connectionToken").value = ""; await connections();
  }, "connectionsStatus");
  on("pairCodeForm", "submit", async () => {
    const address = $("pairAddress").value.trim();
    if (!address) throw new Error(t("先填电脑地址，或拍下电脑上的二维码"));
    const scanned = pairingLink && pairingLink.url === address && pairingLink.code === $("pairCode").value
      && pairingLink.fingerprint === $("pairFingerprint").value.trim() ? pairingLink.text : null;
    const target = /^agentworkspace:/i.test(address) ? { link: address } : scanned ? { link: scanned }
      : { url: address, code: $("pairCode").value, fingerprint: $("pairFingerprint").value.trim() || null };
    const host = await post("/mobile/connections/pair-code", { ...target, device_name: $("pairDeviceName").value.trim() || phoneName() });
    for (const id of ["pairAddress", "pairCode", "pairFingerprint"]) $(id).value = "";
    pairingLink = null;
    $("pairTarget").hidden = true;
    await connections();
    status("connectionsStatus", (host.scopes || []).includes("tasks") ? t("已和 {0} 配对，可以把任务交给它", host.name) : t("已和 {0} 配对，可以查看它的对话", host.name));
  }, "connectionsStatus");
  on("pairAddress", "change", async () => {
    // A pasted pairing link fills the code and fingerprint too.
    if (/agentworkspace:\/\/pair\?/i.test($("pairAddress").value)) await fillFromPairingLink($("pairAddress").value);
  }, "connectionsStatus");
  on("btnScanPairing", "click", () => { nativeResult("scanPairingQr", true); }, "connectionsStatus");
  on("btnPickPairing", "click", () => { nativeResult("scanPairingQr", false); }, "connectionsStatus");
  on("remoteSessionSelector", "change", updateRemoteWorkspace, "computerStatus");
  on("btnUseDraft", "click", () => { $("handoffPrompt").value = ui.context().draft; }, "computerStatus");
  on("btnQueueHandoff", "click", async () => {
    const host = selectedHost;
    if (!host) throw new Error(t("请先选择配对设备"));
    const context = ui.context(); let prompt = $("handoffPrompt").value.trim(); if (!prompt) throw new Error(t("请输入接力指令"));
    if ($("handoffContext").checked) prompt += t("\n\n用户选择附带的对话上下文：\n{0}", context.recentText);
    const confirmed = {};
    // Conversations that approve everything by themselves: told plainly, then the user's choice (2.1).
    const autonomy = targetAutonomy();
    if (broadAutonomy.has(autonomy)) {
      if (!has(host, "autonomy_ack")) throw new Error(t("电脑上的版本还不接受交到这类对话的任务，请先更新电脑上的 Agent Workspace"));
      if (!allowed(host, "broad_autonomy")) throw new Error(t("电脑还没允许这台手机往自动批准的对话交任务；在电脑的「手机连接」里给这台手机勾上这项权限"));
      const choice = await choose(t("电脑会直接执行"),
        t("电脑上这个对话设为「{0}」：交过去的任务里，运行命令、修改和删除文件、联网等操作都会直接在电脑上执行，不会再询问任何人。拿到这台手机配对令牌的人也能这样做。\n确定要交给它吗？", autonomyNames[autonomy]),
        [["send", t("我了解风险，交给电脑"), "send", true], ["x", t("取消"), "cancel"]]);
      if (choice !== "send") return;
      confirmed.accept_autonomy = autonomy;
    }
    // ID and bank card numbers usually stay with the phone's own model (2.2): mask, send, or stop.
    const found = typeof ui.privateParts === "function" ? ui.privateParts(prompt) : [];
    if (found.length) {
      const numbers = found.map((item) => `${item.kind} ${item.masked}`).join(t("、"));
      const model = host.model ? t("{0}，{1}", host.model.name, host.model.location === "computer" ? t("在这台电脑上运行") : t("云端服务")) : t("电脑当前的模型");
      const choice = await choose(t("这段内容里有个人信息"),
        t("要交给电脑的内容里有：{0}。平时这类内容只交给手机上的模型。交给电脑后，内容会发到电脑，由电脑当前的模型（{1}）处理。", numbers, model),
        [...(has(host, "private_ack") ? [["send", t("交给电脑"), "send"]] : []), ["shield", t("打码后交给电脑"), "mask", true], ["x", t("取消"), "cancel"]]);
      if (choice === "cancel") return;
      if (choice === "mask") for (const item of found) prompt = prompt.split(item.value).join(item.masked);
      else { confirmed.on_device = true; confirmed.private_accepted = true; }
    }
    if (!$("remoteSessionSelector").value && host.api === "mobile") {
      const created = await waitOperation(await post("/mobile/link/new-task", { host_id: host.host_id, prompt, confirmed }), "computerStatus", t("正在交给电脑..."));
      status("computerStatus", t("已在 {0} 上新建对话「{1}」并开始，结果会出现在「待发送与接力」", host.name, created?.title || ""));
    } else {
      await post("/mobile/outbox", { host_id: host.host_id, session_id: $("remoteSessionSelector").value, prompt, request_id: requestId("handoff"), ...confirmed });
      status("computerStatus", t("已保存到待发送队列"));
    }
    $("handoffPrompt").value = "";
  }, "computerStatus");
  on("btnReadRemote", "click", async () => {
    if (!selectedHost) throw new Error(t("请先选择配对设备"));
    if (!$("remoteSessionSelector").value) throw new Error(t("先选一个电脑上的对话"));
    const data = await ui.apiJson(`/mobile/connections/events?host_id=${encodeURIComponent(selectedHost.host_id)}&session_id=${encodeURIComponent($("remoteSessionSelector").value)}`);
    $("remoteHistory").hidden = false;
    $("remoteHistory").textContent = (data.events || []).filter(event => event.type === "message.created").map(event => `${event.data?.role || ""}: ${event.data?.content || ""}`).join("\n\n");
  }, "computerStatus");
  on("btnComputerRefresh", "click", async () => {
    if (!selectedHost) return;
    await post("/mobile/link/refresh", { host_id: selectedHost.host_id }).catch(() => {});
    await renderComputer(() => true, true);
    await loadRemoteSessions(() => true);
  }, "computerStatus");
  on("btnComputerRemove", "click", async () => { if (selectedHost) await removeComputer(selectedHost); }, "computerStatus");
  on("computerJobsSetting", "change", async () => {
    const host = selectedHost; const choice = $("computerJobsSetting").value;
    if (choice === "auto") {
      const answer = await choose(t("自动接受电脑交来的任务"),
        t("{0} 交来的任务会直接在这台手机上开始，不再先问你。每一步仍按手机的审批规则：需要审批的操作会停下来等你，银行卡号、身份证号、验证码仍会拦下。", host.name),
        [["check", t("自动接受"), "auto", true], ["x", t("取消"), "cancel"]]);
      if (answer !== "auto") { $("computerJobsSetting").value = computerState?.settings?.jobs || "ask"; return; }
    }
    await post("/mobile/link/settings", { host_id: host.host_id, jobs: choice });
    status("computerStatus", { ask: t("电脑交来的任务每次都会先问你"), auto: t("电脑交来的任务会自动开始"), off: t("不再接受电脑交来的任务") }[choice]);
  }, "computerStatus");
  for (const [id, kind] of [["btnComputerPickFiles", "files"], ["btnComputerPickPhotos", "photos"], ["btnComputerCamera", "camera"]]) {
    on(id, "click", () => { nativeResult("pickForComputer", kind); }, "computerStatus");
  }
  window.addEventListener("agent-computer-files", (event) => {
    const detail = event.detail || {};
    if (detail.cancelled) return;
    addOutgoing(detail.files || []);
    if ((detail.errors || []).length) status("computerStatus", t("有些文件没能读取：{0}", detail.errors.join(t("；"))), true);
  });
  on("btnComputerSendFiles", "click", async () => {
    const host = selectedHost;
    if (!outgoing.length) throw new Error(t("先选要发送的文件"));
    const files = outgoing.map((file) => ({ staged: file.staged, name: file.name }));
    const instruction = $("computerInstruction").value.trim();
    const result = await waitOperation(await post("/mobile/link/send-files", { host_id: host.host_id, files, instruction: instruction || null,
      knowledge: $("computerToKnowledge").checked ? t("来自手机") : null }), "computerStatus", t("正在发送 {0} 个文件...", files.length));
    // What went is no longer on the phone; what did not stays here to send again.
    const went = new Set(result.sent.map((item) => item.staged));
    outgoing = outgoing.filter((file) => !went.has(file.staged)); renderOutgoing();
    const failed = (result.failed || []).map((item) => t("{0}：{1}", item.name, localizeError(item.error)));
    if (result.task_error) status("computerStatus", t("已发送 {0} 个文件，但电脑没有开始处理：{1}", result.sent.length, localizeError(result.task_error)), true);
    else if (failed.length) status("computerStatus", t("已发送 {0} 个文件；没发出去的：{1}", result.sent.length, failed.join(t("；"))), true);
    else {
      $("computerInstruction").value = "";
      status("computerStatus", instruction ? t("已发送 {0} 个文件，电脑开始处理", result.sent.length) : t("已发送 {0} 个文件到电脑：{1}", result.sent.length, result.sent.map((item) => item.path).join(t("、"))));
    }
  }, "computerStatus");
  $("computerBrowse").addEventListener("toggle", () => {
    if ($("computerBrowse").open && selectedHost) void loadBrowse(browsePath).catch((error) => status("computerStatus", error.message, true));
  });
  on("btnComputerPaste", "click", () => {
    const value = nativeResult("readClipboardText");
    if (!value.text) throw new Error(t("剪贴板里没有文字"));
    $("computerTextInput").value = value.text;
  }, "computerStatus");
  on("btnComputerSendText", "click", async () => {
    const text = $("computerTextInput").value;
    if (!text.trim()) throw new Error(t("先写要发送的文字"));
    await post("/mobile/link/send-text", { host_id: selectedHost.host_id, text, kind: /^https?:\/\/\S+$/i.test(text.trim()) ? "link" : "text" });
    $("computerTextInput").value = "";
    status("computerStatus", t("已发到 {0}", selectedHost.name));
  }, "computerStatus");
  on("btnComputerKbAdd", "click", async () => {
    const host = selectedHost;
    const pair = { computer: $("computerKbComputer").value, phone: $("computerKbPhone").value };
    if (!pair.computer || !pair.phone) throw new Error(t("两边各选一个知识库"));
    const pairs = [...(computerState?.settings?.kb_pairs || []).filter((other) => other.computer !== pair.computer || other.phone !== pair.phone), pair];
    await post("/mobile/link/kb-pairs", { host_id: host.host_id, pairs });
    await renderComputer(() => true, false);
    status("computerStatus", t("已对应，点「现在同步」开始"));
  }, "computerStatus");
  on("btnComputerKbSync", "click", async () => {
    const host = selectedHost;
    const result = await waitOperation(await post("/mobile/link/kb-sync", { host_id: host.host_id }), "computerStatus", t("正在同步知识库..."));
    status("computerStatus", t("同步完成：复制到手机 {0} 篇，复制到电脑 {1} 篇", result.to_phone, result.to_computer), (result.errors || []).length > 0);
    await renderComputer(() => true, false);
  }, "computerStatus");
  $("computerRemoteActivity").addEventListener("toggle", async () => {
    if (!$("computerRemoteActivity").open || !selectedHost) return;
    const list = $("computerRemoteActivityList"); list.replaceChildren(row(t("读取中..."), ""));
    try {
      const device = await ui.apiJson(`/mobile/link/device?host_id=${encodeURIComponent(selectedHost.host_id)}`);
      list.replaceChildren(...(device.activity || []).map((entry) => row(activityNames[entry.action] || entry.action, `${when(entry.at)} · ${entry.detail || ""}`)));
      if (!(device.activity || []).length) list.replaceChildren(row(t("还没有记录"), ""));
    } catch (error) { list.replaceChildren(row(error.message, "")); }
  });
  on("btnFindComputers", "click", () => {
    nativeResult("discoverComputers");
    $("nearbyList").replaceChildren(row(t("正在查找…"), ""));
  }, "connectionsStatus");
  window.addEventListener("agent-computers-found", (event) => {
    const found = event.detail?.computers || [];
    const list = $("nearbyList"); list.replaceChildren();
    if (!found.length) { list.append(row(t("没有找到"), t("确认电脑上打开了「允许手机连接这台电脑」，并且手机和电脑在同一个网络"))); return; }
    for (const computer of found) {
      const short = computer.fingerprint ? computer.fingerprint.slice(0, 16).match(/.{4}/g).join(" ") : "";
      const item = row(computer.name, [computer.url, computer.pairing ? t("正在等待配对") : "", short ? t("证书指纹 {0}", short) : ""].filter(Boolean).join(" · "));
      textButton(item, "check", t("填入"), async () => {
        $("pairAddress").value = computer.url;
        $("pairFingerprint").value = computer.fingerprint || "";
        $("pairCompare").hidden = !short;
        $("pairCompare").textContent = short ? t("核对电脑屏幕上配对码旁的证书指纹是否为 {0}。一致再输入配对码；不一致说明这不是你的电脑，不要配对。", short) : "";
        $("pairTarget").hidden = true;
        $("pairCode").focus();
      }, computer.pairing);
      list.append(item);
    }
  });
  on("btnRelayToComputer", "click", async () => {
    const hostId = $("relayComputer").value;
    const sessionId = ui.context().sessionId;
    if (!hostId || !sessionId) throw new Error(t("先选一台电脑"));
    const created = await waitOperation(await post("/mobile/link/relay", { host_id: hostId, session_id: sessionId, prompt: $("relayPrompt").value.trim() || null }), "relayStatus", t("正在发到电脑..."));
    $("relayPrompt").value = "";
    status("relayStatus", t("已在电脑上新建对话「{0}」{1}", created?.title || "", created?.delivery ? t("，结果会出现在「待发送与接力」") : ""));
  }, "relayStatus");
  on("workflowForm", "submit", async () => {
    const original = $("workflowForm")._original || {};
    const assertions = { ...original.assertions }; for (const [key, id] of [["package", "workflowExpectedPackage"], ["text_contains", "workflowExpectedText"]]) { if ($(id).value.trim()) assertions[key] = $(id).value.trim(); else delete assertions[key]; }
    const preconditions = { ...original.preconditions }; if ($("workflowPackage").value.trim()) preconditions.package = $("workflowPackage").value.trim(); else delete preconditions.package;
    const workflowId = $("workflowForm").dataset.workflowId;
    const replay = $("workflowMode").value === "replay";
    await post("/mobile/workflows", { ...(workflowId ? { workflow_id: workflowId } : {}), ...(original.package ? { package: original.package } : {}), name: $("workflowName").value.trim(), ...(replay ? { schema_version: 2, steps: workflowSteps() } : { prompt: $("workflowPrompt").value.trim() }), preconditions, assertions });
    $("workflowForm").reset(); delete $("workflowForm").dataset.workflowId; delete $("workflowForm")._original; $("workflowStepEditor").replaceChildren(); setWorkflowMode(); await workflows();
  }, "workflowsStatus");
  on("workflowMode", "change", setWorkflowMode, "workflowsStatus");
  on("btnAddWorkflowStep", "click", () => addWorkflowStep(), "workflowsStatus");
  on("workflowImportForm", "submit", async () => { if (!$("workflowReviewed").checked) throw new Error(t("请先核对操作内容")); let document; try { document = JSON.parse($("workflowImportData").value); } catch { throw new Error(t("导入内容不是有效的 JSON，请检查后重试")); } await post($("workflowImportMode").value === "record" ? "/mobile/workflows/record" : "/mobile/workflows/import", $("workflowImportMode").value === "record" ? { ...document, reviewed: true } : { document }); $("workflowImportForm").reset(); await workflows(); }, "workflowsStatus");
  on("btnEvaluationExport", "click", async () => shareDocument(t("Android 实测结果"), await ui.apiJson("/mobile/evaluations/export"), "evaluationsStatus"), "evaluationsStatus");
  on("btnEvaluationPlan", "click", async () => { const device = await ui.apiJson("/mobile/android-system/status"); const context = ui.context(); const plan = await post("/mobile/evaluations/plan", { metadata: { device: device.device, app_version: device.app_version, model: context.settings.model, budget_steps: 30, retry_policy: "no automatic task retries; inspect state first" }, repetitions: 1, task_retries: 0 }); await shareDocument(t("Android 固定评测计划"), plan, "evaluationsStatus"); }, "evaluationsStatus");
  on("btnProbeLocalModel", "click", async () => { const data = await post("/mobile/local-models/probe", {}); await localModels(); status("localModelsStatus", data.available ? data.reason || t("引擎已连接") : data.reason, !data.available); }, "localModelsStatus");
  for (const id of ["localDeviceModelSelector", "localMemorySelector"]) $(id).addEventListener("change", deviceStatus);
  on("btnStartLocalBenchmark", "click", () => {
    if (ui.context().activeTask || deviceModelBusy) throw new Error(t("请先完成当前及排队任务"));
    const options = deviceOptions();
    if (!Number.isInteger(options.context_tokens) || (options.context_tokens !== 0 && (options.context_tokens < 512 || options.context_tokens > Number($("localContextCustomInput").max))))
      throw new Error(t("请填写模型支持范围内的整数上下文 Token 数"));
    if (!Number.isInteger(options.threads) || options.threads < 0 || options.threads > 64 || !Number.isInteger(options.timeout_seconds) || options.timeout_seconds < 0 || options.timeout_seconds > 7200)
      throw new Error(t("请填写有效的线程数和超时秒数"));
    nativeResult("startLocalModelBenchmark", JSON.stringify(options));
    deviceStatus();
  }, "localDeviceStatus");
  on("btnCancelLocalBenchmark", "click", () => { nativeResult("cancelLocalModelBenchmark"); deviceStatus(); }, "localDeviceStatus");
  on("localAcceleratorSelector", "change", () => {
    renderAccelerator(nativeResult("setLocalModelAccelerator", $("localAcceleratorSelector").value).accelerator);
  }, "localDeviceStatus");
  on("btnRetryLocalGpu", "click", () => {
    const value = nativeResult("retryLocalModelGpu").accelerator;
    renderAccelerator(value);
    status("localAcceleratorStatus", value?.restart_required ? t("下次启动引擎时会重新检查 GPU。") : acceleratorText(value));
  }, "localDeviceStatus");
  on("btnUseLocalRecommendation", "click", () => {
    if (!deviceRecommendation || deviceModelBusy) return;
    ui.setLocalContextDraft(deviceRecommendation.context_tokens);
    $("localThreadsInput").value = String(deviceRecommendation.threads);
    $("localTimeoutInput").value = String(deviceRecommendation.timeout_seconds);
    status("localDeviceStatus", t("推荐值已填入；点击应用本机设置后才会保存"));
  }, "localDeviceStatus");
  on("btnUnloadLocalModel", "click", async () => { await post("/mobile/local-models/unload", {}); await localModels(); status("localModelsStatus", t("模型内存已释放")); }, "localModelsStatus");
  on("btnRestoreCloudModel", "click", () => { nativeResult("restorePreviousProvider"); status("localModelsStatus", t("正在恢复原模型配置")); }, "localModelsStatus");
  window.addEventListener("agent-local-model-imported", async (event) => {
    if (closed) return;
    const result = event.detail || {};
    if (!result.ok) { status("localModelsStatus", localizeError(result.error) || t("模型导入未完成"), !result.cancelled); return; }
    try { await localModels(); status("localModelsStatus", t("训练模型已校验安装，可以选择使用")); }
    catch (error) { status("localModelsStatus", error.message, true); }
  });
  $("btnVoiceInput").hidden = typeof native?.requestVoiceInput !== "function";
  // The composer is outside the settings sheet, so voice errors go to the composer notice.
  $("btnVoiceInput").addEventListener("click", () => {
    try { native?.requestVoiceInput?.(); }
    catch (error) { ui.notice?.(t("语音输入不可用: {0}", error.message)); }
  });
  window.addEventListener("pagehide", () => { closed = true; generation += 1; stopPolls(); window.clearTimeout(devicePoll); });
})();
