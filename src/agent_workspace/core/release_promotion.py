"""Build reproducibility hash and release channel promotion."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


def reproducibility_hash(manifest: dict[str, str]) -> str:
    if not isinstance(manifest, dict) or any(
        not isinstance(path, str) or not isinstance(digest, str)
        for path, digest in manifest.items()
    ):
        raise ValueError("manifest must map paths to digest strings")
    digest = hashlib.sha256()
    for path, file_digest in sorted(manifest.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(file_digest.casefold().encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class ReleaseChannelPolicy:
    allowed_channels: tuple[str, ...] = ("nightly", "beta", "stable")
    allowed_promotions: tuple[tuple[str, str], ...] = (
        ("nightly", "beta"),
        ("beta", "stable"),
    )

    def __post_init__(self) -> None:
        if "stable" not in self.allowed_channels:
            raise ValueError("stable channel must be allowed")
        if any(
            source not in self.allowed_channels or target not in self.allowed_channels
            for source, target in self.allowed_promotions
        ):
            raise ValueError("promotion edges must reference allowed channels")

    def can_promote(self, source: str, target: str) -> bool:
        return (source, target) in self.allowed_promotions

    def to_document(self) -> dict[str, Any]:
        return {
            "allowed_channels": list(self.allowed_channels),
            "allowed_promotions": [list(edge) for edge in self.allowed_promotions],
        }


@dataclass(frozen=True, slots=True)
class ReleaseRecoveryDiagnostic:
    """Bounded, user-actionable release verification result."""

    status: str
    version: str | None
    manifest_path: str
    files_verified: int
    failures: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recovery_action: str = ""

    def to_document(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "version": self.version,
            "manifest_path": self.manifest_path,
            "files_verified": self.files_verified,
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "recovery_action": self.recovery_action,
        }


def diagnose_release_bundle(
    bundle: str | Path,
    *,
    manifest_name: str = "release-manifest.json",
) -> ReleaseRecoveryDiagnostic:
    """Inspect a release bundle without raising, for startup recovery UX.

    The verifier intentionally checks only the portable manifest contract. A
    packaging-specific verifier can add source, SBOM, or signature checks and
    surface its own result alongside this diagnostic.
    """
    root = Path(bundle).expanduser().resolve()
    try:
        manifest_parts = _safe_bundle_parts(manifest_name)
    except ValueError as exc:
        return ReleaseRecoveryDiagnostic(
            "error",
            None,
            str(root / manifest_name),
            0,
            (str(exc),),
            (),
            "Restore the previous release or rebuild the bundle with a safe manifest path.",
        )
    manifest_path = root.joinpath(*manifest_parts)
    failures: list[str] = []
    warnings: list[str] = []
    version: str | None = None
    verified = 0
    try:
        current = root
        for part in manifest_parts:
            current /= part
            if current.is_symlink():
                raise OSError("release manifest is a symlink")
        manifest_path.resolve(strict=False).relative_to(root)
        raw: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        return ReleaseRecoveryDiagnostic(
            "error",
            None,
            str(manifest_path),
            0,
            (f"cannot read release manifest: {exc}",),
            (),
            "Restore the previous release or rebuild the bundle with a fresh manifest.",
        )
    if not isinstance(raw, dict):
        failures.append("release manifest must be an object")
    elif raw.get("format_version") != 1:
        failures.append("release manifest format_version is unsupported")
    if isinstance(raw, dict) and isinstance(raw.get("version"), str) and raw["version"]:
        version = raw["version"]
    else:
        failures.append("release manifest version is missing")
    entries = raw.get("files") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        failures.append("release manifest file list is invalid")
        entries = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            failures.append("release manifest entry is invalid")
            continue
        relative = entry.get("path")
        digest = entry.get("sha256")
        size = entry.get("size")
        if not isinstance(relative, str) or relative in seen:
            failures.append("release manifest path is invalid")
            continue
        try:
            relative_parts = _safe_bundle_parts(relative)
        except ValueError:
            failures.append("release manifest path is invalid")
            continue
        seen.add(relative)
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest.casefold())
        ):
            failures.append(f"invalid sha256 for {relative}")
            continue
        if type(size) is not int or size < 0:
            failures.append(f"invalid size for {relative}")
            continue
        path = root.joinpath(*relative_parts)
        try:
            current = root
            for part in relative_parts:
                current /= part
                if current.is_symlink():
                    raise OSError("release file is a symlink")
            resolved = path.resolve(strict=False)
            resolved.relative_to(root)
            actual_size = path.stat().st_size
            actual_digest = _sha256_file(path)
        except (OSError, ValueError):
            failures.append(f"missing release file: {relative}")
            continue
        if actual_size != size:
            failures.append(f"size mismatch for {relative}")
            continue
        if actual_digest != digest.casefold():
            failures.append(f"sha256 mismatch for {relative}")
            continue
        verified += 1
    if isinstance(raw, dict) and not raw.get("signed", False):
        warnings.append("release bundle is unsigned")
    status = "error" if failures else ("warn" if warnings else "ok")
    return ReleaseRecoveryDiagnostic(
        status,
        version,
        str(manifest_path),
        verified,
        tuple(failures),
        tuple(warnings),
        ("Restore the previous verified bundle before launching this release." if failures else ""),
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_bundle_parts(relative: str) -> tuple[str, ...]:
    if not relative or "\x00" in relative or "\\" in relative:
        raise ValueError("release manifest path is invalid")
    parsed = PurePosixPath(relative)
    if parsed.is_absolute() or ".." in parsed.parts or not parsed.parts:
        raise ValueError("release manifest path is invalid")
    return tuple(parsed.parts)


__all__ = [
    "ReleaseChannelPolicy",
    "ReleaseRecoveryDiagnostic",
    "diagnose_release_bundle",
    "reproducibility_hash",
]
