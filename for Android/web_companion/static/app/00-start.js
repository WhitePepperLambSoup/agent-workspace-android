// The page script, kept in parts by area: /static/app.js is the files in this folder joined in name
// order (entrypoint.app_script), so they share one scope like the single file they came from.
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  // UI text is written in Chinese and translated by i18n.js; arguments fill {0}, {1}, ...
  const i18n = window.MobileI18n;
  const t = i18n?.t || ((text, ...values) => String(text).replace(/\{(\d+)\}/g, (_, index) => String(values[index] ?? "")));
  const locale = i18n?.locale || "zh-CN";
  const localizeError = i18n?.localizeError || ((message) => message);
  const elements = Object.fromEntries([
    "sessionSelector", "timelineList", "timelineContainer", "btnJumpLatest", "promptInput", "btnSend", "btnStop",
    "btnNewSession", "btnSettings", "btnAttach", "filePickerInput", "attachmentList",
    "approvalShelf", "approvalTitle", "approvalDetail", "approvalScopeSelector",
    "btnApproveAction", "btnRejectAction", "connectionStatus", "quickChipsBar",
    "noticeText", "taskStatusBar", "taskStateLabel", "btnResumeTask", "btnRetryTask", "btnReconnect",
    "modelBar", "modelSummary", "executionSummary", "appShell", "settingsOverlay", "settingsBackdrop", "settingsSheet", "settingsScrollBody",
    "settingsBackButton", "settingsCloseButton", "settingsTitle", "settingsHome",
    "settingsModel", "settingsPermission", "settingsAppearance", "settingsSearch", "settingsError", "settingsActions",
    "btnModelPage", "btnPermissionPage", "btnAppearancePage", "btnSearchPage", "btnProviderSettings",
    "btnExport", "btnRefresh", "menuModelSummary", "menuPermissionSummary", "modelInput",
    "modelOptions", "effortSelector", "effortHint", "autonomySelector", "autonomyHint", "contextSummaryToggle", "contextSummaryLabel", "contextSummaryHint",
    "btnApplySettings", "themeSelector", "textSizeSelector", "quickActionsToggle", "hapticsToggle",
    "sessionSearchInput", "searchStatus", "searchResults",
    "settingsTasks", "settingsFiles", "settingsSession", "settingsNotifications",
    "btnTasksPage", "btnFilesPage", "btnSessionPage", "btnNotificationsPage",
    "btnTasksRefresh", "taskCenterStatus", "taskCenterList",
    "btnFileParent", "btnFilesRefresh", "workspaceFilePath", "workspaceFilesStatus", "workspaceFilesList",
    "fileEditorPanel", "fileEditorMeta", "fileEditorStatus", "fileContentInput", "filePreviewPanel", "btnFileSource", "btnFilePreview", "btnFileInteractive", "btnFileToKnowledge", "btnReloadFile", "btnDiscardFileDraft", "btnSaveFile",
    "sessionTitleInput", "btnRenameSession", "sessionRenameStatus",
    "taskNotificationsToggle", "notificationPermissionStatus", "btnNotificationSettings",
    "settingsUsage", "settingsPricing", "btnUsagePage", "usageScopeSelector", "usageDaysSelector", "usageSummary", "usageModelsList", "usageStatus", "btnUsageRefresh", "btnPricingPage",
    "pricingModelInput", "pricingModelOptions", "pricingInputRate", "pricingOutputRate", "pricingCachedRate", "pricingSource", "btnSavePricing", "pricingStatus",
    "localContextSelector", "localContextCustomInput", "localContextCustomRow", "localMemorySelector", "localThreadsInput", "localTimeoutInput",
    "workspaceSelector", "btnWorkspacesPage", "menuWorkspaceSummary", "workspacesStatus", "workspacesList", "btnWorkspacesRefresh",
    "workspaceCreateForm", "workspaceNameInput", "workspaceFolderInput", "workspaceCreateDirectory", "btnCreateWorkspace", "btnPickWorkspaceFolder", "workspaceStorageStatus", "btnWorkspaceStorageSettings",
    "btnBrowseWorkspaceSystem", "workspaceDocumentsHint", "btnSuggestWorkspaceFolder", "workspacePublicFolderHint",
    "btnAttachmentsPage", "btnImportNotice", "importNoticeText", "menuImportSummary", "btnPickImportFiles", "btnRefreshImports",
    "shareTargetControls", "shareTargetSession", "shareInboxStatus", "shareInboxList", "shareImportActions", "btnImportShares", "btnDiscardShares", "browserUploadList",
    "btnSessions", "btnSessionTitle", "sessionTitleText", "workspaceTitleText", "sessionDrawer", "sessionDrawerBackdrop", "sessionDrawerPanel",
    "btnDrawerClose", "btnDrawerSearch", "drawerWorkspaces", "drawerSessionList", "btnDrawerNewSession", "btnDrawerWorkspaces",
    "btnModeChip", "settingsHeaderActions", "bottomDock", "mobileHeader",
  ].map((id) => [id, $(id)]));
  const token = document.querySelector('meta[name="agent-token"]')?.content || "";
  const bridge = window.AndroidBridge;
  const settingsKey = "agent-mobile-preferences-v1";
  const draftsKey = "agent-mobile-drafts-v1";
  const sessionKey = "agent-mobile-session-v1";
  const runtimeChoiceKey = "agent-mobile-runtime-v1";
  const submissionsKey = "agent-mobile-submissions-v1";
  const pendingRequestsKey = "agent-mobile-pending-requests-v1";
  const fileDraftsKey = "agent-mobile-file-drafts-v1";
  const workspaceKey = "agent-mobile-workspace-v1";
  const wallpaperKey = "agent-mobile-wallpaper-v1";
  const effortLabels = { auto: t("自动"), none: t("关闭"), low: t("低"), medium: t("中"), high: t("高"), xhigh: t("极高"), max: t("最高") };
  const effortOrder = ["none", "low", "medium", "high", "xhigh", "max"];
  const autonomyLabels = { workspace: t("工作区"), yolo: "YOLO", full_access: t("完全访问") };
  const localContextOptions = [0, 4096, 8192, 16384, 32768, 65536, 131072, 262144];
  const terminalStates = new Set(["succeeded", "failed", "cancelled"]);
  const runningStates = new Set(["queued", "running", "waiting_approval"]);
  const maxSharedTextLength = 32768;
  const browserUploads = [];
  const shareSelection = new Map();
  const acknowledgedShares = new Set();
  let shareInbox = { items: [], batches: [] };
  let refreshingImports = false;
  // Files picked or photographed from a conversation go straight into it: the app names the inbox
  // batch the pick will fill, and each file is added as soon as it has been received. Kept in
  // storage because the camera can stop this page while it is open.
  const autoImportsKey = "agent-mobile-auto-imports-v1";
  let autoImports = (() => {
    const saved = readStorage(autoImportsKey, []);
    return Array.isArray(saved) ? saved.filter(entry => typeof entry?.batch === "string" && typeof entry.sessionId === "string"
      && Number.isFinite(entry.deadline) && Array.isArray(entry.confirmed)) : [];
  })();
  const reportedImportErrors = new Set();
  // The import page's own "add" request, until its files have settled.
  let importWatch = null;
  // The conversation chosen on the import page; null follows the open conversation.
  let shareTargetChoice = null;
  const thumbnails = new Map(); // attachment path -> object URL; null while loading, false when unavailable

  function readStorage(key, fallback) {
    try {
      const value = window.localStorage.getItem(key);
      return value === null ? fallback : JSON.parse(value);
    } catch { return fallback; }
  }

  function writeStorage(key, value) {
    try { window.localStorage.setItem(key, JSON.stringify(value)); return true; }
    catch { return false; }
  }

  // Quick tasks: the editable shortcuts above the composer. Until the user edits them, the defaults
  // follow the interface language; once edited, the user's own text is stored as written.
  const quickTasksKey = "agent-mobile-quick-tasks-v1";
  const maxQuickTasks = 8;
  const quickTaskIcons = ["file-text", "languages", "globe", "chart-no-axes-column", "code", "mail", "lightbulb", "notebook-pen", "calendar", "book-open", "graduation-cap", "search", "shopping-cart", "plane", "utensils", "heart", "star", "sparkles", "zap", "camera"];
  function defaultQuickTasks() {
    return [
      { title: t("总结要点"), detail: t("文档、网页或聊天记录"), prompt: t("总结下面内容的要点，并列出需要我跟进的事项：\n"), icon: "file-text", send: false },
      { title: t("翻译润色"), detail: t("中英互译，语气自然"), prompt: t("把下面的内容翻译成英文，语气自然：\n"), icon: "languages", send: false },
      { title: t("做个网页"), detail: t("生成可直接预览的页面"), prompt: t("做一个单页网页（HTML），主题是："), icon: "globe", send: false },
      { title: t("分析数据"), detail: t("表格或 CSV 出结论与图表"), prompt: t("分析附件里的数据，给出关键结论并画一张图表："), icon: "chart-no-axes-column", send: false },
    ];
  }
  function loadQuickTasks() {
    const stored = readStorage(quickTasksKey, null);
    if (!Array.isArray(stored)) return defaultQuickTasks();
    return stored
      .filter((task) => task && typeof task.title === "string" && task.title.trim() && typeof task.prompt === "string" && task.prompt.trim())
      .slice(0, maxQuickTasks)
      .map((task) => ({
        title: task.title.trim().slice(0, 20),
        detail: typeof task.detail === "string" ? task.detail.trim().slice(0, 40) : "",
        prompt: task.prompt.slice(0, 4000),
        icon: quickTaskIcons.includes(task.icon) ? task.icon : "sparkles",
        send: task.send === true,
      }));
  }
  let quickTasks = loadQuickTasks();
  let editingQuickTask = -1; // index being edited; quickTasks.length while adding; -1 when the form is closed

  const appearanceChoices = {
    theme: ["system", "light", "dark"], textSize: ["small", "normal", "large"],
    style: ["solid", "glass"], accent: ["teal", "blue", "violet", "amber", "rose"], motion: ["auto", "full", "reduced", "off"], language: ["auto", "zh", "zh-Hant", "en"],
    backdrop: ["aurora", "sunset", "ocean", "meadow", "iris", "bokeh", "grid", "ribbon", "dusk", "graphite", "plain", "custom"],
  };
  const preferences = {
    theme: "system", textSize: "normal", quickActions: true, haptics: true, style: "solid", accent: "teal", motion: "auto", language: "auto", backdrop: "aurora",
    ...readStorage(settingsKey, {}),
  };
  for (const [key, allowed] of Object.entries(appearanceChoices)) {
    if (!allowed.includes(preferences[key])) preferences[key] = allowed[key === "textSize" ? 1 : 0];
  }
  // The custom wallpaper is a JPEG data URL this page encoded itself; anything else is ignored.
  const wallpaperPattern = /^data:image\/(?:jpeg|png|webp);base64,[A-Za-z0-9+/]+=*$/;
  let customWallpaper = (() => {
    try { const value = window.localStorage.getItem(wallpaperKey) || ""; return wallpaperPattern.test(value) ? value : ""; }
    catch { return ""; }
  })();
  const drafts = readStorage(draftsKey, {});
  const submissions = readStorage(submissionsKey, {});
  const pendingRequests = readStorage(pendingRequestsKey, {});
  const fileDrafts = readStorage(fileDraftsKey, {});
  let selectedSessionId = readStorage(sessionKey, "");
  let currentSessionId = "";
  let sessions = [];
  let workspaces = [];
  let currentWorkspaceId = readStorage(workspaceKey, "");
  let defaultWorkspaceId = "";
  let workspaceSaving = false;
  let workspacePicking = false;
  let workspaceGeneration = 0;
  const backgroundTasks = new Map();
  let historyEvents = [];
  let historyReady = false;
  let isLoadingSession = true;
  let isUploading = false;
  let isPreparingSubmission = false;
  let isResolvingApproval = false;
  let isSteering = false;
  let engineReconnectRequestedAt = 0;
  let activeTask = null;
  let taskAdoptionGeneration = 0;
  let interruptedTask = null;
  let retryTask = null;
  let pendingApproval = null;
  let attachments = [];
  let recoveredPendingDraft = null;
  let settingsPage = "home";
  const settingsScrollPositions = new Map();
  let settings = { model: "", reasoning_effort: "auto", autonomy: "workspace", context_summary_enabled: true, local_context_tokens: 0, local_memory_mode: "balanced", local_threads: 0, local_timeout_seconds: 0, models: [], model_efforts: {} };
  let contextSummaryDirty = false;
  let localContextBusy = true;
  let localDeviceTesting = false;
  let settingsAvailable = false;
  let disposed = false;
  let restartPending = false;
  let stickToBottom = true;
  let searchTimer = null;
  let searchGeneration = 0;
  let taskCenterGeneration = 0;
  let taskCenterTasks = [];
  const taskActions = new Set();
  let filesGeneration = 0;
  let workspacePath = "";
  let workspaceParent = null;
  let fileEditor = null;
  let fileSaving = false;
  let fileKnowledgeAdding = false;
  // Document types the knowledge base reads; code files are left out to keep the toolbar quiet.
  const knowledgeFiles = /\.(pdf|docx|xlsx|epub|html?|xhtml|txt|md|markdown|rst|csv|tsv|json|jsonl|log|ya?ml|toml|ini|xml|tex|srt)$/i;
  let filePreviewUrl = null;
  let renameSaving = false;
  let sessionOpening = null;
  const unavailableSessions = new Set();
  let notificationSettings = { enabled: false, permission_granted: false };
  let usageGeneration = 0;
  let usageData = null;
  let pricingSaving = false;
  const eventCards = new Map();
  const artifactActions = new Map();
  let historyAssistantCard = null;

  // Focus moves after a touch (menu open, Android back) should not paint keyboard focus rings.
  document.documentElement.classList.toggle("touch-input", typeof window.matchMedia === "function" && window.matchMedia("(pointer: coarse)")?.matches === true);
  window.addEventListener("pointerdown", (event) => {
    document.documentElement.classList.toggle("touch-input", event.pointerType === "touch" || event.pointerType === "pen");
  }, { capture: true, passive: true });
  window.addEventListener("keydown", (event) => {
    if (["Tab", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) document.documentElement.classList.remove("touch-input");
  }, { capture: true });

  function icon(name) { return window.MobileUi?.iconMarkup(name) || ""; }
  document.querySelectorAll("[data-icon]").forEach((node) => { node.innerHTML = icon(node.dataset.icon); });
  renderQuickChips();

  // Models by purpose: a cheaper model of the same provider for phone control and summaries.
  async function loadModelRoles() {
    const status = $("modelRolesStatus");
    try {
      const { roles = {} } = await apiJson("/mobile/model-roles");
      $("phoneModelInput").value = roles.phone || "";
      $("summaryModelInput").value = roles.summary || "";
      $("subagentModelInput").value = roles.subagent || "";
      status.textContent = "";
    } catch (error) { status.textContent = t("读取失败：{0}", error.message); }
  }
  async function saveModelRoles() {
    const status = $("modelRolesStatus");
    const roles = {
      phone: $("phoneModelInput").value.trim(),
      summary: $("summaryModelInput").value.trim(),
      subagent: $("subagentModelInput").value.trim(),
    };
    try {
      await apiJson("/mobile/model-roles", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ roles }) });
      status.textContent = roles.phone || roles.summary || roles.subagent ? t("已保存，下一个任务开始生效") : t("已保存：都使用主模型");
    } catch (error) { status.textContent = t("保存失败：{0}", error.message); }
  }

  // A spending limit per task, its sub-tasks included (mobile_task_limits). Tokens are entered in units of 10,000.
  async function loadTaskLimits() {
    const status = $("taskLimitsStatus");
    try {
      const { limits = {} } = await apiJson("/mobile/task-limits");
      if (disposed) return;
      $("taskCostLimitInput").value = limits.max_cost_usd > 0 ? String(limits.max_cost_usd) : "";
      $("taskTokenLimitInput").value = limits.max_tokens > 0 ? String(Math.round(limits.max_tokens / 10_000)) : "";
      status.textContent = "";
    } catch (error) { status.textContent = t("读取失败：{0}", error.message); }
  }
  async function saveTaskLimits() {
    const status = $("taskLimitsStatus");
    const cost = Number($("taskCostLimitInput").value.trim() || 0);
    const tokens = Number($("taskTokenLimitInput").value.trim() || 0);
    if (!Number.isFinite(cost) || cost < 0 || cost > 1000 || !Number.isFinite(tokens) || tokens < 0 || tokens > 100_000) {
      status.textContent = t("请填 0 到 1000 美元、0 到 100000 万 Token");
      return;
    }
    const limits = { max_cost_usd: cost, max_tokens: Math.round(tokens) * 10_000 };
    try {
      await apiJson("/mobile/task-limits", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ limits }) });
      status.textContent = cost || tokens ? t("已保存，下一个任务开始生效") : t("已保存：不限");
    } catch (error) { status.textContent = t("保存失败：{0}", error.message); }
  }

  function haptic(milliseconds = 24) {
    if (!preferences.haptics) return;
    if (typeof bridge?.vibrate === "function") bridge.vibrate(milliseconds);
    else if (navigator.vibrate) navigator.vibrate(milliseconds);
  }

  // A notice is about the moment it was shown: it goes by itself, on a tap, or when a message is sent.
  let noticeTimer = 0;
  function notice(message, tone = "error") {
    if (disposed) return;
    window.clearTimeout(noticeTimer);
    elements.noticeText.textContent = message || "";
    elements.noticeText.dataset.tone = tone;
    elements.noticeText.hidden = !message;
    if (message) noticeTimer = window.setTimeout(() => { if (elements.noticeText.textContent === message) notice(""); }, tone === "info" ? 5000 : 20000);
  }

  function setConnection(online) {
    if (disposed) return;
    const label = online ? t("已连接") : t("连接中断");
    elements.connectionStatus.classList.toggle("offline", !online);
    elements.connectionStatus.title = label;
    elements.connectionStatus.setAttribute("aria-label", label);
  }

  async function submitAfterEngineRecovery(path, options) {
    try { return await apiJson(path, options); }
    catch (error) {
      if (error.status !== 409 || error.code !== "runtime_restarting" || !error.retryable) throw error;
      updateTaskStatus(t("引擎正在恢复..."));
      try { bridge?.ensureEngineRunning?.(); } catch { /* The recovery worker also owns engine restarts. */ }
      for (let attempt = 0; attempt < 45 && !disposed; attempt++) {
        let ready = false;
        try {
          const runtime = await apiJson("/mobile/runtime");
          ready = runtime.task_admission_ready === true;
        } catch (recoveryError) {
          if (recoveryError.code || (recoveryError.status && recoveryError.status < 500)) throw recoveryError;
        }
        if (ready) return await apiJson(path, options);
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      throw new Error(t("引擎尚未恢复，任务草稿已保留，请稍后重试"));
    }
  }

  // The page holds the token of the engine it was loaded from. If that engine died or was restarted
  // (a restart issues a new token), only the app can start it again and reload the page with the
  // current token. Ask it at most every 20 seconds.
  function requestEngineReconnect() {
    if (disposed || typeof bridge?.reconnectEngine !== "function") return false;
    const now = Date.now();
    if (now - engineReconnectRequestedAt < 20000) return true;
    engineReconnectRequestedAt = now;
    try { bridge.reconnectEngine(); return true; } catch { return false; }
  }

  async function apiJson(path, options = {}) {
    if (disposed) throw new Error("Page closed");
    let response;
    try {
      response = await fetch(path, {
        ...options,
        headers: { Authorization: `Bearer ${token}`, ...(options.headers || {}) },
      });
    } catch (cause) {
      // fetch only rejects when nothing answered: the engine is down or its connection dropped.
      const error = new Error(t("无法连接本地引擎"));
      error.network = true;
      error.cause = cause;
      throw error;
    }
    if (response.status === 401) requestEngineReconnect();
    let data;
    try { data = await response.json(); }
    catch {
      // Proxies and crashed engines can answer with HTML or an empty body.
      const error = new Error(response.ok ? t("服务返回了无法识别的数据") : `HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    if (data === null || typeof data !== "object") data = {};
    if (disposed) throw new Error("Page closed");
    if (!response.ok) {
      const error = new Error(localizeError(data.error) || `HTTP ${response.status}`);
      error.status = response.status;
      error.code = data.code;
      error.retryable = data.retryable === true;
      throw error;
    }
    return data;
  }

  const darkSchemeQuery = typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function syncSystemBars() {
    if (disposed) return;
    const dark = preferences.theme === "dark" || (preferences.theme === "system" && darkSchemeQuery?.matches === true);
    const surface = window.getComputedStyle(document.documentElement).getPropertyValue("--system-bar").trim();
    if (!/^#[0-9a-f]{6}$/i.test(surface)) return;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", surface);
    // The native host paints the status and navigation bar areas outside the WebView.
    try { bridge?.setSystemBarsAppearance?.(dark, surface); } catch { /* Older APKs keep their fixed bar colors. */ }
  }

  // Pictures are scaled to screen size and re-encoded as JPEG so they fit in local storage.
  async function storeWallpaper(file) {
    if (!/^image\//.test(file.type || "") && !hasImageName(file)) throw new Error(t("请选择一张图片"));
    const url = URL.createObjectURL(file);
    try {
      const image = await new Promise((resolve, reject) => {
        const element = new Image();
        element.onload = () => resolve(element);
        element.onerror = () => reject(new Error(t("无法读取这张图片，请换一张 JPG 或 PNG")));
        element.src = url;
      });
      for (const [longSide, quality] of [[1600, 0.82], [1080, 0.72], [720, 0.6]]) {
        const scale = Math.min(1, longSide / Math.max(image.naturalWidth, image.naturalHeight, 1));
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
        canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
        canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
        const data = canvas.toDataURL("image/jpeg", quality);
        if (!wallpaperPattern.test(data)) break;
        try { window.localStorage.setItem(wallpaperKey, data); return data; } catch { /* Too large: try a smaller copy. */ }
      }
      throw new Error(t("图片太大，无法保存为壁纸"));
    } finally { URL.revokeObjectURL(url); }
  }

  // Glass rules use :is() (Chromium 88) and backdrop-filter (76). An older WebView would apply only
  // some of them and leave unreadable see-through panels, so it keeps the standard style instead.
  const glassSupported = (() => {
    try {
      document.querySelector(":is(html)");
      return !window.CSS?.supports || CSS.supports("backdrop-filter", "blur(1px)") || CSS.supports("-webkit-backdrop-filter", "blur(1px)");
    } catch { return false; }
  })();

  function applyAppearance() {
    const root = document.documentElement;
    root.dataset.theme = preferences.theme;
    root.dataset.textSize = preferences.textSize;
    root.dataset.style = preferences.style === "glass" && !glassSupported ? "solid" : preferences.style;
    const glassOption = document.querySelector('[data-style-option="glass"]');
    if (glassOption) glassOption.disabled = !glassSupported;
    root.dataset.accent = preferences.accent;
    root.dataset.motion = preferences.motion;
    // A custom backdrop without a stored picture falls back to the first preset.
    const backdrop = preferences.backdrop === "custom" && !customWallpaper ? "aurora" : preferences.backdrop;
    root.dataset.backdrop = backdrop;
    if (backdrop === "custom") root.style.setProperty("--custom-wallpaper", `url("${customWallpaper}")`);
    else root.style.removeProperty("--custom-wallpaper");
    const customSwatch = $("customWallpaperSwatch");
    customSwatch.classList.toggle("has-image", !!customWallpaper);
    customSwatch.style.backgroundImage = customWallpaper ? `url("${customWallpaper}")` : "";
    document.querySelectorAll("[data-backdrop-option]").forEach((option) => option.setAttribute("aria-checked", String(option.dataset.backdropOption === backdrop)));
    $("customWallpaperActions").hidden = backdrop !== "custom";
    // navigator.deviceMemory is coarse (GiB); live blur is the costly part of liquid glass.
    root.classList.toggle("lite-glass", typeof navigator.deviceMemory === "number" && navigator.deviceMemory <= 3);
    document.querySelectorAll("[data-style-option]").forEach((option) => option.setAttribute("aria-checked", String(option.dataset.styleOption === preferences.style)));
    document.querySelectorAll("[data-accent-option]").forEach((option) => option.setAttribute("aria-checked", String(option.dataset.accentOption === preferences.accent)));
    $("motionSelector").value = preferences.motion;
    $("languageSelector").value = preferences.language;
    elements.quickChipsBar.hidden = !preferences.quickActions || !quickTasks.length;
    elements.themeSelector.value = preferences.theme;
    elements.textSizeSelector.value = preferences.textSize;
    elements.quickActionsToggle.checked = !!preferences.quickActions;
    elements.hapticsToggle.checked = !!preferences.haptics;
    syncSystemBars();
    // Home screen widgets take the chosen style (their glass needs no backdrop-filter support).
    try { bridge?.setWidgetStyle?.(preferences.style === "glass" ? "glass" : "solid"); } catch { /* Older APKs have no widgets. */ }
  }

  function renderQuickChips() {
    elements.quickChipsBar.replaceChildren(...quickTasks.map((task) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.dataset.prompt = task.prompt;
      chip.dataset.fill = String(!task.send);
      const glyph = document.createElement("span");
      glyph.dataset.icon = task.icon;
      glyph.innerHTML = icon(task.icon);
      const label = document.createElement("span");
      label.textContent = task.title;
      if (task.detail) {
        const detail = document.createElement("small");
        detail.textContent = task.detail;
        label.append(detail);
      }
      chip.append(glyph, label);
      return chip;
    }));
    elements.quickChipsBar.classList.toggle("many", quickTasks.length > 4);
    elements.quickChipsBar.hidden = !preferences.quickActions || !quickTasks.length;
  }

  function saveQuickTasks(next, reset = false) {
    quickTasks = next;
    let saved = true;
    if (reset) { try { window.localStorage.removeItem(quickTasksKey); } catch { saved = false; } }
    else saved = writeStorage(quickTasksKey, next);
    pageStatus($("quickTaskStatus"), saved ? "" : t("保存失败，手机存储空间可能不足"), !saved);
    renderQuickChips();
    renderQuickTaskEditor();
    syncControls();
    syncWidgetQuickTasks();
  }

  // The home screen's quick tasks widget shows the same tasks; the APK keeps a copy for the launcher.
  function syncWidgetQuickTasks() {
    try { bridge?.setWidgetQuickTasks?.(JSON.stringify(quickTasks.map(({ title, detail, prompt }) => ({ title, detail, prompt })))); }
    catch { /* Older APKs have no widget. */ }
  }

  function renderQuickTaskEditor() {
    const list = $("quickTaskList");
    const button = (symbol, label, disabled, handler) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = "icon-button";
      element.title = label;
      element.setAttribute("aria-label", label);
      element.innerHTML = icon(symbol);
      element.disabled = disabled;
      element.addEventListener("click", handler);
      return element;
    };
    list.replaceChildren(...quickTasks.map((task, index) => {
      const row = document.createElement("div");
      row.className = "management-row quick-task-row";
      const glyph = document.createElement("span");
      glyph.className = "quick-task-icon";
      glyph.innerHTML = icon(task.icon);
      const body = document.createElement("div");
      body.className = "management-row-body";
      const title = document.createElement("strong");
      title.textContent = task.title;
      const detail = document.createElement("small");
      detail.textContent = (task.send ? t("直接发送") : t("填入输入框")) + " · " + (task.prompt.split("\n")[0].slice(0, 60) || task.detail);
      body.append(title, detail);
      const move = (offset) => {
        const next = [...quickTasks];
        [next[index], next[index + offset]] = [next[index + offset], next[index]];
        saveQuickTasks(next);
      };
      row.append(glyph, body,
        button("arrow-up", t("上移"), index === 0, () => move(-1)),
        button("arrow-down", t("下移"), index === quickTasks.length - 1, () => move(1)),
        button("pencil", t("编辑"), false, () => openQuickTaskForm(index)),
        button("trash-2", t("删除"), false, () => {
          if (!window.confirm(t("删除快捷任务“{0}”？", task.title))) return;
          if (editingQuickTask === index) closeQuickTaskForm();
          saveQuickTasks(quickTasks.filter((_, other) => other !== index));
        }));
      return row;
    }));
    if (!quickTasks.length) {
      const empty = document.createElement("p");
      empty.className = "setting-hint";
      empty.textContent = t("还没有快捷任务，点“添加”新建一个。");
      list.append(empty);
    }
    $("btnAddQuickTask").disabled = quickTasks.length >= maxQuickTasks;
  }

  function renderQuickTaskIcons(selected) {
    $("quickTaskIcons").replaceChildren(...quickTaskIcons.map((name) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "icon-option";
      option.setAttribute("role", "radio");
      option.setAttribute("aria-checked", String(name === selected));
      option.setAttribute("aria-label", name);
      option.dataset.iconOption = name;
      option.innerHTML = icon(name);
      return option;
    }));
  }

  function openQuickTaskForm(index) {
    const adding = index >= quickTasks.length;
    if (adding && quickTasks.length >= maxQuickTasks) return;
    editingQuickTask = index;
    const task = adding ? { title: "", detail: "", prompt: "", icon: "sparkles", send: false } : quickTasks[index];
    $("quickTaskFormTitle").textContent = adding ? t("添加快捷任务") : t("编辑快捷任务");
    $("quickTaskTitle").value = task.title;
    $("quickTaskDetail").value = task.detail;
    $("quickTaskPrompt").value = task.prompt;
    $("quickTaskSend").checked = task.send;
    renderQuickTaskIcons(task.icon);
    $("quickTaskForm").hidden = false;
    $("quickTaskTitle").focus();
    $("quickTaskForm").scrollIntoView?.({ block: "nearest" });
  }

