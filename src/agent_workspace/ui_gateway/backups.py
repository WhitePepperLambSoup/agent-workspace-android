"""The desktop's daily database backup.

The core backs up the database when a runtime closes. On the desktop that happened while the
window closed, when the sidecar has two seconds before it is stopped: the copy rarely finished
and the pruning of older copies never did, so copies piled up. The desktop turns those off and
makes one backup a day in the background instead, pruning older copies by their manifests.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent_workspace.storage.recovery import create_verified_backup, latest_backup_time
from agent_workspace.tools.process_worker import run_in_process

BACKUP_INTERVAL = timedelta(days=1)
KEEP_BACKUPS = 10


def backup_directory(database: Path) -> Path:
    return database.parent / "backups"


def backup_due(database: Path, *, now: datetime | None = None) -> bool:
    if not database.is_file():
        return False
    latest = latest_backup_time(database, backup_directory(database))
    return latest is None or (now or datetime.now(UTC)) - latest >= BACKUP_INTERVAL


def _create_daily_backup(database: str, directory: str) -> str:
    return str(create_verified_backup(database, directory, keep=KEEP_BACKUPS, quick_prune=True))


def run_daily_backup(database: Path) -> Path:
    """Back up the database in a worker process, so checking the copy holds up nothing here."""
    return Path(
        asyncio.run(
            run_in_process(_create_daily_backup, str(database), str(backup_directory(database)))
        )
    )
