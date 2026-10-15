"""Notifications kept on the phone for digests (off until the user turns it on).

The Android notification listener reports each notification here while the journal is on
(AgentNotificationListener → /mobile/notification-journal/add); the recent_notifications tool
reads them back so the agent can sort them into what matters, what can wait and ads, and pull out
pickup codes, flights and meeting changes. Verification codes are masked as they arrive and never
stored; entries older than 48 hours are dropped; at most 500 are kept. Stored in
<data>/notification-journal.json, which never leaves the phone by itself.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

MAX_ENTRIES = 500
KEEP_SECONDS = 48 * 3600
_lock = threading.Lock()
# A code next to the words that announce one: "验证码 482913", "your verification code is 1234".
_CODE = re.compile(
    r"(验证码|校验码|动态码|动态密码|确认码|安全码|登录码|取款码|verification code|security code|one[- ]time (?:pass)?code|otp|code)"
    r"([^\d]{0,16})(\d{4,8})",
    re.IGNORECASE,
)


def _path() -> Path:
    return Path(os.getenv("AGENT_WORKSPACE_DATA_DIR") or ".") / "notification-journal.json"


def _read() -> dict[str, Any]:
    try:
        document = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        document = {}
    if not isinstance(document, dict):
        document = {}
    entries = document.get("entries")
    return {"enabled": document.get("enabled") is True, "entries": entries if isinstance(entries, list) else []}


def _write(document: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def mask_codes(text: str) -> str:
    return _CODE.sub(lambda match: f"{match.group(1)}{match.group(2)}[已隐藏]", text)


def status() -> dict[str, Any]:
    with _lock:
        document = _read()
    return {"enabled": document["enabled"], "count": len(document["entries"]), "keep_hours": KEEP_SECONDS // 3600}


def set_enabled(enabled: Any) -> dict[str, Any]:
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be true or false")
    with _lock:
        document = _read()
        document["enabled"] = enabled
        if not enabled:
            document["entries"] = []  # turning it off forgets what was kept
        _write(document)
    return status()


def clear() -> dict[str, Any]:
    with _lock:
        document = _read()
        document["entries"] = []
        _write(document)
    return status()


def add(payload: Any, *, now: float | None = None) -> bool:
    """Keeps one notification while the journal is on; False when it is off or the entry is empty."""
    if not isinstance(payload, dict):
        raise ValueError("a notification must be an object")
    current = time.time() if now is None else now
    entry = {
        "at": current,
        "package": str(payload.get("package") or "")[:120],
        "app": str(payload.get("app_label") or payload.get("package") or "")[:80],
        "title": mask_codes(str(payload.get("title") or "")[:200]),
        "text": mask_codes(str(payload.get("text") or "")[:1000]),
    }
    if not entry["title"] and not entry["text"]:
        return False
    with _lock:
        document = _read()
        if not document["enabled"]:
            return False
        entries = [item for item in document["entries"] if isinstance(item, dict) and current - float(item.get("at", 0)) < KEEP_SECONDS]
        # The same notification updated again (a download, a chat thread) replaces the last copy.
        if entries and all(entries[-1].get(key) == entry[key] for key in ("package", "title", "text")):
            entries[-1] = entry
        else:
            entries.append(entry)
        document["entries"] = entries[-MAX_ENTRIES:]
        _write(document)
    return True


def recent(hours: float = 2, *, limit: int = 200, now: float | None = None) -> list[dict[str, Any]]:
    current = time.time() if now is None else now
    since = current - max(0.1, min(float(hours), KEEP_SECONDS / 3600)) * 3600
    with _lock:
        entries = _read()["entries"]
    picked = [item for item in entries if isinstance(item, dict) and float(item.get("at", 0)) >= since]
    picked = picked[-max(1, min(int(limit), MAX_ENTRIES)):]
    try:  # the phone's own time zone (the engine process may run in UTC)
        from android_adapter.clock_calendar import phone_now

        zone = phone_now().tzinfo
    except Exception:
        zone = None
    from datetime import datetime

    return [
        {"time": datetime.fromtimestamp(float(item["at"]), zone).strftime("%m-%d %H:%M"), "app": item.get("app"),
         "title": item.get("title"), "text": item.get("text")}
        for item in reversed(picked)
    ]
