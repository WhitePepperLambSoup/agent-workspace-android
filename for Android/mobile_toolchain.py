"""Optional verified Linux tooling launched through packaged Android PRoot.

Downloading ELF files is insufficient on Android 10+: only the APK's installed
launcher/loader execute directly. Guest tools run through that loader, using a
private root filesystem. This supplies app-level tooling, not an OS sandbox.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import http.client
import json
import os
import re
import shutil
import tarfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

_MAX_EXTRACTED_BYTES = 700 * 1024 * 1024
_MAX_MEMBERS = 60000
_MAX_INDEX_BYTES = 32 * 1024 * 1024
_ACTIVE = {"downloading", "extracting", "probing", "cancelling"}
# Waits between rounds over every mirror while the network is gone: the install stops after about
# three minutes without a byte of progress.
_RETRY_DELAYS = (3, 5, 10, 20, 30, 30, 30, 30, 30)
# An APK's control segment: signature, metadata and install scripts, none of them guest files.
_CONTROL_FILES = (
    ".SIGN.",
    ".PKGINFO",
    ".INSTALL",
    ".trigger",
    ".pre-install",
    ".post-install",
    ".pre-upgrade",
    ".post-upgrade",
    ".pre-deinstall",
    ".post-deinstall",
)
# How each executable shows that it runs: arguments, accepted exit codes, words its output must hold.
# Others run with --version and must exit 0. scp, sftp and ssh-keygen have no version flag: their
# usage message (exit code 1) proves they start.
_PROBES = {
    "tmux": (["-V"], {0}, "tmux"),
    "ssh": (["-V"], {0}, "OpenSSH"),
    "scp": ([], {1}, "usage: scp"),
    "sftp": ([], {1}, "usage: sftp"),
    "ssh-keygen": (["-?"], {1}, "usage: ssh-keygen"),
}


class ToolchainError(RuntimeError):
    pass


class _Cancelled(ToolchainError):
    pass


class _Incomplete(ToolchainError):
    """The connection ended early; what arrived is kept for the next try."""


def _network_trouble(error: BaseException) -> bool:
    """Whether trying again later may help: no connection, a timeout, a cut, a busy server."""
    if isinstance(error, urllib.error.HTTPError):
        return error.code >= 500 or error.code in {408, 429}
    return isinstance(
        error,
        (_Incomplete, urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException),
    )


def native_toolchain_status() -> dict[str, Any]:
    try:
        from java import jclass

        return json.loads(
            str(jclass("com.agentworkspace.mobile.toolchain.AndroidToolchainBridge").status())
        )
    except Exception:
        return {
            "available": False,
            "reason": "The packaged Android toolchain launcher is unavailable",
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_replace(source: Path, destination: Path) -> None:
    # Windows scanners can briefly hold a just-written directory. Preserve atomic
    # replacement and its rollback, with a bounded retry only for sharing locks.
    for attempt in range(6):
        try:
            os.replace(source, destination)
            return
        except PermissionError as error:
            if os.name != "nt" or getattr(error, "winerror", None) not in {5, 32} or attempt == 5:
                raise
            time.sleep(0.05 * (attempt + 1))


def _safe_relative(value: str) -> Path:
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or ".." in parsed.parts or "\\" in value or "\x00" in value:
        raise ToolchainError("The archive contains a path escape")
    return Path(*parsed.parts)


def extract_verified_archive(
    archive_path: Path,
    destination: Path,
    *,
    prefix: str = "",
    strip_prefix: str = "",
    cancelled: threading.Event | None = None,
) -> None:
    """Extract checked tar/APK content without devices or escaping links.

    APK v2 archives concatenate gzip/tar streams; ignore_zeros reads every
    segment. Absolute guest symlinks become equivalent relative links inside
    the private filesystem, rather than links into the Android host.
    """
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    target_root = root / _safe_relative(prefix)
    target_root.mkdir(parents=True, exist_ok=True)
    total = 0
    count = 0
    with tarfile.open(archive_path, "r:*", ignore_zeros=True) as archive:
        for member in archive:
            if cancelled is not None and cancelled.is_set():
                raise _Cancelled("Toolchain installation was cancelled")
            count += 1
            total += max(0, member.size)
            if count > _MAX_MEMBERS or total > _MAX_EXTRACTED_BYTES:
                raise ToolchainError("The archive exceeds its extraction limit")
            name = member.name.removeprefix("./")
            if not name or name == "." or name.startswith(_CONTROL_FILES):
                continue
            if strip_prefix:
                if name == strip_prefix:
                    continue
                if not name.startswith(strip_prefix + "/"):
                    raise ToolchainError("The archive contains an unexpected root directory")
                name = name[len(strip_prefix) + 1 :]
            target = target_root / _safe_relative(name)
            if not target.parent.resolve().is_relative_to(root):
                raise ToolchainError("The archive escapes the installation directory")
            if member.isdev() or member.isfifo():
                continue
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                target.unlink()
            if member.issym() or member.islnk():
                raw = member.linkname
                if "\\" in raw or "\x00" in raw:
                    raise ToolchainError("The archive contains an invalid link")
                if member.islnk() or raw.startswith("/"):
                    linked = root / _safe_relative(raw.lstrip("/"))
                else:
                    linked = target.parent / raw
                if not linked.resolve().is_relative_to(root):
                    raise ToolchainError("The archive link escapes the installation directory")
                if member.islnk():
                    if not linked.is_file():
                        raise ToolchainError("The archive contains an unresolved hard link")
                    shutil.copyfile(linked, target)
                else:
                    target.symlink_to(os.path.relpath(linked, target.parent))
            elif member.isfile():
                stream = archive.extractfile(member)
                if stream is None:
                    raise ToolchainError("The archive contains an unreadable file")
                with stream, target.open("wb") as output:
                    shutil.copyfileobj(stream, output, 1024 * 1024)
                target.chmod((member.mode & 0o777) | 0o600)
            else:
                raise ToolchainError("The archive contains an unsupported entry")


class MobileToolchainManager:
    retry_delays: tuple[float, ...] = _RETRY_DELAYS

    def __init__(
        self,
        data_dir: str | Path,
        workspace: str | Path,
        *,
        catalog: dict[str, Any] | None = None,
        native_status: Any = native_toolchain_status,
        probe_runner: Any = None,
        probe_on_start: bool = True,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.root = Path(data_dir).resolve() / "toolchain"
        if self.root.is_symlink():
            raise ToolchainError("The private toolchain directory may not be a symlink")
        if self.root.is_relative_to(self.workspace) or self.workspace.is_relative_to(self.root):
            raise ToolchainError("The toolchain must be installed outside the selected workspace")
        self.rootfs = self.root / "rootfs"
        self.download_dir = self.root / "downloads"
        self.state_file = self.root / "state.json"
        # The installed tree's manifest (revision, executable and component hashes). The guest runs
        # as root in the rootfs, so the copy kept there could be rewritten by any command; this one
        # is outside it, and is the one checked.
        self.manifest_file = self.root / "manifest.json"
        self._native_status = native_status
        self._runner = probe_runner
        self._lock = threading.RLock()
        self._cancelled = threading.Event()
        self._thread: threading.Thread | None = None
        self._probed = False
        self._executables: dict[str, dict[str, str]] = {}
        self._processes = 0
        self._completed_bytes = 0
        self._manifest_problem: str | None = None
        try:
            self._state = self._read_json(self.state_file)
        except ToolchainError:
            # Without a manager the page could not remove or reinstall anything: the damaged file
            # is kept aside, named in the reason, and the state starts over.
            kept = self.state_file.with_name(f"state.json.corrupt-{int(time.time())}")
            reason = f"The toolchain's saved state was damaged; it was kept as {kept.name}"
            try:
                _atomic_replace(self.state_file, kept)
            except OSError:
                # Not moved: it stays where it is, and is overwritten only by a later change.
                self._state = {"reason": "The toolchain's saved state is damaged"}
            else:
                self._state = {}
                self._update(reason=reason)
        native = self._native_status()
        if catalog is None:
            catalogs = json.loads(
                Path(__file__).with_name("mobile_toolchain_catalog.json").read_text("utf-8")
            )
            catalog = catalogs["architectures"].get(native.get("architecture"))
        self.catalog = catalog
        if self._state.get("state") in _ACTIVE:
            self._update(
                state="paused",
                reason="Installation was interrupted; retry to resume verified downloads",
            )
        if probe_on_start and self._installed() and native.get("available"):
            with contextlib.suppress(ToolchainError):
                self.probe()

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("invalid state")
            return value
        except (ValueError, OSError) as error:
            raise ToolchainError(
                "Local toolchain state is corrupt; preserve it before repair"
            ) from error

    def _update(self, **values: Any) -> None:
        with self._lock:
            self._state.update(values, updated_at=time.time())
            self.root.mkdir(parents=True, exist_ok=True)
            temporary = self.state_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(self._state, ensure_ascii=False), "utf-8")
            _atomic_replace(temporary, self.state_file)

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        temporary = self.manifest_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest), "utf-8")
        _atomic_replace(temporary, self.manifest_file)

    def _manifest(self) -> dict[str, Any]:
        """The installed tree's manifest; {} when nothing is installed.

        Trees installed before the manifest was kept outside the rootfs have only the guest's copy;
        it is taken over once, and from then on the guest's copy is only for show.
        """
        if self.manifest_file.exists():
            return self._read_json(self.manifest_file)
        guest_copy = self.rootfs / ".agent-toolchain.json"
        if self.rootfs.is_symlink() or guest_copy.is_symlink() or not guest_copy.is_file():
            return {}
        manifest = self._read_json(guest_copy)
        with contextlib.suppress(OSError):
            self._write_manifest(manifest)
        return manifest

    def _installed(self) -> bool:
        if not self.catalog or self.rootfs.is_symlink():
            return False
        try:
            manifest = self._manifest()
        except ToolchainError as error:
            # A damaged manifest means "not installed" (installing again repairs it), not a
            # failure of every command that asks whether the toolchain is there.
            self._manifest_problem = str(error)
            return False
        self._manifest_problem = None
        return manifest.get("revision") == self.catalog["revision"]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            native = self._native_status()
            installed = self._installed()
            available = installed and self._probed and native.get("available") is True
            state = self._state.get("state", "not_installed")
            if installed and not available and state == "ready":
                state = "needs_probe"
            if not installed and state in {"ready", "needs_probe", "probe_failed"}:
                # Installed from an older catalog: installing again downloads what changed.
                earlier = (
                    self.manifest_file.is_file()
                    or (self.rootfs / ".agent-toolchain.json").is_file()
                )
                state = "outdated" if earlier else "not_installed"
            return {
                **self._state,
                # The progress kept from installing the older revision is not this one's.
                **({"downloaded_bytes": 0, "total_bytes": None} if state == "outdated" else {}),
                "state": state,
                "installed": installed,
                "available": available,
                "supported": self.catalog is not None and native.get("available") is True,
                "reason": self._state.get("reason")
                or self._manifest_problem
                or native.get("reason"),
                "revision": self.catalog.get("revision") if self.catalog else None,
                "architecture": native.get("architecture"),
                "download_size": sum(item["size"] for item in self.catalog["artifacts"])
                + (self.catalog.get("alpine") or {}).get("estimated_bytes", 0)
                if self.catalog
                else 0,
                "minimum_free_bytes": self.catalog.get("minimum_free_bytes", 0)
                if self.catalog
                else 0,
                "free_bytes": shutil.disk_usage(self.root.parent).free
                if self.root.parent.exists()
                else 0,
                "executables": {key: dict(value) for key, value in self._executables.items()}
                if available
                else {},
                "native": native,
            }

    def _require_native(self) -> dict[str, Any]:
        native = self._native_status()
        if not native.get("available"):
            raise ToolchainError(str(native.get("reason") or "The native launcher is unavailable"))
        if self.catalog is None or native.get("architecture") != self.catalog["architecture"]:
            raise ToolchainError("This toolchain architecture is unsupported")
        return native

    def install(self, *, wait: bool = False) -> dict[str, Any]:
        self._require_native()
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self.snapshot()
            if self._processes:
                raise ToolchainError("Stop active toolchain processes before installing")
            self._cancelled.clear()
            self._update(
                state="downloading",
                reason=None,
                failure_details=None,
                network_retry=None,
                downloaded_bytes=0,
                total_bytes=None,
            )
            if wait:
                self._install()
            else:
                self._thread = threading.Thread(
                    target=self._background_install, daemon=True, name="android-toolchain-install"
                )
                self._thread.start()
        return self.snapshot()

    def _background_install(self) -> None:
        with contextlib.suppress(ToolchainError):
            self._install()

    def wait_for_install(self) -> dict[str, Any]:
        """Wait for the current installer while progress and cancellation stay usable."""
        with self._lock:
            installer = self._thread
        if installer is not None:
            if installer is threading.current_thread():
                raise ToolchainError("The toolchain installer cannot wait for itself")
            installer.join()
        return self.snapshot()

    def _install(self) -> None:
        staging = self.root / "installing"
        replaced = False
        try:
            assert self.catalog is not None
            self.root.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(self.root).free < self.catalog.get("minimum_free_bytes", 0):
                raise ToolchainError("Not enough free space to install the toolchain")
            self.download_dir.mkdir(parents=True, exist_ok=True)
            archives = []
            self._completed_bytes = 0
            for item in self.catalog["artifacts"]:
                archives.append((item, self._download(item)))
                self._completed_bytes += item["size"]
                self._update(downloaded_bytes=self._completed_bytes)
            packages = []
            if self.catalog.get("alpine"):
                position = next(
                    index for index, (item, _) in enumerate(archives) if item["kind"] == "rootfs"
                )
                packages = self._alpine_packages(archives[position][1])
                # Extracted over the rootfs, before artifacts with their own prefix (Pyright).
                archives[position + 1 : position + 1] = packages
            # Archives of earlier revisions or older package builds are not needed again.
            keep = {path.name for _, path in archives}
            for stale in self.download_dir.iterdir():
                if stale.is_file() and stale.suffix in {".archive", ".part"} and stale.name not in keep:
                    stale.unlink(missing_ok=True)
            self._update(state="extracting", reason=None)
            self._remove_private_tree(staging)
            for item, path in archives:
                extract_verified_archive(
                    path,
                    staging,
                    prefix=item.get("prefix", ""),
                    strip_prefix=item.get("strip_prefix", ""),
                    cancelled=self._cancelled,
                )
            self._prepare_guest(staging)
            executables = {}
            for name, relative in self.catalog["executables"].items():
                candidate = staging / _safe_relative(relative)
                if (
                    not candidate.resolve().is_relative_to(staging.resolve())
                    or not candidate.is_file()
                ):
                    raise ToolchainError(
                        f"The installed {name} executable is missing or escapes the rootfs"
                    )
                executables[name] = {"relative": relative, "sha256": _sha256(candidate)}
            components = {}
            for relative in (
                "opt/pyright/langserver.index.js",
                "usr/lib/node_modules/npm/bin/npm-cli.js",
            ):
                candidate = staging / relative
                if candidate.is_file():
                    components[relative] = _sha256(candidate)
            manifest = {
                "revision": self.catalog["revision"],
                "executables": executables,
                "components": components,
                "packages": {
                    item["package"]: {"version": item["version"], "license": item["license"]}
                    for item, _ in packages
                },
            }
            # The guest's copy is for show (what is installed); manifest_file is the one checked.
            (staging / ".agent-toolchain.json").write_text(json.dumps(manifest), "utf-8")
            if self._cancelled.is_set():
                raise _Cancelled("Toolchain installation was cancelled")
            previous = self.root / "previous"
            self._remove_private_tree(previous)
            if self.rootfs.exists():
                _atomic_replace(self.rootfs, previous)
            try:
                _atomic_replace(staging, self.rootfs)
            except OSError:
                if previous.exists():
                    _atomic_replace(previous, self.rootfs)
                raise
            replaced = True
            self._write_manifest(manifest)
            # The guest's home (SSH keys the agent made, for one) outlives a reinstall.
            home = previous / "home/agent"
            if home.is_dir() and not home.is_symlink():
                with contextlib.suppress(OSError):
                    shutil.rmtree(self.rootfs / "home/agent")
                    _atomic_replace(home, self.rootfs / "home/agent")
                # Font lists of the previous tree: matplotlib would not look for the new fonts.
                for name in ("matplotlib", "fontconfig"):
                    cache = self.rootfs / "home/agent/.cache" / name
                    if cache.resolve().is_relative_to(self.rootfs.resolve()):
                        with contextlib.suppress(OSError):
                            shutil.rmtree(cache)
            self._remove_private_tree(previous)
            self._probed = False
            self._probe()
        except _Cancelled:
            if not replaced and self._still_usable():
                # Reinstalling the same revision: the old tree was never touched and stays in use.
                self._update(state="ready", reason=None)
            else:
                self._update(
                    state="paused",
                    reason="Installation was cancelled; retry to resume downloaded content",
                )
            raise
        except Exception as error:
            reason = (
                str(error)[:400]
                if isinstance(error, ToolchainError)
                else "Toolchain installation failed"
            )
            if not replaced and self._still_usable():
                self._update(state="ready", reason=reason)
            else:
                self._probed = False
                self._executables = {}
                self._update(state="failed", reason=reason)
            raise ToolchainError(reason) from error
        finally:
            self._remove_private_tree(staging)
            # Left set, a cancel stopped every later probe at its first command.
            self._cancelled.clear()

    def _still_usable(self) -> bool:
        """The installed tree passed its probes and is the catalog's revision (a reinstall that
        stopped before replacing it leaves it so)."""
        try:
            return self._probed and self._installed()
        except ToolchainError:
            return False

    def _download(self, item: dict[str, Any], verify: Any = None) -> Path:
        """The artifact, checked by its pinned SHA-256 or by `verify` (which raises AlpineError).

        Each of the item's URLs is tried in turn (mirrors); a partial file resumes on the next one.
        When the network was what failed them all, the round is tried again after a wait.
        """
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,120}", item["id"]):
            raise ToolchainError("Invalid toolchain artifact ID")
        archive = self.download_dir / (item["id"] + ".archive")
        partial = self.download_dir / (item["id"] + ".part")

        def verified(path: Path) -> bool:
            if path.stat().st_size != item["size"]:
                return False
            if verify is None:
                return _sha256(path) == item["sha256"]
            from mobile_alpine import AlpineError

            try:
                verify(path)
            except AlpineError:
                return False
            return True

        if archive.is_file() and verified(archive):
            return archive
        if self._cancelled.is_set():
            raise _Cancelled("Toolchain installation was cancelled")
        if partial.exists() and partial.stat().st_size >= item["size"]:
            if verified(partial):
                _atomic_replace(partial, archive)
                return archive
            partial.unlink()
        urls = item.get("urls") or [item["url"]]
        attempt = 0
        while True:
            before = partial.stat().st_size if partial.exists() else 0
            failure: Exception | None = None
            retry = False
            for url in urls:
                try:
                    self._fetch(item, url, partial)
                except _Cancelled:
                    raise
                except (OSError, ToolchainError, http.client.HTTPException) as error:
                    failure, retry = error, retry or _network_trouble(error)
                    continue
                if verified(partial):
                    _atomic_replace(partial, archive)
                    return archive
                partial.unlink(missing_ok=True)
                failure = None
            if partial.exists() and partial.stat().st_size > before:
                attempt = 0  # Bytes came through: the wait starts over.
            if not retry or not self._wait_for_network(attempt):
                raise failure or ToolchainError(
                    "The downloaded artifact failed its pinned size or SHA-256 check"
                )
            attempt += 1

    def _wait_for_network(self, attempt: int) -> bool:
        """Before another round over the mirrors; False once the network has been gone too long."""
        if attempt >= len(self.retry_delays):
            return False
        self._update(network_retry=attempt + 1)
        if self._cancelled.wait(self.retry_delays[attempt]):
            raise _Cancelled("Toolchain installation was cancelled")
        return True

    def _fetch(self, item: dict[str, Any], url: str, partial: Path) -> None:
        start = partial.stat().st_size if partial.exists() else 0
        headers = {"Accept-Encoding": "identity", "User-Agent": "AgentWorkspace-AndroidToolchain/1"}
        if start:
            headers["Range"] = f"bytes={start}-"
        request = urllib.request.Request(url, headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=8) as response:
            if response.status == 206:
                match = re.fullmatch(
                    r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", "")
                )
                if not match or tuple(map(int, match.groups())) != (
                    start,
                    item["size"] - 1,
                    item["size"],
                ):
                    raise ToolchainError("The server returned an invalid resume range")
            elif response.status == 200:
                start = 0
            else:
                raise ToolchainError("The server rejected the pinned artifact")
            received = start
            last_update = 0.0
            with partial.open("ab" if start else "wb") as output:
                while chunk := response.read(64 * 1024):
                    if self._cancelled.is_set():
                        raise _Cancelled("Toolchain installation was cancelled")
                    received += len(chunk)
                    if received > item["size"]:
                        raise ToolchainError("The downloaded artifact exceeds its pinned size")
                    output.write(chunk)
                    now = time.monotonic()
                    if now - last_update >= 0.5:
                        self._update(
                            artifact=item["id"],
                            downloaded_bytes=self._completed_bytes + received,
                            artifact_downloaded_bytes=received,
                            artifact_size=item["size"],
                            network_retry=None,
                        )
                        last_update = now
        if received != item["size"]:
            # Kept: the next mirror, or the next attempt, resumes from here.
            raise _Incomplete("The download ended before the artifact was complete")

    def _fetch_index(self, url: str, path: Path, settled: threading.Event) -> None:
        """An APKINDEX.tar.gz, fetched afresh each time (its signature is checked by the caller).

        Stops when `settled` is set: another mirror has already given a usable index."""
        request = urllib.request.Request(
            url, headers={"Accept-Encoding": "identity", "User-Agent": "AgentWorkspace-AndroidToolchain/1"}
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        data = bytearray()
        with opener.open(request, timeout=15) as response:
            expected = response.headers.get("Content-Length")
            while chunk := response.read(64 * 1024):
                if self._cancelled.is_set():
                    raise _Cancelled("Toolchain installation was cancelled")
                if settled.is_set():
                    raise ToolchainError("Another mirror answered first")
                data += chunk
                if len(data) > _MAX_INDEX_BYTES:
                    raise ToolchainError("The Alpine package index is larger than expected")
        if expected is not None and expected.isdigit() and len(data) != int(expected):
            raise _Incomplete("The download ended before the index was complete")
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(data)
        _atomic_replace(temporary, path)

    def _race_indexes(self, keys: dict[str, bytes], present: set[str]) -> tuple[str | None, Any]:
        """(mirror, its choice of packages) from the first mirror whose index verifies and resolves,
        or (None, [(mirror, error)]) when none does. All mirrors are read at once; the fastest one
        here wins and the others stop reading."""
        import mobile_alpine as alpine

        assert self.catalog is not None
        config = self.catalog["alpine"]
        architecture = self.catalog["architecture"]
        settled = threading.Event()
        changed = threading.Condition()
        results: list[tuple[str, Any]] = []  # In the order the mirrors finished.

        def read(number: int, mirror: str) -> None:
            index = alpine.Index()
            outcome: Any
            try:
                for repository in config["repositories"]:
                    path = self.download_dir / f"index-{number}-{repository}.tar.gz"
                    try:
                        self._fetch_index(
                            alpine.index_url(mirror, config["branch"], repository, architecture),
                            path,
                            settled,
                        )
                        alpine.parse_index(alpine.verify_index(path, keys), repository, index)
                    finally:
                        path.unlink(missing_ok=True)
                outcome = alpine.resolve(index, config["packages"], present)
            except Exception as error:  # Handed to the installer's thread.
                outcome = error
            with changed:
                if not isinstance(outcome, Exception):
                    settled.set()
                results.append((mirror, outcome))
                changed.notify_all()

        for number, mirror in enumerate(config["mirrors"]):
            threading.Thread(
                target=read, args=(number, mirror), daemon=True, name=f"android-toolchain-index-{number}"
            ).start()
        with changed:
            while True:
                winner = next(
                    ((mirror, outcome) for mirror, outcome in results if not isinstance(outcome, Exception)),
                    None,
                )
                if winner is not None:
                    return winner
                if self._cancelled.is_set():
                    settled.set()
                    raise _Cancelled("Toolchain installation was cancelled")
                if len(results) == len(config["mirrors"]):
                    return None, list(results)
                changed.wait(0.25)

    def _alpine_packages(self, rootfs_archive: Path) -> list[tuple[dict[str, Any], Path]]:
        """The catalog's Alpine packages at the branch's current versions, downloaded and checked.

        The index comes from the mirror that is first to serve both repositories with a valid
        signature, all of them asked at once; packages come from that mirror first, then the others.
        """
        import mobile_alpine as alpine

        assert self.catalog is not None
        config = self.catalog["alpine"]
        architecture = self.catalog["architecture"]
        try:
            keys, database = alpine.rootfs_trust(rootfs_archive)
        except (alpine.AlpineError, tarfile.TarError, OSError) as error:
            raise ToolchainError(f"The rootfs cannot check Alpine packages: {error}") from error
        present = alpine.installed_provides(database)
        attempt = 0
        while True:
            mirror, outcome = self._race_indexes(keys, present)
            if mirror is not None:
                chosen = outcome
                break
            if not any(_network_trouble(error) for _, error in outcome) or not self._wait_for_network(
                attempt
            ):
                # The page shows the reason as it is (translated); what each mirror said is kept apart.
                self._update(
                    failure_details=[
                        f"{urllib.parse.urlsplit(other).hostname}: {str(error)[:120]}"
                        for other, error in outcome
                    ]
                )
                raise ToolchainError(
                    "Could not read Alpine's package index; check the network and try again"
                )
            attempt += 1
        self._update(network_retry=None, mirror=urllib.parse.urlsplit(mirror).hostname)
        mirrors = [mirror, *(other for other in config["mirrors"] if other != mirror)]
        self._update(total_bytes=self._completed_bytes + sum(package.size for package in chosen))
        downloaded = []
        for package in chosen:
            if not re.fullmatch(r"Q1[A-Za-z0-9+/]{27}=", package.checksum):
                raise ToolchainError(f"Alpine's index gives {package.name} no checksum")
            item = {
                # The index checksum names exactly this build of the package.
                "id": "apk-" + base64.b64decode(package.checksum[2:]).hex(),
                "size": package.size,
                "urls": [
                    alpine.package_url(other, config["branch"], architecture, package)
                    for other in mirrors
                ],
            }
            def check(path: Path, package: Any = package) -> None:
                alpine.verify_package(path, package)

            try:
                path = self._download(item, verify=check)
            except (OSError, ToolchainError, http.client.HTTPException) as error:
                if isinstance(error, _Cancelled):
                    raise
                self._update(failure_details=[f"{package.name} {package.version}: {str(error)[:200]}"])
                raise ToolchainError(
                    "A toolchain package could not be downloaded or did not match Alpine's index; "
                    "try again"
                ) from error
            self._completed_bytes += package.size
            self._update(downloaded_bytes=self._completed_bytes)
            record = {"id": item["id"], "package": package.name, "version": package.version}
            downloaded.append(({**record, "license": package.license}, path))
        return downloaded

    def _prepare_guest(self, root: Path) -> None:
        for name in (
            "dev",
            "proc",
            "tmp",
            "home/agent",
            "etc",
            str(self.workspace).lstrip("/").replace(":", ""),
        ):
            (root / name).mkdir(parents=True, exist_ok=True)
        native = self._native_status()
        dns = [
            value
            for value in native.get("dns_servers", [])
            if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F:.]+", value)
        ]
        (root / "etc/resolv.conf").write_text(
            "".join(f"nameserver {value}\n" for value in (dns or ["1.1.1.1"])), "utf-8"
        )
        (root / "etc/passwd").write_text("root:x:0:0:Agent:/home/agent:/bin/sh\n", "utf-8")
        # Charts with Chinese, Japanese or Korean labels: glyphs DejaVu lacks come from the fallback.
        if next(root.glob("usr/share/fonts/*/DroidSansFallbackFull.ttf"), None):
            (root / "etc/matplotlibrc").write_text(
                "font.family: DejaVu Sans, Droid Sans Fallback\n", "utf-8"
            )

    def _remove_private_tree(self, path: Path) -> None:
        if not path.exists() and not path.is_symlink():
            return
        if path.parent.resolve() != self.root.resolve() or path.is_symlink():
            raise ToolchainError("Refusing to delete an unsafe toolchain path")
        shutil.rmtree(path)

    def _guest_argv(self, argv: list[str]) -> list[str]:
        raw = Path(argv[0])
        if raw.is_absolute() and raw.is_relative_to(self.rootfs):
            guest = "/" + raw.relative_to(self.rootfs).as_posix()
        elif argv[0].startswith("/"):
            guest = argv[0]
        else:
            aliases = {
                "sh": ["/bin/sh"],
                "shell": ["/bin/sh"],
                "python": ["/usr/bin/python3"],
                "python3": ["/usr/bin/python3"],
                "pip": ["/usr/bin/python3", "-m", "pip"],
                "pip3": ["/usr/bin/python3", "-m", "pip"],
                "pyright": ["/usr/bin/node", "/opt/pyright/index.js"],
                "pyright-langserver": ["/usr/bin/node", "/opt/pyright/langserver.index.js"],
                "npm": ["/usr/bin/node", "/usr/lib/node_modules/npm/bin/npm-cli.js"],
            }
            return [*aliases.get(argv[0], ["/usr/bin/" + argv[0]]), *argv[1:]]
        return [guest, *argv[1:]]

    def _wrap(
        self, argv: list[str], cwd: Path, workspace: str | Path | None = None
    ) -> tuple[list[str], dict[str, str]]:
        """`workspace` is the one the command belongs to (a conversation's own), and the only one
        the guest sees; the toolchain itself is shared by all of them."""
        native = self._require_native()
        bound = self.workspace if workspace is None else Path(workspace).resolve()
        if self.root.is_relative_to(bound) or bound.is_relative_to(self.root):
            raise ToolchainError("The toolchain must be installed outside the selected workspace")
        cwd = Path(cwd).resolve()
        if not cwd.is_relative_to(bound):
            raise ToolchainError("The command working directory escapes the workspace")
        if not argv or any(not isinstance(value, str) or "\x00" in value for value in argv):
            raise ToolchainError("The guest command arguments are invalid")
        guest_command = self._guest_argv(argv)
        launcher = str(native["launcher"])
        environment = {
            "LD_LIBRARY_PATH": str(native["native_library_dir"]),
            "PROOT_LOADER": str(native["loader"]),
            "PROOT_TMP_DIR": str(self.root / "temporary"),
            "PROOT_NO_SECCOMP": "1",
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": "/home/agent",
            "TMPDIR": "/tmp",
            "LANG": "C.UTF-8",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CEILING_DIRECTORIES": str(bound),
            "GIT_TERMINAL_PROMPT": "0",
            "PYTHONNOUSERSITE": "1",
            # pip installs into the toolchain's own Python (a reinstalled toolchain starts without
            # them). Alpine marks that Python as managed by apk, which nothing runs here.
            "PIP_BREAK_SYSTEM_PACKAGES": "1",
            "PIP_ROOT_USER_ACTION": "ignore",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_CACHE_DIR": "1",
            # No C compiler: an older wheel beats a newer source release that cannot build.
            "PIP_PREFER_BINARY": "1",
            "PIP_PROGRESS_BAR": "off",
            # Below a matplotlibrc of the working folder, above the user's own.
            "MATPLOTLIBRC": "/etc/matplotlibrc",
        }
        (self.root / "temporary").mkdir(exist_ok=True)
        with contextlib.suppress(OSError):  # Otherwise PRoot makes up the mount point on its own.
            (self.rootfs / str(bound).lstrip("/").replace(":", "")).mkdir(parents=True, exist_ok=True)
        from android_adapter.command_guard import binder_covers

        command = [
            launcher,
            "--kill-on-exit",
            "-0",
            "-r",
            str(self.rootfs),
            "-b",
            "/dev",
            # Not Binder, through which a guest program could ask Android for what the app may do.
            *binder_covers(self.root.parent),
            "-b",
            "/proc",
            "-b",
            f"{bound}:{bound}",
            "-w",
            str(cwd),
            *guest_command,
        ]
        return command, environment

    def wrap(
        self, argv: list[str], cwd: str | Path, workspace: str | Path | None = None
    ) -> tuple[list[str], dict[str, str]]:
        if not self._probed:
            raise ToolchainError("The toolchain has not passed its execution probes")
        if argv:
            guest_command = self._guest_argv(argv)
            used = {
                str((self.rootfs / part.lstrip("/")).resolve())
                for part in guest_command[:2]
                if part.startswith("/")
            }
            for record in self._executables.values():
                if record["path"] in used and _sha256(Path(record["path"])) != record["sha256"]:
                    raise ToolchainError("The discovered executable changed after probing")
            manifest = self._manifest()
            for relative, digest in manifest.get("components", {}).items():
                component = self.rootfs / _safe_relative(relative)
                if str(component.resolve()) in used and _sha256(component) != digest:
                    raise ToolchainError("The discovered command script changed after probing")
        return self._wrap(argv, Path(cwd), workspace)

    def owns_command(self, executable: str) -> bool:
        return bool(
            self._probed
            and (
                Path(executable).is_relative_to(self.rootfs)
                or executable
                in {
                    "git",
                    "python",
                    "python3",
                    "pip",
                    "pip3",
                    "node",
                    "npm",
                    "sh",
                    "shell",
                    "pyright",
                    "pyright-langserver",
                }
            )
        )

    def begin_process(self) -> None:
        with self._lock:
            if not self._probed or self._state.get("state") != "ready":
                raise ToolchainError("The toolchain is not ready")
            self._processes += 1

    def end_process(self) -> None:
        with self._lock:
            self._processes = max(0, self._processes - 1)

    def probe(self) -> dict[str, Any]:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                # A cancel pressed for an earlier install or probe must not stop this one.
                self._cancelled.clear()
        return self._probe()

    def _probe(self) -> dict[str, Any]:
        self._require_native()
        if not self._installed():
            raise ToolchainError("The verified toolchain is not installed")
        from android_adapter.terminal import _run_sync

        runner = self._runner or _run_sync
        self._update(state="probing", reason=None, probe_failure=None)
        self._probed = False
        manifest = self._manifest()
        found = {}
        try:
            self.workspace.mkdir(parents=True, exist_ok=True)
            for name, record in manifest["executables"].items():
                path = self.rootfs / _safe_relative(record["relative"])
                if (
                    not path.resolve().is_relative_to(self.rootfs.resolve())
                    or _sha256(path) != record["sha256"]
                ):
                    raise ToolchainError(f"The installed {name} executable changed")
                probe, accepted, expected = _PROBES.get(name, (["--version"], {0}, ""))
                arguments = (
                    [str(path), "-c", "printf agent-toolchain-shell"]
                    if name == "shell"
                    else [str(path), *probe]
                )
                if name == "pyright":
                    arguments = [
                        str(self.rootfs / "usr/bin/node"),
                        "/opt/pyright/index.js",
                        "--version",
                    ]
                argv, environment = self._wrap(arguments, self.workspace)
                response = runner(argv, str(self.workspace), 15, "", self._cancelled, environment)
                output = "\n".join(
                    value
                    for value in (
                        str(response.get("stdout") or ""),
                        str(response.get("stderr") or ""),
                    )
                    if value
                )
                if (
                    response.get("returncode") not in accepted
                    or (expected and expected not in output)
                    or response.get("timed_out")
                    or response.get("truncated")
                ):
                    failure = {
                        "executable": name,
                        "exit_code": response.get("returncode"),
                        "timed_out": bool(response.get("timed_out")),
                        "output": output[:4096],
                        "output_truncated": bool(response.get("truncated")) or len(output) > 4096,
                    }
                    self._update(probe_failure=failure)
                    raise ToolchainError(
                        f"The actual {name} execution probe failed on this Android device "
                        f"(exit code {failure['exit_code']}, timed out {failure['timed_out']}): "
                        f"{failure['output'][:1000]}"
                    )
                found[name] = {
                    "path": str(path.resolve()),
                    "sha256": record["sha256"],
                    # ssh -V writes its version to stderr.
                    "version": (str(response.get("stdout") or "").strip() or output.strip()).split("\n")[0][:200],
                    "runtime": "proot",
                }
            self._executables = found
            self._probed = True
            self._update(
                state="ready",
                reason=None,
                probes={key: value["version"] for key, value in found.items()},
            )
        except Exception as error:
            self._executables = {}
            self._update(state="probe_failed", reason=str(error)[:400])
            raise ToolchainError(str(error)) from error
        return self.snapshot()

    def executables(self) -> dict[str, dict[str, str]]:
        return self.snapshot()["executables"]

    def cancel(self) -> dict[str, Any]:
        self._cancelled.set()
        if self._thread is not None and self._thread.is_alive():
            self._update(state="cancelling")
        return self.snapshot()

    def remove(self) -> dict[str, Any]:
        with self._lock:
            if (self._thread is not None and self._thread.is_alive()) or self._processes:
                raise ToolchainError("Stop toolchain installation and processes before removal")
            for name in ("rootfs", "downloads", "installing", "previous", "temporary"):
                self._remove_private_tree(self.root / name)
            self.manifest_file.unlink(missing_ok=True)
            self._executables = {}
            self._probed = False
            self._update(state="not_installed", reason=None, downloaded_bytes=0, probes={})
            return self.snapshot()


_MANAGERS: dict[tuple[str, str], MobileToolchainManager] = {}
_MANAGER_LOCK = threading.RLock()


def get_toolchain_manager(
    data_dir: str | Path | None = None, workspace: str | Path | None = None
) -> MobileToolchainManager | None:
    data_dir = data_dir or os.getenv("AGENT_WORKSPACE_DATA_DIR")
    workspace = workspace or os.getenv("AGENT_WORKSPACE_ANDROID_WORKSPACE")
    if not data_dir or not workspace:
        return None
    key = (str(Path(data_dir).resolve()), str(Path(workspace).resolve()))
    with _MANAGER_LOCK:
        if key not in _MANAGERS:
            _MANAGERS[key] = MobileToolchainManager(*key)
        return _MANAGERS[key]
