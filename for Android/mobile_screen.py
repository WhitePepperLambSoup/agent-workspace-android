"""Which screen a task's phone actions go to.

A task from a conversation may work on the background screen (Device & tools → Background
operation, needs Shizuku): an off-screen display the agent uses while the user keeps using the phone.
A task from the phone control panel is about the app the user is looking at, so it always uses the
phone's own screen. The runtime controller marks each task (bind); android_system asks (allowed) and
the phone decides, by the user's setting, whether to use the background screen.
"""

from __future__ import annotations

import contextvars

_ALLOWED: contextvars.ContextVar[bool] = contextvars.ContextVar("mobile_background_screen", default=False)


def bind(allowed: bool) -> contextvars.Token[bool]:
    return _ALLOWED.set(bool(allowed))


def reset(token: contextvars.Token[bool]) -> None:
    _ALLOWED.reset(token)


def allowed() -> bool:
    return _ALLOWED.get()


__all__ = ["allowed", "bind", "reset"]
