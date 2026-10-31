
  // ---- The studio behind the conversation (2.7) ---------------------------------------------------
  // Under liquid glass the conversation's studio (29-team.js, the desktop app's studio) is the
  // backdrop: the agent at work in its room, its experts and sub-agents with it, dimmed so the text on
  // the glass stays readable. The scene draws a small picture (three quarters of a CSS pixel), 18 frames
  // a second only while someone walks, one a second while they work, and nothing once all is still,
  // while the app is away or the studio is shown in its own sheet. The studio button shows it in full:
  // the app steps aside and the room can be turned and its people tapped.
  // Only on a capable phone (the live backdrop's test) and over the colour-field backgrounds; without
  // WebGL, or if the scene fails, the colour field stays for this run; a phone whose frames fall
  // behind while the studio draws (probeStudio) keeps the colour field until the switch is turned on again.
  const studioBackdropHost = $("studioBackdrop");
  const studioBackdropToggle = $("studioBackdropToggle");
  const studioBackdropHint = $("studioBackdropHint");
  const studioBackdropPresets = new Set(["aurora", "sunset", "ocean", "meadow", "sand", "dusk", "graphite"]);
  const studioSlowKey = "agent-mobile-studio-backdrop-slow";
  // three.js loads once the app has painted and settled; the colour field shows until then.
  const studioBackdropDelayMs = 1500;
  // The frame check starts a moment after the first picture and draws for three seconds.
  const studioProbeDelayMs = 1000;
  const studioProbeMs = 3000;
  let backdropScene = null;
  let backdropLoading = false;
  let backdropFailed = false;
  let backdropTimer = 0;
  let backdropLook = "";
  let studioViewing = false;
  let studioProbed = false; // the frame check runs once per page load

  function studioBackdropWanted() {
    const root = document.documentElement;
    return preferences.studioBackdrop !== false && root.dataset.style === "glass" && studioBackdropPresets.has(root.dataset.backdrop)
      && !elderShown() && liveHardware() && !backdropFailed && !readStorage(studioSlowKey, false);
  }

  /** The studio is behind the conversation now (drawn, not only wanted). */
  function studioBackdropShown() { return !!backdropScene && studioBackdropWanted(); }

  function dropBackdrop() {
    window.clearTimeout(backdropTimer);
    backdropTimer = 0;
    if (studioViewing) closeStudio();
    backdropScene?.dispose();
    backdropScene = null;
    studioBackdropHost.dataset.ready = "false";
    $("studioBackdropOverlay").replaceChildren();
  }

  function syncStudioBackdrop() {
    if (disposed) return;
    const on = studioBackdropWanted();
    studioBackdropHost.hidden = !on;
    if (!on) dropBackdrop();
    else {
      // Light or dark, the accent or motion changed: the room is built anew with them.
      if (backdropScene && JSON.stringify(studioLook()) !== backdropLook) dropBackdrop();
      if (!backdropScene && !backdropLoading && !backdropTimer) backdropTimer = window.setTimeout(startBackdrop, studioBackdropDelayMs);
    }
    document.documentElement.dataset.studioBackdrop = studioBackdropShown() ? "on" : "off";
    renderStudioBackdropSetting();
  }

  async function startBackdrop() {
    backdropTimer = 0;
    if (disposed || backdropScene || backdropLoading || !studioBackdropWanted()) return;
    backdropLoading = true;
    try {
      // The experts' names, when the conversation may call its team.
      if (teamSettings.on) await loadExpertCatalog().catch(() => null);
      const studio = await loadStudio();
      if (disposed || !studioBackdropWanted()) return;
      const look = studioLook();
      backdropLook = JSON.stringify(look);
      backdropScene = studio.createStudioScene($("studioBackdropStage"), $("studioBackdropOverlay"), look, { pick: studioPick, pickFloor: () => {} }, "backdrop");
    } catch {
      // No WebGL, or the scene failed: the colour field for this run.
      backdropFailed = true;
      backdropScene = null;
    } finally {
      backdropLoading = false;
    }
    if (backdropScene) {
      studioSignature = "";
      refreshStudio();
      // The first picture fades in once it is drawn.
      window.requestAnimationFrame(() => { studioBackdropHost.dataset.ready = String(!!backdropScene); });
      if (!studioProbed) { studioProbed = true; window.setTimeout(probeStudio, studioProbeDelayMs); }
    }
    syncStudioBackdrop();
    // The colour field's drift stops under the studio, and starts again without it.
    syncLiveBackdrop();
  }

  // For three seconds the studio draws as while someone walks and animation frames are counted: they
  // should come at the screen's rate, and a median gap over 25 ms means the phone cannot keep up (the
  // glass over the studio is drawn again with each of its pictures). A check cut short by the app going
  // away gives no verdict; the next start checks again.
  function probeStudio() {
    const scene = backdropScene;
    if (!scene || disposed || document.visibilityState === "hidden") { studioProbed = false; return; }
    scene.exercise(studioProbeMs);
    const times = [];
    const step = (now) => {
      if (scene !== backdropScene || disposed) return;
      times.push(now);
      if (now - times[0] < studioProbeMs) { window.requestAnimationFrame(step); return; }
      const gaps = times.slice(1).map((time, index) => time - times[index]).sort((a, b) => a - b);
      if (document.visibilityState === "hidden" || gaps[gaps.length - 1] > 1000) { studioProbed = false; return; }
      if (gaps.length && gaps[Math.floor(gaps.length / 2)] > 25) {
        writeStorage(studioSlowKey, true);
        syncStudioBackdrop();
        syncLiveBackdrop();
      }
    };
    window.requestAnimationFrame(step);
  }

  /** Shown in full (the studio sheet over it) or back behind the conversation. */
  function viewStudioBackdrop(viewing) {
    if (!backdropScene) return;
    studioViewing = viewing;
    studioBackdropHost.dataset.viewing = String(viewing);
    studioBackdropHost.setAttribute("aria-hidden", String(!viewing));
    document.documentElement.dataset.studioView = String(viewing);
    backdropScene.setMode(viewing ? "room" : "backdrop");
  }

  function renderStudioBackdropSetting() {
    const hardware = liveHardware();
    const slow = !!readStorage(studioSlowKey, false);
    studioBackdropToggle.disabled = !hardware || backdropFailed;
    studioBackdropToggle.checked = hardware && !backdropFailed && !slow && preferences.studioBackdrop !== false;
    studioBackdropHint.textContent = !hardware ? t("这台手机的性能不够，不显示工作室。")
      : backdropFailed ? t("这台手机无法显示 3D 工作室（WebGL 不可用）。")
      : slow ? t("这台手机显示工作室背景时掉帧，已换回颜色背景；打开开关可以再试一次。")
      : !studioBackdropPresets.has(document.documentElement.dataset.backdrop) ? t("自定义壁纸和纯色背景上不显示工作室。")
      : t("聊天背后是 3D 工作室，AI 的动作跟着任务走。任务进行中耗电略多，没有任务时画面静止。");
  }

  studioBackdropToggle.addEventListener("change", () => {
    preferences.studioBackdrop = studioBackdropToggle.checked;
    if (studioBackdropToggle.checked) { writeStorage(studioSlowKey, false); studioProbed = false; }
    writeStorage(settingsKey, preferences);
    syncStudioBackdrop();
    syncLiveBackdrop();
  });
  window.matchMedia?.("(prefers-color-scheme: dark)")?.addEventListener?.("change", () => syncStudioBackdrop());
  window.matchMedia?.("(prefers-reduced-motion: reduce)")?.addEventListener?.("change", () => syncStudioBackdrop());
