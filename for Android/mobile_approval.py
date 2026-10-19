"""Explicit approval broker for Android tools and provider egress."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any
from uuid import uuid4

from agent_workspace.application.ports import EventStore
from agent_workspace.core.events import Event


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    request_id: str
    allowed: bool
    scope: str
    task_id: str
    kind: str


@dataclass(slots=True)
class _PendingApproval:
    request_id: str
    task_id: str
    session_id: str
    kind: str
    details: dict[str, Any]
    future: asyncio.Future[ApprovalDecision]


ApprovalRequestListener = Callable[[dict[str, Any]], Awaitable[None] | None]

# Scopes the user can pick on the approval shelf. "task" approves this request and every later
# request of the same task, until it ends, except the tools below.
APPROVAL_SCOPES = frozenset({"once", "session", "task"})
# A task-wide approval never covers deleting files, changing long-term memory (app notes too),
# operating other apps or sending a message as the user: those still ask each time. The exception
# is a task the user started from the phone control panel to operate the phone: there "allow for
# this task" covers its taps and typing (never a reply sent from a notification).
_ALWAYS_ASK_TOOLS = frozenset(
    {"delete_path", "memory_write", "app_note", "android_action", "notification_reply"}
)
_PHONE_CONTROL_TOOLS = frozenset({"android_action"})
# A message sent as the user: approved one at a time, whatever scope is picked (a "session" grant
# would let later replies in the conversation go out unasked).
_ONCE_ONLY_TOOLS = frozenset({"notification_reply"})


class MobileApprovalBroker:
    def __init__(
        self,
        event_store: EventStore,
        *,
        request_listener: ApprovalRequestListener | None = None,
    ) -> None:
        self.event_store = event_store
        self.request_listener = request_listener
        self._active_task_id: str | None = None
        self._active_session_id: str | None = None
        self._trusted_task_id: str | None = None
        self._phone_task_id: str | None = None
        # A task that read instructions in outside content (mobile_injection): nothing is covered.
        self._distrusted: tuple[str, str] | None = None
        self._pending: dict[str, _PendingApproval] = {}

    def set_active_task(self, task_id: str, session_id: str) -> None:
        if not task_id or not session_id:
            raise ValueError("task_id and session_id are required")
        if task_id != self._trusted_task_id:
            self._trusted_task_id = None
        if task_id != self._phone_task_id:
            self._phone_task_id = None
        if self._distrusted and self._distrusted[0] != task_id:
            self._distrusted = None
        self._active_task_id = task_id
        self._active_session_id = session_id

    def clear_active_task(self, task_id: str | None = None) -> None:
        if task_id is not None and task_id != self._active_task_id:
            return
        self._active_task_id = None
        self._active_session_id = None
        self._trusted_task_id = None
        self._phone_task_id = None
        self._distrusted = None

    def distrust(self, task_id: str, reason: str) -> bool:
        """The running task read what looks like instructions to the agent in outside content (a web
        page, a file, a message, the screen): from now on a task-wide or hosted approval covers none of
        its tool calls, each asks the user with the reason, and "allow for this task" acts as once.
        Requests to the model provider stay as approved: they carry no action."""
        if not task_id or task_id != self._active_task_id:
            return False
        self._distrusted = (task_id, reason[:300])
        return True

    def distrusted(self, task_id: str) -> str | None:
        return self._distrusted[1] if self._distrusted and self._distrusted[0] == task_id else None

    def mark_phone_control(self, task_id: str) -> bool:
        """The running task operates the phone for the user (started from the phone control panel)."""
        if not task_id or task_id != self._active_task_id:
            return False
        self._phone_task_id = task_id
        return True

    def trust_active_task(self, task_id: str) -> bool:
        """Grant the "task" scope in advance, as for a schedule the user set up to run alone.

        The always-ask tools still ask. Applies only to the task that is running.
        """
        if not task_id or task_id != self._active_task_id:
            return False
        self._trusted_task_id = task_id
        return True

    async def request_tool(self, tool: str, arguments: dict[str, Any]) -> ApprovalDecision:
        return await self._request(
            "tool",
            {"tool": tool, "arguments": dict(arguments)},
        )

    async def request_egress(self, request: Any) -> ApprovalDecision:
        if isinstance(request, Mapping):
            details = dict(request)
        elif is_dataclass(request):
            details = asdict(request)
        else:
            details = {"request": str(request)}
        return await self._request("egress", details)

    def resolve(self, request_id: str, allowed: bool, scope: str) -> bool:
        pending = self._pending.get(request_id)
        if pending is None:
            return False
        if scope not in APPROVAL_SCOPES:
            raise ValueError("scope must be once, session or task")
        if pending.details.get("tool") in _ONCE_ONLY_TOOLS:
            scope = "once"
        if (
            allowed
            and scope == "task"
            and pending.task_id == self._active_task_id
            and not self.distrusted(pending.task_id)
        ):
            self._trusted_task_id = pending.task_id
        self.event_store.append(
            Event(
                session_id=pending.session_id,
                type="approval.resolved",
                data={
                    "request_id": request_id,
                    "task_id": pending.task_id,
                    "kind": pending.kind,
                    "allowed": bool(allowed),
                    "scope": scope,
                },
            )
        )
        decision = ApprovalDecision(
            request_id=request_id,
            allowed=bool(allowed),
            scope=scope,
            task_id=pending.task_id,
            kind=pending.kind,
        )
        if not pending.future.done():
            pending.future.set_result(decision)
        self._pending.pop(request_id, None)
        return True

    def pending(self, task_id: str | None = None) -> list[dict[str, object]]:
        result = []
        for item in self._pending.values():
            if task_id is not None and item.task_id != task_id:
                continue
            result.append(
                {
                    "request_id": item.request_id,
                    "task_id": item.task_id,
                    "kind": item.kind,
                    "details": dict(item.details),
                }
            )
        return result

    async def _request(self, kind: str, details: dict[str, Any]) -> ApprovalDecision:
        if self._active_task_id is None or self._active_session_id is None:
            raise RuntimeError("no active mobile task is registered")
        request_id = str(uuid4())
        tool = details.get("tool")
        covered = tool not in _ALWAYS_ASK_TOOLS or (
            tool in _PHONE_CONTROL_TOOLS and self._phone_task_id == self._active_task_id
        )
        untrusted = self.distrusted(self._active_task_id) if kind == "tool" else None
        if untrusted:
            details = {**details, "untrusted_content": untrusted}
        elif self._trusted_task_id == self._active_task_id and covered:
            # Covered by the user's "allow for this task"; recorded for the audit trail.
            self.event_store.append(
                Event(
                    session_id=self._active_session_id,
                    type="mobile.approval.auto",
                    data={
                        "request_id": request_id,
                        "task_id": self._active_task_id,
                        "kind": kind,
                        "subject": details.get("tool") or details.get("endpoint"),
                        "scope": "task",
                    },
                )
            )
            return ApprovalDecision(request_id, True, "task", self._active_task_id, kind)
        loop = asyncio.get_running_loop()
        pending = _PendingApproval(
            request_id=request_id,
            task_id=self._active_task_id,
            session_id=self._active_session_id,
            kind=kind,
            details=details,
            future=loop.create_future(),
        )
        self._pending[request_id] = pending
        self.event_store.append(
            Event(
                session_id=pending.session_id,
                type="approval.requested",
                data={
                    "request_id": request_id,
                    "task_id": pending.task_id,
                    "kind": kind,
                    "details": details,
                },
            )
        )
        if self.request_listener is not None:
            result = self.request_listener(
                {
                    "request_id": request_id,
                    "task_id": pending.task_id,
                    "session_id": pending.session_id,
                    "kind": pending.kind,
                    "details": dict(pending.details),
                }
            )
            if inspect.isawaitable(result):
                await result
        try:
            return await pending.future
        except asyncio.CancelledError:
            self._pending.pop(request_id, None)
            raise
