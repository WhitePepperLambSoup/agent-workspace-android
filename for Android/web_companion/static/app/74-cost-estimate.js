
  // ---- What a message will roughly cost before it is sent (mobile_cost_estimate) ---------------
  // A small line in the composer while typing: the usual cost of a task like the recent ones in this
  // workspace, and what a longer one costs. Hidden for on-device and unpriced models.
  function costMoney(value) { return `$${value.toFixed(value > 0 && value < 0.01 ? 4 : 2)}`; }

  function scheduleCostEstimate() {
    window.clearTimeout(scheduleCostEstimate.timer);
    const text = elements.promptInput.value.trim();
    if (!text || activeTask || !currentSessionId || !settings?.model) { $("costEstimate").hidden = true; return; }
    scheduleCostEstimate.timer = window.setTimeout(async () => {
      // Sent meanwhile: nothing to estimate.
      if (activeTask || !elements.promptInput.value.trim()) return;
      const generation = (scheduleCostEstimate.generation || 0) + 1;
      scheduleCostEstimate.generation = generation;
      try {
        const data = await apiJson(scopedUrl(`/mobile/cost-estimate?session_id=${encodeURIComponent(currentSessionId)}&model=${encodeURIComponent(settings.model)}&chars=${text.length}`,
          workspaceOfSession(currentSessionId)));
        if (disposed || generation !== scheduleCostEstimate.generation) return;
        if (!data.priced || data.free || !elements.promptInput.value.trim() || activeTask) { $("costEstimate").hidden = true; return; }
        $("costEstimate").textContent = t("预计约 {0}，多则 {1}", costMoney(data.expected_usd), costMoney(data.high_usd))
          + (data.from_history ? "" : t("（还没有用量记录，按常见情况估算）"));
        $("costEstimate").hidden = false;
      } catch { $("costEstimate").hidden = true; }
    }, 700);
  }

  // From syncControls: a task started, or the composer was emptied.
  function syncCostEstimate() {
    if (!activeTask && elements.promptInput.value.trim()) return;
    window.clearTimeout(scheduleCostEstimate.timer);
    $("costEstimate").hidden = true;
  }

  elements.promptInput.addEventListener("input", scheduleCostEstimate);
