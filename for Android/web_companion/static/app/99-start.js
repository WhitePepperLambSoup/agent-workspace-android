  // ---- Start-up: the last part, so every part above is defined; it closes the page script. ----
  applyAppearance();
  try { bridge?.setUiLanguage?.(preferences.language); } catch { /* Older APKs keep native text in Chinese. */ }
  syncWidgetQuickTasks();
  resizeVisibleViewport();
  syncControls();
  (async () => { await loadSettings(); if (!disposed) await loadWorkspaces(); if (!disposed) await loadSessions(selectedSessionId); if (!disposed) refreshShareInbox(); })();
})();
