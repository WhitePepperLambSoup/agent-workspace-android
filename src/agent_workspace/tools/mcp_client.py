"""MCP (Model Context Protocol) 2024-11-05 stdio client.

Spawns an MCP server as a subprocess and exchanges line-delimited JSON-RPC
2.0 messages over stdin/stdout, while capturing a bounded stderr tail for
diagnostics when the server misbehaves or exits.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import subprocess
import sys
from asyncio import StreamReader, StreamWriter
from asyncio.subprocess import Process
from collections.abc import Awaitable, Callable, Coroutine, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, cast

from agent_workspace.application.ports import Tool
from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolError

_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_NAME = "agent-workspace"
_CLIENT_VERSION = "0.1.0"
_MAX_LINE_BYTES = 32 * 1024 * 1024
_STDERR_TAIL_BYTES = 8 * 1024
_STDERR_REPORT_BYTES = 2 * 1024
_TERMINATE_SECONDS = 2.0


class McpClientError(ToolError):
    """Raised when the MCP server cannot be reached or misbehaves."""


@dataclass(frozen=True, slots=True)
class McpToolDefinition:
    """A single tool advertised by an MCP server via tools/list."""

    name: str
    description: str
    input_schema: dict[str, Any]


async def _read_line(reader: StreamReader) -> bytes:
    """Read one LF- or CRLF-terminated line from the MCP server stdout."""
    data = await reader.readuntil(b"\n")
    return data.removesuffix(b"\n").removesuffix(b"\r")


async def _drain_oversized_line(reader: StreamReader) -> None:
    """Discard the tail of an oversized line so the next read starts clean.

    After ``readuntil`` raises :class:`asyncio.LimitOverrunError` the remainder
    of that line is still buffered; consuming it here prevents every later
    read from returning the middle of the same oversized line.
    """
    drained = 0
    while drained < _MAX_LINE_BYTES * 2:
        try:
            chunk = await reader.read(64 * 1024)
        except (OSError, ValueError):
            return
        if not chunk:
            return
        drained += len(chunk)
        if b"\n" in chunk:
            return


def _format_result_text(result: dict[str, Any]) -> str:
    """Render a tools/call result object as a plain string."""
    structured = result.get("structuredContent")
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False, sort_keys=True)
    content = result.get("content")
    if not isinstance(content, list):
        return ""
    text_blocks: list[str] = []
    omitted = 0
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            value = block.get("text")
            if isinstance(value, str):
                text_blocks.append(value)
        else:
            omitted += 1
    text = "\n".join(text_blocks)
    if omitted:
        text += f"(non-text content omitted: {omitted} blocks)"
    return text


def sanitize_environment(
    explicit_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Provide a minimal, safe environment for MCP servers.

    Prevents leaking host API keys, secrets, or synthetic test tokens to
    untrusted child processes.
    """
    if explicit_env is not None:
        return dict(explicit_env)
    safe_prefixes = (
        "PATH",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "HOME",
        "LANG",
        "LC_",
    )
    sensitive_markers = ("KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL", "AUTH")
    clean: dict[str, str] = {}
    for k, v in os.environ.items():
        k_upper = k.upper()
        if any(marker in k_upper for marker in sensitive_markers):
            continue
        if k_upper.startswith(safe_prefixes) or k_upper in (
            "VIRTUAL_ENV",
            "PYTHONPATH",
            "NODE_PATH",
            "TERM",
            "PROGRAMDATA",
            "APPDATA",
            "LOCALAPPDATA",
        ):
            clean[k] = v
    return clean


class StdioMcpClient:
    """Async stdio client for one MCP 2024-11-05 server subprocess."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        cwd: str | None = None,
        environment: Mapping[str, str] | None = None,
        init_timeout_seconds: float = 10.0,
        call_timeout_seconds: float = 120.0,
        max_result_bytes: int = 1024 * 1024,
    ) -> None:
        self._command = tuple(command)
        self._cwd = cwd
        self._environment = sanitize_environment(environment)
        self._init_timeout_seconds = init_timeout_seconds
        self._call_timeout_seconds = call_timeout_seconds
        self._max_result_bytes = max_result_bytes
        self._process: Process | None = None
        self._stdin: StreamWriter | None = None
        self._stdout: StreamReader | None = None
        self._stderr: StreamReader | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._stderr_tail = b""
        self._request_id = 0
        self._request_lock = asyncio.Lock()
        self._job_handle: Any = None
        self._connection_generation = 0
        self._last_error: str | None = None

    @property
    def command(self) -> tuple[str, ...]:
        return self._command

    @property
    def connection_generation(self) -> int:
        return self._connection_generation

    @property
    def connected(self) -> bool:
        return self._process is not None and self._process.returncode is None

    def status(self) -> dict[str, Any]:
        process = self._process
        return {
            "connected": self.connected,
            "generation": self._connection_generation,
            "pid": process.pid if process is not None and self.connected else None,
            "exit_code": process.returncode if process is not None else None,
            "last_error": self._last_error,
        }

    async def connect(self) -> None:
        """Start the server subprocess and perform the MCP handshake."""
        if self.connected:
            return
        if self._process is not None:
            await self.aclose()
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = await asyncio.create_subprocess_exec(
                *self._command,
                cwd=self._cwd,
                env=self._environment,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=creationflags,
                limit=_MAX_LINE_BYTES,
            )
        except OSError as exc:
            raise McpClientError(f"cannot start MCP server {self._command[0]!r}: {exc}") from exc
        self._process = process
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                kernel32 = ctypes.windll.kernel32
                raw_job = kernel32.CreateJobObjectW(None, None)
                if raw_job:
                    self._job_handle = raw_job

                    class _IO_COUNTERS(ctypes.Structure):
                        _fields_ = [
                            ("ReadOperationCount", ctypes.c_uint64),
                            ("WriteOperationCount", ctypes.c_uint64),
                            ("OtherOperationCount", ctypes.c_uint64),
                            ("ReadTransferCount", ctypes.c_uint64),
                            ("WriteTransferCount", ctypes.c_uint64),
                            ("OtherTransferCount", ctypes.c_uint64),
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

                    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                        _fields_ = [
                            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
                            ("IoInfo", _IO_COUNTERS),
                            ("ProcessMemoryLimit", ctypes.c_size_t),
                            ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryLimit", ctypes.c_size_t),
                            ("PeakJobMemoryLimit", ctypes.c_size_t),
                        ]

                    info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                    info.BasicLimitInformation.LimitFlags = (
                        0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                    )
                    kernel32.SetInformationJobObject(
                        raw_job,
                        9,  # JobObjectExtendedLimitInformation
                        ctypes.byref(info),
                        ctypes.sizeof(info),
                    )
                    PROCESS_SET_QUOTA = 0x0100
                    PROCESS_TERMINATE = 0x0001
                    h_proc = kernel32.OpenProcess(
                        PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, process.pid
                    )
                    if h_proc:
                        kernel32.AssignProcessToJobObject(raw_job, h_proc)
                        kernel32.CloseHandle(h_proc)
            except Exception:
                pass
        self._stdin = cast(StreamWriter, process.stdin)
        self._stdout = cast(StreamReader, process.stdout)
        self._stderr = cast(StreamReader, process.stderr)
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        try:
            await self._initialize()
            self._connection_generation += 1
            self._last_error = None
        except BaseException:
            await self.aclose()
            raise

    async def reconnect(
        self,
        *,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
    ) -> dict[str, Any]:
        """Restart the child and perform a fresh MCP handshake.

        Reconnect is explicit so a transient provider failure cannot silently
        restart an MCP process while a tool call is in flight.  The returned
        report is safe to expose in health diagnostics and contains no command
        environment or request payloads.
        """
        if max_attempts < 1 or backoff_seconds < 0:
            raise ValueError("MCP reconnect attempts/backoff are invalid")
        await self.aclose()
        last_error: str | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                await self.connect()
                return {
                    "connected": True,
                    "attempts": attempt,
                    "generation": self._connection_generation,
                    "error": None,
                }
            except McpClientError as exc:
                last_error = " ".join(str(exc).split())[:1000]
                self._last_error = last_error
                if attempt < max_attempts and backoff_seconds:
                    await asyncio.sleep(backoff_seconds * (2 ** (attempt - 1)))
        return {
            "connected": False,
            "attempts": max_attempts,
            "generation": self._connection_generation,
            "error": last_error or "MCP reconnect failed",
        }

    async def list_tools(self) -> tuple[McpToolDefinition, ...]:
        """List the tools advertised by the server, sorted by name."""
        response = await self._request("tools/list", None, self._call_timeout_seconds)
        result = response.get("result")
        raw_tools = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(raw_tools, list):
            raise McpClientError("MCP server tools/list response is missing the 'tools' array")
        definitions: list[McpToolDefinition] = []
        for raw in raw_tools:
            if not isinstance(raw, dict):
                continue
            name = raw.get("name")
            if not isinstance(name, str) or not name:
                continue
            description = raw.get("description")
            if not isinstance(description, str):
                description = ""
            schema = raw.get("inputSchema")
            if not isinstance(schema, dict) or schema.get("type") != "object":
                schema = {"type": "object"}
            definitions.append(McpToolDefinition(name, description, schema))
        definitions.sort(key=lambda item: item.name)
        return tuple(definitions)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Invoke a server tool and return its rendered, size-bounded output."""
        params = {"name": name, "arguments": arguments}
        response = await self._request("tools/call", params, self._call_timeout_seconds)
        result = response.get("result")
        if not isinstance(result, dict):
            raise McpClientError(f"MCP server tools/call response is missing 'result' for {name!r}")
        text = _format_result_text(result)
        if result.get("isError") is True:
            raise McpClientError(f"MCP tool {name!r} failed: {text}")
        return self._truncate_result(text)

    async def ping(self) -> None:
        """Send a ping request; raises McpClientError if the server is gone."""
        await self._request("ping", None, self._call_timeout_seconds)

    async def aclose(self) -> None:
        """Terminate the server subprocess. Idempotent and never raises."""
        stderr_task = self._stderr_task
        self._stderr_task = None
        if stderr_task is not None:
            stderr_task.cancel()
            with suppress(BaseException):
                await stderr_task
        process = self._process
        self._process = None
        self._stdin = None
        self._stdout = None
        self._stderr = None
        if hasattr(self, "_job_handle") and self._job_handle:
            try:
                import ctypes

                ctypes.windll.kernel32.CloseHandle(self._job_handle)
            except Exception:
                pass
            self._job_handle = None
        if process is None or process.returncode is not None:
            return
        with suppress(Exception):
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=_TERMINATE_SECONDS)
            except TimeoutError:
                process.kill()
                with suppress(BaseException):
                    await asyncio.wait_for(process.wait(), timeout=_TERMINATE_SECONDS)

    async def _initialize(self) -> None:
        params = {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": _CLIENT_NAME, "version": _CLIENT_VERSION},
        }
        response = await self._request("initialize", params, self._init_timeout_seconds)
        result = response.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("protocolVersion"), str):
            raise McpClientError("MCP server initialize response is missing result.protocolVersion")
        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def _request(
        self,
        method: str,
        params: dict[str, Any] | None,
        timeout: float,
    ) -> dict[str, Any]:
        async with self._request_lock:
            self._request_id += 1
            request_id = self._request_id
            message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
            if params is not None:
                message["params"] = params
            await self._send(message)
            return await self._recv_response(request_id, timeout)

    async def _recv_response(self, request_id: int, timeout: float) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise McpClientError(f"MCP server did not respond within {timeout:g} seconds")
            message = await self._recv(remaining)
            if "id" not in message:
                continue
            if message["id"] != request_id:
                # A response to an earlier timed-out or cancelled request; drop
                # it instead of poisoning this call with a hard protocol error.
                continue
            if "error" in message:
                error = message["error"]
                code = error.get("code") if isinstance(error, dict) else None
                detail = error.get("message") if isinstance(error, dict) else None
                raise McpClientError(
                    f"MCP server returned JSON-RPC error (code={code}, message={detail!r})"
                )
            return message

    async def _send(self, message: dict[str, Any]) -> None:
        writer = self._require_stdin()
        line = (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        writer.write(line)
        try:
            await writer.drain()
        except OSError as exc:
            raise McpClientError(
                await self._server_exit_message("MCP server pipe closed while sending")
            ) from exc

    async def _recv(self, timeout: float) -> dict[str, Any]:
        reader = self._require_stdout()
        try:
            raw = await asyncio.wait_for(_read_line(reader), timeout)
        except TimeoutError as exc:
            raise McpClientError(f"MCP server did not respond within {timeout:g} seconds") from exc
        except asyncio.LimitOverrunError as exc:
            await _drain_oversized_line(reader)
            raise McpClientError(
                f"MCP server sent a message line over the {_MAX_LINE_BYTES}-byte limit"
            ) from exc
        except (asyncio.IncompleteReadError, OSError) as exc:
            raise McpClientError(
                await self._server_exit_message("MCP server closed the connection")
            ) from exc
        if not raw:
            raise McpClientError(await self._server_exit_message("MCP server closed stdout"))
        try:
            message = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise McpClientError("MCP server sent an invalid JSON-RPC message") from exc
        if not isinstance(message, dict):
            raise McpClientError("MCP server sent a non-object JSON-RPC message")
        return message

    async def _drain_stderr(self) -> None:
        reader = self._stderr
        if reader is None:
            return
        while True:
            try:
                chunk = await reader.read(4096)
            except (ConnectionResetError, asyncio.IncompleteReadError):
                return
            if not chunk:
                return
            self._stderr_tail = (self._stderr_tail + chunk)[-_STDERR_TAIL_BYTES:]

    async def _server_exit_message(self, prefix: str) -> str:
        stderr_task = self._stderr_task
        if stderr_task is not None and not stderr_task.done():
            with suppress(BaseException):
                await asyncio.wait_for(asyncio.shield(stderr_task), timeout=0.5)
        process = self._process
        tail = self._stderr_tail.decode("utf-8", errors="replace").strip()
        exit_detail = ""
        if process is not None and process.returncode is not None:
            exit_detail = f" (exit code {process.returncode})"
        if tail:
            return f"{prefix}{exit_detail}; server stderr tail: {tail[-_STDERR_REPORT_BYTES:]}"
        return f"{prefix}{exit_detail}"

    def _truncate_result(self, text: str) -> str:
        encoded = text.encode("utf-8")
        limit = self._max_result_bytes
        if len(encoded) <= limit:
            return text
        total = len(encoded)
        # Upper-bound marker length: {total} has at least as many digits as
        # the final {kept}, so the final marker never exceeds this budget.
        upper_marker = f"[MCP tool output truncated at {total} of {total} bytes]"
        budget = max(0, limit - len(upper_marker.encode("utf-8")))
        kept_text = encoded[:budget].decode("utf-8", errors="ignore")
        kept = len(kept_text.encode("utf-8"))
        return kept_text + f"[MCP tool output truncated at {kept} of {total} bytes]"

    def _require_stdin(self) -> StreamWriter:
        writer = self._stdin
        if writer is None:
            raise McpClientError("MCP client is not connected")
        return writer

    def _require_stdout(self) -> StreamReader:
        reader = self._stdout
        if reader is None:
            raise McpClientError("MCP client is not connected")
        return reader


class McpProxyTool(Tool):
    """Expose one remote MCP tool through the agent Tool protocol.

    `submit` bridges calls onto the event loop that owns the stdio client when
    the proxy is used from a different loop (for example a hosted MCP client on
    a dedicated thread); it defaults to awaiting the coroutine directly.
    """

    def __init__(
        self,
        client: StdioMcpClient,
        definition: McpToolDefinition,
        side_effect: str = "process",
        capability: Capability | None = Capability.PROCESS_EXECUTE,
        *,
        submit: Callable[[Coroutine[Any, Any, str]], Awaitable[str]] | None = None,
        server_id: str = "",
        tool_name: str | None = None,
    ) -> None:
        self._client = client
        self._definition = definition
        self._submit = submit
        self._server_id = server_id
        input_schema = copy.deepcopy(definition.input_schema)
        if "additionalProperties" not in input_schema:
            input_schema["additionalProperties"] = False
        safe_name = tool_name or ("mcp_" + re.sub(r"[^a-zA-Z0-9_-]", "_", definition.name))
        self._spec = ToolSpec(
            name=safe_name,
            description=definition.description,
            input_schema=input_schema,
            side_effect=side_effect,
            capability=capability,
            provider_input_schema=None,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any]) -> str:
        operation = self._client.call_tool(self._definition.name, arguments)
        if self._submit is not None:
            return await self._submit(operation)
        return await operation
