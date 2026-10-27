"""Many file moves, copies and removals in one approved call, each batch undoable afterwards.

The agent sends the whole list and the user approves it once. Before anything changes the list
is checked as a whole: every source exists, nothing leaves the workspace or touches ``.git``, and
no destination is taken or named twice. Each step is written to the batch's journal as soon as it
is done. Removed items go to a recycle area in the app's data folder instead of being deleted,
and destination folders that did not exist are made and remembered. If a step fails, the steps
already taken are reversed.

Undo walks the journal backwards and reverses a step only while the item is still as the batch
left it, so something the user changed afterwards is never moved or removed; such steps are
reported and can be tried again later. Batches, and the items they recycled, are kept 30 days.
"""

from __future__ import annotations

import asyncio
import errno
import hashlib
import json
import os
import shutil
import stat
import tempfile
import threading
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result
from agent_workspace.tools.paths import StrPath, WorkspacePathError, WorkspacePaths

type Action = Literal["move", "copy", "recycle", "make_folder"]
ACTIONS: tuple[Action, ...] = ("move", "copy", "recycle", "make_folder")
MAX_OPERATIONS = 500
MAX_TREE_ENTRIES = 20_000
# What one batch may copy, including recycling to another drive (which copies, then removes).
MAX_COPY_BYTES = 4 * 1024 * 1024 * 1024
KEEP_SECONDS = 30 * 24 * 3600
_EDGE_BYTES = 64 * 1024
_RESULT_STEPS = 50
_ID_LENGTH = 32
UNDOABLE_STATES = frozenset({"done", "partly_undone", "interrupted"})


class FileBatchError(ToolError):
    """The batch was refused or could not finish; the message says why."""


@dataclass(frozen=True, slots=True)
class Operation:
    action: Action
    path: str
    to: str | None = None


@dataclass(slots=True)
class Step:
    action: Action
    path: str  # workspace-relative, POSIX separators
    to: str | None  # workspace-relative; for recycle, the item's place in the batch folder
    kind: Literal["file", "folder"]
    fingerprint: str
    auto: bool = False  # a destination folder the batch made
    undone: bool = False

    def document(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "path": self.path,
            "to": self.to,
            "kind": self.kind,
            "fingerprint": self.fingerprint,
            "auto": self.auto,
            "undone": self.undone,
        }

    @classmethod
    def from_document(cls, raw: dict[str, Any]) -> Step:
        return cls(
            action=raw["action"],
            path=raw["path"],
            to=raw.get("to"),
            kind=raw["kind"],
            fingerprint=raw["fingerprint"],
            auto=bool(raw.get("auto", False)),
            undone=bool(raw.get("undone", False)),
        )


@dataclass(slots=True)
class FileBatch:
    id: str
    workspace: str
    summary: str
    created_at: str
    state: str  # running, done, failed, undone, partly_undone, interrupted
    steps: list[Step] = field(default_factory=list)
    updated_at: str = ""
    problems: list[dict[str, str]] = field(default_factory=list)

    def document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workspace": self.workspace,
            "summary": self.summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at or self.created_at,
            "state": self.state,
            "steps": [step.document() for step in self.steps],
            "problems": self.problems,
        }

    @classmethod
    def from_document(cls, raw: dict[str, Any]) -> FileBatch:
        return cls(
            id=raw["id"],
            workspace=raw["workspace"],
            summary=raw.get("summary", ""),
            created_at=raw["created_at"],
            state=raw["state"],
            steps=[Step.from_document(item) for item in raw.get("steps", [])],
            updated_at=raw.get("updated_at", ""),
            problems=list(raw.get("problems", [])),
        )


@dataclass(frozen=True, slots=True)
class UndoReport:
    batch: FileBatch
    undone: int
    skipped: list[dict[str, str]]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _is_link(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(metadata, "st_file_attributes", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & 0x400)


def _tree(folder: Path) -> Iterator[tuple[str, os.stat_result]]:
    """Every entry under a folder, refusing links and reparse points, within the entry limit."""
    count = 0
    pending = [folder]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                count += 1
                if count > MAX_TREE_ENTRIES:
                    raise FileBatchError(
                        f"{folder.name} holds more than {MAX_TREE_ENTRIES} items; "
                        "organize it in smaller parts"
                    )
                path = Path(entry.path)
                if _is_link(path):
                    raise FileBatchError(f"{path.name} is a link; links are not moved in batches")
                metadata = entry.stat(follow_symlinks=False)
                yield path.relative_to(folder).as_posix(), metadata
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)


def fingerprint(path: Path) -> str:
    """What the item is now: size, change time and edge bytes of a file; every entry of a folder."""
    if _is_link(path):
        raise FileBatchError(f"{path.name} is a link; links are not moved in batches")
    metadata = path.stat()
    if stat.S_ISREG(metadata.st_mode):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            digest.update(stream.read(_EDGE_BYTES))
            if metadata.st_size > 2 * _EDGE_BYTES:
                stream.seek(-_EDGE_BYTES, os.SEEK_END)
                digest.update(stream.read(_EDGE_BYTES))
        return f"f:{metadata.st_size}:{metadata.st_mtime_ns}:{digest.hexdigest()[:32]}"
    if stat.S_ISDIR(metadata.st_mode):
        lines = sorted(
            f"{name}\td"
            if stat.S_ISDIR(entry.st_mode)
            else f"{name}\tf\t{entry.st_size}\t{entry.st_mtime_ns}"
            for name, entry in _tree(path)
        )
        return "d:" + hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    raise FileBatchError(f"{path.name} is neither a file nor a folder")


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(entry.st_size for _, entry in _tree(path) if stat.S_ISREG(entry.st_mode))


def _cross_device(error: OSError) -> bool:
    return error.errno == errno.EXDEV or getattr(error, "winerror", None) == 17


def _relocate(source: Path, destination: Path) -> None:
    """Rename; to another drive, copy and then remove the original."""
    try:
        os.rename(source, destination)
    except OSError as error:
        if not _cross_device(error):
            raise
        if _size(source) > MAX_COPY_BYTES:
            raise FileBatchError(
                f"{source.name} is too large to keep in the recycle area on another drive"
            ) from None
        if source.is_dir():
            shutil.copytree(source, destination, copy_function=shutil.copy2)
            shutil.rmtree(source)
        else:
            shutil.copy2(source, destination)
            source.unlink()


_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(root: Path) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(os.path.normcase(str(root)), threading.Lock())


class FileBatchStore:
    """The journal and recycle area of every batch, one folder per batch."""

    def __init__(self, root: Path, *, clock: Any = time.time) -> None:
        self.root = root
        self._clock = clock
        self.lock = _lock_for(root)

    def folder(self, batch_id: str) -> Path:
        if len(batch_id) != _ID_LENGTH or any(char not in "0123456789abcdef" for char in batch_id):
            raise FileBatchError("unknown batch")
        return self.root / batch_id

    def save(self, batch: FileBatch) -> None:
        batch.updated_at = _now()
        folder = self.folder(batch.id)
        folder.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".batch-", dir=folder)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(batch.document(), stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, folder / "batch.json")
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def get(self, batch_id: str) -> FileBatch:
        try:
            raw = json.loads((self.folder(batch_id) / "batch.json").read_text("utf-8"))
            return FileBatch.from_document(raw)
        except (OSError, ValueError, KeyError, TypeError):
            raise FileBatchError("unknown batch") from None

    def list(self, workspace: StrPath, limit: int = 50) -> list[FileBatch]:
        if not self.root.is_dir():
            return []
        wanted = os.path.normcase(str(Path(workspace).resolve()))
        batches: list[FileBatch] = []
        for folder in self.root.iterdir():
            try:
                batch = self.get(folder.name)
            except FileBatchError:
                continue
            if os.path.normcase(batch.workspace) == wanted:
                batches.append(batch)
        batches.sort(key=lambda item: item.created_at, reverse=True)
        return batches[:limit]

    def prune(self) -> int:
        """Remove batches (and what they recycled) older than the keeping period."""
        if not self.root.is_dir():
            return 0
        removed = 0
        cutoff = self._clock() - KEEP_SECONDS
        for folder in self.root.iterdir():
            journal = folder / "batch.json"
            try:
                if journal.stat().st_mtime < cutoff:
                    shutil.rmtree(folder)
                    removed += 1
            except OSError:
                continue
        return removed


class _Plan:
    """The filesystem as the batch will leave it, to refuse conflicts before anything changes."""

    def __init__(self, paths: WorkspacePaths) -> None:
        self.paths = paths
        self.vacated: set[str] = set()
        self.created: set[str] = set()
        self.folders: set[str] = set()

    def key(self, path: Path) -> str:
        return os.path.normcase(str(path))

    def exists(self, path: Path) -> bool:
        key = self.key(path)
        if key in self.created or key in self.folders:
            return True
        if key in self.vacated or any(key.startswith(item + os.sep) for item in self.vacated):
            return False
        return path.exists() or path.is_symlink()

    def resolve(self, raw: object, name: str) -> Path:
        if not isinstance(raw, str) or not raw.strip():
            raise ToolArgumentError(f"each operation needs a non-empty '{name}'")
        try:
            path = self.paths.resolve(raw)
        except WorkspacePathError as error:
            raise FileBatchError(str(error)) from None
        if path == self.paths.root:
            raise FileBatchError("the workspace folder itself cannot be moved or removed")
        relative = self.paths.relative(path)
        if ".git" in (part.casefold() for part in relative.split("/")):
            raise FileBatchError(f"{relative}: files inside .git are not organized in batches")
        return path


def parse_operations(arguments: dict[str, Any]) -> tuple[list[Operation], str]:
    raw = arguments.get("operations")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_OPERATIONS:
        raise ToolArgumentError(f"'operations' must list 1 to {MAX_OPERATIONS} changes")
    operations: list[Operation] = []
    for item in raw:
        if not isinstance(item, dict) or item.get("action") not in ACTIONS:
            raise ToolArgumentError(f"each operation needs an action: {', '.join(ACTIONS)}")
        action: Action = item["action"]
        target = item.get("to")
        if action in {"move", "copy"} and not isinstance(target, str):
            raise ToolArgumentError(f"'{action}' needs 'to'")
        if action in {"recycle", "make_folder"} and target is not None:
            raise ToolArgumentError(f"'{action}' takes no 'to'")
        operations.append(Operation(action, item.get("path"), target))  # type: ignore[arg-type]
    summary = arguments.get("summary", "")
    if not isinstance(summary, str) or len(summary) > 200:
        raise ToolArgumentError("'summary' must be at most 200 characters")
    return operations, summary.strip()


def _planned_steps(paths: WorkspacePaths, operations: list[Operation]) -> list[Step]:
    """Check the whole batch; the steps it will take, destination folders first where needed."""
    plan = _Plan(paths)
    steps: list[Step] = []
    copied = 0
    for operation in operations:
        source = plan.resolve(operation.path, "path")
        relative = paths.relative(source)
        if operation.action == "make_folder":
            if plan.exists(source):
                if source.is_dir() or plan.key(source) in plan.folders:
                    continue  # already there
                raise FileBatchError(f"{relative} exists and is not a folder")
            for parent in reversed(source.parents):
                if paths.root in parent.parents and not plan.exists(parent):
                    plan.folders.add(plan.key(parent))
                    steps.append(
                        Step("make_folder", paths.relative(parent), None, "folder", "", auto=True)
                    )
            plan.folders.add(plan.key(source))
            steps.append(Step("make_folder", relative, None, "folder", ""))
            continue
        if not plan.exists(source):
            raise FileBatchError(f"{relative} does not exist")
        if plan.key(source) in plan.created or plan.key(source) in plan.folders:
            raise FileBatchError(f"{relative} is made by this batch; change it in a later batch")
        kind: Literal["file", "folder"] = "folder" if source.is_dir() else "file"
        identity = fingerprint(source)
        if operation.action == "recycle":
            plan.vacated.add(plan.key(source))
            steps.append(Step("recycle", relative, None, kind, identity))
            continue
        destination = plan.resolve(operation.to, "to")
        target = paths.relative(destination)
        if destination == source:
            raise FileBatchError(f"{relative}: source and destination are the same")
        if source in destination.parents:
            raise FileBatchError(f"{relative} cannot go inside itself")
        if plan.exists(destination):
            raise FileBatchError(f"{target} already exists; nothing is overwritten")
        for parent in reversed(destination.parents):
            if paths.root in parent.parents and not plan.exists(parent):
                plan.folders.add(plan.key(parent))
                steps.append(
                    Step("make_folder", paths.relative(parent), None, "folder", "", auto=True)
                )
        if operation.action == "copy":
            copied += _size(source)
            if copied > MAX_COPY_BYTES:
                raise FileBatchError("the batch would copy more than 4 GB")
        else:
            plan.vacated.add(plan.key(source))
        plan.created.add(plan.key(destination))
        steps.append(Step(operation.action, relative, target, kind, identity))
    if not steps:
        raise FileBatchError("nothing to change: every folder already exists")
    return steps


def _apply(paths: WorkspacePaths, folder: Path, step: Step, index: int) -> None:
    source = paths.resolve(step.path)
    if step.action == "make_folder":
        source.mkdir()
        return
    if fingerprint(source) != step.fingerprint:
        raise FileBatchError(f"{step.path} changed while the batch ran")
    if step.action == "recycle":
        recycled = folder / "recycled"
        recycled.mkdir(parents=True, exist_ok=True)
        step.to = f"recycled/{index}"
        _relocate(source, folder / step.to)
        return
    assert step.to is not None
    destination = paths.resolve(step.to)
    if destination.exists():
        raise FileBatchError(f"{step.to} appeared while the batch ran; nothing is overwritten")
    if step.action == "move":
        os.rename(source, destination)
        return
    if step.kind == "folder":
        shutil.copytree(source, destination, copy_function=shutil.copy2)
    else:
        shutil.copy2(source, destination)
    step.fingerprint = fingerprint(destination)


def _reverse(paths: WorkspacePaths, folder: Path, step: Step, index: int) -> str | None:
    """Undo one step if the item is as the batch left it; otherwise why not, as a code:
    changed, missing, occupied (something else is at the original place), not_empty or
    recycled_missing (the recycled item is no longer kept)."""
    original = paths.resolve(step.path)
    if step.action == "make_folder":
        if not original.exists():
            return None
        if not original.is_dir() or any(original.iterdir()):
            return "not_empty"
        original.rmdir()
        return None
    if step.action == "recycle":
        assert step.to is not None
        kept = folder / step.to
        if not kept.exists():
            return "recycled_missing"
        if original.exists():
            return "occupied"
        original.parent.mkdir(parents=True, exist_ok=True)
        _relocate(kept, original)
        return None
    assert step.to is not None
    placed = paths.resolve(step.to)
    if not placed.exists():
        return None if step.action == "copy" else "missing"
    if fingerprint(placed) != step.fingerprint:
        return "changed"
    if step.action == "copy":
        # The copy goes to the recycle area too: undoing never deletes anything outright.
        recycled = folder / "recycled"
        recycled.mkdir(parents=True, exist_ok=True)
        _relocate(placed, recycled / f"undo-{index}")
        return None
    if original.exists():
        return "occupied"
    original.parent.mkdir(parents=True, exist_ok=True)
    os.rename(placed, original)
    return None


def run_batch(
    store: FileBatchStore,
    workspace: WorkspacePaths | StrPath,
    operations: list[Operation],
    summary: str,
) -> FileBatch:
    paths = workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
    with store.lock:
        steps = _planned_steps(paths, operations)
        batch = FileBatch(uuid.uuid4().hex, str(paths.root), summary, _now(), "running")
        folder = store.folder(batch.id)
        store.save(batch)
        try:
            for index, step in enumerate(steps):
                _apply(paths, folder, step, index)
                batch.steps.append(step)
                store.save(batch)
        except (OSError, FileBatchError, WorkspacePathError) as error:
            problems = _undo_steps(paths, folder, batch)
            batch.state = "failed" if not problems else "partly_undone"
            batch.problems = problems
            store.save(batch)
            reason = str(error) if isinstance(error, FileBatchError) else type(error).__name__
            detail = (
                "nothing was changed"
                if not problems
                else f"{len(problems)} earlier changes could not be reversed"
            )
            raise FileBatchError(f"The batch stopped ({reason}); {detail}.") from None
        batch.state = "done"
        store.save(batch)
        return batch


def _undo_steps(paths: WorkspacePaths, folder: Path, batch: FileBatch) -> list[dict[str, str]]:
    skipped: list[dict[str, str]] = []
    for index in range(len(batch.steps) - 1, -1, -1):
        step = batch.steps[index]
        if step.undone:
            continue
        try:
            reason = _reverse(paths, folder, step, index)
        except (OSError, FileBatchError, WorkspacePathError):
            reason = "failed"  # locked, too large for another drive, or no longer safe to touch
        if reason is None:
            step.undone = True
        elif not step.auto:
            skipped.append({"path": step.path, "reason": reason})
    return skipped


def undo_batch(store: FileBatchStore, batch_id: str) -> UndoReport:
    with store.lock:
        batch = store.get(batch_id)
        if batch.state == "running":
            batch.state = "interrupted"  # its process ended mid-way
        if batch.state not in UNDOABLE_STATES:
            return UndoReport(batch, 0, [])
        before = sum(not step.undone for step in batch.steps)
        skipped = _undo_steps(WorkspacePaths(batch.workspace), store.folder(batch.id), batch)
        remaining = sum(not step.undone for step in batch.steps if not step.auto)
        batch.state = "undone" if remaining == 0 else "partly_undone"
        batch.problems = skipped
        store.save(batch)
        undone = before - sum(not step.undone for step in batch.steps)
        return UndoReport(batch, undone, skipped)


class OrganizeFilesTool:
    hard_cancellable = False
    _SPEC = ToolSpec(
        name="organize_files",
        description=(
            "Move, rename, copy or remove many workspace files and folders in one call that the "
            "user approves once and can undo from the window. Use it to tidy or reorganize "
            "(sort a folder into subfolders, rename a series of files, clear out old copies) "
            "instead of many move_path or delete_path calls. 'recycle' puts an item in the app's "
            "recycle area, kept for 30 days, rather than deleting it. Destination folders are "
            "made as needed. Nothing is overwritten: an existing destination stops the whole "
            "batch before anything changes. Name every item exactly (no wildcards); list the "
            "folder first. 'summary' is the short title the user sees for the batch."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "operations": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_OPERATIONS,
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": list(ACTIONS)},
                            "path": {"type": "string", "minLength": 1},
                            "to": {"type": "string", "minLength": 1},
                        },
                        "required": ["action", "path"],
                        "additionalProperties": False,
                    },
                },
                "summary": {"type": "string", "maxLength": 200},
            },
            "required": ["operations"],
            "additionalProperties": False,
        },
        side_effect="move",
        capability=Capability.WORKSPACE_MANAGE,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath, store: FileBatchStore) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self.store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        operations, summary = parse_operations(arguments)
        batch = await asyncio.to_thread(run_batch, self.store, self.paths, operations, summary)
        visible = [step for step in batch.steps if not step.auto]
        return json_result(
            {
                "batch_id": batch.id,
                "changes": len(visible),
                "steps": [
                    {"action": step.action, "path": step.path}
                    | ({"to": step.to} if step.action in {"move", "copy"} else {})
                    for step in visible[:_RESULT_STEPS]
                ],
                "note": "The user can undo this batch from the window; recycled items are kept "
                "30 days.",
            }
        )
