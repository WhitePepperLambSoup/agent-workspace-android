"""Puts the npm packages of a language server in the app's tools folder, without npm.

The packages it fetches have no dependencies, so each one is its registry tarball unpacked
under ``<tools>/node_modules/<name>``. The tarball is checked against the registry's integrity
hash, unpacked into a temporary folder, and only then put in place.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import shutil
import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

import httpx

from .servers import ServerSpec

# The mirror answers quickly in China; the main registry is the fallback.
REGISTRIES = ("https://registry.npmmirror.com", "https://registry.npmjs.org")
_MAX_TARBALL_BYTES = 64 * 1024 * 1024
_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

type Fetch = Callable[[str, dict[str, str]], bytes]


class InstallError(RuntimeError):
    pass


def _fetch(url: str, headers: dict[str, str]) -> bytes:
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        if len(response.content) > _MAX_TARBALL_BYTES:
            raise InstallError(f"{url} is larger than expected")
        return response.content


def _pick_version(metadata: dict[str, Any], major: str | None) -> str:
    versions = metadata.get("versions")
    if not isinstance(versions, dict):
        raise InstallError("the registry sent no versions")
    if major is None:
        latest = metadata.get("dist-tags", {}).get("latest")
        if isinstance(latest, str) and latest in versions:
            return latest
    candidates = [
        (tuple(int(part) for part in match.groups()), version)
        for version in versions
        if (match := _VERSION.match(version)) and (major is None or match.group(1) == major)
    ]
    if not candidates:
        raise InstallError(f"no release {major}.x")
    return str(max(candidates)[1])


def _verify(data: bytes, dist: dict[str, Any]) -> None:
    integrity = dist.get("integrity")
    if isinstance(integrity, str) and integrity.startswith("sha512-"):
        expected = base64.b64decode(integrity.removeprefix("sha512-"))
        if hashlib.sha512(data).digest() != expected:
            raise InstallError("the download does not match the registry's integrity hash")
        return
    shasum = dist.get("shasum")
    if isinstance(shasum, str) and hashlib.sha1(data, usedforsecurity=False).hexdigest() == shasum:
        return
    raise InstallError("the download could not be checked")


def _unpack(data: bytes, destination: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != "package" or ".." in parts or member.name.startswith("/"):
                continue
            if not (member.isfile() or member.isdir()):
                continue  # no links or devices
            target = destination.joinpath(*parts[1:])
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                continue
            with source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)


def install_package(
    requirement: str, tools_dir: Path, *, fetch: Fetch = _fetch, registries: tuple[str, ...] = ()
) -> str:
    """Install ``name@major`` (or ``name``) into the tools folder; returns the version."""
    at = requirement.rfind("@")
    name, major = (requirement[:at], requirement[at + 1 :]) if at > 0 else (requirement, "")
    errors: list[str] = []
    for registry in registries or REGISTRIES:
        try:
            raw = fetch(f"{registry}/{name}", {"Accept": "application/vnd.npm.install-v1+json"})
            metadata = json.loads(raw)
            version = _pick_version(metadata, major or None)
            dist = metadata["versions"][version]["dist"]
            data = fetch(str(dist["tarball"]), {})
            _verify(data, dist)
        except (httpx.HTTPError, InstallError, KeyError, ValueError, TypeError) as error:
            errors.append(f"{registry}: {error}")
            continue
        modules = tools_dir / "node_modules"
        modules.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".install-", dir=modules))
        try:
            _unpack(data, staging)
            target = modules / name
            if target.exists():
                shutil.rmtree(target)
            staging.rename(target)
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
        return version
    raise InstallError(f"could not install {requirement}: " + "; ".join(errors))


def install_server(spec: ServerSpec, tools_dir: Path, *, fetch: Fetch = _fetch) -> dict[str, str]:
    if not spec.npm:
        raise InstallError(f"{spec.name} cannot be installed from here: {spec.hint}")
    return {
        requirement: install_package(requirement, tools_dir, fetch=fetch)
        for requirement in spec.npm
    }


__all__ = ["REGISTRIES", "InstallError", "install_package", "install_server"]
