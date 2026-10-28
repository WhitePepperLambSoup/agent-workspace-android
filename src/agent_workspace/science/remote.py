"""Servers the user reaches over SSH: the hosts of ~/.ssh/config, commands run there, files copied
between them and the folder, and Slurm jobs. The user's own ssh and scp do the work, with key
login only (BatchMode): nothing here asks for or keeps a password."""

from __future__ import annotations

import asyncio
import glob
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_workspace.application.ports import Tool
from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import (
    ToolArgumentError,
    ToolError,
    json_result,
    validate_tool_arguments,
)
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

_CREATE_NO_WINDOW = 0x08000000
_HOST = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._\-]{0,252}(@[A-Za-z0-9_][A-Za-z0-9._\-]{0,252})?$")
_JOB = re.compile(r"^\d{1,12}(_\d{1,8})?$")
_OPTION = re.compile(r"^(\S+?)(?:\s*=\s*|\s+)(.*)$")  # Key value, or Key=value
_KEEP = 8_000  # characters kept from the start and from the end of each stream
_CONNECT = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=30"]

type Programs = Callable[[str], list[str] | None]


def find_program(name: str) -> list[str] | None:
    """ssh or scp: the one on PATH, else Windows' own OpenSSH client."""
    found = shutil.which(name)
    if found:
        return [found]
    root = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR")
    if sys.platform == "win32" and root:
        candidate = Path(root) / "System32" / "OpenSSH" / f"{name}.exe"
        if candidate.is_file():
            return [str(candidate)]
    return None


def ssh_config_hosts(config: Path, depth: int = 0) -> list[dict[str, Any]]:
    """The named hosts of an OpenSSH client configuration (patterns are left out)."""
    try:
        text = config.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hosts: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for raw in text.splitlines():
        match = _OPTION.match(raw.strip())
        if not match or match.group(1).startswith("#"):
            continue
        key, value = match.group(1).casefold(), match.group(2).strip().strip('"')
        if key == "include" and depth < 3:
            base = config.parent
            for pattern in value.split():
                expanded = os.path.expanduser(pattern)
                full = expanded if os.path.isabs(expanded) else str(base / expanded)
                for name in sorted(glob.glob(full)):
                    hosts.extend(ssh_config_hosts(Path(name), depth + 1))
        elif key == "host":
            current = [
                {"name": name}
                for name in value.split()
                if not any(mark in name for mark in "*?!") and _HOST.match(name)
            ]
            hosts.extend(current)
        elif key == "match":
            current = []
        elif key in {"hostname", "user", "port", "proxyjump"}:
            for host in current:
                host.setdefault(key, value)
    unique: dict[str, dict[str, Any]] = {}
    for host in hosts:
        unique.setdefault(host["name"], host)
    return list(unique.values())


class _Kept:
    """The start and the end of a stream that may be long."""

    def __init__(self) -> None:
        self.head = bytearray()
        self.tail = bytearray()
        self.total = 0

    def add(self, chunk: bytes) -> None:
        self.total += len(chunk)
        room = _KEEP - len(self.head)
        if room > 0:
            self.head.extend(chunk[:room])
            chunk = chunk[room:]
        if chunk:
            self.tail.extend(chunk)
            del self.tail[: max(0, len(self.tail) - _KEEP)]

    def text(self) -> str:
        head = self.head.decode("utf-8", errors="replace")
        if not self.tail:
            return head
        skipped = self.total - len(self.head) - len(self.tail)
        middle = f"\n… {skipped} bytes left out …\n" if skipped > 0 else ""
        return head + middle + self.tail.decode("utf-8", errors="replace")


@dataclass(frozen=True, slots=True)
class Ran:
    code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    seconds: float


def _drain(stream: Any, kept: _Kept) -> None:
    try:
        while chunk := stream.read(65536):
            kept.add(chunk)
    except (OSError, ValueError):
        return


def _stop(process: subprocess.Popen[bytes]) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW,
            check=False,
        )
    else:
        process.kill()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def _run_sync(argv: list[str], timeout: float, stop: threading.Event) -> Ran:
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except OSError as exc:
        raise ToolError(f"cannot start {argv[0]}: {exc}") from None
    out, err = _Kept(), _Kept()
    readers = [
        threading.Thread(target=_drain, args=(process.stdout, out), daemon=True),
        threading.Thread(target=_drain, args=(process.stderr, err), daemon=True),
    ]
    for reader in readers:
        reader.start()
    timed_out = False
    while process.poll() is None:
        if stop.is_set() or time.monotonic() - started > timeout:
            timed_out = not stop.is_set()
            _stop(process)
            break
        time.sleep(0.05)
    for reader in readers:
        reader.join(timeout=2)
    return Ran(process.returncode, out.text(), err.text(), timed_out, time.monotonic() - started)


async def run(argv: list[str], timeout: float) -> Ran:
    """Run a program to the end, stopping it when the turn is stopped or the time is up."""
    stop = threading.Event()
    try:
        return await asyncio.to_thread(_run_sync, argv, timeout, stop)
    except asyncio.CancelledError:
        stop.set()
        raise


def _host(arguments: dict[str, Any]) -> str:
    host = str(arguments.get("host") or "")
    if not _HOST.match(host):
        raise ToolArgumentError("host must be a name of ~/.ssh/config or user@server")
    return host


def _remote_text(value: Any, name: str) -> str:
    text = str(value or "")
    if not text or any(character in text for character in "\x00\r\n") or text.startswith("-"):
        raise ToolArgumentError(f"{name} must be one line and must not start with '-'")
    return text


def _result(ran: Ran, **extra: Any) -> str:
    hint = None
    if ran.code == 255:
        hint = (
            "ssh could not connect. The host must accept key login without a password prompt "
            "(as in the user's own terminal: ssh <host> works without typing anything); "
            "a new host must be connected to once by hand to accept its key."
        )
    return json_result(
        {
            **extra,
            "exit_code": ran.code,
            "timed_out": ran.timed_out,
            "seconds": round(ran.seconds, 1),
            "stdout": ran.stdout,
            "stderr": ran.stderr,
            **({"hint": hint} if hint else {}),
        }
    )


class _RemoteTool:
    hard_cancellable = True
    _spec: ToolSpec
    _default_seconds = 120

    def __init__(self, workspace: Path, programs: Programs = find_program) -> None:
        self.paths = WorkspacePaths(workspace)
        self.programs = programs

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def execution_timeout_seconds(self, arguments: dict[str, Any]) -> float:
        # The program's own limit, and time to stop it and read what it printed.
        seconds = arguments.get("timeout_seconds")
        return (seconds if isinstance(seconds, int) else self._default_seconds) + 30

    def program(self, name: str) -> list[str]:
        found = self.programs(name)
        if not found:
            raise ToolError(
                f"{name} was not found. On Windows, add the optional feature OpenSSH Client "
                "(Settings > System > Optional features)."
            )
        return found

    async def ssh(self, host: str, command: str, timeout: float) -> Ran:
        return await run([*self.program("ssh"), *_CONNECT, "-T", host, command], timeout)


class RemoteHostsTool(_RemoteTool):
    def __init__(
        self, workspace: Path, programs: Programs = find_program, config: Path | None = None
    ) -> None:
        super().__init__(workspace, programs)
        self.config = config or Path.home() / ".ssh" / "config"
        self._spec = ToolSpec(
            name="remote_hosts",
            description=(
                "List the servers of the user's SSH configuration (~/.ssh/config): name, "
                "hostname, user, port. Use these names as host for remote_run, remote_copy and "
                "slurm_jobs. Hosts must accept key login: password prompts are not answered."
            ),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            side_effect="none",
            capability=Capability.PROCESS_EXECUTE,
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        hosts = await asyncio.to_thread(ssh_config_hosts, self.config)
        return json_result({"hosts": hosts, "ssh": bool(self.programs("ssh"))})


class RemoteRunTool(_RemoteTool):
    def __init__(self, workspace: Path, programs: Programs = find_program) -> None:
        super().__init__(workspace, programs)
        self._spec = ToolSpec(
            name="remote_run",
            description=(
                "Run a shell command on a server over SSH (the user approves each one) and "
                "return its exit code and output (start and end of long output). directory is "
                "the remote folder to run in. For work longer than timeout_seconds, start it in "
                "the background there (nohup … &, tmux) or submit it with slurm_jobs, and check "
                "on it later."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "minLength": 1, "maxLength": 510},
                    "command": {"type": "string", "minLength": 1, "maxLength": 20_000},
                    "directory": {"type": "string", "maxLength": 1000},
                    "timeout_seconds": {"type": "integer", "minimum": 5, "maximum": 1800},
                },
                "required": ["host", "command"],
                "additionalProperties": False,
            },
            side_effect="process",
            capability=Capability.PROCESS_EXECUTE,
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        host = _host(arguments)
        command = str(arguments["command"])
        if "\x00" in command:
            raise ToolArgumentError("command must not contain NUL")
        if arguments.get("directory"):
            command = (
                f"cd {shlex.quote(_remote_text(arguments['directory'], 'directory'))} && {command}"
            )
        ran = await self.ssh(
            host, command, int(arguments.get("timeout_seconds") or self._default_seconds)
        )
        return _result(ran, host=host)


class RemoteCopyTool(_RemoteTool):
    _default_seconds = 600

    def __init__(self, workspace: Path, programs: Programs = find_program) -> None:
        super().__init__(workspace, programs)
        self._spec = ToolSpec(
            name="remote_copy",
            description=(
                "Copy between the folder and a server with scp (the user approves each copy). "
                "upload sends path (a file or, with recursive, a folder of the folder) to "
                "remote_path; download brings remote_path into path, which must not exist yet "
                "(nothing in the folder is overwritten)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "minLength": 1, "maxLength": 510},
                    "direction": {"type": "string", "enum": ["upload", "download"]},
                    "path": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "remote_path": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "recursive": {"type": "boolean"},
                    "timeout_seconds": {"type": "integer", "minimum": 5, "maximum": 3600},
                },
                "required": ["host", "direction", "path", "remote_path"],
                "additionalProperties": False,
            },
            side_effect="process",
            capability=Capability.PROCESS_EXECUTE,
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        host = _host(arguments)
        remote = f"{host}:{_remote_text(arguments['remote_path'], 'remote_path')}"
        try:
            local = self.paths.resolve(arguments["path"])
        except WorkspacePathError as exc:
            raise ToolArgumentError(str(exc)) from None
        upload = arguments["direction"] == "upload"
        if upload and not local.exists():
            raise ToolArgumentError(f"{arguments['path']} is not in the folder")
        if not upload:
            if local.exists():
                raise ToolArgumentError(
                    f"{arguments['path']} already exists; download to a new path"
                )
            local.parent.mkdir(parents=True, exist_ok=True)
        flags = ["-B", "-o", "ConnectTimeout=15"] + (["-r"] if arguments.get("recursive") else [])
        pair = [str(local), remote] if upload else [remote, str(local)]
        ran = await run(
            [*self.program("scp"), *flags, *pair],
            int(arguments.get("timeout_seconds") or self._default_seconds),
        )
        return _result(
            ran,
            host=host,
            direction=arguments["direction"],
            path=self.paths.relative(local),
            remote_path=arguments["remote_path"],
        )


_SQUEUE = "squeue -h -o '%i|%j|%T|%M|%l|%D|%R'"
_SACCT = "sacct -n -P -X -o JobID,JobName,State,Elapsed,ExitCode"


def parse_jobs(text: str, names: Sequence[str]) -> list[dict[str, str]]:
    jobs = []
    for line in text.splitlines():
        parts = line.strip().split("|")
        if len(parts) >= len(names) and parts[0]:
            jobs.append(dict(zip(names, (part.strip() for part in parts), strict=False)))
    return jobs


class SlurmJobsTool(_RemoteTool):
    def __init__(self, workspace: Path, programs: Programs = find_program) -> None:
        super().__init__(workspace, programs)
        self._spec = ToolSpec(
            name="slurm_jobs",
            description=(
                "Slurm on a server over SSH (the user approves each call). submit runs sbatch "
                "on script (a path on the server; upload it first with remote_copy) in directory "
                "and returns the job id; status lists the given jobs (squeue, and sacct for "
                "finished ones) or, without job_ids, the user's queued jobs; cancel runs scancel."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "minLength": 1, "maxLength": 510},
                    "action": {"type": "string", "enum": ["submit", "status", "cancel"]},
                    "script": {"type": "string", "maxLength": 1000},
                    "directory": {"type": "string", "maxLength": 1000},
                    "job_ids": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 24},
                        "maxItems": 100,
                    },
                },
                "required": ["host", "action"],
                "additionalProperties": False,
            },
            side_effect="process",
            capability=Capability.PROCESS_EXECUTE,
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        host = _host(arguments)
        action = arguments["action"]
        ids = [str(item) for item in arguments.get("job_ids") or []]
        if any(not _JOB.match(item) for item in ids):
            raise ToolArgumentError("job_ids are Slurm job numbers such as 123456 or 123456_7")
        joined = ",".join(ids)
        if action == "submit":
            script = shlex.quote(_remote_text(arguments.get("script"), "script"))
            prefix = (
                f"cd {shlex.quote(_remote_text(arguments['directory'], 'directory'))} && "
                if arguments.get("directory")
                else ""
            )
            ran = await self.ssh(host, f"{prefix}sbatch --parsable {script}", 120)
            job = ran.stdout.strip().split(";")[0] if ran.code == 0 else ""
            return _result(ran, host=host, action=action, job_id=job if _JOB.match(job) else None)
        if action == "cancel":
            if not ids:
                raise ToolArgumentError("cancel needs job_ids")
            return _result(await self.ssh(host, f"scancel {joined}", 60), host=host, action=action)
        queue = f"{_SQUEUE} -j {joined}" if ids else f'{_SQUEUE} -u "$USER"'
        command = f"{queue}; echo '--sacct--'; {_SACCT} -j {joined}" if ids else queue
        ran = await self.ssh(host, command, 90)
        queued_text, _, finished_text = ran.stdout.partition("--sacct--")
        queued = parse_jobs(
            queued_text, ["id", "name", "state", "time", "limit", "nodes", "reason"]
        )
        seen = {job["id"] for job in queued}
        finished = [
            job
            for job in parse_jobs(finished_text, ["id", "name", "state", "elapsed", "exit_code"])
            if job["id"] not in seen
        ]
        return json_result(
            {
                "host": host,
                "action": action,
                "queued": queued,
                "finished": finished,
                "exit_code": ran.code,
                "stderr": ran.stderr[-2000:],
            }
        )


def remote_tools(workspace: Path, programs: Programs = find_program) -> tuple[Tool, ...]:
    return (
        RemoteHostsTool(workspace, programs),
        RemoteRunTool(workspace, programs),
        RemoteCopyTool(workspace, programs),
        SlurmJobsTool(workspace, programs),
    )


__all__ = [
    "RemoteCopyTool",
    "RemoteHostsTool",
    "RemoteRunTool",
    "SlurmJobsTool",
    "find_program",
    "parse_jobs",
    "remote_tools",
    "run",
    "ssh_config_hosts",
]
