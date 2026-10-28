"""Install Tectonic for this user: a self-contained TeX engine that fetches the packages a document
needs on first use, for computers without MiKTeX or TeX Live.

The release is pinned and its SHA-256 checked before anything is unpacked; the program goes into
the app's data folder (no administrator rights, nothing on PATH).
"""

from __future__ import annotations

import hashlib
import io
import os
import platform
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_workspace.latex.compile import tectonic_install_path

TECTONIC_VERSION = "0.15.0"
TECTONIC_URL = (
    "https://github.com/tectonic-typesetting/tectonic/releases/download/"
    "tectonic%400.15.0/tectonic-0.15.0-x86_64-pc-windows-msvc.zip"
)
TECTONIC_SHA256 = "1d6bb76f049c8a3774f6e9d66e4b04e1a8c3dcb37527b6b41b7e894328e7bf29"
MAX_DOWNLOAD_BYTES = 120 * 1024 * 1024
_CREATE_NO_WINDOW = 0x08000000


class InstallError(Exception):
    """Why Tectonic could not be installed: ``unsupported``, ``download``, ``checksum``,
    ``archive``, ``cancelled`` or ``blocked`` (it was saved but does not run)."""


def installable() -> bool:
    """The pinned release is for 64-bit Windows."""
    return sys.platform == "win32" and platform.machine().lower() in {"amd64", "x86_64"}


Opener = Callable[[urllib.request.Request], Any]


def _open(request: urllib.request.Request) -> Any:
    # The system's proxy settings apply, as for a browser download.
    return urllib.request.urlopen(request, timeout=30)


def _download(
    url: str,
    cancel: threading.Event | None,
    progress: Callable[[int, int], None] | None,
    opener: Opener | None = None,
) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "AgentWorkspace"})
    try:
        response = (opener or _open)(request)
    except OSError as error:
        raise InstallError("download") from error
    buffer = io.BytesIO()
    with response as stream:
        total = int(stream.headers.get("Content-Length") or 0)
        if total > MAX_DOWNLOAD_BYTES:
            raise InstallError("download")
        while True:
            if cancel is not None and cancel.is_set():
                raise InstallError("cancelled")
            try:
                chunk = stream.read(256 * 1024)
            except OSError as error:
                raise InstallError("download") from error
            if not chunk:
                break
            buffer.write(chunk)
            if buffer.tell() > MAX_DOWNLOAD_BYTES:
                raise InstallError("download")
            if progress is not None:
                progress(buffer.tell(), total)
    data = buffer.getvalue()
    if total and len(data) != total:
        raise InstallError("download")
    return data


def install_tectonic(
    data_dir: Path,
    *,
    cancel: threading.Event | None = None,
    progress: Callable[[int, int], None] | None = None,
    url: str = TECTONIC_URL,
    sha256: str = TECTONIC_SHA256,
    opener: Opener | None = None,
    check_runs: bool = True,
) -> Path:
    """Download, verify and unpack Tectonic; returns the installed program."""
    if opener is None and not installable():
        raise InstallError("unsupported")
    data = _download(url, cancel, progress, opener)
    if hashlib.sha256(data).hexdigest() != sha256:
        raise InstallError("checksum")
    target = tectonic_install_path(data_dir)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = [name for name in archive.namelist() if Path(name).name == target.name]
            if len(names) != 1:
                raise InstallError("archive")
            program = archive.read(names[0])
    except zipfile.BadZipFile as error:
        raise InstallError("archive") from error
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".tectonic-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(program)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    if check_runs:
        try:
            completed = subprocess.run(
                [str(target), "--version"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=30,
                creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise InstallError("blocked") from error
        if completed.returncode != 0:
            raise InstallError("blocked")
    return target
