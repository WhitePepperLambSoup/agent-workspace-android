from __future__ import annotations

import errno
import ntpath
import os
import re
import stat
import sys
from pathlib import Path
from typing import BinaryIO

type StrPath = str | os.PathLike[str]

_SENSITIVE_FILENAMES = frozenset(
    {
        ".env",
        ".envrc",
        ".git-credentials",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "_netrc",
        "credentials",
        "credentials.json",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
        "id_xmss",
        "known_hosts",
        "secrets.json",
        "terraform.rc",
    }
)
_SENSITIVE_DIRECTORIES = frozenset({".aws", ".azure", ".docker", ".kube", ".ssh", "gcloud"})
_SENSITIVE_SUFFIXES = frozenset({".jks", ".key", ".keystore", ".p12", ".pem", ".pfx", ".ppk"})


def is_sensitive_workspace_path(path: str) -> bool:
    parts = tuple(part.casefold() for part in path.replace("\\", "/").split("/") if part)
    if not parts:
        return False
    filename = parts[-1]
    return (
        ".git" in parts
        or any(part in _SENSITIVE_DIRECTORIES for part in parts)
        or filename in _SENSITIVE_FILENAMES
        or filename.startswith(".env.")
        or any(filename.endswith(suffix) for suffix in _SENSITIVE_SUFFIXES)
    )


def open_checked(path: StrPath) -> BinaryIO:
    """Open for reading a file at a path ``WorkspacePaths.resolve`` returned, refusing it when a
    folder on the way became a link after the check (a command running in the workspace can
    swap one in between): the file opened is then not the file that was checked.

    Such a path has no link anywhere, so on POSIX each folder is opened without following
    links (O_PATH where there is one, so no read permission is needed on the way). Windows has
    no O_NOFOLLOW: the opened file's final path must be the checked path.
    """
    text = os.path.abspath(os.fspath(path))
    if os.name == "nt":
        stream = open(text, "rb")  # noqa: SIM115 - returned to the caller, who closes it
        try:
            final = _final_path(stream.fileno())
            if final is not None and os.path.normcase(final) != os.path.normcase(text):
                raise UnsafePathError(f"path changed during open: {text}")
        except BaseException:
            stream.close()
            raise
        return stream
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow or os.open not in os.supports_dir_fd:
        return open(text, "rb")
    cloexec = getattr(os, "O_CLOEXEC", 0)
    folder_flags = (
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_PATH", 0) | nofollow | cloexec
    )
    parts = Path(text).parts
    try:
        folder = os.open(parts[0], folder_flags)
    except PermissionError:
        return open(text, "rb")  # no O_PATH here and the root folder is unreadable
    try:
        for index, part in enumerate(parts[1:-1], start=1):
            try:
                inner = os.open(part, folder_flags, dir_fd=folder)
            except OSError as exc:
                _refuse_link(exc, os.path.join(*parts[: index + 1]), text)
                raise
            os.close(folder)
            folder = inner
        try:
            # Non-blocking: a FIFO put in the file's place does not hang the reader.
            descriptor = os.open(
                parts[-1],
                os.O_RDONLY | nofollow | cloexec | getattr(os, "O_NONBLOCK", 0),
                dir_fd=folder,
            )
        except OSError as exc:
            _refuse_link(exc, text, text)
            raise
    finally:
        os.close(folder)
    return os.fdopen(descriptor, "rb")


def _refuse_link(error: OSError, component: str, path: str) -> None:
    if error.errno in {errno.ELOOP, errno.ENOTDIR, errno.EMLINK} and os.path.islink(component):
        raise UnsafePathError(f"path changed to a link during open: {path}") from error


def _final_path(descriptor: int) -> str | None:
    """Where an open file really is (Windows), or None when the system cannot say."""
    if sys.platform != "win32":
        return None
    import ctypes
    import msvcrt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    function = kernel32.GetFinalPathNameByHandleW
    function.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
    function.restype = ctypes.c_uint32
    handle = msvcrt.get_osfhandle(descriptor)
    size = 1024
    while True:
        buffer = ctypes.create_unicode_buffer(size)
        length = function(handle, buffer, size, 0)  # normalized, with a drive letter
        if length == 0:
            return None
        if length < size:
            break
        size = length + 1
    final = buffer.value
    if final.startswith("\\\\?\\UNC\\"):
        return "\\\\" + final[8:]
    return final.removeprefix("\\\\?\\")


class WorkspacePathError(ValueError):
    """Base error for paths that cannot be used by workspace tools."""


class PathOutsideWorkspaceError(WorkspacePathError):
    """Raised when a path resolves outside the selected workspace."""


class UnsafePathError(WorkspacePathError):
    """Raised for malformed paths or paths containing links/reparse points."""


class WorkspacePaths:
    """Normalize workspace paths and enforce a fail-closed containment boundary."""

    def __init__(self, root: StrPath) -> None:
        root_text = os.fspath(root)
        self._validate_text(root_text)
        raw_root = Path(os.path.abspath(root_text))
        if self._is_link_or_reparse(raw_root):
            raise UnsafePathError(f"workspace root is a symlink or reparse point: {raw_root}")
        try:
            resolved_root = raw_root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise UnsafePathError(f"cannot resolve workspace root: {raw_root}") from exc
        if not resolved_root.is_dir():
            raise WorkspacePathError(f"workspace root is not a directory: {resolved_root}")
        self._root = resolved_root

    @property
    def root(self) -> Path:
        return self._root

    def resolve(self, path: StrPath = ".") -> Path:
        path_text = os.fspath(path)
        self._validate_text(path_text)
        if os.sep == "/":
            path_text = path_text.replace("\\", "/")

        candidate_path = Path(path_text)
        if not candidate_path.is_absolute():
            candidate_path = self._root / candidate_path
        candidate = Path(os.path.abspath(os.path.normpath(candidate_path)))
        if not self._is_contained(candidate):
            raise PathOutsideWorkspaceError(f"path is outside workspace: {path}")

        self._assert_safe_components(candidate)
        return candidate

    def relative(self, path: StrPath) -> str:
        return self.resolve(path).relative_to(self._root).as_posix() or "."

    def _is_contained(self, candidate: Path) -> bool:
        try:
            common = os.path.commonpath((self._root, candidate))
        except ValueError:
            return False
        return os.path.normcase(common) == os.path.normcase(os.fspath(self._root))

    def _assert_safe_components(self, candidate: Path) -> None:
        relative = candidate.relative_to(self._root)
        current = self._root
        for part in relative.parts:
            current /= part
            if self._is_link_or_reparse(current):
                raise UnsafePathError(f"path contains a symlink or reparse point: {current}")
            self._assert_single_link_file(current)

    @staticmethod
    def assert_safe_file_descriptor(descriptor: int, path: StrPath) -> os.stat_result:
        try:
            metadata = os.fstat(descriptor)
        except OSError as exc:
            raise UnsafePathError(f"cannot inspect opened file safely: {path}") from exc
        if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink != 1:
            raise UnsafePathError(f"hard-linked files are not supported: {path}")
        return metadata

    @staticmethod
    def _assert_single_link_file(path: Path) -> None:
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return
        except OSError as exc:
            raise UnsafePathError(f"cannot inspect path safely: {path}") from exc
        if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink != 1:
            raise UnsafePathError(f"hard-linked files are not supported: {path}")

    @staticmethod
    def _is_link_or_reparse(path: Path) -> bool:
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise UnsafePathError(f"cannot inspect path safely: {path}") from exc

        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        attributes = getattr(metadata, "st_file_attributes", 0)
        return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)

    @staticmethod
    def _validate_text(path: str) -> None:
        if "\x00" in path:
            raise UnsafePathError("paths may not contain NUL")
        windows_path = path.replace("/", "\\")
        if windows_path.startswith("\\\\"):
            raise UnsafePathError("UNC and device paths are not supported")
        drive, tail = ntpath.splitdrive(windows_path)
        if drive and os.name != "nt":
            raise UnsafePathError("Windows drive paths are not valid on this platform")
        if ":" in tail:
            raise UnsafePathError("alternate data stream paths are not supported")
        if os.name == "nt":
            for component in (part for part in tail.split("\\") if part):
                if component not in {".", ".."} and component.endswith((" ", ".")):
                    raise UnsafePathError(
                        "Windows paths may not contain components ending in spaces or dots"
                    )
                if re.search(r"~[0-9]+(?:\.|$)", component, flags=re.IGNORECASE):
                    raise UnsafePathError("DOS short-name path aliases are not supported")
