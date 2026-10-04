from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable

from agent_workspace.application.ports import EventListener
from agent_workspace.core.events import Event

_LOGGER = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._listeners: list[EventListener] = []

    def subscribe(self, listener: EventListener) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    async def publish(self, event: Event) -> None:
        task = asyncio.current_task()
        for listener in tuple(self._listeners):
            try:
                result = listener(event)
                if inspect.isawaitable(result):
                    await result
            except asyncio.CancelledError:
                if task is not None and task.cancelling():
                    raise
                _LOGGER.exception(
                    "event listener was cancelled for %s (%r)",
                    event.type,
                    listener,
                )
            except Exception:
                _LOGGER.exception(
                    "event listener failed for %s (%r)",
                    event.type,
                    listener,
                )
