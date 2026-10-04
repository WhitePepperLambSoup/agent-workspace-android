"""Read-only session search index statistics."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def search_index_stats(database: str | Path) -> dict[str, Any]:
    database_path = Path(database)
    if not database_path.is_file():
        raise FileNotFoundError(f"database does not exist: {database_path}")
    connection = sqlite3.connect(
        database_path.as_uri(),
        uri=True,
        timeout=5.0,
    )
    try:
        rows = connection.execute(
            "SELECT COUNT(*) FROM sqlite_schema WHERE type = 'table' AND name = 'session_search'"
        ).fetchone()
        if rows is None or rows[0] != 1:
            return {"available": False, "documents": 0, "tokens": 0}
        documents = connection.execute("SELECT COUNT(*) FROM search_documents").fetchone()[0]
        token_rows = connection.execute("SELECT SUM(sz) FROM session_search_docsize").fetchone()[0]
        return {
            "available": True,
            "documents": int(documents),
            "tokens": int(token_rows or 0),
        }
    except sqlite3.Error as exc:
        raise RuntimeError(f"cannot inspect search index: {exc}") from exc
    finally:
        connection.close()


__all__ = ["search_index_stats"]
