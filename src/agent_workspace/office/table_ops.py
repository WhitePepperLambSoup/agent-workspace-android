# ruff: noqa: RUF001 -- sheet and column names are Chinese.
"""Tables merged (one under another, or joined on key columns like VLOOKUP), compared (rows
only in one, cells that differ), and split into 工资条 (each row under its own header)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_workspace.office.ooxml import OfficeError
from agent_workspace.office.tables import Sheet, column_letter, display

DIFFERENT = "FFC7CE"
ONLY = "FFEB9C"


def _normal(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return round(float(value), 9)
    text = str(value).strip()
    try:
        return round(float(text.replace(",", "")), 9)
    except ValueError:
        return text


def _key(record: dict[str, Any], columns: list[str]) -> tuple[Any, ...]:
    return tuple(_normal(record.get(column)) for column in columns)


def _require(sheet: Sheet, columns: list[str], label: str) -> None:
    missing = [column for column in columns if column not in sheet.header]
    if missing:
        raise OfficeError(
            f"{label} has no column {', '.join(missing)}; its columns: {', '.join(sheet.header)}"
        )


@dataclass
class Result:
    spec: dict[str, Any]
    summary: dict[str, Any] = field(default_factory=dict)


def stack(tables: list[tuple[str, Sheet]], source_column: str = "来源") -> Result:
    """One table under another; columns matched by name, a column naming each row's file."""
    columns: list[str] = []
    for _label, sheet in tables:
        for name in sheet.header:
            if name and name not in columns:
                columns.append(name)
    rows: list[list[Any]] = [[*columns, source_column]]
    counts = {}
    for label, sheet in tables:
        records = sheet.records()
        counts[label] = len(records)
        for record in records:
            rows.append([record.get(name) for name in columns] + [label])
    return Result(
        {"sheets": [{"name": "合并", "rows": rows}]},
        {"rows": len(rows) - 1, "by_file": counts, "columns": columns},
    )


def join(
    base: tuple[str, Sheet],
    others: list[tuple[str, Sheet]],
    keys: list[str],
    columns: list[str] | None = None,
) -> Result:
    """The base table with columns of the others looked up by the key columns (like VLOOKUP);
    rows of the base that found no match are counted and highlighted."""
    label, sheet = base
    _require(sheet, keys, label)
    header = list(sheet.header)
    records = sheet.records()
    added: list[str] = []
    lookups: list[tuple[dict[tuple[Any, ...], dict[str, Any]], list[tuple[str, str]]]] = []
    unmatched: dict[str, int] = {}
    for other_label, other in others:
        _require(other, keys, other_label)
        wanted = [
            name
            for name in other.header
            if name and name not in keys and (not columns or name in columns)
        ]
        renamed = []
        for name in wanted:
            title = name if name not in header and name not in added else f"{name}（{other_label}）"
            renamed.append((name, title))
            added.append(title)
        index: dict[tuple[Any, ...], dict[str, Any]] = {}
        for record in other.records():
            index.setdefault(_key(record, keys), record)
        lookups.append((index, renamed))
        unmatched[other_label] = 0
    rows: list[list[Any]] = [header + added]
    highlight = []
    for row_number, record in enumerate(records, start=2):
        row = [record.get(name) for name in header]
        position = len(header)
        for (index, renamed), (other_label, _other) in zip(lookups, others, strict=True):
            match = index.get(_key(record, keys))
            if match is None:
                unmatched[other_label] += 1
                if renamed:
                    first = column_letter(position)
                    last = column_letter(position + len(renamed) - 1)
                    highlight.append(
                        {
                            "range": f"{first}{row_number}:{last}{row_number}",
                            "color": ONLY,
                        }
                    )
            row.extend(match.get(name) if match else None for name, _title in renamed)
            position += len(renamed)
        rows.append(row)
    return Result(
        {"sheets": [{"name": "合并", "rows": rows, "highlight": highlight}]},
        {"rows": len(records), "added_columns": added, "not_found": unmatched},
    )


def compare(
    first: tuple[str, Sheet],
    second: tuple[str, Sheet],
    keys: list[str],
    columns: list[str] | None = None,
) -> Result:
    """Rows only in one table, and the cells that differ in rows both have."""
    label_a, a = first
    label_b, b = second
    if keys:
        _require(a, keys, label_a)
        _require(b, keys, label_b)
    shared = [
        name
        for name in a.header
        if name and name in b.header and name not in keys and (not columns or name in columns)
    ]
    records_a, records_b = a.records(), b.records()
    if keys:
        index_a = {_key(record, keys): record for record in records_a}
        index_b = {_key(record, keys): record for record in records_b}
        order = list(dict.fromkeys([*index_a, *index_b]))
    else:
        index_a = {(number,): record for number, record in enumerate(records_a, start=1)}
        index_b = {(number,): record for number, record in enumerate(records_b, start=1)}
        order = list(dict.fromkeys([*index_a, *index_b]))
    key_titles = keys or ["行号"]
    differences: list[list[Any]] = [
        [
            *key_titles,
            *[f"{name}（{label_a}）" for name in shared],
            *[f"{name}（{label_b}）" for name in shared],
        ]
    ]
    highlight = []
    only_a: list[list[Any]] = [list(a.header)]
    only_b: list[list[Any]] = [list(b.header)]
    changed_cells = 0
    for key in order:
        record_a, record_b = index_a.get(key), index_b.get(key)
        if record_a is None and record_b is not None:
            only_b.append([record_b.get(name) for name in b.header])
            continue
        if record_b is None and record_a is not None:
            only_a.append([record_a.get(name) for name in a.header])
            continue
        assert record_a is not None and record_b is not None
        differing = [
            name for name in shared if _normal(record_a.get(name)) != _normal(record_b.get(name))
        ]
        if not differing:
            continue
        row_number = len(differences) + 1
        row = [*(record_a.get(name) for name in keys), *([key[0]] if not keys else [])]
        row.extend(record_a.get(name) for name in shared)
        row.extend(record_b.get(name) for name in shared)
        for name in differing:
            changed_cells += 1
            offset = shared.index(name)
            for column in (len(key_titles) + offset, len(key_titles) + len(shared) + offset):
                highlight.append(
                    {"range": f"{column_letter(column)}{row_number}", "color": DIFFERENT}
                )
        differences.append(row)
    summary = {
        f"rows_in_{label_a}": len(records_a),
        f"rows_in_{label_b}": len(records_b),
        "rows_with_differences": len(differences) - 1,
        "cells_different": changed_cells,
        f"only_in_{label_a}": len(only_a) - 1,
        f"only_in_{label_b}": len(only_b) - 1,
        "compared_columns": shared,
    }
    overview = [
        ["项目", "数量"],
        *[[name, value] for name, value in summary.items() if not isinstance(value, list)],
    ]
    name_a, name_b = f"仅在{label_a}"[:31], f"仅在{label_b}"[:31]
    if name_a == name_b:
        name_a, name_b = "仅在表1", "仅在表2"
    spec = {
        "sheets": [
            {"name": "汇总", "rows": overview},
            {"name": "不一致", "rows": differences, "highlight": highlight},
            {"name": name_a, "rows": only_a},
            {"name": name_b, "rows": only_b},
        ]
    }
    return Result(spec, summary)


def payslips(sheet: Sheet, header_rows: int = 1, blank_rows: int = 1) -> Result:
    """Each data row under its own copy of the header, a blank row between (for cutting)."""
    if len(sheet.rows) <= header_rows:
        raise OfficeError("the sheet has no rows under its header")
    header = sheet.rows[:header_rows]
    rows: list[list[Any]] = []
    bold_rows: list[int] = []
    plain_rows: list[int] = []
    count = 0
    for row in sheet.rows[header_rows:]:
        if all(value in (None, "") for value in row):
            continue
        for line in header:
            rows.append(list(line))
            bold_rows.append(len(rows))
        rows.append(list(row))
        count += 1
        for _ in range(blank_rows):
            rows.append([None] * len(row))
            plain_rows.append(len(rows))
    return Result(
        {
            "sheets": [
                {
                    "name": "工资条",
                    "rows": rows,
                    "header": False,
                    "bold_rows": bold_rows,
                    "plain_rows": plain_rows,
                    "freeze": "",
                    "filter": False,
                }
            ]
        },
        {"slips": count},
    )


def preview(rows: list[list[Any]], limit: int = 15) -> list[list[str]]:
    return [[display(value) for value in row] for row in rows[:limit]]


__all__ = ["Result", "compare", "join", "payslips", "preview", "stack"]
