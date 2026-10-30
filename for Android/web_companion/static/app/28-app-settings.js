  // ---- The agent and this app's settings (android_adapter/app_settings_tool.py) --------------------
  // The agent can say what a setting is, open its page, or propose a change; a change shows here as a
  // card and happens only when the user taps Apply, through the same code as the settings page. The
  // page tells the engine the current values so the agent can answer "what is it set to".
  const onOff = (on) => (on ? "on" : "off");
  function nativeJson(method) {
    if (typeof bridge?.[method] !== "function") return null;
    try { return JSON.parse(bridge[method]()); } catch { return null; }
  }
  const settingReaders = {
    theme: () => preferences.theme, text_size: () => preferences.textSize, style: () => preferences.style,
    accent: () => preferences.accent, motion: () => preferences.motion, language: () => preferences.language,
    quick_actions: () => onOff(preferences.quickActions), haptics: () => onOff(preferences.haptics),
    model: () => settings.model || null, reasoning_effort: () => settings.reasoning_effort, execution_mode: () => settings.autonomy,
    floating_ball: () => { const value = nativeJson("getGlobalEntry"); return value ? onOff(!!value.floating_ball) : null; },
    task_notifications: () => { const value = nativeJson("getNotificationSettings"); return value ? onOff(!!value.enabled) : null; },
    offline_voice: () => { const value = nativeJson("getVoiceInputSettings"); return value ? onOff(!!value.prefer_offline) : null; },
    auto_update_check: () => { const value = nativeJson("getUpdateSettings"); return value ? onOff(!!value.autoCheck) : null; },
    expert_team: () => onOff(teamSettings.on),
  };
  // A setting control changed the way a tap on it does, so the page's own handler runs.
  function setControl(control, value) {
    if (!control || control.value === value) return;
    control.value = value;
    control.dispatchEvent(new Event("change", { bubbles: true }));
  }
  function setToggle(control, on) {
    if (!control || control.checked === on) return;
    control.checked = on;
    control.dispatchEvent(new Event("change", { bubbles: true }));
  }
  function nativeSet(method, on) {
    if (typeof bridge?.[method] !== "function") throw new Error(t("这个版本的应用不能修改这一项"));
    bridge[method](on);
  }
  // Model, effort and execution mode go through the app; the engine restarts for some of them.
  function runtimeChange(update) {
    if (typeof bridge?.applyRuntimeSettings !== "function") throw new Error(t("这个版本的应用不能修改这一项"));
    const result = JSON.parse(bridge.applyRuntimeSettings(JSON.stringify({
      model: settings.model, reasoning_effort: settings.reasoning_effort, autonomy: settings.autonomy, ...update,
    })));
    if (!result.ok) throw new Error(localizeError(result.error) || t("无法保存设置"));
    if (result.restarting === false) void loadSettings();
    else { restartPending = true; notice(t("设置已保存，正在重新连接..."), "info"); }
  }
  // What the card calls each setting and value (the engine's catalog, in the page's language).
  const onOffLabels = { on: t("开"), off: t("关") };
  const settingLabels = {
    theme: [t("深色 / 浅色"), { system: t("跟随系统"), light: t("浅色"), dark: t("深色") }],
    text_size: [t("文字大小"), { small: t("小"), normal: t("标准"), large: t("大") }],
    style: [t("界面风格"), { solid: t("标准"), glass: t("液态玻璃") }],
    accent: [t("主题色"), { teal: t("青绿"), blue: t("蓝"), violet: t("紫"), amber: t("琥珀"), rose: t("玫红") }],
    motion: [t("动画"), { auto: t("跟随系统"), full: t("完整"), reduced: t("减少"), off: t("关闭") }],
    // Each language by its own name, as the Appearance page lists them.
    language: [t("界面语言"), Object.fromEntries([...$("languageSelector").options].map((option) => [option.value, option.textContent]))],
    quick_actions: [t("输入框上方的快捷任务"), onOffLabels], haptics: [t("触感反馈"), onOffLabels],
    model: [t("模型"), {}], reasoning_effort: [t("思考程度"), effortLabels],
    execution_mode: [t("执行模式"), { workspace: t("仅工作区"), yolo: "YOLO", full_access: t("完全访问") }],
    floating_ball: [t("悬浮球"), onOffLabels], task_notifications: [t("任务完成通知"), onOffLabels],
    offline_voice: [t("语音输入用离线识别"), onOffLabels], auto_update_check: [t("自动检查更新"), onOffLabels],
    expert_team: [t("专家团"), onOffLabels],
  };
  function settingValueLabel(key, value) { return settingLabels[key]?.[1]?.[value] || value; }
  // Applied only after the task: the engine restarts for these, which would stop the task.
  const restartingSettings = new Set(["execution_mode", "model"]);
  const settingAppliers = {
    theme: (value) => setControl(elements.themeSelector, value),
    text_size: (value) => setControl(elements.textSizeSelector, value),
    motion: (value) => setControl($("motionSelector"), value),
    language: (value) => setControl($("languageSelector"), value),
    style: (value) => chooseAppearance("style", value),
    accent: (value) => chooseAppearance("accent", value),
    quick_actions: (value) => setToggle(elements.quickActionsToggle, value === "on"),
    haptics: (value) => setToggle(elements.hapticsToggle, value === "on"),
    reasoning_effort: (value) => { applyQuickEffort(value); flushQuickEffort(); },
    model: (value) => runtimeChange({ model: value, reasoning_effort: supportedEfforts(value).includes(settings.reasoning_effort) ? settings.reasoning_effort : "auto" }),
    execution_mode: (value) => runtimeChange({ autonomy: value }),
    floating_ball: (value) => nativeSet("setFloatingBall", value === "on"),
    task_notifications: (value) => nativeSet("setTaskNotificationsEnabled", value === "on"),
    offline_voice: (value) => nativeSet("setVoiceInputPreferOffline", value === "on"),
    auto_update_check: (value) => nativeSet("setAutoUpdateCheck", value === "on"),
    expert_team: (value) => {
      if (value === "on" && isLocalModel()) throw new Error(t("专家团需要云端模型：本机模型要跑三到五轮，太慢。"));
      saveTeam({ ...teamSettings, on: value === "on" });
    },
  };
  // Pages the agent can open (app_settings_tool.PAGES); "provider" is the app's own dialog.
  function openSettingsPage(page) {
    if (page === "provider") { bridge?.openSettings?.(); return; }
    openMenu();
    // Through its menu entry, so the page loads what it shows (btnConnectionsPage and the like).
    const entry = $(`btn${page[0].toUpperCase()}${page.slice(1)}Page`);
    if (entry) entry.click();
    else setSettingsPage(page);
  }
  // The page's name as its menu entry shows it (already in the user's language).
  function settingsPageTitle(page) {
    const entry = $(page === "provider" ? "btnProviderSettings" : `btn${page[0].toUpperCase()}${page.slice(1)}Page`);
    return entry?.querySelector("span:nth-child(2)")?.firstChild?.textContent?.trim() || "";
  }

  /** The current values, for the agent (sent before each task and after a change). */
  async function syncAppSettings() {
    const values = {};
    for (const [key, read] of Object.entries(settingReaders)) {
      try { const value = read(); if (typeof value === "string") values[key] = value; } catch { /* left out */ }
    }
    try { await apiJson("/mobile/app-settings/snapshot", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ values }) }); }
    catch { /* the agent then says it cannot tell the current value */ }
  }

  /** Under a finished app_settings step: the change to apply, or the page to open. */
  function showAppSettingsStep(card, args) {
    // Next to the step (a collapsed <details>), so it shows without opening it.
    if (!card || !args || card.nextElementSibling?.classList.contains("setting-proposal")) return;
    const box = document.createElement("div");
    box.className = "setting-proposal";
    const text = document.createElement("p");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button-primary";
    if (args.action === "open" && typeof args.page === "string") {
      // Seen on the phone: the bare "open this page:" left the user guessing which page.
      const title = settingsPageTitle(args.page);
      text.textContent = title ? t("AI 建议打开「{0}」这一页。", title) : t("AI 建议打开这一页：");
      button.textContent = t("打开设置页");
      button.addEventListener("click", () => openSettingsPage(args.page));
      box.append(text, button);
    } else if (args.action === "change" && settingAppliers[args.setting] && typeof args.value === "string") {
      const current = settingReaders[args.setting]?.();
      if (current === args.value) return;
      const title = settingLabels[args.setting]?.[0] || args.setting;
      text.textContent = typeof current === "string"
        ? t("AI 建议把「{0}」从「{1}」改成「{2}」。点「应用更改」才会生效。", title, settingValueLabel(args.setting, current), settingValueLabel(args.setting, args.value))
        : t("AI 建议把「{0}」改成「{1}」。点「应用更改」才会生效。", title, settingValueLabel(args.setting, args.value));
      const risk = { execution_mode: { yolo: t("改成 YOLO 后，AI 改文件、运行命令时大多不再先问你。"), full_access: t("改成完全访问后，AI 几乎不再询问就能执行操作。") } }[args.setting]?.[args.value];
      box.append(text);
      if (risk) { const warning = document.createElement("p"); warning.className = "setting-risk"; warning.textContent = t("⚠ {0}", risk); box.append(warning); }
      button.textContent = t("应用更改");
      const later = document.createElement("button");
      later.type = "button";
      later.className = "button-secondary";
      later.textContent = t("不用了");
      const status = document.createElement("p");
      status.className = "setting-hint";
      status.setAttribute("role", "status");
      button.addEventListener("click", () => {
        if (restartingSettings.has(args.setting) && activeTask) { status.textContent = t("任务结束后再点「应用更改」：这一项要重启引擎。"); return; }
        try {
          settingAppliers[args.setting](args.value);
          button.disabled = later.disabled = true;
          status.textContent = t("已应用");
          haptic(16);
          void syncAppSettings();
        } catch (error) { status.textContent = error.message; }
      });
      later.addEventListener("click", () => box.remove());
      const actions = document.createElement("div");
      actions.className = "setting-proposal-actions";
      actions.append(button, later);
      box.append(actions, status);
    } else return;
    card.after(box);
  }
