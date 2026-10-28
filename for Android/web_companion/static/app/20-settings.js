  function syncKeepScreenOn() {
    const wanted = !!activeTask?.id && experimentalLocalSummary(settings.base_url);
    if (wanted === keepingScreenOn || typeof bridge?.setKeepScreenOn !== "function") return;
    keepingScreenOn = wanted;
    try { bridge.setKeepScreenOn(wanted); } catch { keepingScreenOn = !wanted; }
  }

  function syncControls() {
    if (disposed) return;
    const busy = !!activeTask || isLoadingSession || restartPending || isPreparingSubmission || localDeviceTesting;
    elements.appShell.dataset.busy = String(!!activeTask);
    syncKeepScreenOn();
    // 长辈模式's big button speaks, or stops while an answer is coming (90-elder.js).
    if (elderShown()) renderElderButton();
    syncCostEstimate();
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
    // Edit and regenerate need an idle conversation; regenerate is offered on the latest reply only.
    const replies = [...elements.timelineList.querySelectorAll(".message-card.assistant")].filter((card) => !card.hidden);
    elements.timelineList.querySelectorAll(".btn-edit, .btn-regenerate").forEach((button) => {
      button.disabled = busy || !historyReady || !currentSessionId;
      if (button.classList.contains("btn-regenerate")) button.hidden = button.closest(".message-card") !== replies[replies.length - 1];
    });
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
    $("btnDeleteSession").disabled = !currentSessionId || isLoadingSession || !!activeTask;
    syncFileControls();
    syncWorkspaceControls();
    syncImportControls();
    syncDrawerControls(navigationBusy);
    if (!$("modelSheet").hidden && !effortDrag) renderEffortState(false);
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
    // The chip keeps a colored rim while the model thinks at its highest level.
    elements.modelBar.dataset.top = String(isTopEffort(settings.model, settings.reasoning_effort));
    // No model can answer yet (a new install): the chip asks for one (app/27-setup.js).
    const needsSetup = !!setupNeeded();
    elements.modelBar.dataset.setup = String(needsSetup);
    if (needsSetup) elements.modelSummary.textContent = t("选择模型");
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
      : t("临近容量时由当前模型（或下面设的摘要模型）总结较早记录。会额外调用模型，可能产生 Token 费用；摘要可能遗漏细节，原始会话仍保留。");
    setLocalContextDraft(settings.local_context_tokens);
    elements.localMemorySelector.value = settings.local_memory_mode;
    elements.localThreadsInput.value = String(settings.local_threads);
    elements.localTimeoutInput.value = String(settings.local_timeout_seconds);
    elements.autonomyHint.textContent = typeof bridge?.applyRuntimeSettings === "function"
      ? t("更改执行模式会重新启动本地引擎")
      : t("请在 Android 应用中更改执行模式");
    elements.btnProviderSettings.hidden = typeof bridge?.openSettings !== "function";
    $("btnRefreshModels").hidden = typeof bridge?.refreshProviderModels !== "function" || isLocalModel();
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

  // Sub-pages return to their parent page rather than to the menu.
  const subPageParents = { pricing: "usage", quickTasks: "appearance", computer: "connections" };

  function setSettingsPage(page, initial = false) {
    if (settingsPage === "files" && page !== "files" && !canLeaveFileEditor()) return false;
    const previousPage = settingsPage;
    const movingBack = (page === "home" && previousPage !== "home") || subPageParents[previousPage] === page;
    if (!initial && page !== previousPage) settingsScrollPositions.set(previousPage, elements.settingsScrollBody.scrollTop);
    if (settingsPage === "search" && page !== "search") invalidateSearch();
    if (settingsPage === "tasks" && page !== "tasks") taskCenterGeneration += 1;
    if (settingsPage === "files" && page !== "files") { filesGeneration += 1; resetFilePreview(); }
    if (settingsPage === "usage" && page !== "usage") usageGeneration += 1;
    settingsPage = page;
    const titles = { home: t("菜单"), model: t("模型与思考"), permission: t("执行权限"), appearance: t("界面偏好"), search: t("搜索会话"), tasks: t("任务中心"), files: t("工作区文件"), attachments: t("附件收件箱"), session: t("会话名称"), notifications: t("通知"), usage: t("Token 与费用"), pricing: t("模型费率"), doctor: t("设备与工具"), extensions: t("MCP 与扩展"), skills: t("技能"), schedules: t("定时任务"), connections: t("设备连接"), computer: t("电脑"), outbox: t("待发送与接力"), workflows: t("可复用流程"), evaluations: t("任务评测"), localModels: t("本地模型"), workspaces: t("工作区"), quickTasks: t("快捷任务"), memory: t("记忆"), knowledge: t("知识库"), conversationKnowledge: t("本对话的知识库"), services: t("后台服务"), globalEntry: t("全局入口"), notificationRules: t("通知触发"), backup: t("备份与恢复"), about: t("关于与更新"), elder: t("长辈模式"), appCheck: t("应用体检") };
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
    // The local models page tunes the engine under its collapsed 高级设置 only.
    elements.settingsActions.hidden = !["model", "permission", "localModels"].includes(page) || (page === "localModels" && !$("localAdvanced")?.open);
    elements.btnApplySettings.textContent = page === "permission" ? t("应用执行模式") : page === "localModels" ? t("应用本机设置") : t("应用设置");
    elements.settingsError.hidden = true;
    if (page === "model") {
      renderProfiles();
      elements.modelInput.value = settings.model;
      fillEffortOptions(settings.model, settings.reasoning_effort);
      elements.contextSummaryToggle.checked = settings.context_summary_enabled;
      contextSummaryDirty = false;
      void loadModelRoles();
      void loadTaskLimits();
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
    if (page === "attachments") {
      // Opening the page targets the open conversation again, not the one chosen last time.
      if (previousPage !== "attachments") {
        shareTargetChoice = null;
        if (!importWatch) pageStatus(elements.shareInboxStatus, "");
      }
      refreshShareInbox();
    }
    if (page === "workspaces") { renderWorkspaceNavigation(); refreshWorkspaceAccess(); void loadWorkspaces(); }
    if (page === "files") {
      renderHomeTools();
      if (fileEditor?.loaded) renderFileEditor();
      else void loadWorkspaceFiles(workspacePath);
    }
    if (page === "session") {
      elements.sessionTitleInput.value = sessions.find((session) => session.id === currentSessionId)?.title || "";
      pageStatus(elements.sessionRenameStatus, "");
    }
    if (page === "notifications") refreshNotificationSettings();
    if (page === "usage") void loadUsage();
    if (page === "quickTasks") { closeQuickTaskForm(); renderQuickTaskEditor(); }
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
    if (disposed || layerOpen(elements.settingsOverlay)) return;
    closeModelSheet({ instant: true, keepFocus: true });
    showLayer(elements.settingsOverlay);
    elements.appShell.inert = true;
    elements.btnSettings.setAttribute("aria-expanded", "true");
    settingsScrollPositions.clear();
    setSettingsPage("home", true);
    haptic();
  }

  // Android back: leave the open file, then the sub page, then the sheet itself.
