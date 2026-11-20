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
    DEFAULT_YOLO_RULES,
    WORKSPACE_FILE_KINDS,
    ApprovalCallback,
    ApprovalResult,
    ExtensionApprovalCallback,
    ExtensionApprovalRequiredError,
    WorkspaceExtensionRequest,
    WorkspacePolicy,
    YoloRules,
    build_custom_tool_extension_request,
    build_mcp_extension_request,
    compute_extension_digest,
    workspace_file_decision,
    workspace_file_requests,
)
from .spend_approval import SpendApprovalPolicy, SpendEvaluation

__all__ = [
    "DEFAULT_YOLO_RULES",
    "WORKSPACE_FILE_KINDS",
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
    "YoloRules",
    "build_custom_tool_extension_request",
    "build_mcp_extension_request",
    "compute_extension_digest",
    "egress_dry_run",
    "workspace_file_decision",
    "workspace_file_requests",
]
