from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agent_workspace.application.event_bus import EventBus
from agent_workspace.application.ports import (
    EgressPolicyPort,
    EventStore,
    ModelProvider,
    PolicyPort,
    ToolRegistryPort,
)
from agent_workspace.application.prompt_context import resolve_workspace_prompt_context
from agent_workspace.application.runner import AgentRunner, RunResult
from agent_workspace.application.shutdown import settle_tasks
from agent_workspace.core.budgets import TaskBudget
from agent_workspace.core.events import Event
from agent_workspace.core.models import (
    Autonomy,
    ChatMessage,
    ContentTrust,
    ImagePart,
    Mode,
)
from agent_workspace.core.prompt_assembly import PromptAssembler
from agent_workspace.core.raw_trace import RawConversationTrace
from agent_workspace.core.session import Session
from agent_workspace.optimizations import ModelRequestOptimizer

_ACTIVE_RUN_CLOSE_TIMEOUT_SECONDS = 5.0


def _consume_active_run(task: asyncio.Task[Any]) -> None:
    if not task.cancelled():
        task.exception()


class ApplicationService:
    def __init__(
        self,
        store: EventStore,
        provider: ModelProvider,
        tools: ToolRegistryPort,
        policy: PolicyPort,
        events: EventBus | None = None,
        *,
        egress_policy: EgressPolicyPort,
        execution_workspace: str | Path | None = None,
        execution_autonomy: Autonomy | None = None,
        optimizer: ModelRequestOptimizer | None = None,
        prompt_assembler: PromptAssembler | None = None,
        parallel_tool_calls: bool = False,
        profile_turns: bool = False,
        raw_trace: RawConversationTrace | None = None,
    ) -> None:
        self.store = store
        self._tools = tools
        self._provider = provider
        self.events = events or EventBus()
        self._execution_workspace = (
            Path(execution_workspace).resolve(strict=True)
            if execution_workspace is not None
            else None
        )
        self._execution_autonomy = execution_autonomy
        self._active_runs: set[asyncio.Task[Any]] = set()
        self._closing = False
        self._closed = False
        self._close_lock = asyncio.Lock()
        self.runner = AgentRunner(
            store,
            provider,
            tools,
            policy,
            self.events,
            egress_policy=egress_policy,
            optimizer=optimizer,
            prompt_assembler=prompt_assembler,
            parallel_tool_calls=parallel_tool_calls,
            profile_turns=profile_turns,
            raw_trace=raw_trace,
        )

    def create_session(
        self,
        workspace: str | Path,
        *,
        mode: Mode = Mode.CODING,
        autonomy: Autonomy = Autonomy.WORKSPACE,
        title: str = "New session",
    ) -> Session:
        resolved = Path(workspace).resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError(f"workspace is not a directory: {resolved}")
        if self._execution_workspace is not None and resolved != self._execution_workspace:
            raise ValueError("session workspace does not match the runtime execution scope")
        if self._execution_autonomy is not None and autonomy is not self._execution_autonomy:
            raise ValueError("session autonomy does not match the runtime execution scope")
        session = Session(
            workspace=str(resolved),
            mode=mode,
            autonomy=autonomy,
            title=title,
        )
        self.store.create_session(session)
        return session

    async def run(
        self,
        session: Session,
        user_input: str,
        model: str,
        *,
        budget: TaskBudget | None = None,
        system_suffix: str = "",
        supplemental_messages: tuple[ChatMessage, ...] = (),
        allowed_tools: frozenset[str] | None = None,
        extra_egress_categories: tuple[str, ...] = (),
        agent_id: str | None = None,
        images: tuple[ImagePart, ...] = (),
        summarize_history: bool = False,
        exclude_image_digests: frozenset[str] = frozenset(),
        reasoning_effort: str | None = None,
        include_instructions: bool = True,
        include_skills: bool = True,
    ) -> RunResult:
        task = self._begin_run()
        try:
            self._validate_session_scope(session)
            task_budget = self._task_budget(budget, model, reasoning_effort)
            resolved_suffix = resolve_workspace_prompt_context(
                session.workspace,
                custom_system_suffix=system_suffix,
                include_instructions=include_instructions,
                include_skills=include_skills,
            )
            async with asyncio.timeout(task_budget.max_turn_seconds):
                return await self.runner.run(
                    session,
                    user_input,
                    model,
                    budget=task_budget,
                    system_suffix=resolved_suffix,
                    supplemental_messages=supplemental_messages,
                    allowed_tools=allowed_tools,
                    extra_egress_categories=extra_egress_categories,
                    agent_id=agent_id,
                    images=images,
                    summarize_history=summarize_history,
                    exclude_image_digests=exclude_image_digests,
                    reasoning_effort=reasoning_effort,
                )
        finally:
            self._active_runs.discard(task)

    async def continue_run(
        self,
        session: Session,
        model: str,
        *,
        budget: TaskBudget | None = None,
        system_suffix: str = "",
        supplemental_messages: tuple[ChatMessage, ...] = (),
        allowed_tools: frozenset[str] | None = None,
        extra_egress_categories: tuple[str, ...] = (),
        agent_id: str | None = None,
        continuation_prompt: str = "Continue the previous task from its durable history.",
        continuation_trust: ContentTrust = ContentTrust.DERIVED,
        exclude_image_digests: frozenset[str] = frozenset(),
        reasoning_effort: str | None = None,
        summarize_history: bool = False,
        include_instructions: bool = True,
        include_skills: bool = True,
    ) -> RunResult:
        task = self._begin_run()
        try:
            self._validate_session_scope(session)
            task_budget = self._task_budget(budget, model, reasoning_effort)
            resolved_suffix = resolve_workspace_prompt_context(
                session.workspace,
                custom_system_suffix=system_suffix,
                include_instructions=include_instructions,
                include_skills=include_skills,
            )
            async with asyncio.timeout(task_budget.max_turn_seconds):
                return await self.runner.run(
                    session,
                    None,
                    model,
                    budget=task_budget,
                    system_suffix=resolved_suffix,
                    supplemental_messages=supplemental_messages,
                    allowed_tools=allowed_tools,
                    extra_egress_categories=extra_egress_categories,
                    agent_id=agent_id,
                    continuation_prompt=continuation_prompt,
                    continuation_trust=continuation_trust,
                    exclude_image_digests=exclude_image_digests,
                    reasoning_effort=reasoning_effort,
                    summarize_history=summarize_history,
                )
        finally:
            self._active_runs.discard(task)

    def _task_budget(
        self, budget: TaskBudget | None, model: str, reasoning_effort: str | None
    ) -> TaskBudget:
        if budget is not None:
            return budget
        output_tokens = 8192
        recommendation = getattr(self._provider, "default_output_tokens", None)
        if callable(recommendation):
            recommended = recommendation(model, reasoning_effort)
            if type(recommended) is int and 8192 <= recommended <= 32_768:
                output_tokens = recommended
        return TaskBudget(max_output_tokens_per_call=output_tokens)

    def _begin_run(self) -> asyncio.Task[Any]:
        if self._closing or self._closed:
            raise RuntimeError("application service is closing")
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("application service run requires an asyncio task")
        self._active_runs.add(task)
        return task

    async def aclose(self) -> None:
        async with self._close_lock:
            if self._closed:
                return
            self._closing = True
            current = asyncio.current_task()
            active = tuple(task for task in self._active_runs if task is not current)
            for task in active:
                task.cancel("service_shutdown")
            errors: list[Exception] = []
            try:
                errors = await settle_tasks(
                    active,
                    timeout=_ACTIVE_RUN_CLOSE_TIMEOUT_SECONDS,
                    timeout_message="active run close deadline exceeded",
                )
            finally:
                try:
                    close_tools = getattr(self._tools, "aclose", None)
                    if callable(close_tools):
                        await close_tools()
                except Exception as error:
                    errors.append(error)
                finally:
                    self._closed = True
                    self._closing = False
            if errors:
                raise ExceptionGroup("application service shutdown failed", errors)

    async def change_mode(self, session: Session, mode: Mode) -> Event | None:
        self._validate_session_scope(session)
        async with self.store.session_lock(session.id):
            if session.mode is mode:
                return None
            stored = self.store.append(
                Event(
                    session_id=session.id,
                    type="mode.changed",
                    data={"from_mode": session.mode.value, "to_mode": mode.value},
                )
            )
            session.mode = mode
            session.updated_at = stored.created_at
            await self.events.publish(stored)
            return stored

    def get_session(self, session_id: str) -> Session:
        session = self.store.get_session(session_id)
        if session is not None:
            self._validate_session_scope(session)
            return session
        raise KeyError(f"unknown session: {session_id}")

    def _validate_session_scope(self, session: Session) -> None:
        if (
            self._execution_workspace is not None
            and Path(session.workspace).resolve() != self._execution_workspace
        ):
            raise ValueError("session workspace does not match the runtime execution scope")
        if (
            self._execution_autonomy is not None
            and session.autonomy is not self._execution_autonomy
        ):
            raise ValueError("session autonomy does not match the runtime execution scope")
