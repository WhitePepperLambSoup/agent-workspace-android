
  // ---- @ files and / commands in the composer (2.0) ----------------------------------------
  // "@" at the start of a word lists the workspace (folders open in place) and inserts @path;
  // "/" at the very start lists quick tasks and saved workflows.
  let mentionState = null;
  let workflowCache = { at: 0, items: [] };
  let shortcutMenuCache = { at: 0, items: [] };

  function mentionToken() {
    const input = elements.promptInput;
    const caret = input.selectionStart ?? input.value.length;
    const before = input.value.slice(0, caret);
    const file = before.match(/(^|\s)@([^\s@]*)$/);
    if (file) return { kind: "file", start: caret - file[2].length - 1, end: caret, query: file[2] };
    const command = before.match(/^\/([^\s/]*)$/);
    if (command) return { kind: "command", start: 0, end: caret, query: command[1] };
    return null;
  }

  function closeMentions() {
    mentionState = null;
    $("mentionPopup").hidden = true;
    $("mentionPopup").replaceChildren();
  }

  function replaceToken(token, text) {
    const input = elements.promptInput;
    input.value = input.value.slice(0, token.start) + text + input.value.slice(token.end);
    const caret = token.start + text.length;
    input.setSelectionRange?.(caret, caret);
    input.dispatchEvent(new Event("input"));
    input.focus();
  }

  function mentionRow(iconName, title, detail, choose) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "mention-row";
    row.setAttribute("role", "option");
    row.innerHTML = icon(iconName);
    const text = document.createElement("span");
    const name = document.createElement("strong");
    name.textContent = title;
    text.append(name);
    if (detail) { const small = document.createElement("small"); small.textContent = detail; text.append(small); }
    row.append(text);
    // pointerdown keeps the keyboard and the caret where they are.
    row.addEventListener("pointerdown", (event) => event.preventDefault());
    row.addEventListener("click", choose);
    return row;
  }

  async function workflowItems() {
    if (Date.now() - workflowCache.at < 30000) return workflowCache.items;
    try { workflowCache = { at: Date.now(), items: (await apiJson("/mobile/workflows")).workflows || [] }; }
    catch { workflowCache = { at: Date.now(), items: [] }; }
    return workflowCache.items;
  }

  async function showMentions() {
    const token = mentionToken();
    if (!token) { closeMentions(); return; }
    const state = { token };
    mentionState = state;
    const rows = [];
    const query = token.query.toLowerCase();
    if (token.kind === "file") {
      const slash = token.query.lastIndexOf("/");
      const folder = slash >= 0 ? token.query.slice(0, slash) : "";
      const wanted = (slash >= 0 ? token.query.slice(slash + 1) : token.query).toLowerCase();
      let files = [];
      try { files = (await apiJson(scopedUrl(`/mobile/workspace/files?path=${encodeURIComponent(folder)}`, currentWorkspaceId))).files || []; }
      catch { files = []; }
      if (disposed || mentionState !== state) return;
      for (const file of files.filter((item) => String(item.name || "").toLowerCase().includes(wanted)).slice(0, 30)) {
        const directory = file.type === "directory";
        rows.push(mentionRow(directory ? "folder-open" : "file-text", file.name, directory ? t("文件夹") : formatBytes(file.size), () => {
          if (directory) { replaceToken(token, `@${file.path}/`); void showMentions(); return; }
          replaceToken(token, `@${file.path} `);
          closeMentions();
        }));
      }
      if (!rows.length) rows.push(mentionRow("file-text", t("没有匹配的文件"), folder ? t("在 {0} 里", folder) : t("当前工作区"), closeMentions));
    } else {
      for (const task of quickTasks.filter((item) => `${item.title} ${item.detail}`.toLowerCase().includes(query))) {
        rows.push(mentionRow(task.icon || "sparkles", task.title, task.detail || t("快捷任务"), () => {
          replaceToken(token, task.prompt);
          closeMentions();
          if (task.send) void sendPrompt();
        }));
      }
      const flows = await workflowItems();
      if (mentionState !== state) return;
      for (const flow of flows.filter((item) => String(item.name || "").toLowerCase().includes(query)).slice(0, 20)) {
        const replay = flow.schema_version === 2;
        rows.push(mentionRow("list-checks", flow.name, replay ? t("可复用流程 · 直接运行") : t("可复用流程"), async () => {
          closeMentions();
          if (!replay) { replaceToken(token, flow.prompt || flow.name); return; }
          replaceToken(token, "");
          if (activeTask) { notice(t("请等待当前任务结束")); return; }
          try {
            await apiJson("/mobile/workflows/run", { method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ workflow_id: flow.workflow_id, session_id: currentSessionId, model: settings.model, reasoning_effort: settings.reasoning_effort }) });
            notice(t("流程已提交"), "info");
            void refreshCurrentSessionTask();
          } catch (error) { notice(error.message); }
        }));
      }
      if (Date.now() - shortcutMenuCache.at > 30000) {
        try { shortcutMenuCache = { at: Date.now(), items: (await apiJson("/mobile/shortcuts")).shortcuts || [] }; }
        catch { shortcutMenuCache = { at: Date.now(), items: [] }; }
        if (mentionState !== state) return;
      }
      for (const shortcut of shortcutMenuCache.items.filter((item) => String(item.name || "").toLowerCase().includes(query)).slice(0, 20)) {
        rows.push(mentionRow("zap", shortcut.name, t("快捷操作 · 不用 AI 直接做"), async () => {
          replaceToken(token, "");
          closeMentions();
          try { await runShortcut(shortcut); notice(t("正在运行{0}…", shortcutQuote(shortcut.name)), "info"); }
          catch (error) { notice(error.message); }
        }));
      }
      if (!rows.length) rows.push(mentionRow("sparkles", t("没有匹配的快捷任务或流程"), t("在菜单里可以添加快捷任务和流程"), closeMentions));
    }
    if (mentionState !== state) return;
    $("mentionPopup").replaceChildren(...rows);
    $("mentionPopup").hidden = false;
  }

  elements.promptInput.addEventListener("input", () => { if (mentionToken()) void showMentions(); else if (mentionState) closeMentions(); });
  elements.promptInput.addEventListener("keydown", (event) => { if (event.key === "Escape" && mentionState) { event.preventDefault(); closeMentions(); } });
  elements.promptInput.addEventListener("blur", () => window.setTimeout(() => { if (document.activeElement !== elements.promptInput) closeMentions(); }, 150));
