
  // ---- Interactive cards (2.0): ```card blocks in a reply become things to act on --------------
  // The agent writes one JSON object (see _ANDROID_SYSTEM_SUFFIX): a checklist to tick off, options
  // side by side, an event for the calendar, a place to go, links, or next steps. Everything is
  // drawn as text; links must be http(s); a prompt is sent only when the user taps it.
  const cardTypes = new Set(["checklist", "compare", "event", "place", "links", "actions"]);

  function cardText(value, limit = 300) { return typeof value === "string" ? value.slice(0, limit) : value == null ? "" : String(value).slice(0, limit); }
  function cardUrl(value) {
    try {
      const url = new URL(String(value || ""));
      return ["https:", "http:"].includes(url.protocol) ? url.href : null;
    } catch { return null; }
  }
  function cardButton(iconName, label, action, primary = false) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = primary ? "button-primary card-action" : "button-secondary card-action";
    if (iconName) button.innerHTML = icon(iconName);
    button.append(label);
    button.addEventListener("click", action);
    return button;
  }
  function openCardUrl(url) {
    if (typeof bridge?.openExternal === "function") bridge.openExternal(url);
    else window.open(url, "_blank", "noopener");
  }
  // A checklist remembers its ticks on this device, by the card's own text.
  function cardKey(source) {
    let hash = 0;
    for (let index = 0; index < source.length; index += 1) hash = (hash * 31 + source.charCodeAt(index)) | 0;
    return `agent-card-${hash >>> 0}`;
  }

  // Models often tag the block json, or leave it untagged; such a block holding one card object counts.
  function isCardJson(source) {
    try {
      const spec = JSON.parse(source);
      return !!spec && typeof spec === "object" && !Array.isArray(spec) && cardTypes.has(spec.type);
    } catch { return false; }
  }

  function renderAgentCard(source) {
    let spec;
    try { spec = JSON.parse(source); } catch { return null; }
    if (!spec || typeof spec !== "object" || !cardTypes.has(spec.type)) return null;
    const card = document.createElement("section");
    card.className = `agent-card agent-card-${spec.type}`;
    if (spec.title) {
      const title = document.createElement("strong");
      title.className = "agent-card-title";
      title.textContent = cardText(spec.title, 120);
      card.append(title);
    }
    const items = Array.isArray(spec.items) ? spec.items.slice(0, 50) : [];
    if (spec.type === "checklist") {
      const key = cardKey(source);
      let ticks = [];
      try { ticks = JSON.parse(localStorage.getItem(key) || "[]"); } catch { ticks = []; }
      const count = document.createElement("small");
      const list = document.createElement("div");
      list.className = "agent-card-list";
      const update = () => { count.textContent = t("已完成 {0}/{1}", ticks.filter(Boolean).length, items.length); };
      items.forEach((item, index) => {
        if (ticks[index] === undefined) ticks[index] = typeof item === "object" && item?.done === true;
        const row = document.createElement("label");
        row.className = "agent-card-check";
        const box = document.createElement("input");
        box.type = "checkbox";
        box.checked = Boolean(ticks[index]);
        box.addEventListener("change", () => {
          ticks[index] = box.checked;
          row.classList.toggle("done", box.checked);
          try { localStorage.setItem(key, JSON.stringify(ticks)); } catch { /* Ticks stay for this page. */ }
          update();
          haptic(8);
        });
        const text = document.createElement("span");
        text.textContent = cardText(typeof item === "object" ? item?.text : item, 200);
        row.classList.toggle("done", box.checked);
        row.append(box, text);
        list.append(row);
      });
      update();
      card.append(list, count);
    } else if (spec.type === "compare") {
      const columns = Array.isArray(spec.columns) ? spec.columns.slice(0, 8).map((column) => cardText(column, 40)) : [];
      const rows = Array.isArray(spec.rows) ? spec.rows.slice(0, 30) : [];
      const links = Array.isArray(spec.links) ? spec.links : [];
      const scroll = document.createElement("div");
      scroll.className = "table-scroll";
      const table = document.createElement("table");
      if (columns.length) {
        const head = table.createTHead().insertRow();
        for (const column of columns) { const cell = document.createElement("th"); cell.textContent = column; head.append(cell); }
        if (links.some(cardUrl)) head.append(document.createElement("th"));
      }
      const body = table.createTBody();
      rows.forEach((values, index) => {
        const row = body.insertRow();
        if (Number.isInteger(spec.highlight) && spec.highlight === index) row.className = "highlight";
        for (const value of (Array.isArray(values) ? values : [values]).slice(0, 8)) row.insertCell().textContent = cardText(value, 120);
        const url = cardUrl(links[index]);
        if (links.some(cardUrl)) {
          const cell = row.insertCell();
          if (url) cell.append(cardButton("link", t("打开"), () => openCardUrl(url)));
        }
      });
      scroll.append(table);
      card.append(scroll);
    } else if (spec.type === "event") {
      const start = new Date(spec.start || "");
      const end = new Date(spec.end || "");
      if (Number.isNaN(start.getTime())) return null;
      const when = document.createElement("p");
      const format = { month: "numeric", day: "numeric", weekday: "short", hour: "2-digit", minute: "2-digit" };
      when.textContent = start.toLocaleString(i18n?.locale || "zh-CN", format) +
        (Number.isNaN(end.getTime()) ? "" : ` – ${end.toLocaleTimeString(i18n?.locale || "zh-CN", { hour: "2-digit", minute: "2-digit" })}`);
      card.append(when);
      if (spec.location) { const where = document.createElement("small"); where.textContent = cardText(spec.location, 160); card.append(where); }
      card.append(cardButton("calendar", t("加到日历"), () => {
        const event = { title: cardText(spec.title || t("日程"), 120), start: start.getTime(),
          end: Number.isNaN(end.getTime()) ? start.getTime() + 3600_000 : end.getTime(),
          location: cardText(spec.location, 160), notes: cardText(spec.notes, 1000) };
        const answer = typeof bridge?.addCalendarEvent === "function" ? JSON.parse(bridge.addCalendarEvent(JSON.stringify(event)) || "{}") : null;
        if (!answer?.ok) {
          void sendPrompt(event.location ? t("把这个日程加到日历：{0}，{1}，地点 {2}", event.title, when.textContent, event.location)
            : t("把这个日程加到日历：{0}，{1}", event.title, when.textContent));
        }
      }, true));
    } else if (spec.type === "place") {
      const name = cardText(spec.name, 120);
      const address = cardText(spec.address, 200);
      if (!name && !address) return null;
      const line = document.createElement("p");
      line.textContent = [name, address].filter(Boolean).join(" · ");
      card.append(line, cardButton("send", t("导航"), () => {
        const query = address || name;
        const answer = typeof bridge?.openMap === "function" ? JSON.parse(bridge.openMap(query) || "{}") : null;
        if (!answer?.ok) openCardUrl(`https://uri.amap.com/search?keyword=${encodeURIComponent(query)}`);
      }, true), cardButton("copy", t("复制地址"), () => copyText(address || name)));
    } else if (spec.type === "links") {
      const list = document.createElement("div");
      list.className = "agent-card-list";
      for (const item of items) {
        const url = cardUrl(item?.url);
        if (!url) continue;
        list.append(cardButton("link", cardText(item.title || url, 80), () => openCardUrl(url)));
      }
      if (!list.children.length) return null;
      card.append(list);
    } else if (spec.type === "actions") {
      const list = document.createElement("div");
      list.className = "agent-card-actions";
      for (const item of items.slice(0, 6)) {
        const prompt = cardText(item?.prompt, 2000).trim();
        if (!prompt) continue;
        list.append(cardButton("sparkles", cardText(item.label || prompt, 40), () => {
          if (activeTask) { notice(t("请等待当前任务结束")); return; }
          void sendPrompt(prompt);
        }));
      }
      if (!list.children.length) return null;
      card.append(list);
    }
    return card;
  }
