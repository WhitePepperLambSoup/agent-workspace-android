"""Static linter and validation for prompt templates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Identifies standard {placeholder} format while ignoring escaped {{ and }}
_PLACEHOLDER_RE = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")
_INJECTION_TOKENS = frozenset(
    {
        "<|im_start|>",
        "<|im_end|>",
        "<|endoftext|>",
        "<|system|>",
        "<|user|>",
        "<|assistant|>",
        "[INST]",
        "[/INST]",
        "<<SYS>>",
        "<</SYS>>",
    }
)


@dataclass(frozen=True, slots=True)
class PromptLintIssue:
    severity: str  # "error", "warning"
    rule: str
    message: str
    line: int = 1

    def to_document(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "rule": self.rule,
            "message": self.message,
            "line": self.line,
        }


@dataclass(frozen=True, slots=True)
class PromptLintReport:
    template_length: int
    variables_found: tuple[str, ...]
    issues: tuple[PromptLintIssue, ...]
    is_valid: bool

    def to_document(self) -> dict[str, Any]:
        return {
            "template_length": self.template_length,
            "variables_found": list(self.variables_found),
            "issues": [issue.to_document() for issue in self.issues],
            "is_valid": self.is_valid,
        }


def lint_prompt_template(
    template: str,
    *,
    required_variables: set[str] | None = None,
    allowed_variables: set[str] | None = None,
    max_length: int = 128 * 1024,
) -> PromptLintReport:
    """Lint a prompt template for syntax, variable matching, and injection markers."""
    issues: list[PromptLintIssue] = []

    if len(template) > max_length:
        issues.append(
            PromptLintIssue(
                severity="error",
                rule="max_length_exceeded",
                message=f"Template length ({len(template)}) exceeds maximum allowed ({max_length})",
            )
        )

    # Check for raw injection tokens
    for token in _INJECTION_TOKENS:
        if token.lower() in template.lower():
            issues.append(
                PromptLintIssue(
                    severity="error",
                    rule="forbidden_special_token",
                    message=f"Template contains raw special model token: {token}",
                )
            )

    # Check unescaped braces and extract variables
    lines = template.splitlines()
    variables_found: list[str] = []

    # Check unclosed or unbalanced braces
    brace_depth = 0
    for line_idx, line in enumerate(lines, start=1):
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "{" and i + 1 < len(line) and line[i + 1] == "{":
                # Escaped open brace {{
                i += 2
                continue
            if ch == "}" and i + 1 < len(line) and line[i + 1] == "}":
                # Escaped close brace }}
                i += 2
                continue
            if ch == "{":
                brace_depth += 1
                if brace_depth > 1:
                    issues.append(
                        PromptLintIssue(
                            severity="error",
                            rule="nested_braces",
                            message=f"Nested '{'{'}' not allowed in template placeholder",
                            line=line_idx,
                        )
                    )
            elif ch == "}":
                brace_depth -= 1
                if brace_depth < 0:
                    issues.append(
                        PromptLintIssue(
                            severity="error",
                            rule="unmatched_closing_brace",
                            message="Found closing '}' without matching opening '{'",
                            line=line_idx,
                        )
                    )
                    brace_depth = 0
            i += 1

    if brace_depth > 0:
        issues.append(
            PromptLintIssue(
                severity="error",
                rule="unclosed_brace",
                message="Template has unclosed '{' without matching '}'",
                line=len(lines),
            )
        )

    # Find placeholders
    matches = _PLACEHOLDER_RE.findall(template)
    for var in matches:
        if var not in variables_found:
            variables_found.append(var)

    # Check against allowed variables
    if allowed_variables is not None:
        for var in variables_found:
            if var not in allowed_variables:
                issues.append(
                    PromptLintIssue(
                        severity="error",
                        rule="undeclared_variable",
                        message=f"Placeholder '{var}' is not in allowed variables list",
                    )
                )

    # Check required variables
    if required_variables is not None:
        for req in required_variables:
            if req not in variables_found:
                issues.append(
                    PromptLintIssue(
                        severity="error",
                        rule="missing_required_variable",
                        message=f"Required variable '{req}' was not found in template",
                    )
                )

    has_error = any(issue.severity == "error" for issue in issues)
    return PromptLintReport(
        template_length=len(template),
        variables_found=tuple(variables_found),
        issues=tuple(issues),
        is_valid=not has_error,
    )
