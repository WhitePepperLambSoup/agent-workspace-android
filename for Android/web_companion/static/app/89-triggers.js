
  // ---- Automatic triggers (2.0): charging, Wi-Fi, an app opening -----------------------------
  const triggerKinds = { charging: t("开始充电时"), wifi: t("连上 Wi‑Fi 时"), app_open: t("打开某个应用时") };
  let launcherApps = null;
  let triggerWorkflows = [];
  let triggerShortcuts = [];

  function appsOnPhone() {
    if (launcherApps === null) {
      try { launcherApps = typeof bridge?.getLauncherApps === "function" ? JSON.parse(bridge.getLauncherApps() || "[]") : []; }
      catch { launcherApps = []; }
    }
    return launcherApps;
  }
  function appName(packageName) { return appsOnPhone().find((app) => app.package === packageName)?.label || packageName; }

  function syncTriggerForm() {
    const kind = $("triggerKind").value;
    $("triggerValue").hidden = kind === "charging";
    $("triggerValueLabel").hidden = kind === "charging";
    $("triggerValueLabel").textContent = kind === "app_open" ? t("应用（输入名字可以搜索）") : t("Wi‑Fi 名称（留空表示任意网络）");
    $("triggerApps").replaceChildren(...(kind === "app_open" ? appsOnPhone() : []).map((app) => {
      const option = document.createElement("option");
      option.value = app.label;
      return option;
    }));
    $("triggerPrompt").hidden = Boolean($("triggerWorkflow").value);
    // A shortcut operates the phone by itself, without the model.
    $("triggerPhone").closest("label").hidden = $("triggerWorkflow").value.startsWith("shortcut:");
  }

  async function loadTriggers() {
    const status = $("triggersStatus");
    try {
      const [value, flows, shortcuts] = await Promise.all([apiJson("/mobile/triggers"),
        apiJson("/mobile/workflows").catch(() => ({ workflows: [] })), apiJson("/mobile/shortcuts").catch(() => ({ shortcuts: [] }))]);
      if (disposed) return;
      triggerWorkflows = flows.workflows || [];
      triggerShortcuts = shortcuts.shortcuts || [];
      const select = $("triggerWorkflow");
      const chosen = select.value;
      const choice = (optionValue, text) => {
        const option = document.createElement("option");
        option.value = optionValue;
        option.textContent = text;
        return option;
      };
      // A shortcut's option value is "shortcut:<id>"; a workflow's is its id.
      select.replaceChildren(select.options[0],
        ...triggerShortcuts.map((item) => choice(`shortcut:${item.id}`, t("运行快捷操作「{0}」", item.name))),
        ...triggerWorkflows.map((flow) => choice(flow.workflow_id, t("运行流程「{0}」", flow.name))));
      select.value = chosen;
      const rows = (value.triggers || []).map((trigger) => {
        const when = `${triggerKinds[trigger.kind] || trigger.kind}${trigger.value ? ` · ${trigger.kind === "app_open" ? appName(trigger.value) : trigger.value}` : ""}`;
        const flow = trigger.workflow_id && triggerWorkflows.find((item) => item.workflow_id === trigger.workflow_id);
        const shortcut = trigger.shortcut_id && triggerShortcuts.find((item) => item.id === trigger.shortcut_id);
        const what = shortcut ? t("运行快捷操作「{0}」", shortcut.name) : trigger.shortcut_id ? t("快捷操作已删除")
          : flow ? t("运行流程「{0}」", flow.name) : trigger.prompt || "";
        const row = document.createElement("div");
        row.className = "management-row";
        const text = document.createElement("span");
        const title = document.createElement("strong");
        title.textContent = when;
        const detail = document.createElement("small");
        detail.textContent = `${what} · ${t("冷却 {0} 分钟", trigger.cooldown_minutes)}${trigger.enabled ? "" : ` · ${t("已暂停")}`}`;
        text.append(title, detail);
        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "text-action";
        toggle.textContent = trigger.enabled ? t("暂停") : t("启用");
        toggle.addEventListener("click", async () => {
          await apiJson("/mobile/triggers/enable", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ trigger_id: trigger.trigger_id, enabled: !trigger.enabled }) });
          void loadTriggers();
        });
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "icon-button";
        remove.title = t("删除");
        remove.setAttribute("aria-label", t("删除"));
        remove.innerHTML = icon("trash-2");
        remove.addEventListener("click", async () => {
          if (!window.confirm(t("删除这个自动触发？"))) return;
          await apiJson("/mobile/triggers/delete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ trigger_id: trigger.trigger_id }) });
          void loadTriggers();
        });
        row.append(text, toggle, remove);
        return row;
      });
      $("triggersList").replaceChildren(...rows);
      status.textContent = rows.length ? "" : t("还没有自动触发");
    } catch (error) { if (disposed) return; status.textContent = t("读取失败：{0}", error.message); }
    syncTriggerForm();
  }

  $("triggerKind").addEventListener("change", syncTriggerForm);
  $("triggerWorkflow").addEventListener("change", syncTriggerForm);
  $("triggerForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = $("triggersStatus");
    const kind = $("triggerKind").value;
    let value = kind === "charging" ? "" : $("triggerValue").value.trim();
    if (kind === "app_open") value = appsOnPhone().find((app) => app.label === value || app.package === value)?.package || value;
    const workflow = $("triggerWorkflow").value;
    const target = workflow.startsWith("shortcut:") ? { shortcut_id: workflow.slice(9) }
      : workflow ? { workflow_id: workflow } : { prompt: $("triggerPrompt").value.trim() };
    const body = { kind, value, session_id: currentSessionId, phone_control: $("triggerPhone").checked,
      cooldown_minutes: Number($("triggerCooldown").value), ...target };
    try {
      await apiJson("/mobile/triggers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      $("triggerPrompt").value = "";
      $("triggerValue").value = "";
      await loadTriggers();
      status.textContent = t("已添加：结果会发到当前对话");
    } catch (error) { status.textContent = t("添加失败：{0}", error.message); }
  });
  // Loaded whenever the schedules page opens.
  new MutationObserver(() => { if (!disposed && !$("settingsSchedules").hidden) void loadTriggers(); })
    .observe($("settingsSchedules"), { attributes: true, attributeFilter: ["hidden"] });
