"""Sub-agent task handoff classification and contextual data sanitization."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from agent_workspace.core.models import ChatMessage
from agent_workspace.core.secret_redactor import redact_sensitive_text


class HandoffSecurityLevel(IntEnum):
    PUBLIC = 1
    INTERNAL = 2
    RESTRICTED = 3
    CONFIDENTIAL = 4


@dataclass(frozen=True, slots=True)
class SanitizedHandoff:
    original_count: int
    sanitized_messages: tuple[ChatMessage, ...]
    redacted_blocks_count: int
    clearance_level: HandoffSecurityLevel

    def to_document(self) -> dict[str, Any]:
        return {
            "original_count": self.original_count,
            "sanitized_count": len(self.sanitized_messages),
            "redacted_blocks_count": self.redacted_blocks_count,
            "clearance_level": self.clearance_level.name,
        }


class HandoffClassifier:
    """Classifies message sensitivity and sanitizes handoffs to sub-agents."""

    @staticmethod
    def classify_text(text: str) -> HandoffSecurityLevel:
        """Heuristically classify sensitivity of text."""
        lowered = text.lower()
        if any(w in lowered for w in ("confidential", "private key", "master_key", "password=")):
            return HandoffSecurityLevel.CONFIDENTIAL
        if any(w in lowered for w in ("bearer ", "api_key", "internal token", "secret")):
            return HandoffSecurityLevel.RESTRICTED
        if any(w in lowered for w in ("workspace", "session", "todo", "file:", "path:")):
            return HandoffSecurityLevel.INTERNAL
        return HandoffSecurityLevel.PUBLIC

    @classmethod
    def sanitize_handoff(
        cls,
        messages: Sequence[ChatMessage],
        target_clearance: HandoffSecurityLevel,
    ) -> SanitizedHandoff:
        """Sanitize message context to ensure it does not exceed target_clearance."""
        sanitized: list[ChatMessage] = []
        redactions = 0

        for msg in messages:
            level = cls.classify_text(msg.content)
            if level > target_clearance:
                # Need redaction or redaction of confidential blocks
                redacted_res = redact_sensitive_text(msg.content)
                cleaned_content = redacted_res.redacted_text
                if (
                    level is HandoffSecurityLevel.CONFIDENTIAL
                    and target_clearance < HandoffSecurityLevel.RESTRICTED
                ):
                    cleaned_content = "[Content omitted: exceeds sub-agent clearance level]"
                redactions += 1
                sanitized.append(
                    ChatMessage(
                        role=msg.role,
                        content=cleaned_content,
                        trust=msg.trust,
                    )
                )
            else:
                sanitized.append(msg)

        return SanitizedHandoff(
            original_count=len(messages),
            sanitized_messages=tuple(sanitized),
            redacted_blocks_count=redactions,
            clearance_level=target_clearance,
        )
