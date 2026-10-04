from __future__ import annotations

import errno
import os
import threading
from collections.abc import Callable, Hashable
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, Self


class AlreadyRunningError(RuntimeError):
    pass


class ProcessWriteLock:
    """A non-blocking one-byte process lock for the local writable runtime."""

    def __init__(
        self,
        path: str | Path,
        *,
        busy_message: str = "another Agent Workspace writer is running",
    ) -> None:
        self.path = Path(path)
        self.busy_message = busy_message
        self._stream: BinaryIO | None = None

    @staticmethod
    def _is_lock_denied(exc: OSError) -> bool:
        if os.name == "nt":
            winerror = getattr(exc, "winerror", None)
            if winerror in (32, 33):
                return True
            return exc.errno in (errno.EACCES, errno.EDEADLK)
        else:
            lock_errnos = {errno.EACCES, errno.EAGAIN}
            if hasattr(errno, "EWOULDBLOCK"):
                lock_errnos.add(errno.EWOULDBLOCK)
            return exc.errno in lock_errnos

    def acquire(self) -> None:
        if self._stream is not None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OSError(f"failed to create lock directory {self.path.parent}: {exc}") from exc

        try:
            stream = self.path.open("a+b")
        except OSError as exc:
            if self._is_lock_denied(exc):
                raise AlreadyRunningError(self.busy_message) from exc
            raise OSError(f"failed to open lock file {self.path}: {exc}") from exc

        try:
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(  # type: ignore[attr-defined]
                    stream.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,  # type: ignore[attr-defined]
                )
        except OSError as exc:
            stream.close()
            if self._is_lock_denied(exc):
                raise AlreadyRunningError(self.busy_message) from exc
            raise OSError(f"failed to acquire lock on {self.path}: {exc}") from exc
        self._stream = stream

    def release(self) -> None:
        stream = self._stream
        if stream is None:
            return
        try:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(  # type: ignore[attr-defined]
                    stream.fileno(),
                    fcntl.LOCK_UN,  # type: ignore[attr-defined]
                )
        finally:
            stream.close()
            self._stream = None

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


@dataclass(slots=True)
class _SharedClaim:
    owner: ProcessWriteLockLease
    participants: dict[ProcessWriteLockLease, Callable[[], Future[None] | None] | None] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class _SharedWriteLock:
    lock: ProcessWriteLock
    leases: int = 0
    initialized: dict[Hashable, set[ProcessWriteLockLease]] = field(default_factory=dict)
    claims: dict[Hashable, _SharedClaim] = field(default_factory=dict)


class ProcessWriteLockGroup:
    """Explicitly share one process lock among cooperating runtime owners."""

    def __init__(self) -> None:
        self._mutex = threading.Lock()
        self._locks: dict[Path, _SharedWriteLock] = {}

    def lease(
        self,
        path: str | Path,
        *,
        busy_message: str = "another Agent Workspace writer is running",
    ) -> ProcessWriteLockLease:
        return ProcessWriteLockLease(self, path, busy_message=busy_message)

    def _acquire(self, lease: ProcessWriteLockLease) -> None:
        with self._mutex:
            if lease._held:
                return
            entry = self._locks.get(lease.path)
            if entry is None:
                lock = ProcessWriteLock(lease.path, busy_message=lease.busy_message)
                lock.acquire()
                entry = _SharedWriteLock(lock)
                self._locks[lease.path] = entry
            entry.leases += 1
            lease._held = True

    def _release(self, lease: ProcessWriteLockLease) -> None:
        callbacks: list[Callable[[], Future[None] | None]] = []
        with self._mutex:
            if not lease._held:
                return
            entry = self._locks[lease.path]
            lease._held = False
            entry.leases -= 1
            for key, participants in tuple(entry.initialized.items()):
                participants.discard(lease)
                if not participants:
                    del entry.initialized[key]
            for key in tuple(entry.claims):
                callback = self._drop_claim(entry, key, lease)
                if callback is not None:
                    callbacks.append(callback)
            if entry.leases == 0:
                del self._locks[lease.path]
                entry.lock.release()
        for callback in callbacks:
            callback()

    def _run_once(
        self, lease: ProcessWriteLockLease, key: Hashable, action: Callable[[], None]
    ) -> None:
        with self._mutex:
            if not lease._held:
                raise RuntimeError("writer lease is not acquired")
            entry = self._locks[lease.path]
            if key not in entry.initialized:
                action()
                entry.initialized[key] = set()
            entry.initialized[key].add(lease)

    def _claim(
        self,
        lease: ProcessWriteLockLease,
        key: Hashable,
        on_available: Callable[[], Future[None] | None] | None,
    ) -> bool:
        with self._mutex:
            if not lease._held:
                raise RuntimeError("writer lease is not acquired")
            entry = self._locks[lease.path]
            claim = entry.claims.get(key)
            if claim is None:
                claim = _SharedClaim(lease)
                entry.claims[key] = claim
            claim.participants[lease] = on_available
            return claim.owner is lease

    def _retire_claim(self, lease: ProcessWriteLockLease, key: Hashable) -> None:
        with self._mutex:
            if lease._held:
                claim = self._locks[lease.path].claims.get(key)
                if claim is not None:
                    claim.participants.pop(lease, None)

    @staticmethod
    def _drop_claim(
        entry: _SharedWriteLock, key: Hashable, lease: ProcessWriteLockLease
    ) -> Callable[[], Future[None] | None] | None:
        claim = entry.claims[key]
        claim.participants.pop(lease, None)
        if claim.owner is not lease:
            return None
        if not claim.participants:
            del entry.claims[key]
            return None
        claim.owner = next(iter(claim.participants))
        return claim.participants[claim.owner]

    def _release_claim(self, lease: ProcessWriteLockLease, key: Hashable) -> Future[None] | None:
        with self._mutex:
            if not lease._held:
                return None
            entry = self._locks[lease.path]
            callback = self._drop_claim(entry, key, lease) if key in entry.claims else None
        return callback() if callback is not None else None


class ProcessWriteLockLease(ProcessWriteLock):
    """A runtime's independently releasable share of its group's process lock."""

    def __init__(
        self,
        group: ProcessWriteLockGroup,
        path: str | Path,
        *,
        busy_message: str = "another Agent Workspace writer is running",
    ) -> None:
        super().__init__(Path(path).expanduser().resolve(), busy_message=busy_message)
        self._group = group
        self._held = False

    def acquire(self) -> None:
        self._group._acquire(self)

    def release(self) -> None:
        self._group._release(self)

    def run_once(self, key: Hashable, action: Callable[[], None]) -> None:
        """Initialize once until the last lease participating in this key exits."""
        self._group._run_once(self, key, action)

    def claim(
        self, key: Hashable, *, on_available: Callable[[], Future[None] | None] | None = None
    ) -> bool:
        """Claim a component or wait for its owner to relinquish it."""
        return self._group._claim(self, key, on_available)

    def retire_claim(self, key: Hashable) -> None:
        """Stop waiting for a claim while preserving any currently owned component."""
        self._group._retire_claim(self, key)

    def release_claim(self, key: Hashable) -> Future[None] | None:
        """Relinquish a component and activate a surviving participant outside the mutex."""
        return self._group._release_claim(self, key)
