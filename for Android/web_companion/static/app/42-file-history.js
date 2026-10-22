
  // ---- File history: earlier versions of workspace files (mobile_file_history) -----------------
  // Kept before the agent or you change a file. Listed for one file (from its preview) or for the
  // whole workspace (最近改动, deleted files included); a text version can be read, and any version
  // put back, which keeps what it replaces so that can be undone too.
  function fileHistoryOpen() { return $("fileHistoryPanel")?.hidden === false; }

  function fileHistorySource(source) {
    if (["delete_path"].includes(source)) return t("AI 删除前");
    if (source === "move_path") return t("AI 覆盖前");
    if (source === "edit") return t("你编辑前");
    if (source === "delete") return t("你删除前");
    if (source === "restore") return t("还原前");
    return t("AI 改动前");
  }

  async function openFileHistory(path = null) {
    if (fileSaving || !canLeaveFileEditor()) return;
    openFileHistory.path = path;
    openFileHistory.editor = path ? fileEditor : null;
    elements.workspaceFilesList.hidden = true;
    elements.fileEditorPanel.hidden = true;
    $("homeToolsSection").hidden = true;
    $("fileHistoryPanel").hidden = false;
    $("fileHistoryTitle").textContent = path ? t("「{0}」的历史版本", path.split("/").pop()) : t("最近改动");
    $("fileHistoryList").replaceChildren();
    pageStatus($("fileHistoryStatus"), t("加载中..."));
    const generation = ++filesGeneration;
    try {
      const data = await apiJson(scopedUrl(`/mobile/file-history${path ? `?path=${encodeURIComponent(path)}` : ""}`, currentWorkspaceId));
      if (disposed || generation !== filesGeneration || !fileHistoryOpen()) return;
      const versions = Array.isArray(data.versions) ? data.versions : [];
      $("fileHistoryList").replaceChildren(...versions.map((version) => fileHistoryRow(version, !path, data.current_sha256)));
      pageStatus($("fileHistoryStatus"), versions.length ? ""
        : path ? t("这个文件还没有更早的版本。AI 或你改动它之前，会先存一份。") : t("最近没有改动。AI 或你改动、删除文件之前，会先存一份旧内容，保留 30 天。"));
    } catch (error) {
      if (!disposed && generation === filesGeneration) pageStatus($("fileHistoryStatus"), t("读取历史失败：{0}", localizeError(error.message)), true);
    }
  }

  function fileHistoryRow(version, showPath, currentSha) {
    const row = document.createElement("div");
    row.className = "file-history-row";
    const body = document.createElement("div");
    body.className = "file-history-body";
    const title = document.createElement("strong");
    title.textContent = showPath ? version.path : new Date(version.at).toLocaleString(locale);
    const meta = document.createElement("small");
    const parts = [showPath ? new Date(version.at).toLocaleString(locale) : "", fileHistorySource(version.source), formatBytes(version.size)];
    if (version.exists === false) parts.push(t("文件已不在"));
    else if (currentSha && version.sha256 === currentSha) parts.push(t("和现在相同"));
    meta.textContent = parts.filter(Boolean).join(" · ");
    body.append(title, meta);
    const actions = document.createElement("div");
    actions.className = "file-history-actions";
    const view = document.createElement("button");
    view.type = "button";
    view.className = "button-secondary";
    view.textContent = t("查看");
    const restore = document.createElement("button");
    restore.type = "button";
    restore.className = "button-secondary";
    restore.textContent = t("还原");
    const shown = document.createElement("pre");
    shown.className = "file-history-text";
    shown.hidden = true;
    view.addEventListener("click", async () => {
      if (!shown.hidden) { shown.hidden = true; return; }
      try {
        const data = await apiJson(scopedUrl(`/mobile/file-history/content?id=${encodeURIComponent(version.id)}`, currentWorkspaceId));
        shown.textContent = typeof data.text === "string" ? data.text : t("这个版本不是文本，或者太大，不能在这里显示；还原后可以打开。");
        shown.hidden = false;
      } catch (error) { pageStatus($("fileHistoryStatus"), localizeError(error.message), true); }
    });
    restore.addEventListener("click", async () => {
      const when = new Date(version.at).toLocaleString(locale);
      if (!window.confirm(t("把「{0}」还原到 {1} 的版本？现在的内容会先存一份，还能再还原回来。", version.path, when))) return;
      restore.disabled = true;
      try {
        await apiJson("/mobile/workspace/restore", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: version.id, ...(currentWorkspaceId ? { workspace_id: currentWorkspaceId } : {}) }) });
        await openFileHistory(openFileHistory.path);
        pageStatus($("fileHistoryStatus"), t("已还原「{0}」", version.path));
      } catch (error) {
        pageStatus($("fileHistoryStatus"), t("还原失败：{0}", localizeError(error.message)), true);
      } finally { restore.disabled = false; }
    });
    actions.append(view, restore);
    row.append(body, actions, shown);
    return row;
  }

  // Back to where the history was opened from: the file (read again: it may have been restored) or the list.
  function closeFileHistory() {
    $("fileHistoryPanel").hidden = true;
    const path = openFileHistory.path;
    openFileHistory.path = null;
    if (path) void openWorkspaceFile(path);
    else void loadWorkspaceFiles(workspacePath);
  }

  $("btnFileHistory")?.addEventListener("click", () => void openFileHistory());
  $("btnFileVersions")?.addEventListener("click", () => { if (fileEditor?.path) void openFileHistory(fileEditor.path); });
  $("btnFileHistoryClose")?.addEventListener("click", closeFileHistory);
