
  // ---- 「以后都这样做」(2.8): an answer's request as a scheduled task ------------------------------
  // Under an answer, one tap opens a sheet with the request as it was asked, how often and at what
  // time, filled in from the request's own words where it says ("每天早上 8 点", "每周", "8pm");
  // otherwise every day at this time. Nothing is created until the user confirms. The task runs in this
  // conversation, so it keeps what was said here, and its result arrives here (and as a notification
  // when those are on). A request that worked the phone keeps doing so, which needs it unlocked then.

  /** How often and when the request itself says, else every day at the next five minutes from now. */
  function repeatGuess(text, now = new Date()) {
    const value = String(text || "");
    const repeat = /每周|每星期|每个星期|每礼拜|weekly|every week/i.test(value) ? "604800" : "86400"; // i18n-ignore: words read from the request
    let hour = null, minute = 0;
    // A time of day only with its part of the day or as a clock ("3 点建议" is not three o'clock).
    const chinese = value.match(/(凌晨|早上|早晨|上午|中午|下午|傍晚|晚上)\s*(\d{1,2})\s*[点:：时]\s*(半|(\d{1,2})\s*分?)?/); // i18n-ignore: words read from the request
    const clock = value.match(/(?:^|[^\d])(\d{1,2})[:：](\d{2})(?!\d)/); // i18n-ignore: words read from the request
    const english = value.match(/\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/i);
    if (chinese && Number(chinese[2]) <= 24) {
      hour = Number(chinese[2]) % 24;
      minute = chinese[3] === "半" ? 30 : Number(chinese[4] || 0) % 60; // i18n-ignore: words read from the request
      if (/中午|下午|傍晚|晚上/.test(chinese[1]) && hour < 12) hour += 12; // i18n-ignore: words read from the request
    } else if (english && Number(english[1]) <= 12) {
      hour = Number(english[1]) % 12 + (english[3].toLowerCase() === "pm" ? 12 : 0);
      minute = Number(english[2] || 0) % 60;
    } else if (clock && Number(clock[1]) < 24 && Number(clock[2]) < 60) {
      hour = Number(clock[1]);
      minute = Number(clock[2]);
    }
    if (hour === null) {
      const next = new Date(now.getTime() + 5 * 60000);
      hour = next.getHours();
      minute = Math.ceil(next.getMinutes() / 5) * 5;
      if (minute === 60) { hour = (hour + 1) % 24; minute = 0; }
    }
    return { repeat, time: `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}` };
  }

  /** The first run: today at that time if it is still ahead, else the next day (or week). */
  function repeatFirstRun(time, repeat, now = new Date()) {
    const [hour, minute] = time.split(":").map(Number);
    const due = new Date(now);
    due.setHours(hour, minute, 0, 0);
    if (due.getTime() <= now.getTime() + 60000) due.setDate(due.getDate() + (repeat === "604800" ? 7 : 1));
    return due;
  }

  function openRepeatSheet(card) {
    if (!historyReady || !currentSessionId || disposed) return;
    let userCard = card.previousElementSibling;
    while (userCard && !(userCard.classList.contains("user") && !userCard.hidden)) userCard = userCard.previousElementSibling;
    const request = (userCard?.dataset.messageText || userCard?.dataset.displayText || "").trim();
    if (!request) { notice(t("找不到这条回答对应的请求")); return; }
    // The turn worked the phone: the scheduled run does too.
    let usedPhone = false;
    for (let item = userCard.nextElementSibling; item && item !== card; item = item.nextElementSibling) {
      if (/^android_/.test(item.dataset?.tool || "")) usedPhone = true;
    }
    const guess = repeatGuess(request);
    const layer = document.createElement("div");
    layer.className = "action-sheet repeat-sheet";
    layer.setAttribute("role", "dialog");
    layer.setAttribute("aria-modal", "true");
    const panel = document.createElement("form");
    panel.className = "action-sheet-panel repeat-panel";
    const heading = document.createElement("strong");
    heading.textContent = t("以后都这样做");
    const hint = document.createElement("small");
    hint.textContent = t("到时间会在这个对话里再做一次，完成后通知你（通知开着时）。可以在 菜单 → 定时任务 里修改或删除。");
    const field = (labelText, control) => {
      const label = document.createElement("label");
      const caption = document.createElement("span");
      caption.textContent = labelText;
      label.append(caption, control);
      return label;
    };
    const name = document.createElement("input");
    name.maxLength = 100;
    name.required = true;
    name.value = request.split("\n")[0].replace(/\s+/g, " ").slice(0, 24);
    const prompt = document.createElement("textarea");
    prompt.rows = 3;
    prompt.maxLength = 16384;
    prompt.required = true;
    prompt.value = request;
    const repeat = document.createElement("select");
    for (const [value, label] of [["86400", t("每天")], ["604800", t("每周这一天")], ["", t("只做一次")]]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      repeat.append(option);
    }
    repeat.value = guess.repeat;
    const time = document.createElement("input");
    time.type = "time";
    time.required = true;
    time.value = guess.time;
    const row = document.createElement("div");
    row.className = "repeat-when";
    row.append(field(t("多久一次"), repeat), field(t("时间"), time));
    const phone = document.createElement("input");
    phone.type = "checkbox";
    phone.checked = usedPhone;
    const phoneRow = document.createElement("label");
    phoneRow.className = "repeat-phone";
    phoneRow.hidden = !usedPhone;
    phoneRow.append(phone, t("操作手机（到时间需要手机解锁）"));
    const status = document.createElement("p");
    status.className = "page-status";
    status.setAttribute("role", "status");
    const actions = document.createElement("div");
    actions.className = "compare-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "button-secondary";
    cancel.textContent = t("取消");
    const create = document.createElement("button");
    create.type = "submit";
    create.className = "button-primary";
    create.textContent = t("创建定时任务");
    actions.append(cancel, create);
    panel.append(heading, hint, field(t("名称"), name), field(t("要做的事"), prompt), row, phoneRow, status, actions);
    layer.append(panel);
    document.body.append(layer);
    const shut = () => layer.remove();
    cancel.addEventListener("click", shut);
    layer.addEventListener("click", (event) => { if (event.target === layer) shut(); });
    panel.addEventListener("submit", async (event) => {
      event.preventDefault();
      create.disabled = true;
      status.textContent = "";
      const due = repeatFirstRun(time.value, repeat.value);
      try {
        await apiJson("/mobile/schedules", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: name.value.trim(), prompt: prompt.value.trim(), session_id: currentSessionId,
            model: settings.model, reasoning_effort: settings.reasoning_effort, due_at: due.toISOString(),
            repeat_seconds: repeat.value ? Number(repeat.value) : null, enabled: true, ...(phone.checked ? { phone_control: true } : {}) }) });
        shut();
        const when = repeat.value === "86400" ? t("每天 {0}", time.value)
          : repeat.value === "604800" ? t("每{0} {1}", due.toLocaleDateString(locale, { weekday: "long" }), time.value)
          : `${due.toLocaleDateString(locale, { month: "numeric", day: "numeric" })} ${time.value}`;
        notice(t("已创建定时任务「{0}」：{1}，在这个对话里运行", name.value.trim(), when));
      } catch (error) {
        status.textContent = t("没有创建：{0}", localizeError(error.message));
        create.disabled = false;
      }
    });
    name.focus();
  }
