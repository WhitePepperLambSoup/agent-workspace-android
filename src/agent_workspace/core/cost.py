"""Model call cost estimation over usage events.

Prices in :data:`DEFAULT_PRICING` are approximate USD-per-million-token list
prices and are not contractual. Models without a matching entry are treated as
free via :data:`UNKNOWN_PRICING`, unless a caller asks for ``estimate_unlisted``:
then they are counted at :data:`UNLISTED_PRICING`, a cautious default the caller
shows as an estimate (the desktop does, for a model served from elsewhere).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

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
# exact model ids or families that match ``<key>-<variant>`` (or ``:``/``@``) ids.
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
    # DeepSeek V4.1 peak-hour list prices (off-peak hours cost half), October 2026:
    # https://api-docs.deepseek.com/quick_start/pricing
    "deepseek-flash": ModelPricing(0.30, 1.20, cached_usd_per_million=0.006),
    "deepseek-v4-flash": ModelPricing(0.30, 1.20, cached_usd_per_million=0.006),
    "deepseek-v4.1-flash": ModelPricing(0.30, 1.20, cached_usd_per_million=0.006),
    "deepseek-v4-pro": ModelPricing(1.32, 3.96, cached_usd_per_million=0.044),
    "qwen2.5-coder": ModelPricing(0.0, 0.0),
    # The first models the app offers for each cloud service (desktop provider-presets.ts and
    # the Android first-use setup), from the services' own pricing pages, November 2026.
    # https://developers.openai.com/api/docs/pricing (standard tier, up to 272K input tokens)
    "gpt-5.6-sol": ModelPricing(4.0, 20.0, cached_usd_per_million=0.40),
    # https://platform.claude.com/docs/en/about-claude/pricing (cache hits; writes cost more)
    "claude-sonnet-5-5": ModelPricing(2.0, 10.0, cached_usd_per_million=0.10),
    # https://aistudio.google.com/docs/pricing: the price through December 31, 2026; it doubles
    # from January 1, 2027 (_LATER_PRICING).
    "gemini-3.8-flash": ModelPricing(0.75, 3.75, cached_usd_per_million=0.075),
    # https://docs.x.ai/docs/models: prompts under 200K tokens (twice this above).
    "grok-4.7": ModelPricing(2.0, 6.0, cached_usd_per_million=0.50),
    # https://docs.z.ai/guides/overview/pricing
    "glm-5.3-flash": ModelPricing(0.15, 0.50, cached_usd_per_million=0.03),
    # https://www.alibabacloud.com/help/en/model-studio/model-pricing (Singapore; Beijing and
    # the global deployment cost less). No cache price is listed: cache hits count as input.
    "qwen3.8-flash": ModelPricing(0.15, 0.47),
    # https://platform.kimi.ai/docs/pricing/chat (cache hits; K3 cache writes cost more). K2
    # models are closed to new accounts since October 31, 2026 and retire at the end of 2026.
    "kimi-k3": ModelPricing(3.0, 15.0, cached_usd_per_million=0.30),
    "kimi-k3.1-pro": ModelPricing(2.0, 10.0, cached_usd_per_million=0.20),
    "kimi-k3.1-pro-highspeed": ModelPricing(4.0, 20.0, cached_usd_per_million=0.20),
    "kimi-k2.7-code": ModelPricing(0.95, 4.0, cached_usd_per_million=0.19),
    "kimi-k2.7-code-highspeed": ModelPricing(1.90, 8.0, cached_usd_per_million=0.38),
    "kimi-k2.6": ModelPricing(0.95, 4.0, cached_usd_per_million=0.16),
}

# Prices a service has announced for a later date: (first day, price). A call is priced as of the
# day it was made (UTC), so a past month's bill stays as it was when the price changes.
_LATER_PRICING: dict[str, tuple[date, ModelPricing]] = {
    "gemini-3.8-flash": (date(2027, 1, 1), ModelPricing(1.50, 7.50, cached_usd_per_million=0.15)),
}

UNKNOWN_PRICING = ModelPricing(0.0, 0.0)
# What a model without a listed price is counted at when the caller asks (estimate_unlisted), so
# a spending limit still holds: the dearest first model the app offers (gpt-5.6-sol), with no
# discount for cache hits. Always shown as an estimate.
UNLISTED_PRICING = ModelPricing(4.0, 20.0)
_VARIANT_SEPARATORS = frozenset({"-", ":", "@"})


def resolve_pricing(
    model: str, *, estimate_unlisted: bool = False, on: date | None = None
) -> ModelPricing:
    """Resolve pricing for a model id, longest matching family first.

    A family key covers ids that continue it after a separator (``gpt-4o-2024-08-06``,
    ``qwen2.5-coder:7b``, ``claude-3-7-sonnet@20250219``), not ids that merely start with
    the same letters (``o1`` does not price ``o1x``). A model with no entry is
    :data:`UNKNOWN_PRICING`, or :data:`UNLISTED_PRICING` with ``estimate_unlisted``.
    ``on`` is the day of the call (today, UTC, when not given), for prices that change on a
    known date.
    """
    key = _listed_key(model)
    if key is None:
        return UNLISTED_PRICING if estimate_unlisted and model else UNKNOWN_PRICING
    later = _LATER_PRICING.get(key)
    if later is not None and (on or datetime.now(UTC).date()) >= later[0]:
        return later[1]
    return DEFAULT_PRICING[key]


def _listed_key(model: str) -> str | None:
    if model in DEFAULT_PRICING:
        return model
    best: str | None = None
    for key in DEFAULT_PRICING:
        if (
            model.startswith(key)
            and model[len(key) : len(key) + 1] in _VARIANT_SEPARATORS
            and (best is None or len(key) > len(best))
        ):
            best = key
    return best


def _event_day(event: Event) -> date | None:
    try:
        return datetime.fromisoformat(event.created_at).astimezone(UTC).date()
    except (TypeError, ValueError):
        return None


def estimate_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    *,
    estimate_unlisted: bool = False,
    on: date | None = None,
) -> float:
    """Estimate the USD cost of one model call from its token usage.

    ``input_tokens`` represents the total input prompt token count. Cached tokens
    are billed at ``cached_usd_per_million``, and uncached tokens
    (``max(0, input_tokens - cached_tokens)``) are billed at ``input_usd_per_million``.
    ``on`` is the day of the call (today when not given).
    """
    if input_tokens < 0 or output_tokens < 0 or cached_tokens < 0:
        raise ValueError("token counts may not be negative")
    pricing = resolve_pricing(model, estimate_unlisted=estimate_unlisted, on=on)
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
    # Models in the cost at UNLISTED_PRICING (estimate_unlisted): the figure is an estimate.
    unlisted_models: tuple[str, ...] = ()


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


def session_cost(
    events: Sequence[Event], model: str | None = None, *, estimate_unlisted: bool = False
) -> SessionCost:
    """Accumulate ``usage.updated`` events into a session cost summary.

    ``model`` wins over any ``model.requested`` event. Without it, each
    ``usage.updated`` event is priced with the most recent preceding
    ``model.requested`` model, so sessions that switch models (context
    halving retries, collaboration routes) are priced per segment instead
    of forcing one rate onto the whole stream. Usage events with missing
    or invalid token fields are skipped, and models without a pricing
    entry are treated as free (or at UNLISTED_PRICING with ``estimate_unlisted``).
    """
    current = model if model is not None else ""
    buckets: dict[str, tuple[int, int, int]] = {}
    model_calls = 0
    input_total = 0
    output_total = 0
    cached_total = 0
    cost_usd = 0.0
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
        # Each call at the price of its own day (_LATER_PRICING).
        cost_usd += estimate_cost_usd(
            current,
            usage.input_tokens,
            usage.output_tokens,
            usage.cached_tokens,
            estimate_unlisted=estimate_unlisted,
            on=_event_day(event),
        )
    models = tuple(sorted(bucket_model for bucket_model in buckets if bucket_model))
    return SessionCost(
        model_calls=model_calls,
        input_tokens=input_total,
        output_tokens=output_total,
        cached_tokens=cached_total,
        estimated=estimated,
        cost_usd=cost_usd,
        mixed=len(buckets) > 1,
        models=models,
        unlisted_models=tuple(
            name
            for name in models
            if estimate_unlisted
            and resolve_pricing(name, estimate_unlisted=True) is UNLISTED_PRICING
        ),
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
