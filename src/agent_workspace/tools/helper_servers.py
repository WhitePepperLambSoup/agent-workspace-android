"""Long-lived helper servers (MCP servers, language servers): started so that what they start
can be ended with them.

They are often started through npx, uvx, a shell or a .cmd shim, so the process that does the
work is a grandchild. On POSIX they start in their own session (start_new_session) and are
ended by process group; on Windows they go into a job that ends them all when it is closed or
this process ends.

Kept apart from process_worker: the Android engine puts its own module in place of that one,
and these helpers are needed there too.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import time
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from .process_worker import _WindowsJob

_LOGGER = logging.getLogger(__name__)
_TERMINATE_SECONDS = 2.0

HELPER_SERVER_NEW_SESSION = os.name != "nt"


def helper_server_job(pid: int) -> _WindowsJob | None:
    """The Windows job for a helper server just started, or None (not Windows, or the job
    could not be set up: the server runs as before and the reason is logged)."""
    if os.name != "nt":
        return None
    from .base import ToolError
    from .process_worker import _WindowsJob

    job: _WindowsJob | None = None
    try:
        job = _WindowsJob(limits=False)
        job.kill_on_close()
        job.assign(pid)
    except (ToolError, OSError) as exc:
        if job is not None:
            job.close()
        _LOGGER.warning("helper server %s runs outside a Windows job: %s", pid, exc)
        return None
    return job


async def end_helper_server(
    process: asyncio.subprocess.Process,
    job: _WindowsJob | None,
    *,
    grace_seconds: float = _TERMINATE_SECONDS,
) -> None:
    """End a helper server and what it started, then reap it; never raises. Also when the
    server itself has exited: a grandchild it started can still be running."""
    platform_os = cast(Any, os)
    platform_signal = cast(Any, signal)
    group = False
    if os.name == "nt":
        if job is not None:
            job.close()
        if process.returncode is None:
            with contextlib.suppress(OSError):
                process.terminate()
    else:
        try:
            platform_os.killpg(process.pid, platform_signal.SIGTERM)
            group = True
        except OSError:
            # Not a group of its own (or already gone): the process alone, as before.
            if process.returncode is None:
                with contextlib.suppress(OSError):
                    process.terminate()
    try:
        if group:
            deadline = time.monotonic() + grace_seconds
            while time.monotonic() < deadline:
                try:
                    platform_os.killpg(process.pid, 0)
                except OSError:
                    group = False
                    break
                await asyncio.sleep(0.05)
        if not group:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(process.wait(), timeout=grace_seconds)
    finally:
        # Also when the caller is cancelled meanwhile: nothing is left running.
        if group:
            with contextlib.suppress(OSError):
                platform_os.killpg(process.pid, platform_signal.SIGKILL)
        if process.returncode is None:
            with contextlib.suppress(OSError):
                process.kill()
    if process.returncode is None:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(process.wait(), timeout=grace_seconds)


__all__ = ["HELPER_SERVER_NEW_SESSION", "end_helper_server", "helper_server_job"]
