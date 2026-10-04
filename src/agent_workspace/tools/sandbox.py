from __future__ import annotations

import asyncio
import contextlib
import ctypes
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable
from uuid import uuid4

from agent_workspace.core.events import Event
from agent_workspace.core.models import Autonomy, BinaryArtifact, Capability, ToolSpec
from agent_workspace.core.sandbox_changes import build_sandbox_changeset_data
from agent_workspace.policy.network_allowlist import SandboxNetworkPolicy

from .base import (
    ToolArgumentError,
    ToolError,
    json_result,
    optional_bool,
    optional_int,
)
from .command import (
    _required_executable_sha256,
    _resolve_executable,
    _safe_environment,
)
from .native_isolation import NativeIsolationReport, inspect_native_isolation
from .paths import StrPath, WorkspacePaths, is_sensitive_workspace_path
from .process_worker import run_in_process
from .sandbox_staging import (
    StagingWorkspace,
    capture_staging_artifacts_sync,
    create_staging_workspace_sync,
    diff_staging_workspace_sync,
    recover_stale_staging_workspaces_sync,
    remove_staging_workspace_sync,
    set_staging_owner_sync,
    staging_creating_root_for_execution,
    staging_root_for_execution,
)

if TYPE_CHECKING:
    from agent_workspace.application.ports import ToolExecutionContext

_MAX_ARGUMENTS = 256
_MAX_ARGUMENT_CHARS = 32_767
_MAX_ARGUMENT_BYTES = 128 * 1024
_MAX_RETAINED_STREAM_BYTES = 64 * 1024
_MAX_OBSERVED_STREAM_BYTES = 2 * 1024 * 1024
_READ_CHUNK_BYTES = 16 * 1024
_PROBE_TIMEOUT_SECONDS = 8
_CLEANUP_TIMEOUT_SECONDS = 10
_MAX_MOUNT_ENTRIES = 500_000
_MAX_STALE_CONTAINERS = 128
_IMAGE_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_IMAGE_REPOSITORY = re.compile(r"[a-z0-9][a-z0-9._:/-]*[a-z0-9]\Z")
_NUMERIC_NON_ROOT_USER = re.compile(r"[1-9][0-9]*:[1-9][0-9]*\Z")
_CONTAINER_ID = re.compile(r"[0-9a-f]{12,64}\Z")
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_LOCAL_SANDBOX_TAG = "agent-workspace-sandbox:local"


def _default_sandbox_user() -> str:
    if os.name == "nt":
        return "65532:65532"
    platform_os: Any = os
    return f"{platform_os.getuid()}:{platform_os.getgid()}"


@dataclass(frozen=True, slots=True)
class SandboxRequest:
    argv: tuple[str, ...]
    workspace: str
    execution_id: str | None = None
    sensitive_count: int = 0
    sensitive_sha256: str = _EMPTY_SHA256
    cwd: str = "."
    timeout_seconds: int = 60
    read_only_workspace: bool = False


@dataclass(frozen=True, slots=True)
class SandboxCapabilityReport:
    """Effective execution capability and its explicit security boundary."""

    capability: Literal["isolated", "restricted_host", "unavailable"]
    code: str
    can_execute: bool
    process_boundary: Literal["job_object", "host_process", "unavailable"]
    os_filesystem_boundary: bool
    network_boundary: bool
    risk_boundary: tuple[str, ...] = ()
    remediation: tuple[str, ...] = ()
    verification_evidence: tuple[str, ...] = ()
    repair_action: str = ""

    def to_document(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "code": self.code,
            "can_execute": self.can_execute,
            "process_boundary": self.process_boundary,
            "os_filesystem_boundary": self.os_filesystem_boundary,
            "network_boundary": self.network_boundary,
            "risk_boundary": list(self.risk_boundary),
            "remediation": list(self.remediation),
            "verification_evidence": list(self.verification_evidence),
            "repair_action": self.repair_action,
        }


@dataclass(frozen=True, slots=True)
class SandboxStatus:
    backend: str
    available: bool
    reason: str
    image: str | None
    executable: str | None
    executable_sha256: str | None
    network: str = "none"
    workspace_mount: str = "read-only-or-staged"
    isolation: tuple[str, ...] = ()
    fallback: str = "none"
    actions: tuple[dict[str, str], ...] = ()
    diagnostic_layer: str = "unknown"
    diagnostic_code: str = "unknown"
    capability: str = "unknown"
    risk_boundary: tuple[str, ...] = ()
    remediation: tuple[str, ...] = ()
    native_isolation: NativeIsolationReport | None = None
    code: str = "ready"
    can_execute: bool = True
    verification_evidence: tuple[str, ...] = ()
    repair_action: str = ""

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "backend": self.backend,
            "available": self.available,
            "reason": self.reason,
            "image": self.image,
            "executable": self.executable,
            "executable_sha256": self.executable_sha256,
            "network": self.network,
            "workspace_mount": self.workspace_mount,
            "isolation": list(self.isolation),
            "fallback": self.fallback,
            "actions": [dict(action) for action in self.actions],
            "diagnostic_layer": self.diagnostic_layer,
            "diagnostic_code": self.diagnostic_code,
            "capability": self.capability,
            "risk_boundary": list(self.risk_boundary),
            "remediation": list(self.remediation),
            "code": self.code,
            "can_execute": self.can_execute,
            "verification_evidence": list(self.verification_evidence),
            "repair_action": self.repair_action,
        }
        if self.native_isolation is not None:
            document["native_isolation"] = self.native_isolation.to_document()
        return document

    def to_model_document(self) -> dict[str, Any]:
        document = self.to_document()
        document.pop("executable", None)
        document.pop("executable_sha256", None)
        if not self.available:
            document["isolation"] = []
        return document


def _autonomy_value(autonomy: Autonomy | str) -> str:
    if isinstance(autonomy, Autonomy):
        return autonomy.value
    return str(autonomy).strip().casefold()


def sandbox_status(
    *,
    autonomy: Autonomy | str = Autonomy.WORKSPACE,
    require_isolation: bool = False,
    native_report: NativeIsolationReport | None = None,
    backend: str = "host-staged",
    available: bool = True,
) -> SandboxCapabilityReport:
    """Return the bounded capability decision for a sandbox status request.

    ``host-staged`` is useful for reviewable workspace changes, but it is not
    an OS security boundary.  Callers that require isolation therefore receive
    a stable failure code instead of an implicit host-process fallback.
    """

    strict_isolation = require_isolation or _autonomy_value(autonomy) == "yolo"
    normalized_backend = backend.strip().casefold()
    native = native_report or inspect_native_isolation()
    risks = native.risk_boundary
    remediation = native.remediation
    verification_evidence = native.verification_evidence
    repair_action = native.repair_action

    if not available:
        code = "sandbox.job_object_unavailable"
        return SandboxCapabilityReport(
            capability="unavailable",
            code=code,
            can_execute=False,
            process_boundary=native.process_boundary,
            os_filesystem_boundary=native.os_filesystem_boundary,
            network_boundary=native.network_boundary,
            risk_boundary=risks,
            remediation=remediation,
            verification_evidence=verification_evidence,
            repair_action=repair_action,
        )

    isolated = (
        native.verified_isolation
        and native.can_run_untrusted_code
        and native.os_filesystem_boundary
        and native.network_boundary
    )
    if isolated:
        return SandboxCapabilityReport(
            capability="isolated",
            code="ready",
            can_execute=True,
            process_boundary=native.process_boundary,
            os_filesystem_boundary=native.os_filesystem_boundary,
            network_boundary=native.network_boundary,
            risk_boundary=risks,
            remediation=remediation,
            verification_evidence=verification_evidence,
            repair_action=repair_action,
        )

    if strict_isolation:
        code = (
            "sandbox.job_object_unavailable"
            if native.process_boundary != "job_object"
            else "sandbox.host_staged_only"
        )
        if not native.verified_isolation:
            remediation = (
                *remediation,
                "Isolation boundary is not verified; keep untrusted execution disabled.",
            )
        return SandboxCapabilityReport(
            capability="restricted_host",
            code=code,
            can_execute=False,
            process_boundary=native.process_boundary,
            os_filesystem_boundary=native.os_filesystem_boundary,
            network_boundary=native.network_boundary,
            risk_boundary=risks,
            remediation=remediation,
            verification_evidence=verification_evidence,
            repair_action=repair_action,
        )

    code = "sandbox.network_not_isolated" if not native.network_boundary else "ready"
    if normalized_backend not in {"host-staged", "host", "local"}:
        code = "ready"
    return SandboxCapabilityReport(
        capability="restricted_host",
        code=code,
        can_execute=True,
        process_boundary=native.process_boundary,
        os_filesystem_boundary=native.os_filesystem_boundary,
        network_boundary=native.network_boundary,
        risk_boundary=risks,
        remediation=remediation,
        verification_evidence=verification_evidence,
        repair_action=repair_action,
    )


def _capability_for_status(
    status: SandboxStatus,
    *,
    autonomy: Autonomy | str = Autonomy.WORKSPACE,
    require_isolation: bool = False,
) -> SandboxCapabilityReport:
    if status.backend.strip().casefold() in {"host-staged", "host", "local"}:
        native = status.native_isolation or inspect_native_isolation()
        return sandbox_status(
            autonomy=autonomy,
            require_isolation=require_isolation,
            native_report=native,
            backend=status.backend,
            available=status.available,
        )

    capability = status.capability
    if capability not in {"isolated", "restricted_host", "unavailable"}:
        capability = "isolated" if status.available else "unavailable"
    return SandboxCapabilityReport(
        capability=capability,  # type: ignore[arg-type]
        code=status.code if status.available else status.diagnostic_code,
        can_execute=status.available and status.can_execute,
        process_boundary=("job_object" if status.available else "unavailable"),
        os_filesystem_boundary=capability == "isolated",
        network_boundary=status.network == "none",
        risk_boundary=status.risk_boundary,
        remediation=status.remediation,
        verification_evidence=(
            status.native_isolation.verification_evidence
            if status.native_isolation is not None
            else ()
        ),
        repair_action=(
            status.native_isolation.repair_action if status.native_isolation is not None else ""
        ),
    )


@runtime_checkable
class SandboxBackend(Protocol):
    async def status(self) -> SandboxStatus: ...

    async def execute(self, request: SandboxRequest) -> str | SandboxExecutionResult: ...


class SandboxBackendRegistry:
    def __init__(
        self, factories: dict[str, Callable[[WorkspacePaths], SandboxBackend]] | None = None
    ):
        self._factories = dict(factories or {})

    @classmethod
    def default(
        cls,
        config: LocalSandboxConfig | None = None,
        *,
        include_host_staged: bool = True,
    ) -> SandboxBackendRegistry:
        """Build the only backend exposed to normal runtime/model execution.

        The project-local staged backend is deliberately the default and the
        only backend registered here.  The legacy Docker implementation stays
        available as an internal compatibility class for old unit tests and
        migrations, but it is never instantiated through the runtime registry.
        ``include_host_staged`` is retained as a source-compatible argument for
        callers that used the old opt-in API; it no longer changes the result.
        """

        # Lazy import avoids a circular import through SandboxStatus while
        # keeping the runtime independent of Docker and its environment.
        from .host_staged_sandbox import HostStagedSandboxBackend

        return cls({"host-staged": lambda paths: HostStagedSandboxBackend(paths, config)})

    def register(
        self, backend_id: str, factory: Callable[[WorkspacePaths], SandboxBackend]
    ) -> None:
        if not backend_id or backend_id in self._factories:
            raise ValueError("sandbox backend id is invalid or already registered")
        if backend_id.strip().casefold() == "docker":
            raise ValueError("the legacy Docker sandbox backend is disabled")
        self._factories[backend_id] = factory

    def create(self, backend_id: str, workspace: WorkspacePaths | StrPath) -> SandboxBackend:
        paths = workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        try:
            factory = self._factories[backend_id]
        except KeyError:
            raise ToolError(f"sandbox backend is not registered: {backend_id}") from None
        if backend_id.strip().casefold() == "docker":
            raise ToolError("the legacy Docker sandbox backend is disabled")
        backend = factory(paths)
        if not isinstance(backend, SandboxBackend):
            raise ToolError(f"sandbox backend does not implement its contract: {backend_id}")
        backend_id_value = getattr(backend, "backend_id", "")
        if isinstance(backend_id_value, str) and backend_id_value.casefold() == "docker":
            raise ToolError("the legacy Docker sandbox backend is disabled")
        return backend

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))


def resolve_sandbox_backend_id(requested: str, autonomy: Autonomy) -> str:
    """Resolve a backend name without ever selecting the legacy Docker backend.

    ``docker`` remains accepted as a compatibility alias because older saved
    sessions and callers may still carry that value.  It is mapped to the
    project-local staged backend before registry lookup, so the model/runtime
    can never instantiate or invoke Docker through this path.
    """

    del autonomy  # retained in the public signature for caller compatibility
    if not isinstance(requested, str) or not requested.strip():
        raise ValueError("sandbox backend id must be a non-empty string")
    selected = requested.strip().casefold()
    if selected in {"docker", "host", "local", "host-staged"}:
        return "host-staged"
    return selected


@dataclass(frozen=True, slots=True)
class SandboxExecutionResult:
    document: dict[str, Any]
    artifacts: tuple[BinaryArtifact, ...] = ()


@dataclass(frozen=True, slots=True)
class LocalSandboxConfig:
    """Limits used by the built-in staged workspace backend.

    This configuration is intentionally independent of any container runtime.
    The local backend stages the workspace itself and relies on the process
    worker's native process-tree limits for child execution.
    """

    max_workspace_growth_bytes: int = 2 * 1024 * 1024 * 1024
    minimum_free_space_bytes: int = 512 * 1024 * 1024

    def __post_init__(self) -> None:
        for value in (
            self.max_workspace_growth_bytes,
            self.minimum_free_space_bytes,
        ):
            if type(value) is not int or value <= 0:
                raise ValueError("local sandbox limits must be positive integers")


async def _shielded_worker_cleanup(
    function: Callable[..., str],
    *arguments: Any,
    allow_children: bool = False,
) -> None:
    cancelled = False
    cleanup = asyncio.create_task(
        run_in_process(function, *arguments, allow_children=allow_children)
    )
    while not cleanup.done():
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            cancelled = True
            continue
    cleanup.result()
    if cancelled:
        raise asyncio.CancelledError


@dataclass(frozen=True, slots=True)
class DockerSandboxConfig:
    image: str | None = None
    docker_executable: str | None = None
    docker_executable_sha256: str | None = None
    memory_bytes: int = 2 * 1024 * 1024 * 1024
    cpu_count: float = 2.0
    process_limit: int = 64
    temporary_bytes: int = 256 * 1024 * 1024
    max_workspace_growth_bytes: int = 2 * 1024 * 1024 * 1024
    minimum_free_space_bytes: int = 512 * 1024 * 1024
    user: str = field(default_factory=_default_sandbox_user)
    network_allowlist: SandboxNetworkPolicy | None = None

    def __post_init__(self) -> None:
        integer_limits = (
            self.memory_bytes,
            self.process_limit,
            self.temporary_bytes,
            self.max_workspace_growth_bytes,
            self.minimum_free_space_bytes,
        )
        if any(type(value) is not int or value <= 0 for value in integer_limits):
            raise ValueError("Docker sandbox integer limits must be positive")
        if (
            isinstance(self.cpu_count, bool)
            or not isinstance(self.cpu_count, (int, float))
            or not 0 < self.cpu_count <= 64
        ):
            raise ValueError("Docker sandbox CPU limit must be from 0 to 64")
        if (
            len(self.user) > 128
            or _NUMERIC_NON_ROOT_USER.fullmatch(self.user) is None
            or any(int(part) > 65534 for part in self.user.split(":", maxsplit=1))
        ):
            raise ValueError("Docker sandbox user must be a non-root numeric UID:GID")
        if (
            self.docker_executable_sha256 is not None
            and _IMAGE_DIGEST.fullmatch(self.docker_executable_sha256) is None
        ):
            raise ValueError("Docker executable SHA-256 must be 64 lowercase hex characters")
        if self.docker_executable is not None and self.docker_executable_sha256 is None:
            raise ValueError("a custom Docker executable requires its expected SHA-256")

    def network_policy_document(self) -> dict[str, Any] | None:
        if self.network_allowlist is None:
            return None
        return {
            "entries": [
                {"id": entry.id, "pattern": entry.pattern}
                for entry in self.network_allowlist.entries
            ]
        }

    @classmethod
    def from_environment(cls) -> DockerSandboxConfig:
        return cls(
            image=os.getenv("AGENT_WORKSPACE_SANDBOX_IMAGE") or None,
            docker_executable=os.getenv("AGENT_WORKSPACE_DOCKER_EXECUTABLE") or None,
            docker_executable_sha256=os.getenv("AGENT_WORKSPACE_DOCKER_SHA256") or None,
        )


class DockerSandboxBackend:
    # Kept only for legacy low-level compatibility tests and migration code. The
    # registry and model-facing tool path reject this backend id.
    backend_id = "docker"

    def __init__(
        self,
        workspace: WorkspacePaths | StrPath,
        config: DockerSandboxConfig | None = None,
    ) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self.config = config or DockerSandboxConfig.from_environment()
        self._recovery_lock = asyncio.Lock()
        self._recovery_complete = False
        self._staging_recovery_lock = asyncio.Lock()
        self._staging_recovery_complete = False

    async def status(self) -> SandboxStatus:
        try:
            executable = _resolve_docker_executable(self.paths, self.config)
            executable_sha256 = _required_executable_sha256(executable)
            if (
                self.config.docker_executable_sha256 is not None
                and executable_sha256 != self.config.docker_executable_sha256
            ):
                raise ToolError("Docker executable does not match its configured SHA-256")
        except (ToolArgumentError, ToolError, ValueError) as exc:
            return _sandbox_status(False, str(exc))
        try:
            image = self.config.image
            if image is None:
                image = await run_in_process(
                    _discover_local_sandbox_image_sync,
                    str(executable),
                    executable_sha256,
                    allow_children=True,
                )
                image = image.strip() or None
            image = _required_pinned_image(image)
        except (ToolArgumentError, ToolError, ValueError) as exc:
            return _sandbox_status(
                False,
                str(exc),
                executable=executable,
                executable_sha256=executable_sha256,
            )
        try:
            raw = await run_in_process(
                _probe_docker_sync,
                str(executable),
                executable_sha256,
                image,
                allow_children=True,
            )
            probe = json.loads(raw)
        except (ToolError, json.JSONDecodeError, TypeError, ValueError) as exc:
            return _sandbox_status(
                False,
                " ".join(str(exc).split())[:1000] or type(exc).__name__,
                image=image,
                executable=executable,
                executable_sha256=executable_sha256,
            )
        if not isinstance(probe, dict) or not probe.get("available"):
            reason = str(probe.get("reason", "Docker sandbox is unavailable"))[:1000]
            return _sandbox_status(
                False,
                reason,
                image=image,
                executable=executable,
                executable_sha256=executable_sha256,
            )
        return _sandbox_status(
            True,
            "Docker daemon and pinned sandbox image are available",
            image=image,
            executable=executable,
            executable_sha256=executable_sha256,
        )

    async def _recover_stale_containers(
        self,
        executable: Path,
        executable_sha256: str,
    ) -> None:
        if self._recovery_complete:
            return
        async with self._recovery_lock:
            if self._recovery_complete:
                return
            await run_in_process(
                _recover_stale_containers_sync,
                str(executable),
                executable_sha256,
                _workspace_label(self.paths.root),
                allow_children=True,
            )
            self._recovery_complete = True

    async def _recover_stale_staging_workspaces(self) -> None:
        if self._staging_recovery_complete:
            return
        async with self._staging_recovery_lock:
            if self._staging_recovery_complete:
                return
            for _ in range(8):
                raw = await run_in_process(recover_stale_staging_workspaces_sync)
                document = json.loads(raw)
                if not isinstance(document, dict):
                    raise ToolError("staging recovery returned an invalid result")
                remaining = document.get("remaining", 0)
                if not isinstance(remaining, int) or isinstance(remaining, bool) or remaining < 0:
                    raise ToolError("staging recovery returned an invalid remaining count")
                if remaining == 0:
                    self._staging_recovery_complete = True
                    return
            raise ToolError("too many stale staging workspaces to recover in one execution")

    async def execute(self, request: SandboxRequest) -> str | SandboxExecutionResult:
        requested_workspace = WorkspacePaths(request.workspace)
        if requested_workspace.root != self.paths.root:
            raise ToolError("sandbox request workspace does not match its backend workspace")
        status = await self.status()
        if not status.available or status.executable is None or status.executable_sha256 is None:
            raise ToolError(f"sandbox is unavailable: {status.reason}")
        await self._recover_stale_containers(
            Path(status.executable),
            status.executable_sha256,
        )
        execution_id = request.execution_id or uuid4().hex
        staging_root: Path | None = None
        staging_creating_root: Path | None = None
        try:
            mount_workspace = str(self.paths.root)
            if not request.read_only_workspace:
                await self._recover_stale_staging_workspaces()
                staging_root = staging_root_for_execution(
                    execution_id,
                    uuid4().hex,
                    os.getpid(),
                )
                staging_creating_root = staging_creating_root_for_execution(
                    staging_root,
                    uuid4().hex,
                    os.getpid(),
                )
                raw_staging = await run_in_process(
                    create_staging_workspace_sync,
                    str(self.paths.root),
                    str(staging_root),
                    execution_id,
                    os.getpid(),
                    self.config.user,
                    self.config.max_workspace_growth_bytes,
                    self.config.minimum_free_space_bytes,
                    str(staging_creating_root),
                )
                staging_document = json.loads(raw_staging)
                if not isinstance(staging_document, dict):
                    raise ToolError("sandbox staging worker returned an invalid result")
                staging = StagingWorkspace.from_document(staging_document)
                mount_workspace = staging.workspace

            container_name = _container_name(execution_id, uuid4().hex)
            try:
                raw_result = await run_in_process(
                    _run_docker_sandbox_sync,
                    str(self.paths.root),
                    mount_workspace,
                    status.executable,
                    status.executable_sha256,
                    _required_pinned_image(status.image),
                    list(request.argv),
                    request.sensitive_count,
                    request.sensitive_sha256,
                    request.cwd,
                    request.timeout_seconds,
                    request.read_only_workspace,
                    self.config.memory_bytes,
                    self.config.cpu_count,
                    self.config.process_limit,
                    self.config.temporary_bytes,
                    self.config.max_workspace_growth_bytes,
                    self.config.minimum_free_space_bytes,
                    self.config.user,
                    container_name,
                    _workspace_label(self.paths.root),
                    execution_id,
                    allow_children=True,
                )
            finally:
                await _shielded_worker_cleanup(
                    _remove_container_sync,
                    status.executable,
                    status.executable_sha256,
                    container_name,
                    allow_children=True,
                )

            if staging_root is None:
                return raw_result
            raw_changes = await run_in_process(
                diff_staging_workspace_sync,
                str(self.paths.root),
                str(staging_root),
                execution_id,
            )
            result_document = json.loads(raw_result)
            changes_document = json.loads(raw_changes)
            if not isinstance(result_document, dict) or not isinstance(changes_document, dict):
                raise ToolError("sandbox worker returned an invalid staged result")
            result_document["changes"] = changes_document
            raw_change_items = changes_document.get("changes")
            if not isinstance(raw_change_items, list):
                raise ToolError("sandbox change manifest is invalid")
            expected_files: list[tuple[str, int, str]] = []
            for change in raw_change_items:
                if not isinstance(change, dict) or change.get("after_type") != "file":
                    continue
                path = change.get("path")
                byte_count = change.get("after_bytes")
                sha256 = change.get("after_sha256")
                if (
                    isinstance(path, str)
                    and type(byte_count) is int
                    and 0 <= byte_count <= 16 * 1024 * 1024
                    and isinstance(sha256, str)
                ):
                    expected_files.append((path, byte_count, sha256))
            captured = await run_in_process(
                capture_staging_artifacts_sync,
                str(staging_root),
                execution_id,
                tuple(expected_files),
            )
            if not isinstance(captured, tuple) or any(
                not isinstance(artifact, BinaryArtifact) for artifact in captured
            ):
                raise ToolError("sandbox artifact worker returned an invalid result")
            return SandboxExecutionResult(result_document, captured)
        finally:
            if staging_root is not None:
                await _shielded_worker_cleanup(
                    remove_staging_workspace_sync,
                    str(staging_root),
                    execution_id,
                    str(staging_creating_root) if staging_creating_root is not None else None,
                )


class SandboxStatusTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="sandbox_status",
        description=(
            "Report whether the project-local staged execution sandbox is available. Commands "
            "run in a disposable workspace copy with bounded output and process limits; host "
            "filesystem and network access remain visible. This performs no workspace or network "
            "operation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "autonomy": {
                    "type": "string",
                    "enum": ["ask", "workspace", "yolo", "full_access"],
                },
                "require_isolation": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.PROCESS_EXECUTE,
    )

    def __init__(self, backend: SandboxBackend) -> None:
        self.backend = backend

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        status = await self.backend.status()
        autonomy = arguments.get("autonomy", Autonomy.WORKSPACE)
        require_isolation = arguments.get("require_isolation", False)
        if not isinstance(require_isolation, bool):
            raise ToolArgumentError("'require_isolation' must be a boolean")
        report = _capability_for_status(
            status,
            autonomy=autonomy if isinstance(autonomy, (str, Autonomy)) else Autonomy.WORKSPACE,
            require_isolation=require_isolation,
        )
        document = status.to_model_document()
        document.update(report.to_document())
        document["sandbox_capability"] = report.to_document()
        return json_result(document)


class RunSandboxTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="run_sandbox",
        description=(
            "Run an argv command in the project-local staged execution sandbox. The command runs "
            "in a disposable workspace copy, returns bounded stdout/stderr and a reviewable "
            "change manifest, and enforces process and timeout limits. Host filesystem and "
            "network access remain visible, so this is a workflow isolation boundary rather than "
            "a security boundary. If local staging is unavailable, the result contains a "
            "fallback hint: call discover_executables and then run_process with the normal "
            "autonomy-specific approval policy."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "argv": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "maxLength": _MAX_ARGUMENT_CHARS},
                    "minItems": 1,
                    "maxItems": _MAX_ARGUMENTS,
                },
                "cwd": {"type": "string", "minLength": 1, "default": "."},
                "timeout_seconds": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 110,
                    "default": 60,
                },
                "read_only_workspace": {"type": "boolean", "default": False},
            },
            "required": ["argv"],
            "additionalProperties": False,
        },
        side_effect="sandboxed_process",
        capability=Capability.PROCESS_EXECUTE,
    )

    def __init__(
        self,
        workspace: WorkspacePaths | StrPath,
        backend: SandboxBackend,
    ) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self.backend = backend

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def prepare_for_approval(self, arguments: dict[str, Any]) -> dict[str, Any]:
        prepared = dict(arguments)
        sensitive_count, sensitive_sha256 = _validate_workspace_mount(self.paths.root)
        prepared["_sandbox_sensitive_count"] = sensitive_count
        prepared["_sandbox_sensitive_sha256"] = sensitive_sha256
        return prepared

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await self.execute_with_context(arguments, None)

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext | None,
    ) -> str:
        if "_sandbox_sensitive_count" not in arguments:
            arguments = self.prepare_for_approval(arguments)
        raw_argv = arguments.get("argv")
        if (
            not isinstance(raw_argv, list)
            or not raw_argv
            or any(not isinstance(item, str) or not item or "\x00" in item for item in raw_argv)
        ):
            raise ToolArgumentError("'argv' must be a non-empty array of non-empty strings")
        if len(raw_argv) > _MAX_ARGUMENTS or any(
            len(item) > _MAX_ARGUMENT_CHARS for item in raw_argv
        ):
            raise ToolArgumentError("sandbox command arguments exceed their safety limit")
        encoded_bytes = sum(len(item.encode("utf-8")) for item in raw_argv)
        if encoded_bytes > _MAX_ARGUMENT_BYTES:
            raise ToolArgumentError("sandbox command arguments exceed their byte limit")
        raw_cwd = arguments.get("cwd", ".")
        if not isinstance(raw_cwd, str) or not raw_cwd:
            raise ToolArgumentError("'cwd' must be a non-empty string")
        cwd = self.paths.resolve(raw_cwd)
        if not cwd.is_dir():
            raise ToolError(f"sandbox working directory is not a directory: {cwd}")
        timeout_seconds = optional_int(
            arguments,
            "timeout_seconds",
            60,
            minimum=1,
            maximum=110,
        )
        read_only_workspace = optional_bool(arguments, "read_only_workspace", False)
        sensitive_count = arguments.get("_sandbox_sensitive_count")
        sensitive_sha256 = arguments.get("_sandbox_sensitive_sha256")
        if (
            not isinstance(sensitive_count, int)
            or isinstance(sensitive_count, bool)
            or sensitive_count < 0
            or not isinstance(sensitive_sha256, str)
            or _IMAGE_DIGEST.fullmatch(sensitive_sha256) is None
        ):
            raise ToolArgumentError("sandbox sensitive-path identity is invalid")
        request = SandboxRequest(
            argv=tuple(raw_argv),
            workspace=str(self.paths.root),
            execution_id=context.attempt_id if context is not None else None,
            sensitive_count=sensitive_count,
            sensitive_sha256=sensitive_sha256,
            cwd=self.paths.relative(cwd),
            timeout_seconds=timeout_seconds,
            read_only_workspace=read_only_workspace,
        )
        try:
            backend_result = await self.backend.execute(request)
        except ToolError as exc:
            # A failed sandbox probe should not terminate a full-access turn.  The
            # model has an explicitly selected host-process capability in that
            # mode, so return the same structured hand-off used by the approval
            # modes and let it continue with ``discover_executables`` followed by
            # ``run_process``.  YOLO deliberately remains fail-closed: exposing a
            # host fallback here would bypass its sandbox-only process policy.
            if context is not None and context.autonomy in {
                Autonomy.ASK,
                Autonomy.WORKSPACE,
                Autonomy.FULL_ACCESS,
            }:
                return json_result(
                    {
                        "sandbox_unavailable": True,
                        "reason": str(exc),
                        "fallback_tool": "run_process",
                        "fallback_requires_approval": context.autonomy is not Autonomy.FULL_ACCESS,
                        "fallback": {
                            "kind": "direct",
                            "argv": list(request.argv),
                            "cwd": request.cwd,
                            "timeout_seconds": request.timeout_seconds,
                        },
                        "fallback_next_step": (
                            "Call discover_executables, then run_process with the discovered "
                            "executable and SHA-256 identity."
                        ),
                    }
                )
            raise
        artifacts: tuple[BinaryArtifact, ...] = ()
        if isinstance(backend_result, SandboxExecutionResult):
            captured_result = True
            result_document = backend_result.document
            artifacts = backend_result.artifacts
        else:
            captured_result = False
            try:
                result_document = json.loads(backend_result)
            except json.JSONDecodeError as exc:
                raise ToolError("sandbox backend returned invalid JSON") from exc
        if not isinstance(result_document, dict):
            raise ToolError("sandbox backend returned an invalid result")
        changes = result_document.get("changes")
        if context is not None and not read_only_workspace and isinstance(changes, dict):
            changeset_data = build_sandbox_changeset_data(
                context.attempt_id,
                str(self.paths.root),
                changes,
                {artifact.sha256: artifact for artifact in artifacts} if captured_result else None,
            )
            if changeset_data is not None:
                if artifacts:
                    if context.record_artifact is None:
                        raise ToolError("sandbox artifact persistence is unavailable")
                    for artifact in artifacts:
                        await context.record_artifact(artifact)
                await context.record_event(
                    Event(
                        session_id=context.session_id,
                        type="sandbox.changeset.created",
                        data=changeset_data,
                        causation_id=context.started_event_id,
                        correlation_id=context.correlation_id,
                    )
                )
                changes["changeset_id"] = changeset_data["changeset_id"]
                changes["durable"] = True
                changes["durable_change_count"] = sum(
                    change.get("apply_supported") is True
                    for change in changeset_data["changes"]
                    if isinstance(change, dict)
                )
                if changeset_data.get("format_version") == 2:
                    durable_by_path = {
                        change.get("path"): change
                        for change in changeset_data["changes"]
                        if isinstance(change, dict)
                    }
                    raw_changes = changes.get("changes")
                    if isinstance(raw_changes, list):
                        for change in raw_changes:
                            if not isinstance(change, dict):
                                continue
                            durable = durable_by_path.get(change.get("path"))
                            change.pop("after_text", None)
                            change.pop("patch", None)
                            if isinstance(durable, dict):
                                change["artifact_sha256"] = durable.get("artifact_sha256")
                                change["artifact_bytes"] = durable.get("artifact_bytes")
                                change["content_kind"] = durable.get("content_kind")
            else:
                changes["durable"] = False
        return json_result(result_document)


@dataclass(slots=True)
class _CapturedStream:
    retained: bytearray = field(default_factory=bytearray)
    total_bytes: int = 0
    digest: Any = field(default_factory=hashlib.sha256)
    overflow: threading.Event = field(default_factory=threading.Event)

    def append(self, chunk: bytes) -> None:
        self.total_bytes += len(chunk)
        self.digest.update(chunk)
        remaining = _MAX_RETAINED_STREAM_BYTES - len(self.retained)
        if remaining > 0:
            self.retained.extend(chunk[:remaining])
        if self.total_bytes > _MAX_OBSERVED_STREAM_BYTES:
            self.overflow.set()

    def document(self) -> dict[str, Any]:
        return {
            "text": bytes(self.retained).decode("utf-8", errors="replace"),
            "bytes": self.total_bytes,
            "sha256": self.digest.hexdigest(),
            "truncated": self.total_bytes > len(self.retained),
        }


def _sandbox_status(
    available: bool,
    reason: str,
    *,
    image: str | None = None,
    executable: Path | None = None,
    executable_sha256: str | None = None,
) -> SandboxStatus:
    normalized_reason = " ".join(reason.split())[:1000]
    lowered = normalized_reason.lower()
    actions: tuple[dict[str, str], ...]
    if available:
        diagnostic_layer = "ready"
        diagnostic_code = "ready"
        actions = ()
    elif "executable" in lowered or "docker cli" in lowered or "trusted docker" in lowered:
        diagnostic_layer = "executable"
        diagnostic_code = "executable_unavailable"
        actions = (
            {
                "id": "verify_docker_executable",
                "label": "Install or configure a trusted Docker CLI",
                "command": "docker version",
            },
        )
    # A missing image error includes the example ``image@sha256:digest`` in its
    # remediation text.  Check the availability wording first so that this
    # explanatory digest is not mistaken for an invalid configured digest.
    elif (
        "image is unavailable" in lowered
        or "image is not installed" in lowered
        or "image not installed" in lowered
        or "image unavailable" in lowered
    ):
        diagnostic_layer = "image"
        diagnostic_code = "image_unavailable"
        actions = (
            {
                "id": "build_sandbox_image",
                "label": "Build the local sandbox image",
                "command": (
                    "python scripts/build_sandbox_image.py --tag agent-workspace-sandbox:local"
                ),
            },
        )
    elif "digest" in lowered or "immutable" in lowered:
        diagnostic_layer = "digest"
        diagnostic_code = "image_digest_invalid"
        actions = (
            {
                "id": "pin_sandbox_image",
                "label": "Pin the sandbox image by SHA-256",
                "command": "set AGENT_WORKSPACE_SANDBOX_IMAGE=<image>@sha256:<digest>",
            },
        )
    elif "image" in lowered or "sandbox image" in lowered:
        diagnostic_layer = "image"
        diagnostic_code = "image_unavailable"
        actions = (
            {
                "id": "build_sandbox_image",
                "label": "Build the local sandbox image",
                "command": (
                    "python scripts/build_sandbox_image.py --tag agent-workspace-sandbox:local"
                ),
            },
        )
    elif "daemon" in lowered or "connect" in lowered or "docker" in lowered:
        diagnostic_layer = "daemon"
        diagnostic_code = "daemon_unavailable"
        actions = (
            {
                "id": "start_docker_desktop",
                "label": "Start Docker Desktop and retry",
                "command": "docker info",
            },
        )
    else:
        diagnostic_layer = "workspace"
        diagnostic_code = "probe_failed"
        actions = (
            {
                "id": "open_sandbox_docs",
                "label": "Open sandbox setup documentation",
                "command": "docs/SANDBOX.md",
            },
        )
    return SandboxStatus(
        backend="docker",
        available=available,
        reason=normalized_reason,
        image=image,
        executable=str(executable) if executable is not None else None,
        executable_sha256=executable_sha256,
        fallback="none" if available else "approval_gated_run_process",
        actions=actions,
        diagnostic_layer=diagnostic_layer,
        diagnostic_code=diagnostic_code,
        isolation=(
            "digest_pinned_image",
            "workspace_only_bind_mount",
            "staged_writes_no_direct_commit",
            "link_safe_mount_preflight",
            "read_only_root",
            "network_none",
            "non_root_user",
            "capabilities_dropped",
            "no_new_privileges",
            "pid_cpu_memory_limits",
            "bounded_output",
        ),
    )


def _validate_pinned_image(image: str) -> None:
    if image.startswith("sha256:"):
        if _IMAGE_DIGEST.fullmatch(image.removeprefix("sha256:")) is None:
            raise ValueError("sandbox image ID must contain a lowercase SHA-256 digest")
        return
    if (
        not image
        or len(image) > 512
        or "\x00" in image
        or any(character.isspace() for character in image)
        or "@sha256:" not in image
    ):
        raise ValueError("sandbox image must be a digest-pinned Docker reference")
    repository, digest = image.rsplit("@sha256:", maxsplit=1)
    if (
        _IMAGE_REPOSITORY.fullmatch(repository) is None
        or repository.startswith("-")
        or _IMAGE_DIGEST.fullmatch(digest) is None
    ):
        raise ValueError("sandbox image must end with a lowercase SHA-256 digest")


def _required_pinned_image(image: str | None) -> str:
    if image is None:
        raise ToolError(
            "sandbox image is unavailable; set AGENT_WORKSPACE_SANDBOX_IMAGE to an "
            "image@sha256:digest or build the local agent-workspace-sandbox:local image "
            "with scripts/build_sandbox_image.py. In ASK or WORKSPACE autonomy, use "
            "run_process with explicit approval instead; FULL ACCESS may use the host process "
            "without a routine prompt; YOLO remains fail-closed."
        )
    try:
        _validate_pinned_image(image)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    return image


def _discover_local_sandbox_image_sync(executable: str, expected_sha256: str) -> str:
    """Resolve the project-owned local tag to its immutable Docker image ID."""
    resolved = _resolve_executable(executable)
    if _required_executable_sha256(resolved) != expected_sha256:
        raise ToolError("Docker executable changed after sandbox configuration")
    try:
        version = _run_probe(
            [str(resolved), "version", "--format", "{{.Server.Version}}"],
            _safe_environment(),
        )
    except ToolError as exc:
        # Preserve the failing layer when the CLI cannot connect or times out;
        # otherwise the caller would report a generic probe failure and hide
        # that the daemon, rather than the image, is the missing dependency.
        raise ToolError(f"Docker daemon is unavailable: {exc}") from exc
    if version.returncode != 0:
        raise ToolError(_probe_reason("Docker daemon is unavailable", version))
    result = _run_probe(
        [str(resolved), "image", "inspect", "--format", "{{.Id}}", _LOCAL_SANDBOX_TAG],
        _safe_environment(),
    )
    if result.returncode != 0:
        return ""
    image_id = result.stdout.strip()
    if _IMAGE_DIGEST.fullmatch(image_id.removeprefix("sha256:")) is None:
        return ""
    return image_id


def _resolve_docker_executable(paths: WorkspacePaths, config: DockerSandboxConfig) -> Path:
    candidates: list[str] = []
    if config.docker_executable:
        candidates.append(config.docker_executable)
    else:
        program_files = os.environ.get("PROGRAMFILES")
        if program_files:
            candidates.append(
                str(Path(program_files) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe")
            )
        if os.name != "nt":
            discovered = shutil.which("docker")
            if discovered:
                candidates.append(discovered)
    errors: list[str] = []
    for candidate in dict.fromkeys(candidates):
        try:
            executable = _resolve_executable(candidate)
        except (ToolArgumentError, ToolError) as exc:
            errors.append(str(exc))
            continue
        try:
            executable.relative_to(paths.root)
        except ValueError:
            return executable
        errors.append("Docker executable may not be inside the workspace")
    detail = f": {errors[-1]}" if errors else ""
    raise ToolError(f"trusted Docker CLI is unavailable{detail}")


def _probe_docker_sync(executable: str, expected_sha256: str, image: str) -> str:
    resolved = _resolve_executable(executable)
    if _required_executable_sha256(resolved) != expected_sha256:
        raise ToolError("Docker executable changed after sandbox configuration")
    environment = _safe_environment()
    version = _run_probe(
        [str(resolved), "version", "--format", "{{.Server.Version}}"],
        environment,
    )
    if version.returncode != 0:
        return json_result(
            {
                "available": False,
                "reason": _probe_reason("Docker daemon is unavailable", version),
            }
        )
    inspected = _run_probe(
        [str(resolved), "image", "inspect", "--format", "{{.Id}}", image],
        environment,
    )
    if inspected.returncode != 0:
        return json_result(
            {
                "available": False,
                "reason": _probe_reason("pinned sandbox image is not installed", inspected),
            }
        )
    return json_result(
        {
            "available": True,
            "docker_version": version.stdout.strip()[:200],
            "image_id": inspected.stdout.strip()[:200],
        }
    )


def _run_probe(
    arguments: list[str],
    environment: dict[str, str],
    *,
    timeout_seconds: int = _PROBE_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    creation_flags = (
        subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )
    try:
        return subprocess.run(
            arguments,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            creationflags=creation_flags,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolError(f"Docker sandbox probe failed: {type(exc).__name__}") from exc


def _probe_reason(prefix: str, result: subprocess.CompletedProcess[str]) -> str:
    detail = " ".join((result.stderr or result.stdout).split())[:500]
    return f"{prefix} (exit_code={result.returncode})" + (f": {detail}" if detail else "")


def _identity_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _workspace_label(workspace: Path) -> str:
    return _identity_digest(os.path.normcase(str(workspace.resolve(strict=True))))


def _container_name(execution_id: str, nonce: str) -> str:
    return f"agent-workspace-{_identity_digest(execution_id)[:16]}-{_identity_digest(nonce)[:16]}"


def _recover_stale_containers_sync(
    executable: str,
    expected_executable_sha256: str,
    workspace_label: str,
) -> str:
    resolved = _resolve_executable(executable)
    if _required_executable_sha256(resolved) != expected_executable_sha256:
        raise ToolError("Docker executable changed before sandbox recovery")
    environment = _safe_environment()
    listed = _list_managed_containers(resolved, workspace_label, environment)
    if listed.returncode != 0:
        raise ToolError(_probe_reason("cannot list stale sandbox containers", listed))
    inventory = _parse_managed_container_inventory(listed.stdout)
    stale_ids = tuple(
        container_id for container_id, owner_pid in inventory if not _process_is_alive(owner_pid)
    )
    active_count = len(inventory) - len(stale_ids)
    if stale_ids:
        removed = _run_probe(
            [str(resolved), "rm", "--force", "--volumes", *stale_ids],
            environment,
            timeout_seconds=_CLEANUP_TIMEOUT_SECONDS,
        )
        if removed.returncode != 0:
            raise ToolError(_probe_reason("cannot remove stale sandbox containers", removed))
    verified = _list_managed_containers(resolved, workspace_label, environment)
    if verified.returncode != 0:
        raise ToolError(_probe_reason("cannot verify sandbox recovery", verified))
    remaining = _parse_managed_container_inventory(verified.stdout)
    if any(not _process_is_alive(owner_pid) for _, owner_pid in remaining):
        raise ToolError("sandbox recovery left stale managed containers behind")
    return json_result(
        {
            "recovered": len(stale_ids),
            "active": active_count,
            "workspace_sha256": workspace_label,
        }
    )


def _parse_managed_container_inventory(raw: str) -> tuple[tuple[str, int], ...]:
    lines = tuple(line.strip() for line in raw.splitlines() if line.strip())
    if len(lines) > _MAX_STALE_CONTAINERS:
        raise ToolError("Docker returned too many managed sandbox containers")
    result: list[tuple[str, int]] = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) != 2 or _CONTAINER_ID.fullmatch(parts[0]) is None:
            raise ToolError("Docker returned an invalid managed-container inventory")
        try:
            owner_pid = int(parts[1])
        except ValueError as exc:
            raise ToolError("Docker returned an invalid sandbox owner PID") from exc
        if owner_pid <= 0:
            raise ToolError("Docker returned an invalid sandbox owner PID")
        result.append((parts[0], owner_pid))
    return tuple(result)


def _process_is_alive(process_id: int) -> bool:
    if process_id == os.getpid():
        return True
    if os.name != "nt":
        try:
            os.kill(process_id, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    kernel32: Any = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    kernel32.GetExitCodeProcess.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.OpenProcess(0x1000, False, process_id)
    if not handle:
        return ctypes.get_last_error() != 87
    try:
        exit_code = ctypes.c_uint32()
        return (
            bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)))
            and exit_code.value == 259
        )
    finally:
        kernel32.CloseHandle(handle)


def _list_managed_containers(
    executable: Path,
    workspace_label: str,
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return _run_probe(
        [
            str(executable),
            "container",
            "ls",
            "--all",
            "--no-trunc",
            "--filter",
            "label=agent-workspace.managed=true",
            "--filter",
            f"label=agent-workspace.workspace={workspace_label}",
            "--format",
            '{{.ID}}\t{{.Label "agent-workspace.owner-pid"}}',
        ],
        environment,
    )


def _docker_arguments(
    *,
    executable: str,
    image: str,
    workspace: Path,
    cwd: str,
    argv: list[str],
    container_name: str,
    read_only_workspace: bool,
    memory_bytes: int,
    cpu_count: float,
    process_limit: int,
    temporary_bytes: int,
    user: str,
    workspace_label: str | None = None,
    attempt_label: str | None = None,
    owner_pid: int | None = None,
) -> list[str]:
    workspace_text = str(workspace)
    if "," in workspace_text:
        raise ToolError("Docker sandbox workspace path may not contain a comma")
    mount = (
        f"type=bind,source={workspace_text},target=/workspace,"
        "bind-propagation=rprivate,bind-recursive=disabled"
    )
    if read_only_workspace:
        mount += ",readonly"
    container_cwd = "/workspace"
    if cwd not in {"", "."}:
        container_cwd += f"/{Path(cwd).as_posix()}"
    labels = ["--label", "agent-workspace.managed=true"]
    if workspace_label is not None:
        labels.extend(("--label", f"agent-workspace.workspace={workspace_label}"))
    if attempt_label is not None:
        labels.extend(("--label", f"agent-workspace.attempt={attempt_label}"))
    if owner_pid is not None:
        labels.extend(("--label", f"agent-workspace.owner-pid={owner_pid}"))
    return [
        executable,
        "run",
        "--rm",
        "--init",
        "--pull",
        "never",
        "--name",
        container_name,
        "--hostname",
        "agent-sandbox",
        "--label",
        "agent-workspace.sandbox-version=1",
        *labels,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--pids-limit",
        str(process_limit),
        "--memory",
        str(memory_bytes),
        "--memory-swap",
        str(memory_bytes),
        "--cpus",
        str(cpu_count),
        "--ulimit",
        "nofile=1024:1024",
        "--ulimit",
        f"nproc={process_limit}:{process_limit}",
        "--ipc",
        "private",
        "--user",
        user,
        "--workdir",
        container_cwd,
        "--mount",
        mount,
        "--tmpfs",
        f"/tmp:rw,noexec,nosuid,nodev,size={temporary_bytes}",
        "--env",
        "CI=1",
        "--env",
        "HOME=/tmp",
        "--env",
        "NO_COLOR=1",
        "--env",
        "PAGER=cat",
        "--entrypoint",
        argv[0],
        image,
        *argv[1:],
    ]


def _validate_workspace_mount(root: Path) -> tuple[int, str]:
    """Reject host filesystem objects whose identity or target is not workspace-local."""
    entries = 0
    sensitive_count = 0
    sensitive_digest = hashlib.sha256()
    hard_links: dict[tuple[int, int], tuple[int, list[Path]]] = {}
    root_device = root.stat().st_dev

    def reject_walk_error(error: OSError) -> None:
        raise ToolError(f"cannot inspect workspace before sandbox mount: {error}") from error

    try:
        for directory, directory_names, file_names in os.walk(
            root,
            topdown=True,
            followlinks=False,
            onerror=reject_walk_error,
        ):
            directory_names.sort()
            file_names.sort()
            names = (*directory_names, *file_names)
            entries += len(names)
            if entries > _MAX_MOUNT_ENTRIES:
                raise ToolError("workspace is too large to verify for sandbox mounting")
            for name in names:
                path = Path(directory) / name
                metadata = path.lstat()
                if metadata.st_dev != root_device or path.is_mount():
                    raise ToolError(f"workspace contains a nested filesystem mount: {path}")
                attributes = getattr(metadata, "st_file_attributes", 0)
                if stat.S_ISLNK(metadata.st_mode) or attributes & 0x400:
                    raise ToolError(f"workspace contains a link or reparse point: {path}")
                if stat.S_ISREG(metadata.st_mode):
                    if metadata.st_nlink > 1:
                        identity = (metadata.st_dev, metadata.st_ino)
                        expected, observed = hard_links.setdefault(
                            identity,
                            (metadata.st_nlink, []),
                        )
                        if expected != metadata.st_nlink:
                            raise ToolError(f"hard-link identity changed during mount scan: {path}")
                        observed.append(path)
                elif not stat.S_ISDIR(metadata.st_mode):
                    raise ToolError(f"workspace contains a special file: {path}")
                relative = path.relative_to(root).as_posix()
                if is_sensitive_workspace_path(relative):
                    encoded = relative.encode("utf-8")
                    sensitive_digest.update(len(encoded).to_bytes(8, "big"))
                    sensitive_digest.update(encoded)
                    sensitive_count += 1
    except OSError as exc:
        raise ToolError(f"cannot inspect workspace before sandbox mount: {exc}") from exc
    for expected, observed in hard_links.values():
        if len(observed) != expected:
            raise ToolError(f"workspace file has a hard link outside the mount: {observed[0]}")
    return sensitive_count, sensitive_digest.hexdigest()


def _run_docker_sandbox_sync(
    workspace: str,
    mount_workspace: str,
    executable: str,
    expected_executable_sha256: str,
    image: str,
    argv: list[str],
    expected_sensitive_count: int,
    expected_sensitive_sha256: str,
    raw_cwd: str,
    timeout_seconds: int,
    read_only_workspace: bool,
    memory_bytes: int,
    cpu_count: float,
    process_limit: int,
    temporary_bytes: int,
    max_workspace_growth_bytes: int,
    minimum_free_space_bytes: int,
    user: str,
    container_name: str,
    workspace_label: str,
    execution_id: str,
) -> str:
    paths = WorkspacePaths(workspace)
    cwd = paths.resolve(raw_cwd)
    if not cwd.is_dir():
        raise ToolError(f"sandbox working directory is not a directory: {cwd}")
    observed_sensitive_count, observed_sensitive_sha256 = _validate_workspace_mount(paths.root)
    if (
        observed_sensitive_count != expected_sensitive_count
        or observed_sensitive_sha256 != expected_sensitive_sha256
    ):
        raise ToolError("workspace sensitive paths changed after sandbox approval")
    mount_root = Path(mount_workspace).resolve(strict=True)
    if not mount_root.is_dir():
        raise ToolError("sandbox mount workspace is not a directory")
    if read_only_workspace and mount_root != paths.root:
        raise ToolError("read-only sandbox mount does not match the workspace")
    if not read_only_workspace:
        from .sandbox_staging import _validate_existing_staging_root

        _validate_existing_staging_root(mount_root.parent, execution_id)
        set_staging_owner_sync(str(mount_root.parent), execution_id, os.getpid())
    resolved_executable = _resolve_executable(executable)
    if _required_executable_sha256(resolved_executable) != expected_executable_sha256:
        raise ToolError("Docker executable changed after sandbox status check")
    pinned_image = _required_pinned_image(image)
    initial_free_space = shutil.disk_usage(mount_root).free
    if not read_only_workspace and initial_free_space < minimum_free_space_bytes:
        raise ToolError("workspace volume has insufficient free space for sandbox execution")
    arguments = _docker_arguments(
        executable=str(resolved_executable),
        image=pinned_image,
        workspace=mount_root,
        cwd=paths.relative(cwd),
        argv=argv,
        container_name=container_name,
        read_only_workspace=read_only_workspace,
        memory_bytes=memory_bytes,
        cpu_count=cpu_count,
        process_limit=process_limit,
        temporary_bytes=temporary_bytes,
        user=user,
        workspace_label=workspace_label,
        attempt_label=_identity_digest(execution_id),
        owner_pid=os.getpid(),
    )
    creation_flags = (
        subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )
    started = time.monotonic()
    environment = _safe_environment()
    try:
        process = subprocess.Popen(
            arguments,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            creationflags=creation_flags,
        )
    except OSError as exc:
        raise ToolError("cannot start Docker sandbox") from exc
    assert process.stdout is not None
    assert process.stderr is not None
    stdout = _CapturedStream()
    stderr = _CapturedStream()
    readers = (
        threading.Thread(target=_drain_stream, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=_drain_stream, args=(process.stderr, stderr), daemon=True),
    )
    for reader in readers:
        reader.start()
    timed_out = False
    output_limit_exceeded = False
    storage_limit_exceeded = False
    next_storage_check = started
    try:
        deadline = started + timeout_seconds
        while process.poll() is None:
            if stdout.overflow.is_set() or stderr.overflow.is_set():
                output_limit_exceeded = True
                break
            if time.monotonic() >= deadline:
                timed_out = True
                break
            if not read_only_workspace and time.monotonic() >= next_storage_check:
                current_free_space = shutil.disk_usage(mount_root).free
                storage_limit_exceeded = (
                    current_free_space < minimum_free_space_bytes
                    or initial_free_space - current_free_space > max_workspace_growth_bytes
                )
                if storage_limit_exceeded:
                    break
                next_storage_check = time.monotonic() + 0.1
            time.sleep(0.01)
        if timed_out or output_limit_exceeded or storage_limit_exceeded:
            _remove_container(resolved_executable, container_name, environment)
            if process.poll() is None:
                process.kill()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=2)
    finally:
        for reader in readers:
            reader.join(timeout=1)
        process.stdout.close()
        process.stderr.close()
        for reader in readers:
            reader.join(timeout=0.2)
        if process.poll() is None:
            process.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=2)
            _remove_container(resolved_executable, container_name, environment)
    return json_result(
        {
            "backend": "docker",
            "execution_sha256": _identity_digest(execution_id),
            "image": pinned_image,
            "network": "none",
            "workspace_mode": "read-only" if read_only_workspace else "staged",
            "argv_count": len(argv),
            "argv_sha256": hashlib.sha256(
                json.dumps(argv, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "cwd": paths.relative(cwd),
            "exit_code": process.returncode,
            "timed_out": timed_out,
            "output_limit_exceeded": output_limit_exceeded,
            "storage_limit_exceeded": storage_limit_exceeded,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "stdout": stdout.document(),
            "stderr": stderr.document(),
        }
    )


def _drain_stream(stream: Any, output: _CapturedStream) -> None:
    try:
        while chunk := stream.read(_READ_CHUNK_BYTES):
            output.append(chunk)
    except (OSError, ValueError):
        return


def _remove_container(
    executable: Path,
    container_name: str,
    environment: dict[str, str],
) -> bool:
    creation_flags = (
        subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )
    try:
        subprocess.run(
            [str(executable), "rm", "--force", "--volumes", container_name],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            shell=False,
            creationflags=creation_flags,
            timeout=_CLEANUP_TIMEOUT_SECONDS,
            check=False,
        )
        inspected = subprocess.run(
            [
                str(executable),
                "container",
                "ls",
                "--all",
                "--filter",
                f"name=^/{container_name}$",
                "--format",
                "{{.ID}}",
            ],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            shell=False,
            creationflags=creation_flags,
            timeout=_CLEANUP_TIMEOUT_SECONDS,
            check=False,
        )
        return inspected.returncode == 0 and not (inspected.stdout or b"").strip()
    except (OSError, subprocess.TimeoutExpired):
        return False


def _remove_container_sync(
    executable: str,
    expected_executable_sha256: str,
    container_name: str,
) -> str:
    resolved = _resolve_executable(executable)
    if _required_executable_sha256(resolved) != expected_executable_sha256:
        raise ToolError("Docker executable changed before sandbox cleanup")
    if not _remove_container(resolved, container_name, _safe_environment()):
        raise ToolError("sandbox container cleanup could not be verified")
    return json_result({"container": container_name, "removed": True})
