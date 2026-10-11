/* Motion for the console: spring timing, enter/exit, list reflow, sparks and drag-to-dismiss.
   Everything here only moves transform and opacity, so the compositor animates it off the main
   thread. The app's motion setting decides how much runs: full, reduced (short fades, nothing
   travels) or off (no animation); "auto" follows the system's reduce-motion setting. Without
   this script the console works the same, only without motion (callers check for it). */
(function () {
  "use strict";

  const root = document.documentElement;
  const reduceQuery = typeof window.matchMedia === "function" ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;

  function level() {
    const setting = root.dataset.motion || "auto";
    if (setting === "off") return "off";
    if (setting === "reduced" || (setting === "auto" && reduceQuery && reduceQuery.matches)) return "reduced";
    return "full";
  }

  // ---- Springs --------------------------------------------------------------------------------
  // A damped spring sampled into CSS linear() points, so CSS and Web Animations share one curve.
  // WebViews older than Chromium 113 lack linear(): they get a close cubic-bezier instead.
  const supportsLinear = !!(window.CSS && CSS.supports && CSS.supports("animation-timing-function", "linear(0, 1)"));

  function sampleSpring(stiffness, damping, mass) {
    const w0 = Math.sqrt(stiffness / mass);
    const zeta = damping / (2 * Math.sqrt(stiffness * mass));
    const position = (t) => {
      if (zeta < 1) {
        const wd = w0 * Math.sqrt(1 - zeta * zeta);
        return 1 - Math.exp(-zeta * w0 * t) * (Math.cos(wd * t) + (zeta * w0 / wd) * Math.sin(wd * t));
      }
      return 1 - Math.exp(-w0 * t) * (1 + w0 * t);
    };
    let settle = 0.12;
    for (let t = 0; t < 3; t += 0.004) if (Math.abs(1 - position(t)) > 0.0015) settle = t;
    const points = [];
    const count = 40;
    for (let index = 0; index <= count; index += 1) points.push(Number(position((settle * index) / count).toFixed(4)));
    points[count] = 1;
    return { linear: `linear(${points.join(", ")})`, duration: Math.round(settle * 1000) };
  }

  const fallbackCurves = {
    snappy: "cubic-bezier(.2, .9, .3, 1)",
    bouncy: "cubic-bezier(.3, 1.45, .55, 1)",
    gentle: "cubic-bezier(.25, .8, .25, 1)",
  };
  const springs = {};
  for (const [name, stiffness, damping] of [["snappy", 520, 42], ["bouncy", 340, 21], ["gentle", 190, 26]]) {
    const sampled = sampleSpring(stiffness, damping, 1);
    springs[name] = {
      easing: supportsLinear ? sampled.linear : fallbackCurves[name],
      duration: supportsLinear ? sampled.duration : Math.min(sampled.duration, 420),
    };
    root.style.setProperty(`--spring-${name}`, springs[name].easing);
    root.style.setProperty(`--spring-${name}-ms`, `${springs[name].duration}ms`);
  }

  // ---- Playing animations ----------------------------------------------------------------------
  const running = new WeakMap();
  const active = new Set();

  // Glass panels switch to their cheaper filter while something moves (liquid-glass.js listens).
  function report(milliseconds) {
    try { document.dispatchEvent(new CustomEvent("agent-motion", { detail: milliseconds })); } catch (error) { /* no CustomEvent */ }
  }

  // A finished animation that fills forwards keeps its last frame on the element; it stays listed
  // until stop() or the next play() on that element cancels it, or it would come back into
  // effect as soon as a later animation of the element ends (a reopened sheet jumping away).
  function track(element, animation, holds) {
    const entry = { element, animation };
    active.add(entry);
    const forget = () => active.delete(entry);
    if (!holds) animation.addEventListener("finish", forget);
    animation.addEventListener("cancel", forget);
    return animation;
  }

  /** Cancels this script's animations on an element and everything inside it. */
  function stop(container) {
    for (const entry of Array.from(active)) {
      if (entry.element === container || (container && container.contains(entry.element))) entry.animation.cancel();
    }
  }

  function release(element) {
    for (const entry of Array.from(active)) if (entry.element === element) entry.animation.cancel();
  }

  function onlyOpacity(keyframes) {
    return keyframes.map((frame) => ({ opacity: frame.opacity === undefined ? 1 : frame.opacity, offset: frame.offset }));
  }

  /** Animates and resolves when done (also when motion is off: then immediately). */
  function play(element, keyframes, options) {
    const settings = Object.assign({ spring: "snappy" }, options || {});
    const mode = level();
    if (!element || typeof element.animate !== "function" || mode === "off") return Promise.resolve(null);
    const spring = springs[settings.spring] || springs.snappy;
    const reduced = mode === "reduced";
    const frames = reduced ? onlyOpacity(keyframes) : keyframes;
    if (reduced && frames.every((frame) => frame.opacity === 1)) return Promise.resolve(null);
    if (settings.replace !== false) release(element);
    const timing = {
      duration: reduced ? Math.min(160, settings.duration || 160) : (settings.duration || spring.duration),
      easing: reduced ? "ease-out" : (settings.easing || spring.easing),
      delay: reduced ? 0 : (settings.delay || 0),
      fill: settings.fill || "backwards",
    };
    const animation = track(element, element.animate(frames, timing), timing.fill === "forwards" || timing.fill === "both");
    running.set(element, animation);
    report(timing.duration + timing.delay);
    return new Promise((resolve) => {
      const done = () => { if (running.get(element) === animation) running.delete(element); resolve(animation); };
      animation.addEventListener("finish", done);
      animation.addEventListener("cancel", done);
    });
  }

  /** Shows a hidden element and plays it in from `from` (a keyframe). */
  function enter(element, from, options) {
    if (!element) return Promise.resolve(null);
    element.hidden = false;
    delete element.dataset.leaving;
    return play(element, [Object.assign({ opacity: 0 }, from || {}), { opacity: 1, transform: "none" }], options);
  }

  /** Plays an element out to `to`, then hides it. A later enter() cancels the exit. */
  function exit(element, to, options) {
    if (!element || element.hidden) return Promise.resolve(null);
    element.dataset.leaving = "true";
    const settings = Object.assign({ fill: "forwards", spring: "snappy" }, options || {});
    if (!settings.duration) settings.duration = Math.min(springs[settings.spring || "snappy"].duration, 240);
    if (!settings.easing) settings.easing = "cubic-bezier(.4, 0, 1, 1)";
    return play(element, [{ opacity: 1, transform: "none" }, Object.assign({ opacity: 0 }, to || {})], settings).then((animation) => {
      if (element.dataset.leaving === "true") {
        element.hidden = true;
        delete element.dataset.leaving;
      }
      if (animation) animation.cancel();
      return animation;
    });
  }

  /** FLIP: measure, change the DOM, then slide every element from where it was. */
  function reflow(elements, change, options) {
    const items = Array.from(elements || []);
    const before = new Map(items.map((item) => [item, item.getBoundingClientRect()]));
    change();
    if (level() !== "full") return;
    for (const item of items) {
      if (!item.isConnected) continue;
      const was = before.get(item);
      const now = item.getBoundingClientRect();
      const dx = was.left - now.left;
      const dy = was.top - now.top;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue;
      play(item, [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }], Object.assign({ spring: "snappy", replace: false }, options || {}));
    }
  }

  /** Plays the same entrance on several elements, one after another. */
  function stagger(elements, from, options) {
    const settings = Object.assign({ step: 35, spring: "bouncy" }, options || {});
    Array.from(elements || []).forEach((element, index) => {
      play(element, [Object.assign({ opacity: 0 }, from), { opacity: 1, transform: "none" }],
        Object.assign({}, settings, { delay: (settings.delay || 0) + index * settings.step }));
    });
  }

  // ---- Sparks ----------------------------------------------------------------------------------
  /** A one-shot burst of small glowing dots from an element (the effort slider's top level). */
  function sparks(origin, options) {
    if (!origin || level() !== "full" || typeof origin.animate !== "function") return;
    const settings = Object.assign({ count: 16, colors: ["#a78bfa", "#60a5fa", "#22d3ee", "#34d399", "#fbbf24", "#f472b6"], spread: 70 }, options || {});
    const box = origin.getBoundingClientRect();
    const layer = document.createElement("div");
    layer.className = "motion-sparks";
    layer.setAttribute("aria-hidden", "true");
    layer.style.left = `${box.left + box.width / 2}px`;
    layer.style.top = `${box.top + box.height / 2}px`;
    document.body.appendChild(layer);
    let remaining = settings.count;
    for (let index = 0; index < settings.count; index += 1) {
      const dot = document.createElement("span");
      const color = settings.colors[index % settings.colors.length];
      const size = 3 + Math.random() * 4;
      dot.style.width = dot.style.height = `${size}px`;
      dot.style.background = color;
      dot.style.boxShadow = `0 0 ${size * 2}px ${color}`;
      layer.appendChild(dot);
      const angle = (Math.PI * 2 * index) / settings.count + Math.random() * 0.5;
      const distance = settings.spread * (0.45 + Math.random() * 0.55);
      const x = Math.cos(angle) * distance;
      const y = Math.sin(angle) * distance - 12;
      const animation = dot.animate([
        { transform: "translate(-50%, -50%) scale(.4)", opacity: 0 },
        { transform: `translate(calc(-50% + ${x * 0.55}px), calc(-50% + ${y * 0.55}px)) scale(1.15)`, opacity: 1, offset: 0.3 },
        { transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y + 14}px)) scale(.3)`, opacity: 0 },
      ], { duration: 700 + Math.random() * 350, easing: "cubic-bezier(.15, .7, .3, 1)", fill: "forwards" });
      animation.onfinish = () => { remaining -= 1; if (remaining <= 0) layer.remove(); };
    }
    report(1100);
  }

  // ---- Drag to dismiss ------------------------------------------------------------------------
  /** Lets a panel follow a finger along one axis and dismiss on a long or fast drag.
      axis "y": drag down to close (sheets); "x-": drag left to close (the drawer). */
  function draggable(panel, options) {
    const settings = Object.assign({ axis: "y", handle: panel, threshold: 0.32, onDismiss() {}, extras: [] }, options || {});
    if (!panel || !settings.handle) return () => {};
    const sign = settings.axis === "x-" ? -1 : 1;
    const horizontal = settings.axis !== "y";
    let start = null;
    let samples = [];
    let offset = 0;
    let dragging = false;

    function size() { return horizontal ? panel.offsetWidth : panel.offsetHeight; }
    function apply(value) {
      panel.style.transform = value ? (horizontal ? `translateX(${value}px)` : `translateY(${value}px)`) : "";
      for (const extra of settings.extras) extra.style.opacity = value ? String(Math.max(0, 1 - Math.abs(value) / size())) : "";
    }
    // Finger speed over the last ~80 ms, in px per ms.
    function velocity() {
      const latest = samples[samples.length - 1];
      const earlier = samples.find((sample) => latest.time - sample.time <= 80) || latest;
      return latest.time > earlier.time ? (latest.value - earlier.value) / (latest.time - earlier.time) : 0;
    }
    function down(event) {
      if (event.button !== undefined && event.button !== 0) return;
      if (settings.canStart && !settings.canStart(event)) return;
      start = { x: event.clientX, y: event.clientY, time: event.timeStamp };
      samples = [{ value: 0, time: event.timeStamp }];
      dragging = false;
      offset = 0;
    }
    function move(event) {
      if (!start) return;
      const dx = event.clientX - start.x;
      const dy = event.clientY - start.y;
      const along = horizontal ? dx : dy;
      const across = horizontal ? dy : dx;
      if (!dragging) {
        if (Math.abs(along) < 8 || Math.abs(along) < Math.abs(across) * 1.2 || along * sign <= 0) {
          if (Math.abs(across) > 12) start = null;
          return;
        }
        dragging = true;
        panel.dataset.dragging = "true";
        stop(panel);
        try { settings.handle.setPointerCapture(event.pointerId); } catch (error) { /* already released */ }
      }
      // Past the closed edge the panel follows; pulled the other way it resists.
      offset = along * sign > 0 ? along : along * 0.2;
      apply(offset);
      samples.push({ value: offset, time: event.timeStamp });
      if (samples.length > 12) samples.shift();
      report(120);
      if (event.cancelable) event.preventDefault();
    }
    function up(event) {
      if (!start) return;
      const wasDragging = dragging;
      start = null;
      dragging = false;
      delete panel.dataset.dragging;
      if (!wasDragging) return;
      const speed = event.type === "pointercancel" ? 0 : velocity();
      const far = Math.abs(offset) > size() * settings.threshold;
      const flung = speed * sign > 0.5;
      const from = horizontal ? `translateX(${offset}px)` : `translateY(${offset}px)`;
      if ((far || flung) && offset * sign > 0 && !(speed * sign < -0.3)) {
        const to = horizontal ? `translateX(${sign * size()}px)` : `translateY(${size()}px)`;
        const fading = Math.max(0, 1 - Math.abs(offset) / size());
        apply(0);
        // Keep the finger's speed: the rest of the way takes as long as it would at that speed.
        const duration = Math.max(140, Math.min(300, (size() - Math.abs(offset)) / Math.max(Math.abs(speed), 1.1)));
        const animation = level() === "off" || typeof panel.animate !== "function" ? null
          : track(panel, panel.animate([{ transform: from }, { transform: to }], { duration, easing: "cubic-bezier(.25, .7, .4, 1)", fill: "forwards" }), true);
        if (animation) report(duration);
        for (const extra of settings.extras) {
          if (animation) track(extra, extra.animate([{ opacity: fading }, { opacity: 0 }], { duration, easing: "ease-out", fill: "forwards" }), true);
        }
        const finish = () => {
          settings.onDismiss();
          release(panel);
          for (const extra of settings.extras) release(extra);
        };
        if (animation) animation.addEventListener("finish", finish); else finish();
      } else {
        apply(0);
        play(panel, [{ transform: from }, { transform: "none" }], { spring: "bouncy" });
        for (const extra of settings.extras) extra.style.opacity = "";
      }
      if (event && event.cancelable) event.preventDefault();
    }
    const handle = settings.handle;
    handle.addEventListener("pointerdown", down);
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", up);
    handle.addEventListener("pointercancel", up);
    return () => {
      handle.removeEventListener("pointerdown", down);
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", up);
      handle.removeEventListener("pointercancel", up);
    };
  }

  window.MobileMotion = { level, springs, play, stop, enter, exit, reflow, stagger, sparks, draggable };
})();
