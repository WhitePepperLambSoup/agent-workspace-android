from __future__ import annotations

import asyncio
import hashlib
import os
import re
import stat
import tempfile
from collections import deque
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from uuid import uuid4

from agent_workspace.core.events import Event
from agent_workspace.core.models import Capability, FileCheckpoint, ToolSpec
from agent_workspace.storage.durable import durable_replace, fsync_directory

if TYPE_CHECKING:
    from agent_workspace.application.ports import ToolExecutionContext

from .base import (
    ConcurrentModificationError,
    ToolArgumentError,
    ToolError,
    json_result,
    optional_bool,
    optional_int,
    require_string,
)
from .paths import StrPath, UnsafePathError, WorkspacePathError, WorkspacePaths
from .process_worker import run_in_process

_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")
_IO_CHUNK_BYTES = 64 * 1024
_MAX_EDIT_BYTES = 16 * 1024 * 1024
_MAX_READ_SCAN_BYTES = 64 * 1024 * 1024
_MAX_LIST_ENTRIES = 100_000


def _workspace_paths(value: WorkspacePaths | StrPath) -> WorkspacePaths:
    return value if isinstance(value, WorkspacePaths) else WorkspacePaths(value)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def expected_sha256(arguments: dict[str, Any]) -> str | None:
    if "expected_sha256" not in arguments:
        raise ToolArgumentError("'expected_sha256' is required (use null for a new file)")
    value = arguments["expected_sha256"]
    if value is not None and (not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value)):
        raise ToolArgumentError("'expected_sha256' must be a SHA-256 hex digest or null")
    return value.lower() if isinstance(value, str) else None


def _scan_file(
    path: Path,
    *,
    max_scan_bytes: int | None,
    retain_limit: int | None = None,
    retain: bool = False,
) -> tuple[str | None, bytes | None]:
    try:
        if path.is_dir():
            raise ToolError(f"path is a directory: {path}")
        digest = hashlib.sha256()
        retained = bytearray() if retain_limit is not None or retain else None
        with _open_identity_checked(path, "rb") as stream:
            size = WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), path).st_size
            if max_scan_bytes is not None and size > max_scan_bytes:
                raise ToolError(f"file exceeds {max_scan_bytes}-byte scan limit: {path}")
            while chunk := stream.read(_IO_CHUNK_BYTES):
                digest.update(chunk)
                if retained is not None:
                    if retain_limit is not None and len(retained) + len(chunk) > retain_limit:
                        raise ToolError(f"file exceeds {retain_limit}-byte edit limit: {path}")
                    retained.extend(chunk)
        return digest.hexdigest(), bytes(retained) if retained is not None else None
    except FileNotFoundError:
        return None, None
    except OSError as exc:
        raise ToolError(f"cannot read file: {path}") from exc


def _open_identity_checked(path: Path, mode: str) -> Any:
    before = path.lstat()
    stream = path.open(mode)
    after = WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), path)
    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
        stream.close()
        raise UnsafePathError(f"path changed during open: {path}")
    return stream


def _check_expected_digest(actual: str | None, expected: str | None) -> None:
    if actual == expected:
        return
    # Say how to recover: small local models otherwise retry with another invented digest.
    if actual is None:
        hint = "the file does not exist; use expected_sha256=null to create it"
    elif expected is None:
        hint = "the file already exists; read it and use its sha256 to replace it"
    else:
        hint = "read the file again and use its current sha256"
    raise ConcurrentModificationError(
        f"file changed: expected {expected or '<missing>'}, found {actual or '<missing>'}; {hint}"
    )


def _check_preimage(
    path: Path, expected: str | None, maximum: int | None = _MAX_EDIT_BYTES
) -> str | None:
    actual, _ = _scan_file(path, max_scan_bytes=maximum)
    _check_expected_digest(actual, expected)
    return actual


def _file_executable_state(path: Path) -> bool | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        actual = None
    except OSError as exc:
        raise ToolError(f"cannot inspect file mode: {path}") from exc
    else:
        if not stat.S_ISREG(metadata.st_mode):
            raise ToolError(f"path is not a regular file: {path}")
        return bool(metadata.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
    return actual


def _check_expected_executable(path: Path, expected: bool) -> None:
    actual = _file_executable_state(path)
    if actual is not expected:
        raise ConcurrentModificationError(
            "file mode changed: expected "
            f"{'executable' if expected else 'non-executable'}, found "
            f"{'missing' if actual is None else 'executable' if actual else 'non-executable'}"
        )


def _read_preimage(path: Path, expected: str | None, maximum: int | None) -> bytes | None:
    actual, content = _scan_file(path, max_scan_bytes=maximum, retain_limit=maximum, retain=True)
    _check_expected_digest(actual, expected)
    return content


def _encode_edit_text(value: str, name: str) -> bytes:
    if len(value) > _MAX_EDIT_BYTES:
        raise ToolArgumentError(f"{name!r} exceeds the {_MAX_EDIT_BYTES}-byte UTF-8 limit")
    content = value.encode("utf-8")
    if len(content) > _MAX_EDIT_BYTES:
        raise ToolArgumentError(f"{name!r} exceeds the {_MAX_EDIT_BYTES}-byte UTF-8 limit")
    return content


def _read_file_segment(path: Path, offset: int, maximum: int) -> tuple[bytes, int, int, str]:
    try:
        if path.is_dir():
            raise ToolError(f"path is a directory: {path}")
        digest = hashlib.sha256()
        segment = bytearray()
        size = 0
        capture_start = max(0, offset - 3)
        capture_end = offset + maximum + 4
        with _open_identity_checked(path, "rb") as stream:
            file_size = WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), path).st_size
            if file_size > _MAX_READ_SCAN_BYTES:
                raise ToolError(f"file exceeds {_MAX_READ_SCAN_BYTES}-byte read scan limit: {path}")
            while chunk := stream.read(_IO_CHUNK_BYTES):
                digest.update(chunk)
                chunk_end = size + len(chunk)
                overlap_start = max(size, capture_start)
                overlap_end = min(chunk_end, capture_end)
                if overlap_start < overlap_end:
                    segment.extend(chunk[overlap_start - size : overlap_end - size])
                size = chunk_end
        return bytes(segment), capture_start, size, digest.hexdigest()
    except FileNotFoundError as exc:
        raise ToolError(f"file does not exist: {path}") from exc
    except OSError as exc:
        raise ToolError(f"cannot read file: {path}") from exc


def _utf8_page(
    captured: bytes,
    capture_start: int,
    requested_offset: int,
    maximum: int,
) -> tuple[str, int, int]:
    start = max(0, requested_offset - capture_start)
    while start < len(captured) and captured[start] & 0xC0 == 0x80:
        start += 1
    end = min(start + maximum, len(captured))
    while end > start and end < len(captured) and captured[end] & 0xC0 == 0x80:
        end -= 1
    if end == start and start < len(captured):
        leading = captured[start]
        width = 4 if leading >= 0xF0 else 3 if leading >= 0xE0 else 2 if leading >= 0xC0 else 1
        end = min(start + width, len(captured))
    content = captured[start:end]
    actual_offset = capture_start + start
    return content.decode("utf-8", errors="replace"), actual_offset, actual_offset + len(content)


def atomic_write(
    paths: WorkspacePaths,
    path: StrPath,
    content: bytes,
    expected: str | None,
    *,
    expected_executable: bool | None = None,
    target_executable: bool | None = None,
    maximum: int | None = _MAX_EDIT_BYTES,
) -> tuple[Path, str]:
    if maximum is not None and len(content) > maximum:
        raise ToolError(f"content exceeds {maximum}-byte edit limit")
    target = paths.resolve(path)
    parent = paths.resolve(target.parent)
    if not parent.is_dir():
        raise ToolError(f"parent directory does not exist: {parent}")
    _check_preimage(target, expected, maximum)
    if expected_executable is not None:
        _check_expected_executable(target, expected_executable)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            if target_executable is not None:
                if os.name == "nt" and target_executable:
                    raise ToolError("executable file mode is unavailable on Windows")
                if os.name != "nt":
                    cast(Any, os).fchmod(stream.fileno(), 0o700 if target_executable else 0o600)
            stream.flush()
            os.fsync(stream.fileno())

        rechecked_target = paths.resolve(target)
        rechecked_parent = paths.resolve(parent)
        if rechecked_target != target or rechecked_parent != parent:
            raise ConcurrentModificationError("target path changed during write")
        _check_preimage(rechecked_target, expected, maximum)
        if expected_executable is not None:
            _check_expected_executable(rechecked_target, expected_executable)
        durable_replace(temporary, rechecked_target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise

    return target, sha256_bytes(content)


def rollback_file_checkpoint(
    checkpoint: FileCheckpoint,
) -> Literal["restored", "unchanged", "conflict"]:
    paths = WorkspacePaths(checkpoint.workspace)
    target = paths.resolve(checkpoint.relative_path)
    preimage_kind = checkpoint.preimage_kind or (
        "missing" if checkpoint.preimage is None else "file"
    )
    postimage_kind = checkpoint.postimage_kind
    preimage_executable = (
        False
        if preimage_kind == "file" and checkpoint.preimage_executable is None
        else checkpoint.preimage_executable
    )
    postimage_executable = (
        False
        if postimage_kind == "file" and checkpoint.postimage_executable is None
        else checkpoint.postimage_executable
    )
    actual_kind, actual_sha256, actual_executable = _checkpoint_node_state(target)
    if _node_state_matches(
        actual_kind,
        actual_sha256,
        actual_executable,
        preimage_kind,
        checkpoint.preimage_sha256,
        preimage_executable,
    ):
        return "unchanged"
    if "directory" in {preimage_kind, postimage_kind}:
        return "conflict"
    postimage_matches = _node_state_matches(
        actual_kind,
        actual_sha256,
        actual_executable,
        postimage_kind,
        checkpoint.postimage_sha256,
        postimage_executable,
    )
    intermediate_missing = (
        actual_kind == "missing"
        and preimage_kind != "missing"
        and postimage_kind != "missing"
        and preimage_kind != postimage_kind
    )
    if not postimage_matches and not intermediate_missing:
        return "conflict"
    if preimage_kind == "missing":
        _remove_checkpoint_node(paths, target, actual_kind, actual_sha256, actual_executable)
        return "restored"
    if preimage_kind == "directory":
        if actual_kind != "missing":
            _remove_checkpoint_node(paths, target, actual_kind, actual_sha256, actual_executable)
        target.mkdir()
        fsync_directory(paths.resolve(target.parent))
        return "restored"
    if (
        checkpoint.preimage is None
        or sha256_bytes(checkpoint.preimage) != checkpoint.preimage_sha256
    ):
        raise ToolError("file checkpoint preimage digest is invalid")
    if actual_kind == "directory":
        _remove_checkpoint_node(paths, target, actual_kind, actual_sha256, actual_executable)
        actual_kind, actual_sha256, actual_executable = "missing", None, None
    atomic_write(
        paths,
        target,
        checkpoint.preimage,
        actual_sha256,
        expected_executable=actual_executable if actual_kind == "file" else None,
        target_executable=preimage_executable,
        maximum=None,
    )
    return "restored"


def _checkpoint_node_state(path: Path) -> tuple[str, str | None, bool | None]:
    kind, sha256, executable, _ = _checkpoint_node_state_with_identity(path)
    return kind, sha256, executable


def _checkpoint_node_state_with_identity(
    path: Path,
) -> tuple[str, str | None, bool | None, tuple[int, int] | None]:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return "missing", None, None, None
    except OSError as exc:
        raise ToolError(f"cannot inspect checkpoint path: {path}") from exc
    if stat.S_ISDIR(metadata.st_mode):
        return "directory", None, None, (metadata.st_dev, metadata.st_ino)
    if not stat.S_ISREG(metadata.st_mode):
        raise ToolError(f"checkpoint path is not a regular file or directory: {path}")
    digest, _ = _scan_file(path, max_scan_bytes=None)
    return "file", digest, _file_executable_state(path), None


def _node_state_matches(
    actual_kind: str,
    actual_sha256: str | None,
    actual_executable: bool | None,
    expected_kind: str,
    expected_sha256: str | None,
    expected_executable: bool | None,
) -> bool:
    return (
        actual_kind == expected_kind
        and actual_sha256 == expected_sha256
        and actual_executable == expected_executable
    )


def _remove_checkpoint_node(
    paths: WorkspacePaths,
    target: Path,
    kind: str,
    sha256: str | None,
    executable: bool | None,
    *,
    directory_identity: tuple[int, int] | None = None,
) -> None:
    if kind == "missing":
        return
    if kind not in {"file", "directory"}:
        raise ToolError("checkpoint node kind is invalid")
    if kind == "directory" and directory_identity is None:
        raise ToolError("checkpoint directory identity is unavailable")

    rechecked = paths.resolve(target)
    parent = paths.resolve(rechecked.parent)
    quarantine = parent / (f".{rechecked.name}.agent-workspace-quarantine-{uuid4().hex}")
    try:
        os.replace(rechecked, quarantine)
        fsync_directory(parent)
    except OSError as exc:
        raise ConcurrentModificationError("checkpoint node changed before quarantine") from exc

    retained = quarantine.relative_to(paths.root).as_posix()
    try:
        checked = paths.resolve(quarantine)
        actual_kind, actual_sha256, actual_executable, actual_identity = (
            _checkpoint_node_state_with_identity(checked)
        )
        if not _node_state_matches(
            actual_kind,
            actual_sha256,
            actual_executable,
            kind,
            sha256,
            executable,
        ) or (kind == "directory" and actual_identity != directory_identity):
            raise ConcurrentModificationError(
                f"{kind} changed before removal; retained at {retained}"
            )
        if kind == "file":
            checked.unlink()
        else:
            checked.rmdir()
        fsync_directory(parent)
    except ConcurrentModificationError:
        raise
    except (OSError, ToolError, WorkspacePathError) as exc:
        raise ConcurrentModificationError(
            f"{kind} could not be safely removed; retained at {retained}"
        ) from exc


class ListFilesTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="list_files",
        description=(
            "List files and directories within the workspace. If truncated is true, "
            "the inventory is incomplete: continue by listing returned directories or "
            "using narrower paths before claiming the folder review is complete."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "."},
                "recursive": {"type": "boolean", "default": False},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10000},
                "max_entries": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_LIST_ENTRIES,
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
        if not isinstance(raw_path, str) or not raw_path:
            raise ToolArgumentError("'path' must be a non-empty string")
        recursive = optional_bool(arguments, "recursive", False)
        maximum = optional_int(arguments, "max_results", 1000, minimum=1, maximum=10000)
        max_entries = optional_int(
            arguments,
            "max_entries",
            _MAX_LIST_ENTRIES,
            minimum=1,
            maximum=_MAX_LIST_ENTRIES,
        )
        directory = self.paths.resolve(raw_path)
        if not directory.is_dir():
            raise ToolError(f"path is not a directory: {directory}")

        entries: list[dict[str, Any]] = []
        continuation_paths: set[str] = set()
        pending: deque[Path] = deque((directory,))
        truncated = False
        entries_considered = 0
        while pending:
            current = pending.popleft()
            remaining = maximum - len(entries)
            try:
                enumeration_room = max_entries - entries_considered
                sampled = list(islice(current.iterdir(), enumeration_room + 1))
            except OSError as exc:
                raise ToolError(f"cannot list directory: {current}") from exc
            entries_considered += len(sampled)
            if len(sampled) > enumeration_room:
                truncated = True
                continuation_paths.add(self.paths.relative(current))
                break
            sampled.sort(key=lambda item: (item.name.casefold(), item.name))
            if len(sampled) > remaining:
                truncated = True
                for candidate in sampled[remaining:]:
                    if candidate.is_dir():
                        continuation_paths.add(self.paths.relative(self.paths.resolve(candidate)))
            children = sampled[:remaining]
            for child in children:
                checked = self.paths.resolve(child)
                is_directory = checked.is_dir()
                entries.append(
                    {
                        "path": self.paths.relative(checked),
                        "type": "directory" if is_directory else "file",
                        "size": None if is_directory else checked.stat().st_size,
                    }
                )
                if recursive and is_directory:
                    if len(entries) < maximum:
                        pending.append(checked)
                    else:
                        truncated = True
                        continuation_paths.add(self.paths.relative(checked))
                if len(entries) >= maximum:
                    truncated = truncated or bool(pending) or child != children[-1]
                    continuation_paths.update(self.paths.relative(item) for item in pending)
                    break
            if len(entries) >= maximum:
                break

        document = {
            "entries": entries,
            "entries_considered": entries_considered,
            "truncated": truncated,
        }
        if truncated:
            document["continuation_paths"] = sorted(continuation_paths)[:128]
        if truncated:
            document["continuation_hint"] = (
                "Inventory truncated; inspect returned directories with separate list_files calls "
                "before concluding the workspace review."
            )
        return json_result(document)


class ReadFileTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="read_file",
        description=(
            "Read a UTF-8 workspace file. The JSON content field contains the original text; "
            "metadata and tool-data wrappers are not file content. Returns the file SHA-256; "
            "if truncated, read further pages before copying the full file."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "offset": {"type": "integer", "minimum": 0},
                "max_bytes": {"type": "integer", "minimum": 1, "maximum": 1048576},
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

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        _context: ToolExecutionContext,
    ) -> str:
        return await run_in_process(self._execute_sync, arguments)

    def _execute_sync(self, arguments: dict[str, Any]) -> str:
        raw_path = require_string(arguments, "path")
        offset = optional_int(arguments, "offset", 0, minimum=0, maximum=2**63 - 1)
        maximum = optional_int(arguments, "max_bytes", 262144, minimum=1, maximum=1048576)
        path = self.paths.resolve(raw_path)
        captured, capture_start, size, digest = _read_file_segment(path, offset, maximum)
        content, actual_offset, next_offset = _utf8_page(
            captured,
            capture_start,
            offset,
            maximum,
        )
        return json_result(
            {
                "path": self.paths.relative(path),
                "content": content,
                "offset": actual_offset,
                "next_offset": next_offset,
                "size": size,
                "sha256": digest,
                "truncated": next_offset < size,
            }
        )


class WriteFileTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="write_file",
        description=(
            "Atomically save UTF-8 content to a workspace file. Use expected_sha256=null for a "
            "new destination; to replace an existing destination, first read that destination "
            "and use its observed SHA-256, never the source file digest. Preserve intended text "
            "and whitespace, excluding read-result metadata and tool-data wrappers."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string", "maxLength": _MAX_EDIT_BYTES},
                "expected_sha256": {"type": ["string", "null"]},
            },
            "required": ["path", "content", "expected_sha256"],
            "additionalProperties": False,
        },
        side_effect="write",
        capability=Capability.WORKSPACE_WRITE,
        durable_preimage_checkpoint=True,
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
        context: ToolExecutionContext,
    ) -> str:
        raw_path = require_string(arguments, "path")
        content = _encode_edit_text(
            require_string(arguments, "content", allow_empty=True), "content"
        )
        expected = expected_sha256(arguments)
        path = self.paths.resolve(raw_path)
        preimage = _read_preimage(path, expected, _MAX_EDIT_BYTES)
        relative = self.paths.relative(path)
        postimage_digest = sha256_bytes(content)
        await context.prepare_file_checkpoint(
            FileCheckpoint(
                attempt_id=context.attempt_id,
                session_id=context.session_id,
                workspace=str(self.paths.root),
                started_event_id=context.started_event_id,
                relative_path=relative,
                preimage_sha256=expected,
                preimage=preimage,
                postimage_sha256=postimage_digest,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
        result = await run_in_process(self._execute_prepared, path, content, expected)
        await context.record_event(
            Event(
                session_id=context.session_id,
                type="file.version.recorded",
                data={
                    "attempt_id": context.attempt_id,
                    "path": relative,
                    "sha256": postimage_digest,
                    "bytes": len(content),
                },
                causation_id=context.started_event_id,
                correlation_id=context.correlation_id,
            )
        )
        return result

    def _execute_prepared(
        self,
        path: Path,
        content: bytes,
        expected: str | None,
    ) -> str:
        written_path, digest = atomic_write(self.paths, path, content, expected)
        return json_result(
            {
                "path": self.paths.relative(written_path),
                "bytes_written": len(content),
                "sha256": digest,
            }
        )

    def _execute_sync(self, arguments: dict[str, Any]) -> str:
        raw_path = require_string(arguments, "path")
        content = _encode_edit_text(
            require_string(arguments, "content", allow_empty=True), "content"
        )
        expected = expected_sha256(arguments)
        path = self.paths.resolve(raw_path)
        return self._execute_prepared(path, content, expected)
