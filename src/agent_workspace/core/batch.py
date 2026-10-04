"""Bounded asynchronous prompt batching over one ApplicationService.

Batch execution is intentionally cooperative: callers provide a service whose
provider already has its own concurrency limits. The runner only adds a local
semaphore and deterministic result ordering.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_workspace.application.service import ApplicationService


@dataclass(frozen=True, slots=True)
class BatchPrompt:
    id: str
    prompt: str

    def __post_init__(self) -> None:
        if not self.id or not self.prompt.strip():
            raise ValueError("batch prompt id and text may not be empty")


@dataclass(frozen=True, slots=True)
class BatchResult:
    prompt_id: str
    session_id: str
    text: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


async def run_prompt_batch(
    service: ApplicationService,
    prompts: tuple[BatchPrompt, ...],
    workspace: Path,
    provider_model: str,
    *,
    concurrency: int = 2,
    mode: Any = None,
    autonomy: Any = None,
) -> tuple[BatchResult, ...]:
    """Run prompts concurrently with a local semaphore.

    Each prompt gets its own session in ``workspace``. Results preserve prompt
    order. Individual failures are captured in :class:`BatchResult` instead of
    aborting the whole batch.
    """
    if type(concurrency) is not int or isinstance(concurrency, bool) or concurrency < 1:
        raise ValueError("batch concurrency must be a positive integer")
    if not prompts:
        return ()
    semaphore = asyncio.Semaphore(concurrency)

    async def execute(prompt: BatchPrompt) -> BatchResult:
        async with semaphore:
            session_kwargs: dict[str, Any] = {"title": prompt.prompt.strip()[:80]}
            if mode is not None:
                session_kwargs["mode"] = mode
            if autonomy is not None:
                session_kwargs["autonomy"] = autonomy
            session = service.create_session(workspace, **session_kwargs)
            try:
                result = await service.run(session, prompt.prompt, provider_model)
                return BatchResult(prompt.id, session.id, result.text)
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                return BatchResult(
                    prompt.id,
                    session.id,
                    "",
                    f"{type(exc).__name__}: {exc}",
                )

    results = await asyncio.gather(*(execute(prompt) for prompt in prompts))
    return tuple(results)


__all__ = [
    "BatchPrompt",
    "BatchResult",
    "run_prompt_batch",
]
