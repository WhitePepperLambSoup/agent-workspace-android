from __future__ import annotations

from dataclasses import dataclass


class BudgetExceededError(RuntimeError):
    pass


@dataclass(slots=True)
class TaskBudget:
    max_model_calls: int = 256
    max_provider_attempts: int = 192
    max_tool_calls: int = 256
    max_turn_seconds: float = 7200.0
    max_tool_seconds: float = 120.0
    max_tool_settlement_seconds: float = 5.0
    max_tool_output_bytes: int = 1024 * 1024
    max_model_output_bytes_per_call: int = 8 * 1024 * 1024
    # Keep enough wire headroom for several ordinary vision attachments.
    # Provider adapters still classify real model context errors and retry with
    # a smaller request when a model has a tighter limit.
    max_context_bytes: int = 8 * 1024 * 1024
    # Begin compacting long tool-driven histories before the hard provider
    # context limit. This bounds repeated input cost without shrinking the
    # latest turn or changing the provider maximum.
    proactive_context_bytes: int = 512 * 1024
    # Per-turn input budget is cumulative across repeated tool/model rounds.
    # Keep enough headroom for large coding and research tasks whose latest
    # context is bounded by max_context_bytes but must be sent many times.
    # A 16M ceiling is reached by a single long turn after roughly one
    # hundred tool rounds.
    max_input_tokens: int = 64_000_000
    max_output_tokens: int = 1_000_000
    max_output_tokens_per_call: int = 8192
    max_reasoning_steps: int = 100
    max_cost_usd: float = 50.0
    model_calls: int = 0
    provider_attempts: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_steps: int = 0
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        limits = {
            "max_model_calls": self.max_model_calls,
            "max_provider_attempts": self.max_provider_attempts,
            "max_tool_calls": self.max_tool_calls,
            "max_turn_seconds": self.max_turn_seconds,
            "max_tool_seconds": self.max_tool_seconds,
            "max_tool_settlement_seconds": self.max_tool_settlement_seconds,
            "max_tool_output_bytes": self.max_tool_output_bytes,
            "max_model_output_bytes_per_call": self.max_model_output_bytes_per_call,
            "max_context_bytes": self.max_context_bytes,
            "proactive_context_bytes": self.proactive_context_bytes,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "max_output_tokens_per_call": self.max_output_tokens_per_call,
            "max_reasoning_steps": self.max_reasoning_steps,
            "max_cost_usd": self.max_cost_usd,
        }
        if any(value <= 0 for value in limits.values()):
            raise ValueError("task budget limits must be positive")

    def consume_model_call(self) -> None:
        if self.model_calls >= self.max_model_calls:
            raise BudgetExceededError("model call budget exhausted")
        self.model_calls += 1

    def consume_tool_call(self) -> None:
        if self.tool_calls >= self.max_tool_calls:
            raise BudgetExceededError("tool call budget exhausted")
        self.tool_calls += 1

    def consume_provider_attempt(self) -> None:
        if self.provider_attempts >= self.max_provider_attempts:
            raise BudgetExceededError("provider attempt budget exhausted")
        self.provider_attempts += 1

    def consume_usage(self, input_tokens: int, output_tokens: int) -> None:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token usage may not be negative")
        next_input = self.input_tokens + input_tokens
        next_output = self.output_tokens + output_tokens
        if next_input > self.max_input_tokens:
            raise BudgetExceededError("input token budget exhausted")
        if next_output > self.max_output_tokens:
            raise BudgetExceededError("output token budget exhausted")
        self.input_tokens = next_input
        self.output_tokens = next_output

    def input_token_allowance(self) -> int:
        remaining = self.max_input_tokens - self.input_tokens
        if remaining <= 0:
            raise BudgetExceededError("input token budget exhausted")
        return remaining

    def output_token_allowance(self) -> int:
        remaining = self.max_output_tokens - self.output_tokens
        if remaining <= 0:
            raise BudgetExceededError("output token budget exhausted")
        return min(remaining, self.max_output_tokens_per_call)

    def consume_reasoning_step(self, steps: int = 1) -> None:
        if steps <= 0:
            raise ValueError("reasoning steps must be positive")
        next_steps = self.reasoning_steps + steps
        if next_steps > self.max_reasoning_steps:
            raise BudgetExceededError("reasoning step quota exhausted")
        self.reasoning_steps = next_steps

    def consume_cost_usd(self, usd: float) -> None:
        if usd < 0:
            raise ValueError("cost cannot be negative")
        next_cost = self.cost_usd + usd
        if next_cost > self.max_cost_usd:
            raise BudgetExceededError("monetary cost budget exhausted")
        self.cost_usd = next_cost
