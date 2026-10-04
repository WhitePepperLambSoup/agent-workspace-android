"""Cryptographically verifiable decision audit trail with SHA-256 hash chaining."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4


def _compute_entry_hash(
    decision_id: str,
    timestamp: float,
    actor: str,
    action: str,
    policy_rule: str,
    rationale: str,
    allowed: bool,
    payload_digest: str,
    prev_hash: str,
) -> str:
    serialized = json.dumps(
        {
            "decision_id": decision_id,
            "timestamp": timestamp,
            "actor": actor,
            "action": action,
            "policy_rule": policy_rule,
            "rationale": rationale,
            "allowed": allowed,
            "payload_digest": payload_digest,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DecisionAuditEntry:
    decision_id: str
    timestamp: float
    actor: str
    action: str
    policy_rule: str
    rationale: str
    allowed: bool
    payload_digest: str
    prev_hash: str
    entry_hash: str

    def to_document(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "policy_rule": self.policy_rule,
            "rationale": self.rationale,
            "allowed": self.allowed,
            "payload_digest": self.payload_digest,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }


class DecisionAuditTrail:
    """Tamper-evident audit trail maintaining an unbroken cryptographic hash chain."""

    GENESIS_HASH = "0" * 64

    def __init__(self, entries: list[DecisionAuditEntry] | None = None) -> None:
        self._entries: list[DecisionAuditEntry] = list(entries) if entries else []
        if self._entries:
            self.verify_integrity()

    @property
    def entries(self) -> tuple[DecisionAuditEntry, ...]:
        return tuple(self._entries)

    @property
    def latest_hash(self) -> str:
        return self._entries[-1].entry_hash if self._entries else self.GENESIS_HASH

    def record_decision(
        self,
        *,
        actor: str,
        action: str,
        policy_rule: str,
        rationale: str,
        allowed: bool,
        payload_data: Any = None,
        decision_id: str | None = None,
        timestamp: float | None = None,
    ) -> DecisionAuditEntry:
        """Record an authorization or tool execution decision."""
        did = decision_id or str(uuid4())
        ts = timestamp if timestamp is not None else time.time()
        prev = self.latest_hash

        payload_bytes = (
            json.dumps(payload_data, sort_keys=True).encode("utf-8") if payload_data else b""
        )
        payload_digest = hashlib.sha256(payload_bytes).hexdigest()

        entry_hash = _compute_entry_hash(
            decision_id=did,
            timestamp=ts,
            actor=actor,
            action=action,
            policy_rule=policy_rule,
            rationale=rationale,
            allowed=allowed,
            payload_digest=payload_digest,
            prev_hash=prev,
        )

        entry = DecisionAuditEntry(
            decision_id=did,
            timestamp=ts,
            actor=actor,
            action=action,
            policy_rule=policy_rule,
            rationale=rationale,
            allowed=allowed,
            payload_digest=payload_digest,
            prev_hash=prev,
            entry_hash=entry_hash,
        )
        self._entries.append(entry)
        return entry

    def verify_integrity(self) -> bool:
        """Verify the cryptographic hash chain across all entries."""
        prev = self.GENESIS_HASH
        for idx, entry in enumerate(self._entries):
            if entry.prev_hash != prev:
                msg = f"Hash chain broken at index {idx}: expected {prev}, got {entry.prev_hash}"
                raise ValueError(msg)
            expected_hash = _compute_entry_hash(
                decision_id=entry.decision_id,
                timestamp=entry.timestamp,
                actor=entry.actor,
                action=entry.action,
                policy_rule=entry.policy_rule,
                rationale=entry.rationale,
                allowed=entry.allowed,
                payload_digest=entry.payload_digest,
                prev_hash=entry.prev_hash,
            )
            if entry.entry_hash != expected_hash:
                raise ValueError(f"Entry hash mismatch at index {idx}: tampered record")
            prev = entry.entry_hash
        return True

    def export_audit_log(self) -> list[dict[str, Any]]:
        return [entry.to_document() for entry in self._entries]
