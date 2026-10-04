"""Configurable outbound content redaction.

The redactor is conservative: it only matches explicit high-signal patterns
and never attempts to infer arbitrary secrets. Callers choose whether to
redact before display, before analytics export, or before logging provider
digests.
"""

from __future__ import annotations

import re
from typing import Any

_API_KEY_PATTERN = re.compile(
    r"(?i)\b(sk-[A-Za-z0-9_\-]{16,}|AIza[0-9A-Za-z_\-]{30,}|"
    r"Bearer\s+[A-Za-z0-9._\-]{20,})\b"
)
_PASSWORD_PATTERN = re.compile(
    r"(?i)\b(password|passwd|api[_-]?key|secret|token)\b(\s*[=:]\s*)([^\s,;]{6,})"
)
_AWS_KEY_PATTERN = re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")
_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END "
    r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    re.DOTALL,
)
_REDACTED = "[REDACTED]"


class Redactor:
    """Pattern-based redactor with enabled rule selection."""

    def __init__(self, *, enabled: bool = True, redact_private_keys: bool = True) -> None:
        self.enabled = enabled
        self.redact_private_keys = redact_private_keys

    def redact(self, text: str) -> str:
        if not self.enabled:
            return text
        redacted = _API_KEY_PATTERN.sub(_REDACTED, text)
        redacted = _PASSWORD_PATTERN.sub(
            lambda match: f"{match.group(1)}{match.group(2)}{_REDACTED}", redacted
        )
        redacted = _AWS_KEY_PATTERN.sub(_REDACTED, redacted)
        if self.redact_private_keys:
            redacted = _PRIVATE_KEY_PATTERN.sub(_REDACTED, redacted)
        return redacted

    def redact_mapping(self, value: dict[str, Any]) -> dict[str, Any]:
        return {key: self.redact_value(item) for key, item in value.items()}

    def redact_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, dict):
            return self.redact_mapping(value)
        if isinstance(value, list):
            return [self.redact_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.redact_value(item) for item in value)
        return value


def default_redactor() -> Redactor:
    return Redactor()


__all__ = ["Redactor", "default_redactor"]
