"""Agent runs: tasks, plans, sub-agents, attention items, the run queue, orchestration, run history
and evidence.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import inspect
import json
import sqlite3
import threading
from collections.abc import Awaitable, Mapping, Sequence
from contextlib import suppress
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from agent_workspace.application.agent_control import AgentControlError, AgentControlService
from agent_workspace.application.runtime_host import RuntimeSettings
from agent_workspace.coding.team_desk import team_goal, team_tools
from agent_workspace.config import (
    ProviderConfig,
)
from agent_workspace.core.durable_run_queue import DurableRunQueue, RunQueueStatus
from agent_workspace.core.events import Event
from agent_workspace.core.expert_library import expert_tools
from agent_workspace.core.experts import find_expert
from agent_workspace.core.git_ops import (
    GitOpsError,
    git_head_sha,
    git_worktree_add,
    git_worktree_is_clean,
    git_worktree_remove,
)
from agent_workspace.core.models import (
    AgentRun,
    AgentRunState,
    ApprovalScope,
    AttentionItem,
    AttentionKind,
    AttentionState,
    Autonomy,
    Mode,
    PlanStep,
    PlanStepState,
    Role,
    RunIsolation,
)
from agent_workspace.core.session import Session
from agent_workspace.core.task_graph import TaskGraph, classify_failure
from agent_workspace.storage import (
    SQLiteEventStore,
)
from agent_workspace.tools.delegation import SubagentLaunchError, SubagentOutcome, SubagentTask
from agent_workspace.ui_gateway.gateway_common import (
    _APPROVAL_DISPLAY_FIELDS,
    _COMMAND_TIMEOUT_SECONDS,
    _DELEGATION_ANSWER_CHARS,
    _DELEGATION_POLL_SECONDS,
    _EXPERT_STOP_GRACE_SECONDS,
    _EXPERT_TIME_LIMIT_SECONDS,
    _LIFECYCLE_TIMEOUT_SECONDS,
    _MAX_AGENT_RUN_CONTINUATIONS,
    _MAX_PARALLEL_AGENT_RUNS,
    _MAX_TASK_CONTENT_CHARS,
    _MAX_TASK_POSITION,
    _MAX_TASKS_PER_SESSION,
    _TERMINAL_TURN_EVENTS,
    GatewayError,
    GatewayReply,
    Host,
    _ApprovalEntry,
    _await_value,
    _bounded_projection,
    _camel_case,
    _Delegation,
    _json_safe,
    _RunHostEntry,
)
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import (
    PROTOCOL_VERSION,
    CommandEnvelope,
)


def _accepts(function: Any, name: str) -> bool:
    """Whether a host's method takes this keyword (hosts in tests may be older)."""
    try:
        parameters = inspect.signature(function).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        item.name == name or item.kind is inspect.Parameter.VAR_KEYWORD for item in parameters
    )


def _expert_fields(delegation: _Delegation) -> dict[str, object]:
    """An expert team member's id and round, for the events of its run."""
    if delegation.expert is None:
        return {}
    return {"expert": delegation.expert, "phase": delegation.phase or "work"}


class RunCommands(GatewayState):
    """Agent runs: tasks, plans, sub-agents, attention items, the run queue, orchestration, run
    history and evidence.
    """

    def _list_tasks(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, set(), optional={"sessionId"})
        self._require_selected_session(command.session_id)
        assert command.session_id is not None
        session_id = command.session_id
        payload_session = command.payload.get("sessionId")
        if payload_session is not None and payload_session != session_id:
            raise GatewayError("invalid_session")

        tasks_payload: list[dict[str, object]] = []
        try:
            with SQLiteEventStore(self._database) as store:
                todos = store.list_todos(session_id)
                for t in todos[:_MAX_TASKS_PER_SESSION]:
                    tasks_payload.append(
                        {
                            "id": t.id,
                            "sessionId": t.session_id,
                            "content": t.content,
                            "status": t.status.value,
                            "position": t.position,
                            "createdAt": t.created_at,
                            "updatedAt": t.updated_at,
                        }
                    )
        except (OSError, sqlite3.DatabaseError, ValueError):
            raise GatewayError("storage_unavailable") from None

        return self._reply(
            "workspace.tasks.list.result",
            {
                "epoch": self.epoch,
                "sessionId": session_id,
                "tasks": tasks_payload,
                "truncated": len(todos) > _MAX_TASKS_PER_SESSION,
            },
            session_id=command.session_id,
        )

    def _create_task(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"content"}, optional={"sessionId", "status", "position"})
        self._require_selected_session(command.session_id)
        assert command.session_id is not None
        session_id = command.session_id
        payload_session = command.payload.get("sessionId")
        if payload_session is not None and payload_session != session_id:
            raise GatewayError("invalid_session")

        content = command.payload.get("content")
        if (
            not isinstance(content, str)
            or not content.strip()
            or len(content.strip()) > _MAX_TASK_CONTENT_CHARS
        ):
            raise GatewayError("invalid_content")

        raw_status = command.payload.get("status", "pending")
        if raw_status not in {"pending", "in_progress", "completed"}:
            raise GatewayError("invalid_status")

        position = command.payload.get("position", 0)
        if type(position) is not int or not 0 <= position <= _MAX_TASK_POSITION:
            raise GatewayError("invalid_position")

        todo_id = f"task_{uuid4().hex[:12]}"
        try:
            with SQLiteEventStore(self._database) as store:
                if len(store.list_todos(session_id)) >= _MAX_TASKS_PER_SESSION:
                    raise GatewayError("task_limit_reached")
                event = Event(
                    session_id=session_id,
                    type="todo.upserted",
                    data={
                        "todo_id": todo_id,
                        "content": content.strip(),
                        "status": raw_status,
                        "position": position,
                    },
                )
                store.append(event)
                todos = store.list_todos(session_id)
                created_item = next((t for t in todos if t.id == todo_id), None)
                task_doc: dict[str, object] = {
                    "id": todo_id,
                    "sessionId": session_id,
                    "content": content.strip(),
                    "status": raw_status,
                    "position": position,
                    "createdAt": created_item.created_at if created_item else event.created_at,
                    "updatedAt": created_item.updated_at if created_item else event.created_at,
                }
        except GatewayError:
            raise
        except (OSError, sqlite3.DatabaseError, ValueError):
            raise GatewayError("storage_unavailable") from None

        return self._reply(
            "workspace.tasks.create.result",
            {
                "epoch": self.epoch,
                "sessionId": session_id,
                "task": task_doc,
            },
            session_id=command.session_id,
        )

    def _update_task(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(
            command,
            {"taskId"},
            optional={"sessionId", "content", "status", "position"},
        )
        self._require_selected_session(command.session_id)
        assert command.session_id is not None
        session_id = command.session_id
        payload_session = command.payload.get("sessionId")
        if payload_session is not None and payload_session != session_id:
            raise GatewayError("invalid_session")

        task_id = command.payload.get("taskId")
        if not isinstance(task_id, str) or not task_id.strip():
            raise GatewayError("invalid_task_id")

        try:
            with SQLiteEventStore(self._database) as store:
                todos = store.list_todos(session_id)
                existing = next((t for t in todos if t.id == task_id), None)
                if not existing:
                    raise GatewayError("task_not_found")

                content = command.payload.get("content")
                if content is not None and (
                    not isinstance(content, str)
                    or not content.strip()
                    or len(content.strip()) > _MAX_TASK_CONTENT_CHARS
                ):
                    raise GatewayError("invalid_content")
                target_content = content.strip() if isinstance(content, str) else existing.content

                raw_status = command.payload.get("status")
                if raw_status is not None and raw_status not in {
                    "pending",
                    "in_progress",
                    "completed",
                }:
                    raise GatewayError("invalid_status")
                target_status = raw_status if isinstance(raw_status, str) else existing.status.value

                pos = command.payload.get("position")
                if pos is not None and (type(pos) is not int or not 0 <= pos <= _MAX_TASK_POSITION):
                    raise GatewayError("invalid_position")
                target_pos = pos if isinstance(pos, int) else existing.position

                event = Event(
                    session_id=session_id,
                    type="todo.upserted",
                    data={
                        "todo_id": task_id,
                        "content": target_content,
                        "status": target_status,
                        "position": target_pos,
                    },
                )
                store.append(event)
                updated_item = next(
                    (t for t in store.list_todos(session_id) if t.id == task_id), None
                )
                task_doc: dict[str, object] = {
                    "id": task_id,
                    "sessionId": session_id,
                    "content": target_content,
                    "status": target_status,
                    "position": target_pos,
                    "createdAt": updated_item.created_at if updated_item else existing.created_at,
                    "updatedAt": updated_item.updated_at if updated_item else event.created_at,
                }
        except GatewayError:
            raise
        except (OSError, sqlite3.DatabaseError, ValueError):
            raise GatewayError("storage_unavailable") from None

        return self._reply(
            "workspace.tasks.update.result",
            {
                "epoch": self.epoch,
                "sessionId": session_id,
                "task": task_doc,
            },
            session_id=command.session_id,
        )

    def _delete_task(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"taskId"}, optional={"sessionId"})
        self._require_selected_session(command.session_id)
        assert command.session_id is not None
        session_id = command.session_id
        payload_session = command.payload.get("sessionId")
        if payload_session is not None and payload_session != session_id:
            raise GatewayError("invalid_session")

        task_id = command.payload.get("taskId")
        if not isinstance(task_id, str) or not task_id.strip():
            raise GatewayError("invalid_task_id")

        try:
            with SQLiteEventStore(self._database) as store:
                if not any(t.id == task_id for t in store.list_todos(session_id)):
                    raise GatewayError("task_not_found")
                event = Event(
                    session_id=session_id,
                    type="todo.deleted",
                    data={"todo_id": task_id},
                )
                store.append(event)
        except GatewayError:
            raise
        except (OSError, sqlite3.DatabaseError, ValueError):
            raise GatewayError("storage_unavailable") from None

        return self._reply(
            "workspace.tasks.delete.result",
            {
                "epoch": self.epoch,
                "sessionId": session_id,
                "taskId": task_id,
                "success": True,
            },
            session_id=command.session_id,
        )

    def _control_service(self) -> AgentControlService:
        if self._workspace is None:
            raise GatewayError("runtime_unconfigured")
        service = self._agent_control
        if service is None:
            try:
                service = AgentControlService(self._database)
                service.recover_interrupted_runs(self._workspace)
            except (OSError, sqlite3.DatabaseError, RuntimeError):
                raise GatewayError("storage_unavailable") from None
            self._agent_control = service
        return service

    @staticmethod
    def _run_document(run: AgentRun) -> dict[str, object]:
        raw = cast(dict[str, object], asdict(run))
        return {_camel_case(key): _json_safe(value) for key, value in raw.items()}

    @staticmethod
    def _step_document(step: PlanStep) -> dict[str, object]:
        raw = cast(dict[str, object], asdict(step))
        return {_camel_case(key): _json_safe(value) for key, value in raw.items()}

    @staticmethod
    def _attention_document(item: AttentionItem) -> dict[str, object]:
        raw = cast(dict[str, object], asdict(item))
        return {_camel_case(key): _json_safe(value) for key, value in raw.items()}

    def _list_agent_runs(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"states", "limit"})
        if self._workspace is None:
            raise GatewayError("runtime_unconfigured")
        raw_states = command.payload.get("states")
        states: tuple[AgentRunState, ...] | None = None
        if raw_states is not None:
            if not isinstance(raw_states, list) or len(raw_states) > 20:
                raise GatewayError("invalid_state")
            try:
                states = tuple(AgentRunState(cast(str, state)) for state in raw_states)
            except (TypeError, ValueError):
                raise GatewayError("invalid_state") from None
        limit = command.payload.get("limit", 200)
        if type(limit) is not int or not 1 <= limit <= 1_000:
            raise GatewayError("invalid_limit")
        try:
            runs = self._control_service().list_runs(self._workspace, states=states, limit=limit)
        except (AgentControlError, OSError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "workspace.runs.list.result",
            {"epoch": self.epoch, "runs": [self._run_document(run) for run in runs]},
            session_id=command.session_id,
        )

    def _get_agent_run(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"runId"})
        run_id = command.payload.get("runId")
        if not isinstance(run_id, str) or not run_id:
            raise GatewayError("invalid_run")
        try:
            run = self._control_service().get_run(run_id)
        except (OSError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        if run is None or self._workspace is None or run.workspace != str(self._workspace):
            raise GatewayError("run_not_found")
        steps = self._control_service().list_plan_steps(run_id)
        attention = self._control_service().list_attention(run_id=run_id, state=AttentionState.OPEN)
        execution_database = self._agent_run_database(run_id, self._database)
        requested, usage = SQLiteEventStore.latest_model_context_read_only(
            execution_database, run.session_id
        )
        previews = SQLiteEventStore.list_message_previews_read_only(
            execution_database, run.session_id, limit=30, max_content_chars=12000
        )
        execution_session = SQLiteEventStore.get_session_read_only(
            execution_database, run.session_id
        ) or SQLiteEventStore.get_session_read_only(self._database, run.session_id)
        outputs = [item for item in previews if item.role is Role.ASSISTANT and item.content]
        manifest = (
            dict(requested.data["context_manifest"])
            if requested and isinstance(requested.data.get("context_manifest"), dict)
            else None
        )
        if manifest is not None and requested is not None:
            manifest.update(requestId=requested.id, createdAt=requested.created_at)
        phases = self._phase_projection(run, steps)
        return self._reply(
            "workspace.runs.get.result",
            {
                "epoch": self.epoch,
                "run": self._run_document(run),
                "autonomy": execution_session.autonomy.value if execution_session else None,
                "steps": [self._step_document(step) for step in steps],
                "phases": phases,
                "attention": [self._attention_document(item) for item in attention],
                "resultText": outputs[-1].content if outputs else "",
                "resultTruncated": outputs[-1].truncated if outputs else False,
                "history": [
                    {
                        "role": item.role.value,
                        "content": item.content,
                        "sequence": item.sequence,
                        "truncated": item.truncated,
                    }
                    for item in previews
                ],
                "manifest": manifest,
                "lastUsage": {
                    "inputTokens": usage.data.get("input_tokens", 0),
                    "outputTokens": usage.data.get("output_tokens", 0),
                    "cachedTokens": usage.data.get("cached_tokens", 0),
                    "estimated": usage.data.get("estimated", True),
                }
                if usage
                else None,
            },
            session_id=run.session_id,
        )

    @staticmethod
    def _phase_projection(run: AgentRun, steps: list[PlanStep]) -> list[dict[str, object]]:
        """Expose plan steps as a stable, replayable phase projection."""

        phases: list[dict[str, object]] = []
        for step in steps:
            failure_class: str | None = None
            if step.state is PlanStepState.FAILED:
                failure_class = "permanent"
            elif step.state is PlanStepState.BLOCKED:
                failure_class = "user_action"
            phases.append(
                {
                    "id": step.id,
                    "label": step.title,
                    "state": step.state.value,
                    "progress": 1.0
                    if step.state is PlanStepState.COMPLETED
                    else 0.5
                    if step.state is PlanStepState.RUNNING
                    else 0.0,
                    "attempts": 0,
                    "failureClass": failure_class,
                    "failureReason": run.blocking_reason if failure_class else None,
                    "requiresUserAction": step.state is PlanStepState.BLOCKED,
                }
            )
        return phases

    def _create_agent_run(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(
            command,
            {"goal"},
            optional={"title", "isolation", "parentRunId", "sessionId"},
        )
        if self._workspace is None:
            raise GatewayError("runtime_unconfigured")
        session_id = command.payload.get(
            "sessionId", command.session_id or self._selected_session_id
        )
        if not isinstance(session_id, str) or not session_id:
            raise GatewayError("invalid_session")
        goal = command.payload.get("goal")
        title = command.payload.get("title")
        parent_run_id = command.payload.get("parentRunId")
        if not isinstance(goal, str) or not goal.strip():
            raise GatewayError("invalid_goal")
        if title is not None and not isinstance(title, str):
            raise GatewayError("invalid_title")
        if parent_run_id is not None and not isinstance(parent_run_id, str):
            raise GatewayError("invalid_run")
        raw_isolation = command.payload.get("isolation", "worktree")
        if raw_isolation == "auto":
            # Its own branch in a git repository; elsewhere the run works in the folder itself.
            try:
                git_head_sha(self._workspace)
                raw_isolation = RunIsolation.WORKTREE.value
            except GitOpsError:
                raw_isolation = RunIsolation.SHARED.value
        try:
            isolation = RunIsolation(cast(str, raw_isolation))
        except (TypeError, ValueError):
            raise GatewayError("invalid_isolation") from None
        try:
            run = self._control_service().create_run(
                workspace=self._workspace,
                session_id=session_id,
                goal=goal,
                title=title,
                isolation=isolation,
                parent_run_id=parent_run_id,
            )
        except AgentControlError as error:
            raise GatewayError(str(error)) from None
        except (OSError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "workspace.runs.create.result",
            {"epoch": self.epoch, "run": self._run_document(run)},
            session_id=run.session_id,
        )

    def _update_agent_run(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(
            command,
            {"runId"},
            optional={"state", "title", "goal", "activeStepId", "blockingReason"},
        )
        run_id = command.payload.get("runId")
        if not isinstance(run_id, str) or not run_id:
            raise GatewayError("invalid_run")
        raw_state = command.payload.get("state")
        try:
            state = AgentRunState(cast(str, raw_state)) if raw_state is not None else None
        except (TypeError, ValueError):
            raise GatewayError("invalid_state") from None
        for field in ("title", "goal", "activeStepId", "blockingReason"):
            if command.payload.get(field) is not None and not isinstance(
                command.payload[field], str
            ):
                raise GatewayError("invalid_command")
        try:
            existing = self._control_service().get_run(run_id)
            if (
                existing is None
                or self._workspace is None
                or existing.workspace != str(self._workspace)
            ):
                raise GatewayError("run_not_found")
            update_fields: dict[str, Any] = {"state": state}
            # Keep omitted lifecycle fields intact. A JSON null remains an
            # explicit clear and is passed through to AgentControlService.
            for payload_key, service_key in (
                ("title", "title"),
                ("goal", "goal"),
                ("activeStepId", "active_step_id"),
                ("blockingReason", "blocking_reason"),
            ):
                if payload_key in command.payload:
                    update_fields[service_key] = command.payload[payload_key]
            run = self._control_service().update_run(run_id, **update_fields)
        except GatewayError:
            raise
        except AgentControlError as error:
            raise GatewayError(str(error)) from None
        except (OSError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "workspace.runs.update.result",
            {"epoch": self.epoch, "run": self._run_document(run)},
            session_id=run.session_id,
        )

    def _start_agent_run(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"runId"})
        if self._workspace is None or self._provider is None:
            raise GatewayError("runtime_unconfigured")
        run_id = command.payload.get("runId")
        if not isinstance(run_id, str) or not run_id:
            raise GatewayError("invalid_run")
        service = self._control_service()
        run = service.get_run(run_id)
        if run is None or run.workspace != str(self._workspace):
            raise GatewayError("run_not_found")
        if run.state in {
            AgentRunState.SUCCEEDED,
            AgentRunState.FAILED,
            AgentRunState.CANCELLED,
        }:
            raise GatewayError("terminal_run")
        if self._run_has_pending_approval(run_id, service):
            raise GatewayError("approval_pending")
        if run_id in self._run_preparing or run_id in self._run_hosts:
            raise GatewayError("run_already_active")
        active_count = len(self._run_preparing) + sum(
            not entry.terminal for entry in self._run_hosts.values()
        )
        if active_count >= _MAX_PARALLEL_AGENT_RUNS:
            raise GatewayError("run_concurrency_limit")
        self._check_monthly_cap()
        try:
            run = service.update_run(
                run_id,
                state=AgentRunState.STARTING,
                blocking_reason=None,
            )
        except AgentControlError as error:
            raise GatewayError(str(error)) from None
        self._run_preparing.add(run_id)
        self._run_cancel_requested.discard(run_id)
        provider = self._provider
        workspace = self._workspace
        autonomy = self._autonomy
        worker = threading.Thread(
            target=self._prepare_agent_run,
            args=(run_id, workspace, provider, autonomy, service),
            name=f"agent-run-prepare-{run_id[:8]}",
            daemon=True,
        )
        self._run_prepare_threads[run_id] = worker
        worker.start()
        return self._reply(
            "workspace.runs.start.result",
            {"epoch": self.epoch, "run": self._run_document(run), "accepted": True},
            session_id=run.session_id,
        )

    @staticmethod
    def _agent_run_database(run_id: str, control_database: Path) -> Path:
        digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        return control_database.parent / (control_database.stem + "-runs") / (digest + ".db")

    def _prepare_agent_run(
        self,
        run_id: str,
        workspace: Path,
        provider: ProviderConfig,
        autonomy: Autonomy,
        service: AgentControlService,
    ) -> None:
        run: AgentRun | None = None
        try:
            run = service.get_run(run_id)
            if run is None:
                raise AgentControlError("unknown_run")
            checkout = workspace
            branch: str | None = None
            base_sha: str | None = None
            if run.checkout_path is not None:
                checkout = Path(run.checkout_path).resolve()
                if not checkout.is_dir() or (
                    run.isolation is RunIsolation.WORKTREE
                    and not checkout.is_relative_to(workspace / ".worktrees" / "agent-runs")
                ):
                    raise AgentControlError("run_checkout_unavailable")
                branch = run.branch
                base_sha = run.base_sha
            elif run.isolation is RunIsolation.WORKTREE:
                branch = f"codex/run-{run_id[:12]}"
                relative = Path("agent-runs") / run_id[:12]
                info = git_worktree_add(workspace, relative, branch=branch)
                checkout = Path(info.path).resolve()
                branch = info.branch
                base_sha = info.head
                service.record_checkout(
                    run_id,
                    checkout_path=str(checkout),
                    branch=branch,
                    base_sha=base_sha,
                )
            else:
                with suppress(GitOpsError):
                    base_sha = git_head_sha(workspace)

            execution_database = self._agent_run_database(run_id, service.database)
            execution_database.parent.mkdir(parents=True, exist_ok=True)
            with SQLiteEventStore(execution_database) as execution_store:
                session = execution_store.get_session(run.session_id)
                if session is None:
                    session = Session(
                        workspace=str(checkout), mode=Mode.TASK, autonomy=autonomy, title=run.title
                    )
                    execution_store.create_session(session)
                # Resuming must preserve the run's policy, independently of the owner tab.
                autonomy = session.autonomy
            with SQLiteEventStore(service.database) as store:
                if store.get_session(session.id) is None:
                    store.create_session(session)
            service.bind_execution_context(
                run_id,
                session_id=session.id,
                checkout_path=str(checkout),
                branch=branch,
                base_sha=base_sha,
            )
            with self._lock:
                if run_id in self._run_cancel_requested:
                    service.finish_run(
                        run_id, AgentRunState.CANCELLED, reason="cancelled_before_start"
                    )
                    self._emit_run_update(run_id, session.id, "cancelled")
                    return
                host = self._host_factory(
                    RuntimeSettings(
                        workspace=checkout,
                        database=execution_database,
                        provider=provider,
                        mode=Mode.TASK,
                        autonomy=autonomy,
                        session_id=session.id,
                        extra_tools=(self._skill_tool,),
                        system_note=self._system_note,
                        workspace_tools=self._folder_tools,
                        tool_hooks=self._coding.hooks,
                    )
                )
                entry = _RunHostEntry(
                    run_id=run_id,
                    session_id=session.id,
                    goal=run.goal,
                    host=host,
                )
                self._run_hosts[run_id] = entry
                host.start()
                self._emit_run_update(run_id, session.id, "starting")
        except Exception as error:
            with suppress(Exception):
                failed = service.finish_run(
                    run_id,
                    AgentRunState.FAILED,
                    reason="run_start_failed",
                )
                service.open_attention(
                    run_id=run_id,
                    session_id=failed.session_id,
                    kind=AttentionKind.FAILURE,
                    severity="critical",
                    title="Agent run could not start",
                    detail=str(error)[:2_000],
                    source_key=f"run-start:{run_id}",
                    action={"kind": "inspect_run", "runId": run_id},
                )
            with self._lock:
                self._run_hosts.pop(run_id, None)
                session_id = run.session_id if run is not None else "desktop"
                self._emit_run_update(run_id, session_id, "failed")
        finally:
            with self._lock:
                self._run_preparing.discard(run_id)
                self._run_prepare_threads.pop(run_id, None)

    def _run_has_pending_approval(self, run_id: str, service: AgentControlService) -> bool:
        """Keep a pending approval attached to its live host until it is resolved."""
        if any(
            approval.run_id == run_id and approval.state != "resolved"
            for approval in self._approval_ledger.values()
        ):
            return True
        with suppress(Exception):
            return any(
                item.kind in {AttentionKind.APPROVAL, AttentionKind.INPUT}
                for item in service.list_attention(run_id=run_id, state=AttentionState.OPEN)
            )
        return False

    def _shutdown_paused_run_host(
        self, run_id: str, entry: _RunHostEntry, *, deadline: float | None = None
    ) -> bool:
        """Drain a paused run host before allowing a replacement host to start."""
        deadline = deadline or self._clock() + _LIFECYCLE_TIMEOUT_SECONDS
        with suppress(Exception):
            future = entry.host.request_shutdown()
            if future is not None:
                future.result(timeout=max(0.0, deadline - self._clock()))
        with suppress(Exception):
            entry.host.join(timeout=max(0.0, deadline - self._clock()))
        if entry.host.is_alive():
            return False
        self._run_hosts.pop(run_id, None)
        return True

    def _pause_agent_run(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"runId"})
        run_id = command.payload.get("runId")
        if not isinstance(run_id, str) or not run_id:
            raise GatewayError("invalid_run")
        service = self._control_service()
        run = service.get_run(run_id)
        if run is None or self._workspace is None or run.workspace != str(self._workspace):
            raise GatewayError("run_not_found")
        try:
            requested = service.request_pause(run_id)
        except AgentControlError as error:
            raise GatewayError(str(error)) from None
        self._emit_run_update(run_id, requested.session_id, requested.state.value)
        return self._reply(
            "workspace.runs.pause.result",
            {
                "epoch": self.epoch,
                "run": self._run_document(requested),
                "pauseRequested": requested.pause_requested,
            },
            session_id=requested.session_id,
        )

    def _resume_agent_run(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"runId"})
        run_id = command.payload.get("runId")
        if not isinstance(run_id, str) or not run_id:
            raise GatewayError("invalid_run")
        service = self._control_service()
        run = service.get_run(run_id)
        if run is None or self._workspace is None or run.workspace != str(self._workspace):
            raise GatewayError("run_not_found")
        if run.state in {AgentRunState.SUCCEEDED, AgentRunState.FAILED, AgentRunState.CANCELLED}:
            raise GatewayError("terminal_run")
        # A pause request can coexist with an approval that is blocking the
        # active turn. Surface that blocker before the paused-state guard so a
        # resume attempt cannot accidentally bypass the approval workflow.
        pending_approval = self._run_has_pending_approval(run_id, service)
        if pending_approval and run.pause_requested:
            raise GatewayError("approval_pending")
        if (
            run.state is not AgentRunState.NEEDS_ATTENTION
            or run.blocking_reason != "paused_by_user"
        ):
            raise GatewayError("run_not_paused")
        # The previous run host may still be draining its shutdown after the
        # turn boundary. It is no longer authoritative once marked terminal.
        if pending_approval:
            raise GatewayError("approval_pending")
        entry = self._run_hosts.get(run_id)
        if entry is not None:
            if not entry.terminal and entry.host.is_alive():
                raise GatewayError("run_already_active")
            if not self._shutdown_paused_run_host(run_id, entry):
                raise GatewayError("run_shutdown_pending")
        try:
            started = self._start_agent_run(command)
        except GatewayError:
            raise
        resumed = service.get_run(run_id)
        if resumed is None:
            raise GatewayError("run_not_found")
        return self._reply(
            "workspace.runs.resume.result",
            {
                "epoch": self.epoch,
                "run": self._run_document(resumed),
                "accepted": bool(started.payload.get("accepted", True)),
            },
            session_id=resumed.session_id,
        )

    def _cancel_agent_run(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"runId"})
        run_id = command.payload.get("runId")
        if not isinstance(run_id, str) or not run_id:
            raise GatewayError("invalid_run")
        service = self._control_service()
        run = service.get_run(run_id)
        if (
            run is None
            or self._workspace is None
            or (
                run.workspace != str(self._workspace)
                and run_id not in self._run_hosts
                and run_id not in self._run_preparing
            )
        ):
            raise GatewayError("run_not_found")
        if run.state in {
            AgentRunState.SUCCEEDED,
            AgentRunState.FAILED,
            AgentRunState.CANCELLED,
        }:
            return self._reply(
                "workspace.runs.cancel.result",
                {"epoch": self.epoch, "run": self._run_document(run), "cancelRequested": False},
                session_id=run.session_id,
            )
        entry = self._run_hosts.get(run_id)
        self._run_cancel_requested.add(run_id)
        if entry is None:
            if run_id not in self._run_preparing:
                run = service.finish_run(
                    run_id, AgentRunState.CANCELLED, reason="cancelled_by_user"
                )
                self._emit_run_update(run_id, run.session_id, "cancelled")
        else:
            future = entry.host.request_cancel_turn()
            if future is None:
                raise GatewayError("runtime_unavailable")
        return self._reply(
            "workspace.runs.cancel.result",
            {"epoch": self.epoch, "run": self._run_document(run), "cancelRequested": True},
            session_id=run.session_id,
        )

    def _cleanup_agent_run(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"runId"})
        run_id = command.payload.get("runId")
        if not isinstance(run_id, str) or not run_id:
            raise GatewayError("invalid_run")
        run = self._control_service().get_run(run_id)
        if run is None or self._workspace is None or run.workspace != str(self._workspace):
            raise GatewayError("run_not_found")
        if run_id in self._run_hosts or run_id in self._run_preparing:
            raise GatewayError("run_active")
        if run.state not in {
            AgentRunState.SUCCEEDED,
            AgentRunState.FAILED,
            AgentRunState.CANCELLED,
        }:
            raise GatewayError("run_not_terminal")
        if run.isolation is not RunIsolation.WORKTREE or run.checkout_path is None:
            return self._reply(
                "workspace.runs.cleanup.result",
                {"epoch": self.epoch, "run": self._run_document(run), "cleaned": False},
                session_id=run.session_id,
            )
        try:
            if not git_worktree_is_clean(run.checkout_path):
                raise GatewayError("worktree_dirty")
            git_worktree_remove(self._workspace, run.checkout_path, force=False)
            run = self._control_service().clear_checkout(run_id)
        except GatewayError:
            raise
        except (AgentControlError, GitOpsError, OSError):
            raise GatewayError("worktree_cleanup_failed") from None
        return self._reply(
            "workspace.runs.cleanup.result",
            {"epoch": self.epoch, "run": self._run_document(run), "cleaned": True},
            session_id=run.session_id,
        )

    def _emit_run_update(self, run_id: str, session_id: str, state: str) -> None:
        delegation = self._delegations.get(run_id)
        data: dict[str, Any] = {"run_id": run_id, "state": state}
        if delegation is not None and delegation.parent_session_id == session_id:
            # A delegated run not started yet (waiting for a free slot) is still reported under
            # its conversation: the window shows the sub-agent as about to start.
            data.update(title=delegation.title, delegated=True, **_expert_fields(delegation))
        self._pending_host_events.append(
            Event(session_id=session_id, type="agent.run.updated", data=data)
        )
        if delegation is not None and delegation.parent_session_id != session_id:
            self._pending_host_events.append(
                Event(
                    session_id=delegation.parent_session_id,
                    type="agent.run.updated",
                    data={
                        "run_id": run_id,
                        "state": state,
                        "title": delegation.title,
                        "delegated": True,
                        **_expert_fields(delegation),
                    },
                )
            )

    def _subagent_documents(self) -> list[dict[str, object]]:
        """The sub-agents conversations wait on now, for a window that resynchronises: events it
        dropped while it waited for a snapshot (a run queued for a free slot) are not sent again.
        """
        documents: list[dict[str, object]] = []
        if not self._delegations:
            return documents
        with suppress(Exception):  # an unreadable run database leaves the list short
            service = self._control_service()
            for run_id, delegation in list(self._delegations.items()):
                run = service.get_run(run_id)
                if run is None:
                    continue
                documents.append(
                    {
                        "runId": run_id,
                        "sessionId": delegation.parent_session_id,
                        "title": delegation.title,
                        "state": run.state.value,
                        **_expert_fields(delegation),
                    }
                )
        return documents

    def _emit_delegated_activity(self, run_id: str, activity: str, tool: str | None) -> None:
        """What a sub-agent is doing now (thinking, or which tool), for its conversation."""
        delegation = self._delegations.get(run_id)
        if delegation is None:
            return
        self._pending_host_events.append(
            Event(
                session_id=delegation.parent_session_id,
                type="agent.run.activity",
                data={
                    "run_id": run_id,
                    "activity": activity,
                    **({"tool": tool} if tool else {}),
                    **_expert_fields(delegation),
                },
            )
        )

    async def _run_delegated_tasks(
        self, parent_session_id: str, tasks: Sequence[SubagentTask]
    ) -> list[SubagentOutcome]:
        """A conversation's delegate_tasks call: start each task as an agent run, wait for all.

        Runs in the conversation host's event loop, so every step that takes the gateway lock
        goes to a worker thread; the lock holder may itself be waiting on this loop.

        On an expert team's turn no expert holds up the answer: runs still working at the time
        limit are stopped and reported as cancelled ("time_limit") with what they recorded, and
        the lead answers from the rest.
        """
        team_turn = parent_session_id in self._team_turns
        run_ids = await asyncio.to_thread(self._create_delegated_runs, parent_session_id, tasks)
        loop = asyncio.get_running_loop()
        started = loop.time()
        over_time: list[str] = []
        finished = False
        try:
            while not await asyncio.to_thread(self._advance_delegated_runs, run_ids):
                if team_turn and loop.time() - started >= _EXPERT_TIME_LIMIT_SECONDS:
                    over_time = await asyncio.to_thread(
                        self._cancel_delegated_runs, run_ids, forget=False
                    )
                    # Their cancelled state still reaches the conversation's expert cards.
                    wind_down = loop.time() + _EXPERT_STOP_GRACE_SECONDS
                    while loop.time() < wind_down and not await asyncio.to_thread(
                        self._delegated_runs_finished, run_ids
                    ):
                        await asyncio.sleep(_DELEGATION_POLL_SECONDS)
                    break
                await asyncio.sleep(_DELEGATION_POLL_SECONDS)
            finished = True
        finally:
            if not finished:  # the conversation's turn was stopped: stop its sub-agents too
                await asyncio.shield(asyncio.to_thread(self._cancel_delegated_runs, run_ids))
        return await asyncio.to_thread(self._delegated_outcomes, run_ids, over_time)

    def _create_delegated_runs(
        self, parent_session_id: str, tasks: Sequence[SubagentTask]
    ) -> list[str]:
        with self._lock:
            workspace = self._workspace
            if workspace is None or self._provider is None or self._closing:
                raise SubagentLaunchError("Sub-agents need an open folder and a model")
        if any(task.isolation == "worktree" for task in tasks):
            try:
                git_head_sha(workspace)
            except GitOpsError:
                raise SubagentLaunchError(
                    "'worktree' needs a git repository with at least one commit; "
                    "use 'shared' in this folder"
                ) from None
        run_ids: list[str] = []
        with self._lock:
            service = self._control_service()
            team = self._team_turns.get(parent_session_id)
            phase = None
            if team is not None and any(task.expert for task in tasks):
                # The first call hands out the parts, later ones review the findings.
                phase = "review" if team.rounds else "work"
                team.rounds += 1
            for task in tasks:
                expert = find_expert(team.team, task.expert) if team is not None else None
                try:
                    run = service.create_run(
                        workspace=workspace,
                        session_id=parent_session_id,
                        goal=team_goal(expert, task.goal) if expert is not None else task.goal,
                        title=task.title,
                        isolation=RunIsolation(task.isolation),
                    )
                except (AgentControlError, OSError, sqlite3.DatabaseError) as error:
                    for created in run_ids:
                        with suppress(Exception):
                            service.finish_run(
                                created, AgentRunState.CANCELLED, reason="delegation_not_started"
                            )
                        self._delegations.pop(created, None)
                    raise SubagentLaunchError(
                        f"A sub-agent could not be created: {error}"
                    ) from None
                run_ids.append(run.id)
                self._delegations[run.id] = _Delegation(
                    parent_session_id,
                    task.title,
                    expert.id if expert is not None else None,
                    phase if expert is not None else None,
                )
                self._emit_run_update(run.id, run.session_id, run.state.value)
        return run_ids

    def _delegated_run_finished(self, run: AgentRun, service: AgentControlService) -> bool:
        if run.state in {AgentRunState.SUCCEEDED, AgentRunState.FAILED, AgentRunState.CANCELLED}:
            return True
        if run.state is not AgentRunState.NEEDS_ATTENTION:
            return False
        # Stopped for the user (paused, plan to verify, no progress): report it rather than wait.
        entry = self._run_hosts.get(run.id)
        if entry is not None and not entry.terminal and entry.host.is_alive():
            return False
        return not self._run_has_pending_approval(run.id, service)

    def _advance_delegated_runs(self, run_ids: Sequence[str]) -> bool:
        """Start delegated runs as slots free up; True once every one of them has finished."""
        with self._lock:
            service = self._control_service()
            finished = True
            for run_id in run_ids:
                run = service.get_run(run_id)
                if run is None or self._delegated_run_finished(run, service):
                    continue
                finished = False
                if run.state is not AgentRunState.DRAFT or run_id in self._run_preparing:
                    continue
                try:
                    with self._unsent():
                        self._start_agent_run(
                            CommandEnvelope(
                                v=PROTOCOL_VERSION,
                                request_id=f"delegate-{run_id}",
                                type="workspace.runs.start",
                                payload={"runId": run_id},
                                session_id=run.session_id,
                            )
                        )
                except GatewayError as error:
                    if str(error) in {"run_concurrency_limit", "run_already_active"}:
                        continue  # starts once another run finishes
                    with suppress(Exception):
                        failed = service.finish_run(run_id, AgentRunState.FAILED, reason=str(error))
                        self._emit_run_update(run_id, failed.session_id, failed.state.value)
            return finished

    def _delegated_runs_finished(self, run_ids: Sequence[str]) -> bool:
        with self._lock:
            service = self._control_service()
            return all(
                run is None or self._delegated_run_finished(run, service)
                for run in map(service.get_run, run_ids)
            )

    def _cancel_delegated_runs(self, run_ids: Sequence[str], *, forget: bool = True) -> list[str]:
        """Stop the runs still working and return their ids.

        ``forget`` also drops every run from the conversation, once its turn no longer waits.
        """
        stopped: list[str] = []
        with self._lock:
            service = self._control_service()
            for run_id in run_ids:
                run = service.get_run(run_id)
                if run is not None and run.state not in {
                    AgentRunState.SUCCEEDED,
                    AgentRunState.FAILED,
                    AgentRunState.CANCELLED,
                }:
                    stopped.append(run_id)
                    with suppress(GatewayError, AgentControlError), self._unsent():
                        self._cancel_agent_run(
                            CommandEnvelope(
                                v=PROTOCOL_VERSION,
                                request_id=f"delegate-cancel-{run_id}",
                                type="workspace.runs.cancel",
                                payload={"runId": run_id},
                                session_id=run.session_id,
                            )
                        )
                if forget:
                    self._delegations.pop(run_id, None)
        return stopped

    def _delegated_outcomes(
        self, run_ids: Sequence[str], over_time: Sequence[str] = ()
    ) -> list[SubagentOutcome]:
        with self._lock:
            service = self._control_service()
            runs = [service.get_run(run_id) for run_id in run_ids]
            for run_id in run_ids:
                self._delegations.pop(run_id, None)
        outcomes: list[SubagentOutcome] = []
        for run_id, run in zip(run_ids, runs, strict=True):
            if run is None:
                outcomes.append(SubagentOutcome(run_id, "", "failed", "", reason="run_missing"))
                continue
            answer = ""
            with suppress(Exception):  # an unreadable run database leaves the answer empty
                previews = SQLiteEventStore.list_message_previews_read_only(
                    self._agent_run_database(run_id, self._database),
                    run.session_id,
                    limit=8,
                    max_content_chars=_DELEGATION_ANSWER_CHARS,
                )
                last = next(
                    (
                        item
                        for item in reversed(previews)
                        if item.role is Role.ASSISTANT and item.content
                    ),
                    None,
                )
                if last is not None:
                    answer = last.content + (
                        "\n[shortened; the full answer is on the Agent runs page]"
                        if last.truncated
                        else ""
                    )
            # Stopped at the time limit, unless it finished on its own in the meantime.
            stopped = run_id in over_time and run.state not in {
                AgentRunState.SUCCEEDED,
                AgentRunState.FAILED,
            }
            outcomes.append(
                SubagentOutcome(
                    run_id=run_id,
                    title=run.title,
                    state=AgentRunState.CANCELLED.value if stopped else run.state.value,
                    answer=answer,
                    branch=run.branch if run.isolation is RunIsolation.WORKTREE else None,
                    reason="time_limit" if stopped else run.blocking_reason,
                )
            )
        return outcomes

    def _ensure_phase_graph(self, entry: _RunHostEntry, steps: list[PlanStep]) -> TaskGraph:
        ids = tuple(step.id for step in steps)
        if (
            entry.phase_graph is not None
            and tuple(phase.id for phase in entry.phase_graph.phases()) == ids
        ):
            return entry.phase_graph
        graph = TaskGraph(max_attempts=3)
        for step in steps:
            graph.add_phase(step.id, step.title)
        for step in steps:
            for dependency in step.dependencies:
                if dependency in ids:
                    graph.add_dependency(step.id, dependency)
        entry.phase_graph = graph
        return graph

    def _emit_phase_event(
        self,
        run_id: str,
        session_id: str,
        phase: PlanStep,
        event_name: str,
        *,
        progress: float | None = None,
        failure_class: str | None = None,
        reason: str | None = None,
        retryable: bool | None = None,
        requires_user_action: bool | None = None,
    ) -> None:
        data: dict[str, object] = {
            "run_id": run_id,
            "phase_id": phase.id,
            "phase_name": phase.title,
            "state": phase.state.value,
        }
        if progress is not None:
            data["progress"] = max(0.0, min(1.0, progress))
        if failure_class is not None:
            data["failure_class"] = failure_class
        if reason is not None:
            data["reason"] = reason[:2_000]
        if retryable is not None:
            data["retryable"] = retryable
        if requires_user_action is not None:
            data["requires_user_action"] = requires_user_action
        self._pending_host_events.append(
            Event(session_id=session_id, type=f"task.phase.{event_name}", data=data)
        )

    def _list_plan_steps(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"runId"})
        run_id = command.payload.get("runId")
        if not isinstance(run_id, str) or not run_id:
            raise GatewayError("invalid_run")
        run = self._control_service().get_run(run_id)
        if run is None or self._workspace is None or run.workspace != str(self._workspace):
            raise GatewayError("run_not_found")
        steps = self._control_service().list_plan_steps(run_id)
        return self._reply(
            "workspace.plan.list.result",
            {
                "epoch": self.epoch,
                "runId": run_id,
                "steps": [self._step_document(s) for s in steps],
            },
            session_id=run.session_id,
        )

    def _create_plan_step(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(
            command,
            {"runId", "title"},
            optional={"detail", "acceptance", "position", "dependencies"},
        )
        run_id = command.payload.get("runId")
        title = command.payload.get("title")
        position = command.payload.get("position", 0)
        dependencies = command.payload.get("dependencies", [])
        if not isinstance(run_id, str) or not isinstance(title, str):
            raise GatewayError("invalid_command")
        if (
            type(position) is not int
            or not isinstance(dependencies, list)
            or not all(isinstance(item, str) for item in dependencies)
        ):
            raise GatewayError("invalid_command")
        detail = command.payload.get("detail", "")
        acceptance = command.payload.get("acceptance", "")
        if not isinstance(detail, str) or not isinstance(acceptance, str):
            raise GatewayError("invalid_command")
        try:
            run = self._control_service().get_run(run_id)
            if run is None or self._workspace is None or run.workspace != str(self._workspace):
                raise GatewayError("run_not_found")
            step = self._control_service().create_plan_step(
                run_id,
                title=title,
                detail=detail,
                acceptance=acceptance,
                position=position,
                dependencies=cast(list[str], dependencies),
            )
        except GatewayError:
            raise
        except AgentControlError as error:
            raise GatewayError(str(error)) from None
        return self._reply(
            "workspace.plan.create.result",
            {"epoch": self.epoch, "step": self._step_document(step)},
            session_id=run.session_id,
        )

    def _update_plan_step(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(
            command,
            {"stepId"},
            optional={
                "title",
                "detail",
                "acceptance",
                "state",
                "position",
                "dependencies",
                "evidence",
            },
        )
        step_id = command.payload.get("stepId")
        if not isinstance(step_id, str) or not step_id:
            raise GatewayError("invalid_step")
        existing = self._control_service().get_plan_step(step_id)
        if existing is None:
            raise GatewayError("step_not_found")
        run = self._control_service().get_run(existing.run_id)
        if run is None or self._workspace is None or run.workspace != str(self._workspace):
            raise GatewayError("step_not_found")
        raw_state = command.payload.get("state")
        try:
            state = PlanStepState(cast(str, raw_state)) if raw_state is not None else None
        except (TypeError, ValueError):
            raise GatewayError("invalid_state") from None
        dependencies = command.payload.get("dependencies")
        evidence = command.payload.get("evidence")
        if dependencies is not None and (
            not isinstance(dependencies, list)
            or not all(isinstance(item, str) for item in dependencies)
        ):
            raise GatewayError("invalid_dependencies")
        if evidence is not None and (
            not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence)
        ):
            raise GatewayError("invalid_evidence")
        try:
            step = self._control_service().update_plan_step(
                step_id,
                title=cast(str | None, command.payload.get("title")),
                detail=cast(str | None, command.payload.get("detail")),
                acceptance=cast(str | None, command.payload.get("acceptance")),
                state=state,
                position=cast(int | None, command.payload.get("position")),
                dependencies=cast(list[str] | None, dependencies),
                evidence=cast(list[str] | None, evidence),
            )
        except AgentControlError as error:
            raise GatewayError(str(error)) from None
        service = self._control_service()
        current_run = service.get_run(run.id)
        if (
            current_run is not None
            and current_run.state is AgentRunState.NEEDS_ATTENTION
            and (current_run.blocking_reason or "").startswith(
                (
                    "plan_verification",
                    "plan-verification",
                    "goal_no_progress",
                    "goal-no-progress",
                )
            )
        ):
            remaining = service.list_plan_steps(run.id)
            if all(
                item.state in {PlanStepState.COMPLETED, PlanStepState.SKIPPED} for item in remaining
            ):
                service.update_run(run.id, state=AgentRunState.SUCCEEDED)
                for source_key in (
                    f"plan-verification:{run.id}",
                    f"goal-no-progress:{run.id}",
                ):
                    service.resolve_attention_by_source(source_key, resolution={"verified": True})
                self._emit_run_update(run.id, run.session_id, "succeeded")
        return self._reply(
            "workspace.plan.update.result",
            {"epoch": self.epoch, "step": self._step_document(step)},
            session_id=run.session_id,
        )

    def _delete_plan_step(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"stepId"})
        step_id = command.payload.get("stepId")
        if not isinstance(step_id, str) or not step_id:
            raise GatewayError("invalid_step")
        step = self._control_service().get_plan_step(step_id)
        if step is None:
            raise GatewayError("step_not_found")
        run = self._control_service().get_run(step.run_id)
        if run is None or self._workspace is None or run.workspace != str(self._workspace):
            raise GatewayError("step_not_found")
        try:
            deleted = self._control_service().delete_plan_step(step_id)
        except AgentControlError as error:
            raise GatewayError(str(error)) from None
        return self._reply(
            "workspace.plan.delete.result",
            {"epoch": self.epoch, "stepId": step_id, "success": deleted},
            session_id=run.session_id,
        )

    def _list_attention(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"runId", "state", "limit"})
        if self._workspace is None:
            raise GatewayError("runtime_unconfigured")
        raw_state = command.payload.get("state", "open")
        try:
            state = AttentionState(cast(str, raw_state)) if raw_state is not None else None
        except (TypeError, ValueError):
            raise GatewayError("invalid_state") from None
        run_id = command.payload.get("runId")
        if run_id is not None and not isinstance(run_id, str):
            raise GatewayError("invalid_run")
        limit = command.payload.get("limit", 500)
        if type(limit) is not int or not 1 <= limit <= 1_000:
            raise GatewayError("invalid_limit")
        items = self._control_service().list_attention(
            run_id=run_id,
            workspace=self._workspace,
            state=state,
            limit=limit,
        )
        return self._reply(
            "workspace.attention.list.result",
            {"epoch": self.epoch, "items": [self._attention_document(item) for item in items]},
            session_id=command.session_id,
        )

    def _resolve_attention(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"attentionId"}, optional={"resolution", "dismissed"})
        attention_id = command.payload.get("attentionId")
        resolution = command.payload.get("resolution")
        dismissed = command.payload.get("dismissed", False)
        if not isinstance(attention_id, str) or not attention_id:
            raise GatewayError("invalid_attention")
        if resolution is not None and not isinstance(resolution, Mapping):
            raise GatewayError("invalid_resolution")
        if type(dismissed) is not bool:
            raise GatewayError("invalid_resolution")
        service = self._control_service()
        existing = service.get_attention(attention_id)
        if existing is None:
            raise GatewayError("unknown_attention")
        if (
            (existing.source_key or "").startswith("plan-verification:")
            and existing.run_id
            and any(
                step.state not in {PlanStepState.COMPLETED, PlanStepState.SKIPPED}
                for step in service.list_plan_steps(existing.run_id)
            )
        ):
            raise GatewayError("plan_incomplete")
        if (
            existing.kind is AttentionKind.APPROVAL
            and existing.source_key is not None
            and existing.source_key.startswith("approval:")
        ):
            request_id = existing.source_key.removeprefix("approval:")
            action_request_id = existing.action.get("requestId")
            if action_request_id is not None and action_request_id != request_id:
                raise GatewayError("invalid_attention")
            entry = self._approval_ledger.get(request_id)
            if entry is None and existing.run_id is not None:
                # The durable attention row outlives the in-memory approval
                # ledger across turn boundaries. Rebuild the smallest entry
                # needed to route the decision back to the live child host.
                run_entry = self._run_hosts.get(existing.run_id)
                if run_entry is None or run_entry.terminal or not run_entry.host.is_alive():
                    raise GatewayError("runtime_unavailable")
                action_payload = {
                    key: _bounded_projection(value)
                    for key, value in existing.action.items()
                    if key in _APPROVAL_DISPLAY_FIELDS
                }
                entry = _ApprovalEntry(
                    existing.session_id,
                    action_payload,
                    source_host=run_entry.host,
                    run_id=existing.run_id,
                )
                self._approval_ledger[request_id] = entry
            if entry is not None and entry.state == "pending":
                raw_scope = resolution.get("scope") if isinstance(resolution, Mapping) else None
                if raw_scope is None:
                    scope: ApprovalScope | None = None
                else:
                    try:
                        scope = ApprovalScope(cast(str, raw_scope))
                    except (TypeError, ValueError):
                        raise GatewayError("invalid_approval") from None
                if (
                    scope is ApprovalScope.SESSION
                    and entry.payload.get("supportsSessionScope") is not True
                ):
                    raise GatewayError("invalid_approval")
                target = entry.source_host
                if target is None:
                    raise GatewayError("runtime_unavailable")
                future = target.resolve_approval(request_id, scope)
                if future is None:
                    raise GatewayError("runtime_unavailable")
                try:
                    future.result(timeout=_COMMAND_TIMEOUT_SECONDS)
                except Exception:
                    raise GatewayError("runtime_unavailable") from None
                self._commit_approval_resolution(request_id, entry, scope)
                resolved = service.get_attention(attention_id)
                if resolved is not None:
                    return self._reply(
                        "workspace.attention.resolve.result",
                        {"epoch": self.epoch, "item": self._attention_document(resolved)},
                        session_id=resolved.session_id,
                    )
        try:
            item = service.resolve_attention(
                attention_id,
                resolution=cast(Mapping[str, object] | None, resolution),
                dismissed=dismissed,
            )
        except AgentControlError as error:
            raise GatewayError(str(error)) from None
        return self._reply(
            "workspace.attention.resolve.result",
            {"epoch": self.epoch, "item": self._attention_document(item)},
            session_id=item.session_id,
        )

    @staticmethod
    def _run_queue_enqueue_sync(
        queue: DurableRunQueue,
        workspace: str,
        prompt: str,
        model: str,
        *,
        priority: int,
    ) -> Any:
        """Run the async queue API from the synchronous Gateway thread."""

        coroutine = queue.enqueue(workspace, prompt, model, priority=priority)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)
        result: list[Any] = []
        failure: list[BaseException] = []

        def run_in_thread() -> None:
            try:
                result.append(asyncio.run(coroutine))
            except BaseException as error:  # pragma: no cover - defensive bridge
                failure.append(error)

        worker = threading.Thread(target=run_in_thread, name="schedule-queue-enqueue")
        worker.start()
        worker.join()
        if failure:
            raise failure[0]
        return result[0]

    @staticmethod
    def _queue_document(task: Any) -> dict[str, object]:
        return {
            "id": task.id,
            "workspace": task.workspace,
            "prompt": task.prompt,
            "model": task.model,
            "status": task.status.value,
            "error": task.error,
            "createdAt": task.created_at,
            "updatedAt": task.updated_at,
            "priority": task.priority,
            "owner": task.owner,
            "leaseUntil": task.lease_until,
            "attempt": task.attempt,
        }

    def _queue_command(self, command: CommandEnvelope) -> GatewayReply:
        if self._workspace is None:
            raise GatewayError("runtime_unconfigured")
        action = command.type.rsplit(".", 1)[-1]
        self._require_payload(
            command,
            {"taskId"} if action == "get" else set(),
            optional={"taskId", "status", "limit", "workspace"},
        )
        raw_status = command.payload.get("status")
        status: RunQueueStatus | None = None
        if raw_status is not None:
            try:
                status = RunQueueStatus(cast(str, raw_status))
            except (TypeError, ValueError):
                raise GatewayError("invalid_status") from None
        workspace = command.payload.get("workspace", str(self._workspace))
        if not isinstance(workspace, str) or not workspace:
            raise GatewayError("invalid_workspace")
        if Path(workspace).expanduser().resolve() != self._workspace:
            raise GatewayError("invalid_workspace")
        with SQLiteEventStore(self._database) as event_store:
            queue = DurableRunQueue(event_store)
            tasks = queue.list(status=status, workspace=workspace)
        payload: dict[str, object]
        if action == "get":
            task_id = command.payload.get("taskId")
            task = next((item for item in tasks if item.id == task_id), None)
            if task is None:
                raise GatewayError("queue_task_not_found")
            payload = {"epoch": self.epoch, "task": self._queue_document(task)}
        else:
            limit = command.payload.get("limit", 200)
            if type(limit) is not int or not 1 <= limit <= 1_000:
                raise GatewayError("invalid_limit")
            payload = {
                "epoch": self.epoch,
                "tasks": [self._queue_document(item) for item in tasks[:limit]],
                "counts": {
                    state.value: sum(item.status is state for item in tasks)
                    for state in RunQueueStatus
                },
                "truncated": len(tasks) > limit,
            }
        return self._reply(f"{command.type}.result", payload, session_id=command.session_id)

    def _orchestration_command(self, command: CommandEnvelope) -> GatewayReply:
        runtime = self._orchestration_runtime
        if runtime is None:
            raise GatewayError("orchestration_unavailable")
        payload: dict[str, object]
        parts = command.type.split(".")
        if len(parts) != 3:
            raise GatewayError("unsupported_command")
        kind = "collaboration" if parts[1] == "collaborations" else "delivery"
        action = parts[2]
        if action == "list":
            self._require_payload(command, set(), optional={"limit"})
            limit = command.payload.get("limit", 50)
            if type(limit) is not int or not 1 <= limit <= 250:
                raise GatewayError("invalid_limit")
            method = getattr(runtime, f"list_{kind}s", None)
            if method is None:
                raise GatewayError("orchestration_unavailable")
            try:
                values = method(limit=limit)
            except ValueError:
                raise GatewayError("invalid_orchestration") from None
            payload = {
                "epoch": self.epoch,
                "items": [self._orchestration_document(item) for item in values],
            }
            return self._reply(f"{command.type}.result", payload, session_id=command.session_id)

        self._require_payload(
            command,
            {"id", "sessionId"},
            optional={
                "id",
                "sessionId",
                "reason",
                "routeId",
                "maxCycles",
                "resumeBlocked",
            },
        )
        workflow_id = command.payload["id"]
        session_id = command.payload["sessionId"]
        if not isinstance(workflow_id, str) or not workflow_id:
            raise GatewayError("invalid_orchestration_id")
        if not isinstance(session_id, str) or not session_id:
            raise GatewayError("invalid_session")
        from agent_workspace.core.orchestration import CollaborationHandle, DeliveryHandle

        handle = (
            CollaborationHandle(workflow_id, session_id)
            if kind == "collaboration"
            else DeliveryHandle(workflow_id, session_id)
        )
        if action == "get":
            method = getattr(runtime, f"inspect_{kind}", None)
            if method is None:
                raise GatewayError("orchestration_unavailable")
            try:
                value = method(handle)
            except (KeyError, ValueError):
                raise GatewayError("orchestration_not_found") from None
        elif action == "cancel":
            reason = command.payload.get("reason", f"{kind} cancelled by gateway caller")
            if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
                raise GatewayError("invalid_cancel_reason")
            method = getattr(runtime, f"cancel_{kind}", None)
            if method is None:
                raise GatewayError("orchestration_unavailable")
            try:
                value = self._await_orchestration(method(handle, reason=reason))
            except (KeyError, ValueError):
                raise GatewayError("orchestration_not_found") from None
        elif action == "resume":
            if kind == "collaboration":
                method = getattr(runtime, "resume_collaboration", None)
                if method is None:
                    raise GatewayError("orchestration_unavailable")
                try:
                    value = self._await_orchestration(method(handle))
                except (KeyError, ValueError):
                    raise GatewayError("orchestration_not_found") from None
            else:
                route_id = command.payload.get("routeId")
                if not isinstance(route_id, str) or not route_id:
                    raise GatewayError("invalid_route")
                max_cycles = command.payload.get("maxCycles")
                if max_cycles is not None and (
                    type(max_cycles) is not int or not 1 <= max_cycles <= 10_000
                ):
                    raise GatewayError("invalid_max_cycles")
                resume_blocked = command.payload.get("resumeBlocked", False)
                if type(resume_blocked) is not bool:
                    raise GatewayError("invalid_resume_blocked")
                try:
                    loop = getattr(runtime, "delivery_loop", lambda _route: None)(route_id)
                except (KeyError, ValueError):
                    raise GatewayError("invalid_route") from None
                if loop is None:
                    raise GatewayError("orchestration_unavailable")
                try:
                    value = self._await_orchestration(
                        loop.resume(
                            handle,
                            max_cycles=max_cycles,
                            resume_blocked=resume_blocked,
                        )
                    )
                except (KeyError, ValueError):
                    raise GatewayError("orchestration_not_found") from None
        else:
            raise GatewayError("unsupported_command")
        payload = {
            "epoch": self.epoch,
            "item": self._orchestration_document(value),
        }
        return self._reply(f"{command.type}.result", payload, session_id=command.session_id)

    @staticmethod
    def _await_orchestration(value: object) -> object:
        if not inspect.isawaitable(value):
            return value
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_await_value(cast(Awaitable[object], value)))
        raise GatewayError("orchestration_async_context")

    @classmethod
    def _orchestration_document(cls, value: object) -> dict[str, object]:
        to_document = getattr(value, "to_document", None)
        if callable(to_document):
            document = to_document()
            if isinstance(document, Mapping):
                return dict(document)
        converted = cls._jsonable_orchestration(value)
        if not isinstance(converted, Mapping):
            raise GatewayError("invalid_orchestration_result")
        return dict(converted)

    @classmethod
    def _jsonable_orchestration(cls, value: object) -> object:
        if isinstance(value, Enum):
            return value.value
        if is_dataclass(value) and not isinstance(value, type):
            raw = asdict(cast(Any, value))
            return {key: cls._jsonable_orchestration(item) for key, item in raw.items()}
        if isinstance(value, Mapping):
            return {str(key): cls._jsonable_orchestration(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [cls._jsonable_orchestration(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    def _run_continuity_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.type in {"run.history.page", "workspace.runs.history"}:
            return self._run_history_page(command)
        if command.type in {"run.evidence.page", "workspace.runs.evidence"}:
            return self._run_evidence_page(command)
        return self._run_failure_step_action(command)

    def _run_for_gateway(self, run_id: str) -> AgentRun:
        run = self._control_service().get_run(run_id)
        if run is None or self._workspace is None or run.workspace != str(self._workspace):
            raise GatewayError("run_not_found")
        return run

    def _run_history_page(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(
            command,
            {"runId"},
            optional={"limit", "before", "cursor", "cutoff", "epoch"},
        )
        run_id = command.payload.get("runId")
        if not isinstance(run_id, str) or not run_id:
            raise GatewayError("invalid_run")
        run = self._run_for_gateway(run_id)
        requested_epoch = command.payload.get("epoch")
        if requested_epoch is not None and requested_epoch != self.epoch:
            raise GatewayError("stale_epoch")
        limit = command.payload.get("limit", 100)
        if type(limit) is not int or not 1 <= limit <= 500:
            raise GatewayError("invalid_limit")
        cursor_value = command.payload.get("before", command.payload.get("cursor"))
        before: int | None = None
        cutoff = command.payload.get("cutoff")
        if cutoff is not None and (type(cutoff) is not int or cutoff < 0):
            raise GatewayError("invalid_cursor")
        if cursor_value is not None:
            if not isinstance(cursor_value, str):
                raise GatewayError("invalid_cursor")
            before, encoded_cutoff = self._decode_run_cursor(cursor_value, run_id)
            cutoff = encoded_cutoff if cutoff is None else cutoff
        execution_database = self._agent_run_database(run_id, self._database)
        if cutoff is None:
            latest = SQLiteEventStore.list_events_page_read_only(
                execution_database, run.session_id, limit=1
            )
            cutoff = int(latest[0].sequence or 0) if latest else 0
        events = SQLiteEventStore.list_events_page_read_only(
            execution_database,
            run.session_id,
            limit=limit + 1,
            before_sequence=before,
            cutoff_sequence=cutoff,
        )
        has_more = len(events) > limit
        page = events[:limit]
        next_cursor = (
            self._encode_run_cursor(run_id, int(page[-1].sequence or 0), int(cutoff or 0))
            if has_more and page
            else None
        )
        payload = {
            "epoch": self.epoch,
            "runId": run_id,
            "sessionId": run.session_id,
            "cutoff": cutoff,
            "items": [self._timeline_event(event) for event in page],
            "hasMore": has_more,
            "nextCursor": next_cursor,
        }
        return self._reply(f"{command.type}.result", payload, session_id=run.session_id)

    def _run_evidence_page(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"runId"}, optional={"stepId", "limit", "cursor"})
        run_id = command.payload.get("runId")
        if not isinstance(run_id, str) or not run_id:
            raise GatewayError("invalid_run")
        run = self._run_for_gateway(run_id)
        step_id = command.payload.get("stepId")
        if step_id is not None and not isinstance(step_id, str):
            raise GatewayError("invalid_step")
        steps = self._control_service().list_plan_steps(run_id)
        if step_id is not None and not any(step.id == step_id for step in steps):
            raise GatewayError("step_not_found")
        entries = [
            {"stepId": step.id, "stepTitle": step.title, "index": index, "evidence": evidence}
            for step in steps
            if step_id is None or step.id == step_id
            for index, evidence in enumerate(step.evidence)
        ]
        limit = command.payload.get("limit", 100)
        if type(limit) is not int or not 1 <= limit <= 500:
            raise GatewayError("invalid_limit")
        offset = 0
        cursor = command.payload.get("cursor")
        if cursor is not None:
            if not isinstance(cursor, str):
                raise GatewayError("invalid_cursor")
            offset = self._decode_evidence_cursor(cursor, run_id)
        page = entries[offset : offset + limit]
        has_more = offset + len(page) < len(entries)
        next_cursor = self._encode_evidence_cursor(run_id, offset + len(page)) if has_more else None
        return self._reply(
            f"{command.type}.result",
            {
                "epoch": self.epoch,
                "runId": run_id,
                "stepId": step_id,
                "items": page,
                "hasMore": has_more,
                "nextCursor": next_cursor,
            },
            session_id=run.session_id,
        )

    def _run_failure_step_action(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"stepId"}, optional={"action"})
        step_id = command.payload.get("stepId")
        if not isinstance(step_id, str) or not step_id:
            raise GatewayError("invalid_step")
        step = self._control_service().get_plan_step(step_id)
        if step is None:
            raise GatewayError("step_not_found")
        run = self._run_for_gateway(step.run_id)
        action = command.payload.get("action")
        if action is None:
            action = "skip" if command.type.endswith("skip") else "retry"
        if action not in {"retry", "skip"}:
            raise GatewayError("invalid_action")
        state = PlanStepState.PENDING if action == "retry" else PlanStepState.SKIPPED
        updated = self._control_service().update_plan_step(step_id, state=state)
        return self._reply(
            f"{command.type}.result",
            {"epoch": self.epoch, "step": self._step_document(updated), "action": action},
            session_id=run.session_id,
        )

    def _project_agent_run_event(
        self,
        run_id: str,
        event_type: str,
        payload: Mapping[str, object],
        session_id: str,
        *,
        source_host: Host | None,
    ) -> None:
        entry = self._run_hosts.get(run_id)
        if (
            entry is None
            or entry.session_id != session_id
            or (source_host is not None and entry.host is not source_host)
        ):
            return
        service = self._control_service()
        run = service.get_run(run_id)
        if run is None or entry.terminal:
            return
        if event_type == "model.requested":
            self._emit_delegated_activity(run_id, "thinking", None)
        elif event_type == "tool.started":
            tool = payload.get("toolName") or payload.get("name")
            self._emit_delegated_activity(run_id, "tool", str(tool)[:64] if tool else None)
        attempt_id = payload.get("attemptId") or payload.get("toolCallId")
        if event_type == "tool.proposed":
            # Rejected calls often never emit tool.started.  Record the proposal
            # against the selected phase so permission/argument failures remain
            # visible and actionable instead of disappearing from the phase tree.
            if (
                isinstance(attempt_id, str)
                and run.active_step_id
                and len(entry.step_attempts) < 256
            ):
                entry.step_attempts[attempt_id] = run.active_step_id
                self._ensure_phase_graph(entry, service.list_plan_steps(run_id))
            return
        if event_type == "tool.started":
            if (
                isinstance(attempt_id, str)
                and run.active_step_id
                and len(entry.step_attempts) < 256
            ):
                entry.step_attempts[attempt_id] = run.active_step_id
                steps = service.list_plan_steps(run_id)
                graph = self._ensure_phase_graph(entry, steps)
                phase = next((item for item in steps if item.id == run.active_step_id), None)
                if phase is not None:
                    with suppress(Exception):
                        if graph.phase(phase.id).state.value == "queued":
                            graph.start(phase.id)
                    self._emit_phase_event(run_id, session_id, phase, "started", progress=0.05)
            return
        if event_type in {
            "tool.settled",
            "tool.failed",
            "tool.cancelled",
            "tool.rejected",
            "tool.unknown",
        }:
            step_id = entry.step_attempts.pop(str(attempt_id), None)
            event_id = payload.get("eventId")
            if step_id and isinstance(event_id, str):
                tool_name = str(payload.get("toolName") or payload.get("name") or "tool")[:128]
                evidence = f"{event_type} 路 {tool_name} 路 event:{event_id}"
                service.append_plan_step_evidence(step_id, (evidence,))
                phase = service.get_plan_step(step_id)
                if phase is not None:
                    if event_type in {
                        "tool.failed",
                        "tool.rejected",
                        "tool.cancelled",
                        "tool.unknown",
                    }:
                        reason = str(payload.get("error") or payload.get("reason") or event_type)
                        category = classify_failure(reason)
                        graph = self._ensure_phase_graph(entry, service.list_plan_steps(run_id))
                        decision = None
                        with suppress(Exception):
                            graph_phase = graph.phase(phase.id)
                            if (
                                graph_phase.state.value == "queued"
                                and phase.id in graph.ready_phases()
                            ):
                                graph.start(phase.id)
                            decision = graph.record_failure(
                                phase.id, reason, failure_class=category
                            )
                        self._emit_phase_event(
                            run_id,
                            session_id,
                            phase,
                            "failed",
                            progress=0.0,
                            failure_class=(
                                decision.failure_class.value
                                if decision is not None
                                else category.value
                            ),
                            reason=reason,
                            retryable=(decision.retryable if decision is not None else False),
                            requires_user_action=(
                                decision.requires_user_action
                                if decision is not None
                                else category.value
                                in {"permission", "invalid_arguments", "user_action"}
                            ),
                        )
                    else:
                        self._emit_phase_event(run_id, session_id, phase, "progress", progress=0.8)
                self._emit_run_update(run_id, session_id, run.state.value)
            return
        if event_type in _TERMINAL_TURN_EVENTS and run.active_step_id:
            event_id = payload.get("eventId")
            if isinstance(event_id, str):
                service.append_plan_step_evidence(
                    run.active_step_id, (f"{event_type} 路 event:{event_id}",)
                )
        if event_type == "runtime.started":
            if entry.submitted:
                return
            if run.pause_requested:
                try:
                    paused = service.apply_pause(run_id)
                    entry.terminal = True
                    self._run_cancel_requested.discard(run_id)
                    if not self._run_has_pending_approval(run_id, service):
                        self._shutdown_paused_run_host(run_id, entry)
                    self._emit_run_update(run_id, entry.session_id, paused.state.value)
                except Exception as error:
                    self._fail_agent_run(run_id, entry, "pause_apply_failed", error)
                return
            try:
                step = service.select_ready_step(run_id)
                steps = service.list_plan_steps(run_id)
                plan = "\n".join(
                    f"{index + 1}. [{item.state.value}] {item.title}\n"
                    f"Step ID: {item.id}\n"
                    f"Depends on: {', '.join(item.dependencies) or 'none'}\n"
                    f"Acceptance: {item.acceptance}"
                    for index, item in enumerate(steps)
                )
                prompt = (
                    entry.goal
                    if not steps
                    else entry.goal
                    + "\n\nExecution plan:\n"
                    + plan
                    + "\nDo not repeat completed or skipped steps. "
                    "Continue with unverified steps using the existing workspace and history. "
                    "Pause only for irreversible/external actions, a scope decision, missing "
                    "user-only information, or a hard permission/resource limit. Recover "
                    "ordinary tool failures or use an approved fallback. "
                    "Report concrete verification outcomes for each step; "
                    "do not claim unverified criteria passed."
                )
                limits = self._task_limits()
                kwargs: dict[str, Any] = {}
                if limits is not None:
                    kwargs["limits"] = limits
                delegation = self._delegations.get(run_id)
                tools = (
                    team_tools(delegation.expert, expert_tools(delegation.expert))
                    if delegation and delegation.expert
                    else None
                )
                if tools is not None and _accepts(entry.host.submit_turn, "tools"):
                    kwargs["tools"] = tools
                entry.host.submit_turn(prompt, **kwargs)
                entry.submitted = True
                service.update_run(
                    run_id, state=AgentRunState.RUNNING, active_step_id=step.id if step else None
                )
                self._emit_run_update(run_id, entry.session_id, "running")
            except Exception as error:
                self._fail_agent_run(run_id, entry, "turn_start_failed", error)
            return
        if event_type == "turn.started":
            raw_turn = payload.get("turnId") or payload.get("correlationId")
            service.update_run(
                run_id,
                state=AgentRunState.RUNNING,
                active_turn_id=str(raw_turn or "active"),
                active_step_id=run.active_step_id,
            )
            return
        if event_type == "approval.requested":
            request_id = payload.get("requestId")
            if not isinstance(request_id, str) or not request_id:
                return
            approval_payload = {
                key: _bounded_projection(value)
                for key, value in payload.items()
                if key in _APPROVAL_DISPLAY_FIELDS
            }
            self._approval_ledger.setdefault(
                request_id,
                _ApprovalEntry(
                    None if session_id == "desktop" else session_id,
                    approval_payload,
                    source_host=source_host or entry.host,
                    run_id=run_id,
                ),
            )
            service.open_attention(
                run_id=run_id,
                session_id=entry.session_id,
                kind=AttentionKind.APPROVAL,
                severity="warning",
                title=str(
                    approval_payload.get("tool")
                    or approval_payload.get("toolName")
                    or "Approval required"
                ),
                detail=str(approval_payload.get("summary") or "Review the requested action."),
                source_key=f"approval:{request_id}",
                action={
                    "kind": "resolve_approval",
                    "requestId": request_id,
                    "supportsSessionScope": approval_payload.get("supportsSessionScope") is True,
                },
            )
            self._pending_host_events.append(
                Event(
                    session_id=entry.session_id,
                    type="agent.attention.updated",
                    data={"run_id": run_id, "attention_kind": "approval"},
                )
            )
            delegation = self._delegations.get(run_id)
            if delegation is not None:
                # A sub-agent's question is answered where the user asked for the work.
                self._pending_host_events.append(
                    Event(
                        session_id=delegation.parent_session_id,
                        type="approval.requested",
                        data={
                            "request_id": request_id,
                            "tool": approval_payload.get("tool")
                            or approval_payload.get("toolName"),
                            "summary": approval_payload.get("summary"),
                            "supports_session_scope": approval_payload.get("supportsSessionScope")
                            is True,
                            "subagent": delegation.title,
                        },
                    )
                )
            return
        if event_type == "approval.resolved":
            request_id = payload.get("requestId")
            if isinstance(request_id, str):
                with suppress(Exception):
                    service.resolve_attention_by_source(
                        f"approval:{request_id}",
                        resolution={"allowed": payload.get("allowed")},
                    )
            return
        if event_type in _TERMINAL_TURN_EVENTS:
            if event_type == "turn.completed" and run.pause_requested:
                try:
                    paused = service.apply_pause(run_id)
                    if run.active_step_id:
                        phase = service.get_plan_step(run.active_step_id)
                        if phase is not None:
                            self._emit_phase_event(
                                run_id,
                                session_id,
                                phase,
                                "paused",
                                reason="paused_by_user",
                                requires_user_action=True,
                            )
                    entry.terminal = True
                    self._run_cancel_requested.discard(run_id)
                    if not self._run_has_pending_approval(run_id, service):
                        self._shutdown_paused_run_host(run_id, entry)
                    self._emit_run_update(run_id, entry.session_id, paused.state.value)
                except Exception as error:
                    self._fail_agent_run(run_id, entry, "pause_apply_failed", error)
                return
            no_progress = False
            if event_type == "turn.completed":
                execution_database = self._agent_run_database(run_id, self._database)
                previews = SQLiteEventStore.list_message_previews_read_only(
                    execution_database, run.session_id, limit=8, max_content_chars=12_000
                )
                last_assistant = next(
                    (
                        item
                        for item in reversed(previews)
                        if item.role is Role.ASSISTANT and item.content
                    ),
                    None,
                )
                if last_assistant is not None:
                    result_digest = hashlib.sha256(
                        last_assistant.content.encode("utf-8")
                    ).hexdigest()
                    if result_digest == entry.last_result_digest:
                        entry.no_progress_count += 1
                    else:
                        entry.last_result_digest = result_digest
                        entry.no_progress_count = 0
                if entry.no_progress_count >= 1:
                    no_progress = True
                steps = service.list_plan_steps(run_id)
                remaining = [
                    step
                    for step in steps
                    if step.state not in {PlanStepState.COMPLETED, PlanStepState.SKIPPED}
                ]
                open_attention = service.list_attention(run_id=run_id, state=AttentionState.OPEN)
                if (
                    remaining
                    and entry.submitted
                    and not no_progress
                    and not open_attention
                    and entry.continuation_count < _MAX_AGENT_RUN_CONTINUATIONS
                ):
                    entry.continuation_count += 1
                    next_step = service.select_ready_step(run_id)
                    plan = "\n".join(
                        f"{index + 1}. [{item.state.value}] {item.title}\n"
                        f"Step ID: {item.id}\nAcceptance: {item.acceptance}"
                        for index, item in enumerate(service.list_plan_steps(run_id))
                    )
                    continuation = (
                        f"Continue the task from durable history. This is continuation slice "
                        f"{entry.continuation_count}/{_MAX_AGENT_RUN_CONTINUATIONS}.\n"
                        f"Goal: {entry.goal}\nExecution plan:\n{plan}\n"
                        "Do not repeat completed or skipped steps. Continue unverified steps, "
                        "recover ordinary tool failures, and report concrete evidence. "
                        "Stop only for a real approval, user-only decision, or hard resource limit."
                    )
                    try:
                        limits = self._task_limits()
                        if limits is not None:
                            entry.host.submit_turn(continuation, limits=limits)
                        else:
                            entry.host.submit_turn(continuation)
                        service.update_run(
                            run_id,
                            state=AgentRunState.RUNNING,
                            active_step_id=next_step.id if next_step else run.active_step_id,
                            blocking_reason=None,
                        )
                        self._emit_run_update(run_id, entry.session_id, "running")
                        return
                    except Exception as error:
                        self._fail_agent_run(run_id, entry, "continuation_start_failed", error)
                        return
            graph = self._ensure_phase_graph(entry, service.list_plan_steps(run_id))
            for phase in service.list_plan_steps(run_id):
                if phase.state in {PlanStepState.COMPLETED, PlanStepState.SKIPPED}:
                    with suppress(Exception):
                        if graph.phase(phase.id).state.value == "running":
                            graph.complete(phase.id)
                    self._emit_phase_event(run_id, session_id, phase, "completed", progress=1.0)
            target = (
                AgentRunState.SUCCEEDED
                if event_type == "turn.completed"
                else AgentRunState.CANCELLED
                if event_type == "turn.cancelled"
                else AgentRunState.FAILED
            )
            terminal_reason: str | None = (
                str(payload.get("reason") or payload.get("error") or "") or None
            )
            if no_progress:
                terminal_reason = "goal_no_progress"
            finished_run = service.finish_run(run_id, target, reason=terminal_reason)
            if finished_run.state is AgentRunState.NEEDS_ATTENTION:
                service.open_attention(
                    run_id=run_id,
                    session_id=entry.session_id,
                    kind=AttentionKind.REVIEW,
                    severity="warning",
                    title="Plan verification required",
                    detail="Execution ended; verify each remaining acceptance criterion.",
                    source_key=f"plan-verification:{run_id}",
                    action={"kind": "inspect_run", "runId": run_id},
                )
            if no_progress:
                service.open_attention(
                    run_id=run_id,
                    session_id=entry.session_id,
                    kind=AttentionKind.REVIEW,
                    severity="warning",
                    title="Goal made no progress",
                    detail=(
                        "The last continuation repeated the same result. Re-plan or update "
                        "the acceptance criteria before continuing."
                    ),
                    source_key=f"goal-no-progress:{run_id}",
                    action={"kind": "inspect_run", "runId": run_id},
                )
            entry.terminal = True
            self._run_cancel_requested.discard(run_id)
            if target is AgentRunState.FAILED:
                service.open_attention(
                    run_id=run_id,
                    session_id=entry.session_id,
                    kind=AttentionKind.FAILURE,
                    severity="critical",
                    title="Agent run failed",
                    detail=terminal_reason or "Inspect the run timeline and retry the failed step.",
                    source_key=f"run-failed:{run_id}",
                    action={"kind": "inspect_run", "runId": run_id},
                )
            for request_id in [
                key for key, approval in self._approval_ledger.items() if approval.run_id == run_id
            ]:
                self._approval_ledger.pop(request_id, None)
            with suppress(Exception):
                entry.host.request_shutdown()
            self._emit_run_update(run_id, entry.session_id, finished_run.state.value)
            return
        if event_type in {"runtime.failed", "runtime.command_rejected"}:
            self._fail_agent_run(
                run_id,
                entry,
                "runtime_failed",
                RuntimeError(str(payload.get("reason") or "Agent runtime failed.")),
            )
            return
        if event_type == "runtime.stopped":
            self._run_hosts.pop(run_id, None)

    def _fail_agent_run(
        self,
        run_id: str,
        entry: _RunHostEntry,
        reason: str,
        error: Exception,
    ) -> None:
        if entry.terminal:
            return
        entry.terminal = True
        service = self._control_service()
        with suppress(Exception):
            service.finish_run(run_id, AgentRunState.FAILED, reason=reason)
            service.open_attention(
                run_id=run_id,
                session_id=entry.session_id,
                kind=AttentionKind.FAILURE,
                severity="critical",
                title="Agent run failed",
                detail=str(error)[:2_000],
                source_key=f"run-failed:{run_id}",
                action={"kind": "inspect_run", "runId": run_id},
            )
        with suppress(Exception):
            entry.host.request_shutdown()
        self._emit_run_update(run_id, entry.session_id, "failed")

    def _encode_run_cursor(self, run_id: str, before: int, cutoff: int) -> str:
        body = json.dumps(["run-history", run_id, cutoff, before], separators=(",", ":")).encode()
        encoded = base64.urlsafe_b64encode(body).rstrip(b"=").decode()
        signature = hmac.new(self._cursor_key, encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def _decode_run_cursor(self, cursor: str, run_id: str) -> tuple[int, int]:
        try:
            encoded, signature = cursor.split(".", 1)
            expected = hmac.new(self._cursor_key, encoded.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            padding = "=" * (-len(encoded) % 4)
            document = json.loads(base64.urlsafe_b64decode(encoded + padding))
            if (
                not isinstance(document, list)
                or len(document) != 4
                or document[0] != "run-history"
                or document[1] != run_id
                or type(document[2]) is not int
                or type(document[3]) is not int
                or document[2] < 0
                or document[3] <= 0
                or document[3] > document[2]
            ):
                raise ValueError
            return document[3], document[2]
        except (ValueError, TypeError, json.JSONDecodeError):
            raise GatewayError("invalid_cursor") from None

    def _encode_evidence_cursor(self, run_id: str, offset: int) -> str:
        body = json.dumps(["run-evidence", run_id, offset], separators=(",", ":")).encode()
        encoded = base64.urlsafe_b64encode(body).rstrip(b"=").decode()
        signature = hmac.new(self._cursor_key, encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def _decode_evidence_cursor(self, cursor: str, run_id: str) -> int:
        try:
            encoded, signature = cursor.split(".", 1)
            expected = hmac.new(self._cursor_key, encoded.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            padding = "=" * (-len(encoded) % 4)
            document = json.loads(base64.urlsafe_b64decode(encoded + padding))
            if (
                not isinstance(document, list)
                or len(document) != 3
                or document[0] != "run-evidence"
                or document[1] != run_id
                or type(document[2]) is not int
                or document[2] < 0
            ):
                raise ValueError
            return document[2]
        except (ValueError, TypeError, json.JSONDecodeError):
            raise GatewayError("invalid_cursor") from None
