"""Put workspace files back as they were before a message of a conversation.

Every file the agent writes records the digest it wrote and the digest it replaced
(``file.version.recorded``), and the replaced content is kept in the version store. Rewinding to
a message restores each file changed after it to its content from before the first of those
changes, provided the file is still exactly as the last change left it. A file the agent
created is removed. Before anything is overwritten or removed its current content goes to the
version store too, so nothing is lost. Files changed since by something else are left alone and
reported, as are files whose earlier content is no longer kept.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_workspace.core.events import Event
from agent_workspace.storage.file_versions import FileVersions
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

type RestoreAction = Literal["restore", "remove"]
# Why a file was left alone: changed since, earlier content not kept, outside the workspace.
type LeftAlone = Literal["changed", "not_kept", "unsafe", "failed"]
_UNKNOWN = object()


@dataclass(frozen=True, slots=True)
class FileRestore:
    path: str
    action: RestoreAction
    reason: LeftAlone | None = None  # None: restored (or would be, in a preview)

    def document(self) -> dict[str, str | None]:
        return {"path": self.path, "action": self.action, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class _Change:
    first_previous: object  # the digest before the first change, None for a new file, or unknown
    last_written: str


def changes_after(events: Sequence[Event], message_id: str) -> dict[str, _Change]:
    """Files the agent wrote after the message, oldest change first."""
    start = next((event.sequence for event in events if event.id == message_id), None)
    if start is None:
        raise KeyError(message_id)
    changes: dict[str, _Change] = {}
    for event in events:
        if (
            event.type != "file.version.recorded"
            or event.sequence is None
            or event.sequence <= start
        ):
            continue
        path = event.data.get("path")
        written = event.data.get("sha256")
        if not isinstance(path, str) or not isinstance(written, str):
            continue
        previous = event.data.get("previous_sha256", _UNKNOWN)
        if previous is not None and previous is not _UNKNOWN and not isinstance(previous, str):
            previous = _UNKNOWN
        earlier = changes.get(path)
        changes[path] = _Change(earlier.first_previous if earlier else previous, written)
    return changes


def _digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def rewind_files(
    workspace: Path,
    versions: FileVersions,
    events: Sequence[Event],
    message_id: str,
    *,
    apply: bool,
) -> list[FileRestore]:
    """Each file changed after the message, and whether it is (or would be) put back."""
    paths = WorkspacePaths(workspace)
    report: list[FileRestore] = []
    for relative, change in changes_after(events, message_id).items():
        action: RestoreAction = "remove" if change.first_previous is None else "restore"
        try:
            target = paths.resolve(relative)
        except WorkspacePathError:
            report.append(FileRestore(relative, action, "unsafe"))
            continue
        current = _digest(target)
        if current != change.last_written:
            report.append(FileRestore(relative, action, "changed"))
            continue
        earlier: bytes | None = None
        if action == "restore":
            if not isinstance(change.first_previous, str):
                report.append(FileRestore(relative, action, "not_kept"))
                continue
            earlier = versions.read(change.first_previous)
            if earlier is None:
                report.append(FileRestore(relative, action, "not_kept"))
                continue
        if apply:
            try:
                versions.keep(target.read_bytes())  # what the rewind replaces stays recoverable
                if earlier is None:
                    target.unlink()
                else:
                    _write(target, earlier)
            except OSError:
                report.append(FileRestore(relative, action, "failed"))
                continue
        report.append(FileRestore(relative, action))
    return report


__all__ = ["FileRestore", "changes_after", "rewind_files"]
