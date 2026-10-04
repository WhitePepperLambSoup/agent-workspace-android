from __future__ import annotations

import asyncio
import contextlib
import threading
from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass, replace
from itertools import count
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from agent_workspace.application.runner import RunResult
from agent_workspace.application.runtime import (
    ApplicationRuntime,
    build_runtime_async,
)
from agent_workspace.config import ProviderConfig
from agent_workspace.core.events import Event
from agent_workspace.core.models import (
    ApprovalScope,
    Autonomy,
    ChatMessage,
    DeltaKind,
    ImagePart,
    Mode,
    ProviderEgressRequest,
    ProviderRequest,
    Role,
    ToolSpec,
    validate_image_parts,
)
from agent_workspace.core.session import Session
from agent_workspace.policy import (
    ApprovalResult,
    ExtensionApprovalCallback,
    WorkspaceExtensionRequest,
)
from agent_workspace.policy.approval_display import approval_display_arguments
from agent_workspace.policy.permissions import WorkspacePolicy
from agent_workspace.providers import create_provider
from agent_workspace.storage.lock import ProcessWriteLockGroup, ProcessWriteLockLease
from agent_workspace.tools.terminal_sessions import TerminalSessionRegistry

_SHUTDOWN_GRACE_SECONDS = 10.0
_EXECUTOR_SHUTDOWN_SECONDS = 2.0
_CONTROL_EVENT_CAPACITY = 512
_MAX_CONTROL_EVENT_BYTES = 16 * 1024
_MAX_CONTROL_STRING_CHARS = 4096
_MAX_DISPLAY_DELTA_BYTES = 64 * 1024
_MUST_DELIVER_DISPLAY_EVENTS = frozenset(
    {
        "approval.requested",
        "runtime.failed",
        "runtime.stopped",
        "tool.cancelled",
        "tool.failed",
        "tool.rejected",
        "tool.settled",
        "tool.unknown",
        "turn.cancelled",
        "turn.completed",
        "turn.failed",
        "turn.input.received",
        "turn.input.applied",
    }
)
_OVERFLOW_DELIVER_DISPLAY_EVENTS = _MUST_DELIVER_DISPLAY_EVENTS - {"approval.requested"}
_ONCE_ONLY_APPROVAL_TOOLS = frozenset(
    {
        "delete_path",
        "git_commit",
        "git_diff",
        "git_status",
        "make_directory",
        "memory_write",
        "move_path",
        "run_process",
        "web_fetch",
    }
)
# Effects the policy never grants per-session: every invocation re-asks or is
# granted once. Kept in sync with WorkspacePolicy's grant_key=None branches so
# the approval dialog never advertises a session scope the policy downgrades.
_ONCE_ONLY_EFFECTS = frozenset(
    {
        "delete",
        "git_read",
        "git_write",
        "memory_write",
        "mkdir",
        "move",
        "network",
        "process",
        "sandboxed_process",
    }
)
_CRITICAL_DISPLAY_EVENTS = frozenset(
    {
        *_MUST_DELIVER_DISPLAY_EVENTS,
        "runtime.display_truncated",
        "turn.started",
    }
)


def _split_utf8_text(text: str, maximum_bytes: int) -> list[str]:
    if maximum_bytes < 1:
        raise ValueError("maximum_bytes must be positive")
    encoded = text.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(encoded):
        end = min(start + maximum_bytes, len(encoded))
        while end > start and end < len(encoded) and (encoded[end] & 0xC0) == 0x80:
            end -= 1
        if end == start:
            end = min(start + maximum_bytes, len(encoded))
        chunks.append(encoded[start:end].decode("utf-8"))
        start = end
    return chunks


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    workspace: Path
    database: Path
    provider: ProviderConfig
    mode: Mode
    autonomy: Autonomy
    session_id: str | None = None
    allow_workspace_extensions: bool = False
    extension_approval_callback: ExtensionApprovalCallback | None = None
    writer_lock_group: ProcessWriteLockGroup | None = None


@dataclass(slots=True)
class _DisplayEvent:
    order: int
    event: Event
    text_chunks: list[str] | None = None
    byte_count: int = 0


class RuntimeHost(threading.Thread):
    """Own the application runtime and its asyncio loop outside the UI process."""

    def __init__(
        self,
        settings: RuntimeSettings,
        *,
        event_capacity: int = 1024,
        event_byte_capacity: int = 4 * 1024 * 1024,
    ) -> None:
        super().__init__(name="agent-workspace-runtime", daemon=False)
        if event_capacity < 1:
            raise ValueError("event_capacity must be positive")
        if event_byte_capacity < 1:
            raise ValueError("event_byte_capacity must be positive")
        self.settings = settings
        self._event_capacity = event_capacity
        self._event_byte_capacity = event_byte_capacity
        self._display_events: deque[_DisplayEvent] = deque()
        self._display_lock = threading.Lock()
        self._queued_delta_count = 0
        self._queued_delta_bytes = 0
        self._queued_control_count = 0
        self._display_truncation_queued = False
        self._display_order = count()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._runtime: ApplicationRuntime | None = None
        self._terminal_registry: TerminalSessionRegistry | None = None
        self._session: Session | None = None
        self._active_turn: asyncio.Task[RunResult] | None = None
        self._turn_admission_pending = False
        self._turn_failure_forwarded = False
        self._pending_mode: Mode | None = None
        self._mode_apply_task: asyncio.Task[None] | None = None
        self._shutdown_task: asyncio.Task[None] | None = None
        self._shutdown_completion: Future[None] = Future()
        self._approvals: dict[str, asyncio.Future[ApprovalResult]] = {}
        self._approval_session_scopes: dict[str, bool] = {}
        self._extension_approvals: dict[str, asyncio.Future[bool]] = {}
        self._shutdown_requested = threading.Event()
        self._accepting = False
        self._closing = False
        self._stopped_emitted = False
        self._create_backup_on_shutdown = True
        self._background_work = threading.Event()
        self._background_work_lock = threading.Lock()
        self._background_work_ids: set[tuple[str, str]] = set()

    @property
    def has_background_work(self) -> bool:
        runtime = self._runtime
        return self._background_work.is_set() or (
            runtime is not None and getattr(runtime, "scheduler", None) is not None
        )

    def _track_background_work(self, kind: str, identity: str, *, active: bool) -> None:
        with self._background_work_lock:
            key = (kind, identity)
            if active:
                self._background_work_ids.add(key)
            else:
                self._background_work_ids.discard(key)
            if self._background_work_ids:
                self._background_work.set()
            else:
                self._background_work.clear()

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            if self._shutdown_requested.is_set():
                return
            build_options: dict[str, Any] = {}
            if self.settings.writer_lock_group is not None:
                build_options["writer_lock_group"] = self.settings.writer_lock_group
            self._runtime = loop.run_until_complete(
                build_runtime_async(
                    self.settings.workspace,
                    self.settings.database,
                    self.settings.provider,
                    autonomy=self.settings.autonomy,
                    approval_callback=self._request_approval,
                    egress_approval_callback=self._request_egress_approval,
                    extension_approval_callback=self.settings.extension_approval_callback
                    or self._request_extension_approval,
                    event_listener=self._forward_event,
                    allow_workspace_extensions=self.settings.allow_workspace_extensions,
                    parallel_tool_calls=True,
                    **build_options,
                )
            )
            write_lock = getattr(self._runtime, "write_lock", None)
            shared_writer = isinstance(write_lock, ProcessWriteLockLease)
            self._terminal_registry = TerminalSessionRegistry(
                self.settings.workspace,
                event_sink=self._forward_terminal_event,
                reconcile_on_start=not shared_writer,
            )
            if isinstance(write_lock, ProcessWriteLockLease):
                write_lock.run_once(
                    ("terminal_recovery", str(self.settings.workspace.resolve())),
                    self._terminal_registry.reconcile,
                )
            if self.settings.session_id is not None:
                self._session = self._runtime.service.get_session(self.settings.session_id)
                if Path(self._session.workspace).resolve() != self.settings.workspace.resolve():
                    raise ValueError("resumed session workspace does not match runtime workspace")
                if self._session.autonomy is not self.settings.autonomy:
                    raise ValueError("resumed session autonomy does not match runtime autonomy")
                if self._session.mode is not self.settings.mode:
                    loop.run_until_complete(
                        self._runtime.service.change_mode(self._session, self.settings.mode)
                    )
            self._accepting = True
            self._emit(
                "runtime.started",
                {
                    "workspace": str(self.settings.workspace),
                    "loop": type(loop).__name__,
                    "session_id": self._session.id if self._session is not None else None,
                },
            )
            if self._shutdown_requested.is_set():
                self._schedule_shutdown()
            loop.run_forever()
        except Exception as exc:
            self._emit_error("runtime.failed", exc)
        finally:
            self._accepting = False
            if self._terminal_registry is not None:
                with contextlib.suppress(Exception):
                    loop.run_until_complete(self._terminal_registry.aclose())
                self._terminal_registry = None
            if self._runtime is not None:
                try:
                    loop.run_until_complete(
                        asyncio.wait_for(
                            self._runtime.aclose(create_backup=self._create_backup_on_shutdown),
                            timeout=_SHUTDOWN_GRACE_SECONDS,
                        )
                    )
                except TimeoutError:
                    self._emit(
                        "runtime.close_timeout",
                        {"timeout_seconds": _SHUTDOWN_GRACE_SECONDS},
                    )
                except Exception as exc:
                    self._emit_error("runtime.close_failed", exc)
                self._runtime = None
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel("runtime_exit")
            if pending:
                with contextlib.suppress(Exception):
                    loop.run_until_complete(asyncio.wait(pending, timeout=_SHUTDOWN_GRACE_SECONDS))
            with contextlib.suppress(Exception):
                loop.run_until_complete(loop.shutdown_asyncgens())
            with contextlib.suppress(Exception):
                shutdown_default_executor = cast(Any, loop.shutdown_default_executor)
                loop.run_until_complete(
                    shutdown_default_executor(timeout=_EXECUTOR_SHUTDOWN_SECONDS)
                )
            loop.close()
            self._loop = None
            self._emit_stopped()
            if not self._shutdown_completion.done():
                self._shutdown_completion.set_result(None)

    def submit_turn(
        self,
        prompt: str,
        images: tuple[ImagePart, ...] = (),
        *,
        exclude_image_digests: frozenset[str] = frozenset(),
        reasoning_effort: str | None = None,
    ) -> Future[None]:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._accepting or self._closing:
            raise RuntimeError("runtime is not accepting commands")
        return asyncio.run_coroutine_threadsafe(
            self._run_turn(prompt, images, exclude_image_digests, reasoning_effort), loop
        )

    def steer_turn(
        self,
        session_id: str,
        prompt: str,
        turn_id: str,
        *,
        input_id: str | None = None,
        images: tuple[ImagePart, ...] = (),
    ) -> Future[str]:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._accepting or self._closing:
            raise RuntimeError("runtime_unavailable")
        return asyncio.run_coroutine_threadsafe(
            self._steer_turn(session_id, prompt, turn_id, input_id, images), loop
        )

    async def _steer_turn(
        self,
        session_id: str,
        prompt: str,
        turn_id: str,
        input_id: str | None,
        images: tuple[ImagePart, ...] = (),
    ) -> str:
        runtime = self._runtime
        task = self._active_turn
        if (
            runtime is None or task is None or task.done()
            or self._session is None or self._session.id != session_id
        ):
            raise RuntimeError("turn_not_active")
        return await runtime.service.runner.steer_turn(
            session_id, prompt, turn_id, input_id=input_id, images=images
        )

    def optimize_prompt(
        self,
        prompt: str,
        *,
        provider_config: ProviderConfig | None = None,
    ) -> Future[str]:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._accepting or self._closing:
            raise RuntimeError("runtime is not accepting commands")
        return asyncio.run_coroutine_threadsafe(
            self._optimize_prompt(prompt, provider_config=provider_config), loop
        )

    async def _optimize_prompt(
        self,
        prompt: str,
        *,
        provider_config: ProviderConfig | None = None,
    ) -> str:
        if not prompt.strip():
            raise ValueError("prompt may not be empty")
        if self._active_turn is not None or self._turn_admission_pending:
            raise RuntimeError("runtime_busy")
        runtime = self._runtime
        if runtime is None:
            raise RuntimeError("runtime is unavailable")
        config = provider_config or self.settings.provider
        config.validate()
        provider = runtime.provider if provider_config is None else create_provider(config)
        close_provider = provider_config is not None
        system = (
            "You are a prompt optimizer for a general purpose AI agent. Rewrite the user's "
            "request into one precise, actionable prompt. Preserve the user's intent, language, "
            "technical terms, constraints, requested files, and desired output. Make implicit "
            "deliverables and acceptance checks explicit only when they are clearly implied. "
            "Do not invent facts, APIs, files, permissions, dates, tools, or results. Do not "
            "solve the task. If the request is already clear, make only minimal edits. Return "
            "only the rewritten prompt, with no preface, explanation, markdown fence, "
            "or quote marks."
        )
        request = ProviderRequest(
            model=config.model,
            messages=(
                ChatMessage(role=Role.SYSTEM, content=system),
                ChatMessage(
                    role=Role.USER,
                    content=(
                        "Rewrite this user request while preserving its language and intent:\n\n"
                        "<user_request>\n" + prompt.strip() + "\n</user_request>"
                    ),
                ),
            ),
            max_output_tokens=2048,
            temperature=0.2,
        )
        chunks: list[str] = []
        try:
            async for delta in provider.stream(request):
                if delta.kind is DeltaKind.TEXT and delta.text:
                    chunks.append(delta.text)
        finally:
            if close_provider and hasattr(provider, "aclose"):
                with contextlib.suppress(Exception):
                    await provider.aclose()
        optimized = "".join(chunks).strip()
        if optimized.startswith("```") and optimized.endswith("```"):
            lines = optimized.splitlines()
            if len(lines) >= 3:
                optimized = "\n".join(lines[1:-1]).strip()
        if not optimized:
            raise RuntimeError("prompt_optimization_empty")
        return optimized[:100_000]

    def resolve_approval(
        self,
        request_id: str,
        scope: ApprovalScope | str | None,
    ) -> Future[None] | None:
        loop = self._loop
        if loop is None or loop.is_closed() or self._closing:
            return None
        return asyncio.run_coroutine_threadsafe(self._resolve_approval(request_id, scope), loop)

    def request_shutdown(self, *, create_backup: bool = True) -> Future[None] | None:
        self._create_backup_on_shutdown = create_backup
        self._shutdown_requested.set()
        loop = self._loop
        if loop is None or loop.is_closed():
            return None
        loop.call_soon_threadsafe(self._schedule_shutdown)
        return self._shutdown_completion

    def request_cancel_turn(self) -> Future[None] | None:
        loop = self._loop
        if loop is None or loop.is_closed() or self._closing:
            return None
        return asyncio.run_coroutine_threadsafe(self._cancel_turn(), loop)

    def request_mode(self, mode: Mode) -> Future[None] | None:
        loop = self._loop
        if loop is None or loop.is_closed() or self._closing:
            return None
        return asyncio.run_coroutine_threadsafe(self._queue_mode_change(mode), loop)

    def request_terminal_start(
        self,
        argv: tuple[str, ...],
        *,
        cwd: str = ".",
        owner: str | None = None,
        deadline: float | None = None,
        max_output_bytes: int = 512 * 1024,
    ) -> Future[object] | None:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._accepting or self._closing:
            return None
        return asyncio.run_coroutine_threadsafe(
            self._terminal_start(
                argv,
                cwd=cwd,
                owner=owner,
                deadline=deadline,
                max_output_bytes=max_output_bytes,
            ),
            loop,
        )

    def request_terminal_input(
        self, session_id: str, data: str, *, owner: str | None = None
    ) -> Future[object] | None:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._accepting or self._closing:
            return None
        return asyncio.run_coroutine_threadsafe(
            self._terminal_input(session_id, data, owner=owner), loop
        )

    def request_terminal_resize(
        self,
        session_id: str,
        columns: int,
        rows: int,
        *,
        owner: str | None = None,
    ) -> Future[object] | None:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._accepting or self._closing:
            return None
        return asyncio.run_coroutine_threadsafe(
            self._terminal_resize(session_id, columns, rows, owner=owner), loop
        )

    def request_terminal_status(self, session_id: str) -> Future[object] | None:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._accepting or self._closing:
            return None
        return asyncio.run_coroutine_threadsafe(self._terminal_status(session_id), loop)

    def request_terminal_list(self, limit: int = 32) -> Future[object] | None:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._accepting or self._closing:
            return None
        return asyncio.run_coroutine_threadsafe(self._terminal_list(limit), loop)

    def request_terminal_replay(
        self, session_id: str, offset: int = 0, max_bytes: int | None = None
    ) -> Future[object] | None:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._accepting or self._closing:
            return None
        return asyncio.run_coroutine_threadsafe(
            self._terminal_replay(session_id, offset=offset, max_bytes=max_bytes), loop
        )

    def request_terminal_stop(
        self, session_id: str, *, owner: str | None = None, reason: str = "stopped"
    ) -> Future[object] | None:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._accepting or self._closing:
            return None
        return asyncio.run_coroutine_threadsafe(
            self._terminal_stop(session_id, owner=owner, reason=reason), loop
        )

    async def _terminal_start(
        self,
        argv: tuple[str, ...],
        *,
        cwd: str,
        owner: str | None,
        deadline: float | None,
        max_output_bytes: int,
    ) -> object:
        registry = self._terminal_registry
        if registry is None:
            raise RuntimeError("terminal registry is unavailable")
        session = await registry.start(
            argv,
            cwd=cwd,
            autonomy=self.settings.autonomy.value,
            deadline=deadline,
            max_output_bytes=max_output_bytes,
            owner=owner,
        )
        return session.to_document()

    async def _terminal_input(self, session_id: str, data: str, *, owner: str | None) -> object:
        registry = self._terminal_registry
        if registry is None:
            raise RuntimeError("terminal registry is unavailable")
        await registry.write(session_id, data, owner=owner)
        return registry.status(session_id)

    async def _terminal_resize(
        self,
        session_id: str,
        columns: int,
        rows: int,
        *,
        owner: str | None,
    ) -> object:
        registry = self._terminal_registry
        if registry is None:
            raise RuntimeError("terminal registry is unavailable")
        await registry.resize(session_id, columns, rows, owner=owner)
        return registry.status(session_id)

    async def _terminal_status(self, session_id: str) -> object:
        registry = self._terminal_registry
        if registry is None:
            raise RuntimeError("terminal registry is unavailable")
        return registry.status(session_id)

    async def _terminal_list(self, limit: int) -> object:
        registry = self._terminal_registry
        if registry is None:
            raise RuntimeError("terminal registry is unavailable")
        return registry.list()[:limit]

    async def _terminal_replay(
        self, session_id: str, *, offset: int, max_bytes: int | None
    ) -> object:
        registry = self._terminal_registry
        if registry is None:
            raise RuntimeError("terminal registry is unavailable")
        result = registry.replay(session_id, offset=offset, max_bytes=max_bytes)
        return {
            "sessionId": result.session_id,
            "state": result.state,
            "output": result.output,
            "exitCode": result.exit_code,
            "truncated": result.truncated,
            "exitReason": result.exit_reason,
            "offset": result.offset,
            "nextOffset": result.next_offset,
            "eof": result.eof,
        }

    async def _terminal_stop(self, session_id: str, *, owner: str | None, reason: str) -> object:
        registry = self._terminal_registry
        if registry is None:
            raise RuntimeError("terminal registry is unavailable")
        result = await registry.stop(session_id, owner=owner, reason=reason)
        return {
            "sessionId": result.session_id,
            "state": result.state,
            "output": result.output,
            "exitCode": result.exit_code,
            "truncated": result.truncated,
            "exitReason": result.exit_reason,
            "offset": result.offset,
            "nextOffset": result.next_offset,
            "eof": result.eof,
        }

    def drain_display_events(
        self,
        max_deltas: int = 200,
        max_events: int = 500,
    ) -> list[Event]:
        """Drain events in production order without crossing the delta budget."""
        if max_deltas < 0:
            raise ValueError("max_deltas may not be negative")
        if max_events < 1:
            raise ValueError("max_events must be positive")
        pending: list[_DisplayEvent] = []
        drained_deltas = 0
        with self._display_lock:
            while self._display_events and len(pending) < max_events:
                item = self._display_events[0]
                is_delta = item.event.type == "model.output.delta"
                if is_delta and drained_deltas >= max_deltas:
                    break
                pending.append(self._display_events.popleft())
                if is_delta:
                    drained_deltas += 1
                    self._queued_delta_count -= 1
                    self._queued_delta_bytes -= item.byte_count
                elif item.event.type == "runtime.display_truncated":
                    self._display_truncation_queued = False
                    self._queued_control_count -= 1
                else:
                    self._queued_control_count -= 1
        return [self._materialize_display_event(item) for item in pending]

    async def _run_turn(
        self,
        prompt: str,
        images: tuple[ImagePart, ...] = (),
        exclude_image_digests: frozenset[str] = frozenset(),
        reasoning_effort: str | None = None,
    ) -> None:
        if not self._accepting or self._closing:
            self._emit("runtime.command_rejected", {"reason": "runtime is stopping"})
            return
        if self._active_turn is not None or self._turn_admission_pending:
            self._emit("runtime.command_rejected", {"reason": "a turn is already active"})
            return
        try:
            validate_image_parts(images)
        except ValueError as exc:
            self._emit("runtime.command_rejected", {"reason": str(exc)})
            return
        self._turn_admission_pending = True
        try:
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            self._turn_admission_pending = False
            raise
        mode_apply_task = self._mode_apply_task
        if mode_apply_task is not None and not mode_apply_task.done():
            try:
                await asyncio.shield(mode_apply_task)
            except asyncio.CancelledError:
                self._turn_admission_pending = False
                raise
            except Exception as exc:
                self._turn_admission_pending = False
                self._emit_error("runtime.error", exc)
                return
        if not self._accepting or self._closing:
            self._turn_admission_pending = False
            self._emit("runtime.command_rejected", {"reason": "runtime is stopping"})
            return
        runtime = self._runtime
        if runtime is None:
            self._turn_admission_pending = False
            self._emit("runtime.command_rejected", {"reason": "runtime is unavailable"})
            return
        self._turn_failure_forwarded = False
        task: asyncio.Task[RunResult] | None = None
        try:
            if self._session is None:
                self._session = runtime.service.create_session(
                    self.settings.workspace,
                    mode=self.settings.mode,
                    autonomy=self.settings.autonomy,
                    title=prompt.strip()[:80] or "Desktop session",
                )
                self._emit(
                    "session.created",
                    {
                        "session_id": self._session.id,
                        "title": self._session.title,
                        "mode": self._session.mode.value,
                        "autonomy": self._session.autonomy.value,
                    },
                )
            task = asyncio.create_task(
                runtime.service.run(
                    self._session,
                    prompt,
                    self.settings.provider.model,
                    images=images,
                    exclude_image_digests=exclude_image_digests,
                    reasoning_effort=reasoning_effort,
                )
            )
            self._active_turn = task
            self._turn_admission_pending = False
            await task
        except asyncio.CancelledError:
            self._emit("runtime.turn_cancelled", {})
        except Exception as exc:
            if not self._turn_failure_forwarded:
                self._emit_error("runtime.error", exc)
        finally:
            self._turn_admission_pending = False
            if task is not None and self._active_turn is task:
                self._active_turn = None
            self._turn_failure_forwarded = False

    async def _queue_mode_change(self, mode: Mode) -> None:
        self._pending_mode = mode
        self._emit("runtime.mode_pending", {"mode": mode.value})
        if self._mode_apply_task is None or self._mode_apply_task.done():
            self._mode_apply_task = asyncio.create_task(self._apply_pending_mode())

    async def _apply_pending_mode(self) -> None:
        active_turn = self._active_turn
        if active_turn is not None and not active_turn.done():
            with contextlib.suppress(BaseException):
                await asyncio.shield(active_turn)
        while self._pending_mode is not None and not self._closing:
            mode = self._pending_mode
            self._pending_mode = None
            runtime = self._runtime
            session = self._session
            if session is None:
                self.settings = replace(self.settings, mode=mode)
                self._emit("runtime.mode_applied", {"mode": mode.value, "session_id": None})
                continue
            if runtime is None:
                return
            await runtime.service.change_mode(session, mode)
            self.settings = replace(self.settings, mode=mode)
            self._emit(
                "runtime.mode_applied",
                {"mode": mode.value, "session_id": session.id},
            )

    async def _request_approval(self, tool: ToolSpec, arguments: dict[str, Any]) -> ApprovalResult:
        if self._closing:
            return ApprovalResult(False, "runtime is stopping")
        request_id = str(uuid4())
        future: asyncio.Future[ApprovalResult] = asyncio.get_running_loop().create_future()
        self._approvals[request_id] = future
        supports_session_scope = (
            tool.name not in _ONCE_ONLY_APPROVAL_TOOLS
            and WorkspacePolicy._effect_kind(tool.side_effect) not in _ONCE_ONLY_EFFECTS
        )
        self._approval_session_scopes[request_id] = supports_session_scope
        session_id = (
            self._session.id if self._session is not None else self.settings.session_id or "desktop"
        )
        approval_event = self._compact_control_event(
            Event(
                session_id=session_id,
                type="approval.requested",
                data={
                    "request_id": request_id,
                    "tool": tool.name,
                    "description": tool.description,
                    "side_effect": tool.side_effect,
                    "arguments": approval_display_arguments(tool, arguments),
                    "supports_session_scope": supports_session_scope,
                },
            )
        )
        if approval_event.data.get("display_truncated") is True:
            self._approvals.pop(request_id, None)
            self._approval_session_scopes.pop(request_id, None)
            return ApprovalResult(False, "approval arguments exceed the safe display limit")
        emitted = self._queue_display_event(approval_event)
        if not emitted:
            self._approvals.pop(request_id, None)
            self._approval_session_scopes.pop(request_id, None)
            return ApprovalResult(False, "desktop approval could not be displayed safely")
        try:
            return await future
        finally:
            self._approvals.pop(request_id, None)
            self._approval_session_scopes.pop(request_id, None)

    async def _request_egress_approval(
        self,
        request: ProviderEgressRequest,
    ) -> ApprovalResult:
        if self._closing:
            return ApprovalResult(False, "runtime is stopping")
        request_id = str(uuid4())
        future: asyncio.Future[ApprovalResult] = asyncio.get_running_loop().create_future()
        self._approvals[request_id] = future
        supports_session_scope = not any(
            category.startswith("sensitive_") for category in request.data_categories
        )
        self._approval_session_scopes[request_id] = supports_session_scope
        emitted = self._emit(
            "approval.requested",
            {
                "request_id": request_id,
                "kind": "provider_egress",
                "endpoint": request.endpoint,
                "data_categories": list(request.data_categories),
                "content_digest": request.content_digest,
                "supports_session_scope": supports_session_scope,
            },
        )
        if not emitted:
            self._approvals.pop(request_id, None)
            self._approval_session_scopes.pop(request_id, None)
            return ApprovalResult(False, "desktop approval could not be displayed safely")
        try:
            return await future
        finally:
            self._approvals.pop(request_id, None)
            self._approval_session_scopes.pop(request_id, None)

    async def _request_extension_approval(
        self,
        request: WorkspaceExtensionRequest,
    ) -> bool:
        if self._closing:
            return False
        request_id = str(uuid4())
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._extension_approvals[request_id] = future
        session_id = (
            self._session.id if self._session is not None else self.settings.session_id or "desktop"
        )
        approval_event = self._compact_control_event(
            Event(
                session_id=session_id,
                type="approval.requested",
                data={
                    "request_id": request_id,
                    "kind": "extension",
                    "extension_kind": request.kind,
                    "identifier": request.identifier,
                    "config_source": request.config_source,
                    "command": list(request.command),
                    "config_digest": request.config_digest,
                    "executable_sha256": request.executable_sha256,
                    "tool": f"extension:{request.kind}:{request.identifier}",
                    "description": (
                        f"Allow workspace extension {request.identifier} ({request.kind})"
                    ),
                    "side_effect": "extension_execution",
                    "arguments": {
                        "kind": request.kind,
                        "identifier": request.identifier,
                        "config_source": request.config_source,
                        "command": list(request.command),
                        "config_digest": request.config_digest,
                    },
                    "supports_session_scope": False,
                },
            )
        )
        if approval_event.data.get("display_truncated") is True:
            self._extension_approvals.pop(request_id, None)
            return False
        emitted = self._queue_display_event(approval_event)
        if not emitted:
            self._extension_approvals.pop(request_id, None)
            return False
        try:
            return await future
        finally:
            self._extension_approvals.pop(request_id, None)

    async def _resolve_approval(
        self,
        request_id: str,
        scope: ApprovalScope | str | None,
    ) -> None:
        ext_future = self._extension_approvals.get(request_id)
        if ext_future is not None and not ext_future.done():
            try:
                approval_scope = ApprovalScope(scope) if scope is not None else None
            except ValueError:
                approval_scope = None
            allowed = approval_scope is not None
            ext_future.set_result(allowed)
            return

        future = self._approvals.get(request_id)
        if future is not None and not future.done():
            try:
                approval_scope = ApprovalScope(scope) if scope is not None else None
            except ValueError:
                approval_scope = None
            if approval_scope is ApprovalScope.SESSION and not self._approval_session_scopes.get(
                request_id, False
            ):
                approval_scope = None
            allowed = approval_scope is not None
            reason = "approved in desktop" if allowed else "denied in desktop"
            future.set_result(ApprovalResult(allowed, reason, approval_scope))

    def _schedule_shutdown(self) -> None:
        if self._shutdown_task is not None:
            return
        task = asyncio.create_task(self._shutdown_impl())
        self._shutdown_task = task
        task.add_done_callback(self._shutdown_finished)

    def _shutdown_finished(self, task: asyncio.Task[None]) -> None:
        if not task.cancelled():
            error = task.exception()
            if error is not None:
                self._emit_error("runtime.close_failed", error)
        asyncio.get_running_loop().stop()

    async def _cancel_turn(self) -> None:
        task = self._active_turn
        if task is None or task.done():
            self._emit("runtime.cancel_rejected", {"reason": "no turn is active"})
            return
        self._emit("runtime.turn_cancel_requested", {"source": "user_stop"})
        task.cancel("user_stop")
        for future in tuple(self._approvals.values()):
            if not future.done():
                future.cancel()
        for ext_future in tuple(self._extension_approvals.values()):
            if not ext_future.done():
                ext_future.cancel()
        done, _ = await asyncio.wait({task}, timeout=_SHUTDOWN_GRACE_SECONDS)
        if task not in done:
            self._emit(
                "runtime.turn_cancel_timeout",
                {"timeout_seconds": _SHUTDOWN_GRACE_SECONDS},
            )

    async def _shutdown_impl(self) -> None:
        self._closing = True
        self._accepting = False
        task = self._active_turn
        if task is not None and not task.done():
            task.cancel("runtime_shutdown")
        for future in tuple(self._approvals.values()):
            if not future.done():
                future.cancel()
        for ext_future in tuple(self._extension_approvals.values()):
            if not ext_future.done():
                ext_future.cancel()
        if task is not None and not task.done():
            done, _ = await asyncio.wait({task}, timeout=_SHUTDOWN_GRACE_SECONDS)
            if task not in done:
                self._emit(
                    "runtime.turn_cancel_timeout",
                    {"timeout_seconds": _SHUTDOWN_GRACE_SECONDS},
                )
        runtime = self._runtime
        if runtime is not None:
            try:
                await asyncio.wait_for(
                    runtime.aclose(create_backup=self._create_backup_on_shutdown),
                    timeout=_SHUTDOWN_GRACE_SECONDS,
                )
            except TimeoutError:
                self._emit(
                    "runtime.close_timeout",
                    {"timeout_seconds": _SHUTDOWN_GRACE_SECONDS},
                )
            except Exception as exc:
                self._emit_error("runtime.close_failed", exc)
            finally:
                backup_error = getattr(runtime, "backup_error", None)
                if isinstance(backup_error, str):
                    self._emit(
                        "runtime.backup_failed",
                        {"error": backup_error},
                    )
                self._runtime = None

    def _forward_event(self, event: Event) -> None:
        job_id = event.data.get("job_id")
        if event.type.startswith("background.job.") and isinstance(job_id, str):
            self._track_background_work(
                "job", job_id,
                active=event.type in {"background.job.created", "background.job.started"},
            )
        if event.type == "turn.failed":
            self._turn_failure_forwarded = True
        self._queue_display_event(event)

    def _forward_terminal_event(self, payload: dict[str, object]) -> None:
        event_type = payload.get("type")
        if not isinstance(event_type, str):
            return
        data = {key: value for key, value in payload.items() if key not in {"type", "sessionId"}}
        session_id = payload.get("sessionId")
        if isinstance(session_id, str) and event_type in {"terminal.start", "terminal.exited"}:
            self._track_background_work(
                "terminal", session_id, active=event_type == "terminal.start"
            )
        event = Event(
            session_id=session_id if isinstance(session_id, str) else "desktop",
            type=event_type,
            data=data,
        )
        self._queue_display_event(event)

    def _emit(self, event_type: str, data: dict[str, Any]) -> bool:
        session_id = (
            self._session.id if self._session is not None else self.settings.session_id or "desktop"
        )
        return self._queue_display_event(Event(session_id=session_id, type=event_type, data=data))

    def _queue_display_event(self, event: Event) -> bool:
        with self._display_lock:
            item = self._new_display_event(event)
            if event.type == "model.output.delta":
                self._queue_delta(item)
                return True
            else:
                return self._queue_control(item)

    def _queue_delta(self, item: _DisplayEvent) -> None:
        if item.text_chunks is not None and item.byte_count > _MAX_DISPLAY_DELTA_BYTES:
            text = "".join(item.text_chunks)
            for chunk in _split_utf8_text(text, _MAX_DISPLAY_DELTA_BYTES):
                self._queue_delta(
                    _DisplayEvent(
                        next(self._display_order),
                        item.event,
                        text_chunks=[chunk],
                        byte_count=len(chunk.encode("utf-8")),
                    )
                )
            return

        dropped = False
        if item.byte_count > self._event_byte_capacity and item.text_chunks is not None:
            encoded = item.text_chunks[0].encode("utf-8")[: self._event_byte_capacity]
            item.text_chunks = [encoded.decode("utf-8", errors="ignore")]
            item.byte_count = len(item.text_chunks[0].encode("utf-8"))
            dropped = True
        while self._queued_delta_bytes + item.byte_count > self._event_byte_capacity:
            if not self._drop_oldest_delta():
                break
            dropped = True
        if self._queued_delta_count < self._event_capacity:
            self._display_events.append(item)
            self._queued_delta_count += 1
            self._queued_delta_bytes += item.byte_count
            if dropped:
                self._queue_display_truncation(item.event.session_id)
            return

        merged = self._merge_deltas(self._display_events[-1], item)
        if merged is not None:
            self._display_events[-1] = merged
            self._queued_delta_bytes += item.byte_count
            if dropped:
                self._queue_display_truncation(item.event.session_id)
            return

        for index in range(len(self._display_events) - 1):
            merged = self._merge_deltas(
                self._display_events[index],
                self._display_events[index + 1],
            )
            if merged is not None:
                self._display_events[index] = merged
                del self._display_events[index + 1]
                self._display_events.append(item)
                self._queued_delta_bytes += item.byte_count
                if dropped:
                    self._queue_display_truncation(item.event.session_id)
                return

        if self._is_text_delta(item.event):
            for index, queued in enumerate(self._display_events):
                if not self._is_text_delta(queued.event):
                    if queued.event.type != "model.output.delta":
                        continue
                    self._queued_delta_bytes -= queued.byte_count
                    del self._display_events[index]
                    self._display_events.append(item)
                    self._queued_delta_bytes += item.byte_count
                    self._queue_display_truncation(item.event.session_id)
                    return
        self._queue_display_truncation(item.event.session_id)

    @staticmethod
    def _merge_deltas(left: _DisplayEvent, right: _DisplayEvent) -> _DisplayEvent | None:
        left_kind = left.event.data.get("kind")
        if left_kind != right.event.data.get("kind") or left_kind not in {"text", "reasoning"}:
            return None
        if left.text_chunks is None or right.text_chunks is None:
            return None
        if left.byte_count + right.byte_count > _MAX_DISPLAY_DELTA_BYTES:
            return None
        left.text_chunks.extend(right.text_chunks)
        left.byte_count += right.byte_count
        return left

    def _new_display_event(self, event: Event) -> _DisplayEvent:
        text = event.data.get("text")
        if event.type == "model.output.delta" and isinstance(text, str):
            return _DisplayEvent(
                next(self._display_order),
                event,
                text_chunks=[text],
                byte_count=len(text.encode("utf-8")),
            )
        compacted = self._compact_control_event(event)
        return _DisplayEvent(next(self._display_order), compacted)

    @staticmethod
    def _materialize_display_event(item: _DisplayEvent) -> Event:
        if item.text_chunks is None:
            return item.event
        return replace(
            item.event,
            data={**item.event.data, "text": "".join(item.text_chunks)},
        )

    def _drop_oldest_delta(self) -> bool:
        for index, queued in enumerate(self._display_events):
            if queued.event.type != "model.output.delta":
                continue
            del self._display_events[index]
            self._queued_delta_count -= 1
            self._queued_delta_bytes -= queued.byte_count
            return True
        return False

    def _queue_display_truncation(self, session_id: str) -> None:
        if self._display_truncation_queued:
            return
        self._queue_control(
            self._new_display_event(
                Event(
                    session_id=session_id,
                    type="runtime.display_truncated",
                    data={"reason": "desktop display queue capacity exceeded"},
                )
            )
        )

    def _queue_control(self, item: _DisplayEvent) -> bool:
        dropped = False
        if self._queued_control_count >= _CONTROL_EVENT_CAPACITY:
            removable = next(
                (
                    index
                    for index, queued in enumerate(self._display_events)
                    if queued.event.type != "model.output.delta"
                    and queued.event.type not in _CRITICAL_DISPLAY_EVENTS
                ),
                None,
            )
            if removable is None:
                if item.event.type not in _MUST_DELIVER_DISPLAY_EVENTS:
                    return False
                removable = next(
                    (
                        index
                        for index, queued in enumerate(self._display_events)
                        if queued.event.type != "model.output.delta"
                        and queued.event.type not in _MUST_DELIVER_DISPLAY_EVENTS
                    ),
                    None,
                )
            if removable is None and item.event.type == "runtime.stopped":
                removable = next(
                    (
                        index
                        for index, queued in enumerate(self._display_events)
                        if queued.event.type != "model.output.delta"
                    ),
                    None,
                )
            if removable is None:
                if item.event.type in _OVERFLOW_DELIVER_DISPLAY_EVENTS:
                    removable = next(
                        (
                            index
                            for index, queued in enumerate(self._display_events)
                            if queued.event.type in _OVERFLOW_DELIVER_DISPLAY_EVENTS
                        ),
                        None,
                    )
                    if removable is None:
                        removable = next(
                            (
                                index
                                for index, queued in enumerate(self._display_events)
                                if queued.event.type != "model.output.delta"
                            ),
                            None,
                        )
                        if removable is None:
                            return False
                else:
                    return False
            removed = self._display_events[removable]
            del self._display_events[removable]
            self._queued_control_count -= 1
            dropped = True
            if removed.event.type == "runtime.display_truncated":
                self._display_truncation_queued = False
        if dropped and not self._display_truncation_queued:
            notice_room = next(
                (
                    index
                    for index, queued in enumerate(self._display_events)
                    if queued.event.type != "model.output.delta"
                    and queued.event.type not in _CRITICAL_DISPLAY_EVENTS
                ),
                None,
            )
            if notice_room is None:
                notice_room = next(
                    (
                        index
                        for index, queued in enumerate(self._display_events)
                        if queued.event.type != "model.output.delta"
                    ),
                    None,
                )
            if notice_room is not None:
                del self._display_events[notice_room]
                self._queued_control_count -= 1
                notice = self._new_display_event(
                    Event(
                        session_id=item.event.session_id,
                        type="runtime.display_truncated",
                        data={"reason": "desktop display queue capacity exceeded"},
                    )
                )
                self._display_events.append(notice)
                self._queued_control_count += 1
                self._display_truncation_queued = True
        self._display_events.append(item)
        self._queued_control_count += 1
        if item.event.type == "runtime.display_truncated":
            self._display_truncation_queued = True
        return True

    @staticmethod
    def _compact_control_event(event: Event) -> Event:
        compacted: dict[str, Any] = {}
        remaining = _MAX_CONTROL_EVENT_BYTES
        omitted = False
        for key, value in event.data.items():
            key_size = len(str(key).encode("utf-8"))
            if isinstance(value, str):
                retained = value[:_MAX_CONTROL_STRING_CHARS]
                value_size = len(retained.encode("utf-8"))
                omitted = omitted or retained != value
                candidate: object = retained
            elif value is None or isinstance(value, bool | int | float):
                candidate = value
                value_size = 32
            else:
                bounded_size = RuntimeHost._bounded_display_size(value, remaining - key_size)
                if bounded_size is None:
                    omitted = True
                    candidate = {
                        "display_omitted": True,
                        "items": len(value) if isinstance(value, dict | list | tuple) else None,
                    }
                    value_size = 64
                else:
                    candidate = value
                    value_size = bounded_size
            if key_size + value_size > remaining:
                omitted = True
                continue
            compacted[str(key)] = candidate
            remaining -= key_size + value_size
        if omitted:
            compacted["display_truncated"] = True
        return replace(event, data=compacted)

    @staticmethod
    def _bounded_display_size(value: object, budget: int) -> int | None:
        if budget < 0:
            return None
        if value is None or isinstance(value, bool | int | float):
            return 32 if budget >= 32 else None
        if isinstance(value, str):
            if len(value) > budget:
                return None
            size = len(value.encode("utf-8"))
            return size if size <= budget else None
        if isinstance(value, dict):
            total = 2
            for key, item in value.items():
                key_size = len(str(key).encode("utf-8")) + 4
                item_size = RuntimeHost._bounded_display_size(item, budget - total - key_size)
                if item_size is None:
                    return None
                total += key_size + item_size
                if total > budget:
                    return None
            return total
        if isinstance(value, list | tuple):
            total = 2
            for item in value:
                item_size = RuntimeHost._bounded_display_size(item, budget - total)
                if item_size is None:
                    return None
                total += item_size + 1
                if total > budget:
                    return None
            return total
        return None

    @staticmethod
    def _is_text_delta(event: Event) -> bool:
        return event.data.get("kind") == "text" and isinstance(event.data.get("text"), str)

    def _emit_error(self, event_type: str, exc: BaseException) -> None:
        self._emit(
            event_type,
            {"error_type": type(exc).__name__, "message": str(exc)},
        )

    def _emit_stopped(self) -> None:
        if self._stopped_emitted:
            return
        if self._emit("runtime.stopped", {}):
            self._stopped_emitted = True
