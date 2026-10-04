"""Token budget arbiter for tiered context retention and compaction."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from agent_workspace.core.budgets import BudgetExceededError
from agent_workspace.core.models import ChatMessage, Role


class ContextTier(StrEnum):
    SYSTEM_CORE = "system_core"
    GOAL_SPEC = "goal_spec"
    TOOL_RESULT = "tool_result"
    HISTORY_TURNS = "history_turns"


def estimate_tokens(text: str) -> int:
    """Fast estimate of tokens from text length."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


@dataclass(frozen=True, slots=True)
class TieredMessage:
    tier: ContextTier
    role: Role
    content: str
    priority: int = 0
    estimated_tokens: int = 0
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.estimated_tokens <= 0 and self.content:
            object.__setattr__(self, "estimated_tokens", estimate_tokens(self.content))

    def to_chat_message(self) -> ChatMessage:
        return ChatMessage(role=self.role, content=self.content)


@dataclass(frozen=True, slots=True)
class ArbitrationResult:
    retained: tuple[TieredMessage, ...]
    shed: tuple[TieredMessage, ...]
    tier_usage: dict[str, int]
    total_tokens: int
    budget: int
    shed_count: int
    compaction_required: bool

    def to_document(self) -> dict[str, Any]:
        return {
            "tier_usage": self.tier_usage,
            "total_tokens": self.total_tokens,
            "budget": self.budget,
            "shed_count": self.shed_count,
            "compaction_required": self.compaction_required,
            "retained_count": len(self.retained),
        }


class TokenBudgetArbiter:
    """Arbitrates context messages across priority tiers within a token budget."""

    def __init__(self, max_tokens: int) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        self._max_tokens = max_tokens

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    def arbitrate(self, messages: Sequence[TieredMessage]) -> ArbitrationResult:
        """Arbitrate tiered messages to fit within self._max_tokens."""
        total_initial = sum(m.estimated_tokens for m in messages)
        tier_counts: dict[str, int] = {tier.value: 0 for tier in ContextTier}
        for m in messages:
            tier_counts[m.tier.value] += m.estimated_tokens

        if total_initial <= self._max_tokens:
            return ArbitrationResult(
                retained=tuple(messages),
                shed=(),
                tier_usage=tier_counts,
                total_tokens=total_initial,
                budget=self._max_tokens,
                shed_count=0,
                compaction_required=False,
            )

        core_tokens = sum(
            m.estimated_tokens
            for m in messages
            if m.tier in (ContextTier.SYSTEM_CORE, ContextTier.GOAL_SPEC)
        )
        if core_tokens > self._max_tokens:
            msg = (
                f"Core system and goal context ({core_tokens} tokens) "
                f"exceeds budget ({self._max_tokens})"
            )
            raise BudgetExceededError(msg)

        shed_set: set[int] = set()
        current_total = total_initial

        # Shed history turns first (by priority ascending, then oldest first)
        history_candidates = sorted(
            [item for item in enumerate(messages) if item[1].tier is ContextTier.HISTORY_TURNS],
            key=lambda item: (item[1].priority, item[0]),
        )
        for idx, item in history_candidates:
            if current_total <= self._max_tokens:
                break
            shed_set.add(idx)
            current_total -= item.estimated_tokens

        # Shed tool results if still over budget
        if current_total > self._max_tokens:
            tool_candidates = sorted(
                [item for item in enumerate(messages) if item[1].tier is ContextTier.TOOL_RESULT],
                key=lambda item: (item[1].priority, item[0]),
            )
            for idx, item in tool_candidates:
                if current_total <= self._max_tokens:
                    break
                shed_set.add(idx)
                current_total -= item.estimated_tokens

        if current_total > self._max_tokens:
            msg = f"Unable to fit context within budget {self._max_tokens} after shedding"
            raise BudgetExceededError(msg)

        retained: list[TieredMessage] = []
        shed: list[TieredMessage] = []
        final_tier_usage: dict[str, int] = {tier.value: 0 for tier in ContextTier}

        for idx, m in enumerate(messages):
            if idx in shed_set:
                shed.append(m)
            else:
                retained.append(m)
                final_tier_usage[m.tier.value] += m.estimated_tokens

        return ArbitrationResult(
            retained=tuple(retained),
            shed=tuple(shed),
            tier_usage=final_tier_usage,
            total_tokens=sum(m.estimated_tokens for m in retained),
            budget=self._max_tokens,
            shed_count=len(shed),
            compaction_required=len(shed) > 0,
        )
