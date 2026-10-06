from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

import httpx

from agent_workspace.application.ports import ManagedModelProvider
from agent_workspace.config import ProviderConfig, ProviderProtocol, is_loopback_endpoint
from agent_workspace.providers.anthropic import AnthropicProvider
from agent_workspace.providers.gemini import GeminiProvider
from agent_workspace.providers.ollama import OllamaProvider
from agent_workspace.providers.openai_compatible import OpenAICompatibleProvider

if TYPE_CHECKING:
    from agent_workspace.providers.health import ProviderHealthResult
    from agent_workspace.settings import ProviderProfile, ProviderSettingsStore

_DEFAULT_STREAM_TIMEOUT_SECONDS = 60.0
_STREAM_TIMEOUT_ENV = "AGENT_WORKSPACE_PROVIDER_TIMEOUT"


def provider_stream_timeout() -> float:
    """Resolve the per-request provider stream timeout.

    Long-thinking models can exceed 60s before their first token, so the
    timeout is configurable through AGENT_WORKSPACE_PROVIDER_TIMEOUT (seconds).
    """
    raw = os.getenv(_STREAM_TIMEOUT_ENV)
    if not raw:
        return _DEFAULT_STREAM_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{_STREAM_TIMEOUT_ENV} must be a positive number of seconds") from None
    if value <= 0:
        raise ValueError(f"{_STREAM_TIMEOUT_ENV} must be a positive number of seconds")
    return value


def create_provider(
    config: ProviderConfig,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float | httpx.Timeout | None = None,
) -> ManagedModelProvider:
    config.validate()
    resolved_timeout = provider_stream_timeout() if timeout is None else timeout
    arguments = (config.id, config.base_url, config.api_key)
    if config.protocol is ProviderProtocol.OPENAI_COMPATIBLE:
        return OpenAICompatibleProvider(*arguments, timeout=resolved_timeout, client=client)
    if config.protocol is ProviderProtocol.ANTHROPIC:
        return AnthropicProvider(*arguments, timeout=resolved_timeout, client=client)
    if config.protocol is ProviderProtocol.GEMINI:
        return GeminiProvider(*arguments, timeout=resolved_timeout, client=client)
    if config.protocol is ProviderProtocol.OLLAMA:
        return OllamaProvider(*arguments, timeout=resolved_timeout, client=client)
    raise AssertionError(f"unsupported provider protocol: {config.protocol}")


def _is_local(config: ProviderConfig) -> bool:
    return config.protocol is ProviderProtocol.OLLAMA or is_loopback_endpoint(config.base_url)


def _local_server_hint(config: ProviderConfig) -> str:
    if config.protocol is ProviderProtocol.OLLAMA:
        return "Ensure Ollama is running and accessible."
    return "Ensure the local model server (for example llama.cpp or LM Studio) is running."


async def probe_provider_connection(
    config: ProviderConfig,
    *,
    timeout: float = 8.0,
    client: httpx.AsyncClient | None = None,
) -> tuple[bool, str]:
    """Test connectivity to an LLM provider and categorize errors.

    Returns:
        tuple[bool, str]: (is_successful, detail_message)
    """
    import contextlib

    try:
        config.validate()
    except Exception as exc:
        return False, f"Invalid provider configuration: {exc}"

    provider = None
    try:
        from agent_workspace.core.models import ChatMessage, DeltaKind, ProviderRequest, Role
        from agent_workspace.providers.base import ProviderError

        provider = create_provider(config, timeout=timeout, client=client)
        req = ProviderRequest(
            model=config.model,
            messages=(ChatMessage(role=Role.USER, content="ping"),),
            max_output_tokens=1,
        )
        stream = provider.stream(req)
        finish_seen = False
        async with asyncio.timeout(timeout):
            async for delta in stream:
                if delta.kind is DeltaKind.FINISH:
                    finish_seen = True
        if not finish_seen:
            return (
                False,
                f"Provider stream from {config.id} ({config.model}) ended before completion.",
            )
        return True, f"Connection verified successfully for {config.id} ({config.model})."
    except ProviderError as exc:
        code = exc.status_code
        msg_str = str(exc).lower()
        if code in (401, 403):
            return False, f"Authentication failed (status {code}): Please check your API key."
        if code == 404:
            return (
                False,
                f"Model not found (status 404): "
                f"Model '{config.model}' may not exist on this provider.",
            )
        if code == 429:
            return False, f"Rate limit or quota exceeded (status 429): {exc}"
        if code and code >= 500:
            return (
                False,
                f"Provider service error (status {code}): Service temporarily unavailable.",
            )
        if "timed out" in msg_str:
            if _is_local(config):
                return (
                    False,
                    f"Connection timed out at {config.base_url}. {_local_server_hint(config)}",
                )
            return False, f"Connection to {config.base_url} timed out after {timeout:g}s."
        if ("failed" in msg_str or "refused" in msg_str) and _is_local(config):
            return (
                False,
                f"Connection failed at {config.base_url}. {_local_server_hint(config)}",
            )
        return False, f"Provider error: {exc}"
    except httpx.ConnectError as exc:
        if _is_local(config):
            return (
                False,
                f"Connection refused at {config.base_url}. {_local_server_hint(config)}",
            )
        return False, f"Network connection failed to {config.base_url}: {exc}"
    except (httpx.TimeoutException, TimeoutError):
        return False, f"Connection to {config.base_url} timed out after {timeout:g}s."
    except Exception as exc:
        return False, f"Connection check failed: {exc}"
    finally:
        if provider is not None and hasattr(provider, "aclose"):
            with contextlib.suppress(Exception):
                await provider.aclose()


def provider_health_check(
    profile: str | ProviderConfig | ProviderProfile,
    *,
    settings_store: ProviderSettingsStore | None = None,
    timeout: float = 8.0,
    client: Any = None,
) -> ProviderHealthResult:
    """Run the structured provider health probe without importing it eagerly."""
    from agent_workspace.providers.health import provider_health_check as _health_check

    return _health_check(
        profile,
        settings_store=settings_store,
        timeout=timeout,
        client=client,
    )
