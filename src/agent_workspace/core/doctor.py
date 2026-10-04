"""System Environment Doctor & Diagnostic Probes (GAP-01).

Inspects Python runtime, dependency integrity, Git binary & work tree, SQLite
database accessibility, and provider readiness, returning a structured
diagnostic report with status, details, and actionable remediation steps.
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class DoctorCheckResult:
    id: str
    category: str
    name: str
    status: str  # "ok" | "warn" | "error"
    message: str
    detail: str = ""
    remediation: str = ""
    diagnostic_layer: str = ""
    diagnostic_code: str = ""
    capability: str = ""
    risk_boundary: tuple[str, ...] = ()
    repair_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DoctorReport:
    timestamp: str
    overall_status: str  # "ok" | "warn" | "error"
    checks: list[DoctorCheckResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overallStatus": self.overall_status,
            "checks": [c.to_dict() for c in self.checks],
        }


def check_python_runtime() -> DoctorCheckResult:
    version = sys.version_info
    v_str = f"{version.major}.{version.minor}.{version.micro}"
    if version < (3, 12):
        return DoctorCheckResult(
            id="python_runtime",
            category="runtime",
            name="Python Runtime Version",
            status="error",
            message=f"Python {v_str} is below required 3.12+",
            detail=f"Interpreter executable: {sys.executable}",
            remediation="Install Python 3.12 or newer and update your environment.",
        )
    return DoctorCheckResult(
        id="python_runtime",
        category="runtime",
        name="Python Runtime Version",
        status="ok",
        message=f"Python {v_str} meets version requirement (3.12+)",
        detail=f"Executable: {sys.executable}",
    )


def check_dependencies() -> DoctorCheckResult:
    required = ["sqlite3", "httpx", "cryptography", "jsonschema", "agent_workspace"]
    missing: list[str] = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        return DoctorCheckResult(
            id="core_dependencies",
            category="runtime",
            name="Core Package Dependencies",
            status="error",
            message=f"Missing required packages: {', '.join(missing)}",
            detail=f"Checked packages: {', '.join(required)}",
            remediation="Run 'uv sync --frozen' to install all required dependencies.",
        )
    return DoctorCheckResult(
        id="core_dependencies",
        category="runtime",
        name="Core Package Dependencies",
        status="ok",
        message="All core package dependencies are importable",
        detail=f"Verified: {', '.join(required)}",
    )


def check_git_environment(workspace: Path | None = None) -> DoctorCheckResult:
    git_bin = shutil.which("git")
    if not git_bin:
        return DoctorCheckResult(
            id="git_environment",
            category="vcs",
            name="Git Version Control",
            status="warn",
            message="Git command-line tool not found on PATH",
            detail="Version control and diff inspection features will be disabled.",
            remediation="Install Git from https://git-scm.com/ and ensure it is on PATH.",
        )

    try:
        proc = subprocess.run(
            [git_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0:
            raise OSError("Git version probe failed")
        git_ver = proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheckResult(
            id="git_environment",
            category="vcs",
            name="Git Version Control",
            status="error",
            message="Git could not be executed",
            detail=str(exc),
            remediation="Check Git installation and executable permissions.",
        )

    if workspace is not None and workspace.is_dir():
        try:
            repo_proc = subprocess.run(
                [git_bin, "rev-parse", "--is-inside-work-tree"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            is_repo = repo_proc.returncode == 0 and repo_proc.stdout.strip() == "true"
        except Exception:
            is_repo = False

        if not is_repo:
            return DoctorCheckResult(
                id="git_environment",
                category="vcs",
                name="Git Working Tree",
                status="warn",
                message="Current workspace is not a Git repository",
                detail=f"{git_ver}; workspace: {workspace}",
                remediation=(
                    "Run 'git init' inside the workspace to enable diff review and delivery."
                ),
            )

    return DoctorCheckResult(
        id="git_environment",
        category="vcs",
        name="Git Version Control",
        status="ok",
        message="Git environment is ready",
        detail=f"{git_ver} at {git_bin}",
    )


def check_database_health(db_path: Path | None = None) -> DoctorCheckResult:
    if db_path is None or not db_path.is_file():
        return DoctorCheckResult(
            id="database_health",
            category="storage",
            name="SQLite Database Health",
            status="warn",
            message="Database path not yet configured",
            remediation="Open or initialize a workspace to establish storage.",
        )

    try:
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=rw", uri=True, timeout=2.0)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA schema_version")
            schema_ver = cursor.fetchone()[0]
            if cursor.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise sqlite3.DatabaseError("Database integrity check failed")
            cursor.execute("BEGIN IMMEDIATE")
            conn.rollback()
        finally:
            conn.close()

        return DoctorCheckResult(
            id="database_health",
            category="storage",
            name="SQLite Database Health",
            status="ok",
            message="Database file is accessible and writable",
            detail=f"Schema version: {schema_ver}; path: {db_path}",
        )
    except Exception as exc:
        return DoctorCheckResult(
            id="database_health",
            category="storage",
            name="SQLite Database Health",
            status="error",
            message=f"Database check failed: {exc}",
            detail=f"Target path: {db_path}",
            remediation="Check file system permissions and disk space.",
        )


def check_provider_readiness(config: Any = None) -> DoctorCheckResult:
    if config is None or not getattr(config, "id", None):
        return DoctorCheckResult(
            id="provider_readiness",
            category="provider",
            name="LLM Provider Configuration",
            status="warn",
            message="No LLM provider is currently configured",
            detail="Agent cannot execute turns without an active model provider.",
            remediation="Open Settings to configure an API key and model.",
        )

    provider_id = getattr(config, "id", "unknown")
    model = getattr(config, "model", "")
    api_key = getattr(config, "api_key", None)
    has_key = bool(api_key and str(api_key).strip())
    try:
        host = urlparse(str(getattr(config, "base_url", ""))).hostname or ""
        local = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = False
    status = "ok" if has_key or local else "warn"
    msg = f"Configured for {provider_id} ({model})"
    if not has_key and not local:
        msg += " - API key is missing or empty"

    return DoctorCheckResult(
        id="provider_readiness",
        category="provider",
        name="LLM Provider Configuration",
        status=status,
        message=msg,
        detail=f"Provider: {provider_id}, Model: {model}",
        remediation="Update your API key in Settings if calls fail."
        if not has_key and not local
        else "",
    )


def _isolation_field(report: object, name: str, default: Any) -> Any:
    if isinstance(report, Mapping):
        return report.get(name, default)
    return getattr(report, name, default)


def check_sandbox_environment(
    workspace: Path | None = None,
    *,
    isolation_probe: Callable[[], object] | None = None,
) -> DoctorCheckResult:
    """Report the local staged backend without importing the tools layer.

    The core doctor owns the stable diagnostic shape.  A caller at the
    application boundary may inject the platform-specific isolation probe;
    when it does not, the conservative host-process boundary is reported.
    """

    # ``workspace`` is retained for API compatibility and future workspace
    # specific checks.  The executable probe is independent of that path.
    del workspace
    try:
        executable = Path(sys.executable).resolve(strict=True)
        if not executable.is_file():
            raise OSError("Python executable is not a file")
        digest = hashlib.sha256()
        with executable.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        executable_sha256 = digest.hexdigest()
    except Exception as exc:
        return DoctorCheckResult(
            id="sandbox_environment",
            category="sandbox",
            name="Local Staged Execution Sandbox",
            status="error",
            message="Local staged sandbox is unavailable",
            detail=" ".join(str(exc).split())[:1000] or type(exc).__name__,
            remediation=(
                "Check the bundled Python runtime and workspace permissions, then run "
                "the environment doctor again."
            ),
            diagnostic_layer="runtime",
            diagnostic_code="probe_failed",
        )

    isolation: object | None
    if isolation_probe is None:
        isolation = {
            "capability": "restricted_host",
            "process_boundary": "host_process",
            "risk_boundary": (
                "host_filesystem_visible",
                "network_not_isolated",
                "host_process",
            ),
            "remediation": (
                "Local staged execution bounds the workspace staging flow but does not isolate "
                "the host filesystem or network.",
                "Use an isolated backend before running untrusted code.",
            ),
        }
        isolation_error = ""
    else:
        try:
            isolation = isolation_probe()
        except Exception as exc:
            isolation = None
            isolation_error = " ".join(str(exc).split())[:240] or type(exc).__name__
        else:
            isolation_error = ""

    capability: str
    risk_boundary: tuple[str, ...]
    detail_boundary: str
    remediation: str
    diagnostic_layer: str
    diagnostic_code: str
    repair_action: str
    if isolation is None:
        capability = "unavailable"
        risk_boundary = ("native_isolation_probe_failed",)
        detail_boundary = (
            "Native isolation probe failed; host filesystem and network boundaries are unknown. "
            f"Probe error: {isolation_error}."
        )
        remediation = (
            "Keep untrusted execution disabled until native isolation diagnostics recover."
        )
        diagnostic_layer = "sandbox"
        diagnostic_code = "sandbox.native_isolation_probe_failed"
        repair_action = (
            "Retry the native isolation probe; configure an isolated container, VM, or "
            "AppContainer backend before enabling untrusted execution."
        )
    else:
        capability = str(_isolation_field(isolation, "capability", "restricted_host"))
        raw_risk_boundary = _isolation_field(isolation, "risk_boundary", ())
        risk_boundary = (
            tuple(item for item in raw_risk_boundary if isinstance(item, str))
            if isinstance(raw_risk_boundary, (tuple, list))
            else ()
        )
        detail_boundary = (
            "Host filesystem is visible; network is not isolated; "
            "process lifetime and resource limits are enforced. "
            f"Process boundary: {_isolation_field(isolation, 'process_boundary', 'host_process')}."
        )
        raw_remediation = _isolation_field(isolation, "remediation", ())
        remediation = (
            " ".join(item for item in raw_remediation if isinstance(item, str))
            if isinstance(raw_remediation, (tuple, list))
            else str(raw_remediation)
        )
        diagnostic_layer = "ready"
        diagnostic_code = "ready"
        repair_action = str(_isolation_field(isolation, "repair_action", ""))

    return DoctorCheckResult(
        id="sandbox_environment",
        category="sandbox",
        name="Local Staged Execution Sandbox",
        status="ok" if isolation is not None else "warn",
        message=(
            "Project-local staged sandbox is ready"
            if isolation is not None
            else "Local staged sandbox diagnostics are incomplete"
        ),
        detail=(
            "Backend: host-staged; workspace: staged-copy; "
            f"{detail_boundary} "
            "Bounded output is enforced; "
            f"runtime: {executable}; sha256: {executable_sha256}."
        ),
        remediation=remediation,
        diagnostic_layer=diagnostic_layer,
        diagnostic_code=diagnostic_code,
        capability=capability,
        risk_boundary=risk_boundary,
        repair_action=repair_action,
    )


def check_workspace_permissions(workspace: Path | None = None) -> DoctorCheckResult:
    if workspace is None:
        return DoctorCheckResult(
            id="workspace_permissions",
            category="workspace",
            name="Workspace Permissions",
            status="warn",
            message="Workspace is not configured",
            detail="Read/write permission checks will run after a workspace is opened.",
            remediation="Open a workspace and run the environment doctor again.",
            diagnostic_layer="workspace",
            diagnostic_code="workspace_unconfigured",
        )
    try:
        resolved = workspace.expanduser().resolve()
    except OSError as exc:
        return DoctorCheckResult(
            id="workspace_permissions",
            category="workspace",
            name="Workspace Permissions",
            status="error",
            message="Workspace path could not be resolved",
            detail=str(exc),
            remediation="Choose a workspace path that exists and is accessible.",
            diagnostic_layer="workspace",
            diagnostic_code="workspace_unresolved",
        )
    if not resolved.is_dir():
        return DoctorCheckResult(
            id="workspace_permissions",
            category="workspace",
            name="Workspace Permissions",
            status="error",
            message="Workspace directory is missing",
            detail=f"Workspace: {resolved}",
            remediation=(
                "Choose an existing directory or create the workspace before running tasks."
            ),
            diagnostic_layer="workspace",
            diagnostic_code="workspace_missing",
        )
    readable = os.access(resolved, os.R_OK)
    writable = os.access(resolved, os.W_OK)
    if not readable or not writable:
        missing = ", ".join(
            permission
            for permission, available in (("read", readable), ("write", writable))
            if not available
        )
        return DoctorCheckResult(
            id="workspace_permissions",
            category="workspace",
            name="Workspace Permissions",
            status="error",
            message=f"Workspace lacks {missing} permission",
            detail=f"Workspace: {resolved}",
            remediation="Grant the sidecar account read/write access to the workspace directory.",
            diagnostic_layer="workspace",
            diagnostic_code="workspace_permission_denied",
        )
    return DoctorCheckResult(
        id="workspace_permissions",
        category="workspace",
        name="Workspace Permissions",
        status="ok",
        message="Workspace is readable and writable",
        detail=f"Workspace: {resolved}",
        diagnostic_layer="workspace",
        diagnostic_code="ready",
    )


def check_sidecar_packaging() -> DoctorCheckResult:
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        mode_str = "Frozen Packaged Sidecar (Production)"
    else:
        mode_str = "Python Source Sidecar (Development)"

    return DoctorCheckResult(
        id="sidecar_packaging",
        category="runtime",
        name="Sidecar Packaging Mode",
        status="ok",
        message=mode_str,
        detail=f"sys.frozen: {is_frozen}",
    )


def diagnose_environment(
    workspace: Path | None = None,
    db_path: Path | None = None,
    provider_config: Any = None,
    isolation_probe: Callable[[], object] | None = None,
) -> DoctorReport:
    checks = [
        check_python_runtime(),
        check_dependencies(),
        check_git_environment(workspace),
        check_database_health(db_path),
        check_workspace_permissions(workspace),
        check_provider_readiness(provider_config),
        check_sandbox_environment(workspace, isolation_probe=isolation_probe),
        check_sidecar_packaging(),
    ]

    has_error = any(c.status == "error" for c in checks)
    has_warn = any(c.status == "warn" for c in checks)
    overall = "error" if has_error else ("warn" if has_warn else "ok")

    return DoctorReport(
        timestamp=datetime.now(UTC).isoformat(),
        overall_status=overall,
        checks=checks,
    )
