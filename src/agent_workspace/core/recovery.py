"""Shared error classification and bounded recovery decisions.

The runner and providers expose different exception types, but callers need a
single, stable decision before presenting a retry or an alternative action.
This module contains no I/O and is safe to use from providers, tools, and
acceptance harnesses.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from enum import StrEnum
from typing import Any


class RecoveryKind(StrEnum):
    RETRYABLE = "retryable"
    PARAMETER = "parameter_error"
    PERMISSION = "permission_required"
    UNAVAILABLE = "unavailable"
    FATAL = "fatal"


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """A renderer-safe, typed decision for one failed operation."""

    kind: RecoveryKind
    retryable: bool
    retry_after_seconds: float | None
    suggested_arguments: dict[str, Any]
    alternative_tools: tuple[str, ...]
    requires_user_action: bool
    fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "retryable": self.retryable,
            "retry_after_seconds": self.retry_after_seconds,
            "suggested_arguments": dict(self.suggested_arguments),
            "alternative_tools": list(self.alternative_tools),
            "requires_user_action": self.requires_user_action,
            "error_fingerprint": self.fingerprint,
        }


def parse_retry_after(value: str | int | float | None, *, maximum: float = 30.0) -> float | None:
    """Parse seconds or an HTTP date and clamp it to a finite safe bound."""

    if value is None:
        return None
    try:
        seconds = float(str(value))
    except (TypeError, ValueError):
        try:
            parsed = parsedate_to_datetime(str(value).strip())
        except (TypeError, ValueError, OverflowError):
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        seconds = float((parsed - datetime.now(UTC)).total_seconds())
    if not math.isfinite(seconds):
        return None
    return max(0.0, min(seconds, maximum))


def bounded_backoff(attempt: int, *, base: float = 0.25, maximum: float = 2.0) -> float:
    """Return deterministic exponential backoff for a one-based attempt."""

    if type(attempt) is not int or attempt < 1:
        raise ValueError("attempt must be a positive integer")
    if base < 0 or maximum < 0 or not math.isfinite(base + maximum):
        raise ValueError("backoff bounds must be finite and non-negative")
    return min(maximum, base * (2.0 ** (attempt - 1)))


def classify_error(
    error: BaseException | None,
    *,
    timeout: bool = False,
    retry_after: float | None = None,
    suggested_arguments: dict[str, Any] | None = None,
    alternative_tools: tuple[str, ...] | list[str] = (),
    requires_user_action: bool | None = None,
) -> RetryDecision:
    """Classify ProviderError/ToolError-like objects without importing either layer."""

    name = type(error).__name__ if error is not None else "unknown"
    text = str(error) if error is not None else "unknown error"
    lowered = text.casefold()
    if timeout or bool(getattr(error, "retryable", False)):
        kind = RecoveryKind.RETRYABLE
    elif name in {"ToolArgumentError", "ValueError", "TypeError"}:
        kind = RecoveryKind.PARAMETER
    elif name in {"PermissionError", "ApprovalRequiredError"}:
        kind = RecoveryKind.PERMISSION
    elif name in {"FileNotFoundError", "OSError", "ToolWorkerPreconditionError"}:
        kind = RecoveryKind.UNAVAILABLE
    else:
        kind = RecoveryKind.FATAL
    retryable = kind is RecoveryKind.RETRYABLE
    if requires_user_action is None:
        requires_user_action = kind in {RecoveryKind.PARAMETER, RecoveryKind.PERMISSION}
    alternatives = tuple(dict.fromkeys(tool for tool in alternative_tools if tool))
    fingerprint = hashlib.sha256(f"{name}\n{kind.value}\n{lowered}".encode()).hexdigest()
    return RetryDecision(
        kind=kind,
        retryable=retryable,
        retry_after_seconds=parse_retry_after(retry_after) if retry_after is not None else None,
        suggested_arguments=dict(suggested_arguments or {}),
        alternative_tools=alternatives,
        requires_user_action=requires_user_action,
        fingerprint=fingerprint,
    )


class FailureDeduper:
    """Bounded in-memory deduplication for repeated identical failures."""

    def __init__(self, maximum: int = 256) -> None:
        if type(maximum) is not int or maximum < 1:
            raise ValueError("maximum must be a positive integer")
        self._maximum = maximum
        self._seen: dict[str, None] = {}

    def first(self, decision: RetryDecision) -> bool:
        if decision.fingerprint in self._seen:
            return False
        self._seen[decision.fingerprint] = None
        if len(self._seen) > self._maximum:
            del self._seen[next(iter(self._seen))]
        return True
