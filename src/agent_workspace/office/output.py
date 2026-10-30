# ruff: noqa: RUF001, RUF002 -- file names use Chinese brackets.
"""Files the office tools write into the folder: each one checkpointed and recorded like
write_file's, so the change list under the turn shows it and can put it back."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.events import Event
from agent_workspace.core.models import FileCheckpoint
from agent_workspace.storage.durable import durable_replace
from agent_workspace.storage.file_versions import FileVersions
from agent_workspace.tools.base import ToolArgumentError
from agent_workspace.tools.paths import (
    WorkspacePathError,
    WorkspacePaths,
    is_sensitive_workspace_path,
)

MAX_INPUT = 200 * 1024 * 1024


def safe_name(text: str, fallback: str = "文件") -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "-", text).strip(" .-")
    return name[:80] or fallback


class Folder:
    """The open folder, as the office tools read and write it."""

    def __init__(self, workspace: Path, versions: FileVersions | None = None) -> None:
        self.paths = WorkspacePaths(workspace)
        self.versions = versions
        # Tool calls that already hold their durable checkpoint: the runner keeps one per call.
        self._checkpointed: set[str] = set()

    def resolve(self, raw: str, suffixes: set[str] | None = None, must_exist: bool = True) -> Path:
        try:
            path = self.paths.resolve(raw)
        except WorkspacePathError as error:
            raise ToolArgumentError(str(error)) from None
        if suffixes and path.suffix.lower() not in suffixes:
            raise ToolArgumentError(f"{raw} must be one of: {', '.join(sorted(suffixes))}")
        if must_exist and not path.is_file():
            raise ToolArgumentError(f"{raw} is not a file of the folder")
        return path

    def read(self, raw: str, suffixes: set[str] | None = None) -> tuple[Path, bytes]:
        path = self.resolve(raw, suffixes)
        if path.stat().st_size > MAX_INPUT:
            raise ToolArgumentError(f"{raw} is larger than 200 MB")
        return path, path.read_bytes()

    def relative(self, path: Path) -> str:
        return self.paths.relative(path)

    def free(self, raw: str) -> Path:
        """``raw``, or raw-2, -3 … when a file of that name is there."""
        path = self.resolve(raw, must_exist=False)
        candidate, number = path, 2
        while candidate.exists():
            candidate = path.with_name(f"{path.stem}-{number}{path.suffix}")
            number += 1
        return candidate

    def beside(self, source: Path, label: str, suffix: str | None = None) -> str:
        """A folder-relative name next to ``source``: 'stem（label）.ext'."""
        name = f"{source.stem}（{label}）{suffix or source.suffix}"
        return self.relative(source.parent / name) if source.parent != self.paths.root else name

    async def write(
        self, context: ToolExecutionContext | None, raw: str, data: bytes, *, replace: bool = False
    ) -> dict[str, Any]:
        """Write a file of the folder: a new name unless ``replace`` (then the old content is
        kept for undo).

        A tool call has one durable checkpoint (the runner rolls the call back from it after a
        crash), so only its first file gets one; every file's earlier content still goes to the
        version store and every file is recorded for the turn's change list and undo."""
        target = self.resolve(raw, must_exist=False) if replace else self.free(raw)
        relative = self.relative(target)
        if is_sensitive_workspace_path(relative):
            raise ToolArgumentError(f"{relative} is a protected path")
        target.parent.mkdir(parents=True, exist_ok=True)
        preimage = await asyncio.to_thread(target.read_bytes) if target.is_file() else None
        previous = hashlib.sha256(preimage).hexdigest() if preimage is not None else None
        digest = hashlib.sha256(data).hexdigest()
        if context is not None and context.attempt_id not in self._checkpointed:
            if len(self._checkpointed) > 4096:
                self._checkpointed.clear()
            self._checkpointed.add(context.attempt_id)
            await context.prepare_file_checkpoint(
                FileCheckpoint(
                    attempt_id=context.attempt_id,
                    session_id=context.session_id,
                    workspace=str(self.paths.root),
                    started_event_id=context.started_event_id,
                    relative_path=relative,
                    preimage_sha256=previous,
                    preimage=preimage,
                    postimage_sha256=digest,
                    created_at=datetime.now(UTC).isoformat(),
                )
            )
        if preimage is not None and self.versions is not None:
            await asyncio.to_thread(self.versions.keep, preimage)
        await asyncio.to_thread(_replace, target, data)
        if context is not None:
            await context.record_event(
                Event(
                    session_id=context.session_id,
                    type="file.version.recorded",
                    data={
                        "attempt_id": context.attempt_id,
                        "path": relative,
                        "sha256": digest,
                        "bytes": len(data),
                        "previous_sha256": previous,
                    },
                    causation_id=context.started_event_id,
                    correlation_id=context.correlation_id,
                )
            )
        return {"path": relative, "bytes": len(data)}


def _replace(target: Path, data: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        durable_replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


__all__ = ["Folder", "safe_name"]
