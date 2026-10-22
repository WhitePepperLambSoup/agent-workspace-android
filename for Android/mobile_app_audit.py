"""应用体检: which installed apps behave like rogue software, from what Android says about them.

AppAudit.kt lists every app the user installed with the facts (where it came from, whether it has a
home-screen icon, which powers it holds, special access such as accessibility or device admin), and
PopupWatch.kt adds which of them popped up by themselves while the user was in another app (only
once the user turns that record on). This module weighs those facts into a level and plain reasons,
and keeps the apps the user marked as fine (<data>/app-audit.json). Nothing here removes anything:
removing an app opens Android's own confirmation, and taking back a power opens its settings page.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+")
_DAY_MS = 24 * 3600 * 1000

# App stores, the phone makers' included: an app from one went through some review.
STORES = frozenset({
    "com.android.vending", "com.huawei.appmarket", "com.hihonor.appmarket", "com.xiaomi.market",
    "com.xiaomi.discover", "com.heytap.market", "com.oppo.market", "com.bbk.appstore", "com.vivo.appstore",
    "com.meizu.mstore", "zte.com.market", "com.zte.aliveupdate", "cn.nubia.neostore", "com.oneplus.market",
    "com.sec.android.app.samsungapps", "com.lenovo.leos.appstore", "com.tencent.android.qqdownloader",
    "com.qihoo.appstore", "com.baidu.appsearch", "com.wandoujia.phoenix2", "com.coolapk.market",
    "com.amazon.venezia", "org.fdroid.fdroid", "com.aurora.store", "com.looker.droidify",
})  # fmt: skip
# Android's installer screen: an APK file someone opened by hand.
PACKAGE_INSTALLERS = frozenset({
    "com.android.packageinstaller", "com.google.android.packageinstaller", "com.miui.packageinstaller",
    "com.samsung.android.packageinstaller", "com.oplus.appdetail", "com.coloros.packageinstaller",
})  # fmt: skip

# What each fact adds; reasons the user reads come from the codes (the web page words them).
WEIGHTS = {
    "device_admin": 4,  # can lock the phone or wipe it, and cannot be removed until this is taken back
    "accessibility": 3,  # reads every screen and can tap for the user
    "notification_listener": 2,  # reads every notification, codes included
    "sms": 2,
    "hidden_icon": 2,  # no icon on the home screen, so it is hard to find and remove
    "old_target": 2,  # built for Android 5 or older: got every permission at install without asking
    "pops_up": 2,  # came to the front or covered the screen by itself (4 from the second time)
    "call_log": 1,
    "background_location": 1,
    "overlay": 1,
    "install_others": 1,
    "usage_access": 1,
    "keeps_running": 1,  # starts with the phone and is exempt from battery limits
    "manual_install": 1,
    "installed_by_app": 1,
}
# Facts worth showing that weigh nothing on their own.
INFO = ("new", "disabled")
# The settings page that takes each power back.
PAGES = {
    "device_admin": "device_admin",
    "accessibility": "accessibility",
    "notification_listener": "notification_access",
    "overlay": "overlay",
    "install_others": "install_others",
    "usage_access": "usage_access",
    "keeps_running": "battery",
    "pops_up": "battery",
}
HIGH = 6
MEDIUM = 3


def _path() -> Path | None:
    data = os.getenv("AGENT_WORKSPACE_DATA_DIR")
    return Path(data) / "app-audit.json" if data else None


def _load() -> dict[str, Any]:
    path = _path()
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}
    except (OSError, ValueError):
        value = {}
    return value if isinstance(value, dict) else {}


def _save(value: dict[str, Any]) -> None:
    path = _path()
    if path is None:
        raise ValueError("the app check needs the app's data folder")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def trusted() -> set[str]:
    with _LOCK:
        names = _load().get("trusted")
    return {name for name in names if isinstance(name, str)} if isinstance(names, list) else set()


def set_trusted(package: Any, value: bool) -> None:
    name = check_package(package)
    with _LOCK:
        state = _load()
        names = {item for item in state.get("trusted") or [] if isinstance(item, str)}
        names.add(name) if value else names.discard(name)
        state["trusted"] = sorted(names)
        _save(state)


def check_package(package: Any) -> str:
    if not isinstance(package, str) or len(package) > 255 or not _PACKAGE.fullmatch(package):
        raise ValueError("package_name must be an Android app id such as com.example.app")
    return package


def _source(app: dict[str, Any]) -> dict[str, Any]:
    installer = app.get("installer")
    initiator = app.get("initiator")
    if isinstance(installer, str) and installer in STORES:
        return {"kind": "store", "by": installer, "by_label": app.get("installer_label")}
    if installer == app.get("package"):
        return {"kind": "self", "by": installer}
    if isinstance(installer, str) and installer in PACKAGE_INSTALLERS:
        # Who opened the APK (a browser, a chat app), when Android says.
        by = initiator if isinstance(initiator, str) and initiator not in PACKAGE_INSTALLERS else None
        return {"kind": "manual", "by": by, "by_label": app.get("initiator_label") if by else None}
    if isinstance(installer, str) and installer and installer != "com.android.shell":
        return {"kind": "app", "by": installer, "by_label": app.get("installer_label")}
    # Came with the phone, or put on by a computer over USB.
    return {"kind": "unknown", "by": None}


def _popups(records: list[Any]) -> dict[str, dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("package"), str):
            continue
        entry = counts.setdefault(record["package"], {"jumps": 0, "overlays": 0, "last_at": 0, "over": None})
        entry["jumps" if record.get("kind") == "jump" else "overlays"] += 1
        at = record.get("at") if isinstance(record.get("at"), int) else 0
        if at >= entry["last_at"]:
            entry["last_at"] = at
            entry["over"] = record.get("over") if isinstance(record.get("over"), str) else None
    return counts


def assess_app(app: dict[str, Any], popups: dict[str, Any] | None = None, now_ms: int | None = None) -> dict[str, Any]:
    """One app's level, the facts behind it, and the pages that take its powers back."""
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    permissions = {item for item in app.get("permissions") or [] if isinstance(item, str)}
    source = _source(app)
    signals: list[str] = []
    for key in ("device_admin", "accessibility", "notification_listener"):
        if app.get(key) is True:
            signals.append(key)
    if "sms" in permissions:
        signals.append("sms")
    if app.get("launcher") is False:
        signals.append("hidden_icon")
    target = app.get("target_sdk")
    if isinstance(target, int) and 0 < target < 23:
        signals.append("old_target")
    times = 0
    if popups:
        times = int(popups.get("jumps") or 0) + int(popups.get("overlays") or 0)
        if times:
            signals.append("pops_up")
    for key in ("call_log", "background_location"):
        if key in permissions:
            signals.append(key)
    for key in ("overlay", "install_others", "usage_access"):
        if app.get(key) is True:
            signals.append(key)
    if app.get("boot") is True and app.get("battery_unrestricted") is True:
        signals.append("keeps_running")
    if source["kind"] == "manual":
        signals.append("manual_install")
    elif source["kind"] == "app":
        signals.append("installed_by_app")
    score = sum(WEIGHTS[key] for key in signals) + (2 if times >= 2 else 0)
    # Live wallpapers, keyboards and plugins have no icon either: alone, it says little.
    if "hidden_icon" in signals and not set(signals) - {"hidden_icon", "manual_install", "installed_by_app", "old_target"}:
        score -= 1
    first = app.get("first_install")
    if isinstance(first, int) and 0 < now_ms - first < 3 * _DAY_MS:
        signals.append("new")
    enabled = app.get("enabled") is not False
    if not enabled:
        # Turned off: it cannot run until someone turns it back on.
        signals.append("disabled")
        score = 0
    hidden_power = "hidden_icon" in signals and bool({"device_admin", "accessibility", "notification_listener"} & set(signals))
    if score >= HIGH or (enabled and (hidden_power or times >= 3)):
        level = "high"
    elif score >= MEDIUM:
        level = "medium"
    elif score > 0:
        level = "low"
    else:
        level = "none"
    # Device admin first: Android refuses to remove the app until it is taken back.
    pages = [PAGES[key] for key in signals if key in PAGES and key != "device_admin"]
    first_steps = ["device_admin"] if "device_admin" in signals else []
    actions = list(dict.fromkeys([*first_steps, "uninstall", *pages, "info"]))
    return {
        "package": app.get("package"),
        "label": app.get("label") or app.get("package"),
        "version": app.get("version") or "",
        "level": level,
        "score": score,
        "signals": signals,
        "source": source,
        "popups": popups or None,
        "permissions": sorted(permissions),
        "first_install": first if isinstance(first, int) else None,
        "actions": actions,
    }


_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3, "trusted": 4}


def assess(scan: dict[str, Any], marked: set[str] | None = None, now_ms: int | None = None) -> dict[str, Any]:
    """The whole list, worst first, with counts; [marked] are apps the user said are fine."""
    marked = trusted() if marked is None else marked
    apps = [app for app in scan.get("apps") or [] if isinstance(app, dict) and isinstance(app.get("package"), str)]
    counts = _popups(scan.get("popups") or [])
    labels = {app["package"]: app.get("label") or app["package"] for app in apps}
    labels.update({key: value for key, value in (scan.get("labels") or {}).items() if isinstance(value, str)})
    result = []
    for app in apps:
        entry = assess_app(app, counts.get(app["package"]), now_ms)
        if entry["popups"] and entry["popups"].get("over"):
            entry["popups"] = {**entry["popups"], "over_label": labels.get(entry["popups"]["over"])}
        if app["package"] in marked:
            entry["level"] = "trusted"
        result.append(entry)
    result.sort(key=lambda entry: (_ORDER[entry["level"]], -entry["score"], str(entry["label"]).lower()))
    return {
        "apps": result,
        "checked": len(result),
        "high": sum(entry["level"] == "high" for entry in result),
        "medium": sum(entry["level"] == "medium" for entry in result),
        "watching": scan.get("watching") is True,
        "watch_ready": scan.get("watch_ready") is True,
        "scanned_at": scan.get("scanned_at"),
    }


# ---- On the phone (AppAudit.kt) ----

def _bridge() -> Any:
    from java import jclass

    return jclass("com.agentworkspace.mobile.capabilities.AppAudit")


def available() -> bool:
    try:
        _bridge()
        return True
    except Exception:
        return False


def _call(request: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(str(_bridge().execute(json.dumps(request))))
    if not isinstance(result, dict):
        raise RuntimeError("the phone returned an invalid result")
    if result.get("ok") is not True:
        raise RuntimeError(str(result.get("error") or "the phone refused the request"))
    return result


def scan_phone() -> dict[str, Any]:
    return assess(_call({"action": "scan"}))


def set_watching(enabled: bool) -> bool:
    return _call({"action": "watch", "enabled": bool(enabled)}).get("watching") is True


OPEN_PAGES = ("info", "notifications", "overlay", "install_others", "usage_access", "notification_access",
              "accessibility", "device_admin", "battery")  # fmt: skip


def open_page(package: Any, page: Any) -> None:
    name = check_package(package)
    if page == "uninstall":
        _call({"action": "uninstall", "package_name": name})
        return
    if page not in OPEN_PAGES:
        raise ValueError(f"page must be uninstall or one of {', '.join(OPEN_PAGES)}")
    _call({"action": "open", "package_name": name, "page": page})
