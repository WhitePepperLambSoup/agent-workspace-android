"""Android task orchestration around the existing application runtime."""

from __future__ import annotations

import asyncio
import base64
import binascii
import dataclasses
import hashlib
import json
import os
from contextlib import asynccontextmanager, suppress
from copy import copy
from pathlib import Path
from typing import Any

from mobile_approval import MobileApprovalBroker
from mobile_artifacts import (
    background_job_fingerprint,
    background_jobs_need_attribution,
    collect_task_artifacts,
    register_task_artifacts,
    snapshot_task_workspace,
)
from mobile_images import resolve_mobile_images
from mobile_protocol import REASONING_EFFORTS, MobileEvent, MobileTask, MobileTaskRequest, TaskState
from mobile_task_store import MobileTaskStore
from mobile_workflow_replay import ReplayInterrupted
from mobile_workspace import runtime_private_paths

from agent_workspace.application.ports import ApprovalDecision as RuntimeApprovalDecision
from agent_workspace.application.ports import EventStore
from agent_workspace.core.budgets import TaskBudget
from agent_workspace.core.events import Event
from agent_workspace.core.models import ApprovalScope, Autonomy, ProviderEgressRequest, ToolSpec
from agent_workspace.providers.reasoning import supported_reasoning_efforts

_TERMINAL_STATES = frozenset({TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED})
# Keep the cursor below the HTTP server's 64 KiB request-line limit.
_MAX_SYNC_CURSOR_LENGTH = 60000
_ANDROID_SYSTEM_SUFFIX = (
    "This runtime is embedded in an Android app. Use the tools advertised in this request "
    "and paths in the current workspace. Do not assume Windows cmd, PowerShell, desktop "
    "binaries, or a separately installed Termux environment are available. "
    "Use read_document to read PDF/Office attachments; embedded document parsing works "
    "without a Python executable in the shell. When advertised, Android read_document "
    "automatically uses on-device OCR for scanned or unmapped PDFs; use next_page as "
    "start_page and next_offset as offset to continue reading, and identify OCR uncertainty. "
    "Use render_pdf for visual page "
    "inspection only with a vision-capable model. Use create_pdf to generate a real PDF "
    "report, verify it with read_document, and give the saved file link. Do not use "
    "write_file to save text with a .pdf extension or keep inspecting raw PDF bytes in "
    "the shell when a document tool is available."
)


def _android_system_suffix() -> str:
    """Android guidance plus the phone-wide memory section, rebuilt for every task."""
    if not os.getenv("AGENT_WORKSPACE_DATA_DIR"):
        return _ANDROID_SYSTEM_SUFFIX
    from mobile_memory import memory_system_suffix

    memory = memory_system_suffix()
    return f"{_ANDROID_SYSTEM_SUFFIX}\n\n{memory}" if memory else _ANDROID_SYSTEM_SUFFIX


class MobileRuntimeNotReady(ValueError):
    """Task admission is closed while the embedded engine is restarting."""

    code = "runtime_restarting"
    retryable = True

    def __init__(
        self,
        message: str = "wait for the provider change engine restart before starting tasks",
        *,
        code: str = "runtime_restarting",
    ):
        super().__init__(message)
        self.code = code


def configured_mobile_autonomy() -> Autonomy:
    value = os.getenv("AGENT_WORKSPACE_AUTONOMY") or Autonomy.WORKSPACE.value
    if value not in {Autonomy.WORKSPACE.value, Autonomy.YOLO.value, Autonomy.FULL_ACCESS.value}:
        raise ValueError("AGENT_WORKSPACE_AUTONOMY must be workspace, yolo, or full_access")
    return Autonomy(value)


def experimental_mobile_context_summary(base_url: str | None = None) -> bool:
    endpoint = base_url if base_url is not None else os.getenv("AGENT_WORKSPACE_BASE_URL", "")
    return endpoint.rstrip("/") == "http://127.0.0.1:8080/embedded-qwen/v1"


def configured_mobile_context_summary(base_url: str | None = None) -> bool:
    value = os.getenv("AGENT_WORKSPACE_CONTEXT_SUMMARY_ENABLED")
    if value is None:
        return not experimental_mobile_context_summary(base_url)
    if value not in {"0", "1"}:
        raise ValueError("AGENT_WORKSPACE_CONTEXT_SUMMARY_ENABLED must be 0 or 1")
    return value == "1"


def migrate_workspace_sessions_autonomy(
    store: EventStore, workspace: str | Path, autonomy: Autonomy
) -> int:
    root = Path(workspace).resolve(strict=True)
    changed = 0
    for session in store.list_sessions(limit=2_147_483_647):
        if Path(session.workspace).resolve() != root or session.autonomy is autonomy:
            continue
        store.append(
            Event(
                session_id=session.id,
                type="autonomy.changed",
                data={"from_autonomy": session.autonomy.value, "to_autonomy": autonomy.value},
            )
        )
        changed += 1
    return changed


class MobileRuntimeController:
    """Serialize mobile runs while preserving durable task state and resumability."""

    def __init__(
        self,
        runtime: Any,
        *,
        default_model: str | None = None,
        default_reasoning_effort: str = "auto",
        protocol: str | None = None,
        base_url: str | None = None,
        task_store: MobileTaskStore | None = None,
        approval_broker: MobileApprovalBroker | None = None,
    ) -> None:
        self.runtime = runtime
        self.default_model = default_model
        if (
            not isinstance(default_reasoning_effort, str)
            or default_reasoning_effort not in REASONING_EFFORTS
        ):
            raise ValueError("default reasoning_effort is invalid")
        self.default_reasoning_effort = default_reasoning_effort
        self.protocol = protocol
        self.base_url = base_url
        service = getattr(runtime, "service", None)
        execution_workspace = getattr(service, "_execution_workspace", None)
        self.tasks = task_store or MobileTaskStore(runtime.store, workspace=execution_workspace)
        self.approvals = approval_broker or MobileApprovalBroker(
            runtime.store,
            request_listener=self._on_approval_requested,
        )
        if approval_broker is not None and approval_broker.request_listener is None:
            approval_broker.request_listener = self._on_approval_requested
        self._jobs: dict[str, asyncio.Task[None]] = {}
        self._execution_checks: dict[str, tuple[Any, Any]] = {}
        self._executions: dict[str, Any] = {}
        self._artifact_baselines: dict[str, dict[str, Any]] = {}
        self._artifact_previous: dict[str, dict[str, Any] | None] = {}
        self._artifact_scopes: dict[str, Any] = {}
        self._replay_authorized: dict[str, dict[str, Any]] = {}
        self._cancel_reasons: dict[str, str] = {}
        self._execution_lock = asyncio.Lock()
        self._maintenance = False
        self._active_task_id: str | None = None
        self._active_session_id: str | None = None
        self._started = False
        self._closing = False
        self._restart_pending = False
        self._connection_epoch = 0
        self._last_recovery_count = 0

    async def start(self) -> list[MobileTask]:
        if self._started:
            return []
        self._started = True
        self._connection_epoch += 1
        recovered = self.tasks.recover_after_restart()
        self._last_recovery_count = len(recovered)
        return recovered

    async def reconnect(self) -> dict[str, object]:
        """Return a bounded offline recovery snapshot for a mobile client."""
        if not self._started:
            await self.start()
        return self.sync()

    def get(self, task_id: str) -> MobileTask:
        return self.tasks.get(task_id)

    def list(self, session_id: str | None = None) -> list[MobileTask]:
        return self.tasks.list(session_id)

    def events(self, task_id: str, after: int = 0) -> list[MobileEvent]:
        return self.tasks.events(task_id, after)

    def pending_approvals(self, task_id: str | None = None) -> list[dict[str, object]]:
        return self.approvals.pending(task_id)

    def status(self) -> dict[str, object]:
        active = self.get(self._active_task_id) if self._active_task_id is not None else None
        return {
            "state": "stopping" if self._closing or self._restart_pending else "ready",
            "maintenance": self._maintenance,
            "active_task_id": self._active_task_id,
            "active_task_state": active.state.value if active is not None else None,
            "pending_approvals": len(self.approvals.pending()),
            "queued_tasks": sum(task.state is TaskState.QUEUED for task in self.tasks.list()),
            "connection_epoch": self._connection_epoch,
            "recovered_tasks": self._last_recovery_count,
            "restart_required": self._restart_pending,
            "task_admission_ready": (
                not self._closing and not self._restart_pending and not self._maintenance
            ),
            "last_sequence": max(
                (task.last_sequence for task in self.tasks.list()),
                default=0,
            ),
        }

    @asynccontextmanager
    async def maintenance(self):
        """Hold task execution and admission while an idle runtime is changed."""
        self._ensure_open()
        if self._maintenance:
            raise ValueError("model or tool maintenance is already in progress")
        state = self.status()
        if (
            state.get("active_task_id")
            or state.get("queued_tasks")
            or self._execution_lock.locked()
        ):
            raise ValueError(
                "stop or finish active and queued tasks before changing models or tools"
            )
        # No await separates the idle check and admission flag. The same loop
        # also serializes submit/resume, before either writes durable task state.
        self._maintenance = True
        try:
            async with self._execution_lock:
                yield
        finally:
            self._maintenance = False

    def prepare_provider_restart(self) -> None:
        """Close admission before releasing an owned provider-change reservation."""
        if not self._maintenance or not self._execution_lock.locked():
            raise ValueError("provider restart requires an idle maintenance reservation")
        self._restart_pending = True

    def sync(
        self, *, after: int = 0, limit: int = 200, cursor: str | None = None
    ) -> dict[str, object]:
        """Return durable events; use next_cursor to page across sessions.

        Numeric after remains available for a single session's local sequence.
        """
        if after < 0 or limit < 1 or limit > 1000:
            raise ValueError("sync cursor or limit is invalid")
        tasks = self.tasks.list()
        sessions = {task.session_id for task in tasks}
        if cursor is not None:
            if after:
                raise ValueError("after and cursor cannot be combined")
            positions = _decode_sync_cursor(cursor)
        elif after:
            if len(sessions) > 1:
                raise ValueError("cursor is required for sync across multiple sessions")
            positions = {session_id: after for session_id in sessions}
        else:
            positions = {}
        events = [
            (task.session_id, event)
            for task in tasks
            for event in self.tasks.events(task.task_id, positions.get(task.session_id, 0))
        ]
        events.sort(key=lambda item: (item[1].sequence, item[0], item[1].event_id))
        visible = events[:limit]
        next_positions = dict(positions)
        for session_id, event in visible:
            next_positions[session_id] = event.sequence
        next_sequence = max(next_positions.values(), default=after)
        return {
            "connection_epoch": self._connection_epoch,
            "tasks": [task.to_dict() for task in tasks],
            "events": [event.to_dict() for _, event in visible],
            "after": after,
            "next_sequence": next_sequence,
            "next_cursor": _encode_sync_cursor(next_positions),
            "has_more": len(events) > len(visible),
        }

    async def submit(
        self,
        request: MobileTaskRequest,
        *,
        request_id: str | None = None,
        budget_steps: int | None = None,
        before_run: Any = None,
        after_run: Any = None,
        execution: Any = None,
        execution_kind: str | None = None,
    ) -> MobileTask:
        self._ensure_task_admission()
        if not isinstance(request, MobileTaskRequest):
            raise TypeError("request must be a MobileTaskRequest")
        if execution is not None and (
            not callable(execution) or execution_kind != "workflow_replay"
        ):
            raise ValueError("custom execution requires a workflow_replay callback")
        if execution_kind is not None and execution is None:
            raise ValueError("execution_kind requires an execution callback")
        try:
            self.runtime.service.get_session(request.session_id)
        except ValueError:
            raise KeyError(request.session_id) from None
        if request_id is not None:
            existing = self.tasks.find_request(request, request_id, budget_steps=budget_steps)
            if existing is not None:
                return existing
        model = request.model or self.default_model or ("declarative-replay" if execution else None)
        if not model:
            raise ValueError("no model configured for the mobile task")
        effort = request.reasoning_effort or self.default_reasoning_effort
        if not isinstance(effort, str) or effort not in REASONING_EFFORTS:
            raise ValueError("reasoning_effort is invalid")
        if (
            self.protocol is not None
            and self.base_url is not None
            and execution is None
            and effort not in supported_reasoning_efforts(self.protocol, self.base_url, model)
        ):
            raise ValueError(f"{model} does not support the selected reasoning_effort")
        replaced = None
        if request.rewind_from_event_id is not None:
            replaced = self._rewind_target(request)
            if request.rewind_reason == "regenerate":
                # Ask the same question again: the stored text and pictures, not the client's copy.
                refs = request.image_refs or self._original_image_refs(request.session_id, replaced)
                request = dataclasses.replace(
                    request, prompt=replaced.data.get("content") or request.prompt, image_refs=refs
                )
        images = resolve_mobile_images(self.runtime, request.session_id, request.image_refs)
        if replaced is not None:
            # Recorded only after every check passed, so a refused request changes nothing.
            self._record_rewind(request, replaced)
        task = self.tasks.create(
            request.session_id,
            request.prompt,
            model,
            effort,
            request_id=request_id,
            budget_steps=budget_steps,
            request=request,
            images=images,
        )
        if task.state is TaskState.QUEUED and task.task_id not in self._jobs:
            self._execution_checks[task.task_id] = (before_run, after_run)
            if execution is not None:
                self.tasks.append_event(
                    task.task_id, "task.execution.bound", {"execution_kind": execution_kind}
                )
                self._executions[task.task_id] = execution
            self._schedule(task.task_id)
        return task

    async def switch_provider(self, config: Any, reasoning_effort: str) -> list[Any]:
        """Single-runtime form of MobileWorkspaceController.switch_provider."""
        async with self.maintenance():
            if any(
                task.state in {TaskState.QUEUED, TaskState.RUNNING, TaskState.WAITING_APPROVAL}
                for task in self.tasks.list()
            ):
                raise ValueError("stop or finish active and queued tasks before changing models or tools")
            previous = [self.runtime.switch_provider(config)]
            self.default_model = config.model
            self.default_reasoning_effort = reasoning_effort
            self.protocol = config.protocol.value
            self.base_url = config.base_url
        return previous

    def _rewind_target(self, request: MobileTaskRequest) -> Event:
        """The user message an edit or regenerate replaces, after checking it may be replaced."""
        if any(
            task.state in {TaskState.QUEUED, TaskState.RUNNING, TaskState.WAITING_APPROVAL}
            for task in self.tasks.list(request.session_id)
        ):
            raise ValueError("wait for the running task to finish before editing earlier messages")
        event = self.runtime.store.get_event(request.rewind_from_event_id)
        if (
            event is None
            or event.session_id != request.session_id
            or event.type != "message.created"
            or event.data.get("role") != "user"
            or not event.sequence
        ):
            raise ValueError("only your own messages in this conversation can be edited or regenerated")
        return event

    def _original_image_refs(self, session_id: str, message: Event) -> tuple:
        """The imported pictures of an earlier message, found by digest among this session's tasks."""
        digests = [
            image.get("sha256")
            for image in message.data.get("images", []) or []
            if isinstance(image, dict) and isinstance(image.get("sha256"), str)
        ]
        if not digests:
            return ()
        known = {ref.sha256: ref for task in self.tasks.list(session_id) for ref in task.image_refs}
        if any(digest not in known for digest in digests):
            raise ValueError("the original pictures are no longer available; attach them again")
        return tuple(known[digest] for digest in digests)

    def _record_rewind(self, request: MobileTaskRequest, event: Event) -> None:
        """Edit-and-resend / regenerate: drop the chosen user message and everything after it
        from the model's context. History keeps every event; files already changed stay changed."""
        self.runtime.store.append(
            Event(
                session_id=request.session_id,
                type="context.rewound",
                data={
                    "from_event_id": event.id,
                    "from_sequence": event.sequence,
                    "reason": request.rewind_reason,
                },
            )
        )

    async def resume(self, task_id: str, *, execution: Any = None) -> MobileTask:
        self._ensure_task_admission()
        task = self.tasks.get(task_id)
        kind = self._execution_kind(task_id)
        if kind == "workflow_replay" and execution is None:
            raise ValueError("resume this workflow through its explicit checked replay endpoint")
        if execution is not None and (kind != "workflow_replay" or not callable(execution)):
            raise ValueError("custom resume requires the original workflow execution")
        if task.state is not TaskState.INTERRUPTED or not task.resume_available:
            raise ValueError("task is not resumable")
        if execution is not None:
            self._executions[task_id] = execution
        queued = self.tasks.transition(task_id, TaskState.QUEUED, reason=None)
        self._schedule(task_id)
        return queued

    async def cancel(self, task_id: str) -> MobileTask:
        self._ensure_open()
        task = self.tasks.get(task_id)
        if task.state in _TERMINAL_STATES:
            return task
        self._cancel_reasons[task_id] = "cancelled by client"
        job = self._jobs.get(task_id)
        if task.state is TaskState.QUEUED and job is not None and not job.done():
            cancelled = self.tasks.transition(
                task_id,
                TaskState.CANCELLED,
                reason="cancelled by client",
            )
            job.cancel()
            return cancelled
        if job is not None and not job.done():
            job.cancel()
        elif task.state in {TaskState.INTERRUPTED, TaskState.WAITING_APPROVAL}:
            return self.tasks.transition(
                task_id,
                TaskState.CANCELLED,
                reason="cancelled by client",
            )
        return task

    async def wait(self, task_id: str) -> MobileTask:
        job = self._jobs.get(task_id)
        if job is not None:
            try:
                await asyncio.shield(job)
            except asyncio.CancelledError:
                current = asyncio.current_task()
                if current is not None and current.cancelling():
                    raise
        return self.tasks.get(task_id)

    async def resolve_approval(self, request_id: str, allowed: bool, scope: str) -> bool:
        self._ensure_open()
        return self.approvals.resolve(request_id, allowed, scope)

    async def authorize_tool(
        self,
        tool: ToolSpec,
        arguments: dict[str, Any],
    ) -> RuntimeApprovalDecision:
        task_id = self._require_active_task()
        decision = await self.approvals.request_tool(tool.name, arguments)
        self._resume_after_approval(task_id)
        return RuntimeApprovalDecision(
            decision.allowed,
            "approved by mobile" if decision.allowed else "denied by mobile",
            _approval_scope(decision.scope) if decision.allowed else None,
        )

    async def authorize_egress(
        self,
        request: ProviderEgressRequest,
    ) -> RuntimeApprovalDecision:
        task_id = self._require_active_task()
        decision = await self.approvals.request_egress(request)
        self._resume_after_approval(task_id)
        return RuntimeApprovalDecision(
            decision.allowed,
            "approved by mobile" if decision.allowed else "denied by mobile",
            _approval_scope(decision.scope) if decision.allowed else None,
        )

    async def _record_replay_event(self, kind: str, data: dict[str, Any]) -> Event:
        task_id = self._require_active_task()
        task = self.tasks.get(task_id)
        event = self.runtime.store.append(Event(session_id=task.session_id, type=kind, data=data))
        await self.handle_runtime_event(event)
        return event

    async def authorize_replay_action(self, arguments: dict[str, Any], *, selector=None) -> None:
        """Apply the current task's policy to the same Android tool and masked approval view."""
        from android_adapter.android_system import AndroidActionTool

        from agent_workspace.policy.permissions import WorkspacePolicy
        from agent_workspace.tools.base import validate_tool_arguments

        task_id = self._require_active_task()
        task = self.tasks.get(task_id)
        session = self.runtime.service.get_session(task.session_id)
        tool = AndroidActionTool()
        validate_tool_arguments(tool.spec, arguments)
        prepared = tool.prepare_for_approval(arguments)
        if selector:
            prepared["workflow_selector"] = dict(selector)
        attempt = {
            "attempt_id": self._new_replay_attempt_id(),
            "tool_call_id": self._new_replay_attempt_id(),
            "name": tool.spec.name,
            "execution_kind": "workflow_replay",
        }
        await self._record_replay_event(
            "tool.proposed",
            {**attempt, "idempotency_key": self._new_replay_attempt_id(), "arguments": prepared},
        )
        policy = getattr(getattr(self.runtime.service, "runner", None), "_policy", None)
        if policy is None:
            policy = WorkspacePolicy(
                session.workspace, autonomy=session.autonomy, approval_callback=self.authorize_tool
            )
        else:
            # Retain argument rules, escalation policy and grants with this session's autonomy.
            policy = copy(policy)
            if hasattr(policy, "autonomy"):
                policy.autonomy = session.autonomy
        try:
            decision = await policy.authorize(tool.spec, prepared, session_id=task.session_id)
        except asyncio.CancelledError:
            await self._record_replay_event(
                "tool.cancelled", {**attempt, "reason": "approval interrupted before dispatch"}
            )
            raise
        except Exception:
            await self._record_replay_event(
                "tool.rejected", {**attempt, "reason": "current task policy rejected authorization"}
            )
            raise
        await self._record_replay_event(
            "tool.approved" if decision.allowed else "tool.rejected",
            {**attempt, "reason": decision.reason},
        )
        if not decision.allowed:
            raise PermissionError(f"workflow action denied: {decision.reason}")
        self._replay_authorized[task_id] = {
            "signature": {key: arguments.get(key) for key in ("action", "text", "package_name")},
            "attempt": attempt,
        }

    async def dispatch_replay_action(self, arguments: dict[str, Any], execute) -> dict[str, Any]:
        """Dispatch only after task policy authorization; never place input text in task events."""
        task_id = self._require_active_task()
        authorized = self._replay_authorized.pop(task_id, None)
        if not authorized or authorized["signature"] != {
            key: arguments.get(key) for key in ("action", "text", "package_name")
        }:
            raise PermissionError("workflow action was not authorized in the current task")
        attempt = authorized["attempt"]
        await self._record_replay_event("tool.started", attempt)
        try:
            response = await execute(arguments)
        except BaseException:
            await self._record_replay_event(
                "tool.unknown",
                {**attempt, "reason": "Android dispatch interrupted; execution may have occurred"},
            )
            raise
        error = response.get("error") if isinstance(response, dict) else None
        await self._record_replay_event(
            "android.action.result",
            {
                "attempt_id": attempt["attempt_id"],
                "action": arguments.get("action"),
                "executed": response.get("executed") if isinstance(response, dict) else None,
                "verified": response.get("verified") if isinstance(response, dict) else None,
                "error_code": error.get("code") if isinstance(error, dict) else None,
            },
        )
        await self._record_replay_event(
            "tool.settled"
            if isinstance(response, dict) and type(response.get("executed")) is bool
            else "tool.unknown",
            attempt,
        )
        return response

    @staticmethod
    def _new_replay_attempt_id() -> str:
        from uuid import uuid4

        return str(uuid4())

    def _execution_kind(self, task_id: str) -> str | None:
        return next(
            (
                event.payload.get("execution_kind")
                for event in reversed(self.events(task_id))
                if event.event_type == "task.execution.bound"
            ),
            None,
        )

    async def handle_runtime_event(self, event: Event) -> None:
        task_id = self._active_task_id
        if task_id is None or event.session_id != self._active_session_id:
            return
        scope = self._artifact_scopes.get(task_id)
        checkpoint_allowed = True
        if scope is not None:
            attempt_id = event.data.get("attempt_id") or event.data.get("tool_call_id") or event.id
            if event.type == "tool.started":
                await scope.start_tool(
                    str(attempt_id),
                    file_versions_only=event.data.get("name")
                    in {"write_file", "download_file", "create_pdf"}
                    and event.data.get("recovery_strategy") == "file-preimage-v1",
                )
            elif event.type in {"file.version.recorded", "image.attached"}:
                await scope.record_file_version(event.data.get("path"), event.data.get("sha256"))
            elif event.type in {"tool.settled", "tool.failed", "tool.cancelled", "tool.unknown"}:
                checkpoint_allowed = await scope.finish_tool(str(attempt_id))
        event_type = _mobile_event_type(event.type)
        payload = {
            "source_event_id": event.id,
            "source_type": event.type,
            "source_sequence": event.sequence,
            "data": dict(event.data),
        }
        try:
            self.tasks.append_event(task_id, event_type, payload)
            if (
                event.type == "tool.settled"
                and checkpoint_allowed
                and task_id in self._artifact_baselines
            ):
                await self._checkpoint_task_artifacts(task_id)
        except KeyError:
            return

    async def aclose(self) -> None:
        if self._closing:
            return
        self._closing = True
        jobs = tuple(self._jobs.values())
        for task in jobs:
            if not task.done():
                task.cancel()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
        for task in self.tasks.list():
            if task.state not in _TERMINAL_STATES and task.state is not TaskState.INTERRUPTED:
                with suppress(ValueError):
                    self.tasks.transition(
                        task.task_id,
                        TaskState.INTERRUPTED,
                        reason="runtime stopped",
                        resume_available=True,
                    )

    def _schedule(self, task_id: str) -> None:
        existing = self._jobs.get(task_id)
        if existing is not None and not existing.done():
            raise ValueError("task is already scheduled")
        job = asyncio.create_task(self._execute(task_id), name=f"mobile-task-{task_id}")
        self._jobs[task_id] = job

    async def _execute(self, task_id: str) -> None:
        try:
            async with self._artifact_execution_lock(task_id):
                task = self.tasks.get(task_id)
                if task.state is not TaskState.QUEUED:
                    return
                session = self.runtime.service.get_session(task.session_id)
                model = task.model or self.default_model
                if not model:
                    raise ValueError("no model configured for the mobile task")
                self._active_task_id = task_id
                self._active_session_id = task.session_id
                self.approvals.set_active_task(task_id, task.session_id)
                has_persisted_input = self.tasks.has_persisted_input(task_id)
                self.tasks.transition(task_id, TaskState.RUNNING)
                workspace = Path(session.workspace)
                excluded_paths = self._artifact_excluded_paths()
                scope = register_task_artifacts(task_id, workspace, excluded_paths=excluded_paths)
                scope.background_job_store = self.runtime.store
                scope.background_jobs = background_job_fingerprint(self.runtime.store, workspace)
                self._artifact_scopes[task_id] = scope
                try:
                    async with scope.inspection():
                        baseline = await asyncio.to_thread(
                            snapshot_task_workspace, workspace, excluded_paths=excluded_paths
                        )
                except Exception:
                    baseline = {
                        "version": 1,
                        "files": {},
                        "truncated": False,
                        "error": "Workspace artifact inspection could not start.",
                    }
                previous_snapshot = self.tasks.artifact_snapshot(task_id)
                previous_checkpoint = self.tasks.artifact_checkpoint(task_id)
                if previous_snapshot is not None and previous_checkpoint is None:
                    self._artifact_previous[task_id] = {
                        "artifacts": [],
                        "artifacts_truncated": False,
                        "artifacts_error": (
                            "Earlier interrupted outputs could not be attributed safely; "
                            "inspect the workspace."
                        ),
                        "signatures": {},
                    }
                else:
                    self._artifact_previous[task_id] = previous_checkpoint
                self._artifact_baselines[task_id] = baseline
                scope.baseline = baseline
                try:
                    self.tasks.save_artifact_snapshot(task_id, baseline)
                except Exception:
                    baseline["error"] = "Workspace artifact baseline could not be persisted."
                images = self.tasks.images(task_id) if task.image_refs else ()
                if any(
                    hashlib.sha256(image.data).hexdigest() != ref.sha256
                    for ref, image in zip(task.image_refs, images, strict=True)
                ):
                    raise ValueError("the durable task image SHA-256 does not match its input")
                before_run, after_run = self._execution_checks.get(task_id, (None, None))
                if before_run is not None:
                    await before_run()
                options = {"summarize_history": configured_mobile_context_summary(self.base_url)}
                if task.budget_steps is not None:
                    options["budget"] = TaskBudget(
                        max_tool_calls=task.budget_steps,
                        max_model_calls=task.budget_steps,
                        max_provider_attempts=task.budget_steps,
                        max_turn_seconds=900,
                    )
                execution = self._executions.get(task_id)
                if execution is not None:
                    result = await execution(task)
                elif self._execution_kind(task_id) == "workflow_replay":
                    raise ValueError(
                        "workflow replay callback is missing; use explicit workflow resume"
                    )
                elif has_persisted_input:
                    result = await self.runtime.service.continue_run(
                        session,
                        model,
                        reasoning_effort=task.reasoning_effort,
                        system_suffix=_android_system_suffix(),
                        continuation_prompt=(
                            "Resume the interrupted Android task from its durable history. "
                            "Reuse confirmed tool results and completed actions. "
                            "Inspect the current "
                            "state before retrying any action with an unknown outcome. "
                            f"Original task: {task.prompt}"
                        ),
                        **options,
                    )
                else:
                    result = await self.runtime.service.run(
                        session,
                        task.prompt,
                        model,
                        reasoning_effort=task.reasoning_effort,
                        system_suffix=_android_system_suffix(),
                        **({"images": images} if task.image_refs else {}),
                        **options,
                    )
                # Adapted services may return without a terminal tool event.
                await scope.finish_tool()
                if after_run is not None:
                    await after_run()
                artifacts = await self._checkpoint_task_artifacts(task_id)
                self.tasks.complete(
                    task_id,
                    {
                        "text": getattr(result, "text", ""),
                        "correlation_id": getattr(result, "correlation_id", ""),
                        **artifacts,
                    },
                )
        except asyncio.CancelledError:
            current = self.tasks.get(task_id)
            if current.state not in _TERMINAL_STATES and current.state is not TaskState.INTERRUPTED:
                state = TaskState.INTERRUPTED if self._closing else TaskState.CANCELLED
                reason = (
                    "runtime stopped"
                    if self._closing
                    else self._cancel_reasons.get(task_id, "cancelled")
                )
                with suppress(ValueError):
                    self.tasks.transition(
                        task_id,
                        state,
                        reason=reason,
                        resume_available=state is TaskState.INTERRUPTED,
                    )
            raise
        except ReplayInterrupted as exc:
            current = self.tasks.get(task_id)
            if current.state not in _TERMINAL_STATES and current.state is not TaskState.INTERRUPTED:
                self.tasks.transition(
                    task_id, TaskState.INTERRUPTED, reason=str(exc)[:2000], resume_available=False
                )
        except Exception as exc:
            current = self.tasks.get(task_id)
            if current.state not in _TERMINAL_STATES:
                reason = " ".join(str(exc).split())[:2000] or type(exc).__name__
                try:
                    self.tasks.transition(task_id, TaskState.FAILED, reason=reason)
                    self.tasks.append_event(task_id, "task.failed", {"error": reason})
                except ValueError:
                    pass
        finally:
            unused = self._replay_authorized.pop(task_id, None)
            if unused and self._active_task_id == task_id:
                with suppress(Exception):
                    await self._record_replay_event(
                        "tool.cancelled",
                        {**unused["attempt"], "reason": "state changed before Android dispatch"},
                    )
            if self._active_task_id == task_id:
                self.approvals.clear_active_task(task_id)
                self._active_task_id = None
                self._active_session_id = None
            self._cancel_reasons.pop(task_id, None)
            self._execution_checks.pop(task_id, None)
            self._executions.pop(task_id, None)

    @asynccontextmanager
    async def _artifact_execution_lock(self, task_id: str):
        async with self._execution_lock:
            try:
                yield
            finally:
                scope = self._artifact_scopes.get(task_id)
                try:
                    if scope is not None:
                        await scope.finish_tool()
                    if (
                        task_id in self._artifact_baselines
                        and self.tasks.get(task_id).state is not TaskState.SUCCEEDED
                    ):
                        with suppress(Exception):
                            await self._checkpoint_task_artifacts(task_id)
                finally:
                    if scope is not None:
                        scope.close()
                    self._artifact_scopes.pop(task_id, None)
                    self._artifact_baselines.pop(task_id, None)
                    self._artifact_previous.pop(task_id, None)

    async def _checkpoint_task_artifacts(self, task_id: str) -> dict[str, Any]:
        task = self.tasks.get(task_id)
        session = self.runtime.service.get_session(task.session_id)
        try:
            scope = self._artifact_scopes[task_id]
            scope.background_job_unsafe |= background_jobs_need_attribution(scope)
            if scope.background_job_unsafe:
                scope.overlapped = True
                scope.error = (
                    "Background job activity made unverified workspace changes "
                    "ineligible for linking."
                )
            async with scope.inspection():
                checkpoint = await asyncio.to_thread(
                    collect_task_artifacts,
                    Path(session.workspace),
                    self._artifact_baselines[task_id],
                    excluded_paths=self._artifact_excluded_paths(),
                    prior_checkpoint=None
                    if scope.background_job_unsafe
                    else self._artifact_previous.get(task_id),
                    attributed_files=scope.version_files
                    if scope.background_job_unsafe
                    else scope.files
                    if scope.overlapped
                    else None,
                    attribution_error=scope.error,
                    warn_unattributed=scope.overlapped and not scope.has_tool_events,
                )
                scope.background_job_unsafe |= background_jobs_need_attribution(scope)
                if scope.background_job_unsafe:
                    scope.overlapped = True
                    checkpoint["artifacts"] = [
                        artifact
                        for artifact in checkpoint["artifacts"]
                        if artifact.get("sha256") is not None
                        and artifact["sha256"]
                        == scope.version_files.get(artifact["path"], {}).get("sha256")
                    ]
                    checkpoint["signatures"] = {
                        artifact["path"]: checkpoint["signatures"][artifact["path"]]
                        for artifact in checkpoint["artifacts"]
                    }
                    checkpoint["artifacts_error"] = (
                        "Background job activity made unverified workspace changes "
                        "ineligible for linking."
                    )
                scope.capture_checkpoint(checkpoint)
        except Exception:
            checkpoint = {
                "artifacts": [],
                "artifacts_truncated": False,
                "artifacts_error": "Workspace outputs could not be inspected.",
            }
        try:
            self.tasks.save_artifact_checkpoint(task_id, checkpoint)
        except Exception:
            checkpoint["artifacts_error"] = "Workspace artifact checkpoint could not be persisted."
        return {
            key: checkpoint[key] for key in ("artifacts", "artifacts_truncated", "artifacts_error")
        }

    def _artifact_excluded_paths(self) -> tuple[str, ...]:
        return tuple(str(path) for path in runtime_private_paths(self.runtime))

    async def _on_approval_requested(self, request: dict[str, Any]) -> None:
        task_id = request.get("task_id")
        if not isinstance(task_id, str):
            return
        try:
            current = self.tasks.get(task_id)
            if current.state is TaskState.RUNNING:
                self.tasks.transition(
                    task_id,
                    TaskState.WAITING_APPROVAL,
                    approval_id=str(request.get("request_id", "")) or None,
                )
        except (KeyError, ValueError):
            return

    def _resume_after_approval(self, task_id: str) -> None:
        try:
            current = self.tasks.get(task_id)
            if current.state is TaskState.WAITING_APPROVAL:
                self.tasks.transition(task_id, TaskState.RUNNING)
        except (KeyError, ValueError):
            return

    def _require_active_task(self) -> str:
        if self._active_task_id is None:
            raise RuntimeError("no active mobile task")
        return self._active_task_id

    def _ensure_open(self) -> None:
        if self._closing:
            raise RuntimeError("mobile runtime controller is closing")
        if self._restart_pending:
            raise MobileRuntimeNotReady()

    def _ensure_task_admission(self) -> None:
        self._ensure_open()
        if self._maintenance:
            raise MobileRuntimeNotReady(
                "wait for model or tool maintenance to finish before starting tasks",
                code="runtime_maintenance",
            )


def _encode_sync_cursor(positions: dict[str, int]) -> str:
    payload = json.dumps(
        {"v": 1, "positions": positions}, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    cursor = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    if len(cursor) > _MAX_SYNC_CURSOR_LENGTH:
        raise ValueError("sync cursor exceeds the request limit")
    return cursor


def _decode_sync_cursor(cursor: str) -> dict[str, int]:
    if not isinstance(cursor, str) or not cursor or len(cursor) > _MAX_SYNC_CURSOR_LENGTH:
        raise ValueError("sync cursor is invalid")
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.b64decode(padded, altchars=b"-_", validate=True)
        payload = json.loads(raw)
    except (UnicodeEncodeError, UnicodeDecodeError, binascii.Error, ValueError):
        raise ValueError("sync cursor is invalid") from None
    if (
        not isinstance(payload, dict)
        or set(payload) != {"v", "positions"}
        or payload["v"] != 1
        or not isinstance(payload["positions"], dict)
        or any(
            not isinstance(session_id, str)
            or not session_id
            or len(session_id) > 200
            or type(sequence) is not int
            or sequence < 0
            for session_id, sequence in payload["positions"].items()
        )
    ):
        raise ValueError("sync cursor is invalid")
    return payload["positions"]


def _approval_scope(scope: str) -> ApprovalScope:
    if scope == "session":
        return ApprovalScope.SESSION
    return ApprovalScope.ONCE


def _mobile_event_type(event_type: str) -> str:
    if event_type == "model.output.delta":
        return "assistant.delta"
    if event_type == "approval.requested":
        return "approval.requested"
    return f"runtime.{event_type}"
