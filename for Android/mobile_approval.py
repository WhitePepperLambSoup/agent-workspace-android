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
        self._pending: dict[str, _PendingApproval] = {}

    def set_active_task(self, task_id: str, session_id: str) -> None:
        if not task_id or not session_id:
            raise ValueError("task_id and session_id are required")
        self._active_task_id = task_id
        self._active_session_id = session_id

    def clear_active_task(self, task_id: str | None = None) -> None:
        if task_id is not None and task_id != self._active_task_id:
            return
        self._active_task_id = None
        self._active_session_id = None

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
        if scope not in {"once", "session"}:
            raise ValueError("scope must be once or session")
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
