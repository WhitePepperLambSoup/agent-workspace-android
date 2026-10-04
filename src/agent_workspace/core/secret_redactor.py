"""In-flight sensitive credential redactor for model prompts and egress."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

# Rules: (rule_name, compiled_regex, replacement_func_or_str)
_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("aws_access_key", re.compile(r"\b(AKIA[0-9A-Z]{16})\b"), "[REDACTED_AWS_KEY]"),
    (
        "private_key",
        re.compile(
            r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?"
            r"-----END (RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (
        "generic_api_key",
        re.compile(
            r"""(?i)\b(?:api[_-]?key|apikey|secret[_-]?key)\b\s*[:=]\s*["']([A-Za-z0-9_\-]{16,})["']"""
        ),
        """api_key="[REDACTED_API_KEY]\"""",
    ),
    (
        "password_assignment",
        re.compile(r"""(?i)\b(?:password|passwd)\s*=\s*["']([^"']{6,})["']"""),
        """password="[REDACTED_PASSWORD]\"""",
    ),
    (
        "bearer_token",
        re.compile(r"\bBearer\s+([A-Za-z0-9_\-\.]{20,})\b"),
        "Bearer [REDACTED_TOKEN]",
    ),
)


@dataclass(frozen=True, slots=True)
class RedactionRecord:
    rule: str
    match_hash: str
    start: int
    end: int

    def to_document(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "match_hash": self.match_hash,
            "start": self.start,
            "end": self.end,
        }


@dataclass(frozen=True, slots=True)
class RedactionResult:
    redacted_text: str
    records: tuple[RedactionRecord, ...]
    is_modified: bool

    def to_document(self) -> dict[str, Any]:
        return {
            "is_modified": self.is_modified,
            "redactions_count": len(self.records),
            "records": [r.to_document() for r in self.records],
        }


def redact_sensitive_text(text: str) -> RedactionResult:
    """Redact known sensitive tokens and credentials from text."""
    if not text:
        return RedactionResult(text, (), False)

    current_text = text
    records: list[RedactionRecord] = []

    for rule, pattern, replacement in _PATTERNS:
        # Find matches iteratively
        matches = list(pattern.finditer(current_text))
        if not matches:
            continue

        # Replace in reverse order to preserve string indices
        for match in reversed(matches):
            raw_match = match.group(0)
            match_hash = hashlib.sha256(raw_match.encode("utf-8")).hexdigest()[:16]
            start, end = match.span()

            records.append(
                RedactionRecord(
                    rule=rule,
                    match_hash=match_hash,
                    start=start,
                    end=end,
                )
            )

        current_text = pattern.sub(replacement, current_text)

    # Sort records in forward chronological order
    records.sort(key=lambda r: r.start)

    return RedactionResult(
        redacted_text=current_text,
        records=tuple(records),
        is_modified=len(records) > 0,
    )
