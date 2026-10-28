  // ---- First use: choosing the model ---------------------------------------------------------------
  // A new install has no model that can answer: the default provider has no key, so the first
  // message came back as an English 401, after an approval for api.openai.com that a new user
  // cannot judge. This sheet comes first instead: a cloud provider and its key (tried before it is
  // saved), or a model on the phone, downloaded and switched to in one step.
  const setupSeenKey = "agent-mobile-setup-v1";
  // What waits for the engine to restart or a download to finish: { local } a model to switch to
  // once downloaded, { prepare } a model just switched to, { trust } a provider just set up.
  const setupPendingKey = "agent-mobile-setup-pending-v1";
  const setupProviders = [
    { id: "deepseek", name: "DeepSeek", note: t("国内可以直接使用，价格低。"), protocol: "openai-compatible",
      base_url: "https://api.deepseek.com", model: "deepseek-flash", key_url: "https://platform.deepseek.com/api_keys" },
    { id: "qwen", name: t("通义千问（阿里云百炼）"), note: t("国内可以直接使用。"), protocol: "openai-compatible",
      base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen3.8-flash", key_url: "https://bailian.console.aliyun.com/" },
    { id: "glm", name: t("智谱 GLM"), note: t("国内可以直接使用。"), protocol: "openai-compatible",
      base_url: "https://open.bigmodel.cn/api/paas/v4", model: "glm-5.3-flash", key_url: "https://open.bigmodel.cn/usercenter/apikeys" },
    { id: "openai", name: "OpenAI", note: t("需要能访问 OpenAI 的网络。"), protocol: "openai-compatible",
      base_url: "https://api.openai.com/v1", model: "", key_url: "https://platform.openai.com/api-keys" },
    { id: "anthropic", name: "Claude (Anthropic)", note: t("需要能访问 Anthropic 的网络。"), protocol: "anthropic",
      base_url: "https://api.anthropic.com/v1", model: "claude-sonnet-5-5", key_url: "https://console.anthropic.com/settings/keys" },
    { id: "gemini", name: "Gemini (Google)", note: t("需要能访问 Google 的网络。"), protocol: "gemini",
      base_url: "https://generativelanguage.googleapis.com/v1beta", model: "gemini-3.8-flash", key_url: "https://aistudio.google.com/apikey" },
  ];
  // On the phone, in order of preference: the small one answers in seconds once prepared.
  const setupLocalModels = ["qwen3.5-0.8b-q4-k-m", "qwen3.5-2b-q4-k-m"];
  const setupActiveDownload = ["queued", "downloading", "waiting_network", "verifying"];
  let setupChoice = null;
  let setupLocal = null;
  let setupPoll = 0;
  let setupPendingPoll = 0;

  function hostOf(address) {
    try { return new URL(address).hostname; } catch { return ""; }
  }

  /** Why no model can answer yet ("" when one can, or when this page cannot tell). */
  function setupNeeded() {
    if (!settingsAvailable || typeof bridge?.saveQuickProvider !== "function" || isLocalModel()) return "";
    const host = hostOf(settings.base_url);
    // Ollama and other services on this phone or the home network need no key.
    if (settings.protocol === "ollama" || /^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host)) return "";
    return settings.has_api_key ? "" : "no_key";
  }

  function readPending() { const value = readStorage(setupPendingKey, null); return value && typeof value === "object" ? value : null; }

  function openSetup(reason = "") {
    const layer = $("setupSheet");
    if (disposed || layerOpen(layer) || typeof bridge?.saveQuickProvider !== "function") return false;
    closeModelSheet({ instant: true });
    closeMenu({ instant: true });
    closeAttachMenu();
    closeDrawer();
    $("setupSheetLead").textContent = reason === "send"
      ? t("还没有选好模型，AI 没法回答。先选一个，你写的消息会留在输入框里。")
      : t("先选一个模型，AI 才能回答。以后可以点输入框下面的模型按钮更换。");
    renderSetupProviders();
    pageStatus($("setupStatus"), "");
    const pending = readPending();
    chooseSetup(pending?.local ? "local" : setupChoice);
    showLayer(layer, (motion) => {
      motion.play($("setupSheetPanel"), [{ transform: "translateY(60px)", opacity: 0.6 }, { transform: "none", opacity: 1 }], { spring: "bouncy" });
      motion.play($("setupSheetBackdrop"), [{ opacity: 0 }, { opacity: 1 }], { duration: 220, easing: "ease-out" });
    });
    elements.appShell.inert = true;
    writeStorage(setupSeenKey, true);
    return true;
  }

  function closeSetup() {
    const layer = $("setupSheet");
    if (!layerOpen(layer)) return false;
    clearTimeout(setupPoll);
    elements.appShell.inert = false;
    hideLayer(layer, (motion) => [
      motion.play($("setupSheetPanel"), [{ transform: "none" }, { transform: "translateY(100%)" }], { duration: 230, easing: "cubic-bezier(.4, 0, .9, .55)", fill: "forwards" }),
      motion.play($("setupSheetBackdrop"), [{ opacity: 1 }, { opacity: 0 }], { duration: 210, easing: "ease-out", fill: "forwards" }),
    ]);
    // A download started here goes on; the page switches to the model once it is in.
    if (readPending()?.local) watchPendingLocal();
    return true;
  }

  function renderSetupProviders() {
    const select = $("setupProvider");
    if (!select.options.length) {
      for (const provider of setupProviders) {
        const option = document.createElement("option");
        option.value = provider.id;
        option.textContent = provider.name;
        select.append(option);
      }
      // Chinese readers get one that works on networks in China.
      select.value = locale.startsWith("zh") ? "deepseek" : "openai";
    }
    const provider = setupProviders.find((item) => item.id === select.value) || setupProviders[0];
    $("setupProviderNote").textContent = provider.note;
    $("setupKeyLink").href = provider.key_url;
  }

  function chooseSetup(choice) {
    setupChoice = choice === "cloud" || choice === "local" ? choice : null;
    $("btnSetupCloud").setAttribute("aria-checked", String(setupChoice === "cloud"));
    $("btnSetupLocal").setAttribute("aria-checked", String(setupChoice === "local"));
    $("setupCloud").hidden = setupChoice !== "cloud";
    $("setupLocal").hidden = setupChoice !== "local";
    $("btnSetupMore").hidden = typeof bridge?.openSettings !== "function";
    $("btnSetupPaste").hidden = typeof bridge?.readClipboardText !== "function";
    pageStatus($("setupStatus"), "");
    if (setupChoice === "local") void loadSetupLocal();
  }

  async function saveSetupCloud() {
    const provider = setupProviders.find((item) => item.id === $("setupProvider").value);
    const key = $("setupApiKey").value.trim();
    const status = $("setupStatus");
    if (!provider) return;
    if (!key) { pageStatus(status, t("先把 API 密钥粘贴到上面的框里"), true); $("setupApiKey").focus(); return; }
    let started;
    try {
      started = JSON.parse(bridge.saveQuickProvider(JSON.stringify({ protocol: provider.protocol, base_url: provider.base_url, model: provider.model, api_key: key })));
    } catch { started = { ok: false }; }
    if (!started.ok) { pageStatus(status, localizeError(started.error) || t("无法保存"), true); return; }
    $("btnSetupSave").disabled = true;
    pageStatus(status, t("正在用这个密钥连接 {0}…", provider.name));
    try {
      for (let attempt = 0; attempt < 120; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 500));
        let state;
        try { state = JSON.parse(bridge.getQuickProviderStatus()); } catch { state = { state: "error" }; }
        if (state.state === "checking") continue;
        if (state.state !== "saved") { pageStatus(status, localizeError(state.error) || t("无法连接服务商"), true); return; }
        $("setupApiKey").value = "";
        // The provider the user chose here sends without asking each conversation (mobile_approval).
        writeStorage(setupPendingKey, { trust: provider.base_url });
        pageStatus(status, t("密钥可用，正在切换到 {0}…", provider.name));
        restartPending = true;
        notice(t("已设置 {0}，正在重新连接…", provider.name), "info");
        setTimeout(closeSetup, 900);
        return;
      }
      pageStatus(status, t("服务商一直没有回应，请稍后再试"), true);
    } finally {
      $("btnSetupSave").disabled = false;
    }
  }

  async function loadSetupLocal() {
    const status = $("setupStatus");
    const button = $("btnSetupLocalGo");
    let info;
    try { info = await apiJson("/mobile/local-models"); }
    catch (error) { if (setupChoice === "local") pageStatus(status, error.message, true); return; }
    if (disposed || setupChoice !== "local") return;
    const models = info.models || [];
    const installed = setupLocalModels.map((id) => models.find((model) => model.model_id === id && model.installed)).find(Boolean);
    const pick = installed || models.find((model) => model.model_id === setupLocalModels[0]);
    setupLocal = pick || null;
    const progress = $("setupLocalProgress");
    if (!pick) { $("setupLocalModel").textContent = t("这个版本没有可下载的本机模型"); button.hidden = true; return; }
    button.hidden = false;
    const downloading = setupActiveDownload.includes(pick.state);
    progress.hidden = !downloading;
    progress.value = pick.progress || 0;
    if (installed) {
      $("setupLocalModel").textContent = t("已经下载了 {0}，点下面的按钮就能用。第一次回答前要先准备几分钟，之后就快了。", pick.title);
      button.textContent = t("使用这个模型");
    } else {
      $("setupLocalModel").textContent = t("推荐 {0}：下载 {1}，需要约 {2} 可用内存。下载完自动切换；第一次回答前要先准备几分钟，之后就快了。",
        pick.title, formatBytes(pick.size_bytes), formatBytes(pick.minimum_available_ram_bytes));
      button.textContent = downloading ? t("正在下载…") : pick.downloaded_bytes ? t("继续下载并使用") : t("下载并使用");
    }
    button.disabled = downloading;
    const other = models.find((model) => setupActiveDownload.includes(model.state) && model.model_id !== pick.model_id);
    const lacking = !installed && Number.isFinite(info.storage_free_bytes) && info.storage_free_bytes < pick.size_bytes - (pick.downloaded_bytes || 0) + 64 * 1024 * 1024;
    if (lacking) { button.disabled = true; pageStatus(status, t("手机存储空间不够：需要约 {0}，现在还剩 {1}", formatBytes(pick.size_bytes), formatBytes(info.storage_free_bytes)), true); }
    else if (other) { button.disabled = true; pageStatus(status, t("{0} 正在下载，完成或暂停后再试", other.title)); }
    else if (downloading) pageStatus(status, pick.state === "waiting_network" ? t("网络断了，恢复后自动继续下载") : t("下载 {0}%，下完会自动切换。可以先关掉这页。", Math.floor((pick.progress || 0) * 100)));
    else if (pick.state === "failed") pageStatus(status, localizeError(pick.error) || t("下载失败"), true);
    else pageStatus(status, "");
    clearTimeout(setupPoll);
    if (downloading) setupPoll = setTimeout(() => { if (layerOpen($("setupSheet")) && setupChoice === "local") void loadSetupLocal(); }, 2000);
    else if (installed && readPending()?.local === pick.model_id) switchToLocal(pick.model_id);
  }

  async function startSetupLocal() {
    const model = setupLocal;
    if (!model) return;
    if (model.installed) { switchToLocal(model.model_id); return; }
    writeStorage(setupPendingKey, { local: model.model_id });
    try {
      await apiJson("/mobile/local-models/download", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: model.model_id, source: "auto", prefer: locale.startsWith("zh") ? "modelscope" : "huggingface" }),
      });
    } catch (error) {
      pageStatus($("setupStatus"), localizeError(error.message), true);
      return;
    }
    await loadSetupLocal();
  }

  function switchToLocal(modelId) {
    if (activeTask || restartPending) return false;
    try { bridgeResult("selectLocalModel", modelId); }
    catch (error) { pageStatus($("setupStatus"), error.message, true); return false; }
    // After the restart the model reads its instructions once, ahead of the first message.
    writeStorage(setupPendingKey, { prepare: modelId });
    restartPending = true;
    notice(t("本机模型已就绪，正在切换，引擎需要重启…"), "info");
    closeSetup();
    return true;
  }

  // A download started from the sheet, which was closed meanwhile: switch once it is in.
  function watchPendingLocal() {
    clearTimeout(setupPendingPoll);
    setupPendingPoll = setTimeout(async () => {
      const pending = readPending();
      if (disposed || !pending?.local || layerOpen($("setupSheet"))) return;
      let model;
      try { model = (await apiJson("/mobile/local-models")).models?.find((item) => item.model_id === pending.local); } catch { model = null; }
      if (disposed) return;
      if (model?.installed) { if (!switchToLocal(model.model_id)) watchPendingLocal(); return; }
      if (model?.state === "failed") { notice(t("本机模型下载失败：{0}", localizeError(model.error) || "")); return; }
      if (model && !setupActiveDownload.includes(model.state) && model.state !== "paused") return;
      watchPendingLocal();
    }, 15000);
  }

  /** After the settings load: what the sheet left for the restarted engine, and the sheet itself on first use. */
  async function resumeSetup() {
    const pending = readPending();
    if (pending?.trust) {
      if (pending.trust === settings.base_url) {
        try {
          await apiJson("/mobile/approvals/trust-provider", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ endpoint: pending.trust }) });
          notice(t("可以开始了。"), "info");
        } catch { /* it asks in the conversation, as before */ }
      }
      writeStorage(setupPendingKey, null);
    } else if (pending?.prepare) {
      writeStorage(setupPendingKey, null);
      if (isLocalModel() && settings.model === pending.prepare) await prepareLocalModel();
    } else if (pending?.local) {
      watchPendingLocal();
    }
    if (!disposed && setupNeeded() && !readStorage(setupSeenKey, false) && !elderOn()) openSetup("start");
  }

  // The on-device model reads its long instructions once (minutes on a phone) and keeps what it
  // read: done right after switching, the first message is answered in seconds (mobile_local_prepare).
  async function prepareLocalModel() {
    try {
      await apiJson("/mobile/local-models/prepare", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    } catch { return; }
    notice(t("本机模型正在做第一次准备（只需一次，约几分钟，手机会发热）。准备好之前发的消息会排队。"), "info");
  }

  // Execution mode page: providers sent to without asking (first-use setup, or "always" on an
  // approval); each can be asked about again.
  async function loadTrustedProviders() {
    let trusted = [];
    try { trusted = (await apiJson("/mobile/approvals/trusted-providers")).trusted || []; } catch { trusted = []; }
    if (disposed) return;
    const list = $("trustedProviderList");
    list.replaceChildren();
    $("trustedProviders").hidden = !trusted.length;
    for (const origin of trusted) {
      const row = document.createElement("div");
      row.className = "management-row";
      const name = document.createElement("span");
      name.textContent = hostOf(origin) || origin;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button-secondary";
      button.textContent = t("取消");
      button.addEventListener("click", async () => {
        try {
          await apiJson("/mobile/approvals/distrust-provider", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ origin }) });
        } catch { /* listed again below */ }
        await loadTrustedProviders();
      });
      row.append(name, button);
      list.append(row);
    }
  }
  // jsdom (and a closing WebView) can fire "toggle" after the page went away: no lookup in it.
  const localAdvanced = $("localAdvanced");
  localAdvanced?.addEventListener("toggle", () => {
    if (settingsPage === "localModels") elements.settingsActions.hidden = !localAdvanced.open;
  });
  $("setupSheetBackdrop").addEventListener("click", () => closeSetup());
  $("btnSetupClose").addEventListener("click", () => closeSetup());
  $("btnSetupCloud").addEventListener("click", () => chooseSetup("cloud"));
  $("btnSetupLocal").addEventListener("click", () => chooseSetup("local"));
  $("setupProvider").addEventListener("change", () => { renderSetupProviders(); pageStatus($("setupStatus"), ""); });
  $("setupKeyLink").addEventListener("click", (event) => {
    // The app opens it in the phone's browser; the page itself never navigates away.
    if (typeof bridge?.openExternal === "function") { event.preventDefault(); bridge.openExternal($("setupKeyLink").href); }
  });
  $("btnSetupPaste").addEventListener("click", () => {
    let value = {};
    try { value = JSON.parse(bridge.readClipboardText()); } catch { value = {}; }
    if (!value.text?.trim()) { pageStatus($("setupStatus"), t("剪贴板里没有文字"), true); return; }
    $("setupApiKey").value = value.text.trim();
    pageStatus($("setupStatus"), "");
  });
  $("setupApiKey").addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); void saveSetupCloud(); } });
  $("btnSetupSave").addEventListener("click", () => void saveSetupCloud());
  $("btnSetupMore").addEventListener("click", () => { closeSetup(); bridge?.openSettings?.(); });
  $("btnSetupLocalGo").addEventListener("click", () => void startSetupLocal());
  $("btnSetupLocalMore").addEventListener("click", () => { closeSetup(); openMenu(); setSettingsPage("localModels"); });
