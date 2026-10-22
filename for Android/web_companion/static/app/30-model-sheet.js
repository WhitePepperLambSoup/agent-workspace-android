  function handleBack() {
    if (disposed) return false;
    // 长辈模式 stays on the back key: it only stops the reading (leaving needs the exit button).
    if (elderOn() && !$("elderScreen").hidden) { void stopReading(); return true; }
    if (closeAttachMenu()) return true;
    if (!$("sessionSheet").hidden) { closeSessionSheet(); return true; }
    if (closeModelSheet()) return true;
    if (closeDrawer()) return true;
    if (!layerOpen(elements.settingsOverlay)) return false;
    if (settingsPage === "files" && fileEditor && !fileSaving) { void loadWorkspaceFiles(workspacePath); return true; }
    if (settingsPage === "home") { closeMenu(); return true; }
    setSettingsPage(subPageParents[settingsPage] || "home");
    return true;
  }

  function openModelSettings() {
    if (disposed) return;
    if (!layerOpen(elements.settingsOverlay)) openMenu();
    setSettingsPage("model");
  }

  function closeMenu(options = {}) {
    if (!layerOpen(elements.settingsOverlay)) return false;
    if (settingsPage === "files" && !canLeaveFileEditor()) return false;
    if (settingsPage === "search") invalidateSearch();
    if (settingsPage === "tasks") taskCenterGeneration += 1;
    if (settingsPage === "files") { filesGeneration += 1; resetFilePreview(); }
    if (settingsPage === "usage") usageGeneration += 1;
    elements.appShell.inert = false;
    elements.btnSettings.setAttribute("aria-expanded", "false");
    elements.btnSettings.focus();
    if (options.instant) { motionApi()?.stop(elements.settingsOverlay); elements.settingsOverlay.hidden = true; delete elements.settingsOverlay.dataset.leaving; return true; }
    // A phone shows the menu as a bottom sheet, a wider screen as a side panel.
    const away = window.innerWidth < 600 ? "translateY(100%)" : "translateX(100%)";
    hideLayer(elements.settingsOverlay, (motion) => [
      motion.play(elements.settingsSheet, [{ transform: "none" }, { transform: away }], { duration: 240, easing: "cubic-bezier(.4, 0, .9, .55)", fill: "forwards" }),
      motion.play(elements.settingsBackdrop, [{ opacity: 1 }, { opacity: 0 }], { duration: 210, easing: "ease-out", fill: "forwards" }),
    ]);
    return true;
  }

  // ---- Quick model sheet ------------------------------------------------------------------------
  // The composer's model chip opens a small sheet: saved model profiles and a thinking-effort slider.
  // A cloud model takes the new effort at once (no engine restart). The top level lights up.
  const motionApi = () => window.MobileMotion;
  const sheet = {
    layer: $("modelSheet"), panel: $("modelSheetPanel"), backdrop: $("modelSheetBackdrop"), control: $("effortControl"),
    track: $("effortTrack"), thumb: $("effortThumb"), fill: $("effortFill"), value: $("effortValue"), hint: $("effortSheetHint"),
  };
  let effortLevels = [];
  let effortDrag = null;
  let lastExplicitEffort = "";

  function explicitEfforts(model) { return effortOrder.filter((value) => supportedEfforts(model).includes(value)); }
  function isTopEffort(model, effort) {
    const levels = explicitEfforts(model);
    return levels.length > 0 && effort === levels[levels.length - 1];
  }
  function layerOpen(layer) { return !layer.hidden && layer.dataset.leaving !== "true"; }
  function quickEffortBlocked() {
    return !!activeTask || isLoadingSession || isUploading || isPreparingSubmission || restartPending || localDeviceTesting || !settings.model;
  }

  // Shows a layer at once and lets motion.js play its entrance (when the script runs).
  function showLayer(layer, enter) {
    const motion = motionApi();
    if (motion) motion.stop(layer);
    delete layer.dataset.leaving;
    layer.hidden = false;
    if (motion && enter) enter(motion);
  }
  // Plays the exit, then hides; hides at once when nothing animates (motion off, no motion.js).
  function hideLayer(layer, leave) {
    const motion = motionApi();
    if (!motion || motion.level() === "off" || typeof layer.animate !== "function") { layer.hidden = true; return; }
    layer.dataset.leaving = "true";
    Promise.all(leave(motion)).then(() => {
      if (layer.dataset.leaving !== "true") return; // opened again meanwhile
      delete layer.dataset.leaving;
      layer.hidden = true;
      motion.stop(layer);
    });
  }

  function effortRatio(index) { return effortLevels.length <= 1 ? 1 : Math.max(0, index) / (effortLevels.length - 1); }

  function placeEffortThumb(ratio, animate) {
    const width = sheet.track.clientWidth;
    const knob = sheet.thumb.offsetWidth || 28;
    const x = Math.round(ratio * Math.max(0, width - knob));
    const thumbTo = `translateX(${x}px)`;
    const fillTo = `scaleX(${width ? Math.min(1, (x + knob / 2) / width).toFixed(4) : ratio})`;
    const thumbFrom = sheet.thumb.style.transform;
    const fillFrom = sheet.fill.style.transform;
    sheet.thumb.style.transform = thumbTo;
    sheet.fill.style.transform = fillTo;
    const motion = motionApi();
    if (!animate || !motion || !thumbFrom || thumbFrom === thumbTo) return;
    motion.play(sheet.thumb, [{ transform: thumbFrom }, { transform: thumbTo }], { spring: "bouncy" });
    motion.play(sheet.fill, [{ transform: fillFrom }, { transform: fillTo }], { spring: "bouncy" });
  }

  function renderEffortState(animate) {
    const index = effortLevels.indexOf(settings.reasoning_effort);
    const automatic = index < 0;
    const top = !automatic && isTopEffort(settings.model, settings.reasoning_effort);
    const blocked = quickEffortBlocked();
    sheet.control.dataset.auto = String(automatic);
    sheet.control.dataset.top = String(top);
    sheet.panel.dataset.top = String(top);
    sheet.control.dataset.disabled = String(blocked);
    sheet.control.style.setProperty("--effort", effortLevels.length ? effortRatio(index).toFixed(3) : "0");
    // "Automatic" already shows on its own button; the value then says who decides.
    sheet.value.textContent = automatic ? t("由模型决定") : effortLabels[settings.reasoning_effort];
    $("btnEffortAuto").setAttribute("aria-pressed", String(automatic));
    $("btnEffortAuto").disabled = blocked;
    sheet.track.setAttribute("aria-valuemax", String(Math.max(0, effortLevels.length - 1)));
    sheet.track.setAttribute("aria-valuenow", String(Math.max(0, index)));
    sheet.track.setAttribute("aria-valuetext", sheet.value.textContent);
    sheet.track.setAttribute("aria-disabled", String(blocked));
    sheet.track.tabIndex = blocked ? -1 : 0;
    [...$("effortLabels").children].forEach((label, position) => {
      label.toggleAttribute("data-active", position === index);
      label.disabled = blocked;
    });
    if (!effortLevels.length) pageStatus(sheet.hint, t("此模型使用自动思考强度"));
    else if (blocked && activeTask) pageStatus(sheet.hint, t("任务进行中，结束后再调整"));
    else if (!sheet.hint.classList.contains("error")) pageStatus(sheet.hint, "");
    // Automatic: the knob rests mid-track, dimmed, until a level is picked.
    placeEffortThumb(automatic ? 0.5 : effortRatio(index), animate);
  }

  function renderModelSheet() {
    $("modelSheetModel").textContent = settings.model || t("未配置模型");
    effortLevels = explicitEfforts(settings.model);
    if (effortLevels.includes(settings.reasoning_effort)) lastExplicitEffort = settings.reasoning_effort;
    const stops = $("effortStops");
    const labels = $("effortLabels");
    stops.replaceChildren();
    labels.replaceChildren();
    effortLevels.forEach((value, index) => {
      const stop = document.createElement("span");
      stop.className = "effort-stop";
      stop.style.left = `${(effortRatio(index) * 100).toFixed(2)}%`;
      stops.append(stop);
      const label = document.createElement("button");
      label.type = "button";
      label.className = "effort-label";
      label.tabIndex = -1;
      label.style.left = stop.style.left;
      label.textContent = effortLabels[value];
      label.addEventListener("click", () => chooseEffort(value));
      labels.append(label);
    });
    sheet.control.dataset.levels = String(effortLevels.length);
    pageStatus(sheet.hint, "");
    renderSheetProfiles();
    renderEffortState(false);
  }

  function renderSheetProfiles() {
    const row = $("modelSheetProfiles");
    let profiles = [];
    if (typeof bridge?.getProviderProfiles === "function") {
      try { profiles = bridgeResult("getProviderProfiles").profiles || []; } catch { profiles = []; }
    }
    row.replaceChildren();
    row.hidden = profiles.length < 2;
    for (const profile of profiles) {
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = "model-profile";
      pill.setAttribute("role", "radio");
      pill.setAttribute("aria-checked", String(!!profile.active));
      const name = document.createElement("strong");
      name.textContent = profile.name;
      const detail = document.createElement("small");
      detail.textContent = profile.local ? t("本机") : profile.model;
      pill.append(name, detail);
      pill.disabled = !profile.active && (!!activeTask || restartPending || (!profile.local && !profile.has_api_key));
      pill.addEventListener("click", () => { if (!profile.active) void switchProfileFromSheet(profile); });
      row.append(pill);
    }
  }

  // The provider's models in the sheet: what its own model list says (with what each can do), or
  // the built-in names until the list has been read. Picking one switches without a restart.
  function catalogModels() {
    const listed = Array.isArray(settings.model_catalog) ? settings.model_catalog.filter((item) => item && typeof item.id === "string") : [];
    const models = listed.length ? listed : (settings.models || []).map((id) => ({ id }));
    return models.some((item) => item.id === settings.model) || !settings.model ? models : [{ id: settings.model }, ...models];
  }

  function modelTags(model) {
    const tokens = Number(model.context_tokens) || 0;
    return [
      model.name && model.name !== model.id ? model.name : "",
      model.vision ? t("看图") : "",
      model.tools ? t("工具调用") : "",
      model.reasoning ? t("推理") : "",
      tokens ? t("{0} 上下文", tokens >= 1000000 ? `${Math.round(tokens / 1000000)}M` : `${Math.round(tokens / 1000)}K`) : "",
    ].filter(Boolean).join(" · ");
  }

  function toggleModelPicker(open = $("modelSheetPicker").hidden) {
    $("modelSheetPicker").hidden = !open;
    $("modelSheetModel").setAttribute("aria-expanded", String(open));
    if (!open) return;
    $("modelSheetSearch").value = "";
    renderModelPicker();
    const fetchedAt = Number(settings.model_catalog_fetched_at) || 0;
    // A list never read, or read more than a day ago, is read again in the background.
    if (typeof bridge?.refreshProviderModels === "function" && settings.has_api_key && !isLocalModel()
        && Date.now() - fetchedAt > 24 * 60 * 60 * 1000) {
      void refreshProviderModels($("modelSheetListStatus")).then((done) => { if (done && !$("modelSheetPicker").hidden) renderModelPicker(); });
    }
  }

  function renderModelPicker() {
    const list = $("modelSheetList");
    const query = $("modelSheetSearch").value.trim().toLowerCase();
    const models = catalogModels().filter((item) => !query || item.id.toLowerCase().includes(query)
      || String(item.name || "").toLowerCase().includes(query));
    list.replaceChildren();
    for (const model of models.slice(0, 300)) {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "model-option";
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", String(model.id === settings.model));
      option.disabled = !!activeTask || restartPending;
      const name = document.createElement("strong");
      name.textContent = model.id;
      option.append(name);
      const tags = modelTags(model);
      if (tags) { const detail = document.createElement("small"); detail.textContent = tags; option.append(detail); }
      option.addEventListener("click", () => void chooseModelFromSheet(model.id));
      list.append(option);
    }
    if (!models.length) pageStatus($("modelSheetListStatus"), query ? t("没有匹配的模型") : t("还没有模型列表，点右上角从服务商获取"));
    else if (activeTask) pageStatus($("modelSheetListStatus"), t("任务进行中，结束后再换模型"));
  }

  function isLocalModel() {
    return String(settings.base_url || "").replace(/\/+$/, "").endsWith("/embedded-qwen/v1");
  }

  /** Reads the provider's model list through the app (in the background) and reloads the settings. */
  async function refreshProviderModels(status) {
    if (typeof bridge?.refreshProviderModels !== "function") return false;
    pageStatus(status, t("正在从服务商获取模型列表…"));
    try { JSON.parse(bridge.refreshProviderModels()); } catch { pageStatus(status, t("无法获取模型列表"), true); return false; }
    for (let attempt = 0; attempt < 80; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, 400));
      let state;
      try { state = JSON.parse(bridge.getProviderModelsStatus()); } catch { state = { state: "error" }; }
      if (state.state === "fetching") continue;
      if (state.state !== "done") { pageStatus(status, localizeError(state.error) || t("无法获取模型列表"), true); return false; }
      await loadSettings();
      pageStatus(status, t("已获取 {0} 个模型", state.count));
      return true;
    }
    pageStatus(status, t("获取模型列表超时"), true);
    return false;
  }

  async function chooseModelFromSheet(model) {
    if (model === settings.model || activeTask || restartPending || typeof bridge?.applyRuntimeSettings !== "function") return;
    flushQuickEffort();
    const possible = supportedEfforts(model);
    const effort = possible.includes(settings.reasoning_effort) ? settings.reasoning_effort : "auto";
    let result;
    try {
      result = JSON.parse(bridge.applyRuntimeSettings(JSON.stringify({ model, reasoning_effort: effort })));
      if (!result.ok) throw new Error(localizeError(result.error) || t("无法切换模型"));
    } catch (error) { pageStatus($("modelSheetListStatus"), error.message, true); return; }
    haptic(12);
    writeStorage(runtimeChoiceKey, { protocol: settings.protocol, base_url: settings.base_url, model, reasoning_effort: effort });
    if (result.restarting === false) {
      await loadSettings();
      if (!layerOpen(sheet.layer)) return;
      renderModelSheet();
      renderModelPicker();
      notice(t("已切换到 {0}，无需重启", model), "info");
      return;
    }
    restartPending = true;
    notice(t("设置已保存，正在重新连接..."), "info");
    closeModelSheet();
  }

  async function switchProfileFromSheet(profile) {
    if (activeTask || restartPending) return;
    flushQuickEffort();
    let result;
    try { result = bridgeResult("switchProviderProfile", profile.id); }
    catch (error) { pageStatus(sheet.hint, error.message, true); return; }
    haptic(12);
    if (result.restarting === false) {
      await loadSettings();
      if (!layerOpen(sheet.layer)) return;
      renderModelSheet();
      motionApi()?.play($("modelSheetModel"), [{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }], { spring: "snappy" });
      notice(t("已切换到 {0}", profile.name), "info");
      return;
    }
    restartPending = true;
    notice(t("正在切换到 {0}，引擎需要重启...", profile.name), "info");
    closeModelSheet();
  }

  // The app saves the effort through a synchronous bridge call that takes ~140 ms on a phone, which
  // would freeze the slider's animation. The page takes the new level at once (each task also sends
  // it), and the app is told a moment later, once per burst of changes; sending a task flushes it.
  let pendingEffort = null;
  let pendingEffortTimer = 0;

  function rememberEffort(effort) {
    settings.reasoning_effort = effort;
    writeStorage(runtimeChoiceKey, { protocol: settings.protocol, base_url: settings.base_url, model: settings.model, reasoning_effort: effort });
    renderSettings();
  }

  function applyQuickEffort(effort) {
    if (effort === settings.reasoning_effort) return;
    if (typeof bridge?.applyRuntimeSettings === "function") {
      pendingEffort = { effort, model: settings.model, previous: pendingEffort ? pendingEffort.previous : settings.reasoning_effort };
      clearTimeout(pendingEffortTimer);
      pendingEffortTimer = setTimeout(flushQuickEffort, 650);
    }
    rememberEffort(effort);
  }

  function flushQuickEffort() {
    clearTimeout(pendingEffortTimer);
    const pending = pendingEffort;
    pendingEffort = null;
    if (!pending || disposed || pending.model !== settings.model) return;
    try {
      const result = JSON.parse(bridge.applyRuntimeSettings(JSON.stringify({ model: pending.model, reasoning_effort: pending.effort })));
      if (!result.ok) throw new Error(localizeError(result.error) || t("无法保存设置"));
      if (result.restarting !== false) {
        restartPending = true;
        notice(t("设置已保存，正在重新连接..."), "info");
      }
    } catch (error) {
      rememberEffort(pending.previous);
      if (layerOpen(sheet.layer)) { renderEffortState(true); pageStatus(sheet.hint, error.message, true); }
      else notice(error.message);
    }
  }

  function chooseEffort(effort) {
    if (quickEffortBlocked()) { renderEffortState(true); return; }
    const wasTop = isTopEffort(settings.model, settings.reasoning_effort);
    pageStatus(sheet.hint, "");
    applyQuickEffort(effort);
    if (effortLevels.includes(effort)) lastExplicitEffort = effort;
    renderEffortState(true);
    const top = isTopEffort(settings.model, effort);
    if (top && !wasTop) celebrateTopEffort();
    else if (effort !== "auto") motionApi()?.play(sheet.value, [{ opacity: 0.4, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }], { spring: "snappy" });
    haptic(top ? 28 : 10);
  }

  // The top level: sparks burst from the knob and the label pops; the track's aurora runs in CSS.
  function celebrateTopEffort() {
    const motion = motionApi();
    if (!motion || motion.level() !== "full") return;
    requestAnimationFrame(() => {
      motion.sparks(sheet.thumb, { count: 18, spread: 84 });
      motion.play(sheet.value, [{ transform: "scale(1)" }, { transform: "scale(1.28)", offset: 0.35 }, { transform: "scale(1)" }], { duration: 560, easing: "cubic-bezier(.3, 1.5, .5, 1)" });
      motion.play(sheet.panel.querySelector(".model-sheet-glow"), [{ opacity: 0, transform: "scaleY(.4)" }, { opacity: 1, transform: "none" }], { spring: "gentle", fill: "none" });
    });
  }

  function effortIndexAt(clientX) {
    const box = sheet.track.getBoundingClientRect();
    const knob = sheet.thumb.offsetWidth || 28;
    const ratio = Math.min(1, Math.max(0, (clientX - box.left - knob / 2) / Math.max(1, box.width - knob)));
    return { ratio, index: effortLevels.length <= 1 ? 0 : Math.round(ratio * (effortLevels.length - 1)) };
  }

  sheet.track.addEventListener("pointerdown", (event) => {
    if (!effortLevels.length || quickEffortBlocked() || (event.button !== undefined && event.button !== 0)) return;
    const { ratio, index } = effortIndexAt(event.clientX);
    effortDrag = { pointer: event.pointerId, index, moved: false, startX: event.clientX };
    try { sheet.track.setPointerCapture(event.pointerId); } catch { /* released already */ }
    sheet.control.dataset.dragging = "true";
    motionApi()?.stop(sheet.thumb);
    motionApi()?.stop(sheet.fill);
    placeEffortThumb(ratio, false);
    previewEffort(index);
    event.preventDefault();
  });
  sheet.track.addEventListener("pointermove", (event) => {
    if (!effortDrag || event.pointerId !== effortDrag.pointer) return;
    if (Math.abs(event.clientX - effortDrag.startX) > 4) effortDrag.moved = true;
    const { ratio, index } = effortIndexAt(event.clientX);
    placeEffortThumb(ratio, false);
    if (index !== effortDrag.index) { effortDrag.index = index; previewEffort(index); haptic(6); }
  });
  for (const type of ["pointerup", "pointercancel"]) {
    sheet.track.addEventListener(type, (event) => {
      if (!effortDrag || event.pointerId !== effortDrag.pointer) return;
      const { index } = effortDrag;
      effortDrag = null;
      delete sheet.control.dataset.dragging;
      delete sheet.control.dataset.preview;
      if (type === "pointercancel") { renderEffortState(true); return; }
      if (effortLevels[index] === settings.reasoning_effort) renderEffortState(true);
      else chooseEffort(effortLevels[index]);
    });
  }
  // While the finger moves, the label and colors follow the level under it; nothing is saved yet.
  function previewEffort(index) {
    const value = effortLevels[index];
    sheet.value.textContent = effortLabels[value];
    sheet.control.dataset.preview = isTopEffort(settings.model, value) ? "top" : "level";
    sheet.control.style.setProperty("--effort", effortRatio(index).toFixed(3));
    [...$("effortLabels").children].forEach((label, position) => label.toggleAttribute("data-active", position === index));
  }
  sheet.track.addEventListener("keydown", (event) => {
    if (!effortLevels.length || quickEffortBlocked()) return;
    const index = Math.max(0, effortLevels.indexOf(settings.reasoning_effort));
    const next = { ArrowLeft: index - 1, ArrowDown: index - 1, ArrowRight: index + 1, ArrowUp: index + 1, Home: 0, End: effortLevels.length - 1 }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const clamped = Math.min(effortLevels.length - 1, Math.max(0, next));
    if (effortLevels[clamped] !== settings.reasoning_effort) chooseEffort(effortLevels[clamped]);
  });
  $("btnEffortAuto").addEventListener("click", () => {
    if (settings.reasoning_effort !== "auto") { chooseEffort("auto"); return; }
    const fallback = effortLevels.includes(lastExplicitEffort) ? lastExplicitEffort : effortLevels[Math.floor((effortLevels.length - 1) / 2)];
    if (fallback) chooseEffort(fallback);
  });

  function openModelSheet() {
    if (disposed || layerOpen(sheet.layer)) return;
    if (layerOpen(elements.settingsOverlay) && !closeMenu()) return;
    closeAttachMenu();
    closeDrawer();
    toggleModelPicker(false);
    showLayer(sheet.layer);
    renderModelSheet();
    elements.appShell.inert = true;
    elements.modelBar.setAttribute("aria-expanded", "true");
    const motion = motionApi();
    if (motion) {
      const glass = document.documentElement.dataset.style === "glass";
      // Glass slides without fading: fading a pane that filters its backdrop costs a full offscreen render per frame.
      motion.play(sheet.panel, [{ transform: `translateY(${Math.min(sheet.panel.offsetHeight + 24, 420)}px)`, ...(glass ? {} : { opacity: 0.6 }) }, { transform: "none", opacity: 1 }], { spring: "bouncy" });
      motion.play(sheet.backdrop, [{ opacity: 0 }, { opacity: 1 }], { duration: 220, easing: "ease-out" });
      motion.stagger(sheet.panel.querySelectorAll(".model-sheet-header, .model-sheet-profiles:not([hidden]), .effort-head, .effort-track, .effort-labels"),
        { transform: "translateY(14px)" }, { delay: 50, step: 32, spring: "bouncy" });
      if (sheet.control.dataset.top === "true") celebrateTopEffort();
    }
    (sheet.track.tabIndex >= 0 ? sheet.track : $("btnModelSheetMore")).focus({ preventScroll: true });
    haptic(12);
  }

  function closeModelSheet(options = {}) {
    if (!layerOpen(sheet.layer)) return false;
    effortDrag = null;
    elements.appShell.inert = false;
    elements.modelBar.setAttribute("aria-expanded", "false");
    if (!options.keepFocus) elements.modelBar.focus({ preventScroll: true });
    if (options.instant) { motionApi()?.stop(sheet.layer); sheet.layer.hidden = true; delete sheet.layer.dataset.leaving; return true; }
    hideLayer(sheet.layer, (motion) => [
      motion.play(sheet.panel, [{ transform: "none" }, { transform: `translateY(${sheet.panel.offsetHeight + 24}px)` }], { duration: 230, easing: "cubic-bezier(.4, 0, .9, .55)", fill: "forwards" }),
      motion.play(sheet.backdrop, [{ opacity: 1 }, { opacity: 0 }], { duration: 210, easing: "ease-out", fill: "forwards" }),
    ]);
    return true;
  }

  sheet.backdrop.addEventListener("click", () => closeModelSheet());
  $("btnModelSheetMore").addEventListener("click", () => { flushQuickEffort(); closeModelSheet({ instant: true, keepFocus: true }); openModelSettings(); });
  $("modelSheetModel").addEventListener("click", () => toggleModelPicker());
  $("modelSheetSearch").addEventListener("input", () => renderModelPicker());
  $("btnModelSheetRefresh").addEventListener("click", () => {
    void refreshProviderModels($("modelSheetListStatus")).then((done) => { if (done) renderModelPicker(); });
  });
  motionApi()?.draggable(sheet.panel, {
    axis: "y", extras: [sheet.backdrop],
    canStart: (event) => !event.target.closest(".effort-track, .model-sheet-profiles, .model-sheet-picker"),
    onDismiss: () => closeModelSheet({ instant: true }),
  });
  // The drawer follows a leftward swipe; the phone's bottom-sheet menu follows a pull on its header.
  motionApi()?.draggable(elements.sessionDrawerPanel, {
    axis: "x-", extras: [elements.sessionDrawerBackdrop],
    canStart: (event) => !event.target.closest(".drawer-workspaces, input, textarea, select"),
    onDismiss: () => closeDrawer({ instant: true }),
  });
  motionApi()?.draggable(elements.settingsSheet, {
    axis: "y", handle: elements.settingsSheet.querySelector(".sheet-header"), extras: [elements.settingsBackdrop],
    canStart: () => window.innerWidth < 600,
    onDismiss: () => closeMenu({ instant: true }),
  });
  window.addEventListener("resize", () => { if (layerOpen(sheet.layer) && !effortDrag) renderEffortState(false); });

  function receiveSharedText(text) {
    if (disposed || typeof text !== "string") return false;
    if (!text.trim() || text.length > maxSharedTextLength) return false;
    if (!currentSessionId || isLoadingSession || isPreparingSubmission || !historyReady) return false;
    // Said on the 长辈模式 screen: it goes out from there (90-elder.js).
    if (elderHeard(text)) return true;
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
    // A shared link can also be saved to the knowledge base (management.js offers it).
    window.dispatchEvent(new window.CustomEvent("agent-shared-text", { detail: text }));
    // In a voice conversation what was said goes out at once (the reply is read aloud, then it listens again).
    if (voiceConversation && !activeTask) { voiceTurnPending = true; window.setTimeout(() => { void sendPrompt(); }, 0); }
    return true;
  }

  // Global entries (quick settings tile, floating ball, launcher shortcuts) open a fresh conversation.
  // A floating-ball screenshot arrives in the attachment inbox and is attached to that conversation.
  let quickShareBatch = null;
  let quickShareDeadline = 0;
  // A finished voice note (the app's recorder checked its token): once its recording is attached,
  // the minutes request is sent without waiting for the user.
  let quickNote = null;
  function quickAsk(options = {}) {
    if (disposed || isLoadingSession || !historyReady || sessionOpening || isPreparingSubmission || !canLeaveFileEditor()) return false;
    const mode = ["text", "voice", "camera", "screen", "note"].includes(options?.mode) ? options.mode : "text";
    const batch = typeof options?.share_batch === "string" && options.share_batch ? options.share_batch : null;
    quickNote = mode === "note" && batch ? { batch, attached: false, deadline: Date.now() + 120000 } : null;
    closeMenu();
    closeDrawer();
    // Reuse the current conversation while it is still empty instead of piling up blank ones.
    const empty = !activeTask && !timelineMessages().length;
    const text = typeof options?.text === "string" ? options.text.slice(0, 8000) : "";
    void (empty ? Promise.resolve(true) : createSession()).then((ready) => {
      if (disposed) return;
      // Claim the screenshot only once its conversation is open: the inbox can finish receiving it
      // first, and it would then be attached to the conversation that was open before. If the new
      // conversation could not be created, the screenshot waits in the inbox.
      if (batch && ready !== false) {
        quickShareBatch = batch;
        quickShareDeadline = Date.now() + 60000;
      }
      if (text && !elements.promptInput.value.trim()) {
        elements.promptInput.value = text;
        elements.promptInput.dispatchEvent(new Event("input", { bubbles: true }));
      }
      if (mode === "voice" && typeof bridge?.requestVoiceInput === "function") bridge.requestVoiceInput();
      else if (mode === "camera" && typeof bridge?.captureShareInboxPhoto === "function") $("btnAttachCamera").click();
      else elements.promptInput.focus();
      if (quickShareBatch) refreshShareInbox();
    });
    return true;
  }

