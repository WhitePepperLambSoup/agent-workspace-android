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

  // Share of input tokens the provider served from its prompt cache (billed far cheaper).
  function cacheHitRate(record) {
    const input = Number(record?.input_tokens) || 0;
    if (input <= 0) return "—";
    return `${(Math.min(Number(record.cached_tokens) || 0, input) / input * 100).toFixed(1)}%`;
  }

  function renderUsage(data) {
    elements.usageSummary.replaceChildren();
    elements.usageModelsList.replaceChildren();
    const totals = data.totals || {};
    const values = [
      [t("模型调用"), tokenCount(totals.model_calls)], [t("总 Token"), tokenCount(totals.total_tokens)],
      [t("输入 Token"), tokenCount(totals.input_tokens)], [t("输出 Token"), tokenCount(totals.output_tokens)],
      [t("缓存输入 Token"), tokenCount(totals.cached_tokens)], [t("缓存命中率"), cacheHitRate(totals)],
      [t("预估费用（USD）"), estimatedCost(totals)],
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
    // What the calls were for: the conversations, summaries of long ones, and sub-tasks.
    const purposeNames = { conversation: t("对话"), summary: t("摘要压缩"), subagent: t("子任务") };
    const purposes = (Array.isArray(data.purposes) ? data.purposes : []).filter((share) => purposeNames[share?.purpose]);
    if (purposes.length > 1) {
      for (const share of purposes) {
        const term = document.createElement("dt");
        term.textContent = t("其中{0}", purposeNames[share.purpose]);
        const detail = document.createElement("dd");
        detail.textContent = t("{0} Token · {1}", tokenCount(share.total_tokens), estimatedCost(share));
        elements.usageSummary.append(term, detail);
      }
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
      counts.textContent = t("{0} 次调用 · {1} Token", tokenCount(record.model_calls), tokenCount(record.total_tokens))
        + (record.pricing?.source !== "on_device" && Number(record.input_tokens) > 0 ? t(" · 缓存命中 {0}", cacheHitRate(record)) : "");
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

  // ---- Saved model profiles (Android) ----
  function bridgeResult(method, ...args) {
    const result = JSON.parse(bridge[method](...args));
    if (!result.ok) throw new Error(localizeError(result.error) || t("操作失败"));
    return result;
  }

  function renderProfiles() {
    const section = $("profileSection");
    section.hidden = typeof bridge?.getProviderProfiles !== "function";
    if (section.hidden) return;
    let data;
    try { data = bridgeResult("getProviderProfiles"); }
    catch (error) { pageStatus($("profileStatus"), error.message, true); return; }
    const list = $("profileList");
    list.replaceChildren();
    for (const profile of data.profiles || []) {
      const row = document.createElement("div");
      row.className = "management-row profile-row";
      if (profile.active) row.setAttribute("aria-current", "true");
      const body = document.createElement("div");
      body.className = "management-row-body";
      const title = document.createElement("strong");
      title.textContent = profile.name;
      const detail = document.createElement("small");
      let host = profile.base_url;
      try { host = new URL(profile.base_url).host; } catch {}
      detail.textContent = [profile.model, profile.local ? t("本机") : host,
        profile.active ? t("使用中") : "", !profile.local && !profile.has_api_key ? t("未设置密钥") : ""].filter(Boolean).join(" · ");
      body.append(title, detail);
      const use = document.createElement("button");
      use.type = "button";
      use.className = "button-secondary profile-use";
      use.textContent = profile.active ? t("使用中") : t("切换");
      use.disabled = !!profile.active || !!activeTask || restartPending;
      use.addEventListener("click", () => switchProfile(profile));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "icon-button";
      remove.title = t("删除");
      remove.setAttribute("aria-label", t("删除"));
      remove.innerHTML = icon("trash-2");
      remove.addEventListener("click", () => {
        if (!window.confirm(t("删除模型配置“{0}”？密钥不会被删除。", profile.name))) return;
        try { bridgeResult("deleteProviderProfile", profile.id); renderProfiles(); }
        catch (error) { pageStatus($("profileStatus"), error.message, true); }
      });
      row.append(body, use, remove);
      list.append(row);
    }
    if (!(data.profiles || []).length) {
      const empty = document.createElement("p");
      empty.className = "setting-hint";
      empty.textContent = t("还没有保存的配置。设置好服务商和模型后，点下面的按钮保存。");
      list.append(empty);
    }
    $("btnSaveProfile").disabled = (data.profiles || []).length >= (data.max_profiles || 20) && !(data.profiles || []).some((item) => item.active);
  }

  async function switchProfile(profile) {
    if (activeTask || restartPending) return;
    pageStatus($("profileStatus"), t("正在切换到 {0}...", profile.name));
    let result;
    try { result = bridgeResult("switchProviderProfile", profile.id); }
    catch (error) { pageStatus($("profileStatus"), error.message, true); return; }
    if (result.restarting === false) {
      await loadSettings();
      renderProfiles();
      pageStatus($("profileStatus"), t("已切换到 {0}，无需重启", profile.name));
      notice(t("已切换到 {0}", profile.name), "info");
      return;
    }
    restartPending = true;
    notice(t("正在切换到 {0}，引擎需要重启...", profile.name), "info");
    closeMenu();
  }

  async function applyRuntimeSettings() {
    flushQuickEffort();
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
        if (result.restarting === false) notice(t("已切换到 {0}，无需重启", model), "info");
        else {
          restartPending = true;
          notice(t("设置已保存，正在重新连接..."), "info");
        }
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
    pageStatus(pending.status, result.cancelled ? "" : result.ok ? (pending.action === "save" ? t("已保存")
      : pending.action === "home_tool" ? homeToolAdded(result) : "") : localizeError(result.error) || t("文件操作失败"), !result.ok && !result.cancelled);
  });

