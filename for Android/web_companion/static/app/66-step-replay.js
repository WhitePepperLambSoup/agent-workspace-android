
  // ---- Step replay (2.0): what the phone looked like after each action the AI took -------------
  // The accessibility service keeps a small picture after each phone action of a task (StepShots);
  // the reply then offers to look back through them, one card per step with what was done.
  function offerStepShots(task) {
    if (!(task?.stepShots > 0) || !task.card || task.card.querySelector(".step-replay-offer")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button-secondary step-replay-offer";
    button.innerHTML = icon("eye");
    button.append(t("回看操作（{0} 步）", task.stepShots));
    button.addEventListener("click", () => void openStepReplay(task.id));
    task.card.appendChild(button);
  }

  async function openStepReplay(taskId) {
    let steps = [];
    try { steps = (await apiJson(`/mobile/step-shots?task_id=${encodeURIComponent(taskId)}`)).steps || []; }
    catch (error) { notice(t("读取失败：{0}", error.message)); return; }
    if (disposed) return;
    if (!steps.length) { notice(t("这次操作的截图已经清理掉了"), "info"); return; }
    const layer = document.createElement("div");
    layer.className = "step-replay";
    layer.setAttribute("role", "dialog");
    layer.setAttribute("aria-label", t("回看操作"));
    const head = document.createElement("div");
    head.className = "step-replay-head";
    const title = document.createElement("strong");
    title.textContent = t("回看操作（{0} 步）", steps.length);
    const close = document.createElement("button");
    close.type = "button";
    close.className = "icon-button";
    close.setAttribute("aria-label", t("关闭"));
    close.innerHTML = icon("x");
    close.addEventListener("click", () => layer.remove());
    head.append(title, close);
    const strip = document.createElement("div");
    strip.className = "step-replay-strip";
    for (const step of steps) {
      const figure = document.createElement("figure");
      const image = document.createElement("img");
      image.alt = step.label || "";
      image.loading = "lazy";
      if (/^data:image\/jpeg;base64,/.test(step.image || "")) image.src = step.image;
      const caption = document.createElement("figcaption");
      caption.textContent = t("第 {0} 步 · {1}", step.index, step.label || "");
      figure.append(image, caption);
      strip.append(figure);
    }
    const hint = document.createElement("small");
    hint.textContent = t("截图只存在这台手机上，保留最近 20 个任务、最多 7 天；有密码等敏感内容的画面不会截。");
    layer.append(head, strip, hint);
    document.body.append(layer);
    close.focus();
  }
