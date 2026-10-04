from __future__ import annotations

import inspect
import ipaddress
from collections.abc import Awaitable, Callable

from agent_workspace.application.ports import ApprovalDecision
from agent_workspace.config import provider_origin
from agent_workspace.core.models import ApprovalScope, Autonomy, ProviderEgressRequest


class ApprovalRequiredError(RuntimeError):
    """Raised when a non-interactive client cannot complete a required approval."""


class ProviderEgressDeniedError(RuntimeError):
    """Raised before a Provider request when external data transfer is denied."""


type EgressApprovalValue = ApprovalDecision | bool
type EgressApprovalCallback = Callable[
    [ProviderEgressRequest], EgressApprovalValue | Awaitable[EgressApprovalValue]
]


class ProviderEgressPolicy:
    def __init__(
        self,
        endpoint: str,
        autonomy: Autonomy,
        approval_callback: EgressApprovalCallback | None = None,
    ) -> None:
        _, hostname, _ = provider_origin(endpoint)
        self._endpoint = endpoint
        self._autonomy = autonomy
        self._approval_callback = approval_callback
        self._local = _is_loopback(hostname)
        self._session_grants: dict[tuple[str, str], set[str]] = {}

    @property
    def endpoint(self) -> str:
        return self._endpoint

    async def authorize(self, request: ProviderEgressRequest) -> ApprovalDecision:
        if request.endpoint != self._endpoint:
            return ApprovalDecision(False, "Provider endpoint changed after policy creation")
        if self._local:
            return ApprovalDecision(True, "verified loopback Provider is local")
        if self._autonomy is Autonomy.FULL_ACCESS:
            return ApprovalDecision(
                True,
                "Full access mode allows Provider egress without approval; audit recorded",
            )
        if self._autonomy is Autonomy.YOLO:
            return ApprovalDecision(True, "YOLO mode records Provider egress without prompting")

        grant_key = (request.workspace, request.session_id)
        sensitive = any(category.startswith("sensitive_") for category in request.data_categories)
        granted_categories = self._session_grants.get(grant_key, set())
        if not sensitive and set(request.data_categories).issubset(granted_categories):
            return ApprovalDecision(
                True,
                "Provider egress is approved for this session scope",
                ApprovalScope.SESSION,
            )
        if self._approval_callback is None:
            return ApprovalDecision(False, "Provider egress requires explicit approval")

        decision = self._approval_callback(request)
        if inspect.isawaitable(decision):
            decision = await decision
        if isinstance(decision, bool):
            decision = ApprovalDecision(
                decision,
                "Provider egress approved" if decision else "Provider egress denied",
            )
        if not isinstance(decision, ApprovalDecision):
            return ApprovalDecision(False, "egress approval callback returned an invalid result")
        scope = decision.scope
        if scope is None:
            scope = (
                ApprovalScope.SESSION
                if self._autonomy is Autonomy.WORKSPACE
                else ApprovalScope.ONCE
            )
        if sensitive and scope is ApprovalScope.SESSION:
            scope = ApprovalScope.ONCE
        if decision.allowed and scope is ApprovalScope.SESSION:
            self._session_grants.setdefault(grant_key, set()).update(request.data_categories)
        return ApprovalDecision(
            decision.allowed,
            decision.reason,
            scope if decision.allowed else None,
        )


def egress_dry_run(
    endpoint: str,
    autonomy: Autonomy,
    data_categories: tuple[str, ...],
    *,
    workspace: str,
    session_id: str,
    granted_categories: frozenset[str] = frozenset(),
) -> dict[str, object]:
    """Predict the non-interactive egress decision for a request.

    This helper mirrors :meth:`ProviderEgressPolicy.authorize` without a
    callback, so callers can surface why egress would be blocked before
    constructing a provider request.
    """
    _, hostname, _ = provider_origin(endpoint)
    local = _is_loopback(hostname)
    sensitive = any(category.startswith("sensitive_") for category in data_categories)
    if local:
        return {"allowed": True, "reason": "verified loopback Provider is local"}
    if autonomy is Autonomy.FULL_ACCESS:
        return {
            "allowed": True,
            "reason": "Full access mode allows Provider egress without approval; audit recorded",
        }
    if autonomy is Autonomy.YOLO:
        return {"allowed": True, "reason": "YOLO mode records Provider egress without prompting"}
    if not sensitive and set(data_categories).issubset(granted_categories):
        return {
            "allowed": True,
            "reason": "Provider egress is approved for this session scope",
        }
    return {"allowed": False, "reason": "Provider egress requires explicit approval"}


def _is_loopback(hostname: str) -> bool:
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False
