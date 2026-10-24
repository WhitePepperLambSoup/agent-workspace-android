
  // ---- Privacy routing (2.0): personal numbers stop before they go to a cloud model ------------
  // A message about to go to a cloud provider is checked for Chinese ID card numbers and bank card
  // numbers (only ones whose check digit is right). The user then masks them, sends as is, or
  // cancels. Nothing is checked for the on-device model: that never leaves the phone.
  const ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2];
  function validIdCard(value) {
    if (!/^\d{17}[\dXx]$/.test(value)) return false;
    const sum = ID_WEIGHTS.reduce((total, weight, index) => total + weight * Number(value[index]), 0);
    return "10X98765432"[sum % 11] === value[17].toUpperCase();
  }
  function validBankCard(digits) {
    if (!/^\d{16,19}$/.test(digits)) return false;
    let sum = 0;
    for (let index = 0; index < digits.length; index += 1) {
      let digit = Number(digits[digits.length - 1 - index]);
      if (index % 2 === 1) { digit *= 2; if (digit > 9) digit -= 9; }
      sum += digit;
    }
    return sum % 10 === 0;
  }
  function maskNumber(value) { return value.length <= 8 ? "*".repeat(value.length) : `${value.slice(0, 4)}${"*".repeat(value.length - 8)}${value.slice(-4)}`; }

  /** The personal numbers in this text: [{kind, value, masked}]. */
  function privateParts(text) {
    const found = [];
    for (const match of String(text).matchAll(/(?<![\dXx])\d{17}[\dXx](?![\dXx])/g)) {
      if (validIdCard(match[0])) found.push({ kind: t("身份证号"), value: match[0], masked: maskNumber(match[0]) });
    }
    for (const match of String(text).matchAll(/(?<!\d)\d(?:[ -]?\d){15,18}(?!\d)/g)) {
      const digits = match[0].replace(/[ -]/g, "");
      if (found.some((item) => item.value === digits) || validIdCard(digits)) continue;
      if (validBankCard(digits)) found.push({ kind: t("银行卡号"), value: match[0], masked: maskNumber(digits) });
    }
    return found;
  }

  function cloudModel() {
    const base = String(settings.base_url || "");
    return Boolean(base) && !base.includes("/embedded-qwen/") && !/^https?:\/\/(127\.0\.0\.1|localhost|\[::1\])[:/]/i.test(base);
  }

  // The on-device model that can answer one message instead (mobile_privacy_route), read when needed.
  async function localRoute() {
    if (localRoute.value && Date.now() - localRoute.at < 60_000) return localRoute.value;
    const value = await apiJson("/mobile/privacy-route").catch(() => ({ local_model: null }));
    localRoute.value = value.local_model ? value : null;
    localRoute.at = Date.now();
    return localRoute.value;
  }

  // What to do without asking (Settings → permissions), kept on this phone: for personal numbers
  // "ask", "local" or "mask"; for a message sent with no network "ask", "wait" or "local".
  const routeKey = "agent-privacy-route-v1";
  function routeChoice() {
    const value = readStorage(routeKey, {}) || {};
    return { numbers: value.numbers || "ask", offline: value.offline || "ask" };
  }

  let privacyAsking = false;
  function askSheet(title, text, buttons) {
    return new Promise((resolve) => {
      const sheet = $("sessionSheet");
      let settled = false;
      const done = (choice) => {
        if (settled) return;
        settled = true;
        watcher.disconnect();
        sheet.hidden = true;
        resolve(choice);
      };
      // Closing the sheet any other way (backdrop, Back) cancels.
      const watcher = new MutationObserver(() => { if (sheet.hidden) done("cancel"); });
      $("sessionSheetTitle").textContent = title;
      $("sessionSheetStatus").textContent = text;
      $("sessionSheetTags").hidden = true;
      $("sessionSheetActions").replaceChildren(...buttons.map(([symbol, label, choice]) => sheetButton(symbol, label, () => done(choice))));
      sheet.hidden = false;
      watcher.observe(sheet, { attributes: true, attributeFilter: ["hidden"] });
    });
  }

  // Measured on a Snapdragon 888: the first on-device answer took 20 minutes (the system prompt and
  // tool descriptions, ~24k tokens), the next one 21 s with that prefix saved (local_model_jni.cpp).
  function localFirstNote() {
    return "\n\n" + t("本机模型第一次回答要先处理一遍工具说明，可能要十几分钟；之后每次几十秒。");
  }

  /** "local", "mask", "send" or "cancel" for a message holding personal numbers. */
  function askPrivacy(found, local) {
    const numbers = found.map((item) => `${item.kind} ${item.masked}`).join(t("、"));
    return askSheet(t("这条消息里有个人信息"), local
      ? t("要发给云端模型的内容里有：{0}。可以让手机上的 {1} 回答，内容不出手机；或者遮盖后发给云端，AI 只看到前后几位。", numbers, (local.title || local.local_model).split(" · ")[0]) + localFirstNote()
      : t("要发给云端模型的内容里有：{0}。遮盖后 AI 只看到前后几位。下载一个本机模型后，这类消息可以在手机上回答。", numbers), [
      ...(local ? [["cpu", t("用本机模型回答"), "local"]] : []),
      ["shield", t("遮盖后发送"), "mask"],
      ["send", t("原样发送"), "send"],
      ["x", t("取消"), "cancel"],
    ]);
  }

  /** "wait", "local" or "cancel" for a message sent with no network. */
  function askOffline(local) {
    return askSheet(t("现在没有网络"), local
      ? t("可以等联网后自动发送（App 在后台也会发），或者现在让手机上的 {0} 回答。", (local.title || local.local_model).split(" · ")[0]) + localFirstNote()
      : t("联网后会自动发送，App 在后台也会发。"), [
      ["send", t("联网后自动发送"), "wait"],
      ...(local ? [["cpu", t("用本机模型回答"), "local"]] : []),
      ["x", t("取消"), "cancel"],
    ]);
  }

  /** Whether a typed message must be asked about first (checked without waiting, for every send). */
  function privacyNeeded() {
    return privacyAsking || (cloudModel() && (navigator.onLine === false || privateParts(elements.promptInput.value).length > 0));
  }

  /**
   * Before a typed message goes out: false when the user cancelled, else how to send it
   * ({onDevice} or {waitForNetwork}, or nothing special). May mask the composer's text.
   */
  async function privacyCheck() {
    const text = elements.promptInput.value;
    if (privacyAsking) return false;
    if (!text.trim() || !cloudModel()) return {};
    const found = privateParts(text);
    const offline = navigator.onLine === false;
    if (!found.length && !offline) return {};
    privacyAsking = true;
    try {
      const local = await localRoute();
      const choice = routeChoice();
      if (found.length) {
        const decision = choice.numbers === "local" && local ? "local" : choice.numbers === "mask" ? "mask" : await askPrivacy(found, local);
        if (disposed || decision === "cancel") return false;
        if (decision === "local") return { onDevice: true };
        if (decision === "mask") {
          let masked = text;
          for (const item of found) masked = masked.split(item.value).join(item.masked);
          elements.promptInput.value = masked;
          elements.promptInput.dispatchEvent(new Event("input", { bubbles: true }));
        }
      }
      if (!offline) return {};
      const next = choice.offline === "wait" ? "wait" : choice.offline === "local" && local ? "local" : await askOffline(local);
      if (disposed || next === "cancel") return false;
      return next === "local" ? { onDevice: true } : { waitForNetwork: true };
    } finally { privacyAsking = false; }
  }

  // Settings → permissions: the two defaults above.
  function syncRouteSettings() {
    const choice = routeChoice();
    $("privacyNumbersRoute").value = choice.numbers;
    $("privacyOfflineRoute").value = choice.offline;
  }
  for (const [id, key] of [["privacyNumbersRoute", "numbers"], ["privacyOfflineRoute", "offline"]]) {
    $(id).addEventListener("change", () => writeStorage(routeKey, { ...routeChoice(), [key]: $(id).value }));
  }
  syncRouteSettings();

  // A task that failed because the network went away is sent again once the phone is online.
  window.addEventListener("online", () => {
    if (disposed || activeTask || !retryTask?.offlineFailure || !retryTask.inputText) return;
    retryTask.offlineFailure = false;
    void sendPrompt(retryTask.inputText, retryTask.attachments);
  });

  // A reply the on-device model gave says so above it.
  function markOnDevice(card) {
    const badge = card?.querySelector(".role-badge");
    if (!badge || badge.querySelector(".on-device")) return;
    const tag = document.createElement("span");
    tag.className = "on-device";
    tag.textContent = t("本机模型");
    badge.append(tag);
  }
