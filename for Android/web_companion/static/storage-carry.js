// The console's storage belongs to its address. The engine listens on 8080, or on the next free port
// when another app holds 8080, and the page there would start with none of the settings, drafts and
// choices kept here. The app keeps a copy of this page's own keys (AndroidBridge.savePageStorage), and
// a page at another address starts from that copy when it is newer than what the address last had.
// Loaded before every other script, so they read the restored values.
(function () {
  "use strict";
  const bridge = window.AndroidBridge;
  if (!bridge || typeof bridge.pageStorage !== "function" || typeof bridge.savePageStorage !== "function") return;
  const savedKey = "agent-mobile-page-storage-saved-v1";
  const own = (key) => /^agent-/.test(key) && key !== savedKey;
  let storage;
  try { storage = window.localStorage; void storage.length; } catch { return; }

  function read() {
    const items = {};
    for (let index = 0; index < storage.length; index++) {
      const key = storage.key(index);
      if (key && own(key)) items[key] = storage.getItem(key);
    }
    return items;
  }

  try {
    const copy = JSON.parse(bridge.pageStorage() || "null");
    const here = Number(storage.getItem(savedKey)) || 0;
    if (copy && copy.origin !== window.location.origin && Number(copy.savedAt) > here && copy.items && typeof copy.items === "object") {
      for (const key of Object.keys(read())) storage.removeItem(key);
      for (const [key, value] of Object.entries(copy.items)) {
        if (own(key) && typeof value === "string") storage.setItem(key, value);
      }
      storage.setItem(savedKey, String(copy.savedAt));
    }
  } catch { /* a missing or broken copy leaves this address's storage as it is */ }

  let last = "";
  function save() {
    try {
      const items = read();
      const text = JSON.stringify(items);
      if (text === last) return;
      const savedAt = Date.now();
      const result = JSON.parse(bridge.savePageStorage(JSON.stringify({ origin: window.location.origin, savedAt, items })));
      if (result && result.ok) {
        last = text;
        storage.setItem(savedKey, String(savedAt));
      }
    } catch { /* the next save tries again */ }
  }
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") save(); });
  window.addEventListener("pagehide", save);
  window.setInterval(save, 30000);
  window.setTimeout(save, 3000);
})();
