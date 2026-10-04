"""Pluggable context compaction strategies.

Runner integration can call ``select`` before building a provider request;
strategies return a deterministic slice of the message history and optional
summary instructions. They never mutate history themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agent_workspace.core.models import ChatMessage


class CompactionStrategyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CompactionSelection:
    retained: tuple[ChatMessage, ...]
    dropped: tuple[ChatMessage, ...]
    summary_prompt: str = ""


class CompactionStrategy(Protocol):
    @property
    def name(self) -> str: ...

    def select(
        self,
        messages: tuple[ChatMessage, ...],
        *,
        max_messages: int,
    ) -> CompactionSelection: ...


class DropOldestStrategy:
    """Keep the most recent messages, dropping the oldest first."""

    name = "drop_oldest"

    def select(
        self,
        messages: tuple[ChatMessage, ...],
        *,
        max_messages: int,
    ) -> CompactionSelection:
        if max_messages < 1:
            raise CompactionStrategyError("max_messages must be positive")
        if len(messages) <= max_messages:
            return CompactionSelection(messages, ())
        split = len(messages) - max_messages
        return CompactionSelection(
            retained=messages[split:],
            dropped=messages[:split],
            summary_prompt="Summarize the omitted conversation so future work can continue.",
        )


class RetainRecentTurnsStrategy:
    """Drop whole pairs from the front, keeping recent complete turns."""

    name = "retain_recent_turns"

    def select(
        self,
        messages: tuple[ChatMessage, ...],
        *,
        max_messages: int,
    ) -> CompactionSelection:
        if max_messages < 2:
            raise CompactionStrategyError("max_messages must be at least 2")
        if len(messages) <= max_messages:
            return CompactionSelection(messages, ())
        keep = max_messages if max_messages % 2 == 0 else max_messages - 1
        if keep < 2:
            keep = 2
        split = len(messages) - keep
        return CompactionSelection(
            retained=messages[split:],
            dropped=messages[:split],
            summary_prompt=(
                "Summarize omitted turns as compact user-role context before continuing."
            ),
        )


class CompactionStrategyRegistry:
    def __init__(self, strategies: tuple[CompactionStrategy, ...] = ()) -> None:
        self._strategies: dict[str, CompactionStrategy] = {}
        for strategy in strategies:
            self.register(strategy)

    def register(self, strategy: CompactionStrategy) -> None:
        if strategy.name in self._strategies:
            raise CompactionStrategyError(f"duplicate compaction strategy: {strategy.name}")
        self._strategies[strategy.name] = strategy

    def get(self, name: str) -> CompactionStrategy | None:
        return self._strategies.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(self._strategies)


def default_compaction_registry() -> CompactionStrategyRegistry:
    return CompactionStrategyRegistry((DropOldestStrategy(), RetainRecentTurnsStrategy()))


__all__ = [
    "CompactionSelection",
    "CompactionStrategy",
    "CompactionStrategyError",
    "CompactionStrategyRegistry",
    "DropOldestStrategy",
    "RetainRecentTurnsStrategy",
    "default_compaction_registry",
]
