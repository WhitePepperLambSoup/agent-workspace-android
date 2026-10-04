"""Tool output context triage and compaction to preserve token budget."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TriagedOutput:
    text: str
    original_bytes: int
    triaged_bytes: int
    is_triaged: bool
    head_lines: int
    tail_lines: int
    omitted_lines: int
    omitted_bytes: int
    spillover_artifact_id: str | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "original_bytes": self.original_bytes,
            "triaged_bytes": self.triaged_bytes,
            "is_triaged": self.is_triaged,
            "head_lines": self.head_lines,
            "tail_lines": self.tail_lines,
            "omitted_lines": self.omitted_lines,
            "omitted_bytes": self.omitted_bytes,
            "spillover_artifact_id": self.spillover_artifact_id,
        }


class ContextTriagePolicy:
    """Policy defining when and how to triage large tool outputs."""

    def __init__(
        self,
        max_chars: int = 4000,
        head_line_count: int = 25,
        tail_line_count: int = 25,
    ) -> None:
        if max_chars <= 0 or head_line_count < 0 or tail_line_count < 0:
            raise ValueError("triage policy parameters must be positive")
        self.max_chars = max_chars
        self.head_line_count = head_line_count
        self.tail_line_count = tail_line_count

    def triage(
        self,
        output: str,
        *,
        spillover_artifact_id: str | None = None,
    ) -> TriagedOutput:
        """Triage output text if it exceeds max_chars."""
        raw_bytes = len(output.encode("utf-8"))
        if len(output) <= self.max_chars:
            return TriagedOutput(
                text=output,
                original_bytes=raw_bytes,
                triaged_bytes=raw_bytes,
                is_triaged=False,
                head_lines=len(output.splitlines()),
                tail_lines=0,
                omitted_lines=0,
                omitted_bytes=0,
                spillover_artifact_id=spillover_artifact_id,
            )

        lines = output.splitlines(keepends=True)
        total_lines = len(lines)

        if total_lines <= self.head_line_count + self.tail_line_count:
            # Output is very long horizontally but has few lines
            head_chars = self.max_chars // 2
            tail_chars = self.max_chars // 2
            omitted_char_count = len(output) - (head_chars + tail_chars)
            triaged_text = (
                f"{output[:head_chars]}\n"
                f"[... {omitted_char_count} characters omitted to preserve context budget ...]\n"
                f"{output[-tail_chars:]}"
            )
            triaged_bytes = len(triaged_text.encode("utf-8"))
            return TriagedOutput(
                text=triaged_text,
                original_bytes=raw_bytes,
                triaged_bytes=triaged_bytes,
                is_triaged=True,
                head_lines=total_lines,
                tail_lines=0,
                omitted_lines=0,
                omitted_bytes=raw_bytes - triaged_bytes,
                spillover_artifact_id=spillover_artifact_id,
            )

        head = lines[: self.head_line_count]
        tail = lines[-self.tail_line_count :] if self.tail_line_count > 0 else []
        omitted = lines[
            self.head_line_count : -self.tail_line_count if self.tail_line_count > 0 else None
        ]

        omitted_lines = len(omitted)
        omitted_bytes = sum(len(line.encode("utf-8")) for line in omitted)

        artifact_notice = (
            f" Full output archived in artifact '{spillover_artifact_id}'."
            if spillover_artifact_id
            else ""
        )
        notice = (
            f"\n[... {omitted_lines} lines ({omitted_bytes} bytes) omitted.{artifact_notice} ...]\n"
        )

        triaged_text = "".join(head) + notice + "".join(tail)
        triaged_bytes = len(triaged_text.encode("utf-8"))

        return TriagedOutput(
            text=triaged_text,
            original_bytes=raw_bytes,
            triaged_bytes=triaged_bytes,
            is_triaged=True,
            head_lines=len(head),
            tail_lines=len(tail),
            omitted_lines=omitted_lines,
            omitted_bytes=omitted_bytes,
            spillover_artifact_id=spillover_artifact_id,
        )


def triage_tool_output(
    output: str,
    max_chars: int = 4000,
    head_line_count: int = 25,
    tail_line_count: int = 25,
    spillover_artifact_id: str | None = None,
) -> TriagedOutput:
    """Convenience function to triage large tool output."""
    policy = ContextTriagePolicy(
        max_chars=max_chars,
        head_line_count=head_line_count,
        tail_line_count=tail_line_count,
    )
    return policy.triage(output, spillover_artifact_id=spillover_artifact_id)
