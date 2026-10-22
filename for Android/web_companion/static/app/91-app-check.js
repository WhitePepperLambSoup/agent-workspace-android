
  // ---- 应用体检: apps that behave like rogue software (mobile_app_audit) ----------------------
  // Facts Android gives about each app the user installed, weighed on the phone; the buttons open
  // Android's own uninstall confirmation or the settings page that takes a power back.
  function appCheckWords() {
    return appCheckWords.cache || (appCheckWords.cache = {
      levels: { high: t("建议处理"), medium: t("留意"), low: t("正常"), none: t("正常"), trusted: t("已标为没问题") },
      reasons: {
        device_admin: t("是设备管理器：能锁屏、清空手机，不取消就卸载不掉"),
        accessibility: t("开着无障碍服务：能看到屏幕上的内容，还能替你点按"),
        notification_listener: t("能读取所有通知，包括验证码"),
        sms: t("能读短信"),
        hidden_icon: t("桌面上没有图标，不容易发现"),
        old_target: t("为很旧的安卓版本打包，安装时就拿到了全部权限"),
        call_log: t("能读通话记录"),
        background_location: t("能在后台获取位置"),
        overlay: t("能显示在其他应用上层（悬浮窗）"),
        install_others: t("能安装其他应用"),
        usage_access: t("能看到你在用哪些应用"),
        keeps_running: t("开机自启，并且不受省电限制"),
        new: t("最近 3 天内安装"),
        disabled: t("已停用"),
      },
      actions: {
        uninstall: t("卸载"), device_admin: t("取消设备管理器"), accessibility: t("关闭无障碍"),
        notification_access: t("关闭通知读取"), overlay: t("关闭悬浮窗"), install_others: t("禁止安装应用"),
        usage_access: t("关闭使用情况访问"), battery: t("限制后台"), info: t("应用信息"), notifications: t("通知设置"),
      },
    });
  }

  // For the approval shelf and the step list (60-timeline.js, 70-tasks.js).
  function appCheckActionName(page) { return appCheckWords().actions[page] || page; }

  function appCheckSource(app) {
    const source = app.source || {};
    const by = source.by_label || source.by;
    if (source.kind === "store") return by ? t("来自 {0}", by) : t("来自应用商店");
    if (source.kind === "manual") return by ? t("用安装包安装（从 {0} 打开）", by) : t("用安装包安装");
    if (source.kind === "app") return t("由 {0} 安装", by);
    if (source.kind === "self") return t("自己更新安装");
    return t("来源不明（随手机预装，或用电脑装的）");
  }

  function appCheckReasons(app) {
    const words = appCheckWords().reasons;
    const lines = [];
    for (const code of app.signals || []) {
      if (code === "pops_up" && app.popups) {
        const times = (app.popups.jumps || 0) + (app.popups.overlays || 0);
        const over = app.popups.over_label || app.popups.over;
        const when = app.popups.last_at ? new Date(app.popups.last_at).toLocaleString() : "";
        lines.push(t("7 天内自己弹出来 {0} 次", times) + (over ? t("，最近一次在「{0}」上面", over) : "") + (when ? ` · ${when}` : ""));
      } else if (code === "manual_install" || code === "installed_by_app") {
        continue; // said in the source line
      } else if (words[code]) lines.push(words[code]);
    }
    return lines;
  }

  async function appCheckPost(body) {
    return apiJson("/mobile/app-audit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  }

  function appCheckCard(app) {
    const words = appCheckWords();
    const card = document.createElement("article");
    card.className = "app-check-card";
    card.dataset.level = app.level;
    const head = document.createElement("div");
    head.className = "app-check-head";
    const name = document.createElement("strong");
    name.textContent = app.label;
    const level = document.createElement("span");
    level.className = "app-check-level";
    level.textContent = words.levels[app.level] || "";
    head.append(name, level);
    const meta = document.createElement("small");
    meta.className = "app-check-meta";
    meta.textContent = [app.package, appCheckSource(app)].join(" · ");
    card.append(head, meta);
    const reasons = appCheckReasons(app);
    if (reasons.length) {
      const list = document.createElement("ul");
      list.className = "app-check-reasons";
      list.append(...reasons.map((text) => { const item = document.createElement("li"); item.textContent = text; return item; }));
      card.append(list);
    }
    const actions = document.createElement("div");
    actions.className = "app-check-actions";
    const button = (label, run, primary = false) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = primary ? "button-secondary app-check-primary" : "button-secondary";
      element.textContent = label;
      element.addEventListener("click", async () => {
        element.disabled = true;
        try { await run(); } catch (error) { pageStatus($("appCheckStatus"), localizeError(error.message) || t("操作没有完成"), true); }
        finally { element.disabled = false; }
      });
      return element;
    };
    for (const page of app.actions || []) {
      actions.append(button(words.actions[page] || page, async () => {
        await appCheckPost({ action: "open", package_name: app.package, page });
        // Back from Android's page, the list is checked again (loadAppCheck on return).
        loadAppCheck.stale = true;
      }, page === "uninstall" || page === "device_admin"));
    }
    if (app.level === "trusted") actions.append(button(t("取消标记"), async () => { await appCheckPost({ action: "trust", package_name: app.package, trusted: false }); await loadAppCheck(); }));
    else if (app.level === "high" || app.level === "medium") {
      actions.append(button(t("没问题"), async () => { await appCheckPost({ action: "trust", package_name: app.package, trusted: true }); await loadAppCheck(); }));
    }
    card.append(actions);
    return card;
  }

  async function loadAppCheck() {
    loadAppCheck.stale = false;
    const status = $("appCheckStatus");
    pageStatus(status, t("正在检查…"));
    let report;
    try { report = await apiJson("/mobile/app-audit"); }
    catch (error) { if (!disposed) pageStatus(status, t("检查失败：{0}", localizeError(error.message)), true); return; }
    if (disposed) return;
    const apps = Array.isArray(report.apps) ? report.apps : [];
    const flagged = apps.filter((app) => app.level === "high" || app.level === "medium");
    const others = apps.filter((app) => !flagged.includes(app));
    $("appCheckList").replaceChildren(...flagged.map(appCheckCard));
    $("appCheckOtherList").replaceChildren(...others.map(appCheckCard));
    $("appCheckOthers").hidden = !others.length;
    $("appCheckOthersTitle").textContent = t("其他 {0} 个应用", others.length);
    pageStatus(status, report.high && report.medium
      ? t("检查了 {0} 个你装的应用：{1} 个建议处理，{2} 个可以留意。", report.checked, report.high, report.medium)
      : report.high ? t("检查了 {0} 个你装的应用：{1} 个建议处理。", report.checked, report.high)
        : report.medium ? t("检查了 {0} 个你装的应用：{1} 个可以留意。", report.checked, report.medium)
          : t("检查了 {0} 个你装的应用，没有发现明显的问题。", report.checked));
    $("appCheckWatch").checked = report.watching === true;
    pageStatus($("appCheckWatchStatus"), report.watching && !report.watch_ready
      ? t("本应用的无障碍服务没开，现在记录不到弹窗。可以在「设备与工具」里打开。") : "", report.watching && !report.watch_ready);
  }

  $("btnAppCheckPage")?.addEventListener("click", () => { if (setSettingsPage("appCheck")) void loadAppCheck(); });
  $("btnAppCheckRefresh")?.addEventListener("click", () => void loadAppCheck());
  $("appCheckWatch")?.addEventListener("change", async (event) => {
    const toggle = event.target;
    if (!toggle.checked && !window.confirm(t("关闭后会清除已记下的弹窗记录。继续？"))) { toggle.checked = true; return; }
    toggle.disabled = true;
    try { await appCheckPost({ action: "watch", enabled: toggle.checked }); await loadAppCheck(); }
    catch (error) { toggle.checked = !toggle.checked; pageStatus($("appCheckWatchStatus"), localizeError(error.message), true); }
    finally { toggle.disabled = false; }
  });
  $("btnAppCheckAsk")?.addEventListener("click", () => {
    if (activeTask) { pageStatus($("appCheckStatus"), t("请等待当前任务结束"), true); return; }
    closeMenu();
    void sendPrompt(t("帮我做一次应用体检，看看手机上有没有流氓软件：按轻重告诉我哪些建议处理、为什么。先不要动手，等我说处理哪个，再帮我卸载或关掉它的权限。"));
  });
  // Back from an uninstall or a settings page: what changed shows at once.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && loadAppCheck.stale && !$("settingsAppCheck")?.hidden && !disposed) void loadAppCheck();
  });
