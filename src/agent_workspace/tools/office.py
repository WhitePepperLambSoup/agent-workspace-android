"""Agent tools that make and change Word, Excel and PowerPoint files in the workspace.

Every tool writes through the same checks as the other file tools: the path stays inside the
workspace, a replaced file must have the SHA-256 the agent observed (``expected_sha256``), and
the earlier content is kept as a rollback copy, so the change can be reviewed and undone.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.events import Event
from agent_workspace.core.models import Capability, FileCheckpoint, ToolSpec
from agent_workspace.storage.durable import durable_replace
from agent_workspace.storage.file_versions import FileVersions
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result, require_string
from agent_workspace.tools.filesystem import _check_preimage, _read_preimage, expected_sha256
from agent_workspace.tools.office_formats import (
    OfficeFormatError,
    Slide,
    markdown_docx,
    replace_in_docx,
    rows_xlsx,
    set_xlsx_cells,
    slides_pptx,
)
from agent_workspace.tools.paths import StrPath, WorkspacePaths, is_sensitive_workspace_path

_MAX_CONTENT = 262144
_MAX_ROWS = 50_000
_MAX_COLUMNS = 200
_MAX_CELLS = 500_000
_MAX_SLIDES = 200
_MAX_LINES = 30
_MAX_REPLACEMENTS = 100
_MAX_EDITED_FILE = 64 * 1024 * 1024
_CELL = {"type": ["string", "number", "boolean", "null"]}


class _OfficeFileTool:
    hard_cancellable = False
    _SPEC: ToolSpec
    _SUFFIX = ""
    # An edit changes a file that exists; creating may also replace one.
    _EDITS = False

    def __init__(
        self, workspace: WorkspacePaths | StrPath, versions: FileVersions | None = None
    ) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        # Where the content a call replaces is kept, so the window can compare the change.
        self.versions = versions

    def _keep_previous(self, previous: bytes | None, expected: str | None) -> dict[str, Any]:
        if previous is None or expected is None:
            return {}
        if self.versions is not None:
            self.versions.keep(previous)
        return {"previous_sha256": expected}

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def _make(
        self, arguments: dict[str, Any], current: bytes | None
    ) -> tuple[bytes, dict[str, Any]]:
        raise NotImplementedError

    def _destination(self, arguments: dict[str, Any]) -> tuple[Path, str | None, bytes | None]:
        path = self.paths.resolve(require_string(arguments, "path"))
        if path.suffix.casefold() != self._SUFFIX or is_sensitive_workspace_path(
            self.paths.relative(path)
        ):
            raise ToolArgumentError(
                f"The file must use an allowed workspace path ending in {self._SUFFIX}"
            )
        if not path.parent.is_dir():
            raise ToolError("The parent folder must already exist")
        expected = expected_sha256(arguments)
        if self._EDITS and expected is None:
            raise ToolArgumentError(
                "'expected_sha256' must be the SHA-256 of the file to change (read it first)"
            )
        limit = _MAX_EDITED_FILE if self._EDITS else None
        return path, expected, _read_preimage(path, expected, limit)

    def _write(self, path: Path, expected: str | None, data: bytes) -> dict[str, Any]:
        _check_preimage(path, expected, None)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            _check_preimage(path, expected, None)
            durable_replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return {
            "path": self.paths.relative(path),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes_written": len(data),
        }

    def _build(
        self, arguments: dict[str, Any], current: bytes | None
    ) -> tuple[bytes, dict[str, Any]]:
        try:
            return self._make(arguments, current)
        except OfficeFormatError as error:
            raise ToolError(str(error)) from None

    async def execute(self, arguments: dict[str, Any]) -> str:
        path, expected, current = await asyncio.to_thread(self._destination, arguments)
        data, details = await asyncio.to_thread(self._build, arguments, current)
        kept = await asyncio.to_thread(self._keep_previous, current, expected)
        result = await asyncio.to_thread(self._write, path, expected, data)
        return json_result({**result, **details, **kept})

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        path, expected, preimage = await asyncio.to_thread(self._destination, arguments)
        data, details = await asyncio.to_thread(self._build, arguments, preimage)
        digest = hashlib.sha256(data).hexdigest()
        await context.prepare_file_checkpoint(
            FileCheckpoint(
                attempt_id=context.attempt_id,
                session_id=context.session_id,
                workspace=str(self.paths.root),
                started_event_id=context.started_event_id,
                relative_path=self.paths.relative(path),
                preimage_sha256=expected,
                preimage=preimage,
                postimage_sha256=digest,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
        kept = await asyncio.to_thread(self._keep_previous, preimage, expected)
        result = await asyncio.to_thread(self._write, path, expected, data)
        await context.record_event(
            Event(
                session_id=context.session_id,
                type="file.version.recorded",
                data={
                    "attempt_id": context.attempt_id,
                    "path": result["path"],
                    "sha256": digest,
                    "bytes": len(data),
                    "previous_sha256": expected,
                },
                causation_id=context.started_event_id,
                correlation_id=context.correlation_id,
            )
        )
        return json_result({**result, **details, **kept})


def _file_spec(
    name: str, description: str, properties: dict[str, Any], required: list[str]
) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
                **properties,
                "expected_sha256": {"type": ["string", "null"]},
            },
            "required": ["path", *required, "expected_sha256"],
            "additionalProperties": False,
        },
        side_effect="write",
        capability=Capability.WORKSPACE_WRITE,
        durable_preimage_checkpoint=True,
    )


class CreateDocxTool(_OfficeFileTool):
    _SUFFIX = ".docx"
    _SPEC = _file_spec(
        "create_docx",
        "Create a Word document (.docx) in the workspace from Markdown: # headings, paragraphs, "
        "**bold**, *italic*, `code`, [links](https://...), - and 1. lists (nested by indent), "
        "| tables |, > quotes, ``` code blocks, --- rules, \\newpage. title is an optional "
        "title line. Use expected_sha256=null for a new file; replacing one needs its observed "
        "SHA-256. The parent folder must exist. To change some text of an existing document "
        "and keep its formatting, use edit_docx instead.",
        {
            "content": {"type": "string", "minLength": 1, "maxLength": _MAX_CONTENT},
            "title": {"type": "string", "maxLength": 1024},
        },
        ["content"],
    )

    def _make(
        self, arguments: dict[str, Any], current: bytes | None
    ) -> tuple[bytes, dict[str, Any]]:
        content = require_string(arguments, "content")
        title = arguments.get("title") or ""
        if not isinstance(title, str) or len(title) > 1024 or len(content) > _MAX_CONTENT:
            raise ToolArgumentError("title or content is too long")
        return markdown_docx(content, title), {}


class EditDocxTool(_OfficeFileTool):
    _SUFFIX = ".docx"
    _EDITS = True
    _SPEC = _file_spec(
        "edit_docx",
        "Change text in an existing Word document and keep its formatting, styles, images and "
        "layout: each replacement finds text within one paragraph (also in headers, footers "
        "and notes) and replaces every occurrence; the new text takes the formatting where "
        "the old text began. Read the document first (read_document) for its exact text and "
        "pass its SHA-256 as expected_sha256. The result lists how often each text matched; "
        "nothing is written when none matched.",
        {
            "replacements": {
                "type": "array",
                "minItems": 1,
                "maxItems": _MAX_REPLACEMENTS,
                "items": {
                    "type": "object",
                    "properties": {
                        "find": {"type": "string", "minLength": 1, "maxLength": 4000},
                        "replace": {"type": "string", "maxLength": 20000},
                    },
                    "required": ["find", "replace"],
                    "additionalProperties": False,
                },
            },
        },
        ["replacements"],
    )

    def _make(
        self, arguments: dict[str, Any], current: bytes | None
    ) -> tuple[bytes, dict[str, Any]]:
        if current is None:
            raise ToolError("The document does not exist")
        raw = arguments.get("replacements")
        if not isinstance(raw, list) or not 1 <= len(raw) <= _MAX_REPLACEMENTS:
            raise ToolArgumentError(f"'replacements' lists 1 to {_MAX_REPLACEMENTS} changes")
        pairs: list[tuple[str, str]] = []
        for item in raw:
            find = item.get("find") if isinstance(item, dict) else None
            replace = item.get("replace") if isinstance(item, dict) else None
            if not isinstance(find, str) or not find or not isinstance(replace, str):
                raise ToolArgumentError("each replacement has a non-empty find and a replace text")
            if "\n" in find:
                raise ToolArgumentError("find text cannot span paragraphs (no line breaks)")
            pairs.append((find, replace))
        data, counts = replace_in_docx(current, pairs)
        if not any(counts):
            raise ToolError(
                "None of the texts was found in the document; read it again for the exact wording"
            )
        return data, {
            "matches": [
                {"find": find, "count": count}
                for (find, _), count in zip(pairs, counts, strict=True)
            ]
        }


class CreateXlsxTool(_OfficeFileTool):
    _SUFFIX = ".xlsx"
    _SPEC = _file_spec(
        "create_xlsx",
        "Create an Excel workbook (.xlsx) in the workspace: sheets, each a name and rows (lists "
        "of cells: numbers stay numbers, true/false, text, and text starting with = is a "
        "formula such as =SUM(B2:B9)). The first row is a bold, frozen header unless header is "
        "false. Use expected_sha256=null for a new file; replacing one needs its observed "
        "SHA-256. The parent folder must exist. To fill in or change cells of an existing "
        "workbook and keep the rest, use update_xlsx instead.",
        {
            "sheets": {
                "type": "array",
                "minItems": 1,
                "maxItems": 50,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "maxLength": 31},
                        "rows": {
                            "type": "array",
                            "maxItems": _MAX_ROWS,
                            "items": {"type": "array", "maxItems": _MAX_COLUMNS, "items": _CELL},
                        },
                    },
                    "required": ["rows"],
                    "additionalProperties": False,
                },
            },
            "header": {"type": "boolean"},
        },
        ["sheets"],
    )

    def _make(
        self, arguments: dict[str, Any], current: bytes | None
    ) -> tuple[bytes, dict[str, Any]]:
        sheets = arguments.get("sheets")
        if not isinstance(sheets, list) or not 1 <= len(sheets) <= 50:
            raise ToolArgumentError("'sheets' must list 1 to 50 sheets")
        cells = 0
        for sheet in sheets:
            rows = sheet.get("rows") if isinstance(sheet, dict) else None
            if (
                not isinstance(rows, list)
                or len(rows) > _MAX_ROWS
                or not all(isinstance(row, list) and len(row) <= _MAX_COLUMNS for row in rows)
            ):
                raise ToolArgumentError(
                    f"each sheet needs rows: up to {_MAX_ROWS} lists of up to {_MAX_COLUMNS} cells"
                )
            for row in rows:
                for value in row:
                    _check_cell(value)
                cells += len(row)
        if cells > _MAX_CELLS:
            raise ToolArgumentError(f"at most {_MAX_CELLS} cells")
        header = arguments.get("header", True)
        if not isinstance(header, bool):
            raise ToolArgumentError("'header' must be true or false")
        return rows_xlsx(sheets, header), {}


def _check_cell(value: Any) -> None:
    if value is not None and not isinstance(value, str | int | float | bool):
        raise ToolArgumentError("cells are numbers, text, true/false or null")
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        raise ToolArgumentError("cells cannot hold NaN or infinity")
    if isinstance(value, str) and len(value) > 32767:
        raise ToolArgumentError("a cell holds at most 32767 characters")


class UpdateXlsxTool(_OfficeFileTool):
    _SUFFIX = ".xlsx"
    _EDITS = True
    _SPEC = _file_spec(
        "update_xlsx",
        "Set or clear cells in one sheet of an existing Excel workbook and keep everything else "
        "(other sheets, styles, column widths): cells maps references such as B3 to a number, "
        "true/false, text, a formula starting with = or null to clear the cell. sheet is the "
        "sheet's name (the first sheet when left out). Formulas are recalculated when the "
        "workbook opens. Read the workbook first (read_document) and pass its SHA-256 as "
        "expected_sha256.",
        {
            "sheet": {"type": "string", "minLength": 1, "maxLength": 31},
            "cells": {
                "type": "object",
                "minProperties": 1,
                "maxProperties": 10000,
                "patternProperties": {"^[A-Z]{1,3}[1-9][0-9]{0,6}$": _CELL},
                "additionalProperties": False,
            },
        },
        ["cells"],
    )

    def _make(
        self, arguments: dict[str, Any], current: bytes | None
    ) -> tuple[bytes, dict[str, Any]]:
        if current is None:
            raise ToolError("The workbook does not exist")
        cells = arguments.get("cells")
        if not isinstance(cells, dict) or not 1 <= len(cells) <= 10000:
            raise ToolArgumentError("'cells' maps 1 to 10000 cell references to values")
        for value in cells.values():
            _check_cell(value)
        sheet = arguments.get("sheet")
        if sheet is not None and not isinstance(sheet, str):
            raise ToolArgumentError("'sheet' is a sheet name")
        data = set_xlsx_cells(current, sheet, sorted(cells.items()))
        return data, {"cells_written": len(cells)}


class CreatePptxTool(_OfficeFileTool):
    _SUFFIX = ".pptx"
    _SPEC = _file_spec(
        "create_pptx",
        "Create a PowerPoint presentation (.pptx, 16:9) in the workspace from slides. Each "
        "slide has a kind: title (a large title and subtitle lines, for the first slide), "
        "section (a divider between parts) or content (a title and bullet points). Bullets "
        "are lines of text with an optional level 0-4 for nesting; **bold** works inside a "
        "line. Keep a content slide to about 6 bullets of one or two lines; split longer "
        "material over more slides. Use expected_sha256=null for a new file; replacing one "
        "needs its observed SHA-256.",
        {
            "slides": {
                "type": "array",
                "minItems": 1,
                "maxItems": _MAX_SLIDES,
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"enum": ["title", "section", "content"]},
                        "title": {"type": "string", "maxLength": 300},
                        "subtitle": {"type": "string", "maxLength": 600},
                        "bullets": {
                            "type": "array",
                            "maxItems": _MAX_LINES,
                            "items": {
                                "anyOf": [
                                    {"type": "string", "maxLength": 1000},
                                    {
                                        "type": "object",
                                        "properties": {
                                            "text": {"type": "string", "maxLength": 1000},
                                            "level": {
                                                "type": "integer",
                                                "minimum": 0,
                                                "maximum": 4,
                                            },
                                        },
                                        "required": ["text"],
                                        "additionalProperties": False,
                                    },
                                ]
                            },
                        },
                    },
                    "required": ["kind", "title"],
                    "additionalProperties": False,
                },
            },
        },
        ["slides"],
    )

    def _make(
        self, arguments: dict[str, Any], current: bytes | None
    ) -> tuple[bytes, dict[str, Any]]:
        raw = arguments.get("slides")
        if not isinstance(raw, list) or not 1 <= len(raw) <= _MAX_SLIDES:
            raise ToolArgumentError(f"'slides' lists 1 to {_MAX_SLIDES} slides")
        slides: list[Slide] = []
        for item in raw:
            if not isinstance(item, dict) or item.get("kind") not in {
                "title",
                "section",
                "content",
            }:
                raise ToolArgumentError("each slide has a kind: title, section or content")
            title = item.get("title")
            if not isinstance(title, str):
                raise ToolArgumentError("each slide has a title")
            lines: list[tuple[str, int]] = []
            subtitle = item.get("subtitle")
            if isinstance(subtitle, str) and subtitle.strip():
                lines.extend((line, 0) for line in subtitle.splitlines() if line.strip())
            for bullet in item.get("bullets") or []:
                if isinstance(bullet, str):
                    lines.append((bullet, 0))
                elif isinstance(bullet, dict) and isinstance(bullet.get("text"), str):
                    level = bullet.get("level", 0)
                    if type(level) is not int or not 0 <= level <= 4:
                        raise ToolArgumentError("a bullet's level is 0 to 4")
                    lines.append((bullet["text"], level))
                else:
                    raise ToolArgumentError("a bullet is text or {text, level}")
            if len(lines) > _MAX_LINES:
                raise ToolArgumentError(f"a slide holds at most {_MAX_LINES} lines")
            slides.append(Slide(item["kind"], title, tuple(lines)))
        return slides_pptx(slides), {"slides": len(slides)}
