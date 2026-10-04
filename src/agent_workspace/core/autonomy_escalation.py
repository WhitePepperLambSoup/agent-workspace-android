"""Conditional autonomy escalation rules.

Rules never make the default policy more permissive on their own; they only
select a different, explicitly configured autonomy level for a tool after a
documented condition is met. This keeps every upgrade/downgrade auditable and
reversible by removing the rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_workspace.core.models import Autonomy


class AutonomyEscalationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AutonomyEscalationRule:
    id: str
    tool_names: frozenset[str]
    target_autonomy: Autonomy
    min_grants: int = 1
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.id:
            raise AutonomyEscalationError("autonomy rule id may not be empty")
        if not self.tool_names:
            raise AutonomyEscalationError("autonomy rule must target at least one tool")
        if self.min_grants < 1:
            raise AutonomyEscalationError("autonomy rule min_grants must be positive")

    def matches(self, tool_name: str, granted_tool_names: frozenset[str]) -> bool:
        return (
            self.enabled
            and tool_name in self.tool_names
            and len(granted_tool_names & self.tool_names) >= self.min_grants
        )


class AutonomyEscalationPolicy:
    """Ordered rules; the first match wins."""

    def __init__(self, rules: tuple[AutonomyEscalationRule, ...] = ()) -> None:
        self._rules = tuple(rules)
        seen: set[str] = set()
        for rule in self._rules:
            if rule.id in seen:
                raise AutonomyEscalationError(f"duplicate autonomy rule id: {rule.id}")
            seen.add(rule.id)

    def effective_autonomy(
        self,
        current: Autonomy,
        tool_name: str,
        granted_tool_names: frozenset[str],
    ) -> Autonomy:
        for rule in self._rules:
            if rule.matches(tool_name, granted_tool_names):
                return rule.target_autonomy
        return current

    def rules(self) -> tuple[AutonomyEscalationRule, ...]:
        return self._rules

    def to_document(self) -> list[dict[str, Any]]:
        return [
            {
                "id": rule.id,
                "tool_names": sorted(rule.tool_names),
                "target_autonomy": rule.target_autonomy.value,
                "min_grants": rule.min_grants,
                "enabled": rule.enabled,
            }
            for rule in self._rules
        ]

    @classmethod
    def from_document(cls, value: object) -> AutonomyEscalationPolicy:
        if not isinstance(value, list):
            raise AutonomyEscalationError("autonomy escalation policy must be a list")
        rules: list[AutonomyEscalationRule] = []
        for item in value:
            if not isinstance(item, dict):
                raise AutonomyEscalationError("autonomy rule entries must be objects")
            try:
                rules.append(
                    AutonomyEscalationRule(
                        id=str(item["id"]),
                        tool_names=frozenset(str(name) for name in item["tool_names"]),
                        target_autonomy=Autonomy(str(item["target_autonomy"])),
                        min_grants=int(item.get("min_grants", 1)),
                        enabled=bool(item.get("enabled", True)),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise AutonomyEscalationError("autonomy rule entry is invalid") from exc
        return cls(tuple(rules))


__all__ = [
    "AutonomyEscalationError",
    "AutonomyEscalationPolicy",
    "AutonomyEscalationRule",
]
