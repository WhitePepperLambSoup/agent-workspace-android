
  // ---- Shortcuts (2.0): phone tasks recorded as steps, edited here, run without the model ------
  // Recorded while the agent operates the phone (the panel, or a phone-control task here) and kept
  // by the Android app; each step finds its control again by its words (mobile_shortcuts.py).
  const shortcutKeys = { back: t("返回"), home: t("回到桌面"), recents: t("最近任务"), notifications: t("通知栏") };
  const shortcutDirections = { up: t("向上"), down: t("向下"), left: t("向左"), right: t("向右") };
  // The pages open_page opens, named as the approval prompt names them (AgentAccessibilityService.pageName).
  const shortcutPages = {
    settings: t("设置"), wifi: t("WLAN 设置"), bluetooth: t("蓝牙设置"), mobile_network: t("移动网络设置"),
    data_usage: t("流量使用"), airplane: t("飞行模式设置"), battery: t("电池"), display: t("显示设置"),
    sound: t("声音设置"), location: t("位置信息设置"), storage: t("存储"), date: t("日期和时间"),
    language: t("语言设置"), accessibility: t("无障碍设置"), security: t("安全设置"), nfc: t("NFC 设置"),
    vpn: t("VPN 设置"), developer: t("开发者选项"), apps: t("应用管理"), notifications: t("通知设置"),
    app_details: t("应用信息"), url: t("网页"), map: t("地图搜索"), web_search: t("网页搜索"), dial: t("拨号界面"),
  };
  let shortcutItems = [];
  let shortcutPoll = 0;

  function shortcutQuote(text) { return t("「{0}」", String(text || "").slice(0, 40)); }

  function describeShortcutStep(step) {
    switch (step.kind) {
      case "tap":
        if (!step.label) return t("点击屏幕位置 ({0}, {1})", step.x, step.y);
        return step.optional ? t("有广告时关掉：{0}", shortcutQuote(step.label)) : t("点击{0}", shortcutQuote(step.label));
      case "long": return step.label ? t("长按{0}", shortcutQuote(step.label)) : t("长按屏幕位置 ({0}, {1})", step.x, step.y);
      case "type": return t("在{0}里输入{1}", shortcutQuote(step.label), shortcutQuote(step.text));
      case "enter": return t("按确认键");
      case "scroll": return t("{0}滚动", shortcutDirections[step.direction] || step.direction);
      case "swipe": return t("从 ({0}, {1}) 滑到 ({2}, {3})", step.x, step.y, step.x2, step.y2);
      case "launch": return t("打开{0}", shortcutQuote(appName(step.package)));
      case "key": return shortcutKeys[step.key] || step.key;
      case "page": return t("打开页面：{0}", shortcutPages[step.request?.page] || step.request?.page || "");
      case "find": return step.tap ? t("找到{0}并点击", shortcutQuote(step.text)) : t("滚动找到{0}", shortcutQuote(step.text));
      default: return String(step.kind || "");
    }
  }

  function postShortcut(path, body) {
    return apiJson(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  }

  function shortcutButton(name, label, action) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "icon-button";
    button.title = label;
    button.setAttribute("aria-label", label);
    button.innerHTML = icon(name);
    button.addEventListener("click", async () => {
      try { await action(); } catch (error) { if (!disposed) $("shortcutsStatus").textContent = error.message; }
    });
    return button;
  }

  async function loadShortcuts() {
    const status = $("shortcutsStatus");
    clearTimeout(shortcutPoll);
    // What people who import this phone's shortcuts see as the signer.
    const identity = shareIdentity();
    $("shareFingerprint").hidden = !identity;
    if (identity) $("shareFingerprint").textContent = t("你的分享指纹：{0}。别人导入你分享的快捷操作时会看到它，可以当面或打电话核对。", identity.fingerprint);
    try {
      const value = await apiJson("/mobile/shortcuts");
      if (disposed) return;
      shortcutItems = value.shortcuts || [];
      $("shortcutsList").replaceChildren(...shortcutItems.map(shortcutRow));
      const last = value.last_run;
      const lastItem = last && shortcutItems.find((item) => item.id === last.id);
      if (value.running) status.textContent = t("快捷操作正在运行…");
      else if (lastItem && Date.now() / 1000 - last.at < 600) {
        status.textContent = last.ok ? t("{0}做完了", shortcutQuote(lastItem.name)) : t("{0}没做完：{1}", shortcutQuote(lastItem.name), localizeError(last.reason) || "");
        // Stuck at a step (the app changed, a button moved): the AI can finish from there.
        if (!last.ok && Number.isInteger(last.failed_step)) {
          const heal = document.createElement("button");
          heal.type = "button";
          heal.className = "button-secondary shortcut-heal";
          heal.textContent = t("让 AI 从第 {0} 步接着做", last.failed_step + 1);
          heal.addEventListener("click", () => void healShortcut(lastItem, last.failed_step, localizeError(last.reason) || ""));
          status.append(document.createElement("br"), heal);
        }
      } else status.textContent = shortcutItems.length ? "" : t("还没有快捷操作。用 AI 操作手机做完一件事后，点回复下面的「存为快捷操作」。");
      // Until it finishes (the page is in the background while it runs in another app).
      if (value.running) shortcutPoll = setTimeout(() => { if (!disposed && !$("settingsWorkflows").hidden) void loadShortcuts(); }, 2000);
    } catch (error) { if (!disposed) status.textContent = t("读取失败：{0}", error.message); }
  }

  function shortcutRow(shortcut) {
    const row = document.createElement("div");
    row.className = "management-row shortcut-row";
    const text = document.createElement("span");
    text.className = "management-row-body";
    const title = document.createElement("strong");
    title.textContent = shortcut.name;
    const detail = document.createElement("small");
    const steps = shortcut.steps || [];
    const app = shortcut.app_label || (shortcut.app ? appName(shortcut.app) : "");
    detail.textContent = [app, t("{0} 步", steps.length), steps.slice(0, 3).map(describeShortcutStep).join(" → ")].filter(Boolean).join(" · ");
    text.append(title, detail);
    row.append(text,
      shortcutButton("play", t("运行"), () => runShortcut(shortcut)),
      shortcutButton("clock", t("定时运行"), () => scheduleShortcut(row, shortcut)),
      shortcutButton("pencil", t("编辑"), () => editShortcut(row, shortcut)));
    return row;
  }

  async function runShortcut(shortcut) {
    if (activeTask) throw new Error(t("请等待当前任务结束"));
    await postShortcut("/mobile/shortcuts/run", { id: shortcut.id });
    if (disposed) return;
    haptic(12);
    $("shortcutsStatus").textContent = t("正在运行{0}…", shortcutQuote(shortcut.name));
    clearTimeout(shortcutPoll);
    shortcutPoll = setTimeout(() => { if (!disposed) void loadShortcuts(); }, 1500);
  }

  // One form under its row at a time: the editor or the schedule.
  function shortcutPanel(row, kind) {
    const open = row.nextElementSibling?.classList.contains(kind) ? row.nextElementSibling : null;
    $("shortcutsList").querySelectorAll(".shortcut-editor, .shortcut-schedule").forEach((node) => node.remove());
    if (open) return null;
    const form = document.createElement("form");
    form.className = `management-form ${kind}`;
    row.after(form);
    return form;
  }

  function shortcutField(form, label, control) {
    const wrapper = document.createElement("label");
    wrapper.textContent = label;
    wrapper.append(control);
    form.append(wrapper);
    return control;
  }

  function editShortcut(row, shortcut) {
    const form = shortcutPanel(row, "shortcut-editor");
    if (!form) return;
    const steps = (shortcut.steps || []).map((step) => ({ ...step }));
    const name = document.createElement("input");
    name.maxLength = 40;
    name.required = true;
    name.value = shortcut.name;
    shortcutField(form, t("名称"), name);
    const hint = document.createElement("p");
    hint.className = "setting-hint";
    hint.textContent = t("每一步靠控件上的文字找到它（没有文字的按屏幕位置点），所以改的文字要和屏幕上显示的一样。挡路的广告和弹窗会先关掉。");
    const list = document.createElement("ol");
    list.className = "shortcut-steps";
    const fields = (step) => step.kind === "tap" || step.kind === "long" ? [["label", t("控件上的文字")]]
      : step.kind === "type" ? [["label", t("输入框上的文字")], ["text", t("要输入的内容")]]
        : step.kind === "find" ? [["text", t("要找的文字")]] : [];
    function render() {
      list.replaceChildren(...steps.map((step, index) => {
        const item = document.createElement("li");
        const head = document.createElement("div");
        head.className = "shortcut-step-head";
        const words = document.createElement("span");
        words.textContent = describeShortcutStep(step);
        const move = (to) => { if (to < 0 || to >= steps.length) return; [steps[index], steps[to]] = [steps[to], steps[index]]; render(); };
        head.append(words,
          shortcutButton("arrow-up", t("上移"), () => move(index - 1)),
          shortcutButton("arrow-down", t("下移"), () => move(index + 1)),
          shortcutButton("x", t("删掉这一步"), () => { steps.splice(index, 1); render(); }));
        item.append(head);
        for (const [field, label] of fields(step)) {
          const input = document.createElement("input");
          input.value = step[field] ?? "";
          input.maxLength = field === "text" && step.kind === "type" ? 4096 : 200;
          input.placeholder = label;
          input.setAttribute("aria-label", label);
          input.addEventListener("input", () => { step[field] = input.value; words.textContent = describeShortcutStep(step); });
          item.append(input);
        }
        return item;
      }));
    }
    render();
    const actions = document.createElement("div");
    actions.className = "page-toolbar";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "button-secondary";
    remove.textContent = t("删除快捷操作");
    remove.addEventListener("click", async () => {
      if (!window.confirm(t("删除快捷操作{0}？", shortcutQuote(shortcut.name)))) return;
      try {
        await postShortcut("/mobile/shortcuts/delete", { id: shortcut.id });
        if (!disposed) void loadShortcuts();
      } catch (error) { if (!disposed) $("shortcutsStatus").textContent = error.message; }
    });
    const save = document.createElement("button");
    save.type = "submit";
    save.className = "button-primary";
    save.textContent = t("保存");
    const share = document.createElement("button");
    share.type = "button";
    share.className = "button-secondary";
    share.textContent = t("分享");
    share.addEventListener("click", () => {
      const code = shortcutCode({ name: name.value.trim() || shortcut.name, app: shortcut.app || null, steps });
      try { bridge?.copyToClipboard?.(code); } catch { /* Sharing below still works. */ }
      if (typeof bridge?.shareText === "function") bridge.shareText(t("快捷操作{0}", shortcutQuote(shortcut.name)), code);
      $("shortcutsStatus").textContent = t("分享码已复制：对方在「可复用流程 → 导入分享码」里粘贴即可");
    });
    actions.append(remove, share, save);
    form.append(hint, list, actions);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!steps.length) { $("shortcutsStatus").textContent = t("至少要留一步"); return; }
      try {
        await postShortcut("/mobile/shortcuts", { id: shortcut.id, name: name.value.trim(), steps });
        if (disposed) return;
        $("shortcutsStatus").textContent = t("已保存");
        void loadShortcuts();
      } catch (error) { if (!disposed) $("shortcutsStatus").textContent = t("保存失败：{0}", error.message); }
    });
    name.focus();
  }

  function scheduleShortcut(row, shortcut) {
    const form = shortcutPanel(row, "shortcut-schedule");
    if (!form) return;
    const next = new Date(Date.now() + 3600_000);
    next.setMinutes(0, 0, 0);
    const pad = (value) => String(value).padStart(2, "0");
    const due = document.createElement("input");
    due.type = "datetime-local";
    due.required = true;
    due.value = `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}T${pad(next.getHours())}:00`;
    shortcutField(form, t("什么时候"), due);
    const repeat = document.createElement("select");
    for (const [value, label] of [["", t("仅一次")], ["86400", t("每天")], ["604800", t("每周")], ["3600", t("每小时")]]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      repeat.append(option);
    }
    shortcutField(form, t("重复"), repeat);
    const hint = document.createElement("p");
    hint.className = "setting-hint";
    hint.textContent = t("到点时手机需要是解锁状态（息屏但没锁会自动亮屏），锁着屏就跳过这一次。快捷操作不用 AI，不花 token。");
    const create = document.createElement("button");
    create.type = "submit";
    create.className = "button-primary";
    create.textContent = t("创建定时运行");
    form.append(hint, create);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const when = new Date(due.value);
      if (Number.isNaN(when.getTime())) return;
      try {
        await postShortcut("/mobile/schedules", {
          title: t("快捷操作：{0}", shortcut.name), prompt: t("运行快捷操作{0}", shortcutQuote(shortcut.name)),
          session_id: currentSessionId, model: settings.model, reasoning_effort: settings.reasoning_effort,
          due_at: when.toISOString(), repeat_seconds: repeat.value ? Number(repeat.value) : null, enabled: true,
          shortcut_id: shortcut.id,
        });
        if (disposed) return;
        form.remove();
        $("shortcutsStatus").textContent = t("已创建：在「定时任务」里可以查看和暂停");
      } catch (error) { if (!disposed) $("shortcutsStatus").textContent = t("创建失败：{0}", error.message); }
    });
  }

  // A shortcut that stopped at a step: the AI finishes the rest from the screen as it is, and its
  // reply then offers to put what it did in place of the stuck steps (self-healing shortcuts).
  let healing = null;
  async function healShortcut(shortcut, fromStep, reason) {
    if (activeTask) { $("shortcutsStatus").textContent = t("请等待当前任务结束"); return; }
    const remaining = (shortcut.steps || []).slice(fromStep).map((step, index) => `${index + 1}. ${describeShortcutStep(step)}`).join("\n");
    const prompt = t("快捷操作{0}做到第 {1} 步停下了（{2}）。请操作手机，从现在的屏幕接着把剩下的做完：\n{3}\n做完后告诉我结果。",
      shortcutQuote(shortcut.name), fromStep + 1, reason, remaining);
    healing = { id: shortcut.id, name: shortcut.name, fromStep, prompt };
    closeMenu();
    await sendPrompt(prompt);
  }

  function offerHealedShortcut(task) {
    const heal = healing;
    healing = null;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button-secondary shortcut-offer";
    button.innerHTML = icon("zap");
    button.append(t("更新快捷操作{0}：第 {1} 步起换成这次的 {2} 步", shortcutQuote(heal.name), heal.fromStep + 1, task.shortcutSteps));
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await postShortcut("/mobile/shortcuts/heal", { task_id: task.id, id: heal.id, from_step: heal.fromStep });
        if (disposed) return;
        button.replaceChildren(t("已更新快捷操作{0}", shortcutQuote(heal.name)));
        haptic(12);
      } catch (error) {
        if (disposed) return;
        button.disabled = false;
        notice(t("没存上：{0}", error.message));
      }
    });
    task.card.appendChild(button);
  }

  // ---- Share codes: a shortcut as text, signed by the phone that made it, reviewed before it is
  // installed. "AW-SHORTCUT-2.<body>.<public key>.<signature>" is signed with this install's key in
  // the Android Keystore (ShareSignature.kt); "AW-SHORTCUT-1.<body>.<checksum>" (older versions)
  // only catches a damaged code and says nothing about who made it.
  const codePrefix = "AW-SHORTCUT-1.";
  const signedPrefix = "AW-SHORTCUT-2.";
  const knownAuthorsKey = "agent-share-authors-v1";
  function codeChecksum(text) {
    let hash = 0x811c9dc5;  // FNV-1a: catches a damaged or cut-off code (not a signature)
    for (let index = 0; index < text.length; index += 1) { hash ^= text.charCodeAt(index); hash = Math.imul(hash, 0x01000193) >>> 0; }
    return hash.toString(16).padStart(8, "0");
  }
  function shortcutCode(shortcut) {
    const json = JSON.stringify({ name: shortcut.name, app: shortcut.app || null, steps: shortcut.steps });
    const body = btoa(String.fromCharCode(...new TextEncoder().encode(json))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    if (typeof bridge?.signShareCode === "function") {
      try {
        const signed = JSON.parse(bridge.signShareCode(`${signedPrefix}${body}`) || "{}");
        if (signed.ok) return `${signedPrefix}${body}.${signed.public_key}.${signed.signature}`;
      } catch { /* An unsigned code below still shares the shortcut. */ }
    }
    return `${codePrefix}${body}.${codeChecksum(body)}`;
  }
  function decodeShortcut(body) {
    const binary = atob(body.replace(/-/g, "+").replace(/_/g, "/"));
    const value = JSON.parse(new TextDecoder().decode(Uint8Array.from(binary, (char) => char.charCodeAt(0))));
    if (!value || typeof value.name !== "string" || !Array.isArray(value.steps) || !value.steps.length) throw new Error(t("分享码里没有可用的步骤"));
    return value;
  }
  function shareIdentity() {
    if (shareIdentity.value === undefined) {
      try { shareIdentity.value = typeof bridge?.shareIdentity === "function" ? JSON.parse(bridge.shareIdentity() || "{}") : null; }
      catch { shareIdentity.value = null; }
      if (!shareIdentity.value?.ok) shareIdentity.value = null;
    }
    return shareIdentity.value;
  }
  // The shortcut, and who signed it: signer is null for an unsigned code.
  function readShortcutCode(text) {
    const code = String(text || "").replace(/\s+/g, "");
    const signedAt = code.indexOf(signedPrefix);
    if (signedAt >= 0) {
      const [body, key, signature] = code.slice(signedAt + signedPrefix.length).split(".");
      if (!body || !key || !signature) throw new Error(t("分享码不完整或被改动过"));
      if (typeof bridge?.verifyShareCode !== "function") throw new Error(t("这里核对不了签名：请在手机上的 App 里导入"));
      let check = {};
      try { check = JSON.parse(bridge.verifyShareCode(`${signedPrefix}${body}`, signature, key) || "{}"); } catch { check = {}; }
      if (!check.valid) throw new Error(t("签名对不上：分享码在签名后被改动过"));
      return { shortcut: decodeShortcut(body), signer: { fingerprint: check.fingerprint, own: shareIdentity()?.public_key === key } };
    }
    const at = code.indexOf(codePrefix);
    if (at < 0) throw new Error(t("这不是快捷操作的分享码"));
    const [body, checksum] = code.slice(at + codePrefix.length).split(".");
    if (!body || codeChecksum(body) !== checksum) throw new Error(t("分享码不完整或被改动过"));
    return { shortcut: decodeShortcut(body), signer: null };
  }

  // Authors whose shortcuts were imported here before (fingerprint → the first one's name).
  function knownAuthors() {
    try { return JSON.parse(localStorage.getItem(knownAuthorsKey) || "{}") || {}; } catch { return {}; }
  }
  function rememberAuthor(fingerprint, name) {
    const known = knownAuthors();
    if (known[fingerprint]) return;
    known[fingerprint] = { name: String(name).slice(0, 40), at: Date.now() };
    const kept = Object.entries(known).sort((a, b) => b[1].at - a[1].at).slice(0, 50);
    try { localStorage.setItem(knownAuthorsKey, JSON.stringify(Object.fromEntries(kept))); } catch { /* Only a convenience. */ }
  }
  function signerLine(signer) {
    if (!signer) return t("没有签名：看不出是谁做的，也不能确认没被改过");
    if (signer.own) return t("签名：你自己的");
    const known = knownAuthors()[signer.fingerprint];
    return known ? t("签名：指纹 {0}，你导入过这个人的{1}", signer.fingerprint, shortcutQuote(known.name))
      : t("签名：指纹 {0}，第一次见到。可以请对方在「可复用流程」页看自己的指纹，核对一致再装", signer.fingerprint);
  }

  // What a shared shortcut needs and touches, ahead of its steps.
  const sensitivePages = new Set(["accessibility", "security", "developer", "vpn", "apps", "app_details"]);
  const outsidePages = new Set(["url", "map", "web_search", "dial"]);
  // The payment firewall's words (PaymentFirewall.kt): a run stops at such a button.
  const moneyWords = /支付(?!宝)|付款|买单|转账|提现|充值|免密|提交订单|立即购买|确认购买|确认下单|^pay|payment|checkout|placeorder|buynow|transfer|withdraw|topup/i; // i18n-ignore: words on other apps' buttons
  function shortcutNeeds(shortcut) {
    const steps = shortcut.steps;
    const list = (items) => items.join(t("、"));
    const lines = [t("控制手机（无障碍服务）：按记下的步骤点击、输入和滑动")];
    const packages = [...new Set(steps.filter((step) => step.kind === "launch").map((step) => step.package))];
    if (packages.length) lines.push(t("打开应用：{0}", list(packages.map(appName))));
    const installed = new Set(appsOnPhone().map((app) => app.package));
    const missing = installed.size ? packages.filter((name) => !installed.has(name)) : [];
    if (missing.length) lines.push(t("这台手机上没装：{0}", list(missing)));
    const pages = steps.filter((step) => step.kind === "page").map((step) => step.request || {});
    const settingsPages = [...new Set(pages.filter((page) => !outsidePages.has(page.page)).map((page) => shortcutPages[page.page] || page.page))];
    if (settingsPages.length) lines.push(t("打开系统设置：{0}", list(settingsPages)));
    const links = pages.filter((page) => page.page === "url").map((page) => String(page.url || "").slice(0, 120));
    if (links.length) lines.push(t("打开网页：{0}", list(links)));
    const numbers = pages.filter((page) => page.page === "dial").map((page) => String(page.number || "").slice(0, 30));
    if (numbers.length) lines.push(t("填好号码打开拨号界面：{0}", list(numbers)));
    const typing = steps.filter((step) => step.kind === "type").map((step) => shortcutQuote(step.text));
    if (typing.length) lines.push(t("输入文字：{0}", list(typing)));
    const warnings = [];
    if (pages.some((page) => sensitivePages.has(page.page))) warnings.push(t("会打开安全相关的设置页，只在清楚它要做什么时安装"));
    const paying = steps.filter((step) => (step.kind === "tap" || step.kind === "find")
      && moneyWords.test(String(step.label || step.text || "").replace(/\s+/g, "")));
    if (paying.length) warnings.push(t("有付款类按钮（{0}）：运行到这一步会被拦下，要你自己点", list(paying.map((step) => shortcutQuote(step.label || step.text)))));
    return { lines, warnings };
  }

  $("btnImportShortcut").addEventListener("click", async () => {
    const status = $("shortcutsStatus");
    const text = window.prompt(t("粘贴快捷操作的分享码"), "");
    if (!text) return;
    let read;
    try { read = readShortcutCode(text); } catch (error) { status.textContent = error.message; return; }
    const shared = read.shortcut;
    // Who made it, what it needs, then every step in words.
    const needs = shortcutNeeds(shared);
    const review = [
      t("快捷操作{0}，共 {1} 步", shortcutQuote(shared.name), shared.steps.length),
      signerLine(read.signer),
      "",
      t("需要的权限和会做的事："),
      ...needs.lines.map((line) => `· ${line}`),
      ...needs.warnings.map((line) => `⚠ ${line}`),
      "",
      t("步骤："),
      ...shared.steps.slice(0, 30).map((step, index) => `${index + 1}. ${describeShortcutStep(step)}`),
      shared.steps.length > 30 ? t("……还有 {0} 步", shared.steps.length - 30) : null,
      "",
      t("只从你信任的人那里导入。确定安装？"),
    ].filter((line) => line !== null).join("\n");
    if (!window.confirm(review)) return;
    try {
      await postShortcut("/mobile/shortcuts", { name: shared.name.slice(0, 40), app: shared.app || null, steps: shared.steps });
      if (disposed) return;
      if (read.signer && !read.signer.own) rememberAuthor(read.signer.fingerprint, shared.name);
      status.textContent = t("已导入{0}", shortcutQuote(shared.name));
      void loadShortcuts();
    } catch (error) { if (!disposed) status.textContent = t("导入失败：{0}", error.message); }
  });

  // After a phone-control task: keep what it did as a shortcut.
  function offerShortcut(task) {
    if (!(task?.shortcutSteps > 0) || !task.card || task.card.querySelector(".shortcut-offer")) return;
    if (healing && task.inputText === healing.prompt) { offerHealedShortcut(task); return; }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button-secondary shortcut-offer";
    button.innerHTML = icon("zap");
    button.append(t("存为快捷操作（{0} 步，下次不用 AI）", task.shortcutSteps));
    button.addEventListener("click", async () => {
      const suggested = String(task.prompt || "").replace(/\s+/g, " ").trim().slice(0, 20) || t("快捷操作");
      const name = window.prompt(t("快捷操作的名字"), suggested);
      if (!name || !name.trim()) return;
      button.disabled = true;
      try {
        await postShortcut("/mobile/shortcuts/keep", { task_id: task.id, name: name.trim().slice(0, 40) });
        if (disposed) return;
        button.replaceChildren(t("已存为快捷操作：在「可复用流程」里可以编辑、运行和定时"));
        haptic(12);
      } catch (error) {
        if (disposed) return;
        button.disabled = false;
        notice(t("没存上：{0}", error.message));
      }
    });
    task.card.appendChild(button);
  }

  // Loaded whenever the workflows page opens.
  new MutationObserver(() => { if (!disposed && !$("settingsWorkflows").hidden) void loadShortcuts(); })
    .observe($("settingsWorkflows"), { attributes: true, attributeFilter: ["hidden"] });

  // ---- Hosted limits (2.0): how far phone work nobody approves step by step may go -------------
  async function loadHostedLimits() {
    try {
      const limits = await apiJson("/mobile/hosted-limits");
      if (disposed) return;
      $("hostedMaxSteps").value = limits.max_steps;
      $("hostedMaxMinutes").value = limits.max_minutes;
    } catch (error) { if (!disposed) $("hostedLimitsStatus").textContent = t("读取失败：{0}", error.message); }
  }
  $("hostedLimitsSection").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = $("hostedLimitsStatus");
    try {
      const limits = await postShortcut("/mobile/hosted-limits", {
        max_steps: Math.round(Number($("hostedMaxSteps").value)), max_minutes: Math.round(Number($("hostedMaxMinutes").value)),
      });
      if (disposed) return;
      status.textContent = t("已保存：最多 {0} 步、{1} 分钟", limits.max_steps, limits.max_minutes);
    } catch (error) { if (!disposed) status.textContent = t("保存失败：{0}", error.message); }
  });
  new MutationObserver(() => { if (!disposed && !$("settingsDoctor").hidden) void loadHostedLimits(); })
    .observe($("settingsDoctor"), { attributes: true, attributeFilter: ["hidden"] });