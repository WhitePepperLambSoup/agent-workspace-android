from __future__ import annotations

import asyncio
import contextlib
import threading
import tomllib
from collections.abc import Awaitable, Coroutine, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_workspace.tools.base import ToolError
from agent_workspace.tools.mcp_allowlist import (
    CompositeMcpAllowlist,
    McpAllowlist,
    McpAllowlistError,
)
from agent_workspace.tools.mcp_client import McpProxyTool, StdioMcpClient
from agent_workspace.tools.paths import StrPath

_CONNECT_TIMEOUT_SECONDS = 20.0


class McpHostError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class McpServerConfig:
    id: str
    command: tuple[str, ...]
    allowlist: McpAllowlist | CompositeMcpAllowlist = field(default_factory=McpAllowlist)


def load_mcp_servers(workspace: StrPath) -> tuple[McpServerConfig, ...]:
    """Load MCP stdio server declarations from .agent/mcp.toml."""
    root = Path(workspace)
    try:
        root = root.resolve(strict=True)
    except (OSError, RuntimeError):
        return ()
    path = root / ".agent" / "mcp.toml"
    if not path.is_file():
        return ()
    try:
        with path.open("rb") as stream:
            raw: object = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise McpHostError(f"cannot read MCP config {path}: {exc}") from None
    if not isinstance(raw, dict) or not isinstance(raw.get("servers"), list):
        raise McpHostError(f"MCP config {path} must declare a [[servers]] list")
    try:
        global_allowlist = _allowlist_from_raw(raw.get("allowlist"))
    except McpAllowlistError as exc:
        raise McpHostError(f"MCP config {path} allowlist is invalid: {exc}") from None
    servers: list[McpServerConfig] = []
    for entry in raw["servers"]:
        if not isinstance(entry, dict):
            raise McpHostError(f"MCP config {path} contains an invalid server entry")
        server_id = entry.get("id")
        command = entry.get("command")
        if (
            not isinstance(server_id, str)
            or not server_id
            or len(server_id) > 64
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789._-"
                for character in server_id
            )
            or not isinstance(command, list)
            or len(command) < 1
            or any(not isinstance(item, str) or not item for item in command)
        ):
            raise McpHostError(f"MCP config {path} contains an invalid server entry")
        if any(server.id == server_id for server in servers):
            raise McpHostError(f"MCP server id {server_id!r} is duplicated")
        try:
            server_allowlist = _allowlist_from_raw(entry.get("allowlist"))
        except McpAllowlistError as exc:
            raise McpHostError(f"MCP config {path} allowlist is invalid: {exc}") from None
        if global_allowlist.allow or global_allowlist.deny:
            effective_allowlist: McpAllowlist | CompositeMcpAllowlist = CompositeMcpAllowlist(
                global_allowlist, server_allowlist
            )
        else:
            effective_allowlist = server_allowlist
        servers.append(
            McpServerConfig(
                server_id,
                tuple(command),
                effective_allowlist,
            )
        )
    return tuple(servers)


def _allowlist_from_raw(raw: object) -> McpAllowlist:
    if raw is None:
        return McpAllowlist()
    if not isinstance(raw, dict):
        raise McpAllowlistError("MCP allowlist must be a table")
    allow = raw.get("allow", ())
    deny = raw.get("deny", ())
    if not isinstance(allow, (list, tuple)) or not all(isinstance(item, str) for item in allow):
        raise McpAllowlistError("MCP allowlist 'allow' must be a string array")
    if not isinstance(deny, (list, tuple)) or not all(isinstance(item, str) for item in deny):
        raise McpAllowlistError("MCP allowlist 'deny' must be a string array")
    return McpAllowlist(tuple(allow), tuple(deny))


class McpHost:
    """Hosts MCP stdio clients on a dedicated event loop thread.

    The application runtime is constructed synchronously, so connecting is a
    blocking bootstrap step with a bounded timeout; tool calls submitted from
    the main event loop are bridged onto the host loop afterwards.
    """

    def __init__(self, servers: tuple[McpServerConfig, ...]) -> None:
        self._servers = servers
        self._clients: list[StdioMcpClient] = []
        self._proxies: tuple[McpProxyTool, ...] = ()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="agent-workspace-mcp",
            daemon=True,
        )
        self._connected = False
        self._closed = False

    def _run_loop(self) -> None:
        """Run the host loop and close it when run_forever exits."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            with contextlib.suppress(BaseException):
                self._loop.close()

    def connect_sync(
        self,
        *,
        timeout: float = _CONNECT_TIMEOUT_SECONDS,
    ) -> tuple[McpProxyTool, ...]:
        if self._connected or self._closed:
            return self._proxies
        self._thread.start()
        try:
            future = asyncio.run_coroutine_threadsafe(self._connect(), self._loop)
            self._proxies = tuple(future.result(timeout=timeout))
        except BaseException:
            self.close_sync()
            raise
        self._connected = True
        return self._proxies

    def tools(self) -> tuple[McpProxyTool, ...]:
        return self._proxies

    def health_sync(self, *, timeout: float = 2.0) -> tuple[dict[str, Any], ...]:
        """Ping each connected MCP server on the host loop."""
        if not self._connected or self._closed:
            return ()
        futures = [
            (
                client,
                asyncio.run_coroutine_threadsafe(client.ping(), self._loop),
            )
            for client in self._clients
        ]
        reports: list[dict[str, Any]] = []
        for client, future in futures:
            try:
                future.result(timeout=timeout)
                reports.append({"command": list(client.command), "healthy": True})
            except BaseException:
                reports.append({"command": list(client.command), "healthy": False})
        return tuple(reports)

    def ensure_healthy_sync(
        self,
        *,
        timeout: float = _CONNECT_TIMEOUT_SECONDS,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
    ) -> tuple[dict[str, Any], ...]:
        """Ping servers and reconnect failed children before returning reports."""
        reports = self.health_sync(timeout=min(timeout, 2.0))
        if not any(not bool(report.get("healthy")) for report in reports):
            return reports
        unhealthy_ids = {
            server.id
            for server, report in zip(self._servers, reports, strict=False)
            if not bool(report.get("healthy"))
        }
        reconnect = self.reconnect_sync(
            timeout=timeout,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            server_ids=unhealthy_ids,
        )
        by_server = {str(report.get("server_id")): report for report in reconnect}
        health_by_server = {
            server.id: report for server, report in zip(self._servers, reports, strict=False)
        }
        return tuple(
            {
                "command": list(client.command),
                "healthy": (
                    bool(by_server[server.id].get("connected", False))
                    if server.id in by_server
                    else bool(health_by_server.get(server.id, {}).get("healthy", False))
                ),
            }
            for server, client in zip(self._servers, self._clients, strict=False)
        )

    def status_sync(self, *, timeout: float = 2.0) -> tuple[dict[str, Any], ...]:
        """Return connection state for every configured MCP server."""
        del timeout  # Kept for parity with ``health_sync`` and future probes.
        if self._closed:
            return ()
        return tuple(
            {
                "server_id": server.id,
                "command": list(client.command),
                **client.status(),
            }
            for server, client in zip(self._servers, self._clients, strict=False)
        )

    def reconnect_sync(
        self,
        *,
        timeout: float = _CONNECT_TIMEOUT_SECONDS,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
        server_ids: set[str] | None = None,
    ) -> tuple[dict[str, Any], ...]:
        """Reconnect unhealthy MCP servers and return bounded lifecycle reports."""
        if self._closed or not self._connected:
            return ()
        selected = tuple(
            (server, client)
            for server, client in zip(self._servers, self._clients, strict=False)
            if server_ids is None or server.id in server_ids
        )
        futures = [
            (
                server,
                client,
                asyncio.run_coroutine_threadsafe(
                    client.reconnect(
                        max_attempts=max_attempts,
                        backoff_seconds=backoff_seconds,
                    ),
                    self._loop,
                ),
            )
            for server, client in selected
        ]
        reports: list[dict[str, Any]] = []
        for server, client, future in futures:
            try:
                report = future.result(timeout=timeout)
            except BaseException as exc:
                reports.append(
                    {
                        "server_id": server.id,
                        "command": list(client.command),
                        "connected": False,
                        "error": " ".join(str(exc).split())[:1000] or type(exc).__name__,
                    }
                )
            else:
                reports.append(
                    {
                        "server_id": server.id,
                        "command": list(client.command),
                        **report,
                    }
                )
        return tuple(reports)

    async def _connect(self) -> list[McpProxyTool]:
        import re

        proxies: list[McpProxyTool] = []
        registered_names: set[str] = set()
        for server in self._servers:
            client = StdioMcpClient(server.command)
            await client.connect()
            self._clients.append(client)
            definitions = await client.list_tools()
            definitions = tuple(
                definition for definition in definitions if server.allowlist.allows(definition.name)
            )
            for definition in definitions:
                base_name = "mcp_" + re.sub(r"[^a-zA-Z0-9_-]", "_", definition.name)
                if base_name in registered_names:
                    tool_name = f"mcp_{server.id}_{re.sub(r'[^a-zA-Z0-9_-]', '_', definition.name)}"
                else:
                    tool_name = base_name
                if tool_name in registered_names:
                    idx = 2
                    while f"{tool_name}_{idx}" in registered_names:
                        idx += 1
                    tool_name = f"{tool_name}_{idx}"
                registered_names.add(tool_name)
                proxies.append(
                    McpProxyTool(
                        client,
                        definition,
                        submit=self.submit,
                        server_id=server.id,
                        tool_name=tool_name,
                    )
                )
        return proxies

    def submit(self, operation: Coroutine[Any, Any, str]) -> Awaitable[str]:
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            return operation
        return asyncio.wrap_future(asyncio.run_coroutine_threadsafe(operation, self._loop))

    async def aclose(self) -> None:
        for client in tuple(self._clients):
            await client.aclose()
        self._clients.clear()

    def close_sync(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._loop.is_running():

            async def _shutdown() -> None:
                await self.aclose()

            future = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
            with contextlib.suppress(BaseException):
                future.result(timeout=5.0)
            self._loop.call_soon_threadsafe(self._loop.stop)
        else:
            self._loop.close()
        self._thread.join(timeout=5.0)


def build_mcp_host(
    workspace: StrPath,
    servers: Sequence[McpServerConfig] | None = None,
) -> McpHost | None:
    if servers is None:
        servers = load_mcp_servers(workspace)
    if not servers:
        return None
    host = McpHost(tuple(servers))
    try:
        host.connect_sync()
    except BaseException as exc:
        host.close_sync()
        raise ToolError(f"MCP server startup failed: {exc}") from None
    return host
