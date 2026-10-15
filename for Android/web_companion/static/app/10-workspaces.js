  function closeQuickTaskForm() {
    editingQuickTask = -1;
    $("quickTaskForm").hidden = true;
  }

  function submitQuickTaskForm(event) {
    event.preventDefault();
    if (editingQuickTask < 0) return;
    const title = $("quickTaskTitle").value.trim();
    const prompt = $("quickTaskPrompt").value;
    if (!title || !prompt.trim()) { pageStatus($("quickTaskStatus"), t("名称和提示词都要填写"), true); return; }
    const task = {
      title: title.slice(0, 20),
      detail: $("quickTaskDetail").value.trim().slice(0, 40),
      prompt: prompt.slice(0, 4000),
      icon: $("quickTaskIcons").querySelector('[aria-checked="true"]')?.dataset.iconOption || "sparkles",
      send: $("quickTaskSend").checked,
    };
    const next = [...quickTasks];
    if (editingQuickTask >= next.length) next.push(task); else next[editingQuickTask] = task;
    closeQuickTaskForm();
    saveQuickTasks(next.slice(0, maxQuickTasks));
  }

  function updateTaskStatus(text = "", { resume = false, retry = false, reconnect = false, idle = false } = {}) {
    elements.taskStatusBar.hidden = !text;
    // Terminal states say so explicitly; the label text is translated and must not drive logic.
    elements.taskStatusBar.dataset.busy = String(!!text && !resume && !retry && !reconnect && !idle);
    elements.taskStateLabel.textContent = text;
    elements.btnResumeTask.hidden = !resume;
    elements.btnResumeTask.disabled = !resume;
    elements.btnRetryTask.hidden = !retry;
    elements.btnReconnect.hidden = !reconnect;
  }

  function hasBackgroundTasks() { return [...backgroundTasks.values()].some(task => !task.done); }

  function workspaceOfSession(sessionId) {
    const session = sessions.find(item => item.id === sessionId);
    if (!session) return null;
    return session.workspace_id || workspaces.find(item => item.path === session.workspace)?.id || defaultWorkspaceId;
  }

  function scopedUrl(path, workspaceId = currentWorkspaceId) {
    return workspaceId ? `${path}${path.includes("?") ? "&" : "?"}workspace_id=${encodeURIComponent(workspaceId)}` : path;
  }

  function syncWorkspaceControls() {
    const busy = workspaceSaving || workspacePicking || restartPending;
    elements.btnCreateWorkspace.disabled = busy || !elements.workspaceNameInput.value.trim() || !elements.workspaceFolderInput.value.trim();
    elements.workspaceNameInput.disabled = busy;
    elements.workspaceFolderInput.disabled = busy;
    elements.workspaceCreateDirectory.disabled = busy;
    elements.btnPickWorkspaceFolder.hidden = typeof bridge?.pickWorkspaceFolder !== "function";
    elements.btnPickWorkspaceFolder.disabled = busy;
    elements.btnWorkspacesRefresh.disabled = busy;
    elements.btnBrowseWorkspaceSystem.hidden = typeof bridge?.openWorkspaceBrowser !== "function";
    elements.btnBrowseWorkspaceSystem.disabled = restartPending || !workspaces.some(item => item.id === currentWorkspaceId);
    elements.workspaceDocumentsHint.hidden = elements.btnBrowseWorkspaceSystem.hidden;
    elements.btnSuggestWorkspaceFolder.hidden = typeof bridge?.recommendedWorkspaceFolder !== "function";
    elements.btnSuggestWorkspaceFolder.disabled = busy;
    elements.workspacePublicFolderHint.hidden = elements.btnSuggestWorkspaceFolder.hidden;
  }

  function renderWorkspaceNavigation() {
    elements.workspaceSelector.replaceChildren();
    for (const workspace of workspaces) {
      const option = document.createElement("option");
      option.value = workspace.id;
      option.textContent = workspace.name || workspace.path;
      elements.workspaceSelector.appendChild(option);
    }
    elements.workspaceSelector.value = currentWorkspaceId;
    elements.workspaceSelector.hidden = !workspaces.length;
    const current = workspaces.find(item => item.id === currentWorkspaceId);
    elements.menuWorkspaceSummary.textContent = current?.name || t("默认工作区");
    elements.workspaceTitleText.textContent = current?.name || t("本机工作区");
    renderDrawer();
    elements.workspacesList.replaceChildren();
    for (const workspace of workspaces) {
      const button = document.createElement("button");
      button.className = "menu-row workspace-row";
      button.type = "button";
      button.dataset.workspaceId = workspace.id;
      const text = document.createElement("span");
      const name = document.createElement("strong");
      const folder = document.createElement("small");
      name.textContent = workspace.name;
      folder.textContent = workspace.path;
      text.append(name, folder);
      const selected = document.createElement("span");
      selected.innerHTML = icon(workspace.id === currentWorkspaceId ? "check" : "chevron-right");
      if (workspace.id === currentWorkspaceId) button.setAttribute("aria-current", "true");
      button.append(text, selected);
      button.addEventListener("click", async () => { if (await switchWorkspace(workspace.id)) closeMenu(); });
      const item = document.createElement("div");
      item.className = "workspace-item";
      item.appendChild(button);
      if (workspace.id !== defaultWorkspaceId) {
        const remove = actionButton("trash-2", t("从列表移除 {0}", workspace.name || workspace.path), "data-workspace-remove", workspace.id);
        remove.disabled = workspaceSaving || restartPending;
        remove.addEventListener("click", () => removeWorkspace(workspace));
        item.appendChild(remove);
      }
      elements.workspacesList.appendChild(item);
    }
  }

  async function removeWorkspace(workspace) {
    if (workspaceSaving || disposed) return;
    if (!window.confirm(t("从列表移除「{0}」？\n文件夹和其中的文件不会被删除；重新添加同一文件夹即可找回它的会话。", workspace.name || workspace.path))) return;
    // Leave the workspace first so nothing keeps pointing at it.
    if (workspace.id === currentWorkspaceId && !await switchWorkspace(defaultWorkspaceId)) {
      pageStatus(elements.workspacesStatus, t("请先结束当前操作再移除此工作区"), true);
      return;
    }
    workspaceSaving = true;
    syncWorkspaceControls();
    pageStatus(elements.workspacesStatus, t("移除中..."));
    try {
      const data = await apiJson("/mobile/workspaces/remove", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ workspace_id: workspace.id }) });
      if (Array.isArray(data.workspaces)) workspaces = data.workspaces.filter(item => item && typeof item.id === "string" && typeof item.path === "string");
      else workspaces = workspaces.filter(item => item.id !== workspace.id);
      sessions = sessions.filter(session => workspaceOfSession(session.id) !== workspace.id);
      pageStatus(elements.workspacesStatus, t("已移除「{0}」", workspace.name || workspace.path));
      try { bridge?.refreshWorkspaceDocuments?.(); } catch { /* The app file page remains available. */ }
    } catch (error) {
      if (!disposed) pageStatus(elements.workspacesStatus, error.status === 409 ? t("该工作区仍有运行中的任务，请先停止任务") : t("移除工作区失败: {0}", error.message), true);
    } finally {
      workspaceSaving = false;
      if (!disposed) { renderWorkspaceNavigation(); syncControls(); }
    }
  }

  function sessionsInWorkspace() {
    return sessions.filter(item => !currentWorkspaceId || workspaceOfSession(item.id) === currentWorkspaceId);
  }

  // Archived conversations leave the lists unless they are the one being viewed.
  function listedSessions() {
    return sessionsInWorkspace().filter(item => item.archived !== true || item.id === currentSessionId);
  }

  let announcedSessionId = null;  // the conversation other modules were last told about

  function renderSessionNavigation() {
    elements.sessionSelector.replaceChildren();
    for (const session of listedSessions()) {
      const option = document.createElement("option");
      option.value = session.id;
      option.textContent = session.title || session.id.slice(0, 8);
      elements.sessionSelector.appendChild(option);
    }
    elements.sessionSelector.value = currentSessionId;
    const current = sessions.find(item => item.id === currentSessionId);
    elements.sessionTitleText.textContent = current ? (current.title || t("未命名会话")) : t("正在加载会话...");
    renderDrawer();
    if (announcedSessionId !== currentSessionId) {
      announcedSessionId = currentSessionId;
      window.dispatchEvent(new CustomEvent("agent-session-changed", { detail: { sessionId: currentSessionId } }));
    }
  }

  // ----- Conversation drawer: the visible navigation; the hidden selects keep the state. -----
  function relativeTime(value) {
    const time = new Date(value).getTime();
    if (!value || !Number.isFinite(time)) return "";
    const minutes = Math.floor((Date.now() - time) / 60000);
    if (minutes < 1) return t("刚刚");
    if (minutes < 60) return t("{0} 分钟前", minutes);
    if (minutes < 24 * 60) return t("{0} 小时前", Math.floor(minutes / 60));
    if (minutes < 48 * 60) return t("昨天");
    return new Date(time).toLocaleDateString(locale, { month: "numeric", day: "numeric" });
  }

  function drawerNavigationBusy() {
    return isLoadingSession || isUploading || restartPending || isPreparingSubmission || localDeviceTesting || (!!activeTask && !activeTask.id);
  }

  let showArchived = false;

  function drawerSessionItem(session, busy) {
    const item = document.createElement("div");
    item.className = "drawer-session-item";
    const row = document.createElement("button");
    row.type = "button";
    row.className = "drawer-session";
    row.dataset.sessionId = session.id;
    if (session.id === currentSessionId) row.setAttribute("aria-current", "true");
    const title = document.createElement("span");
    title.className = "drawer-session-title";
    title.textContent = session.title || t("未命名会话");
    const meta = document.createElement("small");
    const running = [...backgroundTasks.values()].some(task => task.sessionId === session.id && !task.done);
    meta.textContent = running ? t("任务进行中") : session.archived ? t("已归档") : relativeTime(session.updated_at);
    if (running) row.dataset.running = "true";
    row.append(title, meta);
    // Its tags, small, under the title.
    const tags = sessionTags(session.id);
    if (tags.length) {
      const chips = document.createElement("span");
      chips.className = "drawer-session-tags";
      for (const tag of tags) { const chip = document.createElement("span"); chip.textContent = tag; chips.append(chip); }
      row.append(chips);
    }
    row.disabled = busy;
    row.addEventListener("click", async () => {
      if (session.id === currentSessionId) { closeDrawer(); return; }
      if (await switchSession(session.id)) closeDrawer();
    });
    // A long press opens the same actions as the ⋯ button.
    row.addEventListener("contextmenu", (event) => { event.preventDefault(); if (!busy) openSessionSheet(session); });
    const archived = session.archived === true;
    const label = session.title || t("未命名会话");
    const more = actionButton("ellipsis", t("{0} 的更多操作", label), "data-session-more", session.id);
    more.classList.add("drawer-session-action");
    more.disabled = busy;
    more.addEventListener("click", () => openSessionSheet(session));
    item.append(row, more);
    if (archived) {
      // Archived conversations can also be deleted for good.
      const remove = actionButton("trash-2", t("删除 {0}", label), "data-session-delete", session.id);
      remove.classList.add("drawer-session-action", "danger-action");
      remove.disabled = busy || running;
      remove.addEventListener("click", () => { void deleteSessions([session]); });
      item.append(remove);
    }
    return item;
  }

  async function deleteSessions(list) {
    if (disposed || !list.length) return false;
    const running = new Set([...backgroundTasks.values()].filter(task => !task.done).map(task => task.sessionId));
    if (list.some(session => running.has(session.id) || (session.id === currentSessionId && activeTask))) {
      notice(t("该会话仍有运行中的任务，请先停止任务"));
      return false;
    }
    const question = list.length === 1
      ? t("永久删除「{0}」？\n聊天记录、任务和图片会被彻底删除，无法恢复；在工作区里生成的文件会保留。", list[0].title || t("未命名会话"))
      : t("永久删除这 {0} 个已归档会话？\n聊天记录、任务和图片会被彻底删除，无法恢复；在工作区里生成的文件会保留。", list.length);
    if (!window.confirm(question)) return false;
    // Deleting checks the whole conversation store before it commits, which takes a few seconds.
    notice(t("正在删除…"), "info");
    try {
      await apiJson("/sessions/delete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_ids: list.map(session => session.id) }) });
    } catch (error) {
      // The reply can be lost on the way while the deletion went through; check before failing.
      let gone = false;
      if (error.network) {
        try {
          const listing = await apiJson("/sessions");
          const remaining = new Set((Array.isArray(listing.sessions) ? listing.sessions : []).map(session => session.id));
          gone = list.every(session => !remaining.has(session.id));
        } catch {}
      }
      if (!gone) {
        if (!disposed) notice(error.status === 409 ? t("该会话仍有运行中的任务，请先停止任务") : t("删除失败: {0}", error.message));
        return false;
      }
    }
    haptic(16);
    const removed = new Set(list.map(session => session.id));
    sessions = sessions.filter(session => !removed.has(session.id));
    if (removed.has(currentSessionId)) {
      const next = sessionsInWorkspace().filter(item => item.archived !== true)
        .sort((first, second) => String(second.updated_at || "").localeCompare(String(first.updated_at || "")))[0];
      if (next) await switchSession(next.id);
      else await createSession();
    }
    if (disposed) return true;
    renderSessionNavigation();
    const message = list.length === 1 ? t("会话已删除") : t("已删除 {0} 个会话", list.length);
    notice(message, "info");
    return true;
  }

  function renderDrawer() {
    if (disposed || !elements.drawerSessionList) return;
    const busy = drawerNavigationBusy();
    elements.drawerWorkspaces.replaceChildren();
    for (const workspace of workspaces) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "drawer-workspace";
      chip.setAttribute("role", "radio");
      chip.setAttribute("aria-checked", String(workspace.id === currentWorkspaceId));
      chip.dataset.workspaceId = workspace.id;
      chip.title = workspace.path;
      chip.textContent = workspace.name || workspace.path;
      chip.disabled = busy || workspaceSaving;
      chip.addEventListener("click", async () => { if (workspace.id !== currentWorkspaceId) await switchWorkspace(workspace.id); });
      elements.drawerWorkspaces.appendChild(chip);
    }
    elements.drawerWorkspaces.hidden = !workspaces.length;
    elements.drawerSessionList.replaceChildren();
    const byRecent = (first, second) => String(second.updated_at || "").localeCompare(String(first.updated_at || ""));
    const known = new Set(allSessionTags());
    if (drawerTag && !known.has(drawerTag)) drawerTag = "";
    const visible = sessionsInWorkspace().filter(item => item.archived !== true && (!drawerTag || sessionTags(item.id).includes(drawerTag))).sort(byRecent);
    const archived = sessionsInWorkspace().filter(item => item.archived === true).sort(byRecent);
    // Filter by tag, when any conversation has one.
    if (known.size) {
      const filters = document.createElement("div");
      filters.className = "drawer-tag-filter";
      for (const [value, label] of [["", t("全部")], ...[...known].map(tag => [tag, tag])]) {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "memory-topic";
        chip.textContent = label;
        chip.setAttribute("aria-pressed", String(drawerTag === value));
        chip.addEventListener("click", () => { drawerTag = value; renderDrawer(); });
        filters.append(chip);
      }
      elements.drawerSessionList.appendChild(filters);
    }
    // Pinned first, then today, yesterday, this week and earlier.
    const pinned = visible.filter(item => isPinned(item.id)).sort((first, second) => sessionMeta.pinned.indexOf(first.id) - sessionMeta.pinned.indexOf(second.id));
    let group = null;
    for (const session of [...pinned, ...visible.filter(item => !isPinned(item.id))]) {
      const name = sessionGroup(session);
      if (name !== group) {
        group = name;
        const heading = document.createElement("p");
        heading.className = "drawer-group";
        heading.textContent = name;
        elements.drawerSessionList.appendChild(heading);
      }
      elements.drawerSessionList.appendChild(drawerSessionItem(session, busy));
    }
    if (!visible.length) {
      const empty = document.createElement("p");
      empty.className = "drawer-empty";
      empty.textContent = t("这个工作区还没有会话");
      elements.drawerSessionList.appendChild(empty);
    }
    if (archived.length) {
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "text-action drawer-archived-toggle";
      toggle.textContent = t("已归档 · {0}", archived.length);
      toggle.setAttribute("aria-expanded", String(showArchived));
      toggle.addEventListener("click", () => { showArchived = !showArchived; renderDrawer(); });
      elements.drawerSessionList.appendChild(toggle);
      if (showArchived) {
        for (const session of archived) elements.drawerSessionList.appendChild(drawerSessionItem(session, busy));
        if (archived.length > 1) {
          const clear = document.createElement("button");
          clear.type = "button";
          clear.className = "text-action drawer-archived-delete danger-action";
          clear.textContent = t("删除全部已归档会话");
          clear.disabled = busy;
          clear.addEventListener("click", () => { void deleteSessions(archived); });
          elements.drawerSessionList.appendChild(clear);
        }
      }
    }
    elements.btnDrawerNewSession.disabled = busy || elements.btnNewSession.disabled;
  }

  async function setSessionArchived(session, archived) {
    if (disposed) return;
    const label = session.title || t("未命名会话");
    if (archived && !window.confirm(t("归档「{0}」？\n会话会从列表隐藏，记录仍完整保留，可在「已归档」中恢复。", label))) return;
    try {
      await apiJson(`/sessions/${encodeURIComponent(session.id)}/archive`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ archived }) });
      session.archived = archived;
      haptic(16);
      if (archived && session.id === currentSessionId) {
        // Leave the archived conversation for the most recent remaining one, or a fresh one.
        const next = sessionsInWorkspace().filter(item => item.archived !== true && item.id !== session.id)
          .sort((first, second) => String(second.updated_at || "").localeCompare(String(first.updated_at || "")))[0];
        if (next) await switchSession(next.id);
        else await createSession();
      }
    } catch (error) {
      if (!disposed) notice(error.status === 409 ? t("该会话仍有运行中的任务，请先停止任务") : (archived ? t("归档失败: {0}", error.message) : t("恢复会话失败: {0}", error.message)));
    } finally {
      if (!disposed) renderSessionNavigation();
    }
  }

  function openDrawer() {
    if (disposed || layerOpen(elements.sessionDrawer)) return;
    if (layerOpen(elements.settingsOverlay) && !closeMenu()) return;
    closeModelSheet({ instant: true, keepFocus: true });
    renderDrawer();
    void loadSessionMeta();
    showLayer(elements.sessionDrawer, (motion) => {
      motion.stagger(elements.drawerSessionList.querySelectorAll(":scope > *:nth-child(-n+10)"), { transform: "translateX(-18px)" }, { delay: 60, step: 22, spring: "snappy" });
    });
    elements.appShell.inert = true;
    elements.btnSessions.setAttribute("aria-expanded", "true");
    (elements.drawerSessionList.querySelector('[aria-current="true"]') || elements.btnDrawerClose).focus({ preventScroll: true });
    haptic();
  }

  function closeDrawer(options = {}) {
    if (!layerOpen(elements.sessionDrawer)) return false;
    elements.appShell.inert = false;
    elements.btnSessions.setAttribute("aria-expanded", "false");
    elements.btnSessions.focus({ preventScroll: true });
    if (options.instant) { motionApi()?.stop(elements.sessionDrawer); elements.sessionDrawer.hidden = true; delete elements.sessionDrawer.dataset.leaving; return true; }
    hideLayer(elements.sessionDrawer, (motion) => [
      motion.play(elements.sessionDrawerPanel, [{ transform: "none" }, { transform: "translateX(-104%)" }], { duration: 220, easing: "cubic-bezier(.4, 0, .9, .55)", fill: "forwards" }),
      motion.play(elements.sessionDrawerBackdrop, [{ opacity: 1 }, { opacity: 0 }], { duration: 200, easing: "ease-out", fill: "forwards" }),
    ]);
    return true;
  }

  function refreshWorkspaceAccess() {
    if (typeof bridge?.workspaceStorageStatus !== "function") return;
    try {
      const status = JSON.parse(bridge.workspaceStorageStatus());
      elements.workspaceStorageStatus.hidden = false;
      pageStatus(elements.workspaceStorageStatus, status.granted ? t("公共文件夹访问已授权") : t("公共文件夹需要文件访问授权；应用内文件夹可直接使用"));
      elements.btnWorkspaceStorageSettings.hidden = status.granted || typeof bridge?.requestWorkspaceStorageAccess !== "function";
    } catch { pageStatus(elements.workspaceStorageStatus, t("无法读取文件访问权限"), true); }
  }

  async function loadWorkspaces() {
    const generation = ++workspaceGeneration;
    try {
      const data = await apiJson("/mobile/workspaces");
      if (disposed || generation !== workspaceGeneration) return;
      if (Array.isArray(data.workspaces)) {
        workspaces = data.workspaces.filter(item => item && typeof item.id === "string" && typeof item.path === "string");
        defaultWorkspaceId = data.default_workspace_id || workspaces.find(item => item.is_default)?.id || workspaces[0]?.id || "";
        if (!workspaces.some(item => item.id === currentWorkspaceId)) currentWorkspaceId = defaultWorkspaceId;
        renderWorkspaceNavigation();
        try { bridge?.refreshWorkspaceDocuments?.(); } catch { /* The app file page remains available. */ }
        pageStatus(elements.workspacesStatus, "");
      }
    } catch (error) {
      if (!disposed && settingsPage === "workspaces") pageStatus(elements.workspacesStatus, t("读取工作区失败: {0}", error.message), true);
    } finally { if (!disposed) { refreshWorkspaceAccess(); syncWorkspaceControls(); } }
  }

  function detachSessionTask() {
    if (activeTask?.id) { backgroundTasks.set(activeTask.sessionId, activeTask); activeTask.card = null; }
    activeTask = null;
    taskAdoptionGeneration += 1;
    showApproval(null);
  }

  async function switchWorkspace(id) {
    if (!workspaces.some(item => item.id === id) || isLoadingSession || isUploading || isPreparingSubmission || restartPending || localDeviceTesting || !canLeaveFileEditor() || fileSaving || (!!activeTask && !activeTask.id)) return false;
    const previousWorkspaceId = currentWorkspaceId;
    const previousSessionId = currentSessionId;
    const previousSessions = sessions;
    const blank = blankSessionId();
    saveDraft();
    detachSessionTask();
    currentWorkspaceId = id;
    writeStorage(workspaceKey, id);
    resetFilePreview();
    fileEditor = null;
    workspacePath = "";
    workspaceParent = null;
    filesGeneration += 1;
    usageGeneration += 1;
    renderWorkspaceNavigation();
    if (!await loadSessions("")) {
      currentWorkspaceId = previousWorkspaceId;
      currentSessionId = previousSessionId;
      selectedSessionId = previousSessionId;
      sessions = previousSessions;
      writeStorage(workspaceKey, previousWorkspaceId);
      writeStorage(sessionKey, previousSessionId);
      renderWorkspaceNavigation();
      renderSessionNavigation();
      restoreDraft(previousSessionId);
      isLoadingSession = true;
      syncControls();
      try {
        await loadTimeline(previousSessionId);
        if (historyReady) await recoverSessionTask(previousSessionId);
      } finally { isLoadingSession = false; syncControls(); }
      return false;
    }
    const switched = currentWorkspaceId === id && historyReady;
    if (switched) discardBlankSession(blank);
    return switched;
  }

  async function createWorkspace(event) {
    event?.preventDefault();
    if (elements.btnCreateWorkspace.disabled) return;
    const payload = { name: elements.workspaceNameInput.value.trim(), path: elements.workspaceFolderInput.value.trim(), create: elements.workspaceCreateDirectory.checked };
    workspaceSaving = true;
    syncWorkspaceControls();
    pageStatus(elements.workspacesStatus, t("创建中..."));
    try {
      const data = await apiJson("/mobile/workspaces", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const workspace = data.workspace || data;
      if (!workspace?.id || typeof workspace.path !== "string") throw new Error(t("服务未返回工作区"));
      workspaces = [...workspaces.filter(item => item.id !== workspace.id), workspace];
      workspaceSaving = false;
      elements.workspaceNameInput.value = "";
      elements.workspaceFolderInput.value = "";
      elements.workspaceCreateDirectory.checked = false;
      await switchWorkspace(workspace.id);
      pageStatus(elements.workspacesStatus, t("已创建"));
      renderWorkspaceNavigation();
      try { bridge?.refreshWorkspaceDocuments?.(); } catch { /* The app file page remains available. */ }
    } catch (error) { if (!disposed) pageStatus(elements.workspacesStatus, t("创建工作区失败: {0}", error.message), true); }
    finally { workspaceSaving = false; if (!disposed) syncControls(); }
  }

  // A long task on the phone's own model must not lose its engine when the screen times out:
  // some phones kill a large background engine once the app is off a lit screen.
  let keepingScreenOn = false;
