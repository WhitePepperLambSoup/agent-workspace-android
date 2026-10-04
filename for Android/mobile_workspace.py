"""Bounded workspace files and desktop-compatible session presentation."""

from __future__ import annotations

import codecs
import errno
import hashlib
import json
import mimetypes
import os
import re
import shutil
import stat
from collections.abc import Mapping
from contextlib import contextmanager, suppress
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO
from uuid import uuid4

from agent_workspace.storage.durable import fsync_directory
from agent_workspace.tools.base import ConcurrentModificationError, ToolError
from agent_workspace.tools.filesystem import (
    _open_identity_checked,
    _scan_file,
    atomic_write,
    expected_sha256,
)
from agent_workspace.tools.paths import (
    WorkspacePaths,
    is_sensitive_workspace_path,
)

_MAX_PREVIEW_BYTES = 512 * 1024
_MAX_HASH_BYTES = 16 * 1024 * 1024
_MAX_DIRECTORY_ITEMS = 500
_MAX_DIRECTORY_SCAN = 10_000
_MAX_PRESENTATION_BYTES = 256 * 1024
_INTERNAL_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".agent",
        ".agent-workspace",
        ".agent_workspace",
        ".agent-upload-request",
    }
)


class WorkspaceContentTooLargeError(ValueError):
    pass


class WorkspaceStorageFullError(OSError):
    pass


def workspace_upload_filename(value: Any) -> str:
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 180
        or len(value.encode("utf-8")) > 255
        or PureWindowsPath(value).name != value
        or value in {".", ".."}
        or value.endswith((" ", "."))
        or any(
            ord(character) < 32 or ord(character) == 127 or character in '<>:"/\\|?*'
            for character in value
        )
        or value.split(".", 1)[0].upper() in reserved
    ):
        raise ValueError("filename must be a safe file name without a path")
    return value


def workspace_upload_media_type(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError("media_type must be a MIME type string")
    normalized = value.split(";", 1)[0].strip().lower()
    if not re.fullmatch(r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+", normalized):
        raise ValueError("media_type must be a MIME type string")
    return normalized


def import_workspace_upload(
    runtime: Any,
    filename: Any,
    source: BinaryIO,
    *,
    content_length: int | None = None,
    media_type: Any = None,
    upload_identifier: str | None = None,
    request_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Stream into an unpublished private directory, then publish without replacing files."""
    from mobile_images import attachment_media_type

    name = workspace_upload_filename(filename)
    declared = workspace_upload_media_type(media_type)
    if content_length is not None and (type(content_length) is not int or content_length < 0):
        raise ValueError("invalid Content-Length")
    paths = WorkspacePaths(runtime_workspace(runtime))
    if content_length is not None and shutil.disk_usage(paths.root).free < content_length:
        raise WorkspaceStorageFullError("not enough available workspace storage for this file")
    uploads = paths.resolve("uploads")
    _assert_public_runtime_path(runtime, uploads)
    uploads.mkdir(exist_ok=True)
    identifier = upload_identifier or uuid4().hex
    if not re.fullmatch(r"[0-9a-f]{32}", identifier):
        raise ValueError("upload_identifier must be a 32-character lowercase hex identifier")
    private_identifier = uuid4().hex if upload_identifier is not None else identifier
    private = paths.resolve(f"uploads/.incoming-{private_identifier}")
    private.mkdir()
    incoming = private / name
    destination = paths.resolve(f"uploads/{identifier}")
    published = False
    size = 0
    digest = hashlib.sha256()
    prefix = bytearray()
    receipt_path: Path | None = None
    receipt_digest: str | None = None
    try:
        with paths.resolve(incoming).open("xb") as output:
            paths.assert_safe_file_descriptor(output.fileno(), incoming)
            paths.resolve(incoming)
            remaining = content_length
            while remaining is None or remaining:
                chunk = source.read(64 * 1024 if remaining is None else min(64 * 1024, remaining))
                if not chunk:
                    if remaining:
                        raise ValueError("incomplete upload body")
                    break
                if len(chunk) > 64 * 1024 or (remaining is not None and len(chunk) > remaining):
                    raise ValueError("upload stream exceeded its declared length")
                if shutil.disk_usage(paths.root).free < len(chunk):
                    raise WorkspaceStorageFullError(
                        "not enough available workspace storage for this file"
                    )
                output.write(chunk)
                digest.update(chunk)
                size += len(chunk)
                if len(prefix) < 2048:
                    prefix.extend(chunk[: 2048 - len(prefix)])
                if remaining is not None:
                    remaining -= len(chunk)
            detected = attachment_media_type(
                bytes(prefix), filename=name, declared_media_type=declared
            )
            resolved_media = (
                detected if detected.startswith("image/") else declared or workspace_mime_type(name)
            )
            output.flush()
            os.fsync(output.fileno())
            paths.assert_safe_file_descriptor(output.fileno(), incoming)
        paths.resolve(incoming)
        paths.resolve(destination)
        if destination.exists():
            raise ConcurrentModificationError("upload destination already exists")
        attachment = {
            "name": name,
            "path": f"uploads/{identifier}/{name}",
            "size": size,
            "sha256": digest.hexdigest(),
            "media_type": resolved_media,
        }
        if request_metadata is not None:
            directory = paths.resolve(private / ".agent-upload-request")
            directory.mkdir()
            receipt_path = paths.resolve(directory / "receipt.json")
            encoded = json.dumps(
                {**request_metadata, **attachment}, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            if len(encoded) > 64 * 1024:
                raise ValueError("upload receipt is too large")
            _, receipt_digest = atomic_write(paths, receipt_path, encoded, None)
            fsync_directory(paths.resolve(private))
        # Renaming the containing directory cannot replace an existing file or nonempty directory.
        os.rename(private, destination)
        paths.resolve(destination / name)
        published = True
        fsync_directory(paths.resolve(uploads))
        return attachment
    except OSError as error:
        if error.errno in {errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)}:
            raise WorkspaceStorageFullError(
                "not enough available workspace storage for this file"
            ) from error
        raise
    finally:
        if not published:
            with suppress(OSError, ValueError, ToolError):
                paths.resolve(incoming).unlink(missing_ok=True)
                if receipt_path is not None:
                    actual, _ = _scan_file(receipt_path, max_scan_bytes=64 * 1024)
                    if actual == receipt_digest:
                        paths.resolve(receipt_path).unlink(missing_ok=True)
                        paths.resolve(receipt_path.parent).rmdir()
                paths.resolve(private).rmdir()


def runtime_workspace(runtime: Any) -> Path:
    workspace = getattr(runtime.service, "_execution_workspace", None)
    if workspace is None:
        raise ValueError("runtime workspace is not configured")
    return WorkspacePaths(workspace).root


def _relative_path(value: Any, *, allow_root: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError("path must be a relative workspace path")
    if allow_root and value in {"", "."}:
        return ""
    pure = PurePosixPath(value)
    if (
        not value
        or len(value) > 2048
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or pure.is_absolute()
        or pure.as_posix() != value
        or any(
            part in {".", ".."} or part.casefold() in _INTERNAL_DIRECTORIES for part in pure.parts
        )
        or is_sensitive_workspace_path(value)
    ):
        raise ValueError("path must be a relative workspace path outside internal directories")
    return value


def list_workspace_files(runtime: Any, raw_path: Any = "") -> dict[str, Any]:
    relative = _relative_path(raw_path, allow_root=True)
    paths = WorkspacePaths(runtime_workspace(runtime))
    target = paths.resolve(relative or ".")
    _assert_public_runtime_path(runtime, target)
    if not target.is_dir():
        raise FileNotFoundError(relative)
    files: list[dict[str, Any]] = []
    scanned = 0
    truncated = False
    with os.scandir(target) as entries:
        for entry in entries:
            scanned += 1
            if scanned > _MAX_DIRECTORY_SCAN:
                truncated = True
                break
            if entry.name.casefold() in _INTERNAL_DIRECTORIES:
                continue
            try:
                child = paths.resolve(Path(entry.path))
                _assert_public_runtime_path(runtime, child)
                metadata = child.lstat()
            except (OSError, ValueError):
                continue
            if not stat.S_ISDIR(metadata.st_mode) and not stat.S_ISREG(metadata.st_mode):
                continue
            if len(files) == _MAX_DIRECTORY_ITEMS:
                truncated = True
                break
            directory = stat.S_ISDIR(metadata.st_mode)
            files.append(
                {
                    "path": paths.relative(child),
                    "name": child.name,
                    "type": "directory" if directory else "file",
                    "size": 0 if directory else metadata.st_size,
                }
            )
    files.sort(key=lambda item: (item["type"] != "directory", item["name"].casefold()))
    parent = PurePosixPath(relative).parent.as_posix() if relative else None
    if parent == ".":
        parent = ""
    return {
        "path": relative,
        "parent": parent,
        "files": files,
        "truncated": truncated,
    }


def _file_document(paths: WorkspacePaths, target: Path) -> dict[str, Any]:
    metadata = target.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise FileNotFoundError(paths.relative(target))
    size = metadata.st_size
    sha256: str | None
    if size <= _MAX_HASH_BYTES:
        sha256, raw = _scan_file(
            target, max_scan_bytes=_MAX_HASH_BYTES, retain_limit=_MAX_HASH_BYTES
        )
        if raw is None:
            raise FileNotFoundError(paths.relative(target))
        size = len(raw)
        try:
            raw.decode("utf-8")
            is_binary = b"\x00" in raw
        except UnicodeDecodeError:
            is_binary = True
    else:
        with _open_identity_checked(target, "rb") as stream:
            size = WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), target).st_size
            raw = stream.read(_MAX_PREVIEW_BYTES + 4)
        sha256 = None
        try:
            codecs.getincrementaldecoder("utf-8")().decode(raw, final=False)
            is_binary = b"\x00" in raw
        except UnicodeDecodeError:
            is_binary = True
    truncated = size > _MAX_PREVIEW_BYTES
    content = ""
    if not is_binary:
        content = codecs.getincrementaldecoder("utf-8")().decode(
            raw[:_MAX_PREVIEW_BYTES], final=not truncated
        )
    return {
        "path": paths.relative(target),
        "content": content,
        "sha256": sha256,
        "size": size,
        "is_binary": is_binary,
        "truncated": truncated,
        "editable": not is_binary and not truncated and sha256 is not None,
    }


def _download_sha256(value: Any) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in value)
    ):
        raise ValueError("sha256 must be a SHA-256 hex digest")
    return value.lower()


def workspace_mime_type(path: str) -> str:
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def runtime_private_paths(runtime: Any) -> tuple[Path, ...]:
    database = getattr(runtime, "database", None)
    if database is None:
        return ()
    database = Path(database).absolute()
    management = database.with_name("mobile-management.db")
    return (
        database,
        Path(str(database) + "-wal"),
        Path(str(database) + "-shm"),
        Path(str(database) + "-journal"),
        database.with_name(f"{database.stem}.session-presentation-v1.json"),
        database.with_name("mobile-extensions.json"),
        management,
        Path(str(management) + "-wal"),
        Path(str(management) + "-shm"),
        Path(str(management) + "-journal"),
        database.with_name("mobile-schedules.json"),
        database.with_name("mobile-workspaces-v1.json"),
        database.with_name("local-models"),
        database.with_name("native-model-imports"),
    )


def _assert_public_runtime_path(runtime: Any, target: Path) -> None:
    if any(
        target == private or private in target.parents for private in runtime_private_paths(runtime)
    ):
        raise ValueError("path identifies internal runtime data")


@contextmanager
def open_workspace_download(runtime: Any, raw_path: Any, raw_sha256: Any = None):
    relative = _relative_path(raw_path)
    expected = _download_sha256(raw_sha256)
    paths = WorkspacePaths(runtime_workspace(runtime))
    target = paths.resolve(relative)
    _assert_public_runtime_path(runtime, target)
    if not stat.S_ISREG(target.lstat().st_mode):
        raise FileNotFoundError(relative)
    with _open_identity_checked(target, "rb") as stream:
        paths.resolve(relative)
        metadata = WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), target)
        if not stat.S_ISREG(metadata.st_mode):
            raise FileNotFoundError(relative)
        if expected is not None:
            digest = hashlib.sha256()
            remaining = metadata.st_size
            while remaining:
                chunk = stream.read(min(remaining, 64 * 1024))
                if not chunk:
                    break
                digest.update(chunk)
                remaining -= len(chunk)
            current = WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), target)
            if digest.hexdigest() != expected or (
                metadata.st_size,
                metadata.st_mtime_ns,
                metadata.st_ctime_ns,
            ) != (current.st_size, current.st_mtime_ns, current.st_ctime_ns):
                raise ConcurrentModificationError("file changed since the task completed")
            stream.seek(0)
        yield (
            stream,
            {
                "path": relative,
                "name": target.name,
                "size": metadata.st_size,
                "mime_type": workspace_mime_type(relative),
            },
        )


def read_workspace_file(runtime: Any, raw_path: Any, raw_sha256: Any = None) -> dict[str, Any]:
    relative = _relative_path(raw_path)
    expected = _download_sha256(raw_sha256)
    paths = WorkspacePaths(runtime_workspace(runtime))
    target = paths.resolve(relative)
    _assert_public_runtime_path(runtime, target)
    document = _file_document(paths, target)
    if expected is not None and document["sha256"] != expected:
        raise ConcurrentModificationError("file changed since the task completed")
    return document


def write_workspace_file(runtime: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    relative = _relative_path(payload.get("path"))
    content = payload.get("content")
    if not isinstance(content, str) or "\x00" in content:
        raise ValueError("content must be UTF-8 text without NUL characters")
    encoded = content.encode("utf-8")
    if len(encoded) > _MAX_PREVIEW_BYTES:
        raise WorkspaceContentTooLargeError("text exceeds the 512 KiB edit limit")
    expected = expected_sha256(dict(payload))
    paths = WorkspacePaths(runtime_workspace(runtime))
    target = paths.resolve(relative)
    _assert_public_runtime_path(runtime, target)
    if target.exists():
        current = _file_document(paths, target)
        if not current["editable"]:
            raise ValueError("binary or truncated files cannot be edited")
        if current["sha256"] != expected:
            raise ConcurrentModificationError("file changed since it was opened")
    elif expected is not None:
        raise ConcurrentModificationError("file was deleted since it was opened")
    target, digest = atomic_write(paths, target, encoded, expected)
    return {"path": paths.relative(target), "sha256": digest, "size": len(encoded)}


def _presentation_path(runtime: Any) -> Path:
    database = getattr(runtime, "database", None)
    if database is None:
        raise OSError("runtime database is not configured")
    database = Path(database)
    return database.with_name(f"{database.stem}.session-presentation-v1.json")


def _read_presentation(runtime: Any) -> tuple[Path, dict[str, Any], str | None]:
    path = _presentation_path(runtime)
    paths = WorkspacePaths(path.parent)
    path = paths.resolve(path)
    try:
        digest, raw = _scan_file(
            path, max_scan_bytes=_MAX_PRESENTATION_BYTES, retain_limit=_MAX_PRESENTATION_BYTES
        )
        if raw is None:
            return path, {"version": 1, "records": {}}, None
        document = json.loads(raw.decode("utf-8"))
    except (ToolError, UnicodeError, json.JSONDecodeError) as exc:
        raise OSError("session presentation cannot be read") from exc
    if (
        not isinstance(document, dict)
        or type(document.get("version")) is not int
        or document["version"] != 1
        or not isinstance(document.get("records"), dict)
    ):
        raise OSError("session presentation is invalid")
    return path, document, digest


def session_aliases(runtime: Any) -> dict[str, str]:
    try:
        _, document, _ = _read_presentation(runtime)
        prefix = hashlib.sha256(str(runtime_workspace(runtime)).encode()).hexdigest() + ":"
    except (OSError, ValueError):
        return {}
    result: dict[str, str] = {}
    for key, record in document["records"].items():
        if not isinstance(key, str) or not key.startswith(prefix) or not isinstance(record, dict):
            continue
        session_id = record.get("sessionId")
        alias = record.get("alias")
        if (
            isinstance(session_id, str)
            and key == prefix + session_id
            and isinstance(alias, str)
            and alias.strip()
            and len(alias) <= 200
        ):
            result[session_id] = alias
    return result


def archived_sessions(runtime: Any) -> set[str]:
    """Sessions the user archived; their history stays in the event store."""
    try:
        _, document, _ = _read_presentation(runtime)
        prefix = hashlib.sha256(str(runtime_workspace(runtime)).encode()).hexdigest() + ":"
    except (OSError, ValueError):
        return set()
    return {
        record["sessionId"]
        for key, record in document["records"].items()
        if isinstance(key, str)
        and isinstance(record, dict)
        and isinstance(record.get("sessionId"), str)
        and key == prefix + record["sessionId"]
        and record.get("archived") is True
    }


def save_session_alias(runtime: Any, session_id: str, title: str) -> dict[str, Any]:
    return _save_presentation_record(runtime, session_id, alias=title)


def save_session_archived(runtime: Any, session_id: str, archived: bool) -> dict[str, Any]:
    return _save_presentation_record(runtime, session_id, archived=archived)


def _save_presentation_record(
    runtime: Any, session_id: str, *, alias: str | None = None, archived: bool | None = None
) -> dict[str, Any]:
    path, document, digest = _read_presentation(runtime)
    workspace = runtime_workspace(runtime)
    key = hashlib.sha256(str(workspace).encode()).hexdigest() + ":" + session_id
    previous = document["records"].get(key, {})
    if not isinstance(previous, dict):
        raise OSError("session presentation is invalid")
    record = {
        **previous,
        "sessionId": session_id,
        "pinned": previous.get("pinned", False),
        "archived": previous.get("archived", False) if archived is None else archived,
        "version": 1,
    }
    if alias is not None:
        record["alias"] = alias
    if type(record["pinned"]) is not bool or type(record["archived"]) is not bool:
        raise OSError("session presentation is invalid")
    document["records"][key] = record
    encoded = json.dumps(
        document, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode()
    if len(encoded) > _MAX_PRESENTATION_BYTES:
        raise OSError("session presentation exceeds its storage limit")
    atomic_write(WorkspacePaths(path.parent), path, encoded, digest)
    return record
