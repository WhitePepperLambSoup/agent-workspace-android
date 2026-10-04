"""SQLite WAL checkpoint advisor.

Inspects the journal mode, page geometry, and on-disk WAL file size and
recommends whether the WAL should be passively checkpointed, fully
checkpointed, or truncated back to zero bytes. All inspection is read-only
and uses bounded ``sqlite3`` timeouts; the optional checkpoint helper is
explicitly requested by the caller.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

_WAL_FRAME_HEADER_BYTES = 24
_BUSY_TIMEOUT_SECONDS = 5.0


class WalCheckpointError(ValueError):
    pass


class WalRecommendation(StrEnum):
    OK = "ok"
    PASSIVE = "passive"
    FULL = "full"
    TRUNCATE = "truncate"


@dataclass(frozen=True, slots=True)
class WalCheckpointPolicy:
    passive_frames: int = 1_000
    full_frames: int = 10_000
    truncate_frames: int = 100_000

    def __post_init__(self) -> None:
        if not 0 < self.passive_frames <= self.full_frames <= self.truncate_frames:
            raise WalCheckpointError(
                "wal checkpoint thresholds must be positive and monotonically ordered"
            )

    def to_document(self) -> dict[str, Any]:
        return {
            "passive_frames": self.passive_frames,
            "full_frames": self.full_frames,
            "truncate_frames": self.truncate_frames,
        }


@dataclass(frozen=True, slots=True)
class WalCheckpointReport:
    database: str
    journal_mode: str
    page_size: int
    database_bytes: int
    wal_bytes: int
    wal_frames: int
    recommendation: WalRecommendation
    reason: str

    def to_document(self) -> dict[str, Any]:
        return {
            "database": self.database,
            "journal_mode": self.journal_mode,
            "page_size": self.page_size,
            "database_bytes": self.database_bytes,
            "wal_bytes": self.wal_bytes,
            "wal_frames": self.wal_frames,
            "recommendation": self.recommendation.value,
            "reason": self.reason,
        }


def _readonly_connection(path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(
            f"{path.as_uri()}?mode=ro",
            timeout=_BUSY_TIMEOUT_SECONDS,
            uri=True,
        )
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection
    except sqlite3.Error as exc:
        raise WalCheckpointError(f"cannot open sqlite database: {path}") from exc


def wal_checkpoint_advisor(
    database: str | Path,
    *,
    policy: WalCheckpointPolicy | None = None,
) -> WalCheckpointReport:
    """Inspect the database and WAL without modifying them."""
    active = policy or WalCheckpointPolicy()
    path = Path(database).expanduser().resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise WalCheckpointError(f"sqlite database does not exist or is empty: {path}")
    connection = _readonly_connection(path)
    try:
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).casefold()
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
    except (sqlite3.Error, TypeError, ValueError) as exc:
        raise WalCheckpointError(f"cannot inspect sqlite database: {path}") from exc
    finally:
        connection.close()
    if page_size <= 0 or page_count < 0:
        raise WalCheckpointError(f"sqlite page geometry is invalid: {path}")
    wal_path = Path(f"{path}-wal")
    wal_bytes = wal_path.stat().st_size if wal_path.is_file() else 0
    wal_frames = (
        wal_bytes // (page_size + _WAL_FRAME_HEADER_BYTES)
        if page_size + _WAL_FRAME_HEADER_BYTES > 0
        else 0
    )
    if journal_mode != "wal":
        return WalCheckpointReport(
            str(path),
            journal_mode,
            page_size,
            page_count * page_size,
            wal_bytes,
            wal_frames,
            WalRecommendation.OK,
            f"journal mode is {journal_mode}, not wal",
        )
    if wal_frames >= active.truncate_frames:
        return WalCheckpointReport(
            str(path),
            journal_mode,
            page_size,
            page_count * page_size,
            wal_bytes,
            wal_frames,
            WalRecommendation.TRUNCATE,
            f"wal contains {wal_frames} frames and should be truncated",
        )
    if wal_frames >= active.full_frames:
        return WalCheckpointReport(
            str(path),
            journal_mode,
            page_size,
            page_count * page_size,
            wal_bytes,
            wal_frames,
            WalRecommendation.FULL,
            f"wal contains {wal_frames} frames and should be fully checkpointed",
        )
    if wal_frames >= active.passive_frames:
        return WalCheckpointReport(
            str(path),
            journal_mode,
            page_size,
            page_count * page_size,
            wal_bytes,
            wal_frames,
            WalRecommendation.PASSIVE,
            f"wal contains {wal_frames} frames; a passive checkpoint is advised",
        )
    return WalCheckpointReport(
        str(path),
        journal_mode,
        page_size,
        page_count * page_size,
        wal_bytes,
        wal_frames,
        WalRecommendation.OK,
        f"wal size is healthy at {wal_frames} frames",
    )


def checkpoint_wal(
    database: str | Path,
    *,
    mode: str = "FULL",
    busy_timeout_seconds: float = _BUSY_TIMEOUT_SECONDS,
) -> dict[str, int]:
    """Run ``PRAGMA wal_checkpoint(mode)`` and return the busy/log/checkpointed row."""
    mode_token = mode.upper()
    if mode_token not in {"PASSIVE", "FULL", "RESTART", "TRUNCATE"}:
        raise WalCheckpointError(f"unsupported wal checkpoint mode: {mode}")
    path = Path(database).expanduser().resolve()
    if not path.is_file():
        raise WalCheckpointError(f"sqlite database does not exist: {path}")
    connection = sqlite3.connect(str(path), timeout=busy_timeout_seconds)
    try:
        row = connection.execute(f"PRAGMA wal_checkpoint({mode_token})").fetchone()
    except sqlite3.Error as exc:
        raise WalCheckpointError(f"wal checkpoint failed for {path}: {exc}") from exc
    finally:
        connection.close()
    return {"busy": int(row[0]), "log": int(row[1]), "checkpointed": int(row[2])}


__all__ = [
    "WalCheckpointError",
    "WalCheckpointPolicy",
    "WalCheckpointReport",
    "WalRecommendation",
    "checkpoint_wal",
    "wal_checkpoint_advisor",
]
