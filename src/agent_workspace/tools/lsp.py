"""LSP (Language Server Protocol) stdio client and diagnostics tool.

Spawns a language server as a subprocess and exchanges Content-Length
framed JSON-RPC 2.0 messages over stdin/stdout, recording
``textDocument/publishDiagnostics`` notifications for the
``run_diagnostics`` workspace tool. The server is never started with
arguments beyond the caller-provided command; the repository bundles no
language server, so callers pass one explicitly (for example
``["pyright-langserver", "--stdio"]`` or ``["pylsp"]``).
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from asyncio import StreamReader, StreamWriter
from asyncio.subprocess import Process
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from agent_workspace.application.ports import Tool
from agent_workspace.core.models import Capability, ToolSpec

from .base import ToolArgumentError, ToolError, json_result, require_string
from .command import _safe_environment
from .filesystem import _workspace_paths
from .paths import StrPath, WorkspacePaths

_MAX_MESSAGE_BYTES = 16 * 1024 * 1024
_MAX_HEADER_LINE_BYTES = 8 * 1024
_STDERR_TAIL_BYTES = 8 * 1024
_STDERR_REPORT_BYTES = 2 * 1024
_TERMINATE_SECONDS = 2.0
_SHUTDOWN_SECONDS = 5.0

_MAX_FILE_BYTES = 4 * 1024 * 1024
_MAX_DIAGNOSTICS = 500
_DIAGNOSTIC_WAIT_SECONDS = 2.0
_DIAGNOSTIC_POLL_SECONDS = 0.05

_LANGUAGE_IDS: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".cs": "csharp",
    ".java": "java",
    ".kt": "kotlin",
    ".json": "json",
    ".md": "markdown",
}

_lsp_diagnostics_cache: dict[tuple[tuple[str, ...], str, int, int], str] = {}
_MAX_LSP_CACHE_ENTRIES = 64


def clear_lsp_diagnostics_cache() -> None:
    _lsp_diagnostics_cache.clear()


class LspClientError(ToolError):
    """Raised when the language server cannot be reached or misbehaves."""


@dataclass(frozen=True, slots=True)
class LspDiagnostic:
    """One LSP diagnostic; ``severity`` uses LSP codes (1=error .. 4=hint)."""

    range_start_line: int
    range_start_character: int
    range_end_line: int
    range_end_character: int
    severity: int
    code: str | None
    source: str | None
    message: str


def _parse_diagnostic(raw: dict[str, Any]) -> LspDiagnostic | None:
    range_value = raw.get("range")
    message = raw.get("message")
    if not isinstance(range_value, dict) or not isinstance(message, str):
        return None
    start = range_value.get("start")
    end = range_value.get("end")
    if not isinstance(start, dict) or not isinstance(end, dict):
        return None
    start_line = start.get("line")
    start_character = start.get("character")
    end_line = end.get("line")
    end_character = end.get("character")
    if (
        not isinstance(start_line, int)
        or not isinstance(start_character, int)
        or not isinstance(end_line, int)
        or not isinstance(end_character, int)
    ):
        return None
    severity = raw.get("severity", 1)
    if not isinstance(severity, int) or severity not in (1, 2, 3, 4):
        severity = 1
    code = raw.get("code")
    if isinstance(code, bool) or not isinstance(code, (str, int)):
        code = None
    elif isinstance(code, int):
        code = str(code)
    source = raw.get("source")
    if not isinstance(source, str):
        source = None
    return LspDiagnostic(
        range_start_line=start_line,
        range_start_character=start_character,
        range_end_line=end_line,
        range_end_character=end_character,
        severity=severity,
        code=code,
        source=source,
        message=message,
    )


def _infer_language_id(path: Path) -> str:
    return _LANGUAGE_IDS.get(path.suffix.lower(), "plaintext")


def _lsp_environment() -> dict[str, str]:
    """Environment for LSP server processes.

    Starts from the audited clean environment (no API keys, tokens, or
    user configuration) and restores only the inherited PATH so servers
    that are configured by name (e.g. ``pyright-langserver``) still resolve
    while credentials never leak into the child process.
    """
    environment = _safe_environment()
    inherited_path = os.environ.get("PATH")
    if inherited_path:
        environment["PATH"] = os.pathsep.join((environment["PATH"], inherited_path))
    return environment


class StdioLspClient:
    """Async stdio client for one LSP server subprocess.

    Responses are dispatched to pending requests by a background reader
    task, while ``textDocument/publishDiagnostics`` notifications are
    recorded under ``diagnostics`` keyed by document URI.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        init_timeout: float = 15.0,
    ) -> None:
        self._command = tuple(command)
        self._init_timeout = init_timeout
        self._process: Process | None = None
        self._stdin: StreamWriter | None = None
        self._stdout: StreamReader | None = None
        self._stderr: StreamReader | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._stderr_tail = b""
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._request_id = 0
        self._closed = False
        self._capabilities: dict[str, Any] | None = None
        self._diagnostics: dict[str, list[LspDiagnostic]] = {}

    @property
    def diagnostics(self) -> dict[str, list[LspDiagnostic]]:
        """Diagnostics recorded so far, keyed by document URI."""
        return dict(self._diagnostics)

    async def connect(self, initialize_params: dict[str, Any]) -> dict[str, Any]:
        """Start the server and perform the LSP initialize handshake.

        Sends ``initialize`` (request id 0, the reserved-by-convention id)
        and waits for its result, then sends the ``initialized``
        notification. Returns the initialize result (server capabilities).
        """
        if self._process is not None:
            capabilities = self._capabilities
            if capabilities is None:
                raise LspClientError("LSP client is already connected without capabilities")
            return capabilities
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        environment = _lsp_environment()
        try:
            process = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=creationflags,
                env=environment,
                limit=_MAX_MESSAGE_BYTES + 64 * 1024,
            )
        except OSError as exc:
            raise LspClientError(f"cannot start LSP server {self._command[0]!r}: {exc}") from exc
        self._process = process
        self._stdin = cast(StreamWriter, process.stdin)
        self._stdout = cast(StreamReader, process.stdout)
        self._stderr = cast(StreamReader, process.stderr)
        self._reader_task = asyncio.create_task(self._read_loop())
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        try:
            capabilities = await self._initialize(initialize_params)
        except BaseException:
            await self.shutdown_exit()
            raise
        self._capabilities = capabilities
        return capabilities

    async def did_open(self, uri: str, language_id: str, version: int, text: str) -> None:
        """Send a ``textDocument/didOpen`` notification."""
        params = {
            "textDocument": {
                "uri": uri,
                "languageId": language_id,
                "version": version,
                "text": text,
            }
        }
        await self._send_notification("textDocument/didOpen", params)

    async def did_close(self, uri: str) -> None:
        """Send a ``textDocument/didClose`` notification."""
        params = {"textDocument": {"uri": uri}}
        await self._send_notification("textDocument/didClose", params)

    async def request(self, method: str, params: dict[str, Any], timeout: float = 15.0) -> Any:
        """Send a request (for example hover/definition) and return its result."""
        request_id = self._next_id()
        response = await self._send_request(request_id, method, params, timeout)
        return response.get("result")

    async def shutdown_exit(self) -> None:
        """Send ``shutdown`` + ``exit``, then reap the server.

        Idempotent and never raises, so it is safe to call from cleanup
        paths (including after a failed connect or a cancellation).
        """
        if self._closed:
            return
        self._closed = True
        process = self._process
        if process is not None and process.returncode is None:
            with suppress(BaseException):
                await self._send_request(self._next_id(), "shutdown", {}, _SHUTDOWN_SECONDS)
            with suppress(BaseException):
                await self._send_notification("exit", {})
        await self._stop_tasks()
        if process is not None:
            await self._wait_for_exit(process)
        self._process = None
        self._stdin = None
        self._stdout = None
        self._stderr = None

    async def _initialize(self, initialize_params: dict[str, Any]) -> dict[str, Any]:
        response = await self._send_request(0, "initialize", initialize_params, self._init_timeout)
        result = response.get("result")
        if not isinstance(result, dict):
            raise LspClientError("LSP server initialize response is missing 'result'")
        await self._send_notification("initialized", {})
        return result

    async def _send_request(
        self,
        request_id: int,
        method: str,
        params: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await self._send(message)
            response = await asyncio.wait_for(future, timeout)
        except TimeoutError as exc:
            raise LspClientError(
                f"LSP server did not respond to {method!r} within {timeout:g} seconds"
            ) from exc
        finally:
            pending = self._pending.pop(request_id, None)
            if pending is not None and not pending.done():
                pending.cancel()
        if "error" in response:
            error = response["error"]
            code = error.get("code") if isinstance(error, dict) else None
            detail = error.get("message") if isinstance(error, dict) else None
            raise LspClientError(
                f"LSP server returned JSON-RPC error (code={code}, message={detail!r})"
            )
        return response

    async def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params})

    async def _send(self, message: dict[str, Any]) -> None:
        writer = self._require_stdin()
        body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(body) > _MAX_MESSAGE_BYTES:
            raise LspClientError(f"outgoing LSP message of {len(body)} bytes exceeds the limit")
        writer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        try:
            await writer.drain()
        except OSError as exc:
            raise LspClientError(
                await self._server_exit_message("LSP server pipe closed while sending")
            ) from exc

    async def _read_loop(self) -> None:
        reader = self._stdout
        if reader is None:
            return
        try:
            while True:
                message = await self._read_frame(reader)
                if "id" in message:
                    self._resolve_response(message)
                else:
                    self._handle_notification(message)
        except asyncio.CancelledError:
            raise
        except (asyncio.IncompleteReadError, OSError):
            self._fail_pending(
                LspClientError(await self._server_exit_message("LSP server closed the connection"))
            )
        except LspClientError as exc:
            self._fail_pending(exc)

    async def _read_frame(self, reader: StreamReader) -> dict[str, Any]:
        headers: dict[str, str] = {}
        while True:
            line = await reader.readuntil(b"\n")
            if line in (b"\r\n", b"\n"):
                break
            if len(line) > _MAX_HEADER_LINE_BYTES:
                raise LspClientError("LSP header line exceeds the size limit")
            name, separator, value = line.decode("ascii", errors="replace").partition(":")
            if separator:
                headers[name.strip().lower()] = value.strip()
        raw_length = headers.get("content-length")
        if raw_length is None:
            raise LspClientError("LSP message is missing a Content-Length header")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise LspClientError(f"invalid Content-Length header: {raw_length!r}") from exc
        if length < 0 or length > _MAX_MESSAGE_BYTES:
            raise LspClientError(
                f"LSP message body of {length} bytes exceeds the {_MAX_MESSAGE_BYTES}-byte limit"
            )
        body = await reader.readexactly(length)
        try:
            message = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise LspClientError("LSP server sent an invalid JSON message") from exc
        if not isinstance(message, dict):
            raise LspClientError("LSP server sent a non-object JSON message")
        return message

    def _resolve_response(self, message: dict[str, Any]) -> None:
        request_id = message["id"]
        if not isinstance(request_id, int):
            return
        future = self._pending.pop(request_id, None)
        if future is not None and not future.done():
            future.set_result(message)

    def _handle_notification(self, message: dict[str, Any]) -> None:
        if message.get("method") == "textDocument/publishDiagnostics":
            self._record_diagnostics(message.get("params"))

    def _record_diagnostics(self, params: Any) -> None:
        if not isinstance(params, dict):
            return
        uri = params.get("uri")
        raw_diagnostics = params.get("diagnostics")
        if not isinstance(uri, str) or not isinstance(raw_diagnostics, list):
            return
        new_diagnostics: list[LspDiagnostic] = []
        for raw in raw_diagnostics:
            if not isinstance(raw, dict):
                continue
            diagnostic = _parse_diagnostic(raw)
            if diagnostic is not None and diagnostic not in new_diagnostics:
                new_diagnostics.append(diagnostic)
        self._diagnostics[uri] = new_diagnostics

    def _fail_pending(self, error: Exception) -> None:
        pending = self._pending
        self._pending = {}
        for future in pending.values():
            if not future.done():
                future.set_exception(error)

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

    async def _stop_tasks(self) -> None:
        reader = self._reader_task
        self._reader_task = None
        if reader is not None:
            reader.cancel()
            with suppress(BaseException):
                await reader
        stderr = self._stderr_task
        self._stderr_task = None
        if stderr is not None:
            stderr.cancel()
            with suppress(BaseException):
                await stderr

    async def _wait_for_exit(self, process: Process) -> None:
        if process.returncode is not None:
            return
        with suppress(BaseException):
            await asyncio.wait_for(process.wait(), timeout=_TERMINATE_SECONDS)
        if process.returncode is not None:
            return
        with suppress(BaseException):
            process.terminate()
        with suppress(BaseException):
            await asyncio.wait_for(process.wait(), timeout=_TERMINATE_SECONDS)
        if process.returncode is not None:
            return
        with suppress(BaseException):
            process.kill()
        with suppress(BaseException):
            await process.wait()

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _require_stdin(self) -> StreamWriter:
        writer = self._stdin
        if writer is None:
            raise LspClientError("LSP client is not connected")
        return writer

    def _require_stdout(self) -> StreamReader:
        reader = self._stdout
        if reader is None:
            raise LspClientError("LSP client is not connected")
        return reader


class LspDiagnosticsTool(Tool):
    """Run a language server over a workspace file and return diagnostics."""

    hard_cancellable = True
    _SPEC = ToolSpec(
        name="run_diagnostics",
        description=(
            "Run a language server over a workspace file and return diagnostics (errors/warnings)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "command": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 32767},
                    "minItems": 1,
                    "maxItems": 256,
                },
            },
            "required": ["path", "command"],
            "additionalProperties": False,
        },
        side_effect="process",
        capability=Capability.PROCESS_EXECUTE,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = _workspace_paths(workspace)

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        path_text = require_string(arguments, "path")
        raw_command = arguments.get("command")
        if (
            not isinstance(raw_command, list)
            or not raw_command
            or len(raw_command) > 256
            or not all(
                isinstance(item, str) and item and len(item) <= 32_767 and "\x00" not in item
                for item in raw_command
            )
        ):
            raise ToolArgumentError("'command' must be a bounded array of non-empty strings")
        command = tuple(raw_command)

        path = self.paths.resolve(path_text)
        text = self._read_workspace_file(path)
        try:
            metadata = path.stat()
        except OSError as exc:
            raise ToolError(f"cannot stat file: {path}") from exc
        cache_key = (command, str(path), metadata.st_mtime_ns, metadata.st_size)
        cached = _lsp_diagnostics_cache.get(cache_key)
        if cached is not None:
            return cached
        language_id = _infer_language_id(path)
        uri = path.as_uri()
        relative = self.paths.relative(path)
        root_uri = self.paths.root.as_uri()
        initialize_params: dict[str, Any] = {
            "capabilities": {},
            "rootUri": root_uri,
            "workspaceFolders": [{"uri": root_uri, "name": self.paths.root.name or "workspace"}],
        }

        client = StdioLspClient(command)
        try:
            await client.connect(initialize_params)
            await client.did_open(uri, language_id, 1, text)
            wait_expired = await self._wait_for_diagnostics(client, uri)
        finally:
            await client.shutdown_exit()

        diagnostics = self._render_diagnostics(client.diagnostics.get(uri, ()))
        rendered = json_result(
            {
                "path": relative,
                "diagnostics": diagnostics,
                "wait_expired": wait_expired,
            }
        )
        if not wait_expired:
            if len(_lsp_diagnostics_cache) >= _MAX_LSP_CACHE_ENTRIES:
                _lsp_diagnostics_cache.pop(next(iter(_lsp_diagnostics_cache)))
            _lsp_diagnostics_cache[cache_key] = rendered
        return rendered

    def _read_workspace_file(self, path: Path) -> str:
        try:
            if path.is_dir():
                raise ToolError(f"path is a directory: {path}")
            data = path.read_bytes()
        except FileNotFoundError:
            raise ToolError(f"file not found: {path}") from None
        except OSError as exc:
            raise ToolError(f"cannot read file: {path}") from exc
        if len(data) > _MAX_FILE_BYTES:
            raise ToolError(f"file exceeds the {_MAX_FILE_BYTES}-byte limit: {path}")
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(f"file is not valid UTF-8: {path}") from exc

    async def _wait_for_diagnostics(self, client: StdioLspClient, uri: str) -> bool:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _DIAGNOSTIC_WAIT_SECONDS
        while True:
            if uri in client.diagnostics:
                return False
            remaining = deadline - loop.time()
            if remaining <= 0:
                return True
            await asyncio.sleep(min(_DIAGNOSTIC_POLL_SECONDS, remaining))

    def _render_diagnostics(self, diagnostics: Sequence[LspDiagnostic]) -> list[dict[str, Any]]:
        rendered = [
            {
                "severity": diagnostic.severity,
                "line": diagnostic.range_start_line,
                "character": diagnostic.range_start_character,
                "message": diagnostic.message,
                "source": diagnostic.source,
                "code": diagnostic.code,
            }
            for diagnostic in diagnostics
        ]
        rendered.sort(key=lambda item: (item["line"], item["character"]))
        return rendered[:_MAX_DIAGNOSTICS]
