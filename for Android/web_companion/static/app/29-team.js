
  // ---- Expert team (2.6) ------------------------------------------------------------------------
  // The conversation's agent leads a few experts (core.experts, mobile_subagents): the composer chip
  // turns the team on for the next messages, the team page says how it is made up, the timeline
  // shows who works on what, and the studio shows them at work in a small 3D office.
  const teamKey = "agent-mobile-team-v1";
  const teamMax = 4;
  const teamDefault = Object.freeze({ on: false, mode: "auto", members: ["researcher", "analyst", "critic"], custom: [], review: true, knowledgeMode: "shared", knowledge: {} });
  const expertIdPattern = /^[a-z0-9][a-z0-9_-]{0,31}$/;
  let expertCatalog = null;
  let expertCatalogLoading = null;
  let teamSettings = normalizeTeam(readStorage(teamKey, null));

  function validCustomExpert(item) {
    return !!item && typeof item === "object" && typeof item.id === "string" && expertIdPattern.test(item.id) && item.id.startsWith("custom-")
      && typeof item.name === "string" && item.name.trim().length > 0 && item.name.trim().length <= 24
      && typeof item.brief === "string" && item.brief.trim().length > 0 && item.brief.length <= 1200;
  }

  function normalizeTeam(value) {
    if (!value || typeof value !== "object") return { ...teamDefault, members: [...teamDefault.members] };
    const custom = Array.isArray(value.custom) ? value.custom.filter(validCustomExpert).slice(0, 12) : [];
    const members = Array.isArray(value.members)
      ? [...new Set(value.members.filter((id) => typeof id === "string" && expertIdPattern.test(id)))].slice(0, teamMax)
      : [...teamDefault.members];
    // Which knowledge base an expert searches, when the user gave them one (by expert id).
    const knowledge = {};
    if (value.knowledge && typeof value.knowledge === "object") {
      for (const [id, base] of Object.entries(value.knowledge).slice(0, 32)) {
        if (expertIdPattern.test(id) && typeof base === "string" && base && base.length <= 80) knowledge[id] = base;
      }
    }
    return {
      on: value.on === true, mode: value.mode === "fixed" ? "fixed" : "auto", members: members.length ? members : [...teamDefault.members], custom,
      review: value.review !== false, knowledgeMode: value.knowledgeMode === "separate" ? "separate" : "shared", knowledge,
    };
  }

  function saveTeam(next) {
    teamSettings = normalizeTeam(next);
    writeStorage(teamKey, teamSettings);
    syncTeamChip();
    if (settingsPage === "team") renderTeamPage();
  }

  // The library's names in the app's language (English for any it lacks).
  function catalogLocale() { return ["zh-CN", "zh-TW", "ja-JP", "ko-KR"].includes(locale) ? locale : "en-US"; }

  function loadExpertCatalog() {
    if (expertCatalog) return Promise.resolve(expertCatalog);
    if (!expertCatalogLoading) {
      expertCatalogLoading = apiJson("/mobile/experts").then((value) => {
        const byId = new Map();
        for (const domain of value.domains || []) for (const expert of domain.experts || []) byId.set(expert.id, { ...expert, domain });
        expertCatalog = { domains: value.domains || [], byId, max: Number(value.max_experts) || teamMax };
        return expertCatalog;
      }).finally(() => { expertCatalogLoading = null; });
    }
    return expertCatalogLoading;
  }

  function expertName(id, fallback = "") {
    const custom = teamSettings.custom.find((item) => item.id === id);
    if (custom) return custom.name;
    const item = expertCatalog?.byId.get(id);
    return item ? item.names[catalogLocale()] || item.names["en-US"] || id : fallback || id || t("专家");
  }
  function expertSummary(id) {
    const item = expertCatalog?.byId.get(id);
    return item ? item.summaries[catalogLocale()] || item.summaries["en-US"] || "" : teamSettings.custom.find((entry) => entry.id === id)?.brief || "";
  }
  function domainName(domain) { return domain.names[catalogLocale()] || domain.names["en-US"] || domain.id; }
  function phaseLabel(phase) { return phase === "review" ? t("审阅成稿") : t("分头研究"); }

  /** What a task sends for its team: "auto", or the fixed members (custom ones with their brief). */
  function teamPayload() {
    if (teamSettings.mode === "auto") return "auto";
    const seen = new Set();
    return teamSettings.members.flatMap((id) => {
      const custom = teamSettings.custom.find((item) => item.id === id);
      const member = custom ? { id, name: custom.name.trim(), brief: custom.brief.trim() } : { id, name: expertName(id).slice(0, 24) };
      const key = member.name.toLowerCase();
      if (seen.has(key)) return [];
      seen.add(key);
      return [member];
    });
  }
  /** The team fields of a task request: none when the team is off or the answer stays on the phone. */
  function teamRequest(onDevice) {
    if (!teamSettings.on || onDevice || isLocalModel()) return {};
    const team = teamPayload();
    if (team !== "auto" && !team.length) return {};
    const separate = teamSettings.knowledgeMode === "separate" && Object.keys(teamSettings.knowledge).length > 0;
    return { team, team_review: teamSettings.review, ...(separate ? { team_knowledge: { ...teamSettings.knowledge } } : {}) };
  }

  function syncTeamChip() {
    const chip = $("btnTeamChip");
    chip.hidden = elderOn();
    chip.setAttribute("aria-pressed", String(teamSettings.on));
    chip.classList.toggle("active", teamSettings.on);
  }

  $("btnTeamChip").addEventListener("click", () => {
    if (!teamSettings.on && isLocalModel()) { notice(t("专家团需要云端模型：本机模型要跑三到五轮，太慢。"), "info"); return; }
    haptic(14);
    saveTeam({ ...teamSettings, on: !teamSettings.on });
    notice(teamSettings.on ? t("专家团已开启：AI 先把问题分给几位专家，再汇总回答。比普通回答慢，也更费 Token。") : "", "info");
    if (teamSettings.on) void loadExpertCatalog().catch(() => {});
  });

  /** "Ask the expert team" in the share menu: a fresh conversation (the open one while it is empty)
   * takes the shared text and files, and the team is turned on for the message, which the user still
   * sends. Without the share's batch the share waits in the attachment inbox as any share. */
  function useExpertTeam(batch = null) {
    if (disposed) return false;
    if (isLocalModel()) { notice(t("专家团需要云端模型：本机模型要跑三到五轮，太慢。"), "info"); return true; }
    const shared = typeof batch === "string" && batch.length > 0 && batch.length <= 64;
    if (shared && !quickAsk({ mode: "text", share_batch: batch })) return false;
    if (!teamSettings.on) saveTeam({ ...teamSettings, on: true });
    quickShareTeam = shared;
    if (!shared) notice(t("这次由专家团回答：看一下问题和附件，点发送。"), "info");
    void loadExpertCatalog().catch(() => {});
    return true;
  }

  // ---- The team page --------------------------------------------------------------------------
  async function openTeamPage() {
    knowledgeBaseNames = null;
    setSettingsPage("team");
    renderTeamPage();
    try { await loadExpertCatalog(); } catch (error) { pageStatus($("teamStatus"), error.message, true); return; }
    if (!disposed && settingsPage === "team") renderTeamPage();
  }

  function renderTeamPage() {
    $("teamOnToggle").checked = teamSettings.on;
    $("teamReviewToggle").checked = teamSettings.review;
    $("teamModeSelect").value = teamSettings.mode;
    const fixed = teamSettings.mode === "fixed";
    $("teamFixedSection").hidden = !fixed;
    const experts = expertCatalog ? expertCatalog.byId.size : 0;
    $("teamModeHint").textContent = fixed
      ? t("每次都用下面选的专家，最多 {0} 位。", teamMax)
      : t("队长按问题从专家库里挑一到四位最对口的专家，比如劳动纠纷会找劳动法律师，而不是泛泛的法务。") + (experts ? t("专家库：{0} 个领域，{1} 位专家。", expertCatalog.domains.length, experts) : "");
    renderTeamMembers();
    renderTeamLibrary();
    renderCustomExperts();
    renderTeamKnowledge();
  }

  // Knowledge bases (Knowledge page) by id, for the experts given one of their own.
  let knowledgeBaseNames = null;
  async function loadKnowledgeBases() {
    try {
      const value = await apiJson("/mobile/knowledge");
      knowledgeBaseNames = new Map((value.collections || []).map((item) => [item.id, item.label || item.name || item.id]));
    } catch { knowledgeBaseNames = new Map(); }
    if (!disposed && settingsPage === "team") renderTeamKnowledge();
  }

  function renderTeamKnowledge() {
    const separate = teamSettings.knowledgeMode === "separate";
    $("teamKnowledgeMode").value = teamSettings.knowledgeMode;
    $("teamKnowledgeSection").hidden = !separate;
    if (!separate) return;
    if (!knowledgeBaseNames) { void loadKnowledgeBases(); return; }
    const list = $("teamKnowledgeList");
    list.replaceChildren();
    for (const [id, base] of Object.entries(teamSettings.knowledge)) {
      const row = document.createElement("div");
      row.className = "management-row";
      const text = document.createElement("span");
      text.textContent = t("{0} → {1}", expertName(id), knowledgeBaseNames.get(base) || t("已删除的知识库"));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "icon-button";
      remove.setAttribute("aria-label", t("取消 {0} 的指定", expertName(id)));
      remove.innerHTML = icon("x");
      remove.addEventListener("click", () => {
        const knowledge = { ...teamSettings.knowledge };
        delete knowledge[id];
        saveTeam({ ...teamSettings, knowledge });
      });
      row.append(text, remove);
      list.append(row);
    }
    // The team's own members first (fixed team), then the user's experts, then the library by field.
    const expertSelect = $("teamKnowledgeExpert");
    const chosen = expertSelect.value;
    expertSelect.replaceChildren();
    const option = (id) => { const item = document.createElement("option"); item.value = id; item.textContent = expertName(id); return item; };
    const group = (label, ids) => {
      if (!ids.length) return;
      const element = document.createElement("optgroup");
      element.label = label;
      element.append(...ids.map(option));
      expertSelect.append(element);
    };
    if (teamSettings.mode === "fixed") group(t("成员"), teamSettings.members);
    group(t("我的专家"), teamSettings.custom.map((item) => item.id).filter((id) => teamSettings.mode !== "fixed" || !teamSettings.members.includes(id)));
    for (const domain of expertCatalog?.domains || []) {
      group(domainName(domain), domain.experts.map((expert) => expert.id).filter((id) => teamSettings.mode !== "fixed" || !teamSettings.members.includes(id)));
    }
    if (chosen) expertSelect.value = chosen;
    const baseSelect = $("teamKnowledgeBase");
    const base = baseSelect.value;
    baseSelect.replaceChildren(...[...knowledgeBaseNames].map(([id, name]) => { const item = document.createElement("option"); item.value = id; item.textContent = name; return item; }));
    if (base) baseSelect.value = base;
    $("btnAddTeamKnowledge").disabled = !knowledgeBaseNames.size;
    if (!knowledgeBaseNames.size) pageStatus($("teamStatus"), t("还没有知识库：先在「知识库」页添加文档。"));
  }

  $("teamKnowledgeMode").addEventListener("change", () => saveTeam({ ...teamSettings, knowledgeMode: $("teamKnowledgeMode").value }));
  $("btnAddTeamKnowledge").addEventListener("click", () => {
    const id = $("teamKnowledgeExpert").value;
    const base = $("teamKnowledgeBase").value;
    if (!id || !base) return;
    saveTeam({ ...teamSettings, knowledge: { ...teamSettings.knowledge, [id]: base } });
    pageStatus($("teamStatus"), t("{0} 以后只查「{1}」", expertName(id), knowledgeBaseNames?.get(base) || base));
  });

  function renderTeamMembers() {
    const box = $("teamMembers");
    box.replaceChildren();
    for (const id of teamSettings.members) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "team-member";
      chip.style.setProperty("--swatch", lookFor(id).shirt);
      chip.setAttribute("aria-label", t("从成员里移除 {0}", expertName(id)));
      const swatch = document.createElement("span");
      swatch.className = "team-swatch";
      const name = document.createElement("span");
      name.textContent = expertName(id);
      chip.append(swatch, name);
      chip.insertAdjacentHTML("beforeend", icon("x"));
      chip.addEventListener("click", () => {
        if (teamSettings.members.length <= 1) { pageStatus($("teamStatus"), t("至少要留一位专家。")); return; }
        saveTeam({ ...teamSettings, members: teamSettings.members.filter((item) => item !== id) });
      });
      box.append(chip);
    }
  }

  function toggleMember(id) {
    const members = teamSettings.members;
    if (members.includes(id)) {
      if (members.length <= 1) { pageStatus($("teamStatus"), t("至少要留一位专家。")); return; }
      saveTeam({ ...teamSettings, members: members.filter((item) => item !== id) });
    } else if (members.length >= teamMax) {
      pageStatus($("teamStatus"), t("最多 {0} 位专家同时工作，先移除一位。", teamMax));
    } else {
      pageStatus($("teamStatus"), "");
      saveTeam({ ...teamSettings, members: [...members, id] });
    }
  }

  function libraryRow(id, title, summary) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "team-expert";
    row.dataset.expert = id;
    row.setAttribute("aria-pressed", String(teamSettings.members.includes(id)));
    row.style.setProperty("--swatch", lookFor(id).shirt);
    const swatch = document.createElement("span");
    swatch.className = "team-swatch";
    const text = document.createElement("span");
    const name = document.createElement("strong");
    name.textContent = title;
    const small = document.createElement("small");
    small.textContent = summary;
    text.append(name, small);
    row.append(swatch, text);
    row.addEventListener("click", () => toggleMember(id));
    return row;
  }

  function renderTeamLibrary() {
    const box = $("teamLibrary");
    box.replaceChildren();
    if (teamSettings.mode !== "fixed") return;
    const query = $("teamSearch").value.trim().toLowerCase();
    const matches = (...texts) => !query || texts.some((text) => String(text || "").toLowerCase().includes(query));
    const groups = [];
    if (teamSettings.custom.length) groups.push({ title: t("我的专家"), rows: teamSettings.custom.filter((item) => matches(item.name, item.brief)).map((item) => [item.id, item.name, item.brief]) });
    for (const domain of expertCatalog?.domains || []) {
      groups.push({
        title: domainName(domain),
        rows: domain.experts
          .filter((expert) => matches(domainName(domain), expert.id, ...Object.values(expert.names), ...Object.values(expert.summaries)))
          .map((expert) => [expert.id, expertName(expert.id), expertSummary(expert.id)]),
      });
    }
    for (const group of groups) {
      if (!group.rows.length) continue;
      const heading = document.createElement("h4");
      heading.className = "team-domain";
      heading.textContent = group.title;
      box.append(heading, ...group.rows.map(([id, title, summary]) => libraryRow(id, title, summary)));
    }
    if (!box.children.length) {
      const empty = document.createElement("p");
      empty.className = "setting-hint";
      empty.textContent = expertCatalog ? t("没有找到这样的专家。") : t("正在读取专家库...");
      box.append(empty);
    }
  }

  function renderCustomExperts() {
    const list = $("teamCustomList");
    list.replaceChildren();
    for (const item of teamSettings.custom) {
      const row = document.createElement("div");
      row.className = "management-row";
      const text = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = item.name;
      const brief = document.createElement("small");
      brief.textContent = item.brief;
      text.append(name, brief);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "icon-button";
      remove.setAttribute("aria-label", t("删除 {0}", item.name));
      remove.innerHTML = icon("trash-2");
      remove.addEventListener("click", () => {
        const members = teamSettings.members.filter((id) => id !== item.id);
        saveTeam({ ...teamSettings, custom: teamSettings.custom.filter((entry) => entry.id !== item.id), members: members.length ? members : [...teamDefault.members] });
      });
      row.append(text, remove);
      list.append(row);
    }
  }

  $("teamOnToggle").addEventListener("change", () => {
    if ($("teamOnToggle").checked && isLocalModel()) {
      $("teamOnToggle").checked = false;
      pageStatus($("teamStatus"), t("专家团需要云端模型：本机模型要跑三到五轮，太慢。"));
      return;
    }
    saveTeam({ ...teamSettings, on: $("teamOnToggle").checked });
  });
  $("teamReviewToggle").addEventListener("change", () => saveTeam({ ...teamSettings, review: $("teamReviewToggle").checked }));
  $("teamModeSelect").addEventListener("change", () => saveTeam({ ...teamSettings, mode: $("teamModeSelect").value }));
  $("teamSearch").addEventListener("input", renderTeamLibrary);
  $("btnAddCustomExpert").addEventListener("click", () => {
    const name = $("teamCustomName").value.trim().replace(/\s+/g, " ");
    const brief = $("teamCustomBrief").value.trim();
    if (!name || !brief) { pageStatus($("teamStatus"), t("名称和负责什么都要填写。"), true); return; }
    const taken = [...teamSettings.custom.map((item) => item.name), ...(expertCatalog ? [...expertCatalog.byId.keys()].map((id) => expertName(id)) : [])];
    if (taken.some((item) => item.toLowerCase() === name.toLowerCase())) { pageStatus($("teamStatus"), t("已有同名的专家。"), true); return; }
    if (teamSettings.custom.length >= 12) { pageStatus($("teamStatus"), t("最多 12 位自定义专家。"), true); return; }
    let index = teamSettings.custom.length + 1;
    while (teamSettings.custom.some((item) => item.id === `custom-${index}`)) index += 1;
    const id = `custom-${index}`;
    const members = teamSettings.mode === "fixed" && teamSettings.members.length < teamMax ? [...teamSettings.members, id] : teamSettings.members;
    saveTeam({ ...teamSettings, custom: [...teamSettings.custom, { id, name: name.slice(0, 24), brief: brief.slice(0, 1200) }], members });
    $("teamCustomName").value = "";
    $("teamCustomBrief").value = "";
    pageStatus($("teamStatus"), t("已添加 {0}", name));
  });
  $("btnTeamPage").addEventListener("click", () => { void openTeamPage(); });
  $("btnOpenStudio").addEventListener("click", () => openStudio());

  // ---- The experts of the task at work ---------------------------------------------------------
  // Helper conversations of expert runs (task.team.expert): who, which round, how it went, and the
  // tool they use now (task.subagent.step).
  const expertRuns = new Map();
  const teamLive = { taskId: null, sessionId: null, running: false, experts: new Map() };

  function noteTeamTask(task) {
    if (teamLive.taskId === task.id && teamLive.running) return;
    teamLive.taskId = task.id;
    teamLive.sessionId = task.sessionId;
    teamLive.running = true;
    teamLive.experts = new Map();
    refreshStudio();
  }

  function noteExpert(task, payload) {
    if (!payload?.session_id || !payload.expert) return;
    const run = { ...(expertRuns.get(payload.session_id) || {}), ...payload };
    expertRuns.set(payload.session_id, run);
    if (expertRuns.size > 200) expertRuns.delete(expertRuns.keys().next().value);
    if (teamLive.taskId !== task.id) noteTeamTask(task);
    // The newest run of each expert: the review round replaces the work round.
    teamLive.experts.set(payload.expert, run);
    if (payload.state === "working") showSubagentStep({ session_id: payload.session_id, tool: "" });
    refreshStudio();
  }

  // Sub-agents that are not experts (run_subagents without a team): known by their first step, in
  // the order they started; done when the run_subagents step is.
  const helperLive = { taskId: null, sessionId: null, helpers: new Map() };

  /** A sub-agent's step (task.subagent.step): an expert's tool, or a plain sub-agent at work. */
  function noteSubagentStep(task, payload) {
    if (!payload?.session_id) return;
    const run = expertRuns.get(payload.session_id);
    if (run) { run.tool = payload.tool || ""; refreshStudio(); return; }
    if (helperLive.taskId !== task.id) {
      helperLive.taskId = task.id;
      helperLive.sessionId = task.sessionId;
      helperLive.helpers = new Map();
    }
    const known = helperLive.helpers.get(payload.session_id);
    helperLive.helpers.set(payload.session_id, { index: known?.index || helperLive.helpers.size + 1, tool: payload.tool || "", done: false });
    queueStudioRefresh();
  }

  /** The run_subagents step finished: its sub-agents are done and go. */
  function endHelpers() {
    for (const helper of helperLive.helpers.values()) helper.done = true;
    queueStudioRefresh();
  }

  function endTeamTask(task) {
    if (helperLive.taskId === task.id) endHelpers();
    if (teamLive.taskId !== task.id) return;
    teamLive.running = false;
    for (const run of teamLive.experts.values()) if (run.state === "working") run.state = task.state === "succeeded" ? "done" : "stopped";
    refreshStudio();
  }

  /** "Researcher (work): searching the web" for an expert's helper, or null for a plain helper. */
  function expertStepLine(sessionId, step) {
    const run = expertRuns.get(sessionId);
    return run ? t("{0}（{1}）：{2}", expertName(run.expert, run.name), phaseLabel(run.phase), step || t("思考中")) : null;
  }

  /** Under the expert step while it runs: a way into the studio to watch them. It sits below the
   * step's card, not in it: the card stays folded while the experts work. */
  function offerStudio(card) {
    if (card.nextElementSibling?.classList.contains("team-watch-row")) return;
    const row = document.createElement("div");
    row.className = "team-watch-row";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button-secondary team-watch";
    button.innerHTML = icon("building-2");
    button.append(t("去工作室看看"));
    button.addEventListener("click", () => { void openStudio(); });
    row.append(button);
    card.after(row);
  }

  /** The step label of a run_subagents call that names experts, or null. */
  function teamToolLabel(args) {
    const tasks = Array.isArray(args?.tasks) ? args.tasks.filter((item) => item && typeof item.expert === "string") : [];
    if (!tasks.length) return null;
    return t("交给专家：{0}", tasks.map((item) => expertName(item.expert, item.title)).join(t("、")));
  }

  /** Under a finished expert step: each expert's part, how it went, their report and their work. */
  function showTeamResult(card, detail) {
    let value = detail;
    try { if (typeof value === "string") value = JSON.parse(value); } catch { return false; }
    const results = Array.isArray(value?.results) ? value.results.filter((item) => item && typeof item.expert === "string") : [];
    if (!results.length) return false;
    for (const item of results) if (item.session_id) expertRuns.set(item.session_id, { ...(expertRuns.get(item.session_id) || {}), expert: item.expert, name: item.name, phase: item.phase, state: item.status, session_id: item.session_id });
    card.querySelector("pre")?.remove();
    card.querySelector(".tool-meta")?.remove();
    card.querySelector(".team-results")?.remove();
    const list = document.createElement("div");
    list.className = "team-results";
    for (const item of results) {
      const row = document.createElement("details");
      row.className = "team-result";
      row.dataset.state = item.status === "done" ? "done" : "failed";
      const summary = document.createElement("summary");
      const swatch = document.createElement("span");
      swatch.className = "team-swatch";
      swatch.style.setProperty("--swatch", lookFor(item.expert).shirt);
      const name = document.createElement("strong");
      name.textContent = expertName(item.expert, item.name);
      const state = document.createElement("small");
      state.textContent = `${phaseLabel(item.phase)} · ${item.status === "done" ? t("完成") : t("出错了")}`;
      summary.append(swatch, name, state);
      const body = document.createElement("div");
      body.className = "team-result-body";
      body.textContent = item.report || item.error || "";
      row.append(summary, body);
      if (item.session_id) {
        const open = document.createElement("button");
        open.type = "button";
        open.className = "button-secondary";
        open.textContent = t("查看过程");
        open.addEventListener("click", () => { if (!openSession(item.session_id)) notice(t("任务进行中，结束后再打开")); });
        row.append(open);
      }
      list.append(row);
    }
    card.appendChild(list);
    return true;
  }

  // ---- The studio -------------------------------------------------------------------------------
  // The same office as the desktop app's studio (web_companion/studio, three.js), for the
  // conversation on screen: the agent and its experts go where their task takes them.
  const studioLooks = {
    lead: { shirt: "#2f5d9e", pants: "#2b3140", skin: "#f1c7a5", hair: "#2b211c", hairStyle: "short", accessory: "badge" },
    researcher: { shirt: "#2a9d8f", pants: "#34404c", skin: "#e9b896", hair: "#5b3a29", hairStyle: "long", accessory: "glasses" },
    analyst: { shirt: "#e0a13a", pants: "#3a3f4a", skin: "#c99272", hair: "#151515", hairStyle: "short", accessory: "headset" },
    critic: { shirt: "#c8553d", pants: "#2e2e36", skin: "#f2d0b4", hair: "#7a4b2a", hairStyle: "spiky", accessory: "cap" },
    engineer: { shirt: "#4f6274", pants: "#2c3440", skin: "#d8a483", hair: "#3a2a20", hairStyle: "short", accessory: "helmet" },
    legal: { shirt: "#3e3f55", pants: "#22232c", skin: "#efc6a6", hair: "#1e1a18", hairStyle: "bun", accessory: "tie" },
    finance: { shirt: "#3a7d44", pants: "#2a3330", skin: "#e3b28f", hair: "#9a9a9a", hairStyle: "bald", accessory: "glasses" },
    product: { shirt: "#7b5ea7", pants: "#33303f", skin: "#f0c9ab", hair: "#3b2416", hairStyle: "bun", accessory: "none" },
    writer: { shirt: "#c06c84", pants: "#38323c", skin: "#e8bc9b", hair: "#6d3b26", hairStyle: "long", accessory: "scarf" },
    teacher: { shirt: "#8a8d3b", pants: "#3b3a30", skin: "#d39b78", hair: "#4a4a4a", hairStyle: "short", accessory: "glasses" },
  };
  const studioShirts = ["#3f88c5", "#d1495b", "#66a182", "#edae49", "#8f6593", "#00798c", "#e76f51"];
  const studioHairs = ["#2b211c", "#6b3e26", "#a0522d", "#1b1b1b", "#c19a6b"];

  function lookHash(text) {
    let value = 2166136261;
    for (const char of text) value = Math.imul(value ^ char.codePointAt(0), 16777619);
    return value >>> 0;
  }
  function lookFor(id) {
    if (studioLooks[id]) return studioLooks[id];
    const seed = lookHash(id);
    // A library expert wears the colour of their field.
    const field = expertCatalog?.byId.get(id)?.domain?.color;
    return {
      shirt: field || studioShirts[seed % studioShirts.length], pants: "#30343e",
      skin: ["#f1c7a5", "#d8a483", "#c99272", "#e9b896"][(seed >> 3) % 4], hair: studioHairs[(seed >> 5) % studioHairs.length],
      hairStyle: ["short", "long", "bun", "spiky"][(seed >> 7) % 4], accessory: ["none", "glasses", "scarf", "cap"][(seed >> 9) % 4],
    };
  }

  // What an agent is doing, by the tool it uses: where it stands and what its tag says.
  const searchTools = /^(web_search|web_fetch|browser|browser_view|http_request|download_file|paper_search|paper_lookup|read_paper|knowledge_search|knowledge_use|memory_search|check_references)$/;
  const readTools = /^(read_file|read_document|list_files|search_files|render_pdf|query_table|list_|read_|office_read|android_observe|android_screenshot|active_notifications|recent_notifications)/;
  const writeTools = /^(write_file|append_file|apply_patch|copy_file|move_path|delete_path|memory_write|knowledge_add|create_|office_template|save_|word_document|spreadsheet|pdf_tools|slides_from_template|export_references|reference_library)/;
  const codeTools = /^(run_|start_service|stop_service|android_action|android_screen_action)/;
  function activityKind(tool) {
    if (!tool) return "thinking";
    if (tool === "run_subagents") return "delegate";
    if (searchTools.test(tool)) return "search";
    if (codeTools.test(tool)) return "code";
    if (writeTools.test(tool)) return "write";
    if (readTools.test(tool)) return "read";
    return "tool";
  }
  // Searches in books and papers are at the shelf; other searches are on the web, at the desk.
  const libraryTools = /^(knowledge_|paper_|read_paper|reference_library|memory_search|check_references)/;
  // Commands run in the app's own Linux, shut off from the phone: in the sandbox's glass room. Working
  // the phone's screen is at the console outside it.
  const sandboxTools = /^(run_terminal|start_service|stop_service)$/;
  // Tools that make a document someone could print: fetched from the printer.
  const printedTools = /^(create_(docx|xlsx|pdf)|word_document|spreadsheet|pdf_tools|slides_from_template|office_template|export_references)$/;
  /** Where an activity takes someone; the tool tells books from the web and the sandbox from the phone. */
  function spotFor(activity, tool = "") {
    if (activity === "search") return tool && !libraryTools.test(tool) ? "desk" : "shelf";
    if (activity === "code") return sandboxTools.test(tool) ? "sandbox" : "terminal";
    return activity === "delegate" ? "board" : "desk";
  }
  const activityLabels = () => ({ thinking: t("思考中"), search: t("查资料"), read: t("看文件"), write: t("写文件"), code: t("运行代码"), delegate: t("分配任务"), tool: t("使用工具") });
  const stateLabels = () => ({ idle: t("空闲"), working: t("工作中"), waiting: t("等你确认"), done: t("完成"), failed: t("出错了"), arriving: t("准备中"), stopped: t("已停止"), answering: t("写回答") });

  function speechLine(value, limit = 30) {
    const flat = String(value || "").replace(/```[\s\S]*?(```|$)/g, " ").replace(/[#*_>`|-]+/g, " ").replace(/\s+/g, " ").trim();
    return flat.length > limit ? `${flat.slice(0, limit - 1).trimEnd()}…` : flat;
  }

  /** Desks besides the agent's: the experts and sub-agents at work in the room at most. */
  const studioDesks = 4;

  /**
   * The studio's people now: the conversation's agent, and once the conversation has called them its
   * expert team and its sub-agents, each as their real task goes. Working alone the agent thinks at
   * the window, looks things up on the web at its desk or in the books at the shelf, runs commands
   * in the sandbox's glass room, and fetches a document it made from the printer.
   */
  function studioCast() {
    const task = activeTask && !activeTask.done && activeTask.sessionId === currentSessionId ? activeTask : null;
    const running = !!task;
    const runningCard = running ? [...elements.timelineList.querySelectorAll('.message-card.tool[data-state="running"]')].pop() : null;
    const tool = runningCard?.dataset.tool || "";
    const approval = running && pendingApproval ? pendingApproval : null;
    // Asked to run something or change files: the agent waits outside the glass door.
    const approvalKind = approval?.kind === "tool" ? activityKind(approval.details?.tool || "") : "";
    const atDoor = approvalKind === "code" || approvalKind === "write";
    const runs = teamLive.sessionId === currentSessionId ? [...teamLive.experts.entries()] : [];
    const helpers = helperLive.sessionId === currentSessionId ? [...helperLive.helpers.entries()] : [];
    const unfinished = runs.filter(([, run]) => run.state === "working");
    const delegating = unfinished.length > 0 || helpers.some(([, helper]) => !helper.done);
    const reviewing = unfinished.some(([, run]) => run.phase === "review");
    const leadActivity = running ? activityKind(tool) : null;
    const answer = running && !tool ? task.text : "";
    // Thinking before it writes or uses anything, the agent stands at the window.
    const pondering = running && !tool && !answer.trim() && !delegating && !approval;
    // The newest document made in the conversation: fetched from the printer once (the scene remembers).
    const printed = running && !approval
      ? [...elements.timelineList.querySelectorAll('.message-card.tool[data-state="done"]')].reverse().find((card) => printedTools.test(card.dataset.tool || ""))
      : null;
    const labels = activityLabels();
    const states = stateLabels();
    const leadState = approval ? "waiting" : !running ? "idle" : answer ? "answering" : "working";
    const lead = {
      id: "lead", name: runs.length ? t("队长") : "AI", lead: true, state: leadState,
      activity: delegating && !tool ? "delegate" : leadActivity,
      spot: approval ? (atDoor ? "door" : "desk") : reviewing ? "table" : delegating && (!tool || tool === "run_subagents") ? "board"
        : pondering ? "window" : spotFor(leadActivity, tool),
      look: lookFor("lead"),
    };
    if (printed?.dataset.toolId) lead.errand = printed.dataset.toolId;
    lead.stateLabel = leadState === "working" ? labels[lead.activity || "thinking"] : states[leadState];
    if (answer && !approval) lead.bubble = speechLine(answer);
    else if (approval) lead.bubble = "?";
    // The experts come in once the conversation calls its team: a fixed team's members, or on auto
    // the experts the lead picked for this task (newest first).
    const picked = runs.map(([id]) => id).reverse();
    const members = !runs.length ? [] : teamSettings.mode === "fixed" ? teamSettings.members : picked.slice(0, studioDesks);
    const experts = members.map((id) => {
      const run = teamLive.experts.get(id);
      const state = !run ? "idle" : run.state === "working" ? "working" : run.state === "done" ? "done" : run.state === "failed" ? "failed" : "stopped";
      const activity = state === "working" ? activityKind(run.tool) : null;
      const actor = {
        id, name: expertName(id, run?.name), lead: false, state, activity,
        spot: state === "working" && run.phase === "review" ? "table" : state === "working" ? spotFor(activity, run.tool) : "desk",
        look: lookFor(id), sessionId: run?.session_id || null,
      };
      actor.stateLabel = state === "working" ? labels[activity || "thinking"] : states[state];
      if (state === "done") actor.bubble = "✓";
      else if (state === "failed") actor.bubble = "!";
      else if (state === "working" && actor.spot === "table") actor.bubble = "…";
      return actor;
    });
    // Sub-agents come in by the door to the desks the experts leave free; done, they go out by it.
    const free = Math.max(0, studioDesks - experts.length);
    const others = free === 0 ? [] : helpers.slice(-free).map(([sessionId, helper]) => {
      const state = helper.done ? "done" : "working";
      const activity = state === "working" ? activityKind(helper.tool) : null;
      const actor = {
        id: `helper:${sessionId}`, name: t("子任务 {0}", helper.index), lead: false, state, activity,
        spot: state === "working" ? spotFor(activity, helper.tool) : "desk", leaves: true,
        look: lookFor(`helper:${sessionId}`), sessionId,
      };
      actor.stateLabel = state === "working" ? labels[activity || "thinking"] : states[state];
      if (state === "done") actor.bubble = "✓";
      return actor;
    });
    return [lead, ...experts, ...others];
  }

  let studioScene = null;
  let studioLoader = null;
  let studioPaused = false;
  let studioSignature = "";
  let studioTimer = 0;

  function loadStudio() {
    if (window.AgentStudio) return Promise.resolve(window.AgentStudio);
    if (!studioLoader) studioLoader = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = `/static/mobile-studio.js?token=${encodeURIComponent(token)}`;
      script.onload = () => (window.AgentStudio ? resolve(window.AgentStudio) : reject(new Error("studio missing")));
      script.onerror = () => { studioLoader = null; reject(new Error("studio unavailable")); };
      document.head.appendChild(script);
    });
    return studioLoader;
  }

  function studioLook() {
    const dark = preferences.theme === "dark" || (preferences.theme === "system" && darkSchemeQuery?.matches === true);
    const accent = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true || document.documentElement.dataset.motion === "reduced";
    return { dark, reducedMotion: reduced, accent: /^#[0-9a-f]{6}$/i.test(accent) ? accent : "#2f7d6d" };
  }

  function renderStudioRoster(cast) {
    const roster = $("studioRoster");
    roster.replaceChildren(...cast.map((actor) => {
      const item = document.createElement("li");
      item.dataset.state = actor.state;
      const button = document.createElement("button");
      button.type = "button";
      button.disabled = !actor.lead && !actor.sessionId;
      button.setAttribute("aria-label", actor.lead ? t("队长") : t("打开 {0} 的任务", actor.name));
      const swatch = document.createElement("span");
      swatch.className = "team-swatch";
      swatch.style.setProperty("--swatch", actor.look.shirt);
      const name = document.createElement("strong");
      name.textContent = actor.name;
      const state = document.createElement("span");
      state.textContent = actor.stateLabel;
      button.append(swatch, name, state);
      button.addEventListener("click", () => studioPick("room", actor.id));
      item.append(button);
      return item;
    }));
  }

  /** A tap on someone: the agent goes back to the conversation, an expert or a sub-agent opens theirs. */
  let studioShownCast = [];
  function studioPick(_floor, actorId) {
    if (!studioViewing && $("studioSheet").hidden) return;
    if (actorId === "lead") { closeStudio(); return; }
    const sessionId = studioShownCast.find((actor) => actor.id === actorId)?.sessionId;
    if (!sessionId) return;
    if (openSession(sessionId)) closeStudio();
    else notice(t("任务进行中，结束后再打开"));
  }

  function refreshStudio() {
    const sheetOpen = !$("studioSheet").hidden;
    if (!backdropScene && !(studioScene && sheetOpen)) return;
    const cast = studioCast();
    const signature = JSON.stringify(cast);
    if (signature === studioSignature) return;
    studioSignature = signature;
    studioShownCast = cast;
    const floors = [{ id: "room", number: "", title: "", summary: "", busy: false, cast }];
    if (sheetOpen) studioScene?.update(floors);
    backdropScene?.update(floors);
    // A place of the campus shown instead lists its own contents (34-campus.js).
    if (sheetOpen && !placeShownName) renderStudioRoster(cast);
  }

  // Task events, approvals and session changes move people: one look a little later, not one per event.
  let studioRefreshTimer = 0;
  function queueStudioRefresh() {
    if (studioRefreshTimer || disposed) return;
    studioRefreshTimer = window.setTimeout(() => {
      studioRefreshTimer = 0;
      refreshStudio();
      refreshPlaces();
    }, 250);
  }

  async function openStudio() {
    const sheet = $("studioSheet");
    if (disposed || layerOpen(sheet)) return;
    closeMenu({ instant: true });
    // Behind the conversation already: the app steps aside and the same studio is shown in full.
    const over = studioBackdropShown();
    sheet.dataset.over = over ? "backdrop" : "";
    showLayer(sheet, (motion) => motion.play(sheet, [{ opacity: 0, transform: "translateY(24px)" }, { opacity: 1, transform: "none" }], { duration: 260, easing: "cubic-bezier(.2, .7, .2, 1)" }));
    elements.appShell.inert = true;
    $("studioHint").hidden = true;
    $("studioUnsupported").hidden = true;
    const cast = studioCast();
    studioShownCast = cast;
    renderStudioRoster(cast);
    // By default the view follows the agent to wherever its work is (34-campus.js).
    if (over) {
      viewStudioBackdrop(true);
      backdropScene.setPaused(studioPaused);
      $("studioHint").hidden = false;
      enterPlaces();
      return;
    }
    enterPlaces();
    // The backdrop takes two colours of the chosen background (its colour fields), if it has them.
    const look = studioLook();
    const palette = getComputedStyle(document.documentElement);
    for (const [name, field] of [["--studio-1", "--wp-1"], ["--studio-2", "--wp-3"]]) {
      const value = palette.getPropertyValue(field).trim();
      if (/^\d+ \d+ \d+$/.test(value)) sheet.style.setProperty(name, `rgb(${value} / ${look.dark ? 0.2 : 0.32})`);
      else sheet.style.removeProperty(name);
    }
    try {
      await loadExpertCatalog().catch(() => null);
      const studio = await loadStudio();
      if (disposed || sheet.hidden) return;
      studioScene = studio.createStudioScene($("studioStage"), $("studioOverlay"), studioLook(), { pick: studioPick, pickFloor: () => {} });
    } catch {
      $("studioUnsupported").hidden = false;
      return;
    }
    studioSignature = "";
    studioScene.setPaused(studioPaused);
    // A place of the campus may be shown already: the room waits, undrawn.
    if (placeShownName) studioScene.setActive(false);
    $("studioStage").dataset.ready = "true";
    $("studioHint").hidden = false;
    refreshStudio();
    // The agent's own steps and its answer change without an expert event: look again now and then.
    studioTimer = window.setInterval(() => {
      refreshStudio();
      refreshPlaces();
    }, 1000);
  }

  function closeStudio() {
    const sheet = $("studioSheet");
    if (!layerOpen(sheet)) return false;
    window.clearInterval(studioTimer);
    leavePlaces();
    studioScene?.dispose();
    studioScene = null;
    $("studioStage").dataset.ready = "false";
    $("studioOverlay").replaceChildren();
    // Back behind the conversation: drawing again (a place may have stopped it), never left paused.
    if (studioViewing) {
      viewStudioBackdrop(false);
      backdropScene?.setPaused(false);
      backdropScene?.setActive(true);
    }
    elements.appShell.inert = false;
    hideLayer(sheet, (motion) => [motion.play(sheet, [{ opacity: 1 }, { opacity: 0 }], { duration: 180, easing: "ease-out", fill: "forwards" })]);
    return true;
  }

  /** The scene the studio's buttons work on: a place of the campus, the studio's own, or the backdrop's shown in full. */
  function shownStudio() { return placeScene || studioScene || (studioViewing ? backdropScene : null); }

  $("btnStudioClose").addEventListener("click", () => closeStudio());
  $("btnStudioReset").addEventListener("click", () => shownStudio()?.resetView());
  $("btnStudioPause").addEventListener("click", () => {
    studioPaused = !studioPaused;
    shownStudio()?.setPaused(studioPaused);
    const button = $("btnStudioPause");
    button.setAttribute("aria-pressed", String(studioPaused));
    button.setAttribute("aria-label", studioPaused ? t("继续动画") : t("暂停动画"));
    button.title = button.getAttribute("aria-label");
    button.innerHTML = icon(studioPaused ? "play" : "pause");
  });
  syncTeamChip();
  if (teamSettings.on) void loadExpertCatalog().catch(() => {});
