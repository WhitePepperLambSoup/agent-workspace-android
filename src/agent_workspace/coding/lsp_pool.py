"""Language servers for the open folders, shared by the agent's tools and the editor.

Each (folder, server) pair gets one server process, started on first use and stopped after it
has been idle a while. All of them live on one event loop in a thread of their own, so a tool
running in a conversation's loop and an editor request on a gateway thread reach the same
servers. Files are sent from disk, or as the editor holds them, before every question.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import os
import shutil
import threading
import time
from collections.abc import Callable, Coroutine
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from agent_workspace.tools.lsp import LspClientError, LspDiagnostic, StdioLspClient

from .install import install_server
from .servers import SERVERS, ServerCommand, find_node, find_server, language_id, spec_for

T = TypeVar("T")

_MAX_FILE_BYTES = 4 * 1024 * 1024
_IDLE_SECONDS = 600.0
_FAILED_RETRY_SECONDS = 60.0
_FIND_CACHE_SECONDS = 30.0
_REQUEST_SECONDS = 20.0


@dataclass(frozen=True, slots=True)
class Location:
    path: Path
    line: int  # 0-based
    character: int  # 0-based, in Python characters
    end_line: int
    end_character: int


@dataclass(frozen=True, slots=True)
class Symbol:
    name: str
    kind: int
    line: int
    end_line: int
    depth: int
    detail: str = ""
    path: Path | None = None


@dataclass(frozen=True, slots=True)
class DiagnosticsReport:
    server: str
    diagnostics: tuple[LspDiagnostic, ...]
    # True when the server had not answered for this text before the wait ran out.
    pending: bool


class NoServerError(RuntimeError):
    """No language server for this kind of file is available."""

    def __init__(self, path: Path) -> None:
        spec = spec_for(path)
        self.server_id = spec.id if spec is not None else None
        self.server_name = spec.name if spec is not None else None
        super().__init__(
            f"no language server for {path.suffix or path.name} files"
            + (f" ({spec.name} is not installed)" if spec is not None else "")
        )


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


def utf16_units(text: str, index: int) -> int:
    """Python character index -> UTF-16 code units (LSP positions)."""
    return index + sum(1 for char in text[:index] if ord(char) > 0xFFFF)


def from_utf16_units(text: str, units: int) -> int:
    count = 0
    for index, char in enumerate(text):
        if count >= units:
            return index
        count += 2 if ord(char) > 0xFFFF else 1
    return len(text)


class _Client(StdioLspClient):
    """The shared stdio client, plus waiting for the next diagnostics of a file and answering
    the settings a server asks for."""

    def __init__(self, *args: Any, settings: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.published: dict[str, int] = {}
        self._waiters: dict[str, list[asyncio.Future[None]]] = {}
        self._settings = settings

    def _record_diagnostics(self, params: Any) -> None:
        uri = params.get("uri") if isinstance(params, dict) else None
        if not isinstance(uri, str):
            return
        key = uri_key(uri)
        # Kept under the key, so they are found whatever spelling the server used.
        super()._record_diagnostics({**params, "uri": key})
        self.published[key] = self.published.get(key, 0) + 1
        for waiter in self._waiters.pop(key, []):
            if not waiter.done():
                waiter.set_result(None)

    async def wait_published(self, key: str, seen: int, timeout: float) -> bool:
        """True once diagnostics newer than ``seen`` arrived for the file (by uri_key)."""
        if self.published.get(key, 0) > seen:
            return True
        waiter: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._waiters.setdefault(key, []).append(waiter)
        try:
            await asyncio.wait_for(waiter, timeout)
        except TimeoutError:
            return False
        return True

    async def _answer_server_request(self, message: dict[str, Any]) -> None:
        if message.get("method") != "workspace/configuration":
            await super()._answer_server_request(message)
            return
        params = message.get("params")
        items = params.get("items") if isinstance(params, dict) else None
        answers = [
            self._settings.get(str(item.get("section") or "")) if isinstance(item, dict) else None
            for item in (items if isinstance(items, list) else [])
        ]
        with suppress(LspClientError, OSError):
            await self._send({"jsonrpc": "2.0", "id": message["id"], "result": answers})


@dataclass(slots=True)
class _Session:
    client: _Client
    root: Path
    server: ServerCommand
    documents: dict[str, tuple[int, str]] = field(default_factory=dict)
    last_used: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def _venv_python(root: Path) -> Path | None:
    for folder in (".venv", "venv", "env"):
        for relative in ("Scripts/python.exe", "bin/python"):
            candidate = root / folder / relative
            if candidate.is_file():
                return candidate
    return None


def _capabilities() -> dict[str, Any]:
    return {
        "textDocument": {
            "synchronization": {"dynamicRegistration": False, "didSave": True},
            "publishDiagnostics": {"relatedInformation": False, "versionSupport": True},
            "definition": {"linkSupport": True},
            "references": {},
            "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
            "hover": {"contentFormat": ["plaintext", "markdown"]},
        },
        "workspace": {"workspaceFolders": True, "configuration": True, "symbol": {}},
        "window": {"workDoneProgress": False},
    }


class LspPool:
    def __init__(
        self,
        tools_dir: Path,
        *,
        idle_seconds: float = _IDLE_SECONDS,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self.tools_dir = tools_dir
        self._idle_seconds = idle_seconds
        self._which = which
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._thread_lock = threading.Lock()
        self._sessions: dict[tuple[str, str], _Session] = {}
        self._starting: dict[tuple[str, str], asyncio.Future[_Session]] = {}
        self._failed: dict[tuple[str, str], tuple[float, str]] = {}
        self._found: dict[str, tuple[float, ServerCommand | None]] = {}
        self._reaper: concurrent.futures.Future[None] | None = None
        self._closed = False

    # -- which servers there are

    def find(self, path: str | Path) -> ServerCommand | None:
        spec = spec_for(path)
        if spec is None:
            return None
        now = time.monotonic()
        cached = self._found.get(spec.id)
        if cached is not None and now - cached[0] < _FIND_CACHE_SECONDS:
            return cached[1]
        found = find_server(spec, self.tools_dir, which=self._which)
        self._found[spec.id] = (now, found)
        return found

    def any_available(self) -> bool:
        return any(self.find(f"x{next(iter(spec.languages))}") for spec in SERVERS)

    def status(self) -> list[dict[str, object]]:
        node = find_node(self._which) is not None
        rows: list[dict[str, object]] = []
        for spec in SERVERS:
            found = self.find(f"x{next(iter(spec.languages))}")
            rows.append(
                {
                    "id": spec.id,
                    "name": spec.name,
                    "extensions": sorted(spec.languages),
                    "available": found is not None,
                    "source": found.source if found is not None else None,
                    "installable": bool(spec.npm) and node,
                    "needsNode": bool(spec.npm) and not node,
                    "hint": spec.hint,
                    "running": any(
                        session.server.spec.id == spec.id for session in self._sessions.values()
                    ),
                }
            )
        return rows

    def install(self, server_id: str) -> dict[str, str]:
        spec = next((item for item in SERVERS if item.id == server_id), None)
        if spec is None:
            raise ValueError(f"unknown language server: {server_id}")
        versions = install_server(spec, self.tools_dir)
        self._found.pop(spec.id, None)
        for key in [key for key in self._failed if key[1] == spec.id]:
            self._failed.pop(key, None)
        return versions

    # -- running work on the pool's loop

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._thread_lock:
            if self._closed:
                raise RuntimeError("the language servers are closed")
            if self._loop is None:
                loop = asyncio.new_event_loop()
                thread = threading.Thread(
                    target=loop.run_forever, name="agent-workspace-lsp", daemon=True
                )
                thread.start()
                self._loop, self._thread = loop, thread
                self._reaper = asyncio.run_coroutine_threadsafe(self._reap_idle(), loop)
            return self._loop

    def run(self, work: Callable[[], Coroutine[Any, Any, T]], timeout: float = 60.0) -> T:
        """Run on the pool's loop from a thread without one (the gateway)."""
        future = asyncio.run_coroutine_threadsafe(work(), self._ensure_loop())
        return future.result(timeout)

    async def call(self, work: Callable[[], Coroutine[Any, Any, T]]) -> T:
        """Run on the pool's loop from another event loop (a conversation's tools)."""
        future = asyncio.run_coroutine_threadsafe(work(), self._ensure_loop())
        return await asyncio.wrap_future(future)

    async def _reap_idle(self) -> None:
        while not self._closed:
            await asyncio.sleep(min(60.0, self._idle_seconds))
            now = time.monotonic()
            for key, session in list(self._sessions.items()):
                if now - session.last_used > self._idle_seconds and not session.lock.locked():
                    self._sessions.pop(key, None)
                    await session.client.shutdown_exit()

    def close(self) -> None:
        with self._thread_lock:
            loop, thread = self._loop, self._thread
            self._closed = True
        if loop is None:
            return
        if self._reaper is not None:
            self._reaper.cancel()

        async def stop_all() -> None:
            sessions = list(self._sessions.values())
            self._sessions.clear()
            await asyncio.gather(
                *(session.client.shutdown_exit() for session in sessions), return_exceptions=True
            )

        with suppress(Exception):
            asyncio.run_coroutine_threadsafe(stop_all(), loop).result(15)
        loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(5)

    # -- sessions and documents (on the pool's loop)

    async def _session(self, root: Path, path: Path) -> _Session:
        server = self.find(path)
        if server is None:
            raise NoServerError(path)
        key = (str(root).casefold(), server.spec.id)
        session = self._sessions.get(key)
        if session is not None and session.client._process is not None:
            session.last_used = time.monotonic()
            return session
        failed = self._failed.get(key)
        if failed is not None and time.monotonic() - failed[0] < _FAILED_RETRY_SECONDS:
            raise LspClientError(failed[1])
        starting = self._starting.get(key)
        if starting is not None:
            return await asyncio.shield(starting)
        future: asyncio.Future[_Session] = asyncio.get_running_loop().create_future()
        self._starting[key] = future
        try:
            session = await self._start(root, server)
        except BaseException as error:
            self._failed[key] = (time.monotonic(), str(error))
            future.set_exception(error)
            future.exception()  # read here, so a start nobody else waited on is not reported
            raise
        finally:
            self._starting.pop(key, None)
        self._sessions[key] = session
        future.set_result(session)
        return session

    async def _start(self, root: Path, server: ServerCommand) -> _Session:
        settings: dict[str, Any] = {"python.analysis": {"diagnosticMode": "openFilesOnly"}}
        python = _venv_python(root)
        if python is not None:
            settings["python"] = {"pythonPath": str(python)}
        client = _Client(server.command, extra_environment=server.environment, settings=settings)
        root_uri = root.as_uri()
        options: dict[str, Any] = dict(server.spec.initialization_options)
        tsserver = self.tools_dir / "node_modules" / "typescript" / "lib" / "tsserver.js"
        if server.spec.id == "typescript" and tsserver.is_file():
            # Our own TypeScript, not one the folder brings along.
            options["tsserver"] = {"path": str(tsserver)}
        await client.connect(
            {
                "processId": os.getpid(),
                "clientInfo": {"name": "Agent Workspace"},
                "rootUri": root_uri,
                "rootPath": str(root),
                "workspaceFolders": [{"uri": root_uri, "name": root.name or "workspace"}],
                "capabilities": _capabilities(),
                "initializationOptions": options,
            }
        )
        return _Session(client, root, server)

    async def _sync(self, session: _Session, path: Path, text: str | None) -> tuple[str, int, str]:
        """Send the file's text if the server has not seen it; returns (uri, diagnostics seen
        before this text, text)."""
        if text is None:
            data = path.read_bytes()
            if len(data) > _MAX_FILE_BYTES:
                raise LspClientError(f"{path.name} is too large for the language server")
            text = data.decode("utf-8", errors="replace")
        uri = path.as_uri()
        digest = hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest()
        known = session.documents.get(uri)
        seen = session.client.published.get(uri_key(uri), 0)
        if known is None:
            await session.client.did_open(uri, language_id(path), 1, text)
            session.documents[uri] = (1, digest)
        elif known[1] != digest:
            version = known[0] + 1
            await session.client._send_notification(
                "textDocument/didChange",
                {
                    "textDocument": {"uri": uri, "version": version},
                    "contentChanges": [{"text": text}],
                },
            )
            session.documents[uri] = (version, digest)
        else:
            seen = -1  # unchanged: what the server last said still stands
        return uri, seen, text

    # -- questions (coroutines for the pool's loop)

    async def diagnostics(
        self, root: Path, path: Path, text: str | None = None, wait: float = 8.0
    ) -> DiagnosticsReport:
        session = await self._session(root, path)
        async with session.lock:
            uri, seen, _ = await self._sync(session, path, text)
            key = uri_key(uri)
            pending = False
            if seen >= 0 or key not in session.client.published:
                pending = not await session.client.wait_published(key, max(seen, 0), wait)
            session.last_used = time.monotonic()
            found = tuple(session.client.diagnostics.get(key, ()))
        return DiagnosticsReport(session.server.spec.name, found, pending)

    async def _position_request(
        self, method: str, root: Path, path: Path, line: int, character: int, extra: dict[str, Any]
    ) -> Any:
        session = await self._session(root, path)
        async with session.lock:
            uri, _, text = await self._sync(session, path, None)
            lines = text.splitlines()
            line_text = lines[line] if 0 <= line < len(lines) else ""
            result = await session.client.request(
                method,
                {
                    "textDocument": {"uri": uri},
                    "position": {"line": line, "character": utf16_units(line_text, character)},
                    **extra,
                },
                timeout=_REQUEST_SECONDS,
            )
            session.last_used = time.monotonic()
        return result

    async def definition(self, root: Path, path: Path, line: int, character: int) -> list[Location]:
        result = await self._position_request(
            "textDocument/definition", root, path, line, character, {}
        )
        return self._locations(result)

    async def references(self, root: Path, path: Path, line: int, character: int) -> list[Location]:
        result = await self._position_request(
            "textDocument/references",
            root,
            path,
            line,
            character,
            {"context": {"includeDeclaration": True}},
        )
        return self._locations(result)

    async def hover(self, root: Path, path: Path, line: int, character: int) -> str:
        result = await self._position_request("textDocument/hover", root, path, line, character, {})
        if not isinstance(result, dict):
            return ""
        contents = result.get("contents")
        parts = contents if isinstance(contents, list) else [contents]
        texts = [
            part if isinstance(part, str) else str(part.get("value", ""))
            for part in parts
            if isinstance(part, (str, dict))
        ]
        return "\n".join(text for text in texts if text).strip()

    async def document_symbols(self, root: Path, path: Path) -> list[Symbol]:
        session = await self._session(root, path)
        async with session.lock:
            uri, _, _ = await self._sync(session, path, None)
            result = await session.client.request(
                "textDocument/documentSymbol", {"textDocument": {"uri": uri}}, _REQUEST_SECONDS
            )
            session.last_used = time.monotonic()
        symbols: list[Symbol] = []

        def walk(items: list[Any], depth: int) -> None:
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                    continue
                span = item.get("range") or (item.get("location") or {}).get("range") or {}
                start = (span.get("start") or {}).get("line", 0)
                end = (span.get("end") or {}).get("line", start)
                symbols.append(
                    Symbol(
                        item["name"],
                        int(item.get("kind", 0)),
                        int(start),
                        int(end),
                        depth,
                        str(item.get("detail") or ""),
                    )
                )
                children = item.get("children")
                if isinstance(children, list):
                    walk(children, depth + 1)

        walk(result if isinstance(result, list) else [], 0)
        return symbols

    async def workspace_symbols(self, root: Path, sample: Path, query: str) -> list[Symbol]:
        session = await self._session(root, sample)
        async with session.lock:
            if sample.is_file():
                await self._sync(session, sample, None)  # some servers index only after a file
            result = await session.client.request(
                "workspace/symbol", {"query": query}, _REQUEST_SECONDS
            )
            session.last_used = time.monotonic()
        symbols: list[Symbol] = []
        for item in result if isinstance(result, list) else []:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            location = item.get("location") or {}
            target = path_from_uri(str(location.get("uri", "")))
            span = (location.get("range") or {}).get("start") or {}
            line = int(span.get("line", 0))
            symbols.append(
                Symbol(item["name"], int(item.get("kind", 0)), line, line, 0, "", target)
            )
        return symbols

    def _locations(self, result: Any) -> list[Location]:
        items = result if isinstance(result, list) else [result] if isinstance(result, dict) else []
        found: list[Location] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            uri = item.get("uri") or item.get("targetUri")
            span = item.get("range") or item.get("targetSelectionRange") or item.get("targetRange")
            target = path_from_uri(str(uri or ""))
            if target is None or not isinstance(span, dict):
                continue
            start, end = span.get("start") or {}, span.get("end") or {}
            line, end_line = int(start.get("line", 0)), int(end.get("line", 0))
            character, end_character = int(start.get("character", 0)), int(end.get("character", 0))
            line_text = _line_of(target, line)
            found.append(
                Location(
                    target,
                    line,
                    from_utf16_units(line_text, character),
                    end_line,
                    from_utf16_units(_line_of(target, end_line), end_character),
                )
            )
        return found


def _line_of(path: Path, line: int) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for index, text in enumerate(handle):
                if index == line:
                    return text.rstrip("\r\n")
    except OSError:
        pass
    return ""


__all__ = [
    "DiagnosticsReport",
    "Location",
    "LspPool",
    "NoServerError",
    "Symbol",
    "from_utf16_units",
    "path_from_uri",
    "uri_key",
    "utf16_units",
]
