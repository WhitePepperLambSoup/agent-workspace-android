  function renderTaskArtifacts(container, payload, taskId = "") {
    const files = taskArtifacts(payload.artifacts);
    const existing = [...container.querySelectorAll(".task-artifacts")].find(panel => panel.dataset.artifactTask === taskId);
    if (!files.length && !payload.artifacts_error && !payload.artifacts_truncated) { existing?.remove(); return; }
    const panel = existing || document.createElement("section");
    panel.className = "task-artifacts";
    panel.dataset.artifactTask = taskId;
    panel.setAttribute("aria-label", t("生成文件"));
    panel.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = t("生成文件{0}", files.length ? ` · ${files.length}` : "");
    panel.appendChild(heading);
    const workspaceId = payload.workspaceId || workspaceOfSession(payload.session_id || currentSessionId) || currentWorkspaceId;
    // Long lists collapse after the first few files so a big task does not bury the conversation.
    const collapsedAfter = files.length > 4 ? 3 : files.length;
    const expanded = panel.dataset.expanded === "true";
    files.forEach((artifact, index) => {
      const file = { ...artifact, workspaceId };
      const row = document.createElement("div");
      row.className = "artifact-row";
      row.dataset.artifactPath = file.path;
      if (index >= collapsedAfter) row.classList.add("artifact-extra");
      const open = document.createElement("button");
      open.type = "button";
      open.className = "artifact-link";
      open.dataset.fileAction = "open";
      open.title = t("打开 {0}", file.path);
      open.innerHTML = icon("file-text");
      const label = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = typeof file.name === "string" && file.name ? file.name : file.path.split("/").pop();
      const metadata = document.createElement("small");
      metadata.textContent = `${file.path} · ${formatBytes(file.size)}${file.state === "modified" ? t(" · 已修改") : ""}`;
      label.append(name, metadata);
      open.appendChild(label);
      const status = document.createElement("p");
      status.className = "page-status artifact-status";
      status.setAttribute("role", "status");
      open.addEventListener("click", () => artifactAction(file, "open", open, status));
      row.appendChild(open);
      for (const [action, glyph, title] of [["share", "share-2", t("分享文件")], ["save", "download", t("另存文件")]]) {
        const button = actionButton(glyph, title, "data-file-action", action);
        button.addEventListener("click", () => artifactAction(file, action, button, status));
        row.appendChild(button);
      }
      row.appendChild(status);
      panel.appendChild(row);
    });
    panel.classList.toggle("collapsed", collapsedAfter < files.length && !expanded);
    if (collapsedAfter < files.length) {
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "text-action artifact-toggle";
      const label = () => panel.classList.contains("collapsed") ? t("显示全部 {0} 个文件", files.length) : t("收起");
      toggle.textContent = label();
      toggle.setAttribute("aria-expanded", String(!panel.classList.contains("collapsed")));
      toggle.addEventListener("click", () => {
        const collapse = !panel.classList.contains("collapsed");
        panel.classList.toggle("collapsed", collapse);
        panel.dataset.expanded = String(!collapse);
        toggle.textContent = label();
        toggle.setAttribute("aria-expanded", String(!collapse));
      });
      panel.appendChild(toggle);
    }
    if (payload.artifacts_error || payload.artifacts_truncated) {
      const warning = document.createElement("p");
      warning.className = "page-status error";
      warning.textContent = payload.artifacts_error || t("文件较多，部分文件可在工作区查看");
      panel.appendChild(warning);
    }
    if (!existing) container.insertBefore(panel, container.querySelector(".card-action-bar"));
  }

  // ```mermaid blocks become diagrams once a reply is complete. The renderer is a large separate file,
  // fetched the first time a diagram appears; results are cached so later re-renders cost nothing.
  const diagramCache = new Map();
  let diagramLoader = null;
  function loadDiagramRenderer() {
    if (window.MobileMermaid) return Promise.resolve(window.MobileMermaid);
    if (!diagramLoader) diagramLoader = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = `/static/mobile-mermaid.js?token=${encodeURIComponent(token)}`;
      script.onload = () => (window.MobileMermaid ? resolve(window.MobileMermaid) : reject(new Error("diagram renderer missing")));
      script.onerror = () => { diagramLoader = null; reject(new Error("diagram renderer unavailable")); };
      document.head.appendChild(script);
    });
    return diagramLoader;
  }

  function renderDiagram(wrapper, source) {
    const dark = preferences.theme === "dark" || (preferences.theme === "system" && darkSchemeQuery?.matches === true);
    const key = `${dark ? "dark" : "light"}\n${source}`;
    const show = (svg) => {
      if (!wrapper.isConnected || !svg) return;
      const diagram = document.createElement("div");
      diagram.className = "diagram";
      diagram.innerHTML = svg;
      wrapper.classList.add("has-diagram");
      wrapper.insertBefore(diagram, wrapper.querySelector("pre"));
    };
    if (diagramCache.has(key)) { show(diagramCache.get(key)); return; }
    loadDiagramRenderer()
      .then((renderer) => renderer.render(source, dark))
      .then((svg) => { diagramCache.set(key, svg); show(svg); })
      // A diagram the renderer rejects stays visible as its source code.
      .catch(() => diagramCache.set(key, ""));
  }

  function decorateMarkdown(body, final = true) {
    body.querySelectorAll("pre > code").forEach((code) => {
      const pre = code.parentElement;
      // ```card blocks become interactive cards once the reply is complete (63-cards.js).
      if (code.classList.contains("language-card")) {
        const card = final ? renderAgentCard(code.textContent) : null;
        if (card) { pre.replaceWith(card); return; }
        if (!final) { pre.classList.add("card-pending"); return; }
      }
      const wrapper = document.createElement("div");
      wrapper.className = "code-wrap";
      const toolbar = document.createElement("div");
      toolbar.className = "code-toolbar";
      const language = document.createElement("span");
      language.textContent = [...code.classList].find((name) => name.startsWith("language-"))?.slice(9) || t("代码");
      const copy = document.createElement("button");
      copy.type = "button";
      copy.className = "icon-button btn-code-copy";
      copy.title = t("复制代码");
      copy.setAttribute("aria-label", t("复制代码"));
      copy.innerHTML = icon("copy");
      copy.addEventListener("click", () => copyText(code.textContent));
      toolbar.append(language, copy);
      pre.replaceWith(wrapper);
      wrapper.append(toolbar, pre);
      if (final && code.classList.contains("language-mermaid")) renderDiagram(wrapper, code.textContent);
    });
    body.querySelectorAll("table").forEach((table) => {
      const scroll = document.createElement("div");
      scroll.className = "table-scroll";
      table.replaceWith(scroll);
      scroll.appendChild(table);
    });
    body.querySelectorAll("a[href]").forEach((link) => {
      try {
        const url = new URL(link.href, window.location.href);
        if (!["https:", "http:"].includes(url.protocol)) { link.removeAttribute("href"); return; }
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.addEventListener("click", (event) => {
          if (typeof bridge?.openExternal !== "function") return;
          event.preventDefault();
          bridge.openExternal(url.href);
        });
      } catch { link.removeAttribute("href"); }
    });
  }

  function setMarkdown(body, value, final = true) {
    body.innerHTML = window.MobileUi?.renderMarkdown(value) || "";
    decorateMarkdown(body, final);
  }

  function appendMessageCard(role, label, text, reasoning = "") {
    const card = document.createElement("article");
    card.className = `message-card ${role}`;
    card.dataset.messageText = text || "";
    card.dataset.displayText = text || "";
    const badge = document.createElement("div");
    badge.className = "role-badge";
    if (role === "assistant") badge.innerHTML = icon("bot");
    badge.append(label);
    card.appendChild(badge);
    if (reasoning) appendReasoning(card, reasoning);
    const body = document.createElement("div");
    body.className = "message-body";
    setMarkdown(body, text);
    card.appendChild(body);
    if (role === "assistant" || role === "user") {
      const actions = document.createElement("div");
      actions.className = "card-action-bar";
      const buttons = role === "assistant" ? [
        ["btn-copy", "copy", t("复制回复"), () => copyText(card.dataset.messageText)],
        ["btn-share", "share-2", t("分享回复"), () => shareText(t("Agent 回复"), card.dataset.messageText)],
        ["btn-regenerate", "rotate-ccw", t("重新生成"), () => regenerateReply(card)],
        ["btn-read", "play", t("朗读"), () => void readAloud(card)],
      ] : [
        ["btn-copy", "copy", t("复制"), () => copyText(card.dataset.displayText || card.dataset.messageText)],
        ["btn-edit", "pencil", t("编辑后重新发送"), () => editMessage(card)],
      ];
      for (const [name, iconName, title, action] of buttons) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `icon-button btn-card-action ${name}`;
        button.title = title;
        button.setAttribute("aria-label", title);
        button.innerHTML = icon(iconName);
        button.addEventListener("click", action);
        actions.appendChild(button);
      }
      card.appendChild(actions);
    }
    elements.timelineList.appendChild(card);
    return card;
  }

  function appendReasoning(card, text) {
    let details = card.querySelector(".reasoning-box");
    if (!details) {
      details = document.createElement("details");
      details.className = "reasoning-box";
      details.append(document.createElement("summary"), document.createElement("pre"));
      card.insertBefore(details, card.querySelector(".message-body"));
    }
    details.querySelector("summary").textContent = t("思考过程 · {0} 字", text.length);
    details.querySelector("pre").textContent = text;
  }

  function toolCardId(data) { return `tool-${data.tool_call_id || data.attempt_id || data.name || data.tool_name || "unknown"}`; }

  const toolStates = {
    running: t("执行中"), done: t("已完成"), failed: t("失败"), cancelled: t("已取消"), rejected: t("已拒绝"), unknown: t("结果未知"), stale: t("未完成"),
  };
  const toolOutcomeEvents = { "tool.settled": "done", "tool.failed": "failed", "tool.cancelled": "cancelled", "tool.rejected": "rejected", "tool.unknown": "unknown" };

  function setToolState(card, state) {
    card.dataset.state = state;
    card.querySelector(".tool-state").textContent = toolStates[state] || toolStates.done;
  }

  const toolTitles = {
    memory_write: t("更新记忆"), memory_search: t("查找记忆"), run_terminal: t("运行命令"),
    knowledge_search: t("查阅知识库"), knowledge_add: t("添加到知识库"), knowledge_use: t("选择知识库"),
    append_file: t("追加到文件"),
    set_alarm: t("设置闹钟"), set_timer: t("设置计时"), list_calendar_events: t("查看日程"), add_calendar_event: t("添加日程"),
    transcribe_audio: t("转写录音"),
    start_service: t("启动后台服务"), stop_service: t("停止后台服务"), list_services: t("查看后台服务"), service_logs: t("查看服务输出"),
    browser: t("浏览器"), browser_view: t("查看网页"),
    android_observe: t("查看屏幕"), android_screenshot: t("截图看屏幕"), android_verify: t("核对屏幕"),
    android_notify: t("发送通知"), android_clipboard: t("使用剪贴板"), android_battery: t("查看电量"),
    read_file: t("读取文件"), write_file: t("写入文件"), list_files: t("查看文件"), delete_path: t("删除文件"),
    web_search: t("联网搜索"), web_fetch: t("读取网页"), read_document: t("读取文档"), render_pdf: t("查看 PDF 页面"),
    create_pdf: t("生成 PDF"), create_docx: t("生成 Word 文档"), create_xlsx: t("生成表格"),
    use_skill: t("使用技能"), save_skill: t("保存技能"),
  };
  // What each tool call was asked to do (from its proposal), for a step label in plain words.
  const toolArguments = new Map();
  function rememberToolArguments(data) {
    if (data?.tool_call_id && data.arguments && typeof data.arguments === "object") toolArguments.set(data.tool_call_id, data.arguments);
    if (toolArguments.size > 400) toolArguments.delete(toolArguments.keys().next().value);
  }
  function toolLabel(name, args) {
    const short = (value, length = 24) => { const text = String(value ?? "").replace(/\s+/g, " ").trim(); return text.length > length ? `${text.slice(0, length)}…` : text; };
    const file = (value) => short(String(value || "").split("/").pop(), 32);
    if (name === "android_action" && args) {
      const steps = { tap_text: () => t("点「{0}」", short(args.text)), scroll_to_text: () => t("找到「{0}」", short(args.text)),
        launch_app: () => t("打开 {0}", short(args.app_name || args.package_name)), back: () => t("返回"), home: () => t("回到桌面"),
        recents: () => t("打开最近任务"), notifications: () => t("拉下通知栏"), scroll: () => t("滑动屏幕"), swipe: () => t("滑动屏幕"),
        type_text: () => t("输入文字"), enter: () => t("按确认键"), ref: () => t("点按"), tap: () => t("点按"), long_press: () => t("长按"),
        open_page: () => t("打开系统页面"), batch: () => t("连续操作 {0} 步", Array.isArray(args.steps) ? args.steps.length : 0),
        repeat: () => t("定时重复操作"), stop_repeat: () => t("停止重复") };
      return (steps[args.action] || (() => t("操作手机")))();
    }
    if (name === "android_action") return t("操作手机");
    if (args && name === "use_skill" && args.skill) return t("使用技能「{0}」", short(args.skill));
    if (args && name === "web_search" && args.query) return t("搜索「{0}」", short(args.query));
    if (args && ["read_file", "write_file", "append_file", "read_document", "create_pdf", "create_docx", "create_xlsx"].includes(name) && args.path) {
      return `${toolTitles[name]} · ${file(args.path)}`;
    }
    return toolTitles[name] || name || t("工具");
  }
  // Tools whose output the engine streams while they run (long installs and builds).
  const liveOutputTools = new Set(["run_terminal"]);

  function endToolOutput(card) {
    delete card.dataset.following;
    card.querySelector(".tool-live")?.remove();
    if (card.dataset.liveOpened) { delete card.dataset.liveOpened; card.open = false; }
  }

  function followToolOutput(card, attemptId) {
    if (card.dataset.following) return;
    card.dataset.following = "1";
    let misses = 0;
    const poll = async () => {
      if (disposed || !card.isConnected || card.dataset.state !== "running") { endToolOutput(card); return; }
      try {
        const value = await apiJson(`/mobile/live-output?attempt_id=${encodeURIComponent(attemptId)}`);
        if (card.dataset.state !== "running") { endToolOutput(card); return; }
        const text = String(value.text || "").trimEnd();
        if (text) {
          let live = card.querySelector(".tool-live");
          if (!live) {
            live = document.createElement("pre");
            live.className = "tool-live";
            card.appendChild(live);
            if (!card.open) { card.open = true; card.dataset.liveOpened = "1"; }
          }
          live.textContent = text.split("\n").slice(-12).join("\n");
          live.scrollTop = live.scrollHeight;
          scrollToBottom();
        }
        // A replayed start from history has no live output on the engine.
        misses = !value.active && !value.bytes ? misses + 1 : 0;
      } catch { misses += 1; }
      if (misses > 5) { delete card.dataset.following; return; }
      window.setTimeout(poll, 1000);
    };
    window.setTimeout(poll, 700);
  }

  function renderTool(data, outcome = null) {
    const id = toolCardId(data);
    const toolName = data.name || data.tool_name;
    let card = [...elements.timelineList.querySelectorAll(".message-card.tool")].find((item) => item.dataset.toolId === id);
    if (!card) {
      card = document.createElement("details");
      card.className = "message-card tool";
      card.dataset.toolId = id;
      const title = document.createElement("summary");
      const name = document.createElement("span");
      name.className = "tool-name";
      name.textContent = toolLabel(toolName, toolArguments.get(data.tool_call_id));
      card.dataset.tool = toolName || "";
      const state = document.createElement("span");
      state.className = "tool-state";
      title.append(name, state);
      card.appendChild(title);
      elements.timelineList.appendChild(card);
    }
    if (!outcome) {
      // A replayed start must not undo a result that already arrived.
      if (!card.dataset.state || card.dataset.state === "stale") setToolState(card, "running");
      if (card.dataset.state === "running" && liveOutputTools.has(toolName) && data.attempt_id) followToolOutput(card, data.attempt_id);
      return;
    }
    setToolState(card, outcome);
    endToolOutput(card);
    const detail = outcome === "done" ? data.result : (data.error ?? data.reason ?? data.result);
    if (detail === undefined || detail === null || detail === "") return;
    const view = toolDetailView(detail);
    let result = card.querySelector("pre");
    if (!result) { result = document.createElement("pre"); card.appendChild(result); }
    result.textContent = view.text;
    result.classList.toggle("tool-text", view.prose);
    let meta = card.querySelector(".tool-meta");
    if (view.meta) {
      if (!meta) { meta = document.createElement("small"); meta.className = "tool-meta"; card.appendChild(meta); }
      meta.textContent = view.meta;
    } else meta?.remove();
  }

  // Tools answer in JSON. A result that carries one main text (a transcript, a file, command output)
  // shows that text with its other short fields on one line; anything else stays formatted JSON.
  const toolTextFields = ["text", "transcript", "content", "output", "stdout", "message"];
  function toolDetailView(detail) {
    let value = detail;
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (!/^[[{]/.test(trimmed)) return { text: detail, prose: false };
      try { value = JSON.parse(trimmed); } catch { return { text: detail, prose: false }; }
    }
    if (!value || typeof value !== "object" || Array.isArray(value)) return { text: JSON.stringify(value, null, 2), prose: false };
    const key = toolTextFields.find(name => typeof value[name] === "string" && value[name].trim());
    if (!key) return { text: JSON.stringify(value, null, 2), prose: false };
    const meta = Object.entries(value)
      .filter(([name, item]) => name !== key && ["string", "number", "boolean"].includes(typeof item) && String(item).length <= 80)
      .map(([name, item]) => `${name}: ${item}`)
      .join(" · ");
    return { text: value[key], prose: key === "text" || key === "transcript" || key === "message", meta };
  }

  function settleUnfinishedTools() {
    elements.timelineList.querySelectorAll('.message-card.tool[data-state="running"]').forEach((card) => setToolState(card, "stale"));
  }

  function renderHistoryEvent(event) {
    const payload = event.data || event.payload || {};
    if (event.type === "mobile.task.running") {
      historyAssistantCard = null;
    } else if (event.type === "message.user" || (event.type === "message.created" && payload.role === "user")) {
      historyAssistantCard = null;
      const card = appendMessageCard("user", t("您"), payload.text || payload.content || "");
      if (event.id) { eventCards.set(event.id, card); card.dataset.eventId = event.id; }
    } else if (event.type === "message.assistant" || (event.type === "message.created" && payload.role === "assistant")) {
      // A step that only called tools has neither; its tool cards follow, as in the live view.
      if (!(payload.text || payload.content) && !payload.reasoning) return;
      const card = appendMessageCard("assistant", "Agent", payload.text || payload.content || "", payload.reasoning);
      historyAssistantCard = card;
      if (event.id) eventCards.set(event.id, card);
    } else if (event.type === "tool.proposed") rememberToolArguments(payload);
    else if (event.type === "tool.started") renderTool(payload);
    else if (toolOutcomeEvents[event.type]) renderTool(payload, toolOutcomeEvents[event.type]);
    else if (event.type === "task.completed" || (event.type === "mobile.event" && payload.event_type === "task.completed")) {
      const completion = event.type === "mobile.event" ? payload.payload || {} : payload;
      if (!taskArtifacts(completion.artifacts).length && !completion.artifacts_error && !completion.artifacts_truncated) return;
      const card = historyAssistantCard || appendMessageCard("assistant", "Agent", completion.text || t("执行完成"));
      renderTaskArtifacts(card, completion, payload.task_id || event.task_id || "");
      historyAssistantCard = null;
    }
  }

  function scrollToBottom(force = false) {
    if (disposed) return;
    if (!force && !stickToBottom) return;
    elements.timelineContainer.scrollTop = elements.timelineContainer.scrollHeight;
    stickToBottom = true;
    elements.btnJumpLatest.hidden = true;
  }

  function emptyState() {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    const glyph = document.createElement("span");
    glyph.className = "empty-state-icon";
    glyph.innerHTML = icon("sparkles");
    const title = document.createElement("strong");
    title.textContent = t("开始一个新任务");
    const hint = document.createElement("span");
    const workspace = workspaces.find(item => item.id === currentWorkspaceId);
    hint.textContent = workspace?.name ? t("描述你想完成的事情，Agent 会在「{0}」中执行。", workspace.name) : t("描述你想完成的事情，Agent 会在当前工作区中执行。");
    empty.append(glyph, title, hint);
    return empty;
  }

  function showTaskError(error) {
    const message = document.createElement("div");
    message.className = "task-error";
    message.setAttribute("role", "alert");
    message.textContent = error;
    elements.timelineList.appendChild(message);
  }

  // Edit-and-resend and regenerate keep the replaced turns in the store (context.rewound marks
  // where the conversation restarted); history shows the conversation as it now stands.
  function visibleHistory(events) {
    const shown = [];
    for (const event of events) {
      if (event.type === "context.rewound") {
        const from = shown.findIndex((item) => item.id === (event.data || event.payload || {}).from_event_id);
        if (from >= 0) shown.length = from;
        continue;
      }
      shown.push(event);
    }
    return shown;
  }

  async function loadTimeline(sessionId) {
    if (!sessionId) return;
    historyReady = false;
    elements.timelineList.replaceChildren();
    eventCards.clear();
    historyAssistantCard = null;
    syncControls();
    try {
      const data = await apiJson(`/sessions/${encodeURIComponent(sessionId)}/events`);
      if (sessionId !== currentSessionId) return;
      unavailableSessions.delete(sessionId);
      historyEvents = visibleHistory(Array.isArray(data.events) ? data.events : []);
      if (pendingRewind) cancelRewind(); // its cards were just replaced
      reconcilePendingRequest(sessionId);
      for (const event of historyEvents) renderHistoryEvent(event);
      // History has no live stream; a started tool without an outcome did not finish.
      settleUnfinishedTools();
      // Not "no events": a conversation whose only events show nothing (an attachment that was
      // staged and removed, say) would otherwise open as a blank page.
      if (!elements.timelineList.childElementCount) elements.timelineList.appendChild(emptyState());
      historyReady = true;
      setConnection(true);
      scrollToBottom(true);
    } catch (error) {
      if (disposed) return;
      if (sessionId !== currentSessionId) return;
      if (error.status === 404) unavailableSessions.add(sessionId);
      historyEvents = [];
      setConnection(false);
      const state = document.createElement("div");
      state.className = "history-error";
      const message = document.createElement("p");
      message.textContent = t("加载会话失败: {0}", error.message);
      const retry = document.createElement("button");
      retry.id = "btnRetryHistory";
      retry.className = "button-secondary";
      retry.type = "button";
      retry.textContent = t("重试");
      retry.addEventListener("click", async () => {
        isLoadingSession = true;
        try { await loadTimeline(sessionId); if (historyReady) await recoverSessionTask(sessionId); }
        finally { isLoadingSession = false; syncControls(); }
      });
      state.append(message, retry);
      elements.timelineList.replaceChildren(state);
    } finally { syncControls(); }
  }

  async function recoverSessionTask(sessionId) {
    if (activeTask) return;
    const adoptionGeneration = taskAdoptionGeneration;
    try {
      const data = await apiJson(`/mobile/tasks?session_id=${encodeURIComponent(sessionId)}`);
      if (sessionId !== currentSessionId || activeTask || adoptionGeneration !== taskAdoptionGeneration) return;
      const tasks = Array.isArray(data.tasks) ? data.tasks : [];
      const ordered = [...tasks].sort((first, second) => String(second.created_at || second.updated_at || "").localeCompare(String(first.created_at || first.updated_at || "")));
      const live = ordered.find((task) => runningStates.has(task.state));
      interruptedTask = null;
      retryTask = null;
      updateTaskStatus("");
      if (live) {
        activeTask = makeTask(live);
        backgroundTasks.set(sessionId, activeTask);
        updateTaskStatus(t("正在恢复任务..."));
        syncControls();
        void watchTask(activeTask);
        return;
      }
      const latest = ordered[0];
      const historySequence = historyEvents.reduce((sequence, event) => Math.max(sequence, Number(event.sequence) || 0), 0);
      if (latest?.state === "succeeded" && latest.last_sequence > historySequence) {
        activeTask = makeTask(latest);
        backgroundTasks.set(sessionId, activeTask);
        updateTaskStatus(t("正在恢复任务..."));
        syncControls();
        void watchTask(activeTask);
      } else if (latest?.state === "interrupted" && latest.resume_available) {
        interruptedTask = latest;
        updateTaskStatus(t("任务已中断"), { resume: true });
      } else if (latest?.state === "failed") {
        const canRetry = !!submissions[latest.task_id]?.prompt;
        if (canRetry) retryTask = makeTask(latest);
        // Say why the last task failed instead of a bare "failed".
        const reason = typeof latest.reason === "string" ? latest.reason.trim().slice(0, 300) : "";
        updateTaskStatus(reason ? t("任务失败：{0}", reason) : t("任务失败"), { retry: canRetry, idle: true });
      }
    } catch (error) {
      if (disposed || adoptionGeneration !== taskAdoptionGeneration) return;
      if (sessionId === currentSessionId) {
        historyReady = false;
        notice(t("恢复任务状态失败: {0}", error.message));
        setConnection(false);
      }
    }
  }

  async function refreshCurrentSessionTask() {
    if (activeTask || isLoadingSession || !historyReady || !currentSessionId) return;
    isLoadingSession = true;
    syncControls();
    try { await recoverSessionTask(currentSessionId); }
    finally { isLoadingSession = false; syncControls(); }
  }

  async function loadSessions(preferredId = selectedSessionId) {
    isLoadingSession = true;
    historyReady = false;
    syncControls();
    try {
      const data = await apiJson("/sessions");
      sessions = Array.isArray(data.sessions) ? data.sessions : [];
      const preferred = sessions.find(item => item.id === preferredId);
      if (preferred?.workspace_id) currentWorkspaceId = preferred.workspace_id;
      const inWorkspace = sessions.filter(session => !currentWorkspaceId || workspaceOfSession(session.id) === currentWorkspaceId);
      // An explicitly requested conversation opens even when archived; otherwise prefer unarchived ones.
      let visible = inWorkspace.filter(session => session.archived !== true);
      if (!visible.length && !inWorkspace.some(session => session.id === preferredId)) {
        const created = await apiJson("/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: t("新会话"), ...(currentWorkspaceId ? { workspace_id: currentWorkspaceId } : {}) }) });
        sessions.push(created);
        visible = [created];
      }
      currentSessionId = inWorkspace.some((session) => session.id === preferredId) ? preferredId : visible[0].id;
      currentWorkspaceId = workspaceOfSession(currentSessionId) || currentWorkspaceId;
      renderWorkspaceNavigation();
      renderSessionNavigation();
      selectedSessionId = currentSessionId;
      writeStorage(sessionKey, currentSessionId);
      restoreDraft(currentSessionId);
      await loadTimeline(currentSessionId);
      if (historyReady) await recoverSessionTask(currentSessionId);
      return historyReady;
    } catch (error) {
      if (disposed) return false;
      historyReady = false;
      setConnection(false);
      notice(t("加载会话失败: {0}", error.message));
      return false;
    } finally {
      isLoadingSession = false;
      syncControls();
      refreshShareInbox();
    }
  }

  async function switchSession(sessionId, title = "") {
    if ((activeTask && !activeTask.id) || isLoadingSession || isUploading || isPreparingSubmission || restartPending || !sessionId) return false;
    if (!canLeaveFileEditor()) return false;
    const previousSessionId = currentSessionId;
    const previousWorkspaceId = currentWorkspaceId;
    const blank = blankSessionId();
    saveDraft();
    if (!sessions.some((session) => session.id === sessionId)) {
      isLoadingSession = true;
      syncControls();
      try {
        const listing = await apiJson("/sessions");
        const target = Array.isArray(listing.sessions) && listing.sessions.find(item => item.id === sessionId);
        if (target) {
          if (target.workspace_id && !workspaces.some(item => item.id === target.workspace_id)) await loadWorkspaces();
          sessions.push(target);
        } else if (workspaces.length) {
          unavailableSessions.add(sessionId);
          notice(t("目标会话不存在或已删除"));
          return false;
        } else sessions.push({ id: sessionId, title });
      } catch (error) {
        notice(t("加载会话失败: {0}", error.message));
        return false;
      } finally { isLoadingSession = false; syncControls(); }
    }
    detachSessionTask();
    currentSessionId = sessionId;
    const targetWorkspace = workspaceOfSession(sessionId);
    if (targetWorkspace && targetWorkspace !== currentWorkspaceId) {
      currentWorkspaceId = targetWorkspace;
      writeStorage(workspaceKey, targetWorkspace);
      renderWorkspaceNavigation();
    }
    renderSessionNavigation();
    selectedSessionId = sessionId;
    writeStorage(sessionKey, sessionId);
    resetFilePreview();
    fileEditor = null;
    workspacePath = "";
    workspaceParent = null;
    filesGeneration += 1;
    attachments = [];
    interruptedTask = null;
    retryTask = null;
    renderAttachments();
    updateTaskStatus("");
    notice("");
    isLoadingSession = true;
    restoreDraft(sessionId);
    syncControls();
    try {
      await loadTimeline(sessionId);
      if (historyReady) await recoverSessionTask(sessionId);
      if (unavailableSessions.has(sessionId) && previousSessionId && previousSessionId !== sessionId) {
        sessions = sessions.filter((session) => session.id !== sessionId);
        currentSessionId = previousSessionId;
        currentWorkspaceId = previousWorkspaceId;
        selectedSessionId = previousSessionId;
        writeStorage(workspaceKey, previousWorkspaceId);
        writeStorage(sessionKey, previousSessionId);
        renderWorkspaceNavigation();
        renderSessionNavigation();
        restoreDraft(previousSessionId);
        await loadTimeline(previousSessionId);
        if (historyReady) await recoverSessionTask(previousSessionId);
        notice(t("目标会话不存在或已删除"));
      }
    } finally {
      isLoadingSession = false;
      syncControls();
      refreshShareInbox();
    }
    const switched = historyReady && currentSessionId === sessionId;
    if (switched) discardBlankSession(blank);
    return switched;
  }

  function makeTask(snapshot, prompt = "") {
    const saved = submissions[snapshot.task_id];
    return {
      id: snapshot.task_id, sessionId: snapshot.session_id || currentSessionId,
      workspaceId: workspaceOfSession(snapshot.session_id || currentSessionId) || currentWorkspaceId,
      prompt: saved?.prompt || prompt, inputText: saved?.inputText || prompt,
      attachments: saved?.attachments || [], model: saved?.model || snapshot.model || settings.model,
      effort: saved?.reasoning_effort || snapshot.reasoning_effort || settings.reasoning_effort,
      sequence: 0, state: snapshot.state || "queued",
      text: "", reasoning: "", card: null, done: false, error: null,
      artifacts: taskArtifacts(snapshot.artifacts), artifacts_truncated: snapshot.artifacts_truncated === true,
      artifacts_error: snapshot.artifacts_error || null,
      resolvedApprovals: new Set(), stopping: false, watching: false, messageFinal: false,
    };
  }

  function adoptTask(snapshot) {
    if (disposed || !snapshot || typeof snapshot.task_id !== "string" || !snapshot.task_id.trim()
      || !currentSessionId || !historyReady || (snapshot.session_id && snapshot.session_id !== currentSessionId)) return false;
    if (activeTask) {
      if (activeTask.id !== snapshot.task_id) return false;
      void watchTask(activeTask);
      return true;
    }
    activeTask = makeTask(snapshot);
    backgroundTasks.set(activeTask.sessionId, activeTask);
    taskAdoptionGeneration += 1;
    interruptedTask = null;
    retryTask = null;
    showApproval(null);
    elements.timelineList.querySelector(".empty-state")?.remove();
    updateTaskStatus(snapshot.state === "waiting_approval" ? t("等待审批") : t("任务执行中"));
    updateAssistantCard(activeTask);
    syncControls();
    scrollToBottom();
    void watchTask(activeTask);
    return true;
  }

  function updateAssistantCard(task) {
    if (task.sessionId !== currentSessionId || activeTask !== task) return;
    if (!task.card) task.card = appendMessageCard("assistant", "Agent", t("正在执行..."));
    const body = task.card.querySelector(".message-body");
    const text = task.text || (task.done ? t("执行完成") : t("正在执行..."));
    // Diagrams are drawn once the reply is complete, not on every streamed chunk.
    setMarkdown(body, text, task.done || !!task.messageFinal);
    task.card.dataset.messageText = task.text;
    task.card.classList.toggle("pending", !task.done && !task.text);
    task.card.classList.toggle("streaming", !task.done && !!task.text && !task.messageFinal);
    if (task.reasoning) appendReasoning(task.card, task.reasoning);
    if (task.state === "succeeded") renderTaskArtifacts(task.card, task, task.id);
  }

