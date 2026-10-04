"""Task interruption, execution checkpointing, and resume manager."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class TaskCheckpoint:
    session_id: str
    checkpoint_id: str
    step_id: str
    completed_step_ids: tuple[str, ...]
    context_variables: dict[str, Any]
    artifact_ids: tuple[str, ...]
    timestamp: float
    status: str = "suspended"

    def to_document(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "checkpoint_id": self.checkpoint_id,
            "step_id": self.step_id,
            "completed_step_ids": list(self.completed_step_ids),
            "context_variables": self.context_variables,
            "artifact_ids": list(self.artifact_ids),
            "timestamp": self.timestamp,
            "status": self.status,
        }


class TaskCheckpointManager:
    """Manages execution state checkpoints for graceful task pause and resume."""

    def __init__(self) -> None:
        self._checkpoints: dict[str, list[TaskCheckpoint]] = {}

    def create_checkpoint(
        self,
        *,
        session_id: str,
        step_id: str,
        completed_step_ids: tuple[str, ...],
        context_variables: dict[str, Any] | None = None,
        artifact_ids: tuple[str, ...] = (),
        checkpoint_id: str | None = None,
        timestamp: float | None = None,
    ) -> TaskCheckpoint:
        """Capture a point-in-time execution checkpoint."""
        cid = checkpoint_id or str(uuid4())
        ts = timestamp if timestamp is not None else time.time()

        checkpoint = TaskCheckpoint(
            session_id=session_id,
            checkpoint_id=cid,
            step_id=step_id,
            completed_step_ids=completed_step_ids,
            context_variables=dict(context_variables or {}),
            artifact_ids=artifact_ids,
            timestamp=ts,
            status="suspended",
        )

        if session_id not in self._checkpoints:
            self._checkpoints[session_id] = []
        self._checkpoints[session_id].append(checkpoint)
        return checkpoint

    def get_latest_checkpoint(self, session_id: str) -> TaskCheckpoint | None:
        """Get the latest checkpoint for a session."""
        session_list = self._checkpoints.get(session_id)
        if not session_list:
            return None
        return session_list[-1]

    def list_checkpoints(self, session_id: str) -> list[TaskCheckpoint]:
        """List all checkpoints for a session ordered by timestamp."""
        return list(self._checkpoints.get(session_id, []))

    def resume_checkpoint(self, checkpoint_id: str) -> TaskCheckpoint:
        """Mark a checkpoint as resumed."""
        for _session_id, c_list in self._checkpoints.items():
            for idx, cp in enumerate(c_list):
                if cp.checkpoint_id == checkpoint_id:
                    resumed = TaskCheckpoint(
                        session_id=cp.session_id,
                        checkpoint_id=cp.checkpoint_id,
                        step_id=cp.step_id,
                        completed_step_ids=cp.completed_step_ids,
                        context_variables=cp.context_variables,
                        artifact_ids=cp.artifact_ids,
                        timestamp=time.time(),
                        status="resumed",
                    )
                    c_list[idx] = resumed
                    return resumed
        raise KeyError(f"Checkpoint '{checkpoint_id}' not found")
