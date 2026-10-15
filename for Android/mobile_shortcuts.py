"""Shortcuts: phone tasks recorded as steps and run again without the model.

The steps are recorded by the accessibility service while the agent operates the phone (from the
phone control panel, or a phone-control task started in the chat) and kept by the Android app
(PhoneMemory, automation/shortcuts.json). Each step finds its control again by its words, so a
shortcut still works when the layout moves a little; a step that needs the user's yes (deleting,
paying) stops it. This module is the engine's side: list, edit, delete and run them, and keep the
steps of the last few phone-control tasks until the user saves one as a shortcut.
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections import OrderedDict
from typing import Any

MAX_STEPS = 60
KINDS = ("tap", "long", "type", "enter", "scroll", "swipe", "launch", "key", "page", "find")
_PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+")
_KEYS = {"back", "home", "recents", "notifications"}
_DIRECTIONS = {"up", "down", "left", "right"}
_PENDING_TASKS = 8

_lock = threading.Lock()
_running = threading.Lock()  # one shortcut at a time
_pending: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
_last_run: dict[str, Any] | None = None


def _bridge():
    from java import jclass  # type: ignore[import-not-found]

    return jclass("com.agentworkspace.mobile.automation.AndroidSystemBridge")


def available() -> bool:
    try:
        _bridge()
    except Exception:
        return False
    return True


def _point(value: Any) -> int:
    if type(value) is not int:
        raise ValueError("step coordinates must be whole numbers")
    return max(0, min(20_000, value))


def _words(value: Any, limit: int, *, required: bool = False) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValueError("this step needs words to find its control")
        return None
    if not isinstance(value, str):
        raise ValueError("step text must be a string")
    return value[:limit]


def clean_steps(steps: Any) -> list[dict[str, Any]]:
    """The steps as the app keeps them (the app checks them again): known kinds and fields only."""
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError(f"a shortcut has 1 to {MAX_STEPS} steps")
    result = []
    for step in steps:
        if not isinstance(step, dict) or step.get("kind") not in KINDS:
            raise ValueError("unknown shortcut step")
        kind = step["kind"]
        if kind in {"tap", "long", "type"}:
            clean = {"kind": kind, "x": _point(step.get("x", 0)), "y": _point(step.get("y", 0)),
                     "label": _words(step.get("label"), 200, required=kind == "type"),
                     "class": _words(step.get("class"), 120)}
            if kind == "type":
                text = step.get("text")
                if not isinstance(text, str) or len(text) > 4096:
                    raise ValueError("a typing step needs its text (at most 4096 characters)")
                clean["text"] = text
            # It closed an ad when recorded: a run without that ad goes on without it.
            if kind == "tap" and step.get("optional") is True:
                clean["optional"] = True
        elif kind == "enter":
            clean = {"kind": kind}
        elif kind == "scroll":
            direction = step.get("direction", "down")
            if direction not in _DIRECTIONS:
                raise ValueError("unknown scroll direction")
            clean = {"kind": kind, "direction": direction}
        elif kind == "swipe":
            clean = {"kind": kind, **{key: _point(step.get(key, 0)) for key in ("x", "y", "x2", "y2")}}
        elif kind == "launch":
            package = step.get("package")
            if not isinstance(package, str) or len(package) > 255 or not _PACKAGE.fullmatch(package):
                raise ValueError("an app step needs a valid package name")
            clean = {"kind": kind, "package": package}
        elif kind == "key":
            if step.get("key") not in _KEYS:
                raise ValueError("unknown key")
            clean = {"kind": kind, "key": step["key"]}
        elif kind == "page":
            request = step.get("request")
            if not isinstance(request, dict) or request.get("action") != "open_page":
                raise ValueError("a page step opens a page")
            clean = {"kind": kind, "request": request}
        else:
            clean = {"kind": kind, "text": _words(step.get("text"), 200, required=True), "tap": step.get("tap") is True}
        result.append(clean)
    return result


def list_shortcuts() -> list[dict[str, Any]]:
    try:
        return json.loads(str(_bridge().shortcuts()))
    except Exception:
        return []


def save(payload: dict[str, Any]) -> dict[str, Any]:
    """Adds a shortcut, or replaces the name and steps of the one with "id"."""
    if not isinstance(payload, dict):
        raise ValueError("a shortcut must be a JSON object")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 40:
        raise ValueError("a shortcut needs a name of at most 40 characters")
    shortcut_id = payload.get("id")
    if shortcut_id is not None and (not isinstance(shortcut_id, str) or not 1 <= len(shortcut_id) <= 64):
        raise ValueError("invalid shortcut id")
    app = payload.get("app")
    if app is not None and (not isinstance(app, str) or not _PACKAGE.fullmatch(app)):
        raise ValueError("invalid app package")
    document = {"id": shortcut_id, "name": name.strip(), "app": app,
                "app_label": _words(payload.get("app_label"), 80), "steps": clean_steps(payload.get("steps"))}
    answer = json.loads(str(_bridge().saveShortcut(json.dumps(document, ensure_ascii=False))))
    if not answer.pop("ok", False):
        raise ValueError(str(answer.get("reason") or "the shortcut was not saved"))
    return answer


def delete(shortcut_id: str) -> None:
    if not isinstance(shortcut_id, str) or not shortcut_id:
        raise ValueError("shortcut id is required")
    if not any(item.get("id") == shortcut_id for item in list_shortcuts()):
        raise KeyError(shortcut_id)
    _bridge().deleteShortcut(shortcut_id)


def running() -> bool:
    return _running.locked()


def run(shortcut_id: str) -> dict[str, Any]:
    """Runs a shortcut now and waits for it (call it from a worker thread): {"ok", "reason"}.
    The phone must be unlocked (a dark screen is turned on); nothing runs over the lock screen."""
    global _last_run
    if not isinstance(shortcut_id, str) or not shortcut_id:
        raise ValueError("shortcut id is required")
    if not _running.acquire(blocking=False):
        return {"ok": False, "reason": "another shortcut is running"}
    try:
        bridge = _bridge()
        ready = json.loads(str(bridge.prepareUnattended()))
        if ready.get("ok") is not True:
            answer = {"ok": False, "reason": ready.get("reason") or "the phone is not ready", "not_ready": True}
        else:
            answer = json.loads(str(bridge.runShortcut(shortcut_id)))
    except Exception as error:  # off the phone, or the bridge failed
        answer = {"ok": False, "reason": str(error)[:300] or "the phone's controls are unavailable"}
    finally:
        _running.release()
    with _lock:
        _last_run = {"id": shortcut_id, "ok": answer.get("ok") is True, "reason": answer.get("reason"), "at": time.time()}
        if type(answer.get("failed_step")) is int:
            _last_run["failed_step"] = answer["failed_step"]
    return answer


def stop() -> None:
    try:
        _bridge().stopShortcut()
    except Exception:
        pass


def last_run() -> dict[str, Any] | None:
    with _lock:
        return dict(_last_run) if _last_run else None


# ---- The steps of recent phone-control tasks, until one is saved -----------------------------

def begin_recording(task_id: str = "") -> None:
    """A task starts: its phone actions are recorded (for a shortcut) and pictured (step replay)."""
    try:
        _bridge().beginRecording(task_id)
    except Exception:
        pass


def end_recording() -> None:
    try:
        _bridge().endRecording()
    except Exception:
        pass


def finish_recording(task_id: str) -> int:
    """Keeps what the task did (for "save as shortcut"); the number of steps."""
    try:
        steps = json.loads(str(_bridge().recordedSteps()))
    except Exception:
        return 0
    if not isinstance(steps, list) or not steps:
        return 0
    # Only where the task started (the app in front, or the home screen): nothing done to keep.
    if len(steps) == 1 and isinstance(steps[0], dict) and steps[0].get("kind") in {"launch", "key"}:
        return 0
    with _lock:
        _pending[task_id] = steps[:MAX_STEPS]
        _pending.move_to_end(task_id)
        while len(_pending) > _PENDING_TASKS:
            _pending.popitem(last=False)
    return len(steps)


def pending(task_id: str) -> list[dict[str, Any]]:
    with _lock:
        return [dict(step) for step in _pending.get(task_id, [])]


def heal(task_id: str, shortcut_id: str, from_step: Any) -> dict[str, Any]:
    """A shortcut stopped at `from_step` and the AI finished the job from there: keep the steps
    that worked and what the AI did instead of the rest."""
    steps = pending(task_id)
    if not steps:
        raise KeyError(task_id)
    shortcut = next((item for item in list_shortcuts() if item.get("id") == shortcut_id), None)
    if shortcut is None:
        raise KeyError(shortcut_id)
    old = shortcut.get("steps") or []
    if type(from_step) is not int or not 0 <= from_step <= len(old):
        raise ValueError("from_step must point into the shortcut")
    healed = save({"id": shortcut_id, "name": shortcut["name"], "steps": (old[:from_step] + steps)[:MAX_STEPS]})
    with _lock:
        _pending.pop(task_id, None)
    return healed


def keep(task_id: str, name: str) -> dict[str, Any]:
    """Saves a finished phone-control task's steps as a shortcut."""
    steps = pending(task_id)
    if not steps:
        raise KeyError(task_id)
    app = next((step["package"] for step in steps if step.get("kind") == "launch"), None)
    shortcut = save({"name": name, "app": app, "steps": steps})
    with _lock:
        _pending.pop(task_id, None)
    return shortcut
