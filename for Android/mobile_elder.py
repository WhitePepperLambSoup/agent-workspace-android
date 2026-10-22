"""长辈模式 (elder mode): a voice-first screen for an older person, switched on in the app.

The settings live on the phone (<data>/elder-mode.json): whether the mode is on, the conversation
it uses, how a family member is called and their phone number (for the call button; the number
never goes to the model), reading replies aloud and how fast, and an optional exit PIN so the mode
is not left by accident. While it is on, the system prompt asks for short spoken-style replies and
for care with anything that looks like a scam.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_PIN = re.compile(r"\d{4,6}")
_PHONE = re.compile(r"\+?[0-9][0-9 -]{2,19}")
_MAX_NAME = 12
_PIN_ROUNDS = 120_000
# Wrong PINs in a row before the next try has to wait (seconds).
_PIN_TRIES = 5
_PIN_WAIT = 60
_failures = {"count": 0, "until": 0.0}


def _path() -> Path | None:
    data = os.getenv("AGENT_WORKSPACE_DATA_DIR")
    return Path(data) / "elder-mode.json" if data else None


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
        raise ValueError("elder mode settings need the app's data folder")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def _public(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": value.get("enabled") is True,
        "session_id": value.get("session_id") if isinstance(value.get("session_id"), str) else None,
        "family_name": value.get("family_name") or "",
        "family_phone": value.get("family_phone") or "",
        "read_aloud": value.get("read_aloud", True) is not False,
        "slow_speech": value.get("slow_speech", True) is not False,
        "has_pin": isinstance(value.get("pin"), dict),
    }


def settings() -> dict[str, Any]:
    with _LOCK:
        return _public(_load())


def _hash(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, _PIN_ROUNDS).hex()


def _check_pin(value: dict[str, Any], pin: Any) -> None:
    stored = value.get("pin")
    if not isinstance(stored, dict):
        return
    now = time.monotonic()
    if now < _failures["until"]:
        raise ValueError(f"too many wrong PINs; try again in {int(_failures['until'] - now) + 1} seconds")
    if not isinstance(pin, str) or not _PIN.fullmatch(pin) or not hmac.compare_digest(
        _hash(pin, bytes.fromhex(stored.get("salt", ""))), str(stored.get("hash", ""))
    ):
        _failures["count"] += 1
        if _failures["count"] >= _PIN_TRIES:
            _failures["count"], _failures["until"] = 0, now + _PIN_WAIT
        raise ValueError("wrong PIN")
    _failures["count"] = 0


def update(changes: Any) -> dict[str, Any]:
    """Applies {enabled, session_id, family_name, family_phone, read_aloud, slow_speech, pin}.

    Turning the mode off, or changing or removing the PIN, needs the current PIN when one is set
    (``current_pin``). An empty ``pin`` removes it.
    """
    if not isinstance(changes, dict):
        raise ValueError("changes must be an object")
    allowed = {"enabled", "session_id", "family_name", "family_phone", "read_aloud", "slow_speech", "pin", "current_pin"}
    if set(changes) - allowed:
        raise ValueError(f"unknown elder mode fields: {', '.join(sorted(set(changes) - allowed))}")
    with _LOCK:
        value = _load()
        guarded = changes.get("enabled") is False and value.get("enabled") is True or "pin" in changes
        if guarded:
            _check_pin(value, changes.get("current_pin"))
        for key in ("enabled", "read_aloud", "slow_speech"):
            if key in changes:
                if not isinstance(changes[key], bool):
                    raise ValueError(f"{key} must be true or false")
                value[key] = changes[key]
        if "session_id" in changes:
            session = changes["session_id"]
            if session is not None and (not isinstance(session, str) or not 0 < len(session) <= 128):
                raise ValueError("session_id must be a conversation id")
            value["session_id"] = session
        if "family_name" in changes:
            name = changes["family_name"]
            if not isinstance(name, str) or len(name.strip()) > _MAX_NAME:
                raise ValueError(f"family_name is text of at most {_MAX_NAME} characters")
            value["family_name"] = " ".join(name.split())
        if "family_phone" in changes:
            phone = changes["family_phone"]
            if not isinstance(phone, str) or (phone.strip() and not _PHONE.fullmatch(phone.strip())):
                raise ValueError("family_phone must be a phone number")
            value["family_phone"] = phone.strip()
        if "pin" in changes:
            pin = changes["pin"]
            if pin == "":
                value.pop("pin", None)
            elif isinstance(pin, str) and _PIN.fullmatch(pin):
                salt = secrets.token_bytes(16)
                value["pin"] = {"salt": salt.hex(), "hash": _hash(pin, salt)}
            else:
                raise ValueError("the PIN is 4 to 6 digits")
        _save(value)
        return _public(value)


def elder_system_suffix() -> str:
    """The system prompt section while the mode is on; empty otherwise."""
    value = _load()
    if value.get("enabled") is not True:
        return ""
    family = value.get("family_name") or ""
    who = f" ({family})" if family else ""
    return (
        "Elder mode: the person using this phone is an older adult who mostly speaks to you and "
        "listens to your replies read aloud. Answer in a few short, plain sentences that sound "
        "natural when spoken: no tables, code, links, headings or long lists, no cards, and say "
        "numbers, dates and times in words people say. Be patient and respectful, not chatty. Do "
        "one thing at a time and say in one sentence what you did. When they ask how to do "
        "something on the phone, give at most three short steps, then offer the next ones. If "
        "something looks like a scam (someone asking for money or a transfer, verification codes, "
        "bank card or ID numbers, a prize, a parcel or police problem that needs paying, a "
        "guaranteed investment, a link to open), say clearly that it may be a scam, do not help "
        f"with it, and suggest they ask a family member{who} first. Never ask them for passwords "
        "or verification codes."
    )
