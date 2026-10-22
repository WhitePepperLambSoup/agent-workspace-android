  // TalkBack: the timeline is not a live region (it would read every streamed piece, and a whole
  // conversation when one opens); a finished reply or an approval to give is said here once.
  function announce(text) {
    const region = $("srAnnouncer");
    if (!region || !text) return;
    region.textContent = "";
    window.setTimeout(() => { region.textContent = String(text).slice(0, 600); }, 50);
  }

  function showApproval(approval) {
    if (approval && activeTask?.resolvedApprovals.has(approval.request_id)) approval = null;
    const changed = approval?.request_id !== pendingApproval?.request_id;
    pendingApproval = approval;
    elements.appShell.dataset.waiting = String(!!approval);
    elements.approvalShelf.hidden = !approval;
    elements.approvalShelf.classList.toggle("hidden", !approval);
    elements.btnApproveAction.disabled = !approval || isResolvingApproval;
    elements.btnRejectAction.disabled = !approval || isResolvingApproval;
    if (approval) {
      elements.approvalTitle.textContent = approval.kind === "egress" ? t("网络访问审批") : t("工具审批");
      elements.approvalDetail.textContent = approvalText(approval);
      elements.approvalDetail.dataset.kind = approval.kind || "";
      if (changed) elements.approvalScopeSelector.value = "once";
      // A reply sent as the user is approved one at a time (the engine ignores a wider scope too).
      const onceOnly = approval.details?.tool === "notification_reply";
      if (onceOnly) elements.approvalScopeSelector.value = "once";
      elements.approvalScopeSelector.disabled = onceOnly;
      if (changed && !elderShown()) announce(t("需要你批准：{0}", elements.approvalTitle.textContent));
    }
    elderApproval(approval);
  }

  // Approval requests arrive as engine records; the shelf says in words where data goes and what a
  // tool will do. The digest and ids stay out: they identify the request but tell the user nothing.
  const egressCategories = {
    system_instruction: t("系统指令"), tool_schema: t("工具说明"), user_message: t("你的消息"),
    assistant_history: t("之前的回复"), tool_result: t("工具结果"), sensitive_tool_result: t("敏感的工具结果"),
    sensitive_content: t("敏感内容"), image_attachment: t("图片"),
  };
  function approvalText(approval) {
    const details = approval.details || {};
    const plain = (value) => typeof value === "string" ? value : JSON.stringify(value, null, 2);
    if (approval.kind === "egress" && typeof details.endpoint === "string") {
      let host = details.endpoint;
      try { host = new URL(details.endpoint).host || host; } catch { /* Keep the endpoint as given. */ }
      const categories = Array.isArray(details.data_categories) ? details.data_categories.map(item => egressCategories[item] || item) : [];
      return [t("发送到 {0}", host), categories.length ? t("内容：{0}", categories.join(t("、"))) : ""].filter(Boolean).join("\n");
    }
    if (approval.kind === "tool" && typeof details.tool === "string") {
      const lines = [t("工具：{0}", toolTitles[details.tool] || details.tool)];
      // The task read instructions in outside content: this step may be driven by them.
      if (details.untrusted_content) lines.unshift(t("⚠ 这一步可能是被外部内容驱动的（{0}）。请确认这确实是你要做的。", String(details.untrusted_content).slice(0, 120)));
      const argumentsValue = details.arguments && typeof details.arguments === "object" ? details.arguments : {};
      // A reply sent from a notification goes out as the user: who it is to and what it says, in full.
      if (details.tool === "notification_reply") {
        if (argumentsValue.to) lines.push(t("发给：{0}", plain(argumentsValue.to)));
        lines.push(t("内容：{0}", plain(argumentsValue.text ?? "")));
        return lines.join("\n");
      }
      // Removing an app or taking back a power: which app, and the system page that opens.
      if (details.tool === "manage_app") {
        lines.push(t("应用：{0}", plain(argumentsValue.package_name ?? "")));
        lines.push(t("打开：{0}", appCheckActionName(argumentsValue.page)));
        return lines.join("\n");
      }
      for (const [name, value] of Object.entries(argumentsValue)) {
        if (name === "key" && String(details.tool).startsWith("notification_")) continue;
        lines.push(`${name}: ${plain(value)}`);
      }
      return lines.join("\n");
    }
    return JSON.stringify(details, null, 2);
  }

  async function resolveApproval(allowed) {
    const approval = pendingApproval;
    if (!approval || isResolvingApproval) return;
    isResolvingApproval = true;
    const scope = allowed ? elements.approvalScopeSelector.value : "once";
    showApproval(approval);
    try {
      await apiJson(`/mobile/approvals/${encodeURIComponent(approval.request_id)}/resolve`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allowed, scope }),
      });
      activeTask?.resolvedApprovals.add(approval.request_id);
      showApproval(null);
      haptic(32);
    } catch (error) {
      if (disposed) return;
      elements.approvalTitle.textContent = t("审批失败: {0}", error.message);
    } finally {
      isResolvingApproval = false;
      if (!disposed) {
        elements.btnApproveAction.disabled = !pendingApproval;
        elements.btnRejectAction.disabled = !pendingApproval;
      }
    }
  }

  function renderTaskEvent(task, event) {
    if (event.task_id !== task.id || event.sequence <= task.sequence) return;
    task.sequence = event.sequence;
    const envelope = event.payload || {};
    const payload = envelope.data && typeof envelope.data === "object" ? envelope.data : envelope;
    if (event.event_type === "assistant.delta") {
      if (task.messageFinal) { task.card = null; task.text = ""; task.reasoning = ""; task.messageFinal = false; }
      if (payload.kind === "reasoning") task.reasoning += payload.text || "";
      else task.text += payload.text || "";
      task.dirty = true;
    } else if (event.event_type === "task.completed") {
      if (typeof payload.text === "string") task.text = payload.text;
      task.artifacts = taskArtifacts(payload.artifacts);
      task.artifacts_truncated = payload.artifacts_truncated === true;
      task.artifacts_error = payload.artifacts_error || null;
      task.done = true;
      task.state = "succeeded";
      updateAssistantCard(task);
      task.dirty = false;
    } else if (["task.failed", "mobile.task.failed"].includes(event.event_type)) {
      task.error = localizeError(payload.error || payload.reason) || t("任务失败");
      task.done = true;
      task.state = "failed";
    } else if (event.event_type === "approval.requested") {
      showApproval(payload);
    } else if (event.event_type === "task.shortcut.available") {
      task.shortcutSteps = Number(payload.steps) || 0;
    } else if (event.event_type === "task.step_shots") {
      task.stepShots = Number(payload.count) || 0;
    } else if (event.event_type === "task.subagent.step") {
      showSubagentStep(payload);
    } else if (event.event_type === "task.untrusted_content") {
      notice(t("AI 读到的内容（{0}）里有像是写给 AI 的指令。为了安全，这个任务接下来的每一步都会先问你。", toolTitles[payload.tool] || payload.tool || ""));
    } else if (event.event_type === "runtime.message.created" && payload.role === "assistant") {
      const existing = envelope.source_event_id && eventCards.get(envelope.source_event_id);
      if (existing) {
        if (task.card && task.card !== existing) task.card.remove();
        task.card = existing;
      }
      if (typeof payload.content === "string") task.text = payload.content;
      if (typeof payload.reasoning === "string") task.reasoning = payload.reasoning;
      updateAssistantCard(task);
      task.dirty = false;
      task.messageFinal = true;
      // An intermediate step can carry only reasoning and tool calls. It is final, so it must not keep
      // the "running" placeholder: show just its reasoning, or drop it when there is nothing to show.
      if (!task.text.trim() && task.card) {
        if (task.reasoning) {
          task.card.classList.remove("pending", "streaming");
          task.card.classList.add("reasoning-only");
          const body = task.card.querySelector(".message-body");
          if (body) { body.textContent = ""; body.hidden = true; }
          const actions = task.card.querySelector(".card-action-bar");
          if (actions) actions.hidden = true;
        } else {
          task.card.remove();
          task.card = null;
        }
      }
      if (envelope.source_event_id) eventCards.set(envelope.source_event_id, task.card);
    } else if (event.event_type === "runtime.message.created" && payload.role === "user") {
      if (!task.prompt && typeof payload.content === "string") task.prompt = payload.content;
    } else if (event.event_type === "runtime.model.requested") {
      const used = Number(payload.context_bytes), limit = Number(payload.context_threshold_bytes);
      task.contextPercent = used > 0 && limit > 0 ? Math.min(100, Math.round(used / limit * 100)) : null;
    } else if (event.event_type === "runtime.tool.proposed") {
      rememberToolArguments(payload);
    } else if (event.event_type === "runtime.tool.started") {
      if (task.dirty) { updateAssistantCard(task); task.dirty = false; }
      renderTool(payload);
    } else if (typeof event.event_type === "string" && event.event_type.startsWith("runtime.") && toolOutcomeEvents[event.event_type.slice(8)]) {
      renderTool(payload, toolOutcomeEvents[event.event_type.slice(8)]);
      // The model switched this conversation's knowledge bases; the composer chip follows.
      if (payload.name === "knowledge_use") window.dispatchEvent(new CustomEvent("agent-knowledge-changed"));
    }
  }

  function showReconnect(error) {
    notice(t("连接中断: {0}", error.message));
    updateTaskStatus(t("任务状态待确认"), { reconnect: true });
    setConnection(false);
  }

  async function watchTask(task) {
    if (!task || task.watching || disposed) return;
    task.watching = true;
    let failures = 0;
    let completedPolls = 0;
    backgroundTasks.set(task.sessionId, task);
    while (!disposed && backgroundTasks.get(task.sessionId) === task && !task.done) {
      try {
        if (activeTask !== task) {
          const background = await apiJson(`/mobile/tasks/${encodeURIComponent(task.id)}`);
          if (backgroundTasks.get(task.sessionId) !== task) break;
          task.state = background.task?.state || task.state;
          if (terminalStates.has(task.state) || task.state === "interrupted") {
            task.done = true;
            backgroundTasks.delete(task.sessionId);
            syncControls();
            if (settingsPage === "tasks") void loadTaskCenter();
            break;
          }
          await new Promise(resolve => setTimeout(resolve, 1500));
          continue;
        }
        const updates = await apiJson(`/mobile/tasks/${encodeURIComponent(task.id)}/events?after=${task.sequence}`);
        if (activeTask !== task) continue;
        for (const event of updates.events || []) renderTaskEvent(task, event);
        if (task.dirty) { updateAssistantCard(task); task.dirty = false; }
        scrollToBottom();
        setConnection(true);
        if (task.done) break;
        const snapshot = await apiJson(`/mobile/tasks/${encodeURIComponent(task.id)}`);
        if (activeTask !== task) continue;
        const approval = (snapshot.approvals || []).find((item) => !task.resolvedApprovals.has(item.request_id));
        showApproval(approval || null);
        const state = snapshot.task?.state;
        const previousState = task.state;
        task.state = state || task.state;
        if (task.state !== previousState) syncControls(); // steering opens once the turn is running
        if (state === "succeeded") {
          task.artifacts = taskArtifacts(snapshot.task.artifacts);
          task.artifacts_truncated = snapshot.task.artifacts_truncated === true;
          task.artifacts_error = snapshot.task.artifacts_error || null;
        }
        // Long tasks show how full the context is; older history is compacted near 100%.
        const context = task.contextPercent >= 30 ? t(" · 上下文 {0}%", task.contextPercent) : "";
        updateTaskStatus(task.stopping ? t("正在停止任务...") : (state === "waiting_approval" ? t("等待审批") : (state === "queued" ? t("任务排队中") : t("任务执行中") + context)));
        if (["failed", "cancelled", "interrupted"].includes(state)) {
          task.error = state === "failed" ? (localizeError(snapshot.task.reason) || t("任务失败")) : null;
          task.interrupted = state === "interrupted" && snapshot.task.resume_available;
          task.done = true;
        } else if (state === "succeeded" && ++completedPolls >= 3) {
          // The terminal state can be visible before the task completion event.
          task.done = true;
          updateAssistantCard(task);
        }
        failures = 0;
      } catch (error) {
        if (disposed || backgroundTasks.get(task.sessionId) !== task) { task.watching = false; return; }
        if (activeTask !== task) { await new Promise(resolve => setTimeout(resolve, 2000)); continue; }
        setConnection(false);
        failures += 1;
        if (error.network || error.status === 401) {
          // The engine is gone or was restarted with a new token: let the app revive it and
          // reload this page. Without the app bridge, fall back to the manual button.
          if (failures >= 3 && !requestEngineReconnect()) { task.watching = false; showReconnect(error); return; }
          if (failures >= 3) updateTaskStatus(t("正在恢复与引擎的连接..."));
        } else if (failures >= 3 && error.status && error.status < 500) {
          // A definite answer such as "unknown task": polling again will not change it.
          task.watching = false; showReconnect(error); return;
        } else if (failures >= 3) {
          // The engine answers but is busy or erroring: keep polling, more slowly.
          updateTaskStatus(t("引擎暂时没有响应，正在重试..."));
        }
      }
      if (!task.done) await new Promise((resolve) => setTimeout(resolve, failures ? Math.min(500 * 2 ** Math.min(failures, 4), 8000) : 500));
    }
    task.watching = false;
    if (disposed || activeTask !== task) return;
    finishTask(task);
  }

  function finishTask(task) {
    if (activeTask !== task || !task.done || disposed) return;
    if (task.error) {
      showTaskError(t("任务失败: {0}", task.error));
      announce(t("任务失败: {0}", task.error));
      retryTask = task.prompt ? task : null;
      updateTaskStatus(t("任务失败"), { retry: !!task.prompt, idle: true });
      if (!elements.promptInput.value.trim() && task.inputText) {
        elements.promptInput.value = task.inputText;
        if (!attachments.length) attachments = task.attachments;
        renderAttachments();
        saveDraft();
        resizePrompt();
      }
      if (task.card && !task.text && !task.reasoning && !task.card.querySelector(".task-artifacts")) task.card.remove();
      // What it did on the phone before failing.
      offerStepShots(task);
    } else if (task.interrupted) {
      interruptedTask = { task_id: task.id, session_id: task.sessionId, prompt_preview: task.prompt, resume_available: true };
      updateTaskStatus(t("任务已中断"), { resume: true });
    } else {
      if (task.card && !task.text && !task.reasoning && !task.card.querySelector(".task-artifacts")) task.card.remove();
      updateTaskStatus(task.state === "cancelled" ? t("任务已停止") : "", { idle: true });
      notice("");
      // The elder screen has its own live region for the answer.
      const reply = task.card?.querySelector(".message-body")?.textContent.trim();
      if (task.state !== "cancelled" && reply && !elderShown()) announce(t("回复：{0}", reply));
      if (task.state !== "cancelled") { offerPlanExecution(task); offerShortcut(task); offerStepShots(task); continueVoiceConversation(task); }
    }
    elderTaskDone(task);
    activeTask = null;
    if (backgroundTasks.get(task.sessionId) === task) backgroundTasks.delete(task.sessionId);
    settleUnfinishedTools();
    elements.timelineList.querySelectorAll(".message-card.pending, .message-card.streaming").forEach((card) => card.classList.remove("pending", "streaming"));
    showApproval(null);
    syncControls();
  }

  function promptWithAttachments(prompt, imports) {
    if (!imports.length) return prompt;
    const paths = imports.map((item) => `- ${item.path}`).join("\n");
    return t("{0}\n\n工作区附件路径:\n{1}", prompt, paths);
  }

  function reconcilePendingRequest(sessionId) {
    const pending = pendingRequests[sessionId];
    if (!pending?.requestId) return;
    const admitted = historyEvents.find(event => event.type === "mobile.task.created"
      && event.data?.request_id === pending.requestId && event.data?.task_id);
    if (!admitted) return;
    submissions[admitted.data.task_id] = {
      sessionId, prompt: pending.payload.prompt, inputText: pending.inputText,
      attachments: pending.attachments, model: pending.payload.model,
      reasoning_effort: pending.payload.reasoning_effort, requestId: pending.requestId, createdAt: Date.now(),
    };
    writeStorage(submissionsKey, submissions);
    if (recoveredPendingDraft?.sessionId === sessionId && recoveredPendingDraft.requestId === pending.requestId) {
      if (elements.promptInput.value === recoveredPendingDraft.text
        && JSON.stringify(attachments.map(attachmentReceipt)) === recoveredPendingDraft.attachments) {
        elements.promptInput.value = "";
        attachments = [];
        saveDraft();
        renderAttachments();
        resizePrompt();
      }
      recoveredPendingDraft = null;
    }
    clearPendingRequest(sessionId, pending.requestId);
  }

  function clearPendingRequest(sessionId, requestId) {
    if (pendingRequests[sessionId]?.requestId !== requestId) return;
    delete pendingRequests[sessionId];
    writeStorage(pendingRequestsKey, pendingRequests);
  }

  function retainPendingRequest(sessionId, payload, inputText, imports, acknowledgedRequestId = null) {
    const signature = JSON.stringify(payload);
    const existing = pendingRequests[sessionId];
    const requestId = acknowledgedRequestId || (existing?.signature === signature && typeof existing.requestId === "string" && existing.requestId
      ? existing.requestId : window.crypto?.randomUUID?.() || `mobile-${Date.now()}-${Math.random().toString(16).slice(2)}`);
    const record = { requestId, signature, payload, inputText, attachments: imports };
    // This receipt must survive a lost response and reload before a task can execute.
    window.localStorage.setItem(pendingRequestsKey, JSON.stringify({ ...pendingRequests, [sessionId]: record }));
    pendingRequests[sessionId] = record;
    return requestId;
  }

  async function prepareAttachments(imports, sessionId) {
    const prepared = [];
    for (const item of imports) {
      let receipt = item;
      if (!/^[a-f0-9]{64}$/.test(item.sha256 || "") || typeof item.media_type !== "string" || !item.media_type) {
        receipt = await apiJson(`/mobile/attachments?session_id=${encodeURIComponent(sessionId)}&path=${encodeURIComponent(item.path)}`);
      }
      if (receipt.path !== item.path || !/^[a-f0-9]{64}$/.test(receipt.sha256 || "") || typeof receipt.media_type !== "string" || !receipt.media_type) {
        throw new Error(t("无法校验附件 {0}，请重新导入", item.name || item.path));
      }
      if (hasImageName(item) && !receipt.media_type.startsWith("image/")) {
        throw new Error(t("图片 {0} 的内容或格式无效，请转换为 PNG、JPEG、WebP 或 GIF 后重新导入", item.name || item.path));
      }
      if (receipt.media_type.startsWith("image/") && !["image/png", "image/jpeg", "image/webp", "image/gif"].includes(receipt.media_type)) {
        throw new Error(t("暂不支持 {0}，请转换成 PNG、JPEG、WebP 或 GIF", receipt.media_type));
      }
      // The engine reads at most 4 MiB per picture (mobile_images.MAX_MOBILE_ATTACHMENT_BYTES);
      // pictures added through the app are shrunk on the way in.
      if (receipt.media_type.startsWith("image/") && receipt.size > 4 * 1024 * 1024) {
        throw new Error(t("图片 {0} 超过 4 MB，请移除后重新添加，应用会自动压缩", item.name || item.path));
      }
      prepared.push(attachmentReceipt(receipt));
    }
    const images = prepared.filter(item => item.media_type.startsWith("image/"));
    if (images.length > 4) throw new Error(t("每次最多发送 4 张图片"));
    if (new Set(images.map(item => item.path)).size !== images.length) throw new Error(t("请移除重复图片后再发送"));
    return prepared;
  }

  function canSteer() {
    return !!activeTask?.id && !activeTask.done && !activeTask.stopping && activeTask.sessionId === currentSessionId
      && ["running", "waiting_approval"].includes(activeTask.state);
  }

  // Add a message to the running task. The engine stores it at once and the agent takes it into
  // account between its next model/tool steps, without starting a new task.
  async function steerActiveTask() {
    const task = activeTask;
    const requested = [...attachments];
    const plainText = elements.promptInput.value.trim();
    if (!canSteer() || isSteering || (!plainText && !requested.length)) return;
    isSteering = true;
    syncControls();
    let card = null;
    try {
      let imports = [];
      try { imports = await prepareAttachments(requested, task.sessionId); }
      catch (error) { notice(t("附件校验失败: {0}", error.message)); return; }
      const text = plainText || t("请查看附件内容。");
      const prompt = promptWithAttachments(text, imports);
      const inputId = `steer-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
      card = appendMessageCard("user", t("您"), text);
      card.dataset.messageText = prompt;
      card.classList.add("steer", "sending");
      elements.promptInput.value = "";
      attachments = [];
      renderAttachments();
      saveDraft();
      resizePrompt();
      scrollToBottom(true);
      await apiJson(`/mobile/tasks/${encodeURIComponent(task.id)}/steer`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, input_id: inputId }),
      });
      card.classList.remove("sending");
      const note = document.createElement("small");
      note.className = "steer-note";
      note.textContent = t("已加入当前任务");
      card.appendChild(note);
      haptic(24);
    } catch (error) {
      if (disposed) return;
      // Nothing was added: put the text back so it is not lost.
      card?.remove();
      if (!elements.promptInput.value.trim()) {
        elements.promptInput.value = plainText;
        if (!attachments.length) attachments = requested;
        renderAttachments();
        saveDraft();
        resizePrompt();
      }
      notice(error.code === "turn_not_active"
        ? (task.done ? t("当前任务已结束，消息已放回输入框") : t("任务尚未开始执行，请稍后再补充"))
        : error.code === "turn_input_full" ? t("已有较多补充等待处理，请稍后再发")
        : t("补充失败: {0}", error.message));
    } finally {
      isSteering = false;
      if (!disposed) syncControls();
    }
  }

  // ---- Edit and resend / regenerate ----
  // The next submission replaces a user message and everything after it (the server records the
  // rewind; history keeps the old turns). Files the replaced turns changed stay changed.
  let pendingRewind = null; // { sessionId, eventId, card, reason }

  function isUserMessageEvent(event) {
    const payload = event.data || event.payload || {};
    return event.type === "message.user" || (event.type === "message.created" && payload.role === "user");
  }

  // Cards created live (this visit) do not know their stored event; match them from the end of history.
  async function userEventIdFor(card) {
    if (card.dataset.eventId) return card.dataset.eventId;
    const data = await apiJson(`/sessions/${encodeURIComponent(currentSessionId)}/events`);
    const users = visibleHistory(Array.isArray(data.events) ? data.events : []).filter(isUserMessageEvent);
    const cards = [...elements.timelineList.querySelectorAll(".message-card.user")].filter((item) => !item.hidden);
    const event = users[users.length - (cards.length - cards.indexOf(card))];
    if (!event || cards.indexOf(card) < 0) throw new Error(t("找不到这条消息，请刷新后重试"));
    card.dataset.eventId = event.id;
    return event.id;
  }

  function cardsFrom(card) {
    const cards = [];
    for (let node = card; node; node = node.nextElementSibling) cards.push(node);
    return cards;
  }

  function cancelRewind() {
    pendingRewind = null;
    $("editBanner").hidden = true;
    syncControls();
  }

  async function editMessage(card) {
    if (activeTask || !historyReady || !currentSessionId) return;
    try {
      const eventId = await userEventIdFor(card);
      const text = card.dataset.displayText || card.dataset.messageText || "";
      if (elements.promptInput.value.trim() && elements.promptInput.value.trim() !== text.trim()
        && !window.confirm(t("用这条消息替换输入框里的草稿？"))) return;
      pendingRewind = { sessionId: currentSessionId, eventId, card, reason: "edit" };
      elements.promptInput.value = text;
      elements.promptInput.dispatchEvent(new Event("input", { bubbles: true }));
      $("editBanner").hidden = false;
      elements.promptInput.focus();
      syncControls();
    } catch (error) { notice(error.message); }
  }

  async function regenerateReply(card) {
    if (activeTask || !historyReady || !currentSessionId) return;
    let userCard = card.previousElementSibling;
    while (userCard && !(userCard.classList.contains("user") && !userCard.hidden)) userCard = userCard.previousElementSibling;
    if (!userCard) return;
    try {
      const eventId = await userEventIdFor(userCard);
      pendingRewind = { sessionId: currentSessionId, eventId, card: userCard, reason: "regenerate" };
      // The server re-asks the stored question; sending the same text keeps retries idempotent.
      await sendPrompt(userCard.dataset.messageText || userCard.dataset.displayText || t("请重新回答。"));
    } catch (error) { notice(error.message); }
    // A regenerate that did not go through must not turn the next ordinary message into one.
    if (pendingRewind?.reason === "regenerate") cancelRewind();
  }

  // ---- Fork: a new conversation from an earlier point; this one stays as it is ----
  // From a user's message: what came before it, with the message back in the input box to change.
  // From a reply: everything up to that reply. Files are shared (same workspace).
  async function forkFrom(card, keepReply) {
    if (!historyReady || !currentSessionId || isLoadingSession) return;
    let userCard = card;
    while (keepReply && userCard && !(userCard.classList.contains("user") && !userCard.hidden)) userCard = userCard.previousElementSibling;
    if (!userCard) return;
    const text = keepReply ? "" : (userCard.dataset.displayText || userCard.dataset.messageText || "");
    try {
      const eventId = await userEventIdFor(userCard);
      const result = await apiJson("/mobile/sessions/fork", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: currentSessionId, message_event_id: eventId, keep_reply: keepReply,
          title: t("{0}（分叉）", sessionTitle(currentSessionId)) }) });
      if (disposed || !await switchSession(result.session.id, result.session.title)) return;
      if (text && !elements.promptInput.value.trim()) {
        elements.promptInput.value = text;
        elements.promptInput.dispatchEvent(new Event("input", { bubbles: true }));
        elements.promptInput.focus();
      }
      notice(t("已分叉为新对话，原对话不变"), "info");
    } catch (error) { notice(t("分叉失败：{0}", error.message)); }
  }

  async function sendPrompt(customText = null, attachmentOverride = []) {
    flushQuickEffort();
    // Personal numbers typed for a cloud model: mask, send or cancel (65-privacy.js).
    if (customText === null && privacyNeeded() && !(await privacyCheck())) return;
    if (customText === null && canSteer()) { await steerActiveTask(); return; }
    if (customText === null && importsInFlight(currentSessionId)) { notice(t("附件还在导入，稍等片刻再发送"), "info"); return; }
    const requestedImports = customText === null ? [...attachments] : [...attachmentOverride];
    const defaultPrompt = requestedImports.every(item => item.media_type?.startsWith("image/") || /\.(png|jpe?g|webp|gif)$/i.test(item.name || "")) ? t("请描述图片内容。") : t("请查看附件内容。");
    const plainText = customText || elements.promptInput.value.trim() || (requestedImports.length ? defaultPrompt : "");
    if (!plainText || activeTask || isLoadingSession || isUploading || isPreparingSubmission || restartPending || localDeviceTesting || !historyReady || !currentSessionId || !settingsAvailable) return;
    const sessionId = currentSessionId;
    let imports;
    isPreparingSubmission = true;
    syncControls();
    try {
      imports = await prepareAttachments(requestedImports, sessionId);
      if (customText === null) { attachments = imports; saveDraft(); }
    } catch (error) {
      notice(t("附件校验失败: {0}", error.message));
      return;
    } finally {
      isPreparingSubmission = false;
      syncControls();
      window.setTimeout(refreshShareInbox, 0);
    }
    if (disposed || currentSessionId !== sessionId || activeTask || isLoadingSession || isUploading || restartPending || localDeviceTesting || !historyReady || !settingsAvailable) return;
    const imageRefs = imports.filter(item => item.media_type.startsWith("image/")).map(item => ({ path: item.path, sha256: item.sha256 }));
    const submittedPrompt = promptWithAttachments(plainText, imports.filter(item => !item.media_type.startsWith("image/")));
    const rewind = pendingRewind?.sessionId === sessionId && pendingRewind.card.isConnected ? pendingRewind : null;
    const payload = { session_id: sessionId, prompt: submittedPrompt, model: settings.model,
      reasoning_effort: settings.reasoning_effort, ...(imageRefs.length ? { image_refs: imageRefs } : {}),
      ...(rewind ? { rewind_from_event_id: rewind.eventId, rewind_reason: rewind.reason } : {}),
      ...(planMode ? { plan_mode: true } : {}) };
    // The replaced turns disappear while the new one is submitted, and come back if it fails.
    const replacedCards = rewind ? cardsFrom(rewind.card) : [];
    replacedCards.forEach((card) => { card.hidden = true; });
    let requestId;
    try { requestId = retainPendingRequest(sessionId, payload, plainText, imports); }
    catch { notice(t("无法保存任务提交记录，请检查存储空间后重试")); return; }
    haptic(36);
    elements.timelineList.querySelector(".empty-state")?.remove();
    const userCard = appendMessageCard("user", t("您"), plainText);
    userCard.dataset.messageText = submittedPrompt;
    // A retry sends the prompt that the failure put back in the composer, so that copy goes too.
    const composerHoldsPrompt = customText !== null && elements.promptInput.value.trim() === plainText.trim()
      && JSON.stringify(attachments.map(attachmentReceipt)) === JSON.stringify(imports.map(attachmentReceipt));
    if (customText === null || composerHoldsPrompt) {
      elements.promptInput.value = "";
      attachments = [];
      renderAttachments();
      saveDraft();
      resizePrompt();
    }
    activeTask = makeTask({ task_id: null, session_id: sessionId }, plainText);
    const task = activeTask;
    task.prompt = submittedPrompt;
    task.inputText = plainText;
    task.attachments = imports;
    task.requestId = requestId;
    task.planMode = payload.plan_mode === true;
    task.voiceTurn = voiceTurnPending;
    voiceTurnPending = false;
    retryTask = null;
    interruptedTask = null;
    notice("");
    updateTaskStatus(t("正在提交任务..."));
    syncControls();
    scrollToBottom(true);
    try {
      const result = await submitAfterEngineRecovery("/mobile/tasks", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, request_id: requestId }),
      });
      task.id = result.task?.task_id;
      if (!task.id) throw new Error(t("服务未返回有效任务 ID"));
      if (rewind) { replacedCards.forEach((card) => card.remove()); if (pendingRewind === rewind) cancelRewind(); }
      backgroundTasks.set(sessionId, task);
      submissions[task.id] = {
        sessionId, prompt: submittedPrompt, inputText: plainText, attachments: imports,
        model: task.model, reasoning_effort: task.effort, requestId, createdAt: Date.now(),
      };
      const retained = Object.keys(submissions).sort((first, second) => (submissions[second].createdAt || 0) - (submissions[first].createdAt || 0));
      retained.slice(20).forEach((id) => { delete submissions[id]; });
      writeStorage(submissionsKey, submissions);
      clearPendingRequest(sessionId, requestId);
      titleUntitledSession(sessionId, plainText);
      updateTaskStatus(t("任务执行中"));
      syncControls();
      updateAssistantCard(task);
      await watchTask(task);
      if (!disposed) haptic(40);
    } catch (error) {
      if (disposed) return;
      // A transport failure after an acknowledgement still needs the same task identity.
      if (task.id) { try { retainPendingRequest(sessionId, payload, plainText, imports, requestId); } catch {} }
      showTaskError(t("任务提交失败: {0}", error.message));
      retryTask = task;
      if (!elements.promptInput.value.trim() && customText === null) {
        elements.promptInput.value = plainText;
        if (!attachments.length) attachments = imports;
        if (pendingRequests[sessionId]?.requestId === requestId) {
          recoveredPendingDraft = { sessionId, requestId, text: plainText,
            attachments: JSON.stringify(imports.map(attachmentReceipt)) };
        }
        renderAttachments();
        saveDraft();
        resizePrompt();
      }
      task.card?.remove();
      userCard.remove();
      replacedCards.forEach((card) => { if (card.isConnected) card.hidden = false; });
      activeTask = null;
      if (backgroundTasks.get(sessionId) === task) backgroundTasks.delete(sessionId);
      updateTaskStatus(t("任务提交失败"), { retry: true });
      syncControls();
    }
    scrollToBottom();
  }

  // A conversation still named "新会话" takes its first instruction as its name, so the list stays readable.
  // Stored titles are compared raw: a conversation created in either language counts as untitled.
  const placeholderTitles = new Set(["", "新会话", "New chat", "New session", "New conversation"]); // i18n-ignore: stored data
