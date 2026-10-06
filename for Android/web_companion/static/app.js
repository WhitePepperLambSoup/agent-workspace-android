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
    "fileEditorPanel", "fileEditorMeta", "fileEditorStatus", "fileContentInput", "filePreviewPanel", "btnFileSource", "btnFilePreview", "btnFileInteractive", "btnReloadFile", "btnDiscardFileDraft", "btnSaveFile",
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

  const appearanceChoices = {
    theme: ["system", "light", "dark"], textSize: ["small", "normal", "large"],
    style: ["solid", "glass"], accent: ["teal", "blue", "violet", "amber", "rose"], motion: ["auto", "full", "reduced", "off"], language: ["auto", "zh", "en"],
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

  function haptic(milliseconds = 24) {
    if (!preferences.haptics) return;
    if (typeof bridge?.vibrate === "function") bridge.vibrate(milliseconds);
    else if (navigator.vibrate) navigator.vibrate(milliseconds);
  }

  function notice(message, tone = "error") {
    if (disposed) return;
    elements.noticeText.textContent = message || "";
    elements.noticeText.dataset.tone = tone;
    elements.noticeText.hidden = !message;
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
    elements.quickChipsBar.hidden = !preferences.quickActions;
    elements.themeSelector.value = preferences.theme;
    elements.textSizeSelector.value = preferences.textSize;
    elements.quickActionsToggle.checked = !!preferences.quickActions;
    elements.hapticsToggle.checked = !!preferences.haptics;
    syncSystemBars();
  }

  function updateTaskStatus(text = "", { resume = false, retry = false, reconnect = false, idle = false } = {}) {
    elements.taskStatusBar.hidden = !text;
    // Terminal states say so explicitly; the label text is translated and must not drive logic.
    elements.taskStatusBar.dataset.busy = String(!!text && !resume && !retry && !reconnect && !idle);
    elements.taskStateLabel.textContent = text;
    elements.btnResumeTask.hidden = !resume;
    elements.btnResumeTask.disabled = !resume;
    elements.btnRetryTask.hidden = !retry;
    elements.btnReconnect.hidden = !reconnect;
  }

  function hasBackgroundTasks() { return [...backgroundTasks.values()].some(task => !task.done); }

  function workspaceOfSession(sessionId) {
    const session = sessions.find(item => item.id === sessionId);
    if (!session) return null;
    return session.workspace_id || workspaces.find(item => item.path === session.workspace)?.id || defaultWorkspaceId;
  }

  function scopedUrl(path, workspaceId = currentWorkspaceId) {
    return workspaceId ? `${path}${path.includes("?") ? "&" : "?"}workspace_id=${encodeURIComponent(workspaceId)}` : path;
  }

  function syncWorkspaceControls() {
    const busy = workspaceSaving || workspacePicking || restartPending;
    elements.btnCreateWorkspace.disabled = busy || !elements.workspaceNameInput.value.trim() || !elements.workspaceFolderInput.value.trim();
    elements.workspaceNameInput.disabled = busy;
    elements.workspaceFolderInput.disabled = busy;
    elements.workspaceCreateDirectory.disabled = busy;
    elements.btnPickWorkspaceFolder.hidden = typeof bridge?.pickWorkspaceFolder !== "function";
    elements.btnPickWorkspaceFolder.disabled = busy;
    elements.btnWorkspacesRefresh.disabled = busy;
    elements.btnBrowseWorkspaceSystem.hidden = typeof bridge?.openWorkspaceBrowser !== "function";
    elements.btnBrowseWorkspaceSystem.disabled = restartPending || !workspaces.some(item => item.id === currentWorkspaceId);
    elements.workspaceDocumentsHint.hidden = elements.btnBrowseWorkspaceSystem.hidden;
    elements.btnSuggestWorkspaceFolder.hidden = typeof bridge?.recommendedWorkspaceFolder !== "function";
    elements.btnSuggestWorkspaceFolder.disabled = busy;
    elements.workspacePublicFolderHint.hidden = elements.btnSuggestWorkspaceFolder.hidden;
  }

  function renderWorkspaceNavigation() {
    elements.workspaceSelector.replaceChildren();
    for (const workspace of workspaces) {
      const option = document.createElement("option");
      option.value = workspace.id;
      option.textContent = workspace.name || workspace.path;
      elements.workspaceSelector.appendChild(option);
    }
    elements.workspaceSelector.value = currentWorkspaceId;
    elements.workspaceSelector.hidden = !workspaces.length;
    const current = workspaces.find(item => item.id === currentWorkspaceId);
    elements.menuWorkspaceSummary.textContent = current?.name || t("默认工作区");
    elements.workspaceTitleText.textContent = current?.name || t("本机工作区");
    renderDrawer();
    elements.workspacesList.replaceChildren();
    for (const workspace of workspaces) {
      const button = document.createElement("button");
      button.className = "menu-row workspace-row";
      button.type = "button";
      button.dataset.workspaceId = workspace.id;
      const text = document.createElement("span");
      const name = document.createElement("strong");
      const folder = document.createElement("small");
      name.textContent = workspace.name;
      folder.textContent = workspace.path;
      text.append(name, folder);
      const selected = document.createElement("span");
      selected.innerHTML = icon(workspace.id === currentWorkspaceId ? "check" : "chevron-right");
      if (workspace.id === currentWorkspaceId) button.setAttribute("aria-current", "true");
      button.append(text, selected);
      button.addEventListener("click", async () => { if (await switchWorkspace(workspace.id)) closeMenu(); });
      const item = document.createElement("div");
      item.className = "workspace-item";
      item.appendChild(button);
      if (workspace.id !== defaultWorkspaceId) {
        const remove = actionButton("trash-2", t("从列表移除 {0}", workspace.name || workspace.path), "data-workspace-remove", workspace.id);
        remove.disabled = workspaceSaving || restartPending;
        remove.addEventListener("click", () => removeWorkspace(workspace));
        item.appendChild(remove);
      }
      elements.workspacesList.appendChild(item);
    }
  }

  async function removeWorkspace(workspace) {
    if (workspaceSaving || disposed) return;
    if (!window.confirm(t("从列表移除「{0}」？\n文件夹和其中的文件不会被删除；重新添加同一文件夹即可找回它的会话。", workspace.name || workspace.path))) return;
    // Leave the workspace first so nothing keeps pointing at it.
    if (workspace.id === currentWorkspaceId && !await switchWorkspace(defaultWorkspaceId)) {
      pageStatus(elements.workspacesStatus, t("请先结束当前操作再移除此工作区"), true);
      return;
    }
    workspaceSaving = true;
    syncWorkspaceControls();
    pageStatus(elements.workspacesStatus, t("移除中..."));
    try {
      const data = await apiJson("/mobile/workspaces/remove", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ workspace_id: workspace.id }) });
      if (Array.isArray(data.workspaces)) workspaces = data.workspaces.filter(item => item && typeof item.id === "string" && typeof item.path === "string");
      else workspaces = workspaces.filter(item => item.id !== workspace.id);
      sessions = sessions.filter(session => workspaceOfSession(session.id) !== workspace.id);
      pageStatus(elements.workspacesStatus, t("已移除「{0}」", workspace.name || workspace.path));
      try { bridge?.refreshWorkspaceDocuments?.(); } catch { /* The app file page remains available. */ }
    } catch (error) {
      if (!disposed) pageStatus(elements.workspacesStatus, error.status === 409 ? t("该工作区仍有运行中的任务，请先停止任务") : t("移除工作区失败: {0}", error.message), true);
    } finally {
      workspaceSaving = false;
      if (!disposed) { renderWorkspaceNavigation(); syncControls(); }
    }
  }

  function sessionsInWorkspace() {
    return sessions.filter(item => !currentWorkspaceId || workspaceOfSession(item.id) === currentWorkspaceId);
  }

  // Archived conversations leave the lists unless they are the one being viewed.
  function listedSessions() {
    return sessionsInWorkspace().filter(item => item.archived !== true || item.id === currentSessionId);
  }

  function renderSessionNavigation() {
    elements.sessionSelector.replaceChildren();
    for (const session of listedSessions()) {
      const option = document.createElement("option");
      option.value = session.id;
      option.textContent = session.title || session.id.slice(0, 8);
      elements.sessionSelector.appendChild(option);
    }
    elements.sessionSelector.value = currentSessionId;
    const current = sessions.find(item => item.id === currentSessionId);
    elements.sessionTitleText.textContent = current ? (current.title || t("未命名会话")) : t("正在加载会话...");
    renderDrawer();
  }

  // ----- Conversation drawer: the visible navigation; the hidden selects keep the state. -----
  function relativeTime(value) {
    const time = new Date(value).getTime();
    if (!value || !Number.isFinite(time)) return "";
    const minutes = Math.floor((Date.now() - time) / 60000);
    if (minutes < 1) return t("刚刚");
    if (minutes < 60) return t("{0} 分钟前", minutes);
    if (minutes < 24 * 60) return t("{0} 小时前", Math.floor(minutes / 60));
    if (minutes < 48 * 60) return t("昨天");
    return new Date(time).toLocaleDateString(locale, { month: "numeric", day: "numeric" });
  }

  function drawerNavigationBusy() {
    return isLoadingSession || isUploading || restartPending || isPreparingSubmission || localDeviceTesting || (!!activeTask && !activeTask.id);
  }

  let showArchived = false;

  function drawerSessionItem(session, busy) {
    const item = document.createElement("div");
    item.className = "drawer-session-item";
    const row = document.createElement("button");
    row.type = "button";
    row.className = "drawer-session";
    row.dataset.sessionId = session.id;
    if (session.id === currentSessionId) row.setAttribute("aria-current", "true");
    const title = document.createElement("span");
    title.className = "drawer-session-title";
    title.textContent = session.title || t("未命名会话");
    const meta = document.createElement("small");
    const running = [...backgroundTasks.values()].some(task => task.sessionId === session.id && !task.done);
    meta.textContent = running ? t("任务进行中") : session.archived ? t("已归档") : relativeTime(session.updated_at);
    if (running) row.dataset.running = "true";
    row.append(title, meta);
    row.disabled = busy;
    row.addEventListener("click", async () => {
      if (session.id === currentSessionId) { closeDrawer(); return; }
      if (await switchSession(session.id)) closeDrawer();
    });
    const archived = session.archived === true;
    const label = session.title || t("未命名会话");
    const toggle = actionButton(archived ? "archive-restore" : "archive", archived ? t("恢复 {0}", label) : t("归档 {0}", label),
      archived ? "data-session-restore" : "data-session-archive", session.id);
    toggle.classList.add("drawer-session-action");
    toggle.disabled = busy || running;
    toggle.addEventListener("click", () => setSessionArchived(session, !archived));
    item.append(row, toggle);
    return item;
  }

  function renderDrawer() {
    if (disposed || !elements.drawerSessionList) return;
    const busy = drawerNavigationBusy();
    elements.drawerWorkspaces.replaceChildren();
    for (const workspace of workspaces) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "drawer-workspace";
      chip.setAttribute("role", "radio");
      chip.setAttribute("aria-checked", String(workspace.id === currentWorkspaceId));
      chip.dataset.workspaceId = workspace.id;
      chip.title = workspace.path;
      chip.textContent = workspace.name || workspace.path;
      chip.disabled = busy || workspaceSaving;
      chip.addEventListener("click", async () => { if (workspace.id !== currentWorkspaceId) await switchWorkspace(workspace.id); });
      elements.drawerWorkspaces.appendChild(chip);
    }
    elements.drawerWorkspaces.hidden = !workspaces.length;
    elements.drawerSessionList.replaceChildren();
    const byRecent = (first, second) => String(second.updated_at || "").localeCompare(String(first.updated_at || ""));
    const visible = sessionsInWorkspace().filter(item => item.archived !== true).sort(byRecent);
    const archived = sessionsInWorkspace().filter(item => item.archived === true).sort(byRecent);
    for (const session of visible) elements.drawerSessionList.appendChild(drawerSessionItem(session, busy));
    if (!visible.length) {
      const empty = document.createElement("p");
      empty.className = "drawer-empty";
      empty.textContent = t("这个工作区还没有会话");
      elements.drawerSessionList.appendChild(empty);
    }
    if (archived.length) {
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "text-action drawer-archived-toggle";
      toggle.textContent = t("已归档 · {0}", archived.length);
      toggle.setAttribute("aria-expanded", String(showArchived));
      toggle.addEventListener("click", () => { showArchived = !showArchived; renderDrawer(); });
      elements.drawerSessionList.appendChild(toggle);
      if (showArchived) for (const session of archived) elements.drawerSessionList.appendChild(drawerSessionItem(session, busy));
    }
    elements.btnDrawerNewSession.disabled = busy || elements.btnNewSession.disabled;
  }

  async function setSessionArchived(session, archived) {
    if (disposed) return;
    const label = session.title || t("未命名会话");
    if (archived && !window.confirm(t("归档「{0}」？\n会话会从列表隐藏，记录仍完整保留，可在「已归档」中恢复。", label))) return;
    try {
      await apiJson(`/sessions/${encodeURIComponent(session.id)}/archive`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ archived }) });
      session.archived = archived;
      haptic(16);
      if (archived && session.id === currentSessionId) {
        // Leave the archived conversation for the most recent remaining one, or a fresh one.
        const next = sessionsInWorkspace().filter(item => item.archived !== true && item.id !== session.id)
          .sort((first, second) => String(second.updated_at || "").localeCompare(String(first.updated_at || "")))[0];
        if (next) await switchSession(next.id);
        else await createSession();
      }
    } catch (error) {
      if (!disposed) notice(error.status === 409 ? t("该会话仍有运行中的任务，请先停止任务") : (archived ? t("归档失败: {0}", error.message) : t("恢复会话失败: {0}", error.message)));
    } finally {
      if (!disposed) renderSessionNavigation();
    }
  }

  function openDrawer() {
    if (disposed || !elements.sessionDrawer.hidden) return;
    if (!elements.settingsOverlay.hidden && !closeMenu()) return;
    renderDrawer();
    elements.sessionDrawer.hidden = false;
    elements.appShell.inert = true;
    elements.btnSessions.setAttribute("aria-expanded", "true");
    (elements.drawerSessionList.querySelector('[aria-current="true"]') || elements.btnDrawerClose).focus({ preventScroll: true });
    haptic();
  }

  function closeDrawer() {
    if (elements.sessionDrawer.hidden) return false;
    elements.sessionDrawer.hidden = true;
    elements.appShell.inert = false;
    elements.btnSessions.setAttribute("aria-expanded", "false");
    elements.btnSessions.focus({ preventScroll: true });
    return true;
  }

  function refreshWorkspaceAccess() {
    if (typeof bridge?.workspaceStorageStatus !== "function") return;
    try {
      const status = JSON.parse(bridge.workspaceStorageStatus());
      elements.workspaceStorageStatus.hidden = false;
      pageStatus(elements.workspaceStorageStatus, status.granted ? t("公共文件夹访问已授权") : t("公共文件夹需要文件访问授权；应用内文件夹可直接使用"));
      elements.btnWorkspaceStorageSettings.hidden = status.granted || typeof bridge?.requestWorkspaceStorageAccess !== "function";
    } catch { pageStatus(elements.workspaceStorageStatus, t("无法读取文件访问权限"), true); }
  }

  async function loadWorkspaces() {
    const generation = ++workspaceGeneration;
    try {
      const data = await apiJson("/mobile/workspaces");
      if (disposed || generation !== workspaceGeneration) return;
      if (Array.isArray(data.workspaces)) {
        workspaces = data.workspaces.filter(item => item && typeof item.id === "string" && typeof item.path === "string");
        defaultWorkspaceId = data.default_workspace_id || workspaces.find(item => item.is_default)?.id || workspaces[0]?.id || "";
        if (!workspaces.some(item => item.id === currentWorkspaceId)) currentWorkspaceId = defaultWorkspaceId;
        renderWorkspaceNavigation();
        try { bridge?.refreshWorkspaceDocuments?.(); } catch { /* The app file page remains available. */ }
        pageStatus(elements.workspacesStatus, "");
      }
    } catch (error) {
      if (!disposed && settingsPage === "workspaces") pageStatus(elements.workspacesStatus, t("读取工作区失败: {0}", error.message), true);
    } finally { if (!disposed) { refreshWorkspaceAccess(); syncWorkspaceControls(); } }
  }

  function detachSessionTask() {
    if (activeTask?.id) { backgroundTasks.set(activeTask.sessionId, activeTask); activeTask.card = null; }
    activeTask = null;
    taskAdoptionGeneration += 1;
    showApproval(null);
  }

  async function switchWorkspace(id) {
    if (!workspaces.some(item => item.id === id) || isLoadingSession || isUploading || isPreparingSubmission || restartPending || localDeviceTesting || !canLeaveFileEditor() || fileSaving || (!!activeTask && !activeTask.id)) return false;
    const previousWorkspaceId = currentWorkspaceId;
    const previousSessionId = currentSessionId;
    const previousSessions = sessions;
    saveDraft();
    detachSessionTask();
    currentWorkspaceId = id;
    writeStorage(workspaceKey, id);
    resetFilePreview();
    fileEditor = null;
    workspacePath = "";
    workspaceParent = null;
    filesGeneration += 1;
    usageGeneration += 1;
    renderWorkspaceNavigation();
    if (!await loadSessions("")) {
      currentWorkspaceId = previousWorkspaceId;
      currentSessionId = previousSessionId;
      selectedSessionId = previousSessionId;
      sessions = previousSessions;
      writeStorage(workspaceKey, previousWorkspaceId);
      writeStorage(sessionKey, previousSessionId);
      renderWorkspaceNavigation();
      renderSessionNavigation();
      restoreDraft(previousSessionId);
      isLoadingSession = true;
      syncControls();
      try {
        await loadTimeline(previousSessionId);
        if (historyReady) await recoverSessionTask(previousSessionId);
      } finally { isLoadingSession = false; syncControls(); }
      return false;
    }
    return currentWorkspaceId === id && historyReady;
  }

  async function createWorkspace(event) {
    event?.preventDefault();
    if (elements.btnCreateWorkspace.disabled) return;
    const payload = { name: elements.workspaceNameInput.value.trim(), path: elements.workspaceFolderInput.value.trim(), create: elements.workspaceCreateDirectory.checked };
    workspaceSaving = true;
    syncWorkspaceControls();
    pageStatus(elements.workspacesStatus, t("创建中..."));
    try {
      const data = await apiJson("/mobile/workspaces", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const workspace = data.workspace || data;
      if (!workspace?.id || typeof workspace.path !== "string") throw new Error(t("服务未返回工作区"));
      workspaces = [...workspaces.filter(item => item.id !== workspace.id), workspace];
      workspaceSaving = false;
      elements.workspaceNameInput.value = "";
      elements.workspaceFolderInput.value = "";
      elements.workspaceCreateDirectory.checked = false;
      await switchWorkspace(workspace.id);
      pageStatus(elements.workspacesStatus, t("已创建"));
      renderWorkspaceNavigation();
      try { bridge?.refreshWorkspaceDocuments?.(); } catch { /* The app file page remains available. */ }
    } catch (error) { if (!disposed) pageStatus(elements.workspacesStatus, t("创建工作区失败: {0}", error.message), true); }
    finally { workspaceSaving = false; if (!disposed) syncControls(); }
  }

  function syncControls() {
    if (disposed) return;
    const busy = !!activeTask || isLoadingSession || restartPending || isPreparingSubmission || localDeviceTesting;
    elements.appShell.dataset.busy = String(!!activeTask);
    const hasInput = !!elements.promptInput.value.trim() || attachments.length > 0;
    // While a task runs, typing adds to it ("steering"): Send sits next to Stop once there is text.
    const steerable = canSteer();
    elements.btnSend.disabled = steerable
      ? isSteering || isUploading || !hasInput
      : busy || isUploading || !settingsAvailable || !historyReady || !currentSessionId || !hasInput;
    elements.promptInput.disabled = isPreparingSubmission;
    elements.btnSend.hidden = !!activeTask?.id && !(steerable && hasInput);
    elements.btnStop.hidden = !activeTask?.id;
    elements.promptInput.placeholder = steerable ? t("补充说明，Agent 会在下一步采纳...") : t("给 Agent 布置任务…");
    elements.btnStop.disabled = !activeTask?.id || !!activeTask?.stopping;
    const navigationBusy = isLoadingSession || isUploading || restartPending || isPreparingSubmission || localDeviceTesting || (!!activeTask && !activeTask.id);
    elements.btnNewSession.disabled = navigationBusy;
    elements.sessionSelector.disabled = navigationBusy;
    elements.workspaceSelector.disabled = navigationBusy || workspaceSaving;
    elements.btnAttach.disabled = isLoadingSession || isUploading || restartPending || isPreparingSubmission || !historyReady || !currentSessionId;
    elements.filePickerInput.disabled = elements.btnAttach.disabled;
    elements.quickChipsBar.querySelectorAll(".chip").forEach((chip) => {
      chip.disabled = busy || !historyReady || !currentSessionId;
    });
    const restartBlocked = busy || isUploading || localDeviceTesting || hasBackgroundTasks();
    elements.btnApplySettings.disabled = restartBlocked || !settingsAvailable || !elements.modelInput.value.trim()
      || (settingsPage === "permission" && typeof bridge?.applyRuntimeSettings !== "function")
      || (settingsPage === "localModels" && (localContextBusy || typeof bridge?.applyRuntimeSettings !== "function"));
    elements.modelInput.disabled = restartBlocked;
    elements.effortSelector.disabled = restartBlocked || supportedEfforts(elements.modelInput.value.trim()).length === 1;
    elements.btnProviderSettings.disabled = restartBlocked;
    elements.autonomySelector.disabled = restartBlocked || typeof bridge?.applyRuntimeSettings !== "function";
    elements.contextSummaryToggle.disabled = restartBlocked || typeof bridge?.applyRuntimeSettings !== "function";
    elements.localContextSelector.disabled = restartBlocked || localContextBusy || typeof bridge?.applyRuntimeSettings !== "function";
    elements.localContextCustomInput.disabled = elements.localContextSelector.disabled;
    elements.localMemorySelector.disabled = elements.localContextSelector.disabled;
    elements.localThreadsInput.disabled = elements.localContextSelector.disabled;
    elements.localTimeoutInput.disabled = elements.localContextSelector.disabled;
    if (localDeviceTesting) elements.btnSend.disabled = true;
    elements.btnExport.disabled = !historyReady || !currentSessionId;
    elements.searchResults.querySelectorAll(".search-result").forEach((button) => {
      button.disabled = navigationBusy;
    });
    elements.taskCenterList.querySelectorAll("[data-task-open]").forEach((button) => {
      button.disabled = navigationBusy;
    });
    const title = elements.sessionTitleInput.value.trim();
    elements.sessionTitleInput.disabled = !currentSessionId || isLoadingSession || renameSaving;
    elements.btnRenameSession.disabled = !currentSessionId || isLoadingSession || renameSaving || !title || title.length > 200;
    $("btnArchiveSession").disabled = !currentSessionId || isLoadingSession || !!activeTask;
    syncFileControls();
    syncWorkspaceControls();
    syncImportControls();
    syncDrawerControls(navigationBusy);
  }

  function syncDrawerControls(navigationBusy) {
    if (elements.sessionDrawer.hidden) return;
    elements.drawerSessionList.querySelectorAll(".drawer-session").forEach((row) => { row.disabled = navigationBusy; });
    elements.drawerWorkspaces.querySelectorAll(".drawer-workspace").forEach((chip) => { chip.disabled = navigationBusy || workspaceSaving; });
    elements.btnDrawerNewSession.disabled = elements.btnNewSession.disabled;
  }

  function saveDraft() {
    if (!currentSessionId) return;
    const savedAttachments = attachments.map(attachmentReceipt);
    const recovered = recoveredPendingDraft?.sessionId === currentSessionId
      && recoveredPendingDraft.text === elements.promptInput.value
      && recoveredPendingDraft.attachments === JSON.stringify(savedAttachments);
    drafts[currentSessionId] = { ...draftMetadata(currentSessionId), text: elements.promptInput.value, attachments: savedAttachments,
      ...(recovered ? { pendingRequestId: recoveredPendingDraft.requestId } : {}) };
    if (!recovered) recoveredPendingDraft = null;
    return writeStorage(draftsKey, drafts);
  }

  function draftMetadata(sessionId) {
    const saved = drafts[sessionId];
    return {
      ...(Array.isArray(saved?.shared_item_ids) ? { shared_item_ids: saved.shared_item_ids } : {}),
      ...(Array.isArray(saved?.shared_batch_ids) ? { shared_batch_ids: saved.shared_batch_ids } : {}),
    };
  }

  function attachmentReceipt(item) {
    return { name: item.name, path: item.path, size: item.size, sha256: item.sha256, media_type: item.media_type };
  }

  function hasImageName(item) {
    return /\.(png|apng|jpe?g|jfif|webp|gif|bmp|tiff?|svgz?|ico|heic|heif|avif|dng|jxl)$/i.test(item.name || item.path || "");
  }

  function restoreDraft(sessionId) {
    const draft = drafts[sessionId];
    elements.promptInput.value = typeof draft === "string" ? draft : (draft?.text || "");
    attachments = Array.isArray(draft?.attachments) ? draft.attachments : [];
    recoveredPendingDraft = null;
    const pending = pendingRequests[sessionId];
    const recoveringEmptyDraft = !elements.promptInput.value && !attachments.length
      && typeof pending?.inputText === "string" && pending.requestId;
    if (recoveringEmptyDraft) {
      elements.promptInput.value = pending.inputText;
      attachments = Array.isArray(pending.attachments) ? pending.attachments : [];
    }
    if (pending?.requestId && (recoveringEmptyDraft || draft?.pendingRequestId === pending.requestId)
      && elements.promptInput.value === pending.inputText
      && JSON.stringify(attachments.map(attachmentReceipt)) === JSON.stringify((pending.attachments || []).map(attachmentReceipt))) {
      recoveredPendingDraft = { sessionId, requestId: pending.requestId, text: pending.inputText,
        attachments: JSON.stringify(attachments.map(attachmentReceipt)) };
      saveDraft();
    }
    renderAttachments();
    resizePrompt();
    syncControls();
  }

  function resizePrompt() {
    const input = elements.promptInput;
    input.style.height = "auto";
    const limit = Number.parseFloat(window.getComputedStyle(input).maxHeight) || 160;
    input.style.height = `${Math.min(input.scrollHeight, limit)}px`;
  }

  // A draft restored before the first layout is measured at the wrong width; re-measure when the width settles.
  let promptWidth = 0;
  if (typeof window.ResizeObserver === "function") {
    new window.ResizeObserver(() => {
      const width = elements.promptInput.clientWidth;
      if (width && width !== promptWidth) { promptWidth = width; resizePrompt(); }
    }).observe(elements.promptInput);
  }
  document.fonts?.ready?.then(() => { if (!disposed) resizePrompt(); });

  function resizeVisibleViewport() {
    const viewport = window.visualViewport;
    if (!viewport || Math.abs((viewport.scale || 1) - 1) > 0.01 || !Number.isFinite(viewport.height) || viewport.height <= 0) return;
    document.documentElement.style.setProperty("--visible-height", `${Math.round(viewport.height)}px`);
    if (stickToBottom) scrollToBottom(true);
  }

  function supportedEfforts(model) {
    const declared = settings.model_efforts?.[model];
    const values = Array.isArray(declared) ? declared.filter((effort) => effort in effortLabels) : [];
    return values.length ? [...new Set(values)] : ["auto"];
  }

  function fillEffortOptions(model, proposed) {
    const values = supportedEfforts(model);
    elements.effortSelector.replaceChildren();
    for (const value of values) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = effortLabels[value];
      elements.effortSelector.appendChild(option);
    }
    elements.effortSelector.value = values.includes(proposed) ? proposed : "auto";
    elements.effortHint.textContent = values.length === 1 ? t("此模型使用自动思考强度") : "";
    elements.effortSelector.disabled = values.length === 1 || !!activeTask;
  }

  function setLocalContextDraft(tokens) {
    elements.localContextSelector.value = localContextOptions.includes(tokens) ? String(tokens) : "custom";
    elements.localContextCustomInput.value = String(tokens > 0 ? tokens : 8192);
    elements.localContextCustomRow.hidden = elements.localContextSelector.value !== "custom";
  }

  function readLocalContextDraft() {
    if (elements.localContextSelector.value !== "custom") return Number(elements.localContextSelector.value);
    const value = elements.localContextCustomInput.value.trim();
    return value && Number(value) > 0 ? Number(value) : NaN;
  }

  function validLocalContext(tokens) { return Number.isInteger(tokens) && (tokens === 0 || tokens >= 512 && tokens <= 262144); }

  function experimentalLocalSummary(baseUrl) {
    return typeof baseUrl === "string"
      && baseUrl.replace(/\/+$/, "") === "http://127.0.0.1:8080/embedded-qwen/v1";
  }

  function renderSettings() {
    const model = settings.model || t("未配置模型");
    const effort = effortLabels[settings.reasoning_effort] || effortLabels.auto;
    // The composer chip is narrow: name the effort only when it is not automatic.
    elements.modelSummary.textContent = settings.reasoning_effort && settings.reasoning_effort !== "auto" ? `${model} · ${effort}` : model;
    elements.modelBar.title = t("{0} · 思考强度 {1}", model, effort);
    elements.executionSummary.textContent = autonomyLabels[settings.autonomy] || autonomyLabels.workspace;
    // The composer shows the mode as a color-coded shield; the name stays available to touch and screen readers.
    elements.btnModeChip.dataset.mode = settings.autonomy in autonomyLabels ? settings.autonomy : "workspace";
    elements.btnModeChip.setAttribute("aria-label", t("执行权限：{0}", elements.executionSummary.textContent));
    elements.btnModeChip.title = t("执行权限：{0}", elements.executionSummary.textContent);
    elements.menuModelSummary.textContent = `${model} · ${effort}`;
    elements.menuPermissionSummary.textContent = autonomyLabels[settings.autonomy] || autonomyLabels.workspace;
    elements.modelInput.value = settings.model;
    elements.modelOptions.replaceChildren();
    for (const item of settings.models || []) {
      const option = document.createElement("option");
      option.value = item;
      elements.modelOptions.appendChild(option);
    }
    fillEffortOptions(settings.model, settings.reasoning_effort);
    elements.autonomySelector.value = settings.autonomy;
    elements.contextSummaryToggle.checked = settings.context_summary_enabled;
    contextSummaryDirty = false;
    const experimentalSummary = experimentalLocalSummary(settings.base_url);
    elements.contextSummaryLabel.textContent = experimentalSummary ? t("本机摘要（实验功能）") : t("自动摘要压缩上下文");
    elements.contextSummaryHint.textContent = experimentalSummary
      ? t("本机摘要为实验功能，0.8B 真机测试会丢待办或误记完成状态。其他本机型号尚未完成保真验收，默认关闭，可自行启用。关闭时超出容量的早期记录会被裁剪；原始会话仍保留。")
      : t("临近容量时由当前模型总结较早记录。会额外调用模型，可能产生 Token 费用；摘要可能遗漏细节，原始会话仍保留。");
    setLocalContextDraft(settings.local_context_tokens);
    elements.localMemorySelector.value = settings.local_memory_mode;
    elements.localThreadsInput.value = String(settings.local_threads);
    elements.localTimeoutInput.value = String(settings.local_timeout_seconds);
    elements.autonomyHint.textContent = typeof bridge?.applyRuntimeSettings === "function"
      ? t("更改执行模式会重新启动本地引擎")
      : t("请在 Android 应用中更改执行模式");
    elements.btnProviderSettings.hidden = typeof bridge?.openSettings !== "function";
    syncControls();
  }

  async function loadSettings() {
    try {
      const data = typeof bridge?.getProviderSettings === "function"
        ? JSON.parse(bridge.getProviderSettings())
        : await apiJson("/mobile/settings");
      if (!data || typeof data.model !== "string") throw new Error(t("模型设置不可用"));
      settings = {
        ...settings, ...data,
        reasoning_effort: data.reasoning_effort || "auto",
        autonomy: data.autonomy || "workspace",
        context_summary_enabled: typeof data.context_summary_enabled === "boolean"
          ? data.context_summary_enabled : !experimentalLocalSummary(data.base_url),
        local_context_tokens: validLocalContext(data.local_context_tokens) ? data.local_context_tokens : 0,
        local_memory_mode: ["balanced", "extended"].includes(data.local_memory_mode) ? data.local_memory_mode : "balanced",
        local_threads: Number.isInteger(data.local_threads) && data.local_threads >= 0 && data.local_threads <= 64 ? data.local_threads : 0,
        local_timeout_seconds: Number.isInteger(data.local_timeout_seconds) && data.local_timeout_seconds >= 0 && data.local_timeout_seconds <= 7200 ? data.local_timeout_seconds : 0,
      };
      if (typeof bridge?.getProviderSettings !== "function") {
        const selected = readStorage(runtimeChoiceKey, null);
        if (selected && selected.protocol === settings.protocol && selected.base_url === settings.base_url && typeof selected.model === "string") {
          settings.model = selected.model;
          settings.reasoning_effort = selected.reasoning_effort || "auto";
        }
      }
      if (!supportedEfforts(settings.model).includes(settings.reasoning_effort)) settings.reasoning_effort = "auto";
      settingsAvailable = true;
      setConnection(true);
    } catch (error) {
      if (disposed) return;
      settingsAvailable = false;
      notice(t("读取模型设置失败: {0}", error.message));
      setConnection(false);
    }
    renderSettings();
  }

  function setSettingsPage(page, initial = false) {
    if (settingsPage === "files" && page !== "files" && !canLeaveFileEditor()) return false;
    const previousPage = settingsPage;
    const movingBack = (page === "home" && previousPage !== "home") || (page === "usage" && previousPage === "pricing");
    if (!initial && page !== previousPage) settingsScrollPositions.set(previousPage, elements.settingsScrollBody.scrollTop);
    if (settingsPage === "search" && page !== "search") invalidateSearch();
    if (settingsPage === "tasks" && page !== "tasks") taskCenterGeneration += 1;
    if (settingsPage === "files" && page !== "files") { filesGeneration += 1; resetFilePreview(); }
    if (settingsPage === "usage" && page !== "usage") usageGeneration += 1;
    settingsPage = page;
    const titles = { home: t("菜单"), model: t("模型与思考"), permission: t("执行权限"), appearance: t("界面偏好"), search: t("搜索会话"), tasks: t("任务中心"), files: t("工作区文件"), attachments: t("附件收件箱"), session: t("会话名称"), notifications: t("通知"), usage: t("Token 与费用"), pricing: t("模型费率"), doctor: t("设备与工具"), extensions: t("MCP 与扩展"), schedules: t("定时任务"), connections: t("设备连接"), outbox: t("待发送与接力"), workflows: t("可复用流程"), evaluations: t("任务评测"), localModels: t("本地模型"), workspaces: t("工作区") };
    document.querySelectorAll(".settings-page").forEach((element) => { element.hidden = true; });
    const selectedPage = document.getElementById(`settings${page[0].toUpperCase()}${page.slice(1)}`);
    if (selectedPage) {
      if (initial || page !== previousPage) selectedPage.dataset.navigation = initial ? "initial" : movingBack ? "back" : "forward";
      selectedPage.hidden = false;
    }
    placeHeaderActions(selectedPage);
    elements.settingsTitle.textContent = titles[page];
    elements.settingsBackButton.hidden = page === "home";
    elements.settingsHome.hidden = page !== "home";
    elements.settingsModel.hidden = page !== "model";
    elements.settingsPermission.hidden = page !== "permission";
    elements.settingsAppearance.hidden = page !== "appearance";
    elements.settingsSearch.hidden = page !== "search";
    elements.settingsTasks.hidden = page !== "tasks";
    elements.settingsFiles.hidden = page !== "files";
    elements.settingsSession.hidden = page !== "session";
    elements.settingsNotifications.hidden = page !== "notifications";
    elements.settingsUsage.hidden = page !== "usage";
    elements.settingsPricing.hidden = page !== "pricing";
    elements.settingsActions.hidden = !["model", "permission", "localModels"].includes(page);
    elements.btnApplySettings.textContent = page === "permission" ? t("应用执行模式") : page === "localModels" ? t("应用本机设置") : t("应用设置");
    elements.settingsError.hidden = true;
    if (page === "model") {
      elements.modelInput.value = settings.model;
      fillEffortOptions(settings.model, settings.reasoning_effort);
      elements.contextSummaryToggle.checked = settings.context_summary_enabled;
      contextSummaryDirty = false;
    }
    if (page === "permission") elements.autonomySelector.value = settings.autonomy;
    if (page === "localModels") {
      localContextBusy = true;
      setLocalContextDraft(settings.local_context_tokens);
      elements.localMemorySelector.value = settings.local_memory_mode;
      elements.localThreadsInput.value = String(settings.local_threads);
      elements.localTimeoutInput.value = String(settings.local_timeout_seconds);
    }
    if (page === "search") {
      if (elements.sessionSearchInput.value.trim()) queueSessionSearch();
    }
    if (page === "tasks") void loadTaskCenter();
    if (page === "attachments") refreshShareInbox();
    if (page === "workspaces") { renderWorkspaceNavigation(); refreshWorkspaceAccess(); void loadWorkspaces(); }
    if (page === "files") {
      if (fileEditor?.loaded) renderFileEditor();
      else void loadWorkspaceFiles(workspacePath);
    }
    if (page === "session") {
      elements.sessionTitleInput.value = sessions.find((session) => session.id === currentSessionId)?.title || "";
      pageStatus(elements.sessionRenameStatus, "");
    }
    if (page === "notifications") refreshNotificationSettings();
    if (page === "usage") void loadUsage();
    syncControls();
    if (initial || page !== previousPage) {
      elements.settingsScrollBody.scrollTop = movingBack ? (settingsScrollPositions.get(page) || 0) : 0;
      if (!elements.settingsOverlay.hidden) {
        const returnButton = movingBack ? document.getElementById(`btn${previousPage[0].toUpperCase()}${previousPage.slice(1)}Page`) : null;
        const focusTarget = page === "search" ? elements.sessionSearchInput
          : returnButton && !returnButton.disabled && !returnButton.closest("[hidden]") ? returnButton
          : page === "home" ? elements.settingsCloseButton : elements.settingsBackButton;
        focusTarget.focus({ preventScroll: true });
      }
    }
    return true;
  }

  // Page-level actions (refresh) live in the sheet header while their page is shown.
  const headerActionHomes = new Map();
  function placeHeaderActions(page) {
    for (const button of [...elements.settingsHeaderActions.children]) {
      const home = headerActionHomes.get(button);
      if (home) home.parent.insertBefore(button, home.next?.parentNode === home.parent ? home.next : null);
    }
    page?.querySelectorAll(":scope > [data-header-action]").forEach((button) => {
      headerActionHomes.set(button, { parent: button.parentNode, next: button.nextSibling });
      elements.settingsHeaderActions.appendChild(button);
    });
  }

  function invalidateSearch() {
    searchGeneration += 1;
    window.clearTimeout(searchTimer);
    searchTimer = null;
  }

  function queueSessionSearch() {
    invalidateSearch();
    const query = elements.sessionSearchInput.value.trim();
    const generation = searchGeneration;
    elements.searchResults.replaceChildren();
    if (!query) {
      elements.searchStatus.textContent = t("输入关键词搜索");
      return;
    }
    elements.searchStatus.textContent = t("搜索中...");
    searchTimer = window.setTimeout(async () => {
      if (disposed || generation !== searchGeneration) return;
      try {
        const data = await apiJson(`/mobile/sessions/search?q=${encodeURIComponent(query)}&limit=30`);
        if (disposed || generation !== searchGeneration || elements.sessionSearchInput.value.trim() !== query) return;
        const results = Array.isArray(data.results) ? data.results : [];
        for (const result of results.slice(0, 30)) {
          if (!result || typeof result.session_id !== "string" || !result.session_id) continue;
          const button = document.createElement("button");
          button.type = "button";
          button.className = "search-result";
          button.title = t("打开会话");
          const title = document.createElement("strong");
          title.textContent = typeof result.title === "string" && result.title ? result.title : result.session_id;
          const snippet = document.createElement("span");
          snippet.textContent = typeof result.snippet === "string" ? result.snippet : "";
          const kind = document.createElement("small");
          kind.textContent = result.document_kind === "comment" ? t("评论") : t("对话");
          button.append(title, snippet, kind);
          button.addEventListener("click", async () => {
            if (await switchSession(result.session_id, title.textContent)) closeMenu();
          });
          elements.searchResults.appendChild(button);
        }
        elements.searchStatus.textContent = elements.searchResults.children.length ? "" : t("没有找到结果");
        syncControls();
      } catch (error) {
        if (disposed || generation !== searchGeneration) return;
        elements.searchResults.replaceChildren();
        elements.searchStatus.textContent = t("搜索失败: {0}", error.message);
      }
    }, 180);
  }

  function openMenu() {
    if (disposed || !elements.settingsOverlay.hidden) return;
    elements.settingsOverlay.hidden = false;
    elements.appShell.inert = true;
    elements.btnSettings.setAttribute("aria-expanded", "true");
    settingsScrollPositions.clear();
    setSettingsPage("home", true);
    haptic();
  }

  // Android back: leave the open file, then the sub page, then the sheet itself.
  function handleBack() {
    if (disposed) return false;
    if (closeDrawer()) return true;
    if (elements.settingsOverlay.hidden) return false;
    if (settingsPage === "files" && fileEditor && !fileSaving) { void loadWorkspaceFiles(workspacePath); return true; }
    if (settingsPage === "home") { closeMenu(); return true; }
    setSettingsPage(settingsPage === "pricing" ? "usage" : "home");
    return true;
  }

  function openModelSettings() {
    if (disposed) return;
    if (elements.settingsOverlay.hidden) openMenu();
    setSettingsPage("model");
  }

  function closeMenu() {
    if (elements.settingsOverlay.hidden) return false;
    if (settingsPage === "files" && !canLeaveFileEditor()) return false;
    if (settingsPage === "search") invalidateSearch();
    if (settingsPage === "tasks") taskCenterGeneration += 1;
    if (settingsPage === "files") { filesGeneration += 1; resetFilePreview(); }
    if (settingsPage === "usage") usageGeneration += 1;
    elements.settingsOverlay.hidden = true;
    elements.appShell.inert = false;
    elements.btnSettings.setAttribute("aria-expanded", "false");
    elements.btnSettings.focus();
    return true;
  }

  function receiveSharedText(text) {
    if (disposed || typeof text !== "string") return false;
    if (!text.trim() || text.length > maxSharedTextLength) return false;
    if (!currentSessionId || isLoadingSession || isPreparingSubmission || !historyReady) return false;
    const nextText = elements.promptInput.value
      ? `${elements.promptInput.value}\n\n${text}` : text;
    const draft = {
      ...draftMetadata(currentSessionId),
      text: nextText,
      attachments: attachments.map(attachmentReceipt),
    };
    try {
      window.localStorage.setItem(draftsKey, JSON.stringify({ ...drafts, [currentSessionId]: draft }));
    } catch { return false; }
    drafts[currentSessionId] = draft;
    elements.promptInput.value = nextText;
    elements.promptInput.dispatchEvent(new window.Event("input", { bubbles: true }));
    elements.promptInput.focus();
    return true;
  }

  function openSession(sessionId) {
    if (disposed || typeof sessionId !== "string" || !sessionId || sessionId.length > 200) return false;
    if (unavailableSessions.has(sessionId) && !isLoadingSession && historyReady) {
      notice(t("目标会话不存在或已删除"));
      return true;
    }
    if (!isLoadingSession && historyReady && currentSessionId === sessionId) {
      void refreshCurrentSessionTask();
      closeMenu();
      return true;
    }
    if (isLoadingSession || !historyReady || isUploading || isPreparingSubmission || restartPending || (!!activeTask && !activeTask.id) || sessionOpening) return false;
    if (!canLeaveFileEditor()) return false;
    sessionOpening = sessionId;
    void switchSession(sessionId).finally(() => { sessionOpening = null; });
    return false;
  }

  window.AgentMobileUi = { closeMenu, handleBack, notice, reloadForLanguage: () => window.location.reload(), receiveSharedText, openSession, apiJson, setSettingsPage, adoptTask,
    readLocalContextDraft, setLocalContextDraft,
    setLocalContextBusy: (busy) => { localContextBusy = !!busy; syncControls(); },
    setLocalDeviceTestBusy: (busy) => { localDeviceTesting = !!busy; syncControls(); },
    context: () => ({ sessionId: currentSessionId, workspaceId: currentWorkspaceId, settings: { ...settings }, activeTask: !!activeTask || isPreparingSubmission || localDeviceTesting, draft: elements.promptInput.value,
      recentText: historyEvents.filter((event) => event.type === "message.created" && ["user", "assistant"].includes(event.data?.role)).slice(-6).map((event) => `${event.data.role}: ${event.data.content || ""}`).join("\n").slice(-16384) }),
  };
  window.AgentMobile = window.AgentMobileUi;

  function pageStatus(element, text, error = false) {
    element.textContent = text;
    element.classList.toggle("error", error);
  }

  const taskStateLabels = { queued: t("排队中"), running: t("执行中"), waiting_approval: t("等待审批"), succeeded: t("已完成"), failed: t("失败"), cancelled: t("已停止"), interrupted: t("已中断") };

  function displayTime(value) {
    const time = new Date(value);
    return value && Number.isFinite(time.getTime()) ? time.toLocaleString(locale, { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
  }

  function actionButton(name, label, attribute, taskId) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "icon-button";
    button.title = label;
    button.setAttribute("aria-label", label);
    button.setAttribute(attribute, taskId);
    button.innerHTML = icon(name);
    return button;
  }

  function renderTaskCenter() {
    elements.taskCenterList.replaceChildren();
    for (const task of taskCenterTasks) {
      if (!task?.task_id || !task.session_id) continue;
      const row = document.createElement("div");
      row.className = "task-center-row";
      const title = document.createElement("strong");
      title.textContent = task.prompt_preview || task.task_id;
      const meta = document.createElement("div");
      meta.className = "task-center-meta";
      const state = document.createElement("span");
      state.textContent = taskStateLabels[task.state] || task.state;
      const time = document.createElement("time");
      time.textContent = displayTime(task.updated_at || task.created_at);
      if (task.updated_at || task.created_at) time.dateTime = task.updated_at || task.created_at;
      const model = document.createElement("span");
      model.textContent = task.model || "";
      meta.append(state, time, model);
      if (task.state === "failed" && typeof task.reason === "string" && task.reason.trim()) {
        const reason = document.createElement("span");
        reason.className = "task-center-reason";
        reason.textContent = task.reason.trim().slice(0, 300);
        meta.append(reason);
      }
      const actions = document.createElement("div");
      actions.className = "task-center-actions";
      const open = document.createElement("button");
      open.type = "button";
      open.className = "text-action";
      open.textContent = t("打开会话");
      open.dataset.taskOpen = task.task_id;
      open.dataset.sessionId = task.session_id;
      open.addEventListener("click", async () => {
        if (task.session_id === currentSessionId && !isLoadingSession && historyReady) {
          await refreshCurrentSessionTask();
          closeMenu();
        }
        else if (await switchSession(task.session_id)) closeMenu();
      });
      actions.appendChild(open);
      if (runningStates.has(task.state)) {
        const cancel = actionButton("square", t("停止任务"), "data-task-cancel", task.task_id);
        cancel.disabled = taskActions.has(task.task_id);
        cancel.addEventListener("click", () => changeTask(task, "cancel"));
        actions.appendChild(cancel);
      } else if (task.state === "interrupted" && task.resume_available) {
        const resume = actionButton("play", t("恢复任务"), "data-task-resume", task.task_id);
        resume.disabled = taskActions.has(task.task_id);
        resume.addEventListener("click", () => changeTask(task, "resume"));
        actions.appendChild(resume);
      }
      row.append(title, meta, actions);
      renderTaskArtifacts(row, task, task.task_id);
      elements.taskCenterList.appendChild(row);
    }
    syncControls();
  }

  async function loadTaskCenter() {
    const generation = ++taskCenterGeneration;
    pageStatus(elements.taskCenterStatus, t("加载中..."));
    try {
      const data = await apiJson("/mobile/tasks");
      if (generation !== taskCenterGeneration || settingsPage !== "tasks") return;
      if (workspaces.length && (data.tasks || []).some(task => !workspaceOfSession(task.session_id))) {
        const listing = await apiJson("/sessions");
        if (generation !== taskCenterGeneration || settingsPage !== "tasks") return;
        if (!Array.isArray(listing.sessions)) throw new Error(t("无法确认任务所属工作区"));
        sessions = [...new Map([...sessions, ...listing.sessions].map(session => [session.id, session])).values()];
        if ((data.tasks || []).some(task => !workspaceOfSession(task.session_id))) throw new Error(t("无法确认任务所属工作区，请刷新任务列表"));
      }
      taskCenterTasks = Array.isArray(data.tasks) ? [...data.tasks].sort((first, second) => String(second.created_at || "").localeCompare(String(first.created_at || ""))) : [];
      renderTaskCenter();
      pageStatus(elements.taskCenterStatus, taskCenterTasks.length ? "" : t("暂无任务"));
    } catch (error) {
      if (disposed || generation !== taskCenterGeneration || settingsPage !== "tasks") return;
      elements.taskCenterList.replaceChildren();
      pageStatus(elements.taskCenterStatus, t("加载任务失败: {0}", error.message), true);
    }
  }

  async function changeTask(snapshot, action) {
    if (taskActions.has(snapshot.task_id) || disposed) return;
    taskActions.add(snapshot.task_id);
    renderTaskCenter();
    const targetSessionId = snapshot.session_id;
    try {
      const result = await apiJson(`/mobile/tasks/${encodeURIComponent(snapshot.task_id)}/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      if (activeTask?.id === snapshot.task_id && action === "cancel") {
        activeTask.stopping = true;
        if (terminalStates.has(result.task?.state)) {
          activeTask.state = result.task.state;
          activeTask.done = true;
          finishTask(activeTask);
        } else if (!activeTask.watching) void watchTask(activeTask);
      } else if (action === "resume" && !activeTask && !isLoadingSession && targetSessionId === currentSessionId) {
        activeTask = makeTask(result.task || snapshot);
        interruptedTask = null;
        syncControls();
        void watchTask(activeTask);
      }
      if (settingsPage === "tasks" && !elements.settingsOverlay.hidden) await loadTaskCenter();
    } catch (error) {
      if (disposed) return;
      if (settingsPage === "tasks") pageStatus(elements.taskCenterStatus, t("{0}任务失败: {1}", action === "cancel" ? t("停止") : t("恢复"), error.message), true);
      else notice(error.message);
    } finally {
      taskActions.delete(snapshot.task_id);
      if (!disposed && settingsPage === "tasks") renderTaskCenter();
    }
  }

  function formatBytes(size) {
    const count = Number(size) || 0;
    return count >= 1024 * 1024 ? `${(count / (1024 * 1024)).toFixed(1)} MB` : count >= 1024 ? `${(count / 1024).toFixed(1)} KB` : `${count} B`;
  }

  function fileDirty() { return !!fileEditor?.loaded && fileEditor.content !== fileEditor.originalContent; }

  function fileDraftKey(path, workspaceId = fileEditor?.workspaceId || currentWorkspaceId) {
    return workspaceId && workspaceId !== defaultWorkspaceId ? `${workspaceId}:${path}` : path;
  }

  function persistFileDraft() {
    if (!fileEditor?.loaded || !fileEditor.editable) return true;
    const next = { ...fileDrafts };
    const key = fileDraftKey(fileEditor.path);
    if (fileDirty()) next[key] = { content: fileEditor.content, sha256: fileEditor.sha256 };
    else delete next[key];
    try {
      window.localStorage.setItem(fileDraftsKey, JSON.stringify(next));
      for (const path of Object.keys(fileDrafts)) delete fileDrafts[path];
      Object.assign(fileDrafts, next);
      return true;
    } catch {
      pageStatus(elements.fileEditorStatus, t("本地草稿保存失败，请先保存文件"), true);
      return false;
    }
  }

  function canLeaveFileEditor() {
    if (!fileDirty() || persistFileDraft()) return true;
    return window.confirm(t("文件草稿无法保存在手机上，离开可能丢失修改。继续离开？"));
  }

  function syncFileControls() {
    const loaded = !!fileEditor?.loaded;
    elements.fileContentInput.readOnly = !loaded || !fileEditor.editable || fileSaving;
    elements.btnSaveFile.disabled = !loaded || !fileEditor.editable || !fileDirty() || !!fileEditor.conflict || fileSaving || restartPending;
    elements.btnReloadFile.disabled = !loaded || fileSaving;
    elements.btnDiscardFileDraft.hidden = !loaded || (!fileDirty() && !fileDrafts[fileDraftKey(fileEditor?.path)]);
    elements.btnDiscardFileDraft.disabled = fileSaving;
    elements.btnFileParent.disabled = fileSaving || (!fileEditor && workspaceParent === null);
    elements.btnFilesRefresh.disabled = fileSaving;
    const preview = loaded && /\.(md|markdown|html?|png|jpe?g|webp|gif|svg)$/i.test(fileEditor.path);
    elements.btnFilePreview.hidden = !preview;
    elements.btnFileSource.hidden = !preview || fileEditor.is_binary;
    elements.btnFilePreview.disabled = !loaded || fileSaving;
    elements.btnFileSource.disabled = !loaded || fileSaving;
    elements.btnFileInteractive.hidden = !loaded || !/\.html?$/i.test(fileEditor.path) || typeof bridge?.workspaceFileAction !== "function";
    elements.btnFileInteractive.disabled = !loaded || fileSaving || fileDirty() || restartPending;
  }

  function resetFilePreview() {
    if (filePreviewUrl) URL.revokeObjectURL(filePreviewUrl);
    filePreviewUrl = null;
    elements.filePreviewPanel.replaceChildren();
    elements.filePreviewPanel.classList.remove("message-body");
    elements.filePreviewPanel.hidden = true;
    elements.fileContentInput.hidden = false;
    elements.btnFilePreview.setAttribute("aria-pressed", "false");
    elements.btnFileSource.setAttribute("aria-pressed", "true");
  }

  async function showFilePreview() {
    const editor = fileEditor;
    if (!editor?.loaded || fileSaving || elements.btnFilePreview.hidden) return;
    const generation = filesGeneration;
    const image = /\.(png|jpe?g|webp|gif|svg)$/i.test(editor.path);
    if (image) {
      pageStatus(elements.fileEditorStatus, t("读取图片..."));
      try {
        const downloaded = await downloadArtifact(editor);
        const type = /\.svg$/i.test(editor.path) ? "image/svg+xml" : downloaded.type;
        const blob = type ? new Blob([downloaded], { type }) : downloaded;
        if (disposed || fileEditor !== editor || generation !== filesGeneration || elements.settingsOverlay.hidden) return;
        resetFilePreview();
        filePreviewUrl = URL.createObjectURL(blob);
        const img = document.createElement("img");
        img.src = filePreviewUrl;
        img.alt = editor.path.split("/").pop();
        elements.filePreviewPanel.appendChild(img);
        pageStatus(elements.fileEditorStatus, "");
      } catch (error) {
        if (!disposed && fileEditor === editor && generation === filesGeneration) pageStatus(elements.fileEditorStatus, t("预览失败: {0}", error.message), true);
        return;
      }
    } else {
      resetFilePreview();
      if (/\.html?$/i.test(editor.path)) {
        const frame = document.createElement("iframe");
        frame.setAttribute("sandbox", "");
        frame.setAttribute("referrerpolicy", "no-referrer");
        frame.title = editor.path;
        frame.srcdoc = editor.content || "";
        elements.filePreviewPanel.appendChild(frame);
      } else {
        elements.filePreviewPanel.classList.add("message-body");
        setMarkdown(elements.filePreviewPanel, editor.content || "");
      }
    }
    elements.fileContentInput.hidden = true;
    elements.filePreviewPanel.hidden = false;
    elements.btnFilePreview.setAttribute("aria-pressed", "true");
    elements.btnFileSource.setAttribute("aria-pressed", "false");
  }

  function renderFileEditor() {
    if (!fileEditor) return;
    elements.workspaceFilesList.hidden = true;
    elements.fileEditorPanel.hidden = false;
    elements.workspaceFilePath.textContent = fileEditor.path;
    elements.fileContentInput.value = fileEditor.content || "";
    elements.fileEditorMeta.textContent = fileEditor.loaded ? `${formatBytes(fileEditor.size)}${fileEditor.editable ? " · UTF-8" : t(" · 只读")}` : "";
    syncFileControls();
  }

  async function loadWorkspaceFiles(path = "") {
    if (!canLeaveFileEditor() || fileSaving) return;
    const generation = ++filesGeneration;
    const workspaceId = currentWorkspaceId;
    resetFilePreview();
    fileEditor = null;
    workspacePath = path;
    elements.workspaceFilePath.textContent = path || t("工作区");
    elements.workspaceFilesList.hidden = false;
    elements.fileEditorPanel.hidden = true;
    elements.workspaceFilesList.replaceChildren();
    pageStatus(elements.workspaceFilesStatus, t("加载中..."));
    syncFileControls();
    try {
      const data = await apiJson(scopedUrl(`/mobile/workspace/files?path=${encodeURIComponent(path)}`, workspaceId));
      if (generation !== filesGeneration || settingsPage !== "files") return;
      workspacePath = typeof data.path === "string" ? data.path : path;
      workspaceParent = data.parent ?? null;
      elements.workspaceFilePath.textContent = workspacePath || t("工作区");
      for (const file of Array.isArray(data.files) ? data.files : []) {
        if (!file || typeof file.path !== "string" || typeof file.name !== "string") continue;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "workspace-file-row";
        button.dataset.filePath = file.path;
        button.innerHTML = icon(file.type === "directory" ? "folder" : "file-text");
        const name = document.createElement("span");
        name.textContent = file.name;
        const size = document.createElement("small");
        size.textContent = file.type === "directory" ? "" : formatBytes(file.size);
        button.append(name, size);
        button.addEventListener("click", () => { if (file.type === "directory") void loadWorkspaceFiles(file.path); else void openWorkspaceFile(file.path); });
        elements.workspaceFilesList.appendChild(button);
      }
      pageStatus(elements.workspaceFilesStatus, data.truncated ? t("文件较多，仅显示部分结果") : (elements.workspaceFilesList.children.length ? "" : t("目录为空")));
    } catch (error) {
      if (disposed || generation !== filesGeneration || settingsPage !== "files") return;
      pageStatus(elements.workspaceFilesStatus, t("加载文件失败: {0}", error.message), true);
    } finally { if (generation === filesGeneration && !disposed) syncFileControls(); }
  }

  async function openWorkspaceFile(path, sha256 = null, workspaceId = currentWorkspaceId) {
    if (!canLeaveFileEditor() || fileSaving) return;
    const generation = ++filesGeneration;
    resetFilePreview();
    fileEditor = { path, workspaceId, content: "", loaded: false, editable: false };
    renderFileEditor();
    pageStatus(elements.workspaceFilesStatus, "");
    pageStatus(elements.fileEditorStatus, t("读取中..."));
    try {
      const data = await apiJson(scopedUrl(`/mobile/workspace/file?path=${encodeURIComponent(path)}${sha256 ? `&sha256=${encodeURIComponent(sha256)}` : ""}`, workspaceId));
      if (generation !== filesGeneration || settingsPage !== "files") return false;
      const originalContent = typeof data.content === "string" ? data.content : "";
      const draft = fileDrafts[fileDraftKey(path, workspaceId)];
      const editable = data.editable === true && !data.is_binary && !data.truncated && typeof data.sha256 === "string";
      fileEditor = {
        ...data, path, workspaceId, loaded: true, editable, originalContent,
        content: editable && typeof draft?.content === "string" ? draft.content : originalContent,
        sha256: editable && typeof draft?.sha256 === "string" ? draft.sha256 : data.sha256,
        conflict: editable && !!draft && draft.sha256 !== data.sha256,
      };
      renderFileEditor();
      const message = data.is_binary ? t("二进制文件无法编辑") : data.truncated ? t("文件过大，仅显示部分内容（只读）")
        : fileEditor.conflict ? t("文件已在其他地方更改，本地草稿存在冲突。可复制草稿或放弃草稿后重新读取")
        : !editable ? t("此文件仅可查看") : draft ? t("已恢复本地草稿") : "";
      pageStatus(elements.fileEditorStatus, message, !!fileEditor.conflict);
      return true;
    } catch (error) {
      if (disposed || generation !== filesGeneration || settingsPage !== "files") return;
      pageStatus(elements.fileEditorStatus, t("读取文件失败: {0}", error.message), true);
      return false;
    }
  }

  async function saveWorkspaceFile() {
    const editor = fileEditor;
    if (!editor?.loaded || !editor.editable || !fileDirty() || editor.conflict || fileSaving || restartPending) return;
    const content = editor.content;
    if (new Blob([content]).size > 512 * 1024) { pageStatus(elements.fileEditorStatus, t("文件内容不能超过 512 KB"), true); return; }
    fileSaving = true;
    syncFileControls();
    pageStatus(elements.fileEditorStatus, t("保存中..."));
    try {
      const data = await apiJson("/mobile/workspace/file", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: editor.path, content, expected_sha256: editor.sha256, ...(editor.workspaceId ? { workspace_id: editor.workspaceId } : {}) }) });
      editor.originalContent = content;
      editor.sha256 = data.sha256;
      editor.size = data.size;
      persistFileDraft();
      if (fileEditor === editor) {
        renderFileEditor();
        pageStatus(elements.fileEditorStatus, t("已保存"));
      }
    } catch (error) {
      if (disposed) return;
      if (error.status === 409) editor.conflict = true;
      if (fileEditor === editor) pageStatus(elements.fileEditorStatus, t("保存失败: {0}", error.message), true);
      else notice(t("保存文件失败: {0}", error.message));
      persistFileDraft();
    } finally { fileSaving = false; if (!disposed) syncFileControls(); }
  }

  async function discardFileDraft() {
    if (!fileEditor?.loaded || fileSaving || !window.confirm(t("放弃文件草稿并重新读取文件？"))) return;
    const path = fileEditor.path;
    const next = { ...fileDrafts };
    const key = fileDraftKey(path);
    delete next[key];
    try { window.localStorage.setItem(fileDraftsKey, JSON.stringify(next)); }
    catch { pageStatus(elements.fileEditorStatus, t("无法移除本地草稿，请重试"), true); return; }
    delete fileDrafts[key];
    fileEditor.content = fileEditor.originalContent;
    await openWorkspaceFile(path);
  }

  async function renameSession() {
    const sessionId = currentSessionId;
    const title = elements.sessionTitleInput.value.trim();
    if (!sessionId || isLoadingSession || renameSaving || !title || title.length > 200) return;
    renameSaving = true;
    syncControls();
    pageStatus(elements.sessionRenameStatus, t("保存中..."));
    try {
      const data = await apiJson(`/sessions/${encodeURIComponent(sessionId)}/rename`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) });
      const session = sessions.find((item) => item.id === sessionId);
      if (session) session.title = data.title || title;
      const option = Array.from(elements.sessionSelector.options).find((item) => item.value === sessionId);
      if (option) option.textContent = data.title || title;
      if (sessionId === currentSessionId && settingsPage === "session") {
        elements.sessionTitleInput.value = data.title || title;
        pageStatus(elements.sessionRenameStatus, t("已保存"));
      }
    } catch (error) {
      if (!disposed && sessionId === currentSessionId && settingsPage === "session") pageStatus(elements.sessionRenameStatus, t("保存名称失败: {0}", error.message), true);
    } finally { renameSaving = false; if (!disposed) syncControls(); }
  }

  function refreshNotificationSettings() {
    const available = typeof bridge?.getNotificationSettings === "function" && typeof bridge?.setTaskNotificationsEnabled === "function";
    elements.taskNotificationsToggle.disabled = !available;
    elements.btnNotificationSettings.disabled = typeof bridge?.openNotificationSettings !== "function";
    if (!available) {
      elements.taskNotificationsToggle.checked = false;
      pageStatus(elements.notificationPermissionStatus, t("请在 Android 应用中设置通知"));
      return;
    }
    try {
      const snapshot = JSON.parse(bridge.getNotificationSettings());
      if (typeof snapshot?.enabled !== "boolean" || typeof snapshot.permission_granted !== "boolean") throw new Error(t("通知设置不可用"));
      notificationSettings = snapshot;
      elements.taskNotificationsToggle.checked = snapshot.enabled;
      pageStatus(elements.notificationPermissionStatus, snapshot.permission_granted ? t("系统通知权限已开启") : t("系统通知权限未开启"));
    } catch (error) {
      elements.taskNotificationsToggle.disabled = true;
      pageStatus(elements.notificationPermissionStatus, t("读取通知设置失败: {0}", error.message), true);
    }
  }

  function changeNotificationPreference() {
    const enabled = elements.taskNotificationsToggle.checked;
    try {
      const result = bridge.setTaskNotificationsEnabled(enabled);
      if (typeof result === "string") {
        const response = JSON.parse(result);
        if (response.ok === false) throw new Error(localizeError(response.error) || t("通知设置保存失败"));
      }
      refreshNotificationSettings();
    } catch (error) {
      elements.taskNotificationsToggle.checked = notificationSettings.enabled;
      pageStatus(elements.notificationPermissionStatus, t("保存通知设置失败: {0}", error.message), true);
    }
  }

  function tokenCount(value) { return (Number(value) || 0).toLocaleString("en-US"); }

  function estimatedCost(record) {
    if (typeof record?.cost_usd !== "number" || !Number.isFinite(record.cost_usd)) return t("未定价");
    return `$${record.cost_usd.toFixed(record.cost_usd > 0 && record.cost_usd < 0.01 ? 6 : 2)}`;
  }

  function renderUsage(data) {
    elements.usageSummary.replaceChildren();
    elements.usageModelsList.replaceChildren();
    const totals = data.totals || {};
    const values = [
      [t("模型调用"), tokenCount(totals.model_calls)], [t("总 Token"), tokenCount(totals.total_tokens)],
      [t("输入 Token"), tokenCount(totals.input_tokens)], [t("输出 Token"), tokenCount(totals.output_tokens)],
      [t("缓存输入 Token"), tokenCount(totals.cached_tokens)], [t("预估费用（USD）"), estimatedCost(totals)],
    ];
    for (const [label, value] of values) {
      const term = document.createElement("dt");
      term.textContent = label;
      const detail = document.createElement("dd");
      detail.textContent = value;
      elements.usageSummary.append(term, detail);
    }
    if (Number(totals.unpriced_calls) > 0) {
      const term = document.createElement("dt");
      term.textContent = t("已定价部分 / 未定价调用");
      const detail = document.createElement("dd");
      detail.textContent = t("${0} / {1} 次", (Number(totals.known_cost_usd) || 0).toFixed(6), tokenCount(totals.unpriced_calls));
      elements.usageSummary.append(term, detail);
    }
    if (Number(totals.estimated_calls) > 0) {
      const term = document.createElement("dt");
      term.textContent = t("估算 Token 的调用");
      const detail = document.createElement("dd");
      detail.textContent = tokenCount(totals.estimated_calls);
      elements.usageSummary.append(term, detail);
    }
    for (const record of Array.isArray(data.models) ? data.models : []) {
      if (!record || typeof record.model !== "string") continue;
      const row = document.createElement("div");
      row.className = "usage-model-row";
      const heading = document.createElement("div");
      heading.className = "page-toolbar";
      const title = document.createElement("strong");
      title.textContent = record.model;
      const pricing = actionButton("pencil", t("调整模型费率"), "data-pricing-model", record.model);
      pricing.addEventListener("click", () => openPricing(record.model));
      heading.append(title, pricing);
      const counts = document.createElement("p");
      counts.className = "usage-model-counts";
      counts.textContent = t("{0} 次调用 · {1} Token", tokenCount(record.model_calls), tokenCount(record.total_tokens));
      const cost = document.createElement("p");
      cost.className = "usage-model-cost";
      cost.textContent = t("预估 {0}{1}", estimatedCost(record), record.pricing?.source === "custom" ? t(" · 自定费率") : record.pricing?.source === "reference" ? t(" · 参考费率") : record.pricing?.source === "on_device" ? t(" · 本机推理，无 API 费用") : "");
      row.append(heading, counts, cost);
      elements.usageModelsList.appendChild(row);
    }
  }

  async function loadUsage() {
    const generation = ++usageGeneration;
    const sessionId = currentSessionId;
    const scope = elements.usageScopeSelector.value;
    const days = elements.usageDaysSelector.value;
    if (scope === "session" && !sessionId) {
      pageStatus(elements.usageStatus, t("请先选择会话"));
      return;
    }
    const query = new URLSearchParams();
    if (scope === "session") query.set("session_id", sessionId);
    if (days) query.set("days", days);
    pageStatus(elements.usageStatus, t("加载中..."));
    try {
      const data = await apiJson(scopedUrl(`/mobile/usage${query.size ? `?${query}` : ""}`));
      if (generation !== usageGeneration || settingsPage !== "usage" || (scope === "session" && sessionId !== currentSessionId)) return;
      usageData = data;
      renderUsage(data);
      pageStatus(elements.usageStatus, Number(data.totals?.model_calls) ? "" : t("暂无用量"));
    } catch (error) {
      if (disposed || generation !== usageGeneration || settingsPage !== "usage") return;
      elements.usageSummary.replaceChildren();
      elements.usageModelsList.replaceChildren();
      pageStatus(elements.usageStatus, t("加载用量失败: {0}", error.message), true);
    }
  }

  function fillPricingFields(model) {
    const pricing = usageData?.models?.find((record) => record.model === model)?.pricing;
    elements.pricingInputRate.value = typeof pricing?.input_usd_per_million === "number" ? pricing.input_usd_per_million : "";
    elements.pricingOutputRate.value = typeof pricing?.output_usd_per_million === "number" ? pricing.output_usd_per_million : "";
    elements.pricingCachedRate.value = typeof pricing?.cached_usd_per_million === "number" ? pricing.cached_usd_per_million : "";
    elements.pricingSource.textContent = pricing?.source === "custom" ? t("自定费率") : pricing?.source === "reference" ? t("参考费率") : pricing?.source === "on_device" ? t("本机推理，无 API 费用") : t("未定价");
    pageStatus(elements.pricingStatus, "");
    syncPricingControls();
  }

  function openPricing(model = settings.model) {
    setSettingsPage("pricing");
    elements.pricingModelInput.value = model;
    elements.pricingModelOptions.replaceChildren();
    for (const name of new Set([...(settings.models || []), ...(usageData?.models || []).map((record) => record.model)])) {
      const option = document.createElement("option");
      option.value = name;
      elements.pricingModelOptions.appendChild(option);
    }
    fillPricingFields(model);
  }

  function pricingRates() {
    const values = [elements.pricingInputRate, elements.pricingOutputRate, elements.pricingCachedRate].map((input) => input.value.trim());
    return values.every((value) => value !== "" && Number.isFinite(Number(value)) && Number(value) >= 0) ? values.map(Number) : null;
  }

  function syncPricingControls() {
    const model = elements.pricingModelInput.value.trim();
    elements.btnSavePricing.disabled = pricingSaving || !model || model.length > 200 || !pricingRates();
    for (const input of [elements.pricingModelInput, elements.pricingInputRate, elements.pricingOutputRate, elements.pricingCachedRate]) input.disabled = pricingSaving;
  }

  async function savePricing() {
    const model = elements.pricingModelInput.value.trim();
    const rates = pricingRates();
    if (pricingSaving || !rates || !model || model.length > 200) return;
    pricingSaving = true;
    syncPricingControls();
    pageStatus(elements.pricingStatus, t("保存中..."));
    try {
      const data = await apiJson("/mobile/usage/pricing", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model, input_usd_per_million: rates[0], output_usd_per_million: rates[1], cached_usd_per_million: rates[2] }) });
      if (data.ok === false) throw new Error(localizeError(data.error) || t("费率保存失败"));
      const record = usageData?.models?.find((item) => item.model === model);
      if (record) record.pricing = data.pricing;
      elements.pricingSource.textContent = t("自定费率");
      pageStatus(elements.pricingStatus, t("已保存，历史用量将按此费率估算"));
    } catch (error) {
      if (!disposed) pageStatus(elements.pricingStatus, t("保存费率失败: {0}", error.message), true);
    } finally { pricingSaving = false; if (!disposed) syncPricingControls(); }
  }

  async function applyRuntimeSettings() {
    if (activeTask || isLoadingSession || isUploading || isPreparingSubmission || restartPending || localDeviceTesting) return;
    const localSettings = settingsPage === "localModels";
    if (localSettings && (localContextBusy || typeof bridge?.applyRuntimeSettings !== "function")) return;
    const model = settingsPage === "model" ? elements.modelInput.value.trim() : settings.model;
    if (!model) return;
    const possible = supportedEfforts(model);
    const selectedEffort = settingsPage === "model" ? elements.effortSelector.value : settings.reasoning_effort;
    const effort = possible.includes(selectedEffort) ? selectedEffort : "auto";
    const autonomy = settingsPage === "permission" ? elements.autonomySelector.value : settings.autonomy;
    const contextTokens = localSettings ? readLocalContextDraft() : settings.local_context_tokens;
    const summaryEnabled = settingsPage === "model" ? elements.contextSummaryToggle.checked : settings.context_summary_enabled;
    const explicitSummaryChoice = settingsPage === "model" && contextSummaryDirty;
    const memoryMode = localSettings ? elements.localMemorySelector.value : settings.local_memory_mode;
    const threads = localSettings ? Number(elements.localThreadsInput.value) : settings.local_threads;
    const timeoutSeconds = localSettings ? Number(elements.localTimeoutInput.value) : settings.local_timeout_seconds;
    if (!Number.isInteger(threads) || threads < 0 || threads > 64 || !Number.isInteger(timeoutSeconds) || timeoutSeconds < 0 || timeoutSeconds > 7200) {
      elements.settingsError.textContent = t("线程数须为 0–64 的整数，超时须为 0–7200 秒的整数");
      elements.settingsError.hidden = false; return;
    }
    if (!validLocalContext(contextTokens) || (localSettings && contextTokens > Number(elements.localContextCustomInput.max)) || !["balanced", "extended"].includes(memoryMode)) {
      elements.settingsError.textContent = t("上下文须为自动（0）或 512–{0} 的整数 Token 数", elements.localContextCustomInput.max);
      elements.settingsError.hidden = false; return;
    }
    const changed = model !== settings.model || effort !== settings.reasoning_effort || autonomy !== settings.autonomy
      || contextTokens !== settings.local_context_tokens || memoryMode !== settings.local_memory_mode
      || threads !== settings.local_threads || timeoutSeconds !== settings.local_timeout_seconds
      || summaryEnabled !== settings.context_summary_enabled || explicitSummaryChoice;
    if (!changed) { closeMenu(); return; }
    elements.settingsError.hidden = true;
    if (typeof bridge?.applyRuntimeSettings === "function") {
      saveDraft();
      try {
        const result = JSON.parse(bridge.applyRuntimeSettings(JSON.stringify(localSettings
          ? { local_context_tokens: contextTokens, local_memory_mode: memoryMode,
              ...(threads !== settings.local_threads || timeoutSeconds !== settings.local_timeout_seconds
                ? { local_threads: threads, local_timeout_seconds: timeoutSeconds } : {}) }
          : { model, reasoning_effort: effort, autonomy,
              ...(summaryEnabled !== settings.context_summary_enabled || explicitSummaryChoice ? { context_summary_enabled: summaryEnabled } : {}) })));
        if (!result.ok) throw new Error(localizeError(result.error) || t("无法保存设置"));
        restartPending = true;
        notice(t("设置已保存，正在重新连接..."), "info");
      } catch (error) {
        elements.settingsError.textContent = error.message;
        elements.settingsError.hidden = false;
        return;
      }
    } else if (autonomy !== settings.autonomy || summaryEnabled !== settings.context_summary_enabled) {
      elements.settingsError.textContent = t("执行模式和自动摘要只能在 Android 应用中更改");
      elements.settingsError.hidden = false;
      return;
    }
    settings.model = model;
    settings.reasoning_effort = effort;
    settings.autonomy = autonomy;
    settings.local_context_tokens = contextTokens;
    settings.local_memory_mode = memoryMode;
    settings.local_threads = threads;
    settings.local_timeout_seconds = timeoutSeconds;
    settings.context_summary_enabled = summaryEnabled;
    writeStorage(runtimeChoiceKey, { protocol: settings.protocol, base_url: settings.base_url, model, reasoning_effort: effort });
    renderSettings();
    closeMenu();
  }

  function copyText(text) {
    haptic(16);
    if (typeof bridge?.copyToClipboard === "function") bridge.copyToClipboard(text);
    else if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).catch(() => notice(t("复制失败")));
    else notice(t("剪贴板不可用"));
  }

  function shareText(title, content) {
    haptic(16);
    if (typeof bridge?.shareText === "function") bridge.shareText(title, content);
    else if (navigator.share) navigator.share({ title, text: content }).catch(() => {});
    else copyText(content);
  }

  function validArtifactPath(path) {
    if (typeof path !== "string" || !path || path.length > 2048 || /[\\\\:\x00-\x1f\x7f]/.test(path)) return false;
    const reserved = new Set([".git", ".agent", ".agent-workspace", ".agent_workspace", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "uploads"]);
    return path.split("/").every(part => part && part !== "." && part !== ".." && !reserved.has(part.toLowerCase()));
  }

  function taskArtifacts(value) {
    const seen = new Set();
    return (Array.isArray(value) ? value : []).filter(file => {
      if (!file || !validArtifactPath(file.path) || seen.has(file.path)) return false;
      if (file.sha256 != null && (typeof file.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(file.sha256))) return false;
      if (!Number.isSafeInteger(file.size) || file.size < 0) return false;
      seen.add(file.path);
      return true;
    });
  }

  async function downloadArtifact(file) {
    const url = scopedUrl(`/mobile/workspace/download?path=${encodeURIComponent(file.path)}${file.sha256 ? `&sha256=${encodeURIComponent(file.sha256)}` : ""}`, file.workspaceId || currentWorkspaceId);
    const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) {
      let message = t("无法读取文件 ({0})", response.status);
      try { message = (await response.json()).error || message; } catch { /* Download failures may be plain HTTP errors. */ }
      throw new Error(message);
    }
    const blob = await response.blob();
    if (disposed) throw new Error("Page closed");
    if (file.sha256 && window.crypto?.subtle && typeof blob.arrayBuffer === "function") {
      const digest = new Uint8Array(await window.crypto.subtle.digest("SHA-256", await blob.arrayBuffer()));
      const actual = [...digest].map(value => value.toString(16).padStart(2, "0")).join("");
      if (actual !== file.sha256) throw new Error(t("文件内容已变化，请重新打开任务中的最新文件"));
    }
    return blob;
  }

  function saveArtifactBlob(blob, file) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = file.path.split("/").pop();
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  async function artifactAction(file, action, button, status, nativeOnly = false) {
    if (button.disabled || disposed) return;
    haptic(16);
    button.disabled = true;
    pageStatus(status, action === "open" ? t("读取中...") : t("准备文件..."));
    try {
      if (!nativeOnly && action === "open" && (/^(text\/|application\/(json|xml))/.test(file.mime_type || "") || /\.(md|markdown|html?|png|jpe?g|webp|gif|svg)$/i.test(file.path))) {
        const parent = file.path.split("/").slice(0, -1).join("/");
        if (!canLeaveFileEditor() || fileSaving) { pageStatus(status, t("请先处理未保存的文件草稿"), true); return; }
        if (file.workspaceId && file.workspaceId !== currentWorkspaceId && !await switchWorkspace(file.workspaceId)) {
          pageStatus(status, t("暂时无法切换到此文件的工作区"), true);
          return;
        }
        workspacePath = parent;
        fileEditor = null;
        openMenu();
        if (!setSettingsPage("files")) return;
        const opened = await openWorkspaceFile(file.path, file.sha256, file.workspaceId || currentWorkspaceId);
        if (!opened || disposed) return;
        if (!fileEditor?.is_binary || /\.(png|jpe?g|webp|gif|svg)$/i.test(file.path)) {
          if (/\.(md|markdown|html?|png|jpe?g|webp|gif|svg)$/i.test(file.path)) await showFilePreview();
          pageStatus(status, "");
          return;
        }
        pageStatus(elements.fileEditorStatus, t("正在使用系统应用打开此文件..."));
      }
      if (typeof bridge?.workspaceFileAction === "function") {
        const requestId = window.crypto?.randomUUID?.() || `file-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        artifactActions.set(requestId, { button, status, action });
        let outcome;
        try {
          outcome = JSON.parse(bridge.workspaceFileAction(JSON.stringify({ request_id: requestId, action,
            path: file.path, sha256: file.sha256 || null, mime_type: file.mime_type || "application/octet-stream",
            ...((file.workspaceId || currentWorkspaceId) ? { workspace_id: file.workspaceId || currentWorkspaceId } : {}) })));
          if (!outcome.ok) throw new Error(localizeError(outcome.error) || t("无法处理文件"));
        } catch (error) { artifactActions.delete(requestId); throw error; }
        return;
      }
      const blob = await downloadArtifact(file);
      const sharedFile = new File([blob], file.path.split("/").pop(), { type: blob.type || file.mime_type || "application/octet-stream" });
      if (action === "share" && navigator.share && navigator.canShare?.({ files: [sharedFile] })) {
        await navigator.share({ files: [sharedFile], title: file.name || sharedFile.name });
        pageStatus(status, "");
      } else {
        saveArtifactBlob(blob, file);
        pageStatus(status, action === "share" ? t("已下载文件，可从下载列表分享") : t("已提交下载"));
      }
    } catch (error) {
      if (!disposed) pageStatus(status, error.name === "AbortError" ? "" : error.message, error.name !== "AbortError");
    } finally {
      if (![...artifactActions.values()].some(pending => pending.button === button)) button.disabled = false;
    }
  }

  window.addEventListener("agent-workspace-file-action", event => {
    const result = event.detail;
    if (disposed || !result || typeof result.request_id !== "string") return;
    const pending = artifactActions.get(result.request_id);
    if (!pending) return;
    artifactActions.delete(result.request_id);
    pending.button.disabled = false;
    pageStatus(pending.status, result.cancelled ? "" : result.ok ? (pending.action === "save" ? t("已保存") : "") : localizeError(result.error) || t("文件操作失败"), !result.ok && !result.cancelled);
  });

  function renderTaskArtifacts(container, payload, taskId = "") {
    const files = taskArtifacts(payload.artifacts);
    const existing = [...container.querySelectorAll(".task-artifacts")].find(panel => panel.dataset.artifactTask === taskId);
    if (!files.length && !payload.artifacts_error && !payload.artifacts_truncated) { existing?.remove(); return; }
    const panel = existing || document.createElement("section");
    panel.className = "task-artifacts";
    panel.dataset.artifactTask = taskId;
    panel.setAttribute("aria-label", t("生成文件"));
    panel.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = t("生成文件{0}", files.length ? ` · ${files.length}` : "");
    panel.appendChild(heading);
    const workspaceId = payload.workspaceId || workspaceOfSession(payload.session_id || currentSessionId) || currentWorkspaceId;
    // Long lists collapse after the first few files so a big task does not bury the conversation.
    const collapsedAfter = files.length > 4 ? 3 : files.length;
    const expanded = panel.dataset.expanded === "true";
    files.forEach((artifact, index) => {
      const file = { ...artifact, workspaceId };
      const row = document.createElement("div");
      row.className = "artifact-row";
      row.dataset.artifactPath = file.path;
      if (index >= collapsedAfter) row.classList.add("artifact-extra");
      const open = document.createElement("button");
      open.type = "button";
      open.className = "artifact-link";
      open.dataset.fileAction = "open";
      open.title = t("打开 {0}", file.path);
      open.innerHTML = icon("file-text");
      const label = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = typeof file.name === "string" && file.name ? file.name : file.path.split("/").pop();
      const metadata = document.createElement("small");
      metadata.textContent = `${file.path} · ${formatBytes(file.size)}${file.state === "modified" ? t(" · 已修改") : ""}`;
      label.append(name, metadata);
      open.appendChild(label);
      const status = document.createElement("p");
      status.className = "page-status artifact-status";
      status.setAttribute("role", "status");
      open.addEventListener("click", () => artifactAction(file, "open", open, status));
      row.appendChild(open);
      for (const [action, glyph, title] of [["share", "share-2", t("分享文件")], ["save", "download", t("另存文件")]]) {
        const button = actionButton(glyph, title, "data-file-action", action);
        button.addEventListener("click", () => artifactAction(file, action, button, status));
        row.appendChild(button);
      }
      row.appendChild(status);
      panel.appendChild(row);
    });
    panel.classList.toggle("collapsed", collapsedAfter < files.length && !expanded);
    if (collapsedAfter < files.length) {
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "text-action artifact-toggle";
      const label = () => panel.classList.contains("collapsed") ? t("显示全部 {0} 个文件", files.length) : t("收起");
      toggle.textContent = label();
      toggle.setAttribute("aria-expanded", String(!panel.classList.contains("collapsed")));
      toggle.addEventListener("click", () => {
        const collapse = !panel.classList.contains("collapsed");
        panel.classList.toggle("collapsed", collapse);
        panel.dataset.expanded = String(!collapse);
        toggle.textContent = label();
        toggle.setAttribute("aria-expanded", String(!collapse));
      });
      panel.appendChild(toggle);
    }
    if (payload.artifacts_error || payload.artifacts_truncated) {
      const warning = document.createElement("p");
      warning.className = "page-status error";
      warning.textContent = payload.artifacts_error || t("文件较多，部分文件可在工作区查看");
      panel.appendChild(warning);
    }
    if (!existing) container.insertBefore(panel, container.querySelector(".card-action-bar"));
  }

  function decorateMarkdown(body) {
    body.querySelectorAll("pre > code").forEach((code) => {
      const pre = code.parentElement;
      const wrapper = document.createElement("div");
      wrapper.className = "code-wrap";
      const toolbar = document.createElement("div");
      toolbar.className = "code-toolbar";
      const language = document.createElement("span");
      language.textContent = [...code.classList].find((name) => name.startsWith("language-"))?.slice(9) || t("代码");
      const copy = document.createElement("button");
      copy.type = "button";
      copy.className = "icon-button btn-code-copy";
      copy.title = t("复制代码");
      copy.setAttribute("aria-label", t("复制代码"));
      copy.innerHTML = icon("copy");
      copy.addEventListener("click", () => copyText(code.textContent));
      toolbar.append(language, copy);
      pre.replaceWith(wrapper);
      wrapper.append(toolbar, pre);
    });
    body.querySelectorAll("table").forEach((table) => {
      const scroll = document.createElement("div");
      scroll.className = "table-scroll";
      table.replaceWith(scroll);
      scroll.appendChild(table);
    });
    body.querySelectorAll("a[href]").forEach((link) => {
      try {
        const url = new URL(link.href, window.location.href);
        if (!["https:", "http:"].includes(url.protocol)) { link.removeAttribute("href"); return; }
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.addEventListener("click", (event) => {
          if (typeof bridge?.openExternal !== "function") return;
          event.preventDefault();
          bridge.openExternal(url.href);
        });
      } catch { link.removeAttribute("href"); }
    });
  }

  function setMarkdown(body, value) {
    body.innerHTML = window.MobileUi?.renderMarkdown(value) || "";
    decorateMarkdown(body);
  }

  function appendMessageCard(role, label, text, reasoning = "") {
    const card = document.createElement("article");
    card.className = `message-card ${role}`;
    card.dataset.messageText = text || "";
    const badge = document.createElement("div");
    badge.className = "role-badge";
    if (role === "assistant") badge.innerHTML = icon("bot");
    badge.append(label);
    card.appendChild(badge);
    if (reasoning) appendReasoning(card, reasoning);
    const body = document.createElement("div");
    body.className = "message-body";
    setMarkdown(body, text);
    card.appendChild(body);
    if (role === "assistant") {
      const actions = document.createElement("div");
      actions.className = "card-action-bar";
      for (const [name, iconName, title, action] of [
        ["btn-copy", "copy", t("复制回复"), () => copyText(card.dataset.messageText)],
        ["btn-share", "share-2", t("分享回复"), () => shareText(t("Agent 回复"), card.dataset.messageText)],
      ]) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `icon-button btn-card-action ${name}`;
        button.title = title;
        button.setAttribute("aria-label", title);
        button.innerHTML = icon(iconName);
        button.addEventListener("click", action);
        actions.appendChild(button);
      }
      card.appendChild(actions);
    }
    elements.timelineList.appendChild(card);
    return card;
  }

  function appendReasoning(card, text) {
    let details = card.querySelector(".reasoning-box");
    if (!details) {
      details = document.createElement("details");
      details.className = "reasoning-box";
      details.append(document.createElement("summary"), document.createElement("pre"));
      card.insertBefore(details, card.querySelector(".message-body"));
    }
    details.querySelector("summary").textContent = t("思考过程 · {0} 字", text.length);
    details.querySelector("pre").textContent = text;
  }

  function toolCardId(data) { return `tool-${data.tool_call_id || data.attempt_id || data.name || data.tool_name || "unknown"}`; }

  const toolStates = {
    running: t("执行中"), done: t("已完成"), failed: t("失败"), cancelled: t("已取消"), rejected: t("已拒绝"), unknown: t("结果未知"), stale: t("未完成"),
  };
  const toolOutcomeEvents = { "tool.settled": "done", "tool.failed": "failed", "tool.cancelled": "cancelled", "tool.rejected": "rejected", "tool.unknown": "unknown" };

  function setToolState(card, state) {
    card.dataset.state = state;
    card.querySelector(".tool-state").textContent = toolStates[state] || toolStates.done;
  }

  function renderTool(data, outcome = null) {
    const id = toolCardId(data);
    let card = [...elements.timelineList.querySelectorAll(".message-card.tool")].find((item) => item.dataset.toolId === id);
    if (!card) {
      card = document.createElement("details");
      card.className = "message-card tool";
      card.dataset.toolId = id;
      const title = document.createElement("summary");
      const name = document.createElement("span");
      name.className = "tool-name";
      name.textContent = data.name || data.tool_name || t("工具");
      const state = document.createElement("span");
      state.className = "tool-state";
      title.append(name, state);
      card.appendChild(title);
      elements.timelineList.appendChild(card);
    }
    if (!outcome) {
      // A replayed start must not undo a result that already arrived.
      if (!card.dataset.state || card.dataset.state === "stale") setToolState(card, "running");
      return;
    }
    setToolState(card, outcome);
    const detail = outcome === "done" ? data.result : (data.error ?? data.reason ?? data.result);
    if (detail === undefined || detail === null || detail === "") return;
    let result = card.querySelector("pre");
    if (!result) { result = document.createElement("pre"); card.appendChild(result); }
    result.textContent = typeof detail === "string" ? detail : JSON.stringify(detail, null, 2);
  }

  function settleUnfinishedTools() {
    elements.timelineList.querySelectorAll('.message-card.tool[data-state="running"]').forEach((card) => setToolState(card, "stale"));
  }

  function renderHistoryEvent(event) {
    const payload = event.data || event.payload || {};
    if (event.type === "mobile.task.running") {
      historyAssistantCard = null;
    } else if (event.type === "message.user" || (event.type === "message.created" && payload.role === "user")) {
      historyAssistantCard = null;
      const card = appendMessageCard("user", t("您"), payload.text || payload.content || "");
      if (event.id) eventCards.set(event.id, card);
    } else if (event.type === "message.assistant" || (event.type === "message.created" && payload.role === "assistant")) {
      const card = appendMessageCard("assistant", "Agent", payload.text || payload.content || "", payload.reasoning);
      historyAssistantCard = card;
      if (event.id) eventCards.set(event.id, card);
    } else if (event.type === "tool.started") renderTool(payload);
    else if (toolOutcomeEvents[event.type]) renderTool(payload, toolOutcomeEvents[event.type]);
    else if (event.type === "task.completed" || (event.type === "mobile.event" && payload.event_type === "task.completed")) {
      const completion = event.type === "mobile.event" ? payload.payload || {} : payload;
      if (!taskArtifacts(completion.artifacts).length && !completion.artifacts_error && !completion.artifacts_truncated) return;
      const card = historyAssistantCard || appendMessageCard("assistant", "Agent", completion.text || t("执行完成"));
      renderTaskArtifacts(card, completion, payload.task_id || event.task_id || "");
      historyAssistantCard = null;
    }
  }

  function scrollToBottom(force = false) {
    if (disposed) return;
    if (!force && !stickToBottom) return;
    elements.timelineContainer.scrollTop = elements.timelineContainer.scrollHeight;
    stickToBottom = true;
    elements.btnJumpLatest.hidden = true;
  }

  function emptyState() {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    const glyph = document.createElement("span");
    glyph.className = "empty-state-icon";
    glyph.innerHTML = icon("sparkles");
    const title = document.createElement("strong");
    title.textContent = t("开始一个新任务");
    const hint = document.createElement("span");
    const workspace = workspaces.find(item => item.id === currentWorkspaceId);
    hint.textContent = workspace?.name ? t("描述你想完成的事情，Agent 会在「{0}」中执行。", workspace.name) : t("描述你想完成的事情，Agent 会在当前工作区中执行。");
    empty.append(glyph, title, hint);
    return empty;
  }

  function showTaskError(error) {
    const message = document.createElement("div");
    message.className = "task-error";
    message.setAttribute("role", "alert");
    message.textContent = error;
    elements.timelineList.appendChild(message);
  }

  async function loadTimeline(sessionId) {
    if (!sessionId) return;
    historyReady = false;
    elements.timelineList.replaceChildren();
    eventCards.clear();
    historyAssistantCard = null;
    syncControls();
    try {
      const data = await apiJson(`/sessions/${encodeURIComponent(sessionId)}/events`);
      if (sessionId !== currentSessionId) return;
      unavailableSessions.delete(sessionId);
      historyEvents = Array.isArray(data.events) ? data.events : [];
      reconcilePendingRequest(sessionId);
      for (const event of historyEvents) renderHistoryEvent(event);
      // History has no live stream; a started tool without an outcome did not finish.
      settleUnfinishedTools();
      if (!historyEvents.length) elements.timelineList.appendChild(emptyState());
      historyReady = true;
      setConnection(true);
      scrollToBottom(true);
    } catch (error) {
      if (disposed) return;
      if (sessionId !== currentSessionId) return;
      if (error.status === 404) unavailableSessions.add(sessionId);
      historyEvents = [];
      setConnection(false);
      const state = document.createElement("div");
      state.className = "history-error";
      const message = document.createElement("p");
      message.textContent = t("加载会话失败: {0}", error.message);
      const retry = document.createElement("button");
      retry.id = "btnRetryHistory";
      retry.className = "button-secondary";
      retry.type = "button";
      retry.textContent = t("重试");
      retry.addEventListener("click", async () => {
        isLoadingSession = true;
        try { await loadTimeline(sessionId); if (historyReady) await recoverSessionTask(sessionId); }
        finally { isLoadingSession = false; syncControls(); }
      });
      state.append(message, retry);
      elements.timelineList.replaceChildren(state);
    } finally { syncControls(); }
  }

  async function recoverSessionTask(sessionId) {
    if (activeTask) return;
    const adoptionGeneration = taskAdoptionGeneration;
    try {
      const data = await apiJson(`/mobile/tasks?session_id=${encodeURIComponent(sessionId)}`);
      if (sessionId !== currentSessionId || activeTask || adoptionGeneration !== taskAdoptionGeneration) return;
      const tasks = Array.isArray(data.tasks) ? data.tasks : [];
      const ordered = [...tasks].sort((first, second) => String(second.created_at || second.updated_at || "").localeCompare(String(first.created_at || first.updated_at || "")));
      const live = ordered.find((task) => runningStates.has(task.state));
      interruptedTask = null;
      retryTask = null;
      updateTaskStatus("");
      if (live) {
        activeTask = makeTask(live);
        backgroundTasks.set(sessionId, activeTask);
        updateTaskStatus(t("正在恢复任务..."));
        syncControls();
        void watchTask(activeTask);
        return;
      }
      const latest = ordered[0];
      const historySequence = historyEvents.reduce((sequence, event) => Math.max(sequence, Number(event.sequence) || 0), 0);
      if (latest?.state === "succeeded" && latest.last_sequence > historySequence) {
        activeTask = makeTask(latest);
        backgroundTasks.set(sessionId, activeTask);
        updateTaskStatus(t("正在恢复任务..."));
        syncControls();
        void watchTask(activeTask);
      } else if (latest?.state === "interrupted" && latest.resume_available) {
        interruptedTask = latest;
        updateTaskStatus(t("任务已中断"), { resume: true });
      } else if (latest?.state === "failed") {
        const canRetry = !!submissions[latest.task_id]?.prompt;
        if (canRetry) retryTask = makeTask(latest);
        // Say why the last task failed instead of a bare "failed".
        const reason = typeof latest.reason === "string" ? latest.reason.trim().slice(0, 300) : "";
        updateTaskStatus(reason ? t("任务失败：{0}", reason) : t("任务失败"), { retry: canRetry, idle: true });
      }
    } catch (error) {
      if (disposed || adoptionGeneration !== taskAdoptionGeneration) return;
      if (sessionId === currentSessionId) {
        historyReady = false;
        notice(t("恢复任务状态失败: {0}", error.message));
        setConnection(false);
      }
    }
  }

  async function refreshCurrentSessionTask() {
    if (activeTask || isLoadingSession || !historyReady || !currentSessionId) return;
    isLoadingSession = true;
    syncControls();
    try { await recoverSessionTask(currentSessionId); }
    finally { isLoadingSession = false; syncControls(); }
  }

  async function loadSessions(preferredId = selectedSessionId) {
    isLoadingSession = true;
    historyReady = false;
    syncControls();
    try {
      const data = await apiJson("/sessions");
      sessions = Array.isArray(data.sessions) ? data.sessions : [];
      const preferred = sessions.find(item => item.id === preferredId);
      if (preferred?.workspace_id) currentWorkspaceId = preferred.workspace_id;
      const inWorkspace = sessions.filter(session => !currentWorkspaceId || workspaceOfSession(session.id) === currentWorkspaceId);
      // An explicitly requested conversation opens even when archived; otherwise prefer unarchived ones.
      let visible = inWorkspace.filter(session => session.archived !== true);
      if (!visible.length && !inWorkspace.some(session => session.id === preferredId)) {
        const created = await apiJson("/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: t("新会话"), ...(currentWorkspaceId ? { workspace_id: currentWorkspaceId } : {}) }) });
        sessions.push(created);
        visible = [created];
      }
      currentSessionId = inWorkspace.some((session) => session.id === preferredId) ? preferredId : visible[0].id;
      currentWorkspaceId = workspaceOfSession(currentSessionId) || currentWorkspaceId;
      renderWorkspaceNavigation();
      renderSessionNavigation();
      selectedSessionId = currentSessionId;
      writeStorage(sessionKey, currentSessionId);
      restoreDraft(currentSessionId);
      await loadTimeline(currentSessionId);
      if (historyReady) await recoverSessionTask(currentSessionId);
      return historyReady;
    } catch (error) {
      if (disposed) return false;
      historyReady = false;
      setConnection(false);
      notice(t("加载会话失败: {0}", error.message));
      return false;
    } finally {
      isLoadingSession = false;
      syncControls();
      refreshShareInbox();
    }
  }

  async function switchSession(sessionId, title = "") {
    if ((activeTask && !activeTask.id) || isLoadingSession || isUploading || isPreparingSubmission || restartPending || !sessionId) return false;
    if (!canLeaveFileEditor()) return false;
    const previousSessionId = currentSessionId;
    const previousWorkspaceId = currentWorkspaceId;
    saveDraft();
    if (!sessions.some((session) => session.id === sessionId)) {
      isLoadingSession = true;
      syncControls();
      try {
        const listing = await apiJson("/sessions");
        const target = Array.isArray(listing.sessions) && listing.sessions.find(item => item.id === sessionId);
        if (target) {
          if (target.workspace_id && !workspaces.some(item => item.id === target.workspace_id)) await loadWorkspaces();
          sessions.push(target);
        } else if (workspaces.length) {
          unavailableSessions.add(sessionId);
          notice(t("目标会话不存在或已删除"));
          return false;
        } else sessions.push({ id: sessionId, title });
      } catch (error) {
        notice(t("加载会话失败: {0}", error.message));
        return false;
      } finally { isLoadingSession = false; syncControls(); }
    }
    detachSessionTask();
    currentSessionId = sessionId;
    const targetWorkspace = workspaceOfSession(sessionId);
    if (targetWorkspace && targetWorkspace !== currentWorkspaceId) {
      currentWorkspaceId = targetWorkspace;
      writeStorage(workspaceKey, targetWorkspace);
      renderWorkspaceNavigation();
    }
    renderSessionNavigation();
    selectedSessionId = sessionId;
    writeStorage(sessionKey, sessionId);
    resetFilePreview();
    fileEditor = null;
    workspacePath = "";
    workspaceParent = null;
    filesGeneration += 1;
    attachments = [];
    interruptedTask = null;
    retryTask = null;
    renderAttachments();
    updateTaskStatus("");
    isLoadingSession = true;
    restoreDraft(sessionId);
    syncControls();
    try {
      await loadTimeline(sessionId);
      if (historyReady) await recoverSessionTask(sessionId);
      if (unavailableSessions.has(sessionId) && previousSessionId && previousSessionId !== sessionId) {
        sessions = sessions.filter((session) => session.id !== sessionId);
        currentSessionId = previousSessionId;
        currentWorkspaceId = previousWorkspaceId;
        selectedSessionId = previousSessionId;
        writeStorage(workspaceKey, previousWorkspaceId);
        writeStorage(sessionKey, previousSessionId);
        renderWorkspaceNavigation();
        renderSessionNavigation();
        restoreDraft(previousSessionId);
        await loadTimeline(previousSessionId);
        if (historyReady) await recoverSessionTask(previousSessionId);
        notice(t("目标会话不存在或已删除"));
      }
    } finally {
      isLoadingSession = false;
      syncControls();
      refreshShareInbox();
    }
    return historyReady && currentSessionId === sessionId;
  }

  function makeTask(snapshot, prompt = "") {
    const saved = submissions[snapshot.task_id];
    return {
      id: snapshot.task_id, sessionId: snapshot.session_id || currentSessionId,
      workspaceId: workspaceOfSession(snapshot.session_id || currentSessionId) || currentWorkspaceId,
      prompt: saved?.prompt || prompt, inputText: saved?.inputText || prompt,
      attachments: saved?.attachments || [], model: saved?.model || snapshot.model || settings.model,
      effort: saved?.reasoning_effort || snapshot.reasoning_effort || settings.reasoning_effort,
      sequence: 0, state: snapshot.state || "queued",
      text: "", reasoning: "", card: null, done: false, error: null,
      artifacts: taskArtifacts(snapshot.artifacts), artifacts_truncated: snapshot.artifacts_truncated === true,
      artifacts_error: snapshot.artifacts_error || null,
      resolvedApprovals: new Set(), stopping: false, watching: false, messageFinal: false,
    };
  }

  function adoptTask(snapshot) {
    if (disposed || !snapshot || typeof snapshot.task_id !== "string" || !snapshot.task_id.trim()
      || !currentSessionId || !historyReady || (snapshot.session_id && snapshot.session_id !== currentSessionId)) return false;
    if (activeTask) {
      if (activeTask.id !== snapshot.task_id) return false;
      void watchTask(activeTask);
      return true;
    }
    activeTask = makeTask(snapshot);
    backgroundTasks.set(activeTask.sessionId, activeTask);
    taskAdoptionGeneration += 1;
    interruptedTask = null;
    retryTask = null;
    showApproval(null);
    elements.timelineList.querySelector(".empty-state")?.remove();
    updateTaskStatus(snapshot.state === "waiting_approval" ? t("等待审批") : t("任务执行中"));
    updateAssistantCard(activeTask);
    syncControls();
    scrollToBottom();
    void watchTask(activeTask);
    return true;
  }

  function updateAssistantCard(task) {
    if (task.sessionId !== currentSessionId || activeTask !== task) return;
    if (!task.card) task.card = appendMessageCard("assistant", "Agent", t("正在执行..."));
    const body = task.card.querySelector(".message-body");
    const text = task.text || (task.done ? t("执行完成") : t("正在执行..."));
    setMarkdown(body, text);
    task.card.dataset.messageText = task.text;
    task.card.classList.toggle("pending", !task.done && !task.text);
    task.card.classList.toggle("streaming", !task.done && !!task.text && !task.messageFinal);
    if (task.reasoning) appendReasoning(task.card, task.reasoning);
    if (task.state === "succeeded") renderTaskArtifacts(task.card, task, task.id);
  }

  function showApproval(approval) {
    if (approval && activeTask?.resolvedApprovals.has(approval.request_id)) approval = null;
    const changed = approval?.request_id !== pendingApproval?.request_id;
    pendingApproval = approval;
    elements.approvalShelf.hidden = !approval;
    elements.approvalShelf.classList.toggle("hidden", !approval);
    elements.btnApproveAction.disabled = !approval || isResolvingApproval;
    elements.btnRejectAction.disabled = !approval || isResolvingApproval;
    if (approval) {
      elements.approvalTitle.textContent = approval.kind === "egress" ? t("网络访问审批") : t("工具审批");
      elements.approvalDetail.textContent = JSON.stringify(approval.details || {}, null, 2);
      if (changed) elements.approvalScopeSelector.value = "once";
    }
  }

  async function resolveApproval(allowed) {
    const approval = pendingApproval;
    if (!approval || isResolvingApproval) return;
    isResolvingApproval = true;
    const scope = allowed ? elements.approvalScopeSelector.value : "once";
    showApproval(approval);
    try {
      await apiJson(`/mobile/approvals/${encodeURIComponent(approval.request_id)}/resolve`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allowed, scope }),
      });
      activeTask?.resolvedApprovals.add(approval.request_id);
      showApproval(null);
      haptic(32);
    } catch (error) {
      if (disposed) return;
      elements.approvalTitle.textContent = t("审批失败: {0}", error.message);
    } finally {
      isResolvingApproval = false;
      if (!disposed) {
        elements.btnApproveAction.disabled = !pendingApproval;
        elements.btnRejectAction.disabled = !pendingApproval;
      }
    }
  }

  function renderTaskEvent(task, event) {
    if (event.task_id !== task.id || event.sequence <= task.sequence) return;
    task.sequence = event.sequence;
    const envelope = event.payload || {};
    const payload = envelope.data && typeof envelope.data === "object" ? envelope.data : envelope;
    if (event.event_type === "assistant.delta") {
      if (task.messageFinal) { task.card = null; task.text = ""; task.reasoning = ""; task.messageFinal = false; }
      if (payload.kind === "reasoning") task.reasoning += payload.text || "";
      else task.text += payload.text || "";
      task.dirty = true;
    } else if (event.event_type === "task.completed") {
      if (typeof payload.text === "string") task.text = payload.text;
      task.artifacts = taskArtifacts(payload.artifacts);
      task.artifacts_truncated = payload.artifacts_truncated === true;
      task.artifacts_error = payload.artifacts_error || null;
      task.done = true;
      task.state = "succeeded";
      updateAssistantCard(task);
      task.dirty = false;
    } else if (["task.failed", "mobile.task.failed"].includes(event.event_type)) {
      task.error = payload.error || payload.reason || t("任务失败");
      task.done = true;
      task.state = "failed";
    } else if (event.event_type === "approval.requested") {
      showApproval(payload);
    } else if (event.event_type === "runtime.message.created" && payload.role === "assistant") {
      const existing = envelope.source_event_id && eventCards.get(envelope.source_event_id);
      if (existing) {
        if (task.card && task.card !== existing) task.card.remove();
        task.card = existing;
      }
      if (typeof payload.content === "string") task.text = payload.content;
      if (typeof payload.reasoning === "string") task.reasoning = payload.reasoning;
      updateAssistantCard(task);
      task.dirty = false;
      task.messageFinal = true;
      // An intermediate step can carry only reasoning and tool calls. It is final, so it must not keep
      // the "running" placeholder: show just its reasoning, or drop it when there is nothing to show.
      if (!task.text.trim() && task.card) {
        if (task.reasoning) {
          task.card.classList.remove("pending", "streaming");
          task.card.classList.add("reasoning-only");
          const body = task.card.querySelector(".message-body");
          if (body) { body.textContent = ""; body.hidden = true; }
          const actions = task.card.querySelector(".card-action-bar");
          if (actions) actions.hidden = true;
        } else {
          task.card.remove();
          task.card = null;
        }
      }
      if (envelope.source_event_id) eventCards.set(envelope.source_event_id, task.card);
    } else if (event.event_type === "runtime.message.created" && payload.role === "user") {
      if (!task.prompt && typeof payload.content === "string") task.prompt = payload.content;
    } else if (event.event_type === "runtime.tool.started") {
      if (task.dirty) { updateAssistantCard(task); task.dirty = false; }
      renderTool(payload);
    } else if (typeof event.event_type === "string" && event.event_type.startsWith("runtime.") && toolOutcomeEvents[event.event_type.slice(8)]) {
      renderTool(payload, toolOutcomeEvents[event.event_type.slice(8)]);
    }
  }

  function showReconnect(error) {
    notice(t("连接中断: {0}", error.message));
    updateTaskStatus(t("任务状态待确认"), { reconnect: true });
    setConnection(false);
  }

  async function watchTask(task) {
    if (!task || task.watching || disposed) return;
    task.watching = true;
    let failures = 0;
    let completedPolls = 0;
    backgroundTasks.set(task.sessionId, task);
    while (!disposed && backgroundTasks.get(task.sessionId) === task && !task.done) {
      try {
        if (activeTask !== task) {
          const background = await apiJson(`/mobile/tasks/${encodeURIComponent(task.id)}`);
          if (backgroundTasks.get(task.sessionId) !== task) break;
          task.state = background.task?.state || task.state;
          if (terminalStates.has(task.state) || task.state === "interrupted") {
            task.done = true;
            backgroundTasks.delete(task.sessionId);
            syncControls();
            if (settingsPage === "tasks") void loadTaskCenter();
            break;
          }
          await new Promise(resolve => setTimeout(resolve, 1500));
          continue;
        }
        const updates = await apiJson(`/mobile/tasks/${encodeURIComponent(task.id)}/events?after=${task.sequence}`);
        if (activeTask !== task) continue;
        for (const event of updates.events || []) renderTaskEvent(task, event);
        if (task.dirty) { updateAssistantCard(task); task.dirty = false; }
        scrollToBottom();
        setConnection(true);
        if (task.done) break;
        const snapshot = await apiJson(`/mobile/tasks/${encodeURIComponent(task.id)}`);
        if (activeTask !== task) continue;
        const approval = (snapshot.approvals || []).find((item) => !task.resolvedApprovals.has(item.request_id));
        showApproval(approval || null);
        const state = snapshot.task?.state;
        const previousState = task.state;
        task.state = state || task.state;
        if (task.state !== previousState) syncControls(); // steering opens once the turn is running
        if (state === "succeeded") {
          task.artifacts = taskArtifacts(snapshot.task.artifacts);
          task.artifacts_truncated = snapshot.task.artifacts_truncated === true;
          task.artifacts_error = snapshot.task.artifacts_error || null;
        }
        updateTaskStatus(task.stopping ? t("正在停止任务...") : (state === "waiting_approval" ? t("等待审批") : (state === "queued" ? t("任务排队中") : t("任务执行中"))));
        if (["failed", "cancelled", "interrupted"].includes(state)) {
          task.error = state === "failed" ? (snapshot.task.reason || t("任务失败")) : null;
          task.interrupted = state === "interrupted" && snapshot.task.resume_available;
          task.done = true;
        } else if (state === "succeeded" && ++completedPolls >= 3) {
          // The terminal state can be visible before the task completion event.
          task.done = true;
          updateAssistantCard(task);
        }
        failures = 0;
      } catch (error) {
        if (disposed || backgroundTasks.get(task.sessionId) !== task) { task.watching = false; return; }
        if (activeTask !== task) { await new Promise(resolve => setTimeout(resolve, 2000)); continue; }
        setConnection(false);
        failures += 1;
        if (error.network || error.status === 401) {
          // The engine is gone or was restarted with a new token: let the app revive it and
          // reload this page. Without the app bridge, fall back to the manual button.
          if (failures >= 3 && !requestEngineReconnect()) { task.watching = false; showReconnect(error); return; }
          if (failures >= 3) updateTaskStatus(t("正在恢复与引擎的连接..."));
        } else if (failures >= 3 && error.status && error.status < 500) {
          // A definite answer such as "unknown task": polling again will not change it.
          task.watching = false; showReconnect(error); return;
        } else if (failures >= 3) {
          // The engine answers but is busy or erroring: keep polling, more slowly.
          updateTaskStatus(t("引擎暂时没有响应，正在重试..."));
        }
      }
      if (!task.done) await new Promise((resolve) => setTimeout(resolve, failures ? Math.min(500 * 2 ** Math.min(failures, 4), 8000) : 500));
    }
    task.watching = false;
    if (disposed || activeTask !== task) return;
    finishTask(task);
  }

  function finishTask(task) {
    if (activeTask !== task || !task.done || disposed) return;
    if (task.error) {
      showTaskError(t("任务失败: {0}", task.error));
      retryTask = task.prompt ? task : null;
      updateTaskStatus(t("任务失败"), { retry: !!task.prompt, idle: true });
      if (!elements.promptInput.value.trim() && task.inputText) {
        elements.promptInput.value = task.inputText;
        if (!attachments.length) attachments = task.attachments;
        renderAttachments();
        saveDraft();
        resizePrompt();
      }
      if (task.card && !task.text && !task.reasoning && !task.card.querySelector(".task-artifacts")) task.card.remove();
    } else if (task.interrupted) {
      interruptedTask = { task_id: task.id, session_id: task.sessionId, prompt_preview: task.prompt, resume_available: true };
      updateTaskStatus(t("任务已中断"), { resume: true });
    } else {
      if (task.card && !task.text && !task.reasoning && !task.card.querySelector(".task-artifacts")) task.card.remove();
      updateTaskStatus(task.state === "cancelled" ? t("任务已停止") : "", { idle: true });
      notice("");
    }
    activeTask = null;
    if (backgroundTasks.get(task.sessionId) === task) backgroundTasks.delete(task.sessionId);
    settleUnfinishedTools();
    elements.timelineList.querySelectorAll(".message-card.pending, .message-card.streaming").forEach((card) => card.classList.remove("pending", "streaming"));
    showApproval(null);
    syncControls();
  }

  function promptWithAttachments(prompt, imports) {
    if (!imports.length) return prompt;
    const paths = imports.map((item) => `- ${item.path}`).join("\n");
    return t("{0}\n\n工作区附件路径:\n{1}", prompt, paths);
  }

  function reconcilePendingRequest(sessionId) {
    const pending = pendingRequests[sessionId];
    if (!pending?.requestId) return;
    const admitted = historyEvents.find(event => event.type === "mobile.task.created"
      && event.data?.request_id === pending.requestId && event.data?.task_id);
    if (!admitted) return;
    submissions[admitted.data.task_id] = {
      sessionId, prompt: pending.payload.prompt, inputText: pending.inputText,
      attachments: pending.attachments, model: pending.payload.model,
      reasoning_effort: pending.payload.reasoning_effort, requestId: pending.requestId, createdAt: Date.now(),
    };
    writeStorage(submissionsKey, submissions);
    if (recoveredPendingDraft?.sessionId === sessionId && recoveredPendingDraft.requestId === pending.requestId) {
      if (elements.promptInput.value === recoveredPendingDraft.text
        && JSON.stringify(attachments.map(attachmentReceipt)) === recoveredPendingDraft.attachments) {
        elements.promptInput.value = "";
        attachments = [];
        saveDraft();
        renderAttachments();
        resizePrompt();
      }
      recoveredPendingDraft = null;
    }
    clearPendingRequest(sessionId, pending.requestId);
  }

  function clearPendingRequest(sessionId, requestId) {
    if (pendingRequests[sessionId]?.requestId !== requestId) return;
    delete pendingRequests[sessionId];
    writeStorage(pendingRequestsKey, pendingRequests);
  }

  function retainPendingRequest(sessionId, payload, inputText, imports, acknowledgedRequestId = null) {
    const signature = JSON.stringify(payload);
    const existing = pendingRequests[sessionId];
    const requestId = acknowledgedRequestId || (existing?.signature === signature && typeof existing.requestId === "string" && existing.requestId
      ? existing.requestId : window.crypto?.randomUUID?.() || `mobile-${Date.now()}-${Math.random().toString(16).slice(2)}`);
    const record = { requestId, signature, payload, inputText, attachments: imports };
    // This receipt must survive a lost response and reload before a task can execute.
    window.localStorage.setItem(pendingRequestsKey, JSON.stringify({ ...pendingRequests, [sessionId]: record }));
    pendingRequests[sessionId] = record;
    return requestId;
  }

  async function prepareAttachments(imports, sessionId) {
    const prepared = [];
    for (const item of imports) {
      let receipt = item;
      if (!/^[a-f0-9]{64}$/.test(item.sha256 || "") || typeof item.media_type !== "string" || !item.media_type) {
        receipt = await apiJson(`/mobile/attachments?session_id=${encodeURIComponent(sessionId)}&path=${encodeURIComponent(item.path)}`);
      }
      if (receipt.path !== item.path || !/^[a-f0-9]{64}$/.test(receipt.sha256 || "") || typeof receipt.media_type !== "string" || !receipt.media_type) {
        throw new Error(t("无法校验附件 {0}，请重新导入", item.name || item.path));
      }
      if (hasImageName(item) && !receipt.media_type.startsWith("image/")) {
        throw new Error(t("图片 {0} 的内容或格式无效，请转换为 PNG、JPEG、WebP 或 GIF 后重新导入", item.name || item.path));
      }
      if (receipt.media_type.startsWith("image/") && !["image/png", "image/jpeg", "image/webp", "image/gif"].includes(receipt.media_type)) {
        throw new Error(t("暂不支持 {0}，请转换成 PNG、JPEG、WebP 或 GIF", receipt.media_type));
      }
      prepared.push(attachmentReceipt(receipt));
    }
    const images = prepared.filter(item => item.media_type.startsWith("image/"));
    if (images.length > 4) throw new Error(t("每次最多发送 4 张图片"));
    if (new Set(images.map(item => item.path)).size !== images.length) throw new Error(t("请移除重复图片后再发送"));
    return prepared;
  }

  function canSteer() {
    return !!activeTask?.id && !activeTask.done && !activeTask.stopping && activeTask.sessionId === currentSessionId
      && ["running", "waiting_approval"].includes(activeTask.state);
  }

  // Add a message to the running task. The engine stores it at once and the agent takes it into
  // account between its next model/tool steps, without starting a new task.
  async function steerActiveTask() {
    const task = activeTask;
    const requested = [...attachments];
    const plainText = elements.promptInput.value.trim();
    if (!canSteer() || isSteering || (!plainText && !requested.length)) return;
    isSteering = true;
    syncControls();
    let card = null;
    try {
      let imports = [];
      try { imports = await prepareAttachments(requested, task.sessionId); }
      catch (error) { notice(t("附件校验失败: {0}", error.message)); return; }
      const text = plainText || t("请查看附件内容。");
      const prompt = promptWithAttachments(text, imports);
      const inputId = `steer-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
      card = appendMessageCard("user", t("您"), text);
      card.dataset.messageText = prompt;
      card.classList.add("steer", "sending");
      elements.promptInput.value = "";
      attachments = [];
      renderAttachments();
      saveDraft();
      resizePrompt();
      scrollToBottom(true);
      await apiJson(`/mobile/tasks/${encodeURIComponent(task.id)}/steer`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, input_id: inputId }),
      });
      card.classList.remove("sending");
      const note = document.createElement("small");
      note.className = "steer-note";
      note.textContent = t("已加入当前任务");
      card.appendChild(note);
      haptic(24);
    } catch (error) {
      if (disposed) return;
      // Nothing was added: put the text back so it is not lost.
      card?.remove();
      if (!elements.promptInput.value.trim()) {
        elements.promptInput.value = plainText;
        if (!attachments.length) attachments = requested;
        renderAttachments();
        saveDraft();
        resizePrompt();
      }
      notice(error.code === "turn_not_active"
        ? (task.done ? t("当前任务已结束，消息已放回输入框") : t("任务尚未开始执行，请稍后再补充"))
        : error.code === "turn_input_full" ? t("已有较多补充等待处理，请稍后再发")
        : t("补充失败: {0}", error.message));
    } finally {
      isSteering = false;
      if (!disposed) syncControls();
    }
  }

  async function sendPrompt(customText = null, attachmentOverride = []) {
    if (customText === null && canSteer()) { await steerActiveTask(); return; }
    const requestedImports = customText === null ? [...attachments] : [...attachmentOverride];
    const defaultPrompt = requestedImports.every(item => item.media_type?.startsWith("image/") || /\.(png|jpe?g|webp|gif)$/i.test(item.name || "")) ? t("请描述图片内容。") : t("请查看附件内容。");
    const plainText = customText || elements.promptInput.value.trim() || (requestedImports.length ? defaultPrompt : "");
    if (!plainText || activeTask || isLoadingSession || isUploading || isPreparingSubmission || restartPending || localDeviceTesting || !historyReady || !currentSessionId || !settingsAvailable) return;
    const sessionId = currentSessionId;
    let imports;
    isPreparingSubmission = true;
    syncControls();
    try {
      imports = await prepareAttachments(requestedImports, sessionId);
      if (customText === null) { attachments = imports; saveDraft(); }
    } catch (error) {
      notice(t("附件校验失败: {0}", error.message));
      return;
    } finally {
      isPreparingSubmission = false;
      syncControls();
      window.setTimeout(refreshShareInbox, 0);
    }
    if (disposed || currentSessionId !== sessionId || activeTask || isLoadingSession || isUploading || restartPending || localDeviceTesting || !historyReady || !settingsAvailable) return;
    const imageRefs = imports.filter(item => item.media_type.startsWith("image/")).map(item => ({ path: item.path, sha256: item.sha256 }));
    const submittedPrompt = promptWithAttachments(plainText, imports.filter(item => !item.media_type.startsWith("image/")));
    const payload = { session_id: sessionId, prompt: submittedPrompt, model: settings.model,
      reasoning_effort: settings.reasoning_effort, ...(imageRefs.length ? { image_refs: imageRefs } : {}) };
    let requestId;
    try { requestId = retainPendingRequest(sessionId, payload, plainText, imports); }
    catch { notice(t("无法保存任务提交记录，请检查存储空间后重试")); return; }
    haptic(36);
    elements.timelineList.querySelector(".empty-state")?.remove();
    const userCard = appendMessageCard("user", t("您"), plainText);
    userCard.dataset.messageText = submittedPrompt;
    if (customText === null) {
      elements.promptInput.value = "";
      attachments = [];
      renderAttachments();
      saveDraft();
      resizePrompt();
    }
    activeTask = makeTask({ task_id: null, session_id: sessionId }, plainText);
    const task = activeTask;
    task.prompt = submittedPrompt;
    task.inputText = plainText;
    task.attachments = imports;
    task.requestId = requestId;
    retryTask = null;
    interruptedTask = null;
    updateTaskStatus(t("正在提交任务..."));
    syncControls();
    scrollToBottom(true);
    try {
      const result = await submitAfterEngineRecovery("/mobile/tasks", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, request_id: requestId }),
      });
      task.id = result.task?.task_id;
      if (!task.id) throw new Error(t("服务未返回有效任务 ID"));
      backgroundTasks.set(sessionId, task);
      submissions[task.id] = {
        sessionId, prompt: submittedPrompt, inputText: plainText, attachments: imports,
        model: task.model, reasoning_effort: task.effort, requestId, createdAt: Date.now(),
      };
      const retained = Object.keys(submissions).sort((first, second) => (submissions[second].createdAt || 0) - (submissions[first].createdAt || 0));
      retained.slice(20).forEach((id) => { delete submissions[id]; });
      writeStorage(submissionsKey, submissions);
      clearPendingRequest(sessionId, requestId);
      titleUntitledSession(sessionId, plainText);
      updateTaskStatus(t("任务执行中"));
      syncControls();
      updateAssistantCard(task);
      await watchTask(task);
      if (!disposed) haptic(40);
    } catch (error) {
      if (disposed) return;
      // A transport failure after an acknowledgement still needs the same task identity.
      if (task.id) { try { retainPendingRequest(sessionId, payload, plainText, imports, requestId); } catch {} }
      showTaskError(t("任务提交失败: {0}", error.message));
      retryTask = task;
      if (!elements.promptInput.value.trim() && customText === null) {
        elements.promptInput.value = plainText;
        if (!attachments.length) attachments = imports;
        if (pendingRequests[sessionId]?.requestId === requestId) {
          recoveredPendingDraft = { sessionId, requestId, text: plainText,
            attachments: JSON.stringify(imports.map(attachmentReceipt)) };
        }
        renderAttachments();
        saveDraft();
        resizePrompt();
      }
      task.card?.remove();
      userCard.remove();
      activeTask = null;
      if (backgroundTasks.get(sessionId) === task) backgroundTasks.delete(sessionId);
      updateTaskStatus(t("任务提交失败"), { retry: true });
      syncControls();
    }
    scrollToBottom();
  }

  // A conversation still named "新会话" takes its first instruction as its name, so the list stays readable.
  // Stored titles are compared raw: a conversation created in either language counts as untitled.
  const placeholderTitles = new Set(["", "新会话", "New chat", "New session", "New conversation"]); // i18n-ignore: stored data
  function titleUntitledSession(sessionId, text) {
    const session = sessions.find(item => item.id === sessionId);
    const title = String(text || "").replace(/\s+/g, " ").trim().slice(0, 40);
    if (!session || !title || !placeholderTitles.has(String(session.title || "").trim())) return;
    const previous = session.title;
    session.title = title;
    renderSessionNavigation();
    apiJson(`/sessions/${encodeURIComponent(sessionId)}/rename`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) })
      .then((data) => { if (typeof data.title === "string" && data.title) { session.title = data.title; renderSessionNavigation(); } })
      .catch(() => { if (disposed || session.title !== title) return; session.title = previous; renderSessionNavigation(); });
  }

  async function stopTask() {
    const task = activeTask;
    if (!task?.id || task.stopping) return;
    task.stopping = true;
    syncControls();
    try {
      const result = await apiJson(`/mobile/tasks/${encodeURIComponent(task.id)}/cancel`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      if (terminalStates.has(result.task?.state)) {
        task.state = result.task.state;
        task.done = true;
        finishTask(task);
      } else {
        updateTaskStatus(t("正在停止任务..."));
        if (!task.watching) void watchTask(task);
      }
    } catch (error) {
      if (disposed) return;
      task.stopping = false;
      notice(t("停止失败: {0}", error.message));
      syncControls();
    }
  }

  async function resumeTask() {
    const snapshot = interruptedTask;
    if (!snapshot || activeTask) return;
    elements.btnResumeTask.disabled = true;
    try {
      const result = await apiJson(`/mobile/tasks/${encodeURIComponent(snapshot.task_id)}/resume`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      interruptedTask = null;
      activeTask = makeTask(result.task || snapshot);
      backgroundTasks.set(activeTask.sessionId, activeTask);
      updateTaskStatus(t("正在恢复任务..."));
      syncControls();
      await watchTask(activeTask);
    } catch (error) {
      if (disposed) return;
      notice(t("恢复失败: {0}", error.message));
      elements.btnResumeTask.disabled = false;
    }
  }

  function renderAttachments() {
    elements.attachmentList.replaceChildren();
    for (const item of attachments) {
      const chip = document.createElement("div");
      chip.className = "attachment-chip";
      const label = document.createElement("span");
      label.textContent = `${item.media_type?.startsWith("image/") ? t("图片 · ") : ""}${item.name}`;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "icon-button attachment-remove";
      remove.title = t("移除 {0}", item.name);
      remove.setAttribute("aria-label", t("移除 {0}", item.name));
      remove.innerHTML = icon("x");
      remove.addEventListener("click", async () => {
        if (isUploading || isPreparingSubmission) return;
        const submitted = Object.values(submissions).some((record) => record.sessionId === currentSessionId
          && record.attachments?.some((file) => file.path === item.path));
        if (!submitted) {
          isUploading = true;
          remove.disabled = true;
          syncControls();
          try {
            const path = `/mobile/attachments?session_id=${encodeURIComponent(currentSessionId)}&path=${encodeURIComponent(item.path)}`;
            await apiJson(path, { method: "DELETE" });
          } catch (error) {
            if (disposed) return;
            if (error.status !== 409) {
              notice(t("移除附件失败: {0}", error.message));
              remove.disabled = false;
              return;
            }
          } finally { isUploading = false; syncControls(); }
        }
        if (disposed) return;
        attachments = attachments.filter((entry) => entry !== item);
        renderAttachments();
        saveDraft();
      });
      chip.append(label, remove);
      elements.attachmentList.appendChild(chip);
    }
  }

  function requestId(prefix) {
    return window.crypto?.randomUUID?.() || `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function persistImportedFiles(sessionId, files, itemIds = [], batchTexts = []) {
    if (disposed || (sessionId === currentSessionId && (isLoadingSession || isPreparingSubmission))) return false;
    const previous = drafts[sessionId];
    const base = typeof previous === "string" ? { text: previous, attachments: [] } : (previous || { text: "", attachments: [] });
    const next = { ...base, text: sessionId === currentSessionId ? elements.promptInput.value : base.text || "",
      attachments: [...(sessionId === currentSessionId ? attachments : Array.isArray(base.attachments) ? base.attachments : [])] };
    const knownItems = new Set(base.shared_item_ids || []), knownBatches = new Set(base.shared_batch_ids || []);
    for (const file of files) {
      if (typeof file?.name !== "string" || typeof file?.path !== "string") throw new Error(t("服务未返回附件路径"));
      if (!next.attachments.some(existing => existing.path === file.path)) next.attachments.push(attachmentReceipt(file));
    }
    for (const [id, text] of batchTexts) {
      if (!knownBatches.has(id) && typeof text === "string" && text.trim()) next.text += `${next.text ? "\n\n" : ""}${text}`;
      knownBatches.add(id);
    }
    for (const id of itemIds) knownItems.add(id);
    if (knownItems.size) next.shared_item_ids = [...knownItems];
    if (knownBatches.size) next.shared_batch_ids = [...knownBatches];
    const updated = { ...drafts, [sessionId]: next };
    if (!writeStorage(draftsKey, updated)) {
      notice(t("附件已导入，草稿保存失败；文件仍保留在收件箱，请释放存储后重试"));
      return false;
    }
    drafts[sessionId] = next;
    if (sessionId === currentSessionId) {
      attachments = next.attachments; elements.promptInput.value = next.text;
      recoveredPendingDraft = null; renderAttachments(); resizePrompt(); syncControls();
    }
    return true;
  }

  function rawUpload(entry) {
    const query = new URLSearchParams({ session_id: entry.sessionId, filename: entry.file.name,
      media_type: entry.file.type || "application/octet-stream", request_id: entry.id });
    if (entry.workspaceId) query.set("workspace_id", entry.workspaceId);
    const route = `/mobile/attachments/upload?${query}`;
    if (typeof window.XMLHttpRequest !== "function") return apiJson(route, {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: entry.file,
    });
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest(); entry.xhr = xhr;
      xhr.open("POST", route); xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.setRequestHeader("Content-Type", "application/octet-stream");
      xhr.upload.onprogress = event => { entry.loaded = event.loaded; renderImportUploads(); };
      xhr.onerror = () => reject(new Error(t("连接中断；重试会复用同一个导入编号")));
      xhr.onabort = () => reject(new Error(t("上传已取消，已完成的文件仍保留")));
      xhr.onload = () => {
        try {
          const data = JSON.parse(xhr.responseText);
          if (xhr.status < 200 || xhr.status >= 300) throw new Error(localizeError(data.error) || `HTTP ${xhr.status}`);
          resolve(data);
        } catch (error) { reject(error); }
      };
      xhr.send(entry.file);
    }).finally(() => { entry.xhr = null; });
  }

  async function runUploads(entries) {
    if (isUploading || disposed) return;
    isUploading = true; syncControls();
    const queue = [...entries];
    for (let index = 0; index < queue.length; index++) {
      const entry = queue[index];
      if (disposed) break;
      entry.state = "uploading"; entry.error = ""; renderImportUploads();
      try {
        const file = entry.file;
        if (!entry.attachment) {
          if ((file.type.startsWith("image/") && !["image/png", "image/jpeg", "image/webp", "image/gif"].includes(file.type))
            || (hasImageName(file) && !/\.(png|jpe?g|jfif|webp|gif)$/i.test(file.name)))
            throw new Error(t("{0} 请先转换成 PNG、JPEG、WebP 或 GIF", file.name));
          entry.attachment = await rawUpload(entry);
          if ((file.type.startsWith("image/") || hasImageName(file))
            && !["image/png", "image/jpeg", "image/webp", "image/gif"].includes(entry.attachment.media_type)) {
            entry.attachment = null;
            throw new Error(t("图片 {0} 的内容或格式无效，请转换后重新导入", file.name));
          }
        }
        if (disposed) break;
        if (!persistImportedFiles(entry.sessionId, [entry.attachment])) throw new Error(t("草稿保存失败，导入文件已保留"));
        entry.loaded = file.size; entry.state = "ready";
      } catch (error) {
        entry.state = "error"; entry.error = error.message;
        if (!disposed) notice(t("附件 {0} 导入失败: {1}", entry.file.name, error.message));
      }
      renderImportUploads();
      for (const added of browserUploads) {
        if (added.state === "pending" && !queue.includes(added)) queue.push(added);
      }
    }
    isUploading = false;
    if (!disposed) { elements.filePickerInput.value = ""; syncControls(); renderImportUploads(); }
  }

  function uploadFiles(files) {
    if (!files.length || !currentSessionId || isPreparingSubmission || isLoadingSession || restartPending) return;
    const entries = files.map(file => ({ id: requestId("upload"), sessionId: currentSessionId,
      workspaceId: currentWorkspaceId, file, loaded: 0, state: "pending" }));
    browserUploads.push(...entries); renderImportUploads();
    void runUploads(browserUploads.filter(entry => entry.state === "pending"));
  }

  function showImportPage() { if (elements.settingsOverlay.hidden) openMenu(); setSettingsPage("attachments"); }

  function chooseImportFiles() {
    haptic();
    if (typeof bridge?.pickShareInboxFiles === "function") {
      showImportPage();
      try {
        const result = JSON.parse(bridge.pickShareInboxFiles());
        if (!result.ok) throw new Error(localizeError(result.error) || t("无法选择文件"));
      } catch (error) { pageStatus(elements.shareInboxStatus, error.message, true); }
    } else elements.filePickerInput.click();
  }

  function syncImportControls() {
    const ids = shareInbox.items.filter(item => shareSelection.get(item.id) !== false
      && ["pending", "error", "uncertain"].includes(item.state)).map(item => item.id);
    elements.btnImportShares.disabled = !ids.length || !elements.shareTargetSession.value || isLoadingSession || isPreparingSubmission;
    elements.btnDiscardShares.disabled = !ids.length;
    elements.btnPickImportFiles.disabled = isPreparingSubmission || isLoadingSession || restartPending;
    elements.shareTargetSession.disabled = isPreparingSubmission || isLoadingSession;
  }

  function renderImportUploads() {
    if (disposed) return;
    elements.browserUploadList.replaceChildren();
    for (const entry of browserUploads) {
      const row = document.createElement("div"); row.className = "import-row";
      const body = document.createElement("div"); body.className = "import-row-body";
      const title = document.createElement("strong"); title.textContent = entry.file.name;
      const status = document.createElement("small"); status.textContent = entry.error || (entry.state === "ready" ? t("已添加") : entry.state === "uploading" ? t("上传中") : t("等待上传"));
      const progress = document.createElement("progress"); progress.max = Math.max(1, entry.file.size); progress.value = entry.loaded;
      body.append(title, status, progress); row.append(body);
      if (entry.state === "error") {
        const retry = actionButton("refresh-cw", t("重试 {0}", entry.file.name), "data-upload-retry", entry.id);
        retry.disabled = isUploading; retry.addEventListener("click", () => void runUploads([entry])); row.append(retry);
      } else if (entry.state === "uploading" && entry.xhr) {
        const cancel = actionButton("x", t("取消 {0}", entry.file.name), "data-upload-cancel", entry.id);
        cancel.addEventListener("click", () => entry.xhr?.abort()); row.append(cancel);
      }
      elements.browserUploadList.append(row);
    }
    updateImportNotice();
  }

  function updateImportNotice() {
    const count = shareInbox.items.filter(item => !acknowledgedShares.has(item.id)).length
      + browserUploads.filter(item => item.state !== "ready").length;
    elements.btnImportNotice.hidden = count === 0;
    elements.importNoticeText.textContent = t("{0} 个附件待处理", count);
    elements.menuImportSummary.textContent = count ? t("{0} 个待处理", count) : "";
  }

  function applyReadyShares() {
    for (const item of shareInbox.items) {
      if (item.state !== "ready" || acknowledgedShares.has(item.id)) continue;
      const target = item.target || (item.session_id ? {
        session_id: item.session_id,
        workspace_id: item.workspace_id,
      } : null);
      if (!target?.session_id) continue;
      const session = sessions.find(value => value.id === target.session_id);
      if (!session || (session.workspace_id && session.workspace_id !== target.workspace_id)) continue;
      const savedIds = drafts[session.id]?.shared_item_ids || [];
      const batch = shareInbox.batches.find(value => value.id === item.batch_id);
      const text = typeof item.text === "string" ? item.text : batch?.text;
      const textKey = text ? (batch?.id || item.id) : null;
      if (!savedIds.includes(item.id) && !persistImportedFiles(session.id,
        item.attachment ? [item.attachment] : [], [item.id], textKey ? [[textKey, text]] : [])) continue;
      if (typeof bridge?.ackShareInbox === "function") {
        try {
          const result = JSON.parse(bridge.ackShareInbox(JSON.stringify({ item_ids: [item.id] })));
          if (result.ok) acknowledgedShares.add(item.id);
        } catch { /* The durable draft records this id before acknowledging the native copy. */ }
      }
    }
  }

  function renderShareInbox() {
    const native = typeof bridge?.getShareInbox === "function";
    elements.shareTargetControls.hidden = !native;
    elements.shareImportActions.hidden = !native;
    elements.btnRefreshImports.hidden = !native;
    const selected = elements.shareTargetSession.value || currentSessionId;
    elements.shareTargetSession.replaceChildren();
    for (const session of sessions) {
      const option = document.createElement("option"); option.value = session.id;
      const workspace = workspaces.find(value => value.id === session.workspace_id);
      option.textContent = `${workspace?.name || t("工作区")} · ${session.title || t("会话")}`;
      elements.shareTargetSession.append(option);
    }
    elements.shareTargetSession.value = sessions.some(session => session.id === selected) ? selected : currentSessionId;
    elements.shareInboxList.replaceChildren();
    const stateNames = { staging: t("接收中"), pending: t("等待导入"), uploading: t("导入中"), importing: t("导入中"), ready: t("已导入"), error: t("导入失败"), uncertain: t("等待确认") };
    for (const item of shareInbox.items) {
      if (acknowledgedShares.has(item.id)) continue;
      const row = document.createElement("label"); row.className = "import-row";
      const checkbox = document.createElement("input"); checkbox.type = "checkbox";
      checkbox.checked = shareSelection.get(item.id) !== false; checkbox.disabled = !["pending", "error", "uncertain"].includes(item.state);
      checkbox.setAttribute("aria-label", t("选择 {0}", item.name || t("附件")));
      checkbox.addEventListener("change", () => { shareSelection.set(item.id, checkbox.checked); syncImportControls(); });
      const body = document.createElement("div"); body.className = "import-row-body";
      const title = document.createElement("strong"); title.textContent = item.name || t("附件");
      const status = document.createElement("small"); status.textContent = `${formatBytes(item.size || 0)} · ${item.error || stateNames[item.state] || t("等待导入")}`;
      body.append(title, status); row.append(checkbox, body); elements.shareInboxList.append(row);
    }
    syncImportControls(); updateImportNotice();
  }

  function refreshShareInbox() {
    if (disposed || refreshingImports) return;
    refreshingImports = true;
    try {
      if (typeof bridge?.getShareInbox === "function") {
        const snapshot = JSON.parse(bridge.getShareInbox());
        if (!snapshot.ok || !Array.isArray(snapshot.items)) throw new Error(localizeError(snapshot.error) || t("无法读取收件箱"));
        shareInbox = { items: snapshot.items, batches: Array.isArray(snapshot.batches) ? snapshot.batches : [] };
        applyReadyShares();
        if (snapshot.capture_error) pageStatus(elements.shareInboxStatus, localizeError(String(snapshot.capture_error)), true);
      }
      renderShareInbox(); renderImportUploads();
    } catch (error) { pageStatus(elements.shareInboxStatus, error.message, true); }
    finally { refreshingImports = false; }
  }

  function confirmShares() {
    const session = sessions.find(item => item.id === elements.shareTargetSession.value);
    const ids = shareInbox.items.filter(item => shareSelection.get(item.id) !== false
      && ["pending", "error", "uncertain"].includes(item.state)).map(item => item.id);
    if (!session || !ids.length || elements.btnImportShares.disabled) return;
    try {
      const result = JSON.parse(bridge.confirmShareInbox(JSON.stringify({ request_id: requestId("share"),
        session_id: session.id, workspace_id: workspaceOfSession(session.id), item_ids: ids })));
      if (!result.ok) throw new Error(localizeError(result.error) || t("无法导入附件"));
      pageStatus(elements.shareInboxStatus, t("正在添加到目标会话...")); refreshShareInbox();
    } catch (error) { pageStatus(elements.shareInboxStatus, error.message, true); }
  }

  function discardShares() {
    const ids = shareInbox.items.filter(item => shareSelection.get(item.id) !== false
      && ["pending", "error", "uncertain"].includes(item.state)).map(item => item.id);
    if (!ids.length || !window.confirm(t("丢弃所选的 {0} 个附件？", ids.length))) return;
    try {
      const result = JSON.parse(bridge.discardShareInbox(JSON.stringify({ item_ids: ids })));
      if (!result.ok) throw new Error(localizeError(result.error) || t("无法丢弃附件"));
      refreshShareInbox();
    } catch (error) { pageStatus(elements.shareInboxStatus, error.message, true); }
  }

  async function exportConversation() {
    const session = sessions.find((item) => item.id === currentSessionId);
    const title = session?.title || "Agent Workspace";
    try {
      const result = await apiJson(`/sessions/${encodeURIComponent(currentSessionId)}/events`);
      const lines = [`# ${title}`];
      for (const event of result.events || []) {
        const data = event.data || {};
        if (event.type === "message.user" || (event.type === "message.created" && data.role === "user")) lines.push(t("\n## 您\n\n{0}", data.text || data.content || ""));
        if (event.type === "message.assistant" || (event.type === "message.created" && data.role === "assistant")) lines.push(`\n## Agent\n\n${data.text || data.content || ""}`);
      }
      shareText(title, lines.join("\n"));
      closeMenu();
    } catch (error) {
      if (!disposed) notice(t("导出失败: {0}", error.message));
    }
  }

  elements.promptInput.addEventListener("input", () => { recoveredPendingDraft = null; saveDraft(); resizePrompt(); syncControls(); });
  // Soft keyboards have no Shift+Enter, so Enter inserts a line there; Ctrl+Enter always sends.
  const touchKeyboard = typeof window.matchMedia === "function" && window.matchMedia("(pointer: coarse)")?.matches === true;
  elements.promptInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    if (touchKeyboard && !event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    sendPrompt();
  });
  elements.btnSend.addEventListener("click", () => sendPrompt());
  elements.btnStop.addEventListener("click", stopTask);
  elements.btnJumpLatest.addEventListener("click", () => scrollToBottom(true));
  elements.btnResumeTask.addEventListener("click", resumeTask);
  elements.btnRetryTask.addEventListener("click", () => { if (retryTask?.inputText) sendPrompt(retryTask.inputText, retryTask.attachments); });
  elements.btnReconnect.addEventListener("click", async () => {
    if (!activeTask) return;
    engineReconnectRequestedAt = 0;
    if (requestEngineReconnect()) { updateTaskStatus(t("正在恢复与引擎的连接...")); return; }
    try { await apiJson("/mobile/reconnect", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); } catch { /* Event polling is the authoritative recovery path. */ }
    notice("");
    updateTaskStatus(t("正在重新连接..."));
    await watchTask(activeTask);
  });
  elements.btnAttach.addEventListener("click", chooseImportFiles);
  elements.filePickerInput.addEventListener("change", (event) => uploadFiles(Array.from(event.target.files || [])));
  elements.btnAttachmentsPage.addEventListener("click", () => setSettingsPage("attachments"));
  elements.btnImportNotice.addEventListener("click", showImportPage);
  elements.btnPickImportFiles.addEventListener("click", chooseImportFiles);
  elements.btnRefreshImports.addEventListener("click", refreshShareInbox);
  elements.btnImportShares.addEventListener("click", confirmShares);
  elements.btnDiscardShares.addEventListener("click", discardShares);
  elements.shareTargetSession.addEventListener("change", syncImportControls);
  elements.quickChipsBar.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip || chip.disabled) return;
    if (chip.dataset.fill !== "true") { sendPrompt(chip.dataset.prompt); return; }
    // Open-ended shortcuts start the prompt and leave the rest to the user.
    const input = elements.promptInput;
    input.value = input.value.trim() ? `${chip.dataset.prompt}${input.value}` : chip.dataset.prompt;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  });
  elements.btnApproveAction.addEventListener("click", () => resolveApproval(true));
  elements.btnRejectAction.addEventListener("click", () => resolveApproval(false));
  elements.btnNewSession.addEventListener("click", createSession);
  elements.btnDrawerNewSession.addEventListener("click", async () => { if (await createSession()) closeDrawer(); });
  async function createSession() {
    if (elements.btnNewSession.disabled || !canLeaveFileEditor() || fileSaving) return false;
    // One tap creates the conversation; it can be renamed later from the menu.
    const title = t("新会话");
    haptic();
    saveDraft();
    detachSessionTask();
    isLoadingSession = true;
    syncControls();
    try {
      const created = await apiJson("/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, ...(currentWorkspaceId ? { workspace_id: currentWorkspaceId } : {}) }) });
      attachments = [];
      renderAttachments();
      return await loadSessions(created.id);
    } catch (error) { if (!disposed) notice(t("创建会话失败: {0}", error.message)); return false; }
    finally { isLoadingSession = false; syncControls(); }
  }
  elements.sessionSelector.addEventListener("change", async () => {
    if (!await switchSession(elements.sessionSelector.value)) elements.sessionSelector.value = currentSessionId;
  });
  elements.workspaceSelector.addEventListener("change", async () => {
    if (!await switchWorkspace(elements.workspaceSelector.value)) elements.workspaceSelector.value = currentWorkspaceId;
  });
  elements.btnWorkspacesPage.addEventListener("click", () => setSettingsPage("workspaces"));
  elements.btnWorkspacesRefresh.addEventListener("click", loadWorkspaces);
  elements.btnBrowseWorkspaceSystem.addEventListener("click", () => {
    if (elements.btnBrowseWorkspaceSystem.disabled) return;
    const workspaceId = currentWorkspaceId;
    try {
      const result = JSON.parse(bridge.openWorkspaceBrowser(workspaceId));
      if (!result.ok) throw new Error(localizeError(result.error) || t("无法打开系统文件浏览器"));
      pageStatus(elements.workspacesStatus, t("正在打开当前工作区的系统文件浏览入口"));
    } catch (error) { pageStatus(elements.workspacesStatus, error.message, true); }
  });
  elements.btnSuggestWorkspaceFolder.addEventListener("click", () => {
    if (elements.btnSuggestWorkspaceFolder.disabled) return;
    try {
      const result = JSON.parse(bridge.recommendedWorkspaceFolder(elements.workspaceNameInput.value.trim()));
      if (!result.ok || typeof result.path !== "string" || !result.path) throw new Error(localizeError(result.error) || t("无法读取公共文档目录"));
      elements.workspaceFolderInput.value = result.path;
      elements.workspaceCreateDirectory.checked = true;
      syncWorkspaceControls();
      pageStatus(elements.workspacesStatus, t("已填入公共目录建议；点击创建工作区后保存"));
    } catch (error) { pageStatus(elements.workspacesStatus, error.message, true); }
  });
  elements.workspaceCreateForm.addEventListener("submit", createWorkspace);
  for (const input of [elements.workspaceNameInput, elements.workspaceFolderInput]) input.addEventListener("input", syncWorkspaceControls);
  elements.btnPickWorkspaceFolder.addEventListener("click", () => {
    if (elements.btnPickWorkspaceFolder.disabled) return;
    try {
      const result = JSON.parse(bridge.pickWorkspaceFolder());
      if (!result.ok) throw new Error(localizeError(result.error) || t("无法选择文件夹"));
      workspacePicking = true;
      syncWorkspaceControls();
    } catch (error) { pageStatus(elements.workspacesStatus, error.message, true); }
  });
  elements.btnWorkspaceStorageSettings.addEventListener("click", () => {
    try { bridge?.requestWorkspaceStorageAccess?.(); }
    catch (error) { pageStatus(elements.workspaceStorageStatus, error.message, true); }
  });
  window.addEventListener("agent-workspace-folder-selected", event => {
    workspacePicking = false;
    const result = event.detail;
    if (result?.path) elements.workspaceFolderInput.value = result.path;
    pageStatus(elements.workspacesStatus, localizeError(result?.error) || "", !!result?.error);
    refreshWorkspaceAccess();
    syncWorkspaceControls();
  });
  window.addEventListener("focus", refreshWorkspaceAccess);
  window.addEventListener("agent-workspace-storage-changed", refreshWorkspaceAccess);
  elements.btnSettings.addEventListener("click", openMenu);
  elements.modelBar.addEventListener("click", openModelSettings);
  elements.settingsBackdrop.addEventListener("click", closeMenu);
  elements.settingsCloseButton.addEventListener("click", closeMenu);
  elements.btnSessions.addEventListener("click", openDrawer);
  elements.btnSessionTitle.addEventListener("click", openDrawer);
  elements.btnDrawerClose.addEventListener("click", closeDrawer);
  elements.sessionDrawerBackdrop.addEventListener("click", closeDrawer);
  elements.btnDrawerSearch.addEventListener("click", () => { closeDrawer(); openMenu(); setSettingsPage("search"); });
  elements.btnDrawerWorkspaces.addEventListener("click", () => { closeDrawer(); openMenu(); setSettingsPage("workspaces"); });
  elements.btnModeChip.addEventListener("click", () => { if (elements.settingsOverlay.hidden) openMenu(); setSettingsPage("permission"); });
  elements.settingsBackButton.addEventListener("click", () => setSettingsPage(settingsPage === "pricing" ? "usage" : "home"));
  elements.btnModelPage.addEventListener("click", () => setSettingsPage("model"));
  elements.btnPermissionPage.addEventListener("click", () => setSettingsPage("permission"));
  elements.btnAppearancePage.addEventListener("click", () => setSettingsPage("appearance"));
  elements.btnSearchPage.addEventListener("click", () => setSettingsPage("search"));
  elements.btnTasksPage.addEventListener("click", () => setSettingsPage("tasks"));
  elements.btnFilesPage.addEventListener("click", () => setSettingsPage("files"));
  elements.btnSessionPage.addEventListener("click", () => setSettingsPage("session"));
  elements.btnNotificationsPage.addEventListener("click", () => setSettingsPage("notifications"));
  elements.btnUsagePage.addEventListener("click", () => setSettingsPage("usage"));
  elements.usageScopeSelector.addEventListener("change", loadUsage);
  elements.usageDaysSelector.addEventListener("change", loadUsage);
  elements.btnUsageRefresh.addEventListener("click", loadUsage);
  elements.btnPricingPage.addEventListener("click", () => openPricing());
  elements.pricingModelInput.addEventListener("input", () => fillPricingFields(elements.pricingModelInput.value.trim()));
  for (const input of [elements.pricingInputRate, elements.pricingOutputRate, elements.pricingCachedRate]) input.addEventListener("input", syncPricingControls);
  elements.btnSavePricing.addEventListener("click", savePricing);
  elements.btnTasksRefresh.addEventListener("click", loadTaskCenter);
  elements.btnFileParent.addEventListener("click", () => loadWorkspaceFiles(fileEditor ? workspacePath : (workspaceParent || "")));
  elements.btnFilesRefresh.addEventListener("click", () => loadWorkspaceFiles(workspacePath));
  elements.btnReloadFile.addEventListener("click", () => { if (fileEditor) void openWorkspaceFile(fileEditor.path, null, fileEditor.workspaceId); });
  elements.btnDiscardFileDraft.addEventListener("click", discardFileDraft);
  elements.btnSaveFile.addEventListener("click", saveWorkspaceFile);
  elements.btnFilePreview.addEventListener("click", showFilePreview);
  elements.btnFileSource.addEventListener("click", resetFilePreview);
  elements.btnFileInteractive.addEventListener("click", () => {
    if (!fileEditor?.loaded) return;
    void artifactAction({ ...fileEditor, mime_type: "text/html" }, "open", elements.btnFileInteractive, elements.fileEditorStatus, true);
  });
  elements.fileContentInput.addEventListener("input", () => {
    if (!fileEditor?.loaded || !fileEditor.editable || fileSaving) return;
    fileEditor.content = elements.fileContentInput.value;
    const saved = persistFileDraft();
    if (saved && !fileEditor.conflict) pageStatus(elements.fileEditorStatus, fileDirty() ? t("未保存 · 本地草稿已保留") : "");
    syncFileControls();
  });
  elements.sessionTitleInput.addEventListener("input", syncControls);
  elements.btnRenameSession.addEventListener("click", renameSession);
  $("btnArchiveSession").addEventListener("click", async () => {
    const session = sessions.find(item => item.id === currentSessionId);
    if (!session || isLoadingSession || activeTask) return;
    closeMenu();
    await setSessionArchived(session, true);
  });
  elements.taskNotificationsToggle.addEventListener("change", changeNotificationPreference);
  elements.btnNotificationSettings.addEventListener("click", () => {
    try { bridge?.openNotificationSettings?.(); }
    catch (error) { pageStatus(elements.notificationPermissionStatus, t("打开通知设置失败: {0}", error.message), true); }
  });
  elements.sessionSearchInput.addEventListener("input", queueSessionSearch);
  elements.btnApplySettings.addEventListener("click", applyRuntimeSettings);
  elements.contextSummaryToggle.addEventListener("change", () => { contextSummaryDirty = true; });
  elements.btnProviderSettings.addEventListener("click", () => { if (!elements.btnProviderSettings.disabled) { closeMenu(); bridge?.openSettings?.(); } });
  elements.btnExport.addEventListener("click", exportConversation);
  elements.btnRefresh.addEventListener("click", async () => { closeMenu(); await loadSettings(); if (!activeTask) await loadSessions(currentSessionId); });
  elements.modelInput.addEventListener("input", () => { fillEffortOptions(elements.modelInput.value.trim(), elements.effortSelector.value); syncControls(); });
  elements.localContextSelector.addEventListener("change", () => { elements.localContextCustomRow.hidden = elements.localContextSelector.value !== "custom"; });
  elements.themeSelector.addEventListener("change", () => { preferences.theme = elements.themeSelector.value; writeStorage(settingsKey, preferences); applyAppearance(); });
  elements.textSizeSelector.addEventListener("change", () => { preferences.textSize = elements.textSizeSelector.value; writeStorage(settingsKey, preferences); applyAppearance(); });
  elements.quickActionsToggle.addEventListener("change", () => { preferences.quickActions = elements.quickActionsToggle.checked; writeStorage(settingsKey, preferences); applyAppearance(); });
  elements.hapticsToggle.addEventListener("change", () => { preferences.haptics = elements.hapticsToggle.checked; writeStorage(settingsKey, preferences); });
  function chooseAppearance(key, value) {
    if (!appearanceChoices[key].includes(value) || preferences[key] === value) return;
    preferences[key] = value;
    writeStorage(settingsKey, preferences);
    applyAppearance();
    haptic(12);
  }
  $("stylePicker").addEventListener("click", (event) => { const option = event.target.closest("[data-style-option]"); if (option) chooseAppearance("style", option.dataset.styleOption); });
  $("accentPicker").addEventListener("click", (event) => { const option = event.target.closest("[data-accent-option]"); if (option) chooseAppearance("accent", option.dataset.accentOption); });
  $("motionSelector").addEventListener("change", (event) => chooseAppearance("motion", event.target.value));
  $("backdropPicker").addEventListener("click", (event) => {
    const option = event.target.closest("[data-backdrop-option]");
    if (!option) return;
    if (option.dataset.backdropOption === "custom" && !customWallpaper) $("wallpaperInput").click();
    else chooseAppearance("backdrop", option.dataset.backdropOption);
  });
  $("btnChangeWallpaper").addEventListener("click", () => $("wallpaperInput").click());
  $("btnRemoveWallpaper").addEventListener("click", () => {
    customWallpaper = "";
    try { window.localStorage.removeItem(wallpaperKey); } catch { /* Nothing stored. */ }
    preferences.backdrop = "aurora";
    writeStorage(settingsKey, preferences);
    applyAppearance();
  });
  $("wallpaperInput").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    elements.settingsError.hidden = true;
    try {
      customWallpaper = await storeWallpaper(file);
      preferences.backdrop = "custom";
      writeStorage(settingsKey, preferences);
      applyAppearance();
      haptic(12);
    } catch (error) {
      elements.settingsError.textContent = error.message;
      elements.settingsError.hidden = false;
    }
  });
  $("languageSelector").addEventListener("change", (event) => {
    const value = event.target.value;
    if (!appearanceChoices.language.includes(value) || value === preferences.language) return;
    preferences.language = value;
    writeStorage(settingsKey, preferences);
    try { bridge?.setUiLanguage?.(value); } catch { /* Older APKs keep native text in Chinese. */ }
    // Text is chosen once per page load; drafts are already saved on every edit.
    saveDraft();
    persistFileDraft();
    window.AgentMobileUi.reloadForLanguage();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && (closeDrawer() || closeMenu())) event.preventDefault();
    const dialog = !elements.sessionDrawer.hidden ? elements.sessionDrawerPanel : !elements.settingsOverlay.hidden ? elements.settingsSheet : null;
    if (event.key !== "Tab" || !dialog) return;
    const controls = [...dialog.querySelectorAll("button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], summary, [tabindex]")]
      .filter((control) => control.tabIndex >= 0 && !control.closest("[hidden], .hidden"));
    const first = controls[0];
    const last = controls[controls.length - 1];
    const active = document.activeElement;
    if (first && ((!dialog.contains(active)) || (event.shiftKey ? active === first : active === last))) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    }
  });
  elements.timelineContainer.addEventListener("scroll", () => {
    const timeline = elements.timelineContainer;
    stickToBottom = timeline.scrollHeight - timeline.scrollTop - timeline.clientHeight < 80;
    elements.btnJumpLatest.hidden = stickToBottom || timeline.scrollHeight <= timeline.clientHeight + 80;
  }, { passive: true });
  window.addEventListener("agent-notification-settings-changed", () => { if (!disposed) refreshNotificationSettings(); });
  window.addEventListener("agent-share-inbox-changed", refreshShareInbox);
  window.addEventListener("agent-share-inbox-imported", refreshShareInbox);
  window.addEventListener("focus", refreshShareInbox);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshShareInbox(); });
  window.addEventListener("beforeunload", (event) => {
    if (fileDirty() && !persistFileDraft()) { event.preventDefault(); event.returnValue = ""; }
  });
  window.addEventListener("pagehide", () => { saveDraft(); persistFileDraft(); resetFilePreview(); artifactActions.clear(); disposed = true; });
  darkSchemeQuery?.addEventListener?.("change", syncSystemBars);
  window.visualViewport?.addEventListener("resize", resizeVisibleViewport);
  window.addEventListener("resize", resizeVisibleViewport);

  // Suggestion cards belong to an empty conversation only.
  const markEmptyConversation = () => { elements.appShell.dataset.empty = String(!!elements.timelineList.querySelector(":scope > .empty-state")); };
  new MutationObserver(markEmptyConversation).observe(elements.timelineList, { childList: true });
  markEmptyConversation();
  // The glass layout lets the timeline scroll under the header and dock, so it needs their sizes.
  if (typeof window.ResizeObserver === "function") {
    const chromeSize = new window.ResizeObserver(() => {
      elements.appShell.style.setProperty("--header-h", `${elements.mobileHeader.offsetHeight}px`);
      elements.appShell.style.setProperty("--dock-h", `${elements.bottomDock.offsetHeight}px`);
      if (stickToBottom) scrollToBottom(true);
    });
    chromeSize.observe(elements.mobileHeader);
    chromeSize.observe(elements.bottomDock);
  }

  applyAppearance();
  try { bridge?.setUiLanguage?.(preferences.language); } catch { /* Older APKs keep native text in Chinese. */ }
  resizeVisibleViewport();
  syncControls();
  (async () => { await loadSettings(); if (!disposed) await loadWorkspaces(); if (!disposed) await loadSessions(selectedSessionId); if (!disposed) refreshShareInbox(); })();
})();
