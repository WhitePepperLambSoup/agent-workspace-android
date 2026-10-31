
  // ---- The campus (2.7) -------------------------------------------------------------------------
  // Shown in full, the studio can look elsewhere (the desktop app's campus, web_companion/studio/
  // places): by default it follows the agent to wherever its work is, the library while it searches
  // the knowledge base or the literature, the building site while it works on code or runs commands,
  // the front desk while it hands a task to a computer, its own room otherwise; any place can be
  // picked by hand. The places hold the phone's things: the knowledge bases, the workspace's files, the
  // scheduled tasks, the paired computers (there is no server room). A followed place must hold a
  // moment and stays a few seconds, so the view does not flick at every tool.
  const followStayMs = 5000;
  const followSettleMs = 1500;
  // How often a place asks again while it is shown; the workspace's files only when it opens and
  // after a task.
  const placeEvery = { campus: 15000, library: 6000, site: 10000, duty: 10000, desk: 5000 };
  const placeNeeds = { campus: ["knowledge", "schedules", "connections", "files"], library: ["knowledge"], site: ["files"], duty: ["schedules"], desk: ["connections"] };
  const placeLibraryTools = /^(knowledge_|paper_|read_paper|reference_library|check_references|export_references)/;
  const placeSiteTools = /^(apply_patch|run_terminal|start_service|stop_service|code_|find_)/;
  const placeEditTools = /^(write_file|append_file|apply_patch|copy_file|move_path|delete_path|create_)/;
  const placeSkipped = /^(node_modules|\.git|\.venv|venv|__pycache__|dist|out|build|target|\.next|coverage|\.mypy_cache|\.pytest_cache|\.ruff_cache)$/;
  let placeChoice = "follow";
  let followed = "studio";
  let followedSince = 0;
  let followTimer = 0;
  let placeScene = null;
  let placeShownName = null;
  let placeData = {};
  let placeTimer = 0;
  let placeSignature = "";
  let placeWasRunning = false;

  // The places' words, by the desktop app's keys (the scenes ask for them so).
  const placeWords = {
    "places.campus.title": () => t("园区"), "places.studio.title": () => t("工作室"), "places.library.title": () => t("图书馆"),
    "places.site.title": () => t("工地"), "places.duty.title": () => t("值班室"), "places.desk.title": () => t("前台"),
    "places.library.librarian.idle": () => t("空闲"), "places.library.librarian.searching": () => t("检索知识库"),
    "places.library.librarian.reading": () => t("看检索到的资料"), "places.library.librarian.adding": () => t("加入资料"),
    "places.library.librarian.papers": () => t("查文献"), "places.library.clerk": () => t("读入文档"),
    "places.library.reading": (v) => t("正在读入 {0} 份", v.count), "places.library.documents": (v) => t("{0} 份文档", v.count),
    "places.library.papers": () => t("文献库"), "places.library.paperCount": (v) => t("{0} 篇", v.count),
    "places.library.cart": () => t("待读入"), "places.library.failed": (v) => t("{0} 份读入失败", v.count),
    "places.library.empty": () => t("还没有知识库"), "places.library.off": () => t("知识库已关闭"),
    "places.site.worker.idle": () => t("空闲"), "places.site.worker.editing": () => t("改文件"),
    "places.site.worker.testing": () => t("运行命令"), "places.site.worker.reading": () => t("看文件"),
    "places.site.noGit": () => t("本机工作区"), "places.site.checking": () => "", "places.site.checksFailed": () => "",
    "places.site.changed": (v) => t("这个对话改过 {0} 个文件", v.count), "places.site.clean": () => t("这个对话没有改过文件"),
    "places.site.unpushed": () => "", "places.site.empty": () => t("工作区是空的"), "places.site.uncommitted": () => t("这个对话改过"),
    "places.duty.untitled": () => t("未命名任务"), "places.duty.state.running": () => t("运行中"), "places.duty.state.soon": () => t("即将开始"),
    "places.duty.state.idle": () => t("待命"), "places.duty.state.failed": () => t("上次失败"), "places.duty.state.done": () => t("刚完成"),
    "places.duty.state.off": () => t("已暂停"), "places.duty.empty": () => t("还没有定时任务"), "places.duty.more": (v) => t("还有 {0} 个", v.count),
    "places.desk.receptionist": () => t("前台"), "places.desk.error": () => t("出错了"), "places.desk.pairing": () => t("等待配对"),
    "places.desk.sending": (v) => t("{0} 个任务交给了电脑", v.count), "places.desk.open": () => t("接待中"), "places.desk.starting": () => t("接待中"),
    "places.desk.waiting": () => t("在线"), "places.desk.online": () => t("在线"), "places.desk.offline": () => t("离线"),
    "places.desk.noPhones": () => t("还没有配对的电脑"), "places.desk.closed": () => t("还没有配对的电脑"), "places.desk.closedHint": () => "",
    "places.desk.action.job": () => t("电脑发来请求"), "places.desk.action.approval": () => t("有审批等你回复"), "places.desk.action.waking": () => t("正在唤醒"),
  };
  function placeText(key, values = {}) { return placeWords[key]?.(values) ?? ""; }
  function placeTitle(place) { return place === "studio" ? t("工作室") : placeText(`places.${place}.title`); }
  function placeDescription(place) {
    return {
      campus: t("工作室和它周围的地方。哪里有事在做，哪里就亮着灯。"),
      library: t("知识库：一个知识库一个书架，AI 检索时会去书架取书。"),
      site: t("工作区：一个文件夹一个街区，一个文件一栋楼；这个对话改过的楼搭着脚手架。"),
      duty: t("定时任务：每个任务一位值班员，快到点时起身，运行时在工位上干活。"),
      desk: t("连接电脑：配对的电脑挂在访客牌上，在线的在等候区，有事的走到台前。"),
    }[place] || t("AI 和它叫来的专家、子任务在这里干活，动作跟着真实的任务走。");
  }

  // ---- Where the agent works ---------------------------------------------------------------------
  const placeCodeFiles = /\.(ts|tsx|js|jsx|mjs|cjs|py|rs|go|java|kt|c|h|cc|cpp|hpp|cs|rb|php|swift|scala|lua|sh|ps1|r|m|jl|vue|svelte|html|htm|css|scss|less|toml|ya?ml|ini|cfg|xml|json)$/i;
  function placeOfTool(tool, path = "") {
    if (placeLibraryTools.test(tool)) return "library";
    if (tool === "ask_computer") return "desk";
    if (placeSiteTools.test(tool)) return "site";
    // Writing or reading a file is building work when the file is code; documents are desk work.
    if (/^(write_file|read_file|append_file)$/.test(tool) && placeCodeFiles.test(path)) return "site";
    return "studio";
  }
  function placeTaskRunning() { return !!activeTask && !activeTask.done && activeTask.sessionId === currentSessionId; }
  function runningToolCard() {
    return placeTaskRunning() ? [...elements.timelineList.querySelectorAll('.message-card.tool[data-state="running"]')].pop() || null : null;
  }
  function cardPath(card) {
    const args = toolArguments.get(String(card?.dataset.toolId || "").replace(/^tool-/, ""));
    return typeof args?.path === "string" ? args.path : "";
  }
  function agentPlace() {
    const card = runningToolCard();
    return card ? placeOfTool(card.dataset.tool || "", cardPath(card)) : "studio";
  }

  /** Experts and sub-agents of the conversation whose tool now belongs to the place. */
  function placeVisitors(place) {
    const labels = activityLabels();
    const visitors = [];
    if (teamLive.sessionId === currentSessionId) {
      for (const [id, run] of teamLive.experts) {
        if (run.state !== "working" || !run.tool || placeOfTool(run.tool) !== place) continue;
        visitors.push({ id: `run-${run.session_id}`, name: expertName(id, run.name), stateLabel: labels[activityKind(run.tool)], look: lookFor(id), pick: `run:${run.session_id}` });
      }
    }
    if (helperLive.sessionId === currentSessionId) {
      for (const [sessionId, helper] of helperLive.helpers) {
        if (helper.done || !helper.tool || placeOfTool(helper.tool) !== place) continue;
        visitors.push({ id: `run-${sessionId}`, name: t("子任务 {0}", helper.index), stateLabel: labels[activityKind(helper.tool)], look: lookFor(`helper:${sessionId}`), pick: `run:${sessionId}` });
      }
    }
    return visitors;
  }

  // ---- What each place shows ----------------------------------------------------------------------
  function bookKind(name) {
    const lower = String(name || "").toLowerCase();
    if (/^https?:/.test(lower)) return "web";
    const suffix = lower.split(".").pop() || "";
    if (suffix === "pdf") return "pdf";
    if (["doc", "docx", "odt", "rtf", "wps"].includes(suffix)) return "word";
    if (["xls", "xlsx", "csv", "ods", "et"].includes(suffix)) return "sheet";
    if (["ppt", "pptx", "odp", "dps"].includes(suffix)) return "slides";
    if (["png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff"].includes(suffix)) return "image";
    if (["txt", "md", "markdown", "html", "htm", "json", "xml", "tex", "epub"].includes(suffix)) return "text";
    return "other";
  }
  function buildingKind(path) {
    const suffix = String(path).toLowerCase().split(".").pop() || "";
    if (["ts", "tsx", "js", "jsx", "mjs", "cjs", "py", "rs", "go", "java", "kt", "c", "h", "cc", "cpp", "hpp", "cs", "rb", "php", "swift", "scala", "lua", "sh", "ps1", "r", "m", "jl", "vue", "svelte"].includes(suffix)) return "code";
    if (["html", "htm", "css", "scss", "less"].includes(suffix)) return "web";
    if (["md", "txt", "rst", "tex", "bib", "docx", "doc", "pdf", "pptx", "odt"].includes(suffix)) return "doc";
    if (["json", "csv", "xlsx", "xls", "parquet", "sqlite", "db", "npy", "h5", "jsonl", "tsv"].includes(suffix)) return "data";
    if (["toml", "yaml", "yml", "ini", "cfg", "lock", "xml", "env", "gitignore", "editorconfig"].includes(suffix)) return "config";
    if (["png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "mp3", "mp4", "wav", "ttf", "woff", "woff2", "m4a", "amr"].includes(suffix)) return "asset";
    return "other";
  }

  /** The documents the conversation's latest knowledge search found, when its result reads as JSON. */
  function citedDocuments() {
    const card = [...elements.timelineList.querySelectorAll('.message-card.tool[data-tool="knowledge_search"][data-state="done"]')].pop();
    try {
      const value = JSON.parse(card?.querySelector("pre")?.textContent || "");
      return new Set((Array.isArray(value?.results) ? value.results : []).map((item) => item?.document_id || item?.documentId).filter(Boolean));
    } catch { return new Set(); }
  }

  function libraryModel() {
    const snapshot = placeData.knowledge;
    const documents = Array.isArray(snapshot?.documents) ? snapshot.documents : [];
    const collections = Array.isArray(snapshot?.collections) ? snapshot.collections : [];
    const cited = citedDocuments();
    const book = (document) => ({
      id: String(document.id), title: String(document.title || ""), kind: bookKind(document.origin_path || document.origin || document.title),
      size: Math.max(1, Number(document.passages) || 1), state: ["queued", "indexing", "ready", "failed"].includes(document.state) ? document.state : "ready",
      cited: cited.has(document.id),
    });
    const cases = [];
    collections.forEach((collection, index) => {
      if (index < 5) cases.push({ id: String(collection.id), name: String(collection.label || collection.name || collection.id), total: Number(collection.documents) || 0, books: [] });
      const target = cases[Math.min(index, 4)];
      if (index >= 5) target.total += Number(collection.documents) || 0;
      // The cited ones first, so they are on the shelves even in a full case; then the newest.
      const shelved = documents.filter((document) => document.collection_id === collection.id && document.state === "ready")
        .sort((a, b) => Number(cited.has(b.id)) - Number(cited.has(a.id)) || String(b.created_at || "").localeCompare(String(a.created_at || "")));
      target.books.push(...shelved.map(book));
    });
    for (const item of cases) item.books = item.books.slice(0, 72);
    const caseOf = (collectionId) => {
      const index = collections.findIndex((collection) => collection.id === collectionId);
      return index < 0 ? null : cases[Math.min(index, 4)]?.id ?? null;
    };
    const tool = runningToolCard()?.dataset.tool || "";
    const firstCited = documents.find((document) => cited.has(document.id));
    let librarian = { state: "idle", caseId: null, cited: cited.size };
    if (placeTaskRunning()) {
      if (tool === "knowledge_add") librarian = { ...librarian, state: "adding" };
      else if (/^knowledge_/.test(tool)) librarian = { ...librarian, state: "searching", caseId: caseOf(firstCited?.collection_id) ?? cases[0]?.id ?? null };
      else if (placeLibraryTools.test(tool)) librarian = { ...librarian, state: "papers" };
      else if (cited.size) librarian = { ...librarian, state: "reading", caseId: caseOf(firstCited?.collection_id) };
    }
    return {
      enabled: snapshot?.enabled !== false, cases, cart: documents.filter((document) => document.state !== "ready").slice(0, 10).map(book),
      papers: { total: 0, books: [] }, librarian, clerk: documents.some((document) => document.state === "queued" || document.state === "indexing"),
    };
  }

  /** Files written in this conversation (the phone has no Git: the scaffolding marks these). */
  function writtenPaths() {
    return new Set([...elements.timelineList.querySelectorAll('.message-card.tool[data-state="done"]')]
      .filter((card) => /^(write_file|append_file)$/.test(card.dataset.tool || "")).map(cardPath).filter(Boolean));
  }

  function siteModel() {
    const files = placeData.files || [];
    const written = writtenPaths();
    const card = runningToolCard();
    const tool = card?.dataset.tool || "";
    const editPath = placeEditTools.test(tool) ? cardPath(card) : "";
    const largest = Math.max(1, ...files.map((item) => item.size));
    const building = (item) => ({
      path: item.path, name: item.name, height: Math.min(1, Math.log2(1 + item.size) / Math.log2(1 + largest)), kind: buildingKind(item.path),
      changed: written.has(item.path), conflict: false, editing: !!editPath && item.path === editPath,
    });
    // A block per top-level folder, the root's own files as one; the busiest first.
    const groups = new Map();
    for (const item of files) {
      const name = item.path.includes("/") ? item.path.split("/")[0] : ".";
      groups.set(name, [...(groups.get(name) || []), item]);
    }
    const shown = [...groups.entries()].sort((a, b) => b[1].length - a[1].length).slice(0, 8);
    const share = Math.max(8, Math.floor(180 / Math.max(1, shown.length)));
    const districts = shown.map(([name, items]) => ({
      name, total: items.length,
      // Edited and written files always stand; then the largest.
      buildings: items.map(building).sort((a, b) => Number(b.editing) - Number(a.editing) || Number(b.changed) - Number(a.changed) || b.height - a.height).slice(0, share),
    }));
    const worker = !placeTaskRunning() ? "idle" : editPath ? "editing" : /^(run_|start_service|stop_service)/.test(tool) ? "testing"
      : /^(read_file|list_files|search_files|read_document|office_read)/.test(tool) ? "reading" : "idle";
    const folder = elements.workspaceTitleText.textContent || t("本机工作区");
    return {
      folder, districts, files: files.length, changed: [...written].filter((path) => files.some((item) => item.path === path)).length,
      branch: folder, ahead: 0, head: null, checks: { running: false, failed: [], passed: 0 }, worker: { state: worker, path: editPath || null },
    };
  }

  /** The workspace's files, folder by folder (the engine lists one at a time), as far as is sensible. */
  async function loadWorkspaceTree() {
    const found = [];
    const queue = [""];
    let asked = 0;
    while (queue.length && asked < 40 && found.length < 1200) {
      const folder = queue.shift();
      asked += 1;
      const data = await apiJson(scopedUrl(`/mobile/workspace/files?path=${encodeURIComponent(folder)}`, currentWorkspaceId));
      for (const item of Array.isArray(data.files) ? data.files : []) {
        if (typeof item?.path !== "string") continue;
        if (item.type === "directory") { if (!placeSkipped.test(item.name) && item.path.split("/").length < 6) queue.push(item.path); }
        else found.push({ path: item.path, name: String(item.name || item.path), size: Number(item.size) || 0 });
      }
    }
    return found;
  }

  function dutyModel(now) {
    const items = Array.isArray(placeData.schedules?.schedules) ? placeData.schedules.schedules : [];
    const failed = new Set(["failed", "missed", "interrupted", "skipped_locked", "mode_required"]);
    const officers = items.map((item) => {
      const next = item.enabled && item.next_due_at ? String(item.next_due_at) : null;
      const due = next ? Date.parse(next) - now : Infinity;
      const ran = item.last_run ? Date.parse(item.last_run) : NaN;
      const lately = Number.isFinite(ran) && now - ran < 3600000;
      // A run handed to the engine in the last minutes is taken as still going.
      const state = item.last_status === "dispatching" || (item.last_status === "submitted" && Number.isFinite(ran) && now - ran < 180000) ? "running"
        : !item.enabled ? "off" : due <= 90000 ? "soon"
          : lately && failed.has(item.last_status) ? "failed" : lately && ["completed", "submitted"].includes(item.last_status) ? "done" : "idle";
      return { id: String(item.schedule_id), title: String(item.title || ""), state, next };
    });
    const rank = { running: 0, soon: 1, failed: 2, done: 3, idle: 4, off: 5 };
    const ordered = [...officers].sort((a, b) => rank[a.state] - rank[b.state]);
    const upcoming = officers.filter((officer) => officer.next).map((officer) => ({ id: officer.id, title: officer.title, at: officer.next }))
      .sort((a, b) => a.at.localeCompare(b.at)).slice(0, 5);
    return { officers: ordered.slice(0, 8), more: Math.max(0, ordered.length - 8), upcoming };
  }

  function deskModel() {
    const hosts = Array.isArray(placeData.connections?.hosts) ? placeData.connections.hosts : [];
    const phones = hosts.map((host) => {
      const link = host.link || {};
      return {
        id: String(host.host_id), name: String(host.name || host.host_id), online: link.online === true,
        recent: link.jobs_waiting > 0 ? "job" : link.approvals > 0 ? "approval" : link.waking ? "waking" : null,
      };
    });
    const outgoing = elements.timelineList.querySelectorAll('.message-card.tool[data-tool="ask_computer"][data-state="running"]').length;
    return { enabled: true, running: true, error: false, pairing: false, phones, outgoing };
  }

  function campusModel(now) {
    const library = libraryModel();
    const site = siteModel();
    const duty = dutyModel(now);
    const desk = deskModel();
    const working = teamLive.sessionId === currentSessionId ? [...teamLive.experts.values()].filter((run) => run.state === "working").length : 0;
    const next = duty.upcoming[0];
    const nextTime = next ? new Date(next.at) : null;
    const online = desk.phones.filter((phone) => phone.online).length;
    const documents = Array.isArray(placeData.knowledge?.documents) ? placeData.knowledge.documents.length : 0;
    return {
      floors: 1,
      spots: {
        studio: {
          busy: placeTaskRunning(), alert: !!pendingApproval,
          detail: working ? t("{0} 位专家在工作", working) : placeTaskRunning() ? t("AI 在工作") : t("空闲"),
        },
        library: {
          busy: library.librarian.state !== "idle" || library.clerk, alert: library.cart.some((book) => book.state === "failed"),
          detail: !placeData.knowledge ? "" : library.clerk ? t("正在读入 {0} 份", library.cart.length) : t("{0} 个知识库，{1} 份文档", library.cases.length, documents),
        },
        site: {
          busy: site.worker.state !== "idle", alert: false,
          detail: !placeData.files ? "" : site.changed ? t("这个对话改过 {0} 个文件", site.changed) : t("{0} 个文件", site.files),
        },
        duty: {
          busy: duty.officers.some((officer) => officer.state === "running"), alert: duty.officers.some((officer) => officer.state === "failed"),
          detail: next && nextTime && !Number.isNaN(nextTime.getTime())
            ? t("下次：{0} {1}", nextTime.toLocaleString(locale, { weekday: "short", hour: "2-digit", minute: "2-digit" }), next.title)
            : !placeData.schedules ? "" : t("没有排定的运行"),
        },
        desk: {
          busy: online > 0 || desk.outgoing > 0, alert: false,
          detail: !placeData.connections ? "" : desk.phones.length ? t("{0}/{1} 台电脑在线", online, desk.phones.length) : t("还没有配对的电脑"),
        },
      },
    };
  }

  function placeModel(place, now) {
    return place === "campus" ? campusModel(now) : place === "library" ? libraryModel() : place === "site" ? siteModel()
      : place === "duty" ? dutyModel(now) : deskModel();
  }

  // ---- Showing a place ----------------------------------------------------------------------------
  function updatePlace() {
    if (!placeScene || !placeShownName) return;
    const place = placeShownName;
    // A place says nothing before its things have been read (an empty bookcase is no "no knowledge
    // base"); the campus's signs stay blank meanwhile.
    if (place !== "campus" && placeNeeds[place].some((need) => !placeData[need])) return;
    const model = placeModel(place, Date.now());
    const visitors = place === "library" || place === "site" ? placeVisitors(place) : [];
    const signature = JSON.stringify([model, visitors, locale]);
    if (signature === placeSignature) return;
    placeSignature = signature;
    placeScene.update({ model, t: placeText, lead: "AI", visitors });
    renderPlaceRoster(place, model);
  }

  /** The place's contents as a list below it: what the 3D shows, for screen readers and a tap. */
  function renderPlaceRoster(place, model) {
    const items = [];
    if (place === "campus") {
      for (const [id, spot] of Object.entries(model.spots)) items.push({ title: placeTitle(id), detail: spot.detail, pick: `place:${id}`, busy: spot.busy });
    } else if (place === "library") {
      for (const item of model.cases) items.push({ title: item.name, detail: t("{0} 份文档", item.total), pick: "route:knowledge", busy: model.librarian.caseId === item.id && model.librarian.state !== "idle" });
      if (!model.cases.length) items.push({ title: t("还没有知识库"), detail: "", pick: "route:knowledge" });
    } else if (place === "site") {
      const marked = model.districts.flatMap((district) => district.buildings.filter((building) => building.changed || building.editing));
      for (const building of marked.slice(0, 12)) items.push({ title: building.path, detail: building.editing ? t("改文件") : t("这个对话改过"), pick: `file:${building.path}`, busy: building.editing });
      if (!marked.length) items.push({ title: model.folder || t("本机工作区"), detail: t("这个对话没有改过文件"), pick: "route:workspace" });
    } else if (place === "duty") {
      for (const officer of model.officers) items.push({ title: officer.title || t("未命名任务"), detail: placeText(`places.duty.state.${officer.state}`), pick: "route:schedules", busy: officer.state === "running" });
      if (!model.officers.length) items.push({ title: t("还没有定时任务"), detail: "", pick: "route:schedules" });
    } else {
      for (const computer of model.phones) items.push({ title: computer.name, detail: computer.recent ? placeText(`places.desk.action.${computer.recent}`) : computer.online ? t("在线") : t("离线"), pick: "route:settings", busy: computer.online });
      if (!model.phones.length) items.push({ title: t("还没有配对的电脑"), detail: "", pick: "route:settings" });
    }
    $("studioRoster").replaceChildren(...items.map((item) => {
      const row = document.createElement("li");
      row.dataset.busy = String(!!item.busy);
      const button = document.createElement("button");
      button.type = "button";
      const name = document.createElement("strong");
      name.textContent = item.title;
      button.append(name);
      if (item.detail) {
        const detail = document.createElement("span");
        detail.textContent = item.detail;
        button.append(detail);
      }
      button.addEventListener("click", () => placePick(item.pick));
      row.append(button);
      return row;
    }));
  }

  /** A tap in a place: the agent goes back to the conversation, a building of the campus opens,
   * a thing with a page of its own opens it. */
  function placePick(id) {
    if (id === "agent") { closeStudio(); return; }
    if (id.startsWith("run:")) {
      if (openSession(id.slice(4))) closeStudio();
      else notice(t("任务进行中，结束后再打开"));
      return;
    }
    if (id.startsWith("place:")) {
      const next = id.slice(6);
      void (placeScene?.approach(id) ?? Promise.resolve()).then(() => choosePlace(next));
      return;
    }
    if (id.startsWith("file:")) {
      closeStudio();
      openMenu();
      if (setSettingsPage("files") !== false) void openWorkspaceFile(id.slice(5));
      return;
    }
    const page = { "route:knowledge": "btnKnowledgePage", "route:schedules": "btnSchedulesPage", "route:settings": "btnConnectionsPage", "route:changes": "btnFilesPage", "route:workspace": "btnFilesPage" }[id];
    if (!page) return;
    closeStudio();
    openMenu();
    $(page).click();
  }

  function renderPlaceSwitch() {
    for (const button of $("studioPlaces").querySelectorAll("[data-place]")) button.setAttribute("aria-checked", String(button.dataset.place === placeChoice));
    $("studioFollowLabel").textContent = t("跟随 AI · {0}", placeTitle(followed));
  }

  function choosePlace(choice) {
    window.clearTimeout(followTimer);
    followTimer = 0;
    placeChoice = choice;
    if (choice === "follow") { followed = agentPlace(); followedSince = Date.now(); }
    void showStudioPlace();
    // The row scrolls sideways on a narrow phone: the chosen one into sight.
    $("studioPlaces").querySelector(`[data-place="${choice}"]`)?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }

  function dropPlaceScene() {
    window.clearInterval(placeTimer);
    placeTimer = 0;
    placeScene?.dispose();
    placeScene = null;
    placeSignature = "";
    $("placeOverlay").replaceChildren();
    $("placeStage").dataset.ready = "false";
    $("placeHint").hidden = true;
  }

  /** The studio or the place now wanted, in the sheet: the studio's own scene (or the one behind the
   * conversation) stops drawing while a place is shown. */
  async function showStudioPlace() {
    const sheet = $("studioSheet");
    if (disposed || sheet.hidden) return;
    renderPlaceSwitch();
    const wanted = placeChoice === "follow" ? followed : placeChoice;
    const place = wanted === "studio" ? null : wanted;
    if (place === placeShownName) return;
    dropPlaceScene();
    placeShownName = place;
    $("studioTitle").textContent = place ? placeTitle(place) : t("工作室");
    $("studioDescription").textContent = placeDescription(place);
    $("studioStage").hidden = !!place;
    $("placeStage").hidden = !place;
    sheet.dataset.over = !place && studioViewing ? "backdrop" : "";
    studioScene?.setActive(!place);
    if (studioViewing) backdropScene?.setActive(!place);
    if (!place) {
      studioSignature = "";
      const cast = studioCast();
      studioShownCast = cast;
      renderStudioRoster(cast);
      refreshStudio();
      return;
    }
    $("studioRoster").replaceChildren();
    let studio;
    try { studio = await loadStudio(); }
    catch { $("studioUnsupported").hidden = false; return; }
    if (disposed || sheet.hidden || placeShownName !== place) return;
    try {
      placeScene = studio.createPlaceScene($("placeStage"), $("placeOverlay"), studioLook(), studio.places[place], { pick: placePick });
    } catch {
      $("placeHint").textContent = t("这台手机无法显示 3D 工作室（WebGL 不可用）。");
      $("placeHint").hidden = false;
      return;
    }
    placeScene.setPaused(studioPaused);
    $("placeStage").dataset.ready = "true";
    $("placeHint").textContent = place === "campus" ? t("点一栋楼进去看。") : t("拖动旋转，双指缩放，点东西打开对应的页面。");
    $("placeHint").hidden = false;
    updatePlace();
    void loadPlace(place, true);
    placeTimer = window.setInterval(() => void loadPlace(place, false), placeEvery[place]);
  }

  /** Asks the engine for what the place shows, one question at a time; a failure keeps what was there. */
  async function loadPlace(place, first) {
    for (const need of placeNeeds[place]) {
      if (disposed || placeShownName !== place) return;
      if (need === "files" && !first && placeData.files) continue;
      try {
        if (need === "knowledge") placeData.knowledge = await apiJson("/mobile/knowledge");
        else if (need === "schedules") placeData.schedules = await apiJson("/mobile/schedules");
        else if (need === "connections") placeData.connections = await apiJson("/mobile/connections");
        else placeData.files = await loadWorkspaceTree();
      } catch { /* the place keeps what it had */ }
      updatePlace();
    }
  }

  /** Task events and the like: the place shown follows, and the view follows the agent. */
  function refreshPlaces() {
    if (disposed || $("studioSheet").hidden) return;
    const running = placeTaskRunning();
    // A task that ended may have changed the workspace's files.
    if (placeWasRunning && !running && placeShownName && placeNeeds[placeShownName].includes("files")) {
      void loadWorkspaceTree().then((files) => { placeData.files = files; updatePlace(); }).catch(() => {});
    }
    placeWasRunning = running;
    const wanted = agentPlace();
    if (placeChoice === "follow" && wanted !== followed && !followTimer) {
      followTimer = window.setTimeout(() => {
        followTimer = 0;
        if (placeChoice !== "follow" || $("studioSheet").hidden) return;
        const now = agentPlace();
        if (now === followed) return;
        followed = now;
        followedSince = Date.now();
        void showStudioPlace();
      }, Math.max(followSettleMs, followStayMs - (Date.now() - followedSince)));
    }
    renderPlaceSwitch();
    updatePlace();
  }

  /** The studio sheet opens: following the agent from where it is. */
  function enterPlaces() {
    placeChoice = "follow";
    followed = agentPlace();
    followedSince = Date.now();
    placeWasRunning = placeTaskRunning();
    placeShownName = null;
    void showStudioPlace();
  }

  /** The studio sheet closes: the place goes, the studio's title and words come back. */
  function leavePlaces() {
    window.clearTimeout(followTimer);
    followTimer = 0;
    dropPlaceScene();
    placeShownName = null;
    placeChoice = "follow";
    $("studioTitle").textContent = t("工作室");
    $("studioDescription").textContent = placeDescription(null);
    $("studioStage").hidden = false;
    $("placeStage").hidden = true;
  }

  for (const button of $("studioPlaces").querySelectorAll("[data-place]")) {
    button.addEventListener("click", () => choosePlace(button.dataset.place));
  }
