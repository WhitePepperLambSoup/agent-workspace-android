"""Policy for checking spend thresholds and triggering approvals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_workspace.policy.egress import ApprovalRequiredError


@dataclass(frozen=True, slots=True)
class SpendEvaluation:
    requires_approval: bool
    reason: str
    projected_session_spend: float
    threshold: float

    def to_document(self) -> dict[str, Any]:
        return {
            "requires_approval": self.requires_approval,
            "reason": self.reason,
            "projected_session_spend": round(self.projected_session_spend, 6),
            "threshold": round(self.threshold, 6),
        }


class SpendApprovalPolicy:
    """Evaluates whether prospective model execution costs exceed human approval thresholds."""

    def __init__(
        self,
        session_spend_threshold_usd: float = 2.0,
        turn_spend_threshold_usd: float = 0.5,
    ) -> None:
        if session_spend_threshold_usd <= 0 or turn_spend_threshold_usd <= 0:
            raise ValueError("spend approval thresholds must be positive")
        self.session_spend_threshold_usd = session_spend_threshold_usd
        self.turn_spend_threshold_usd = turn_spend_threshold_usd

    def evaluate(
        self,
        current_session_spend: float,
        estimated_turn_spend: float,
    ) -> SpendEvaluation:
        """Evaluate whether spend triggers human-in-the-loop confirmation."""
        if current_session_spend < 0 or estimated_turn_spend < 0:
            raise ValueError("spend amounts cannot be negative")

        projected = current_session_spend + estimated_turn_spend

        if estimated_turn_spend >= self.turn_spend_threshold_usd:
            return SpendEvaluation(
                requires_approval=True,
                reason=(
                    f"Single turn estimated cost (${estimated_turn_spend:.4f}) exceeds "
                    f"turn threshold (${self.turn_spend_threshold_usd:.4f})"
                ),
                projected_session_spend=projected,
                threshold=self.turn_spend_threshold_usd,
            )

        if projected >= self.session_spend_threshold_usd:
            return SpendEvaluation(
                requires_approval=True,
                reason=(
                    f"Projected session cost (${projected:.4f}) exceeds "
                    f"session threshold (${self.session_spend_threshold_usd:.4f})"
                ),
                projected_session_spend=projected,
                threshold=self.session_spend_threshold_usd,
            )

        return SpendEvaluation(
            requires_approval=False,
            reason="Within budget thresholds",
            projected_session_spend=projected,
            threshold=self.session_spend_threshold_usd,
        )

    def enforce(
        self,
        current_session_spend: float,
        estimated_turn_spend: float,
    ) -> SpendEvaluation:
        """Enforce approval policy, raising ApprovalRequiredError if threshold exceeded."""
        eval_result = self.evaluate(current_session_spend, estimated_turn_spend)
        if eval_result.requires_approval:
            raise ApprovalRequiredError(eval_result.reason)
        return eval_result
