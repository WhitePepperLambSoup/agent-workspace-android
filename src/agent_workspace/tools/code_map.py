from __future__ import annotations

import asyncio
import fnmatch
import re
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent_workspace.core.models import Capability, ToolSpec

from .base import ToolArgumentError, ToolError, json_result, optional_int
from .filesystem import _workspace_paths
from .paths import StrPath, WorkspacePathError, WorkspacePaths, is_sensitive_workspace_path
from .process_worker import run_in_process

if TYPE_CHECKING:
    from agent_workspace.application.ports import ToolExecutionContext

_MAX_RESULTS = 10_000
_MAX_FILES = 5_000
_MAX_FILE_BYTES = 1_048_576
_DEFAULT_MAX_RESULTS = 2_000
_DEFAULT_MAX_FILES = 2_000
_DEFAULT_MAX_FILE_BYTES = 262_144
_MAX_SIGNATURE_CHARS = 120
_MAX_SYMBOL_CACHE_ENTRIES = 4096

_symbol_cache: dict[str, tuple[int, int, list[dict[str, Any]]]] = {}

_SKIPPED_DIRECTORIES = frozenset({".git", ".venv", "node_modules", "__pycache__", "dist", "build"})

_JS_EXTENSIONS = frozenset({".js", ".jsx", ".ts", ".tsx"})
_JAVA_EXTENSIONS = frozenset({".java", ".kt", ".cs"})
_SUPPORTED_EXTENSIONS = frozenset({".py", ".go", ".rs"}) | _JS_EXTENSIONS | _JAVA_EXTENSIONS

_PYTHON_CLASS = re.compile(r"^class\s+([A-Za-z_]\w*)\b")
_PYTHON_DEF = re.compile(r"^(?:async\s+)?def\s+([A-Za-z_]\w*)\b")
_PYTHON_CONSTANT = re.compile(r"^([A-Z][A-Z0-9_]*)\s*(?::[^=\n]*)?(?<!:)=(?!=)")

_JS_FUNCTION = re.compile(r"^function\s+([A-Za-z_$][\w$]*)\b")
_JS_CLASS = re.compile(r"^class\s+([A-Za-z_$][\w$]*)\b")
_JS_CONST = re.compile(r"^const\s+([A-Za-z_$][\w$]*)\s*=")
_JS_EXPORT_DEFAULT_FUNCTION = re.compile(r"^export\s+default\s+function\s+([A-Za-z_$][\w$]*)\b")
_JS_EXPORT_DEFAULT_CLASS = re.compile(r"^export\s+default\s+class\s+([A-Za-z_$][\w$]*)\b")
_JS_EXPORT_FUNCTION = re.compile(r"^export\s+function\s+([A-Za-z_$][\w$]*)\b")
_JS_EXPORT_CLASS = re.compile(r"^export\s+class\s+([A-Za-z_$][\w$]*)\b")
_JS_EXPORT_VAR = re.compile(r"^export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=")

_GO_FUNC = re.compile(r"^func\s+(?:(\([^)]*\))\s+)?([A-Za-z_]\w*)\b")
_GO_TYPE = re.compile(r"^type\s+([A-Za-z_]\w*)\b")
_GO_VAR = re.compile(r"^var\s+([A-Za-z_]\w*)\b")
_GO_CONST = re.compile(r"^const\s+([A-Za-z_]\w*)\b")

_RS_DECL = re.compile(r"^(?:pub\s+)?(fn|struct|enum|trait|impl)\s+([A-Za-z_]\w*)\b")

_JAVA_DECL = re.compile(
    r"^(?:public\s+|private\s+)?(class|interface|enum|record)\s+([A-Za-z_]\w*)\b"
)


def _truncate(text: str) -> str:
    if len(text) <= _MAX_SIGNATURE_CHARS:
        return text
    return text[:_MAX_SIGNATURE_CHARS]


def _python_signature(line: str) -> str:
    """Signature of a top-level Python declaration: up to the trailing colon."""
    text = line.rstrip()
    if text.endswith(":"):
        text = text[:-1].rstrip()
    text = re.sub(r"\(\s*self\s*(?:,\s*)?", "(", text)
    return _truncate(text)


def _symbol(line_number: int, kind: str, name: str, signature: str) -> dict[str, Any]:
    return {"line": line_number, "kind": kind, "name": name, "signature": signature}


def _scan_symbols(text: str, extension: str) -> list[dict[str, Any]]:
    """Extract top-level symbol entries for one decoded source file."""
    symbols: list[dict[str, Any]] = []
    if extension == ".py":
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line or line[0].isspace() or line.startswith(("#", "@")):
                continue
            match = _PYTHON_CLASS.match(line)
            if match:
                symbols.append(
                    _symbol(line_number, "class", match.group(1), _python_signature(line))
                )
                continue
            match = _PYTHON_DEF.match(line)
            if match:
                symbols.append(
                    _symbol(line_number, "function", match.group(1), _python_signature(line))
                )
                continue
            match = _PYTHON_CONSTANT.match(line)
            if match:
                symbols.append(
                    _symbol(line_number, "constant", match.group(1), _truncate(line.strip()))
                )
    elif extension in _JS_EXTENSIONS:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line or line[0].isspace():
                continue
            match = (
                _JS_EXPORT_DEFAULT_FUNCTION.match(line)
                or _JS_EXPORT_FUNCTION.match(line)
                or _JS_FUNCTION.match(line)
            )
            if match:
                symbols.append(
                    _symbol(line_number, "function", match.group(1), _truncate(line.strip()))
                )
                continue
            match = (
                _JS_EXPORT_DEFAULT_CLASS.match(line)
                or _JS_EXPORT_CLASS.match(line)
                or _JS_CLASS.match(line)
            )
            if match:
                symbols.append(
                    _symbol(line_number, "class", match.group(1), _truncate(line.strip()))
                )
                continue
            match = _JS_EXPORT_VAR.match(line) or _JS_CONST.match(line)
            if match:
                symbols.append(
                    _symbol(line_number, "constant", match.group(1), _truncate(line.strip()))
                )
    elif extension == ".go":
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line or line[0].isspace():
                continue
            match = _GO_FUNC.match(line)
            if match:
                symbols.append(
                    _symbol(line_number, "function", match.group(2), _truncate(line.strip()))
                )
                continue
            match = _GO_TYPE.match(line)
            if match:
                symbols.append(
                    _symbol(line_number, "type", match.group(1), _truncate(line.strip()))
                )
                continue
            match = _GO_VAR.match(line)
            if match:
                symbols.append(_symbol(line_number, "var", match.group(1), _truncate(line.strip())))
                continue
            match = _GO_CONST.match(line)
            if match:
                symbols.append(
                    _symbol(line_number, "const", match.group(1), _truncate(line.strip()))
                )
    elif extension == ".rs":
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line or line[0].isspace():
                continue
            match = _RS_DECL.match(line)
            if match:
                keyword = match.group(1)
                kind = "function" if keyword == "fn" else keyword
                symbols.append(_symbol(line_number, kind, match.group(2), _truncate(line.strip())))
    elif extension in _JAVA_EXTENSIONS:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line or line[0].isspace():
                continue
            match = _JAVA_DECL.match(line)
            if match:
                symbols.append(
                    _symbol(
                        line_number,
                        match.group(1),
                        match.group(2),
                        _truncate(line.strip()),
                    )
                )
    return symbols


def _matches_glob(relative: str, basename: str, file_glob: str) -> bool:
    if "/" in file_glob:
        return fnmatch.fnmatchcase(relative, file_glob)
    return fnmatch.fnmatchcase(basename, file_glob)


def _collect_files(
    paths: WorkspacePaths,
    root: Path,
    file_glob: str,
    max_files: int,
) -> tuple[list[tuple[str, Path]], int, bool]:
    """Collect candidate files sorted by relative path; stop past max_files."""
    if root.is_file():
        relative = paths.relative(root)
        if is_sensitive_workspace_path(relative) or not _matches_glob(
            relative, root.name, file_glob
        ):
            return [], 0, False
        return [(relative, root)], 1, False

    files: list[tuple[str, Path]] = []
    pending: deque[Path] = deque((root,))
    files_considered = 0
    truncated = False
    while pending:
        directory = pending.popleft()
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise ToolError(f"cannot list directory: {directory}") from exc
        for child in children:
            try:
                checked = paths.resolve(child)
            except WorkspacePathError:
                # Symlinks, junctions, and escaping paths are skipped per
                # entry instead of aborting the whole tree walk.
                continue
            relative = paths.relative(checked)
            if is_sensitive_workspace_path(relative):
                continue
            if checked.is_dir():
                if checked.name in _SKIPPED_DIRECTORIES:
                    continue
                pending.append(checked)
                continue
            if not _matches_glob(relative, checked.name, file_glob):
                continue
            if files_considered >= max_files:
                truncated = True
                pending.clear()
                break
            files_considered += 1
            files.append((relative, checked))
    files.sort(key=lambda item: item[0])
    return files, files_considered, truncated


def clear_code_map_cache() -> None:
    """Drop all cached per-file symbol extraction results."""
    _symbol_cache.clear()


def _index_files(
    files: list[tuple[str, Path]],
    max_file_bytes: int,
    max_results: int,
    truncated: bool,
) -> tuple[list[dict[str, Any]], int, bool]:
    entries: list[dict[str, Any]] = []
    files_indexed = 0
    for relative, checked in files:
        if len(entries) >= max_results:
            truncated = True
            break
        if checked.suffix not in _SUPPORTED_EXTENSIONS:
            continue
        try:
            metadata = checked.stat()
        except OSError as exc:
            raise ToolError(f"cannot stat file while mapping symbols: {checked}") from exc
        signature = (metadata.st_mtime_ns, metadata.st_size)
        cache_key = str(checked)
        cached = _symbol_cache.get(cache_key)
        if cached is not None and cached[:2] == signature:
            symbols = cached[2]
        else:
            if metadata.st_size > max_file_bytes:
                truncated = True
                continue
            try:
                with checked.open("rb") as stream:
                    file_size = WorkspacePaths.assert_safe_file_descriptor(
                        stream.fileno(), checked
                    ).st_size
                    if file_size > max_file_bytes:
                        truncated = True
                        continue
                    data = stream.read()
            except OSError as exc:
                raise ToolError(f"cannot read file while mapping symbols: {checked}") from exc
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                continue
            symbols = _scan_symbols(text, checked.suffix)
            if len(_symbol_cache) >= _MAX_SYMBOL_CACHE_ENTRIES:
                _symbol_cache.pop(next(iter(_symbol_cache)))
            _symbol_cache[cache_key] = (signature[0], signature[1], symbols)
        files_indexed += 1
        remaining = max_results - len(entries)
        for symbol in symbols:
            if remaining <= 0:
                truncated = True
                break
            entries.append({"path": relative, **symbol})
            remaining -= 1
    return entries, files_indexed, truncated


class CodeMapTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="code_map",
        description=(
            "Build a bounded symbol outline (top-level definitions) of workspace source "
            "files for orientation; use read_file for details. If truncated is true, "
            "continue with narrower paths or file_glob values before claiming coverage."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "."},
                "file_glob": {"type": "string", "default": "*"},
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_RESULTS,
                    "default": _DEFAULT_MAX_RESULTS,
                },
                "max_files": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_FILES,
                    "default": _DEFAULT_MAX_FILES,
                },
                "max_file_bytes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_FILE_BYTES,
                    "default": _DEFAULT_MAX_FILE_BYTES,
                },
            },
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
        raw_path = arguments.get("path", ".")
        file_glob = arguments.get("file_glob", "*")
        if not isinstance(raw_path, str) or not raw_path:
            raise ToolArgumentError("'path' must be a non-empty string")
        if not isinstance(file_glob, str) or not file_glob:
            raise ToolArgumentError("'file_glob' must be a non-empty string")
        maximum = optional_int(
            arguments, "max_results", _DEFAULT_MAX_RESULTS, minimum=1, maximum=_MAX_RESULTS
        )
        max_files = optional_int(
            arguments, "max_files", _DEFAULT_MAX_FILES, minimum=1, maximum=_MAX_FILES
        )
        max_file_bytes = optional_int(
            arguments,
            "max_file_bytes",
            _DEFAULT_MAX_FILE_BYTES,
            minimum=1,
            maximum=_MAX_FILE_BYTES,
        )

        root = self.paths.resolve(raw_path)
        if not root.is_file() and not root.is_dir():
            raise ToolError(f"path is not a file or directory: {root}")
        files, files_considered, truncated = _collect_files(self.paths, root, file_glob, max_files)
        entries, files_indexed, truncated = _index_files(files, max_file_bytes, maximum, truncated)
        document = {
            "entries": entries,
            "files_considered": files_considered,
            "files_indexed": files_indexed,
            "truncated": truncated,
        }
        if truncated:
            document["continuation_hint"] = (
                "Code map truncated; continue by partitioning the folder or file_glob "
                "and review every partition."
            )
        return json_result(document)
