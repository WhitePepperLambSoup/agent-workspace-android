"""Server static asset cache header policy.

Distinguishes immutable fingerprinted assets (``app.8f2b31c9.js``) from
mutable entries such as ``index.html`` and emits cache-control plus optional
ETag headers accordingly.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

_IMMUTABLE_MARKER = re.compile(r"[.\-][0-9a-f]{8,}[.\-]", re.IGNORECASE)


class StaticCachePolicyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StaticCachePolicy:
    immutable_max_age_seconds: int = 31_536_000
    mutable_max_age_seconds: int = 300
    no_cache_paths: tuple[str, ...] = ("/index.html", "/service-worker.js", "/manifest.json")

    def __post_init__(self) -> None:
        if self.immutable_max_age_seconds < 0 or self.mutable_max_age_seconds < 0:
            raise StaticCachePolicyError("static cache max ages may not be negative")

    def to_document(self) -> dict[str, Any]:
        return {
            "immutable_max_age_seconds": self.immutable_max_age_seconds,
            "mutable_max_age_seconds": self.mutable_max_age_seconds,
            "no_cache_paths": list(self.no_cache_paths),
        }


@dataclass(frozen=True, slots=True)
class StaticAssetHeaders:
    cache_control: str
    etag: str | None
    immutable: bool

    def headers(self) -> dict[str, str]:
        headers = {"Cache-Control": self.cache_control}
        if self.etag:
            headers["ETag"] = self.etag
        return headers

    def to_document(self) -> dict[str, Any]:
        return {
            "cache_control": self.cache_control,
            "etag": self.etag,
            "immutable": self.immutable,
        }


def validate_static_cache_config(config: dict[str, Any]) -> StaticCachePolicy:
    if not isinstance(config, dict):
        raise StaticCachePolicyError("static cache config must be an object")
    immutable = config.get("immutable_max_age_seconds", 31_536_000)
    mutable = config.get("mutable_max_age_seconds", 300)
    if isinstance(immutable, bool) or not isinstance(immutable, int):
        raise StaticCachePolicyError("immutable max age must be an integer")
    if isinstance(mutable, bool) or not isinstance(mutable, int):
        raise StaticCachePolicyError("mutable max age must be an integer")
    raw_no_cache = config.get(
        "no_cache_paths", ("/index.html", "/service-worker.js", "/manifest.json")
    )
    if isinstance(raw_no_cache, str) or not isinstance(raw_no_cache, (list, tuple)):
        raise StaticCachePolicyError("no_cache_paths must be a list")
    return StaticCachePolicy(
        immutable_max_age_seconds=immutable,
        mutable_max_age_seconds=mutable,
        no_cache_paths=tuple(str(value) for value in raw_no_cache),
    )


def is_immutable_asset(path: str) -> bool:
    return _IMMUTABLE_MARKER.search(path.replace("\\", "/")) is not None


def etag_for_bytes(payload: bytes) -> str:
    return f'"{hashlib.sha256(payload).hexdigest()[:32]}"'


def static_cache_headers(
    path: str,
    *,
    policy: StaticCachePolicy | None = None,
    payload: bytes | None = None,
) -> StaticAssetHeaders:
    active = policy or StaticCachePolicy()
    normalized = path.replace("\\", "/")
    folded = normalized.casefold()
    if any(folded == marker.casefold() for marker in active.no_cache_paths):
        return StaticAssetHeaders("no-cache", None, False)
    if is_immutable_asset(normalized):
        return StaticAssetHeaders(
            f"public, max-age={active.immutable_max_age_seconds}, immutable",
            etag_for_bytes(payload) if payload is not None else None,
            True,
        )
    return StaticAssetHeaders(
        f"public, max-age={active.mutable_max_age_seconds}",
        etag_for_bytes(payload) if payload is not None else None,
        False,
    )


__all__ = [
    "StaticAssetHeaders",
    "StaticCachePolicy",
    "StaticCachePolicyError",
    "etag_for_bytes",
    "is_immutable_asset",
    "static_cache_headers",
    "validate_static_cache_config",
]
