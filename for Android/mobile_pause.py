"""Pausing a running task without stopping it (the phone control window's pause button).

A paused task finishes what it is doing (a model reply streaming in, an action under way) and then
waits: before its next model request and before its next action on the phone. Meanwhile the user
can add to the request (steer); it is read when the task goes on. The task stays "running"
throughout, so approvals, steering and stopping all keep working.
"""

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import AsyncIterator
from typing import Any

_CURRENT: contextvars.ContextVar[str | None] = contextvars.ContextVar("mobile_task", default=None)
# task id -> an event that is set while the task may run.
_GATES: dict[str, asyncio.Event] = {}


def bind_task(task_id: str) -> contextvars.Token[str | None]:
    """The task the current coroutine runs (model calls and tools started from it inherit it)."""
    return _CURRENT.set(task_id)


def forget_task(task_id: str) -> None:
    """The task ended: nothing is held for it any more."""
    gate = _GATES.pop(task_id, None)
    if gate is not None:
        gate.set()


def _gate(task_id: str) -> asyncio.Event:
    gate = _GATES.get(task_id)
    if gate is None:
        gate = _GATES[task_id] = asyncio.Event()
        gate.set()
    return gate


def pause(task_id: str) -> None:
    _gate(task_id).clear()


def unpause(task_id: str) -> None:
    _gate(task_id).set()


def paused(task_id: str) -> bool:
    gate = _GATES.get(task_id)
    return gate is not None and not gate.is_set()


async def wait_if_paused() -> None:
    """Holds the current task here while it is paused."""
    task_id = _CURRENT.get()
    if task_id is None:
        return
    gate = _GATES.get(task_id)
    if gate is not None and not gate.is_set():
        await gate.wait()


class PausableProvider:
    """A model provider that holds each new request while its task is paused."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provider, name)

    def stream(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        return self._held(lambda: self._provider.stream(*args, **kwargs))

    @staticmethod
    async def _held(start: Any) -> AsyncIterator[Any]:
        await wait_if_paused()
        async for item in start():
            yield item


class _PausableRetryProvider(PausableProvider):
    # Only for providers that report their retries (the runner checks for this method).
    def stream_with_attempts(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        return self._held(lambda: self._provider.stream_with_attempts(*args, **kwargs))


def make_pausable(runner: Any) -> None:
    """Wraps the runner's provider once (a later wrap is a no-op)."""
    provider = getattr(runner, "_provider", None)
    if provider is None or isinstance(provider, PausableProvider):
        return
    wrapper = _PausableRetryProvider if callable(getattr(provider, "stream_with_attempts", None)) else PausableProvider
    runner._provider = wrapper(provider)
