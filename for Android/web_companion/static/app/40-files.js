  function attachQuickShare() {
    if (!quickShareBatch || typeof bridge?.confirmShareInbox !== "function") return;
    if (Date.now() > quickShareDeadline || !currentSessionId) { quickShareBatch = null; return; }
    const items = shareInbox.items.filter((item) => item.batch_id === quickShareBatch);
    if (!items.length || items.some((item) => item.state === "staging")) return; // wait for the next inbox change
    const pending = items.filter((item) => item.state === "pending").map((item) => item.id);
    quickShareBatch = null;
    if (!pending.length) return;
    try {
      const result = JSON.parse(bridge.confirmShareInbox(JSON.stringify({ request_id: requestId("share"),
        session_id: currentSessionId, workspace_id: workspaceOfSession(currentSessionId), item_ids: pending })));
      if (!result.ok) throw new Error(localizeError(result.error) || t("无法导入附件"));
      if (quickNote?.batch === items[0].batch_id) notice(t("录音已保存，正在整理纪要…"), "info");
      else notice(t("截图已添加到这次对话，输入你的问题吧"), "info");
    } catch (error) { notice(error.message); }
  }

  // Sends the voice note's request once its recording reached this conversation's attachments.
  function sendQuickNote() {
    if (!quickNote || disposed) return;
    if (Date.now() > quickNote.deadline || !currentSessionId) { quickNote = null; return; }
    const recorded = shareInbox.items.some((item) => item.batch_id === quickNote.batch && item.state === "ready"
      && attachments.some((file) => file.path === item.attachment?.path));
    if (!recorded || activeTask || isPreparingSubmission || isUploading) return; // checked again on the next inbox change
    quickNote = null;
    elements.promptInput.value = t("把附件里的录音转写成文字，整理成一份纪要（要点、决定、待办事项），保存为 Markdown 文件放到工作区的「录音速记」文件夹，再把纪要加入知识库。最后告诉我纪要的要点和文件位置。");
    elements.promptInput.dispatchEvent(new Event("input", { bubbles: true }));
    void sendPrompt();
  }

  function openSession(sessionId) {
    if (disposed || typeof sessionId !== "string" || !sessionId || sessionId.length > 200) return false;
    if (unavailableSessions.has(sessionId) && !isLoadingSession && historyReady) {
      notice(t("目标会话不存在或已删除"));
      return true;
    }
    if (!isLoadingSession && historyReady && currentSessionId === sessionId) {
      void refreshCurrentSessionTask();
      closeMenu();
      return true;
    }
    if (isLoadingSession || !historyReady || isUploading || isPreparingSubmission || restartPending || (!!activeTask && !activeTask.id) || sessionOpening) return false;
    if (!canLeaveFileEditor()) return false;
    sessionOpening = sessionId;
    void switchSession(sessionId).finally(() => { sessionOpening = null; });
    return false;
  }

  window.AgentMobileUi = { openMenu, closeMenu, handleBack, notice, reloadForLanguage: () => window.location.reload(), receiveSharedText, openSession, quickAsk, apiJson, setSettingsPage, adoptTask,
    readLocalContextDraft, setLocalContextDraft,
    setLocalContextBusy: (busy) => { localContextBusy = !!busy; syncControls(); },
    setLocalDeviceTestBusy: (busy) => { localDeviceTesting = !!busy; syncControls(); },
    context: () => ({ sessionId: currentSessionId, workspaceId: currentWorkspaceId, settings: { ...settings }, activeTask: !!activeTask || isPreparingSubmission || localDeviceTesting, draft: elements.promptInput.value,
      recentText: timelineMessages().filter((message) => message.content).slice(-6).map((message) => `${message.role}: ${message.content}`).join("\n").slice(-16384) }),
  };

  // Read from the timeline: historyEvents only holds what was loaded, not turns sent since then.
  function timelineMessages() {
    return [...elements.timelineList.querySelectorAll(".message-card.user, .message-card.assistant")]
      .filter((card) => !card.hidden)
      .map((card) => card.classList.contains("user")
        ? { role: "user", content: card.dataset.displayText || card.dataset.messageText || "" }
        // A live reply keeps its text in messageText; displayText still holds the placeholder.
        : { role: "assistant", content: card.dataset.messageText || "" });
  }
  window.AgentMobile = window.AgentMobileUi;

  function pageStatus(element, text, error = false) {
    element.textContent = text;
    element.classList.toggle("error", error);
  }

  const taskStateLabels = { queued: t("排队中"), running: t("执行中"), waiting_approval: t("等待审批"), succeeded: t("已完成"), failed: t("失败"), cancelled: t("已停止"), interrupted: t("已中断") };

  function displayTime(value) {
    const time = new Date(value);
    return value && Number.isFinite(time.getTime()) ? time.toLocaleString(locale, { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
  }

  function actionButton(name, label, attribute, taskId) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "icon-button";
    button.title = label;
    button.setAttribute("aria-label", label);
    button.setAttribute(attribute, taskId);
    button.innerHTML = icon(name);
    return button;
  }

  function renderTaskCenter() {
    elements.taskCenterList.replaceChildren();
    for (const task of taskCenterTasks) {
      if (!task?.task_id || !task.session_id) continue;
      const row = document.createElement("div");
      row.className = "task-center-row";
      const title = document.createElement("strong");
      title.textContent = task.prompt_preview || task.task_id;
      const meta = document.createElement("div");
      meta.className = "task-center-meta";
      const state = document.createElement("span");
      state.textContent = taskStateLabels[task.state] || task.state;
      const time = document.createElement("time");
      time.textContent = displayTime(task.updated_at || task.created_at);
      if (task.updated_at || task.created_at) time.dateTime = task.updated_at || task.created_at;
      const model = document.createElement("span");
      model.textContent = task.model || "";
      meta.append(state, time, model);
      if (task.state === "failed" && typeof task.reason === "string" && task.reason.trim()) {
        const reason = document.createElement("span");
        reason.className = "task-center-reason";
        reason.textContent = task.reason.trim().slice(0, 300);
        meta.append(reason);
      }
      const actions = document.createElement("div");
      actions.className = "task-center-actions";
      const open = document.createElement("button");
      open.type = "button";
      open.className = "text-action";
      open.textContent = t("打开会话");
      open.dataset.taskOpen = task.task_id;
      open.dataset.sessionId = task.session_id;
      open.addEventListener("click", async () => {
        if (task.session_id === currentSessionId && !isLoadingSession && historyReady) {
          await refreshCurrentSessionTask();
          closeMenu();
        }
        else if (await switchSession(task.session_id)) closeMenu();
      });
      actions.appendChild(open);
      if (runningStates.has(task.state)) {
        const cancel = actionButton("square", t("停止任务"), "data-task-cancel", task.task_id);
        cancel.disabled = taskActions.has(task.task_id);
        cancel.addEventListener("click", () => changeTask(task, "cancel"));
        actions.appendChild(cancel);
      } else if (task.state === "interrupted" && task.resume_available) {
        const resume = actionButton("play", t("恢复任务"), "data-task-resume", task.task_id);
        resume.disabled = taskActions.has(task.task_id);
        resume.addEventListener("click", () => changeTask(task, "resume"));
        actions.appendChild(resume);
      }
      row.append(title, meta, actions);
      renderTaskArtifacts(row, task, task.task_id);
      elements.taskCenterList.appendChild(row);
    }
    syncControls();
  }

  async function loadTaskCenter() {
    const generation = ++taskCenterGeneration;
    pageStatus(elements.taskCenterStatus, t("加载中..."));
    try {
      const data = await apiJson("/mobile/tasks");
      if (generation !== taskCenterGeneration || settingsPage !== "tasks") return;
      if (workspaces.length && (data.tasks || []).some(task => !workspaceOfSession(task.session_id))) {
        const listing = await apiJson("/sessions");
        if (generation !== taskCenterGeneration || settingsPage !== "tasks") return;
        if (!Array.isArray(listing.sessions)) throw new Error(t("无法确认任务所属工作区"));
        sessions = [...new Map([...sessions, ...listing.sessions].map(session => [session.id, session])).values()];
        if ((data.tasks || []).some(task => !workspaceOfSession(task.session_id))) throw new Error(t("无法确认任务所属工作区，请刷新任务列表"));
      }
      taskCenterTasks = Array.isArray(data.tasks) ? [...data.tasks].sort((first, second) => String(second.created_at || "").localeCompare(String(first.created_at || ""))) : [];
      renderTaskCenter();
      pageStatus(elements.taskCenterStatus, taskCenterTasks.length ? "" : t("暂无任务"));
    } catch (error) {
      if (disposed || generation !== taskCenterGeneration || settingsPage !== "tasks") return;
      elements.taskCenterList.replaceChildren();
      pageStatus(elements.taskCenterStatus, t("加载任务失败: {0}", error.message), true);
    }
  }

  async function changeTask(snapshot, action) {
    if (taskActions.has(snapshot.task_id) || disposed) return;
    taskActions.add(snapshot.task_id);
    renderTaskCenter();
    const targetSessionId = snapshot.session_id;
    try {
      const result = await apiJson(`/mobile/tasks/${encodeURIComponent(snapshot.task_id)}/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      if (activeTask?.id === snapshot.task_id && action === "cancel") {
        activeTask.stopping = true;
        if (terminalStates.has(result.task?.state)) {
          activeTask.state = result.task.state;
          activeTask.done = true;
          finishTask(activeTask);
        } else if (!activeTask.watching) void watchTask(activeTask);
      } else if (action === "resume" && !activeTask && !isLoadingSession && targetSessionId === currentSessionId) {
        activeTask = makeTask(result.task || snapshot);
        interruptedTask = null;
        syncControls();
        void watchTask(activeTask);
      }
      if (settingsPage === "tasks" && !elements.settingsOverlay.hidden) await loadTaskCenter();
    } catch (error) {
      if (disposed) return;
      if (settingsPage === "tasks") pageStatus(elements.taskCenterStatus, t("{0}任务失败: {1}", action === "cancel" ? t("停止") : t("恢复"), error.message), true);
      else notice(error.message);
    } finally {
      taskActions.delete(snapshot.task_id);
      if (!disposed && settingsPage === "tasks") renderTaskCenter();
    }
  }

  function formatBytes(size) {
    const count = Number(size) || 0;
    return count >= 1024 * 1024 ? `${(count / (1024 * 1024)).toFixed(1)} MB` : count >= 1024 ? `${(count / 1024).toFixed(1)} KB` : `${count} B`;
  }

  function fileDirty() { return !!fileEditor?.loaded && fileEditor.content !== fileEditor.originalContent; }

  function fileDraftKey(path, workspaceId = fileEditor?.workspaceId || currentWorkspaceId) {
    return workspaceId && workspaceId !== defaultWorkspaceId ? `${workspaceId}:${path}` : path;
  }

  function persistFileDraft() {
    if (!fileEditor?.loaded || !fileEditor.editable) return true;
    const next = { ...fileDrafts };
    const key = fileDraftKey(fileEditor.path);
    if (fileDirty()) next[key] = { content: fileEditor.content, sha256: fileEditor.sha256 };
    else delete next[key];
    try {
      window.localStorage.setItem(fileDraftsKey, JSON.stringify(next));
      for (const path of Object.keys(fileDrafts)) delete fileDrafts[path];
      Object.assign(fileDrafts, next);
      return true;
    } catch {
      pageStatus(elements.fileEditorStatus, t("本地草稿保存失败，请先保存文件"), true);
      return false;
    }
  }

  function canLeaveFileEditor() {
    if (!fileDirty() || persistFileDraft()) return true;
    return window.confirm(t("文件草稿无法保存在手机上，离开可能丢失修改。继续离开？"));
  }

  function syncFileControls() {
    const loaded = !!fileEditor?.loaded;
    elements.fileContentInput.readOnly = !loaded || !fileEditor.editable || fileSaving;
    elements.btnSaveFile.disabled = !loaded || !fileEditor.editable || !fileDirty() || !!fileEditor.conflict || fileSaving || restartPending;
    elements.btnReloadFile.disabled = !loaded || fileSaving;
    elements.btnDiscardFileDraft.hidden = !loaded || (!fileDirty() && !fileDrafts[fileDraftKey(fileEditor?.path)]);
    elements.btnDiscardFileDraft.disabled = fileSaving;
    elements.btnFileParent.disabled = fileSaving || (!fileEditor && workspaceParent === null);
    elements.btnFilesRefresh.disabled = fileSaving;
    $("btnNewFolder").hidden = !!fileEditor;
    $("btnNewFolder").disabled = fileSaving || restartPending;
    for (const button of elements.workspaceFilesList.querySelectorAll(".workspace-file-actions button, .workspace-file-more")) button.disabled = fileSaving || restartPending;
    const preview = loaded && /\.(md|markdown|html?|png|jpe?g|webp|gif|svg)$/i.test(fileEditor.path);
    elements.btnFilePreview.hidden = !preview;
    elements.btnFileSource.hidden = !preview || fileEditor.is_binary;
    elements.btnFilePreview.disabled = !loaded || fileSaving;
    elements.btnFileSource.disabled = !loaded || fileSaving;
    elements.btnFileInteractive.hidden = !loaded || !/\.html?$/i.test(fileEditor.path) || typeof bridge?.workspaceFileAction !== "function";
    elements.btnFileInteractive.disabled = !loaded || fileSaving || fileDirty() || restartPending;
    elements.btnFileHomeTool.hidden = elements.btnFileInteractive.hidden || !canMakeHomeTools();
    elements.btnFileHomeTool.disabled = elements.btnFileInteractive.disabled;
    syncHomeToolsVisibility();
    elements.btnFileToKnowledge.hidden = !loaded || !knowledgeFiles.test(fileEditor.path);
    elements.btnFileToKnowledge.disabled = fileSaving || fileKnowledgeAdding;
  }

  async function addFileToKnowledge() {
    const editor = fileEditor;
    if (!editor?.loaded || fileKnowledgeAdding) return;
    fileKnowledgeAdding = true;
    syncFileControls();
    try {
      const added = await apiJson("/mobile/knowledge/import", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: editor.path, ...(editor.workspaceId ? { workspace_id: editor.workspaceId } : {}) }) });
      if (fileEditor === editor) pageStatus(elements.fileEditorStatus, added?.duplicate ? t("这份文档已经在知识库里了") : t("已加入知识库，正在读取内容，可在“知识库”页查看"));
    } catch (error) {
      if (!disposed && fileEditor === editor) pageStatus(elements.fileEditorStatus, t("加入知识库失败: {0}", error.message), true);
    } finally { fileKnowledgeAdding = false; if (!disposed) syncFileControls(); }
  }

  function resetFilePreview() {
    if (filePreviewUrl) URL.revokeObjectURL(filePreviewUrl);
    filePreviewUrl = null;
    elements.filePreviewPanel.replaceChildren();
    elements.filePreviewPanel.classList.remove("message-body");
    elements.filePreviewPanel.hidden = true;
    elements.fileContentInput.hidden = false;
    elements.btnFilePreview.setAttribute("aria-pressed", "false");
    elements.btnFileSource.setAttribute("aria-pressed", "true");
  }

  async function showFilePreview() {
    const editor = fileEditor;
    if (!editor?.loaded || fileSaving || elements.btnFilePreview.hidden) return;
    const generation = filesGeneration;
    const image = /\.(png|jpe?g|webp|gif|svg)$/i.test(editor.path);
    if (image) {
      pageStatus(elements.fileEditorStatus, t("读取图片..."));
      try {
        const downloaded = await downloadArtifact(editor);
        const type = /\.svg$/i.test(editor.path) ? "image/svg+xml" : downloaded.type;
        const blob = type ? new Blob([downloaded], { type }) : downloaded;
        if (disposed || fileEditor !== editor || generation !== filesGeneration || elements.settingsOverlay.hidden) return;
        resetFilePreview();
        filePreviewUrl = URL.createObjectURL(blob);
        const img = document.createElement("img");
        img.src = filePreviewUrl;
        img.alt = editor.path.split("/").pop();
        elements.filePreviewPanel.appendChild(img);
        pageStatus(elements.fileEditorStatus, "");
      } catch (error) {
        if (!disposed && fileEditor === editor && generation === filesGeneration) pageStatus(elements.fileEditorStatus, t("预览失败: {0}", error.message), true);
        return;
      }
    } else {
      resetFilePreview();
      if (/\.html?$/i.test(editor.path)) {
        const frame = document.createElement("iframe");
        frame.setAttribute("sandbox", "");
        frame.setAttribute("referrerpolicy", "no-referrer");
        frame.title = editor.path;
        frame.srcdoc = editor.content || "";
        elements.filePreviewPanel.appendChild(frame);
      } else {
        elements.filePreviewPanel.classList.add("message-body");
        setMarkdown(elements.filePreviewPanel, editor.content || "");
      }
    }
    elements.fileContentInput.hidden = true;
    elements.filePreviewPanel.hidden = false;
    elements.btnFilePreview.setAttribute("aria-pressed", "true");
    elements.btnFileSource.setAttribute("aria-pressed", "false");
  }

  function renderFileEditor() {
    if (!fileEditor) return;
    elements.workspaceFilesList.hidden = true;
    elements.fileEditorPanel.hidden = false;
    $("fileHistoryPanel").hidden = true;
    elements.workspaceFilePath.textContent = fileEditor.path;
    elements.fileContentInput.value = fileEditor.content || "";
    elements.fileEditorMeta.textContent = fileEditor.loaded ? `${formatBytes(fileEditor.size)}${fileEditor.editable ? " · UTF-8" : t(" · 只读")}` : "";
    syncFileControls();
  }

  async function loadWorkspaceFiles(path = "") {
    if (!canLeaveFileEditor() || fileSaving) return;
    const generation = ++filesGeneration;
    const workspaceId = currentWorkspaceId;
    resetFilePreview();
    fileEditor = null;
    workspacePath = path;
    elements.workspaceFilePath.textContent = path || t("工作区");
    elements.workspaceFilesList.hidden = false;
    elements.fileEditorPanel.hidden = true;
    $("fileHistoryPanel").hidden = true;
    elements.workspaceFilesList.replaceChildren();
    pageStatus(elements.workspaceFilesStatus, t("加载中..."));
    syncFileControls();
    try {
      const data = await apiJson(scopedUrl(`/mobile/workspace/files?path=${encodeURIComponent(path)}`, workspaceId));
      if (generation !== filesGeneration || settingsPage !== "files") return;
      workspacePath = typeof data.path === "string" ? data.path : path;
      workspaceParent = data.parent ?? null;
      elements.workspaceFilePath.textContent = workspacePath || t("工作区");
      for (const file of Array.isArray(data.files) ? data.files : []) {
        if (!file || typeof file.path !== "string" || typeof file.name !== "string") continue;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "workspace-file-row";
        button.dataset.filePath = file.path;
        button.innerHTML = icon(file.type === "directory" ? "folder" : "file-text");
        const name = document.createElement("span");
        name.textContent = file.name;
        const size = document.createElement("small");
        size.textContent = file.type === "directory" ? "" : formatBytes(file.size);
        button.append(name, size);
        button.addEventListener("click", () => { if (file.type === "directory") void loadWorkspaceFiles(file.path); else void openWorkspaceFile(file.path); });
        elements.workspaceFilesList.appendChild(workspaceFileItem(file, button));
      }
      pageStatus(elements.workspaceFilesStatus, data.truncated ? t("文件较多，仅显示部分结果") : (elements.workspaceFilesList.children.length ? "" : t("目录为空")));
    } catch (error) {
      if (disposed || generation !== filesGeneration || settingsPage !== "files") return;
      pageStatus(elements.workspaceFilesStatus, t("加载文件失败: {0}", error.message), true);
    } finally { if (generation === filesGeneration && !disposed) syncFileControls(); }
  }

  // ----- Files page changes: rename, move, delete, new folder -----
  function workspaceFileItem(file, row) {
    const item = document.createElement("div");
    item.className = "workspace-file-item";
    const more = document.createElement("button");
    more.type = "button";
    more.className = "icon-button workspace-file-more";
    more.title = t("更多操作");
    more.setAttribute("aria-label", t("{0} 的更多操作", file.name));
    more.setAttribute("aria-expanded", "false");
    more.innerHTML = icon("ellipsis");
    const actions = document.createElement("div");
    actions.className = "workspace-file-actions";
    actions.hidden = true;
    for (const [name, label, run, danger] of [
      ["pencil", t("重命名"), () => renameWorkspaceEntry(file)],
      ["folder-open", t("移动到…"), () => moveWorkspaceEntry(file)],
      ["trash-2", t("删除"), () => deleteWorkspaceEntry(file), true],
    ]) {
      const action = document.createElement("button");
      action.type = "button";
      action.className = danger ? "text-action danger-action" : "text-action";
      action.innerHTML = icon(name);
      action.append(label);
      action.addEventListener("click", () => { void run(); });
      actions.appendChild(action);
    }
    more.addEventListener("click", () => {
      actions.hidden = !actions.hidden;
      more.setAttribute("aria-expanded", String(!actions.hidden));
    });
    item.append(row, more, actions);
    return item;
  }

  const entryParent = (path) => (path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "");
  const entryPath = (folder, name) => (folder ? `${folder}/${name}` : name);
  const validEntryName = (name) => !!name && name.length <= 255 && !/[\/\\]/.test(name) && name !== "." && name !== "..";

  async function changeWorkspaceEntry(action, payload, done, missing) {
    if (fileSaving || restartPending || disposed) return false;
    fileSaving = true;
    syncFileControls();
    try {
      await apiJson(`/mobile/workspace/${action}`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, ...(currentWorkspaceId ? { workspace_id: currentWorkspaceId } : {}) }) });
    } catch (error) {
      fileSaving = false;
      if (!disposed) {
        syncFileControls();
        pageStatus(elements.workspaceFilesStatus, error.status === 409 ? t("已有同名的文件或文件夹")
          : error.status === 404 ? missing
          : error.status === 503 ? t("工作区正忙，请等当前工具运行完再试")
          : t("操作失败: {0}", error.message), true);
      }
      return false;
    }
    fileSaving = false;
    haptic(16);
    await loadWorkspaceFiles(workspacePath);
    if (!disposed) pageStatus(elements.workspaceFilesStatus, done);
    return true;
  }

  async function renameWorkspaceEntry(file) {
    const answer = window.prompt(t("新名称"), file.name);
    if (answer === null) return;
    const name = answer.trim();
    if (!validEntryName(name)) { pageStatus(elements.workspaceFilesStatus, t("名称不能为空，也不能包含 / 或 \\"), true); return; }
    if (name === file.name) return;
    await changeWorkspaceEntry("move", { path: file.path, destination: entryPath(entryParent(file.path), name) },
      t("已重命名为“{0}”", name), t("文件或文件夹不存在，可能已被移动或删除"));
  }

  async function moveWorkspaceEntry(file) {
    const answer = window.prompt(t("移动到哪个文件夹？填写工作区里的文件夹路径，例如 docs/2026；留空表示工作区根目录"), entryParent(file.path));
    if (answer === null) return;
    const folder = answer.trim().replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
    if (folder === entryParent(file.path)) return;
    await changeWorkspaceEntry("move", { path: file.path, destination: entryPath(folder, file.name) },
      folder ? t("已移动到 {0}", folder) : t("已移动到工作区根目录"), t("目标文件夹不存在，请先新建它"));
  }

  async function deleteWorkspaceEntry(file) {
    const question = file.type === "directory"
      ? t("删除文件夹“{0}”和其中的全部内容？删除后无法恢复。", file.name)
      : t("删除“{0}”？删除后无法恢复。", file.name);
    if (!window.confirm(question)) return;
    await changeWorkspaceEntry("delete", { path: file.path }, t("已删除“{0}”", file.name), t("文件或文件夹不存在，可能已被移动或删除"));
  }

  async function createWorkspaceFolder() {
    const answer = window.prompt(t("新文件夹名称"), "");
    if (answer === null) return;
    const name = answer.trim();
    if (!validEntryName(name)) { pageStatus(elements.workspaceFilesStatus, t("名称不能为空，也不能包含 / 或 \\"), true); return; }
    await changeWorkspaceEntry("mkdir", { path: entryPath(workspacePath, name) }, t("已新建文件夹“{0}”", name), t("当前文件夹不存在，请刷新后再试"));
  }

  async function openWorkspaceFile(path, sha256 = null, workspaceId = currentWorkspaceId) {
    if (!canLeaveFileEditor() || fileSaving) return;
    const generation = ++filesGeneration;
    resetFilePreview();
    fileEditor = { path, workspaceId, content: "", loaded: false, editable: false };
    renderFileEditor();
    pageStatus(elements.workspaceFilesStatus, "");
    pageStatus(elements.fileEditorStatus, t("读取中..."));
    try {
      const data = await apiJson(scopedUrl(`/mobile/workspace/file?path=${encodeURIComponent(path)}${sha256 ? `&sha256=${encodeURIComponent(sha256)}` : ""}`, workspaceId));
      if (generation !== filesGeneration || settingsPage !== "files") return false;
      const originalContent = typeof data.content === "string" ? data.content : "";
      const draft = fileDrafts[fileDraftKey(path, workspaceId)];
      const editable = data.editable === true && !data.is_binary && !data.truncated && typeof data.sha256 === "string";
      fileEditor = {
        ...data, path, workspaceId, loaded: true, editable, originalContent,
        content: editable && typeof draft?.content === "string" ? draft.content : originalContent,
        sha256: editable && typeof draft?.sha256 === "string" ? draft.sha256 : data.sha256,
        conflict: editable && !!draft && draft.sha256 !== data.sha256,
      };
      renderFileEditor();
      const message = data.is_binary ? t("二进制文件无法编辑") : data.truncated ? t("文件过大，仅显示部分内容（只读）")
        : fileEditor.conflict ? t("文件已在其他地方更改，本地草稿存在冲突。可复制草稿或放弃草稿后重新读取")
        : !editable ? t("此文件仅可查看") : draft ? t("已恢复本地草稿") : "";
      pageStatus(elements.fileEditorStatus, message, !!fileEditor.conflict);
      return true;
    } catch (error) {
      if (disposed || generation !== filesGeneration || settingsPage !== "files") return;
      pageStatus(elements.fileEditorStatus, t("读取文件失败: {0}", error.message), true);
      return false;
    }
  }

