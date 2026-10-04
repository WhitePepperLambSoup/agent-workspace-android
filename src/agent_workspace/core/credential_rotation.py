"""Credential age tracking and rotation workflow.

The manager records when provider credentials were stored or used and
computes rotation recommendations. It never reads or logs the secret itself.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agent_workspace.credentials import CredentialStore


class CredentialRotationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CredentialStatus:
    provider_id: str
    stored_at: float
    last_used_at: float | None = None
    age_days: float = 0.0

    def to_document(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "stored_at": self.stored_at,
            "last_used_at": self.last_used_at,
        }


class CredentialRotationManager:
    """Persist credential age metadata beside the credential store."""

    def __init__(
        self,
        store: CredentialStore,
        metadata_path: str | Path,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self.path = Path(metadata_path)
        self._clock = clock
        self._records: dict[str, dict[str, float | None]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CredentialRotationError(f"cannot read credential metadata: {exc}") from exc
        if not isinstance(document, dict) or not isinstance(document.get("records"), dict):
            raise CredentialRotationError("credential metadata is invalid")
        for provider_id, raw in document["records"].items():
            if not isinstance(provider_id, str) or not isinstance(raw, dict):
                raise CredentialRotationError("credential metadata is invalid")
            stored_at = raw.get("stored_at")
            last_used_at = raw.get("last_used_at")
            if not isinstance(stored_at, (int, float)) or (
                last_used_at is not None and not isinstance(last_used_at, (int, float))
            ):
                raise CredentialRotationError("credential metadata is invalid")
            self._records[provider_id] = {
                "stored_at": float(stored_at),
                "last_used_at": float(last_used_at) if last_used_at is not None else None,
            }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps({"records": self._records}, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def record_stored(self, provider_id: str) -> None:
        if not provider_id:
            raise CredentialRotationError("provider id may not be empty")
        self._records[provider_id] = {"stored_at": self._clock(), "last_used_at": None}
        self._save()

    def record_used(self, provider_id: str) -> None:
        record = self._records.get(provider_id)
        if record is None:
            self.record_stored(provider_id)
            record = self._records[provider_id]
        record["last_used_at"] = self._clock()
        self._save()

    def status(self, provider_id: str) -> CredentialStatus | None:
        record = self._records.get(provider_id)
        if record is None:
            return None
        stored_value = record["stored_at"]
        if stored_value is None:
            raise CredentialRotationError("credential stored_at metadata is missing")
        last_used_value = record["last_used_at"]
        now = self._clock()
        age_days = max(0.0, (now - float(stored_value)) / 86400.0)
        return CredentialStatus(
            provider_id=provider_id,
            stored_at=float(stored_value),
            last_used_at=float(last_used_value) if last_used_value is not None else None,
            age_days=age_days,
        )

    def list_statuses(self) -> list[CredentialStatus]:
        statuses: list[CredentialStatus] = []
        for provider_id in self._records:
            status = self.status(provider_id)
            if status is not None:
                statuses.append(status)
        statuses.sort(key=lambda status: (-status.age_days, status.provider_id))
        return statuses

    def recommendations(
        self, *, warn_days: float = 60.0, rotate_days: float = 90.0
    ) -> dict[str, str]:
        if warn_days <= 0 or rotate_days < warn_days:
            raise CredentialRotationError("invalid rotation thresholds")
        result: dict[str, str] = {}
        for provider_id in self._records:
            status = self.status(provider_id)
            if status is None:
                continue
            if status.age_days >= rotate_days:
                result[provider_id] = "rotate"
            elif status.age_days >= warn_days:
                result[provider_id] = "warn"
        return result

    def rotate(self, provider_id: str, new_secret: str) -> None:
        if not new_secret:
            raise CredentialRotationError("new credential secret may not be empty")
        self._store.set(provider_id, new_secret)
        self.record_stored(provider_id)


__all__ = [
    "CredentialRotationError",
    "CredentialRotationManager",
    "CredentialStatus",
]
