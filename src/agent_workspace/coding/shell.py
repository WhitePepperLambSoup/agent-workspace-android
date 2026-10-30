"""The user's own terminals in the window: a shell in a pseudo console (ConPTY on Windows, a pty
elsewhere). What it prints goes to the window as it comes, and the last part of it is kept so a
reloaded window shows it again and the agent can read the end of it when the user asks."""

from __future__ import annotations

import codecs
import contextlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import validate_tool_arguments

MAX_RUNNING = 8
MAX_KEPT = 16
KEPT_CHARS = 200_000
# A message on the wire is at most 1 MB and escapes every character outside ASCII (up to 12
# bytes each): output goes out in pieces, and a replay is cut to fit.
EVENT_CHARS = 48_000
REPLAY_BYTES = 700_000
MAX_INPUT_CHARS = 100_000
MAX_COLUMNS, MAX_ROWS = 1000, 500


class ShellError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Program:
    id: str
    label: str
    argv: tuple[str, ...]

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label}


# Docker Desktop's own distributions: no shell to work in.
_WSL_INTERNAL = ("docker-desktop", "docker-desktop-data")


def wsl_output(data: bytes) -> str:
    """wsl.exe's own messages are UTF-16 unless WSL_UTF8 is honoured; Linux output is UTF-8."""
    if b"\x00" in data:
        try:
            return data.decode("utf-16-le", errors="replace").replace("\ufeff", "")
        except UnicodeDecodeError:
            return data.replace(b"\x00", b"").decode("utf-8", errors="replace")
    return data.decode("utf-8", errors="replace")


def wsl_environment() -> dict[str, str]:
    return {**os.environ, "WSL_UTF8": "1"}


def wsl_distributions(wsl: str) -> list[str]:
    """The Linux distributions installed in WSL to work in (wsl.exe is there even with none)."""
    try:
        completed = subprocess.run(
            [wsl, "--list", "--quiet"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=8,
            check=False,
            env=wsl_environment(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    names = [line.strip("\x00 \r") for line in wsl_output(completed.stdout).splitlines()]
    return [name for name in names if name and name not in _WSL_INTERNAL]


def find_programs(which: Callable[[str], str | None] = shutil.which) -> list[Program]:
    """The shells this computer has, the usual one first."""
    if os.name != "nt":
        shell = os.environ.get("SHELL") or which("bash") or "/bin/sh"
        return [Program("default", Path(shell).name, (shell, "-l"))]
    found: list[Program] = []
    for program_id, label, name, arguments in (
        ("pwsh", "PowerShell 7", "pwsh", ("-NoLogo",)),
        ("powershell", "PowerShell", "powershell", ("-NoLogo",)),
        ("cmd", "cmd", "cmd", ()),
    ):
        path = which(name)
        if path:
            found.append(Program(program_id, label, (path, *arguments)))
    git = which("git")
    if git:
        bash = Path(git).resolve().parent.parent / "bin" / "bash.exe"
        if bash.is_file():
            found.append(Program("gitbash", "Git Bash", (str(bash), "--login", "-i")))
    wsl = which("wsl")
    distributions = wsl_distributions(wsl) if wsl else []
    if wsl and distributions:
        found.append(Program("wsl", "WSL", (wsl,)))
        if len(distributions) > 1:
            found.extend(
                Program(f"wsl:{name}", f"WSL: {name}", (wsl, "-d", name)) for name in distributions
            )
    return found + ssh_programs(which)


def ssh_programs(which: Callable[[str], str | None] = shutil.which) -> list[Program]:
    """A terminal on each host of the user's SSH configuration (~/.ssh/config)."""
    from agent_workspace.science.remote import ssh_config_hosts

    ssh = which("ssh")
    if ssh is None and os.name == "nt":
        root = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR") or ""
        candidate = Path(root, "System32", "OpenSSH", "ssh.exe")
        ssh = str(candidate) if root and candidate.is_file() else None
    if ssh is None:
        return []
    hosts = ssh_config_hosts(Path.home() / ".ssh" / "config")
    return [
        Program(f"ssh:{host['name']}", f"SSH: {host['name']}", (ssh, str(host["name"])))
        for host in hosts[:20]
    ]


_APP_VARIABLES = ("AGENT_WORKSPACE_", "ELECTRON_")


def shell_environment() -> dict[str, str]:
    """The user's environment without the app's own variables, and with colors on."""
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith(_APP_VARIABLES)
    }
    environment["COLORTERM"] = "truecolor"
    if os.name != "nt":
        environment["TERM"] = "xterm-256color"
    return environment


_ESCAPES = re.compile(
    r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # window title and other OSC strings
    r"|\x1b\[[0-?]*[ -/]*[@-~]"  # colors, cursor moves
    r"|\x1b[@-Z\\-_]"
    r"|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
)


_CURSOR_TO = re.compile(r"\x1b\[[\d;]*[Hf]")


def screen_text(raw: str) -> str:
    """Terminal output as plain lines: no escape sequences, a carriage return overwrites and
    a move of the cursor (how a Windows console redraws) starts a new line."""
    lines: list[str] = []
    for line in _ESCAPES.sub("", _CURSOR_TO.sub("\n", raw)).split("\n"):
        line = line.removesuffix("\r")
        line = line.rsplit("\r", 1)[-1].rstrip()
        if line or (lines and lines[-1]):
            lines.append(line)
    return "\n".join(lines).strip("\n")


class _Backend(Protocol):
    def read(self) -> bytes: ...
    def write(self, data: bytes) -> None: ...
    def resize(self, columns: int, rows: int) -> None: ...
    def kill(self) -> None: ...
    def wait(self) -> int: ...
    def after_exit(self) -> None: ...
    def close(self) -> None: ...


BackendFactory = Callable[[tuple[str, ...], Path, dict[str, str], int, int], _Backend]


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    from agent_workspace.tools import pty as _win

    _CREATE_SUSPENDED = 0x00000004
    _INFINITE = 0xFFFFFFFF
    _KILL_ON_JOB_CLOSE = 0x2000
    _EXTENDED_LIMIT_INFORMATION = 9

    class _ConPty:
        """A pseudo console with the shell attached (Windows 10 1809 and later)."""

        def __init__(
            self,
            argv: tuple[str, ...],
            cwd: Path,
            environment: dict[str, str],
            columns: int,
            rows: int,
        ) -> None:
            kernel32 = _win._load_kernel32()
            kernel32.ResizePseudoConsole.argtypes = [wintypes.HANDLE, _win._COORD]
            kernel32.ResizePseudoConsole.restype = ctypes.c_long
            kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
            kernel32.ResumeThread.restype = wintypes.DWORD
            kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel32.WaitForSingleObject.restype = wintypes.DWORD
            self._k = kernel32
            self._console = wintypes.HANDLE()
            self._input = wintypes.HANDLE()  # the keys the user types go in here
            self._output = wintypes.HANDLE()  # what the console shows comes out here
            self._process = _win._PROCESS_INFORMATION()
            self._job: Any = None
            self._attributes: Any = None
            self._attribute_buffer: Any = None
            self._buffer = ctypes.create_string_buffer(65536)
            self._closed = False
            try:
                self._start(argv, cwd, environment, columns, rows)
            except BaseException:
                self.close()
                raise

        def _start(
            self,
            argv: tuple[str, ...],
            cwd: Path,
            environment: dict[str, str],
            columns: int,
            rows: int,
        ) -> None:
            kernel32 = self._k
            console_input = wintypes.HANDLE()
            console_output = wintypes.HANDLE()
            try:
                if not kernel32.CreatePipe(
                    ctypes.byref(console_input), ctypes.byref(self._input), None, 0
                ) or not kernel32.CreatePipe(
                    ctypes.byref(self._output), ctypes.byref(console_output), None, 0
                ):
                    raise ShellError("shell_start_failed")
                if kernel32.CreatePseudoConsole(
                    _win._COORD(columns, rows),
                    console_input,
                    console_output,
                    0,
                    ctypes.byref(self._console),
                ):
                    raise ShellError("shell_unavailable")
            finally:
                # The console holds its own copies; keeping ours would hide the end of output.
                _win._close(kernel32, console_input, console_output)
            size = ctypes.c_size_t()
            kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
            self._attribute_buffer = ctypes.create_string_buffer(size.value)
            attributes = ctypes.cast(self._attribute_buffer, _win._LPPROC_THREAD_ATTRIBUTE_LIST)
            if not kernel32.InitializeProcThreadAttributeList(attributes, 1, 0, ctypes.byref(size)):
                raise ShellError("shell_start_failed")
            self._attributes = attributes
            if not kernel32.UpdateProcThreadAttribute(
                attributes,
                0,
                _win._PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
                self._console.value or 0,
                ctypes.sizeof(wintypes.HANDLE),
                None,
                None,
            ):
                raise ShellError("shell_start_failed")
            startup = _win._STARTUPINFOEXW()
            startup.StartupInfo.cb = ctypes.sizeof(_win._STARTUPINFOEXW)
            # Empty standard handles: otherwise the shell would write to the gateway's own pipes.
            startup.StartupInfo.dwFlags = _win._STARTF_USESTDHANDLES
            startup.lpAttributeList = attributes
            block = "".join(
                f"{name}={value}\0"
                for name, value in sorted(environment.items(), key=lambda item: item[0].upper())
            )
            if not kernel32.CreateProcessW(
                None,
                ctypes.create_unicode_buffer(subprocess.list2cmdline(argv)),
                None,
                None,
                False,
                _win._EXTENDED_STARTUPINFO_PRESENT
                | _win._CREATE_UNICODE_ENVIRONMENT
                | _CREATE_SUSPENDED,
                ctypes.create_unicode_buffer(block + "\0"),
                str(cwd),
                ctypes.byref(startup),
                ctypes.byref(self._process),
            ):
                raise ShellError("shell_start_failed")
            # In a job before it runs, so closing the terminal (or the app) ends what it started.
            job = kernel32.CreateJobObjectW(None, None)
            if job:
                self._job = job
                limits = _win._JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                limits.BasicLimitInformation.LimitFlags = _KILL_ON_JOB_CLOSE
                kernel32.SetInformationJobObject(
                    job, _EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), ctypes.sizeof(limits)
                )
                kernel32.AssignProcessToJobObject(job, self._process.hProcess)
            kernel32.ResumeThread(self._process.hThread)

        def read(self) -> bytes:
            count = wintypes.DWORD()
            if not self._k.ReadFile(
                self._output, self._buffer, len(self._buffer), ctypes.byref(count), None
            ):
                return b""
            return self._buffer.raw[: count.value]

        def write(self, data: bytes) -> None:
            view = memoryview(data)
            while view:
                written = wintypes.DWORD()
                chunk = ctypes.create_string_buffer(bytes(view[:65536]), len(view[:65536]))
                if not self._k.WriteFile(
                    self._input, chunk, len(chunk), ctypes.byref(written), None
                ):
                    return
                view = view[written.value :]

        def resize(self, columns: int, rows: int) -> None:
            if self._console:
                self._k.ResizePseudoConsole(self._console, _win._COORD(columns, rows))

        def kill(self) -> None:
            if self._job:
                self._k.TerminateJobObject(self._job, 1)
            elif self._process.hProcess:
                self._k.TerminateProcess(self._process.hProcess, 1)

        def wait(self) -> int:
            self._k.WaitForSingleObject(self._process.hProcess, _INFINITE)
            code = wintypes.DWORD()
            self._k.GetExitCodeProcess(self._process.hProcess, ctypes.byref(code))
            return int(code.value)

        def after_exit(self) -> None:
            # Ends the console, which closes its end of the output: the reader then stops.
            if self._console:
                self._k.ClosePseudoConsole(self._console)
                self._console = wintypes.HANDLE()

        def close(self) -> None:
            if self._closed:
                return
            self._closed = True
            self.after_exit()
            _win._close(
                self._k,
                self._input,
                self._output,
                self._process.hThread,
                self._process.hProcess,
                self._job,
            )
            if self._attributes is not None:
                self._k.DeleteProcThreadAttributeList(self._attributes)
                self._attributes = None

    def _default_backend(
        argv: tuple[str, ...], cwd: Path, environment: dict[str, str], columns: int, rows: int
    ) -> _Backend:
        return _ConPty(argv, cwd, environment, columns, rows)

else:
    import fcntl
    import signal
    import struct
    import termios

    class _Pty:
        def __init__(
            self,
            argv: tuple[str, ...],
            cwd: Path,
            environment: dict[str, str],
            columns: int,
            rows: int,
        ) -> None:
            self._master, terminal = os.openpty()
            self.resize(columns, rows)

            def take_terminal() -> None:
                fcntl.ioctl(0, termios.TIOCSCTTY, 0)

            try:
                self._process = subprocess.Popen(
                    argv,
                    cwd=cwd,
                    env=environment,
                    stdin=terminal,
                    stdout=terminal,
                    stderr=terminal,
                    start_new_session=True,
                    # The new session needs the pty as its controlling terminal (job control).
                    preexec_fn=take_terminal,
                )
            except OSError:
                os.close(self._master)
                raise ShellError("shell_start_failed") from None
            finally:
                os.close(terminal)

        def read(self) -> bytes:
            try:
                return os.read(self._master, 65536)
            except OSError:
                return b""

        def write(self, data: bytes) -> None:
            with contextlib.suppress(OSError):
                os.write(self._master, data)

        def resize(self, columns: int, rows: int) -> None:
            with contextlib.suppress(OSError):
                fcntl.ioctl(
                    self._master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0)
                )

        def kill(self) -> None:
            with contextlib.suppress(OSError):
                os.killpg(self._process.pid, signal.SIGKILL)

        def wait(self) -> int:
            return self._process.wait()

        def after_exit(self) -> None:
            return None

        def close(self) -> None:
            with contextlib.suppress(OSError):
                os.close(self._master)

    def _default_backend(
        argv: tuple[str, ...], cwd: Path, environment: dict[str, str], columns: int, rows: int
    ) -> _Backend:
        return _Pty(argv, cwd, environment, columns, rows)


class Shell:
    """One terminal: its process, what it printed, and the threads that move the bytes."""

    def __init__(
        self, shell_id: str, program: Program, cwd: Path, backend: _Backend, size: tuple[int, int]
    ) -> None:
        self.id = shell_id
        self.program = program
        self.cwd = cwd
        self.columns, self.rows = size
        self.started_at = time.time()
        self.used_at = self.started_at
        self.exit_code: int | None = None
        self._backend = backend
        self._lock = threading.Lock()
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._pending: list[str] = []
        self._kept: deque[str] = deque()
        self._kept_chars = 0
        self._sequence = 0
        self._running = True
        self._exit_reported = False
        self._keys: queue.SimpleQueue[bytes | None] = queue.SimpleQueue()
        self._reader = threading.Thread(target=self._read, name="shell-read", daemon=True)
        self._writer = threading.Thread(target=self._write, name="shell-write", daemon=True)
        self._waiter = threading.Thread(target=self._wait, name="shell-wait", daemon=True)
        for thread in (self._reader, self._writer, self._waiter):
            thread.start()

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def _take(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            self._pending.append(text)
            self._kept.append(text)
            self._kept_chars += len(text)
            while self._kept_chars > KEPT_CHARS and len(self._kept) > 1:
                self._kept_chars -= len(self._kept.popleft())

    def _read(self) -> None:
        while data := self._backend.read():
            self._take(self._decoder.decode(data))
        self._take(self._decoder.decode(b"", final=True))

    def _write(self) -> None:
        while (data := self._keys.get()) is not None:
            self._backend.write(data)

    def _wait(self) -> None:
        code = self._backend.wait()
        self._backend.after_exit()
        self._reader.join(timeout=5)
        self._keys.put(None)
        self._writer.join(timeout=5)
        self._backend.close()
        with self._lock:
            self.exit_code = code
            self._running = False

    def write(self, data: str) -> None:
        if self.running:
            self.used_at = time.time()
            self._keys.put(data.encode("utf-8"))

    def resize(self, columns: int, rows: int) -> None:
        self.columns, self.rows = columns, rows
        if self.running:
            self._backend.resize(columns, rows)

    def stop(self) -> None:
        if self.running:
            self._backend.kill()

    def join(self, timeout: float) -> None:
        self._waiter.join(timeout)

    def drain(self) -> list[tuple[str, dict[str, object]]]:
        """The output since the last call, in pieces small enough for the wire, then the exit."""
        with self._lock:
            events: list[tuple[str, dict[str, object]]] = []
            if self._pending:
                text = "".join(self._pending)
                self._pending.clear()
                for start in range(0, len(text), EVENT_CHARS):
                    self._sequence += 1
                    data = text[start : start + EVENT_CHARS]
                    events.append(
                        ("shell.output", {"shellId": self.id, "data": data, "seq": self._sequence})
                    )
            if not self._running and not self._exit_reported:
                self._exit_reported = True
                events.append(("shell.exited", {"shellId": self.id, "exitCode": self.exit_code}))
            return events

    def replay(self) -> dict[str, object]:
        """What is kept, and the sequence number it reaches: output events up to that number
        are in it (output not yet sent is counted here instead of being sent)."""
        with self._lock:
            if self._pending:
                self._pending.clear()
                self._sequence += 1
            data = "".join(self._kept)
            sequence = self._sequence
        while data and len(json.dumps(data)) > REPLAY_BYTES:
            data = data[len(data) // 4 :]
        return {**self.info(), "data": data, "seq": sequence}

    def tail(self, lines: int) -> str:
        with self._lock:
            raw = "".join(self._kept)
        return "\n".join(screen_text(raw).split("\n")[-lines:])

    def info(self) -> dict[str, object]:
        with self._lock:
            running, exit_code = self._running, self.exit_code
        return {
            "id": self.id,
            "program": self.program.id,
            "label": self.program.label,
            "cwd": str(self.cwd),
            "running": running,
            "exitCode": exit_code,
            "columns": self.columns,
            "rows": self.rows,
            "startedAt": self.started_at,
        }


def _size(value: object, upper: int) -> int:
    if type(value) is not int or not 2 <= value <= upper:
        raise ShellError("invalid_size")
    return value


class ShellDesk:
    """Every terminal the window opened, across folders, until the user closes it."""

    def __init__(
        self,
        *,
        programs: Callable[[], list[Program]] = find_programs,
        backend: BackendFactory | None = None,
    ) -> None:
        self._find_programs = programs
        self._programs: list[Program] | None = None
        self._backend = backend or _default_backend
        self._shells: dict[str, Shell] = {}
        self._lock = threading.Lock()

    def programs(self) -> list[Program]:
        with self._lock:
            if self._programs is None:
                self._programs = self._find_programs()
            return list(self._programs)

    def start(self, cwd: Path, *, program: str | None, columns: object, rows: object) -> Shell:
        width, height = _size(columns, MAX_COLUMNS), _size(rows, MAX_ROWS)
        choices = self.programs()
        chosen = next((item for item in choices if item.id == program), None)
        if program is None and choices:
            chosen = choices[0]
        if chosen is None:
            raise ShellError("shell_program_unknown")
        if not cwd.is_dir():
            raise ShellError("invalid_cwd")
        with self._lock:
            if sum(shell.running for shell in self._shells.values()) >= MAX_RUNNING:
                raise ShellError("shell_limit")
        try:
            backend = self._backend(chosen.argv, cwd, shell_environment(), width, height)
        except OSError:
            raise ShellError("shell_start_failed") from None
        shell = Shell(uuid4().hex, chosen, cwd, backend, (width, height))
        with self._lock:
            self._shells[shell.id] = shell
            finished = [item for item in self._shells.values() if not item.running]
            for old in sorted(finished, key=lambda item: item.used_at)[
                : max(0, len(self._shells) - MAX_KEPT)
            ]:
                self._shells.pop(old.id, None)
        return shell

    def get(self, shell_id: object) -> Shell:
        with self._lock:
            shell = self._shells.get(shell_id) if isinstance(shell_id, str) else None
        if shell is None:
            raise ShellError("shell_not_found")
        return shell

    def write(self, shell_id: object, data: object) -> None:
        if not isinstance(data, str) or len(data) > MAX_INPUT_CHARS:
            raise ShellError("invalid_input")
        self.get(shell_id).write(data)

    def resize(self, shell_id: object, columns: object, rows: object) -> None:
        self.get(shell_id).resize(_size(columns, MAX_COLUMNS), _size(rows, MAX_ROWS))

    def stop(self, shell_id: object) -> None:
        self.get(shell_id).stop()

    def remove(self, shell_id: object) -> None:
        shell = self.get(shell_id)
        shell.stop()
        with self._lock:
            self._shells.pop(shell.id, None)

    def listing(self) -> list[dict[str, object]]:
        with self._lock:
            shells = sorted(self._shells.values(), key=lambda item: item.started_at)
        return [shell.info() for shell in shells]

    def drain(self) -> list[tuple[str, dict[str, object]]]:
        with self._lock:
            shells = list(self._shells.values())
        return [event for shell in shells for event in shell.drain()]

    def latest(self) -> Shell | None:
        """The terminal the user typed in last."""
        with self._lock:
            shells = list(self._shells.values())
        return max(shells, key=lambda item: item.used_at, default=None)

    def close(self) -> None:
        with self._lock:
            shells = list(self._shells.values())
            self._shells.clear()
        for shell in shells:
            shell.stop()
        for shell in shells:
            shell.join(timeout=3)


class ReadTerminalTool:
    """The end of what the user's terminal in the window shows, for "look at the error"."""

    _spec = ToolSpec(
        name="read_terminal",
        description=(
            "Read the last lines of the terminal the user has open in the app (the one they "
            "typed in last): the output of what they ran there, such as a failing build or "
            "test. Use it when the user refers to their terminal. Read-only."
        ),
        input_schema={
            "type": "object",
            "properties": {"lines": {"type": "integer", "minimum": 1, "maximum": 400}},
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    def __init__(self, desk: ShellDesk) -> None:
        self.desk = desk

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        shell = self.desk.latest()
        if shell is None:
            return "The user has no terminal open in the app."
        state = "running" if shell.running else f"exited with code {shell.exit_code}"
        text = shell.tail(int(arguments.get("lines", 80)))
        header = f"Terminal: {shell.program.label} in {shell.cwd} ({state})"
        return f"{header}\n\n{text}" if text else f"{header}\n\n(nothing printed yet)"


__all__ = [
    "Program",
    "ReadTerminalTool",
    "Shell",
    "ShellDesk",
    "ShellError",
    "find_programs",
    "screen_text",
    "shell_environment",
    "ssh_programs",
    "wsl_distributions",
    "wsl_environment",
    "wsl_output",
]
