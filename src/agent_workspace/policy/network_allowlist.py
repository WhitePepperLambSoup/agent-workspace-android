"""Sandbox network allowlist policy.

This module provides the policy half for sandbox implementations that support
network allowlists: callers validate a requested hostname or CIDR before
configuring sandbox network access. The default host-staged backend keeps the
host network visible and does not claim to enforce this policy as an operating
system boundary.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from urllib.parse import urlsplit


class NetworkAllowlistError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NetworkAllowlistEntry:
    id: str
    pattern: str

    def __post_init__(self) -> None:
        if not self.id or not self.pattern:
            raise NetworkAllowlistError("network allowlist id and pattern may not be empty")
        self._validate_pattern(self.pattern)

    @staticmethod
    def _validate_pattern(pattern: str) -> None:
        lowered = pattern.casefold()
        if lowered in {"*", "*.*"}:
            return
        if "/" in pattern:
            try:
                ipaddress.ip_network(pattern, strict=False)
                return
            except ValueError:
                raise NetworkAllowlistError(
                    f"network allowlist CIDR is invalid: {pattern}"
                ) from None
        if not lowered or any(character in lowered for character in " /\\"):
            raise NetworkAllowlistError(f"network allowlist domain is invalid: {pattern}")

    def matches(self, value: str) -> bool:
        lowered = value.casefold().rstrip(".")
        pattern = self.pattern.casefold().rstrip(".")
        if pattern in {"*", "*.*"}:
            return True
        if "/" in pattern:
            try:
                address = ipaddress.ip_address(value)
            except ValueError:
                return False
            try:
                return address in ipaddress.ip_network(pattern, strict=False)
            except ValueError:
                return False
        return lowered == pattern or lowered.endswith("." + pattern)


@dataclass(frozen=True, slots=True)
class SandboxNetworkPolicy:
    entries: tuple[NetworkAllowlistEntry, ...] = field(default_factory=tuple)

    def allows(self, host_or_ip: str) -> bool:
        return any(entry.matches(host_or_ip) for entry in self.entries)

    def allows_url(self, url: str) -> bool:
        try:
            parsed = urlsplit(url)
        except ValueError:
            return False
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        return self.allows(parsed.hostname)


__all__ = [
    "NetworkAllowlistEntry",
    "NetworkAllowlistError",
    "SandboxNetworkPolicy",
]
