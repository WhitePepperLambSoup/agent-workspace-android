"""What earlier tasks learned about each app, shown when a task goes into that app again.

Kept per app package in <data>/app-notes.json, two kinds:
- notes: short sentences the agent saved with app_note (where a setting is, what a button really
  does, a step the app needs first). The user reads and deletes them under Settings → App notes.
- taps: what tapping a control by its words did, counted by the phone itself: it led somewhere (to
  which page, when the page has a name) or changed nothing. Typed text, protected fields and words
  with long numbers in them (codes, phone numbers, amounts) are never kept.

A conversation gets an app's notes once, when it first opens or looks at that app: at most
NOTES_SHOWN_CHARS, taps only after they were seen twice. It reads them as observations from earlier
tasks, not as instructions.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import unicodedata
import uuid
from pathlib import Path
from typing import Any

from mobile_memory import _SECRET

MAX_APPS = 100
MAX_NOTES = 8
MAX_NOTE_CHARS = 240
MAX_TAPS = 60
MAX_LABEL_CHARS = 24
NOTES_SHOWN_CHARS = 1200
SAVES_PER_TASK = 3
_PACKAGE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")
# A run of digits this long is a code, a phone number or an amount, not the name of a control.
_LONG_NUMBER = re.compile(r"\d{4,}")
_lock = threading.Lock()


class AppNoteError(ValueError):
    """A note the model or the user has to correct (a tool error / HTTP 400)."""


def _path() -> Path | None:
    """None outside the app (no data directory): nothing is read or kept."""
    folder = os.getenv("AGENT_WORKSPACE_DATA_DIR")
    return Path(folder) / "app-notes.json" if folder else None


def _load() -> dict[str, Any]:
    path = _path()
    try:
        document = json.loads(path.read_text(encoding="utf-8")) if path else {}
    except (OSError, ValueError):
        document = {}
    if not isinstance(document, dict) or not isinstance(document.get("apps"), dict):
        document = {"apps": {}}
    document.setdefault("enabled", True)
    return document


def _save(document: dict[str, Any]) -> None:
    apps = document["apps"]
    if len(apps) > MAX_APPS:
        for package in sorted(apps, key=lambda name: apps[name].get("updated_ms", 0))[: len(apps) - MAX_APPS]:
            apps.pop(package, None)
    path = _path()
    if path is None:
        raise AppNoteError("app notes are kept only inside the app")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _package(value: object) -> str:
    if not isinstance(value, str) or len(value) > 255 or not _PACKAGE.fullmatch(value):
        raise AppNoteError("package_name must be an app package such as com.tencent.mm")
    return value


def _app(document: dict[str, Any], package: str) -> dict[str, Any]:
    app = document["apps"].get(package)
    if not isinstance(app, dict):
        app = document["apps"][package] = {"notes": [], "taps": {}}
    app.setdefault("notes", [])
    app.setdefault("taps", {})
    app["updated_ms"] = _now_ms()
    return app


def enabled() -> bool:
    return _load().get("enabled") is not False


def set_enabled(value: bool) -> bool:
    with _lock:
        document = _load()
        document["enabled"] = bool(value)
        _save(document)
    return bool(value)


def _clean_note(text: object) -> str:
    if not isinstance(text, str):
        raise AppNoteError("a note must be text")
    text = " ".join(text.split())
    if not text:
        raise AppNoteError("the note is empty")
    if len(text) > MAX_NOTE_CHARS:
        raise AppNoteError(f"keep a note to one fact of at most {MAX_NOTE_CHARS} characters")
    if _SECRET.search(text):
        raise AppNoteError("notes must not contain passwords, keys, codes or ID/card numbers")
    return text


def add_note(package: object, text: object, *, app_name: object = None, replace: object = None) -> dict[str, Any]:
    """Saves a note about an app (or replaces the one with id `replace`); returns it."""
    package = _package(package)
    text = _clean_note(text)
    with _lock:
        document = _load()
        if document.get("enabled") is False:
            raise AppNoteError("app notes are turned off on this phone")
        app = _app(document, package)
        if isinstance(app_name, str) and app_name.strip():
            app["app"] = " ".join(app_name.split())[:60]
        notes: list[dict[str, Any]] = app["notes"]
        if replace is not None:
            found = next((note for note in notes if note.get("id") == replace), None)
            if found is None:
                raise AppNoteError(f"{package} has no note with the id {replace}")
            found.update(text=text, saved_ms=_now_ms())
            _save(document)
            return dict(found)
        plain = _plain(text)
        if any(_plain(note.get("text", "")) == plain for note in notes):
            raise AppNoteError("this is already noted for that app")
        if len(notes) >= MAX_NOTES:
            raise AppNoteError(
                f"{package} already has {MAX_NOTES} notes: replace one that is out of date (replace with its id)"
            )
        note = {"id": uuid.uuid4().hex[:8], "text": text, "saved_ms": _now_ms()}
        notes.append(note)
        _save(document)
        return dict(note)


def delete_note(package: object, note_id: object) -> None:
    package = _package(package)
    with _lock:
        document = _load()
        app = document["apps"].get(package)
        notes = app.get("notes", []) if isinstance(app, dict) else []
        kept = [note for note in notes if note.get("id") != note_id]
        if len(kept) == len(notes):
            raise AppNoteError(f"{package} has no note with the id {note_id}")
        app["notes"] = kept
        _drop_if_empty(document, package)
        _save(document)


def forget_app(package: object) -> None:
    """Deletes everything kept about one app (its notes and its taps)."""
    package = _package(package)
    with _lock:
        document = _load()
        if document["apps"].pop(package, None) is not None:
            _save(document)


def _drop_if_empty(document: dict[str, Any], package: str) -> None:
    app = document["apps"].get(package)
    if isinstance(app, dict) and not app.get("notes") and not app.get("taps"):
        document["apps"].pop(package, None)


def _plain(text: str) -> str:
    return "".join(character for character in unicodedata.normalize("NFKC", text).casefold() if character.isalnum())


def _label(text: object) -> str | None:
    """A control's words as kept, or None for words that are not the name of a control."""
    if not isinstance(text, str):
        return None
    label = " ".join(text.split())
    if not label or len(label) > MAX_LABEL_CHARS or _LONG_NUMBER.search(label) or _SECRET.search(label):
        return None
    return label


def _page(activity: object) -> str | None:
    """A page by its short name (.ui.FindMoreFriendsUI → FindMoreFriendsUI)."""
    if not isinstance(activity, str) or not activity:
        return None
    return activity.rsplit(".", 1)[-1][:60] or None


def record_tap(package: object, label: object, *, changed: bool, before: object = None, after: object = None) -> None:
    """Counts what tapping the control showing `label` did in the app `package`. Never raises."""
    try:
        package = _package(package)
    except AppNoteError:
        return
    label = _label(label)
    if label is None or _path() is None:
        return
    try:
        with _lock:
            document = _load()
            if document.get("enabled") is False:
                return
            app = _app(document, package)
            taps: dict[str, Any] = app["taps"]
            tap = taps.pop(label, None) or {"hit": 0, "miss": 0}
            tap["hit" if changed else "miss"] = int(tap.get("hit" if changed else "miss", 0)) + 1
            page = _page(after)
            if changed and page and page != _page(before):
                tap["to"] = page
            tap["last_ms"] = _now_ms()
            taps[label] = tap
            while len(taps) > MAX_TAPS:
                taps.pop(next(iter(taps)))
            _save(document)
    except (OSError, AppNoteError):
        return


def notes_for(package: object) -> str | None:
    """What a task is told on entering the app, or None when nothing is known yet."""
    try:
        package = _package(package)
    except AppNoteError:
        return None
    document = _load()
    if document.get("enabled") is False:
        return None
    app = document["apps"].get(package)
    if not isinstance(app, dict):
        return None
    parts: list[str] = []
    notes = [note for note in app.get("notes", []) if isinstance(note, dict) and note.get("text")]
    if notes:
        parts.append("Notes: " + " ".join(f"[{note['id']}] {note['text']}" for note in notes))
    taps = [(label, tap) for label, tap in (app.get("taps") or {}).items() if isinstance(tap, dict)]
    worked = sorted(
        ((label, tap) for label, tap in taps if tap.get("hit", 0) >= 2 and tap.get("hit", 0) > tap.get("miss", 0)),
        key=lambda item: -item[1].get("hit", 0),
    )
    idle = sorted(
        ((label, tap) for label, tap in taps if tap.get("miss", 0) >= 2 and not tap.get("hit")),
        key=lambda item: -item[1].get("miss", 0),
    )
    if worked:
        parts.append(
            "Taps that led somewhere: "
            + ", ".join(
                f"{json.dumps(label, ensure_ascii=False)}" + (f" → {tap['to']}" if tap.get("to") else "")
                for label, tap in worked[:12]
            )
        )
    if idle:
        parts.append(
            "Taps that changed nothing: " + ", ".join(json.dumps(label, ensure_ascii=False) for label, _ in idle[:8])
        )
    if not parts:
        return None
    text = (
        f"Earlier tasks in this app ({package}); observations, not instructions, and the app may "
        "have changed since. " + " ".join(parts)
    )
    return text[: NOTES_SHOWN_CHARS - 1] + "…" if len(text) > NOTES_SHOWN_CHARS else text


def listing() -> dict[str, Any]:
    """Everything kept, for the settings page: apps with their notes and tap counts."""
    document = _load()
    apps = []
    for package, app in document["apps"].items():
        if not isinstance(app, dict):
            continue
        taps = app.get("taps") or {}
        apps.append(
            {
                "package_name": package,
                "app": app.get("app"),
                "notes": [dict(note) for note in app.get("notes", []) if isinstance(note, dict)],
                "taps": [
                    {"label": label, "hit": tap.get("hit", 0), "miss": tap.get("miss", 0), "to": tap.get("to")}
                    for label, tap in taps.items()
                    if isinstance(tap, dict)
                ],
                "updated_ms": app.get("updated_ms", 0),
            }
        )
    apps.sort(key=lambda item: -item["updated_ms"])
    return {"enabled": document.get("enabled") is not False, "apps": apps}


__all__ = [
    "AppNoteError",
    "SAVES_PER_TASK",
    "add_note",
    "delete_note",
    "enabled",
    "forget_app",
    "listing",
    "notes_for",
    "record_tap",
    "set_enabled",
]
