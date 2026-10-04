"""Sandbox filesystem mount policy for secure container isolation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

_FORBIDDEN_DIR_NAMES = frozenset(
    {
        ".ssh",
        ".aws",
        ".gnupg",
        ".docker",
        ".kube",
    }
)


@dataclass(frozen=True, slots=True)
class MountDecision:
    allowed: bool
    reason: str
    host_path: str
    container_path: str
    read_only: bool

    def to_document(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "host_path": self.host_path,
            "container_path": self.container_path,
            "read_only": self.read_only,
        }


class SandboxMountPolicy:
    """Policy restricting host directory mounts into execution sandboxes."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        allow_subpath_write: bool = True,
        extra_forbidden_paths: tuple[str | Path, ...] = (),
    ) -> None:
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self.allow_subpath_write = allow_subpath_write
        self.extra_forbidden_paths = tuple(
            Path(p).expanduser().resolve() for p in extra_forbidden_paths
        )

    def evaluate_mount(
        self,
        host_path: str | Path,
        container_path: str,
        *,
        read_only: bool = True,
    ) -> MountDecision:
        """Evaluate whether a host directory mount is allowed into the sandbox."""
        resolved = Path(host_path).expanduser().resolve()

        # Check system root mounts
        if resolved == resolved.parent:
            return MountDecision(
                allowed=False,
                reason="Cannot mount root filesystem into sandbox",
                host_path=str(resolved),
                container_path=container_path,
                read_only=read_only,
            )

        # Check forbidden directories
        for part in resolved.parts:
            if part.lower() in _FORBIDDEN_DIR_NAMES:
                return MountDecision(
                    allowed=False,
                    reason=f"Mounting sensitive directory '{part}' is strictly forbidden",
                    host_path=str(resolved),
                    container_path=container_path,
                    read_only=read_only,
                )

        # Check explicit forbidden paths
        for forbidden in self.extra_forbidden_paths:
            if resolved == forbidden or forbidden in resolved.parents:
                return MountDecision(
                    allowed=False,
                    reason=f"Host path is in forbidden list: {forbidden}",
                    host_path=str(resolved),
                    container_path=container_path,
                    read_only=read_only,
                )

        # Check workspace boundary
        try:
            resolved.relative_to(self.workspace_root)
            is_inside_workspace = True
        except ValueError:
            is_inside_workspace = False

        if not is_inside_workspace and not read_only:
            return MountDecision(
                allowed=False,
                reason="Host paths outside workspace cannot be mounted read-write",
                host_path=str(resolved),
                container_path=container_path,
                read_only=read_only,
            )

        if not read_only and not self.allow_subpath_write:
            return MountDecision(
                allowed=False,
                reason="Read-write mounts are disabled by policy",
                host_path=str(resolved),
                container_path=container_path,
                read_only=read_only,
            )

        return MountDecision(
            allowed=True,
            reason="Mount authorized",
            host_path=str(resolved),
            container_path=container_path,
            read_only=read_only,
        )

    def enforce_mount(
        self,
        host_path: str | Path,
        container_path: str,
        *,
        read_only: bool = True,
    ) -> MountDecision:
        """Evaluate and raise PermissionError if mount is not allowed."""
        decision = self.evaluate_mount(host_path, container_path, read_only=read_only)
        if not decision.allowed:
            raise PermissionError(f"Sandbox mount denied: {decision.reason}")
        return decision
