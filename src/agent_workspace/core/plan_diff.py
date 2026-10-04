"""Plan evolution and re-planning version diff generator."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from agent_workspace.core.plans import PlanStep


@dataclass(frozen=True, slots=True)
class PlanStepDiff:
    step_id: str
    change_type: str  # "added", "removed", "modified", "unchanged"
    old_step: PlanStep | None
    new_step: PlanStep | None
    changed_fields: tuple[str, ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "change_type": self.change_type,
            "old_step": self.old_step.to_document() if self.old_step else None,
            "new_step": self.new_step.to_document() if self.new_step else None,
            "changed_fields": list(self.changed_fields),
        }


@dataclass(frozen=True, slots=True)
class PlanDiffReport:
    goal_id: str
    added_count: int
    removed_count: int
    modified_count: int
    unchanged_count: int
    diffs: tuple[PlanStepDiff, ...]

    @property
    def has_changes(self) -> bool:
        return self.added_count > 0 or self.removed_count > 0 or self.modified_count > 0

    def to_document(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "has_changes": self.has_changes,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "modified_count": self.modified_count,
            "unchanged_count": self.unchanged_count,
            "diffs": [d.to_document() for d in self.diffs],
        }

    def to_markdown(self) -> str:
        """Render a readable markdown diff table."""
        lines = [
            f"### Plan Evolution Diff (Goal: {self.goal_id or 'all'})",
            (
                f"**Summary**: +{self.added_count} added, "
                f"~{self.modified_count} modified, -{self.removed_count} removed"
            ),
            "",
            "| Change | Step ID | Title | Status | Details |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        badge_map = {
            "added": "🟢 `ADDED`",
            "modified": "🟡 `MODIFIED`",
            "removed": "🔴 `REMOVED`",
            "unchanged": "⚪ `UNCHANGED`",
        }
        for d in self.diffs:
            badge = badge_map.get(d.change_type, d.change_type)
            title = d.new_step.title if d.new_step else (d.old_step.title if d.old_step else "")
            status = (
                d.new_step.status.value
                if d.new_step
                else (d.old_step.status.value if d.old_step else "")
            )
            details = f"Changed: {', '.join(d.changed_fields)}" if d.changed_fields else "-"
            lines.append(f"| {badge} | `{d.step_id}` | {title} | `{status}` | {details} |")
        return "\n".join(lines)


def diff_plan_steps(
    old_steps: Sequence[PlanStep],
    new_steps: Sequence[PlanStep],
    goal_id: str = "",
) -> PlanDiffReport:
    """Compare two snapshots of plan steps and compute structural diffs."""
    old_map = {s.id: s for s in old_steps}
    new_map = {s.id: s for s in new_steps}

    all_ids = list(dict.fromkeys([s.id for s in old_steps] + [s.id for s in new_steps]))
    diffs: list[PlanStepDiff] = []
    added = 0
    removed = 0
    modified = 0
    unchanged = 0

    for sid in all_ids:
        o = old_map.get(sid)
        n = new_map.get(sid)

        if o is None and n is not None:
            added += 1
            diffs.append(
                PlanStepDiff(
                    step_id=sid,
                    change_type="added",
                    old_step=None,
                    new_step=n,
                    changed_fields=(),
                )
            )
        elif o is not None and n is None:
            removed += 1
            diffs.append(
                PlanStepDiff(
                    step_id=sid,
                    change_type="removed",
                    old_step=o,
                    new_step=None,
                    changed_fields=(),
                )
            )
        elif o is not None and n is not None:
            changed: list[str] = []
            if o.title != n.title:
                changed.append("title")
            if o.status != n.status:
                changed.append("status")
            if o.position != n.position:
                changed.append("position")
            if o.parent_step_id != n.parent_step_id:
                changed.append("parent_step_id")

            if changed:
                modified += 1
                diffs.append(
                    PlanStepDiff(
                        step_id=sid,
                        change_type="modified",
                        old_step=o,
                        new_step=n,
                        changed_fields=tuple(changed),
                    )
                )
            else:
                unchanged += 1
                diffs.append(
                    PlanStepDiff(
                        step_id=sid,
                        change_type="unchanged",
                        old_step=o,
                        new_step=n,
                        changed_fields=(),
                    )
                )

    return PlanDiffReport(
        goal_id=goal_id,
        added_count=added,
        removed_count=removed,
        modified_count=modified,
        unchanged_count=unchanged,
        diffs=tuple(diffs),
    )
