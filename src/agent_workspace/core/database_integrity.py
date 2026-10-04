"""SQLite integrity watch helper."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def database_integrity_check(database: str | Path) -> dict[str, Any]:
    database_path = Path(database).expanduser().resolve()
    if not database_path.is_file() or database_path.stat().st_size == 0:
        return {"ok": True, "quick_check": "ok", "foreign_key_violations": 0}
    connection = sqlite3.connect(
        f"{database_path.as_uri()}?mode=ro",
        timeout=5.0,
        uri=True,
    )
    try:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        return {
            "ok": quick_check == "ok" and not violations,
            "quick_check": quick_check,
            "foreign_key_violations": len(violations),
            "violations": [
                {
                    "table": str(row[0]),
                    "rowid": int(row[1]) if row[1] is not None else None,
                }
                for row in violations
            ],
        }
    except sqlite3.Error as exc:
        raise RuntimeError(f"database integrity check failed: {exc}") from exc
    finally:
        connection.close()


__all__ = ["database_integrity_check"]
