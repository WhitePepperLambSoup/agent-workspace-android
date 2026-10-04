"""Process resource limits reporting.

The report is deliberately dependency-free. POSIX platforms expose the
``resource.getrlimit`` soft/hard pairs plus current RSS/CPU accounting.
Windows has no ``resource`` module, so current memory and CPU accounting are
read through small ctypes bindings and the limit table is empty.
"""

from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProcessResourceReport:
    platform: str
    pid: int
    rss_bytes: int | None
    peak_rss_bytes: int | None
    cpu_user_seconds: float | None
    cpu_system_seconds: float | None
    limits: tuple[tuple[str, int | None, int | None], ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "pid": self.pid,
            "rss_bytes": self.rss_bytes,
            "peak_rss_bytes": self.peak_rss_bytes,
            "cpu_user_seconds": self.cpu_user_seconds,
            "cpu_system_seconds": self.cpu_system_seconds,
            "limits": [
                {"name": name, "soft": soft, "hard": hard} for name, soft, hard in self.limits
            ],
        }


class _Filetime(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _windows_usage() -> tuple[int | None, int | None, float | None, float | None]:
    """Read memory and CPU accounting for the current Windows process."""
    try:
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except OSError:
        return None, None, None, None

    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(_ProcessMemoryCounters)
    process = ctypes.c_void_p(kernel32.GetCurrentProcess())
    if not psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
        rss: int | None = None
        peak_rss: int | None = None
    else:
        rss = int(counters.WorkingSetSize)
        peak_rss = int(counters.PeakWorkingSetSize)

    created = _Filetime()
    exited = _Filetime()
    kernel = _Filetime()
    user = _Filetime()
    if not kernel32.GetProcessTimes(
        process,
        ctypes.byref(created),
        ctypes.byref(exited),
        ctypes.byref(kernel),
        ctypes.byref(user),
    ):
        return rss, peak_rss, None, None

    def to_seconds(value: _Filetime) -> float:
        units = (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)
        return units / 10_000_000.0

    return rss, peak_rss, to_seconds(user), to_seconds(kernel)


def _posix_limits() -> tuple[tuple[str, int | None, int | None], ...]:
    try:
        import resource
    except ImportError:
        return ()
    infinity = getattr(resource, "RLIM_INFINITY", -1)
    names = (
        ("address_space", "RLIMIT_AS"),
        ("data_segment", "RLIMIT_DATA"),
        ("cpu_seconds", "RLIMIT_CPU"),
        ("file_size", "RLIMIT_FSIZE"),
        ("open_files", "RLIMIT_NOFILE"),
        ("processes", "RLIMIT_NPROC"),
        ("resident_set", "RLIMIT_RSS"),
        ("stack", "RLIMIT_STACK"),
    )
    limits: list[tuple[str, int | None, int | None]] = []
    for name, attribute in names:
        constant = getattr(resource, attribute, None)
        if constant is None:
            limits.append((name, None, None))
            continue
        try:
            soft, hard = resource.getrlimit(constant)  # type: ignore[attr-defined]
        except (OSError, ValueError):
            limits.append((name, None, None))
            continue
        soft_value: int | None = None if soft == infinity else soft
        hard_value: int | None = None if hard == infinity else hard
        limits.append((name, soft_value, hard_value))
    return tuple(limits)


def _posix_usage() -> tuple[int | None, int | None, float | None, float | None]:
    try:
        import resource
    except ImportError:
        return None, None, None, None
    usage = resource.getrusage(resource.RUSAGE_SELF)  # type: ignore[attr-defined]
    peak = getattr(usage, "ru_maxrss", 0)
    if sys.platform == "darwin":
        # On macOS ru_maxrss is reported in bytes.
        peak_rss: int | None = int(peak)
    else:
        # On Linux ru_maxrss is reported in kibibytes.
        peak_rss = int(peak) * 1024 if peak else None
    return peak_rss, peak_rss, usage.ru_utime, usage.ru_stime


def process_resource_report() -> ProcessResourceReport:
    if os.name == "nt":
        rss, peak_rss, user, system = _windows_usage()
        limits: tuple[tuple[str, int | None, int | None], ...] = ()
    else:
        limits = _posix_limits()
        rss, peak_rss, user, system = _posix_usage()
    return ProcessResourceReport(
        platform=sys.platform,
        pid=os.getpid(),
        rss_bytes=rss,
        peak_rss_bytes=peak_rss,
        cpu_user_seconds=user,
        cpu_system_seconds=system,
        limits=limits,
    )


__all__ = ["ProcessResourceReport", "process_resource_report"]
