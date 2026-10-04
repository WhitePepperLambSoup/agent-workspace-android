"""Forecast model invocation and task costs prior to provider calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_workspace.core.cost import UNKNOWN_PRICING, estimate_cost_usd, resolve_pricing


@dataclass(frozen=True, slots=True)
class CostForecast:
    model: str
    prompt_tokens: int
    min_completion_tokens: int
    expected_completion_tokens: int
    max_completion_tokens: int
    cached_tokens: int
    min_cost_usd: float
    expected_cost_usd: float
    max_cost_usd: float
    is_pricing_known: bool

    def to_document(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "min_completion_tokens": self.min_completion_tokens,
            "expected_completion_tokens": self.expected_completion_tokens,
            "max_completion_tokens": self.max_completion_tokens,
            "cached_tokens": self.cached_tokens,
            "min_cost_usd": round(self.min_cost_usd, 6),
            "expected_cost_usd": round(self.expected_cost_usd, 6),
            "max_cost_usd": round(self.max_cost_usd, 6),
            "is_pricing_known": self.is_pricing_known,
        }


def forecast_turn_cost(
    model: str,
    prompt_tokens: int,
    expected_completion_tokens: int,
    max_completion_tokens: int | None = None,
    cached_tokens: int = 0,
) -> CostForecast:
    """Forecast USD cost range for a single LLM turn."""
    if prompt_tokens < 0 or expected_completion_tokens < 0 or cached_tokens < 0:
        raise ValueError("token values cannot be negative")

    max_tokens = (
        max_completion_tokens
        if max_completion_tokens is not None
        else max(expected_completion_tokens, 4096)
    )
    if max_tokens < expected_completion_tokens:
        max_tokens = expected_completion_tokens

    pricing = resolve_pricing(model)
    is_known = pricing is not UNKNOWN_PRICING and (
        pricing.input_usd_per_million > 0 or pricing.output_usd_per_million > 0
    )

    min_cost = estimate_cost_usd(model, prompt_tokens, 0, cached_tokens)
    expected_cost = estimate_cost_usd(
        model, prompt_tokens, expected_completion_tokens, cached_tokens
    )
    max_cost = estimate_cost_usd(model, prompt_tokens, max_tokens, cached_tokens)

    return CostForecast(
        model=model,
        prompt_tokens=prompt_tokens,
        min_completion_tokens=0,
        expected_completion_tokens=expected_completion_tokens,
        max_completion_tokens=max_tokens,
        cached_tokens=cached_tokens,
        min_cost_usd=min_cost,
        expected_cost_usd=expected_cost,
        max_cost_usd=max_cost,
        is_pricing_known=is_known,
    )


def forecast_task_budget(
    model: str,
    estimated_turns: int,
    avg_prompt_tokens: int,
    avg_completion_tokens: int,
) -> dict[str, float]:
    """Estimate total expected cost for a multi-turn task."""
    if estimated_turns <= 0 or avg_prompt_tokens < 0 or avg_completion_tokens < 0:
        raise ValueError("invalid arguments for task forecast")

    turn_forecast = forecast_turn_cost(
        model,
        prompt_tokens=avg_prompt_tokens,
        expected_completion_tokens=avg_completion_tokens,
    )
    return {
        "estimated_turns": float(estimated_turns),
        "expected_total_cost_usd": round(turn_forecast.expected_cost_usd * estimated_turns, 6),
        "max_total_cost_usd": round(turn_forecast.max_cost_usd * estimated_turns, 6),
    }
