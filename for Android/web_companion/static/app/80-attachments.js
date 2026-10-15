  function titleUntitledSession(sessionId, text) {
    const session = sessions.find(item => item.id === sessionId);
    const title = String(text || "").replace(/\s+/g, " ").trim().slice(0, 40);
    if (!session || !title || !placeholderTitles.has(String(session.title || "").trim())) return;
    const previous = session.title;
    session.title = title;
    renderSessionNavigation();
    apiJson(`/sessions/${encodeURIComponent(sessionId)}/rename`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) })
      .then((data) => { if (typeof data.title === "string" && data.title) { session.title = data.title; renderSessionNavigation(); } })
      .catch(() => { if (disposed || session.title !== title) return; session.title = previous; renderSessionNavigation(); });
  }

  async function stopTask() {
    const task = activeTask;
    if (!task?.id || task.stopping) return;
    task.stopping = true;
    syncControls();
    try {
      const result = await apiJson(`/mobile/tasks/${encodeURIComponent(task.id)}/cancel`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      if (terminalStates.has(result.task?.state)) {
        task.state = result.task.state;
        task.done = true;
        finishTask(task);
      } else {
        updateTaskStatus(t("正在停止任务..."));
        if (!task.watching) void watchTask(task);
      }
    } catch (error) {
      if (disposed) return;
      task.stopping = false;
      notice(t("停止失败: {0}", error.message));
      syncControls();
    }
  }

  async function resumeTask() {
    const snapshot = interruptedTask;
    if (!snapshot || activeTask) return;
    elements.btnResumeTask.disabled = true;
    try {
      const result = await apiJson(`/mobile/tasks/${encodeURIComponent(snapshot.task_id)}/resume`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      interruptedTask = null;
      activeTask = makeTask(result.task || snapshot);
      backgroundTasks.set(activeTask.sessionId, activeTask);
      updateTaskStatus(t("正在恢复任务..."));
      syncControls();
      await watchTask(activeTask);
    } catch (error) {
      if (disposed) return;
      notice(t("恢复失败: {0}", error.message));
      elements.btnResumeTask.disabled = false;
    }
  }

  // Pictures in the message box show a small thumbnail, as other chat apps do. Each one is shrunk
  // to 96 px once, so a few large photos do not hold full-size bitmaps in the page.
  async function loadThumbnail(item, workspaceId) {
    if (thumbnails.has(item.path) || typeof window.createImageBitmap !== "function") return;
    thumbnails.set(item.path, null);
    try {
      const blob = await downloadArtifact({ path: item.path, sha256: item.sha256, workspaceId });
      const bitmap = await window.createImageBitmap(blob, { resizeHeight: 96, resizeQuality: "medium" });
      const canvas = document.createElement("canvas");
      canvas.width = bitmap.width; canvas.height = bitmap.height;
      canvas.getContext("2d").drawImage(bitmap, 0, 0);
      bitmap.close?.();
      const small = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.8));
      if (!small || disposed) throw new Error("thumbnail");
      thumbnails.set(item.path, URL.createObjectURL(small));
      for (const [path, url] of thumbnails) {
        if (thumbnails.size <= 24) break;
        if (url) URL.revokeObjectURL(url);
        thumbnails.delete(path);
      }
      renderAttachments();
    } catch { thumbnails.set(item.path, false); }
  }

  function renderAttachments() {
    elements.attachmentList.replaceChildren();
    for (const item of attachments) {
      const chip = document.createElement("div");
      chip.className = "attachment-chip";
      const label = document.createElement("span");
      const thumbnail = item.media_type?.startsWith("image/") ? thumbnails.get(item.path) : false;
      if (thumbnail) {
        const img = document.createElement("img");
        img.className = "attachment-thumb"; img.src = thumbnail; img.alt = "";
        chip.classList.add("has-thumb"); chip.append(img);
      } else if (thumbnail === undefined) void loadThumbnail(item, workspaceOfSession(currentSessionId));
      label.textContent = `${item.media_type?.startsWith("image/") && !thumbnail ? t("图片 · ") : ""}${item.name}`;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "icon-button attachment-remove";
      remove.title = t("移除 {0}", item.name);
      remove.setAttribute("aria-label", t("移除 {0}", item.name));
      remove.innerHTML = icon("x");
      remove.addEventListener("click", async () => {
        if (isUploading || isPreparingSubmission) return;
        const submitted = Object.values(submissions).some((record) => record.sessionId === currentSessionId
          && record.attachments?.some((file) => file.path === item.path));
        if (!submitted) {
          isUploading = true;
          remove.disabled = true;
          syncControls();
          try {
            const path = `/mobile/attachments?session_id=${encodeURIComponent(currentSessionId)}&path=${encodeURIComponent(item.path)}`;
            await apiJson(path, { method: "DELETE" });
          } catch (error) {
            if (disposed) return;
            if (error.status !== 409) {
              notice(t("移除附件失败: {0}", error.message));
              remove.disabled = false;
              return;
            }
          } finally { isUploading = false; syncControls(); }
        }
        if (disposed) return;
        attachments = attachments.filter((entry) => entry !== item);
        renderAttachments();
        saveDraft();
      });
      chip.append(label, remove);
      elements.attachmentList.appendChild(chip);
    }
    // Files still on their way in from the picker, the camera or the import page.
    for (const item of incomingFor(currentSessionId)) {
      const chip = document.createElement("div");
      chip.className = "attachment-chip incoming";
      chip.dataset.state = item.state === "error" ? "error" : "busy";
      const label = document.createElement("span");
      const state = item.state === "error" ? (item.uncertain ? t("等待确认") : t("导入失败"))
        : item.state === "staging" ? t("接收中") : t("导入中");
      label.textContent = `${state} · ${item.name || t("附件")}`;
      if (item.error) label.title = localizeError(item.error);
      chip.append(label);
      if (item.state === "error") {
        const retry = document.createElement("button");
        retry.type = "button"; retry.className = "icon-button attachment-remove";
        retry.title = t("重试 {0}", item.name || t("附件")); retry.setAttribute("aria-label", retry.title);
        retry.innerHTML = icon("refresh-cw");
        retry.addEventListener("click", () => retryIncoming(item));
        chip.append(retry);
      }
      if (["pending", "error"].includes(item.state) && typeof bridge?.discardShareInbox === "function") {
        const remove = document.createElement("button");
        remove.type = "button"; remove.className = "icon-button attachment-remove";
        remove.title = t("移除 {0}", item.name || t("附件")); remove.setAttribute("aria-label", remove.title);
        remove.innerHTML = icon("x");
        remove.addEventListener("click", () => discardIncoming(item));
        chip.append(remove);
      }
      elements.attachmentList.appendChild(chip);
    }
  }

  function requestId(prefix) {
    return window.crypto?.randomUUID?.() || `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function persistImportedFiles(sessionId, files, itemIds = [], batchTexts = []) {
    if (disposed || (sessionId === currentSessionId && (isLoadingSession || isPreparingSubmission))) return false;
    const previous = drafts[sessionId];
    const base = typeof previous === "string" ? { text: previous, attachments: [] } : (previous || { text: "", attachments: [] });
    const next = { ...base, text: sessionId === currentSessionId ? elements.promptInput.value : base.text || "",
      attachments: [...(sessionId === currentSessionId ? attachments : Array.isArray(base.attachments) ? base.attachments : [])] };
    const knownItems = new Set(base.shared_item_ids || []), knownBatches = new Set(base.shared_batch_ids || []);
    for (const file of files) {
      if (typeof file?.name !== "string" || typeof file?.path !== "string") throw new Error(t("服务未返回附件路径"));
      if (!next.attachments.some(existing => existing.path === file.path)) next.attachments.push(attachmentReceipt(file));
    }
    for (const [id, text] of batchTexts) {
      if (!knownBatches.has(id) && typeof text === "string" && text.trim()) next.text += `${next.text ? "\n\n" : ""}${text}`;
      knownBatches.add(id);
    }
    for (const id of itemIds) knownItems.add(id);
    if (knownItems.size) next.shared_item_ids = [...knownItems];
    if (knownBatches.size) next.shared_batch_ids = [...knownBatches];
    const updated = { ...drafts, [sessionId]: next };
    if (!writeStorage(draftsKey, updated)) {
      notice(t("附件已导入，草稿保存失败；文件仍保留在收件箱，请释放存储后重试"));
      return false;
    }
    drafts[sessionId] = next;
    if (sessionId === currentSessionId) {
      attachments = next.attachments; elements.promptInput.value = next.text;
      recoveredPendingDraft = null; renderAttachments(); resizePrompt(); syncControls();
    }
    return true;
  }

  function rawUpload(entry) {
    const query = new URLSearchParams({ session_id: entry.sessionId, filename: entry.file.name,
      media_type: entry.file.type || "application/octet-stream", request_id: entry.id });
    if (entry.workspaceId) query.set("workspace_id", entry.workspaceId);
    const route = `/mobile/attachments/upload?${query}`;
    if (typeof window.XMLHttpRequest !== "function") return apiJson(route, {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: entry.file,
    });
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest(); entry.xhr = xhr;
      xhr.open("POST", route); xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.setRequestHeader("Content-Type", "application/octet-stream");
      xhr.upload.onprogress = event => { entry.loaded = event.loaded; renderImportUploads(); };
      xhr.onerror = () => reject(new Error(t("连接中断；重试会复用同一个导入编号")));
      xhr.onabort = () => reject(new Error(t("上传已取消，已完成的文件仍保留")));
      xhr.onload = () => {
        try {
          const data = JSON.parse(xhr.responseText);
          if (xhr.status < 200 || xhr.status >= 300) throw new Error(localizeError(data.error) || `HTTP ${xhr.status}`);
          resolve(data);
        } catch (error) { reject(error); }
      };
      xhr.send(entry.file);
    }).finally(() => { entry.xhr = null; });
  }

  async function runUploads(entries) {
    if (isUploading || disposed) return;
    isUploading = true; syncControls();
    const queue = [...entries];
    for (let index = 0; index < queue.length; index++) {
      const entry = queue[index];
      if (disposed) break;
      entry.state = "uploading"; entry.error = ""; renderImportUploads();
      try {
        const file = entry.file;
        if (!entry.attachment) {
          if ((file.type.startsWith("image/") && !["image/png", "image/jpeg", "image/webp", "image/gif"].includes(file.type))
            || (hasImageName(file) && !/\.(png|jpe?g|jfif|webp|gif)$/i.test(file.name)))
            throw new Error(t("{0} 请先转换成 PNG、JPEG、WebP 或 GIF", file.name));
          entry.attachment = await rawUpload(entry);
          if ((file.type.startsWith("image/") || hasImageName(file))
            && !["image/png", "image/jpeg", "image/webp", "image/gif"].includes(entry.attachment.media_type)) {
            entry.attachment = null;
            throw new Error(t("图片 {0} 的内容或格式无效，请转换后重新导入", file.name));
          }
        }
        if (disposed) break;
        if (!persistImportedFiles(entry.sessionId, [entry.attachment])) throw new Error(t("草稿保存失败，导入文件已保留"));
        entry.loaded = file.size; entry.state = "ready";
      } catch (error) {
        entry.state = "error"; entry.error = error.message;
        if (!disposed) notice(t("附件 {0} 导入失败: {1}", entry.file.name, error.message));
      }
      renderImportUploads();
      for (const added of browserUploads) {
        if (added.state === "pending" && !queue.includes(added)) queue.push(added);
      }
    }
    isUploading = false;
    if (!disposed) { elements.filePickerInput.value = ""; syncControls(); renderImportUploads(); }
  }

  function uploadFiles(files) {
    if (!files.length || !currentSessionId || isPreparingSubmission || isLoadingSession || restartPending) return;
    const entries = files.map(file => ({ id: requestId("upload"), sessionId: currentSessionId,
      workspaceId: currentWorkspaceId, file, loaded: 0, state: "pending" }));
    browserUploads.push(...entries); renderImportUploads();
    void runUploads(browserUploads.filter(entry => entry.state === "pending"));
  }

  function showImportPage() { if (!layerOpen(elements.settingsOverlay)) openMenu(); setSettingsPage("attachments"); }

  // From the message box the files go to the open conversation; from the import page, to the
  // conversation chosen there.
  function chooseImportFiles(fromPage = false) {
    haptic();
    if (typeof bridge?.pickShareInboxFiles === "function") {
      pickIntoConversation(() => bridge.pickShareInboxFiles(), t("无法选择文件"),
        fromPage ? elements.shareTargetSession.value : currentSessionId, fromPage);
    } else elements.filePickerInput.click();
  }

  function pickIntoConversation(launch, failure, sessionId, fromPage) {
    try {
      const result = JSON.parse(launch());
      if (!result.ok) throw new Error(localizeError(result.error) || failure);
      if (typeof result.batch_id !== "string" || !sessionId) { showImportPage(); return; } // an app without batch ids
      autoImports = [...autoImports.filter(entry => entry.deadline > Date.now() || entry.seen),
        { batch: result.batch_id, sessionId, deadline: Date.now() + 30 * 60000, confirmed: [] }];
      writeStorage(autoImportsKey, autoImports);
      if (fromPage) pageStatus(elements.shareInboxStatus, t("选好的文件会自动添加到「{0}」", sessionTitle(sessionId)));
    } catch (error) {
      if (fromPage) pageStatus(elements.shareInboxStatus, error.message, true);
      else notice(error.message);
    }
  }

  function sessionTitle(sessionId) {
    return sessions.find(session => session.id === sessionId)?.title || t("会话");
  }

  // Inbox files on their way into a conversation: picked for it, or confirmed for it on the import page.
  function incomingFor(sessionId) {
    if (!sessionId) return [];
    const batches = new Set(autoImports.filter(entry => entry.sessionId === sessionId).map(entry => entry.batch));
    return shareInbox.items.filter(item => item.kind === "file" && !acknowledgedShares.has(item.id)
      && (item.session_id ? item.session_id === sessionId : batches.has(item.batch_id)));
  }

  function importsInFlight(sessionId) {
    return incomingFor(sessionId).some(item => item.state !== "error");
  }

  // Confirms each picked file for its conversation once it has been received.
  function importPickedFiles() {
    if (!autoImports.length || typeof bridge?.confirmShareInbox !== "function" || !sessions.length) return;
    let changed = false;
    autoImports = autoImports.filter((entry) => {
      const items = shareInbox.items.filter(item => item.batch_id === entry.batch && !acknowledgedShares.has(item.id));
      if (!items.length) {
        // Nothing (more) to receive: the pick was cancelled or every file was added.
        const done = entry.seen || Date.now() > entry.deadline;
        if (done) changed = true;
        return !done;
      }
      if (!entry.seen) { entry.seen = true; changed = true; }
      // The conversation is gone: its files wait in the inbox for another one.
      if (!sessions.some(session => session.id === entry.sessionId)) { changed = true; return false; }
      const ids = items.filter(item => item.state === "pending" && !entry.confirmed.includes(item.id)).map(item => item.id);
      if (!ids.length) return true;
      entry.confirmed.push(...ids);
      changed = true;
      try {
        const result = JSON.parse(bridge.confirmShareInbox(JSON.stringify({ request_id: requestId("share"),
          session_id: entry.sessionId, workspace_id: workspaceOfSession(entry.sessionId), item_ids: ids })));
        if (!result.ok) throw new Error(localizeError(result.error) || t("无法导入附件"));
      } catch (error) { notice(t("附件导入失败: {0}", error.message)); }
      return true;
    });
    if (changed) writeStorage(autoImportsKey, autoImports);
  }

  function retryIncoming(item) {
    const sessionId = item.session_id || autoImports.find(entry => entry.batch === item.batch_id)?.sessionId;
    if (!sessionId || typeof bridge?.confirmShareInbox !== "function") return;
    reportedImportErrors.delete(item.id);
    try {
      const result = JSON.parse(bridge.confirmShareInbox(JSON.stringify({ request_id: requestId("share"),
        session_id: sessionId, workspace_id: item.workspace_id || workspaceOfSession(sessionId), item_ids: [item.id] })));
      if (!result.ok) throw new Error(localizeError(result.error) || t("无法导入附件"));
      refreshShareInbox();
    } catch (error) { notice(error.message); }
  }

  function discardIncoming(item) {
    try {
      const result = JSON.parse(bridge.discardShareInbox(JSON.stringify({ item_ids: [item.id] })));
      if (!result.ok) throw new Error(localizeError(result.error) || t("无法丢弃附件"));
      refreshShareInbox();
    } catch (error) { notice(error.message); }
  }

  // A failed file is reported once in the conversation it was meant for.
  function reportImportErrors() {
    for (const item of incomingFor(currentSessionId)) {
      if (item.state !== "error" || reportedImportErrors.has(item.id)) continue;
      reportedImportErrors.add(item.id);
      notice(t("附件 {0} 导入失败: {1}", item.name || t("附件"), localizeError(item.error) || t("请重试")));
    }
  }

  function syncImportControls() {
    const ids = shareInbox.items.filter(item => shareSelection.get(item.id) !== false
      && ["pending", "error", "uncertain"].includes(item.state)).map(item => item.id);
    elements.btnImportShares.disabled = !ids.length || !elements.shareTargetSession.value || isLoadingSession || isPreparingSubmission;
    elements.btnDiscardShares.disabled = !ids.length;
    elements.btnPickImportFiles.disabled = isPreparingSubmission || isLoadingSession || restartPending;
    elements.shareTargetSession.disabled = isPreparingSubmission || isLoadingSession;
  }

  function renderImportUploads() {
    if (disposed) return;
    elements.browserUploadList.replaceChildren();
    for (const entry of browserUploads) {
      const row = document.createElement("div"); row.className = "import-row";
      const body = document.createElement("div"); body.className = "import-row-body";
      const title = document.createElement("strong"); title.textContent = entry.file.name;
      const status = document.createElement("small"); status.textContent = entry.error || (entry.state === "ready" ? t("已添加") : entry.state === "uploading" ? t("上传中") : t("等待上传"));
      const progress = document.createElement("progress"); progress.max = Math.max(1, entry.file.size); progress.value = entry.loaded;
      body.append(title, status, progress); row.append(body);
      if (entry.state === "error") {
        const retry = actionButton("refresh-cw", t("重试 {0}", entry.file.name), "data-upload-retry", entry.id);
        retry.disabled = isUploading; retry.addEventListener("click", () => void runUploads([entry])); row.append(retry);
      } else if (entry.state === "uploading" && entry.xhr) {
        const cancel = actionButton("x", t("取消 {0}", entry.file.name), "data-upload-cancel", entry.id);
        cancel.addEventListener("click", () => entry.xhr?.abort()); row.append(cancel);
      }
      elements.browserUploadList.append(row);
    }
    updateImportNotice();
  }

  function updateImportNotice() {
    const count = shareInbox.items.filter(item => !acknowledgedShares.has(item.id)).length
      + browserUploads.filter(item => item.state !== "ready").length;
    elements.btnImportNotice.hidden = count === 0;
    elements.importNoticeText.textContent = t("{0} 个附件待处理", count);
    elements.menuImportSummary.textContent = count ? t("{0} 个待处理", count) : "";
  }

  function applyReadyShares() {
    for (const item of shareInbox.items) {
      if (item.state !== "ready" || acknowledgedShares.has(item.id)) continue;
      const target = item.target || (item.session_id ? {
        session_id: item.session_id,
        workspace_id: item.workspace_id,
      } : null);
      if (!target?.session_id) continue;
      const session = sessions.find(value => value.id === target.session_id);
      if (!session || (session.workspace_id && session.workspace_id !== target.workspace_id)) continue;
      const savedIds = drafts[session.id]?.shared_item_ids || [];
      const batch = shareInbox.batches.find(value => value.id === item.batch_id);
      const text = typeof item.text === "string" ? item.text : batch?.text;
      const textKey = text ? (batch?.id || item.id) : null;
      if (!savedIds.includes(item.id) && !persistImportedFiles(session.id,
        item.attachment ? [item.attachment] : [], [item.id], textKey ? [[textKey, text]] : [])) continue;
      if (typeof bridge?.ackShareInbox === "function") {
        try {
          const result = JSON.parse(bridge.ackShareInbox(JSON.stringify({ item_ids: [item.id] })));
          if (result.ok) acknowledgedShares.add(item.id);
        } catch { /* The durable draft records this id before acknowledging the native copy. */ }
      }
    }
  }

  function renderShareInbox() {
    const native = typeof bridge?.getShareInbox === "function";
    elements.shareTargetControls.hidden = !native;
    elements.shareImportActions.hidden = !native;
    elements.btnRefreshImports.hidden = !native;
    const selected = shareTargetChoice || currentSessionId;
    elements.shareTargetSession.replaceChildren();
    for (const session of sessions) {
      const option = document.createElement("option"); option.value = session.id;
      const workspace = workspaces.find(value => value.id === session.workspace_id);
      option.textContent = `${workspace?.name || t("工作区")} · ${session.title || t("会话")}${session.id === currentSessionId ? t("（当前对话）") : ""}`;
      elements.shareTargetSession.append(option);
    }
    elements.shareTargetSession.value = sessions.some(session => session.id === selected) ? selected : currentSessionId;
    if (importWatch) {
      // The page's own request is reported once its files have been added or have failed.
      const open = shareInbox.items.filter(item => importWatch.ids.includes(item.id) && !acknowledgedShares.has(item.id));
      if (!open.some(item => item.state !== "error")) {
        const failed = open.length, added = importWatch.ids.length - failed;
        pageStatus(elements.shareInboxStatus, failed
          ? t("{0} 个已添加到「{1}」，{2} 个失败，可以选中后重试", added, sessionTitle(importWatch.sessionId), failed)
          : t("已添加到「{0}」，回到这个对话就能看到", sessionTitle(importWatch.sessionId)), failed > 0);
        importWatch = null;
      }
    }
    elements.shareInboxList.replaceChildren();
    const stateNames = { staging: t("接收中"), pending: t("等待导入"), uploading: t("导入中"), importing: t("导入中"), ready: t("已导入"), error: t("导入失败"), uncertain: t("等待确认") };
    for (const item of shareInbox.items) {
      if (acknowledgedShares.has(item.id)) continue;
      const row = document.createElement("label"); row.className = "import-row";
      const checkbox = document.createElement("input"); checkbox.type = "checkbox";
      checkbox.checked = shareSelection.get(item.id) !== false; checkbox.disabled = !["pending", "error", "uncertain"].includes(item.state);
      checkbox.setAttribute("aria-label", t("选择 {0}", item.name || t("附件")));
      checkbox.addEventListener("change", () => { shareSelection.set(item.id, checkbox.checked); syncImportControls(); });
      const body = document.createElement("div"); body.className = "import-row-body";
      const title = document.createElement("strong"); title.textContent = item.name || t("附件");
      const status = document.createElement("small"); status.textContent = `${formatBytes(item.size || 0)} · ${item.error || stateNames[item.state] || t("等待导入")}`;
      body.append(title, status); row.append(checkbox, body); elements.shareInboxList.append(row);
    }
    syncImportControls(); updateImportNotice();
  }

  function refreshShareInbox() {
    if (disposed || refreshingImports) return;
    refreshingImports = true;
    try {
      if (typeof bridge?.getShareInbox === "function") {
        const snapshot = JSON.parse(bridge.getShareInbox());
        if (!snapshot.ok || !Array.isArray(snapshot.items)) throw new Error(localizeError(snapshot.error) || t("无法读取收件箱"));
        shareInbox = { items: snapshot.items, batches: Array.isArray(snapshot.batches) ? snapshot.batches : [] };
        applyReadyShares();
        importPickedFiles();
        attachQuickShare();
        sendQuickNote();
        reportImportErrors();
        if (snapshot.capture_error) pageStatus(elements.shareInboxStatus, localizeError(String(snapshot.capture_error)), true);
      }
      renderShareInbox(); renderImportUploads(); renderAttachments(); syncControls();
    } catch (error) { pageStatus(elements.shareInboxStatus, error.message, true); }
    finally { refreshingImports = false; }
  }

  function confirmShares() {
    const session = sessions.find(item => item.id === elements.shareTargetSession.value);
    const ids = shareInbox.items.filter(item => shareSelection.get(item.id) !== false
      && ["pending", "error", "uncertain"].includes(item.state)).map(item => item.id);
    if (!session || !ids.length || elements.btnImportShares.disabled) return;
    try {
      const result = JSON.parse(bridge.confirmShareInbox(JSON.stringify({ request_id: requestId("share"),
        session_id: session.id, workspace_id: workspaceOfSession(session.id), item_ids: ids })));
      if (!result.ok) throw new Error(localizeError(result.error) || t("无法导入附件"));
      importWatch = { ids, sessionId: session.id };
      pageStatus(elements.shareInboxStatus, t("正在添加到「{0}」...", sessionTitle(session.id))); refreshShareInbox();
    } catch (error) { pageStatus(elements.shareInboxStatus, error.message, true); }
  }

  function discardShares() {
    const ids = shareInbox.items.filter(item => shareSelection.get(item.id) !== false
      && ["pending", "error", "uncertain"].includes(item.state)).map(item => item.id);
    if (!ids.length || !window.confirm(t("丢弃所选的 {0} 个附件？", ids.length))) return;
    try {
      const result = JSON.parse(bridge.discardShareInbox(JSON.stringify({ item_ids: ids })));
      if (!result.ok) throw new Error(localizeError(result.error) || t("无法丢弃附件"));
      refreshShareInbox();
    } catch (error) { pageStatus(elements.shareInboxStatus, error.message, true); }
  }

  async function exportConversation() {
    const session = sessions.find((item) => item.id === currentSessionId);
    const title = session?.title || "Agent Workspace";
    try {
      const result = await apiJson(`/sessions/${encodeURIComponent(currentSessionId)}/events`);
      const lines = [`# ${title}`];
      for (const event of result.events || []) {
        const data = event.data || {};
        if (event.type === "message.user" || (event.type === "message.created" && data.role === "user")) lines.push(t("\n## 您\n\n{0}", data.text || data.content || ""));
        if (event.type === "message.assistant" || (event.type === "message.created" && data.role === "assistant")) lines.push(`\n## Agent\n\n${data.text || data.content || ""}`);
      }
      shareText(title, lines.join("\n"));
      closeMenu();
    } catch (error) {
      if (!disposed) notice(t("导出失败: {0}", error.message));
    }
  }

  elements.promptInput.addEventListener("input", () => { recoveredPendingDraft = null; saveDraft(); resizePrompt(); syncControls(); });
  // Soft keyboards have no Shift+Enter, so Enter inserts a line there; Ctrl+Enter always sends.
  const touchKeyboard = typeof window.matchMedia === "function" && window.matchMedia("(pointer: coarse)")?.matches === true;
  elements.promptInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    if (touchKeyboard && !event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    sendPrompt();
  });
  elements.btnSend.addEventListener("click", () => {
    // The arrow lifts off and comes back from below, as the message leaves.
    const arrow = elements.btnSend.querySelector("svg");
    if (arrow && !elements.btnSend.disabled && motionApi()?.level() === "full") motionApi().play(arrow, [
      { transform: "none", opacity: 1 }, { transform: "translateY(-16px)", opacity: 0, offset: 0.42 },
      { transform: "translateY(12px)", opacity: 0, offset: 0.43 }, { transform: "none", opacity: 1 },
    ], { duration: 520, easing: "cubic-bezier(.3, .7, .3, 1)" });
    void sendPrompt();
  });
  elements.btnStop.addEventListener("click", stopTask);
  elements.noticeText.addEventListener("click", () => notice(""));
  $("btnSaveModelRoles").addEventListener("click", saveModelRoles);
  elements.btnJumpLatest.addEventListener("click", () => scrollToBottom(true));
  elements.btnResumeTask.addEventListener("click", resumeTask);
  elements.btnRetryTask.addEventListener("click", () => { if (retryTask?.inputText) sendPrompt(retryTask.inputText, retryTask.attachments); });
  elements.btnReconnect.addEventListener("click", async () => {
    if (!activeTask) return;
    engineReconnectRequestedAt = 0;
    if (requestEngineReconnect()) { updateTaskStatus(t("正在恢复与引擎的连接...")); return; }
    try { await apiJson("/mobile/reconnect", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); } catch { /* Event polling is the authoritative recovery path. */ }
    notice("");
    updateTaskStatus(t("正在重新连接..."));
    await watchTask(activeTask);
  });
  // With a camera available the paperclip offers "take a photo" or "choose files"; otherwise it picks files.
  function closeAttachMenu() {
    const menu = $("attachMenu");
    if (!layerOpen(menu)) return false;
    elements.btnAttach.setAttribute("aria-expanded", "false");
    hideLayer(menu, (motion) => [motion.play(menu, [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(6px) scale(.94)" }],
      { duration: 140, easing: "cubic-bezier(.4, 0, 1, 1)", fill: "forwards" })]);
    return true;
  }
  elements.btnAttach.addEventListener("click", () => {
    if (typeof bridge?.captureShareInboxPhoto !== "function") { chooseImportFiles(); return; }
    if (closeAttachMenu()) return;
    haptic();
    const menu = $("attachMenu");
    showLayer(menu, (motion) => {
      motion.play(menu, [{ opacity: 0, transform: "translateY(10px) scale(.88)" }, { opacity: 1, transform: "none" }], { spring: "bouncy" });
      motion.stagger(menu.querySelectorAll(".menu-row:not([hidden])"), { transform: "translateY(8px)" }, { delay: 30, step: 30 });
    });
    elements.btnAttach.setAttribute("aria-expanded", "true");
    $("btnAttachCamera").focus();
  });
  $("btnAttachFiles").addEventListener("click", () => { closeAttachMenu(); chooseImportFiles(); });
  $("btnAttachPhotos").hidden = typeof bridge?.pickShareInboxPhotos !== "function";
  $("btnAttachPhotos").addEventListener("click", () => {
    closeAttachMenu();
    haptic();
    pickIntoConversation(() => bridge.pickShareInboxPhotos(), t("无法选择照片"), currentSessionId, false);
  });
  // Records until the user is done; the recording comes back as a new conversation with minutes.
  $("btnAttachVoiceNote").hidden = typeof bridge?.startVoiceNote !== "function";
  $("btnAttachVoiceNote").addEventListener("click", () => { closeAttachMenu(); haptic(); bridge.startVoiceNote(); });
  $("btnCancelEdit").addEventListener("click", () => {
    cancelRewind();
    elements.promptInput.value = "";
    elements.promptInput.dispatchEvent(new Event("input", { bubbles: true }));
  });
  $("btnAttachCamera").addEventListener("click", () => {
    closeAttachMenu();
    haptic();
    pickIntoConversation(() => bridge.captureShareInboxPhoto(), t("无法打开相机"), currentSessionId, false);
  });
  document.addEventListener("click", (event) => {
    if (!$("attachMenu").hidden && !event.target.closest("#attachMenu, #btnAttach")) closeAttachMenu();
  });
  elements.filePickerInput.addEventListener("change", (event) => uploadFiles(Array.from(event.target.files || [])));
  elements.btnAttachmentsPage.addEventListener("click", () => setSettingsPage("attachments"));
  elements.btnImportNotice.addEventListener("click", showImportPage);
  elements.btnPickImportFiles.addEventListener("click", () => chooseImportFiles(true));
  elements.btnRefreshImports.addEventListener("click", refreshShareInbox);
  elements.btnImportShares.addEventListener("click", confirmShares);
  elements.btnDiscardShares.addEventListener("click", discardShares);
  elements.shareTargetSession.addEventListener("change", () => { shareTargetChoice = elements.shareTargetSession.value; syncImportControls(); });
  elements.quickChipsBar.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip || chip.disabled) return;
    if (chip.dataset.fill !== "true") { sendPrompt(chip.dataset.prompt); return; }
    // Open-ended shortcuts start the prompt and leave the rest to the user.
    const input = elements.promptInput;
    input.value = input.value.trim() ? `${chip.dataset.prompt}${input.value}` : chip.dataset.prompt;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  });
  elements.btnApproveAction.addEventListener("click", () => resolveApproval(true));
  elements.btnRejectAction.addEventListener("click", () => resolveApproval(false));
  elements.btnNewSession.addEventListener("click", createSession);
  elements.btnDrawerNewSession.addEventListener("click", async () => { if (await createSession()) closeDrawer(); });
  // A conversation opened and left without anything in it would pile up in the drawer. The engine
  // only removes one that has no stored events at all; the page also keeps any draft or attachment.
  function blankSessionId() {
    if (!currentSessionId || !historyReady || activeTask || pendingRequests[currentSessionId]) return null;
    // Only a conversation the app opened under its default name and that was never renamed.
    const current = sessions.find(item => item.id === currentSessionId);
    if (!current || current.archived === true || current.title !== t("新会话")) return null;
    if (elements.promptInput.value.trim() || attachments.length || timelineMessages().length || incomingFor(currentSessionId).length) return null;
    if ([...backgroundTasks.values()].some(task => task.sessionId === currentSessionId && !task.done)) return null;
    return currentSessionId;
  }

  function discardBlankSession(sessionId) {
    if (!sessionId || sessionId === currentSessionId || disposed) return;
    apiJson(`/sessions/${encodeURIComponent(sessionId)}/discard`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
      .then((result) => {
        if (!result?.discarded || disposed) return;
        sessions = sessions.filter(item => item.id !== sessionId);
        if (drafts[sessionId]) { delete drafts[sessionId]; writeStorage(draftsKey, drafts); }
        renderSessionNavigation();
      })
      .catch(() => {});
  }

  async function createSession() {
    if (elements.btnNewSession.disabled || !canLeaveFileEditor() || fileSaving) return false;
    // The open conversation is still blank: use it instead of adding another empty one.
    if (blankSessionId()) {
      haptic();
      elements.promptInput.focus();
      return true;
    }
    // One tap creates the conversation; it can be renamed later from the menu.
    const title = t("新会话");
    haptic();
    saveDraft();
    detachSessionTask();
    isLoadingSession = true;
    syncControls();
    try {
      const created = await apiJson("/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, ...(currentWorkspaceId ? { workspace_id: currentWorkspaceId } : {}) }) });
      attachments = [];
      renderAttachments();
      return await loadSessions(created.id);
    } catch (error) { if (!disposed) notice(t("创建会话失败: {0}", error.message)); return false; }
    finally { isLoadingSession = false; syncControls(); }
  }
  elements.sessionSelector.addEventListener("change", async () => {
    if (!await switchSession(elements.sessionSelector.value)) elements.sessionSelector.value = currentSessionId;
  });
  elements.workspaceSelector.addEventListener("change", async () => {
    if (!await switchWorkspace(elements.workspaceSelector.value)) elements.workspaceSelector.value = currentWorkspaceId;
  });
  elements.btnWorkspacesPage.addEventListener("click", () => setSettingsPage("workspaces"));
  elements.btnWorkspacesRefresh.addEventListener("click", loadWorkspaces);
  elements.btnBrowseWorkspaceSystem.addEventListener("click", () => {
    if (elements.btnBrowseWorkspaceSystem.disabled) return;
    const workspaceId = currentWorkspaceId;
    try {
      const result = JSON.parse(bridge.openWorkspaceBrowser(workspaceId));
      if (!result.ok) throw new Error(localizeError(result.error) || t("无法打开系统文件浏览器"));
      pageStatus(elements.workspacesStatus, t("正在打开当前工作区的系统文件浏览入口"));
    } catch (error) { pageStatus(elements.workspacesStatus, error.message, true); }
  });
  elements.btnSuggestWorkspaceFolder.addEventListener("click", () => {
    if (elements.btnSuggestWorkspaceFolder.disabled) return;
    try {
      const result = JSON.parse(bridge.recommendedWorkspaceFolder(elements.workspaceNameInput.value.trim()));
      if (!result.ok || typeof result.path !== "string" || !result.path) throw new Error(localizeError(result.error) || t("无法读取公共文档目录"));
      elements.workspaceFolderInput.value = result.path;
      elements.workspaceCreateDirectory.checked = true;
      syncWorkspaceControls();
      pageStatus(elements.workspacesStatus, t("已填入公共目录建议；点击创建工作区后保存"));
    } catch (error) { pageStatus(elements.workspacesStatus, error.message, true); }
  });
  elements.workspaceCreateForm.addEventListener("submit", createWorkspace);
  for (const input of [elements.workspaceNameInput, elements.workspaceFolderInput]) input.addEventListener("input", syncWorkspaceControls);
  elements.btnPickWorkspaceFolder.addEventListener("click", () => {
    if (elements.btnPickWorkspaceFolder.disabled) return;
    try {
      const result = JSON.parse(bridge.pickWorkspaceFolder());
      if (!result.ok) throw new Error(localizeError(result.error) || t("无法选择文件夹"));
      workspacePicking = true;
      syncWorkspaceControls();
    } catch (error) { pageStatus(elements.workspacesStatus, error.message, true); }
  });
  elements.btnWorkspaceStorageSettings.addEventListener("click", () => {
    try { bridge?.requestWorkspaceStorageAccess?.(); }
    catch (error) { pageStatus(elements.workspaceStorageStatus, error.message, true); }
  });
  window.addEventListener("agent-workspace-folder-selected", event => {
    workspacePicking = false;
    const result = event.detail;
    if (result?.path) elements.workspaceFolderInput.value = result.path;
    pageStatus(elements.workspacesStatus, localizeError(result?.error) || "", !!result?.error);
    refreshWorkspaceAccess();
    syncWorkspaceControls();
  });
  window.addEventListener("focus", refreshWorkspaceAccess);
  window.addEventListener("agent-workspace-storage-changed", refreshWorkspaceAccess);
  elements.btnSettings.addEventListener("click", openMenu);
  elements.modelBar.addEventListener("click", openModelSheet);
  elements.settingsBackdrop.addEventListener("click", closeMenu);
  elements.settingsCloseButton.addEventListener("click", closeMenu);
  elements.btnSessions.addEventListener("click", openDrawer);
  elements.btnSessionTitle.addEventListener("click", openDrawer);
  elements.btnDrawerClose.addEventListener("click", closeDrawer);
  elements.sessionDrawerBackdrop.addEventListener("click", closeDrawer);
  elements.btnDrawerSearch.addEventListener("click", () => { closeDrawer(); openMenu(); setSettingsPage("search"); });
  elements.btnDrawerWorkspaces.addEventListener("click", () => { closeDrawer(); openMenu(); setSettingsPage("workspaces"); });
  elements.btnModeChip.addEventListener("click", () => { if (!layerOpen(elements.settingsOverlay)) openMenu(); setSettingsPage("permission"); });
  elements.settingsBackButton.addEventListener("click", () => setSettingsPage(subPageParents[settingsPage] || "home"));
  $("btnQuickTasksPage").addEventListener("click", () => setSettingsPage("quickTasks"));
  $("btnRefreshModels").addEventListener("click", () => {
    void refreshProviderModels($("modelListStatus")).then((done) => { if (done) renderSettings(); });
  });
  $("btnSaveProfile").addEventListener("click", () => {
    const name = window.prompt(t("给这个配置起个名字"), settings.model);
    if (name === null || !name.trim()) return;
    try { bridgeResult("saveProviderProfile", name.trim()); renderProfiles(); pageStatus($("profileStatus"), t("已保存")); }
    catch (error) { pageStatus($("profileStatus"), error.message, true); }
  });
  $("btnAddQuickTask").addEventListener("click", () => openQuickTaskForm(quickTasks.length));
  $("btnCancelQuickTask").addEventListener("click", closeQuickTaskForm);
  $("quickTaskForm").addEventListener("submit", submitQuickTaskForm);
  $("quickTaskIcons").addEventListener("click", (event) => {
    const option = event.target.closest("[data-icon-option]");
    if (!option) return;
    $("quickTaskIcons").querySelectorAll("[data-icon-option]").forEach((item) => item.setAttribute("aria-checked", String(item === option)));
  });
  $("btnResetQuickTasks").addEventListener("click", () => {
    if (!window.confirm(t("把快捷任务恢复成默认的 4 个？你添加和修改的内容会被清除。"))) return;
    closeQuickTaskForm();
    saveQuickTasks(defaultQuickTasks(), true);
  });
  elements.btnModelPage.addEventListener("click", () => setSettingsPage("model"));
  elements.btnPermissionPage.addEventListener("click", () => setSettingsPage("permission"));
  elements.btnAppearancePage.addEventListener("click", () => setSettingsPage("appearance"));
  elements.btnSearchPage.addEventListener("click", () => setSettingsPage("search"));
  elements.btnTasksPage.addEventListener("click", () => setSettingsPage("tasks"));
  elements.btnFilesPage.addEventListener("click", () => setSettingsPage("files"));
  elements.btnSessionPage.addEventListener("click", () => setSettingsPage("session"));
  elements.btnNotificationsPage.addEventListener("click", () => setSettingsPage("notifications"));
  elements.btnUsagePage.addEventListener("click", () => setSettingsPage("usage"));
  elements.usageScopeSelector.addEventListener("change", loadUsage);
  elements.usageDaysSelector.addEventListener("change", loadUsage);
  elements.btnUsageRefresh.addEventListener("click", loadUsage);
  elements.btnPricingPage.addEventListener("click", () => openPricing());
  elements.pricingModelInput.addEventListener("input", () => fillPricingFields(elements.pricingModelInput.value.trim()));
  for (const input of [elements.pricingInputRate, elements.pricingOutputRate, elements.pricingCachedRate]) input.addEventListener("input", syncPricingControls);
  elements.btnSavePricing.addEventListener("click", savePricing);
  elements.btnTasksRefresh.addEventListener("click", loadTaskCenter);
  elements.btnFileParent.addEventListener("click", () => loadWorkspaceFiles(fileEditor ? workspacePath : (workspaceParent || "")));
  elements.btnFilesRefresh.addEventListener("click", () => loadWorkspaceFiles(workspacePath));
  $("btnNewFolder").addEventListener("click", () => { void createWorkspaceFolder(); });
  elements.btnReloadFile.addEventListener("click", () => { if (fileEditor) void openWorkspaceFile(fileEditor.path, null, fileEditor.workspaceId); });
  elements.btnFileToKnowledge.addEventListener("click", () => { void addFileToKnowledge(); });
  elements.btnDiscardFileDraft.addEventListener("click", discardFileDraft);
  elements.btnSaveFile.addEventListener("click", saveWorkspaceFile);
  elements.btnFilePreview.addEventListener("click", showFilePreview);
  elements.btnFileSource.addEventListener("click", resetFilePreview);
  elements.btnFileInteractive.addEventListener("click", () => {
    if (!fileEditor?.loaded) return;
    void artifactAction({ ...fileEditor, mime_type: "text/html" }, "open", elements.btnFileInteractive, elements.fileEditorStatus, true);
  });
  elements.fileContentInput.addEventListener("input", () => {
    if (!fileEditor?.loaded || !fileEditor.editable || fileSaving) return;
    fileEditor.content = elements.fileContentInput.value;
    const saved = persistFileDraft();
    if (saved && !fileEditor.conflict) pageStatus(elements.fileEditorStatus, fileDirty() ? t("未保存 · 本地草稿已保留") : "");
    syncFileControls();
  });
  elements.sessionTitleInput.addEventListener("input", syncControls);
  elements.btnRenameSession.addEventListener("click", renameSession);
  $("btnArchiveSession").addEventListener("click", async () => {
    const session = sessions.find(item => item.id === currentSessionId);
    if (!session || isLoadingSession || activeTask) return;
    closeMenu();
    await setSessionArchived(session, true);
  });
  $("btnDeleteSession").addEventListener("click", async () => {
    const session = sessions.find(item => item.id === currentSessionId);
    if (!session || isLoadingSession || activeTask) return;
    if (await deleteSessions([session])) closeMenu();
  });
  elements.taskNotificationsToggle.addEventListener("change", changeNotificationPreference);
  elements.btnNotificationSettings.addEventListener("click", () => {
    try { bridge?.openNotificationSettings?.(); }
    catch (error) { pageStatus(elements.notificationPermissionStatus, t("打开通知设置失败: {0}", error.message), true); }
  });
  elements.sessionSearchInput.addEventListener("input", queueSessionSearch);
  elements.btnApplySettings.addEventListener("click", applyRuntimeSettings);
  elements.contextSummaryToggle.addEventListener("change", () => { contextSummaryDirty = true; });
  elements.btnProviderSettings.addEventListener("click", () => { if (!elements.btnProviderSettings.disabled) { closeMenu(); bridge?.openSettings?.(); } });
  elements.btnExport.addEventListener("click", exportConversation);
  elements.btnRefresh.addEventListener("click", async () => { closeMenu(); await loadSettings(); if (!activeTask) await loadSessions(currentSessionId); });
  elements.modelInput.addEventListener("input", () => { fillEffortOptions(elements.modelInput.value.trim(), elements.effortSelector.value); syncControls(); });
  elements.localContextSelector.addEventListener("change", () => { elements.localContextCustomRow.hidden = elements.localContextSelector.value !== "custom"; });
  elements.themeSelector.addEventListener("change", () => { preferences.theme = elements.themeSelector.value; writeStorage(settingsKey, preferences); applyAppearance(); });
  elements.textSizeSelector.addEventListener("change", () => { preferences.textSize = elements.textSizeSelector.value; writeStorage(settingsKey, preferences); applyAppearance(); });
  elements.quickActionsToggle.addEventListener("change", () => { preferences.quickActions = elements.quickActionsToggle.checked; writeStorage(settingsKey, preferences); applyAppearance(); });
  elements.hapticsToggle.addEventListener("change", () => { preferences.haptics = elements.hapticsToggle.checked; writeStorage(settingsKey, preferences); });
  function chooseAppearance(key, value) {
    if (!appearanceChoices[key].includes(value) || preferences[key] === value) return;
    preferences[key] = value;
    writeStorage(settingsKey, preferences);
    applyAppearance();
    haptic(12);
  }
  $("stylePicker").addEventListener("click", (event) => { const option = event.target.closest("[data-style-option]"); if (option) chooseAppearance("style", option.dataset.styleOption); });
  $("accentPicker").addEventListener("click", (event) => { const option = event.target.closest("[data-accent-option]"); if (option) chooseAppearance("accent", option.dataset.accentOption); });
  $("motionSelector").addEventListener("change", (event) => chooseAppearance("motion", event.target.value));
  $("backdropPicker").addEventListener("click", (event) => {
    const option = event.target.closest("[data-backdrop-option]");
    if (!option) return;
    if (option.dataset.backdropOption === "custom" && !customWallpaper) $("wallpaperInput").click();
    else chooseAppearance("backdrop", option.dataset.backdropOption);
  });
  $("btnChangeWallpaper").addEventListener("click", () => $("wallpaperInput").click());
  $("btnRemoveWallpaper").addEventListener("click", () => {
    customWallpaper = "";
    try { window.localStorage.removeItem(wallpaperKey); } catch { /* Nothing stored. */ }
    preferences.backdrop = "aurora";
    writeStorage(settingsKey, preferences);
    applyAppearance();
  });
  $("wallpaperInput").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    elements.settingsError.hidden = true;
    try {
      customWallpaper = await storeWallpaper(file);
      preferences.backdrop = "custom";
      writeStorage(settingsKey, preferences);
      applyAppearance();
      haptic(12);
    } catch (error) {
      elements.settingsError.textContent = error.message;
      elements.settingsError.hidden = false;
    }
  });
  $("languageSelector").addEventListener("change", (event) => {
    const value = event.target.value;
    if (!appearanceChoices.language.includes(value) || value === preferences.language) return;
    preferences.language = value;
    writeStorage(settingsKey, preferences);
    try { bridge?.setUiLanguage?.(value); } catch { /* Older APKs keep native text in Chinese. */ }
    // Text is chosen once per page load; drafts are already saved on every edit.
    saveDraft();
    persistFileDraft();
    window.AgentMobileUi.reloadForLanguage();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && (closeModelSheet() || closeDrawer() || closeMenu())) event.preventDefault();
    const dialog = layerOpen(sheet.layer) ? sheet.panel : layerOpen(elements.sessionDrawer) ? elements.sessionDrawerPanel
      : layerOpen(elements.settingsOverlay) ? elements.settingsSheet : null;
    if (event.key !== "Tab" || !dialog) return;
    const controls = [...dialog.querySelectorAll("button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], summary, [tabindex]")]
      .filter((control) => control.tabIndex >= 0 && !control.closest("[hidden], .hidden"));
    const first = controls[0];
    const last = controls[controls.length - 1];
    const active = document.activeElement;
    if (first && ((!dialog.contains(active)) || (event.shiftKey ? active === first : active === last))) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    }
  });
  elements.timelineContainer.addEventListener("scroll", () => {
    const timeline = elements.timelineContainer;
    stickToBottom = timeline.scrollHeight - timeline.scrollTop - timeline.clientHeight < 80;
    elements.btnJumpLatest.hidden = stickToBottom || timeline.scrollHeight <= timeline.clientHeight + 80;
  }, { passive: true });
  window.addEventListener("agent-notification-settings-changed", () => { if (!disposed) refreshNotificationSettings(); });
  window.addEventListener("agent-share-inbox-changed", refreshShareInbox);
  window.addEventListener("agent-share-inbox-imported", refreshShareInbox);
  window.addEventListener("focus", refreshShareInbox);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshShareInbox(); else flushQuickEffort(); });
  window.addEventListener("beforeunload", (event) => {
    if (fileDirty() && !persistFileDraft()) { event.preventDefault(); event.returnValue = ""; }
  });
  window.addEventListener("pagehide", () => { flushQuickEffort(); saveDraft(); persistFileDraft(); resetFilePreview(); artifactActions.clear(); disposed = true; });
  darkSchemeQuery?.addEventListener?.("change", syncSystemBars);
  window.visualViewport?.addEventListener("resize", resizeVisibleViewport);
  window.addEventListener("resize", resizeVisibleViewport);

  // Suggestion cards belong to an empty conversation only.
  const markEmptyConversation = () => { elements.appShell.dataset.empty = String(!!elements.timelineList.querySelector(":scope > .empty-state")); };
  new MutationObserver(markEmptyConversation).observe(elements.timelineList, { childList: true });
  markEmptyConversation();
  // The glass layout lets the timeline scroll under the header and dock, so it needs their sizes.
  if (typeof window.ResizeObserver === "function") {
    const chromeSize = new window.ResizeObserver(() => {
      elements.appShell.style.setProperty("--header-h", `${elements.mobileHeader.offsetHeight}px`);
      elements.appShell.style.setProperty("--dock-h", `${elements.bottomDock.offsetHeight}px`);
      if (stickToBottom) scrollToBottom(true);
    });
    chromeSize.observe(elements.mobileHeader);
    chromeSize.observe(elements.bottomDock);
  }

