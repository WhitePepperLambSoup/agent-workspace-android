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
  function stopPolls() { window.clearTimeout(modelPoll); window.clearTimeout(toolchainPoll); window.clearTimeout(servicesPoll); modelPoll = toolchainPoll = servicesPoll = null; }
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

  async function doctor(isCurrent = () => true) {
    const value = await ui.apiJson("/mobile/capabilities");
    if (!isCurrent()) return;
    const android = value.android || {};
    let engine = {};
    try { engine = JSON.parse(native?.getEngineStatus?.() || "{}"); } catch {}
    terms("doctorSummary", [[t("运行环境"), value.runtime], [t("引擎状态"), engine.state || t("已连接")], [t("系统操作"), android.enabled && android.connected ? t("已连接") : t("需要无障碍权限")], [t("截图"), android.screenshot_supported ? t("支持") : t("不可用")], [t("内存"), android.memory_total_bytes ? `${(android.memory_total_bytes / 1024 ** 3).toFixed(1)} GiB` : t("未测量")]]);
    $("systemPaused").checked = !!android.paused;
    $("systemPaused").disabled = typeof native?.setSystemPaused !== "function";
    $("btnAccessibilitySettings").disabled = typeof native?.openAccessibilitySettings !== "function";
    $("btnTakeover").disabled = typeof native?.requestSystemTakeover !== "function";
    $("doctorTools").replaceChildren();
    for (const tool of value.tools || []) $("doctorTools").append(row(tool.name, tool.available ? t("可用") : tool.reason || t("不可用")));
    $("browserSection").hidden = !(value.tools || []).some((tool) => tool.name === "browser_view" && tool.available);
    status("doctorStatus", android.reason || "");
    let background = {};
    try { background = JSON.parse(native?.getBackgroundStatus?.() || "{}"); } catch {}
    terms("backgroundSummary", [[t("电池优化"), background.battery_optimization_exempt ? t("已豁免") : t("系统默认")], [t("恢复状态"), background.engine?.requires_user_launch ? t("需要手动启动") : background.engine?.state || t("按系统条件恢复")], [t("后台限制"), background.background_restricted ? t("已限制") : t("未限制")], [t("完成通知"), background.notifications_enabled ? t("已开启") : t("未开启或未授权")]]);
    $("btnBatterySettings").disabled = typeof native?.openBatteryOptimizationSettings !== "function";
    $("btnBackgroundSettings").disabled = typeof native?.openAppBackgroundSettings !== "function";
    $("btnShareDiagnostics").disabled = typeof native?.shareDiagnostics !== "function";
    updates();
    await toolchain(isCurrent);
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
    $("memoryFormLabel").textContent = t("添加一条记忆");
    $("memorySubmitLabel").textContent = t("添加");
    $("btnCancelMemoryEdit").hidden = true;
  }
  async function memory(isCurrent = () => true, value = null) {
    value = value || await ui.apiJson("/mobile/memory");
    if (!isCurrent()) return;
    memoryLimits = { ...memoryLimits, ...(value.limits || {}) };
    $("memoryEnabledToggle").checked = value.enabled !== false;
    $("memoryAutoToggle").checked = value.auto !== false;
    $("memoryAutoToggle").disabled = value.enabled === false;
    $("memoryContent").maxLength = memoryLimits.max_chars;
    $("memoryHint").textContent = t("最多 {0} 条，每条不超过 {1} 字。对话时只带上最新的记忆（约 {2} 字以内），控制 Token 用量；AI 每次任务最多自动记 {3} 条，相似的内容不会重复记。", memoryLimits.max_items, memoryLimits.max_chars, memoryLimits.prompt_budget_chars, memoryLimits.auto_saves_per_task);
    const items = Array.isArray(value.items) ? value.items : [];
    $("memoryCounter").textContent = `${items.length}/${memoryLimits.max_items}`;
    $("memoryList").replaceChildren();
    for (const item of items) {
      const when = item.updated_at ? new Date(item.updated_at).toLocaleString() : "";
      const element = row(item.content, `${item.source === "auto" ? t("AI 记的") : t("你添加的")}${when ? ` · ${when}` : ""}`);
      element.classList.add("memory-row");
      action(element, "pencil", t("编辑"), () => {
        memoryEditing = item.id;
        $("memoryContent").value = item.content;
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
    }
    $("btnClearMemory").disabled = !items.length;
    status("memoryStatus", value.enabled === false ? t("记忆已关闭：对话中不会使用，AI 也不会保存") : "");
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
      element.querySelector("strong").textContent = `${service.name} · ${serviceStates[service.state] || service.state}`;
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
    const result = JSON.parse(native.createBackup(JSON.stringify(web)));
    if (!result.ok) throw new Error(localizeError(result.error) || t("操作失败"));
  }, "backupStatus");
  on("btnRestoreBackup", "click", () => {
    if (!window.confirm(t("恢复会用备份替换这台手机上的会话、记忆、工作区文件和设置（当前数据会保留一份），然后重启引擎。API 密钥不在备份里，恢复后需要重新填写。继续？"))) return;
    const result = JSON.parse(native.restoreBackup());
    if (!result.ok) throw new Error(localizeError(result.error) || t("操作失败"));
  }, "backupStatus");

  async function schedules(isCurrent = () => true) {
    const value = await ui.apiJson("/mobile/schedules"); if (!isCurrent()) return;
    $("schedulesList").replaceChildren();
    for (const schedule of value.schedules || []) {
      const item = row(schedule.title, `${schedule.enabled ? t("启用") : t("暂停")} · ${schedule.next_due_at || schedule.due_at}\n${schedule.last_status || ""}`);
      const toggle = document.createElement("input"); toggle.type = "checkbox"; toggle.checked = schedule.enabled; toggle.setAttribute("aria-label", t("启用 {0}", schedule.title));
      toggle.addEventListener("change", async () => { toggle.disabled = true; try { await post("/mobile/schedules/update", { schedule_id: schedule.schedule_id, enabled: toggle.checked }); await schedules(); } catch (error) { toggle.checked = !toggle.checked; status("schedulesStatus", error.message, true); } finally { toggle.disabled = false; } });
      item.append(toggle);
      action(item, "trash-2", t("删除定时任务"), async () => { if (!window.confirm(t("删除 {0}？", schedule.title))) return; await post("/mobile/schedules/delete", { schedule_id: schedule.schedule_id }); await schedules(); });
      $("schedulesList").append(item);
    }
    const mode = ui.context().settings.autonomy;
    $("btnSaveSchedule").disabled = !["yolo", "full_access"].includes(mode);
    status("schedulesStatus", ["yolo", "full_access"].includes(mode) ? (value.status?.reason || "") : t("无人值守任务需要 YOLO 或完全访问模式"));
  }
  async function connections(isCurrent = () => true) {
    const value = await ui.apiJson("/mobile/connections"); if (!isCurrent()) return;
    $("connectionsList").replaceChildren();
    for (const host of value.hosts || []) {
      const item = row(host.name, `${host.url}\n${host.api === "mobile" ? t("手机任务 API") : t("桌面 Serve API")}`);
      action(item, "link", t("打开远程工作区"), async () => {
        selectedHost = host;
        const data = await ui.apiJson(`/mobile/connections/sessions?host_id=${encodeURIComponent(host.host_id)}`);
        remoteSessions = Array.isArray(data.sessions) ? data.sessions : [];
        $("remoteSessionSelector").replaceChildren();
        for (const session of remoteSessions) { const option = document.createElement("option"); option.value = session.id; option.textContent = session.title || session.id; $("remoteSessionSelector").append(option); }
        $("remoteSessionPanel").hidden = false;
        updateRemoteWorkspace();
        $("btnQueueHandoff").disabled = !remoteSessions.length;
      });
      action(item, "trash-2", t("移除配对设备"), async () => { if (!window.confirm(t("移除 {0}？", host.name))) return; await post("/mobile/connections/remove", { host_id: host.host_id }); if (selectedHost?.host_id === host.host_id) { selectedHost = null; remoteSessions = []; $("remoteSessionPanel").hidden = true; $("remoteHistory").hidden = true; } await connections(); });
      $("connectionsList").append(item);
    }
    status("connectionsStatus", t("本机工作区：{0}", value.workspace || t("手机")));
  }
  function updateRemoteWorkspace() { $("remoteWorkspace").textContent = t("数据保存在 {0}：{1}", selectedHost?.name || t("远程设备"), remoteSessions.find(item => item.id === $("remoteSessionSelector").value)?.workspace || ""); }
  async function outbox(isCurrent = () => true) {
    const value = await ui.apiJson("/mobile/outbox"); if (!isCurrent()) return;
    $("outboxList").replaceChildren();
    for (const delivery of value.deliveries || []) {
      const item = row((delivery.payload?.prompt || "").slice(0, 100), `${stateNames[delivery.state] || delivery.state} · ${delivery.payload?.session_id || ""}\n${delivery.error || ""}`);
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
      deviceRecommendation = null; terms("localDeviceRecommendation", []);
      setUnavailable($("btnUseLocalRecommendation"), error.message);
      setUnavailable($("btnStartLocalBenchmark"), error.message);
      status("localDeviceStatus", error.message, true);
    }
  }

  async function localModels(isCurrent = () => true) {
    const [value, capabilities] = await Promise.all([ui.apiJson("/mobile/local-models"), ui.apiJson("/mobile/capabilities")]); if (!isCurrent()) return;
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
    terms("localModelSummary", [[t("当前模型"), value.model], [t("当前推理"), value.route === "embedded_qwen" ? t("本机 CPU") : value.route === "local_endpoint" ? t("本地 HTTP 引擎") : t("远程模型")], [t("本机引擎"), engine.available ? t("llama.cpp 已就绪") : engine.last_error || t("未就绪")], ...capacityTerms, ...(!planPending && outputTokens != null ? [[t("每轮输出上限"), `${outputTokens} Token`]] : []), [t("可用内存"), bytes(plan?.available_ram_bytes ?? capabilities.android?.memory_available_bytes)], [t("可用存储"), bytes(value.storage_free_bytes)], [t("首 Token"), measurement.first_token_ms == null ? t("未测量") : `${measurement.first_token_ms} ms`], [t("生成速度"), measurement.tokens_per_second == null ? t("未测量") : `${measurement.tokens_per_second.toFixed(2)} Token/s`]]);
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
    const entries = [...(value.models || []), ...(value.vision_components || [])];
    const list = $("localModelList"); const activeDownload = entries.find(model => ["queued", "downloading", "verifying"].includes(model.state)); const downloading = !!activeDownload;
    const ids = new Set();
    for (const model of entries) {
      const projection = model.kind === "vision_projection";
      ids.add(model.model_id);
      let card = [...list.children].find(item => item.dataset.modelId === model.model_id);
      if (!card) { card = row(model.title); card.classList.add("local-model-card"); card.dataset.modelId = model.model_id; const progress = document.createElement("progress"); progress.max = 1; progress.setAttribute("aria-label", t("{0}下载进度", model.title)); card.append(progress); const links = document.createElement("div"); links.className = "model-sources"; for (const [label, address] of [[t("下载来源"), model.source_page], [t("直接下载"), model.download_url]]) { try { const url = new URL(address); if (url.protocol !== "https:") continue; const link = document.createElement("a"); link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = label; links.append(link); } catch {} } card.append(links); const actions = document.createElement("div"); actions.className = "model-actions"; card.append(actions); list.append(card); }
      const vision = !projection && model.supports_vision ? t("\n图片理解：{0}", !engine.supports_vision ? t("需支持视觉的本机引擎") : model.vision_component_installed ? t("视觉组件已就绪") : t("请下载配套视觉组件")) : "";
      card.querySelector("small").textContent = `${model.publisher || ""} · ${model.local_artifact ? t("工具训练版 · 实验") : model.official_weights ? t("官方量化") : t("社区量化")} · ${model.license || ""}\n${bytes(model.size_bytes)}${projection ? t(" · 配套图片理解组件") : t(" · 预计需 {0} 可用内存", bytes(model.minimum_available_ram_bytes))}${vision}\n${model.local_artifact && !model.installed ? t("请选择此版本对应的 GGUF 文件导入") : ({ not_installed: t("未下载"), installed: t("已校验安装"), queued: t("等待下载"), downloading: t("下载中"), verifying: t("校验中"), paused: t("已暂停"), failed: t("下载失败") })[model.state] || model.state}${model.error ? t("：{0}", model.error) : ""}`;
      const progress = card.querySelector("progress"); progress.hidden = !["queued", "downloading", "paused", "verifying"].includes(model.state); progress.value = model.progress || 0;
      const signature = `${model.state}:${!!model.has_local_files}:${busy}:${!!engine.available}:${activeDownload?.model_id}:${value.model}:${value.route}`;
      if (card.dataset.signature !== signature) { card.dataset.signature = signature; const actions = card.querySelector(".model-actions"); actions.replaceChildren();
        if (["queued", "downloading"].includes(model.state)) namedAction(actions, "pause", t("暂停下载"), async () => { await post("/mobile/local-models/cancel", { model_id: model.model_id }); await localModels(isCurrent); });
        else if (!model.installed && model.local_artifact) { const button = namedAction(actions, "folder-open", t("导入训练模型"), () => { nativeResult("importLocalModel", model.model_id); status("localModelsStatus", t("请选择训练模型文件，导入后将自动校验")); }); button.disabled = busy || typeof native?.importLocalModel !== "function"; }
        else if (!model.installed && model.state !== "verifying") { const button = namedAction(actions, "download", model.downloaded_bytes ? t("继续下载") : projection ? t("下载视觉组件") : t("下载模型"), async () => { await post("/mobile/local-models/download", { model_id: model.model_id }); await localModels(isCurrent); }); setUnavailable(button, downloading ? t("{0} 正在{1}，完成或暂停后可下载", activeDownload.title || activeDownload.model_id, activeDownload.state === "verifying" ? t("校验") : t("下载")) : ""); }
        if (model.installed && !projection) { const button = namedAction(actions, "play", value.model === model.model_id && value.route === "embedded_qwen" ? t("当前模型") : t("使用此模型"), () => { nativeResult("selectLocalModel", model.model_id); status("localModelsStatus", t("模型配置已保存，正在切换引擎")); }); button.disabled = busy || !engine.available || typeof native?.selectLocalModel !== "function"; }
        if (model.has_local_files || model.installed || model.downloaded_bytes) { const button = namedAction(actions, "trash-2", projection ? t("移除视觉组件") : t("移除模型"), async () => { if (!window.confirm(t("移除 {0} 的已下载文件？", model.title))) return; await post("/mobile/local-models/remove", { model_id: model.model_id }); await localModels(isCurrent); }); button.disabled = busy || ["queued", "downloading", "verifying"].includes(model.state); }
      }
      let actionStatus = card.querySelector(".model-action-status");
      if (!actionStatus) { actionStatus = document.createElement("p"); actionStatus.className = "model-action-status"; actionStatus.setAttribute("role", "status"); card.append(actionStatus); }
      actionStatus.textContent = !model.installed && downloading && model.model_id !== activeDownload.model_id ? t("{0} 正在{1}，完成或暂停后可下载", activeDownload.title || activeDownload.model_id, activeDownload.state === "verifying" ? t("校验") : t("下载")) : "";
      actionStatus.hidden = !actionStatus.textContent;
    }
    for (const card of [...list.children]) if (!ids.has(card.dataset.modelId)) card.remove();
    status("localModelsStatus", "");
    window.clearTimeout(modelPoll);
    if (downloading || busy) modelPoll = window.setTimeout(() => { if (!closed && !$("settingsLocalModels").hidden && !$("settingsOverlay").hidden) localModels(isCurrent).catch(error => status("localModelsStatus", error.message, true)); }, 2000);
  }
  const pages = {
    Memory: ["memory", memory, "memoryStatus"], Services: ["services", services, "servicesStatus"], GlobalEntry: ["globalEntry", globalEntry, "globalEntryStatus"], NotificationRules: ["notificationRules", notificationRules, "notificationRulesStatus"], Backup: ["backup", backup, "backupStatus"], Doctor: ["doctor", doctor, "doctorStatus"], Extensions: ["extensions", extensions, "extensionsStatus"], Schedules: ["schedules", schedules, "schedulesStatus"], Connections: ["connections", connections, "connectionsStatus"], Outbox: ["outbox", outbox, "outboxStatus"], Workflows: ["workflows", workflows, "workflowsStatus"], Evaluations: ["evaluations", evaluations, "evaluationsStatus"], LocalModels: ["localModels", localModels, "localModelsStatus"],
  };
  for (const [name, [route, loader, statusId]] of Object.entries(pages)) on(`btn${name}Page`, "click", () => page(route, loader, statusId), statusId);
  for (const [name, loader, statusId] of [["Doctor", doctor, "doctorStatus"], ["Extensions", extensions, "extensionsStatus"], ["Outbox", outbox, "outboxStatus"]]) on(`btn${name}Refresh`, "click", () => loader(), statusId);
  on("memoryForm", "submit", async () => {
    const content = $("memoryContent").value.trim();
    if (!content) return;
    let value;
    try {
      value = memoryEditing
        ? await post("/mobile/memory/update", { id: memoryEditing, content })
        : await post("/mobile/memory", { content });
    } catch (error) { throw new Error(memoryMessage(error)); }
    stopMemoryEdit();
    await memory(undefined, value);
  }, "memoryStatus");
  on("btnCancelMemoryEdit", "click", () => stopMemoryEdit(), "memoryStatus");
  for (const [id, key] of [["memoryEnabledToggle", "enabled"], ["memoryAutoToggle", "auto"]]) {
    on(id, "change", async () => {
      try { await memory(undefined, await post("/mobile/memory/settings", { [key]: $(id).checked })); }
      catch (error) { $(id).checked = !$(id).checked; throw error; }
    }, "memoryStatus");
  }
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
    const context = ui.context();
    const value = await post("/mobile/notification-rules", {
      package: select.value, app_label: select.selectedOptions[0]?.textContent || select.value,
      keywords: $("notificationRuleKeywords").value, prompt, confirm: $("notificationRuleConfirm").checked,
      session_id: context.sessionId, model: context.settings.model, reasoning_effort: context.settings.reasoning_effort,
    });
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
  on("systemPaused", "change", async () => { native?.setSystemPaused?.($("systemPaused").checked); await doctor(); }, "doctorStatus");
  on("btnTakeover", "click", async () => { native?.requestSystemTakeover?.(); await doctor(); }, "doctorStatus");
  on("btnObserveScreen", "click", async () => { const response = await post("/mobile/android-system", { action: "observe" }); $("systemObservation").hidden = false; $("systemObservation").textContent = JSON.stringify(response.observation || response, null, 2); }, "doctorStatus");
  on("btnBatterySettings", "click", () => native?.openBatteryOptimizationSettings?.(), "doctorStatus");
  on("btnBackgroundSettings", "click", () => native?.openAppBackgroundSettings?.(), "doctorStatus");
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
    await post("/mobile/schedules", { title: $("scheduleTitle").value.trim(), prompt: $("schedulePrompt").value.trim(), session_id: context.sessionId, model: context.settings.model, reasoning_effort: context.settings.reasoning_effort, due_at: date.toISOString(), repeat_seconds: $("scheduleRepeat").value ? Number($("scheduleRepeat").value) : null, enabled: true });
    $("scheduleForm").reset(); await schedules();
  }, "schedulesStatus");
  on("connectionForm", "submit", async () => {
    await post("/mobile/connections", { name: $("connectionName").value.trim(), url: $("connectionUrl").value.trim(), token: $("connectionToken").value, allow_lan: $("connectionAllowLan").checked });
    $("connectionToken").value = ""; await connections();
  }, "connectionsStatus");
  on("remoteSessionSelector", "change", updateRemoteWorkspace, "connectionsStatus");
  on("btnUseDraft", "click", () => { $("handoffPrompt").value = ui.context().draft; }, "connectionsStatus");
  on("btnQueueHandoff", "click", async () => {
    if (!selectedHost) throw new Error(t("请先选择配对设备"));
    const context = ui.context(); let prompt = $("handoffPrompt").value.trim(); if (!prompt) throw new Error(t("请输入接力指令"));
    if ($("handoffContext").checked) prompt += t("\n\n用户选择附带的对话上下文：\n{0}", context.recentText);
    await post("/mobile/outbox", { host_id: selectedHost.host_id, session_id: $("remoteSessionSelector").value, prompt, request_id: window.crypto?.randomUUID?.() || `handoff-${Date.now()}-${Math.random().toString(16).slice(2)}` });
    status("connectionsStatus", t("已保存到待发送队列"));
  }, "connectionsStatus");
  on("btnReadRemote", "click", async () => {
    if (!selectedHost) throw new Error(t("请先选择配对设备"));
    const data = await ui.apiJson(`/mobile/connections/events?host_id=${encodeURIComponent(selectedHost.host_id)}&session_id=${encodeURIComponent($("remoteSessionSelector").value)}`);
    $("remoteHistory").hidden = false;
    $("remoteHistory").textContent = (data.events || []).filter(event => event.type === "message.created").map(event => `${event.data?.role || ""}: ${event.data?.content || ""}`).join("\n\n");
  }, "connectionsStatus");
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
