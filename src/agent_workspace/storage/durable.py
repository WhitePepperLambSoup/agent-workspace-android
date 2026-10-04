from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path
from typing import Any

_MOVEFILE_REPLACE_EXISTING = 0x1
_MOVEFILE_WRITE_THROUGH = 0x8
_ERROR_FILE_EXISTS = 80
_ERROR_ALREADY_EXISTS = 183


def durable_replace(source: Path, destination: Path) -> None:
    if os.name == "nt":
        _move_file_ex(
            source,
            destination,
            _MOVEFILE_REPLACE_EXISTING | _MOVEFILE_WRITE_THROUGH,
        )
        return
    os.replace(source, destination)
    fsync_directory(destination.parent)


def durable_publish_new(source: Path, destination: Path) -> None:
    if os.name == "nt":
        try:
            _move_file_ex(source, destination, _MOVEFILE_WRITE_THROUGH)
        except OSError as exc:
            if exc.winerror in {_ERROR_FILE_EXISTS, _ERROR_ALREADY_EXISTS}:
                raise FileExistsError(f"destination already exists: {destination}") from None
            raise
        return
    try:
        os.link(source, destination)
    except FileExistsError:
        raise FileExistsError(f"destination already exists: {destination}") from None
    except OSError as exc:
        # Android's app-private filesystems can reject hard links even when a
        # same-directory atomic rename is supported. The backup name is
        # generated uniquely, so preserve the no-overwrite check before moving.
        if exc.errno not in {
            errno.EACCES,
            errno.EPERM,
            errno.ENOTSUP,
            getattr(errno, "EOPNOTSUPP", errno.ENOTSUP),
        }:
            raise
        if destination.exists():
            raise FileExistsError(f"destination already exists: {destination}") from None
        os.rename(source, destination)
        fsync_directory(destination.parent)
        return
    fsync_directory(destination.parent)
    source.unlink()
    fsync_directory(source.parent)


def fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except PermissionError:
        # Some app-private filesystems support atomic rename but deny opening
        # directories for fsync. The file itself was already flushed before
        # this best-effort durability barrier.
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _move_file_ex(source: Path, destination: Path, flags: int) -> None:
    kernel32: Any = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
    kernel32.MoveFileExW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    kernel32.MoveFileExW.restype = ctypes.c_int
    if not kernel32.MoveFileExW(str(source), str(destination), flags):
        error_code = ctypes.get_last_error()
        raise ctypes.WinError(error_code)
