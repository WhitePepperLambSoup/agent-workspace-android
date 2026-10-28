"""What a turn changed in the open folder, for the list shown when it ends.

The agent's own writes are recorded as they happen (``file.version.recorded`` names the digest
each one wrote and the one it replaced, and the replaced content is kept), so the list says
exactly which files it created or changed, can show what changed, and can put them back.
Commands it runs can change other files too. For those the folder is listed before the turn and
again after it, by size and modification time; that listing is bounded, and a folder too large
to list in time only shows the agent's own writes. Changes nothing in the turn could have made
(the user editing a file meanwhile) are not attributed to it: other changes are listed only when
the turn ran a tool that may change files without recording them.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from agent_workspace.application.rewind import FileRestore, rewind_files
from agent_workspace.core.events import Event
from agent_workspace.storage.file_versions import FileVersions
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

TURN_FILES_EVENT: Final = "turn.files.changed"
TURN_FILES_UNDONE_EVENT: Final = "turn.files.undone"

# Folders that hold dependencies, caches and version control, and this app's own settings.
SKIPPED_DIRECTORIES: Final = frozenset(
    {
        ".agent",
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".latex-build",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".cache",
        ".next",
        ".nuxt",
        ".svelte-kit",
        ".turbo",
        ".parcel-cache",
        ".gradle",
        ".idea",
        ".vs",
    }
)
MAX_LISTED_FILES: Final = 20_000
MAX_LISTING_SECONDS: Final = 1.5
MAX_REPORTED_FILES: Final = 200
MAX_DIFF_BYTES: Final = 1024 * 1024
MAX_DIFF_LINES: Final = 4000

# Tools whose writes are recorded one by one.
_RECORDED_WRITERS: Final = frozenset(
    {
        "write_file",
        "apply_patch",
        "create_docx",
        "edit_docx",
        "create_xlsx",
        "update_xlsx",
        "create_pptx",
        "download_file",
    }
)
# Tools that change nothing in the folder (or only in the staged sandbox, or another worktree).
_NO_FOLDER_CHANGES: Final = frozenset(
    {
        "list_files",
        "read_file",
        "search_files",
        "code_map",
        "read_document",
        "query_table",
        "git_status",
        "git_log",
        "git_blame",
        "git_diff",
        "web_fetch",
        "web_search",
        "http_request",
        "memory_search",
        "memory_write",
        "session_history",
        "todo",
        "attach_image",
        "run_diagnostics",
        "sandbox_status",
        "run_sandbox",
        "list_sandbox_changesets",
        "inspect_sandbox_change",
        "review_sandbox_change",
        "sandbox_change_status",
        "save_research_source",
        "list_research_sources",
        "read_research_source",
        "add_citation",
        "list_citations",
        "use_skill",
        "delegate_tasks",
        "phone_task",
        "speak_text",
        "background_job_status",
        "background_job_logs",
        "stop_background_job",
        "discover_executables",
    }
)
_QUARANTINE_MARKER: Final = ".agent-workspace-quarantine-"

# Relative path -> (size, modification time in nanoseconds).
type Listing = dict[str, tuple[int, int]]


def _key(path: str) -> str:
    """Paths compare as the file system does: without case on Windows."""
    return path.casefold() if os.name == "nt" else path


def list_folder(
    root: Path,
    *,
    max_files: int = MAX_LISTED_FILES,
    max_seconds: float = MAX_LISTING_SECONDS,
    clock: Callable[[], float] = time.monotonic,
) -> Listing | None:
    """Every file under the folder with its size and modification time.

    None when the folder has more files than ``max_files`` or takes longer than
    ``max_seconds`` to list. Links and junctions are not followed.
    """
    deadline = clock() + max_seconds
    listing: Listing = {}
    pending: list[tuple[str, str]] = [(os.fspath(root), "")]
    seen = 0
    while pending:
        directory, prefix = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    seen += 1
                    if seen % 256 == 0 and clock() > deadline:
                        return None
                    name = entry.name
                    try:
                        if entry.is_symlink() or entry.is_junction():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if name not in SKIPPED_DIRECTORIES:
                                pending.append((entry.path, f"{prefix}{name}/"))
                            continue
                        if not entry.is_file(follow_symlinks=False) or _QUARANTINE_MARKER in name:
                            continue
                        info = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    listing[prefix + name] = (info.st_size, info.st_mtime_ns)
                    if len(listing) > max_files:
                        return None
        except OSError:
            if not prefix:
                return None
    return listing if clock() <= deadline else None


@dataclass(slots=True)
class _Write:
    first_previous: str | None
    previous_known: bool
    last_written: str
    size: int


@dataclass(slots=True)
class TurnFileWatch:
    """Collects one turn's file changes from its events, then lists what changed."""

    workspace: Path
    before: Listing | None
    lister: Callable[[Path], Listing | None] = list_folder
    turn_id: str | None = None
    _writes: dict[str, _Write] = field(default_factory=dict)
    # How each written path is spelled, by its comparison key.
    _names: dict[str, str] = field(default_factory=dict)
    _arguments: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    _moves: dict[str, str] = field(default_factory=dict)
    _deleted: set[str] = field(default_factory=set)
    _untracked_tools: bool = False

    def observe(self, event: Event) -> None:
        data = event.data
        if event.type == "turn.started":
            if self.turn_id is None and event.correlation_id:
                self.turn_id = event.correlation_id
        elif event.type == "file.version.recorded":
            self._record_write(data)
        elif event.type == "tool.proposed":
            attempt = data.get("attempt_id")
            arguments = data.get("arguments")
            if isinstance(attempt, str) and isinstance(arguments, Mapping):
                self._arguments[attempt] = arguments
        elif event.type == "tool.started":
            name = data.get("name")
            if isinstance(name, str) and name not in _RECORDED_WRITERS | _NO_FOLDER_CHANGES:
                self._untracked_tools = True
        elif event.type == "tool.settled":
            self._record_settled(data)

    def _record_write(self, data: Mapping[str, Any]) -> None:
        path = data.get("path")
        written = data.get("sha256")
        if not isinstance(path, str) or not path or not isinstance(written, str):
            return
        size = data.get("bytes")
        previous = data.get("previous_sha256")
        known = "previous_sha256" in data and (previous is None or isinstance(previous, str))
        earlier = self._writes.get(_key(path))
        if earlier is not None:
            earlier.last_written = written
            earlier.size = size if type(size) is int else earlier.size
            return
        self._writes[_key(path)] = _Write(
            previous if known and isinstance(previous, str) else None,
            known,
            written,
            size if type(size) is int else -1,
        )
        self._names[_key(path)] = path

    def _record_settled(self, data: Mapping[str, Any]) -> None:
        name = data.get("name")
        attempt = data.get("attempt_id")
        arguments = self._arguments.pop(attempt, None) if isinstance(attempt, str) else None
        if name == "move_path" and arguments is not None:
            source, destination = arguments.get("source"), arguments.get("destination")
            if isinstance(source, str) and isinstance(destination, str):
                self._moves[_normal(source)] = _normal(destination)
        elif name == "delete_path" and arguments is not None:
            path = arguments.get("path")
            if isinstance(path, str) and arguments.get("kind") == "file":
                self._deleted.add(_normal(path))
        elif name == "organize_files":
            for step in _batch_steps(data.get("result")):
                action, path, target = step
                if action == "move" and target:
                    self._moves[_normal(path)] = _normal(target)
                elif action == "recycle":
                    self._deleted.add(_normal(path))

    def finish(self) -> dict[str, Any] | None:
        """The ``turn.files.changed`` record for this turn, or None when nothing changed."""
        before = self.before
        after = self.lister(self.workspace) if before is not None else None
        listed = before is not None and after is not None
        before_keys = {_key(path): path for path in before} if before is not None else {}
        after_keys = {_key(path): path for path in after} if after is not None else {}
        entries: list[dict[str, Any]] = []
        explained: set[str] = set()
        moved_away = {_key(source) for source in self._moves}

        for key, write in self._writes.items():
            path = self._names.get(key, key)
            if after is not None:
                if key not in after_keys:
                    if key in moved_away:
                        continue  # the moves below say where it went
                    explained.add(key)
                    if key in before_keys:
                        entries.append(_entry(before_keys[key], "deleted", "agent"))
                    continue
                path = after_keys[key]
            elif not (self.workspace / path).is_file():
                continue
            explained.add(key)
            if write.previous_known and write.first_previous == write.last_written:
                continue  # back as it was before the turn
            created = (write.previous_known and write.first_previous is None) or (
                not write.previous_known and before is not None and key not in before_keys
            )
            entry = _entry(path, "created" if created else "modified", "agent")
            entry["before"] = None if created else write.first_previous
            entry["after"] = write.last_written
            size = after[after_keys[key]][0] if after is not None else write.size
            if size >= 0:
                entry["bytes"] = size
            entries.append(entry)

        for source, destination in self._moves.items():
            source_key, destination_key = _key(source), _key(destination)
            if source_key in explained:
                continue
            if after is not None and (
                source_key in after_keys or destination_key not in after_keys
            ):
                continue
            explained.update({source_key, destination_key})
            target = after_keys.get(destination_key, destination)
            if before is not None and source_key not in before_keys:
                # Made during the turn and then moved: new where it ended.
                ended = after[target][0] if after is not None else None
                entries.append(_entry(target, "created", "agent", ended))
                continue
            entry = _entry(before_keys.get(source_key, source), "moved", "agent")
            entry["to"] = target
            entries.append(entry)

        for path in sorted(self._deleted):
            key = _key(path)
            if key in explained or (after is not None and key in after_keys):
                continue
            explained.add(key)
            if before is not None and key not in before_keys:
                continue  # made and removed during the turn (a scratch file, a screenshot)
            entries.append(_entry(before_keys.get(key, path), "deleted", "agent"))

        if before is not None and after is not None and self._untracked_tools:
            for key, path in sorted(after_keys.items()):
                if key in explained:
                    continue
                if key not in before_keys:
                    entries.append(_entry(path, "created", "other", after[path][0]))
                elif before[before_keys[key]] != after[path]:
                    entries.append(_entry(path, "modified", "other", after[path][0]))
            for key, path in sorted(before_keys.items()):
                if key not in explained and key not in after_keys:
                    entries.append(_entry(path, "deleted", "other"))

        if not entries:
            return None
        order = {"agent": 0, "other": 1}
        entries.sort(key=lambda item: (order[item["by"]], item["path"].casefold()))
        return {
            "turn_id": self.turn_id,
            "files": entries[:MAX_REPORTED_FILES],
            "omitted": max(0, len(entries) - MAX_REPORTED_FILES),
            "listed": listed,
        }


def _entry(path: str, change: str, by: str, size: int | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"path": path, "change": change, "by": by}
    if size is not None:
        entry["bytes"] = size
    return entry


def _normal(path: str) -> str:
    """A tool's path argument as the folder listing spells it."""
    return path.replace("\\", "/").strip().removeprefix("./")


def _batch_steps(result: object) -> list[tuple[str, str, str | None]]:
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return []
    steps = result.get("steps") if isinstance(result, Mapping) else None
    if not isinstance(steps, list):
        return []
    found: list[tuple[str, str, str | None]] = []
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        action, path, target = step.get("action"), step.get("path"), step.get("to")
        if isinstance(action, str) and isinstance(path, str):
            found.append((action, path, target if isinstance(target, str) else None))
    return found


# Folders found too large to list, and when: their turns skip the listing (each attempt costs up
# to MAX_LISTING_SECONDS before the turn starts) for a while.
_UNLISTED: dict[str, float] = {}
UNLISTED_SECONDS: Final = 30 * 60.0


def start_turn_watch(
    workspace: Path, *, clock: Callable[[], float] = time.monotonic
) -> TurnFileWatch:
    """List the folder before a turn starts (unless it was too large to list a short while ago)."""
    key = os.path.normcase(os.fspath(workspace))
    found = _UNLISTED.get(key)
    if found is not None and clock() - found < UNLISTED_SECONDS:
        return TurnFileWatch(workspace, None)
    listing = list_folder(workspace)
    if listing is None:
        _UNLISTED[key] = clock()
    else:
        _UNLISTED.pop(key, None)
    return TurnFileWatch(workspace, listing)


def display_record(data: Mapping[str, Any]) -> dict[str, Any]:
    """A ``turn.files.changed`` record as the window shows it: without the content digests,
    which the gateway looks up itself when asked for a diff or an undo."""
    files = data.get("files")
    shown = [
        {
            **{key: item[key] for key in ("path", "change", "by", "to", "bytes") if key in item},
            # The agent's recorded writes can be put back; other changes cannot.
            **({"undoable": True} if isinstance(item.get("after"), str) else {}),
        }
        for item in (files if isinstance(files, list) else [])
        if isinstance(item, Mapping)
    ]
    return {
        **{key: data[key] for key in ("turn_id", "omitted", "listed") if key in data},
        "files": shown,
    }


def changed_file(record: Event, path: str) -> Mapping[str, Any]:
    """The agent's entry for a path in a ``turn.files.changed`` record."""
    files = record.data.get("files")
    for item in files if isinstance(files, list) else []:
        if isinstance(item, Mapping) and item.get("path") == path and item.get("by") == "agent":
            return item
    raise KeyError(path)


def undo_turn_files(
    workspace: Path,
    versions: FileVersions,
    record: Event,
    paths: Sequence[str] | None,
    *,
    apply: bool,
) -> list[FileRestore]:
    """Put the files the agent created or changed in a turn back as they were before it.

    Uses the same rules as rewinding to a message: a file is put back only while it is exactly
    as the turn left it, and what it replaces is kept first.
    """
    marker = Event(session_id=record.session_id, type="turn.files.undo", data={}, sequence=0)
    events: list[Event] = [marker]
    wanted = None if paths is None else set(paths)
    files = record.data.get("files")
    for item in files if isinstance(files, list) else []:
        if not isinstance(item, Mapping) or item.get("by") != "agent":
            continue
        path, change, after = item.get("path"), item.get("change"), item.get("after")
        if not isinstance(path, str) or change not in {"created", "modified"}:
            continue
        if not isinstance(after, str) or (wanted is not None and path not in wanted):
            continue
        data: dict[str, Any] = {"path": path, "sha256": after}
        before = item.get("before")
        if change == "created":
            data["previous_sha256"] = None
        elif isinstance(before, str):
            data["previous_sha256"] = before
        events.append(
            Event(
                session_id=record.session_id,
                type="file.version.recorded",
                data=data,
                sequence=len(events),
            )
        )
    return rewind_files(workspace, versions, events, marker.id, apply=apply)


def file_diff(workspace: Path, versions: FileVersions, entry: Mapping[str, Any]) -> dict[str, Any]:
    """What the turn changed in one text file, as a unified diff against its content now."""
    path = entry.get("path")
    if not isinstance(path, str):
        return {"state": "unavailable"}
    try:
        target = WorkspacePaths(workspace).resolve(path)
    except WorkspacePathError:
        return {"state": "unavailable"}
    if entry.get("change") == "created":
        before: bytes | None = b""
    else:
        digest = entry.get("before")
        before = versions.read(digest) if isinstance(digest, str) else None
    if before is None:
        return {"state": "not_kept"}
    missing = False
    try:
        if target.stat().st_size > MAX_DIFF_BYTES:
            return {"state": "too_large"}
        after = target.read_bytes()
    except FileNotFoundError:
        after, missing = b"", True
    except OSError:
        return {"state": "unavailable"}
    if len(before) > MAX_DIFF_BYTES:
        return {"state": "too_large"}
    try:
        old_text, new_text = before.decode("utf-8"), after.decode("utf-8")
    except UnicodeDecodeError:
        return {"state": "binary"}
    if "\x00" in old_text or "\x00" in new_text:
        return {"state": "binary"}
    lines = list(
        difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=3,
        )
    )
    truncated = len(lines) > MAX_DIFF_LINES
    text = "".join(line if line.endswith("\n") else f"{line}\n" for line in lines[:MAX_DIFF_LINES])
    written = entry.get("after")
    return {
        "state": "ok",
        "diff": text,
        "truncated": truncated,
        "missing": missing,
        "changedSince": not missing
        and isinstance(written, str)
        and hashlib.sha256(after).hexdigest() != written,
    }


__all__ = [
    "MAX_REPORTED_FILES",
    "SKIPPED_DIRECTORIES",
    "TURN_FILES_EVENT",
    "TURN_FILES_UNDONE_EVENT",
    "Listing",
    "TurnFileWatch",
    "changed_file",
    "display_record",
    "file_diff",
    "list_folder",
    "start_turn_watch",
    "undo_turn_files",
]
