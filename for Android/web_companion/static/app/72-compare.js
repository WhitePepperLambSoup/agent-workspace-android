
  // ---- Compare: the same question answered by another model, one above the other ----------------
  // The conversation is forked up to this reply (mobile_session_fork.py) and the question asked again
  // there with the other model (a regenerate in the fork), so the original stays as it is. Models of
  // the current provider only: a task names its model, not its provider.
  const terminalTaskStates = new Set(["succeeded", "failed", "cancelled", "interrupted"]);

  // From the start of a task's events: the model's own time (each call from request to answer, so
  // waiting for an approval does not count), the tokens it used, and its last answer.
  function taskSummary(events, from) {
    let input = 0, output = 0, answer = "", modelTime = 0, calls = 0, asked = null;
    for (let index = from + 1; index < events.length; index += 1) {
      const event = events[index];
      const data = event.data || {};
      const when = Date.parse(event.created_at || "");
      if (event.type === "model.requested") asked = when;
      if (event.type === "model.completed" && Number.isFinite(asked) && Number.isFinite(when)) { modelTime += when - asked; calls += 1; asked = null; }
      if (event.type === "usage.updated") { input += Number(data.input_tokens) || 0; output += Number(data.output_tokens) || 0; }
      if (event.type === "message.created" && data.role === "assistant" && data.content) answer = String(data.content);
      if (event.type?.startsWith("mobile.task.") && terminalTaskStates.has(data.state || event.type.split(".").pop())) break;
      if (event.type === "mobile.task.created") break;
    }
    return { input, output, answer, seconds: calls ? Math.max(0, Math.round(modelTime / 100) / 10) : null };
  }

  function summaryLine(summary) {
    const parts = [];
    if (summary.seconds !== null) parts.push(t("模型用时 {0} 秒", summary.seconds));
    if (summary.input || summary.output) parts.push(t("输入 {0} · 输出 {1} tokens", summary.input.toLocaleString(locale), summary.output.toLocaleString(locale)));
    return parts.join(" · ");
  }

  function compareColumn(label) {
    const section = document.createElement("section");
    section.className = "compare-answer";
    const head = document.createElement("header");
    const name = document.createElement("strong");
    name.textContent = label;
    const detail = document.createElement("small");
    const body = document.createElement("div");
    body.className = "message-body";
    head.append(name, detail);
    section.append(head, body);
    return { section, name, detail, body };
  }

  async function compareWithModel(card) {
    if (!historyReady || !currentSessionId || isLoadingSession || activeTask) return;
    let userCard = card;
    while (userCard && !(userCard.classList.contains("user") && !userCard.hidden)) userCard = userCard.previousElementSibling;
    if (!userCard) return;
    const sourceId = currentSessionId;
    const layer = document.createElement("div");
    layer.className = "action-sheet compare-sheet";
    layer.setAttribute("role", "dialog");
    layer.setAttribute("aria-modal", "true");
    const panel = document.createElement("div");
    panel.className = "action-sheet-panel compare-panel";
    const title = document.createElement("strong");
    title.textContent = t("换个模型对比");
    const pick = document.createElement("div");
    pick.className = "compare-pick";
    const hint = document.createElement("small");
    hint.textContent = t("选一个模型回答同一个问题。原对话不变，另一个回答在分出的新对话里。");
    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = t("搜索模型");
    search.setAttribute("aria-label", t("搜索模型"));
    const list = document.createElement("div");
    list.className = "action-sheet-list";
    pick.append(hint, search, list);
    const columns = document.createElement("div");
    columns.className = "compare-columns";
    columns.hidden = true;
    const status = document.createElement("p");
    status.className = "page-status";
    status.setAttribute("role", "status");
    const actions = document.createElement("div");
    actions.className = "compare-actions";
    const close = document.createElement("button");
    close.type = "button";
    close.className = "button-secondary";
    close.textContent = t("关闭");
    const keep = document.createElement("button");
    keep.type = "button";
    keep.className = "button-primary";
    keep.textContent = t("用这个回答继续");
    keep.hidden = true;
    actions.append(close, keep);
    panel.append(title, pick, columns, status, actions);
    layer.append(panel);
    document.body.append(layer);

    let fork = null, taskId = null, finished = false, closed = false;
    const shut = async (keepFork) => {
      if (closed) return;
      closed = true;
      layer.remove();
      if (!fork || keepFork) return;
      // The comparison's conversation is put away (archived, so it can still be found).
      try {
        if (taskId && !finished) await apiJson(`/mobile/tasks/${encodeURIComponent(taskId)}/cancel`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        await apiJson(`/sessions/${encodeURIComponent(fork.id)}/archive`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ archived: true }) });
      } catch { /* It stays in the list; the user can archive it there. */ }
    };
    close.addEventListener("click", () => void shut(false));
    layer.addEventListener("click", (event) => { if (event.target === layer && !fork) void shut(false); });
    keep.addEventListener("click", () => { void shut(true).then(() => switchSession(fork.id, fork.title)); });

    const run = async (model) => {
      pick.hidden = true;
      columns.hidden = false;
      const original = compareColumn(t("原回答"));
      const other = compareColumn(model);
      setMarkdown(original.body, card.dataset.messageText || "");
      other.detail.textContent = t("准备中...");
      columns.append(original.section, other.section);
      try {
        const eventId = await userEventIdFor(userCard);
        const forked = await apiJson("/mobile/sessions/fork", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sourceId, message_event_id: eventId, keep_reply: true,
            title: t("{0}（{1}）", sessionTitle(sourceId), model) }) });
        fork = forked.session;
        if (forked.model) original.name.textContent = t("原回答 · {0}", forked.model);
        const efforts = supportedEfforts(model);
        const effort = efforts.includes(settings.reasoning_effort) ? settings.reasoning_effort : efforts.includes("auto") ? "auto" : efforts[0];
        const submitted = await apiJson("/mobile/tasks", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: fork.id, prompt: userCard.dataset.messageText || userCard.dataset.displayText || "",
            model, ...(effort ? { reasoning_effort: effort } : {}), rewind_from_event_id: forked.message_event_id,
            rewind_reason: "regenerate", request_id: window.crypto?.randomUUID?.() || `compare-${Date.now()}` }) });
        taskId = submitted.task.task_id;
        const started = Date.now();
        let state = submitted.task.state;
        while (!closed && !terminalTaskStates.has(state)) {
          other.detail.textContent = t("正在回答...（{0} 秒）", Math.round((Date.now() - started) / 1000));
          await new Promise((resolve) => setTimeout(resolve, 1500));
          if (closed || disposed) return;
          const snapshot = await apiJson(`/mobile/tasks/${encodeURIComponent(taskId)}`);
          state = snapshot.task.state;
          // Approvals are answered in the new conversation itself.
          if (state === "waiting_approval") { other.detail.textContent = t("等你批准：在新对话里处理"); keep.hidden = false; }
        }
        finished = true;
        if (closed) return;
        const [mine, theirs] = await Promise.all([sourceId, fork.id].map((id) => apiJson(`/sessions/${encodeURIComponent(id)}/events`)));
        const ownEvents = mine.events || [];
        const at = ownEvents.findIndex((event) => event.id === eventId);
        let start = at;
        while (start > 0 && ownEvents[start].type !== "mobile.task.created") start -= 1;
        original.detail.textContent = summaryLine(taskSummary(ownEvents, Math.max(start, 0)));
        // The question asked again: the task that follows the fork's rewind.
        const forkEvents = theirs.events || [];
        let rewound = forkEvents.length - 1;
        while (rewound > 0 && forkEvents[rewound].type !== "context.rewound") rewound -= 1;
        const asked = forkEvents.findIndex((event, index) => index > rewound && event.type === "mobile.task.created");
        const summary = taskSummary(forkEvents, asked >= 0 ? asked : Math.max(rewound, 0));
        other.detail.textContent = state === "succeeded" ? summaryLine(summary) : t("没有答完：{0}", taskStateLabels[state] || state);
        setMarkdown(other.body, summary.answer || "");
        keep.hidden = false;
      } catch (error) {
        if (!closed) status.textContent = t("对比失败：{0}", error.message);
      }
    };

    const render = () => {
      const query = search.value.trim().toLowerCase();
      const models = catalogModels().filter((item) => !query || item.id.toLowerCase().includes(query)
        || String(item.name || "").toLowerCase().includes(query));
      list.replaceChildren(...models.slice(0, 200).map((model) => {
        const option = document.createElement("button");
        option.type = "button";
        option.className = "action-sheet-item";
        option.innerHTML = icon("cpu");
        option.append(model.id);
        option.addEventListener("click", () => void run(model.id));
        return option;
      }));
      status.textContent = models.length ? "" : t("没有可选的模型。模型列表在模型设置里从服务商获取。");
    };
    search.addEventListener("input", render);
    render();
    search.hidden = catalogModels().length < 8;
    (search.hidden ? list.querySelector("button") || close : search).focus();
  }
