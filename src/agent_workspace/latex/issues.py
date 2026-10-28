"""One problem found in a document: a compile error or warning, or a finding of a source rule."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["error", "warning", "info", "suggestion"]
SEVERITY_ORDER: dict[str, int] = {"error": 0, "warning": 1, "info": 2, "suggestion": 3}


@dataclass
class Issue:
    severity: Severity
    # What kind of problem: a log code (``undefined_control_sequence``) or a rule id (``percent``).
    code: str
    # One line in English, for the agent and for logs; the window words it from code and params.
    message: str
    source: Literal["compile", "rule"] = "compile"
    file: str | None = None
    line: int | None = None
    column: int | None = None
    params: dict[str, Any] = field(default_factory=dict)
    # The log lines the problem came from (compile problems only).
    raw: str | None = None
    # The source rule that found it, so it can be switched off or fixed.
    rule: str | None = None
    # Whether the rule can rewrite the file itself.
    fixable: bool = False

    def to_dict(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "source": self.source,
        }
        for key in ("file", "line", "column"):
            value = getattr(self, key)
            if value is not None:
                document[key] = value
        if self.params:
            document["params"] = self.params
        if self.raw:
            document["raw"] = self.raw[:4000]
        if self.rule:
            document["rule"] = self.rule
        if self.fixable:
            document["fixable"] = True
        return document

    def location(self) -> str:
        if not self.file:
            return ""
        return f"{self.file}:{self.line}" if self.line else self.file


def sort_issues(issues: list[Issue]) -> list[Issue]:
    """Errors first, then by file and line; stable for problems on the same line."""
    return sorted(
        issues,
        key=lambda issue: (
            SEVERITY_ORDER.get(issue.severity, 9),
            issue.file is None,
            issue.file or "",
            issue.line or 0,
        ),
    )
