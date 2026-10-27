"""Earlier contents of files the agent replaced, kept so a change can be compared afterwards.

A tool's rollback copy lives only while the call runs; this store keeps the replaced content
after it settled, addressed by its SHA-256 (the digest the call named as ``expected_sha256``),
so the window can show a document before and after an edit. Identical content is kept once.
Old entries go first when the store passes its size budget or its age limit.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time
from pathlib import Path

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_MAX_BYTES = 1024 * 1024 * 1024
DEFAULT_MAX_AGE_SECONDS = 90 * 24 * 3600


class FileVersions:
    def __init__(
        self,
        root: Path,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
    ) -> None:
        self.root = root
        self.max_bytes = max_bytes
        self.max_age_seconds = max_age_seconds

    def _path(self, digest: str) -> Path:
        return self.root / digest[:2] / f"{digest}.bin"

    def keep(self, data: bytes) -> str:
        """Store the content (once per digest) and return its SHA-256."""
        digest = hashlib.sha256(data).hexdigest()
        path = self._path(digest)
        if path.is_file():
            os.utime(path)  # recently used versions are the last to be pruned
            return digest
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".version-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        return digest

    def read(self, digest: str) -> bytes | None:
        """The content with this SHA-256, or None when it was never kept or has been pruned."""
        if not _DIGEST.match(digest):
            return None
        try:
            data = self._path(digest).read_bytes()
        except OSError:
            return None
        return data if hashlib.sha256(data).hexdigest() == digest else None

    def prune(self, *, now: float | None = None) -> int:
        """Remove versions past the age limit, then the oldest beyond the size budget."""
        if not self.root.is_dir():
            return 0
        moment = time.time() if now is None else now
        entries: list[tuple[float, int, Path]] = []
        for path in self.root.glob("??/*.bin"):
            try:
                metadata = path.stat()
            except OSError:
                continue
            entries.append((metadata.st_mtime, metadata.st_size, path))
        removed = 0
        kept: list[tuple[float, int, Path]] = []
        for modified, size, path in entries:
            if moment - modified > self.max_age_seconds:
                path.unlink(missing_ok=True)
                removed += 1
            else:
                kept.append((modified, size, path))
        total = sum(size for _, size, _ in kept)
        for _, size, path in sorted(kept):
            if total <= self.max_bytes:
                break
            path.unlink(missing_ok=True)
            total -= size
            removed += 1
        return removed
