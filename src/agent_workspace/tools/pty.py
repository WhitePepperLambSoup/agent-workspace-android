from __future__ import annotations

import asyncio
import contextlib
import ctypes
import os
import subprocess
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import (
    ToolArgumentError,
    ToolError,
    json_result,
    optional_int,
)
from agent_workspace.tools.paths import StrPath, WorkspacePaths
from agent_workspace.tools.process_worker import terminate_process_tree_pid

_MAX_OUTPUT_BYTES = 512 * 1024
_MAX_INPUT_CHARS = 100_000
_MAX_ARGUMENTS = 256
_MAX_ARGUMENT_CHARS = 32_767
_STILL_ACTIVE = 259
_CREATE_UNICODE_ENVIRONMENT = 0x00000400

_PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
_EXTENDED_STARTUPINFO_PRESENT = 0x00080000
_STARTF_USESTDHANDLES = 0x00000100


def spawn_terminal_process(
    paths: WorkspacePaths,
    argv: list[str],
    raw_cwd: str = ".",
) -> subprocess.Popen[bytes]:
    """Start a long-lived pipe-backed terminal process.

    ConPTY remains the implementation used by the one-shot ``run_terminal``
    tool.  Persistent sessions use ordinary pipes so stdin, output replay and
    bounded lifecycle control work on every supported host, with a process
    group/job tree attached for cleanup.
    """
    cwd = paths.resolve(raw_cwd)
    if not cwd.is_dir():
        raise ToolError(f"terminal working directory is not a directory: {cwd}")
    options: dict[str, Any] = {
        "cwd": str(cwd),
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "bufsize": 0,
    }
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "CREATE_NO_WINDOW", 0
        )
    else:
        options["start_new_session"] = True
    return subprocess.Popen(argv, **options)


def terminate_terminal_process(process: subprocess.Popen[bytes]) -> None:
    """Terminate a persistent terminal process and its process tree."""
    if process.poll() is not None:
        return
    pid = process.pid
    if type(pid) is int and pid > 0:
        terminate_process_tree_pid(pid)
    if process.poll() is None:
        with contextlib.suppress(ProcessLookupError):
            process.kill()


_LPPROC_THREAD_ATTRIBUTE_LIST = ctypes.c_void_p
_LPHANDLE = ctypes.POINTER(wintypes.HANDLE)
_LPDWORD = ctypes.POINTER(wintypes.DWORD)


class _COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [
        ("StartupInfo", _STARTUPINFOW),
        ("lpAttributeList", _LPPROC_THREAD_ATTRIBUTE_LIST),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoCounters", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryLimit", ctypes.c_size_t),
        ("PeakJobMemoryLimit", ctypes.c_size_t),
    ]


def _load_kernel32() -> Any:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreatePipe.argtypes = [_LPHANDLE, _LPHANDLE, ctypes.c_void_p, wintypes.DWORD]
    kernel32.CreatePipe.restype = wintypes.BOOL
    kernel32.CreatePseudoConsole.argtypes = [
        _COORD,
        wintypes.HANDLE,
        wintypes.HANDLE,
        wintypes.DWORD,
        _LPHANDLE,
    ]
    kernel32.CreatePseudoConsole.restype = ctypes.c_long
    kernel32.InitializeProcThreadAttributeList.argtypes = [
        _LPPROC_THREAD_ATTRIBUTE_LIST,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    kernel32.UpdateProcThreadAttribute.argtypes = [
        _LPPROC_THREAD_ATTRIBUTE_LIST,
        wintypes.DWORD,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL
    kernel32.DeleteProcThreadAttributeList.argtypes = [_LPPROC_THREAD_ATTRIBUTE_LIST]
    kernel32.DeleteProcThreadAttributeList.restype = None
    kernel32.ClosePseudoConsole.argtypes = [wintypes.HANDLE]
    kernel32.ClosePseudoConsole.restype = None
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, _LPDWORD]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    if hasattr(kernel32, "CreateJobObjectW"):
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    if hasattr(kernel32, "SetInformationJobObject"):
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
    if hasattr(kernel32, "AssignProcessToJobObject"):
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    if hasattr(kernel32, "TerminateJobObject"):
        kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.PeekNamedPipe.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
        _LPDWORD,
        ctypes.c_void_p,
    ]
    kernel32.PeekNamedPipe.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        _LPDWORD,
        ctypes.c_void_p,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        _LPDWORD,
        ctypes.c_void_p,
    ]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    return kernel32


def _clean_environment_block() -> Any:
    system_root = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR")
    if system_root:
        path_value = os.pathsep.join((str(Path(system_root) / "System32"), str(Path(system_root))))
    else:
        path_value = os.defpath
    values = {
        "CI": "1",
        "NO_COLOR": "1",
        "PATH": path_value,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }
    for name in ("SystemDrive", "SystemRoot", "WINDIR", "PATHEXT", "COMSPEC", "TEMP", "TMP"):
        value = os.environ.get(name)
        if value:
            values[name] = value
    block = "".join(f"{name}={value}\0" for name, value in values.items()) + "\0"
    return ctypes.create_unicode_buffer(block)


def _close(kernel32: Any, *handles: Any) -> None:
    for handle in handles:
        if handle:
            kernel32.CloseHandle(handle)


def _conpty_sync(
    workspace: str,
    argv: list[str],
    raw_cwd: str,
    timeout_seconds: int,
    startup_input: str = "",
) -> str:
    if os.name != "nt":
        raise ToolError("interactive ConPTY execution is only available on Windows")
    paths = WorkspacePaths(workspace)
    cwd = paths.resolve(raw_cwd)
    if not cwd.is_dir():
        raise ToolError(f"terminal working directory is not a directory: {cwd}")
    kernel32 = _load_kernel32()

    read_handle = wintypes.HANDLE()
    write_handle = wintypes.HANDLE()
    input_read = wintypes.HANDLE()
    input_write = wintypes.HANDLE()
    pseudo_console = wintypes.HANDLE()
    process_info = _PROCESS_INFORMATION()
    process_started = False
    attribute_list: Any = None
    try:
        if not kernel32.CreatePipe(ctypes.byref(read_handle), ctypes.byref(write_handle), None, 0):
            raise ToolError("cannot create ConPTY pipe")
        if not kernel32.CreatePipe(ctypes.byref(input_read), ctypes.byref(input_write), None, 0):
            raise ToolError("cannot create ConPTY input pipe")
        created = kernel32.CreatePseudoConsole(
            _COORD(120, 40),
            input_read,
            write_handle,
            0,
            ctypes.byref(pseudo_console),
        )
        if created != 0:
            error_code = ctypes.get_last_error()
            raise ToolError(
                f"CreatePseudoConsole failed with HRESULT {created:#x} (last error {error_code})"
            )

        attribute_size = ctypes.c_size_t()
        # The first call intentionally fails with ERROR_INSUFFICIENT_BUFFER and
        # reports the required allocation size.
        kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(attribute_size))
        attribute_buffer = ctypes.create_string_buffer(attribute_size.value)
        attribute_list = ctypes.cast(attribute_buffer, _LPPROC_THREAD_ATTRIBUTE_LIST)
        if not kernel32.InitializeProcThreadAttributeList(
            attribute_list,
            1,
            0,
            ctypes.byref(attribute_size),
        ):
            raise ToolError("cannot initialize the process attribute list")
        pseudo_console_value = pseudo_console.value or 0
        if not kernel32.UpdateProcThreadAttribute(
            attribute_list,
            0,
            _PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
            pseudo_console_value,
            ctypes.sizeof(wintypes.HANDLE),
            None,
            None,
        ):
            raise ToolError("cannot attach the pseudo console to the process")

        startup_info = _STARTUPINFOEXW()
        startup_info.StartupInfo.cb = ctypes.sizeof(_STARTUPINFOEXW)
        startup_info.StartupInfo.dwFlags = _STARTF_USESTDHANDLES
        startup_info.StartupInfo.hStdInput = input_read
        # Per the Microsoft ConPTY reference implementation, stdout/stderr go to
        # the console-side write end; the input-pipe read end is read-only and
        # must not be reused here.
        startup_info.StartupInfo.hStdOutput = write_handle
        startup_info.StartupInfo.hStdError = write_handle
        startup_info.lpAttributeList = attribute_list
        command_line = subprocess.list2cmdline(argv)
        environment_block = _clean_environment_block()
        if not kernel32.CreateProcessW(
            None,
            ctypes.c_wchar_p(command_line),
            None,
            None,
            False,
            _EXTENDED_STARTUPINFO_PRESENT | _CREATE_UNICODE_ENVIRONMENT,
            environment_block,
            ctypes.c_wchar_p(str(cwd)),
            ctypes.byref(startup_info),
            ctypes.byref(process_info),
        ):
            raise ToolError("cannot start the interactive process")
        process_started = True

        if startup_input:
            input_bytes = startup_input.encode("utf-8")
            input_buffer = ctypes.create_string_buffer(input_bytes)
            written = wintypes.DWORD()
            if not kernel32.WriteFile(
                input_write,
                input_buffer,
                wintypes.DWORD(len(input_bytes)),
                ctypes.byref(written),
                None,
            ) or written.value != len(input_bytes):
                raise ToolError("cannot write terminal startup input")
            kernel32.CloseHandle(input_write)
            input_write = wintypes.HANDLE()

        job_handle: wintypes.HANDLE | None = None
        if hasattr(kernel32, "CreateJobObjectW"):
            raw_job = kernel32.CreateJobObjectW(None, None)
            if raw_job:
                job_handle = raw_job
                info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                kernel32.SetInformationJobObject(
                    job_handle,
                    9,  # JobObjectExtendedLimitInformation
                    ctypes.byref(info),
                    ctypes.sizeof(info),
                )
                kernel32.AssignProcessToJobObject(job_handle, process_info.hProcess)

        output = bytearray()
        deadline = time.monotonic() + timeout_seconds
        timed_out = False
        output_limit_reached = False
        termination_reason: str | None = None
        exit_code: int | None = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            current_exit = wintypes.DWORD()
            running = kernel32.GetExitCodeProcess(
                process_info.hProcess,
                ctypes.byref(current_exit),
            )
            if running and current_exit.value != _STILL_ACTIVE:
                exit_code = current_exit.value
                break
            available = wintypes.DWORD()
            if not kernel32.PeekNamedPipe(
                read_handle,
                None,
                0,
                None,
                ctypes.byref(available),
                None,
            ):
                break
            if available.value:
                chunk = ctypes.create_string_buffer(min(available.value, 64 * 1024))
                read = wintypes.DWORD()
                if kernel32.ReadFile(
                    read_handle,
                    chunk,
                    wintypes.DWORD(len(chunk)),
                    ctypes.byref(read),
                    None,
                ):
                    output.extend(chunk.raw[: read.value])
                if len(output) > _MAX_OUTPUT_BYTES:
                    output_limit_reached = True
                    termination_reason = "output_limit"
                    break
            else:
                time.sleep(0.02)
        if timed_out:
            termination_reason = "timeout"
        if timed_out or output_limit_reached:
            if job_handle:
                kernel32.TerminateJobObject(job_handle, 1)
            kernel32.TerminateProcess(process_info.hProcess, 1)
        # Drain remaining output with a short quiet grace so slow ConPTY
        # delivery after process exit is not lost.
        if not timed_out and not output_limit_reached:
            quiet_deadline = time.monotonic() + 0.8
            while time.monotonic() < quiet_deadline:
                available = wintypes.DWORD()
                if not kernel32.PeekNamedPipe(
                    read_handle,
                    None,
                    0,
                    None,
                    ctypes.byref(available),
                    None,
                ):
                    break
                if available.value == 0:
                    time.sleep(0.02)
                    continue
                chunk = ctypes.create_string_buffer(min(available.value, 64 * 1024))
                read = wintypes.DWORD()
                if not kernel32.ReadFile(
                    read_handle,
                    chunk,
                    wintypes.DWORD(len(chunk)),
                    ctypes.byref(read),
                    None,
                ):
                    break
                output.extend(chunk.raw[: read.value])
                quiet_deadline = time.monotonic() + 0.2
                if len(output) > _MAX_OUTPUT_BYTES:
                    break
        text = bytes(output[:_MAX_OUTPUT_BYTES]).decode("utf-8", errors="replace")
        return json_result(
            {
                "command": argv,
                "cwd": paths.relative(cwd),
                "exit_code": exit_code,
                "timed_out": timed_out,
                "output_limit_reached": output_limit_reached,
                "termination_reason": termination_reason,
                "bytes": len(output),
                "truncated": len(output) > _MAX_OUTPUT_BYTES,
                "output": text,
            }
        )
    finally:
        if job_handle:
            _close(kernel32, job_handle)
        if process_started:
            _close(kernel32, process_info.hThread, process_info.hProcess)
        if attribute_list is not None:
            kernel32.DeleteProcThreadAttributeList(attribute_list)
        if pseudo_console:
            kernel32.ClosePseudoConsole(pseudo_console)
        _close(kernel32, input_read, input_write, write_handle, read_handle)


class RunTerminalTool:
    """Run an interactive command through a Windows ConPTY and capture output."""

    hard_cancellable = False
    _SPEC = ToolSpec(
        name="run_terminal",
        description=(
            "Run an interactive command inside a Windows pseudo terminal (ConPTY) in the "
            "workspace. Captures combined bounded output and accepts optional one-shot startup "
            "input. The process is closed after completion or timeout; use background jobs for "
            "durable non-interactive work. ASK and WORKSPACE require approval; FULL ACCESS "
            "does not require a routine approval prompt."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "argv": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 32767},
                    "maxItems": 256,
                    "minItems": 1,
                },
                "cwd": {"type": "string", "minLength": 1, "default": "."},
                "input": {"type": "string", "maxLength": _MAX_INPUT_CHARS},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 300},
            },
            "required": ["argv"],
            "additionalProperties": False,
        },
        side_effect="process",
        capability=Capability.PROCESS_EXECUTE,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        raw_argv = arguments.get("argv")
        if (
            not isinstance(raw_argv, list)
            or not raw_argv
            or any(not isinstance(item, str) or not item or "\x00" in item for item in raw_argv)
            or len(raw_argv) > _MAX_ARGUMENTS
            or any(len(item) > _MAX_ARGUMENT_CHARS for item in raw_argv)
        ):
            raise ToolArgumentError("'argv' must be a bounded array of non-empty strings")
        raw_cwd = arguments.get("cwd", ".")
        if not isinstance(raw_cwd, str) or not raw_cwd:
            raise ToolArgumentError("'cwd' must be a non-empty string")
        startup_input = arguments.get("input", "")
        if (
            not isinstance(startup_input, str)
            or len(startup_input) > _MAX_INPUT_CHARS
            or "\x00" in startup_input
        ):
            raise ToolArgumentError(
                f"'input' must be a string of at most {_MAX_INPUT_CHARS} characters without NUL"
            )
        timeout_seconds = optional_int(
            arguments,
            "timeout_seconds",
            60,
            minimum=1,
            maximum=300,
        )
        # ConPTY requires the calling process to be attached to a console; the
        # process worker is detached, so run in a thread of the runtime process
        # and rely on the internal timeout plus TerminateProcess for cleanup.
        return await asyncio.to_thread(
            _conpty_sync,
            str(self.paths.root),
            list(raw_argv),
            raw_cwd,
            timeout_seconds,
            startup_input,
        )
