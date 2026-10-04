"""Reasoning step and token quota tracking for reasoning models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_workspace.core.budgets import BudgetExceededError


@dataclass(slots=True)
class ReasoningQuotaTracker:
    max_steps: int = 50
    max_thinking_tokens: int = 64_000
    consumed_steps: int = 0
    consumed_thinking_tokens: int = 0

    def __post_init__(self) -> None:
        if self.max_steps <= 0 or self.max_thinking_tokens <= 0:
            raise ValueError("reasoning quota limits must be positive")

    def record_reasoning_step(self, thinking_tokens: int = 0) -> None:
        """Record a single reasoning step and associated thinking tokens."""
        if thinking_tokens < 0:
            raise ValueError("thinking_tokens cannot be negative")
        if self.consumed_steps >= self.max_steps:
            raise BudgetExceededError("reasoning step quota exhausted")
        next_tokens = self.consumed_thinking_tokens + thinking_tokens
        if next_tokens > self.max_thinking_tokens:
            raise BudgetExceededError("thinking token quota exhausted")
        self.consumed_steps += 1
        self.consumed_thinking_tokens = next_tokens

    def remaining_steps(self) -> int:
        return max(0, self.max_steps - self.consumed_steps)

    def remaining_thinking_tokens(self) -> int:
        return max(0, self.max_thinking_tokens - self.consumed_thinking_tokens)

    def to_document(self) -> dict[str, Any]:
        return {
            "max_steps": self.max_steps,
            "max_thinking_tokens": self.max_thinking_tokens,
            "consumed_steps": self.consumed_steps,
            "consumed_thinking_tokens": self.consumed_thinking_tokens,
            "remaining_steps": self.remaining_steps(),
            "remaining_thinking_tokens": self.remaining_thinking_tokens(),
        }
