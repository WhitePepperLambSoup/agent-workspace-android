
  // ---- Notification digest (2.0): notifications kept on the phone, sorted by the agent ---------
  const digestPrompt = () => t("用 recent_notifications 读最近 2 小时的通知，整理成摘要：先一句话说最要紧的事；再分「要处理」「可稍后」「广告推广」三类，每条一行；取件码、航班车次、会议变更、账单到期单独列出来（用勾选清单卡片）。验证码不要复述。没有新通知就说一句没有。");

  async function loadDigest() {
    const status = $("notificationDigestStatus");
    try {
      const state = await apiJson("/mobile/notification-journal");
      if (disposed) return;
      $("notificationDigestToggle").checked = state.enabled === true;
      const access = (() => { try { return JSON.parse(bridge?.getNotificationAccess?.() || "{}"); } catch { return {}; } })();
      status.textContent = state.enabled
        ? (access.granted === false ? t("还没有通知使用权：点上面的「通知使用权」允许后才能记录") : t("已记录 {0} 条通知（最近 48 小时）", state.count))
        : "";
    } catch (error) { if (!disposed) status.textContent = t("读取失败：{0}", error.message); }
  }

  $("notificationDigestToggle").addEventListener("change", async (event) => {
    const toggle = event.target;
    toggle.disabled = true;
    try {
      await apiJson("/mobile/notification-journal", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: toggle.checked }) });
      if (!disposed) await loadDigest();
    } catch (error) {
      if (disposed) return;
      toggle.checked = !toggle.checked;
      $("notificationDigestStatus").textContent = error.message;
    } finally { toggle.disabled = false; }
  });

  $("btnDigestNow").addEventListener("click", () => {
    if (!$("notificationDigestToggle").checked) { $("notificationDigestStatus").textContent = t("先打开「记录通知用于摘要」"); return; }
    if (activeTask) { $("notificationDigestStatus").textContent = t("请等待当前任务结束"); return; }
    closeMenu();
    void sendPrompt(digestPrompt());
  });

  // Every 2 hours from the next full hour, in a conversation of its own.
  $("btnDigestSchedule").addEventListener("click", async () => {
    const status = $("notificationDigestStatus");
    if (!$("notificationDigestToggle").checked) { status.textContent = t("先打开「记录通知用于摘要」"); return; }
    try {
      const session = await apiJson("/sessions", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: t("通知摘要") }) });
      const due = new Date(Date.now() + 3600_000);
      due.setMinutes(0, 0, 0);
      await apiJson("/mobile/schedules", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: t("通知摘要"), prompt: digestPrompt(), session_id: session.id, model: settings.model,
          reasoning_effort: settings.reasoning_effort, due_at: due.toISOString(), repeat_seconds: 7200, enabled: true }) });
      if (!disposed) status.textContent = t("已添加：每 2 小时在「通知摘要」对话里整理一次，可以在「定时任务」里暂停");
    } catch (error) { if (!disposed) status.textContent = t("添加失败：{0}", error.message); }
  });

  new MutationObserver(() => { if (!disposed && !$("settingsNotificationRules").hidden) void loadDigest(); })
    .observe($("settingsNotificationRules"), { attributes: true, attributeFilter: ["hidden"] });
