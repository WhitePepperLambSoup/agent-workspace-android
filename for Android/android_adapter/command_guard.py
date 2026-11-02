"""Commands the agent runs see the workspace, not the app's own files or Android's services.

A command runs as the app's own Linux user. Unguarded it could read the engine's serve.token (and
with it call the engine: resolve approvals, work the phone), the conversations' database, the
settings and the engine's Python code, and through Binder ask Android for anything the app may do:
its contacts permission, its own unexported receivers, Shizuku. Every command the agent starts
therefore runs under the packaged PRoot over the phone's own root, with the app's private folders
and Binder covered by empty ones, and the workspace and the temporary folder shown again.

PRoot translates paths; it is not an OS sandbox, and a program written to get out of it could. What
it stops is a command reaching those files or services by name, which is what a page that talks the
agent into running something would try.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

_BINDER_NODES = ("binder", "hwbinder", "vndbinder")
_PROBE_SECONDS = 15
_LOCK = threading.Lock()
# Probed once per engine: {"state": "on", "mode": "seccomp" | "ptrace"} or {"state": "off", ...}.
_STATE: dict[str, Any] | None = None


def _data_dir() -> Path | None:
    value = os.getenv("AGENT_WORKSPACE_DATA_DIR")
    return Path(value) if value else None


def private_folders(data_dir: Path) -> list[Path]:
    """The app's own folders on the phone, as Android resolves them (data_dir is <app>/files/agent-data)."""
    app = Path(os.path.abspath(data_dir)).parent.parent
    package = app.name
    parts = app.parts
    user = parts[3] if len(parts) == 5 and parts[1:3] == ("data", "user") else "0"
    candidates = [
        app,
        Path(f"/data/user_de/{user}/{package}"),
        Path(f"/storage/emulated/{user}/Android/data/{package}"),
        Path(f"/storage/emulated/{user}/Android/media/{package}"),
        Path(f"/storage/emulated/{user}/Android/obb/{package}"),
    ]
    found: list[Path] = []
    for candidate in candidates:
        real = Path(os.path.realpath(candidate))
        if real.is_dir() and not any(real == seen or real.is_relative_to(seen) for seen in found):
            found.append(real)
    return found


def binder_nodes() -> list[tuple[Path, bool]]:
    """Binder as the guest would open it: the binderfs folder, else the device nodes themselves."""
    nodes: list[tuple[Path, bool]] = []
    binderfs = Path("/dev/binderfs")
    if binderfs.is_dir():
        nodes.append((binderfs, True))
    for name in _BINDER_NODES:
        node = Path("/dev") / name
        if os.path.lexists(node) and not node.is_symlink():
            nodes.append((node, False))
    return nodes


def _covers(data_dir: Path, targets: list[tuple[Path, bool]]) -> list[str]:
    """PRoot bindings that lay an empty folder (or file) of the app's over each target."""
    root = Path(data_dir) / "command-guard" / "cover"
    root.mkdir(parents=True, exist_ok=True)
    empty_file = root / "node"
    if not empty_file.exists():
        empty_file.write_bytes(b"")
    bindings: list[str] = []
    for index, (target, folder) in enumerate(targets):
        if folder:
            # One empty folder each: PRoot builds the way to a binding inside a covered folder in
            # the folder it was given, and a shared one would show those entries under every cover.
            source = root / str(index)
            source.mkdir(exist_ok=True)
        else:
            source = empty_file
        bindings += ["-b", f"{source}:{target}"]
    return bindings


def binder_covers(data_dir: Path) -> list[str]:
    """For the toolchain's own PRoot, which shows the guest all of /dev."""
    return _covers(data_dir, binder_nodes())


def _command(
    native: dict[str, Any],
    data_dir: Path,
    argv: list[str],
    cwd: Path,
    shown: list[Path],
    mode: str,
) -> tuple[list[str], dict[str, str]]:
    hidden = [(folder, True) for folder in private_folders(data_dir)] + binder_nodes()
    bindings = _covers(data_dir, hidden)
    for folder in shown:
        real = os.path.realpath(folder)
        if any(Path(real).is_relative_to(target) for target, _folder in hidden):
            bindings += ["-b", f"{real}:{real}"]
    temporary = Path(data_dir) / "command-guard" / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    environment = {
        "LD_LIBRARY_PATH": str(native["native_library_dir"]),
        "PROOT_LOADER": str(native["loader"]),
        "PROOT_TMP_DIR": str(temporary),
    }
    if mode == "ptrace":
        environment["PROOT_NO_SECCOMP"] = "1"
    # PRoot hands the guest its own environment; the command gets the one it had before.
    strip: list[str] = []
    if Path("/system/bin/env").exists():
        strip = ["/system/bin/env", *[part for name in environment for part in ("-u", name)]]
    command = [
        str(native["launcher"]),
        "--kill-on-exit",
        *bindings,
        "-w",
        str(cwd),
        *strip,
        *argv,
    ]
    return command, environment


def _native() -> dict[str, Any]:
    from mobile_toolchain import native_toolchain_status

    native = native_toolchain_status()
    if not native.get("available") or not native.get("launcher") or not native.get("loader"):
        raise RuntimeError(str(native.get("reason") or "the packaged PRoot launcher is unavailable"))
    return native


def _probe(native: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    """Run a command that looks for a file in the app's folder and for a shown folder."""
    root = Path(data_dir) / "command-guard"
    root.mkdir(parents=True, exist_ok=True)
    marker = root / "probe-marker"
    marker.write_text("private", "utf-8")
    shown = root / "probe-shown"
    shown.mkdir(exist_ok=True)
    script = f'test -e "{marker}" && echo seen || echo hidden; test -d "{shown}" && echo shown'
    failure = ""
    for mode in ("seccomp", "ptrace"):
        argv, environment = _command(native, data_dir, ["/system/bin/sh", "-c", script], shown, [shown], mode)
        try:
            done = subprocess.run(
                argv,
                cwd=str(shown),
                env={"PATH": os.environ.get("PATH", "/system/bin"), **environment},
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=_PROBE_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            failure = f"{mode}: {type(error).__name__}"
            continue
        output = done.stdout.decode("utf-8", "replace").split()
        if output == ["hidden", "shown"]:
            return {"state": "on", "mode": mode}
        failure = f"{mode}: exit {done.returncode}, {(done.stdout + done.stderr)[:300]!r}"
    return {"state": "off", "reason": f"the probe command did not pass ({failure})"}


def status() -> dict[str, Any]:
    """Whether commands are guarded on this phone; probed on the first command."""
    global _STATE
    with _LOCK:
        if _STATE is None:
            data_dir = _data_dir()
            if os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") != "chaquopy" or data_dir is None:
                _STATE = {"state": "off", "reason": "not on Android"}
            else:
                try:
                    _STATE = _probe(_native(), data_dir)
                except Exception as error:
                    _STATE = {"state": "off", "reason": str(error)[:300]}
                if _STATE["state"] != "on":
                    print(f"command guard off: {_STATE.get('reason')}", flush=True)
        return dict(_STATE)


def guard(
    argv: list[str], cwd: Path, workspace: Path | None = None
) -> tuple[list[str], dict[str, str]] | None:
    """argv under the guard, with the environment PRoot needs; None runs it as it is.

    A program that cannot be found is left to start as it is, so its caller says what is missing.
    """
    state = status()
    if not argv or state["state"] != "on":
        return None
    executable = argv[0]
    if "/" not in executable:
        from .terminal import _environment

        found = shutil.which(executable, path=_environment().get("PATH"))
        if found is None:
            return None
        executable = found
    data_dir = _data_dir()
    if data_dir is None:
        return None
    shown = [Path(workspace or cwd), Path(tempfile.gettempdir())]
    return _command(_native(), data_dir, [executable, *argv[1:]], Path(cwd), shown, state["mode"])


def _reset_for_tests() -> None:
    global _STATE
    with _LOCK:
        _STATE = None


__all__ = ["binder_covers", "guard", "private_folders", "status"]
