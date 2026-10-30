"""The agent's code-intelligence tools: problems in files, where a symbol is defined and used,
and a file's outline, answered by the language servers of the LspPool."""

from __future__ import annotations

import re
from functools import partial
from pathlib import Path
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import (
    ToolArgumentError,
    ToolError,
    json_result,
    validate_tool_arguments,
)
from agent_workspace.tools.lsp import LspClientError, LspDiagnostic
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

from .lsp_pool import Location, LspPool, NoServerError, Symbol

_MAX_PROBLEMS = 40
_MAX_REFERENCES = 150
_MAX_SYMBOLS = 300
_SEVERITY = {1: "error", 2: "warning", 3: "info", 4: "hint"}
_KIND = {
    2: "module",
    3: "namespace",
    5: "class",
    6: "method",
    7: "property",
    8: "field",
    9: "constructor",
    10: "enum",
    11: "interface",
    12: "function",
    13: "variable",
    14: "constant",
    22: "enum member",
    23: "struct",
    26: "type parameter",
}


def find_symbol(text: str, symbol: str, line: int | None) -> tuple[int, int] | None:
    """(line, column), 0-based, of the symbol as a whole word: on the given 1-based line or
    the lines next to it, else its first use in the file."""
    name = symbol.split(".")[-1].strip()
    if not name:
        return None
    pattern = re.compile(rf"(?<![\w$]){re.escape(name)}(?![\w$])")
    lines = text.splitlines()
    if line is not None:
        start = line - 1
        for index in (start, start - 1, start + 1, start - 2, start + 2):
            if 0 <= index < len(lines) and (match := pattern.search(lines[index])):
                return index, match.start()
    for index, line_text in enumerate(lines):
        if match := pattern.search(line_text):
            return index, match.start()
    return None


def problem_line(diagnostic: LspDiagnostic) -> str:
    severity = _SEVERITY.get(diagnostic.severity, "error")
    code = f" [{diagnostic.code}]" if diagnostic.code else ""
    message = " ".join(diagnostic.message.split())
    return (
        f"{diagnostic.range_start_line + 1}:{diagnostic.range_start_character + 1} "
        f"{severity}: {message}{code}"
    )


class _CodeTool:
    _spec: ToolSpec

    def __init__(self, workspace: Path, pool: LspPool) -> None:
        self.paths = WorkspacePaths(workspace)
        self.pool = pool

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def offered(self) -> bool:
        return self.pool.any_available()

    def _file(self, value: object) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise ToolArgumentError("path must be a file of the folder")
        try:
            path = self.paths.resolve(value)
        except WorkspacePathError as error:
            raise ToolArgumentError(str(error)) from None
        if not path.is_file():
            raise ToolError(f"file not found: {value}")
        return path

    def _shown(self, path: Path) -> str:
        try:
            return self.paths.relative(path)
        except (ValueError, WorkspacePathError):
            return str(path)  # outside the folder: a library's source

    def _code(self, location: Location) -> str:
        try:
            with location.path.open("r", encoding="utf-8", errors="replace") as handle:
                for index, text in enumerate(handle):
                    if index == location.line:
                        return text.strip()[:200]
        except OSError:
            pass
        return ""

    def _where(self, location: Location) -> dict[str, object]:
        return {
            "path": self._shown(location.path),
            "line": location.line + 1,
            "code": self._code(location),
        }

    async def _position(self, arguments: dict[str, Any]) -> tuple[Path, int, int]:
        path = self._file(arguments.get("path"))
        symbol = str(arguments.get("symbol", ""))
        line = arguments.get("line")
        text = path.read_text(encoding="utf-8", errors="replace")
        found = find_symbol(text, symbol, line if isinstance(line, int) else None)
        if found is None:
            where = f" near line {line}" if isinstance(line, int) else ""
            raise ToolError(f"'{symbol}' does not appear in {arguments.get('path')}{where}")
        return path, found[0], found[1]


def _no_server(error: NoServerError) -> str:
    name = error.server_name or "a language server"
    return (
        f"{error}. The user can install {name} in Settings → Code intelligence; meanwhile use "
        "search_files and read_file."
    )


class CodeDiagnosticsTool(_CodeTool):
    _spec = ToolSpec(
        name="code_diagnostics",
        description=(
            "Ask the language server (Pyright, TypeScript, rust-analyzer, gopls, clangd) for the "
            "errors and warnings in files: type errors, undefined names, wrong arguments, bad "
            "imports. Faster and more exact than running the compiler; use it after editing and "
            "before running tests."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "minItems": 1,
                    "maxItems": 20,
                }
            },
            "required": ["paths"],
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        files: list[dict[str, object]] = []
        for value in arguments["paths"]:
            path = self._file(value)
            entry: dict[str, object] = {"path": self._shown(path)}
            try:
                report = await self.pool.call(partial(self.pool.diagnostics, self.paths.root, path))
            except NoServerError as error:
                entry["unavailable"] = _no_server(error)
            except (LspClientError, OSError) as error:
                entry["unavailable"] = f"the language server failed: {error}"
            else:
                problems = sorted(
                    report.diagnostics, key=lambda item: (item.severity, item.range_start_line)
                )
                entry.update(
                    server=report.server,
                    errors=sum(1 for item in problems if item.severity == 1),
                    warnings=sum(1 for item in problems if item.severity == 2),
                    problems=[problem_line(item) for item in problems[:_MAX_PROBLEMS]],
                )
                if report.pending:
                    entry["note"] = "the server was still analysing; ask again for the final list"
            files.append(entry)
        return json_result({"files": files})


class FindDefinitionTool(_CodeTool):
    _spec = ToolSpec(
        name="find_definition",
        description=(
            "Where a symbol is defined, found by the language server rather than by text: give "
            "a file where the symbol is used, its name, and the line (optional, 1-based). Also "
            "returns its type or signature. Works across files and into libraries."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1, "maxLength": 1000},
                "symbol": {"type": "string", "minLength": 1, "maxLength": 300},
                "line": {"type": "integer", "minimum": 1},
            },
            "required": ["path", "symbol"],
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        path, line, column = await self._position(arguments)
        root = self.paths.root
        try:
            found = await self.pool.call(lambda: self.pool.definition(root, path, line, column))
            hover = await self.pool.call(lambda: self.pool.hover(root, path, line, column))
        except NoServerError as error:
            raise ToolError(_no_server(error)) from None
        except LspClientError as error:
            raise ToolError(f"the language server failed: {error}") from None
        return json_result(
            {
                "symbol": arguments["symbol"],
                "used_at": f"{self._shown(path)}:{line + 1}",
                "definitions": [self._where(item) for item in found[:20]],
                "type": hover[:800],
            }
        )


class FindReferencesTool(_CodeTool):
    _spec = ToolSpec(
        name="find_references",
        description=(
            "Every place a symbol is used, found by the language server (not text matches of "
            "the same name): give a file where it appears, its name and optionally the line. "
            "Use before renaming or changing a function's signature."
        ),
        input_schema=FindDefinitionTool._spec.input_schema,
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        path, line, column = await self._position(arguments)
        root = self.paths.root
        try:
            found = await self.pool.call(lambda: self.pool.references(root, path, line, column))
        except NoServerError as error:
            raise ToolError(_no_server(error)) from None
        except LspClientError as error:
            raise ToolError(f"the language server failed: {error}") from None
        found.sort(key=lambda item: (str(item.path), item.line))
        return json_result(
            {
                "symbol": arguments["symbol"],
                "count": len(found),
                "files": len({item.path for item in found}),
                "references": [self._where(item) for item in found[:_MAX_REFERENCES]],
            }
        )


class ListSymbolsTool(_CodeTool):
    _spec = ToolSpec(
        name="list_symbols",
        description=(
            "The outline of a file (classes, functions, methods with their lines), or with "
            "query the symbols of the whole project whose names match. Cheaper than reading a "
            "large file to find where something is."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1, "maxLength": 1000},
                "query": {"type": "string", "minLength": 1, "maxLength": 200},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        path = self._file(arguments.get("path"))
        root = self.paths.root
        query = arguments.get("query")
        try:
            if isinstance(query, str):
                found: list[Symbol] = await self.pool.call(
                    lambda: self.pool.workspace_symbols(root, path, query)
                )
            else:
                found = await self.pool.call(lambda: self.pool.document_symbols(root, path))
        except NoServerError as error:
            raise ToolError(_no_server(error)) from None
        except LspClientError as error:
            raise ToolError(f"the language server failed: {error}") from None
        rows = []
        for symbol in found[:_MAX_SYMBOLS]:
            kind = _KIND.get(symbol.kind, "symbol")
            where = (
                f"{self._shown(symbol.path)}:{symbol.line + 1}"
                if symbol.path is not None
                else f"{symbol.line + 1}-{symbol.end_line + 1}"
            )
            detail = f" {symbol.detail}" if symbol.detail else ""
            rows.append(f"{'  ' * symbol.depth}{kind} {symbol.name}{detail} ({where})")
        return json_result(
            {
                "path": self._shown(path),
                "query": query,
                "symbols": rows,
                "more": max(0, len(found) - _MAX_SYMBOLS),
            }
        )


def code_tools(workspace: Path, pool: LspPool) -> tuple[Any, ...]:
    return (
        CodeDiagnosticsTool(workspace, pool),
        FindDefinitionTool(workspace, pool),
        FindReferencesTool(workspace, pool),
        ListSymbolsTool(workspace, pool),
    )


__all__ = [
    "CodeDiagnosticsTool",
    "FindDefinitionTool",
    "FindReferencesTool",
    "ListSymbolsTool",
    "code_tools",
    "find_symbol",
    "problem_line",
]
