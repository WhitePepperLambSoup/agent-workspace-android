"""Server CORS policy validator and per-request decision helper.

The policy rejects dangerous combinations (credentials with a wildcard origin,
invalid origins, methods outside the allow-list) and emits the exact response
headers a browser preflight or actual request needs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_DEFAULT_METHODS = ("GET", "POST", "OPTIONS")
_ORIGIN_WITHOUT_PATH = re.compile(r"^[a-z][a-z0-9+.-]*://[^/?#]+$", re.IGNORECASE)


class CorsPolicyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CorsPolicy:
    allow_origins: tuple[str, ...]
    allow_methods: tuple[str, ...] = _DEFAULT_METHODS
    allow_headers: tuple[str, ...] = ("Accept", "Content-Type")
    allow_credentials: bool = False
    max_age_seconds: int = 600

    def __post_init__(self) -> None:
        if not self.allow_origins:
            raise CorsPolicyError("cors policy requires at least one allowed origin")
        if any(not isinstance(origin, str) or not origin for origin in self.allow_origins):
            raise CorsPolicyError("cors origins must be non-empty strings")
        wildcards = sum(1 for origin in self.allow_origins if origin == "*")
        if wildcards > 1:
            raise CorsPolicyError("cors wildcard origin may appear at most once")
        if self.allow_credentials and wildcards:
            raise CorsPolicyError("cors credentials may not be combined with a wildcard origin")
        for origin in self.allow_origins:
            if origin != "*" and _ORIGIN_WITHOUT_PATH.fullmatch(origin) is None:
                raise CorsPolicyError(
                    f"cors origin {origin!r} must be a scheme://host[:port] origin"
                )
        if not self.allow_methods:
            raise CorsPolicyError("cors policy requires at least one allowed method")
        if any(
            not method or not method.isupper() or not method.isascii()
            for method in self.allow_methods
        ):
            raise CorsPolicyError("cors methods must be uppercase ASCII tokens")
        if self.max_age_seconds < 0:
            raise CorsPolicyError("cors max age may not be negative")
        normalized_headers: list[str] = []
        for header in self.allow_headers:
            if not isinstance(header, str) or not header.strip():
                raise CorsPolicyError("cors headers must be non-empty strings")
            token = header.strip().casefold()
            if (
                token in {"authorization", "cookie", "set-cookie"}
                and self.allow_credentials is False
            ):
                # Credentialed headers are still legal without credentials,
                # but browsers drop them on cross-origin requests, so warn via
                # an explicit policy error to catch misconfiguration early.
                raise CorsPolicyError(
                    f"cors header {header!r} requires allow_credentials to be useful"
                )
            normalized_headers.append(header.strip())
        object.__setattr__(self, "allow_methods", tuple(self.allow_methods))
        object.__setattr__(self, "allow_headers", tuple(normalized_headers))

    def allows_origin(self, origin: str) -> bool:
        return "*" in self.allow_origins or origin in self.allow_origins

    def to_document(self) -> dict[str, Any]:
        return {
            "allow_origins": list(self.allow_origins),
            "allow_methods": list(self.allow_methods),
            "allow_headers": list(self.allow_headers),
            "allow_credentials": self.allow_credentials,
            "max_age_seconds": self.max_age_seconds,
        }


@dataclass(frozen=True, slots=True)
class CorsDecision:
    allowed: bool
    headers: tuple[tuple[str, str], ...]
    vary: bool = True

    def to_document(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "headers": [list(header) for header in self.headers],
            "vary": self.vary,
        }


def validate_cors_config(config: dict[str, Any]) -> CorsPolicy:
    if not isinstance(config, dict):
        raise CorsPolicyError("cors config must be an object")
    raw_origins = config.get("allow_origins", ())
    if isinstance(raw_origins, str) or not isinstance(raw_origins, (list, tuple)):
        raise CorsPolicyError("cors allow_origins must be a list")
    raw_methods = config.get("allow_methods", list(_DEFAULT_METHODS))
    if isinstance(raw_methods, str) or not isinstance(raw_methods, (list, tuple)):
        raise CorsPolicyError("cors allow_methods must be a list")
    raw_headers = config.get("allow_headers", ("Accept", "Content-Type"))
    if isinstance(raw_headers, str) or not isinstance(raw_headers, (list, tuple)):
        raise CorsPolicyError("cors allow_headers must be a list")
    raw_credentials = config.get("allow_credentials", False)
    if not isinstance(raw_credentials, bool):
        raise CorsPolicyError("cors allow_credentials must be a boolean")
    raw_max_age = config.get("max_age_seconds", 600)
    if isinstance(raw_max_age, bool) or not isinstance(raw_max_age, int):
        raise CorsPolicyError("cors max_age_seconds must be an integer")
    return CorsPolicy(
        allow_origins=tuple(str(origin) for origin in raw_origins),
        allow_methods=tuple(str(method) for method in raw_methods),
        allow_headers=tuple(str(header) for header in raw_headers),
        allow_credentials=raw_credentials,
        max_age_seconds=raw_max_age,
    )


def cors_decision(
    origin: str,
    *,
    policy: CorsPolicy,
    method: str = "GET",
    requested_headers: list[str] | tuple[str, ...] = (),
    preflight: bool = False,
) -> CorsDecision:
    if not origin:
        raise CorsPolicyError("cors request origin may not be empty")
    method_token = method.upper()
    if method_token not in policy.allow_methods:
        return CorsDecision(False, ())
    if not policy.allows_origin(origin):
        return CorsDecision(False, ())
    exposed_origin = "*" if "*" in policy.allow_origins and not policy.allow_credentials else origin
    headers: list[tuple[str, str]] = [
        ("Access-Control-Allow-Origin", exposed_origin),
        ("Vary", "Origin"),
    ]
    if policy.allow_credentials:
        headers.append(("Access-Control-Allow-Credentials", "true"))
    if preflight:
        headers.append(("Access-Control-Allow-Methods", ", ".join(policy.allow_methods)))
        allowed_headers = requested_headers or policy.allow_headers
        headers.append(("Access-Control-Allow-Headers", ", ".join(allowed_headers)))
        headers.append(("Access-Control-Max-Age", str(policy.max_age_seconds)))
    return CorsDecision(True, tuple(headers))


__all__ = [
    "CorsDecision",
    "CorsPolicy",
    "CorsPolicyError",
    "cors_decision",
    "validate_cors_config",
]
