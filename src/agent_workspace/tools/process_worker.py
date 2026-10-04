from __future__ import annotations

import asyncio
import contextlib
import ctypes
import multiprocessing
import os
import pickle
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Any, cast

from agent_workspace.tools.base import ToolError

_POLL_SECONDS = 0.01
_TERMINATE_SECONDS = 2.0
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
_JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
_JOB_OBJECT_LIMIT_JOB_TIME = 0x00000004
_JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
_JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
_JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_WORKER_CPU_SECONDS = 130
_WORKER_MEMORY_BYTES = 768 * 1024 * 1024
_COMMAND_ACTIVE_PROCESSES = 64
_COMMAND_PROCESS_MEMORY_BYTES = 1024 * 1024 * 1024
_COMMAND_JOB_MEMORY_BYTES = 2 * 1024 * 1024 * 1024
_COMMAND_JOB_CPU_SECONDS = 300
_PROCESS_TERMINATE = 0x0001
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_TOOL_WORKER_ARGUMENT = "--agent-workspace-tool-worker"
_MAX_WORKER_MESSAGE_BYTES = 16 * 1024 * 1024


def _active_process_limit(*, allow_children: bool) -> int:
    if allow_children:
        return _COMMAND_ACTIVE_PROCESSES
    # Windows launchers may need one short-lived shim process before the Python
    # payload starts (virtualenv and frozen launchers both do this). Keep the
    # worker tree bounded while allowing that payload to initialize.
    return 2


class ToolWorkerError(ToolError):
    pass


class ToolWorkerPreconditionError(ToolWorkerError):
    pass


class _JobBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("per_process_user_time_limit", ctypes.c_int64),
        ("per_job_user_time_limit", ctypes.c_int64),
        ("limit_flags", ctypes.c_uint32),
        ("minimum_working_set_size", ctypes.c_size_t),
        ("maximum_working_set_size", ctypes.c_size_t),
        ("active_process_limit", ctypes.c_uint32),
        ("affinity", ctypes.c_size_t),
        ("priority_class", ctypes.c_uint32),
        ("scheduling_class", ctypes.c_uint32),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("read_operation_count", ctypes.c_uint64),
        ("write_operation_count", ctypes.c_uint64),
        ("other_operation_count", ctypes.c_uint64),
        ("read_transfer_count", ctypes.c_uint64),
        ("write_transfer_count", ctypes.c_uint64),
        ("other_transfer_count", ctypes.c_uint64),
    ]


class _JobExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("basic_limit_information", _JobBasicLimitInformation),
        ("io_info", _IoCounters),
        ("process_memory_limit", ctypes.c_size_t),
        ("job_memory_limit", ctypes.c_size_t),
        ("peak_process_memory_used", ctypes.c_size_t),
        ("peak_job_memory_used", ctypes.c_size_t),
    ]


class _WindowsJob:
    def __init__(self, *, allow_children: bool = False) -> None:
        kernel32: Any = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        kernel32.SetInformationJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        kernel32.SetInformationJobObject.restype = ctypes.c_int
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel32.AssignProcessToJobObject.restype = ctypes.c_int
        kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.TerminateJobObject.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise _windows_worker_error("CreateJobObjectW")
        self._kernel32 = kernel32
        self._handle: int | None = cast(int, handle)
        information = _JobExtendedLimitInformation()
        information.basic_limit_information.limit_flags = (
            _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | _JOB_OBJECT_LIMIT_PROCESS_TIME
            | _JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | _JOB_OBJECT_LIMIT_JOB_MEMORY
        )
        information.basic_limit_information.active_process_limit = _active_process_limit(
            allow_children=allow_children
        )
        information.basic_limit_information.per_process_user_time_limit = (
            _WORKER_CPU_SECONDS * 10_000_000
        )
        information.process_memory_limit = (
            _COMMAND_PROCESS_MEMORY_BYTES if allow_children else _WORKER_MEMORY_BYTES
        )
        information.job_memory_limit = (
            _COMMAND_JOB_MEMORY_BYTES if allow_children else _WORKER_MEMORY_BYTES
        )
        if allow_children:
            information.basic_limit_information.limit_flags |= _JOB_OBJECT_LIMIT_JOB_TIME
            information.basic_limit_information.per_job_user_time_limit = (
                _COMMAND_JOB_CPU_SECONDS * 10_000_000
            )
        if not kernel32.SetInformationJobObject(
            handle,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            self.close()
            raise _windows_worker_error("SetInformationJobObject")

    def assign(self, process_id: int) -> None:
        handle = self._handle
        if handle is None:
            raise ToolWorkerError("Windows tool worker Job Object is closed")
        process_handle = self._kernel32.OpenProcess(
            _PROCESS_TERMINATE | _PROCESS_SET_QUOTA | _PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            process_id,
        )
        if not process_handle:
            raise _windows_worker_error("OpenProcess")
        try:
            if not self._kernel32.AssignProcessToJobObject(handle, process_handle):
                raise _windows_worker_error("AssignProcessToJobObject")
        finally:
            self._kernel32.CloseHandle(process_handle)

    def terminate(self) -> None:
        if self._handle is not None:
            self._kernel32.TerminateJobObject(self._handle, 1)

    def close(self) -> None:
        handle = self._handle
        if handle is not None:
            self._handle = None
            self._kernel32.CloseHandle(handle)


async def run_in_process[T](
    function: Callable[..., T],
    *arguments: Any,
    allow_children: bool = False,
) -> T:
    if os.name == "nt":
        return await _run_windows_worker_subprocess(
            function,
            arguments,
            allow_children=allow_children,
        )
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    task_receive, task_send = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker_entry,
        args=(send, task_receive),
        name="agent-workspace-tool",
        daemon=False,
    )
    try:
        process.start()
        task_receive.close()
        task_send.send((function, arguments))
        task_send.close()
    except BaseException:
        if process.pid is not None and process.is_alive():
            process.kill()
            process.join(timeout=_TERMINATE_SECONDS)
        process.close()
        receive.close()
        send.close()
        task_receive.close()
        task_send.close()
        raise
    send.close()
    received = False
    try:
        while True:
            if receive.poll():
                raw_message = receive.recv()
                received = True
                return cast(T, _worker_result(raw_message))
            if not process.is_alive():
                if receive.poll():
                    raw_message = receive.recv()
                    received = True
                    return cast(T, _worker_result(raw_message))
                raise ToolWorkerError(
                    f"tool worker exited without a result (exit_code={process.exitcode})"
                )
            await asyncio.sleep(_POLL_SECONDS)
    finally:
        receive.close()
        process.join(timeout=0.05 if received else 0)
        if process.is_alive():
            _terminate_process_tree(process, None)
        process.close()


def _worker_command() -> tuple[str, ...]:
    if getattr(sys, "frozen", False):
        return (sys.executable, _TOOL_WORKER_ARGUMENT)
    return (
        sys.executable,
        "-m",
        "agent_workspace.ui_gateway",
        _TOOL_WORKER_ARGUMENT,
    )


async def _run_windows_worker_subprocess[T](
    function: Callable[..., T],
    arguments: tuple[Any, ...],
    *,
    allow_children: bool,
) -> T:
    payload = pickle.dumps((function, arguments), protocol=pickle.HIGHEST_PROTOCOL)
    if len(payload) > _MAX_WORKER_MESSAGE_BYTES:
        raise ToolWorkerError("tool worker request is too large")
    job = _WindowsJob(allow_children=allow_children)
    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            *_worker_command(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        assert process.pid is not None
        assert process.stdin is not None
        assert process.stdout is not None
        job.assign(process.pid)
        process.stdin.write(len(payload).to_bytes(8, "big") + payload)
        await process.stdin.drain()
        process.stdin.close()
        await process.stdin.wait_closed()
        header = await process.stdout.readexactly(8)
        size = int.from_bytes(header, "big")
        if size > _MAX_WORKER_MESSAGE_BYTES:
            raise ToolWorkerError("tool worker response is too large")
        raw_message = await process.stdout.readexactly(size)
        return cast(T, _worker_result(pickle.loads(raw_message)))
    except asyncio.IncompleteReadError as exc:
        return_code = None if process is None else process.returncode
        stderr = ""
        if process is not None and process.stderr is not None:
            stderr = (await process.stderr.read(4096)).decode("utf-8", errors="replace")
        detail = f": {' '.join(stderr.split())[:1000]}" if stderr else ""
        raise ToolWorkerError(
            f"tool worker exited without a result (exit_code={return_code}){detail}"
        ) from exc
    finally:
        if process is not None and process.returncode is None:
            job.terminate()
            with contextlib.suppress(ProcessLookupError, TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=_TERMINATE_SECONDS)
            if process.returncode is None:
                process.kill()
                with contextlib.suppress(ProcessLookupError):
                    await process.wait()
        job.close()


def run_serialized_tool_worker() -> int:
    try:
        header = _read_exact(sys.stdin.buffer, 8)
        size = int.from_bytes(header, "big")
        if size > _MAX_WORKER_MESSAGE_BYTES:
            raise ToolWorkerError("tool worker request is too large")
        task = pickle.loads(_read_exact(sys.stdin.buffer, size))
        if (
            not isinstance(task, tuple)
            or len(task) != 2
            or not callable(task[0])
            or not isinstance(task[1], tuple)
        ):
            raise ToolWorkerError("tool worker received an invalid task")
        function, arguments = task
        result: tuple[object, ...] = ("ok", function(*arguments))
    except BaseException as exc:
        message = " ".join(str(exc).split())[:1000]
        result = ("error", type(exc).__name__, message)
    response = pickle.dumps(result, protocol=pickle.HIGHEST_PROTOCOL)
    sys.stdout.buffer.write(len(response).to_bytes(8, "big") + response)
    sys.stdout.buffer.flush()
    return 0


def _read_exact(stream: Any, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = stream.read(remaining)
        if not isinstance(chunk, bytes) or not chunk:
            raise ToolWorkerError("tool worker received an incomplete message")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _worker_entry(
    connection: Connection,
    task_gate: Connection,
) -> None:
    if os.name != "nt":
        platform_os = cast(Any, os)
        platform_os.setsid()
    try:
        task = task_gate.recv()
        if (
            not isinstance(task, tuple)
            or len(task) != 2
            or not callable(task[0])
            or not isinstance(task[1], tuple)
        ):
            raise ToolWorkerError("tool worker received an invalid task")
        function, arguments = task
        result = function(*arguments)
        connection.send(("ok", result))
    except BaseException as exc:
        message = " ".join(str(exc).split())[:1000]
        connection.send(("error", type(exc).__name__, message))
    finally:
        task_gate.close()
        connection.close()


def _worker_result(message: object) -> object:
    if isinstance(message, tuple) and len(message) == 2 and message[0] == "ok":
        return message[1]
    if (
        isinstance(message, tuple)
        and len(message) == 3
        and message[0] == "error"
        and isinstance(message[1], str)
        and isinstance(message[2], str)
    ):
        detail = f": {message[2]}" if message[2] else ""
        error_type = message[1]
        error = f"tool worker failed ({error_type}){detail}"
        if error_type == "ConcurrentModificationError":
            raise ToolWorkerPreconditionError(error)
        raise ToolWorkerError(error)
    raise ToolWorkerError("tool worker returned an invalid result envelope")


def _terminate_process_tree(process: BaseProcess, job: _WindowsJob | None) -> None:
    if process.pid is None:
        return
    if job is not None:
        job.terminate()
    else:
        platform_os = cast(Any, os)
        platform_signal = cast(Any, signal)
        with contextlib.suppress(OSError):
            platform_os.killpg(process.pid, platform_signal.SIGKILL)
    process.join(timeout=_TERMINATE_SECONDS)
    if process.is_alive():
        process.kill()
        process.join(timeout=_TERMINATE_SECONDS)


def terminate_process_tree_pid(pid: int, *, timeout: float = _TERMINATE_SECONDS) -> None:
    """Terminate a native process and its descendants.

    Tool workers use ``BaseProcess`` and a Windows Job Object, while persistent
    terminal sessions own a ``subprocess.Popen``.  Keep the tree-kill policy in
    one small helper so both paths use the same bounded cleanup behavior.
    """
    if type(pid) is not int or pid <= 0:
        raise ValueError("process id must be a positive integer")
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(
            ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            creationflags=creationflags,
        )
        if completed.returncode not in {0, 128}:
            raise ToolWorkerError("process tree termination failed")
        return
    platform_os = cast(Any, os)
    platform_signal = cast(Any, signal)
    with contextlib.suppress(OSError):
        platform_os.killpg(pid, platform_signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(min(_POLL_SECONDS, max(0.0, deadline - time.monotonic())))
    with contextlib.suppress(OSError):
        platform_os.killpg(pid, platform_signal.SIGKILL)


def _windows_worker_error(operation: str) -> ToolWorkerError:
    error_code = ctypes.get_last_error()
    return ToolWorkerError(f"{operation} failed for tool worker (winerror={error_code})")
