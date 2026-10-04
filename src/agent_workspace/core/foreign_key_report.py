"""SQLite foreign key report.

Enumerates declared foreign key references and counts orphaned child rows
(existing values with no matching parent row) without modifying the database.
Composite foreign keys are grouped and evaluated as a single relationship.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_BUSY_TIMEOUT_SECONDS = 5.0


class ForeignKeyReportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ForeignKeyReference:
    table: str
    sequence: int
    parent_table: str
    columns: tuple[tuple[str, str], ...]
    on_update: str
    on_delete: str

    @property
    def key(self) -> str:
        return f"{self.table}.{self.sequence}"

    def to_document(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "sequence": self.sequence,
            "parent_table": self.parent_table,
            "columns": [list(column) for column in self.columns],
            "on_update": self.on_update,
            "on_delete": self.on_delete,
        }


@dataclass(frozen=True, slots=True)
class ForeignKeyReport:
    database: str
    foreign_keys_enabled: bool
    tables: tuple[str, ...]
    references: tuple[ForeignKeyReference, ...]
    orphan_counts: dict[str, int]

    @property
    def total_orphans(self) -> int:
        return sum(self.orphan_counts.values())

    def to_document(self) -> dict[str, Any]:
        return {
            "database": self.database,
            "foreign_keys_enabled": self.foreign_keys_enabled,
            "tables": list(self.tables),
            "references": [reference.to_document() for reference in self.references],
            "orphan_counts": dict(self.orphan_counts),
            "total_orphans": self.total_orphans,
        }


def _quote(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def _primary_key_columns(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    rows = connection.execute(f"PRAGMA table_info({_quote(table)})").fetchall()
    ordered = sorted(
        (row for row in rows if int(row[5]) > 0),
        key=lambda row: int(row[5]),
    )
    return tuple(str(row[1]) for row in ordered)


def _references_for(connection: sqlite3.Connection, table: str) -> tuple[ForeignKeyReference, ...]:
    rows = connection.execute(f"PRAGMA foreign_key_list({_quote(table)})").fetchall()
    grouped: dict[int, list[tuple[str, str | None, str, str, str, int]]] = {}
    for row in rows:
        sequence = int(row[0])
        raw_parent: Any = row[2]
        raw_to: Any = row[4]
        parent = str(raw_parent) if raw_parent is not None else ""
        to = str(raw_to) if raw_to is not None else None
        grouped.setdefault(sequence, []).append(
            (str(row[3]), to, parent, str(row[5]), str(row[6]), int(row[1]))
        )
    references: list[ForeignKeyReference] = []
    for sequence, entries in grouped.items():
        entries.sort(key=lambda entry: entry[5])
        parent = entries[0][2]
        if not parent:
            continue
        implicit = [entry[1] is None for entry in entries]
        if any(implicit):
            if not all(implicit):
                raise ForeignKeyReportError(
                    f"table {table!r} foreign key {sequence} mixes implicit and explicit parents"
                )
            primary_keys = _primary_key_columns(connection, parent)
            if len(primary_keys) != len(entries):
                raise ForeignKeyReportError(
                    f"table {table!r} foreign key {sequence} cannot resolve parent key"
                )
            columns = tuple(
                (child, primary_keys[index])
                for index, (child, _to, _parent, _on_update, _on_delete, _order) in enumerate(
                    entries
                )
            )
        else:
            columns = tuple(
                (child, str(to))
                for child, to, _parent, _on_update, _on_delete, _order in entries
                if to is not None
            )
        references.append(
            ForeignKeyReference(
                table=table,
                sequence=sequence,
                parent_table=parent,
                columns=columns,
                on_update=entries[0][3],
                on_delete=entries[0][4],
            )
        )
    return tuple(sorted(references, key=lambda reference: reference.key))


def _count_orphans(connection: sqlite3.Connection, reference: ForeignKeyReference) -> int:
    if not reference.columns:
        return 0
    child = _quote(reference.table)
    parent = _quote(reference.parent_table)
    conditions = " AND ".join(
        f"parent.{_quote(parent_column)} = child.{_quote(child_column)}"
        for child_column, parent_column in reference.columns
    )
    non_null = " AND ".join(
        f"child.{_quote(child_column)} IS NOT NULL"
        for child_column, _parent_column in reference.columns
    )
    query = (
        f"SELECT COUNT(*) FROM {child} AS child WHERE {non_null} "
        f"AND NOT EXISTS (SELECT 1 FROM {parent} AS parent WHERE {conditions})"
    )
    row = connection.execute(query).fetchone()
    return int(row[0]) if row else 0


def foreign_key_report(database: str | Path) -> ForeignKeyReport:
    path = Path(database).expanduser().resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise ForeignKeyReportError(f"sqlite database does not exist or is empty: {path}")
    connection = sqlite3.connect(
        f"{path.as_uri()}?mode=ro",
        timeout=_BUSY_TIMEOUT_SECONDS,
        uri=True,
    )
    try:
        enabled = bool(connection.execute("PRAGMA foreign_keys").fetchone()[0])
        table_rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
        tables = tuple(str(row[0]) for row in table_rows)
        references: list[ForeignKeyReference] = []
        for table in tables:
            references.extend(_references_for(connection, table))
        orphan_counts = {
            reference.key: _count_orphans(connection, reference) for reference in references
        }
    except (sqlite3.Error, TypeError, ValueError) as exc:
        raise ForeignKeyReportError(f"cannot inspect sqlite database: {path}") from exc
    finally:
        connection.close()
    return ForeignKeyReport(
        database=str(path),
        foreign_keys_enabled=enabled,
        tables=tables,
        references=tuple(references),
        orphan_counts=orphan_counts,
    )


__all__ = [
    "ForeignKeyReference",
    "ForeignKeyReport",
    "ForeignKeyReportError",
    "foreign_key_report",
]
