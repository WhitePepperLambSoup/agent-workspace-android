from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from agent_workspace.core.background_jobs import BackgroundJobStatus
from agent_workspace.core.events import Event
from agent_workspace.core.models import (
    ApprovalScope,
    Autonomy,
    BinaryArtifact,
    Citation,
    FileCheckpoint,
    MemoryItem,
    Mode,
    ProviderDelta,
    ProviderEgressRequest,
    ProviderRequest,
    ResearchSource,
    TextArtifact,
    TodoItem,
    ToolAttempt,
    ToolSpec,
)
from agent_workspace.core.session import Session


class EventStore(Protocol):
    def create_session(self, session: Session) -> None: ...

    def import_session(
        self,
        session: Session,
        events: tuple[Event, ...],
        artifacts: tuple[BinaryArtifact, ...] = (),
    ) -> list[Event]: ...

    def append(self, event: Event) -> Event: ...

    def append_many(self, events: tuple[Event, ...]) -> list[Event]: ...

    def append_many_with_artifacts(
        self,
        events: tuple[Event, ...],
        artifacts: tuple[BinaryArtifact, ...],
    ) -> list[Event]: ...

    def list_events(self, session_id: str) -> list[Event]: ...

    def list_pending_turn_inputs(self, session_id: str) -> list[Event]: ...

    def list_events_paged(
        self,
        session_id: str,
        *,
        cursor: int | None = None,
        limit: int = 100,
        reverse: bool = False,
    ) -> list[Event]: ...

    def list_events_by_type(
        self,
        event_type: str,
        *,
        limit: int = 50,
        workspace: str | None = None,
        route_id: str | None = None,
    ) -> list[Event]: ...

    def list_background_jobs(
        self,
        workspace: str,
        *,
        session_id: str | None = None,
        limit: int = 50,
        active_only: bool = False,
    ) -> list[BackgroundJobStatus]: ...

    def get_background_job(
        self,
        session_id: str,
        job_id: str,
    ) -> BackgroundJobStatus | None: ...

    def get_background_job_active_event(
        self,
        session_id: str,
        job_id: str,
    ) -> Event | None: ...

    def list_context_events(self, session_id: str) -> list[Event]: ...

    def list_sessions(self, limit: int = 50) -> list[Session]: ...

    def get_session(self, session_id: str) -> Session | None: ...

    def list_incomplete_tool_attempts(self, session_id: str) -> list[ToolAttempt]: ...

    def list_incomplete_tool_attempts_for_workspace(
        self,
        workspace: str,
    ) -> list[ToolAttempt]: ...

    def get_event(self, event_id: str) -> Event | None: ...

    def get_sandbox_changeset_event(
        self,
        session_id: str,
        workspace: str,
        changeset_id: str,
    ) -> Event | None: ...

    def get_sandbox_change_applied_event(
        self,
        session_id: str,
        workspace: str,
        changeset_id: str,
        path: str,
    ) -> Event | None: ...

    def get_sandbox_change_review_event(
        self,
        session_id: str,
        workspace: str,
        changeset_id: str,
        path: str,
    ) -> Event | None: ...

    def list_sandbox_changeset_events(
        self,
        session_id: str,
        workspace: str,
        *,
        limit: int = 50,
    ) -> list[Event]: ...

    def list_sandbox_change_applied_events(
        self,
        session_id: str,
        workspace: str,
        changeset_id: str,
    ) -> list[Event]: ...

    def list_settled_tool_results(
        self,
        session_id: str,
        tool_name: str,
        *,
        limit: int = 1000,
    ) -> list[str]: ...

    def prepare_file_checkpoint(self, checkpoint: FileCheckpoint) -> None: ...

    def get_file_checkpoint(self, attempt_id: str) -> FileCheckpoint | None: ...

    def session_lock(self, session_id: str) -> asyncio.Lock: ...

    def list_todos(self, session_id: str) -> list[TodoItem]: ...

    def list_research_sources(self, session_id: str) -> list[ResearchSource]: ...

    def list_citations(self, session_id: str) -> list[Citation]: ...

    def get_text_artifact(self, sha256: str) -> TextArtifact | None: ...

    def get_binary_artifact(self, sha256: str) -> BinaryArtifact | None: ...

    def binary_artifact_stats(self) -> tuple[int, int]: ...

    def garbage_collect_binary_artifacts(self) -> int: ...

    def list_memories(
        self,
        workspace: str,
        *,
        query: str = "",
        limit: int = 100,
    ) -> list[MemoryItem]: ...

    def get_memory(self, workspace: str, memory_id: str) -> MemoryItem | None: ...

    def get_memory_owner_workspace(self, memory_id: str) -> str | None: ...

    def close(self) -> None: ...


class ModelProvider(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def reasoning_protocol(self) -> str | None: ...

    def encode_request(self, request: ProviderRequest) -> bytes: ...

    def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderDelta]: ...


class ManagedModelProvider(ModelProvider, Protocol):
    async def aclose(self) -> None: ...


@runtime_checkable
class RetryObservableProvider(Protocol):
    def stream_with_attempts(
        self,
        request: ProviderRequest,
        attempt_started: Callable[[int], Awaitable[None]],
    ) -> AsyncIterator[ProviderDelta]: ...


class Tool(Protocol):
    @property
    def spec(self) -> ToolSpec: ...

    async def execute(self, arguments: dict[str, Any]) -> str: ...


@runtime_checkable
class ApprovalPreparedTool(Protocol):
    def prepare_for_approval(self, arguments: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class ToolExecutionContext:
    session_id: str
    correlation_id: str
    attempt_id: str
    started_event_id: str
    record_event: Callable[[Event], Awaitable[Event]]
    prepare_file_checkpoint: Callable[[FileCheckpoint], Awaitable[None]]
    record_artifact: Callable[[BinaryArtifact], Awaitable[None]] | None = None
    autonomy: Autonomy = Autonomy.WORKSPACE


@runtime_checkable
class ContextualTool(Protocol):
    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str: ...


@runtime_checkable
class HardCancellableTool(Protocol):
    @property
    def hard_cancellable(self) -> bool: ...


class ToolRegistryPort(Protocol):
    def specs(self, mode: Mode | None = None) -> tuple[ToolSpec, ...]: ...

    def get(self, name: str) -> Tool: ...


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    allowed: bool
    reason: str = ""
    scope: ApprovalScope | None = None


class PolicyPort(Protocol):
    def authorize(
        self,
        tool: ToolSpec,
        arguments: dict[str, Any],
        *,
        session_id: str | None = None,
        untrusted_context: bool = False,
    ) -> Awaitable[ApprovalDecision]: ...


class EgressPolicyPort(Protocol):
    @property
    def endpoint(self) -> str: ...

    def authorize(self, request: ProviderEgressRequest) -> Awaitable[ApprovalDecision]: ...


EventListener = Callable[[Event], Awaitable[None] | None]


class EventBusPort(Protocol):
    def subscribe(self, listener: EventListener) -> Callable[[], None]: ...

    async def publish(self, event: Event) -> None: ...


class SessionLoader(Protocol):
    def messages(self, session_id: str) -> Iterable[dict[str, Any]]: ...
