"""File history: earlier versions of workspace files, so a change can be undone.

Before the agent writes, appends to, patches, replaces, downloads over, deletes or moves something
onto a workspace file, and before the user saves or deletes one on the Files page, the content it
had is kept in <data>/file-history (stored once per content, by SHA-256). The Files page lists the
versions of a file, or every recent change of a workspace, shows a text version and puts one back;
putting one back keeps the content it replaces too, so that is undoable as well.

Kept: files up to 10 MiB, the latest 30 versions of each file, for 30 days, 300 MiB in all (the
oldest go first). Files under the workspace's internal folders are not kept.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from agent_workspace.tools.paths import WorkspacePaths, is_sensitive_workspace_path

_LOCK = threading.Lock()
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 300 * 1024 * 1024
MAX_VERSIONS_PER_FILE = 30
KEEP_SECONDS = 30 * 24 * 3600
MAX_PREVIEW_BYTES = 512 * 1024
# Files a deleted folder held that are kept at most.
MAX_FOLDER_FILES = 200
_INTERNAL = (".git", ".venv", "venv", "node_modules", "__pycache__", ".agent", ".agent-workspace", ".agent_workspace")
# The argument of each tool that names the file it is about to change.
CHANGING_TOOLS = {
    "write_file": ("path",), "append_file": ("path",), "apply_patch": ("path",), "copy_file": ("path",),
    "create_docx": ("path",), "create_xlsx": ("path",), "create_pdf": ("path",), "download_file": ("path",),
    "delete_path": ("path",), "move_path": ("destination",),
}  # fmt: skip


def _root() -> Path | None:
    data = os.getenv("AGENT_WORKSPACE_DATA_DIR")
    return Path(data) / "file-history" if data else None


def _load(root: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads((root / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _save(root: Path, entries: list[dict[str, Any]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / "index.json.tmp"
    temporary.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, root / "index.json")


def _prune(root: Path, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = time.time()
    entries = [entry for entry in entries if now - entry.get("at", 0) / 1000 < KEEP_SECONDS]
    # The newest versions of each file.
    seen: dict[tuple[str, str], int] = {}
    kept = []
    for entry in sorted(entries, key=lambda item: item.get("at", 0), reverse=True):
        key = (entry.get("workspace", ""), entry.get("path", ""))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] <= MAX_VERSIONS_PER_FILE:
            kept.append(entry)
    # Within the total, newest first (content shared by versions counts once).
    total, sized, counted = 0, [], set()
    for entry in kept:
        digest = entry.get("sha256")
        size = 0 if digest in counted else int(entry.get("size") or 0)
        if total + size > MAX_TOTAL_BYTES:
            continue
        total += size
        counted.add(digest)
        sized.append(entry)
    sized.reverse()
    used = {entry.get("sha256") for entry in sized}
    objects = root / "objects"
    if objects.is_dir():
        for stored in objects.iterdir():
            if stored.name not in used:
                stored.unlink(missing_ok=True)
    return sized


def _relative(paths: WorkspacePaths, raw: Any) -> tuple[Path, str] | None:
    """The workspace file a tool argument names, or None when it is not one to keep."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        target = paths.resolve(raw)
        relative = paths.relative(target)
    except Exception:  # outside the workspace, or not a path at all
        return None
    parts = PurePosixPath(relative).parts
    if not parts or parts[0] in _INTERNAL or any(part.startswith(".agent") for part in parts):
        return None
    if is_sensitive_workspace_path(relative):
        return None
    return target, relative


def _keep(root: Path, entries: list[dict[str, Any]], workspace: str, relative: str, target: Path,
          source: str, task_id: str | None) -> dict[str, Any] | None:
    try:
        if not target.is_file() or target.is_symlink():
            return None
        size = target.stat().st_size
        if size > MAX_FILE_BYTES:
            return None
        content = target.read_bytes()
    except OSError:
        return None
    digest = hashlib.sha256(content).hexdigest()
    latest = next((entry for entry in reversed(entries)
                   if entry.get("workspace") == workspace and entry.get("path") == relative), None)  # fmt: skip
    if latest is not None and latest.get("sha256") == digest:
        return None
    stored = root / "objects" / digest
    if not stored.exists():
        stored.parent.mkdir(parents=True, exist_ok=True)
        partial = stored.with_suffix(".partial")
        partial.write_bytes(content)
        os.replace(partial, stored)
    entry = {"id": uuid.uuid4().hex[:16], "workspace": workspace, "path": relative, "sha256": digest,
             "size": size, "at": int(time.time() * 1000), "source": source, "task_id": task_id}  # fmt: skip
    entries.append(entry)
    return entry


def remember(workspace: str | Path, raw_path: Any, source: str, task_id: str | None = None) -> int:
    """Keep the content [raw_path] has now (a folder: the files in it). Returns how many were kept."""
    root = _root()
    if root is None:
        return 0
    paths = WorkspacePaths(workspace)
    found = _relative(paths, raw_path)
    if found is None:
        return 0
    target, relative = found
    workspace_key = str(paths.root)
    with _LOCK:
        entries = _load(root)
        kept = 0
        if target.is_dir() and not target.is_symlink():
            for count, file in enumerate(path for path in target.rglob("*") if path.is_file()):
                if count >= MAX_FOLDER_FILES:
                    break
                inner = _relative(paths, paths.relative(file))
                if inner is not None and _keep(root, entries, workspace_key, inner[1], inner[0], source, task_id):
                    kept += 1
        elif _keep(root, entries, workspace_key, relative, target, source, task_id):
            kept = 1
        if kept:
            _save(root, _prune(root, entries))
        return kept


def before_tool(workspace: str | Path, tool: str, arguments: Any, task_id: str | None = None) -> int:
    """Called before a tool runs: keeps the files it is about to change."""
    names = CHANGING_TOOLS.get(tool)
    if not names or not isinstance(arguments, dict):
        return 0
    return sum(remember(workspace, arguments.get(name), tool, task_id) for name in names)


def versions(workspace: str | Path, raw_path: Any = None, limit: int = 200) -> dict[str, Any]:
    """Kept versions, newest first: of one file, or every recent change in the workspace."""
    root = _root()
    paths = WorkspacePaths(workspace)
    relative = None
    if raw_path not in (None, ""):
        found = _relative(paths, raw_path)
        if found is None:
            raise ValueError("path is not a workspace file whose history is kept")
        relative = found[1]
    with _LOCK:
        entries = _load(root) if root is not None else []
    workspace_key = str(paths.root)
    chosen = [entry for entry in entries if entry.get("workspace") == workspace_key
              and (relative is None or entry.get("path") == relative)]  # fmt: skip
    chosen.sort(key=lambda entry: entry.get("at", 0), reverse=True)
    result = []
    for entry in chosen[:limit]:
        current = paths.root / entry["path"]
        result.append({key: entry.get(key) for key in ("id", "path", "sha256", "size", "at", "source", "task_id")}
                      | {"exists": current.is_file()})  # fmt: skip
    current_sha = None
    if relative is not None:
        target = paths.root / relative
        if target.is_file() and target.stat().st_size <= MAX_FILE_BYTES:
            current_sha = hashlib.sha256(target.read_bytes()).hexdigest()
    return {"versions": result, "path": relative, "current_sha256": current_sha}


def _entry(workspace: str | Path, version_id: Any) -> dict[str, Any]:
    root = _root()
    if root is None or not isinstance(version_id, str):
        raise KeyError(version_id)
    workspace_key = str(WorkspacePaths(workspace).root)
    with _LOCK:
        entries = _load(root)
    entry = next((item for item in entries if item.get("id") == version_id and item.get("workspace") == workspace_key), None)
    if entry is None:
        raise KeyError(version_id)
    return entry


def content(workspace: str | Path, version_id: Any) -> dict[str, Any]:
    """A kept version for preview: its text when it is UTF-8 text of a readable size."""
    entry = _entry(workspace, version_id)
    data = (_root() / "objects" / entry["sha256"]).read_bytes()
    text = None
    if len(data) <= MAX_PREVIEW_BYTES and b"\x00" not in data:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = None
    return {"id": entry["id"], "path": entry["path"], "size": len(data), "text": text, "at": entry["at"]}


def restore(workspace: str | Path, version_id: Any) -> dict[str, Any]:
    """Put a kept version back. What the file holds now is kept first, so this can be undone."""
    entry = _entry(workspace, version_id)
    paths = WorkspacePaths(workspace)
    found = _relative(paths, entry["path"])
    if found is None:
        raise ValueError("this file can no longer be restored here")
    target, relative = found
    data = (_root() / "objects" / entry["sha256"]).read_bytes()
    if target.is_dir():
        raise ValueError("a folder now has this name")
    remember(workspace, relative, "restore")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.restoring")
    partial.write_bytes(data)
    os.replace(partial, target)
    return {"path": relative, "sha256": entry["sha256"], "size": len(data)}
