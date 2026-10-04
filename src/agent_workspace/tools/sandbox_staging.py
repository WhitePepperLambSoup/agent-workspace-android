from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent_workspace.core.models import BinaryArtifact

from .base import ToolError, json_result
from .paths import WorkspacePaths

_COPY_CHUNK_BYTES = 1024 * 1024
_MAX_ENTRIES = 200_000
_MAX_SOURCE_BYTES = 8 * 1024 * 1024 * 1024
_MAX_FILE_BYTES = 512 * 1024 * 1024
_MAX_CHANGES = 128
_MAX_PATH_CHARS = 512
_MAX_PREVIEW_FILE_BYTES = 64 * 1024
_MAX_PREVIEW_JSON_BYTES = 256 * 1024
_MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
_MAX_ARTIFACT_BATCH_BYTES = 64 * 1024 * 1024
_MAX_STALE_STAGING_ROOTS = 128
_STAGING_NAME_PREFIX = "agent-stage-"


@dataclass(frozen=True, slots=True)
class StagingWorkspace:
    root: str
    workspace: str
    execution_sha256: str
    source_tree_sha256: str
    entries: int
    bytes: int

    def to_document(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "workspace": self.workspace,
            "execution_sha256": self.execution_sha256,
            "source_tree_sha256": self.source_tree_sha256,
            "entries": self.entries,
            "bytes": self.bytes,
        }

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> StagingWorkspace:
        required_strings = ("root", "workspace", "execution_sha256", "source_tree_sha256")
        if any(not isinstance(document.get(name), str) for name in required_strings):
            raise ToolError("staging workspace result is invalid")
        entries = document.get("entries")
        byte_count = document.get("bytes")
        if (
            not isinstance(entries, int)
            or isinstance(entries, bool)
            or entries < 0
            or not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
        ):
            raise ToolError("staging workspace counts are invalid")
        return cls(
            root=document["root"],
            workspace=document["workspace"],
            execution_sha256=document["execution_sha256"],
            source_tree_sha256=document["source_tree_sha256"],
            entries=entries,
            bytes=byte_count,
        )


def staging_root_for_execution(execution_id: str, nonce: str, owner_pid: int) -> Path:
    execution_digest = _identity_digest(execution_id)
    nonce_digest = _identity_digest(nonce)
    return _staging_parent() / (
        f"{_STAGING_NAME_PREFIX}{owner_pid}-{execution_digest[:16]}-{nonce_digest[:16]}"
    )


def staging_creating_root_for_execution(
    staging_root: Path,
    nonce: str,
    owner_pid: int,
) -> Path:
    if staging_root.parent != _staging_parent() or not staging_root.name.startswith(
        _STAGING_NAME_PREFIX
    ):
        raise ToolError("final staging path is not managed")
    return staging_root.parent / (
        f".creating-{staging_root.name}-{owner_pid}-{_identity_digest(nonce)[:16]}"
    )


def create_staging_workspace_sync(
    source_workspace: str,
    staging_root: str,
    execution_id: str,
    owner_pid: int,
    container_user: str | None = None,
    max_staging_bytes: int = _MAX_SOURCE_BYTES,
    minimum_free_space_bytes: int = 1,
    creating_root: str | None = None,
) -> str:
    source = WorkspacePaths(source_workspace)
    _validate_staging_user(container_user)
    root = _validate_requested_staging_root(Path(staging_root), execution_id, owner_pid)
    try:
        root.relative_to(source.root)
    except ValueError:
        pass
    else:
        raise ToolError("sandbox staging root may not be inside the source workspace")
    parent = root.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _assert_private_staging_parent(parent)
    initial_free_space = shutil.disk_usage(parent).free
    if initial_free_space < minimum_free_space_bytes:
        raise ToolError("staging volume has insufficient free space")
    creating = (
        _validate_requested_creating_root(Path(creating_root), root, owner_pid)
        if creating_root is not None
        else staging_creating_root_for_execution(root, uuid4().hex, owner_pid)
    )
    try:
        creating.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise ToolError("staging workspace already exists") from exc
    staged_workspace = creating / "workspace"
    baseline_path = creating / "baseline.json"
    owner_path = creating / "owner.json"
    try:
        staged_workspace.mkdir()
        if os.name != "nt":
            staged_workspace.chmod(0o700)
        owner_path.write_text(
            json.dumps(
                {
                    "execution_sha256": _identity_digest(execution_id),
                    "owner_pid": owner_pid,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        _check_staging_storage(
            owner_path,
            initial_free_space,
            max_staging_bytes,
            minimum_free_space_bytes,
        )
        entries, byte_count = _copy_workspace(
            source,
            staged_workspace,
            initial_free_space=initial_free_space,
            max_staging_bytes=min(max_staging_bytes, _MAX_SOURCE_BYTES),
            minimum_free_space_bytes=minimum_free_space_bytes,
        )
        verified_entries, verified_bytes = _scan_tree(source.root, source)
        if verified_entries != entries or verified_bytes != byte_count:
            raise ToolError("workspace changed while its sandbox staging snapshot was created")
        tree_sha256 = _tree_digest(entries)
        baseline_text = json.dumps(
            {
                "version": 1,
                "execution_sha256": _identity_digest(execution_id),
                "source_workspace": str(source.root),
                "source_tree_sha256": tree_sha256,
                "entries": entries,
                "entry_count": len(entries),
                "bytes": byte_count,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        _check_staging_storage(
            creating,
            initial_free_space,
            max_staging_bytes,
            minimum_free_space_bytes,
        )
        baseline_path.write_text(baseline_text, encoding="utf-8")
        _check_staging_storage(
            baseline_path,
            initial_free_space,
            max_staging_bytes,
            minimum_free_space_bytes,
        )
        result = json_result(
            StagingWorkspace(
                root=str(root),
                workspace=str(root / "workspace"),
                execution_sha256=_identity_digest(execution_id),
                source_tree_sha256=tree_sha256,
                entries=len(entries),
                bytes=byte_count,
            ).to_document()
        )
        os.replace(creating, root)
        return result
    except BaseException:
        _remove_tree(creating)
        raise


def diff_staging_workspace_sync(
    source_workspace: str,
    staging_root: str,
    execution_id: str,
) -> str:
    source = WorkspacePaths(source_workspace)
    root = _validate_existing_staging_root(Path(staging_root), execution_id)
    staged_workspace = root / "workspace"
    baseline = _read_baseline(root / "baseline.json", source, execution_id)
    after_entries, after_bytes = _scan_tree(staged_workspace, source)
    before_entries = baseline["entries"]
    if not isinstance(before_entries, dict):
        raise ToolError("staging baseline entries are invalid")
    changes: list[dict[str, Any]] = []
    preview_bytes = 0
    changed_paths = tuple(
        path
        for path in sorted(set(before_entries) | set(after_entries))
        if before_entries.get(path) != after_entries.get(path)
    )
    for relative in changed_paths[:_MAX_CHANGES]:
        before = before_entries.get(relative)
        after = after_entries.get(relative)
        change = _change_document(relative, before, after)
        preview, consumed = _change_preview(
            source.root,
            staged_workspace,
            relative,
            before,
            after,
            _MAX_PREVIEW_JSON_BYTES - preview_bytes,
        )
        change.update(preview)
        preview_bytes += consumed
        changes.append(change)
    after_tree_sha256 = _tree_digest(after_entries)
    complete = len(changed_paths) <= _MAX_CHANGES
    manifest: dict[str, Any] = {
        "version": 1,
        "mode": "staged",
        "execution_sha256": _identity_digest(execution_id),
        "source_workspace_sha256": _identity_digest(os.path.normcase(str(source.root))),
        "complete": complete,
        "change_limit_exceeded": not complete,
        "change_count": len(changed_paths),
        "retained_change_count": len(changes),
        "preview_json_bytes": preview_bytes,
        "source_tree_sha256": baseline["source_tree_sha256"],
        "staged_tree_sha256": after_tree_sha256,
        "source_entries": baseline["entry_count"],
        "staged_entries": len(after_entries),
        "source_bytes": baseline["bytes"],
        "staged_bytes": after_bytes,
        "changes": changes,
        "limits": {
            "max_changes": _MAX_CHANGES,
            "max_path_chars": _MAX_PATH_CHARS,
            "max_preview_file_bytes": _MAX_PREVIEW_FILE_BYTES,
            "max_preview_json_bytes": _MAX_PREVIEW_JSON_BYTES,
        },
    }
    manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(
            manifest,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return json_result(manifest)


def capture_staging_artifacts_sync(
    staging_root: str,
    execution_id: str,
    expected_files: tuple[tuple[str, int, str], ...],
) -> tuple[BinaryArtifact, ...]:
    root = _validate_existing_staging_root(Path(staging_root), execution_id)
    workspace = root / "workspace"
    artifacts: dict[str, BinaryArtifact] = {}
    total_bytes = 0
    for relative, expected_bytes, expected_sha256 in expected_files:
        _validate_relative_path(relative)
        if (
            type(expected_bytes) is not int
            or not 0 <= expected_bytes <= _MAX_ARTIFACT_BYTES
            or len(expected_sha256) != 64
            or any(character not in "0123456789abcdef" for character in expected_sha256)
        ):
            raise ToolError("sandbox artifact expectation is invalid")
        path = workspace / Path(relative)
        try:
            before = path.lstat()
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_size != expected_bytes
            ):
                raise ToolError(f"staged artifact identity is invalid: {relative}")
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags)
            digest = hashlib.sha256()
            content = bytearray()
            with os.fdopen(descriptor, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                    raise ToolError(f"staged artifact changed during capture: {relative}")
                while chunk := stream.read(_COPY_CHUNK_BYTES):
                    content.extend(chunk)
                    if len(content) > _MAX_ARTIFACT_BYTES:
                        raise ToolError(f"staged artifact exceeds its byte limit: {relative}")
                    digest.update(chunk)
            after = path.stat()
        except ToolError:
            raise
        except OSError as exc:
            raise ToolError(f"cannot capture staged artifact: {relative}") from exc
        if (
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            or len(content) != expected_bytes
            or digest.hexdigest() != expected_sha256
        ):
            raise ToolError(f"staged artifact changed during capture: {relative}")
        total_bytes += len(content)
        if total_bytes > _MAX_ARTIFACT_BATCH_BYTES:
            raise ToolError("sandbox artifacts exceed their aggregate byte limit")
        artifact = BinaryArtifact(expected_sha256, bytes(content))
        existing = artifacts.setdefault(expected_sha256, artifact)
        if existing.content != artifact.content:
            raise ToolError("sandbox artifact digest collision detected")
    return tuple(artifacts[digest] for digest in sorted(artifacts))


def remove_staging_workspace_sync(
    staging_root: str,
    execution_id: str,
    creating_root: str | None = None,
) -> str:
    if creating_root is not None:
        creating = _validate_cleanup_staging_path(Path(creating_root), execution_id)
        _remove_tree(creating)
    root = _validate_existing_staging_root(Path(staging_root), execution_id, require_marker=False)
    _remove_tree(root)
    return json_result({"removed": True, "execution_sha256": _identity_digest(execution_id)})


def set_staging_owner_sync(staging_root: str, execution_id: str, owner_pid: int) -> str:
    if owner_pid <= 0:
        raise ToolError("sandbox staging owner PID is invalid")
    root = _validate_existing_staging_root(Path(staging_root), execution_id)
    owner_path = root / "owner.json"
    temporary = root / f".owner-{uuid4().hex}.tmp"
    try:
        temporary.write_text(
            json.dumps(
                {
                    "execution_sha256": _identity_digest(execution_id),
                    "owner_pid": owner_pid,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, owner_path)
    finally:
        temporary.unlink(missing_ok=True)
    return json_result({"owner_pid": owner_pid})


def recover_stale_staging_workspaces_sync() -> str:
    parent = _staging_parent()
    if not parent.exists():
        return json_result({"recovered": 0, "active": 0})
    _assert_private_staging_parent(parent)
    all_candidates = tuple(
        child
        for child in parent.iterdir()
        if child.name.startswith(_STAGING_NAME_PREFIX)
        or child.name.startswith(f".creating-{_STAGING_NAME_PREFIX}")
        or child.name.startswith(".deleting-")
    )
    candidates = tuple(sorted(all_candidates, key=lambda path: path.name))[
        :_MAX_STALE_STAGING_ROOTS
    ]
    recovered = 0
    active = 0
    invalid = 0
    for candidate in candidates:
        try:
            owner_pid = _staging_candidate_owner_pid(candidate)
        except ToolError:
            invalid += 1
            continue
        if _process_is_alive(owner_pid):
            active += 1
            continue
        _remove_tree(candidate)
        recovered += 1
    return json_result(
        {
            "recovered": recovered,
            "active": active,
            "invalid": invalid,
            "remaining": len(all_candidates) - len(candidates),
        }
    )


def _copy_workspace(
    source: WorkspacePaths,
    destination: Path,
    *,
    initial_free_space: int,
    max_staging_bytes: int,
    minimum_free_space_bytes: int,
) -> tuple[dict[str, dict[str, Any]], int]:
    from .sandbox import _validate_workspace_mount

    _validate_workspace_mount(source.root)
    entries: dict[str, dict[str, Any]] = {}
    total_bytes = 0
    entry_count = 0

    def reject_walk_error(error: OSError) -> None:
        raise ToolError(f"cannot enumerate workspace for sandbox staging: {error}") from error

    for directory, directory_names, file_names in os.walk(
        source.root,
        topdown=True,
        onerror=reject_walk_error,
    ):
        directory_names.sort()
        file_names.sort()
        relative_directory = Path(directory).relative_to(source.root)
        for name in directory_names:
            relative = relative_directory / name
            relative_text = relative.as_posix()
            _validate_relative_path(relative_text)
            (destination / relative).mkdir()
            if os.name != "nt":
                (destination / relative).chmod(0o700)
            _check_staging_storage(
                destination / relative,
                initial_free_space,
                max_staging_bytes,
                minimum_free_space_bytes,
            )
            entries[relative_text] = {"type": "directory"}
            entry_count += 1
            if entry_count > _MAX_ENTRIES:
                raise ToolError("workspace exceeds sandbox staging entry limits")
        for name in file_names:
            relative = relative_directory / name
            relative_text = relative.as_posix()
            _validate_relative_path(relative_text)
            source_path = source.resolve(relative)
            destination_path = destination / relative
            file_size, digest = _copy_regular_file(
                source_path,
                destination_path,
                initial_free_space=initial_free_space,
                max_staging_bytes=max_staging_bytes,
                minimum_free_space_bytes=minimum_free_space_bytes,
            )
            _check_staging_storage(
                destination_path,
                initial_free_space,
                max_staging_bytes,
                minimum_free_space_bytes,
            )
            total_bytes += file_size
            entry_count += 1
            if total_bytes > max_staging_bytes or entry_count > _MAX_ENTRIES:
                raise ToolError("workspace exceeds sandbox staging limits")
            entries[relative_text] = {
                "type": "file",
                "bytes": file_size,
                "sha256": digest,
                "executable": _is_executable(source_path.stat()),
            }
    return entries, total_bytes


def _copy_regular_file(
    source: Path,
    destination: Path,
    *,
    initial_free_space: int,
    max_staging_bytes: int,
    minimum_free_space_bytes: int,
) -> tuple[int, str]:
    try:
        before = source.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > _MAX_FILE_BYTES:
            raise ToolError(f"file exceeds sandbox staging limits: {source}")
        digest = hashlib.sha256()
        copied = 0
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(source, flags)
        with os.fdopen(descriptor, "rb") as input_stream, destination.open("xb") as output_stream:
            opened = os.fstat(input_stream.fileno())
            if (opened.st_dev, opened.st_ino) != (
                before.st_dev,
                before.st_ino,
            ) or opened.st_nlink != 1:
                raise ToolError(f"workspace file changed during staging: {source}")
            while chunk := input_stream.read(_COPY_CHUNK_BYTES):
                copied += len(chunk)
                if copied > _MAX_FILE_BYTES or copied > max_staging_bytes:
                    raise ToolError(f"file grew beyond sandbox staging limits: {source}")
                digest.update(chunk)
                output_stream.write(chunk)
                _check_staging_storage(
                    destination,
                    initial_free_space,
                    max_staging_bytes,
                    minimum_free_space_bytes,
                )
            output_stream.flush()
            _check_staging_storage(
                destination,
                initial_free_space,
                max_staging_bytes,
                minimum_free_space_bytes,
            )
        after = source.stat()
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) or copied != before.st_size:
            raise ToolError(f"workspace file changed during staging: {source}")
        if os.name != "nt":
            destination.chmod(0o600 | (stat.S_IMODE(before.st_mode) & 0o100))
        return copied, digest.hexdigest()
    except ToolError:
        raise
    except OSError as exc:
        raise ToolError(f"cannot copy workspace file into sandbox staging: {source}") from exc


def _scan_tree(
    root: Path,
    source_paths: WorkspacePaths | None = None,
) -> tuple[dict[str, dict[str, Any]], int]:
    entries: dict[str, dict[str, Any]] = {}
    total_bytes = 0
    entry_count = 0
    root_device = root.stat().st_dev

    def reject_walk_error(error: OSError) -> None:
        raise ToolError(f"cannot enumerate staged sandbox output: {error}") from error

    for directory, directory_names, file_names in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=reject_walk_error,
    ):
        directory_names.sort()
        file_names.sort()
        relative_directory = Path(directory).relative_to(root)
        for name in (*directory_names, *file_names):
            path = Path(directory) / name
            relative = (relative_directory / name).as_posix()
            _validate_relative_path(relative)
            if source_paths is not None:
                source_paths._validate_text(relative)
            metadata = path.lstat()
            attributes = getattr(metadata, "st_file_attributes", 0)
            if metadata.st_dev != root_device or path.is_mount():
                raise ToolError(f"staged output contains a nested mount: {relative}")
            if stat.S_ISLNK(metadata.st_mode) or attributes & 0x400:
                raise ToolError(f"staged output contains a link or reparse point: {relative}")
            if stat.S_ISDIR(metadata.st_mode):
                entries[relative] = {"type": "directory"}
            elif stat.S_ISREG(metadata.st_mode):
                if metadata.st_nlink != 1 or metadata.st_size > _MAX_FILE_BYTES:
                    raise ToolError(
                        f"staged output file violates identity or size limits: {relative}"
                    )
                file_size, digest = _hash_regular_file(path, metadata)
                total_bytes += file_size
                entries[relative] = {
                    "type": "file",
                    "bytes": file_size,
                    "sha256": digest,
                    "executable": _is_executable(metadata),
                }
            else:
                raise ToolError(f"staged output contains a special file: {relative}")
            entry_count += 1
            if entry_count > _MAX_ENTRIES or total_bytes > _MAX_SOURCE_BYTES:
                raise ToolError("staged output exceeds manifest limits")
    return entries, total_bytes


def _hash_regular_file(path: Path, expected: os.stat_result) -> tuple[int, str]:
    digest = hashlib.sha256()
    observed = 0
    try:
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
                raise ToolError(f"staged output changed during scan: {path}")
            while chunk := stream.read(_COPY_CHUNK_BYTES):
                observed += len(chunk)
                if observed > _MAX_FILE_BYTES:
                    raise ToolError(f"staged output grew beyond file limits: {path}")
                digest.update(chunk)
        after = path.stat()
    except ToolError:
        raise
    except OSError as exc:
        raise ToolError(f"cannot scan staged output: {path}") from exc
    if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
        expected.st_dev,
        expected.st_ino,
        expected.st_size,
        expected.st_mtime_ns,
    ) or observed != expected.st_size:
        raise ToolError(f"staged output changed during scan: {path}")
    return observed, digest.hexdigest()


def _change_document(
    relative: str,
    before: object,
    after: object,
) -> dict[str, Any]:
    before_entry = before if isinstance(before, dict) else None
    after_entry = after if isinstance(after, dict) else None
    kind = (
        "added"
        if before_entry is None
        else "deleted"
        if after_entry is None
        else "type_changed"
        if before_entry.get("type") != after_entry.get("type")
        else "modified"
    )
    return {
        "path": relative,
        "kind": kind,
        "before_type": before_entry.get("type") if before_entry else None,
        "after_type": after_entry.get("type") if after_entry else None,
        "before_bytes": before_entry.get("bytes") if before_entry else None,
        "after_bytes": after_entry.get("bytes") if after_entry else None,
        "before_sha256": before_entry.get("sha256") if before_entry else None,
        "after_sha256": after_entry.get("sha256") if after_entry else None,
        "before_executable": before_entry.get("executable") if before_entry else None,
        "after_executable": after_entry.get("executable") if after_entry else None,
    }


def _change_preview(
    source_root: Path,
    staged_root: Path,
    relative: str,
    before: object,
    after: object,
    remaining_json_bytes: int,
) -> tuple[dict[str, Any], int]:
    if remaining_json_bytes <= 0:
        return {"preview_truncated": True}, 0
    before_entry = before if isinstance(before, dict) else None
    after_entry = after if isinstance(after, dict) else None
    before_text = _bounded_utf8_file(source_root / relative, before_entry)
    after_text = _bounded_utf8_file(staged_root / relative, after_entry)
    preview: dict[str, Any] = {}
    consumed = 0
    if after_text is not None:
        encoded_size = _json_string_bytes(after_text)
        if encoded_size <= remaining_json_bytes:
            preview["after_text"] = after_text
            consumed += encoded_size
            remaining_json_bytes -= encoded_size
        else:
            preview["preview_truncated"] = True
    if before_text is not None or after_text is not None:
        patch = "".join(
            difflib.unified_diff(
                (before_text or "").splitlines(keepends=True),
                (after_text or "").splitlines(keepends=True),
                fromfile=f"a/{relative}",
                tofile=f"b/{relative}",
            )
        )
        patch_size = _json_string_bytes(patch)
        if patch and patch_size <= remaining_json_bytes:
            preview["patch"] = patch
            consumed += patch_size
        elif patch:
            preview["preview_truncated"] = True
    return preview, consumed


def _bounded_utf8_file(path: Path, entry: dict[str, Any] | None) -> str | None:
    if entry is None or entry.get("type") != "file":
        return None
    size = entry.get("bytes")
    digest = entry.get("sha256")
    if not isinstance(size, int) or size > _MAX_PREVIEW_FILE_BYTES or not isinstance(digest, str):
        return None
    try:
        content = path.read_bytes()
    except OSError:
        return None
    if len(content) != size or hashlib.sha256(content).hexdigest() != digest or b"\x00" in content:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _read_baseline(path: Path, source: WorkspacePaths, execution_id: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError("cannot read sandbox staging baseline") from exc
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("execution_sha256") != _identity_digest(execution_id)
        or document.get("source_workspace") != str(source.root)
        or not isinstance(document.get("source_tree_sha256"), str)
        or not isinstance(document.get("entry_count"), int)
        or not isinstance(document.get("bytes"), int)
    ):
        raise ToolError("sandbox staging baseline identity is invalid")
    entries = document.get("entries")
    if (
        not isinstance(entries, dict)
        or len(entries) != document["entry_count"]
        or _tree_digest(entries) != document["source_tree_sha256"]
    ):
        raise ToolError("sandbox staging baseline manifest is invalid")
    return document


def _tree_digest(entries: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(entries):
        encoded = json.dumps(
            [relative, entries[relative]],
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _staging_parent() -> Path:
    return Path(tempfile.gettempdir()).resolve() / "agent-workspace-sandbox-staging"


def _validate_requested_staging_root(root: Path, execution_id: str, owner_pid: int) -> Path:
    resolved_parent = _staging_parent()
    absolute = Path(os.path.abspath(root))
    expected_prefix = f"{_STAGING_NAME_PREFIX}{owner_pid}-{_identity_digest(execution_id)[:16]}-"
    if absolute.parent != resolved_parent or not absolute.name.startswith(expected_prefix):
        raise ToolError("sandbox staging path identity is invalid")
    return absolute


def _validate_requested_creating_root(
    creating: Path,
    staging_root: Path,
    owner_pid: int,
) -> Path:
    absolute = Path(os.path.abspath(creating))
    expected_prefix = f".creating-{staging_root.name}-{owner_pid}-"
    if absolute.parent != _staging_parent() or not absolute.name.startswith(expected_prefix):
        raise ToolError("sandbox creating path identity is invalid")
    return absolute


def _validate_cleanup_staging_path(path: Path, execution_id: str) -> Path:
    absolute = Path(os.path.abspath(path))
    if absolute.parent != _staging_parent():
        raise ToolError("sandbox cleanup path is outside its managed root")
    execution_fragment = f"-{_identity_digest(execution_id)[:16]}-"
    if execution_fragment not in absolute.name or not absolute.name.startswith(
        (_STAGING_NAME_PREFIX, f".creating-{_STAGING_NAME_PREFIX}")
    ):
        raise ToolError("sandbox cleanup path does not match execution")
    return absolute


def _validate_existing_staging_root(
    root: Path,
    execution_id: str,
    *,
    require_marker: bool = True,
) -> Path:
    absolute = Path(os.path.abspath(root))
    parent = _staging_parent()
    if absolute.parent != parent or not absolute.name.startswith(_STAGING_NAME_PREFIX):
        raise ToolError("sandbox staging path is outside its managed root")
    if f"-{_identity_digest(execution_id)[:16]}-" not in absolute.name:
        raise ToolError("sandbox staging path does not match execution")
    _assert_private_staging_parent(parent)
    if absolute.exists():
        _assert_plain_directory(absolute)
    if require_marker:
        try:
            owner = json.loads((absolute / "owner.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ToolError("sandbox staging owner identity is unavailable") from exc
        if not isinstance(owner, dict) or owner.get("execution_sha256") != _identity_digest(
            execution_id
        ):
            raise ToolError("sandbox staging owner identity does not match execution")
    return absolute


def _assert_plain_directory(path: Path) -> None:
    metadata = path.lstat()
    attributes = getattr(metadata, "st_file_attributes", 0)
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or attributes & 0x400:
        raise ToolError("sandbox staging parent is not a plain directory")


def _assert_private_staging_parent(path: Path) -> None:
    _assert_plain_directory(path)
    if os.name == "nt":
        return
    platform_os: Any = os
    metadata = path.stat()
    if metadata.st_uid != platform_os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ToolError("sandbox staging parent must be owned by the current user with mode 0700")


def _read_staging_owner(root: Path) -> int:
    _assert_plain_directory(root)
    try:
        owner = json.loads((root / "owner.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError("sandbox staging directory has no valid owner marker") from exc
    if not isinstance(owner, dict):
        raise ToolError("sandbox staging directory has no valid owner marker")
    raw_pid = owner.get("owner_pid")
    execution_sha256 = owner.get("execution_sha256")
    if (
        not isinstance(raw_pid, int)
        or isinstance(raw_pid, bool)
        or raw_pid <= 0
        or not isinstance(execution_sha256, str)
        or f"-{execution_sha256[:16]}-" not in root.name
    ):
        raise ToolError("sandbox staging directory has an invalid owner identity")
    return raw_pid


def _staging_candidate_owner_pid(root: Path) -> int:
    if root.name.startswith(".deleting-"):
        name = root.name
    elif (root / "owner.json").is_file():
        return _read_staging_owner(root)
    else:
        name = root.name
        if name.startswith(".creating-"):
            name = name.removeprefix(".creating-")
    if name.startswith(_STAGING_NAME_PREFIX):
        raw_pid = name.removeprefix(_STAGING_NAME_PREFIX).split("-", maxsplit=1)[0]
    elif name.startswith(".deleting-"):
        raw_pid = name.removeprefix(".deleting-").split("-", maxsplit=1)[0]
    else:
        raise ToolError("sandbox staging directory name is invalid")
    try:
        owner_pid = int(raw_pid)
    except ValueError as exc:
        raise ToolError("sandbox staging directory name has an invalid owner PID") from exc
    if owner_pid <= 0:
        raise ToolError("sandbox staging directory name has an invalid owner PID")
    return owner_pid


def _process_is_alive(process_id: int) -> bool:
    from .sandbox import _process_is_alive as sandbox_process_is_alive

    return sandbox_process_is_alive(process_id)


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return
    parent = _staging_parent()
    if Path(os.path.abspath(path)).parent != parent:
        raise ToolError("refusing to remove a directory outside sandbox staging")
    _assert_private_staging_parent(parent)
    quarantine = parent / f".deleting-{os.getpid()}-{uuid4().hex}"
    try:
        os.replace(path, quarantine)
        metadata = quarantine.lstat()
        attributes = getattr(metadata, "st_file_attributes", 0)
        if stat.S_ISLNK(metadata.st_mode) or attributes & 0x400:
            if quarantine.is_dir():
                os.rmdir(quarantine)
            else:
                quarantine.unlink()
        else:
            _assert_plain_directory(quarantine)
            shutil.rmtree(quarantine)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ToolError(f"cannot remove sandbox staging workspace: {quarantine}") from exc


def _validate_relative_path(relative: str) -> None:
    if (
        not relative
        or len(relative) > _MAX_PATH_CHARS
        or "\x00" in relative
        or any(ord(character) < 32 for character in relative)
    ):
        raise ToolError("workspace path exceeds sandbox staging limits")
    if (
        "\\" in relative
        or relative.startswith("/")
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    ):
        raise ToolError("workspace path escapes sandbox staging")


def _identity_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_string_bytes(value: str) -> int:
    return len(json.dumps(value, ensure_ascii=True).encode("utf-8"))


def _validate_staging_user(container_user: str | None) -> None:
    if os.name == "nt" or container_user is None:
        return
    platform_os: Any = os
    expected = f"{platform_os.getuid()}:{platform_os.getgid()}"
    if container_user != expected:
        raise ToolError("POSIX staged sandbox user must match the current host UID:GID")


def _check_staging_storage(
    path: Path,
    initial_free_space: int,
    max_staging_bytes: int,
    minimum_free_space_bytes: int,
) -> None:
    current_free_space = shutil.disk_usage(path.parent).free
    if (
        current_free_space < minimum_free_space_bytes
        or initial_free_space - current_free_space > max_staging_bytes
    ):
        raise ToolError("sandbox staging copy exceeded its storage limits")


def _is_executable(metadata: os.stat_result) -> bool:
    return os.name != "nt" and bool(stat.S_IMODE(metadata.st_mode) & 0o111)
