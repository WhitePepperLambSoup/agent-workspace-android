"""Client-side event sequence and duplicate suppression helpers."""

from __future__ import annotations

from collections import deque


class EventCursor:
    def __init__(self, after: int = 0, *, max_event_ids: int = 2048) -> None:
        if after < 0:
            raise ValueError("after must be non-negative")
        if max_event_ids < 1:
            raise ValueError("max_event_ids must be positive")
        self._last_sequence = after
        self._max_event_ids = max_event_ids
        self._event_ids: set[str] = set()
        self._event_order: deque[str] = deque()

    @property
    def last_sequence(self) -> int:
        return self._last_sequence

    def advance(self, sequence: int) -> None:
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        if sequence > self._last_sequence:
            self._last_sequence = sequence

    def accept(self, event_id: str, sequence: int) -> bool:
        if not isinstance(event_id, str) or not event_id:
            return False
        if sequence <= self._last_sequence or sequence <= 0:
            return False
        if event_id in self._event_ids:
            return False
        self._last_sequence = sequence
        self._event_ids.add(event_id)
        self._event_order.append(event_id)
        while len(self._event_order) > self._max_event_ids:
            self._event_ids.discard(self._event_order.popleft())
        return True
