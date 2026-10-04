from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.storage.durable import fsync_directory

from .base import ConcurrentModificationError, ToolArgumentError, ToolError, json_result
from .paths import StrPath, WorkspacePaths
from .process_worker import run_in_process

_MAX_MANAGED_FILE_BYTES = 16 * 1024 * 1024


def _file_digest(path: Path) -> str:
    try:
        if not path.is_file():
            raise ToolError(f"path is not a regular file: {path}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            metadata = WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), path)
            if metadata.st_size > _MAX_MANAGED_FILE_BYTES:
                raise ToolError(
                    f"managed file exceeds {_MAX_MANAGED_FILE_BYTES}-byte safety limit: {path}"
                )
            while chunk := stream.read(64 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
    except FileNotFoundError as exc:
        raise ToolError(f"file does not exist: {path}") from exc
    except OSError as exc:
        raise ToolError(f"cannot read managed file: {path}") from exc


def _make_directory_sync(workspace: str, raw_path: str) -> str:
    paths = WorkspacePaths(workspace)
    target = paths.resolve(raw_path)
    parent = paths.resolve(target.parent)
    if target.exists():
        raise ConcurrentModificationError(f"directory target already exists: {target}")
    if not parent.is_dir():
        raise ToolError(f"directory parent does not exist: {parent}")
    try:
        target.mkdir()
        fsync_directory(parent)
    except OSError as exc:
        raise ToolError(f"cannot create directory: {target}") from exc
    return json_result({"path": paths.relative(target), "created": True})


def _move_file_sync(
    workspace: str,
    raw_source: str,
    raw_destination: str,
    expected_sha256: str,
) -> str:
    paths = WorkspacePaths(workspace)
    source = paths.resolve(raw_source)
    destination = paths.resolve(raw_destination)
    source_parent = paths.resolve(source.parent)
    destination_parent = paths.resolve(destination.parent)
    if source == destination:
        raise ToolArgumentError("source and destination must differ")
    if destination.exists():
        raise ConcurrentModificationError(f"move destination already exists: {destination}")
    if not destination_parent.is_dir():
        raise ToolError(f"move destination parent does not exist: {destination_parent}")
    actual = _file_digest(source)
    if actual != expected_sha256:
        raise ConcurrentModificationError(
            f"source changed: expected {expected_sha256}, found {actual}"
        )
    if _file_digest(source) != expected_sha256 or destination.exists():
        raise ConcurrentModificationError("move paths changed before mutation")
    try:
        os.rename(source, destination)
        fsync_directory(source_parent)
        if destination_parent != source_parent:
            fsync_directory(destination_parent)
    except OSError as exc:
        raise ToolError(f"cannot move file to destination: {destination}") from exc
    return json_result(
        {
            "source": paths.relative(source),
            "destination": paths.relative(destination),
            "sha256": expected_sha256,
        }
    )


def _delete_path_sync(
    workspace: str,
    kind: str,
    raw_path: str,
    expected_sha256: str | None,
) -> str:
    paths = WorkspacePaths(workspace)
    target = paths.resolve(raw_path)
    parent = paths.resolve(target.parent)
    if target == paths.root:
        raise ToolArgumentError("workspace root cannot be deleted")
    try:
        if kind == "file":
            if expected_sha256 is None:
                raise ToolArgumentError("file deletion requires 'expected_sha256'")
            actual = _file_digest(target)
            if actual != expected_sha256:
                raise ConcurrentModificationError(
                    f"file changed: expected {expected_sha256}, found {actual}"
                )
            if _file_digest(target) != expected_sha256:
                raise ConcurrentModificationError("file changed before deletion")
            target.unlink()
        elif kind == "empty_directory":
            if not target.is_dir():
                raise ToolError(f"path is not a directory: {target}")
            target.rmdir()
        else:
            raise ToolArgumentError("unsupported deletion kind")
        fsync_directory(parent)
    except (ConcurrentModificationError, ToolArgumentError, ToolError):
        raise
    except OSError as exc:
        raise ToolError(f"cannot delete {kind.replace('_', ' ')}: {target}") from exc
    return json_result({"path": paths.relative(target), "kind": kind, "deleted": True})


class _ManageTool:
    hard_cancellable = False

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )


class MakeDirectoryTool(_ManageTool):
    _SPEC = ToolSpec(
        name="make_directory",
        description="Create one workspace directory whose parent already exists.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "minLength": 1}},
            "required": ["path"],
            "additionalProperties": False,
        },
        side_effect="mkdir",
        capability=Capability.WORKSPACE_MANAGE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        raw_path = arguments.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise ToolArgumentError("'path' must be a non-empty string")
        return await run_in_process(_make_directory_sync, str(self.paths.root), raw_path)


class MovePathTool(_ManageTool):
    _SPEC = ToolSpec(
        name="move_path",
        description=(
            "Move one bounded regular workspace file without overwrite using a SHA-256 CAS check."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string", "minLength": 1},
                "destination": {"type": "string", "minLength": 1},
                "expected_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-fA-F]{64}$",
                },
            },
            "required": ["source", "destination", "expected_sha256"],
            "additionalProperties": False,
        },
        side_effect="move",
        capability=Capability.WORKSPACE_MANAGE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        source = arguments.get("source")
        destination = arguments.get("destination")
        expected = arguments.get("expected_sha256")
        if not all(isinstance(value, str) and value for value in (source, destination, expected)):
            raise ToolArgumentError("move requires source, destination, and expected_sha256")
        assert isinstance(source, str)
        assert isinstance(destination, str)
        assert isinstance(expected, str)
        return await run_in_process(
            _move_file_sync,
            str(self.paths.root),
            source,
            destination,
            expected.lower(),
        )


class DeletePathTool(_ManageTool):
    _SPEC = ToolSpec(
        name="delete_path",
        description=(
            "Delete one bounded CAS-checked regular file or one empty directory. Recursive "
            "deletion is unavailable. Every deletion requires user approval and is not "
            "automatically replayed after a crash."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["file", "empty_directory"]},
                "path": {"type": "string", "minLength": 1},
                "expected_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-fA-F]{64}$",
                },
            },
            "required": ["kind", "path"],
            "allOf": [
                {
                    "if": {"properties": {"kind": {"const": "file"}}},
                    "then": {"required": ["expected_sha256"]},
                },
                {
                    "if": {"properties": {"kind": {"const": "empty_directory"}}},
                    "then": {"not": {"required": ["expected_sha256"]}},
                },
            ],
            "additionalProperties": False,
        },
        side_effect="delete",
        capability=Capability.WORKSPACE_MANAGE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        kind = arguments.get("kind")
        raw_path = arguments.get("path")
        expected = arguments.get("expected_sha256")
        if kind not in {"file", "empty_directory"}:
            raise ToolArgumentError("'kind' is unsupported")
        if not isinstance(raw_path, str) or not raw_path:
            raise ToolArgumentError("'path' must be a non-empty string")
        if expected is not None and not isinstance(expected, str):
            raise ToolArgumentError("'expected_sha256' must be a string")
        return await run_in_process(
            _delete_path_sync,
            str(self.paths.root),
            kind,
            raw_path,
            expected.lower() if isinstance(expected, str) else None,
        )
