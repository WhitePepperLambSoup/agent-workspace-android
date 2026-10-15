
  // ---- App lock (2.0): the app's own setting; the system prompt does the checking ----------
  function syncAppLock(state) {
    let value = state;
    if (!value) { try { value = JSON.parse(bridge.getAppLock()); } catch { return; } }
    $("appLockSection").hidden = false;
    $("appLockToggle").checked = value.enabled === true;
    $("appLockToggle").disabled = value.available !== true;
    $("appLockDelay").value = String(value.delay_minutes ?? 1);
    $("appLockDelay").disabled = value.enabled !== true;
    $("appLockHint").textContent = value.available === true
      ? t("对话、记忆和 API 设置都存在这台手机上。开启后，重新打开应用或从后台回来时需要解锁；悬浮球、圈选提问这些快捷入口不受影响。")
      : t("这台手机没有设置锁屏密码（或系统低于 Android 9），无法使用应用锁。");
  }

  if (typeof bridge?.getAppLock === "function") {
    syncAppLock();
    $("appLockToggle").addEventListener("change", () => bridge.setAppLock($("appLockToggle").checked, Number($("appLockDelay").value)));
    $("appLockDelay").addEventListener("change", () => bridge.setAppLock(true, Number($("appLockDelay").value)));
    window.addEventListener("agent-app-lock-changed", (event) => syncAppLock(event.detail));
  }

  // Tasks from other apps (Tasker, Shortcuts): asked about each time until this is on.
  if (typeof bridge?.getExternalEntry === "function") {
    $("externalEntrySection").hidden = false;
    $("externalEntryToggle").checked = bridge.getExternalEntry() === true;
    $("externalEntryToggle").addEventListener("change", () => bridge.setExternalEntry($("externalEntryToggle").checked));
  }

  // Contacts and location for the personal-info tools (Device & tools page).
  function syncPersonalAccess() {
    let access = {};
    try { access = JSON.parse(bridge.getPersonalAccess() || "{}"); } catch { return; }
    $("personalInfoSection").hidden = false;
    $("contactsAccessState").textContent = access.contacts ? t("已允许：AI 可以按名字查电话") : t("未允许：点这里授权");
    $("locationAccessState").textContent = access.location ? t("已允许：AI 可以查看手机位置") : t("未允许：点这里授权");
  }
  if (typeof bridge?.getPersonalAccess === "function") {
    syncPersonalAccess();
    $("btnContactsAccess").addEventListener("click", () => bridge.requestPersonalAccess("contacts"));
    $("btnLocationAccess").addEventListener("click", () => bridge.requestPersonalAccess("location"));
    window.addEventListener("agent-personal-access-changed", syncPersonalAccess);
  }
