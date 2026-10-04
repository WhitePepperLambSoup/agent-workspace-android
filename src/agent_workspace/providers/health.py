from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from typing import Any, Literal

from agent_workspace.config import ProviderConfig, ProviderProtocol, is_loopback_endpoint
from agent_workspace.core.models import ChatMessage, ProviderRequest, Role
from agent_workspace.providers.base import ProviderError
from agent_workspace.providers.factory import create_provider
from agent_workspace.settings import (
    ProviderProfile,
    ProviderSettingsStore,
    default_provider_settings_store,
)

HealthStatus = Literal["healthy", "degraded", "needs_setup", "needs_credential", "error"]


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Capabilities exposed by the adapter and conservative model metadata."""

    streaming: bool = True
    tool_calling: bool | None = None
    vision: bool | None = None
    reasoning: bool | None = None
    context_window: int | None = None

    def to_document(self) -> dict[str, object]:
        return {
            "streaming": self.streaming,
            "toolCalling": self.tool_calling,
            "vision": self.vision,
            "reasoning": self.reasoning,
            "contextWindow": self.context_window,
        }


@dataclass(frozen=True, slots=True)
class ProviderHealthResult:
    """Sanitized provider readiness result suitable for the UI and wire protocol."""

    provider_id: str
    model: str
    status: HealthStatus
    ok: bool
    api_key_present: bool
    latency_ms: float | None
    capabilities: ProviderCapabilities
    error_code: str | None = None
    message: str = ""
    remediation: str = ""
    api_key_value: None = None

    def to_document(self) -> dict[str, object]:
        # Keep the explicit null field as a regression guard: callers can never
        # accidentally receive the secret through a health response.
        return {
            "providerId": self.provider_id,
            "model": self.model,
            "status": self.status,
            "ok": self.ok,
            "apiKeyPresent": self.api_key_present,
            "apiKeyValue": self.api_key_value,
            "latencyMs": self.latency_ms,
            "capabilities": self.capabilities.to_document(),
            "errorCode": self.error_code,
            "message": self.message,
            "remediation": self.remediation,
        }


def provider_capabilities(config: ProviderConfig) -> ProviderCapabilities:
    """Return capabilities known by this adapter without guessing model limits.

    All shipped adapters implement streaming. Tool support is known at the
    adapter level, while vision and context windows depend on the selected
    model, so they remain unknown unless a provider-specific catalogue is
    added later.
    """

    model = config.model.casefold()
    deepseek_vision = config.id.casefold() == "deepseek" and model.startswith(
        ("deepseek-flash", "deepseek-v4-flash", "deepseek-v4.1-flash")
    )

    return ProviderCapabilities(
        streaming=True,
        tool_calling=config.protocol
        in {
            ProviderProtocol.OPENAI_COMPATIBLE,
            ProviderProtocol.ANTHROPIC,
            ProviderProtocol.GEMINI,
            ProviderProtocol.OLLAMA,
        },
        vision=True if deepseek_vision else None,
        reasoning=None,
        context_window=None,
    )


def provider_health_check(
    profile: str | ProviderConfig | ProviderProfile,
    *,
    settings_store: ProviderSettingsStore | None = None,
    timeout: float = 8.0,
    client: Any = None,
) -> ProviderHealthResult:
    """Run a bounded minimal request and return a sanitized health report.

    ``profile`` may be a saved provider id, a decoded profile, or a complete
    config. Saved ids are resolved through Credential Manager; the key only
    exists in the local config object and is never copied into the result.
    """

    config: ProviderConfig | None
    if isinstance(profile, ProviderConfig):
        config = profile
    else:
        store = settings_store or default_provider_settings_store()
        try:
            if isinstance(profile, ProviderProfile):
                config = store.resolve_config(profile.id)
            else:
                config = store.resolve_config(profile)
        except (KeyError, OSError, ValueError):
            provider_id = profile.id if isinstance(profile, ProviderProfile) else str(profile)
            return ProviderHealthResult(
                provider_id=provider_id,
                model=profile.model if isinstance(profile, ProviderProfile) else "",
                status="needs_setup",
                ok=False,
                api_key_present=False,
                latency_ms=None,
                capabilities=ProviderCapabilities(streaming=True),
                error_code="provider_unconfigured",
                message="Provider profile is not fully configured.",
                remediation="Choose a provider, model, and endpoint in Settings.",
            )

    try:
        config.validate()
    except ValueError:
        return ProviderHealthResult(
            provider_id=config.id,
            model=config.model,
            status="needs_setup",
            ok=False,
            api_key_present=False,
            latency_ms=None,
            capabilities=provider_capabilities(config),
            error_code="invalid_provider",
            message="Provider configuration is invalid.",
            remediation="Check the endpoint, protocol, and model in Settings.",
        )

    key_present = bool(config.api_key and config.api_key.strip())
    if not key_present and not is_loopback_endpoint(config.base_url):
        return ProviderHealthResult(
            provider_id=config.id,
            model=config.model,
            status="needs_credential",
            ok=False,
            api_key_present=False,
            latency_ms=None,
            capabilities=provider_capabilities(config),
            error_code="provider_credential_missing",
            message="Provider endpoint requires an API key.",
            remediation="Enter the API key in Settings; it will be stored in Credential Manager.",
        )

    started = time.perf_counter()
    provider = None
    try:
        provider = create_provider(config, timeout=timeout, client=client)
        request = ProviderRequest(
            model=config.model,
            messages=(ChatMessage(role=Role.USER, content="Reply with OK."),),
            max_output_tokens=1,
        )
        finish_seen = False

        async def probe() -> None:
            nonlocal finish_seen
            async for delta in provider.stream(request):
                if delta.kind.value == "finish":
                    finish_seen = True
                    break
                # The request is bounded to one output token. Consume the small
                # response so a normal finish marker can distinguish healthy
                # streaming from an interrupted provider response.

        _run_probe(probe(), timeout=timeout)
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return ProviderHealthResult(
            provider_id=config.id,
            model=config.model,
            status="healthy" if finish_seen else "degraded",
            ok=True,
            api_key_present=key_present,
            latency_ms=latency_ms,
            capabilities=provider_capabilities(config),
            message=(
                "Provider accepted a minimal request."
                if finish_seen
                else "Provider responded to a minimal request."
            ),
            remediation=(
                ""
                if finish_seen
                else (
                    "The provider responded, but did not emit a complete finish marker; "
                    "retry before running a long task."
                )
            ),
        )
    except ProviderError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        code, message, remediation = _classify_error(exc)
        return ProviderHealthResult(
            provider_id=config.id,
            model=config.model,
            status="error",
            ok=False,
            api_key_present=key_present,
            latency_ms=latency_ms,
            capabilities=provider_capabilities(config),
            error_code=code,
            message=message,
            remediation=remediation,
        )
    except TimeoutError:
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return ProviderHealthResult(
            provider_id=config.id,
            model=config.model,
            status="error",
            ok=False,
            api_key_present=key_present,
            latency_ms=latency_ms,
            capabilities=provider_capabilities(config),
            error_code="provider_timeout",
            message="Provider health check timed out.",
            remediation="Check network access and endpoint health, then retry.",
        )
    except Exception:
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return ProviderHealthResult(
            provider_id=config.id,
            model=config.model,
            status="error",
            ok=False,
            api_key_present=key_present,
            latency_ms=latency_ms,
            capabilities=provider_capabilities(config),
            error_code="provider_health_failed",
            message="Provider health check failed.",
            remediation="Review the provider endpoint, model, API key, and network access.",
        )
    finally:
        if provider is not None and hasattr(provider, "aclose"):
            with contextlib.suppress(Exception):
                _run_probe(provider.aclose(), timeout=min(timeout, 2.0))


def _run_probe(awaitable: Any, *, timeout: float) -> None:
    async def runner() -> None:
        async with asyncio.timeout(timeout):
            await awaitable

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(runner())
    else:
        # Gateway health calls are synchronous by contract. A worker thread is
        # used only when an embedding caller already owns an event loop.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(asyncio.run, runner()).result(timeout=timeout + 1.0)


def _classify_error(error: ProviderError) -> tuple[str, str, str]:
    status = error.status_code
    if status in (401, 403):
        return (
            "provider_auth_failed",
            "Provider rejected the stored API key.",
            "Re-enter the API key in Settings and retry.",
        )
    if status == 404:
        return (
            "provider_model_not_found",
            "Provider or model was not found.",
            "Check the endpoint and model name in Settings.",
        )
    if error.balance_exceeded:
        return (
            "provider_billing_required",
            "Provider balance is insufficient for this request.",
            "Add provider balance or choose another provider/model, then retry.",
        )
    if status == 429 or error.quota_exceeded:
        return (
            "provider_rate_limited",
            "Provider rate limit or quota was reached.",
            "Wait, check quota, or choose another provider/model.",
        )
    if error.context_exceeded:
        return (
            "provider_context_exceeded",
            "The provider rejected the probe because of context limits.",
            "Choose a model with a larger context window or reduce the prompt budget.",
        )
    if status is not None and status >= 500:
        return (
            "provider_service_unavailable",
            "Provider service is temporarily unavailable.",
            "Retry shortly and check the provider status page if it persists.",
        )
    if error.retryable:
        return (
            "provider_transport_unavailable",
            "Provider could not be reached reliably.",
            "Check network access and endpoint health, then retry.",
        )
    return (
        "provider_request_failed",
        "Provider rejected the health request.",
        "Check endpoint, model, and API key settings.",
    )


__all__ = [
    "HealthStatus",
    "ProviderCapabilities",
    "ProviderHealthResult",
    "provider_capabilities",
    "provider_health_check",
]
