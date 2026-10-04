from __future__ import annotations

import asyncio
import fnmatch
import re
from collections import deque
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent_workspace.core.models import Capability, ToolSpec

from .base import (
    ToolArgumentError,
    ToolError,
    json_result,
    optional_bool,
    optional_int,
    require_string,
)
from .filesystem import _workspace_paths
from .paths import StrPath, WorkspacePathError, WorkspacePaths, is_sensitive_workspace_path
from .process_worker import run_in_process

if TYPE_CHECKING:
    from agent_workspace.application.ports import ToolExecutionContext

_MAX_FILES = 10_000
_MAX_ENTRIES = 100_000
_MAX_FILE_BYTES = 16 * 1024 * 1024
_MAX_TOTAL_BYTES = 64 * 1024 * 1024
_MAX_REGEX_PATTERN_CHARS = 1024
# Regex matching is bounded to the first 64 KiB of any single line so a
# pathological pattern cannot hang the worker on an enormous line.
_MAX_REGEX_LINE_CHARS = 64 * 1024


def _search_files(
    paths: WorkspacePaths,
    root: Path,
    query: str,
    file_glob: str,
    case_sensitive: bool,
    include_sensitive: bool,
    regex: bool,
    maximum: int,
    max_files: int,
    max_entries: int,
    max_file_bytes: int,
    max_total_bytes: int,
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    pending: deque[Path] = deque((root,))
    files_considered = 0
    entries_considered = 0
    files_searched = 0
    bytes_searched = 0
    binary_files = 0
    oversized_files = 0
    sensitive_files = 0
    truncated_by = {
        "max_results": False,
        "max_files": False,
        "max_entries": False,
        "max_total_bytes": False,
    }
    normalized_query = query if case_sensitive else query.casefold()
    pattern: re.Pattern[str] | None = None
    if regex:
        pattern = re.compile(query, flags=0 if case_sensitive else re.IGNORECASE)
    stop = False

    while pending and not stop:
        directory = pending.popleft()
        try:
            remaining_entries = max_entries - entries_considered
            children = list(islice(directory.iterdir(), remaining_entries + 1))
            entries_considered += len(children)
            if len(children) > remaining_entries:
                truncated_by["max_entries"] = True
                stop = True
                break
            children.sort(key=lambda item: (item.name.casefold(), item.name))
            for child in children:
                try:
                    checked = paths.resolve(child)
                except WorkspacePathError:
                    # Symlinks, junctions, and escaping paths are skipped per
                    # entry instead of aborting the whole tree walk.
                    continue
                relative = paths.relative(checked)
                if is_sensitive_workspace_path(relative) and not include_sensitive:
                    sensitive_files += 1
                    continue
                if checked.is_dir():
                    pending.append(checked)
                    continue
                if not fnmatch.fnmatch(relative, file_glob) and not fnmatch.fnmatch(
                    checked.name, file_glob
                ):
                    continue
                if files_considered >= max_files:
                    truncated_by["max_files"] = True
                    stop = True
                    break
                files_considered += 1

                try:
                    with checked.open("rb") as stream:
                        file_size = paths.assert_safe_file_descriptor(
                            stream.fileno(), checked
                        ).st_size
                        if file_size > max_file_bytes:
                            oversized_files += 1
                            continue
                        if file_size > max_total_bytes - bytes_searched:
                            truncated_by["max_total_bytes"] = True
                            stop = True
                            break

                        file_matches: list[dict[str, Any]] = []
                        file_hit_result_limit = False
                        is_binary = False
                        remaining = file_size
                        line_number = 0
                        while remaining:
                            raw_line = stream.readline(remaining)
                            if not raw_line:
                                break
                            remaining -= len(raw_line)
                            bytes_searched += len(raw_line)
                            if b"\x00" in raw_line:
                                is_binary = True
                                break
                            line_number += 1
                            if file_hit_result_limit:
                                continue
                            text = (
                                raw_line.removesuffix(b"\n")
                                .removesuffix(b"\r")
                                .decode("utf-8", errors="replace")
                            )
                            if pattern is not None:
                                match_text = (
                                    text
                                    if len(text) <= _MAX_REGEX_LINE_CHARS
                                    else text[:_MAX_REGEX_LINE_CHARS]
                                )
                                hit = pattern.search(match_text) is not None
                            else:
                                searchable = text if case_sensitive else text.casefold()
                                hit = normalized_query in searchable
                            if not hit:
                                continue
                            file_matches.append(
                                {"path": relative, "line": line_number, "text": text}
                            )
                            if len(matches) + len(file_matches) >= maximum:
                                file_hit_result_limit = True
                except OSError as exc:
                    raise ToolError(f"cannot read file while searching: {checked}") from exc

                if is_binary:
                    binary_files += 1
                    continue
                files_searched += 1
                matches.extend(file_matches)
                if file_hit_result_limit:
                    truncated_by["max_results"] = True
                    stop = True
                    break
        except OSError as exc:
            raise ToolError(f"cannot search directory: {directory}") from exc

    truncation_reasons = [name for name, reached in truncated_by.items() if reached]
    return {
        "matches": matches,
        "truncated": bool(truncation_reasons),
        "skipped": {
            "binary_files": binary_files,
            "oversized_files": oversized_files,
            "sensitive_files": sensitive_files,
        },
        "stats": {
            "entries_considered": entries_considered,
            "bytes_searched": bytes_searched,
            "files_considered": files_considered,
            "files_searched": files_searched,
            "truncated_by": truncation_reasons,
        },
    }


class SearchFilesTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="search_files",
        description=(
            "Search UTF-8 workspace files using literal text, or a bounded regular "
            "expression with the regex flag. Regex patterns are limited to 1024 "
            "characters and each line is matched on its first 64 KiB."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string", "default": "."},
                "regex": {
                    "type": "boolean",
                    "default": False,
                    "description": "Treat the query as a bounded regular expression.",
                },
                "case_sensitive": {"type": "boolean", "default": True},
                "include_sensitive": {
                    "type": "boolean",
                    "default": False,
                    "description": "Requires explicit approval and includes sensitive paths.",
                },
                "file_glob": {"type": "string", "default": "*"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10000},
                "max_files": {"type": "integer", "minimum": 1, "maximum": _MAX_FILES},
                "max_entries": {"type": "integer", "minimum": 1, "maximum": _MAX_ENTRIES},
                "max_file_bytes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_FILE_BYTES,
                },
                "max_total_bytes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_TOTAL_BYTES,
                },
            },
            "required": ["query"],
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

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        _context: ToolExecutionContext,
    ) -> str:
        return await run_in_process(self._execute_sync, arguments)

    def _execute_sync(self, arguments: dict[str, Any]) -> str:
        query = require_string(arguments, "query")
        raw_path = arguments.get("path", ".")
        file_glob = arguments.get("file_glob", "*")
        if not isinstance(raw_path, str) or not raw_path:
            raise ToolArgumentError("'path' must be a non-empty string")
        if not isinstance(file_glob, str) or not file_glob:
            raise ToolArgumentError("'file_glob' must be a non-empty string")
        use_regex = optional_bool(arguments, "regex", False)
        if use_regex:
            if len(query) > _MAX_REGEX_PATTERN_CHARS:
                raise ToolArgumentError("'query' exceeds the regex pattern length limit")
            try:
                re.compile(query)
            except re.error as exc:
                raise ToolArgumentError(
                    f"'query' is not a valid regular expression: {exc}"
                ) from exc
        case_sensitive = optional_bool(arguments, "case_sensitive", True)
        include_sensitive = optional_bool(arguments, "include_sensitive", False)
        maximum = optional_int(arguments, "max_results", 1000, minimum=1, maximum=10000)
        max_files = optional_int(arguments, "max_files", 1000, minimum=1, maximum=_MAX_FILES)
        max_entries = optional_int(
            arguments,
            "max_entries",
            20_000,
            minimum=1,
            maximum=_MAX_ENTRIES,
        )
        max_file_bytes = optional_int(
            arguments,
            "max_file_bytes",
            1024 * 1024,
            minimum=1,
            maximum=_MAX_FILE_BYTES,
        )
        max_total_bytes = optional_int(
            arguments,
            "max_total_bytes",
            16 * 1024 * 1024,
            minimum=1,
            maximum=_MAX_TOTAL_BYTES,
        )

        root = self.paths.resolve(raw_path)
        if not root.is_dir():
            raise ToolError(f"path is not a directory: {root}")
        result = _search_files(
            self.paths,
            root,
            query,
            file_glob,
            case_sensitive,
            include_sensitive,
            use_regex,
            maximum,
            max_files,
            max_entries,
            max_file_bytes,
            max_total_bytes,
        )
        return json_result(result)
