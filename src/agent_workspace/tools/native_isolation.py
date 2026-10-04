"""Small, side-effect-free probes for native process isolation.

The host-staged backend can bound a process tree with a Windows Job Object,
but that object does not create filesystem or network boundaries.  This module
keeps that distinction explicit so callers cannot present host execution as a
security sandbox.
"""

from __future__ import annotations

import os
import platform as platform_module
from dataclasses import dataclass
from typing import Literal

ProcessBoundary = Literal["job_object", "host_process", "unavailable"]


@dataclass(frozen=True, slots=True)
class NativeIsolationReport:
    platform: str
    process_boundary: ProcessBoundary
    os_filesystem_boundary: bool
    network_boundary: bool
    can_run_untrusted_code: bool
    remediation: tuple[str, ...]
    verification_evidence: tuple[str, ...] = ()
    verified_isolation: bool = False
    repair_action: str = ""

    @property
    def capability(self) -> str:
        if self.verified_isolation and self.can_run_untrusted_code:
            return "isolated"
        if self.process_boundary == "unavailable":
            return "unavailable"
        return "restricted_host"

    @property
    def risk_boundary(self) -> tuple[str, ...]:
        risks: list[str] = []
        if not self.os_filesystem_boundary:
            risks.append("host_filesystem_visible")
        if not self.network_boundary:
            risks.append("network_not_isolated")
        if self.process_boundary == "job_object":
            risks.append("job_object_limits_only")
        elif self.process_boundary == "host_process":
            risks.append("host_process")
        else:
            risks.append("process_boundary_unavailable")
        return tuple(risks)

    def to_document(self) -> dict[str, object]:
        return {
            "platform": self.platform,
            "process_boundary": self.process_boundary,
            "os_filesystem_boundary": self.os_filesystem_boundary,
            "network_boundary": self.network_boundary,
            "can_run_untrusted_code": self.can_run_untrusted_code,
            "capability": self.capability,
            "risk_boundary": list(self.risk_boundary),
            "remediation": list(self.remediation),
            "verification_evidence": list(self.verification_evidence),
            "verified_isolation": self.verified_isolation,
            "repair_action": self.repair_action,
        }


def _probe_job_object() -> None:
    """Create and close a configured Job Object as a capability probe."""

    if os.name != "nt":
        raise OSError("Windows Job Object is unavailable on this platform")
    # Import lazily so importing this module never loads Windows-only ctypes
    # bindings on non-Windows hosts.
    from .process_worker import _WindowsJob

    job = _WindowsJob(allow_children=True)
    job.close()


def inspect_native_isolation() -> NativeIsolationReport:
    """Describe the native execution boundary available to this process.

    A Job Object bounds process lifetime, CPU time, memory, and child count.
    It does not prevent access to host files or the host network, so the
    resulting capability is deliberately reported as restricted host access.
    """

    system = platform_module.system() or os.name
    try:
        _probe_job_object()
    except Exception as exc:
        detail = " ".join(str(exc).split())[:240] or type(exc).__name__
        return NativeIsolationReport(
            platform=system,
            process_boundary="host_process",
            os_filesystem_boundary=False,
            network_boundary=False,
            can_run_untrusted_code=False,
            remediation=(
                f"Windows Job Object is unavailable ({detail}); execution remains a host process.",
                "Use a container, VM, or AppContainer before running untrusted code.",
            ),
            verification_evidence=("Windows Job Object probe failed",),
            repair_action="Install or enable an isolated container, VM, or AppContainer backend.",
        )

    return NativeIsolationReport(
        platform=system,
        process_boundary="job_object",
        os_filesystem_boundary=False,
        network_boundary=False,
        can_run_untrusted_code=False,
        remediation=(
            "Windows Job Object limits child process trees, CPU time, memory, and lifetime; "
            "it does not isolate filesystem or network.",
            "Use an isolated backend before running untrusted code.",
        ),
        verification_evidence=(
            "Windows Job Object probe succeeded",
            "Filesystem boundary probe: unavailable",
            "Network boundary probe: unavailable",
        ),
        repair_action="Configure an isolated container, VM, or AppContainer backend.",
    )
