from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any


async def settle_tasks(
    tasks: Iterable[asyncio.Task[Any]],
    *,
    timeout: float,
    timeout_message: str,
    cancel_pending: bool = True,
) -> list[Exception]:
    """Wait for tasks to become quiescent without abandoning shared-resource users.

    The timeout is a cancellation deadline, not permission to detach a coroutine.
    A coroutine that suppresses cancellation is joined before this helper returns so
    callers may safely close stores and release process-wide writer locks.
    """

    tracked = tuple(tasks)
    if not tracked:
        return []

    caller_cancelled = False
    timed_out = False
    try:
        done, pending = await asyncio.wait(tracked, timeout=timeout)
    except asyncio.CancelledError:
        caller_cancelled = True
        done = {task for task in tracked if task.done()}
        pending = set(tracked) - done

    if pending:
        timed_out = not caller_cancelled
        if cancel_pending and (timed_out or not caller_cancelled):
            for task in pending:
                task.cancel()

        joined = asyncio.gather(*pending, return_exceptions=True)
        while not joined.done():
            try:
                await asyncio.shield(joined)
            except asyncio.CancelledError:
                caller_cancelled = True
        joined.result()
        done.update(pending)

    errors: list[Exception] = []
    if timed_out:
        errors.append(TimeoutError(timeout_message))
    for task in done:
        if task.cancelled():
            continue
        error = task.exception()
        if isinstance(error, Exception):
            errors.append(error)
        elif error is not None:
            raise error

    if caller_cancelled:
        raise asyncio.CancelledError
    return errors
