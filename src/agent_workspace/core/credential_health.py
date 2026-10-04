"""Credential health dashboard data.

This module only consumes already-derived ``CredentialStatus`` metadata. It
never touches secret values, so its output is safe for dashboards, logs, and
audit exports.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from agent_workspace.core.credential_rotation import CredentialStatus

_HEALTHY = "healthy"
_WARN = "warn"
_ROTATE = "rotate"


@dataclass(frozen=True, slots=True)
class CredentialHealthEntry:
    provider_id: str
    age_days: float
    last_used_days: float | None
    health: str
    recommendation: str

    def to_document(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "age_days": self.age_days,
            "last_used_days": self.last_used_days,
            "health": self.health,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True, slots=True)
class CredentialHealthDashboard:
    warn_days: float
    rotate_days: float
    entries: tuple[CredentialHealthEntry, ...]
    healthy: int
    warning: int
    rotation_due: int
    total_age_days: float
    average_age_days: float
    oldest_age_days: float

    def to_document(self) -> dict[str, Any]:
        return {
            "thresholds": {
                "warn_days": self.warn_days,
                "rotate_days": self.rotate_days,
            },
            "summary": {
                "total": len(self.entries),
                "healthy": self.healthy,
                "warning": self.warning,
                "rotation_due": self.rotation_due,
                "average_age_days": self.average_age_days,
                "oldest_age_days": self.oldest_age_days,
            },
            "providers": [entry.to_document() for entry in self.entries],
        }


def credential_health_dashboard(
    statuses: Iterable[CredentialStatus],
    *,
    warn_days: float = 60.0,
    rotate_days: float = 90.0,
    now: float | None = None,
) -> CredentialHealthDashboard:
    if warn_days <= 0 or rotate_days < warn_days:
        raise ValueError("invalid credential health thresholds")
    entries: list[CredentialHealthEntry] = []
    healthy = 0
    warning = 0
    rotation_due = 0
    total_age = 0.0
    oldest = 0.0
    reference = time.time() if now is None else now
    for status in statuses:
        if status.age_days >= rotate_days:
            health = _ROTATE
            recommendation = "rotate now"
            rotation_due += 1
        elif status.age_days >= warn_days:
            health = _WARN
            recommendation = "schedule rotation"
            warning += 1
        else:
            health = _HEALTHY
            recommendation = "no action"
            healthy += 1
        last_used_days = (
            max(0.0, (reference - status.last_used_at) / 86400.0)
            if status.last_used_at is not None
            else None
        )
        entries.append(
            CredentialHealthEntry(
                provider_id=status.provider_id,
                age_days=status.age_days,
                last_used_days=last_used_days,
                health=health,
                recommendation=recommendation,
            )
        )
        total_age += status.age_days
        oldest = max(oldest, status.age_days)
    entries.sort(key=lambda entry: (-entry.age_days, entry.provider_id))
    count = len(entries)
    return CredentialHealthDashboard(
        warn_days=warn_days,
        rotate_days=rotate_days,
        entries=tuple(entries),
        healthy=healthy,
        warning=warning,
        rotation_due=rotation_due,
        total_age_days=total_age,
        average_age_days=total_age / count if count else 0.0,
        oldest_age_days=oldest,
    )


__all__ = [
    "CredentialHealthDashboard",
    "CredentialHealthEntry",
    "credential_health_dashboard",
]
