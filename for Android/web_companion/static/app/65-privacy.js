
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

  let privacyAsking = false;
  /** "send", "mask" or "cancel" for a message holding personal numbers. */
  function askPrivacy(found) {
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
      $("sessionSheetTitle").textContent = t("这条消息里有个人信息");
      $("sessionSheetStatus").textContent = t("要发给云端模型的内容里有：{0}。遮盖后 AI 只看到前后几位。想完全不出手机，可以在「模型与思考」里换成本机模型。",
        found.map((item) => `${item.kind} ${item.masked}`).join(t("、")));
      $("sessionSheetTags").hidden = true;
      $("sessionSheetActions").replaceChildren(
        sheetButton("shield", t("遮盖后发送"), () => done("mask")),
        sheetButton("send", t("原样发送"), () => done("send")),
        sheetButton("x", t("取消"), () => done("cancel")),
      );
      sheet.hidden = false;
      watcher.observe(sheet, { attributes: true, attributeFilter: ["hidden"] });
    });
  }

  /** Whether a typed message must be asked about first (checked without waiting, for every send). */
  function privacyNeeded() {
    return privacyAsking || (cloudModel() && privateParts(elements.promptInput.value).length > 0);
  }

  /** Before a typed message goes out: false when the user cancelled. May mask the composer's text. */
  async function privacyCheck() {
    const text = elements.promptInput.value;
    if (privacyAsking || !text.trim() || !cloudModel()) return !privacyAsking;
    const found = privateParts(text);
    if (!found.length) return true;
    privacyAsking = true;
    try {
      const choice = await askPrivacy(found);
      if (disposed || choice === "cancel") return false;
      if (choice === "mask") {
        let masked = text;
        for (const item of found) masked = masked.split(item.value).join(item.masked);
        elements.promptInput.value = masked;
        elements.promptInput.dispatchEvent(new Event("input", { bubbles: true }));
      }
      return true;
    } finally { privacyAsking = false; }
  }
