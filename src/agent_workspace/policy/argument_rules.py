"""Fine-grained tool argument rules.

Rules run before the normal autonomy policy and can only make a request more
restrictive: a matching deny rule rejects the call, while allow rules record a
reason but never bypass the standard policy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class ToolArgumentRuleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ToolArgumentRule:
    id: str
    tool_name: str
    path: str
    pattern: str
    allow: bool = False

    def __post_init__(self) -> None:
        if not self.id or not self.tool_name or not self.path:
            raise ToolArgumentRuleError("rule id, tool_name, and path may not be empty")
        try:
            re.compile(self.pattern)
        except re.error as exc:
            raise ToolArgumentRuleError(f"invalid rule pattern: {exc}") from None

    def matches(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        if tool_name != self.tool_name:
            return False
        value = _value_at_path(arguments, self.path)
        return isinstance(value, str) and re.search(self.pattern, value) is not None


class ToolArgumentPolicy:
    """Ordered, idempotent collection of argument rules."""

    def __init__(self, rules: tuple[ToolArgumentRule, ...] = ()) -> None:
        self._rules: dict[str, ToolArgumentRule] = {}
        for rule in rules:
            self.register(rule)

    def register(self, rule: ToolArgumentRule) -> None:
        if rule.id in self._rules:
            raise ToolArgumentRuleError(f"duplicate argument rule id: {rule.id}")
        self._rules[rule.id] = rule

    def evaluate(self, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str | None]:
        """Return (allowed, denial reason)."""
        for rule in self._rules.values():
            if rule.matches(tool_name, arguments) and not rule.allow:
                return False, f"tool argument denied by rule {rule.id!r}"
        return True, None


def _value_at_path(arguments: dict[str, Any], path: str) -> Any:
    current: Any = arguments
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


__all__ = [
    "ToolArgumentPolicy",
    "ToolArgumentRule",
    "ToolArgumentRuleError",
]
