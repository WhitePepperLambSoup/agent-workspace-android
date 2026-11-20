"""LSP (Language Server Protocol) stdio client and diagnostics tool.

Spawns a language server as a subprocess and exchanges Content-Length
framed JSON-RPC 2.0 messages over stdin/stdout, recording
``textDocument/publishDiagnostics`` notifications for the
``run_diagnostics`` workspace tool. The server is never started with
arguments beyond the caller-provided command. The tool's caller is the model,
so the tool takes no command: it picks the server for the file's type from
the known ones installed outside the folder (coding/servers.py).
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from asyncio import StreamReader, StreamWriter
from asyncio.subprocess import Process
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from agent_workspace.application.ports import Tool
from agent_workspace.coding.servers import find_server, spec_for
from agent_workspace.core.models import Capability, ToolSpec

from .base import ToolError, json_result, require_string, validate_tool_arguments
from .command import _safe_environment
from .filesystem import _workspace_paths
from .helper_servers import HELPER_SERVER_NEW_SESSION, end_helper_server, helper_server_job
from .paths import StrPath, WorkspacePaths

_MAX_MESSAGE_BYTES = 16 * 1024 * 1024
_MAX_HEADER_LINE_BYTES = 8 * 1024
_STDERR_TAIL_BYTES = 8 * 1024
_STDERR_REPORT_BYTES = 2 * 1024
_TERMINATE_SECONDS = 2.0
_SHUTDOWN_SECONDS = 5.0

_MAX_FILE_BYTES = 4 * 1024 * 1024
_MAX_DIAGNOSTICS = 500
# A language server started cold (pyright reading a project) often takes several seconds.
_DIAGNOSTIC_WAIT_SECONDS = 10.0
# Some servers publish a quick first pass and the full result after it.
_DIAGNOSTIC_SETTLE_SECONDS = 0.5
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


def path_from_uri(uri: str) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    if os.name != "nt":
        return Path(unquote(parsed.path))
    text = url2pathname(unquote(parsed.path))
    if len(text) > 1 and text[1] == ":":
        text = text[0].upper() + text[1:]  # pyright writes file:///c%3A/…
    return Path(text)


def uri_key(uri: str) -> str:
    """One spelling for the same file: servers write drive letters and colons their own way."""
    path = path_from_uri(uri)
    if path is None:
        return uri
    text = os.path.normpath(str(path))
    return text.casefold() if os.name == "nt" else text


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


def _diagnostics_for(client: Any, uri: str) -> Sequence[LspDiagnostic] | None:
    """The diagnostics a server published for the file, whatever spelling of its URI it used
    (pyright on Windows writes file:///c%3A/... for Path.as_uri()'s file:///C:/...)."""
    published: Mapping[str, Sequence[LspDiagnostic]] = client.diagnostics
    if uri in published:
        return published[uri]
    key = uri_key(uri)
    for name, diagnostics in published.items():
        if uri_key(name) == key:
            return diagnostics
    return None


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
        extra_environment: Mapping[str, str] | None = None,
    ) -> None:
        self._command = tuple(command)
        self._init_timeout = init_timeout
        # Added to the clean environment (the desktop runs JavaScript servers with its own
        # Electron as Node: ELECTRON_RUN_AS_NODE=1).
        self._extra_environment = dict(extra_environment or {})
        self._workspace_folders: list[dict[str, str]] = []
        self._process: Process | None = None
        self._job: Any = None
        self._stdin: StreamWriter | None = None
        self._stdout: StreamReader | None = None
        self._stderr: StreamReader | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._stderr_tail = b""
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._request_id = 0
        self._closed = False
        self._connection_lost = False
        self._capabilities: dict[str, Any] | None = None
        self._diagnostics: dict[str, list[LspDiagnostic]] = {}

    @property
    def diagnostics(self) -> dict[str, list[LspDiagnostic]]:
        """Diagnostics recorded so far, keyed by document URI."""
        return dict(self._diagnostics)

    @property
    def alive(self) -> bool:
        """The server is running and its output is still being read: false once it exited or
        closed its output, though the process handle stays until shutdown_exit."""
        process = self._process
        return (
            process is not None
            and process.returncode is None
            and not self._closed
            and not self._connection_lost
        )

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
        environment = {**_lsp_environment(), **self._extra_environment}
        folders = initialize_params.get("workspaceFolders")
        if isinstance(folders, list):
            self._workspace_folders = [item for item in folders if isinstance(item, dict)]
        try:
            process = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=creationflags,
                env=environment,
                limit=_MAX_MESSAGE_BYTES + 64 * 1024,
                start_new_session=HELPER_SERVER_NEW_SESSION,
            )
        except OSError as exc:
            raise LspClientError(f"cannot start LSP server {self._command[0]!r}: {exc}") from exc
        self._process = process
        self._job = helper_server_job(process.pid)
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
                if "id" in message and isinstance(message.get("method"), str):
                    # A request from the server (pyright asks for its settings): answered, not
                    # taken for the response to one of ours that has the same id.
                    await self._answer_server_request(message)
                elif "id" in message:
                    self._resolve_response(message)
                else:
                    self._handle_notification(message)
        except asyncio.CancelledError:
            raise
        except (asyncio.IncompleteReadError, OSError):
            self._connection_lost = True
            self._fail_pending(
                LspClientError(await self._server_exit_message("LSP server closed the connection"))
            )
        except LspClientError as exc:
            self._connection_lost = True
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

    async def _answer_server_request(self, message: dict[str, Any]) -> None:
        method = message["method"]
        params = message.get("params")
        result: Any = None
        if method == "workspace/configuration":
            items = params.get("items") if isinstance(params, dict) else None
            result = [None] * (len(items) if isinstance(items, list) else 0)
        elif method == "workspace/workspaceFolders":
            result = self._workspace_folders
        with suppress(LspClientError, OSError):
            await self._send({"jsonrpc": "2.0", "id": message["id"], "result": result})

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
        job, self._job = self._job, None
        try:
            if process.returncode is None:
                with suppress(Exception):
                    await asyncio.wait_for(process.wait(), timeout=_TERMINATE_SECONDS)
        finally:
            # Also after the server exited by itself: what it started (a node behind npx or a
            # .cmd shim) can still be running.
            await end_helper_server(process, job, grace_seconds=_TERMINATE_SECONDS)

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
            "Run a language server over a workspace file and return diagnostics (errors/warnings). "
            "The server is chosen by the file's type from those installed on this computer."
        ),
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "minLength": 1}},
            "required": ["path"],
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

    def _server_command(self, path: Path) -> tuple[str, ...]:
        spec = spec_for(path)
        found = find_server(spec, None) if spec is not None else None
        if found is None:
            raise ToolError(f"no language server for {path.suffix or path.name} files is installed")
        return found.command

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._SPEC, arguments)
        path_text = require_string(arguments, "path")

        path = self.paths.resolve(path_text)
        text = self._read_workspace_file(path)
        # Not cached by this file's size and time: its diagnostics also change with the files
        # it uses (a function's signature changed elsewhere).
        command = self._server_command(path)
        language_id = _infer_language_id(path)
        uri = path.as_uri()
        relative = self.paths.relative(path)
        root_uri = self.paths.root.as_uri()
        initialize_params: dict[str, Any] = {
            "capabilities": {},
            "rootUri": root_uri,
            "workspaceFolders": [{"uri": root_uri, "name": self.paths.root.name or "workspace"}],
        }
        spec = spec_for(path)
        if spec is not None and spec.initialization_options:
            initialize_params["initializationOptions"] = dict(spec.initialization_options)

        client = StdioLspClient(command)
        try:
            await client.connect(initialize_params)
            await client.did_open(uri, language_id, 1, text)
            wait_expired = await self._wait_for_diagnostics(client, uri)
        finally:
            await client.shutdown_exit()

        diagnostics = self._render_diagnostics(_diagnostics_for(client, uri) or ())
        return json_result(
            {
                "path": relative,
                "diagnostics": diagnostics,
                "wait_expired": wait_expired,
            }
        )

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
        """Wait for the file's diagnostics, then for a short quiet spell in case a fuller
        result follows; True when none came in time."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _DIAGNOSTIC_WAIT_SECONDS
        last: Sequence[LspDiagnostic] | None = None
        quiet_until = deadline
        while True:
            current = _diagnostics_for(client, uri)
            now = loop.time()
            if current is not None:
                # Each publication is a new list: a different object is a newer result.
                if current is not last:
                    last = current
                    quiet_until = now + _DIAGNOSTIC_SETTLE_SECONDS
                elif now >= quiet_until:
                    return False
            if now >= deadline:
                return current is None
            await asyncio.sleep(min(_DIAGNOSTIC_POLL_SECONDS, deadline - now))

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
