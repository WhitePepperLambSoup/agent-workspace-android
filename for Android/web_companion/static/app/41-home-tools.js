
  // ---- Home-screen tools: an HTML page the agent made, kept in the app with its own shortcut -------
  // HomeTools.kt keeps the copy and opens it offline, away from the app (ToolActivity); a page
  // becomes one through the file action "home_tool". The Files page lists them at its top level.
  // Kept on a function, not a top-level let: syncFileControls (40-files.js) may run before this part.
  function homeToolsKept() { return homeToolsKept.tools || []; }

  function canMakeHomeTools() { return typeof bridge?.workspaceFileAction === "function" && typeof bridge?.getHomeTools === "function"; }

  function syncHomeToolsVisibility() {
    const section = $("homeToolsSection");
    if (section) section.hidden = !homeToolsKept().length || !!fileEditor || workspacePath !== "";
  }

  function renderHomeTools(value = null) {
    if (!canMakeHomeTools()) return;
    try { homeToolsKept.tools = (value || JSON.parse(bridge.getHomeTools())).tools || []; } catch { homeToolsKept.tools = []; }
    const list = $("homeToolsList");
    list.replaceChildren(...homeToolsKept().map((tool) => {
      const row = document.createElement("div");
      row.className = "home-tool-row";
      const open = document.createElement("button");
      open.type = "button";
      open.className = "home-tool-open";
      open.innerHTML = icon("app-window");
      const label = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = tool.name;
      const source = document.createElement("small");
      source.textContent = tool.source || "";
      label.append(name, source);
      open.append(label);
      open.addEventListener("click", () => homeToolAction(tool, "open"));
      const pin = actionButton("plus", t("再次添加到桌面"), "data-home-tool", "pin");
      pin.addEventListener("click", () => homeToolAction(tool, "pin"));
      const remove = actionButton("trash-2", t("删除小工具"), "data-home-tool", "delete");
      remove.addEventListener("click", () => {
        if (window.confirm(t("删除「{0}」？它存下的数据会清掉；桌面上的图标会变灰，长按可以移除。", tool.name))) homeToolAction(tool, "delete");
      });
      row.append(open, pin, remove);
      return row;
    }));
    syncHomeToolsVisibility();
  }

  function homeToolAction(tool, action) {
    let result;
    try { result = JSON.parse(bridge.homeToolAction(JSON.stringify({ id: tool.id, action }))); }
    catch { result = { ok: false }; }
    if (!result.ok) { pageStatus($("homeToolsStatus"), localizeError(result.error) || t("操作没有完成"), true); return; }
    pageStatus($("homeToolsStatus"), action === "pin" ? t("按系统提示把它放到桌面") : "");
    renderHomeTools(result);
  }

  // The result of a "home_tool" file action, from the event that ends it (50-usage-artifacts.js).
  function homeToolAdded(result) {
    renderHomeTools();
    return result.pinned === false
      ? t("已存为小工具「{0}」。这个桌面不能添加快捷方式，可在 文件 页最上方打开。", result.tool_name || "")
      : t("已存为小工具「{0}」，按系统提示放到桌面", result.tool_name || "");
  }
