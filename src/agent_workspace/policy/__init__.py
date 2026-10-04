"""Authorization and approval policies."""

from agent_workspace.core.autonomy_escalation import (
    AutonomyEscalationError,
    AutonomyEscalationPolicy,
    AutonomyEscalationRule,
)

from .argument_rules import ToolArgumentPolicy, ToolArgumentRule, ToolArgumentRuleError
from .egress import (
    ApprovalRequiredError,
    EgressApprovalCallback,
    ProviderEgressDeniedError,
    ProviderEgressPolicy,
    egress_dry_run,
)
from .permissions import (
    ApprovalCallback,
    ApprovalResult,
    ExtensionApprovalCallback,
    ExtensionApprovalRequiredError,
    WorkspaceExtensionRequest,
    WorkspacePolicy,
    build_custom_tool_extension_request,
    build_mcp_extension_request,
    compute_extension_digest,
)
from .spend_approval import SpendApprovalPolicy, SpendEvaluation

__all__ = [
    "ApprovalCallback",
    "ApprovalRequiredError",
    "ApprovalResult",
    "AutonomyEscalationError",
    "AutonomyEscalationPolicy",
    "AutonomyEscalationRule",
    "EgressApprovalCallback",
    "ExtensionApprovalCallback",
    "ExtensionApprovalRequiredError",
    "ProviderEgressDeniedError",
    "ProviderEgressPolicy",
    "SpendApprovalPolicy",
    "SpendEvaluation",
    "ToolArgumentPolicy",
    "ToolArgumentRule",
    "ToolArgumentRuleError",
    "WorkspaceExtensionRequest",
    "WorkspacePolicy",
    "build_custom_tool_extension_request",
    "build_mcp_extension_request",
    "compute_extension_digest",
    "egress_dry_run",
]
