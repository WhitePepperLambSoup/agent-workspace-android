/* Japanese and Korean UI catalogs are large, so only the one this page needs is loaded, before
   i18n.js reads it (window.MobileI18nJa / MobileI18nKo). Same choice as i18n.js: the saved language,
   else the system's. */
(() => {
  let preference = "auto";
  try { preference = JSON.parse(window.localStorage.getItem("agent-mobile-preferences-v1") || "{}").language || "auto"; }
  catch { /* Private storage can be unavailable; follow the system language. */ }
  const system = ((navigator.languages && navigator.languages[0]) || navigator.language || "").slice(0, 2).toLowerCase();
  const language = preference === "auto" ? system : preference;
  if (language !== "ja" && language !== "ko") return;
  // The page's own token (entrypoint.py adds it to every script address).
  const query = (document.currentScript && document.currentScript.src.split("?")[1]) || "";
  document.write(`<script src="/static/i18n-${language}.js${query ? `?${query}` : ""}"><\/script>`);
})();
