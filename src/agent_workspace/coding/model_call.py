"""One request to the conversation's model with a system and a user message, for the coding
desk's small model jobs (a review, a commit message): the answer's text, or an error code."""

from __future__ import annotations

import asyncio
import contextlib

from agent_workspace.config import ProviderConfig
from agent_workspace.core.models import ChatMessage, DeltaKind, ProviderRequest, Role
from agent_workspace.providers import create_provider


class ModelCallError(RuntimeError):
    pass


def ask_model(
    config: ProviderConfig,
    system: str,
    user: str,
    *,
    max_output_tokens: int,
    seconds: float,
    temperature: float = 0.1,
    error_prefix: str = "model",
) -> str:
    """Raises ModelCallError(f"{error_prefix}_timeout" or f"{error_prefix}_failed")."""
    request = ProviderRequest(
        model=config.model,
        messages=(
            ChatMessage(role=Role.SYSTEM, content=system),
            ChatMessage(role=Role.USER, content=user),
        ),
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )

    async def stream() -> str:
        provider = create_provider(config)
        chunks: list[str] = []
        try:
            async for delta in provider.stream(request):
                if delta.kind is DeltaKind.TEXT and delta.text:
                    chunks.append(delta.text)
        finally:
            if hasattr(provider, "aclose"):
                with contextlib.suppress(Exception):
                    await provider.aclose()
        return "".join(chunks)

    try:
        return asyncio.run(asyncio.wait_for(stream(), seconds))
    except TimeoutError:
        raise ModelCallError(f"{error_prefix}_timeout") from None
    except Exception:
        raise ModelCallError(f"{error_prefix}_failed") from None


__all__ = ["ModelCallError", "ask_model"]
