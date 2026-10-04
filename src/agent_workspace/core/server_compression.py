"""Server response compression middleware config and decision helper.

Chooses whether and how to compress an HTTP response body based on content
type, body size, and the client's Accept-Encoding quality values. It never
compresses a body that is too small or a content type that is commonly
pre-compressed (images, archives, ...).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_SUPPORTED_ENCODINGS = ("gzip", "deflate", "br")
_DEFAULT_EXCLUDED_PREFIXES = (
    "image/",
    "audio/",
    "video/",
    "application/zip",
    "application/gzip",
    "application/x-tar",
    "application/pdf",
    "application/epub+zip",
)


class CompressionPolicyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CompressionPolicy:
    minimum_size_bytes: int = 1024
    encodings: tuple[str, ...] = ("gzip", "br")
    excluded_content_types: tuple[str, ...] = _DEFAULT_EXCLUDED_PREFIXES
    compressible_wildcard: bool = True

    def __post_init__(self) -> None:
        if self.minimum_size_bytes < 0:
            raise CompressionPolicyError("compression minimum size may not be negative")
        if not self.encodings:
            raise CompressionPolicyError("compression policy requires at least one encoding")
        unknown = [encoding for encoding in self.encodings if encoding not in _SUPPORTED_ENCODINGS]
        if unknown:
            raise CompressionPolicyError(f"unsupported compression encodings: {', '.join(unknown)}")

    def to_document(self) -> dict[str, Any]:
        return {
            "minimum_size_bytes": self.minimum_size_bytes,
            "encodings": list(self.encodings),
            "excluded_content_types": list(self.excluded_content_types),
            "compressible_wildcard": self.compressible_wildcard,
        }


@dataclass(frozen=True, slots=True)
class CompressionDecision:
    compress: bool
    encoding: str | None
    headers: tuple[tuple[str, str], ...]
    reason: str

    def to_document(self) -> dict[str, Any]:
        return {
            "compress": self.compress,
            "encoding": self.encoding,
            "headers": [list(header) for header in self.headers],
            "reason": self.reason,
        }


def validate_compression_config(config: dict[str, Any]) -> CompressionPolicy:
    if not isinstance(config, dict):
        raise CompressionPolicyError("compression config must be an object")
    raw_minimum = config.get("minimum_size_bytes", 1024)
    if isinstance(raw_minimum, bool) or not isinstance(raw_minimum, int):
        raise CompressionPolicyError("compression minimum_size_bytes must be an integer")
    raw_encodings = config.get("encodings", ("gzip", "br"))
    if isinstance(raw_encodings, str) or not isinstance(raw_encodings, (list, tuple)):
        raise CompressionPolicyError("compression encodings must be a list")
    raw_excluded = config.get("excluded_content_types", list(_DEFAULT_EXCLUDED_PREFIXES))
    if isinstance(raw_excluded, str) or not isinstance(raw_excluded, (list, tuple)):
        raise CompressionPolicyError("compression excluded_content_types must be a list")
    raw_wildcard = config.get("compressible_wildcard", True)
    if not isinstance(raw_wildcard, bool):
        raise CompressionPolicyError("compression compressible_wildcard must be a boolean")
    return CompressionPolicy(
        minimum_size_bytes=raw_minimum,
        encodings=tuple(str(encoding) for encoding in raw_encodings),
        excluded_content_types=tuple(str(value) for value in raw_excluded),
        compressible_wildcard=raw_wildcard,
    )


def parse_accept_encoding(header: str) -> dict[str, float]:
    """Parse Accept-Encoding into encoding -> quality (0.0 means rejected)."""
    qualities: dict[str, float] = {}
    for part in header.split(","):
        pieces = part.strip().split(";")
        encoding = pieces[0].strip().casefold()
        if not encoding:
            continue
        quality = 1.0
        for parameter in pieces[1:]:
            key, separator, value = parameter.strip().partition("=")
            if separator and key.strip().casefold() == "q":
                try:
                    quality = float(value.strip())
                except ValueError:
                    quality = 0.0
        if quality > 0:
            qualities[encoding] = quality
        else:
            qualities[encoding] = 0.0
    if "*" in qualities and qualities["*"] > 0:
        for encoding in _SUPPORTED_ENCODINGS:
            qualities.setdefault(encoding, qualities["*"])
    return qualities


def _is_excluded(content_type: str, policy: CompressionPolicy) -> bool:
    folded = content_type.split(";", 1)[0].strip().casefold()
    if folded in {"application/octet-stream", "text/event-stream"}:
        return True
    return any(
        folded == prefix or folded.startswith(prefix) for prefix in policy.excluded_content_types
    )


def compression_decision(
    content_type: str,
    content_length: int,
    accept_encoding: str,
    *,
    policy: CompressionPolicy | None = None,
) -> CompressionDecision:
    """Decide whether to compress one server response body."""
    active = policy or CompressionPolicy()
    if content_length < active.minimum_size_bytes:
        return CompressionDecision(
            False,
            None,
            (("Vary", "Accept-Encoding"),),
            f"content length {content_length} is below minimum {active.minimum_size_bytes}",
        )
    folded_type = content_type.casefold()
    compressible_type = (
        folded_type.startswith("text/")
        or folded_type == "application/json"
        or folded_type.endswith("+json")
        or folded_type == "application/javascript"
        or folded_type.endswith("+xml")
        or (active.compressible_wildcard and folded_type == "*/*")
    )
    if compressible_type:
        pass
    elif _is_excluded(content_type, active):
        return CompressionDecision(
            False,
            None,
            (("Vary", "Accept-Encoding"),),
            f"content type {content_type!r} is excluded from compression",
        )
    else:
        return CompressionDecision(
            False,
            None,
            (("Vary", "Accept-Encoding"),),
            f"content type {content_type!r} is not compressible",
        )
    qualities = parse_accept_encoding(accept_encoding)
    chosen = next(
        (encoding for encoding in active.encodings if qualities.get(encoding, 0.0) > 0),
        None,
    )
    if chosen is None:
        return CompressionDecision(
            False,
            None,
            (("Vary", "Accept-Encoding"),),
            "client does not accept any configured encoding",
        )
    return CompressionDecision(
        True,
        chosen,
        (("Content-Encoding", chosen), ("Vary", "Accept-Encoding")),
        "response body is compressible and client accepts encoding",
    )


__all__ = [
    "CompressionDecision",
    "CompressionPolicy",
    "CompressionPolicyError",
    "compression_decision",
    "parse_accept_encoding",
    "validate_compression_config",
]
