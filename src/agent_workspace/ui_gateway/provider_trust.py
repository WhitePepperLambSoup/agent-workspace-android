"""Model services the user chose, which conversations send to without asking each time.

Under the Workspace level the first request of every conversation asked whether it may go to the
provider, a question a new user cannot judge and an old one tires of. A service chosen in first-use
setup, or with "Always" on that question, is trusted from then on. What the policy calls sensitive
(keys, .env files) still asks, every time, and trust can be taken back in Settings.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

from agent_workspace.config import provider_origin

_LOGGER = logging.getLogger(__name__)


def origin_of(endpoint: str) -> str:
    """A service's address without its path: https://host, with the port if it is not the usual."""
    scheme, host, port = provider_origin(endpoint)
    usual = {"https": 443, "http": 80}.get(scheme)
    return f"{scheme}://{host}" if port == usual else f"{scheme}://{host}:{port}"


class TrustedProviders:
    """The trusted services, kept in a file beside the database."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def origins(self) -> list[str]:
        with self._lock:
            return sorted(self._read())

    def trusts(self, endpoint: str) -> bool:
        try:
            origin = origin_of(endpoint)
        except ValueError:
            return False
        with self._lock:
            return origin in self._read()

    def add(self, endpoint: str) -> str:
        origin = origin_of(endpoint)
        with self._lock:
            origins = self._read()
            origins.add(origin)
            self._write(origins)
        return origin

    def remove(self, origin: str) -> bool:
        with self._lock:
            origins = self._read()
            if origin not in origins:
                return False
            origins.discard(origin)
            self._write(origins)
        return True

    def _read(self) -> set[str]:
        try:
            document = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            return set()
        origins = document.get("origins") if isinstance(document, dict) else None
        return (
            {item for item in origins if isinstance(item, str)}
            if isinstance(origins, list)
            else set()
        )

    def _write(self, origins: set[str]) -> None:
        temporary = self._path.with_name(f"{self._path.name}.tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps({"origins": sorted(origins)}), encoding="utf-8")
            os.replace(temporary, self._path)
        except OSError as error:
            _LOGGER.warning("trusted providers could not be saved: %s", error)
            raise


__all__ = ["TrustedProviders", "origin_of"]
