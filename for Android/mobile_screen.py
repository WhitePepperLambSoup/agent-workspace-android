"""Which screen a task's phone actions go to.

A task from a conversation may work on the background screen (Device & tools → Background
operation, needs Shizuku): an off-screen display the agent uses while the user keeps using the phone.
A task from the phone control panel is about the app the user is looking at, so it always uses the
phone's own screen. The runtime controller marks each task (bind); android_system asks (allowed) and
the phone decides, by the user's setting, whether to use the background screen.

The background screen is drawn while the phone is locked. There it is only read then, unless the
user started the task on the phone in person (bind_in_person): not a schedule, a notification
rule, another device or another app.
"""

from __future__ import annotations

import contextvars

_ALLOWED: contextvars.ContextVar[bool] = contextvars.ContextVar("mobile_background_screen", default=False)
_IN_PERSON: contextvars.ContextVar[bool] = contextvars.ContextVar("mobile_in_person", default=False)


def bind(allowed: bool) -> contextvars.Token[bool]:
    return _ALLOWED.set(bool(allowed))


def reset(token: contextvars.Token[bool]) -> None:
    _ALLOWED.reset(token)


def allowed() -> bool:
    return _ALLOWED.get()


def bind_in_person(value: bool) -> contextvars.Token[bool]:
    return _IN_PERSON.set(bool(value))


def reset_in_person(token: contextvars.Token[bool]) -> None:
    _IN_PERSON.reset(token)


def in_person() -> bool:
    return _IN_PERSON.get()


__all__ = ["allowed", "bind", "bind_in_person", "in_person", "reset", "reset_in_person"]
