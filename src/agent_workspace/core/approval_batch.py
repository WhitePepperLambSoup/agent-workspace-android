"""File-backed approval batch review.

A batch file is a JSON object with ``requests`` and ``resolutions`` arrays.
Reviewers list pending requests and apply many allow/deny decisions in one
call; expired requests are default-deny and reported separately so a reviewer
can tell "denied by me" from "timed out".
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ApprovalBatchError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BatchApprovalRequest:
    id: str
    tool: str
    arguments: dict[str, Any]
    created_at: float
    expires_at: float
    priority: int = 100
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool": self.tool,
            "arguments": self.arguments,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "priority": self.priority,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class ApprovalBatchDecision:
    request_id: str
    allowed: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ApprovalBatchReviewReport:
    applied: tuple[str, ...]
    denied: tuple[str, ...]
    expired: tuple[str, ...]
    unknown: tuple[str, ...]
    remaining: tuple[str, ...]
    dry_run: bool

    def to_document(self) -> dict[str, Any]:
        return {
            "applied": list(self.applied),
            "denied": list(self.denied),
            "expired": list(self.expired),
            "unknown": list(self.unknown),
            "remaining": list(self.remaining),
            "dry_run": self.dry_run,
        }


def _request_from_document(document: object) -> BatchApprovalRequest:
    if not isinstance(document, dict):
        raise ApprovalBatchError("approval batch request must be an object")
    try:
        request = BatchApprovalRequest(
            id=str(document["id"]),
            tool=str(document["tool"]),
            arguments=dict(document["arguments"]),
            created_at=float(document["created_at"]),
            expires_at=float(document["expires_at"]),
            priority=int(document.get("priority", 100)),
            session_id=str(document["session_id"])
            if document.get("session_id") is not None
            else None,
            metadata=dict(document.get("metadata", {})),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ApprovalBatchError(f"approval batch request is invalid: {exc}") from exc
    if not request.id or not request.tool or not isinstance(request.arguments, dict):
        raise ApprovalBatchError("approval batch request is invalid")
    return request


class ApprovalBatchReviewer:
    """Load, submit, review, and persist one approval batch file."""

    def __init__(
        self,
        path: str | Path,
        *,
        default_ttl_seconds: float = 300.0,
        clock: Any = time.time,
    ) -> None:
        if default_ttl_seconds <= 0:
            raise ApprovalBatchError("approval TTL must be positive")
        self.path = Path(path)
        self.default_ttl_seconds = default_ttl_seconds
        self._clock = clock
        self._requests: dict[str, BatchApprovalRequest] = {}
        self._resolutions: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ApprovalBatchError(f"cannot read approval batch: {exc}") from exc
        if not isinstance(document, dict) or not isinstance(document.get("requests"), list):
            raise ApprovalBatchError("approval batch file is invalid")
        for raw in document["requests"]:
            request = _request_from_document(raw)
            if request.id in self._requests:
                raise ApprovalBatchError(f"duplicate approval request id: {request.id}")
            self._requests[request.id] = request
        raw_resolutions = document.get("resolutions", [])
        if not isinstance(raw_resolutions, list):
            raise ApprovalBatchError("approval batch resolutions must be an array")
        for raw in raw_resolutions:
            if not isinstance(raw, dict) or not isinstance(raw.get("request_id"), str):
                raise ApprovalBatchError("approval batch resolution is invalid")
            self._resolutions[raw["request_id"]] = raw

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(
                {
                    "requests": [request.to_document() for request in self._requests.values()],
                    "resolutions": [self._resolutions[key] for key in sorted(self._resolutions)],
                },
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, self.path)

    def submit(
        self,
        tool: str,
        arguments: dict[str, Any],
        *,
        session_id: str | None = None,
        priority: int = 100,
        ttl_seconds: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> BatchApprovalRequest:
        if not tool or not isinstance(arguments, dict):
            raise ApprovalBatchError("approval tool and arguments are invalid")
        for value in (arguments, metadata or {}):
            try:
                json.dumps(value, sort_keys=True)
            except (TypeError, ValueError) as exc:
                raise ApprovalBatchError(
                    f"approval arguments must be JSON-serializable: {exc}"
                ) from exc
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            raise ApprovalBatchError("approval TTL must be positive")
        now = self._clock()
        request = BatchApprovalRequest(
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
        self.save()
        return request

    def pending(self, *, now: float | None = None) -> tuple[BatchApprovalRequest, ...]:
        reference = self._clock() if now is None else now
        pending = [
            request
            for request in self._requests.values()
            if request.id not in self._resolutions and request.expires_at > reference
        ]
        pending.sort(key=lambda request: (request.priority, request.created_at, request.id))
        return tuple(pending)

    def review(
        self,
        decisions: list[ApprovalBatchDecision] | tuple[ApprovalBatchDecision, ...],
        *,
        dry_run: bool = False,
        now: float | None = None,
    ) -> ApprovalBatchReviewReport:
        reference = self._clock() if now is None else now
        applied: list[str] = []
        denied: list[str] = []
        expired: list[str] = []
        unknown: list[str] = []
        resolutions: dict[str, dict[str, Any]] = dict(self._resolutions)
        for decision in decisions:
            request = self._requests.get(decision.request_id)
            if request is None or decision.request_id in self._resolutions:
                unknown.append(decision.request_id)
                continue
            if request.expires_at <= reference:
                expired.append(decision.request_id)
                resolutions[decision.request_id] = {
                    "request_id": decision.request_id,
                    "allowed": False,
                    "reason": "approval request expired",
                    "expired": True,
                    "resolved_at": reference,
                }
                continue
            resolutions[decision.request_id] = {
                "request_id": decision.request_id,
                "allowed": decision.allowed,
                "reason": decision.reason,
                "expired": False,
                "resolved_at": reference,
            }
            if decision.allowed:
                applied.append(decision.request_id)
            else:
                denied.append(decision.request_id)
        remaining = [
            request.id
            for request in self._requests.values()
            if request.id not in resolutions and request.expires_at > reference
        ]
        if not dry_run:
            self._resolutions = resolutions
            self.save()
        return ApprovalBatchReviewReport(
            applied=tuple(applied),
            denied=tuple(denied),
            expired=tuple(expired),
            unknown=tuple(unknown),
            remaining=tuple(remaining),
            dry_run=dry_run,
        )


def review_approval_batch_file(
    path: str | Path,
    decisions: list[tuple[str, bool, str]] | tuple[tuple[str, bool, str], ...],
    *,
    dry_run: bool = False,
    now: float | None = None,
) -> ApprovalBatchReviewReport:
    reviewer = ApprovalBatchReviewer(path)
    return reviewer.review(
        [
            ApprovalBatchDecision(request_id, allowed, reason)
            for request_id, allowed, reason in decisions
        ],
        dry_run=dry_run,
        now=now,
    )


__all__ = [
    "ApprovalBatchDecision",
    "ApprovalBatchError",
    "ApprovalBatchReviewReport",
    "ApprovalBatchReviewer",
    "BatchApprovalRequest",
    "review_approval_batch_file",
]
