"""Notifications kept on the phone for digests (off until the user turns it on).

The Android notification listener reports each notification here while the journal is on
(AgentNotificationListener → /mobile/notification-journal/add); the recent_notifications tool
reads them back so the agent can sort them into what matters, what can wait and ads, and pull out
pickup codes, flights and meeting changes. Verification codes, and card and ID numbers, are masked
as they arrive and never stored; entries older than 48 hours are dropped; at most 500 are kept.
Stored in <data>/notification-journal.json, which never leaves the phone by itself.

mask_private is how any notification text reaches the model (notification rules, the notification
tools): card and ID numbers masked, and verification codes too unless the rule or the task is about
codes (about_codes; the runtime controller marks each task, bind_codes).
"""

from __future__ import annotations

import contextvars
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

import mobile_private_numbers

MAX_ENTRIES = 500
KEEP_SECONDS = 48 * 3600
_lock = threading.Lock()
# The words that announce a verification code. A bare "code" is not enough: "summarise code
# reviews", "QR code", "postal code" are not about these codes.
_CODE_WORDS = (
    r"验证码|校验码|动态码|动态密码|确认码|安全码|登录码|短信码"
    r"|(?<![a-z])(?:verification code|security code|one[- ]time (?:pass)?code|otp|passcode"
    r"|(?:sms|text|login|sign[- ]in|2fa|auth|authentication|confirmation|access) codes?"
    r")(?![a-z])"
)
# A rule or request about codes: "把短信验证码读给我", "fill in the SMS code".
_ABOUT_CODES = re.compile(_CODE_WORDS, re.IGNORECASE)
# A notification that names a code (取款码, a cash withdrawal code, too), anywhere in it: the code
# can come first ("482913（登录验证码）", "Use 482913 as your security code") or after other numbers.
_NAMES_CODE = re.compile(_CODE_WORDS + r"|取款码", re.IGNORECASE)
# A number such a notification may carry as its code: 4 to 8 digits, or 3 and 3 ("482-913"). The
# kept ends of a masked card or ID number ("4111********1111") are not one.
_CODE_NUMBER = re.compile(r"(?<![\d*])(?:\d{3}[- ]\d{3}|\d{4,8})(?![\d*])")
# A code next to a word that announces one, a bare "code" included: "Your code is 1234",
# "WhatsApp code 482-913".
_CODE = re.compile(
    r"(验证码|校验码|动态码|动态密码|确认码|安全码|登录码|取款码|verification code|security code|one[- ]time (?:pass)?code|otp|code)"
    r"([^\d]{0,16})(\d{3}[- ]\d{3}(?!\d)|\d{4,8})",
    re.IGNORECASE,
)
# Numbers that are meant to be read: a pickup code ("取件码 4829", "pickup code 4829"), a postal code.
_NOT_SECRET = re.compile(
    r"取件|取餐|取货|提货|快递柜|邮编|邮政编码|postal|zip|post ?code|pick[- ]?up|parcel|locker|tracking",
    re.IGNORECASE,
)
# Digits written in groups ("110101 19900307 123X"), checked joined, as memory does (mobile_memory).
_GROUPED = re.compile(r"(?<![\dXx])\d[\d -]{14,24}[\dXx](?![\dXx])")
# Whether the running task may read verification codes in notifications (bound per task).
_CODES_WANTED: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "notification_codes", default=False
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


def names_code(text: str) -> bool:
    """Whether [text] names a verification code anywhere (elder mode uses this too)."""
    return _NAMES_CODE.search(text) is not None


def _readable(text: str, start: int) -> bool:
    """Whether the number at [start] is introduced as a pickup or postal code: the nearest word
    before it says so, not a word that announces a verification code."""
    before = text[max(0, start - 16) : start]
    readable = [match.end() for match in _NOT_SECRET.finditer(before)]
    secret = [match.end() for match in _NAMES_CODE.finditer(before)]
    return bool(readable) and (not secret or readable[-1] > secret[-1])


def mask_codes(text: str) -> str:
    if names_code(text):
        return _CODE_NUMBER.sub(
            lambda match: match.group() if _readable(text, match.start()) else "[已隐藏]", text
        )
    return _CODE.sub(
        lambda match: match.group()
        if _readable(text, match.start(3))
        else f"{match.group(1)}{match.group(2)}[已隐藏]",
        text,
    )


def about_codes(*texts: object) -> bool:
    """Whether a rule's words, or a task's request, ask about verification codes."""
    return any(isinstance(text, str) and _ABOUT_CODES.search(text) for text in texts)


def bind_codes(wanted: bool) -> contextvars.Token[bool]:
    return _CODES_WANTED.set(bool(wanted))


def reset_codes(token: contextvars.Token[bool]) -> None:
    _CODES_WANTED.reset(token)


def codes_wanted() -> bool:
    return _CODES_WANTED.get()


def _mask_grouped(match: re.Match[str]) -> str:
    joined = re.sub(r"[ -]", "", match.group())
    found = mobile_private_numbers.find(joined)
    return found[0]["masked"] if found and found[0]["value"] == joined else match.group()


def mask_private(text: str, *, codes: bool = True) -> str:
    """[text] as it may reach the model: card and ID numbers masked (only ones with a valid check
    digit), and verification codes too unless [codes] is False."""
    text = _GROUPED.sub(_mask_grouped, mobile_private_numbers.mask(text))
    return mask_codes(text) if codes else text


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
        "title": mask_private(str(payload.get("title") or "")[:200]),
        "text": mask_private(str(payload.get("text") or "")[:1000]),
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


def _phone_zone() -> Any:
    """The phone's own time zone (the engine process may run in UTC), or None for the process's."""
    from datetime import timedelta, timezone

    try:
        from android_adapter.clock_calendar import phone_now

        now = phone_now() or {}
    except Exception:
        return None
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(str(now["zone"]))
    except Exception:
        pass
    # Python on the phone has no time zone database: the offset the phone reports for now.
    offset = now.get("offset_seconds")
    if type(offset) is int and abs(offset) < 86400:
        return timezone(timedelta(seconds=offset))
    return None


def recent(hours: float = 2, *, limit: int = 200, now: float | None = None) -> list[dict[str, Any]]:
    current = time.time() if now is None else now
    since = current - max(0.1, min(float(hours), KEEP_SECONDS / 3600)) * 3600
    with _lock:
        entries = _read()["entries"]
    picked = [item for item in entries if isinstance(item, dict) and float(item.get("at", 0)) >= since]
    picked = picked[-max(1, min(int(limit), MAX_ENTRIES)):]
    from datetime import datetime

    zone = _phone_zone()
    return [
        {"time": datetime.fromtimestamp(float(item["at"]), zone).strftime("%m-%d %H:%M"), "app": item.get("app"),
         "title": item.get("title"), "text": item.get("text")}
        for item in reversed(picked)
    ]
