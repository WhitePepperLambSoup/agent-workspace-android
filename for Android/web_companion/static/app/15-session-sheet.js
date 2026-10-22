
  // ---- Conversation actions (2.0): pin, tags, export, archive -------------------------------
  // Pins and tags live on the engine (session-meta); the drawer groups and filters by them.
  let sessionMeta = { tags: {}, pinned: [] };
  let drawerTag = "";
  let sheetSession = null;

  async function loadSessionMeta() {
    try {
      const value = await apiJson("/mobile/session-meta");
      sessionMeta = { tags: value.tags || {}, pinned: value.pinned || [] };
    } catch { /* The drawer still lists conversations without pins and tags. */ }
    if (!disposed) renderDrawer();
  }
  function sessionTags(id) { return sessionMeta.tags?.[id] || []; }
  function isPinned(id) { return (sessionMeta.pinned || []).includes(id); }
  function allSessionTags() { return [...new Set(Object.values(sessionMeta.tags || {}).flat())].sort((first, second) => first.localeCompare(second, locale)); }

  // Today / yesterday / this week / earlier, by the last change.
  function sessionGroup(session) {
    if (isPinned(session.id)) return t("置顶");
    const when = new Date(session.updated_at || 0);
    if (Number.isNaN(when.getTime())) return t("更早");
    const start = new Date(); start.setHours(0, 0, 0, 0);
    const day = 24 * 60 * 60 * 1000;
    if (when >= start) return t("今天");
    if (when >= start.getTime() - day) return t("昨天");
    if (when >= start.getTime() - 6 * day) return t("过去 7 天");
    return t("更早");
  }

  function sheetButton(iconName, label, action, attribute = null) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "action-sheet-item";
    button.innerHTML = icon(iconName);
    button.append(label);
    if (attribute) button.setAttribute(attribute, sheetSession?.id || "");
    button.addEventListener("click", action);
    return button;
  }

  function openSessionSheet(session) {
    if (disposed || !session) return;
    sheetSession = session;
    haptic(14);
    const sheet = $("sessionSheet");
    $("sessionSheetTitle").textContent = session.title || t("未命名会话");
    $("sessionSheetStatus").textContent = "";
    $("sessionSheetTags").hidden = true;
    const pinned = isPinned(session.id);
    const running = [...backgroundTasks.values()].some(task => task.sessionId === session.id && !task.done);
    const archived = session.archived === true;
    const actions = [
      sheetButton("pin", pinned ? t("取消置顶") : t("置顶"), () => void pinSession(session, !pinned)),
      sheetButton("list-checks", t("标签"), () => showTagEditor(session)),
      sheetButton("file-text", t("导出为 Markdown"), (event) => void exportSession(session, "md", event.currentTarget)),
      sheetButton("download", t("导出为 PDF"), (event) => void exportSession(session, "pdf", event.currentTarget)),
      sheetButton("image-plus", t("导出为长图"), (event) => void exportSession(session, "image", event.currentTarget)),
      sheetButton("book-open", t("做成图文教程"), (event) => void chooseTutorialTask(session, event.currentTarget)),
      sheetButton(archived ? "archive-restore" : "archive", archived ? t("恢复") : t("归档"),
        () => { closeSessionSheet(); void setSessionArchived(session, !archived); }, archived ? "data-session-restore" : "data-session-archive"),
    ];
    actions[actions.length - 1].disabled = running;
    $("sessionSheetActions").replaceChildren(...actions);
    if (window.MobileMotion && sheet.hidden) window.MobileMotion.enter(sheet.querySelector(".action-sheet-panel"), { transform: "translateY(24px)" }, { spring: "snappy" });
    sheet.hidden = false;
  }

  function closeSessionSheet() {
    $("sessionSheet").hidden = true;
    sheetSession = null;
  }

  async function pinSession(session, pinned) {
    try {
      const value = await apiJson("/mobile/session-meta/pin", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: session.id, pinned }) });
      sessionMeta = { tags: value.tags || {}, pinned: value.pinned || [] };
      closeSessionSheet();
      renderDrawer();
    } catch (error) { $("sessionSheetStatus").textContent = error.message; }
  }

  function showTagEditor(session) {
    $("sessionSheetTags").hidden = false;
    const chosen = new Set(sessionTags(session.id));
    const render = () => {
      $("sessionTagChips").replaceChildren(...[...new Set([...allSessionTags(), ...chosen])].map((tag) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "memory-topic";
        chip.textContent = tag;
        chip.setAttribute("aria-pressed", String(chosen.has(tag)));
        chip.addEventListener("click", () => { if (chosen.has(tag)) chosen.delete(tag); else chosen.add(tag); void saveTags(); });
        return chip;
      }));
    };
    const saveTags = async () => {
      render();
      try {
        const value = await apiJson("/mobile/session-meta/tags", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: session.id, tags: [...chosen] }) });
        sessionMeta = { tags: value.tags || {}, pinned: value.pinned || [] };
        $("sessionSheetStatus").textContent = "";
        renderDrawer();
      } catch (error) { $("sessionSheetStatus").textContent = error.message; }
    };
    $("btnAddSessionTag").onclick = () => {
      const tag = $("sessionTagInput").value.trim();
      if (!tag) return;
      chosen.add(tag);
      $("sessionTagInput").value = "";
      void saveTags();
    };
    render();
    $("sessionTagInput").focus();
  }

  // Export: the engine writes the file into the conversation's workspace (exports/), then it is
  // shared like any task output; without the app (a browser) it downloads.
  async function exportSession(session, format, button) {
    const status = $("sessionSheetStatus");
    status.textContent = format === "md" ? t("正在导出...") : t("正在生成，长对话可能要几秒...");
    button.disabled = true;
    try {
      const result = await apiJson("/mobile/sessions/export", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: session.id, format, title: session.title || "" }) });
      const mime = format === "md" ? "text/markdown" : format === "pdf" ? "application/pdf" : "image/jpeg";
      for (const path of result.paths || []) {
        await artifactAction({ path, mime_type: mime, workspaceId: workspaceOfSession(session.id) }, "share", button, status, true);
      }
      if (!status.textContent || status.textContent === t("准备文件...")) status.textContent = t("已导出到工作区 exports 文件夹");
    } catch (error) {
      status.textContent = t("导出失败: {0}", error.message);
    } finally { button.disabled = false; }
  }

  // A picture guide from one of this conversation's phone tasks whose step pictures are still kept
  // (66-step-replay.js opens the editor).
  async function chooseTutorialTask(session, button) {
    const status = $("sessionSheetStatus");
    button.disabled = true;
    let tasks = [];
    try { tasks = (await apiJson(`/mobile/step-shots/tasks?session_id=${encodeURIComponent(session.id)}`)).tasks || []; }
    catch (error) { status.textContent = t("读取失败：{0}", error.message); return; }
    finally { button.disabled = false; }
    if (disposed || sheetSession !== session) return;
    if (!tasks.length) { status.textContent = t("这个对话里没有可用的手机操作截图（只保留最近 20 个任务、最多 7 天）"); return; }
    const open = (task) => { closeSessionSheet(); void openStepTutorial({ id: task.task_id, sessionId: session.id, prompt: task.prompt }); };
    if (tasks.length === 1) { open(tasks[0]); return; }
    status.textContent = t("选一次手机操作");
    $("sessionSheetActions").replaceChildren(...tasks.map((task) => sheetButton("book-open", t("{0} · {1} 步", task.prompt, task.steps), () => open(task))));
  }

  $("sessionSheet").addEventListener("click", (event) => { if (event.target === $("sessionSheet")) closeSessionSheet(); });
