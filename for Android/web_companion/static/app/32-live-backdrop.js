
  // ---- Live backdrop (2.7) ---------------------------------------------------------------------
  // On a capable phone the glass wallpaper's colour fields drift slowly. A small canvas (a sixth of
  // the screen; the browser smooths it up) is redrawn about seven times a second from a timer: a field
  // moves at most two pixels a step across a gradient hundreds of pixels wide, so no step shows, and
  // the page makes no frames in between. (An animation-frame loop kept the WebView drawing at the
  // screen's rate: 84% of a core on a Snapdragon 888; ten steps a second cost 30%.)
  // Nothing is drawn while the page is hidden, while motion is reduced or off, or once the phone has
  // been left alone for a while. If the first seconds show the phone dropping frames, it stays off on
  // this phone until the switch is turned on again.
  const liveCanvas = $("liveBackdrop");
  const liveToggle = $("liveBackdropToggle");
  const liveHint = $("liveBackdropHint");
  const liveSlowKey = "agent-mobile-live-backdrop-slow";
  const liveFieldPresets = new Set(["aurora", "sunset", "ocean", "meadow", "sand", "graphite"]);
  const liveIdleMs = 30000;
  // The four fields of the static template (style.css): centre, radii (share of the screen), and
  // each one's own slow path: periods in seconds and how far it wanders.
  const liveFields = [
    { x: 0, y: 0, rx: 1.1, ry: .62, px: 41, py: 53, ax: .16, ay: .1 },
    { x: 1, y: .22, rx: .95, ry: .55, px: 47, py: 37, ax: .14, ay: .12 },
    { x: 0, y: .8, rx: 1.1, ry: .6, px: 59, py: 43, ax: .15, ay: .1 },
    { x: 1, y: 1, rx: 1.05, ry: .62, px: 37, py: 61, ax: .16, ay: .11 },
  ];
  const liveStepMs = 150;
  let liveTimer = 0;
  let liveColors = null;
  let liveLastTouch = Date.now();
  let liveProbed = false; // the frame check runs once per page load

  let liveHardwareOk = null;
  function liveHardware() {
    if (liveHardwareOk === null) {
      const memory = typeof navigator.deviceMemory === "number" ? navigator.deviceMemory : 8;
      liveHardwareOk = (navigator.hardwareConcurrency || 0) >= 8 && memory >= 6 && typeof window.requestAnimationFrame === "function"
        && !!liveCanvas.getContext?.("2d");
    }
    return liveHardwareOk;
  }

  function liveMotionAllowed() {
    if (preferences.motion === "off" || preferences.motion === "reduced") return false;
    return preferences.motion === "full" || !window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  }

  function liveWanted() {
    const root = document.documentElement;
    return preferences.liveBackdrop !== false && root.dataset.style === "glass" && liveFieldPresets.has(root.dataset.backdrop)
      && !studioBackdropShown() && liveMotionAllowed() && liveHardware() && !readStorage(liveSlowKey, false)
      && document.visibilityState !== "hidden" && Date.now() - liveLastTouch < liveIdleMs;
  }

  function readLiveColors() {
    const style = window.getComputedStyle(document.body);
    const rgb = (name) => style.getPropertyValue(name).trim().split(/\s+/).map(Number).slice(0, 3);
    return {
      base: [rgb("--wp-base-1"), rgb("--wp-base-2")],
      fields: [1, 2, 3, 4].map((index) => rgb(`--wp-${index}`)),
      alpha: Number.parseFloat(style.getPropertyValue("--wp-a")) || .6,
    };
  }

  function drawLive(now) {
    const context = liveCanvas.getContext("2d");
    const { width, height } = liveCanvas;
    const seconds = now / 1000;
    const turn = Math.PI * 2;
    context.setTransform(1, 0, 0, 1, 0, 0);
    // The base: CSS linear-gradient(165deg, ...).
    const dx = Math.sin(165 * Math.PI / 180), dy = -Math.cos(165 * Math.PI / 180);
    const half = (Math.abs(width * dx) + Math.abs(height * dy)) / 2;
    const base = context.createLinearGradient(width / 2 - dx * half, height / 2 - dy * half, width / 2 + dx * half, height / 2 + dy * half);
    base.addColorStop(0, `rgb(${liveColors.base[0].join(", ")})`);
    base.addColorStop(1, `rgb(${liveColors.base[1].join(", ")})`);
    context.fillStyle = base;
    context.fillRect(0, 0, width, height);
    liveFields.forEach((field, index) => {
      const x = (field.x + Math.sin(seconds * turn / field.px + index) * field.ax) * width;
      const y = (field.y + Math.cos(seconds * turn / field.py + index * 1.7) * field.ay) * height;
      const scale = 1 + Math.sin(seconds * turn / (field.px + field.py) + index) * .08;
      // A unit circle stretched to the field's ellipse, fading out at 72% like the static template.
      context.setTransform(field.rx * width * scale, 0, 0, field.ry * height * scale, x, y);
      const colour = liveColors.fields[index].join(", ");
      const gradient = context.createRadialGradient(0, 0, 0, 0, 0, 1);
      gradient.addColorStop(0, `rgba(${colour}, ${liveColors.alpha})`);
      gradient.addColorStop(.72, `rgba(${colour}, 0)`);
      context.fillStyle = gradient;
      context.fillRect(-1, -1, 2, 2);
    });
  }

  function liveTick() {
    liveTimer = 0;
    if (!liveWanted()) { syncLiveBackdrop(); return; }
    drawLive(performance.now());
    liveTimer = window.setTimeout(liveTick, liveStepMs);
  }

  // For three seconds animation frames are counted while it draws: they should come at the screen's
  // rate, and a median gap over 25 ms means the phone cannot keep up.
  function probeLive() {
    const times = [];
    const step = (now) => {
      if (!liveTimer || disposed) return;
      times.push(now);
      if (now - times[0] < 3000) { window.requestAnimationFrame(step); return; }
      const gaps = times.slice(1).map((time, index) => time - times[index]).sort((a, b) => a - b);
      if (gaps.length && gaps[Math.floor(gaps.length / 2)] > 25) {
        writeStorage(liveSlowKey, true);
        syncLiveBackdrop();
      }
    };
    window.requestAnimationFrame(step);
  }

  function syncLiveBackdrop() {
    if (disposed) return;
    const on = liveWanted();
    document.documentElement.dataset.live = on ? "on" : "off";
    if (on) {
      liveColors = readLiveColors();
      const width = Math.max(48, Math.round(window.innerWidth / 6));
      const height = Math.max(96, Math.round(window.innerHeight / 6));
      if (liveCanvas.width !== width || liveCanvas.height !== height) { liveCanvas.width = width; liveCanvas.height = height; }
      if (!liveTimer) {
        drawLive(performance.now());
        liveTimer = window.setTimeout(liveTick, liveStepMs);
        if (!liveProbed) { liveProbed = true; probeLive(); }
      }
    } else if (liveTimer) {
      window.clearTimeout(liveTimer);
      liveTimer = 0;
    }
    renderLiveSetting();
  }

  function renderLiveSetting() {
    const hardware = liveHardware();
    const slow = !!readStorage(liveSlowKey, false);
    liveToggle.disabled = !hardware;
    liveToggle.checked = hardware && !slow && preferences.liveBackdrop !== false;
    liveHint.textContent = !hardware ? t("这台手机的性能不够，不显示动态背景。")
      : slow ? t("这台手机显示动态背景时掉帧，已自动关闭；打开开关可以再试一次。")
      : !liveFieldPresets.has(document.documentElement.dataset.backdrop) ? t("这个背景没有动态效果。")
      : studioBackdropShown() ? t("工作室当背景时，颜色在它后面，不流动。")
      : !liveMotionAllowed() ? t("动画设为精简或关闭时，背景不流动。")
      : t("背景的颜色缓慢流动，耗电略多；一段时间不操作会停下。");
  }

  liveToggle.addEventListener("change", () => {
    preferences.liveBackdrop = liveToggle.checked;
    if (liveToggle.checked) { writeStorage(liveSlowKey, false); liveProbed = false; }
    writeStorage(settingsKey, preferences);
    liveLastTouch = Date.now();
    syncLiveBackdrop();
  });
  // A touch wakes it after the idle stop.
  for (const type of ["pointerdown", "keydown", "wheel"]) {
    window.addEventListener(type, () => {
      liveLastTouch = Date.now();
      if (!liveTimer && liveWanted()) syncLiveBackdrop();
    }, { capture: true, passive: true });
  }
  document.addEventListener("visibilitychange", () => { liveLastTouch = Date.now(); syncLiveBackdrop(); });
  window.addEventListener("resize", () => { if (liveTimer) syncLiveBackdrop(); });
  window.matchMedia?.("(prefers-color-scheme: dark)")?.addEventListener?.("change", () => syncLiveBackdrop());
  window.matchMedia?.("(prefers-reduced-motion: reduce)")?.addEventListener?.("change", () => syncLiveBackdrop());
