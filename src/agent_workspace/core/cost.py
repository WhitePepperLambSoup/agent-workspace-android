"""Model call cost estimation over usage events.

Prices in :data:`DEFAULT_PRICING` are approximate USD-per-million-token list
prices (early 2026) and are not contractual. Models without a matching entry
are treated as free via :data:`UNKNOWN_PRICING`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from agent_workspace.core.events import Event
from agent_workspace.core.models import Usage

_MILLION = 1_000_000


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Per-million-token list prices for one model family."""

    input_usd_per_million: float
    output_usd_per_million: float
    cached_usd_per_million: float | None = None


# Approximate USD-per-million-token list prices, early 2026. Keys may be
# exact model ids or family prefixes that match any ``<key>-<variant>`` id.
DEFAULT_PRICING: dict[str, ModelPricing] = {
    "gpt-4o": ModelPricing(2.5, 10.0, cached_usd_per_million=1.25),
    "gpt-4o-mini": ModelPricing(0.15, 0.6, cached_usd_per_million=0.075),
    "o3-mini": ModelPricing(1.10, 4.40, cached_usd_per_million=0.55),
    "o1": ModelPricing(15.0, 60.0, cached_usd_per_million=7.50),
    "claude-3-5-sonnet": ModelPricing(3.0, 15.0, cached_usd_per_million=0.30),
    "claude-3-7-sonnet": ModelPricing(3.0, 15.0, cached_usd_per_million=0.30),
    "gemini-1.5-pro": ModelPricing(1.25, 5.0),
    "gemini-2.0-flash": ModelPricing(0.1, 0.4, cached_usd_per_million=0.025),
    "deepseek-chat": ModelPricing(0.27, 1.1, cached_usd_per_million=0.07),
    "deepseek-reasoner": ModelPricing(0.55, 2.19),
    "qwen2.5-coder": ModelPricing(0.0, 0.0),
}

UNKNOWN_PRICING = ModelPricing(0.0, 0.0)


def resolve_pricing(model: str) -> ModelPricing:
    """Resolve pricing for a model id, longest matching prefix first."""
    exact = DEFAULT_PRICING.get(model)
    if exact is not None:
        return exact
    best: ModelPricing | None = None
    best_length = -1
    for key, pricing in DEFAULT_PRICING.items():
        if model.startswith(key) and len(key) > best_length:
            best = pricing
            best_length = len(key)
    return UNKNOWN_PRICING if best is None else best


def estimate_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Estimate the USD cost of one model call from its token usage.

    ``input_tokens`` represents the total input prompt token count. Cached tokens
    are billed at ``cached_usd_per_million``, and uncached tokens
    (``max(0, input_tokens - cached_tokens)``) are billed at ``input_usd_per_million``.
    """
    if input_tokens < 0 or output_tokens < 0 or cached_tokens < 0:
        raise ValueError("token counts may not be negative")
    pricing = resolve_pricing(model)
    cached_rate = pricing.cached_usd_per_million
    if cached_rate is None:
        cached_rate = pricing.input_usd_per_million
    uncached_tokens = max(0, input_tokens - cached_tokens)
    input_cost = uncached_tokens * pricing.input_usd_per_million / _MILLION
    output_cost = output_tokens * pricing.output_usd_per_million / _MILLION
    cached_cost = cached_tokens * cached_rate / _MILLION
    return input_cost + output_cost + cached_cost


@dataclass(frozen=True, slots=True)
class SessionCost:
    """Accumulated token usage and estimated cost for a session."""

    model_calls: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    estimated: bool
    cost_usd: float
    mixed: bool = False
    models: tuple[str, ...] = ()


def _usage_from_event(event: Event) -> Usage | None:
    input_tokens = event.data.get("input_tokens")
    output_tokens = event.data.get("output_tokens")
    cached_tokens = event.data.get("cached_tokens", 0)
    estimated = event.data.get("estimated", False)
    if (
        type(input_tokens) is not int
        or input_tokens < 0
        or type(output_tokens) is not int
        or output_tokens < 0
        or type(cached_tokens) is not int
        or cached_tokens < 0
        or not isinstance(estimated, bool)
    ):
        return None
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        estimated=estimated,
    )


def session_cost(events: Sequence[Event], model: str | None = None) -> SessionCost:
    """Accumulate ``usage.updated`` events into a session cost summary.

    ``model`` wins over any ``model.requested`` event. Without it, each
    ``usage.updated`` event is priced with the most recent preceding
    ``model.requested`` model, so sessions that switch models (context
    halving retries, collaboration routes) are priced per segment instead
    of forcing one rate onto the whole stream. Usage events with missing
    or invalid token fields are skipped, and models without a pricing
    entry are treated as free.
    """
    current = model if model is not None else ""
    buckets: dict[str, tuple[int, int, int]] = {}
    model_calls = 0
    input_total = 0
    output_total = 0
    cached_total = 0
    estimated = False
    for event in events:
        if event.type == "model.requested":
            raw_model = event.data.get("model")
            if model is None and isinstance(raw_model, str) and raw_model:
                current = raw_model
            continue
        if event.type != "usage.updated":
            continue
        usage = _usage_from_event(event)
        if usage is None:
            continue
        model_calls += 1
        input_total += usage.input_tokens
        output_total += usage.output_tokens
        cached_total += usage.cached_tokens
        estimated = estimated or usage.estimated
        previous = buckets.get(current, (0, 0, 0))
        buckets[current] = (
            previous[0] + usage.input_tokens,
            previous[1] + usage.output_tokens,
            previous[2] + usage.cached_tokens,
        )
    cost_usd = sum(
        estimate_cost_usd(bucket_model, bucket[0], bucket[1], bucket[2])
        for bucket_model, bucket in buckets.items()
    )
    return SessionCost(
        model_calls=model_calls,
        input_tokens=input_total,
        output_tokens=output_total,
        cached_tokens=cached_total,
        estimated=estimated,
        cost_usd=cost_usd,
        mixed=len(buckets) > 1,
        models=tuple(sorted(bucket_model for bucket_model in buckets if bucket_model)),
    )


def format_cost(cost: SessionCost) -> str:
    """Render a session cost as a single human-readable line."""
    rendered = (
        f"model calls: {cost.model_calls}, input: {cost.input_tokens}, "
        f"output: {cost.output_tokens}, cost: ${cost.cost_usd:.4f}"
    )
    if cost.models:
        rendered += f", models: {', '.join(cost.models)}"
    return rendered
