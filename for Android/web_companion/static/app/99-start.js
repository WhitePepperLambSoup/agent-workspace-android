  // ---- Start-up: the last part, so every part above is defined; it closes the page script. ----
  applyAppearance();
  try { bridge?.setUiLanguage?.(preferences.language); } catch { /* Older APKs keep native text in Chinese. */ }
  syncWidgetQuickTasks();
  resizeVisibleViewport();
  syncControls();
  (async () => {
    await loadSettings();
    // What first-use setup left for this start (a provider to trust, a model to prepare), or the sheet.
    if (!disposed) void resumeSetup();
    if (!disposed) await loadWorkspaces();
    if (!disposed) await loadSessions(selectedSessionId);
    if (!disposed) refreshShareInbox();
    // 长辈模式 opens straight on its own screen.
    if (!disposed) await loadElder();
  })();
})();
