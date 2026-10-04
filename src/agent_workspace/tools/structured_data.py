from __future__ import annotations

import asyncio
import csv
import json
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec

from .base import ToolArgumentError, ToolError, json_result, optional_int, require_string
from .filesystem import _workspace_paths
from .paths import StrPath, WorkspacePaths

_MAX_BYTES = 8 * 1024 * 1024
_MAX_ROWS = 5000
_MAX_COLUMNS = 64


class QueryTableTool:
    """Bounded, read-only CSV/JSON tabular data extraction."""

    _SPEC = ToolSpec(
        name="query_table",
        description=(
            "Read a bounded subset of a workspace CSV or JSON-array table. CSV files are "
            "parsed as UTF-8 with a header row; JSON files must contain an array of objects."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "limit": {"type": "integer", "minimum": 1, "maximum": _MAX_ROWS},
                "columns": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "maxItems": _MAX_COLUMNS,
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = _workspace_paths(workspace)

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await asyncio.to_thread(self._execute_sync, arguments)

    def _execute_sync(self, arguments: dict[str, Any]) -> str:
        raw_path = require_string(arguments, "path")
        limit = optional_int(arguments, "limit", 100, minimum=1, maximum=_MAX_ROWS)
        raw_columns = arguments.get("columns")
        columns: list[str] | None = None
        if raw_columns is not None:
            if not isinstance(raw_columns, list) or not all(
                isinstance(column, str) and column for column in raw_columns
            ):
                raise ToolArgumentError("'columns' must be an array of non-empty strings")
            columns = list(raw_columns)
            if len(set(columns)) != len(columns):
                raise ToolArgumentError("'columns' contains duplicates")
        path = self.paths.resolve(raw_path)
        if not path.is_file():
            raise ToolError(f"table path is not a file: {raw_path}")
        if path.stat().st_size > _MAX_BYTES:
            raise ToolError("table file exceeds the 8 MiB limit")
        if path.suffix.casefold() == ".csv":
            rows = _read_csv(path, limit, columns)
        elif path.suffix.casefold() == ".json":
            rows = _read_json(path, limit, columns)
        else:
            raise ToolError("query_table supports .csv and .json files only")
        return json_result({"path": self.paths.relative(path), "rows": rows})


def _read_csv(path: Any, limit: int, columns: list[str] | None) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None:
                raise ToolError("CSV file has no header row")
            selected = columns if columns is not None else list(reader.fieldnames)
            unknown = [column for column in selected if column not in reader.fieldnames]
            if unknown:
                raise ToolError(f"CSV columns not found: {', '.join(unknown)}")
            rows: list[dict[str, str]] = []
            for row in reader:
                if len(rows) >= limit:
                    break
                rows.append({column: row.get(column, "") for column in selected})
            return rows
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ToolError(f"cannot read CSV table: {exc}") from exc


def _read_json(path: Any, limit: int, columns: list[str] | None) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ToolError(f"cannot read JSON table: {exc}") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ToolError("JSON table must be an array of objects")
    rows: list[dict[str, Any]] = []
    for item in value:
        if len(rows) >= limit:
            break
        rows.append(
            dict(item) if columns is None else {column: item.get(column) for column in columns}
        )
    return rows


__all__ = ["QueryTableTool"]
