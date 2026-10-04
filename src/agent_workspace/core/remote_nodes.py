"""Remote execution node registry.

Nodes are validated configuration objects; execution is left to the process
tool so the existing approval and executable-binding policies continue to
apply. The registry only builds explicit ssh command lines.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_NODE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
_SAFE_TOKEN = re.compile(r"[A-Za-z0-9@._:/+=-]{1,256}\Z")


class RemoteNodeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RemoteNodeHealth:
    node_id: str
    state: str
    last_heartbeat_at: float | None = None
    checked_at: float | None = None
    latency_ms: float | None = None
    capabilities: tuple[str, ...] = ()
    error: str | None = None

    def to_document(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "state": self.state,
            "last_heartbeat_at": self.last_heartbeat_at,
            "checked_at": self.checked_at,
            "latency_ms": self.latency_ms,
            "capabilities": list(self.capabilities),
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class RemoteNode:
    id: str
    host: str
    user: str | None = None
    port: int = 22
    ssh_command: str = "ssh"
    capabilities: tuple[str, ...] = ()
    heartbeat_argv: tuple[str, ...] = ("printf", "agent-workspace-heartbeat")
    heartbeat_interval_seconds: float = 60.0
    heartbeat_timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if _NODE_ID.fullmatch(self.id) is None:
            raise RemoteNodeError(
                "node id must be lowercase ASCII letters, digits, '.', '_' or '-'"
            )
        if _SAFE_TOKEN.fullmatch(self.host) is None or not self.host:
            raise RemoteNodeError("node host contains unsupported characters")
        if self.user is not None and _SAFE_TOKEN.fullmatch(self.user) is None:
            raise RemoteNodeError("node user contains unsupported characters")
        if type(self.port) is not int or isinstance(self.port, bool) or not 1 <= self.port <= 65535:
            raise RemoteNodeError("node port must be from 1 to 65535")
        if _SAFE_TOKEN.fullmatch(self.ssh_command) is None or not self.ssh_command:
            raise RemoteNodeError("node ssh command contains unsupported characters")
        if any(
            not isinstance(capability, str)
            or not capability
            or len(capability) > 64
            or _SAFE_TOKEN.fullmatch(capability) is None
            for capability in self.capabilities
        ) or len(set(self.capabilities)) != len(self.capabilities):
            raise RemoteNodeError("node capabilities must be unique safe tokens")
        if not self.heartbeat_argv or any(
            not isinstance(argument, str) or not argument or len(argument) > 256
            for argument in self.heartbeat_argv
        ):
            raise RemoteNodeError("node heartbeat command is invalid")
        if self.heartbeat_interval_seconds <= 0 or self.heartbeat_timeout_seconds <= 0:
            raise RemoteNodeError("node heartbeat intervals must be positive")

    def command(self, argv: tuple[str, ...]) -> tuple[str, ...]:
        if not argv:
            raise RemoteNodeError("node command may not be empty")
        destination = self.host if self.user is None else f"{self.user}@{self.host}"
        args = [
            self.ssh_command,
            "-p",
            str(self.port),
            destination,
            shlex.join(argv),
        ]
        return tuple(args)

    def heartbeat_command(self) -> tuple[str, ...]:
        return self.command(self.heartbeat_argv)

    def to_document(self) -> dict[str, object]:
        return {
            "id": self.id,
            "host": self.host,
            "user": self.user,
            "port": self.port,
            "ssh_command": self.ssh_command,
            "capabilities": list(self.capabilities),
            "heartbeat_argv": list(self.heartbeat_argv),
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "heartbeat_timeout_seconds": self.heartbeat_timeout_seconds,
        }


class RemoteNodeRegistry:
    def __init__(self, nodes: tuple[RemoteNode, ...] = (), *, clock: Any = time.time) -> None:
        self._nodes: dict[str, RemoteNode] = {}
        self._health: dict[str, RemoteNodeHealth] = {}
        self._clock = clock
        for node in nodes:
            self.register(node)

    def register(self, node: RemoteNode) -> None:
        if node.id in self._nodes:
            raise RemoteNodeError(f"duplicate remote node id: {node.id}")
        self._nodes[node.id] = node

    def get(self, node_id: str) -> RemoteNode | None:
        return self._nodes.get(node_id)

    def nodes(self) -> tuple[RemoteNode, ...]:
        return tuple(self._nodes.values())

    def command(self, node_id: str, argv: tuple[str, ...]) -> tuple[str, ...]:
        node = self.get(node_id)
        if node is None:
            raise RemoteNodeError(f"unknown remote node: {node_id}")
        return node.command(argv)

    def supports(self, node_id: str, capability: str) -> bool:
        node = self.get(node_id)
        if node is None:
            raise RemoteNodeError(f"unknown remote node: {node_id}")
        # Resolve through ``status`` so an expired heartbeat cannot continue
        # to advertise capabilities from the last healthy observation.
        health = self.status(node_id)
        if health is not None and health.state in {"unreachable", "stale"}:
            return False
        available = set(node.capabilities)
        if health is not None and health.state == "healthy":
            available.update(health.capabilities)
        return capability in available

    def record_heartbeat(
        self,
        node_id: str,
        *,
        success: bool,
        now: float | None = None,
        capabilities: tuple[str, ...] | None = None,
        latency_ms: float | None = None,
        error: str | None = None,
    ) -> RemoteNodeHealth:
        node = self.get(node_id)
        if node is None:
            raise RemoteNodeError(f"unknown remote node: {node_id}")
        checked_at = float(self._clock()) if now is None else float(now)
        if checked_at < 0:
            raise RemoteNodeError("heartbeat timestamp must be non-negative")
        if latency_ms is not None and latency_ms < 0:
            raise RemoteNodeError("heartbeat latency must be non-negative")
        if capabilities is None:
            reported = self._health.get(node_id)
            normalized_capabilities = (
                reported.capabilities if reported is not None else node.capabilities
            )
        else:
            normalized_capabilities = tuple(capabilities)
            if any(not isinstance(item, str) or not item for item in normalized_capabilities):
                raise RemoteNodeError("heartbeat capabilities are invalid")
        previous = self._health.get(node_id)
        health = RemoteNodeHealth(
            node_id=node_id,
            state="healthy" if success else "unreachable",
            last_heartbeat_at=checked_at
            if success
            else (previous.last_heartbeat_at if previous is not None else None),
            checked_at=checked_at,
            latency_ms=float(latency_ms) if latency_ms is not None else None,
            capabilities=normalized_capabilities,
            error=None if success else (" ".join(str(error or "heartbeat failed").split())[:500]),
        )
        self._health[node_id] = health
        return health

    def status(self, node_id: str, *, now: float | None = None) -> RemoteNodeHealth:
        node = self.get(node_id)
        if node is None:
            raise RemoteNodeError(f"unknown remote node: {node_id}")
        health = self._health.get(node_id)
        if health is None:
            return RemoteNodeHealth(node_id, "unknown", capabilities=node.capabilities)
        if health.state == "unreachable":
            return health
        current = float(self._clock()) if now is None else float(now)
        if health.last_heartbeat_at is None:
            return health
        if current - health.last_heartbeat_at > node.heartbeat_interval_seconds:
            return RemoteNodeHealth(
                node_id=node_id,
                state="stale",
                last_heartbeat_at=health.last_heartbeat_at,
                checked_at=health.checked_at,
                latency_ms=health.latency_ms,
                capabilities=health.capabilities,
                error="heartbeat expired",
            )
        return health

    def statuses(self, *, now: float | None = None) -> tuple[RemoteNodeHealth, ...]:
        return tuple(self.status(node_id, now=now) for node_id in sorted(self._nodes))

    def due_for_heartbeat(self, *, now: float | None = None) -> tuple[RemoteNode, ...]:
        current = float(self._clock()) if now is None else float(now)
        due: list[RemoteNode] = []
        for node in self._nodes.values():
            health = self._health.get(node.id)
            if (
                health is None
                or health.last_heartbeat_at is None
                or (current - health.last_heartbeat_at >= node.heartbeat_interval_seconds)
            ):
                due.append(node)
        return tuple(sorted(due, key=lambda item: item.id))

    def heartbeat(
        self,
        node_id: str,
        *,
        runner: Callable[[tuple[str, ...], float], object] | None = None,
        now: float | None = None,
    ) -> RemoteNodeHealth:
        node = self.get(node_id)
        if node is None:
            raise RemoteNodeError(f"unknown remote node: {node_id}")
        command = node.heartbeat_command()
        started = time.perf_counter()
        try:
            result = (
                runner(command, node.heartbeat_timeout_seconds)
                if runner is not None
                else subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=node.heartbeat_timeout_seconds,
                    check=False,
                )
            )
            if isinstance(result, bool) and not result:
                raise OSError("heartbeat probe returned false")
            return_code = getattr(result, "returncode", 0)
            if return_code != 0:
                raise OSError(f"heartbeat exited with code {return_code}")
        except Exception as exc:
            return self.record_heartbeat(
                node_id,
                success=False,
                now=now,
                latency_ms=(time.perf_counter() - started) * 1000,
                error=str(exc),
            )
        return self.record_heartbeat(
            node_id,
            success=True,
            now=now,
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    @classmethod
    def load(cls, path: str | Path) -> RemoteNodeRegistry:
        source = Path(path)
        if not source.is_file():
            return cls()
        try:
            with source.open("rb") as stream:
                document = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise RemoteNodeError(f"cannot read remote nodes {source}: {exc}") from exc
        if not isinstance(document, dict) or not isinstance(document.get("nodes"), list):
            raise RemoteNodeError("remote node config must declare a [[nodes]] list")
        nodes: list[RemoteNode] = []
        for raw in document["nodes"]:
            if not isinstance(raw, dict):
                raise RemoteNodeError("remote node entries must be tables")
            try:
                nodes.append(
                    RemoteNode(
                        id=str(raw["id"]),
                        host=str(raw["host"]),
                        user=str(raw["user"]) if raw.get("user") is not None else None,
                        port=int(raw.get("port", 22)),
                        ssh_command=str(raw.get("ssh_command", "ssh")),
                        capabilities=tuple(str(item) for item in raw.get("capabilities", ())),
                        heartbeat_argv=tuple(
                            str(item)
                            for item in raw.get(
                                "heartbeat_argv", ("printf", "agent-workspace-heartbeat")
                            )
                        ),
                        heartbeat_interval_seconds=float(
                            raw.get("heartbeat_interval_seconds", 60.0)
                        ),
                        heartbeat_timeout_seconds=float(raw.get("heartbeat_timeout_seconds", 10.0)),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise RemoteNodeError("remote node entry is invalid") from exc
        return cls(tuple(nodes))


__all__ = ["RemoteNode", "RemoteNodeError", "RemoteNodeHealth", "RemoteNodeRegistry"]
