"""MCP tool allowlist/denylist matching."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass


class McpAllowlistError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class McpAllowlist:
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if any(not pattern for pattern in (*self.allow, *self.deny)):
            raise McpAllowlistError("MCP allowlist patterns may not be empty")

    def allows(self, name: str) -> bool:
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in self.deny):
            return False
        if not self.allow:
            return True
        return any(fnmatch.fnmatchcase(name, pattern) for pattern in self.allow)

    def filter(self, names: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(name for name in names if self.allows(name))


@dataclass(frozen=True, slots=True)
class CompositeMcpAllowlist:
    """Intersects allow constraints while merging deny constraints.

    The global allowlist serves as an upper bound ceiling: a tool must be
    permitted by both the global policy and the server-specific policy.
    Deny rules on either layer are strictly enforced.
    """

    global_allowlist: McpAllowlist
    server_allowlist: McpAllowlist

    @property
    def allow(self) -> tuple[str, ...]:
        return self.server_allowlist.allow or self.global_allowlist.allow

    @property
    def deny(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.global_allowlist.deny, *self.server_allowlist.deny)))

    def allows(self, name: str) -> bool:
        return self.global_allowlist.allows(name) and self.server_allowlist.allows(name)

    def filter(self, names: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(name for name in names if self.allows(name))


def default_allowlist() -> McpAllowlist:
    return McpAllowlist()


__all__ = ["CompositeMcpAllowlist", "McpAllowlist", "McpAllowlistError", "default_allowlist"]
