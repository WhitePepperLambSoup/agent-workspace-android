/* Liquid glass refraction for the "glass" appearance style.
   Apple's Liquid Glass reads as glass through lensing: content under the curved rim is bent.
   CSS blur alone cannot bend light, so each glass surface gets an SVG filter used as
   backdrop-filter: url(#...) (Chromium, i.e. Android WebView). The filter displaces the backdrop
   with a map computed from a convex-squircle bezel and Snell's law, adds a little frost and
   saturation, and paints a specular rim. Elsewhere the CSS frosted fallback stays in place.
   Technique after kube.io "Liquid Glass in the browser: refraction with CSS and SVG". */
(function () {
  "use strict";

  const root = document.documentElement;
  const SVG_NS = "http://www.w3.org/2000/svg";
  const REFRACTIVE_INDEX = 1.5;
  // Surfaces that float over the conversation. Larger panels get a wider bezel. Large panels skip the
  // dispersive filter: on a big surface it is barely visible, and switching filters is itself costly.
  const SURFACES = [
    { selector: "#mobileHeader", bezel: 24, scale: 64, frost: 1.2 },

    { selector: ".composer", bezel: 26, scale: 64, frost: 1.5 },
    { selector: "#btnJumpLatest", bezel: 18, scale: 40, frost: 0.4 },
    { selector: "#taskStatusBar", bezel: 14, scale: 30, frost: 0.8 },
    { selector: ".chip", bezel: 20, scale: 44, frost: 0.8 },
    { selector: "#approvalShelf", bezel: 22, scale: 44, frost: 12, dispersion: false },
    { selector: ".empty-state", bezel: 24, scale: 50, frost: 8, dispersion: false },
    { selector: "#sessionDrawerPanel", bezel: 28, scale: 60, frost: 16, dispersion: false },
    { selector: "#settingsSheet", bezel: 28, scale: 60, frost: 16, dispersion: false },
  ];

  function refractionAvailable() {
    try {
      const canvas = document.createElement("canvas");
      if (!canvas.getContext || !canvas.getContext("2d")) return false;
      // Only Chromium renders SVG filters inside backdrop-filter; Safari and Firefox paint nothing.
      return /\bChrome\/\d+/.test(navigator.userAgent) && !/Firefox\//.test(navigator.userAgent)
        && typeof CSS !== "undefined" && CSS.supports("backdrop-filter", "url(#x)");
    } catch { return false; }
  }
  if (!refractionAvailable()) return;

  // ---- Optics: how far light bends across the bezel (0 = outer edge, 1 = flat top). ----
  const height = (t) => Math.pow(1 - Math.pow(1 - t, 4), 0.25); // convex squircle
  const PROFILE = (() => {
    const samples = 256;
    const values = new Float32Array(samples);
    let max = 0;
    for (let index = 0; index < samples; index++) {
      const t = Math.min(0.999, Math.max(0.001, index / (samples - 1)));
      const slope = (height(Math.min(1, t + 0.001)) - height(Math.max(0, t - 0.001))) / 0.002;
      const incidence = Math.atan(slope); // surface tilt seen by a vertical ray
      const refracted = Math.asin(Math.sin(incidence) / REFRACTIVE_INDEX);
      const deviation = Math.tan(incidence - refracted) * (1 - height(t) * 0.35);
      values[index] = deviation;
      max = Math.max(max, deviation);
    }
    for (let index = 0; index < samples; index++) values[index] /= max || 1;
    return values;
  })();
  const profileAt = (t) => PROFILE[Math.min(PROFILE.length - 1, Math.max(0, Math.round(t * (PROFILE.length - 1))))];

  // Signed distance to a rounded rectangle and its outward normal at (x, y).
  function edge(x, y, width, height, radius) {
    const qx = Math.abs(x - width / 2) - (width / 2 - radius);
    const qy = Math.abs(y - height / 2) - (height / 2 - radius);
    const sx = x < width / 2 ? -1 : 1;
    const sy = y < height / 2 ? -1 : 1;
    if (qx > 0 && qy > 0) {
      const length = Math.hypot(qx, qy);
      return { distance: radius - length, nx: (qx / length) * sx, ny: (qy / length) * sy };
    }
    if (qx > qy) return { distance: radius - qx, nx: sx, ny: 0 };
    return { distance: radius - qy, nx: 0, ny: sy };
  }

  // ---- Maps ----
  // Only the rim band can differ from neutral: beyond max(bezel, radius) from every edge the glass is
  // flat, so the interior is filled in one step and the per-pixel optics run on the band alone.
  function rimPixels(pixelsWide, pixelsHigh, density, margin, visit) {
    const band = Math.min(Math.ceil(margin * density) + 1, Math.ceil(pixelsWide / 2), Math.ceil(pixelsHigh / 2));
    for (let row = 0; row < pixelsHigh; row++) {
      const fullRow = row < band || row >= pixelsHigh - band;
      for (let column = 0; column < pixelsWide; column++) {
        if (!fullRow && column >= band && column < pixelsWide - band) { column = pixelsWide - band - 1; continue; }
        visit(row, column);
      }
    }
  }

  // The displacement map is smooth, so 1x is enough; the specular line is drawn at up to 2x to stay crisp.
  function drawMaps(width, height, radius, bezel) {
    const margin = Math.max(bezel, radius);
    const displacementCanvas = document.createElement("canvas");
    displacementCanvas.width = width;
    displacementCanvas.height = height;
    const displacementContext = displacementCanvas.getContext("2d");
    const displacement = displacementContext.createImageData(width, height);
    new Uint32Array(displacement.data.buffer).fill(0xff808080); // r = g = b = 128, a = 255: no bend
    rimPixels(width, height, 1, margin, (row, column) => {
      const { distance, nx, ny } = edge(column + 0.5, row + 0.5, width, height, radius);
      if (distance < 0 || distance >= bezel) return;
      // Sample inward (towards the centre): the backdrop only exists under the element.
      const magnitude = profileAt(distance / bezel);
      const offset = (row * width + column) * 4;
      displacement.data[offset] = 128 - nx * magnitude * 127;
      displacement.data[offset + 1] = 128 - ny * magnitude * 127;
    });
    displacementContext.putImageData(displacement, 0, 0);

    const density = Math.min(2, Math.max(1, window.devicePixelRatio || 1));
    const pixelsWide = Math.round(width * density);
    const pixelsHigh = Math.round(height * density);
    const specularCanvas = document.createElement("canvas");
    specularCanvas.width = pixelsWide;
    specularCanvas.height = pixelsHigh;
    const specularContext = specularCanvas.getContext("2d");
    const specular = specularContext.createImageData(pixelsWide, pixelsHigh);
    const light = { x: -0.6, y: -0.8 }; // from the top left, like Apple's highlight
    // Highlights gather at the corner facing the light and its opposite, fading along the edges,
    // so the rim never reads as a uniform outline.
    const reach = Math.max(height * 2.2, width * 0.6);
    const corner = (x, y) => Math.max(0, 1 - Math.hypot(x, y) / reach) ** 1.6;
    rimPixels(pixelsWide, pixelsHigh, density, margin, (row, column) => {
      const x = (column + 0.5) / density, y = (row + 0.5) / density;
      const { distance, nx, ny } = edge(x, y, width, height, radius);
      if (distance < 0 || distance >= bezel) return;
      // A crisp line on the very edge plus a soft sheen down the curved bezel, both strongest where
      // the surface faces the light and near the lit corner.
      const facing = nx * light.x + ny * light.y;
      const line = Math.exp(-distance / 0.9);
      const sheen = Math.max(0, 1 - distance / (bezel * 0.75)) ** 2;
      const lit = Math.max(0, facing) * (0.35 + 0.65 * corner(x, y));
      const back = Math.max(0, -facing) * corner(width - x, height - y);
      const alpha = lit * (line + sheen * 0.32) + back * (line * 0.7 + sheen * 0.16);
      if (alpha <= 0) return;
      specular.data.set([255, 255, 255, Math.round(Math.min(1, alpha) * 255)], (row * pixelsWide + column) * 4);
    });
    specularContext.putImageData(specular, 0, 0);
    return { displacementCanvas, specularCanvas };
  }

  // PNG encoding is the slow part of a rebuild; toBlob does it off the main thread where available.
  function encode(canvas) {
    if (typeof canvas.toBlob !== "function" || typeof FileReader !== "function") return Promise.resolve(canvas.toDataURL("image/png"));
    return new Promise((resolve) => {
      canvas.toBlob((blob) => {
        if (!blob) { resolve(canvas.toDataURL("image/png")); return; }
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => resolve(canvas.toDataURL("image/png"));
        reader.readAsDataURL(blob);
      }, "image/png");
    });
  }

  // Elements of the same size and shape (the four suggestion cards) share one pair of maps.
  const mapCache = new Map();
  function maps(width, height, radius, bezel) {
    const key = `${width}x${height}r${radius}b${bezel}d${window.devicePixelRatio || 1}`;
    if (!mapCache.has(key)) {
      const { displacementCanvas, specularCanvas } = drawMaps(width, height, radius, bezel);
      const pending = Promise.all([encode(displacementCanvas), encode(specularCanvas)])
        .then(([displacementUrl, specularUrl]) => ({ displacementUrl, specularUrl }));
      mapCache.set(key, pending);
      if (mapCache.size > 24) mapCache.delete(mapCache.keys().next().value);
    }
    return mapCache.get(key);
  }

  // ---- SVG filters ----
  // Each surface gets two filters over the same map. The rich one bends red, green and blue by slightly
  // different amounts (dispersion); it costs three displacement passes, so it is used only while the
  // page is still, when nothing is redrawn. While content moves, the single-pass filter takes over.
  // Frost and saturation are CSS filter functions around the url(), and the highlight is a static image
  // over the surface, so neither is recomputed per frame.
  const defs = document.createElementNS(SVG_NS, "svg");
  defs.setAttribute("aria-hidden", "true");
  defs.setAttribute("width", "0");
  defs.setAttribute("height", "0");
  defs.style.cssText = "position:absolute;width:0;height:0;overflow:hidden;pointer-events:none";
  document.body.appendChild(defs);
  const state = new WeakMap();
  let sequence = 0;

  function node(name, attributes) {
    const element = document.createElementNS(SVG_NS, name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
    return element;
  }

  function filters(id, width, height, displacementUrl, scale, dispersion) {
    const frame = { x: 0, y: 0, width, height, filterUnits: "userSpaceOnUse", "color-interpolation-filters": "sRGB" };
    const map = () => node("feImage", { href: displacementUrl, x: 0, y: 0, width, height, preserveAspectRatio: "none", result: "map" });
    const plain = node("filter", { id, ...frame });
    plain.append(map(), node("feDisplacementMap", { in: "SourceGraphic", in2: "map", scale, xChannelSelector: "R", yChannelSelector: "G" }));
    if (!dispersion) return [plain];
    const rich = node("filter", { id: `${id}-rich`, ...frame });
    rich.append(
      map(),
      ...[["red", 1, "1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0"], ["green", 0.93, "0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0"],
        ["blue", 0.86, "0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0"]].flatMap(([channel, ratio, matrix]) => [
        node("feDisplacementMap", { in: "SourceGraphic", in2: "map", scale: scale * ratio, xChannelSelector: "R", yChannelSelector: "G", result: `${channel}-bent` }),
        node("feColorMatrix", { in: `${channel}-bent`, type: "matrix", values: matrix, result: channel }),
      ]),
      node("feBlend", { in: "red", in2: "green", mode: "screen", result: "red-green" }),
      node("feBlend", { in: "red-green", in2: "blue", mode: "screen" }),
    );
    return [plain, rich];
  }

  function build(element, surface) {
    const width = Math.round(element.offsetWidth);
    const height = Math.round(element.offsetHeight);
    if (width < 8 || height < 8) return Promise.resolve();
    const record = state.get(element) || { id: `liquid-glass-${++sequence}` };
    state.set(element, record);
    if (record.width === width && record.height === height) return record.ready || Promise.resolve();
    record.width = width;
    record.height = height;
    const radius = Math.min(parseFloat(getComputedStyle(element).borderTopLeftRadius) || 0, width / 2, height / 2);
    const bezel = Math.max(4, Math.min(surface.bezel, radius || surface.bezel, width / 2, height / 2));
    const token = (record.token || 0) + 1;
    record.token = token;
    record.ready = maps(width, height, Math.max(radius, 1), bezel).then(({ displacementUrl, specularUrl }) => {
      if (record.token !== token) return; // a newer size superseded this one
      const dispersion = surface.dispersion !== false;
      const created = filters(record.id, width, height, displacementUrl, surface.scale, dispersion);
      record.filters?.forEach((filter) => filter.remove());
      defs.append(...created);
      record.filters = created;
      element.style.setProperty("--liquid-glass-filter", `url(#${record.id})`);
      element.style.setProperty("--liquid-glass-moving", `blur(${surface.frost}px) url(#${record.id}) saturate(180%)`);
      element.style.setProperty("--liquid-glass-still", `blur(${surface.frost}px) url(#${record.id}${dispersion ? "-rich" : ""}) saturate(180%)`);
      element.style.setProperty("--liquid-glass-specular", `url("${specularUrl}")`);
    });
    return record.ready;
  }

  // Size changes arrive in bursts (the composer grows while typing, panels animate open); rebuild once
  // they settle instead of on every frame.
  const dirty = new Set();
  let rebuildTimer = 0;
  function scheduleRebuild(element) {
    dirty.add(element);
    clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(() => {
      if (!active()) { dirty.clear(); return; }
      for (const target of dirty) {
        if (!target.isConnected) { resize?.unobserve(target); observed.delete(target); continue; }
        const surface = SURFACES.find((candidate) => target.matches(candidate.selector));
        if (surface) build(target, surface);
      }
      dirty.clear();
    }, 80);
  }
  const observed = new Set();
  const resize = typeof ResizeObserver === "function"
    ? new ResizeObserver((entries) => { for (const entry of entries) scheduleRebuild(entry.target); })
    : null;

  // ---- Motion: single-pass filter while anything moves, the rich one once the page is still ----
  let idleTimer = 0;
  let transitions = 0;
  function settle() {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      transitions = 0; // a transition whose element was removed never reports its end
      delete root.dataset.glassMoving;
    }, transitions > 0 ? 1500 : 200);
  }
  function moving() {
    if (root.dataset.glassMoving !== "true") root.dataset.glassMoving = "true";
    settle();
  }
  document.addEventListener("scroll", moving, { capture: true, passive: true });
  document.addEventListener("touchmove", moving, { capture: true, passive: true });
  document.addEventListener("transitionrun", () => { transitions += 1; moving(); }, true);
  for (const type of ["transitionend", "transitioncancel"]) {
    document.addEventListener(type, () => { transitions = Math.max(0, transitions - 1); if (transitions === 0) settle(); }, true);
  }
  function active() {
    return root.dataset.style === "glass" && !root.classList.contains("lite-glass")
      && !window.matchMedia?.("(prefers-reduced-transparency: reduce)")?.matches;
  }

  function sync() {
    const enabled = active();
    root.classList.toggle("liquid-refraction", enabled);
    const builds = [];
    for (const surface of SURFACES) {
      for (const element of document.querySelectorAll(surface.selector)) {
        if (!observed.has(element)) { observed.add(element); resize?.observe(element); }
        if (enabled) builds.push(build(element, surface));
      }
    }
    return Promise.all(builds);
  }

  new MutationObserver(() => { sync(); }).observe(root, { attributes: true, attributeFilter: ["data-style", "class"] });
  // The welcome card is re-created whenever an empty conversation is shown; give each new one its glass.
  // Only that card is checked, so streaming replies into the timeline cost nothing here.
  const timeline = document.getElementById("timelineList");
  if (timeline) {
    new MutationObserver(() => {
      const card = timeline.querySelector(":scope > .empty-state");
      if (card && !observed.has(card)) sync();
    }).observe(timeline, { childList: true });
  }
  window.addEventListener("load", () => { sync(); });
  sync();
  window.MobileLiquidGlass = { sync, profile: PROFILE };
})();
