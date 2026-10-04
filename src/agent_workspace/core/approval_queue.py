"""Bounded approval queue with TTL, priority, and default-deny expiry."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


class ApprovalQueueError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    id: str
    tool: str
    arguments: dict[str, Any]
    created_at: float
    expires_at: float
    priority: int = 100
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ApprovalResolution:
    request_id: str
    allowed: bool
    reason: str = ""
    expired: bool = False


class ApprovalQueue:
    """Prioritized TTL queue.

    ``peek`` returns the highest-priority (lowest number) unexpired request;
    ``resolve`` removes it and returns an explicit expiry marker so callers
    can distinguish "user said no" from "the approval timed out".
    """

    def __init__(
        self,
        *,
        default_ttl_seconds: float = 300.0,
        max_pending: int = 256,
        clock: Any = time.monotonic,
    ) -> None:
        if default_ttl_seconds <= 0 or max_pending < 1:
            raise ValueError("approval queue TTL and capacity must be positive")
        self.default_ttl_seconds = default_ttl_seconds
        self.max_pending = max_pending
        self._clock = clock
        self._requests: dict[str, ApprovalRequest] = {}

    def submit(
        self,
        tool: str,
        arguments: dict[str, Any],
        *,
        session_id: str | None = None,
        priority: int = 100,
        ttl_seconds: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        if not tool or not isinstance(arguments, dict):
            raise ApprovalQueueError("approval tool and arguments are invalid")
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            raise ApprovalQueueError("approval TTL must be positive")
        self._expire()
        if len(self._requests) >= self.max_pending:
            raise ApprovalQueueError("approval queue is full")
        now = self._clock()
        request = ApprovalRequest(
            id=str(uuid.uuid4()),
            tool=tool,
            arguments=dict(arguments),
            created_at=now,
            expires_at=now + ttl,
            priority=priority,
            session_id=session_id,
            metadata=dict(metadata or {}),
        )
        self._requests[request.id] = request
        return request

    def _expire(self) -> None:
        now = self._clock()
        for request in tuple(self._requests.values()):
            if request.expires_at <= now:
                self._requests.pop(request.id, None)

    def peek(self) -> ApprovalRequest | None:
        self._expire()
        pending = list(self._requests.values())
        if not pending:
            return None
        return min(pending, key=lambda request: (request.priority, request.created_at, request.id))

    def resolve(self, request_id: str, *, allowed: bool, reason: str = "") -> ApprovalResolution:
        request = self._requests.pop(request_id, None)
        if request is None:
            raise ApprovalQueueError(f"unknown approval request: {request_id}")
        now = self._clock()
        if request.expires_at <= now:
            return ApprovalResolution(request_id, False, "approval request expired", expired=True)
        return ApprovalResolution(request_id, allowed, reason)

    def expire_request(self, request_id: str) -> ApprovalResolution:
        request = self._requests.get(request_id)
        if request is None:
            raise ApprovalQueueError(f"unknown approval request: {request_id}")
        self._requests.pop(request_id, None)
        return ApprovalResolution(request_id, False, "approval request expired", expired=True)

    def pending(self) -> tuple[ApprovalRequest, ...]:
        self._expire()
        return tuple(
            sorted(
                self._requests.values(),
                key=lambda request: (request.priority, request.created_at, request.id),
            )
        )

    def __len__(self) -> int:
        self._expire()
        return len(self._requests)


__all__ = [
    "ApprovalQueue",
    "ApprovalQueueError",
    "ApprovalRequest",
    "ApprovalResolution",
]
