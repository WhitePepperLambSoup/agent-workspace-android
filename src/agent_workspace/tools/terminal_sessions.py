from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, RLock
from typing import Any
from uuid import uuid4

from agent_workspace.config import workspace_database_path
from agent_workspace.tools.paths import WorkspacePaths

_MAX_DEFAULT_OUTPUT_BYTES = 512 * 1024
_MAX_OUTPUT_BYTES = 8 * 1024 * 1024
_MAX_ARGUMENTS = 256
_MAX_ARGUMENT_CHARS = 32_767
_STATE_LOCKS: dict[Path, RLock] = {}
_STATE_LOCKS_GUARD = Lock()


def _state_file_lock(path: Path) -> RLock:
    with _STATE_LOCKS_GUARD:
        return _STATE_LOCKS.setdefault(path.expanduser().resolve(), RLock())


class TerminalSessionError(RuntimeError):
    """Stable error raised for invalid terminal session operations."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


@dataclass(frozen=True, slots=True)
class TerminalResult:
    session_id: str
    state: str
    output: str
    exit_code: int | None
    truncated: bool = False
    exit_reason: str | None = None
    offset: int = 0
    next_offset: int = 0
    eof: bool = False


class TerminalSession:
    """One durable interactive subprocess with bounded replayable output."""

    def __init__(
        self,
        *,
        session_id: str,
        workspace: Path,
        argv: Sequence[str],
        process: asyncio.subprocess.Process,
        max_output_bytes: int,
        autonomy: str,
        deadline: float | None,
        event_sink: Callable[[dict[str, object]], None] | None,
        process_group: int,
        owner: str | None = None,
        state_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.session_id = session_id
        self.workspace = workspace
        self.argv = tuple(argv)
        self.process = process
        self.max_output_bytes = max_output_bytes
        self.autonomy = autonomy
        self.deadline = deadline
        self.process_group = process_group
        self.owner = owner
        self._event_sink = event_sink
        self._state_sink = state_sink
        self._output = bytearray()
        self._total_output_bytes = 0
        self._truncated = False
        self._state = "running"
        self._exit_reason: str | None = None
        self._exit_code: int | None = None
        self._columns: int | None = None
        self._rows: int | None = None
        self._lock = asyncio.Lock()
        self._reader_task = asyncio.create_task(self._read_output())
        self._wait_task = asyncio.create_task(self._watch_exit())
        self._deadline_task: asyncio.Task[None] | None = None
        if deadline is not None:
            self._deadline_task = asyncio.create_task(self._watch_deadline(deadline))

    @property
    def state(self) -> str:
        return self._state

    @property
    def exit_reason(self) -> str | None:
        return self._exit_reason

    @property
    def output_offset(self) -> int:
        return self._total_output_bytes

    def _emit(self, event_type: str, **payload: object) -> None:
        if self._event_sink is None:
            return
        event = {"type": event_type, "sessionId": self.session_id, **payload}
        try:
            self._event_sink(event)
        except Exception:
            # Event observers must not be able to terminate the subprocess.
            return

    async def _read_output(self) -> None:
        stream = self.process.stdout
        if stream is None:
            return
        while True:
            chunk = await stream.read(64 * 1024)
            if not chunk:
                break
            async with self._lock:
                if len(chunk) >= self.max_output_bytes:
                    self._output[:] = chunk[-self.max_output_bytes :]
                    self._truncated = True
                else:
                    combined = self._output + chunk
                    if len(combined) > self.max_output_bytes:
                        self._output[:] = combined[-self.max_output_bytes :]
                        self._truncated = True
                    else:
                        self._output[:] = combined
                chunk_start = self._total_output_bytes
                self._total_output_bytes += len(chunk)
                text = chunk.decode("utf-8", errors="replace")
                self._emit(
                    "terminal.output",
                    output=text,
                    offset=chunk_start,
                    nextOffset=self._total_output_bytes,
                    truncated=self._truncated,
                    bytes=len(self._output),
                )
                self._persist()

    async def _watch_exit(self) -> None:
        code = await self.process.wait()
        with contextlib.suppress(asyncio.CancelledError):
            await self._reader_task
        async with self._lock:
            self._exit_code = code
            if self._state == "running":
                self._state = "exited"
                if self._exit_reason is None:
                    self._exit_reason = "completed" if code == 0 else "process_exit"
            self._emit(
                "terminal.exited",
                state=self._state,
                exitCode=self._exit_code,
                reason=self._exit_reason,
                truncated=self._truncated,
            )
            self._persist()

    async def _watch_deadline(self, deadline: float) -> None:
        try:
            await asyncio.sleep(deadline)
            if self.state == "running":
                await self.stop(reason="timeout")
        except asyncio.CancelledError:
            return

    async def write(self, data: str, *, owner: str | None = None) -> None:
        self._check_owner(owner)
        if not isinstance(data, str) or "\x00" in data:
            raise TerminalSessionError("invalid_input", "terminal input must be text without NUL")
        async with self._lock:
            if self._state != "running" or self.process.stdin is None:
                raise TerminalSessionError(
                    "terminal_exited",
                    "terminal_exited: terminal session has exited",
                )
            stdin = self.process.stdin
            stdin.write(data.encode("utf-8"))
        try:
            await stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as exc:
            raise TerminalSessionError(
                "terminal_exited",
                "terminal_exited: terminal session has exited",
            ) from exc

    async def write_as(self, data: str, *, owner: str | None = None) -> None:
        await self.write(data, owner=owner)

    async def resize(
        self,
        columns: int,
        rows: int,
        *,
        owner: str | None = None,
    ) -> None:
        self._check_owner(owner)
        if type(columns) is not int or not 1 <= columns <= 1000:
            raise TerminalSessionError("invalid_resize", "terminal columns are invalid")
        if type(rows) is not int or not 1 <= rows <= 1000:
            raise TerminalSessionError("invalid_resize", "terminal rows are invalid")
        async with self._lock:
            if self._state != "running":
                raise TerminalSessionError("terminal_exited", "terminal session has exited")
            self._columns = columns
            self._rows = rows
            self._emit("terminal.resize", columns=columns, rows=rows)
            self._persist()

    async def stop(self, *, reason: str = "stopped") -> TerminalResult:
        async with self._lock:
            if self._state != "running":
                return self.replay()
            self._state = "stopped"
            self._exit_reason = reason
            self._persist()
        if self._deadline_task is not None:
            self._deadline_task.cancel()
        await _terminate_process_tree(self.process, self.process_group)
        await self._wait_task
        return self.replay()

    async def wait(self) -> TerminalResult:
        await self._wait_task
        return self.replay()

    def replay(self, offset: int = 0, *, max_bytes: int | None = None) -> TerminalResult:
        if type(offset) is not int or offset < 0:
            raise TerminalSessionError("invalid_offset", "terminal replay offset is invalid")
        if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 1):
            raise TerminalSessionError("invalid_output_limit", "terminal replay limit is invalid")
        raw = bytes(self._output)
        buffer_start = self._total_output_bytes - len(raw)
        effective_offset = max(offset, buffer_start)
        start = max(0, effective_offset - buffer_start)
        selected = raw[start:]
        if max_bytes is not None:
            selected = selected[:max_bytes]
        output = selected.decode("utf-8", errors="replace")
        next_offset = effective_offset + len(selected)
        return TerminalResult(
            session_id=self.session_id,
            state=self._state,
            output=output,
            exit_code=self._exit_code,
            truncated=self._truncated or offset < buffer_start,
            exit_reason=self._exit_reason,
            offset=effective_offset,
            next_offset=next_offset,
            eof=self._state != "running" and next_offset >= self._total_output_bytes,
        )

    async def aclose(self) -> None:
        if self._state == "running":
            await self.stop(reason="registry_closed")
        for task in (self._reader_task, self._wait_task, self._deadline_task):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(
            self._reader_task,
            self._wait_task,
            *(task for task in (self._deadline_task,) if task is not None),
            return_exceptions=True,
        )

    def _check_owner(self, owner: str | None) -> None:
        if self.owner is not None and owner != self.owner:
            raise TerminalSessionError(
                "terminal_owner",
                "terminal_owner: terminal session belongs to another owner",
            )

    def _persist(self) -> None:
        if self._state_sink is None:
            return
        try:
            self._state_sink(self.to_document())
        except Exception:
            return

    def to_document(self) -> dict[str, object]:
        replay = self.replay()
        return {
            "sessionId": self.session_id,
            "state": self._state,
            "workspace": str(self.workspace),
            "argv": list(self.argv),
            "owner": self.owner,
            "output": replay.output,
            "outputOffset": replay.offset,
            "nextOffset": replay.next_offset,
            "truncated": replay.truncated,
            "exitCode": self._exit_code,
            "exitReason": self._exit_reason,
            "eof": replay.eof,
            "columns": self._columns,
            "rows": self._rows,
        }


async def _terminate_process_tree(
    process: asyncio.subprocess.Process,
    process_group: int,
) -> None:
    if process.returncode is not None:
        return
    if os.name == "nt":
        # taskkill /T is the most reliable tree kill for a Windows process group
        # when the child has launched a console shim or another interpreter.
        proc = await asyncio.create_subprocess_exec(
            "taskkill",
            "/PID",
            str(process.pid),
            "/T",
            "/F",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await proc.wait()
    else:
        kill_group = getattr(os, "killpg", None)
        sigterm = getattr(signal, "SIGTERM", signal.SIGINT)
        sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
        if callable(kill_group):
            with contextlib.suppress(ProcessLookupError):
                kill_group(process_group, sigterm)
        try:
            await asyncio.wait_for(process.wait(), timeout=1.0)
        except TimeoutError:
            if callable(kill_group):
                with contextlib.suppress(ProcessLookupError):
                    kill_group(process_group, sigkill)
    if process.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(process.wait(), timeout=2.0)


class TerminalSessionRegistry:
    def __init__(
        self,
        workspace: str | Path,
        *,
        event_sink: Callable[[dict[str, object]], None] | None = None,
        state_path: str | Path | None = None,
        reconcile_on_start: bool = True,
    ) -> None:
        self.paths = WorkspacePaths(workspace)
        self.event_sink = event_sink
        self.state_path = (
            Path(state_path)
            if state_path is not None
            else workspace_database_path(self.paths.root).with_suffix(".terminals.json")
        )
        self._state_lock = _state_file_lock(self.state_path)
        self._sessions: dict[str, TerminalSession] = {}
        self._records: dict[str, dict[str, object]] = self._load_records()
        self._dirty_record_ids: set[str] = set()
        if state_path is None and not self.state_path.exists():
            legacy_path = self.paths.root / ".agent" / "terminal-registry.json"
            if legacy_path.is_file():
                self._records = self._load_records(legacy_path)
                self._dirty_record_ids.update(self._records)
                if self._records and self._save_records():
                    with contextlib.suppress(OSError):
                        legacy_path.unlink()
        if reconcile_on_start:
            self.reconcile()

    def reconcile(self) -> None:
        """Recover saved processes once, before a workspace's live owners start."""
        with self._state_lock:
            self._refresh_records()
            for session_id, record in self._records.items():
                if record.get("state") == "running":
                    record["state"] = "orphaned"
                    record["exitReason"] = "runtime_restarted"
                    record["eof"] = True
                    self._dirty_record_ids.add(session_id)
            if self._dirty_record_ids:
                self._save_records()

    async def start(
        self,
        argv: Sequence[str],
        *,
        cwd: str = ".",
        autonomy: str = "workspace",
        deadline: float | None = None,
        max_output_bytes: int = _MAX_DEFAULT_OUTPUT_BYTES,
        owner: str | None = None,
    ) -> TerminalSession:
        if not argv or len(argv) > _MAX_ARGUMENTS:
            raise TerminalSessionError("invalid_argv", "terminal argv is empty or too large")
        if any(not isinstance(item, str) or not item or "\x00" in item for item in argv):
            raise TerminalSessionError("invalid_argv", "terminal argv contains an invalid item")
        if any(len(item) > _MAX_ARGUMENT_CHARS for item in argv):
            raise TerminalSessionError("invalid_argv", "terminal argv item is too long")
        if type(max_output_bytes) is not int or not 1 <= max_output_bytes <= _MAX_OUTPUT_BYTES:
            raise TerminalSessionError("invalid_output_limit", "terminal output limit is invalid")
        owner = _validate_owner(owner)
        working_directory = self.paths.resolve(cwd)
        if not working_directory.is_dir():
            raise TerminalSessionError(
                "invalid_cwd",
                "terminal working directory is not a directory",
            )
        kwargs: dict[str, Any] = {
            "cwd": str(working_directory),
            "stdin": asyncio.subprocess.PIPE,
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.STDOUT,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        try:
            process = await asyncio.create_subprocess_exec(*argv, **kwargs)
        except (OSError, ValueError) as exc:
            raise TerminalSessionError("terminal_start_failed", str(exc)) from exc
        session_id = str(uuid4())
        process_group = int(process.pid)
        session = TerminalSession(
            session_id=session_id,
            workspace=working_directory,
            argv=argv,
            process=process,
            max_output_bytes=max_output_bytes,
            autonomy=str(autonomy),
            deadline=deadline,
            event_sink=self.event_sink,
            process_group=process_group,
            owner=owner,
            state_sink=self._record_session,
        )
        self._sessions[session_id] = session
        self._record_session(session.to_document())
        session._emit(
            "terminal.start",
            workspace=str(self.paths.root),
            cwd=str(working_directory),
            argv=list(argv),
            autonomy=str(autonomy),
            deadline=deadline,
            processGroup=process_group,
        )
        return session

    def get(self, session_id: str) -> TerminalSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise TerminalSessionError(
                "terminal_not_found",
                "terminal session was not found",
            ) from exc

    def status(self, session_id: str) -> dict[str, object]:
        session = self._sessions.get(session_id)
        if session is not None:
            return session.to_document()
        with self._state_lock:
            self._refresh_records()
            record = self._records.get(session_id)
            if record is None:
                raise TerminalSessionError("terminal_not_found", "terminal session was not found")
            return dict(record)

    def list(self) -> tuple[dict[str, object], ...]:
        with self._state_lock:
            self._refresh_records()
            records = dict(self._records)
        records.update(
            {session_id: session.to_document() for session_id, session in self._sessions.items()}
        )
        return tuple(dict(record) for record in records.values())

    def replay(
        self,
        session_id: str,
        *,
        offset: int = 0,
        max_bytes: int | None = None,
    ) -> TerminalResult:
        session = self._sessions.get(session_id)
        if session is not None:
            return session.replay(offset, max_bytes=max_bytes)
        record = self.status(session_id)
        if type(offset) is not int or offset < 0:
            raise TerminalSessionError("invalid_offset", "terminal replay offset is invalid")
        raw_output = record.get("output")
        output = raw_output if isinstance(raw_output, str) else ""
        base_offset = record.get("outputOffset")
        next_offset = record.get("nextOffset")
        base_offset = base_offset if type(base_offset) is int and base_offset >= 0 else 0
        next_offset = (
            next_offset
            if type(next_offset) is int and next_offset >= base_offset
            else base_offset + len(output.encode())
        )
        effective = max(offset, base_offset)
        selected = output.encode("utf-8")[max(0, effective - base_offset) :]
        if max_bytes is not None:
            if type(max_bytes) is not int or max_bytes < 1:
                raise TerminalSessionError(
                    "invalid_output_limit", "terminal replay limit is invalid"
                )
            selected = selected[:max_bytes]
        raw_exit_code = record.get("exitCode")
        exit_code = raw_exit_code if isinstance(raw_exit_code, int) else None
        raw_exit_reason = record.get("exitReason")
        exit_reason = raw_exit_reason if isinstance(raw_exit_reason, str) else None
        return TerminalResult(
            session_id=session_id,
            state=str(record.get("state") or "orphaned"),
            output=selected.decode("utf-8", errors="replace"),
            exit_code=exit_code,
            truncated=record.get("truncated") is True or offset < base_offset,
            exit_reason=exit_reason,
            offset=effective,
            next_offset=effective + len(selected),
            eof=record.get("eof") is True and effective + len(selected) >= next_offset,
        )

    async def write(self, session_id: str, data: str, *, owner: str | None = None) -> None:
        await self.get(session_id).write(data, owner=owner)

    async def resize(
        self,
        session_id: str,
        columns: int,
        rows: int,
        *,
        owner: str | None = None,
    ) -> None:
        await self.get(session_id).resize(columns, rows, owner=owner)

    async def stop(
        self,
        session_id: str,
        *,
        reason: str = "stopped",
        owner: str | None = None,
    ) -> TerminalResult:
        session = self.get(session_id)
        session._check_owner(owner)
        return await session.stop(reason=reason)

    async def aclose(self) -> None:
        await asyncio.gather(*(session.aclose() for session in self._sessions.values()))
        for session in self._sessions.values():
            self._record_session(session.to_document())
        self._sessions.clear()

    def _record_session(self, record: dict[str, object]) -> None:
        session_id = record.get("sessionId")
        if not isinstance(session_id, str) or not session_id:
            return
        with self._state_lock:
            self._records[session_id] = dict(record)
            self._dirty_record_ids.add(session_id)
            self._save_records()

    def _refresh_records(self) -> None:
        records = self._load_records()
        records.update(
            {
                session_id: self._records[session_id]
                for session_id in self._dirty_record_ids
                if session_id in self._records
            }
        )
        self._records = records

    def _load_records(self, path: Path | None = None) -> dict[str, dict[str, object]]:
        try:
            raw = json.loads((path or self.state_path).read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        records = raw.get("sessions") if isinstance(raw, dict) else None
        if not isinstance(records, dict):
            return {}
        return {
            str(session_id): dict(record)
            for session_id, record in records.items()
            if isinstance(session_id, str) and isinstance(record, dict)
        }

    def _save_records(self) -> bool:
        with self._state_lock:
            # Each host updates only its changed records; a stale peer snapshot
            # must never erase newer output or other conversations' terminals.
            self._refresh_records()
            try:
                self.state_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
                temporary.write_text(
                    json.dumps(
                        {"sessions": self._records}, ensure_ascii=False, separators=(",", ":")
                    ),
                    encoding="utf-8",
                )
                temporary.replace(self.state_path)
            except OSError:
                return False
            self._dirty_record_ids.clear()
            return True


async def start_terminal_session(
    workspace: str | Path,
    argv: Sequence[str],
    *,
    cwd: str = ".",
    autonomy: str = "workspace",
    deadline: float | None = None,
    max_output_bytes: int = _MAX_DEFAULT_OUTPUT_BYTES,
    event_sink: Callable[[dict[str, object]], None] | None = None,
    owner: str | None = None,
    state_path: str | Path | None = None,
) -> TerminalSession:
    registry = TerminalSessionRegistry(workspace, event_sink=event_sink, state_path=state_path)
    session = await registry.start(
        argv,
        cwd=cwd,
        autonomy=autonomy,
        deadline=deadline,
        max_output_bytes=max_output_bytes,
        owner=owner,
    )
    # Keep the registry attached so the convenience API remains alive until the
    # caller has stopped/waited the session. A wait/stop closes the registry later.
    session._registry = registry  # type: ignore[attr-defined]
    return session


def _validate_owner(owner: str | None) -> str | None:
    if owner is None:
        return None
    if not isinstance(owner, str) or not owner.strip() or len(owner) > 128:
        raise TerminalSessionError("invalid_owner", "terminal owner is invalid")
    return owner.strip()
