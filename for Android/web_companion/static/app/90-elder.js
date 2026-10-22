
  // ---- 长辈模式 (elder mode): one big button to speak, answers read aloud ------------------------
  // Turned on in Menu → 长辈模式, usually by a family member. The settings live on the engine
  // (mobile_elder.py), which also asks the model for short spoken replies and care with scams. The
  // screen covers the app and drives the same conversation machinery, one thing at a time: the last
  // question and its answer, one big button (speak; stop while an answer is coming), a photo button
  // and a call button. Nothing is asked of the older person: the mode's conversation runs as under
  // full access, a step driven by outside content is refused (mobile_approval), and card and ID
  // numbers are covered before sending. Leaving takes a two-second press, and the PIN when the
  // family set one.
  // State is kept on the functions, not in top-level lets: earlier parts call these during start-up.
  function elderState() { return elderState.value || null; }
  function elderOn() { return elderState()?.enabled === true; }
  function elderExchanges() { return elderExchanges.list || (elderExchanges.list = []); }
  function elderShown() { return elderOn() && $("elderScreen")?.hidden === false; }

  async function loadElder(tries = 0) {
    try { elderState.value = await apiJson("/mobile/elder"); }
    catch {
      elderState.value = null;
      // Shown early (below) while the engine still starts: try again for a while.
      if (!disposed && !$("elderScreen").hidden && tries < 40) window.setTimeout(() => void loadElder(tries + 1), 3000);
      return;
    }
    if (disposed) return;
    elderRemember(elderOn());
    renderElderSettings();
    if (elderOn()) await showElderScreen();
    else if (!$("elderScreen").hidden) hideElderScreen();
  }

  // Remembered on the phone, so the next start shows the screen at once (elderEarly).
  function elderRemember(on) {
    try { window.localStorage.setItem("agent-mobile-elder-v1", on ? "1" : "0"); } catch { /* shown once loaded */ }
  }

  // On a slow phone the rest of the app takes a moment to load: the screen comes first.
  function elderEarly() {
    let on = false;
    try { on = window.localStorage.getItem("agent-mobile-elder-v1") === "1"; } catch { return; }
    if (!on) return;
    document.body.classList.add("elder-mode");
    $("elderScreen").hidden = false;
    elements.appShell.inert = true;
    elderToday();
    elderStatus(t("准备中..."));
  }

  async function saveElder(changes) {
    const value = await apiJson("/mobile/elder", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes) });
    elderState.value = value;
    renderElderSettings();
    return value;
  }

  // The conversation the mode uses: one a day, so its history and what goes to the model stay small
  // (what matters is kept in the phone's memory). Made again when archived or deleted.
  async function elderSession() {
    const kept = elderState()?.session_id;
    const listed = kept && sessions.find((session) => session.id === kept);
    const today = (value) => new Date(value).toDateString() === new Date().toDateString();
    if (listed && listed.archived !== true && (!listed.updated_at || today(listed.updated_at))) return kept;
    if (listed && listed.archived !== true) {
      try { await apiJson(`/sessions/${encodeURIComponent(kept)}/archive`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ archived: true }) }); }
      catch { /* An older conversation left in the list is harmless. */ }
    }
    const created = await apiJson("/sessions", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: t("长辈模式"), ...(currentWorkspaceId ? { workspace_id: currentWorkspaceId } : {}) }) });
    await saveElder({ session_id: created.id });
    await loadSessions(created.id);
    elderExchanges.list = [];
    return created.id;
  }

  // Before each question: still today's conversation (the screen may have stayed up overnight).
  async function elderKeepToday() {
    elderToday();
    const sessionId = await elderSession();
    if (sessionId !== currentSessionId) await switchSession(sessionId);
  }

  async function showElderScreen() {
    closeMenu({ instant: true });
    closeDrawer();
    document.body.classList.add("elder-mode");
    $("elderScreen").hidden = false;
    // The app underneath takes no focus or touches while the screen is up.
    elements.appShell.inert = true;
    elderToday();
    elderCallButton();
    if ($("elderStatus").textContent === t("准备中...")) elderStatus("");
    try {
      const sessionId = await elderSession();
      if (sessionId !== currentSessionId) await switchSession(sessionId);
    } catch (error) { elderStatus(t("暂时连不上，请稍后再试：{0}", error.message)); }
    // Opened again later: the last question and answer are there, from the conversation's history.
    if (!elderExchanges().length) {
      for (const card of elements.timelineList.querySelectorAll(".message-card.user, .message-card.assistant")) {
        if (card.classList.contains("user")) elderExchanges().push({ asked: card.dataset.displayText || card.dataset.messageText || "", answer: "" });
        else if (elderExchanges().length) elderExchanges()[elderExchanges().length - 1].answer = card.dataset.messageText || "";
      }
    }
    renderElderTalk();
    renderElderButton();
    $("elderSpeak").focus({ preventScroll: true });
  }

  function hideElderScreen() {
    void stopReading();
    document.body.classList.remove("elder-mode");
    $("elderScreen").hidden = true;
    elements.appShell.inert = false;
  }

  function elderToday() {
    const now = new Date();
    $("elderToday").textContent = now.toLocaleDateString(locale, { month: "long", day: "numeric", weekday: "long" });
  }

  // Shown once the family left a number.
  function elderCallButton() {
    const value = elderState() || {};
    $("elderCall").hidden = !value.family_phone;
    $("elderCallLabel").textContent = value.family_name ? t("打给{0}", value.family_name) : t("打给家人");
  }

  function elderStatus(text) { $("elderStatus").textContent = text || ""; }

  // The big button speaks; while an answer is coming it stops instead.
  function renderElderButton(busy = !!activeTask) {
    $("elderSpeak").classList.toggle("stop", busy);
    $("elderSpeakIcon").innerHTML = icon(busy ? "square" : "mic");
    $("elderSpeakLabel").textContent = busy ? t("停下") : t("按一下，说话");
  }

  // Only the last question and its answer, in large type; with nothing asked yet, what can be said.
  function renderElderTalk() {
    const talk = $("elderTalk");
    const last = elderExchanges()[elderExchanges().length - 1];
    if (!last) {
      const hint = document.createElement("div");
      hint.className = "elder-hint";
      const lead = document.createElement("p");
      lead.textContent = t("按下面的大按钮，说出想问的事。");
      const examples = document.createElement("p");
      examples.className = "elder-examples";
      examples.textContent = [t("比如可以说："), t("“明天天气怎么样？”"), t("“每天早上八点提醒我吃药。”"), t("“微信的字怎么调大？”")].join("\n");
      hint.append(lead, examples);
      talk.replaceChildren(hint);
      return;
    }
    const block = document.createElement("div");
    block.className = "elder-exchange";
    const asked = document.createElement("p");
    asked.className = "elder-asked";
    asked.textContent = last.asked;
    block.append(asked);
    if (last.answer) {
      const answer = document.createElement("div");
      answer.className = "elder-answer";
      setMarkdown(answer, last.answer);
      const again = document.createElement("button");
      again.type = "button";
      again.id = "elderRepeat";
      again.className = "elder-again";
      again.addEventListener("click", () => {
        if (elderSay.reading) { void stopReading(); elderSay.reading = null; renderElderRepeat(); }
        else void elderSay(spokenText(last.answer), true);
      });
      block.append(answer, again);
    }
    talk.replaceChildren(block);
    renderElderRepeat();
    talk.scrollTop = 0;
  }

  function renderElderRepeat() {
    const again = $("elderRepeat");
    if (!again) return;
    const reading = !!elderSay.reading && speakingId === elderSay.reading;
    again.innerHTML = `${icon(reading ? "square" : "volume-2")}<span></span>`;
    again.lastChild.textContent = reading ? t("别读了") : t("再听一遍");
  }

  // Reads a text aloud when the family left reading on (always for 再听一遍); slower when they
  // chose so. With [wait], it returns once the speech ended.
  async function elderSay(text, force = false, wait = false) {
    if (!text || (!force && elderState()?.read_aloud === false)) return;
    await stopReading();
    let id;
    try {
      const started = await apiJson("/mobile/speech/speak", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.slice(0, 4000), rate: elderState()?.slow_speech === false ? 1 : 0.85 }) });
      if (started.accepted === false) return;
      id = started.request_id;
    } catch { return; } // Reading is a help; the text stays on the screen.
    speakingId = id;
    elderSay.reading = id;
    renderElderRepeat();
    const ended = (async () => {
      for (let tries = 0; tries < 300 && speakingId === id && !disposed; tries += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 400));
        let state = "";
        try { state = (await apiJson(`/mobile/speech/status?id=${encodeURIComponent(id)}`)).state || ""; } catch { break; }
        if (["completed", "failed", "stopped", "cancelled", "interrupted", "unknown"].includes(state)) break;
      }
      if (speakingId === id) speakingId = null;
      if (elderSay.reading === id) elderSay.reading = null;
      if (!disposed) renderElderRepeat();
    })();
    if (wait) await ended;
  }

  function spokenText(markdown) {
    const box = document.createElement("div");
    setMarkdown(box, markdown);
    box.querySelectorAll("pre, .message-card-json, .reply-card").forEach((element) => element.remove());
    return (box.textContent || "").replace(/\s+/g, " ").trim();
  }

  // Listening: the phone's voice input (offline or the system's) brings back what was said.
  function elderListen() {
    if (typeof bridge?.requestVoiceInput !== "function") { elderStatus(t("这台手机不能语音输入，可以点下面的「打字」。")); return; }
    void stopReading();
    elderListen.until = Date.now() + 120000;
    elderStatus(t("请说话，说完停一下。"));
    bridge.requestVoiceInput();
  }

  // What was said, from receiveSharedText while the mode listens; false when it was not for here.
  function elderHeard(text) {
    if (!elderShown() || Date.now() > (elderListen.until || 0)) return false;
    elderListen.until = 0;
    const said = String(text).trim();
    if (said) void elderSend(said);
    else elderStatus("");
    return true;
  }

  async function elderSend(message, shown = message) {
    if (activeTask) { elderStatus(t("还在回答上一个问题，请稍等。")); return; }
    // A photo just taken belongs to the conversation it was attached to.
    if (!attachments.length) { try { await elderKeepToday(); } catch { /* Stays in the conversation it has. */ } }
    // Bank card and ID numbers never go out from here: they are covered first, without the
    // three-way question the app asks otherwise (65-privacy.js).
    const found = cloudModel() ? privateParts(message) : [];
    for (const item of found) { message = message.split(item.value).join(item.masked); shown = shown.split(item.value).join(item.masked); }
    elderExchanges().push({ asked: shown, answer: "" });
    renderElderTalk();
    elderStatus(found.length ? t("卡号、身份证号已经遮住，没有发出去。正在想，请稍等…") : t("正在想，请稍等…"));
    elements.promptInput.value = message;
    elements.promptInput.dispatchEvent(new Event("input", { bubbles: true }));
    elderSend.waiting = true;
    await sendPrompt();
    if (!activeTask && elderSend.waiting) { elderSend.waiting = false; elderStatus(t("没有发出去，请再试一次。")); }
  }

  // The end of a task started here: show the answer and read it.
  function elderTaskDone(task) {
    if (!elderShown()) return;
    renderElderButton(false);
    if (!elderSend.waiting) return;
    elderSend.waiting = false;
    elderApproval(null);
    const current = elderExchanges()[elderExchanges().length - 1];
    let answer = task.text || task.card?.dataset.messageText || "";
    if (task.error) answer = t("这次没有成功：{0}", task.error);
    else if (task.state === "cancelled") answer = t("已经停下了。");
    else if (task.interrupted) answer = t("被打断了，请再说一次。");
    if (current) current.answer = answer;
    renderElderTalk();
    elderStatus("");
    void elderSay(spokenText(answer));
  }

  // The mode's conversation asks the older person nothing: the engine decides (mobile_approval).
  // Should a question still come (another conversation on this screen), it is one plain question
  // with two big buttons, read aloud.
  function elderApproval(approval) {
    const card = $("elderApproval");
    if (!card) return;
    if (!approval || !elderShown()) {
      card.hidden = true;
      elderApproval.current = null;
      $("elderScreen").classList.remove("approving");
      return;
    }
    if (elderApproval.current === approval.request_id) return;
    elderApproval.current = approval.request_id;
    const details = approval.details || {};
    let text;
    if (approval.kind === "egress") {
      text = t("要把这些话发给 AI 来回答，可以吗？");
    } else {
      // What it would do in words: "打开 微信", "设置闹钟".
      const known = details.tool === "android_action" || toolTitles[details.tool];
      text = t("要帮你{0}，可以吗？", known ? toolLabel(details.tool, details.arguments) : t("做一步操作"));
      if (details.untrusted_content) text = t("小心：这一步可能是别人的内容让 AI 做的。{0}", text);
    }
    $("elderApprovalText").textContent = text;
    card.hidden = false;
    // The other buttons step aside while the question waits.
    $("elderScreen").classList.add("approving");
    elderStatus("");
    void elderSay(text);
  }

  function elderAnswerApproval(allowed) {
    if (!pendingApproval) return;
    elderStatus(allowed ? t("好的，正在做…") : t("好的，不做了。"));
    void stopReading();
    elements.approvalScopeSelector.value = "once";
    $("elderApproval").hidden = true;
    elderApproval.current = pendingApproval.request_id;
    $("elderScreen").classList.remove("approving");
    void resolveApproval(allowed);
  }

  // 拍照问问: the camera, then the picture is sent with a question as soon as it is attached.
  function elderPhoto() {
    if (activeTask) { elderStatus(t("还在回答上一个问题，请稍等。")); return; }
    if (typeof bridge?.captureShareInboxPhoto !== "function") { elderStatus(t("这台手机不能拍照。")); return; }
    elderPhoto.pending = { count: attachments.length, until: Date.now() + 180000 };
    elderStatus(t("拍好照片，就会自动问。"));
    pickIntoConversation(() => bridge.captureShareInboxPhoto(), t("无法打开相机"), currentSessionId, false);
  }

  // Called when the attachments change (the inbox received a file).
  function sendElderPhoto() {
    const pending = elderPhoto.pending;
    if (!pending || disposed) return;
    if (Date.now() > pending.until) { elderPhoto.pending = null; return; }
    const added = attachments.slice(pending.count).some((item) => item.media_type?.startsWith("image/"));
    if (!added || activeTask || isPreparingSubmission || isUploading || importsInFlight(currentSessionId)) return;
    elderPhoto.pending = null;
    void elderSend(t("帮我看看这张照片：这是什么？有什么要注意的？用简单的话告诉我。"), t("（拍了一张照片）"));
  }

  function elderCall() {
    const phone = elderState()?.family_phone;
    if (!phone) return;
    if (typeof bridge?.dialNumber !== "function") { elderStatus(t("这台手机不能打电话。")); return; }
    let result = {};
    try { result = JSON.parse(bridge.dialNumber(phone)); } catch { result = { ok: false }; }
    elderStatus(result.ok ? t("已经拨好号码，按绿色的键就能打出去。") : localizeError(result.error) || t("没能打开拨号。"));
  }

  function elderError(message) {
    if (message === "wrong PIN") return t("密码不对。");
    if (/^too many wrong PINs/.test(message)) return t("密码错的次数太多，请过一分钟再试。");
    return localizeError(message);
  }

  async function elderLeave() {
    let pin;
    if (elderState()?.has_pin) {
      pin = window.prompt(t("请输入退出密码"));
      if (pin === null) return;
    }
    try {
      await saveElder({ enabled: false, ...(pin !== undefined ? { current_pin: pin } : {}) });
      elderRemember(false);
      hideElderScreen();
      notice(t("已退出长辈模式"), "info");
    } catch (error) {
      elderStatus(elderError(error.message));
    }
  }

  // Menu → 长辈模式: the family sets it up, then starts it.
  function renderElderSettings() {
    const value = elderState();
    if (!value || !$("settingsElder")) return;
    if (document.activeElement !== $("elderFamilyName")) $("elderFamilyName").value = value.family_name || "";
    if (document.activeElement !== $("elderFamilyPhone")) $("elderFamilyPhone").value = value.family_phone || "";
    $("elderReadAloud").checked = value.read_aloud !== false;
    $("elderSlowSpeech").checked = value.slow_speech !== false;
    $("btnElderPinSave").textContent = value.has_pin ? t("更换密码") : t("设置密码");
    $("btnElderPinRemove").hidden = !value.has_pin;
  }

  async function elderSettingsChange(changes, done = "") {
    try { await saveElder(changes); pageStatus($("elderSettingsStatus"), done); }
    catch (error) { pageStatus($("elderSettingsStatus"), elderError(error.message), true); }
  }

  async function elderPinChange(pin) {
    const changes = { pin };
    if (elderState()?.has_pin) {
      const current = window.prompt(t("请输入现在的退出密码"));
      if (current === null) return;
      changes.current_pin = current;
    }
    await elderSettingsChange(changes, pin ? t("退出密码已设置") : t("已去掉退出密码"));
    $("elderPin").value = "";
  }

  $("btnElderPage")?.addEventListener("click", () => { if (setSettingsPage("elder")) void loadElder(); });
  $("elderFamilyName")?.addEventListener("change", (event) => void elderSettingsChange({ family_name: event.target.value }, t("已保存")));
  $("elderFamilyPhone")?.addEventListener("change", (event) => void elderSettingsChange({ family_phone: event.target.value }, t("已保存")));
  $("elderReadAloud")?.addEventListener("change", (event) => void elderSettingsChange({ read_aloud: event.target.checked }));
  $("elderSlowSpeech")?.addEventListener("change", (event) => void elderSettingsChange({ slow_speech: event.target.checked }));
  $("btnElderPinSave")?.addEventListener("click", () => {
    const pin = $("elderPin").value.trim();
    if (!/^\d{4,6}$/.test(pin)) { pageStatus($("elderSettingsStatus"), t("密码是 4 到 6 位数字"), true); return; }
    void elderPinChange(pin);
  });
  $("btnElderPinRemove")?.addEventListener("click", () => void elderPinChange(""));
  $("btnElderStart")?.addEventListener("click", async () => {
    try { await saveElder({ enabled: true }); elderRemember(true); await showElderScreen(); }
    catch (error) { pageStatus($("elderSettingsStatus"), localizeError(error.message), true); }
  });
  $("elderSpeak")?.addEventListener("click", () => {
    if (!activeTask) { elderListen(); return; }
    void stopReading();
    void stopTask();
    elderStatus(t("好的，停下了。"));
  });
  // Typing instead of speaking (a noisy room, a voice that is hard to recognize).
  const elderTyping = (on) => {
    $("elderTypeForm").hidden = !on;
    $("elderScreen").classList.toggle("typing", on);
    if (on) $("elderTypeInput").focus();
  };
  $("elderTypeToggle")?.addEventListener("click", () => elderTyping(true));
  $("elderTypeCancel")?.addEventListener("click", () => { $("elderTypeInput").value = ""; elderTyping(false); });
  $("elderTypeForm")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = $("elderTypeInput").value.trim();
    if (!text || activeTask) return;
    $("elderTypeInput").value = "";
    elderTyping(false);
    void elderSend(text);
  });
  $("elderPhoto")?.addEventListener("click", elderPhoto);
  $("elderCall")?.addEventListener("click", elderCall);
  $("elderApprove")?.addEventListener("click", () => elderAnswerApproval(true));
  $("elderReject")?.addEventListener("click", () => elderAnswerApproval(false));
  // Leaving takes a two-second press, so a passing touch does not end the mode.
  (() => {
    const exit = $("elderExit");
    if (!exit) return;
    let timer = null;
    // Lifted too early: say how it works.
    const cancel = (explain) => {
      if (!timer) return;
      window.clearTimeout(timer);
      timer = null;
      exit.classList.remove("holding");
      if (explain) elderStatus(t("要退出，请按住这个按钮两秒。"));
    };
    // The WebView treats a held touch as a long press after half a second and cancels the pointer;
    // without its long-press menu the press lasts until the finger lifts.
    exit.addEventListener("touchstart", (event) => event.preventDefault(), { passive: false });
    exit.addEventListener("contextmenu", (event) => event.preventDefault());
    exit.addEventListener("pointerdown", () => {
      cancel(false);
      exit.classList.add("holding");
      timer = window.setTimeout(() => { timer = null; exit.classList.remove("holding"); void elderLeave(); }, 2000);
    });
    exit.addEventListener("pointerup", () => cancel(true));
    for (const type of ["pointerleave", "pointercancel"]) exit.addEventListener(type, () => cancel(false));
  })();
  elderEarly();
