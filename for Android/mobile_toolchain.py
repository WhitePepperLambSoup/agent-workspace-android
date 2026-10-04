"""Optional verified Linux tooling launched through packaged Android PRoot.

Downloading ELF files is insufficient on Android 10+: only the APK's installed
launcher/loader execute directly. Guest tools run through that loader, using a
private root filesystem. This supplies app-level tooling, not an OS sandbox.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import tarfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

_MAX_EXTRACTED_BYTES = 700 * 1024 * 1024
_MAX_MEMBERS = 60000
_ACTIVE = {"downloading", "extracting", "probing", "cancelling"}


class ToolchainError(RuntimeError):
    pass


class _Cancelled(ToolchainError):
    pass


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
            if (
                not name
                or name == "."
                or name.startswith((".SIGN.", ".PKGINFO", ".INSTALL", ".trigger"))
            ):
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
        self._native_status = native_status
        self._runner = probe_runner
        self._lock = threading.RLock()
        self._cancelled = threading.Event()
        self._thread: threading.Thread | None = None
        self._probed = False
        self._executables: dict[str, dict[str, str]] = {}
        self._processes = 0
        self._completed_bytes = 0
        self._state = self._read_json(self.state_file)
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

    def _installed(self) -> bool:
        if not self.catalog or self.rootfs.is_symlink():
            return False
        manifest = self._read_json(self.rootfs / ".agent-toolchain.json")
        return manifest.get("revision") == self.catalog["revision"]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            native = self._native_status()
            installed = self._installed()
            available = installed and self._probed and native.get("available") is True
            state = self._state.get("state", "not_installed")
            if installed and not available and state == "ready":
                state = "needs_probe"
            return {
                **self._state,
                "state": state,
                "installed": installed,
                "available": available,
                "supported": self.catalog is not None and native.get("available") is True,
                "reason": self._state.get("reason") or native.get("reason"),
                "revision": self.catalog.get("revision") if self.catalog else None,
                "architecture": native.get("architecture"),
                "download_size": sum(item["size"] for item in self.catalog["artifacts"])
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
            self._update(state="downloading", reason=None)
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
            (staging / ".agent-toolchain.json").write_text(
                json.dumps(
                    {
                        "revision": self.catalog["revision"],
                        "executables": executables,
                        "components": components,
                    }
                ),
                "utf-8",
            )
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
            self._remove_private_tree(previous)
            self._probed = False
            self.probe()
        except _Cancelled:
            self._update(
                state="paused",
                reason="Installation was cancelled; retry to resume downloaded content",
            )
            raise
        except Exception as error:
            self._probed = False
            self._executables = {}
            reason = (
                str(error)[:400]
                if isinstance(error, ToolchainError)
                else "Toolchain installation failed"
            )
            self._update(state="failed", reason=reason)
            raise ToolchainError(reason) from error
        finally:
            self._remove_private_tree(staging)

    def _download(self, item: dict[str, Any]) -> Path:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,120}", item["id"]):
            raise ToolchainError("Invalid toolchain artifact ID")
        archive = self.download_dir / (item["id"] + ".archive")
        partial = self.download_dir / (item["id"] + ".part")
        if (
            archive.is_file()
            and archive.stat().st_size == item["size"]
            and _sha256(archive) == item["sha256"]
        ):
            return archive
        if self._cancelled.is_set():
            raise _Cancelled("Toolchain installation was cancelled")
        start = partial.stat().st_size if partial.exists() else 0
        if start >= item["size"]:
            if start == item["size"] and _sha256(partial) == item["sha256"]:
                _atomic_replace(partial, archive)
                return archive
            partial.unlink()
            start = 0
        headers = {"Accept-Encoding": "identity", "User-Agent": "AgentWorkspace-AndroidToolchain/1"}
        if start:
            headers["Range"] = f"bytes={start}-"
        request = urllib.request.Request(item["url"], headers=headers)
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
                        )
                        last_update = now
        if received != item["size"] or _sha256(partial) != item["sha256"]:
            partial.unlink(missing_ok=True)
            raise ToolchainError("The downloaded artifact failed its pinned size or SHA-256 check")
        _atomic_replace(partial, archive)
        return archive

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
                "pyright": ["/usr/bin/node", "/opt/pyright/index.js"],
                "pyright-langserver": ["/usr/bin/node", "/opt/pyright/langserver.index.js"],
                "npm": ["/usr/bin/node", "/usr/lib/node_modules/npm/bin/npm-cli.js"],
            }
            return [*aliases.get(argv[0], ["/usr/bin/" + argv[0]]), *argv[1:]]
        return [guest, *argv[1:]]

    def _wrap(self, argv: list[str], cwd: Path) -> tuple[list[str], dict[str, str]]:
        native = self._require_native()
        cwd = Path(cwd).resolve()
        if not cwd.is_relative_to(self.workspace):
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
            "GIT_CEILING_DIRECTORIES": str(self.workspace),
            "GIT_TERMINAL_PROMPT": "0",
            "PYTHONNOUSERSITE": "1",
        }
        (self.root / "temporary").mkdir(exist_ok=True)
        command = [
            launcher,
            "--kill-on-exit",
            "-0",
            "-r",
            str(self.rootfs),
            "-b",
            "/dev",
            "-b",
            "/proc",
            "-b",
            f"{self.workspace}:{self.workspace}",
            "-w",
            str(cwd),
            *guest_command,
        ]
        return command, environment

    def wrap(self, argv: list[str], cwd: str | Path) -> tuple[list[str], dict[str, str]]:
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
            manifest = self._read_json(self.rootfs / ".agent-toolchain.json")
            for relative, digest in manifest.get("components", {}).items():
                component = self.rootfs / _safe_relative(relative)
                if str(component.resolve()) in used and _sha256(component) != digest:
                    raise ToolchainError("The discovered command script changed after probing")
        return self._wrap(argv, Path(cwd))

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
        self._require_native()
        if not self._installed():
            raise ToolchainError("The verified toolchain is not installed")
        from android_adapter.terminal import _run_sync

        runner = self._runner or _run_sync
        self._update(state="probing", reason=None, probe_failure=None)
        self._probed = False
        manifest = self._read_json(self.rootfs / ".agent-toolchain.json")
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
                arguments = (
                    [str(path), "-c", "printf agent-toolchain-shell"]
                    if name == "shell"
                    else [str(path), "--version"]
                )
                if name == "pyright":
                    arguments = [
                        str(self.rootfs / "usr/bin/node"),
                        "/opt/pyright/index.js",
                        "--version",
                    ]
                argv, environment = self._wrap(arguments, self.workspace)
                response = runner(argv, str(self.workspace), 15, "", self._cancelled, environment)
                if (
                    response.get("returncode") != 0
                    or response.get("timed_out")
                    or response.get("truncated")
                ):
                    output = "\n".join(
                        value
                        for value in (
                            str(response.get("stdout") or ""),
                            str(response.get("stderr") or ""),
                        )
                        if value
                    )
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
                    "version": str(response.get("stdout", "")).strip().split("\n")[0][:200],
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
