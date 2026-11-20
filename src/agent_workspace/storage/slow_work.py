"""A long check of the conversations says it is still at work, so that whoever waits for it can tell
it from a stuck process. The check's own queries report, not a timer: a check that hangs falls
silent.
"""

from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Callable

_PROGRESS_EVERY_STEPS = 100_000
_report: Callable[[], None] | None = None


def report_slow_work_with(report: Callable[[], None] | None) -> None:
    global _report
    _report = report


def still_working() -> int:
    """Also SQLite's progress handler, for which 0 means go on."""
    report = _report
    if report is not None:
        report()
    return 0


def watch_connection(connection: sqlite3.Connection) -> None:
    """Report while this connection runs a long query (quick_check is one call of many minutes)."""
    connection.set_progress_handler(still_working, _PROGRESS_EVERY_STEPS)


def simulate_long_check() -> None:
    """For acceptance tests: a check as long as on a much larger history."""
    if os.environ.get("AGENT_WORKSPACE_E2E") != "1":
        return
    seconds = os.environ.pop("AGENT_WORKSPACE_TEST_LONG_CHECK_SECONDS", "")
    if seconds.isdigit():
        until = time.monotonic() + int(seconds)
        while time.monotonic() < until:
            still_working()
            time.sleep(0.5)


__all__ = ["report_slow_work_with", "simulate_long_check", "still_working", "watch_connection"]
