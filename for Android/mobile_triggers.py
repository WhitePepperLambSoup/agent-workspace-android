"""Automatic triggers: run a prompt, a saved workflow or a recorded shortcut when the phone starts
charging, joins a Wi-Fi network, an app is opened, the battery runs low, headphones or a Bluetooth
audio device connect, the phone is unlocked, or a calendar event is a set number of minutes away.

The Android app watches for these events (TriggerEvents while the engine service runs, the
accessibility service for app openings) and reports them to /mobile/triggers/fire; this store
decides which triggers match. Each trigger waits out its cooldown before firing again, so plugging
in twice or reopening an app does not start the same task over and over. Calendar triggers are
checked by the engine itself (calendar_due) and fire once per event instead. Stored in
<data>/triggers.json.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

KINDS = ("charging", "wifi", "app_open", "battery_low", "headset", "unlock", "calendar")
MAX_TRIGGERS = 30
# The number a trigger's value holds, with its default and allowed range.
_NUMBERS = {"battery_low": (20, 5, 90), "calendar": (10, 1, 720)}
_FIRED_EVENTS = 50
_lock = threading.Lock()


def _path() -> Path:
    return Path(os.getenv("AGENT_WORKSPACE_DATA_DIR") or ".") / "triggers.json"


def _read() -> list[dict[str, Any]]:
    try:
        document = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = document.get("triggers") if isinstance(document, dict) else None
    return [item for item in items if isinstance(item, dict) and item.get("kind") in KINDS] if isinstance(items, list) else []


def _write(items: list[dict[str, Any]]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"version": 1, "triggers": items}, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def snapshot() -> dict[str, Any]:
    with _lock:
        return {"triggers": _read(), "kinds": list(KINDS)}


def add(payload: dict[str, Any]) -> dict[str, Any]:
    kind = payload.get("kind")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    value = str(payload.get("value") or "").strip()[:200]
    if kind == "app_open" and not value:
        raise ValueError("app_open needs the app's package name")
    if kind in ("charging", "unlock"):
        value = ""
    if kind in _NUMBERS:
        default, low, high = _NUMBERS[kind]
        try:
            number = int(value or default)
        except ValueError:
            number = -1
        if not low <= number <= high:
            raise ValueError(f"{'the battery level' if kind == 'battery_low' else 'the minutes before an event'} must be {low} to {high}")
        value = str(number)
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("session_id is required")
    prompt = str(payload.get("prompt") or "").strip()
    workflow_id = str(payload.get("workflow_id") or "").strip()
    # A recorded shortcut (mobile_shortcuts) runs without the model.
    shortcut_id = str(payload.get("shortcut_id") or "").strip()[:64]
    if sum(map(bool, (prompt, workflow_id, shortcut_id))) != 1:
        raise ValueError("give one of a prompt, a workflow_id or a shortcut_id")
    if len(prompt) > 4000:
        raise ValueError("the prompt is longer than 4000 characters")
    cooldown = payload.get("cooldown_minutes", 30)
    if not isinstance(cooldown, int) or not 1 <= cooldown <= 1440:
        raise ValueError("cooldown_minutes must be 1 to 1440")
    item = {
        "trigger_id": "t" + uuid.uuid4().hex[:10],
        "kind": kind,
        "value": value,
        "session_id": session_id,
        **({"prompt": prompt} if prompt else {"workflow_id": workflow_id} if workflow_id else {"shortcut_id": shortcut_id}),
        "phone_control": payload.get("phone_control") is True,
        "cooldown_minutes": cooldown,
        "enabled": True,
        "last_fired": None,
    }
    with _lock:
        items = _read()
        if len(items) >= MAX_TRIGGERS:
            raise ValueError(f"at most {MAX_TRIGGERS} triggers")
        items.append(item)
        _write(items)
    return item


def delete(trigger_id: str) -> None:
    with _lock:
        items = _read()
        remaining = [item for item in items if item.get("trigger_id") != trigger_id]
        if len(remaining) == len(items):
            raise KeyError(trigger_id)
        _write(remaining)


def set_enabled(trigger_id: str, enabled: bool) -> dict[str, Any]:
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be true or false")
    with _lock:
        items = _read()
        for item in items:
            if item.get("trigger_id") == trigger_id:
                item["enabled"] = enabled
                _write(items)
                return item
    raise KeyError(trigger_id)


def _matches(item: dict[str, Any], kind: str, value: str, previous: str) -> bool:
    if item.get("kind") != kind or not item.get("enabled"):
        return False
    wanted = str(item.get("value") or "").strip()
    if kind == "app_open":
        return wanted == value
    if kind == "battery_low":
        # Only when the level drops past the trigger's mark, not at every lower percent after it.
        try:
            return int(previous) > int(wanted or 20) >= int(value)
        except ValueError:
            return False
    if kind == "headset":
        # Part of the device name ("AirPods" for "Lin's AirPods Pro"); empty for any device.
        return not wanted or wanted.casefold() in value.casefold()
    # Charging and unlocking need nothing more; a Wi-Fi trigger without a network name fires on any network.
    return not wanted or wanted.strip('"').casefold() == value.strip('"').casefold()


def fire(kind: str, value: str = "", *, previous: str = "", now: float | None = None) -> list[dict[str, Any]]:
    """The triggers this event starts (their cooldown restarts now); nothing for an unknown kind.
    A battery_low event's value is the battery level and previous the level before it."""
    if kind not in KINDS or kind == "calendar":
        return []
    current = time.time() if now is None else now
    with _lock:
        items = _read()
        due = [
            item for item in items
            if _matches(item, kind, str(value or ""), str(previous or ""))
            and (
                item.get("last_fired") is None
                or current - float(item["last_fired"]) >= int(item.get("cooldown_minutes") or 30) * 60
            )
        ]
        for item in due:
            item["last_fired"] = current
        if due:
            _write(items)
        return [dict(item) for item in due]


def calendar_lead() -> int:
    """The most minutes ahead an enabled calendar trigger looks; 0 when there is none."""
    with _lock:
        leads = [int(item.get("value") or 10) for item in _read() if item.get("kind") == "calendar" and item.get("enabled")]
    return max(leads, default=0)


def calendar_due(events: list[dict[str, Any]], *, now: float | None = None) -> list[dict[str, Any]]:
    """The calendar triggers to start now, each with the event it is for ("event").

    events are the phone's upcoming timed events (key, title, begin and end in epoch ms,
    location). A trigger fires once per event, from its set minutes before the start until the
    start, so a check that runs late (the phone dozing) still catches it."""
    current = time.time() if now is None else now
    with _lock:
        items = _read()
        due = []
        for item in items:
            if item.get("kind") != "calendar" or not item.get("enabled"):
                continue
            lead = int(item.get("value") or 10) * 60
            fired = item.setdefault("fired_events", [])
            for event in events:
                key = str(event.get("key") or "")
                begin = float(event.get("begin") or 0) / 1000
                if key and key not in fired and begin - lead <= current < begin:
                    fired.append(key)
                    del fired[:-_FIRED_EVENTS]
                    item["last_fired"] = current
                    due.append({**item, "event": event})
        if due:
            _write(items)
    return [{key: value for key, value in item.items() if key != "fired_events"} for item in due]
