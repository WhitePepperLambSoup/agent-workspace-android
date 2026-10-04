"""Durable embedding batch queue.

Texts are persisted before any provider call, leased in bounded batches,
acknowledged on success, and re-queued with exponential backoff on failure.
Leases that outlive their timeout are recovered by ``requeue_stale`` so a
crashed worker never loses work.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_MAX_TEXT_BYTES = 32 * 1024


class EmbeddingQueueError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EmbeddingQueueItem:
    id: str
    text: str
    created_at: float
    attempts: int = 0
    next_attempt_at: float = 0.0
    status: str = "pending"
    leased_at: float | None = None
    completed_at: float | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "created_at": self.created_at,
            "attempts": self.attempts,
            "next_attempt_at": self.next_attempt_at,
            "status": self.status,
            "leased_at": self.leased_at,
            "completed_at": self.completed_at,
        }


class EmbeddingBatchQueue:
    """JSON-persisted work queue with recoverable leases."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_retries: int = 3,
        backoff_seconds: float = 30.0,
        lease_timeout_seconds: float = 300.0,
        clock: Any = time.time,
    ) -> None:
        if max_retries < 0 or backoff_seconds < 0 or lease_timeout_seconds <= 0:
            raise EmbeddingQueueError("embedding queue retries/backoff/lease timeout are invalid")
        self.path = Path(path)
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.lease_timeout_seconds = lease_timeout_seconds
        self._clock = clock
        self._items: dict[str, EmbeddingQueueItem] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EmbeddingQueueError(f"cannot read embedding queue: {exc}") from exc
        raw_items = document.get("items") if isinstance(document, dict) else None
        if not isinstance(raw_items, list):
            raise EmbeddingQueueError("embedding queue must declare an items array")
        for raw in raw_items:
            item = self._parse(raw)
            self._items[item.id] = item

    def _parse(self, raw: object) -> EmbeddingQueueItem:
        if not isinstance(raw, dict):
            raise EmbeddingQueueError("embedding queue item is invalid")
        try:
            return EmbeddingQueueItem(
                id=str(raw["id"]),
                text=str(raw["text"]),
                created_at=float(raw["created_at"]),
                attempts=int(raw.get("attempts", 0)),
                next_attempt_at=float(raw.get("next_attempt_at", 0.0)),
                status=str(raw.get("status", "pending")),
                leased_at=float(raw["leased_at"]) if raw.get("leased_at") is not None else None,
                completed_at=float(raw["completed_at"])
                if raw.get("completed_at") is not None
                else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingQueueError("embedding queue item is invalid") from exc

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(
                {"items": [item.to_document() for item in self._items.values()]},
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, self.path)

    def enqueue(self, text: str, *, item_id: str | None = None) -> EmbeddingQueueItem:
        if not isinstance(text, str) or not text.strip():
            raise EmbeddingQueueError("embedding text may not be empty")
        if len(text.encode("utf-8")) > _MAX_TEXT_BYTES:
            raise EmbeddingQueueError(f"embedding text exceeds {_MAX_TEXT_BYTES} utf-8 bytes")
        now = float(self._clock())
        item = EmbeddingQueueItem(
            id=item_id or uuid.uuid4().hex,
            text=text,
            created_at=now,
            next_attempt_at=now,
        )
        self._items[item.id] = item
        self.save()
        return item

    def lease_batch(
        self, limit: int, *, now: float | None = None
    ) -> tuple[EmbeddingQueueItem, ...]:
        if limit < 1:
            raise EmbeddingQueueError("embedding batch limit must be positive")
        current = float(self._clock()) if now is None else now
        due = [
            item
            for item in self._items.values()
            if item.status == "pending" and item.next_attempt_at <= current
        ]
        due.sort(key=lambda item: (item.next_attempt_at, item.created_at, item.id))
        leased: list[EmbeddingQueueItem] = []
        for item in due[:limit]:
            updated = EmbeddingQueueItem(
                id=item.id,
                text=item.text,
                created_at=item.created_at,
                attempts=item.attempts,
                next_attempt_at=item.next_attempt_at,
                status="leased",
                leased_at=current,
                completed_at=None,
            )
            self._items[item.id] = updated
            leased.append(updated)
        if leased:
            self.save()
        return tuple(leased)

    def complete(self, item_ids: list[str] | tuple[str, ...]) -> int:
        now = float(self._clock())
        completed = 0
        for item_id in item_ids:
            item = self._items.get(item_id)
            if item is None or item.status != "leased":
                continue
            self._items[item_id] = EmbeddingQueueItem(
                id=item.id,
                text=item.text,
                created_at=item.created_at,
                attempts=item.attempts,
                next_attempt_at=item.next_attempt_at,
                status="done",
                leased_at=item.leased_at,
                completed_at=now,
            )
            completed += 1
        if completed:
            self.save()
        return completed

    def fail(self, item_ids: list[str] | tuple[str, ...]) -> int:
        now = float(self._clock())
        failed = 0
        for item_id in item_ids:
            item = self._items.get(item_id)
            if item is None or item.status != "leased":
                continue
            attempts = item.attempts + 1
            if attempts > self.max_retries:
                status = "dead"
                next_attempt_at = item.next_attempt_at
            else:
                status = "pending"
                next_attempt_at = now + self.backoff_seconds * (2 ** (attempts - 1))
            self._items[item_id] = EmbeddingQueueItem(
                id=item.id,
                text=item.text,
                created_at=item.created_at,
                attempts=attempts,
                next_attempt_at=next_attempt_at,
                status=status,
                leased_at=None,
                completed_at=None,
            )
            failed += 1
        if failed:
            self.save()
        return failed

    def requeue_stale(self, *, now: float | None = None) -> int:
        current = float(self._clock()) if now is None else now
        recovered = 0
        for item in list(self._items.values()):
            if item.status != "leased" or item.leased_at is None:
                continue
            if current - item.leased_at < self.lease_timeout_seconds:
                continue
            self._items[item.id] = EmbeddingQueueItem(
                id=item.id,
                text=item.text,
                created_at=item.created_at,
                attempts=item.attempts,
                next_attempt_at=current,
                status="pending",
                leased_at=None,
                completed_at=None,
            )
            recovered += 1
        if recovered:
            self.save()
        return recovered

    def prune_completed(self, *, cutoff: float | None = None, now: float | None = None) -> int:
        current = float(self._clock()) if now is None else now
        threshold = current - (cutoff if cutoff is not None else 86_400.0)
        stale = [
            item_id
            for item_id, item in self._items.items()
            if item.status == "done"
            and item.completed_at is not None
            and item.completed_at < threshold
        ]
        for item_id in stale:
            del self._items[item_id]
        if stale:
            self.save()
        return len(stale)

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self._items.values():
            counts[item.status] = counts.get(item.status, 0) + 1
        return counts

    def __len__(self) -> int:
        return len(self._items)


__all__ = [
    "EmbeddingBatchQueue",
    "EmbeddingQueueError",
    "EmbeddingQueueItem",
]
