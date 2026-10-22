
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
    button.addEventListener("click", () => void openStepReplay(task));
    task.card.appendChild(button);
  }

  function stepLayer(label) {
    const layer = document.createElement("div");
    layer.className = "step-replay";
    layer.setAttribute("role", "dialog");
    layer.setAttribute("aria-label", label);
    const head = document.createElement("div");
    head.className = "step-replay-head";
    const title = document.createElement("strong");
    title.textContent = label;
    const close = document.createElement("button");
    close.type = "button";
    close.className = "icon-button";
    close.setAttribute("aria-label", t("关闭"));
    close.innerHTML = icon("x");
    close.addEventListener("click", () => layer.remove());
    head.append(title, close);
    layer.append(head);
    return { layer, head, title, close };
  }

  async function openStepReplay(task) {
    let steps = [];
    try { steps = (await apiJson(`/mobile/step-shots?task_id=${encodeURIComponent(task.id)}`)).steps || []; }
    catch (error) { notice(t("读取失败：{0}", error.message)); return; }
    if (disposed) return;
    if (!steps.length) { notice(t("这次操作的截图已经清理掉了"), "info"); return; }
    const { layer, head, close } = stepLayer(t("回看操作（{0} 步）", steps.length));
    const tutorial = document.createElement("button");
    tutorial.type = "button";
    tutorial.className = "step-replay-make";
    tutorial.innerHTML = icon("book-open");
    tutorial.append(t("做成图文教程"));
    tutorial.addEventListener("click", () => { layer.remove(); void openStepTutorial(task); });
    head.insertBefore(tutorial, close);
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
    layer.append(strip, hint);
    document.body.append(layer);
    close.focus();
  }

  // As in the long picture (StepTutorial.kt): small floating windows on a step picture (this app's
  // bubble, a floating assist button) are filled with the color found most around each, except one
  // holding the spot the step touches.
  function paintOutFloating(image, covers, ring) {
    if (!Array.isArray(covers) || !covers.length) return;
    image.addEventListener("load", () => {
      const canvas = document.createElement("canvas");
      const width = canvas.width = image.naturalWidth;
      const height = canvas.height = image.naturalHeight;
      const context = width && height ? canvas.getContext("2d") : null;
      if (!context) return;
      context.drawImage(image, 0, 0);
      const pixels = context.getImageData(0, 0, width, height).data;
      for (const [x1, y1, x2, y2] of covers) {
        if (Array.isArray(ring) && ring[0] >= x1 && ring[0] <= x2 && ring[1] >= y1 && ring[1] <= y2) continue;
        const left = Math.min(Math.max(Math.floor(x1 * width) - 3, 0), width);
        const top = Math.min(Math.max(Math.floor(y1 * height) - 3, 0), height);
        const right = Math.min(Math.max(Math.floor(x2 * width) + 3, 0), width);
        const bottom = Math.min(Math.max(Math.floor(y2 * height) + 3, 0), height);
        if (right <= left || bottom <= top) continue;
        const counts = new Map();
        const take = (x, y) => {
          if (x < 0 || y < 0 || x >= width || y >= height) return;
          const at = (y * width + x) * 4;
          const [red, green, blue] = [pixels[at], pixels[at + 1], pixels[at + 2]];
          const key = ((red >> 4) << 8) | ((green >> 4) << 4) | (blue >> 4);
          const sums = counts.get(key) || [0, 0, 0, 0];
          sums[0] += 1; sums[1] += red; sums[2] += green; sums[3] += blue;
          counts.set(key, sums);
        };
        for (let x = left - 1; x <= right; x += 1) { take(x, top - 1); take(x, bottom); }
        for (let y = top; y < bottom; y += 1) { take(left - 1, y); take(right, y); }
        const most = [...counts.values()].sort((first, second) => second[0] - first[0])[0] || [1, 255, 255, 255];
        context.fillStyle = `rgb(${Math.round(most[1] / most[0])}, ${Math.round(most[2] / most[0])}, ${Math.round(most[3] / most[0])})`;
        context.fillRect(left, top, right - left, bottom - top);
      }
      image.src = canvas.toDataURL("image/jpeg", 0.9);
    }, { once: true });
  }

  // ---- Picture tutorial: the steps of a task as one long picture to send to someone ---------------
  // Each step says what to do; a step that touched one spot shows the screen it was done on with the
  // spot circled (mobile_step_tutorial.py plans it, StepTutorial.kt draws it). The words can be
  // changed and steps dropped before it is made.
  async function openStepTutorial(task) {
    let frames = [];
    try { frames = (await apiJson(`/mobile/step-shots/tutorial?task_id=${encodeURIComponent(task.id)}`)).frames || []; }
    catch (error) { notice(t("读取失败：{0}", error.message)); return; }
    if (disposed) return;
    if (!frames.length) { notice(t("这次操作的截图已经清理掉了"), "info"); return; }
    const { layer, close } = stepLayer(t("图文教程"));
    layer.classList.add("step-tutorial");
    const body = document.createElement("div");
    body.className = "step-tutorial-body";
    const titleLabel = document.createElement("label");
    titleLabel.className = "step-tutorial-title";
    titleLabel.append(t("标题"));
    const titleInput = document.createElement("input");
    titleInput.type = "text";
    titleInput.maxLength = 200;
    titleInput.value = String(task.prompt || "").replace(/\s+/g, " ").trim().slice(0, 60);
    titleLabel.append(titleInput);
    const list = document.createElement("ol");
    list.className = "step-tutorial-steps";
    const renumber = () => {
      let number = 0;
      for (const item of list.children) {
        item.querySelector(".step-tutorial-number").textContent = item.dataset.kind === "done" ? "✓" : String(++number);
      }
      make.disabled = !list.children.length;
    };
    for (const frame of frames) {
      const item = document.createElement("li");
      item.dataset.kind = frame.kind;
      item.dataset.index = frame.index ?? "";
      const row = document.createElement("div");
      row.className = "step-tutorial-row";
      const number = document.createElement("span");
      number.className = "step-tutorial-number";
      const words = document.createElement("textarea");
      words.rows = 2;
      words.maxLength = 300;
      words.value = frame.kind === "done" ? t("完成后是这样") : frame.caption || "";
      words.setAttribute("aria-label", t("这一步的说明"));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "icon-button";
      remove.setAttribute("aria-label", t("删掉这一步"));
      remove.innerHTML = icon("trash-2");
      remove.addEventListener("click", () => { item.remove(); renumber(); });
      row.append(number, words, remove);
      item.append(row);
      if (/^data:image\/jpeg;base64,/.test(frame.image || "")) {
        const picture = document.createElement("div");
        picture.className = "step-tutorial-picture";
        const image = document.createElement("img");
        image.alt = "";
        paintOutFloating(image, frame.covers, frame.ring);
        image.src = frame.image;
        picture.append(image);
        if (Array.isArray(frame.ring)) {
          const ring = document.createElement("span");
          ring.className = "step-tutorial-ring";
          ring.style.left = `${Math.min(Math.max(Number(frame.ring[0]) || 0, 0), 1) * 100}%`;
          ring.style.top = `${Math.min(Math.max(Number(frame.ring[1]) || 0, 0), 1) * 100}%`;
          picture.append(ring);
        }
        item.append(picture);
      }
      list.append(item);
    }
    body.append(titleLabel, list);
    const foot = document.createElement("div");
    foot.className = "step-tutorial-foot";
    const hint = document.createElement("small");
    hint.textContent = t("说明可以改，用不上的步骤可以删掉。图片存到工作区的 exports 文件夹。");
    const status = document.createElement("small");
    status.className = "step-tutorial-status";
    status.setAttribute("aria-live", "polite");
    const make = document.createElement("button");
    make.type = "button";
    make.className = "button-primary";
    make.textContent = t("生成长图");
    make.addEventListener("click", async () => {
      const title = titleInput.value.trim();
      if (!title) { status.textContent = t("先写个标题"); titleInput.focus(); return; }
      const chosen = [...list.children].map((item) => ({
        kind: item.dataset.kind,
        index: item.dataset.index === "" ? null : Number(item.dataset.index),
        caption: item.querySelector("textarea").value.trim(),
      }));
      const steps = chosen.filter((frame) => frame.kind !== "done").length;
      make.disabled = true;
      status.textContent = t("正在生成...");
      try {
        const result = await apiJson("/mobile/step-shots/tutorial", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task_id: task.id, session_id: task.sessionId, title,
            subtitle: t("共 {0} 步 · {1}", steps, new Date().toLocaleDateString()), frames: chosen }) });
        for (const path of result.paths || []) {
          await artifactAction({ path, mime_type: "image/jpeg", workspaceId: workspaceOfSession(task.sessionId) }, "share", make, status, true);
        }
        if (!status.textContent || status.textContent === t("正在生成...") || status.textContent === t("准备文件...")) {
          status.textContent = t("已存到工作区 exports 文件夹");
        }
      } catch (error) {
        status.textContent = t("生成失败：{0}", error.message);
      } finally { make.disabled = !list.children.length; }
    });
    foot.append(hint, status, make);
    layer.append(body, foot);
    renumber();
    document.body.append(layer);
    close.focus();
  }
