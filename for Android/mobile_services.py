"""Long-running programs the agent starts for the user: dev servers, bots, watchers.

A service outlives the task that started it and runs until it is stopped or the engine stops.
Its output goes to a capped log file, which the Services page and the agent read from the end.
Services marked autostart are started again whenever the engine starts, unless the user or the
agent stopped them on purpose: that stop holds until the service is started again.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import signal
import socket
import subprocess
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_RUNNING = 4
MAX_RECORDS = 20
LOG_LIMIT = 1024 * 1024
LOG_KEEP = 256 * 1024
STOP_GRACE_SECONDS = 3.0
_MAX_ARGUMENT_BYTES = 128 * 1024
_URL_PORT = re.compile(
    rb"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1?\]|\[::\])(?::(\d{2,5}))", re.I
)
_SIGKILL = getattr(signal, "SIGKILL", signal.SIGTERM)
# Stops someone asked for; an engine shutdown or a restart is not one of them.
DELIBERATE_STOPS = frozenset({"stopped by the user", "stopped by the agent"})


class ServiceError(ValueError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _process_start_ticks(pid: int) -> int | None:
    """The kernel start time of a process, so a reused PID is never mistaken for a service."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text("ascii", errors="replace")
        return int(stat[stat.rindex(")") + 2 :].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _kill_group(pid: int, sig: int) -> None:
    if os.name == "nt":
        # Desktop test runs only; services are an Android feature.
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        return
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(pid, sig)


def _port_open(port: int) -> bool:
    with contextlib.suppress(OSError), socket.create_connection(("127.0.0.1", port), 0.2):
        return True
    return False


def validate_argv(argv: Any) -> list[str]:
    if (
        not isinstance(argv, list)
        or not argv
        or len(argv) > 256
        or any(not isinstance(item, str) or not item or "\x00" in item for item in argv)
        or sum(len(item.encode("utf-8")) for item in argv) > _MAX_ARGUMENT_BYTES
    ):
        raise ServiceError("'argv' must be a bounded array of non-empty strings")
    return list(argv)


class _Running:
    def __init__(self, process: subprocess.Popen[bytes], lease: Any) -> None:
        self.process = process
        self.lease = lease
        self.stop_reason: str | None = None
        self.thread: threading.Thread | None = None


class ServiceManager:
    def __init__(self, data_dir: str | os.PathLike[str], *, transport: Any = None) -> None:
        self.root = Path(data_dir) / "services"
        self.root.mkdir(parents=True, exist_ok=True)
        self._file = self.root / "services.json"
        self._lock = threading.RLock()
        self._running: dict[str, _Running] = {}
        self._transport = transport
        state = self._read()
        self._keep_awake = state.get("keep_awake") is True
        self._records: dict[str, dict[str, Any]] = {
            record["id"]: record
            for record in state.get("services", [])
            if isinstance(record, dict) and isinstance(record.get("id"), str)
        }

    # Persistence -------------------------------------------------------------------------------

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self._file.read_text("utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        records = sorted(self._records.values(), key=lambda item: item.get("created_at", ""))
        temporary = self._file.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"version": 1, "keep_awake": self._keep_awake, "services": records},
                ensure_ascii=False,
                indent=1,
            ),
            "utf-8",
        )
        os.replace(temporary, self._file)

    def _log_path(self, service_id: str) -> Path:
        return self.root / f"{service_id}.log"

    def _prune(self) -> None:
        finished = sorted(
            (record for record in self._records.values() if record["id"] not in self._running),
            key=lambda item: (bool(item.get("autostart")), item.get("ended_at") or ""),
        )
        while len(self._records) > MAX_RECORDS and finished:
            record = finished.pop(0)
            self._records.pop(record["id"], None)
            with contextlib.suppress(OSError):
                self._log_path(record["id"]).unlink()

    # Lifecycle ---------------------------------------------------------------------------------

    def find(self, key: str) -> dict[str, Any]:
        """A service by id, or by name when the name is unambiguous."""
        with self._lock:
            if key in self._records:
                return self._records[key]
            named = [record for record in self._records.values() if record.get("name") == key]
            if len(named) == 1:
                return named[0]
        raise KeyError("unknown service")

    def start(
        self,
        name: str,
        argv: list[str],
        cwd: Path,
        *,
        workspace: Path,
        port: int | None = None,
        autostart: bool = False,
        source: str = "agent",
    ) -> dict[str, Any]:
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 60:
            raise ServiceError("a service needs a name of 1 to 60 characters")
        if port is not None and (type(port) is not int or not 1 <= port <= 65535):
            raise ServiceError("'port' must be a TCP port number")
        argv = validate_argv(argv)
        name = name.strip()
        with self._lock:
            existing = next(
                (record for record in self._records.values() if record.get("name") == name), None
            )
            if existing is not None and existing["id"] in self._running:
                raise ServiceError(f"service '{name}' is already running; stop it first")
            record = existing or {"id": uuid.uuid4().hex[:12], "created_at": _now()}
            record.update(
                name=name,
                argv=argv,
                cwd=str(cwd),
                workspace=str(workspace),
                port=port,
                autostart=bool(autostart),
                source=source,
            )
            self._launch(record)
            self._records[record["id"]] = record
            self._prune()
            self._save()
            return self.describe(record)

    def restart(self, key: str) -> dict[str, Any]:
        # Stop outside the lock: the follower thread needs it to record the exit.
        self.stop(key, "restarting")
        with self._lock:
            record = self.find(key)
            if record["id"] in self._running:
                raise ServiceError("the service is still stopping; try again")
            cwd = Path(record["cwd"])
            if not cwd.is_dir():
                raise ServiceError("the service's working folder no longer exists")
            self._launch(record)
            self._save()
            return self.describe(record)

    def _launch(self, record: dict[str, Any]) -> None:
        if len(self._running) >= MAX_RUNNING:
            raise ServiceError(f"at most {MAX_RUNNING} services can run at once; stop one first")
        from android_adapter.terminal import _environment

        log = self._log_path(record["id"])
        with contextlib.suppress(OSError):
            if log.stat().st_size > LOG_KEEP:
                data = log.read_bytes()[-LOG_KEEP:]
                log.write_bytes(data)
        header = f"\n--- {_now()} start: {' '.join(record['argv'])[:500]}\n".encode()
        with log.open("ab") as stream:
            stream.write(header)
        transport = self._transport
        if transport is None:
            from android_adapter.toolchain import command_transport as transport
        argv, environment, lease = transport(list(record["argv"]), Path(record["cwd"]))
        try:
            process = subprocess.Popen(
                argv,
                cwd=record["cwd"],
                env={**_environment(), **(environment or {})},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as error:
            if lease is not None:
                lease.end_process()
            raise ServiceError(f"cannot start the service: {error.strerror or error}") from error
        running = _Running(process, lease)
        self._running[record["id"]] = running
        record.update(
            state="running",
            pid=process.pid,
            pid_start=_process_start_ticks(process.pid),
            started_at=_now(),
            ended_at=None,
            exit_code=None,
            reason=None,
        )
        running.thread = threading.Thread(
            target=self._follow,
            args=(record["id"], running),
            daemon=True,
            name=f"service-{record['id']}",
        )
        running.thread.start()

    def _follow(self, service_id: str, running: _Running) -> None:
        log = self._log_path(service_id)
        process = running.process
        assert process.stdout is not None
        stream = None
        try:
            stream = log.open("ab", buffering=0)
            size = stream.tell()
            while chunk := process.stdout.read1(16 * 1024):  # type: ignore[attr-defined]
                stream.write(chunk)
                size += len(chunk)
                if size > LOG_LIMIT:
                    stream.close()
                    data = log.read_bytes()[-LOG_KEEP:]
                    log.write_bytes(data)
                    stream = log.open("ab", buffering=0)
                    size = len(data)
        except (OSError, ValueError):
            # Keep draining so a full pipe never blocks the program.
            with contextlib.suppress(OSError, ValueError):
                while process.stdout.read1(16 * 1024):  # type: ignore[attr-defined]
                    pass
        finally:
            if stream is not None:
                with contextlib.suppress(OSError):
                    stream.close()
            code = process.wait()
            _kill_group(process.pid, _SIGKILL)
            with contextlib.suppress(OSError):
                process.stdout.close()
            if running.lease is not None:
                with contextlib.suppress(Exception):
                    running.lease.end_process()
            with self._lock:
                if self._running.get(service_id) is running:
                    self._running.pop(service_id, None)
                record = self._records.get(service_id)
                if record is not None and record.get("pid") == process.pid:
                    stopped = running.stop_reason is not None
                    record.update(
                        state="stopped" if stopped else ("exited" if code == 0 else "failed"),
                        exit_code=code,
                        ended_at=_now(),
                        reason=running.stop_reason,
                        pid=None,
                        pid_start=None,
                    )
                    with contextlib.suppress(OSError):
                        self._save()

    def stop(self, key: str, reason: str = "stopped") -> dict[str, Any]:
        with self._lock:
            record = self.find(key)
            running = self._running.get(record["id"])
        if running is None:
            return self.describe(record)
        running.stop_reason = reason
        pid = running.process.pid
        _kill_group(pid, signal.SIGTERM)
        deadline = time.monotonic() + STOP_GRACE_SECONDS
        while running.process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        _kill_group(pid, _SIGKILL)
        if running.thread is not None:
            running.thread.join(timeout=STOP_GRACE_SECONDS)
        with self._lock:
            return self.describe(record)

    def stop_all(self, reason: str = "engine stopped", grace: float = 2.0) -> None:
        """Stop every service together; the engine has only a few seconds to shut down."""
        with self._lock:
            running = list(self._running.values())
        for item in running:
            item.stop_reason = reason
            _kill_group(item.process.pid, signal.SIGTERM)
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline and any(item.process.poll() is None for item in running):
            time.sleep(0.05)
        for item in running:
            _kill_group(item.process.pid, _SIGKILL)
        for item in running:
            if item.thread is not None:
                item.thread.join(timeout=1.0)

    def remove(self, key: str) -> None:
        with self._lock:
            record = self.find(key)
            if record["id"] in self._running:
                raise ServiceError("stop the service before removing it")
            self._records.pop(record["id"], None)
            with contextlib.suppress(OSError):
                self._log_path(record["id"]).unlink()
            self._save()

    def set_autostart(self, key: str, enabled: bool) -> dict[str, Any]:
        if type(enabled) is not bool:
            raise ServiceError("'enabled' must be true or false")
        with self._lock:
            record = self.find(key)
            record["autostart"] = enabled
            self._save()
            return self.describe(record)

    def set_keep_awake(self, enabled: bool) -> dict[str, Any]:
        if type(enabled) is not bool:
            raise ServiceError("'keep_awake' must be true or false")
        with self._lock:
            self._keep_awake = enabled
            self._save()
        return self.snapshot()

    def recover(self) -> list[str]:
        """End programs a previous engine left running, then start the autostart services.

        Returns the names of services that could not be started again.
        """
        failed: list[str] = []
        with self._lock:
            for record in self._records.values():
                if record["id"] in self._running or record.get("state") != "running":
                    continue
                pid, ticks = record.get("pid"), record.get("pid_start")
                if type(pid) is int and ticks is not None and _process_start_ticks(pid) == ticks:
                    _kill_group(pid, _SIGKILL)
                record.update(
                    state="interrupted",
                    reason="engine restarted",
                    ended_at=_now(),
                    pid=None,
                    pid_start=None,
                )
            for record in list(self._records.values()):
                if not record.get("autostart") or record["id"] in self._running:
                    continue
                if record.get("state") == "stopped" and record.get("reason") in DELIBERATE_STOPS:
                    continue
                try:
                    if not Path(record["cwd"]).is_dir():
                        raise ServiceError("the working folder no longer exists")
                    self._launch(record)
                except Exception as error:
                    record.update(state="failed", reason=f"autostart: {str(error)[:300]}")
                    failed.append(record["name"])
            with contextlib.suppress(OSError):
                self._save()
        return failed

    # Reading -----------------------------------------------------------------------------------

    def logs(self, key: str, max_bytes: int = 8192) -> dict[str, Any]:
        if type(max_bytes) is not int or not 1 <= max_bytes <= LOG_LIMIT:
            raise ServiceError("'max_bytes' must be from 1 to 1048576")
        record = self.find(key)
        path = self._log_path(record["id"])
        try:
            with path.open("rb") as stream:
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                stream.seek(max(0, size - max_bytes))
                data = stream.read(max_bytes)
        except OSError:
            data, size = b"", 0
        text = data.decode("utf-8", errors="replace")
        if size > max_bytes:
            # Drop the partial first line of a tail read.
            text = text.split("\n", 1)[-1]
        return {
            "id": record["id"],
            "name": record["name"],
            "state": record.get("state"),
            "text": text,
            "bytes": size,
            "truncated": size > max_bytes,
        }

    def _ports(self, record: dict[str, Any]) -> list[int]:
        ports: list[int] = []
        if type(record.get("port")) is int:
            ports.append(record["port"])
        try:
            with self._log_path(record["id"]).open("rb") as stream:
                stream.seek(0, os.SEEK_END)
                stream.seek(max(0, stream.tell() - 64 * 1024))
                tail = stream.read()
        except OSError:
            tail = b""
        for match in _URL_PORT.finditer(tail):
            if match.group(1):
                port = int(match.group(1))
                if 0 < port < 65536 and port not in ports:
                    ports.append(port)
        return ports[-3:] if len(ports) > 3 else ports

    def describe(self, record: dict[str, Any], *, probe: bool = False) -> dict[str, Any]:
        running = record["id"] in self._running
        ports = self._ports(record)
        urls = []
        for port in ports:
            if not running:
                break
            if probe and not _port_open(port):
                continue
            urls.append(f"http://127.0.0.1:{port}/")
        return {
            "id": record["id"],
            "name": record["name"],
            "argv": record["argv"],
            "cwd": record["cwd"],
            "port": record.get("port"),
            "autostart": bool(record.get("autostart")),
            "state": "running" if running else record.get("state", "stopped"),
            "exit_code": record.get("exit_code"),
            "reason": record.get("reason"),
            "created_at": record.get("created_at"),
            "started_at": record.get("started_at"),
            "ended_at": record.get("ended_at"),
            "urls": urls,
            "source": record.get("source", "agent"),
        }

    def is_running(self, key: str) -> bool:
        with self._lock:
            return key in self._running

    def status(self, key: str, *, probe: bool = False) -> dict[str, Any]:
        with self._lock:
            return self.describe(self.find(key), probe=probe)

    def snapshot(self, *, probe: bool = False) -> dict[str, Any]:
        with self._lock:
            records = sorted(
                self._records.values(),
                key=lambda item: (item["id"] not in self._running, item.get("name", "")),
            )
            services = [self.describe(record, probe=probe) for record in records]
            running = len(self._running)
        return {
            "services": services,
            "running": running,
            "max_running": MAX_RUNNING,
            "keep_awake": self._keep_awake,
        }

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {"running": len(self._running), "keep_awake": self._keep_awake}


_MANAGER: ServiceManager | None = None
_MANAGER_LOCK = threading.Lock()


def get_service_manager(data_dir: str | os.PathLike[str] | None = None) -> ServiceManager | None:
    """The process-wide manager; services must survive registry and runtime rebuilds."""
    global _MANAGER
    with _MANAGER_LOCK:
        if _MANAGER is None:
            data_dir = data_dir or os.getenv("AGENT_WORKSPACE_DATA_DIR")
            if not data_dir:
                return None
            _MANAGER = ServiceManager(data_dir)
        return _MANAGER


# Live output of a running terminal command, shown under its tool card while it runs. ---------

_LIVE_TAIL = 16 * 1024
_LIVE_KEEP_SECONDS = 120.0
_LIVE: dict[str, dict[str, Any]] = {}
_LIVE_LOCK = threading.Lock()


def live_output_open(key: str) -> Any:
    with _LIVE_LOCK:
        now = time.monotonic()
        for stale in [
            name
            for name, entry in _LIVE.items()
            if not entry["active"] and now - entry["ended"] > _LIVE_KEEP_SECONDS
        ]:
            _LIVE.pop(stale, None)
        entry = {"data": bytearray(), "bytes": 0, "active": True, "ended": 0.0}
        _LIVE[key] = entry

    def write(chunk: bytes) -> None:
        with _LIVE_LOCK:
            entry["bytes"] += len(chunk)
            data = entry["data"]
            data.extend(chunk)
            if len(data) > _LIVE_TAIL:
                del data[: len(data) - _LIVE_TAIL]

    return write


def live_output_close(key: str) -> None:
    with _LIVE_LOCK:
        entry = _LIVE.get(key)
        if entry is not None:
            entry["active"] = False
            entry["ended"] = time.monotonic()


def live_output(key: str) -> dict[str, Any] | None:
    with _LIVE_LOCK:
        entry = _LIVE.get(key)
        if entry is None:
            return None
        text = bytes(entry["data"]).decode("utf-8", errors="replace")
        if entry["bytes"] > len(entry["data"]):
            text = text.split("\n", 1)[-1]
        return {"active": entry["active"], "text": text, "bytes": entry["bytes"]}
