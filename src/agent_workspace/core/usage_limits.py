"""Rate and budget tracking utilities for providers, tools, and sessions."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(slots=True)
class SlidingWindowRateLimiter:
    """A fixed-size sliding window rate limiter with injectable time."""

    limit: int
    window_seconds: float
    clock: Callable[[], float] = time.monotonic

    _stamps: deque[float] = field(default_factory=deque, init=False)

    def __post_init__(self) -> None:
        if type(self.limit) is not int or isinstance(self.limit, bool) or self.limit < 1:
            raise ValueError("rate limit must be a positive integer")
        if self.window_seconds <= 0:
            raise ValueError("rate limit window must be positive")

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._stamps and self._stamps[0] <= cutoff:
            self._stamps.popleft()

    def try_acquire(self) -> bool:
        """Return True when one token is admitted inside the window."""
        current = self.clock()
        self._prune(current)
        if len(self._stamps) >= self.limit:
            return False
        self._stamps.append(current)
        return True

    def available(self) -> int:
        current = self.clock()
        self._prune(current)
        return self.limit - len(self._stamps)


@dataclass(slots=True)
class UsageBudgetTracker:
    """Track token/cost usage against configured budgets.

    Budgets are soft defaults; enforcement decisions belong to callers so this
    class stays side-effect free and easy to test with injected clocks.
    """

    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None
    max_cost_usd: float | None = None
    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0

    input_tokens: int = field(default=0, init=False)
    output_tokens: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("max_input_tokens", self.max_input_tokens),
            ("max_output_tokens", self.max_output_tokens),
            ("max_total_tokens", self.max_total_tokens),
        ):
            if value is not None and (
                type(value) is not int or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be non-negative")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float:
        return (
            self.input_tokens * self.input_price_per_million
            + self.output_tokens * self.output_price_per_million
        ) / 1_000_000

    def record(self, input_tokens: int, output_tokens: int) -> None:
        if (
            type(input_tokens) is not int
            or isinstance(input_tokens, bool)
            or input_tokens < 0
            or type(output_tokens) is not int
            or isinstance(output_tokens, bool)
            or output_tokens < 0
        ):
            raise ValueError("token counts must be non-negative integers")
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def violations(self) -> tuple[str, ...]:
        result: list[str] = []
        if self.max_input_tokens is not None and self.input_tokens > self.max_input_tokens:
            result.append("input_tokens")
        if self.max_output_tokens is not None and self.output_tokens > self.max_output_tokens:
            result.append("output_tokens")
        if self.max_total_tokens is not None and self.total_tokens > self.max_total_tokens:
            result.append("total_tokens")
        if self.max_cost_usd is not None and self.cost_usd > self.max_cost_usd:
            result.append("cost_usd")
        return tuple(result)


__all__ = [
    "SlidingWindowRateLimiter",
    "UsageBudgetTracker",
]
