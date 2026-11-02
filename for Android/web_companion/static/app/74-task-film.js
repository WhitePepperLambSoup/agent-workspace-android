
  // ---- A task's replay film (2.8) --------------------------------------------------------------------
  // Under an answer: the studio plays the turn again, faster than it happened. The agent thinks at the
  // window, goes to the desk, the shelves, the sandbox, the console or the board for each step (as in
  // the studio, castFor), writes the answer, and is done, with what each step did written under the
  // picture. The page records it while it plays (when the WebView can record a canvas); the video can
  // then be kept in the workspace's exports folder and shared. Nothing leaves the phone unless shared.
  const filmSpeed = 2.5;
  const filmShots = 16;
  const filmWidth = 720;
  const filmHeight = 1280;

  /** The turn's steps up to this answer, one shot for a run of the same tool; null without a request. */
  function filmTurn(card) {
    let userCard = card.previousElementSibling;
    while (userCard && !(userCard.classList.contains("user") && !userCard.hidden)) userCard = userCard.previousElementSibling;
    const request = (userCard?.dataset.messageText || userCard?.dataset.displayText || "").trim();
    if (!userCard || !request) return null;
    let shots = [];
    let answer = "";
    for (let item = userCard.nextElementSibling; item; item = item === card ? null : item.nextElementSibling) {
      if (item.hidden) continue;
      if (item.classList.contains("assistant")) { answer = item.dataset.messageText || answer; continue; }
      if (!item.classList.contains("tool")) continue;
      const tool = item.dataset.tool || "";
      const label = item.querySelector(".tool-name")?.textContent.trim() || toolTitles[tool] || tool;
      const previous = shots[shots.length - 1];
      if (previous && previous.tool === tool) { previous.count += 1; continue; }
      shots.push({ tool, label, count: 1, id: item.dataset.toolId || "" });
    }
    // Many steps: runs at the same place become one shot, then every so many are shown.
    if (shots.length > filmShots) {
      const merged = [];
      for (const shot of shots) {
        const kind = activityKind(shot.tool);
        const previous = merged[merged.length - 1];
        if (previous && previous.kind === kind && spotFor(kind, previous.tool) === spotFor(kind, shot.tool)) {
          previous.count += shot.count;
          previous.label = activityLabels()[kind] || previous.label;
        } else merged.push({ ...shot, kind });
      }
      shots = merged.length > filmShots
        ? Array.from({ length: filmShots }, (_, index) => merged[Math.round(index * (merged.length - 1) / (filmShots - 1))])
        : merged;
    }
    return { request, answer: answer || card.dataset.messageText || "", shots };
  }

  /** What the film shows, in order: who stands where, what the caption says, for how long. */
  function filmBeats(turn) {
    const quiet = { approval: null, answer: "", printed: null, fixed: false, runs: [], helpers: [] };
    const shotMs = Math.min(2600, Math.max(1300, 22000 / Math.max(turn.shots.length, 1)));
    const beats = [{ cast: castFor({ ...quiet, running: true, tool: "", started: false }), ms: 2200, step: "", caption: t("「{0}」", speechLine(turn.request, 40)) }];
    turn.shots.forEach((shot, index) => {
      beats.push({
        cast: castFor({ ...quiet, running: true, tool: shot.tool, started: true, printed: printedTools.test(shot.tool) ? shot.id : null }),
        ms: shotMs, step: t("第 {0}/{1} 步", index + 1, turn.shots.length),
        // Several calls in one shot are named by what they were, not by the first one's words.
        caption: shot.count > 1 ? t("{0}（{1} 次）", toolTitles[shot.tool] || shot.label, shot.count) : shot.label,
      });
    });
    beats.push({ cast: castFor({ ...quiet, running: true, tool: "", started: true, answer: turn.answer || "…" }), ms: 2600, step: "", caption: t("写回答") });
    const done = castFor({ ...quiet, running: false, tool: "", started: true });
    done[0] = { ...done[0], state: "done", stateLabel: t("完成"), bubble: "✓" };
    beats.push({ cast: done, ms: 1800, step: "", caption: t("完成") });
    let at = 0;
    for (const beat of beats) { beat.at = at; at += beat.ms; }
    return { beats, total: at };
  }

  /** Lines of at most this width, as many as fit, the last one cut with an ellipsis. */
  function filmLines(context, text, width, most) {
    const lines = [];
    let line = "";
    for (const char of String(text || "").replace(/\s+/g, " ").trim()) {
      if (context.measureText(line + char).width > width && line) {
        lines.push(line);
        line = char.trim();
        if (lines.length === most) break;
      } else line += char;
    }
    if (lines.length < most && line) lines.push(line);
    else if (lines.length === most && line) lines[most - 1] = `${lines[most - 1].slice(0, -1)}…`;
    return lines;
  }

  /** One frame of the film: the studio over the backdrop's colours, the date on top, the caption below. */
  function drawFilmFrame(context, scene, look, beat, progress, date) {
    const { width, height } = context.canvas;
    const colour = (value, fallback) => /^\d+ \d+ \d+$/.test(value) ? `rgb(${value.split(" ").join(",")})` : fallback;
    const field = context.createLinearGradient(0, 0, 0, height);
    field.addColorStop(0, colour(look.field[0], look.dark ? "#1d2523" : "#e9efec"));
    field.addColorStop(1, colour(look.field[1], look.dark ? "#141a19" : "#d7e2dd"));
    context.fillStyle = field;
    context.fillRect(0, 0, width, height);
    // Drawn and read in one go: the canvas does not keep its picture after the page yields.
    context.drawImage(scene.frame(), 0, 0, width, height);
    const font = getComputedStyle(document.body).fontFamily || "sans-serif";
    const top = context.createLinearGradient(0, 0, 0, height * 0.1);
    top.addColorStop(0, "rgba(0,0,0,.32)");
    top.addColorStop(1, "rgba(0,0,0,0)");
    context.fillStyle = top;
    context.fillRect(0, 0, width, height * 0.1);
    context.fillStyle = "rgba(255,255,255,.92)";
    context.font = `600 ${Math.round(width * 0.032)}px ${font}`;
    context.textBaseline = "top";
    context.fillText(`Agent Workspace · ${date}`, width * 0.06, height * 0.03);
    const band = height * 0.24;
    const bottom = context.createLinearGradient(0, height - band, 0, height);
    bottom.addColorStop(0, "rgba(0,0,0,0)");
    bottom.addColorStop(0.45, "rgba(0,0,0,.5)");
    bottom.addColorStop(1, "rgba(0,0,0,.68)");
    context.fillStyle = bottom;
    context.fillRect(0, height - band, width, band);
    const left = width * 0.07;
    let y = height - band * 0.56;
    if (beat.step) {
      context.fillStyle = "rgba(255,255,255,.72)";
      context.font = `600 ${Math.round(width * 0.034)}px ${font}`;
      context.fillText(beat.step, left, y);
    }
    y += width * 0.052;
    context.fillStyle = "#fff";
    context.font = `650 ${Math.round(width * 0.05)}px ${font}`;
    for (const line of filmLines(context, beat.caption, width - left * 2, 2)) {
      context.fillText(line, left, y);
      y += width * 0.066;
    }
    context.fillStyle = "rgba(255,255,255,.22)";
    context.fillRect(left, height - height * 0.035, width - left * 2, 4);
    context.fillStyle = look.accent;
    context.fillRect(left, height - height * 0.035, (width - left * 2) * Math.min(Math.max(progress, 0), 1), 4);
  }

  /** A recorder for the film's canvas, MP4 where the WebView makes it (it plays everywhere), else WebM. */
  function filmRecorder(canvas) {
    if (typeof window.MediaRecorder !== "function" || typeof canvas.captureStream !== "function") return null;
    const type = ["video/mp4;codecs=avc1", "video/mp4", "video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"]
      .find((value) => window.MediaRecorder.isTypeSupported?.(value));
    if (!type) return null;
    try {
      const stream = canvas.captureStream(30);
      const recorder = new window.MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: 3000000 });
      const chunks = [];
      recorder.addEventListener("dataavailable", (event) => { if (event.data?.size) chunks.push(event.data); });
      const stopped = new Promise((resolve) => recorder.addEventListener("stop", resolve, { once: true }));
      return { recorder, chunks, stopped, stream, format: type.startsWith("video/mp4") ? "mp4" : "webm", mime: type.split(";")[0] };
    } catch { return null; }
  }

  function openTaskFilm(card) {
    if (!historyReady || !currentSessionId || disposed) return;
    const turn = filmTurn(card);
    if (!turn) { notice(t("找不到这条回答对应的请求")); return; }
    if (!turn.shots.length) { notice(t("这次回答没有用到工具，没有步骤可以回放"), "info"); return; }
    const sessionId = currentSessionId;
    const { layer, close } = stepLayer(t("任务回放"));
    layer.classList.add("task-film");
    const canvas = document.createElement("canvas");
    canvas.className = "task-film-picture";
    canvas.width = filmWidth;
    canvas.height = filmHeight;
    const context = canvas.getContext("2d");
    const foot = document.createElement("div");
    foot.className = "step-tutorial-foot";
    const hint = document.createElement("small");
    const keeping = t("视频存在工作区的 exports 文件夹，分享时才会发出去。");
    hint.textContent = keeping;
    const status = document.createElement("small");
    status.className = "step-tutorial-status";
    status.setAttribute("aria-live", "polite");
    const again = document.createElement("button");
    again.type = "button";
    again.className = "button-secondary";
    again.textContent = t("再放一遍");
    const save = document.createElement("button");
    save.type = "button";
    save.className = "button-primary";
    save.textContent = t("保存视频");
    const buttons = document.createElement("div");
    buttons.className = "compare-actions";
    buttons.append(again, save);
    foot.append(hint, status, buttons);
    layer.append(canvas, foot);
    document.body.append(layer);
    close.focus();

    const { beats, total } = filmBeats(turn);
    const look = studioWidgetLook();
    const date = new Date().toLocaleDateString(locale);
    let scene = null;
    let stage = null;
    let frame = 0;
    let take = null;
    let film = null;
    let playing = 0;
    const end = () => {
      playing += 1;
      window.cancelAnimationFrame(frame);
      if (take?.recorder.state === "recording") take.recorder.stop();
      take?.stream.getTracks().forEach((track) => track.stop());
      take = null;
      scene?.dispose();
      scene = null;
      stage?.remove();
      stage = null;
    };
    // Away from the app mid-film, the picture stops: the take is dropped and can be played again.
    const away = () => {
      if (document.visibilityState === "visible" || !scene) return;
      end();
      again.disabled = false;
      save.disabled = !film;
      status.textContent = t("回放中断了，再放一遍即可");
    };
    document.addEventListener("visibilitychange", away);
    close.addEventListener("click", () => { document.removeEventListener("visibilitychange", away); end(); }, { once: true });

    const play = async () => {
      end();
      const run = playing;
      again.disabled = true;
      save.disabled = true;
      status.textContent = t("准备中...");
      try {
        const studio = await loadStudio();
        if (run !== playing || !layer.isConnected) return;
        stage = document.createElement("div");
        stage.className = "task-film-stage";
        stage.setAttribute("aria-hidden", "true");
        const overlay = document.createElement("div");
        overlay.className = "studio-overlay";
        stage.append(overlay);
        document.body.append(stage);
        scene = studio.createStudioScene(stage, overlay, { ...studioLook(), reducedMotion: false, pixelRatio: filmWidth / 360, centered: true, speed: filmSpeed },
          { pick() {}, pickFloor() {} }, "backdrop");
        const floor = (cast) => [{ id: "room", number: "", title: "", summary: "", busy: false, cast }];
        // The fish tank's fish follow the model in use (the big fat fish for DeepSeek).
        scene.setModel?.(studioModel());
        scene.update(floor(beats[0].cast));
        scene.exercise(total + 6000);
        // The agent in its first place and the camera there before the film starts (at most four seconds).
        const settled = Date.now() + 4000;
        await new Promise((resolve) => setTimeout(resolve, 600));
        while (scene && !scene.calm() && Date.now() < settled) await new Promise((resolve) => setTimeout(resolve, 200));
        if (run !== playing || !scene) return;
        drawFilmFrame(context, scene, look, beats[0], 0, date);
        take = filmRecorder(canvas);
        take?.recorder.start(1000);
        status.textContent = t("正在回放...");
        const recording = take;
        const start = performance.now();
        let shown = 0;
        let drawn = 0;
        const tick = (now) => {
          if (run !== playing || !scene) return;
          const elapsed = now - start;
          while (shown + 1 < beats.length && elapsed >= beats[shown + 1].at) {
            shown += 1;
            scene.update(floor(beats[shown].cast));
          }
          if (now - drawn >= 1000 / 30 - 2) {
            drawn = now;
            drawFilmFrame(context, scene, look, beats[shown], elapsed / total, date);
          }
          if (elapsed < total) { frame = window.requestAnimationFrame(tick); return; }
          void (async () => {
            if (recording) {
              recording.recorder.stop();
              await recording.stopped;
              const blob = new Blob(recording.chunks, { type: recording.mime });
              if (blob.size) film = { blob, format: recording.format, mime: recording.mime };
            }
            if (run !== playing) return;
            end();
            again.disabled = false;
            save.disabled = !film;
            status.textContent = film ? t("回放完成，可以存成视频") : t("回放完成。这台手机录不了视频，只能观看。");
          })();
        };
        frame = window.requestAnimationFrame(tick);
      } catch {
        if (run !== playing) return;
        end();
        again.disabled = false;
        save.disabled = !film;
        status.textContent = t("这台手机画不了工作室，放不了回放");
      }
    };

    again.addEventListener("click", () => { film = null; hint.textContent = keeping; void play(); });
    save.addEventListener("click", async () => {
      if (!film || save.disabled) return;
      save.disabled = true;
      status.textContent = t("正在保存...");
      try {
        const title = `${t("任务回放")} ${speechLine(turn.request, 24).replace(/…$/, "")}`;
        const result = await apiJson(`/mobile/replays/upload?session_id=${encodeURIComponent(sessionId)}&format=${film.format}&title=${encodeURIComponent(title)}`,
          { method: "POST", headers: { "Content-Type": film.mime }, body: film.blob });
        // Said where the status line stays free for the share sheet's answer.
        hint.textContent = t("已存到工作区 exports 文件夹");
        status.textContent = "";
        save.disabled = false;
        for (const path of result.paths || []) {
          await artifactAction({ path, mime_type: result.mime_type || film.mime, workspaceId: workspaceOfSession(sessionId) }, "share", save, status, true);
        }
      } catch (error) {
        status.textContent = t("保存失败：{0}", localizeError(error.message));
        save.disabled = false;
      }
    });
    void play();
  }
