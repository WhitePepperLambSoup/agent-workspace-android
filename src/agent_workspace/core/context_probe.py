"""Model context window probe.

Without a tokenizer dependency the probe uses a conservative estimator:
each ASCII word or number counts as one token and each non-ASCII character
(CJK/emoji) counts as one token. The report tells callers whether a prompt
assembly fits a model's context window and how many completion tokens remain
after reserving a configurable output budget.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[^\x00-\x7f]")


@dataclass(frozen=True, slots=True)
class ContextWindowProbe:
    model: str
    context_limit_tokens: int
    input_tokens: int
    reserved_output_tokens: int
    available_completion_tokens: int
    headroom_tokens: int
    fits: bool

    @property
    def utilization(self) -> float:
        if self.context_limit_tokens <= 0:
            return 0.0
        return round(self.input_tokens / self.context_limit_tokens, 4)

    def to_document(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "context_limit_tokens": self.context_limit_tokens,
            "input_tokens": self.input_tokens,
            "reserved_output_tokens": self.reserved_output_tokens,
            "available_completion_tokens": self.available_completion_tokens,
            "headroom_tokens": self.headroom_tokens,
            "fits": self.fits,
            "utilization": self.utilization,
        }


def estimate_tokens(text: str) -> int:
    if not isinstance(text, str):
        raise ValueError("probe text must be a string")
    return len(_TOKEN_PATTERN.findall(text))


def context_window_probe(
    model: str,
    context_limit_tokens: int,
    *,
    system_prompt: str = "",
    history: list[str] | tuple[str, ...] = (),
    tool_schemas: list[str] | tuple[str, ...] = (),
    reserved_output_tokens: int = 1024,
) -> ContextWindowProbe:
    if not isinstance(model, str) or not model:
        raise ValueError("model name may not be empty")
    if type(context_limit_tokens) is not int or isinstance(context_limit_tokens, bool):
        raise ValueError("context_limit_tokens must be an integer")
    if context_limit_tokens <= 0:
        raise ValueError("context_limit_tokens must be positive")
    if reserved_output_tokens < 0:
        raise ValueError("reserved_output_tokens must be non-negative")
    input_tokens = (
        estimate_tokens(system_prompt)
        + sum(estimate_tokens(part) for part in history)
        + sum(estimate_tokens(schema) for schema in tool_schemas)
    )
    available = max(0, context_limit_tokens - input_tokens - reserved_output_tokens)
    return ContextWindowProbe(
        model=model,
        context_limit_tokens=context_limit_tokens,
        input_tokens=input_tokens,
        reserved_output_tokens=reserved_output_tokens,
        available_completion_tokens=available,
        headroom_tokens=max(0, context_limit_tokens - input_tokens),
        fits=input_tokens + reserved_output_tokens <= context_limit_tokens,
    )


__all__ = ["ContextWindowProbe", "context_window_probe", "estimate_tokens"]
