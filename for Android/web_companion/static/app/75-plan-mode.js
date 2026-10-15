
  // ---- Plan mode (2.0) -------------------------------------------------------------------------
  // With the chip on, a message asks for a plan only: the engine gives the agent read-only tools and
  // it answers with numbered steps. Nothing changes until "Carry out the plan" sends the go-ahead.
  let planMode = false;

  function syncPlanChip() {
    const chip = $("btnPlanChip");
    chip.setAttribute("aria-pressed", String(planMode));
    chip.classList.toggle("active", planMode);
  }

  // Under a finished plan: one button that carries it out (plan mode then turns off).
  function offerPlanExecution(task) {
    if (!task?.planMode || !task.card || task.card.querySelector(".plan-approve")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button-primary plan-approve";
    button.innerHTML = icon("check");
    button.append(t("按计划执行"));
    button.addEventListener("click", () => {
      planMode = false;
      syncPlanChip();
      button.disabled = true;
      void sendPrompt(t("按上面的计划执行。"));
    });
    task.card.appendChild(button);
  }

  $("btnPlanChip").addEventListener("click", () => {
    planMode = !planMode;
    haptic(14);
    syncPlanChip();
    notice(planMode ? t("计划模式：AI 只查看、不改动，先给出计划，你批准后再执行") : "", "info");
  });

  // ---- Gateway headers and backup keys for the current provider (2.0) ----------------------
  async function loadProviderExtras() {
    try {
      const value = await apiJson("/mobile/provider/extras");
      if (disposed) return;
      const parts = [];
      if (value.header_names?.length) parts.push(t("请求头：{0}", value.header_names.join(" / ")));
      if (value.backup_keys) parts.push(t("备用 Key {0} 个", value.backup_keys));
      $("providerExtrasState").textContent = parts.length ? t("已设置 · {0}", parts.join(" · ")) : t("还没有设置");
    } catch { if (!disposed) $("providerExtrasState").textContent = ""; }
  }
  $("btnSaveProviderExtras").addEventListener("click", async () => {
    const status = $("providerExtrasStatus");
    const headers = {};
    for (const line of $("providerHeaders").value.split("\n").map((item) => item.trim()).filter(Boolean)) {
      const split = line.indexOf(":");
      if (split < 1) { status.textContent = t("请求头要写成「名称: 值」：{0}", line); return; }
      headers[line.slice(0, split).trim()] = line.slice(split + 1).trim();
    }
    const keys = $("providerKeys").value.split("\n").map((item) => item.trim()).filter(Boolean);
    try {
      await apiJson("/mobile/provider/extras", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ headers, keys }) });
      $("providerHeaders").value = "";
      $("providerKeys").value = "";
      status.textContent = t("已保存，重启引擎后生效");
      void loadProviderExtras();
    } catch (error) { status.textContent = t("保存失败：{0}", error.message); }
  });
  new MutationObserver(() => { if (!disposed && !elements.settingsModel.hidden) void loadProviderExtras(); })
    .observe(elements.settingsModel, { attributes: true, attributeFilter: ["hidden"] });
