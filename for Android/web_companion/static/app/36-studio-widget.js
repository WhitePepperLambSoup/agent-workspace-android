
  // ---- The studio widget (2.8) ------------------------------------------------------------------------
  // A home-screen widget cannot draw 3D, so while the app is open and quiet the page draws the agent at
  // each place it works (mobile_studio_pose.POSES) in a hidden studio of its own, close up as behind the
  // conversation, four frames a place on the backdrop's colours, and hands them to the app
  // (AgentWidgets): the launcher plays them in a loop while a task runs. Drawn again when the look
  // (light or dark, the accent, the background) or this drawing changes, and only while a studio
  // widget is placed. About half a minute of drawing, once.
  const studioWidgetDrawing = 1;
  const studioWidgetPlaces = {
    window: { spot: "window", activity: "thinking", state: "working" },
    desk: { spot: "desk", activity: "search", state: "working" },
    shelf: { spot: "shelf", activity: "search", state: "working" },
    sandbox: { spot: "sandbox", activity: "code", state: "working" },
    console: { spot: "terminal", activity: "code", state: "working" },
    board: { spot: "board", activity: "delegate", state: "working" },
    door: { spot: "door", activity: null, state: "waiting" },
    idle: { spot: "desk", activity: null, state: "idle" },
  };
  let studioWidgetBusy = false;
  let studioWidgetTimer = 0;
  let studioWidgetWebGl = null;

  /** Whether this phone can draw the studio at all. A one-off drawing, not the live backdrop's
   * animation: liveHardware() asks for 8 cores and 8 GB (deviceMemory reports 6 GB as 4), which
   * left most phones' widget empty for good. */
  function studioWidgetCanDraw() {
    if (studioWidgetWebGl === null) {
      try {
        const probe = document.createElement("canvas");
        studioWidgetWebGl = !!(probe.getContext("webgl2") || probe.getContext("webgl"));
      } catch { studioWidgetWebGl = false; }
    }
    return studioWidgetWebGl && typeof window.requestAnimationFrame === "function";
  }

  function studioWidgetLook() {
    const palette = getComputedStyle(document.documentElement);
    return { ...studioLook(), field: [palette.getPropertyValue("--wp-1").trim(), palette.getPropertyValue("--wp-3").trim()] };
  }

  /** One frame of the scene over the backdrop's colours (a widget picture has no transparency). */
  function studioWidgetFrame(scene, look) {
    return new Promise((resolve) => window.requestAnimationFrame(() => {
      // Drawn and read in one go: the canvas does not keep its picture after the page yields.
      const canvas = scene.frame();
      const frame = document.createElement("canvas");
      frame.width = canvas.width;
      frame.height = canvas.height;
      const context = frame.getContext("2d");
      const colour = (value, fallback) => /^\d+ \d+ \d+$/.test(value) ? `rgb(${value.split(" ").join(",")})` : fallback;
      const fill = context.createLinearGradient(0, 0, 0, frame.height);
      fill.addColorStop(0, colour(look.field[0], look.dark ? "#1d2523" : "#e9efec"));
      fill.addColorStop(1, colour(look.field[1], look.dark ? "#141a19" : "#d7e2dd"));
      context.fillStyle = fill;
      context.fillRect(0, 0, frame.width, frame.height);
      context.drawImage(canvas, 0, 0);
      const webp = frame.toDataURL("image/webp", 0.85);
      resolve(webp.startsWith("data:image/webp") ? webp : frame.toDataURL("image/png"));
    }));
  }

  async function drawStudioWidget() {
    studioWidgetTimer = 0;
    if (studioWidgetBusy || disposed || typeof bridge?.studioWidgetState !== "function") return;
    let state;
    try { state = JSON.parse(bridge.studioWidgetState()); } catch { return; }
    const look = studioWidgetLook();
    const version = JSON.stringify({ drawing: studioWidgetDrawing, ...look });
    if (!state.placed || state.version === version) return;
    // Not over a running task or while the app is away; it is tried again later.
    if (!studioWidgetCanDraw()) return;
    if (activeTask || document.visibilityState !== "visible") { queueStudioWidget(30000); return; }
    studioWidgetBusy = true;
    const stage = document.createElement("div");
    stage.className = "studio-widget-stage";
    stage.setAttribute("aria-hidden", "true");
    const overlay = document.createElement("div");
    overlay.className = "studio-overlay";
    stage.append(overlay);
    document.body.append(stage);
    let complete = false;
    try {
      const studio = await loadStudio();
      for (const [pose, place] of Object.entries(studioWidgetPlaces)) {
        if (disposed || activeTask || document.visibilityState !== "visible") break;
        const scene = studio.createStudioScene(stage, overlay, { ...studioLook(), reducedMotion: false, pixelRatio: 2, centered: true },
          { pick() {}, pickFloor() {} }, "backdrop");
        try {
          // The fish tank's fish follow the model in use (the big fat fish for DeepSeek).
          scene.setModel?.(settings.model || null);
          scene.update([{ id: "room", number: "", title: "", summary: "", busy: false,
            cast: [{ id: "lead", name: "AI", lead: true, state: place.state, activity: place.activity, spot: place.spot, look: lookFor("lead"), stateLabel: "" }] }]);
          // Drawn as while someone walks, so the four frames differ; the agent walks to its place and
          // the camera follows first (at most ten seconds).
          scene.exercise(14000);
          const settled = Date.now() + 10000;
          await new Promise((resolve) => setTimeout(resolve, 1200));
          while (!scene.calm() && Date.now() < settled) await new Promise((resolve) => setTimeout(resolve, 250));
          await new Promise((resolve) => setTimeout(resolve, 400));
          const frames = [];
          for (let index = 0; index < 4; index++) {
            frames.push(await studioWidgetFrame(scene, look));
            await new Promise((resolve) => setTimeout(resolve, 180));
          }
          if (!frames.length || !JSON.parse(bridge.saveStudioWidgetFrames(pose, JSON.stringify(frames)) || "{}").ok) break;
          if (pose === "idle") complete = true;
        } finally { scene.dispose(); }
      }
      if (complete) bridge.studioWidgetDrawn(version);
      else queueStudioWidget(30000);
    } catch { /* tried again at the next start */ }
    finally {
      stage.remove();
      studioWidgetBusy = false;
    }
  }

  function queueStudioWidget(delay = 8000) {
    if (studioWidgetTimer || disposed) return;
    studioWidgetTimer = window.setTimeout(() => { void drawStudioWidget(); }, delay);
  }

  // A while after the app has settled, and when it comes back (the widget may have been placed meanwhile).
  queueStudioWidget(12000);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") queueStudioWidget(8000); });
  // Asked to place one (Settings → Global entry): the launcher confirms in its own time.
  window.addEventListener("agent-studio-widget-pinned", () => {
    let looks = 0;
    const look = window.setInterval(() => {
      if (disposed || ++looks > 12) { window.clearInterval(look); return; }
      void drawStudioWidget();
    }, 5000);
  });
