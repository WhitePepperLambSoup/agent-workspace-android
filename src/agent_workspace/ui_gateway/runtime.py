from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import inspect
import json
import math
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import threading
import time
from collections.abc import Awaitable, Callable, Iterator, Mapping
from concurrent.futures import Future
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass, is_dataclass, replace
from dataclasses import field as dataclass_field
from datetime import date, datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol, cast
from urllib.parse import urlsplit
from uuid import uuid4

from agent_workspace.application.agent_control import AgentControlError, AgentControlService
from agent_workspace.application.github_delivery import GitHubDeliveryError, GitHubDeliveryService
from agent_workspace.application.review_workflow import ReviewWorkflowError, ReviewWorkflowService
from agent_workspace.application.runtime_host import RuntimeHost, RuntimeSettings
from agent_workspace.application.scheduler import ScheduledTaskConfigError, ScheduleStore
from agent_workspace.config import (
    ProviderConfig,
    ProviderProtocol,
    default_database_path,
    default_workspace_catalog_path,
    is_loopback_endpoint,
)
from agent_workspace.core.background_jobs import BackgroundJobStatus
from agent_workspace.core.cost import UNKNOWN_PRICING, resolve_pricing, session_cost
from agent_workspace.core.durable_run_queue import DurableRunQueue, RunQueueStatus
from agent_workspace.core.events import Event, validate_event_payload
from agent_workspace.core.git_diff_review import FileDiff, GitDiffReviewService
from agent_workspace.core.git_ops import (
    GitOpsError,
    git_head_sha,
    git_worktree_add,
    git_worktree_is_clean,
    git_worktree_remove,
)
from agent_workspace.core.instructions import INSTRUCTION_FILENAMES, discover_skill_files
from agent_workspace.core.models import (
    MAX_IMAGE_BYTES,
    MAX_IMAGES_PER_MESSAGE,
    AgentRun,
    AgentRunState,
    ApprovalScope,
    AttentionItem,
    AttentionKind,
    AttentionState,
    Autonomy,
    BinaryArtifact,
    ChatMessage,
    DeliveryCheck,
    DeliveryState,
    DeltaKind,
    ImagePart,
    MemoryItem,
    Mode,
    PlanStep,
    PlanStepState,
    ProviderRequest,
    ReviewComment,
    ReviewDelivery,
    ReviewSnapshot,
    Role,
    RunIsolation,
    capabilities_for_mode,
)
from agent_workspace.core.session import Session
from agent_workspace.core.skills import SkillError, load_skills
from agent_workspace.core.task_graph import TaskGraph, classify_failure
from agent_workspace.core.workspace_catalog import WorkspaceCatalog, WorkspaceCatalogError
from agent_workspace.credentials import credential_target
from agent_workspace.policy.redaction import Redactor
from agent_workspace.providers import create_provider
from agent_workspace.providers.health import ProviderHealthResult, provider_health_check
from agent_workspace.providers.reasoning import supported_reasoning_efforts
from agent_workspace.settings import (
    ProviderProfile,
    ProviderSettings,
    ProviderSettingsError,
    ProviderSettingsStore,
    default_provider_settings_store,
)
from agent_workspace.storage import (
    BackupValidationError,
    SearchIndexUnavailableError,
    SessionExportError,
    SQLiteEventStore,
    export_session,
    import_session_archive,
)
from agent_workspace.storage.lock import ProcessWriteLockGroup
from agent_workspace.tools.base import ConcurrentModificationError, ToolError
from agent_workspace.tools.custom import CustomToolError, load_custom_tool_definitions
from agent_workspace.tools.filesystem import _open_identity_checked, atomic_write, sha256_bytes
from agent_workspace.tools.mcp_host import McpHostError, load_mcp_servers
from agent_workspace.tools.paths import WorkspacePaths
from agent_workspace.tools.terminal_sessions import TerminalSessionError
from agent_workspace.ui_gateway.protocol import (
    MAX_MESSAGE_BYTES,
    PROTOCOL_VERSION,
    CommandEnvelope,
    ProtocolError,
    encode_message,
)
from agent_workspace.ui_gateway.transcription import decode_recording, transcribe

_MAX_SESSIONS = 100
_MAX_PROMPT_CHARS = 100_000
_MAX_TURN_QUEUE = 16
_MAX_ATTACHMENTS = 8
_MAX_EXCLUDED_IMAGE_DIGESTS = 16
_MAX_STRING_CHARS = 100_000
_MAX_COLLECTION_ITEMS = 2_000
_MAX_NESTING = 24
_START_TIMEOUT_SECONDS = 10.0
_COMMAND_TIMEOUT_SECONDS = 10.0
_LIFECYCLE_TIMEOUT_SECONDS = 8.0
_HISTORY_MINIMUM_USER_TURNS = 8
_HISTORY_MAX_EVENTS = 1001
_HISTORY_ENTRY_BYTES = 24 * 1024
_HISTORY_ASSISTANT_ENTRY_BYTES = 256 * 1024
_HISTORY_TOTAL_BYTES = 512 * 1024
_MAX_BOOTSTRAP_APPROVALS = 32
_MAX_BOOTSTRAP_STRING_CHARS = 2_048
_MAX_SEARCH_RESULTS = 100
_MAX_CHANGE_PAGE_BYTES = 256 * 1024
_MAX_JOB_LOG_BYTES = 128 * 1024
_MAX_WORKSPACE_READ_BYTES = 1024 * 1024
_MAX_WORKSPACE_EDIT_BYTES = 16 * 1024 * 1024
_MAX_TASK_CONTENT_CHARS = 10_000
_MAX_TASKS_PER_SESSION = 500
_MAX_TASK_POSITION = 1_000_000
_MAX_PARALLEL_AGENT_RUNS = 4
_MAX_AGENT_RUN_CONTINUATIONS = 8
_MAX_PROVIDER_NAME_CHARS = 128
_MAX_PROVIDER_BASE_URL_CHARS = 2_048
_MAX_PROVIDER_MODEL_CHARS = 512
_MAX_PROVIDER_CREDENTIAL_BYTES = 2_560
_PROVIDER_TEST_TIMEOUT_SECONDS = 20.0
_CONTEXT_ESTIMATE_BYTES_PER_TOKEN = 3
_TERMINAL_JOB_STATES = frozenset({"succeeded", "failed", "stopped", "interrupted"})
_BOOTSTRAP_RESERVED_BYTES = 64 * 1024
_SENSITIVE_KEYS = frozenset(
    {"api_key", "apiKey", "credential", "credentials", "password", "secret", "token"}
)
_TERMINAL_TURN_EVENTS = frozenset({"turn.cancelled", "turn.completed", "turn.failed"})
_HOST_LIFECYCLE_EVENTS = frozenset(
    {
        "runtime.started",
        "runtime.stopped",
        "runtime.failed",
        "runtime.error",
        "runtime.command_rejected",
        "runtime.session_switch_failed",
        "runtime.workspace_switch_failed",
        "runtime.autonomy_failed",
        "runtime.mode_applied",
        "runtime.autonomy_applied",
    }
)
_CURRENT_SESSION = object()
_DISPLAY_FIELDS = frozenset(
    {
        "kind",
        "text",
        "content",
        "input_id",
        "model_request_id",
        "superseded_model_request_ids",
        "recoveryAttempt",
        "role",
        "turn_id",
        "attempt_id",
        "tool_call_id",
        "tool_name",
        "name",
        "state",
        "status",
        "error",
        "reason",
        "mode",
        "from_mode",
        "to_mode",
        "autonomy",
        "from_autonomy",
        "to_autonomy",
        "request_id",
        "allowed",
        "scope",
        "finish_reason",
        "usage",
        "reasoning",
        "result",
        "resources",
    }
)
_SAFE_HISTORY_TOOL_ARGUMENTS: dict[str, frozenset[str]] = {
    "list_files": frozenset({"path", "recursive", "max_results", "max_entries"}),
    "read_file": frozenset({"path", "offset", "max_bytes"}),
    "write_file": frozenset({"path", "expected_sha256"}),
    "git_status": frozenset({"repository", "include_ignored", "max_entries"}),
    "git_log": frozenset({"repository", "max_count"}),
    "git_diff": frozenset({"repository", "path", "max_bytes"}),
    "search_text": frozenset({"path", "query", "max_results", "max_entries"}),
    "make_directory": frozenset({"path"}),
    "move_path": frozenset({"source", "destination"}),
    "delete_path": frozenset({"path", "recursive"}),
}
_APPROVAL_DISPLAY_FIELDS = frozenset(
    {"tool", "toolName", "name", "summary", "supportsSessionScope"}
)
_COMPACT_CHANGE_EVENTS = frozenset(
    {"sandbox.changeset.created", "sandbox.change.applied", "sandbox.change.reviewed"}
)


def _approval_display_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if (
        not text
        or len(text) > 160
        or any(ord(char) < 32 for char in text)
        or re.search(r"(?i)api[_-]?key|credential|password|secret|token|bearer", text)
        or re.search(r"[A-Za-z0-9_-]{48,}", text)
        or Redactor().redact(text) != text
    ):
        return None
    return text


def _approval_summary(data: Mapping[str, object]) -> str | None:
    raw_tool = data.get("tool") or data.get("toolName") or data.get("name")
    tool = raw_tool if isinstance(raw_tool, str) else ""
    arguments = data.get("arguments")
    args = arguments if isinstance(arguments, Mapping) else {}
    if tool == "run_process":
        kind = args.get("kind")
        if kind == "direct":
            executable = args.get("executable")
            name = (
                _approval_display_text(executable.replace("\\", "/").rsplit("/", 1)[-1])
                if isinstance(executable, str)
                else None
            )
            command = name or "program"
            argv = args.get("argv")
            if isinstance(argv, list):
                command += f" ({len(argv)} arguments)"
        elif kind == "powershell" or kind == "cmd":
            command = f"{kind} (contents hidden)"
        else:
            command = "process (details hidden)"
        cwd = _approval_display_text(args.get("cwd"))
        return f"Command: {command}" + (f" in {cwd}" if cwd else "")
    if tool == "move_path":
        source = _approval_display_text(args.get("source"))
        destination = _approval_display_text(args.get("destination"))
        if source and destination:
            return f"Move: {source} -> {destination}"
    path = _approval_display_text(args.get("path"))
    if path:
        action = {"write_file": "Write", "delete_path": "Delete", "read_file": "Read"}.get(
            tool, "Target"
        )
        return f"{action}: {path}"
    if data.get("kind") == "provider_egress":
        endpoint = data.get("endpoint")
        if isinstance(endpoint, str):
            try:
                parsed = urlsplit(endpoint)
            except ValueError:
                return None
            host = _approval_display_text(parsed.hostname)
            if parsed.scheme in {"http", "https"} and host:
                return f"Network: {parsed.scheme}://{host}"
    if data.get("kind") == "extension":
        identifier = _approval_display_text(data.get("identifier"))
        if identifier:
            return f"Extension: {identifier}"
    return None


class GatewayError(ValueError):
    """A stable runtime error safe to return over the desktop protocol."""


class Host(Protocol):
    settings: RuntimeSettings

    def start(self) -> None: ...

    def is_alive(self) -> bool: ...

    def request_shutdown(self) -> Future[None] | None: ...

    def join(self, timeout: float | None = None) -> None: ...

    def submit_turn(
        self,
        prompt: str,
        images: tuple[ImagePart, ...] = (),
        *,
        exclude_image_digests: frozenset[str] = frozenset(),
        reasoning_effort: str | None = None,
    ) -> Future[None]: ...

    def optimize_prompt(
        self,
        prompt: str,
        *,
        provider_config: ProviderConfig | None = None,
    ) -> Future[str]: ...

    def request_cancel_turn(self) -> Future[None] | None: ...

    def steer_turn(
        self,
        session_id: str,
        prompt: str,
        turn_id: str,
        *,
        input_id: str | None = None,
        images: tuple[ImagePart, ...] = (),
    ) -> Future[str]: ...

    def request_mode(self, mode: Mode) -> Future[None] | None: ...

    def resolve_approval(
        self, request_id: str, scope: ApprovalScope | str | None
    ) -> Future[None] | None: ...

    def drain_display_events(self, max_deltas: int = 200, max_events: int = 500) -> list[Event]: ...

    def request_job_logs(
        self, session_id: str, job_id: str, max_bytes: int, offset: int = 0
    ) -> Future[object] | None: ...

    def request_job_stop(self, session_id: str, job_id: str) -> Future[object] | None: ...

    def request_terminal_start(
        self,
        argv: tuple[str, ...],
        *,
        cwd: str = ".",
        owner: str | None = None,
        deadline: float | None = None,
        max_output_bytes: int = 512 * 1024,
    ) -> Future[object] | None: ...

    def request_terminal_input(
        self, session_id: str, data: str, *, owner: str | None = None
    ) -> Future[object] | None: ...

    def request_terminal_resize(
        self,
        session_id: str,
        columns: int,
        rows: int,
        *,
        owner: str | None = None,
    ) -> Future[object] | None: ...

    def request_terminal_status(self, session_id: str) -> Future[object] | None: ...

    def request_terminal_list(self, limit: int = 32) -> Future[object] | None: ...

    def request_terminal_replay(
        self, session_id: str, offset: int = 0, max_bytes: int | None = None
    ) -> Future[object] | None: ...

    def request_terminal_stop(
        self, session_id: str, *, owner: str | None = None, reason: str = "stopped"
    ) -> Future[object] | None: ...


class _GatewayRuntimeHost(RuntimeHost):
    """Schedules job actions on the one ApplicationRuntime-owned manager."""

    def request_job_logs(
        self, session_id: str, job_id: str, max_bytes: int, offset: int = 0
    ) -> Future[object] | None:
        loop = self._loop
        if loop is None or loop.is_closed() or self._closing:
            return None

        async def read_logs() -> object:
            runtime = self._runtime
            if runtime is None or runtime.jobs is None:
                raise RuntimeError("background job runtime is unavailable")
            return runtime.jobs.logs(session_id, job_id, offset=offset, max_bytes=max_bytes)

        return asyncio.run_coroutine_threadsafe(read_logs(), loop)

    def request_job_stop(self, session_id: str, job_id: str) -> Future[object] | None:
        loop = self._loop
        if loop is None or loop.is_closed() or self._closing:
            return None

        async def stop_job() -> object:
            runtime = self._runtime
            if runtime is None or runtime.jobs is None:
                raise RuntimeError("background job runtime is unavailable")
            return await runtime.jobs.stop(session_id, job_id)

        return asyncio.run_coroutine_threadsafe(stop_job(), loop)


@dataclass(frozen=True, slots=True)
class GatewayReply:
    type: str
    payload: dict[str, object]
    session_id: str | None
    sequence: int
    should_stop: bool = False

    def to_document(self, request_id: str) -> dict[str, object]:
        return {
            "v": PROTOCOL_VERSION,
            "kind": "response",
            "requestId": request_id,
            "type": self.type,
            "payload": self.payload,
            "sessionId": self.session_id,
            "sequence": self.sequence,
        }


@dataclass(slots=True)
class _ApprovalEntry:
    session_id: str | None
    payload: dict[str, object]
    source_host: Host | None = None
    run_id: str | None = None
    state: Literal["pending", "resolving", "resolved"] = "pending"
    resolution: Future[None] | None = None
    resolution_scope: ApprovalScope | None = None
    turn_terminal: bool = False


@dataclass(slots=True)
class _RunHostEntry:
    run_id: str
    session_id: str
    goal: str
    host: Host
    submitted: bool = False
    terminal: bool = False
    step_attempts: dict[str, str] = dataclass_field(default_factory=dict)
    phase_attempts: dict[str, int] = dataclass_field(default_factory=dict)
    phase_graph: TaskGraph | None = None
    continuation_count: int = 0
    last_result_digest: str | None = None
    no_progress_count: int = 0


@dataclass(slots=True)
class _SessionHostContext:
    """Execution state retained when an ordinary conversation loses focus."""

    host: Host | None
    workspace: Path | None
    provider: ProviderConfig | None
    selected_session_id: str | None
    host_session_id: str | None
    mode: Mode
    autonomy: Autonomy
    runtime_state: str
    active_turn: str | None
    turn_requested: bool
    queued_turns: list[tuple[str, str, list[str], frozenset[str], str | None]]
    ephemeral_queued_images: dict[str, tuple[ImagePart, ...]]
    active_queue_id: str | None
    turn_to_queue_id: dict[str, str]


def _default_provider_test(config: ProviderConfig) -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("provider test cannot run inside an active event loop")
    asyncio.run(_test_provider(config))


async def _test_provider(config: ProviderConfig) -> None:
    provider = create_provider(config)
    finish_seen = False
    text_seen = False
    try:
        async with asyncio.timeout(_PROVIDER_TEST_TIMEOUT_SECONDS):
            request = ProviderRequest(
                model=config.model,
                messages=(ChatMessage(role=Role.USER, content="Reply with OK."),),
            )
            async for delta in provider.stream(request):
                if finish_seen:
                    raise RuntimeError("provider emitted data after its finish marker")
                if delta.kind is DeltaKind.FINISH:
                    finish_reason = (delta.finish_reason or "").strip().casefold().replace("-", "_")
                    if finish_reason not in {"end_turn", "stop", "stop_sequence"}:
                        raise RuntimeError("provider test did not complete normally")
                    finish_seen = True
                elif delta.kind is DeltaKind.TEXT and delta.text.strip():
                    text_seen = True
    finally:
        await provider.aclose()
    if not finish_seen or not text_seen:
        raise RuntimeError("provider test did not return a complete text response")


def _workspace_error_text(error: Exception, workspace: Path) -> str:
    """Bound a configuration error and show paths relative to the workspace."""
    text = str(error).replace(str(workspace) + os.sep, "").replace(str(workspace), ".")
    return text[:500]


def _archive_path(value: object) -> Path:
    """Validate an absolute ``.zip`` path chosen in a desktop file dialog."""
    if not isinstance(value, str) or not value or len(value) > 4096 or "\x00" in value:
        raise GatewayError("invalid_path")
    path = Path(value)
    if not path.is_absolute() or path.suffix.casefold() != ".zip":
        raise GatewayError("invalid_path")
    try:
        return path.resolve()
    except OSError:
        raise GatewayError("invalid_path") from None


def _bounded_text(value: object, limit: int = _MAX_BOOTSTRAP_STRING_CHARS) -> str | None:
    return value[:limit] if isinstance(value, str) else None


def _bounded_scalar(value: object) -> object:
    if isinstance(value, str):
        return value[:_MAX_BOOTSTRAP_STRING_CHARS]
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def _context_budget_from_manifest(
    manifest: Mapping[str, object] | None, usage: Mapping[str, object] | None
) -> dict[str, object] | None:
    """Return a conservative, explainable token budget for a logical request."""

    if manifest is None:
        return None

    def non_negative_int(value: object) -> int | None:
        return value if type(value) is int and value >= 0 else None

    context_limit_bytes = non_negative_int(manifest.get("contextLimitBytes"))
    logical_bytes = non_negative_int(manifest.get("logicalBytes"))
    if context_limit_bytes is None or context_limit_bytes <= 0 or logical_bytes is None:
        return None

    def bytes_to_tokens(value: int) -> int:
        return (value + _CONTEXT_ESTIMATE_BYTES_PER_TOKEN - 1) // _CONTEXT_ESTIMATE_BYTES_PER_TOKEN

    max_output_tokens = non_negative_int(manifest.get("maxOutputTokens")) or 0
    max_tokens = max(0, bytes_to_tokens(context_limit_bytes) - max_output_tokens)
    if max_tokens <= 0:
        return None

    group_bytes: dict[str, int] = {}
    raw_groups = manifest.get("groupBytes")
    if isinstance(raw_groups, Mapping):
        group_bytes = {
            str(kind): size
            for kind, raw_size in raw_groups.items()
            if isinstance(kind, str) and (size := non_negative_int(raw_size)) is not None
        }
    if not group_bytes:
        raw_items = manifest.get("items")
        if isinstance(raw_items, list):
            for raw_item in raw_items:
                if not isinstance(raw_item, Mapping):
                    continue
                kind = raw_item.get("kind")
                size = non_negative_int(raw_item.get("bytes"))
                if isinstance(kind, str) and size is not None:
                    group_bytes[kind] = group_bytes.get(kind, 0) + size

    system_bytes = group_bytes.get("system", 0)
    history_bytes = sum(group_bytes.get(kind, 0) for kind in ("user", "assistant", "tool", "image"))
    memory_bytes = group_bytes.get("memory", 0)
    tools_bytes = group_bytes.get("tool_schema", 0)
    breakdown = {
        "systemTokens": bytes_to_tokens(system_bytes),
        "historyTokens": bytes_to_tokens(history_bytes),
        "memoryTokens": bytes_to_tokens(memory_bytes),
        "toolsTokens": bytes_to_tokens(tools_bytes),
    }

    input_tokens: int | None = None
    if usage is not None:
        input_tokens = non_negative_int(usage.get("inputTokens"))
    if input_tokens is None:
        input_tokens = bytes_to_tokens(logical_bytes)
        source = "logical_context_manifest"
    else:
        source = "provider_usage"
    percentage = min(100, max(0, round(input_tokens * 100 / max_tokens)))
    return {
        "available": True,
        "maxTokens": max_tokens,
        "estimatedUsedTokens": input_tokens,
        "percentage": percentage,
        "source": source,
        "breakdown": breakdown,
    }


def _bounded_projection(value: object, *, depth: int = 0) -> object:
    if depth >= 8:
        return None
    if isinstance(value, str):
        return value[:_MAX_BOOTSTRAP_STRING_CHARS]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        return [_bounded_projection(item, depth=depth + 1) for item in value[:32]]
    if isinstance(value, Mapping):
        return {
            str(key)[:_MAX_BOOTSTRAP_STRING_CHARS]: _bounded_projection(item, depth=depth + 1)
            for key, item in list(value.items())[:32]
            if isinstance(key, str)
        }
    return None


async def _await_value(value: Awaitable[object]) -> object:
    return await value


class GatewayRuntime:
    """Owns session runtimes, the sidecar epoch, wire order, and projections."""

    def __init__(
        self,
        *,
        database: str | Path | None = None,
        host_factory: Callable[[RuntimeSettings], Host] = _GatewayRuntimeHost,
        provider_resolver: Callable[[], ProviderConfig] | None = None,
        provider_settings_store: ProviderSettingsStore | None = None,
        provider_tester: Callable[[ProviderConfig], None] = _default_provider_test,
        provider_health_checker: Callable[[ProviderConfig], ProviderHealthResult] | None = None,
        audio_transcriber: Callable[[ProviderConfig, str, bytes, str, str], str] = transcribe,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        async_workspace_switch: bool | None = None,
        orchestration_runtime: object | None = None,
    ) -> None:
        self.epoch = str(uuid4())
        self._database = Path(database or default_database_path()).expanduser().resolve()
        self._host_factory = host_factory
        self._provider_settings_store = provider_settings_store
        self._provider_resolver = provider_resolver
        self._provider_tester = provider_tester
        self._provider_health_checker = provider_health_checker or provider_health_check
        self._audio_transcriber = audio_transcriber
        self._clock = clock
        self._sleeper = sleeper
        # Optional multi-provider orchestration is deliberately injected. The
        # regular desktop RuntimeHost remains independent, while embedders and
        # remote companions can expose the durable collaboration/delivery DTOs
        # through the same authenticated Gateway contract.
        self._orchestration_runtime = orchestration_runtime
        # Injected test hosts historically expect ``workspace.open`` to be
        # fully settled when the command returns. Production RuntimeHost
        # startup is expensive enough to warrant the asynchronous path. Keep
        # the test seam explicit so callers can exercise either contract.
        self._async_workspace_switch = (
            host_factory is _GatewayRuntimeHost
            if async_workspace_switch is None
            else async_workspace_switch
        )
        self._cursor_key = uuid4().bytes
        self._lock = threading.RLock()
        self._wire_sequence_lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._host_startup_lock = threading.Lock()
        self._host_startup_outcomes: dict[int, str] = {}
        self._next_wire_sequence = 1
        self._host: Host | None = None
        self._writer_lock_group = ProcessWriteLockGroup()
        self._session_hosts: dict[str, _SessionHostContext] = {}
        self._projecting_background_session = False
        self._closing = False
        self._workspace: Path | None = None
        self._git_review_service: GitDiffReviewService | None = None
        self._provider: ProviderConfig | None = None
        self._mode = Mode.CODING
        self._autonomy = Autonomy.WORKSPACE
        self._selected_session_id: str | None = None
        self._host_session_id: str | None = None
        self._active_turn: str | None = None
        self._turn_requested = False
        self._queued_turns: list[tuple[str, str, list[str], frozenset[str], str | None]] = []
        self._ephemeral_queued_images: dict[str, tuple[ImagePart, ...]] = {}
        self._active_queue_id: str | None = None
        self._turn_to_queue_id: dict[str, str] = {}
        self._git_delivery_in_progress = False
        self._runtime_state = "unconfigured"
        self._approval_ledger: dict[str, _ApprovalEntry] = {}
        self._pending_host_events: list[Event] = []
        self._durable_cutoffs: dict[str, int] = {}
        self._snapshot_pending_event_ids: set[str] = set()
        self._session_presentation: dict[str, dict[str, object]] = {}
        # Workspace history is deliberately independent from the event store:
        # a fresh runtime can restore the last folder even before a session has
        # been created in it. Invalid history is ignored and rebuilt on use.
        self._workspace_catalog_path = (
            default_workspace_catalog_path()
            if self._database == default_database_path().expanduser().resolve()
            else self._database.with_name("workspaces.json")
        )
        try:
            self._workspace_catalog: WorkspaceCatalog | None = WorkspaceCatalog(
                self._workspace_catalog_path
            )
        except WorkspaceCatalogError:
            self._workspace_catalog = None
        self._agent_control: AgentControlService | None = None
        self._review_workflow: ReviewWorkflowService | None = None
        self._review_delivery_in_progress: set[str] = set()
        self._run_hosts: dict[str, _RunHostEntry] = {}
        self._run_preparing: set[str] = set()
        self._run_cancel_requested: set[str] = set()
        self._run_prepare_threads: dict[str, threading.Thread] = {}
        self._session_switch_thread: threading.Thread | None = None
        self._session_switch_generation = 0
        self._pending_session_activation_id: str | None = None
        # Workspace replacement is performed off the gateway command lock. A
        # host build opens the SQLite store, provider and tool registry and can
        # take about a second on a warm machine; blocking ``workspace.open``
        # made the desktop appear frozen. The latest requested directory wins
        # while one replacement is in flight.
        self._workspace_switch_thread: threading.Thread | None = None
        self._workspace_switch_generation = 0
        self._pending_workspace_activation: tuple[Path, ProviderConfig] | None = None
        # Keep the target visible for commands that arrive after the
        # lifecycle worker has dequeued it but before the replacement host has
        # committed ``self._workspace``.  In particular, the desktop sends
        # ``session.create`` immediately after ``workspace.open``; the worker
        # may already have moved the target out of ``_pending_workspace_activation``
        # by then.  The target remains authoritative until the worker either
        # commits it or reports a failed replacement.
        self._workspace_activation_target: tuple[Path, ProviderConfig] | None = None
        self._autonomy_switch_thread: threading.Thread | None = None
        self._autonomy_switch_generation = 0
        self._pending_autonomy_request: tuple[str, Autonomy] | None = None
        # A replacement host emits runtime.started before the lifecycle worker
        # has persisted autonomy and published runtime.autonomy_applied. Keep
        # the gateway unavailable for turns until that commit event is queued.
        self._autonomy_apply_pending = False
        self._skip_backup_next_stop = False
        self._load_session_presentation()

    def _apply_autonomy_in_background(
        self,
        session_id: str,
        previous: Autonomy,
        autonomy: Autonomy,
        changed: Event,
        generation: int,
    ) -> None:
        try:
            with self._lock:
                if generation != self._autonomy_switch_generation:
                    return
            with self._lifecycle_lock:
                self._stop_host_for_lifecycle(deadline=self._clock() + _LIFECYCLE_TIMEOUT_SECONDS)
                self._start_host(
                    session_id=session_id, deadline=self._clock() + _LIFECYCLE_TIMEOUT_SECONDS
                )
                self._restore_queued_turns(session_id)
            with self._lock:
                if generation != self._autonomy_switch_generation:
                    return
                # The host's runtime.started event may have been observed
                # before this worker finished persistence and queue restore.
                # Publish the applied marker and only then expose ready state.
                self._autonomy_apply_pending = False
                self._runtime_state = "ready" if self._host is not None else "failed"
                self._pending_host_events.extend(
                    (
                        changed,
                        Event(
                            session_id=session_id,
                            type="runtime.autonomy_applied",
                            data={"autonomy": autonomy.value},
                        ),
                    )
                )
        except GatewayError as error:
            self._recover_autonomy_failure(
                session_id=session_id,
                previous=previous,
                attempted=autonomy,
                generation=generation,
                reason=str(error),
            )
        except Exception as error:
            # A lifecycle worker must never die silently.  A non-GatewayError
            # here used to leave the gateway in ``stopped`` with no host and
            # no recovery signal, which made the next user turn appear to
            # vanish.  Preserve the concrete exception through the normal
            # event stream and restore the previous host before exposing a
            # ready state again.
            self._recover_autonomy_failure(
                session_id=session_id,
                previous=previous,
                attempted=autonomy,
                generation=generation,
                reason=f"{type(error).__name__}: {error}",
            )
        finally:
            with self._lock:
                current = threading.current_thread()
                if self._autonomy_switch_thread is current:
                    self._autonomy_switch_thread = None

    def _recover_autonomy_failure(
        self,
        *,
        session_id: str,
        previous: Autonomy,
        attempted: Autonomy,
        generation: int,
        reason: str,
    ) -> None:
        """Restore a usable previous runtime before publishing a failed switch."""
        with self._lock:
            if generation != self._autonomy_switch_generation:
                return
            self._autonomy = previous
            # A replacement host can emit runtime.started before this recovery
            # has finished. Keep command admission closed until the previous
            # policy has a host that is actually ready.
            self._autonomy_apply_pending = True
            with suppress(Exception), SQLiteEventStore(self._database) as store:
                store.append(
                    Event(
                        session_id=session_id,
                        type="autonomy.changed",
                        data={"from_autonomy": attempted.value, "to_autonomy": previous.value},
                    )
                )

        restored = False
        recovery_reason: str | None = None
        try:
            with self._lifecycle_lock:
                if self._host is not None:
                    self._stop_host_for_lifecycle(
                        deadline=self._clock() + _LIFECYCLE_TIMEOUT_SECONDS
                    )
                self._start_host(
                    session_id=session_id,
                    deadline=self._clock() + _LIFECYCLE_TIMEOUT_SECONDS,
                )
                self._restore_queued_turns(session_id)
                with self._lock:
                    # Recovery owns the autonomy generation. Once the
                    # previous-policy host has started, the temporary gate
                    # used for the failed replacement must be cleared before
                    # evaluating readiness; otherwise runtime.started is
                    # projected as switching and recovery is reported false.
                    self._autonomy_apply_pending = False
                    host = self._host
                    restored = (
                        host is not None
                        and host.is_alive()
                        and self._runtime_state in {"ready", "switching"}
                    )
                    if restored and self._runtime_state == "switching":
                        self._runtime_state = "ready"
        except Exception as error:
            recovery_reason = f"{type(error).__name__}: {error}"
            with self._lock:
                host = self._host
                if host is not None and host.is_alive():
                    self._runtime_state = "stopping"
                else:
                    self._runtime_state = "failed"
        finally:
            with self._lock:
                if generation == self._autonomy_switch_generation:
                    self._autonomy_apply_pending = False
                    if restored:
                        self._runtime_state = "ready"

        with self._lock:
            if generation != self._autonomy_switch_generation:
                return
            self._pending_host_events.append(
                Event(
                    session_id=session_id,
                    type="runtime.autonomy_failed",
                    data={
                        "autonomy": previous.value,
                        "reason": reason,
                        "restored": restored,
                        "recoveryReason": recovery_reason,
                    },
                )
            )

    def _schedule_session_activation(self, session: Session) -> None:
        """Activate the latest selection after the current lifecycle operation."""
        if self._closing or self._workspace is None or self._provider is None:
            return
        if (
            self._host is not None
            and self._host_session_id == session.id
            and self._runtime_state == "ready"
        ):
            self._pending_session_activation_id = None
            return
        current = self._session_switch_thread
        if current is not None and current.is_alive():
            return
        self._session_switch_generation += 1
        generation = self._session_switch_generation
        self._runtime_state = "switching"
        worker = threading.Thread(
            target=self._activate_session_in_background,
            args=(session, generation),
            name=f"session-switch-{session.id[:8]}",
            daemon=True,
        )
        self._session_switch_thread = worker
        worker.start()

    def _activate_pending_session_if_idle(self) -> None:
        if self._projecting_background_session:
            return
        pending_id = self._pending_session_activation_id
        if pending_id is None or self._closing:
            return
        if pending_id == self._host_session_id:
            self._pending_session_activation_id = None
            return
        try:
            session = self._stored_session(pending_id)
        except GatewayError:
            return
        if session is None:
            self._pending_session_activation_id = None
            return
        self._schedule_session_activation(session)

    def _activate_session_in_background(self, session: Session, generation: int) -> None:
        try:
            with self._lock:
                if generation != self._session_switch_generation:
                    return
                workspace = self._workspace
                provider = self._provider
            if workspace is None or provider is None:
                return
            with self._lifecycle_lock:
                with self._lock:
                    if generation != self._session_switch_generation:
                        return
                self._replace_host_unlocked(
                    workspace=workspace,
                    provider=provider,
                    session_id=session.id,
                    mode=session.mode,
                    autonomy=session.autonomy,
                    deadline=self._clock() + _LIFECYCLE_TIMEOUT_SECONDS,
                )
            with self._lock:
                if generation != self._session_switch_generation:
                    return
                if self._pending_session_activation_id == session.id:
                    self._pending_session_activation_id = None
                self._pending_host_events.append(
                    Event(
                        session_id=session.id,
                        type="session.opened",
                        data={"session_id": session.id, "activated": True},
                    )
                )
                pending = self._pending_autonomy_request
                if pending is not None and pending[0] == session.id:
                    self._pending_autonomy_request = None
                    pending_autonomy = pending[1]
                    previous_autonomy = self._autonomy
                    if pending_autonomy is not previous_autonomy:
                        self._autonomy = pending_autonomy
                        self._autonomy_apply_pending = True
                        self._runtime_state = "switching"
                        self._autonomy_switch_generation += 1
                        autonomy_generation = self._autonomy_switch_generation
                        changed = Event(
                            session_id=session.id,
                            type="autonomy.changed",
                            data={
                                "from_autonomy": previous_autonomy.value,
                                "to_autonomy": pending_autonomy.value,
                            },
                        )
                        worker = threading.Thread(
                            target=self._apply_autonomy_in_background,
                            args=(
                                session.id,
                                previous_autonomy,
                                pending_autonomy,
                                changed,
                                autonomy_generation,
                            ),
                            name="autonomy-switch-after-session",
                            daemon=True,
                        )
                        self._autonomy_switch_thread = worker
                        worker.start()
        except GatewayError as error:
            with self._lock:
                if generation != self._session_switch_generation:
                    return
                retryable = (
                    str(error) == "runtime_shutdown_failed"
                    and self._host is not None
                    and self._runtime_state == "stopping"
                )
                if self._pending_session_activation_id == session.id and not retryable:
                    self._pending_session_activation_id = None
                previous_session_id = self._host_session_id
                self._runtime_state = (
                    "stopping" if retryable else ("ready" if self._host is not None else "failed")
                )
                self._pending_host_events.append(
                    Event(
                        session_id=session.id,
                        type="runtime.session_switch_failed",
                        data={
                            "session_id": session.id,
                            "target_session_id": session.id,
                            "previous_session_id": previous_session_id,
                            "generation": generation,
                            "retryable": retryable,
                            "reason": str(error),
                        },
                    )
                )
        finally:
            with self._lock:
                current = threading.current_thread()
                owns_switch_slot = self._session_switch_thread is current
                if owns_switch_slot:
                    self._session_switch_thread = None
                if owns_switch_slot:
                    self._activate_pending_session_if_idle()

    def _restore_queued_turns(self, session_id: str | None) -> None:
        self._ephemeral_queued_images.clear()
        if session_id is None or not self._database.is_file():
            self._queued_turns = []
            return
        try:
            with SQLiteEventStore(self._database) as store:
                turns = store.list_queued_turns(session_id, states=("queued", "running"))
                restored: list[tuple[str, str, list[str], frozenset[str], str | None]] = []
                for t in turns:
                    if t.state == "running":
                        store.mark_turn_state(t.turn_id, "cancelled")
                    elif t.state == "queued":
                        restored.append(
                            (
                                t.turn_id,
                                t.prompt,
                                list(t.references),
                                frozenset(t.exclude_image_digests),
                                t.reasoning_effort,
                            )
                        )
                self._queued_turns = restored
        except (OSError, sqlite3.DatabaseError, ValueError):
            self._queued_turns = []

    @property
    def selected_session_id(self) -> str | None:
        with self._lock:
            return self._selected_session_id

    def _capture_session_host(self) -> _SessionHostContext:
        return _SessionHostContext(
            self._host, self._workspace, self._provider, self._selected_session_id,
            self._host_session_id, self._mode, self._autonomy, self._runtime_state,
            self._active_turn, self._turn_requested, self._queued_turns,
            self._ephemeral_queued_images, self._active_queue_id, self._turn_to_queue_id,
        )

    def _apply_session_host(self, context: _SessionHostContext) -> None:
        self._host = context.host
        self._workspace = context.workspace
        self._provider = context.provider
        self._selected_session_id = context.selected_session_id
        self._host_session_id = context.host_session_id
        self._mode = context.mode
        self._autonomy = context.autonomy
        self._runtime_state = context.runtime_state
        self._active_turn = context.active_turn
        self._turn_requested = context.turn_requested
        self._queued_turns = context.queued_turns
        self._ephemeral_queued_images = context.ephemeral_queued_images
        self._active_queue_id = context.active_queue_id
        self._turn_to_queue_id = context.turn_to_queue_id

    @contextmanager
    def _session_host_scope(self, context: _SessionHostContext) -> Iterator[None]:
        """Route synchronous bookkeeping to its owner under the gateway lock."""
        with self._lock:
            foreground = self._capture_session_host()
            projecting = self._projecting_background_session
            self._apply_session_host(context)
            self._projecting_background_session = True
            try:
                yield
            finally:
                updated = self._capture_session_host()
                for name in _SessionHostContext.__dataclass_fields__:
                    setattr(context, name, getattr(updated, name))
                self._apply_session_host(foreground)
                self._projecting_background_session = projecting

    def _park_session_host(self) -> bool:
        with self._lock:
            session_id = self._host_session_id
            if self._host is None or session_id is None or not (
                self._busy or self._queued_turns
                or getattr(self._host, "has_background_work", False)
            ):
                return False
            context = self._capture_session_host()
            context.selected_session_id = session_id
            if context.runtime_state == "switching" and (
                context.active_turn is not None or context.turn_requested or context.queued_turns
                or getattr(context.host, "has_background_work", False)
            ):
                context.runtime_state = "ready"
            self._session_hosts[session_id] = context
            self._host = None
            self._host_session_id = None
            self._active_turn = None
            self._turn_requested = False
            self._queued_turns = []
            self._ephemeral_queued_images = {}
            self._active_queue_id = None
            self._turn_to_queue_id = {}
            return True

    def _resume_session_host(self, session_id: str | None) -> bool:
        with self._lock:
            context = self._session_hosts.get(session_id) if session_id is not None else None
            if context is None or context.host is None or not context.host.is_alive():
                if session_id is not None:
                    self._session_hosts.pop(session_id, None)
                return False
            self._session_hosts.pop(cast(str, session_id))
            self._apply_session_host(context)
            return True

    def _session_runtime_document(self, *, include_sessions: bool = True) -> dict[str, object]:
        selected_is_active = self._selected_session_id == self._host_session_id
        document: dict[str, object] = {
            "state": self._runtime_state,
            "ready": self._runtime_state == "ready" and selected_is_active,
            "activeTurn": _bounded_text(self._active_turn) if selected_is_active else None,
            "turnRequested": self._turn_requested if selected_is_active else False,
            "mode": self._mode.value,
            "autonomy": self._autonomy.value,
            "queuedCount": len(self._queued_turns) if selected_is_active else 0,
            "hostSessionId": _bounded_text(self._host_session_id),
        }
        if include_sessions:
            document["activeSessions"] = self._active_session_documents()
        return document

    def _active_session_documents(self) -> list[dict[str, object]]:
        contexts = list(self._session_hosts.values())
        if self._host_session_id is not None and self._host is not None:
            contexts.append(self._capture_session_host())
        return [
            {
                "sessionId": context.host_session_id,
                "workspace": str(context.workspace),
                "state": context.runtime_state,
                "ready": context.runtime_state == "ready",
                "activeTurn": context.active_turn,
                "turnRequested": context.turn_requested,
                "queuedCount": len(context.queued_turns),
            }
            for context in contexts
            if context.host is not None and context.host_session_id is not None
        ]

    def _session_queued_count(self, session_id: str) -> int:
        context = self._session_hosts.get(session_id)
        if context is not None and session_id != self._host_session_id:
            return len(context.queued_turns)
        # Parked hosts are keyed by session; with no selected session, any
        # other event comes from the active sessionless host.
        if session_id == self._host_session_id or self._host_session_id is None:
            return len(self._queued_turns)
        return 0

    def _execute_session_command(self, command: CommandEnvelope) -> GatewayReply:
        handler = {
            "turn.start": self._start_turn,
            "turn.steer": self._steer_turn,
            "turn.cancel": self._cancel_turn,
            "runtime.mode.set": self._set_mode,
            "jobs.list": self._list_jobs,
            "jobs.logs": self._job_logs,
            "jobs.stop": self._stop_job,
            "terminal.start": self._terminal_start,
            "terminal.input": self._terminal_input,
            "terminal.resize": self._terminal_resize,
            "terminal.status": self._terminal_status,
            "terminal.list": self._terminal_list,
            "terminal.replay": self._terminal_replay,
            "terminal.stop": self._terminal_stop,
        }[command.type]
        context = self._session_hosts.get(command.session_id) if command.session_id else None
        if context is not None and command.session_id != self._host_session_id:
            with self._session_host_scope(context):
                return handler(command)
        return handler(command)

    def execute(self, command: CommandEnvelope) -> GatewayReply:
        reply = self._execute(command)
        if command.type in {"session.open", "session.create"}:
            with self._lock:
                reply = replace(
                    reply, payload={
                        **reply.payload,
                        "runtime": self._session_runtime_document(),
                        "approvals": self._session_approval_documents(),
                    }
                )
        if command.type.startswith(
            ("workspace.runs.", "workspace.plan.", "workspace.attention.", "workspace.review.")
        ):
            return replace(reply, session_id=command.session_id)
        return reply

    def _session_approval_documents(self) -> list[dict[str, object]]:
        return [
            {**entry.payload, "requestId": request_id, "sessionId": entry.session_id}
            for request_id, entry in self._approval_ledger.items()
            if entry.state != "resolved" and (
                entry.session_id == self._selected_session_id
                or (entry.session_id is None and entry.source_host is self._host)
            )
        ][-_MAX_BOOTSTRAP_APPROVALS:]

    def _execute(self, command: CommandEnvelope) -> GatewayReply:
        # ``workspace.open`` deliberately returns before a production
        # RuntimeHost has finished starting. Commands sent immediately after
        # that response still need a coherent ready host; wait outside the
        # gateway lock so the lifecycle worker can make progress. Session
        # creation also writes the shared SQLite store, so it must join this
        # wait rather than racing the host's startup transaction. Lifecycle
        # commands themselves remain non-blocking and can replace/cancel the
        # pending target.
        background_control = command.type in {
            "turn.start", "turn.steer", "turn.cancel", "jobs.logs", "jobs.stop",
        } and command.session_id in self._session_hosts
        if not background_control and command.type not in {
            "app.handshake",
            "workspace.open",
            "workspace.sessions.list",
            "session.open",
            "app.shutdown",
            "provider.set",
            "provider.clear",
            "provider.delete",
            "provider.default",
            "runtime.mode.set",
            "runtime.autonomy.set",
        }:
            self._await_lifecycle_settle()
        if command.type == "prompt.optimize":
            return self._optimize_prompt(command)
        if command.type == "provider.test":
            return self._test_saved_provider(command)
        if command.type == "provider.health":
            return self._health_saved_provider(command)
        if command.type == "workspace.git.deliver":
            return self._deliver_git_changes(command)
        if command.type == "session.history":
            return self._session_history(command)
        if command.type == "events.replay":
            return self._events_replay(command)
        if command.type in {
            "workspace.schedule.list",
            "workspace.schedule.create",
            "workspace.schedule.update",
            "workspace.schedule.delete",
            "workspace.schedule.pause",
            "workspace.schedule.resume",
            "workspace.schedule.run_now",
            "workspace.schedule.preview",
            "workspace.schedules.list",
            "workspace.schedules.create",
            "workspace.schedules.update",
            "workspace.schedules.delete",
            "workspace.schedules.pause",
            "workspace.schedules.resume",
            "workspace.schedules.run_now",
        }:
            return self._schedule_command(command)
        if command.type in {"workspace.queue.list", "workspace.queue.get"}:
            return self._queue_command(command)
        if command.type in {
            "workspace.collaborations.list",
            "workspace.collaborations.get",
            "workspace.collaborations.cancel",
            "workspace.collaborations.resume",
            "workspace.deliveries.list",
            "workspace.deliveries.get",
            "workspace.deliveries.cancel",
            "workspace.deliveries.resume",
        }:
            return self._orchestration_command(command)
        if command.type in {
            "run.history.page",
            "workspace.runs.history",
            "run.evidence.page",
            "workspace.runs.evidence",
            "workspace.plan.retry",
            "workspace.plan.skip",
            "workspace.runs.failure.action",
        }:
            return self._run_continuity_command(command)
        if command.type == "system.doctor":
            return self._run_doctor(command)
        if command.type == "session.export":
            return self._export_session(command)
        if command.type == "session.import":
            return self._import_session(command)
        if command.type == "session.usage":
            return self._session_usage(command)
        if command.type == "memory.list":
            return self._list_memories(command)
        if command.type == "workspace.agent.inspect":
            return self._inspect_agent_setup(command)
        if command.type == "audio.transcribe":
            return self._transcribe_audio(command)
        if command.type in {"memory.update", "memory.delete"}:
            return self._write_memory(command)
        if command.type == "workspace.review.create":
            return self._create_review_snapshot(command)
        if command.type == "workspace.review.pr.create":
            return self._create_review_pull_request(command)
        if command.type == "workspace.review.pr.refresh":
            return self._refresh_review_pull_request(command)
        with self._lock:
            if command.type == "app.handshake":
                return self._handshake(command)
            if command.type == "app.bootstrap":
                self._require_payload(command, set())
                return self._bootstrap_reply(command.request_id)
            if command.type == "workspace.open":
                return self._open_workspace(command)
            if command.type == "workspace.sessions.list":
                return self._list_workspace_sessions(command)
            if command.type == "session.list":
                return self._list_sessions(command)
            if command.type == "session.open":
                return self._open_session(command)
            if command.type == "session.create":
                return self._create_session(command)
            if command.type == "session.presentation.set":
                return self._set_session_presentation(command)
            if command.type == "session.search":
                return self._search_sessions(command)
            if command.type == "research.sources.list":
                return self._list_research_sources(command)
            if command.type == "research.source.read":
                return self._read_research_source(command)
            if command.type == "research.citations.list":
                return self._list_research_citations(command)
            if command.type == "workspace.summary.get":
                return self._workspace_summary(command)
            if command.type == "changes.list":
                return self._list_changes(command)
            if command.type == "changes.inspect":
                return self._inspect_change(command)
            if command.type == "jobs.list":
                return self._execute_session_command(command)
            if command.type == "jobs.logs":
                return self._execute_session_command(command)
            if command.type == "jobs.stop":
                return self._execute_session_command(command)
            if command.type == "terminal.start":
                return self._execute_session_command(command)
            if command.type == "terminal.input":
                return self._execute_session_command(command)
            if command.type == "terminal.resize":
                return self._execute_session_command(command)
            if command.type == "terminal.status":
                return self._execute_session_command(command)
            if command.type == "terminal.list":
                return self._execute_session_command(command)
            if command.type == "terminal.replay":
                return self._execute_session_command(command)
            if command.type == "terminal.stop":
                return self._execute_session_command(command)
            if command.type == "provider.list":
                return self._list_providers(command)
            if command.type == "provider.get":
                return self._get_provider(command)
            if command.type == "provider.set":
                return self._set_provider(command)
            if command.type == "provider.clear":
                return self._clear_provider(command)
            if command.type == "provider.delete":
                return self._delete_provider(command)
            if command.type == "provider.default":
                return self._set_default_provider(command)
            if command.type == "provider.bootstrap":
                return self._bootstrap_provider(command)
            if command.type == "provider.health":
                return self._health_saved_provider(command)
            if command.type == "turn.start":
                return self._execute_session_command(command)
            if command.type == "turn.steer":
                return self._execute_session_command(command)
            if command.type == "turn.cancel":
                return self._execute_session_command(command)
            if command.type == "runtime.mode.set":
                return self._execute_session_command(command)
            if command.type == "runtime.autonomy.set":
                return self._set_autonomy(command)
            if command.type == "approval.resolve":
                return self._resolve_approval(command)
            if command.type == "workspace.files.tree":
                return self._list_workspace_files_tree(command)
            if command.type == "workspace.file.read":
                return self._read_workspace_file(command)
            if command.type == "workspace.file.write":
                return self._write_workspace_file(command)
            if command.type == "workspace.git.diff":
                return self._get_git_diff(command)
            if command.type == "workspace.git.revert":
                return self._revert_git_diff(command)
            if command.type == "workspace.git.undo":
                return self._undo_git_diff(command)
            if command.type == "workspace.context.get":
                return self._get_workspace_context(command)
            if command.type == "workspace.tasks.list":
                return self._list_tasks(command)
            if command.type == "workspace.tasks.create":
                return self._create_task(command)
            if command.type == "workspace.tasks.update":
                return self._update_task(command)
            if command.type == "workspace.tasks.delete":
                return self._delete_task(command)
            if command.type == "workspace.runs.list":
                return self._list_agent_runs(command)
            if command.type == "workspace.runs.get":
                return self._get_agent_run(command)
            if command.type == "workspace.runs.create":
                return self._create_agent_run(command)
            if command.type == "workspace.runs.update":
                return self._update_agent_run(command)
            if command.type == "workspace.runs.start":
                return self._start_agent_run(command)
            if command.type == "workspace.runs.pause":
                return self._pause_agent_run(command)
            if command.type == "workspace.runs.resume":
                return self._resume_agent_run(command)
            if command.type == "workspace.runs.cancel":
                return self._cancel_agent_run(command)
            if command.type == "workspace.runs.cleanup":
                return self._cleanup_agent_run(command)
            if command.type == "workspace.plan.list":
                return self._list_plan_steps(command)
            if command.type == "workspace.plan.create":
                return self._create_plan_step(command)
            if command.type == "workspace.plan.update":
                return self._update_plan_step(command)
            if command.type == "workspace.plan.delete":
                return self._delete_plan_step(command)
            if command.type == "workspace.attention.list":
                return self._list_attention(command)
            if command.type == "workspace.attention.resolve":
                return self._resolve_attention(command)
            if command.type == "workspace.review.list":
                return self._list_review_snapshots(command)
            if command.type == "workspace.review.get":
                return self._get_review_snapshot(command)
            if command.type == "workspace.review.comments.create":
                return self._create_review_comment(command)
            if command.type == "workspace.review.comments.resolve":
                return self._resolve_review_comment(command)
            if command.type == "workspace.review.comments.followup":
                return self._followup_review_comment(command)
            if command.type == "system.doctor":
                return self._run_doctor(command)
            if command.type == "app.shutdown":
                self._require_payload(command, set())
                self._remember_selected_session()
                self._begin_close()
                self._stop_run_hosts()
                self._stop_session_hosts()
                self._stop_host()
                return self._reply(
                    "app.shutdown.result",
                    {"epoch": self.epoch, "stopping": True},
                    session_id=None,
                    should_stop=True,
                )
            raise GatewayError("unsupported_command")

    def _await_lifecycle_settle(self) -> None:
        """Wait briefly for an asynchronous workspace/session replacement.

        This is called before acquiring ``self._lock``. A command arriving
        directly after ``workspace.open`` should observe the new workspace,
        while the worker still needs that lock to publish its ready state. The
        wait is bounded by the same lifecycle timeout used for host startup;
        an unresolved replacement then receives the normal
        ``runtime_unavailable`` error from the command handler.
        """

        deadline = self._clock() + _LIFECYCLE_TIMEOUT_SECONDS
        while True:
            threads = (
                self._workspace_switch_thread,
                self._session_switch_thread,
                self._autonomy_switch_thread,
            )
            active = tuple(
                thread
                for thread in threads
                if thread is not None
                and thread is not threading.current_thread()
                and thread.is_alive()
            )
            if not active:
                return
            remaining = deadline - self._clock()
            if remaining <= 0:
                return
            for thread in active:
                thread.join(timeout=min(remaining, 0.05))

    def error_reply(
        self, request_id: str, code: str, session_id: str | None = None
    ) -> dict[str, object]:
        if re.fullmatch(r"[a-z][a-z0-9_]*", code, flags=re.ASCII) is None:
            code = "runtime_error"
        with self._lock:
            return self._reply(
                "app.error",
                {"code": code, "epoch": self.epoch},
                session_id=session_id,
            ).to_document(request_id)

    def drain_events(self) -> list[dict[str, object]]:
        with self._lock:
            self._collect_host_events()
            raw = self._pending_host_events
            self._pending_host_events = []
            documents: list[dict[str, object]] = []
            for event in raw:
                cutoff = self._durable_cutoffs.get(event.session_id, 0)
                if event.sequence is not None and event.sequence <= cutoff:
                    if event.id in self._snapshot_pending_event_ids:
                        self._snapshot_pending_event_ids.discard(event.id)
                        continue
                    if event.type != "turn.started" and event.type not in _TERMINAL_TURN_EVENTS:
                        continue
                documents.append(self._event_document(event))
                if event.sequence is not None:
                    self._durable_cutoffs[event.session_id] = event.sequence
            return documents

    def close(self) -> None:
        with self._lock:
            self._begin_close()
            self._stop_run_hosts()
            self._stop_session_hosts()
            self._stop_host()

    def _begin_close(self) -> None:
        self._closing = True
        self._pending_workspace_activation = None
        self._workspace_activation_target = None
        self._pending_session_activation_id = None
        self._workspace_switch_generation += 1
        self._session_switch_generation += 1
        self._autonomy_switch_generation += 1

    @property
    def _presentation_path(self) -> Path:
        return self._database.with_name(f"{self._database.stem}.session-presentation-v1.json")

    def _load_session_presentation(self) -> None:
        path = self._presentation_path
        try:
            if not path.is_file() or path.stat().st_size > 256 * 1024:
                return
            document = json.loads(path.read_text("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return
        if not isinstance(document, Mapping) or document.get("version") != 1:
            return
        records = document.get("records")
        if not isinstance(records, Mapping):
            return
        for key, raw in list(records.items())[:_MAX_COLLECTION_ITEMS]:
            if not isinstance(key, str) or not isinstance(raw, Mapping):
                continue
            session_id = raw.get("sessionId")
            alias = raw.get("alias")
            pinned = raw.get("pinned")
            archived = raw.get("archived")
            if (
                isinstance(session_id, str)
                and 0 < len(session_id) <= 256
                and (alias is None or (isinstance(alias, str) and len(alias) <= 200))
                and type(pinned) is bool
                and type(archived) is bool
            ):
                self._session_presentation[key] = {
                    "sessionId": session_id,
                    "alias": alias,
                    "pinned": pinned,
                    "archived": archived,
                    "version": 1,
                }

    def _persist_session_presentation(self) -> None:
        path = self._presentation_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(
                    {"version": 1, "records": self._session_presentation},
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                "utf-8",
            )
            temporary.replace(path)
        except OSError:
            raise GatewayError("presentation_unavailable") from None

    def _touch_workspace_catalog(self, workspace: Path) -> None:
        """Remember a successfully opened workspace without blocking runtime use."""
        try:
            catalog = self._workspace_catalog
            if catalog is None:
                catalog = WorkspaceCatalog(self._workspace_catalog_path)
                self._workspace_catalog = catalog
            catalog.touch(workspace)
        except (OSError, RuntimeError, ValueError, WorkspaceCatalogError):
            # A read-only profile or malformed legacy catalog must never make
            # opening a workspace fail; the event store remains authoritative.
            return

    def _recent_workspace_documents(self, limit: int = 12) -> list[dict[str, object]]:
        catalog = self._workspace_catalog
        if catalog is None:
            return []
        documents: list[dict[str, object]] = []
        for entry in catalog.entries()[:limit]:
            path = Path(entry.path)
            if not path.is_dir():
                continue
            documents.append(
                {
                    "path": _bounded_text(entry.path),
                    "name": _bounded_text(entry.name),
                    "lastUsed": entry.last_used,
                }
            )
        return documents

    def _presentation_key(self, session_id: str) -> str:
        assert self._workspace is not None
        assert self._provider is not None
        digest = hashlib.sha256(str(self._workspace).encode("utf-8")).hexdigest()
        return f"{digest}:{session_id}"

    def _workspace_presentations(self) -> dict[str, dict[str, object]]:
        if self._workspace is None:
            return {}
        digest = hashlib.sha256(str(self._workspace).encode("utf-8")).hexdigest() + ":"
        return {
            cast(str, record["sessionId"]): dict(record)
            for key, record in self._session_presentation.items()
            if key.startswith(digest)
        }

    def _handshake(self, command: CommandEnvelope) -> GatewayReply:
        if command.payload != {"client": "electron", "protocol": PROTOCOL_VERSION}:
            raise GatewayError("invalid_handshake")
        return self._reply(
            "app.handshake.result",
            {
                "epoch": self.epoch,
                "protocol": PROTOCOL_VERSION,
                "ready": True,
                "features": [
                    "runtime",
                    "sessions",
                    "approvals",
                    "resync",
                    "search",
                    "changes",
                    "jobs",
                    "providers",
                ],
                "maxMessageBytes": 1_048_576,
            },
            session_id=None,
        )

    def _bootstrap_reply(self, request_id: str) -> GatewayReply:
        self._restore_last_session()
        self._collect_host_events()
        sequence = self._take_sequence()
        reply = GatewayReply(
            "app.bootstrap.result",
            self._snapshot(sequence),
            self._selected_session_id,
            sequence,
        )
        try:
            self._preflight_bootstrap(reply.to_document(request_id))
        except ProtocolError:
            reply = GatewayReply(
                "app.bootstrap.result",
                self._snapshot(sequence, compact=True),
                self._selected_session_id,
                sequence,
            )
            try:
                self._preflight_bootstrap(reply.to_document(request_id))
            except ProtocolError:
                raise GatewayError("runtime_bootstrap_failed") from None
        if self._selected_session_id is not None:
            self._acknowledge_history_page(self._selected_session_id, reply.payload)
        return reply

    def _selected_session_path(self) -> Path:
        return self._database.with_name("last-selected-session.json")

    def _remember_selected_session(self) -> None:
        """Record the session the user was viewing so a relaunch reopens it.

        Parallel sessions mean the most recently updated session is not
        necessarily the one on screen; the recency order stays the fallback.
        """
        session_id = self._selected_session_id
        if not session_id:
            return
        path = self._selected_session_path()
        staging = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            staging.write_text(json.dumps({"sessionId": session_id}), encoding="utf-8")
            os.replace(staging, path)
        except OSError:
            staging.unlink(missing_ok=True)

    def _remembered_session(self) -> Session | None:
        try:
            raw = json.loads(self._selected_session_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        session_id = raw.get("sessionId") if isinstance(raw, dict) else None
        if not isinstance(session_id, str) or not session_id or len(session_id) > 256:
            return None
        try:
            # Only an ordinary conversation in a folder that still exists qualifies.
            matches = SQLiteEventStore.list_sessions_read_only(
                self._database, limit=1, include_ids=[session_id], exclude_run_sessions=True
            )
        except (OSError, ValueError, sqlite3.DatabaseError):
            return None
        session = next((item for item in matches if item.id == session_id), None)
        if session is None or not Path(session.workspace).is_dir():
            return None
        return session

    def _restore_last_session(self) -> None:
        """Reopen the session viewed at the last shutdown, else the most recent one."""
        if (
            self._runtime_state != "unconfigured"
            or self._host is not None
            or self._workspace is not None
        ):
            return
        session: Session | None = None
        try:
            if self._database.is_file():
                session = self._remembered_session()
                if session is None:
                    sessions = SQLiteEventStore.list_sessions_read_only(
                        self._database, limit=1, exclude_run_sessions=True
                    )
                    if sessions:
                        session = sessions[0]
            if session is not None:
                workspace = Path(session.workspace).expanduser().resolve(strict=True)
            else:
                recent = self._recent_workspace_documents(limit=1)
                if not recent:
                    return
                workspace = Path(cast(str, recent[0]["path"])).expanduser().resolve(strict=True)
            if not workspace.is_dir():
                return
            resolver = self._provider_resolver
            provider = (
                resolver() if resolver is not None else self._settings_store().resolve_config()
            )
            provider.validate()
        except (
            GatewayError,
            KeyError,
            OSError,
            ProviderSettingsError,
            RuntimeError,
            sqlite3.DatabaseError,
            ValueError,
        ):
            return

        previous_autonomy = self._autonomy
        self._autonomy = session.autonomy if session is not None else Autonomy.WORKSPACE
        try:
            self._replace_host(
                workspace=workspace,
                provider=provider,
                session_id=session.id if session is not None else None,
                mode=session.mode if session is not None else Mode.CODING,
                deadline=self._clock() + _LIFECYCLE_TIMEOUT_SECONDS,
            )
            self._touch_workspace_catalog(workspace)
        except GatewayError:
            self._autonomy = previous_autonomy

    @staticmethod
    def _preflight_bootstrap(document: Mapping[str, object]) -> None:
        encoded = encode_message(document)
        if len(encoded) + _BOOTSTRAP_RESERVED_BYTES > MAX_MESSAGE_BYTES:
            raise ProtocolError("message_too_large")

    def _snapshot(self, watermark: int, *, compact: bool = False) -> dict[str, object]:
        recent_workspaces = self._recent_workspace_documents()
        if compact:
            return {
                "epoch": self.epoch,
                "watermark": watermark,
                "ready": self._runtime_state == "ready",
                "runtime": self._session_runtime_document(),
                "workspace": (
                    None
                    if self._workspace is None
                    else {
                        "path": _bounded_text(str(self._workspace)),
                        "name": _bounded_text(self._workspace.name),
                    }
                ),
                **({"recentWorkspaces": recent_workspaces} if recent_workspaces else {}),
                "provider": (
                    None
                    if self._provider is None
                    else {
                        "id": _bounded_text(self._provider.id),
                        "model": _bounded_text(self._provider.model),
                    }
                ),
                "sessions": [],
                "selectedSession": (
                    None
                    if self._selected_session_id is None
                    else {
                        "id": _bounded_text(self._selected_session_id),
                        "title": "Selected session",
                        "workspace": _bounded_text(str(self._workspace))
                        if self._workspace is not None
                        else None,
                        "mode": self._mode.value,
                        "autonomy": self._autonomy.value,
                    }
                ),
                "timeline": [],
                "history": {"hasMore": False, "nextCursor": None, "cutoff": 0},
                "approvals": [],
                "sessionPresentation": {},
                "truncated": True,
            }
        sessions = self._sessions(_MAX_SESSIONS)
        selected = next(
            (item for item in sessions if item["id"] == self._selected_session_id), None
        )
        page = (
            self._history_page(self._selected_session_id)
            if self._selected_session_id is not None
            else {"timeline": [], "history": {"hasMore": False, "nextCursor": None, "cutoff": 0}}
        )
        unresolved = [
            {**entry.payload, "requestId": request_id, "sessionId": entry.session_id}
            for request_id, entry in self._approval_ledger.items()
            if entry.state != "resolved"
        ]
        approvals = unresolved[-_MAX_BOOTSTRAP_APPROVALS:]
        provider = self._provider
        return {
            "epoch": self.epoch,
            "watermark": watermark,
            "ready": self._runtime_state == "ready",
            "runtime": self._session_runtime_document(),
            "workspace": (
                None
                if self._workspace is None
                else {
                    "path": _bounded_text(str(self._workspace)),
                    "name": _bounded_text(self._workspace.name),
                }
            ),
            **({"recentWorkspaces": recent_workspaces} if recent_workspaces else {}),
            "provider": (
                None
                if provider is None
                else {
                    "id": _bounded_text(provider.id),
                    "model": _bounded_text(provider.model),
                }
            ),
            "sessions": sessions,
            "selectedSession": selected,
            "timeline": page["timeline"],
            "history": page["history"],
            "approvals": approvals,
            "sessionPresentation": self._workspace_presentations(),
            **({"approvalsTruncated": True} if len(unresolved) > len(approvals) else {}),
        }

    def _list_providers(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set())
        settings = self._load_provider_settings()
        providers = [
            self._provider_document(profile, settings) for profile in settings.profiles.values()
        ]
        return self._reply(
            "provider.list.result",
            {
                "epoch": self.epoch,
                "defaultProviderId": settings.default_provider_id,
                "providers": providers,
            },
            session_id=None,
        )

    def _get_provider(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"providerId"})
        provider_id = self._provider_id(command.payload.get("providerId"))
        settings = self._load_provider_settings()
        profile = self._saved_provider(settings, provider_id)
        return self._reply(
            "provider.get.result",
            {
                "epoch": self.epoch,
                "provider": self._provider_document(profile, settings),
            },
            session_id=None,
        )

    def _set_provider(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(
            command,
            {"providerId", "name", "protocol", "baseUrl", "model"},
            optional={"apiKey", "makeDefault"},
        )
        provider_id = self._provider_id(command.payload.get("providerId"))
        name = self._provider_text(
            command.payload.get("name"),
            max_chars=_MAX_PROVIDER_NAME_CHARS,
            allow_empty=False,
        )
        base_url = self._provider_text(
            command.payload.get("baseUrl"),
            max_chars=_MAX_PROVIDER_BASE_URL_CHARS,
            allow_empty=False,
        )
        model = self._provider_text(
            command.payload.get("model"),
            max_chars=_MAX_PROVIDER_MODEL_CHARS,
            allow_empty=True,
        )
        raw_protocol = command.payload.get("protocol")
        if not isinstance(raw_protocol, str):
            raise GatewayError("invalid_provider")
        try:
            protocol = ProviderProtocol(raw_protocol)
            target = credential_target(provider_id, base_url)
        except (TypeError, ValueError):
            raise GatewayError("invalid_provider") from None

        raw_default = command.payload.get("makeDefault", False)
        if not isinstance(raw_default, bool):
            raise GatewayError("invalid_provider")
        raw_secret = command.payload.get("apiKey")
        secret: str | None = None
        if "apiKey" in command.payload:
            if (
                not isinstance(raw_secret, str)
                or not raw_secret.strip()
                or raw_secret != raw_secret.strip()
                or not raw_secret.isprintable()
            ):
                raise GatewayError("invalid_provider_credential")
            try:
                credential_bytes = len(raw_secret.encode("utf-8"))
            except UnicodeEncodeError:
                raise GatewayError("invalid_provider_credential") from None
            if credential_bytes > _MAX_PROVIDER_CREDENTIAL_BYTES:
                raise GatewayError("invalid_provider_credential")
            secret = raw_secret

        profile = ProviderProfile(
            id=provider_id,
            name=name,
            protocol=protocol,
            base_url=base_url,
            model=model,
            credential_target=target,
        )
        try:
            has_credential = (
                True if secret is not None else self._settings_store().has_credential(profile)
            )
        except (OSError, ProviderSettingsError, ValueError):
            raise GatewayError("provider_settings_unavailable") from None
        try:
            settings = self._settings_store().upsert(
                profile,
                secret=secret,
                make_default=raw_default,
            )
        except (OSError, ProviderSettingsError, ValueError):
            raise GatewayError("provider_settings_failed") from None
        return self._reply(
            "provider.set.result",
            {
                "epoch": self.epoch,
                "defaultProviderId": settings.default_provider_id,
                "provider": self._provider_document(
                    profile,
                    settings,
                    has_credential=has_credential,
                ),
            },
            session_id=None,
        )

    def _clear_provider(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"providerId"})
        provider_id = self._provider_id(command.payload.get("providerId"))
        settings = self._load_provider_settings()
        profile = self._saved_provider(settings, provider_id)
        active = self._provider is not None and self._provider.id == provider_id
        if active and self._busy:
            raise GatewayError("runtime_busy")
        previous_provider = self._provider
        previous_session_id = self._selected_session_id
        if active:
            self._stop_host()
        try:
            self._settings_store().clear_credential(profile)
        except (OSError, ProviderSettingsError, ValueError):
            if active:
                assert previous_provider is not None
                credential_restored = previous_provider.api_key is None
                if previous_provider.api_key is not None:
                    try:
                        self._settings_store().set_credential(
                            provider_id,
                            previous_provider.api_key,
                        )
                        credential_restored = True
                    except (KeyError, OSError, ProviderSettingsError, ValueError):
                        credential_restored = False
                if credential_restored:
                    self._provider = previous_provider
                    self._start_host(session_id=previous_session_id)
                else:
                    self._provider = None
                    self._host = None
                    self._runtime_state = "unconfigured"
            raise GatewayError("provider_settings_failed") from None
        if active:
            self._provider = None
            self._host = None
            self._runtime_state = "unconfigured"
        return self._reply(
            "provider.clear.result",
            {
                "epoch": self.epoch,
                "provider": self._provider_document(
                    profile,
                    settings,
                    has_credential=False,
                ),
            },
            session_id=None,
        )

    def _delete_provider(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"providerId"})
        provider_id = self._provider_id(command.payload.get("providerId"))
        settings = self._load_provider_settings()
        self._saved_provider(settings, provider_id)
        if provider_id == settings.default_provider_id or (
            self._provider is not None and provider_id == self._provider.id
        ):
            raise GatewayError("provider_in_use")
        try:
            updated = self._settings_store().delete(provider_id)
        except KeyError:
            raise GatewayError("unknown_provider") from None
        except (OSError, ProviderSettingsError, ValueError):
            raise GatewayError("provider_settings_failed") from None
        return self._reply(
            "provider.delete.result",
            {
                "epoch": self.epoch,
                "deletedProviderId": provider_id,
                "defaultProviderId": updated.default_provider_id,
            },
            session_id=None,
        )

    def _set_default_provider(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"providerId"})
        provider_id = self._provider_id(command.payload.get("providerId"))
        settings = self._load_provider_settings()
        profile = self._saved_provider(settings, provider_id)
        try:
            provider = self._settings_store().resolve_config(provider_id)
            provider.validate()
        except KeyError:
            raise GatewayError("unknown_provider") from None
        except (OSError, ProviderSettingsError, ValueError):
            raise GatewayError("provider_settings_unavailable") from None
        if self._busy:
            raise GatewayError("runtime_busy")

        previous_default_id = settings.default_provider_id
        previous_provider = self._provider
        previous_session_id = self._selected_session_id
        try:
            updated = self._settings_store().set_default(provider_id)
        except KeyError:
            raise GatewayError("unknown_provider") from None
        except (OSError, ProviderSettingsError, ValueError):
            raise GatewayError("provider_settings_failed") from None

        applied = self._workspace is not None
        if applied:
            deadline = self._clock() + _LIFECYCLE_TIMEOUT_SECONDS
            replacement_attempted = False
            try:
                if self._host is not None:
                    self._stop_host_for_lifecycle(deadline=deadline)
                self._provider = provider
                replacement_attempted = True
                self._start_host(session_id=previous_session_id, deadline=deadline)
            except GatewayError as error:
                failure_code = "runtime_start_failed" if replacement_attempted else str(error)
                replacement_cleanup_failed = False
                if replacement_attempted and self._host is not None:
                    try:
                        self._stop_host_for_lifecycle()
                    except GatewayError:
                        replacement_cleanup_failed = True
                rollback_settings_failed = False
                if previous_default_id is None:
                    rollback_settings_failed = True
                else:
                    try:
                        self._settings_store().set_default(previous_default_id)
                    except (KeyError, OSError, ProviderSettingsError, ValueError):
                        rollback_settings_failed = True
                if not replacement_attempted:
                    self._provider = previous_provider
                elif not replacement_cleanup_failed:
                    self._provider = previous_provider
                    if previous_provider is None:
                        self._host = None
                        self._runtime_state = "unconfigured"
                    else:
                        try:
                            self._start_host(session_id=previous_session_id)
                        except GatewayError:
                            raise GatewayError("runtime_start_failed") from None
                if rollback_settings_failed:
                    raise GatewayError("provider_settings_failed") from None
                raise GatewayError(failure_code) from None

        return self._reply(
            "provider.default.result",
            {
                "epoch": self.epoch,
                "defaultProviderId": updated.default_provider_id,
                "applied": applied,
                "provider": self._provider_document(
                    profile,
                    updated,
                    has_credential=provider.api_key is not None,
                ),
            },
            session_id=None,
        )

    def _bootstrap_provider(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"providerId"})
        raw_provider_id = command.payload.get("providerId")
        provider_id = self._provider_id(raw_provider_id) if raw_provider_id is not None else None
        settings = self._load_provider_settings()
        selected_id = provider_id or settings.default_provider_id
        providers = [
            self._provider_document(profile, settings) for profile in settings.profiles.values()
        ]
        if selected_id is None:
            return self._reply(
                "provider.bootstrap.result",
                {
                    "epoch": self.epoch,
                    "status": "needs_setup",
                    "ready": False,
                    "nextAction": "select_provider",
                    "defaultProviderId": None,
                    "provider": None,
                    "providers": providers,
                },
                session_id=None,
            )
        profile = self._saved_provider(settings, selected_id)
        has_credential = self._settings_store().has_credential(profile)
        # Local servers (Ollama, llama.cpp, LM Studio, vLLM) on loopback need no key.
        local_endpoint = profile.protocol is ProviderProtocol.OLLAMA or is_loopback_endpoint(
            profile.base_url
        )
        status = "ready" if has_credential or local_endpoint else "needs_credential"
        next_action = None if status == "ready" else "enter_api_key"
        return self._reply(
            "provider.bootstrap.result",
            {
                "epoch": self.epoch,
                "status": status,
                "ready": status == "ready",
                "nextAction": next_action,
                "defaultProviderId": settings.default_provider_id,
                "provider": self._provider_document(
                    profile, settings, has_credential=has_credential
                ),
                "providers": providers,
            },
            session_id=None,
        )

    def _health_saved_provider(self, command: CommandEnvelope) -> GatewayReply:
        with self._lock:
            self._require_payload(command, set(), optional={"providerId"})
            raw_provider_id = command.payload.get("providerId")
            provider_id = (
                self._provider_id(raw_provider_id) if raw_provider_id is not None else None
            )
            settings = self._load_provider_settings()
            if provider_id is not None:
                self._saved_provider(settings, provider_id)
            elif settings.default_provider_id is None:
                raise GatewayError("provider_unconfigured")
            try:
                config = self._settings_store().resolve_config(provider_id)
            except KeyError:
                raise GatewayError("unknown_provider") from None
            except (OSError, ProviderSettingsError, ValueError):
                raise GatewayError("provider_unconfigured") from None
        result = self._provider_health_checker(config)
        if not isinstance(result, ProviderHealthResult):
            raise GatewayError("provider_health_failed")
        return self._reply(
            "provider.health.result",
            {"epoch": self.epoch, **result.to_document()},
            session_id=None,
        )

    def _test_saved_provider(self, command: CommandEnvelope) -> GatewayReply:
        with self._lock:
            self._require_payload(command, set(), optional={"providerId"})
            raw_provider_id = command.payload.get("providerId")
            provider_id = (
                self._provider_id(raw_provider_id) if raw_provider_id is not None else None
            )
            settings = self._load_provider_settings()
            if provider_id is not None:
                self._saved_provider(settings, provider_id)
            elif settings.default_provider_id is None:
                raise GatewayError("provider_unconfigured")
            try:
                config = self._settings_store().resolve_config(provider_id)
            except KeyError:
                raise GatewayError("unknown_provider") from None
            except (OSError, ProviderSettingsError, ValueError):
                raise GatewayError("provider_unconfigured") from None
        try:
            self._provider_tester(config)
        except Exception:
            raise GatewayError("provider_test_failed") from None
        with self._lock:
            return self._reply(
                "provider.test.result",
                {"epoch": self.epoch, "providerId": config.id, "ok": True},
                session_id=None,
            )

    def _transcribe_audio(self, command: CommandEnvelope) -> GatewayReply:
        """Turn a composer recording into text with a saved OpenAI-compatible profile."""
        with self._lock:
            self._require_payload(command, {"providerId", "model", "mediaType", "data"})
            provider_id = self._provider_id(command.payload.get("providerId"))
            model = command.payload.get("model")
            if not isinstance(model, str) or not model.strip() or len(model) > 200:
                raise GatewayError("invalid_model")
            settings = self._load_provider_settings()
            profile = self._saved_provider(settings, provider_id)
            if profile.protocol is not ProviderProtocol.OPENAI_COMPATIBLE:
                raise GatewayError("transcription_unsupported")
            try:
                config = self._settings_store().resolve_config(provider_id)
            except KeyError:
                raise GatewayError("unknown_provider") from None
            except (OSError, ProviderSettingsError, ValueError):
                raise GatewayError("provider_unconfigured") from None
        try:
            audio, filename, media_type = decode_recording(
                command.payload.get("mediaType"), command.payload.get("data")
            )
        except ValueError:
            raise GatewayError("invalid_recording") from None
        try:
            text = self._audio_transcriber(config, model.strip(), audio, filename, media_type)
        except Exception:
            raise GatewayError("transcription_failed") from None
        with self._lock:
            return self._reply(
                "audio.transcribe.result",
                {"epoch": self.epoch, "text": text},
                session_id=None,
            )

    def _load_provider_settings(self) -> ProviderSettings:
        try:
            return self._settings_store().load()
        except (OSError, ProviderSettingsError, ValueError):
            raise GatewayError("provider_settings_unavailable") from None

    def _settings_store(self) -> ProviderSettingsStore:
        store = self._provider_settings_store
        if store is None:
            store = default_provider_settings_store()
            self._provider_settings_store = store
        return store

    @staticmethod
    def _saved_provider(settings: ProviderSettings, provider_id: str) -> ProviderProfile:
        try:
            return settings.profiles[provider_id]
        except KeyError:
            raise GatewayError("unknown_provider") from None

    def _provider_document(
        self,
        profile: ProviderProfile,
        settings: ProviderSettings,
        *,
        has_credential: bool | None = None,
    ) -> dict[str, object]:
        if has_credential is None:
            try:
                has_credential = self._settings_store().has_credential(profile)
            except (OSError, ProviderSettingsError, ValueError):
                raise GatewayError("provider_settings_unavailable") from None
        return {
            "id": profile.id,
            "name": profile.name,
            "protocol": profile.protocol.value,
            "baseUrl": profile.base_url,
            "model": profile.model,
            "isDefault": profile.id == settings.default_provider_id,
            "hasCredential": has_credential,
            "supportedReasoningEfforts": list(self._supported_turn_reasoning_efforts(profile)),
        }

    @staticmethod
    def _supported_turn_reasoning_efforts(
        provider: ProviderConfig | ProviderProfile,
    ) -> tuple[str, ...]:
        if provider.protocol not in {
            ProviderProtocol.OPENAI_COMPATIBLE,
            ProviderProtocol.ANTHROPIC,
        }:
            return ()
        native = supported_reasoning_efforts(
            provider.protocol.value, provider.base_url, provider.model
        )
        supported = {"none", "low", "medium", "high", "xhigh", "max"}
        return tuple(
            "off" if effort == "none" else effort for effort in native if effort in supported
        )

    @staticmethod
    def _provider_id(value: object) -> str:
        if not isinstance(value, str):
            raise GatewayError("invalid_provider")
        try:
            credential_target(value, "https://validation.invalid")
        except ValueError:
            raise GatewayError("invalid_provider") from None
        return value

    @staticmethod
    def _provider_text(value: object, *, max_chars: int, allow_empty: bool) -> str:
        if not isinstance(value, str) or len(value) > max_chars:
            raise GatewayError("invalid_provider")
        normalized = value.strip()
        if not allow_empty and not normalized:
            raise GatewayError("invalid_provider")
        try:
            normalized.encode("utf-8")
        except UnicodeEncodeError:
            raise GatewayError("invalid_provider") from None
        return normalized

    def _open_workspace(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"path"})
        if self._git_delivery_in_progress:
            raise GatewayError("runtime_busy")
        raw_path = command.payload.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise GatewayError("invalid_workspace")
        try:
            workspace = Path(raw_path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            raise GatewayError("invalid_workspace") from None
        if not workspace.is_dir():
            raise GatewayError("invalid_workspace")
        try:
            resolver = self._provider_resolver
            provider = (
                resolver() if resolver is not None else self._settings_store().resolve_config()
            )
            provider.validate()
        except (KeyError, OSError, ProviderSettingsError, ValueError):
            raise GatewayError("runtime_unconfigured") from None

        if (
            self._workspace == workspace
            and self._host is not None
            and self._runtime_state == "ready"
            and self._workspace_switch_thread is None
        ):
            return self._reply(
                "workspace.open.result",
                {
                    "epoch": self.epoch,
                    "ready": True,
                    "switching": False,
                    "workspace": {"path": str(workspace), "name": workspace.name},
                },
                session_id=None,
            )

        if not self._async_workspace_switch:
            # Preserve the synchronous contract for injected host factories;
            # production uses the background path below.
            self._replace_host(
                workspace=workspace,
                provider=provider,
                session_id=None,
                mode=Mode.CODING,
                deadline=self._clock() + _LIFECYCLE_TIMEOUT_SECONDS,
            )
            self._touch_workspace_catalog(workspace)
            return self._reply(
                "workspace.open.result",
                {
                    "epoch": self.epoch,
                    "ready": self._runtime_state == "ready",
                    "switching": False,
                    "workspace": {"path": str(workspace), "name": workspace.name},
                },
                session_id=None,
            )

        # Queue the replacement and return immediately. The lifecycle worker
        # serializes stop/start and keeps only the newest target, just like
        # session activation. This keeps the command lane responsive while a
        # fresh RuntimeHost initializes its database/provider/tool registry.
        self._pending_workspace_activation = (workspace, provider)
        self._workspace_activation_target = (workspace, provider)
        self._workspace_switch_generation += 1
        generation = self._workspace_switch_generation
        self._runtime_state = "switching"
        current = self._workspace_switch_thread
        if current is None or not current.is_alive():
            worker = threading.Thread(
                target=self._activate_workspace_in_background,
                args=(generation,),
                name="workspace-switch",
                daemon=True,
            )
            self._workspace_switch_thread = worker
            worker.start()
        return self._reply(
            "workspace.open.result",
            {
                "epoch": self.epoch,
                "ready": False,
                "switching": True,
                "workspace": {"path": str(workspace), "name": workspace.name},
            },
            session_id=None,
        )

    def _activate_workspace_in_background(self, generation: int) -> None:
        """Replace the runtime host for the latest requested workspace."""
        current_generation = generation
        try:
            while True:
                with self._lock:
                    if self._closing:
                        return
                    # A newer request supersedes the generation captured when
                    # the worker was created. It is still safe for this worker
                    # to continue; it will consume the newest pending target.
                    current_generation = self._workspace_switch_generation
                    target = self._pending_workspace_activation
                    self._pending_workspace_activation = None
                    if target is None:
                        self._workspace_activation_target = None
                        self._runtime_state = "ready" if self._host is not None else "failed"
                        return
                    workspace, provider = target

                try:
                    with self._lifecycle_lock:
                        self._replace_host_unlocked(
                            workspace=workspace,
                            provider=provider,
                            session_id=None,
                            mode=Mode.CODING,
                            deadline=self._clock() + _LIFECYCLE_TIMEOUT_SECONDS,
                        )
                except GatewayError as error:
                    with self._lock:
                        # If another target arrived while this replacement was
                        # running, retry it instead of surfacing a stale error.
                        if current_generation != self._workspace_switch_generation:
                            continue
                        self._runtime_state = "ready" if self._host is not None else "failed"
                        if self._workspace_activation_target == target:
                            self._workspace_activation_target = None
                        self._pending_host_events.append(
                            Event(
                                session_id="desktop",
                                type="runtime.workspace_switch_failed",
                                data={
                                    "generation": current_generation,
                                    "path": str(workspace),
                                    "reason": str(error),
                                    "restored": self._host is not None,
                                },
                            )
                        )
                    return

                activate_pending_session = False
                with self._lock:
                    if current_generation != self._workspace_switch_generation:
                        # A newer request won the race. Keep the current host
                        # isolated and immediately replace it with that target.
                        continue
                    self._touch_workspace_catalog(workspace)
                    self._runtime_state = "ready" if self._host is not None else "failed"
                    if self._workspace_activation_target == target:
                        self._workspace_activation_target = None
                    activate_pending_session = (
                        self._pending_session_activation_id is not None
                        and self._runtime_state == "ready"
                    )
                if activate_pending_session:
                    # A session can be created while the workspace host is
                    # starting.  Activate that durable session only after the
                    # workspace replacement has installed its host.
                    self._activate_pending_session_if_idle()
                return
        finally:
            with self._lock:
                if self._workspace_switch_thread is threading.current_thread():
                    self._workspace_switch_thread = None
                    if self._pending_workspace_activation is not None:
                        # A request can arrive in the tiny window between the
                        # final check and cleanup. Start a successor worker so
                        # that request cannot be stranded.
                        target = self._pending_workspace_activation
                        self._pending_workspace_activation = None
                        self._workspace_switch_generation += 1
                        successor = threading.Thread(
                            target=self._activate_workspace_in_background,
                            args=(self._workspace_switch_generation,),
                            name="workspace-switch",
                            daemon=True,
                        )
                        self._workspace_switch_thread = successor
                        self._pending_workspace_activation = target
                        successor.start()

    def _list_sessions(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, set(), optional={"limit"})
        limit = command.payload.get("limit", 50)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= _MAX_SESSIONS:
            raise GatewayError("invalid_limit")
        return self._reply(
            "session.list.result",
            {"epoch": self.epoch, "sessions": self._sessions(limit)},
        )

    def _list_workspace_sessions(self, command: CommandEnvelope) -> GatewayReply:
        """Read registered folder conversations without replacing any runtime.

        The catalog and database belong to this gateway profile. This is an
        explicit directory operation; session.list/open retain their selected
        workspace boundary and no conversation history enters this response.
        """
        self._require_payload(
            command, set(), optional={"path", "limit", "offset", "workspaceOffset"}
        )
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        limit = command.payload.get("limit", 20)
        offset = command.payload.get("offset", 0)
        workspace_offset = command.payload.get("workspaceOffset", 0)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise GatewayError("invalid_limit")
        for value in (offset, workspace_offset):
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100_000:
                raise GatewayError("invalid_offset")
        offset = cast(int, offset)
        workspace_offset = cast(int, workspace_offset)
        requested_path = command.payload.get("path")
        if requested_path is None and (offset != 0 or limit > 25):
            raise GatewayError("invalid_payload")

        catalog = self._workspace_catalog
        entries = [] if catalog is None else list(catalog.entries())
        registered: dict[str, dict[str, object]] = {}
        for entry in entries:
            path = Path(entry.path)
            if not path.is_dir():
                continue
            registered[str(path.resolve())] = {
                "path": str(path.resolve()),
                "name": _bounded_text(entry.name, 128),
                "lastUsed": entry.last_used,
            }
        if self._workspace is not None:
            current_path = str(self._workspace)
            registered.setdefault(
                current_path, {"path": current_path, "name": self._workspace.name, "lastUsed": 0}
            )
        documents = list(registered.values())
        if requested_path is not None:
            if not isinstance(requested_path, str) or not requested_path.strip():
                raise GatewayError("invalid_workspace")
            try:
                path_key = str(Path(requested_path).expanduser().resolve())
            except (OSError, RuntimeError):
                raise GatewayError("invalid_workspace") from None
            if path_key not in registered:
                raise GatewayError("unknown_workspace")
            documents = [registered[path_key]]
            next_workspace_offset: int | None = None
        else:
            # 32 folder summaries plus at most 25 compact conversations each
            # stay within the bounded IPC frame; remaining folders are paged.
            next_workspace_offset = (
                workspace_offset + 32 if len(documents) > workspace_offset + 32 else None
            )
            documents = documents[workspace_offset : workspace_offset + 32]

        groups: list[dict[str, object]] = []
        try:
            for document in documents:
                workspace = Path(cast(str, document["path"]))
                sessions = (
                    SQLiteEventStore.list_sessions_read_only(
                        self._database,
                        limit + 1,
                        workspace=workspace,
                        exclude_run_sessions=True,
                        offset=offset,
                    )
                    if self._database.is_file()
                    else []
                )
                visible = sessions[:limit]
                session_documents = []
                for session in visible:
                    summary = self._session_document(session)
                    summary.pop("workspace", None)  # The enclosing folder owns this path.
                    summary["title"] = _bounded_text(session.title, 256)
                    session_documents.append(summary)
                prefix = hashlib.sha256(str(workspace).encode("utf-8")).hexdigest() + ":"
                presentations = {}
                for session in visible:
                    record = self._session_presentation.get(prefix + session.id)
                    if record is not None:
                        presentations[session.id] = {
                            **record,
                            "alias": _bounded_text(record.get("alias"), 256),
                        }
                groups.append(
                    {
                        **document,
                        "sessions": session_documents,
                        "sessionPresentation": presentations,
                        "offset": offset,
                        "hasMore": len(sessions) > limit,
                        "nextOffset": offset + len(visible) if len(sessions) > limit else None,
                    }
                )
        except (OSError, sqlite3.DatabaseError, ValueError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "workspace.sessions.list.result",
            {
                "epoch": self.epoch,
                "workspaces": groups,
                **({"workspaceOffset": workspace_offset} if requested_path is None else {}),
                "nextWorkspaceOffset": next_workspace_offset,
                "partial": requested_path is not None or workspace_offset > 0,
            },
            session_id=None,
        )

    def _open_session(self, command: CommandEnvelope) -> GatewayReply:
        # Session selection remains available while a previous host is stopping
        # or a replacement host is starting. The activation is serialized by
        # the lifecycle worker and the latest pending target wins.
        self._require_workspace_provider()
        self._require_payload(command, set())
        session_id = command.session_id
        if session_id is None:
            raise GatewayError("invalid_session")
        session = self._stored_session(session_id)
        if session is None:
            raise GatewayError("unknown_session")
        assert self._workspace is not None
        if Path(session.workspace).resolve() != self._workspace:
            raise GatewayError("unknown_session")
        parked = self._session_hosts.get(session.id)
        if (
            parked is not None and parked.host is not None and parked.host.is_alive()
            and not self._session_switch_in_progress and self._workspace_switch_thread is None
        ):
            assert self._provider is not None
            self._replace_host(
                workspace=self._workspace,
                provider=self._provider,
                session_id=session.id,
                mode=session.mode,
                autonomy=session.autonomy,
                deadline=self._clock() + _LIFECYCLE_TIMEOUT_SECONDS,
            )
            self._pending_session_activation_id = None
        if (
            session.id == self._host_session_id
            and self._host is not None
            and self._runtime_state == "ready"
        ):
            self._selected_session_id = session.id
            self._pending_session_activation_id = None
            page = self._history_page(session.id)
            self._acknowledge_history_page(session.id, page)
            return self._reply(
                "session.open.result",
                {
                    "epoch": self.epoch,
                    "session": self._session_document(session),
                    "timeline": page["timeline"],
                    "history": page["history"],
                    "activated": True,
                    "hostSessionId": self._host_session_id,
                },
                session_id=session.id,
            )

        # A busy sessionless host cannot be parked; wait for its turn to settle.
        sessionless_busy = (
            self._host is not None
            and self._host_session_id is None
            and (self._busy or bool(self._queued_turns))
        )
        lifecycle_pending = (
            self._session_switch_in_progress
            or self._runtime_state != "ready"
            or self._host is None
            or sessionless_busy
        )
        if lifecycle_pending:
            self._selected_session_id = session.id
            self._pending_session_activation_id = session.id
            self._pending_host_events.append(
                Event(
                    session_id=session.id,
                    type="session.opened",
                    data={"session_id": session.id, "activated": False},
                )
            )
            page = self._history_page(session.id)
            self._acknowledge_history_page(session.id, page)
            if self._workspace_switch_thread is None and not sessionless_busy:
                self._schedule_session_activation(session)
            return self._reply(
                "session.open.result",
                {
                    "epoch": self.epoch,
                    "session": self._session_document(session),
                    "timeline": page["timeline"],
                    "history": page["history"],
                    "activated": False,
                    "hostSessionId": self._host_session_id,
                    "switching": self._session_switch_in_progress or self._runtime_state != "ready",
                },
                session_id=session.id,
            )

        assert self._provider is not None
        if isinstance(self._host, RuntimeHost) or self._async_workspace_switch:
            self._selected_session_id = session.id
            self._pending_session_activation_id = session.id
            page = self._history_page(session.id)
            self._acknowledge_history_page(session.id, page)
            self._schedule_session_activation(session)
            return self._reply(
                "session.open.result",
                {
                    "epoch": self.epoch,
                    "session": self._session_document(session),
                    "timeline": page["timeline"],
                    "history": page["history"],
                    "activated": False,
                    "hostSessionId": self._host_session_id,
                    "switching": True,
                },
                session_id=session.id,
            )
        deadline = self._clock() + _LIFECYCLE_TIMEOUT_SECONDS
        self._pending_session_activation_id = None
        self._replace_host(
            workspace=self._workspace,
            provider=self._provider,
            session_id=session.id,
            mode=session.mode,
            autonomy=session.autonomy,
            deadline=deadline,
        )
        self._pending_host_events.append(
            Event(session_id=session.id, type="session.opened", data={"session_id": session.id})
        )
        page = self._history_page(session.id)
        self._acknowledge_history_page(session.id, page)
        return self._reply(
            "session.open.result",
            {
                "epoch": self.epoch,
                "session": self._session_document(session),
                "timeline": page["timeline"],
                "history": page["history"],
                "activated": True,
                "hostSessionId": self._host_session_id,
            },
            session_id=session.id,
        )

    def _session_history(self, command: CommandEnvelope) -> GatewayReply:
        with self._lock:
            self._require_configured()
            self._require_payload(command, {"cursor"})
            if command.session_id is None or command.session_id != self._selected_session_id:
                raise GatewayError("invalid_session")
            cursor = command.payload.get("cursor")
            if not isinstance(cursor, str):
                raise GatewayError("invalid_cursor")
            session_id = command.session_id
            cutoff, before = self._decode_cursor(cursor, session_id)

        # SQLite history reconstruction can be materially slower than command
        # dispatch on large sessions. Keep it outside the lifecycle lock so
        # terminal events, cancellation, and approvals continue to flow.
        page = self._history_page(session_id, cutoff=cutoff, before=before)
        page["epoch"] = self.epoch
        with self._lock:
            return self._reply("session.history.result", page, session_id=session_id)

    def _events_replay(self, command: CommandEnvelope) -> GatewayReply:
        """Return durable domain events for reconnecting clients.

        Wire events are intentionally process-local and receive a new sequence
        after every sidecar start.  The domain sequence and event id are the
        stable replay cursor, so a client can recover after an epoch change
        without asking the runtime to re-execute any work.
        """

        self._require_payload(command, {"afterSequence"}, optional={"limit", "epoch"})
        session_id = command.session_id
        if session_id is None:
            raise GatewayError("invalid_session")
        with self._lock:
            if self._selected_session_id != session_id:
                raise GatewayError("invalid_session")
        raw_after = command.payload.get("afterSequence")
        if type(raw_after) is not int or raw_after < 0:
            raise GatewayError("invalid_cursor")
        raw_limit = command.payload.get("limit", 100)
        if type(raw_limit) is not int or not 1 <= raw_limit <= 1000:
            raise GatewayError("invalid_limit")
        previous_epoch = command.payload.get("epoch")
        if previous_epoch is not None and (
            not isinstance(previous_epoch, str) or not previous_epoch
        ):
            raise GatewayError("invalid_epoch")
        try:
            with SQLiteEventStore(self._database) as store:
                if store.get_session(session_id) is None:
                    raise GatewayError("invalid_session")
                events, oldest, newest, has_more = store.replay_events(
                    session_id,
                    after_sequence=raw_after,
                    limit=raw_limit,
                )
        except GatewayError:
            raise
        except (OSError, sqlite3.DatabaseError, ValueError):
            raise GatewayError("replay_unavailable") from None
        next_sequence = (
            events[-1].sequence if events and events[-1].sequence is not None else raw_after
        )
        payload: dict[str, object] = {
            "epoch": self.epoch,
            "epochChanged": previous_epoch is not None and previous_epoch != self.epoch,
            "events": [self._timeline_event(event) for event in events],
            "afterSequence": raw_after,
            "nextSequence": next_sequence,
            "oldestSequence": oldest,
            "newestSequence": newest,
            "hasMore": has_more,
            "watermark": newest,
        }
        return self._reply("events.replay.result", payload, session_id=session_id)

    def _create_session(self, command: CommandEnvelope) -> GatewayReply:
        # ``workspace.open`` is intentionally asynchronous for the production
        # RuntimeHost.  A UI commonly sends ``session.create`` immediately
        # after that response, while the replacement host is still starting.
        # Accept the request against the queued target and persist it; the
        # workspace switch worker activates the session once its host is ready.
        pending_workspace = self._pending_workspace_activation or self._workspace_activation_target
        if pending_workspace is None:
            self._require_workspace_provider()
            assert self._workspace is not None and self._provider is not None
            session_workspace = self._workspace
        else:
            session_workspace = pending_workspace[0]
        self._require_payload(command, set(), optional={"title", "mode"})
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        raw_title = command.payload.get("title", "New session")
        if not isinstance(raw_title, str):
            raise GatewayError("invalid_title")
        title = raw_title.strip()
        if not title or len(title) > 200:
            raise GatewayError("invalid_title")
        raw_mode = command.payload.get("mode", self._mode.value)
        try:
            mode = Mode(cast(str, raw_mode))
        except (TypeError, ValueError):
            raise GatewayError("invalid_mode") from None
        session = Session(
            workspace=str(session_workspace),
            mode=mode,
            autonomy=self._autonomy,
            title=title,
        )
        # Session hosts are parked by session id, so a busy sessionless host
        # cannot be parked; switching now would cancel its turn. Its terminal
        # turn event activates the new session instead.
        sessionless_busy = (
            self._host is not None
            and self._host_session_id is None
            and (self._busy or bool(self._queued_turns))
        )
        if (
            self._session_switch_in_progress
            or self._runtime_state != "ready"
            or self._host is None
            or sessionless_busy
        ):
            try:
                with SQLiteEventStore(self._database) as store:
                    store.create_session(session)
            except (OSError, sqlite3.DatabaseError, ValueError):
                raise GatewayError("storage_unavailable") from None
            self._selected_session_id = session.id
            self._pending_session_activation_id = session.id
            self._pending_host_events.append(
                Event(
                    session_id=session.id,
                    type="session.created",
                    data={
                        "session_id": session.id,
                        "title": session.title,
                        "mode": session.mode.value,
                        "autonomy": session.autonomy.value,
                        "activated": False,
                    },
                )
            )
            if self._workspace_switch_thread is None and not sessionless_busy:
                self._schedule_session_activation(session)
            return self._reply(
                "session.create.result",
                {
                    "epoch": self.epoch,
                    "session": self._session_document(session),
                    "activated": False,
                    "hostSessionId": self._host_session_id,
                },
                session_id=None,
            )
        deadline = self._clock() + _LIFECYCLE_TIMEOUT_SECONDS
        previous_workspace = self._workspace
        previous_provider = self._provider
        previous_session_id = self._selected_session_id
        previous_mode = self._mode
        self._stop_host_for_lifecycle(deadline=deadline, preserve_session=True)
        try:
            with SQLiteEventStore(self._database) as store:
                store.create_session(session)
        except (OSError, sqlite3.DatabaseError, ValueError):
            self._restore_host_state(
                previous_workspace,
                previous_provider,
                previous_session_id,
                previous_mode,
            )
            raise GatewayError("storage_unavailable") from None
        self._workspace = previous_workspace
        self._provider = previous_provider
        self._mode = mode
        self._selected_session_id = session.id
        try:
            self._start_host(session_id=session.id, deadline=deadline)
            self._restore_queued_turns(session.id)
        except GatewayError:
            if self._host is not None:
                try:
                    self._stop_host()
                except GatewayError:
                    raise GatewayError("runtime_start_failed") from None
            rollback_failed = False
            try:
                with SQLiteEventStore(self._database) as store:
                    rollback_failed = not store.delete_session_if_empty(session.id)
            except (OSError, sqlite3.DatabaseError, ValueError):
                rollback_failed = True
            self._restore_host_state(
                previous_workspace,
                previous_provider,
                previous_session_id,
                previous_mode,
            )
            if rollback_failed:
                raise GatewayError("storage_unavailable") from None
            raise GatewayError("runtime_start_failed") from None
        self._pending_host_events.append(
            Event(
                session_id=session.id,
                type="session.created",
                data={
                    "session_id": session.id,
                    "title": session.title,
                    "mode": session.mode.value,
                    "autonomy": session.autonomy.value,
                },
            )
        )
        return self._reply(
            "session.create.result",
            {
                "epoch": self.epoch,
                "session": self._session_document(session),
                "activated": True,
                "hostSessionId": self._host_session_id,
            },
            session_id=None,
        )

    def _set_session_presentation(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(
            command,
            {"sessionId"},
            optional={"alias", "pinned", "archived"},
        )
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        session_id = command.payload.get("sessionId")
        if not isinstance(session_id, str) or not session_id:
            raise GatewayError("invalid_session")
        session = self._stored_session(session_id)
        assert self._workspace is not None
        if session is None or Path(session.workspace).resolve() != self._workspace:
            raise GatewayError("unknown_session")
        key = self._presentation_key(session_id)
        previous = self._session_presentation.get(
            key,
            {
                "sessionId": session_id,
                "alias": None,
                "pinned": False,
                "archived": False,
                "version": 1,
            },
        )
        alias = command.payload.get("alias", previous["alias"])
        if alias is not None:
            if not isinstance(alias, str):
                raise GatewayError("invalid_presentation")
            alias = alias.strip()
            if not alias or len(alias) > 200:
                raise GatewayError("invalid_presentation")
        pinned = command.payload.get("pinned", previous["pinned"])
        archived = command.payload.get("archived", previous["archived"])
        if type(pinned) is not bool or type(archived) is not bool:
            raise GatewayError("invalid_presentation")
        record: dict[str, object] = {
            "sessionId": session_id,
            "alias": alias,
            "pinned": pinned,
            "archived": archived,
            "version": 1,
        }
        self._session_presentation[key] = record
        self._persist_session_presentation()
        self._pending_host_events.append(
            Event(session_id=session_id, type="session.presentation.changed", data=record)
        )
        return self._reply(
            "session.presentation.set.result",
            {"epoch": self.epoch, "presentation": record},
            session_id=None,
        )

    def _workspace_session(self, session_id: object) -> Session:
        if not isinstance(session_id, str) or not session_id:
            raise GatewayError("invalid_session")
        session = self._stored_session(session_id)
        with self._lock:
            workspace = self._workspace
        if workspace is None:
            raise GatewayError("runtime_unconfigured")
        if session is None or Path(session.workspace).resolve() != workspace:
            raise GatewayError("unknown_session")
        return session

    def _export_session(self, command: CommandEnvelope) -> GatewayReply:
        """Write one session as a verified archive to a path the user chose."""
        self._require_payload(command, {"sessionId", "path"})
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        session = self._workspace_session(command.payload.get("sessionId"))
        destination = _archive_path(command.payload.get("path"))
        if not destination.parent.is_dir():
            raise GatewayError("invalid_path")
        # The save dialog already confirmed replacing an existing file; the
        # archive is staged beside it so a failed export leaves it untouched.
        staging = destination.with_name(f".{destination.stem}.{uuid4().hex}.export.zip")
        try:
            export_session(self._database, session.id, staging)
            os.replace(staging, destination)
        except SessionExportError:
            raise GatewayError("session_export_blocked") from None
        except (OSError, KeyError, ValueError, sqlite3.DatabaseError, BackupValidationError):
            raise GatewayError("storage_unavailable") from None
        finally:
            staging.unlink(missing_ok=True)
        return self._reply(
            "session.export.result",
            {"epoch": self.epoch, "sessionId": session.id, "path": str(destination)},
            session_id=None,
        )

    def _import_session(self, command: CommandEnvelope) -> GatewayReply:
        """Import a session archive into the open workspace as a new session."""
        self._require_payload(command, {"path"})
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        archive = _archive_path(command.payload.get("path"))
        if not archive.is_file():
            raise GatewayError("invalid_path")
        with self._lock:
            workspace = self._workspace
        if workspace is None:
            raise GatewayError("runtime_unconfigured")
        try:
            with SQLiteEventStore(self._database) as store:
                session = import_session_archive(store, archive, workspace)
        except BackupValidationError:
            raise GatewayError("invalid_session_archive") from None
        except (OSError, KeyError, ValueError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        with self._lock:
            self._pending_host_events.append(
                Event(
                    session_id=session.id,
                    type="session.created",
                    data={
                        "session_id": session.id,
                        "title": session.title,
                        "mode": session.mode.value,
                        "autonomy": session.autonomy.value,
                        "activated": False,
                    },
                )
            )
            document = self._session_document(session)
        return self._reply(
            "session.import.result",
            {"epoch": self.epoch, "session": document},
            session_id=None,
        )

    def _session_usage(self, command: CommandEnvelope) -> GatewayReply:
        """Summarize recorded token usage and its estimated price for a session."""
        self._require_payload(command, {"sessionId"})
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        session = self._workspace_session(command.payload.get("sessionId"))
        try:
            events = SQLiteEventStore.list_session_events_of_types_read_only(
                self._database, session.id, frozenset({"model.requested", "usage.updated"})
            )
        except (OSError, ValueError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        cost = session_cost(events)
        priced = any(resolve_pricing(model) is not UNKNOWN_PRICING for model in cost.models)
        return self._reply(
            "session.usage.result",
            {
                "epoch": self.epoch,
                "sessionId": session.id,
                "modelCalls": cost.model_calls,
                "inputTokens": cost.input_tokens,
                "outputTokens": cost.output_tokens,
                "cachedTokens": cost.cached_tokens,
                "estimated": cost.estimated,
                "costUsd": round(cost.cost_usd, 6),
                # Unpriced models count as free; the UI must not present $0 as a price.
                "priced": priced,
                "models": list(cost.models)[:16],
            },
            session_id=None,
        )

    def _memory_scope(self) -> tuple[str, str | None]:
        """Return the workspace key memories use and a session to attribute edits to."""
        with self._lock:
            workspace = self._workspace
            selected = self._selected_session_id
        if workspace is None:
            raise GatewayError("runtime_unconfigured")
        if selected:
            session = self._stored_session(selected)
            if session is not None and Path(session.workspace).resolve() == workspace:
                return session.workspace, session.id
        if not self._database.is_file():
            return str(workspace), None
        try:
            sessions = SQLiteEventStore.list_sessions_read_only(
                self._database, 1, workspace=workspace, exclude_run_sessions=True
            )
        except (OSError, ValueError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        if sessions:
            return sessions[0].workspace, sessions[0].id
        return str(workspace), None

    @staticmethod
    def _memory_document(memory: MemoryItem) -> dict[str, object]:
        return {
            "id": memory.id,
            "content": memory.content,
            "tags": list(memory.tags),
            "sourceSessionId": memory.source_session_id,
            "createdAt": memory.created_at,
            "updatedAt": memory.updated_at,
            "expiresAt": memory.expires_at,
        }

    def _list_memories(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"query", "limit"})
        query = command.payload.get("query", "")
        limit = command.payload.get("limit", 200)
        if not isinstance(query, str) or len(query) > 500:
            raise GatewayError("invalid_query")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise GatewayError("invalid_limit")
        workspace, _session_id = self._memory_scope()
        try:
            memories = (
                SQLiteEventStore.list_memories_read_only(
                    self._database, workspace, query=query.strip(), limit=limit
                )
                if self._database.is_file()
                else []
            )
        except (OSError, ValueError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "memory.list.result",
            {
                "epoch": self.epoch,
                "memories": [self._memory_document(memory) for memory in memories],
                "truncated": len(memories) >= limit,
            },
            session_id=None,
        )

    def _write_memory(self, command: CommandEnvelope) -> GatewayReply:
        """Edit or delete one memory through the same events the memory tool appends."""
        deleting = command.type == "memory.delete"
        if deleting:
            self._require_payload(command, {"memoryId"})
        else:
            self._require_payload(command, {"memoryId", "content"}, optional={"tags"})
        memory_id = command.payload.get("memoryId")
        if not isinstance(memory_id, str) or not memory_id or len(memory_id) > 128:
            raise GatewayError("invalid_memory")
        workspace, session_id = self._memory_scope()
        if session_id is None:
            raise GatewayError("session_required")
        data: dict[str, object] = {"memory_id": memory_id, "workspace": workspace}
        try:
            with SQLiteEventStore(self._database) as store:
                existing = store.get_memory(workspace, memory_id)
                if existing is None:
                    raise GatewayError("unknown_memory")
                if not deleting:
                    content = command.payload.get("content")
                    tags = command.payload.get("tags", list(existing.tags))
                    if not isinstance(content, str) or not content.strip() or len(content) > 10_000:
                        raise GatewayError("invalid_memory")
                    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
                        raise GatewayError("invalid_memory")
                    cleaned: list[str] = []
                    for tag in (tag.strip() for tag in tags):
                        if tag and tag.casefold() not in {item.casefold() for item in cleaned}:
                            cleaned.append(tag[:64])
                    if len(cleaned) > 16:
                        raise GatewayError("invalid_memory")
                    data["content"] = content.strip()
                    data["tags"] = cleaned
                    data["expires_at"] = existing.expires_at
                event_type = "memory.deleted" if deleting else "memory.upserted"
                validate_event_payload(event_type, data)
                store.append(Event(session_id=session_id, type=event_type, data=data))
                updated = None if deleting else store.get_memory(workspace, memory_id)
        except GatewayError:
            raise
        except ValueError:
            raise GatewayError("invalid_memory") from None
        except (OSError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            f"{command.type}.result",
            {
                "epoch": self.epoch,
                "memoryId": memory_id,
                "deleted": deleting,
                "memory": self._memory_document(updated) if updated is not None else None,
            },
            session_id=None,
        )

    def _inspect_agent_setup(self, command: CommandEnvelope) -> GatewayReply:
        """Report the instruction, skill, MCP and custom-tool files the agent loads.

        Editing goes through the ordinary workspace file commands; this read-only
        view shows what parses and why a file is rejected.
        """
        self._require_payload(command, set())
        with self._lock:
            workspace = self._workspace
        if workspace is None:
            raise GatewayError("runtime_unconfigured")
        paths = WorkspacePaths(workspace)

        def file_fact(relative: str) -> dict[str, object]:
            try:
                target = paths.resolve(relative)
                exists = target.is_file()
                size = target.stat().st_size if exists else 0
            except (OSError, ValueError, ToolError):
                exists, size = False, 0
            return {"path": relative, "exists": exists, "bytes": size}

        instructions = [file_fact(name) for name in INSTRUCTION_FILENAMES]
        skills: list[dict[str, object]] = []
        skill_error: str | None = None
        try:
            for skill in load_skills(workspace):
                skills.append(
                    {
                        "id": skill.id,
                        "name": skill.name,
                        "description": skill.description[:500],
                        "path": paths.relative(Path(skill.path)),
                    }
                )
        except SkillError as exc:
            skill_error = _workspace_error_text(exc, workspace)
        skill_files = [paths.relative(path) for path in discover_skill_files(workspace)]
        servers: list[dict[str, object]] = []
        mcp_error: str | None = None
        try:
            for server in load_mcp_servers(workspace):
                servers.append({"id": server.id, "command": list(server.command)[:32]})
        except McpHostError as exc:
            mcp_error = _workspace_error_text(exc, workspace)
        custom_tools: list[dict[str, object]] = []
        custom_error: str | None = None
        try:
            for definition in load_custom_tool_definitions(workspace):
                custom_tools.append(
                    {
                        "name": definition.name,
                        "description": definition.description[:500],
                        "path": paths.relative(Path(definition.path)),
                    }
                )
        except CustomToolError as exc:
            custom_error = _workspace_error_text(exc, workspace)
        return self._reply(
            "workspace.agent.inspect.result",
            {
                "epoch": self.epoch,
                "instructions": instructions,
                "skills": skills,
                "skillFiles": skill_files[:200],
                "skillError": skill_error,
                "mcp": {**file_fact(".agent/mcp.toml"), "servers": servers, "error": mcp_error},
                "customTools": custom_tools,
                "customToolError": custom_error,
            },
            session_id=None,
        )

    def _search_sessions(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"query"}, optional={"limit"})
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        raw_query = command.payload.get("query")
        limit = command.payload.get("limit", 20)
        if not isinstance(raw_query, str):
            raise GatewayError("invalid_query")
        query = raw_query.strip()
        if not query or len(query) > 256 or len(query.split()) > 16:
            raise GatewayError("invalid_query")
        if type(limit) is not int or not 1 <= limit <= _MAX_SEARCH_RESULTS:
            raise GatewayError("invalid_limit")
        assert self._workspace is not None
        try:
            results = SQLiteEventStore.search_sessions_read_only(
                self._database, query, limit, workspace=self._workspace, exclude_run_sessions=True
            )
        except SearchIndexUnavailableError:
            index_state = "unavailable"
            results = []
        except (OSError, ValueError):
            raise GatewayError("storage_unavailable") from None
        else:
            index_state = "ready"
        documents = [
            {
                "id": result.session.id,
                "title": result.session.title[:200],
                "mode": result.session.mode.value,
                "updatedAt": result.session.updated_at,
                "snippet": result.snippet[:2_000],
                "documentKind": result.document_kind,
            }
            for result in results
        ]
        return self._reply(
            "session.search.result",
            {
                "epoch": self.epoch,
                "query": query,
                "indexState": index_state,
                "results": documents,
            },
            session_id=None,
        )

    def _workspace_summary(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured(allow_awaiting_approval=True)
        self._require_payload(command, set())
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        assert self._workspace is not None
        provider = self._provider
        try:
            sessions = (
                SQLiteEventStore.list_sessions_read_only(
                    self._database,
                    _MAX_COLLECTION_ITEMS,
                    workspace=self._workspace,
                    exclude_run_sessions=True,
                )
                if self._database.is_file()
                else []
            )
        except (OSError, sqlite3.DatabaseError, ValueError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "workspace.summary.get.result",
            {
                "epoch": self.epoch,
                "name": self._workspace.name,
                "path": str(self._workspace),
                "sessionCount": len(sessions),
                "provider": (
                    None if provider is None else {"id": provider.id, "model": provider.model}
                ),
                "runtime": {
                    "state": self._runtime_state,
                    "mode": self._mode.value,
                    "activeTurn": self._active_turn,
                },
                "capabilities": sorted(
                    capability.value for capability in capabilities_for_mode(self._mode)
                ),
            },
            session_id=None,
        )

    @staticmethod
    def _research_page_bounds(command: CommandEnvelope, *, max_limit: int) -> tuple[int, int]:
        offset = command.payload.get("offset", 0)
        limit = command.payload.get("limit", 20)
        if type(offset) is not int or not 0 <= offset <= 100_000:
            raise GatewayError("invalid_offset")
        if type(limit) is not int or not 1 <= limit <= max_limit:
            raise GatewayError("invalid_limit")
        return offset, limit

    def _list_research_sources(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"offset", "limit"})
        self._require_selected_session(command.session_id)
        assert command.session_id is not None
        offset, limit = self._research_page_bounds(command, max_limit=50)
        try:
            with SQLiteEventStore(self._database) as store:
                all_sources = store.list_research_sources(command.session_id)
        except (OSError, sqlite3.DatabaseError, ValueError):
            raise GatewayError("storage_unavailable") from None
        page = all_sources[offset : offset + limit]
        next_offset = offset + len(page) if len(all_sources) > offset + limit else None
        return self._reply(
            "research.sources.list.result",
            {
                "epoch": self.epoch,
                "sources": [
                    {
                        "id": source.id,
                        "url": source.url,
                        "title": source.title,
                        "summary": source.summary[:2_000],
                        "mediaType": source.media_type,
                        "fetchedAt": source.fetched_at,
                        "truncated": source.truncated,
                        "artifactSha256": source.artifact_sha256,
                        "artifactBytes": source.artifact_bytes,
                    }
                    for source in page
                ],
                "truncated": next_offset is not None,
                "nextOffset": next_offset,
            },
            session_id=command.session_id,
        )

    def _read_research_source(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"sourceId"}, optional={"offset", "maxChars"})
        self._require_selected_session(command.session_id)
        assert command.session_id is not None
        source_id = command.payload.get("sourceId")
        if not isinstance(source_id, str) or re.fullmatch(r"[0-9a-fA-F]{64}", source_id) is None:
            raise GatewayError("invalid_source_id")
        offset = command.payload.get("offset", 0)
        maximum = command.payload.get("maxChars", 16_000)
        if type(offset) is not int or not 0 <= offset <= 131_072:
            raise GatewayError("invalid_offset")
        if type(maximum) is not int or not 1 <= maximum <= 32_768:
            raise GatewayError("invalid_limit")
        try:
            with SQLiteEventStore(self._database) as store:
                source = next(
                    (
                        item
                        for item in store.list_research_sources(command.session_id)
                        if item.id == source_id.lower()
                    ),
                    None,
                )
                if source is None:
                    raise GatewayError("research_source_not_found")
                artifact = store.get_text_artifact(source.artifact_sha256)
                if artifact is None:
                    raise GatewayError("research_source_unavailable")
                content = artifact.content.decode("utf-8")
        except GatewayError:
            raise
        except (OSError, sqlite3.DatabaseError, UnicodeDecodeError, ValueError):
            raise GatewayError("storage_unavailable") from None
        part = content[offset : offset + maximum]
        next_offset = offset + len(part) if offset + len(part) < len(content) else None
        return self._reply(
            "research.source.read.result",
            {
                "epoch": self.epoch,
                "sourceId": source_id.lower(),
                "content": part,
                "offset": offset,
                "totalChars": len(content),
                "truncated": next_offset is not None,
                "nextOffset": next_offset,
            },
            session_id=command.session_id,
        )

    def _list_research_citations(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"offset", "limit"})
        self._require_selected_session(command.session_id)
        assert command.session_id is not None
        offset, limit = self._research_page_bounds(command, max_limit=20)
        try:
            with SQLiteEventStore(self._database) as store:
                all_citations = store.list_citations(command.session_id)
        except (OSError, sqlite3.DatabaseError, ValueError):
            raise GatewayError("storage_unavailable") from None
        page = all_citations[offset : offset + limit]
        next_offset = offset + len(page) if len(all_citations) > offset + limit else None
        return self._reply(
            "research.citations.list.result",
            {
                "epoch": self.epoch,
                "citations": [
                    {
                        "id": citation.id,
                        "sourceId": citation.source_id,
                        "claim": citation.claim,
                        "locator": citation.locator,
                        "quote": citation.quote,
                        "createdAt": citation.created_at,
                    }
                    for citation in page
                ],
                "truncated": next_offset is not None,
                "nextOffset": next_offset,
            },
            session_id=command.session_id,
        )

    def _list_changes(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, set(), optional={"limit"})
        self._require_selected_session(command.session_id)
        limit = command.payload.get("limit", 20)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise GatewayError("invalid_limit")
        assert self._workspace is not None and command.session_id is not None
        try:
            with SQLiteEventStore(self._database) as store:
                events = store.list_sandbox_changeset_events(
                    command.session_id, str(self._workspace), limit=limit + 1
                )
                documents = [
                    self._changeset_summary(store, command.session_id, event)
                    for event in events[:limit]
                ]
        except (OSError, ValueError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "changes.list.result",
            {
                "epoch": self.epoch,
                "changesets": documents,
                "truncated": len(events) > limit,
            },
            session_id=command.session_id,
        )

    def _changeset_summary(
        self, store: SQLiteEventStore, session_id: str, event: Event
    ) -> dict[str, object]:
        assert self._workspace is not None
        changes = event.data.get("changes")
        changeset_id = event.data.get("changeset_id")
        if not isinstance(changes, list) or not isinstance(changeset_id, str):
            raise GatewayError("invalid_change")
        supported: set[str] = set()
        files_summary: list[dict[str, object]] = []
        for change in changes:
            if not isinstance(change, Mapping):
                continue
            path = change.get("path")
            if isinstance(path, str):
                is_supported = change.get("apply_supported") is True
                if is_supported:
                    supported.add(path)
                files_summary.append(
                    {
                        "path": path,
                        "kind": change.get("kind", "modified"),
                        "applySupported": is_supported,
                        "beforeBytes": change.get("before_bytes"),
                        "afterBytes": change.get("after_bytes"),
                    }
                )
        applied = {
            item.data.get("path")
            for item in store.list_sandbox_change_applied_events(
                session_id, str(self._workspace), changeset_id
            )
            if isinstance(item.data.get("path"), str)
        }
        rejected = 0
        for path in supported:
            review = store.get_sandbox_change_review_event(
                session_id, str(self._workspace), changeset_id, path
            )
            if review is not None and review.data.get("decision") == "rejected":
                rejected += 1
        applied_count = len(applied & supported)
        state = (
            "rejected"
            if rejected
            else "review_only"
            if not supported
            else "applied"
            if applied_count == len(supported)
            else "partially_applied"
            if applied_count
            else "pending"
        )
        return {
            "changesetId": changeset_id,
            "createdAt": event.created_at,
            "changeCount": len(changes),
            "supportedCount": len(supported),
            "appliedCount": applied_count,
            "rejectedCount": rejected,
            "state": state,
            "files": files_summary,
        }

    def _inspect_change(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(
            command,
            {"changesetId", "path"},
            optional={"offsetBytes", "maxBytes"},
        )
        self._require_selected_session(command.session_id)
        changeset_id = command.payload.get("changesetId")
        raw_path = command.payload.get("path")
        offset = command.payload.get("offsetBytes", 0)
        max_bytes = command.payload.get("maxBytes", 65_536)
        if not isinstance(changeset_id, str) or re.fullmatch(r"[0-9a-f]{64}", changeset_id) is None:
            raise GatewayError("invalid_change")
        if not isinstance(raw_path, str) or not self._is_canonical_relative_path(raw_path):
            raise GatewayError("invalid_change")
        if type(offset) is not int or offset < 0:
            raise GatewayError("invalid_change")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 1_048_576:
            raise GatewayError("invalid_change")
        assert self._workspace is not None and command.session_id is not None
        try:
            with SQLiteEventStore(self._database) as store:
                event = store.get_sandbox_changeset_event(
                    command.session_id, str(self._workspace), changeset_id
                )
                if event is None:
                    raise GatewayError("unknown_change")
                changes = event.data.get("changes")
                change = (
                    next(
                        (
                            item
                            for item in changes
                            if isinstance(item, Mapping) and item.get("path") == raw_path
                        ),
                        None,
                    )
                    if isinstance(changes, list)
                    else None
                )
                if change is None:
                    raise GatewayError("unknown_change")
                applied = store.get_sandbox_change_applied_event(
                    command.session_id, str(self._workspace), changeset_id, raw_path
                )
                review = store.get_sandbox_change_review_event(
                    command.session_id, str(self._workspace), changeset_id, raw_path
                )
                content: bytes | None = None
                utf8 = False
                artifact_id = change.get("artifact_sha256")
                if isinstance(artifact_id, str):
                    artifact = store.get_binary_artifact(artifact_id)
                    if artifact is None:
                        raise GatewayError("storage_unavailable")
                    content = artifact.content
                    utf8 = change.get("content_kind") == "utf8"
                elif isinstance(change.get("after_text"), str):
                    content = cast(str, change["after_text"]).encode("utf-8")
                    utf8 = True
        except GatewayError:
            raise
        except (OSError, ValueError):
            raise GatewayError("storage_unavailable") from None
        page = None
        if content is not None:
            cap = min(max_bytes, _MAX_CHANGE_PAGE_BYTES)
            raw_page = content[offset : offset + cap]
            encoding = "utf-8" if utf8 else "base64"
            data = (
                raw_page.decode("utf-8", errors="ignore")
                if utf8
                else base64.b64encode(raw_page).decode("ascii")
            )
            page = {
                "encoding": encoding,
                "data": data,
                "offsetBytes": offset,
                "bytes": len(content),
                "truncated": offset + len(raw_page) < len(content),
            }
        payload: dict[str, object] = {
            "epoch": self.epoch,
            "changesetId": changeset_id,
            "path": raw_path,
            "kind": change.get("kind"),
            "beforeType": change.get("before_type"),
            "afterType": change.get("after_type"),
            "beforeBytes": change.get("before_bytes"),
            "afterBytes": change.get("after_bytes"),
            "beforeSha256": change.get("before_sha256"),
            "afterSha256": change.get("after_sha256"),
            "applySupported": change.get("apply_supported") is True,
            "applied": applied is not None,
            "review": review.data.get("decision") if review is not None else None,
            "content": page,
        }
        return self._reply("changes.inspect.result", payload, session_id=command.session_id)

    @staticmethod
    def _is_canonical_relative_path(path: str) -> bool:
        if not path or path != path.strip() or len(path) > 512 or "\\" in path or ":" in path:
            return False
        pure = PurePosixPath(path)
        return (
            not pure.is_absolute()
            and pure.as_posix() == path
            and all(part not in {"", ".", ".."} for part in pure.parts)
        )

    def _list_workspace_files_tree(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, set(), optional={"path", "maxDepth", "limit"})
        assert self._workspace is not None
        root_path = self._workspace
        paths = WorkspacePaths(root_path)
        rel_sub = command.payload.get("path", "")
        if not isinstance(rel_sub, str):
            raise GatewayError("invalid_path")
        max_depth = command.payload.get("maxDepth", 6)
        if type(max_depth) is not int or max_depth < 1:
            max_depth = 6
        raw_limit = command.payload.get("limit", 1000)
        limit = min(raw_limit if type(raw_limit) is int and raw_limit > 0 else 1000, 3000)

        try:
            target_dir = paths.resolve(rel_sub) if rel_sub.strip() else root_path
        except Exception:
            raise GatewayError("invalid_path") from None

        if not target_dir.is_dir():
            raise GatewayError("workspace_not_found")

        ignore_dirs = {
            ".git",
            "node_modules",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "dist",
            "build",
            "out",
            "output",
            ".gemini",
        }

        items: list[dict[str, object]] = []
        target_depth = len(target_dir.parts)
        try:
            for current_root, dirnames, filenames in os.walk(target_dir):
                dirnames[:] = [
                    d for d in dirnames if d not in ignore_dirs and not d.startswith(".")
                ]
                curr_path = Path(current_root)
                curr_depth = len(curr_path.parts) - target_depth
                if curr_depth >= max_depth:
                    dirnames.clear()

                if curr_path != target_dir:
                    rel_dir = paths.relative(curr_path)
                    try:
                        st = curr_path.stat()
                        mtime = st.st_mtime
                    except OSError:
                        mtime = 0.0
                    items.append(
                        {
                            "path": rel_dir,
                            "name": curr_path.name,
                            "type": "directory",
                            "size": 0,
                            "modified": mtime,
                        }
                    )
                    if len(items) >= limit:
                        break

                for f in sorted(filenames):
                    if f.startswith("."):
                        continue
                    file_path = curr_path / f
                    try:
                        st = file_path.stat()
                        items.append(
                            {
                                "path": paths.relative(file_path),
                                "name": f,
                                "type": "file",
                                "size": st.st_size,
                                "modified": st.st_mtime,
                            }
                        )
                    except OSError:
                        continue
                    if len(items) >= limit:
                        break
                if len(items) >= limit:
                    break
        except (OSError, ValueError):
            raise GatewayError("storage_unavailable") from None

        return self._reply(
            "workspace.files.tree.result",
            {"epoch": self.epoch, "files": items, "truncated": len(items) >= limit},
            session_id=command.session_id,
        )

    def _read_workspace_file(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"path"}, optional={"offset", "maxBytes"})
        assert self._workspace is not None
        raw_path = command.payload.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise GatewayError("invalid_path")
        offset = command.payload.get("offset", 0)
        if type(offset) is not int or offset < 0:
            raise GatewayError("invalid_offset")
        max_bytes = command.payload.get("maxBytes", 512 * 1024)
        if type(max_bytes) is not int or not 1 <= max_bytes <= _MAX_WORKSPACE_READ_BYTES:
            raise GatewayError("invalid_limit")
        paths = WorkspacePaths(self._workspace)
        try:
            target = paths.resolve(raw_path.strip())
            if not target.is_file():
                raise GatewayError("file_not_found")

            size = target.stat().st_size
            if size > _MAX_WORKSPACE_EDIT_BYTES:
                with target.open("rb") as f:
                    sample = f.read(64 * 1024)
                    if offset > 0:
                        f.seek(offset)
                    slice_bytes = f.read(max_bytes)
                sha256 = "unavailable_large_file"
                try:
                    sample.decode("utf-8")
                    is_binary = b"\x00" in sample
                except UnicodeDecodeError:
                    is_binary = True
            else:
                content_bytes = target.read_bytes()
                sha256 = sha256_bytes(content_bytes)
                slice_bytes = content_bytes[offset : offset + max_bytes]
                try:
                    content_bytes.decode("utf-8")
                    is_binary = b"\x00" in content_bytes
                except UnicodeDecodeError:
                    is_binary = True

            content_str = slice_bytes.decode("utf-8", errors="replace")
            truncated = (offset + len(slice_bytes)) < size
            editable = (
                offset == 0
                and (not truncated)
                and (not is_binary)
                and sha256 != "unavailable_large_file"
            )
            line_count = len(content_str.splitlines())
        except GatewayError:
            raise
        except (OSError, ValueError):
            raise GatewayError("file_read_failed") from None

        return self._reply(
            "workspace.file.read.result",
            {
                "epoch": self.epoch,
                "path": paths.relative(target),
                "content": content_str,
                "sha256": sha256,
                "size": size,
                "lineCount": line_count,
                "truncated": truncated,
                "isBinary": is_binary,
                "editable": editable,
            },
            session_id=command.session_id,
        )

    def _write_workspace_file(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"path", "content"}, optional={"expectedSha256"})
        assert self._workspace is not None
        raw_path = command.payload.get("path")
        content = command.payload.get("content")
        expected_sha = command.payload.get("expectedSha256")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise GatewayError("invalid_path")
        if not isinstance(content, str):
            raise GatewayError("invalid_content")
        if expected_sha is not None and (
            not isinstance(expected_sha, str)
            or re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha) is None
        ):
            raise GatewayError("invalid_digest")

        paths = WorkspacePaths(self._workspace)
        try:
            target = paths.resolve(raw_path.strip())
            content_bytes = content.encode("utf-8")
            if len(content_bytes) > _MAX_WORKSPACE_EDIT_BYTES:
                raise GatewayError("content_too_large")
            if target.exists():
                if expected_sha is None:
                    raise GatewayError("invalid_digest")
                if not target.is_file() or target.stat().st_size > _MAX_WORKSPACE_EDIT_BYTES:
                    raise GatewayError("file_not_editable")
                actual_bytes = target.read_bytes()
                try:
                    actual_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    raise GatewayError("binary_file_not_editable") from None
                if b"\x00" in actual_bytes:
                    raise GatewayError("binary_file_not_editable")
                actual_sha = sha256_bytes(actual_bytes)
                if expected_sha.lower() != actual_sha:
                    raise GatewayError("concurrent_modification")
            elif expected_sha is not None:
                raise GatewayError("concurrent_modification")

            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(paths, target, content_bytes, expected_sha)
            new_sha = sha256_bytes(content_bytes)
        except GatewayError:
            raise
        except ConcurrentModificationError:
            raise GatewayError("concurrent_modification") from None
        except ToolError:
            raise GatewayError("file_write_failed") from None
        except (OSError, ValueError):
            raise GatewayError("file_write_failed") from None

        return self._reply(
            "workspace.file.write.result",
            {
                "epoch": self.epoch,
                "path": paths.relative(target),
                "sha256": new_sha,
                "size": len(content_bytes),
            },
            session_id=command.session_id,
        )

    def _get_git_diff(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, set())
        assert self._workspace is not None
        files_payload: list[dict[str, object]] = []
        is_git_repo = True
        error: str | None = None
        try:
            service = self._get_git_service()
            if not service.is_git_repository():
                is_git_repo = False
                error = "not_git_repository"
            else:
                file_diffs = service.get_working_tree_diffs()
                for fd in file_diffs:
                    files_payload.append(self._file_diff_document(fd))
                if service.last_diff_truncated:
                    error = "diff_output_too_large"
        except (OSError, ValueError):
            files_payload = []
            error = "git_diff_unavailable"

        return self._reply(
            "workspace.git.diff.result",
            {
                "epoch": self.epoch,
                "isGitRepo": is_git_repo,
                "files": files_payload,
                "error": error,
            },
            session_id=command.session_id,
        )

    @staticmethod
    def _file_diff_document(file_diff: FileDiff) -> dict[str, object]:
        hunks_payload: list[dict[str, object]] = []
        for hunk in file_diff.hunks:
            hunks_payload.append(
                {
                    "hunkIndex": hunk.hunk_index,
                    "oldStart": hunk.old_start,
                    "oldCount": hunk.old_count,
                    "newStart": hunk.new_start,
                    "newCount": hunk.new_count,
                    "header": hunk.header,
                    "lines": [
                        {
                            "kind": line.kind,
                            "content": line.content,
                            "oldLineno": line.old_lineno,
                            "newLineno": line.new_lineno,
                        }
                        for line in hunk.lines
                    ],
                }
            )
        return {
            "filePath": file_diff.file_path,
            "status": file_diff.status,
            "additions": file_diff.additions,
            "deletions": file_diff.deletions,
            "summary": file_diff.summary,
            "isStaged": file_diff.is_staged,
            "isBinary": file_diff.is_binary,
            "hunks": hunks_payload,
        }

    def _get_git_service(self) -> GitDiffReviewService:
        assert self._workspace is not None
        if (
            self._git_review_service is None
            or self._git_review_service.workspace != self._workspace
        ):
            self._git_review_service = GitDiffReviewService(self._workspace)
        return self._git_review_service

    def _revert_git_diff(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"filePath"}, optional={"hunkIndex"})
        assert self._workspace is not None
        file_path = command.payload.get("filePath")
        hunk_index = command.payload.get("hunkIndex")
        if not isinstance(file_path, str) or not file_path.strip():
            raise GatewayError("invalid_path")
        if hunk_index is not None and type(hunk_index) is not int:
            raise GatewayError("invalid_hunk_index")

        service = self._get_git_service()
        success = False
        checkpoint_id: str | None = None
        error: str | None = None
        try:
            if hunk_index is None:
                success = service.revert_file(file_path)
            else:
                file_diffs = service.get_working_tree_diffs()
                match_fd = next((fd for fd in file_diffs if fd.file_path == file_path), None)
                if match_fd:
                    match_hunk = next(
                        (h for h in match_fd.hunks if h.hunk_index == hunk_index), None
                    )
                    if match_hunk:
                        success = service.revert_hunk(file_path, match_hunk)
            if success:
                checkpoint_id = service.last_checkpoint_id
        except ValueError:
            error = "invalid_path"
            success = False
        except (OSError, subprocess.SubprocessError):
            error = "git_revert_failed"
            success = False
        if not success and error is None:
            error = "git_revert_failed"

        return self._reply(
            "workspace.git.revert.result",
            {
                "epoch": self.epoch,
                "filePath": file_path,
                "hunkIndex": hunk_index,
                "success": success,
                "checkpointId": checkpoint_id,
                "error": error,
            },
            session_id=command.session_id,
        )

    def _undo_git_diff(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"checkpointId"})
        assert self._workspace is not None
        checkpoint_id = command.payload.get("checkpointId")
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise GatewayError("invalid_checkpoint_id")

        service = self._get_git_service()
        success = False
        error: str | None = None
        try:
            success = service.undo_checkpoint(checkpoint_id.strip())
        except (OSError, ValueError):
            success = False
        if not success:
            error = "checkpoint_changed_or_unavailable"

        return self._reply(
            "workspace.git.undo.result",
            {
                "epoch": self.epoch,
                "checkpointId": checkpoint_id,
                "success": success,
                "error": error,
            },
            session_id=command.session_id,
        )

    def _deliver_git_changes(self, command: CommandEnvelope) -> GatewayReply:
        with self._lock:
            self._require_configured()
            self._require_payload(
                command, {"title"}, optional={"description", "stageAll", "selectedFiles"}
            )
            assert self._workspace is not None
            if self._git_delivery_in_progress:
                raise GatewayError("runtime_busy")
            title = command.payload.get("title")
            description = command.payload.get("description", "")
            stage_all = command.payload.get("stageAll", False)
            selected_files = command.payload.get("selectedFiles")
            if not isinstance(title, str) or not title.strip():
                raise GatewayError("invalid_title")
            if not isinstance(description, str):
                raise GatewayError("invalid_description")
            if len(title.strip()) > 200 or len(description) > 4_000:
                raise GatewayError("invalid_commit_message")
            if type(stage_all) is not bool or stage_all:
                raise GatewayError("stage_all_not_supported")
            if not isinstance(selected_files, list) or not 1 <= len(selected_files) <= 200:
                raise GatewayError("invalid_selection")
            workspace = self._workspace
            self._git_delivery_in_progress = True

        commit_message = f"{title.strip()}\n\n{description.strip()}".strip()
        git_cmd = shutil.which("git")
        branch = "HEAD"
        commit_sha: str | None = None
        success = False
        summary = ""
        error_code: str | None = None

        try:
            if not git_cmd:
                summary = "Git executable unavailable"
            else:
                import os

                env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}
                service = GitDiffReviewService(workspace)
                if not service.is_git_repository():
                    summary = "Workspace is not a Git repository"
                else:
                    paths = WorkspacePaths(workspace)
                    valid_paths: list[str] = []
                    for raw_path in selected_files:
                        if (
                            not isinstance(raw_path, str)
                            or not raw_path.strip()
                            or any(ord(char) < 32 for char in raw_path)
                        ):
                            raise GatewayError("invalid_selection")
                        normalized = paths.relative(paths.resolve(raw_path.strip()))
                        if normalized in valid_paths:
                            raise GatewayError("invalid_selection")
                        valid_paths.append(normalized)

                    available_paths = {
                        item.file_path for item in service.get_working_tree_diffs(max_files=200)
                    }
                    if service.last_diff_truncated:
                        summary = "Selected diff is too large to deliver safely"
                    elif not set(valid_paths).issubset(available_paths):
                        summary = "Selection no longer matches the working tree"
                    else:
                        pre_staged = subprocess.run(
                            [git_cmd, "diff", "--cached", "--quiet", "--", *valid_paths],
                            cwd=workspace,
                            stdin=subprocess.DEVNULL,
                            capture_output=True,
                            timeout=10.0,
                            env=env,
                        )
                        if pre_staged.returncode == 1:
                            summary = "Selected files contain pre-existing staged changes"
                            error_code = "selected_files_have_staged_changes"
                        elif pre_staged.returncode != 0:
                            summary = "Unable to inspect selected staged changes"
                        else:
                            subprocess.run(
                                [git_cmd, "add", "--", *valid_paths],
                                cwd=workspace,
                                stdin=subprocess.DEVNULL,
                                check=True,
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                                timeout=15.0,
                                env=env,
                            )

                    if not summary:
                        st_res = subprocess.run(
                            [git_cmd, "diff", "--cached", "--quiet", "--", *valid_paths],
                            cwd=workspace,
                            stdin=subprocess.DEVNULL,
                            capture_output=True,
                            timeout=10.0,
                            env=env,
                        )
                        if st_res.returncode == 0:
                            summary = "No selected changes to commit"
                        elif st_res.returncode == 1:
                            proc = subprocess.run(
                                [
                                    git_cmd,
                                    "commit",
                                    "--only",
                                    "-m",
                                    commit_message,
                                    "--",
                                    *valid_paths,
                                ],
                                cwd=workspace,
                                stdin=subprocess.DEVNULL,
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                                timeout=15.0,
                                env=env,
                            )
                            if proc.returncode == 0:
                                success = True
                                summary = proc.stdout.strip()[:2000]
                                rev_proc = subprocess.run(
                                    [git_cmd, "rev-parse", "HEAD"],
                                    cwd=workspace,
                                    stdin=subprocess.DEVNULL,
                                    capture_output=True,
                                    text=True,
                                    timeout=5.0,
                                    env=env,
                                )
                                if rev_proc.returncode == 0:
                                    commit_sha = rev_proc.stdout.strip()
                                branch_proc = subprocess.run(
                                    [git_cmd, "rev-parse", "--abbrev-ref", "HEAD"],
                                    cwd=workspace,
                                    stdin=subprocess.DEVNULL,
                                    capture_output=True,
                                    text=True,
                                    timeout=5.0,
                                    env=env,
                                )
                                if branch_proc.returncode == 0:
                                    branch = branch_proc.stdout.strip()
                            else:
                                summary = "Git commit failed"
                        else:
                            summary = "Unable to inspect selected changes"
        except GatewayError:
            raise
        except (OSError, subprocess.SubprocessError):
            summary = "Git delivery command failed"
        finally:
            with self._lock:
                self._git_delivery_in_progress = False

        err_msg = None if success else (error_code or summary or "delivery_failed")
        if summary == "Workspace is not a Git repository":
            err_msg = "not_git_repository"

        with self._lock:
            return self._reply(
                "workspace.git.deliver.result",
                {
                    "epoch": self.epoch,
                    "commitSha": commit_sha,
                    "branch": branch,
                    "success": success,
                    "summary": summary,
                    "error": err_msg,
                },
                session_id=command.session_id,
            )

    def _get_workspace_context(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, set())
        assert self._workspace is not None
        memory_items: list[dict[str, object]] = []
        try:
            memories = SQLiteEventStore.list_memories_read_only(
                self._database, str(self._workspace), limit=50
            )
            memory_items = [
                {
                    "id": item.id,
                    "type": "workspace_memory",
                    "summary": item.content[:500],
                    "createdAt": item.created_at,
                    "updatedAt": item.updated_at,
                }
                for item in memories
            ]
        except (OSError, sqlite3.Error, ValueError):
            raise GatewayError("storage_unavailable") from None

        caps = sorted(capability.value for capability in capabilities_for_mode(self._mode))
        manifest: dict[str, object] | None = None
        measured_usage: dict[str, object] | None = None
        context_session = command.session_id or self._selected_session_id
        if context_session:
            stored_session = self._stored_session(context_session)
            if (
                stored_session is None
                or Path(stored_session.workspace).resolve() != self._workspace
            ):
                raise GatewayError("invalid_session")
            requested, usage = SQLiteEventStore.latest_model_context_read_only(
                self._database, context_session
            )
            if requested is not None and isinstance(requested.data.get("context_manifest"), dict):
                manifest = dict(requested.data["context_manifest"])
                manifest.update(
                    requestId=requested.id,
                    createdAt=requested.created_at,
                    correlationId=requested.correlation_id,
                )
            if usage is not None:
                measured_usage = {
                    "inputTokens": usage.data.get("input_tokens"),
                    "outputTokens": usage.data.get("output_tokens"),
                    "cachedTokens": usage.data.get("cached_tokens"),
                    "estimated": usage.data.get("estimated", True),
                    "requestId": usage.causation_id,
                    "createdAt": usage.created_at,
                }
        budget = _context_budget_from_manifest(manifest, measured_usage)
        if budget is None:
            budget = {
                "available": False,
                "source": "provider_telemetry_unavailable",
            }
        instructions = [
            {
                "title": "Runtime Mode",
                "detail": f"Agent Workspace active mode: {self._mode.value}.",
            },
            {
                "title": "Autonomy Policy",
                "detail": (
                    f"Execution policy set to {self._autonomy.value} with "
                    "explicit user approval gates."
                ),
            },
        ]

        return self._reply(
            "workspace.context.get.result",
            {
                "epoch": self.epoch,
                "memory": memory_items,
                "manifest": manifest,
                "lastUsage": measured_usage,
                "skills": caps,
                "budget": budget,
                "instructions": instructions,
            },
            session_id=command.session_id,
        )

    def _run_doctor(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"workspace"})
        from agent_workspace.core.doctor import diagnose_environment
        from agent_workspace.tools.native_isolation import inspect_native_isolation

        with self._lock:
            ws = self._workspace
            database = self._database
            provider = self._provider
            epoch = self.epoch
        req_ws = command.payload.get("workspace")
        if isinstance(req_ws, str) and req_ws.strip():
            ws = Path(req_ws).expanduser().resolve()

        report = diagnose_environment(
            workspace=ws,
            db_path=database,
            provider_config=provider,
            isolation_probe=inspect_native_isolation,
        )

        return self._reply(
            "system.doctor.result",
            {
                "epoch": epoch,
                "timestamp": report.timestamp,
                "overallStatus": report.overall_status,
                "checks": [c.to_dict() for c in report.checks],
            },
            session_id=command.session_id,
        )

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
        try:
            isolation = RunIsolation(cast(str, command.payload.get("isolation", "worktree")))
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
        self._pending_host_events.append(
            Event(
                session_id=session_id,
                type="agent.run.updated",
                data={"run_id": run_id, "state": state},
            )
        )

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

    def _review_service(self) -> ReviewWorkflowService:
        if self._workspace is None:
            raise GatewayError("runtime_unconfigured")
        service = self._review_workflow
        if service is None:
            try:
                service = ReviewWorkflowService(self._database)
            except (OSError, sqlite3.DatabaseError, RuntimeError):
                raise GatewayError("storage_unavailable") from None
            self._review_workflow = service
        return service

    @staticmethod
    def _review_snapshot_document(
        snapshot: ReviewSnapshot, *, include_files: bool = False
    ) -> dict[str, object]:
        additions = sum(
            value for file in snapshot.files if type(value := file.get("additions")) is int
        )
        deletions = sum(
            value for file in snapshot.files if type(value := file.get("deletions")) is int
        )
        document: dict[str, object] = {
            "id": snapshot.id,
            "workspace": snapshot.workspace,
            "checkoutPath": snapshot.checkout_path,
            "sessionId": snapshot.session_id,
            "runId": snapshot.run_id,
            "baseSha": snapshot.base_sha,
            "headSha": snapshot.head_sha,
            "diffSha256": snapshot.diff_sha256,
            "workingTreeDirty": snapshot.working_tree_dirty,
            "fileCount": len(snapshot.files),
            "additions": additions,
            "deletions": deletions,
            "createdAt": snapshot.created_at,
        }
        if include_files:
            document["files"] = list(snapshot.files)
        return document

    @staticmethod
    def _review_comment_document(comment: ReviewComment) -> dict[str, object]:
        raw = cast(dict[str, object], asdict(comment))
        return {_camel_case(key): _json_safe(value) for key, value in raw.items()}

    @staticmethod
    def _review_delivery_document(delivery: ReviewDelivery | None) -> dict[str, object] | None:
        if delivery is None:
            return None
        raw = cast(dict[str, object], asdict(delivery))
        return {_camel_case(key): _json_safe(value) for key, value in raw.items()}

    @staticmethod
    def _delivery_check_document(check: DeliveryCheck) -> dict[str, object]:
        raw = cast(dict[str, object], asdict(check))
        return {_camel_case(key): _json_safe(value) for key, value in raw.items()}

    def _review_details_payload(
        self, service: ReviewWorkflowService, snapshot: ReviewSnapshot
    ) -> dict[str, object]:
        comments = service.list_comments(snapshot.id)
        delivery = service.get_delivery(snapshot.id)
        checks = service.list_delivery_checks(snapshot.id) if delivery is not None else []
        return {
            "epoch": self.epoch,
            "snapshot": self._review_snapshot_document(snapshot, include_files=True),
            "comments": [self._review_comment_document(comment) for comment in comments],
            "delivery": self._review_delivery_document(delivery),
            "checks": [self._delivery_check_document(check) for check in checks],
        }

    def _list_review_snapshots(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"limit"})
        if self._workspace is None:
            raise GatewayError("runtime_unconfigured")
        limit = command.payload.get("limit", 100)
        if type(limit) is not int or not 1 <= limit <= 500:
            raise GatewayError("invalid_limit")
        try:
            snapshots = self._review_service().list_snapshots(self._workspace, limit=limit)
        except (ReviewWorkflowError, OSError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "workspace.review.list.result",
            {
                "epoch": self.epoch,
                "snapshots": [self._review_snapshot_document(item) for item in snapshots],
            },
            session_id=command.session_id,
        )

    def _get_review_snapshot(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"snapshotId"})
        snapshot_id = command.payload.get("snapshotId")
        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise GatewayError("invalid_snapshot")
        service = self._review_service()
        snapshot = service.get_snapshot(snapshot_id)
        if (
            snapshot is None
            or self._workspace is None
            or snapshot.workspace != str(self._workspace)
        ):
            raise GatewayError("snapshot_not_found")
        return self._reply(
            "workspace.review.get.result",
            self._review_details_payload(service, snapshot),
            session_id=snapshot.session_id,
        )

    def _create_review_snapshot(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"runId", "baseSha"})
        with self._lock:
            if self._workspace is None:
                raise GatewayError("runtime_unconfigured")
            root = self._workspace
            service = self._review_service()
            run_id = command.payload.get("runId")
            if run_id is not None and (not isinstance(run_id, str) or not run_id):
                raise GatewayError("invalid_run")
            run = self._control_service().get_run(run_id) if isinstance(run_id, str) else None
            if run_id is not None and (run is None or run.workspace != str(root)):
                raise GatewayError("run_not_found")
            if run is not None:
                checkout = Path(run.checkout_path or run.workspace).resolve()
                session_id = run.session_id
                default_base = run.base_sha
            else:
                checkout = root
                candidate_session_id = command.session_id or self._selected_session_id
                default_base = None
                if candidate_session_id is None:
                    raise GatewayError("invalid_session")
                session_id = candidate_session_id
                with SQLiteEventStore(self._database) as store:
                    session = store.get_session(session_id)
                if session is None or Path(session.workspace).resolve() != root:
                    raise GatewayError("invalid_session")
        try:
            head_sha = git_head_sha(checkout)
            raw_base = command.payload.get("baseSha") or default_base or head_sha
            if not isinstance(raw_base, str):
                raise GatewayError("invalid_base_revision")
            git_service = GitDiffReviewService(checkout)
            files = git_service.get_review_diffs(raw_base)
            if git_service.last_diff_truncated:
                raise GatewayError("review_snapshot_too_large")
            if not files:
                raise GatewayError("review_empty")
            file_documents = [self._file_diff_document(file) for file in files]
            diff_text = json.dumps(
                file_documents,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            dirty = not git_worktree_is_clean(checkout)
            with self._lock:
                if self._workspace != root:
                    raise GatewayError("workspace_changed")
                snapshot = service.create_snapshot(
                    workspace=root,
                    checkout_path=checkout,
                    session_id=session_id,
                    run_id=run_id if isinstance(run_id, str) else None,
                    base_sha=raw_base,
                    head_sha=head_sha,
                    files=file_documents,
                    diff_text=diff_text,
                    working_tree_dirty=dirty,
                )
                return self._reply(
                    "workspace.review.create.result",
                    self._review_details_payload(service, snapshot),
                    session_id=session_id,
                )
        except GatewayError:
            raise
        except ReviewWorkflowError as error:
            raise GatewayError(str(error)) from None
        except (GitOpsError, OSError, ValueError):
            raise GatewayError("review_capture_failed") from None

    def _create_review_comment(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"snapshotId", "path", "side", "line", "body"})
        snapshot_id = command.payload.get("snapshotId")
        path = command.payload.get("path")
        side = command.payload.get("side")
        line = command.payload.get("line")
        body = command.payload.get("body")
        if not all(isinstance(value, str) for value in (snapshot_id, path, side, body)):
            raise GatewayError("invalid_review_comment")
        if type(line) is not int:
            raise GatewayError("invalid_review_comment")
        service = self._review_service()
        snapshot = service.get_snapshot(cast(str, snapshot_id))
        if (
            snapshot is None
            or self._workspace is None
            or snapshot.workspace != str(self._workspace)
        ):
            raise GatewayError("snapshot_not_found")
        try:
            comment = service.create_comment(
                snapshot.id,
                path=cast(str, path),
                side=cast(str, side),
                line=line,
                body=cast(str, body),
            )
        except ReviewWorkflowError as error:
            raise GatewayError(str(error)) from None
        return self._reply(
            "workspace.review.comments.create.result",
            {"epoch": self.epoch, "comment": self._review_comment_document(comment)},
            session_id=snapshot.session_id,
        )

    def _resolve_review_comment(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"commentId"})
        comment_id = command.payload.get("commentId")
        if not isinstance(comment_id, str) or not comment_id:
            raise GatewayError("invalid_review_comment")
        service = self._review_service()
        existing = service.get_comment(comment_id)
        if existing is None:
            raise GatewayError("comment_not_found")
        snapshot = service.get_snapshot(existing.snapshot_id)
        if (
            snapshot is None
            or self._workspace is None
            or snapshot.workspace != str(self._workspace)
        ):
            raise GatewayError("comment_not_found")
        try:
            comment = service.resolve_comment(comment_id)
        except ReviewWorkflowError as error:
            raise GatewayError(str(error)) from None
        return self._reply(
            "workspace.review.comments.resolve.result",
            {"epoch": self.epoch, "comment": self._review_comment_document(comment)},
            session_id=snapshot.session_id,
        )

    def _followup_review_comment(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(
            command,
            {"commentId"},
            optional={"sessionId", "isolation", "start"},
        )
        comment_id = command.payload.get("commentId")
        owner_session_id = (
            command.payload.get("sessionId") or command.session_id or self._selected_session_id
        )
        raw_isolation = command.payload.get("isolation", RunIsolation.WORKTREE.value)
        start = command.payload.get("start", True)
        if not isinstance(comment_id, str) or not comment_id:
            raise GatewayError("invalid_review_comment")
        if not isinstance(owner_session_id, str) or type(start) is not bool:
            raise GatewayError("invalid_session")
        try:
            isolation = RunIsolation(cast(str, raw_isolation))
        except (TypeError, ValueError):
            raise GatewayError("invalid_isolation") from None
        service = self._review_service()
        comment = service.get_comment(comment_id)
        snapshot = service.get_snapshot(comment.snapshot_id) if comment is not None else None
        if (
            comment is None
            or snapshot is None
            or self._workspace is None
            or snapshot.workspace != str(self._workspace)
        ):
            raise GatewayError("comment_not_found")
        goal = (
            f"Address review comment {comment.id} from immutable snapshot {snapshot.id} "
            f"({snapshot.diff_sha256}) at {comment.path}:{comment.line} "
            f"on the {comment.side} side.\n\n"
            f"Reviewer feedback:\n{comment.body}\n\n"
            "Implement the correction, add appropriate verification, and report evidence against "
            "the frozen review anchor."
        )
        try:
            run = self._control_service().create_run(
                workspace=self._workspace,
                session_id=owner_session_id,
                goal=goal,
                title=f"Review follow-up: {comment.path}:{comment.line}",
                isolation=isolation,
                parent_run_id=snapshot.run_id,
            )
            comment = service.link_comment_followup(comment.id, run.id)
        except (AgentControlError, ReviewWorkflowError) as error:
            raise GatewayError(str(error)) from None
        started = False
        if start:
            self._start_agent_run(
                CommandEnvelope(
                    v=command.v,
                    request_id=command.request_id,
                    type="workspace.runs.start",
                    payload={"runId": run.id},
                    session_id=owner_session_id,
                )
            )
            started = True
        return self._reply(
            "workspace.review.comments.followup.result",
            {
                "epoch": self.epoch,
                "comment": self._review_comment_document(comment),
                "run": self._run_document(run),
                "started": started,
            },
            session_id=owner_session_id,
        )

    def _assert_review_snapshot_current(
        self,
        snapshot: ReviewSnapshot,
        *,
        prepared_commit_sha: str | None = None,
    ) -> None:
        checkout = Path(snapshot.checkout_path).resolve()
        try:
            current_head = git_head_sha(checkout)
            if current_head != snapshot.head_sha:
                if (
                    snapshot.working_tree_dirty
                    and prepared_commit_sha is not None
                    and current_head == prepared_commit_sha
                ):
                    return
                raise GatewayError("review_snapshot_stale")
            files = GitDiffReviewService(checkout).get_review_diffs(snapshot.base_sha)
            documents = [self._file_diff_document(file) for file in files]
            current = json.dumps(
                documents,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            if hashlib.sha256(current.encode("utf-8")).hexdigest() != snapshot.diff_sha256:
                raise GatewayError("review_snapshot_stale")
        except GatewayError:
            raise
        except (GitOpsError, OSError, ValueError):
            raise GatewayError("review_validation_failed") from None

    def _create_review_pull_request(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(
            command,
            {"snapshotId", "title", "baseBranch"},
            optional={"body", "commitTitle"},
        )
        snapshot_id = command.payload.get("snapshotId")
        title = command.payload.get("title")
        body = command.payload.get("body", "")
        base_branch = command.payload.get("baseBranch")
        commit_title = command.payload.get("commitTitle")
        if not all(isinstance(value, str) for value in (snapshot_id, title, body, base_branch)):
            raise GatewayError("invalid_pull_request")
        if commit_title is not None and not isinstance(commit_title, str):
            raise GatewayError("invalid_pull_request")
        with self._lock:
            service = self._review_service()
            snapshot = service.get_snapshot(cast(str, snapshot_id))
            existing_delivery = service.get_delivery(snapshot.id) if snapshot is not None else None
            if (
                snapshot is None
                or self._workspace is None
                or snapshot.workspace != str(self._workspace)
            ):
                raise GatewayError("snapshot_not_found")
            if existing_delivery is not None and existing_delivery.pr_url is not None:
                raise GatewayError("pull_request_exists")
            if snapshot.id in self._review_delivery_in_progress:
                raise GatewayError("delivery_in_progress")
            self._review_delivery_in_progress.add(snapshot.id)
        try:
            self._assert_review_snapshot_current(
                snapshot,
                prepared_commit_sha=(
                    existing_delivery.commit_sha if existing_delivery is not None else None
                ),
            )
            result = GitHubDeliveryService().create_draft(
                snapshot,
                title=cast(str, title),
                body=cast(str, body),
                base_branch=cast(str, base_branch),
                commit_title=commit_title,
                resume_commit_sha=(
                    existing_delivery.commit_sha if existing_delivery is not None else None
                ),
            )
            delivery = service.upsert_delivery(
                snapshot.id,
                pr_url=cast(str, result["prUrl"]),
                pr_number=cast(int, result["prNumber"]),
                state=DeliveryState(cast(str, result["state"])),
                is_draft=cast(bool, result["isDraft"]),
                head_branch=cast(str | None, result["headBranch"]),
                base_branch=cast(str | None, result["baseBranch"]),
                commit_sha=cast(str, result["commitSha"]),
            )
            checks = service.replace_delivery_checks(
                snapshot.id,
                cast(list[Mapping[str, object]], result["checks"]),
            )
            with suppress(Exception):
                self._control_service().resolve_attention_by_source(
                    f"delivery:{snapshot.id}", resolution={"state": delivery.state.value}
                )
        except (GitHubDeliveryError, ReviewWorkflowError, GatewayError) as error:
            code = str(error)
            delivery_error = error if isinstance(error, GitHubDeliveryError) else None
            with suppress(Exception):
                service.upsert_delivery(
                    snapshot.id,
                    pr_url=delivery_error.pr_url if delivery_error is not None else None,
                    pr_number=(delivery_error.pr_number if delivery_error is not None else None),
                    state=DeliveryState.ERROR,
                    is_draft=True,
                    head_branch=(
                        delivery_error.head_branch if delivery_error is not None else None
                    ),
                    base_branch=cast(str, base_branch),
                    commit_sha=(delivery_error.commit_sha if delivery_error is not None else None),
                    last_error=code,
                )
                self._control_service().open_attention(
                    run_id=snapshot.run_id,
                    session_id=snapshot.session_id,
                    kind=AttentionKind.CI,
                    severity="critical",
                    title="Pull request delivery failed",
                    detail=code,
                    source_key=f"delivery:{snapshot.id}",
                    action={"kind": "inspect_review", "snapshotId": snapshot.id},
                )
            raise GatewayError(
                code if re.fullmatch(r"[a-z][a-z0-9_]*", code) else "delivery_failed"
            ) from None
        finally:
            with self._lock:
                self._review_delivery_in_progress.discard(snapshot.id)
        with self._lock:
            return self._reply(
                "workspace.review.pr.create.result",
                {
                    "epoch": self.epoch,
                    "delivery": self._review_delivery_document(delivery),
                    "checks": [self._delivery_check_document(check) for check in checks],
                },
                session_id=snapshot.session_id,
            )

    def _refresh_review_pull_request(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"snapshotId"})
        snapshot_id = command.payload.get("snapshotId")
        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise GatewayError("invalid_snapshot")
        with self._lock:
            service = self._review_service()
            snapshot = service.get_snapshot(snapshot_id)
            delivery = service.get_delivery(snapshot_id)
            if (
                snapshot is None
                or self._workspace is None
                or snapshot.workspace != str(self._workspace)
            ):
                raise GatewayError("snapshot_not_found")
            if delivery is None or delivery.pr_url is None:
                raise GatewayError("pull_request_not_found")
        try:
            result = GitHubDeliveryService().inspect(
                delivery.pr_url, checkout=snapshot.checkout_path
            )
            delivery = service.upsert_delivery(
                snapshot.id,
                pr_url=cast(str, result["prUrl"]),
                pr_number=cast(int, result["prNumber"]),
                state=DeliveryState(cast(str, result["state"])),
                is_draft=cast(bool, result["isDraft"]),
                head_branch=cast(str | None, result["headBranch"]),
                base_branch=cast(str | None, result["baseBranch"]),
            )
            checks = service.replace_delivery_checks(
                snapshot.id,
                cast(list[Mapping[str, object]], result["checks"]),
            )
        except (GitHubDeliveryError, ReviewWorkflowError) as error:
            raise GatewayError(str(error)) from None
        with self._lock:
            return self._reply(
                "workspace.review.pr.refresh.result",
                {
                    "epoch": self.epoch,
                    "delivery": self._review_delivery_document(delivery),
                    "checks": [self._delivery_check_document(check) for check in checks],
                },
                session_id=snapshot.session_id,
            )

    def _list_jobs(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, set(), optional={"limit", "sessionScope", "activeOnly"})
        limit = command.payload.get("limit", 50)
        scope = command.payload.get("sessionScope", "selected")
        active_only = command.payload.get("activeOnly", False)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise GatewayError("invalid_limit")
        if scope not in {"selected", "workspace"} or type(active_only) is not bool:
            raise GatewayError("invalid_command")
        if command.session_id not in {None, self._selected_session_id}:
            raise GatewayError("invalid_session")
        session_id = None
        if scope == "selected":
            self._require_selected_session(command.session_id)
            session_id = command.session_id
        assert self._workspace is not None
        try:
            with SQLiteEventStore(self._database) as store:
                jobs = store.list_background_jobs(
                    str(self._workspace),
                    session_id=session_id,
                    limit=limit,
                    active_only=active_only,
                )
        except (OSError, ValueError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "jobs.list.result",
            {"epoch": self.epoch, "jobs": [self._job_document(job) for job in jobs]},
        )

    def _job_logs(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"jobId"}, optional={"maxBytes", "offset"})
        self._require_selected_session(command.session_id)
        job_id = command.payload.get("jobId")
        max_bytes = command.payload.get("maxBytes", 65_536)
        offset = command.payload.get("offset", 0)
        if not isinstance(job_id, str) or not job_id or len(job_id) > 128:
            raise GatewayError("invalid_job")
        if type(max_bytes) is not int or not 1 <= max_bytes <= _MAX_JOB_LOG_BYTES:
            raise GatewayError("invalid_job")
        if type(offset) is not int or offset < 0:
            raise GatewayError("invalid_offset")
        assert command.session_id is not None
        self._selected_job(command.session_id, job_id)
        host = self._require_host()
        try:
            future = host.request_job_logs(command.session_id, job_id, max_bytes, offset)
        except TypeError:
            if offset != 0:
                raise GatewayError("runtime_unavailable") from None
            future = host.request_job_logs(command.session_id, job_id, max_bytes)
        if future is None:
            raise GatewayError("runtime_unavailable")
        try:
            raw = future.result(timeout=_COMMAND_TIMEOUT_SECONDS)
        except Exception:
            raise GatewayError("runtime_unavailable") from None
        if not isinstance(raw, Mapping):
            raise GatewayError("runtime_unavailable")
        data = raw.get("data")
        if not isinstance(data, str):
            raise GatewayError("runtime_unavailable")
        encoded = data.encode("utf-8")
        wire_cap = min(max_bytes, _MAX_STRING_CHARS)
        if len(encoded) > wire_cap:
            data = encoded[:wire_cap].decode("utf-8", errors="ignore")
        raw_bytes = raw.get("bytes")
        raw_state = raw.get("state")
        if type(raw_bytes) is not int or not isinstance(raw_state, str):
            raise GatewayError("runtime_unavailable")
        return self._reply(
            "jobs.logs.result",
            {
                "epoch": self.epoch,
                "jobId": job_id,
                "state": raw_state,
                "data": data,
                "bytes": raw_bytes,
                "offset": raw.get("offset", offset),
                "nextOffset": raw.get("next_offset", raw.get("nextOffset", offset + len(encoded))),
                "eof": raw.get("eof") is True,
                "truncated": raw.get("truncated") is True or len(encoded) > wire_cap,
            },
            session_id=command.session_id,
        )

    def _stop_job(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"jobId"})
        self._require_selected_session(command.session_id)
        job_id = command.payload.get("jobId")
        if not isinstance(job_id, str) or not job_id or len(job_id) > 128:
            raise GatewayError("invalid_job")
        assert command.session_id is not None
        status = self._selected_job(command.session_id, job_id)
        if status.state in _TERMINAL_JOB_STATES:
            raise GatewayError("job_not_stoppable")
        future = self._require_host().request_job_stop(command.session_id, job_id)
        if future is None:
            raise GatewayError("runtime_unavailable")
        try:
            stopped = future.result(timeout=_COMMAND_TIMEOUT_SECONDS)
        except Exception:
            raise GatewayError("runtime_unavailable") from None
        return self._reply(
            "jobs.stop.result",
            {"epoch": self.epoch, "job": self._job_document(stopped)},
            session_id=command.session_id,
        )

    def _schedule_command(self, command: CommandEnvelope) -> GatewayReply:
        """Handle mutable schedules without rewriting legacy TOML files."""

        if self._workspace is None:
            raise GatewayError("runtime_unconfigured")
        action = command.type.rsplit(".", 1)[-1]
        store = ScheduleStore(self._workspace)
        try:
            if action == "list":
                self._require_payload(command, set(), optional={"limit"})
                limit = command.payload.get("limit", 100)
                if type(limit) is not int or not 1 <= limit <= 500:
                    raise GatewayError("invalid_limit")
                schedules = store.list()[:limit]
                payload = {
                    "epoch": self.epoch,
                    "schedules": [item.to_document() for item in schedules],
                    "truncated": len(store.list()) > limit,
                }
            elif action == "create":
                self._require_payload(
                    command,
                    {"id", "prompt"},
                    optional={"cron", "at", "timezone"},
                )
                schedule_id = command.payload.get("id")
                if not isinstance(schedule_id, str) or not schedule_id.strip():
                    raise GatewayError("invalid_schedule")
                schedule = store.create(
                    schedule_id=schedule_id.strip(),
                    prompt=cast(str, command.payload["prompt"]),
                    cron=cast(str | None, command.payload.get("cron")),
                    at=cast(str | None, command.payload.get("at")),
                    timezone=cast(str, command.payload.get("timezone", "UTC")),
                )
                payload = {"epoch": self.epoch, "schedule": schedule.to_document()}
            elif action == "update":
                self._require_payload(
                    command,
                    {"scheduleId"},
                    optional={"prompt", "cron", "at", "timezone", "enabled"},
                )
                schedule_id = command.payload.get("scheduleId")
                if not isinstance(schedule_id, str) or not schedule_id:
                    raise GatewayError("invalid_schedule")
                changes = {
                    key: command.payload[key]
                    for key in ("prompt", "cron", "at", "timezone", "enabled")
                    if key in command.payload
                }
                schedule = store.update(schedule_id, **changes)
                payload = {"epoch": self.epoch, "schedule": schedule.to_document()}
            elif action in {"pause", "resume"}:
                self._require_payload(command, {"scheduleId"})
                schedule_id = command.payload.get("scheduleId")
                if not isinstance(schedule_id, str) or not schedule_id:
                    raise GatewayError("invalid_schedule")
                schedule = (
                    store.pause(schedule_id) if action == "pause" else store.resume(schedule_id)
                )
                payload = {"epoch": self.epoch, "schedule": schedule.to_document()}
            elif action == "delete":
                self._require_payload(command, {"scheduleId"})
                schedule_id = command.payload.get("scheduleId")
                if not isinstance(schedule_id, str) or not schedule_id:
                    raise GatewayError("invalid_schedule")
                if not store.delete(schedule_id):
                    raise GatewayError("schedule_not_found")
                payload = {"epoch": self.epoch, "scheduleId": schedule_id, "success": True}
            elif action == "run_now":
                self._require_payload(command, {"scheduleId"}, optional={"priority"})
                schedule_id = command.payload.get("scheduleId")
                if not isinstance(schedule_id, str) or not schedule_id:
                    raise GatewayError("invalid_schedule")
                trigger = store.run_now(schedule_id)
                priority = command.payload.get("priority", 0)
                if type(priority) is not int or not -100_000 <= priority <= 100_000:
                    raise GatewayError("invalid_priority")
                provider = self._provider
                model = provider.model if provider is not None and provider.model else "scheduled"
                with SQLiteEventStore(self._database) as event_store:
                    queue = DurableRunQueue(event_store)
                    queued = self._run_queue_enqueue_sync(
                        queue,
                        str(self._workspace),
                        cast(str, trigger["prompt"]),
                        model,
                        priority=priority,
                    )
                payload = {
                    "epoch": self.epoch,
                    "scheduleId": schedule_id,
                    "trigger": trigger,
                    "task": self._queue_document(queued),
                    "accepted": True,
                }
            elif action == "preview":
                self._require_payload(command, {"scheduleId"}, optional={"count"})
                schedule_id = command.payload.get("scheduleId")
                if not isinstance(schedule_id, str) or not schedule_id:
                    raise GatewayError("invalid_schedule")
                preview_schedule = store.get(schedule_id)
                if preview_schedule is None:
                    raise GatewayError("schedule_not_found")
                count = command.payload.get("count", 5)
                if type(count) is not int or not 1 <= count <= 100:
                    raise GatewayError("invalid_limit")
                if preview_schedule.cron is None:
                    runs = [preview_schedule.at] if preview_schedule.at is not None else []
                else:
                    from agent_workspace.core.timezone_schedules import (
                        TimezoneSchedule,
                        timezone_schedule_preview,
                    )

                    preview = timezone_schedule_preview(
                        TimezoneSchedule(preview_schedule.cron, preview_schedule.timezone),
                        count=count,
                    )
                    runs = [item.isoformat() for item in preview.next_runs_utc]
                payload = {
                    "epoch": self.epoch,
                    "schedule": preview_schedule.to_document(),
                    "nextRuns": runs,
                }
            else:
                raise GatewayError("unsupported_command")
        except GatewayError:
            raise
        except (ScheduledTaskConfigError, OSError, ValueError, sqlite3.DatabaseError) as error:
            code = str(error)
            if "not found" in code:
                code = "schedule_not_found"
            elif "duplicated" in code:
                code = "schedule_exists"
            elif not code.startswith("invalid_"):
                code = "invalid_schedule"
            raise GatewayError(code) from None
        return self._reply(f"{command.type}.result", payload, session_id=command.session_id)

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

    def _terminal_scope(self, command: CommandEnvelope) -> None:
        self._require_configured()
        if command.session_id not in {None, self._selected_session_id}:
            raise GatewayError("invalid_session")
        if command.session_id is not None:
            self._require_selected_session(command.session_id)

    def _terminal_result(
        self,
        command: CommandEnvelope,
        future: Future[object] | None,
        response_type: str,
    ) -> GatewayReply:
        if future is None:
            raise GatewayError("runtime_unavailable")
        try:
            raw = future.result(timeout=_COMMAND_TIMEOUT_SECONDS)
        except TerminalSessionError as error:
            raise GatewayError(error.code) from None
        except TimeoutError:
            raise GatewayError("runtime_timeout") from None
        except Exception:
            raise GatewayError("runtime_unavailable") from None
        if not isinstance(raw, Mapping):
            raise GatewayError("runtime_unavailable")
        terminal = _bounded_projection(raw)
        if not isinstance(terminal, Mapping):
            raise GatewayError("runtime_unavailable")
        return self._reply(
            response_type,
            {"epoch": self.epoch, "terminal": dict(terminal)},
            session_id=command.session_id,
        )

    def _terminal_start(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(
            command,
            {"argv"},
            optional={"cwd", "owner", "deadlineSeconds", "maxOutputBytes"},
        )
        raw_argv = command.payload.get("argv")
        cwd = command.payload.get("cwd", ".")
        owner = command.payload.get("owner")
        deadline = command.payload.get("deadlineSeconds")
        max_output = command.payload.get("maxOutputBytes", 512 * 1024)
        if (
            not isinstance(raw_argv, list)
            or not raw_argv
            or len(raw_argv) > 256
            or any(not isinstance(item, str) or not item for item in raw_argv)
        ):
            raise GatewayError("invalid_argv")
        if not isinstance(cwd, str) or len(cwd) > 32_767:
            raise GatewayError("invalid_cwd")
        if owner is not None and (not isinstance(owner, str) or not owner.strip()):
            raise GatewayError("invalid_owner")
        if deadline is not None and (
            isinstance(deadline, bool)
            or not isinstance(deadline, (int, float))
            or deadline <= 0
            or deadline > 86_400
        ):
            raise GatewayError("invalid_deadline")
        if type(max_output) is not int or not 1 <= max_output <= 8 * 1024 * 1024:
            raise GatewayError("invalid_output_limit")
        future = self._require_host().request_terminal_start(
            tuple(raw_argv),
            cwd=cwd,
            owner=owner.strip() if isinstance(owner, str) else None,
            deadline=float(deadline) if deadline is not None else None,
            max_output_bytes=max_output,
        )
        return self._terminal_result(command, future, "terminal.start.result")

    def _terminal_input(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(command, {"terminalId", "data"}, optional={"owner"})
        terminal_id = command.payload.get("terminalId")
        data = command.payload.get("data")
        owner = command.payload.get("owner")
        if not isinstance(terminal_id, str) or not terminal_id:
            raise GatewayError("invalid_terminal")
        if not isinstance(data, str) or "\x00" in data or len(data.encode()) > 256 * 1024:
            raise GatewayError("invalid_input")
        if owner is not None and not isinstance(owner, str):
            raise GatewayError("invalid_owner")
        future = self._require_host().request_terminal_input(
            terminal_id, data, owner=owner if isinstance(owner, str) else None
        )
        return self._terminal_result(command, future, "terminal.input.result")

    def _terminal_resize(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(command, {"terminalId", "columns", "rows"}, optional={"owner"})
        terminal_id = command.payload.get("terminalId")
        columns = command.payload.get("columns")
        rows = command.payload.get("rows")
        owner = command.payload.get("owner")
        if not isinstance(terminal_id, str) or not terminal_id:
            raise GatewayError("invalid_terminal")
        if type(columns) is not int or not 1 <= columns <= 1000:
            raise GatewayError("invalid_resize")
        if type(rows) is not int or not 1 <= rows <= 1000:
            raise GatewayError("invalid_resize")
        future = self._require_host().request_terminal_resize(
            terminal_id,
            columns,
            rows,
            owner=owner if isinstance(owner, str) else None,
        )
        return self._terminal_result(command, future, "terminal.resize.result")

    def _terminal_status(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(command, {"terminalId"})
        terminal_id = command.payload.get("terminalId")
        if not isinstance(terminal_id, str) or not terminal_id:
            raise GatewayError("invalid_terminal")
        future = self._require_host().request_terminal_status(terminal_id)
        return self._terminal_result(command, future, "terminal.status.result")

    def _terminal_list(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(command, set(), optional={"limit"})
        limit = command.payload.get("limit", 32)
        if type(limit) is not int or not 1 <= limit <= 32:
            raise GatewayError("invalid_limit")
        future = self._require_host().request_terminal_list(limit)
        if future is None:
            raise GatewayError("runtime_unavailable")
        try:
            raw = future.result(timeout=_COMMAND_TIMEOUT_SECONDS)
        except TimeoutError:
            raise GatewayError("runtime_timeout") from None
        except Exception:
            raise GatewayError("runtime_unavailable") from None
        if not isinstance(raw, (list, tuple)):
            raise GatewayError("runtime_unavailable")
        terminals = _bounded_projection(list(raw[:limit]))
        if not isinstance(terminals, list):
            raise GatewayError("runtime_unavailable")
        return self._reply(
            "terminal.list.result",
            {"epoch": self.epoch, "terminals": terminals},
            session_id=command.session_id,
        )

    def _terminal_replay(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(command, {"terminalId"}, optional={"offset", "maxBytes"})
        terminal_id = command.payload.get("terminalId")
        offset = command.payload.get("offset", 0)
        max_bytes = command.payload.get("maxBytes")
        if not isinstance(terminal_id, str) or not terminal_id:
            raise GatewayError("invalid_terminal")
        if type(offset) is not int or offset < 0:
            raise GatewayError("invalid_offset")
        if max_bytes is not None and (
            type(max_bytes) is not int or not 1 <= max_bytes <= 8 * 1024 * 1024
        ):
            raise GatewayError("invalid_output_limit")
        future = self._require_host().request_terminal_replay(
            terminal_id, offset=offset, max_bytes=max_bytes
        )
        return self._terminal_result(command, future, "terminal.replay.result")

    def _terminal_stop(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(command, {"terminalId"}, optional={"owner", "reason"})
        terminal_id = command.payload.get("terminalId")
        owner = command.payload.get("owner")
        reason = command.payload.get("reason", "stopped")
        if not isinstance(terminal_id, str) or not terminal_id:
            raise GatewayError("invalid_terminal")
        if owner is not None and not isinstance(owner, str):
            raise GatewayError("invalid_owner")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 256:
            raise GatewayError("invalid_reason")
        future = self._require_host().request_terminal_stop(
            terminal_id,
            owner=owner if isinstance(owner, str) else None,
            reason=reason.strip(),
        )
        return self._terminal_result(command, future, "terminal.stop.result")

    def _selected_job(self, session_id: str | None, job_id: str) -> BackgroundJobStatus:
        assert session_id is not None
        try:
            with SQLiteEventStore(self._database) as store:
                status = store.get_background_job(session_id, job_id)
        except (OSError, ValueError):
            raise GatewayError("storage_unavailable") from None
        if status is None:
            raise GatewayError("unknown_job")
        return status

    @staticmethod
    def _job_document(status: object) -> dict[str, object]:
        safe = _json_safe(status)
        if not isinstance(safe, Mapping):
            raise GatewayError("runtime_unavailable")
        return {
            "jobId": safe.get("job_id", safe.get("jobId")),
            "sessionId": safe.get("session_id", safe.get("sessionId")),
            "label": safe.get("label"),
            "state": safe.get("state"),
            "createdAt": safe.get("created_at", safe.get("createdAt")),
            "updatedAt": safe.get("updated_at", safe.get("updatedAt")),
            "terminalReason": safe.get("terminal_reason", safe.get("terminalReason")),
        }

    def _dispatch_next_turn(self, session_id: str | None) -> bool:
        if self._host is None or self._active_turn is not None or self._turn_requested:
            return False

        attempts = 0
        max_attempts = len(self._queued_turns)
        while self._queued_turns and attempts < max_attempts:
            attempts += 1
            (
                next_turn_id,
                next_prompt,
                references,
                exclude_image_digests,
                reasoning_effort,
            ) = self._queued_turns.pop(0)
            try:
                images = self._queued_attachment_images(next_turn_id, session_id, references)
                if images:
                    self._require_image_provider()
                self._submit_host_turn(
                    next_prompt, exclude_image_digests, reasoning_effort, images=images
                )
            except (GatewayError, RuntimeError) as error:
                if self._selected_session_id is not None and self._database.is_file():
                    with suppress(Exception), SQLiteEventStore(self._database) as store:
                        store.mark_turn_state(next_turn_id, "failed")
                self._pending_host_events.append(
                    Event(
                        session_id=session_id or "desktop",
                        type="runtime.command_rejected",
                        data={
                            "reason": str(error)
                            if isinstance(error, GatewayError)
                            else "queued_turn_unavailable",
                            "turnId": next_turn_id,
                        },
                    )
                )
                continue
            else:
                self._active_turn = next_turn_id
                self._active_queue_id = next_turn_id
                self._turn_requested = True
                if self._selected_session_id is not None and self._database.is_file():
                    with suppress(Exception), SQLiteEventStore(self._database) as store:
                        store.mark_turn_state(next_turn_id, "running")
                return True

        return False

    def _optimize_prompt(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"prompt"}, optional={"providerId", "model"})
        self._require_selected_session(command.session_id, allow_unselected=True)
        prompt = command.payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > _MAX_PROMPT_CHARS:
            raise GatewayError("invalid_prompt")
        raw_provider_id = command.payload.get("providerId")
        raw_model = command.payload.get("model")
        if raw_provider_id is not None and not isinstance(raw_provider_id, str):
            raise GatewayError("invalid_provider")
        if raw_model is not None and (not isinstance(raw_model, str) or not raw_model.strip()):
            raise GatewayError("invalid_provider")
        host = self._host
        if host is None or self._runtime_state != "ready":
            raise GatewayError("runtime_unavailable")
        provider_config: ProviderConfig | None = None
        if raw_provider_id is not None:
            provider_id = self._provider_id(raw_provider_id)
            try:
                self._saved_provider(self._load_provider_settings(), provider_id)
                config = self._settings_store().resolve_config(provider_id)
            except (KeyError, OSError, ProviderSettingsError, ValueError):
                raise GatewayError("unknown_provider") from None
            if raw_model is not None:
                config = replace(config, model=raw_model.strip())
                config.validate()
            provider_config = config
        elif raw_model is not None:
            if self._provider is None:
                raise GatewayError("runtime_unavailable")
            provider_config = replace(self._provider, model=raw_model.strip())
            provider_config.validate()
        try:
            future = host.optimize_prompt(prompt, provider_config=provider_config)
            optimized = future.result(timeout=_PROVIDER_TEST_TIMEOUT_SECONDS)
        except TimeoutError:
            raise GatewayError("prompt_optimization_timeout") from None
        except GatewayError:
            raise
        except Exception as exc:
            code = str(exc).strip()
            if code == "runtime_busy":
                raise GatewayError("runtime_busy") from None
            if code in {"prompt_optimization_empty", "runtime_unavailable"}:
                raise GatewayError(code) from None
            raise GatewayError("prompt_optimization_failed") from exc
        active_provider = provider_config or host.settings.provider
        active_provider_id = active_provider.id
        active_model = active_provider.model
        return self._reply(
            "prompt.optimize.result",
            {
                "epoch": self.epoch,
                "optimizedPrompt": optimized,
                "providerId": active_provider_id,
                "model": active_model,
            },
            session_id=command.session_id,
        )

    def _start_turn(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(
            command,
            {"prompt"},
            optional={"attachmentPaths", "excludeImageDigests", "reasoningEffort"},
        )
        self._require_selected_session(command.session_id, allow_unselected=True)
        if command.session_id != self._host_session_id:
            raise GatewayError("session_not_active")
        prompt = command.payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > _MAX_PROMPT_CHARS:
            raise GatewayError("invalid_prompt")
        references = self._attachment_references(command.payload.get("attachmentPaths"))
        images = self._attachment_images(references)
        exclude_image_digests = self._excluded_image_digests(
            command.payload.get("excludeImageDigests")
        )
        reasoning_effort: str | None = None
        if "reasoningEffort" in command.payload:
            selected_effort = command.payload["reasoningEffort"]
            if not isinstance(selected_effort, str) or selected_effort not in {
                "off",
                "low",
                "medium",
                "high",
                "xhigh",
                "max",
            }:
                raise GatewayError("invalid_reasoning_effort")
            if (
                self._provider is None
                or selected_effort not in self._supported_turn_reasoning_efforts(self._provider)
            ):
                raise GatewayError("unsupported_reasoning_effort")
            reasoning_effort = selected_effort
        prompt = prompt.strip()
        if references:
            prompt = f"{prompt}\n\n" + "\n".join(f"[File reference: {path}]" for path in references)
        if self._active_turn is not None or self._turn_requested or len(self._queued_turns) > 0:
            if len(self._queued_turns) >= _MAX_TURN_QUEUE:
                raise GatewayError("turn_queue_full")
            turn_id = f"turn-{uuid4()}"
            if self._selected_session_id is not None and self._database.is_file():
                try:
                    with SQLiteEventStore(self._database) as store:
                        if references:
                            self._persist_queued_attachments(
                                store, turn_id, self._selected_session_id, references, images
                            )
                        store.enqueue_turn(
                            turn_id,
                            self._selected_session_id,
                            prompt,
                            references,
                            exclude_image_digests=exclude_image_digests,
                            reasoning_effort=reasoning_effort,
                        )
                except (OSError, sqlite3.DatabaseError, ValueError):
                    raise GatewayError("storage_unavailable") from None
            else:
                self._ephemeral_queued_images[turn_id] = images
            self._queued_turns.append(
                (turn_id, prompt, references, exclude_image_digests, reasoning_effort)
            )
            if self._active_turn is None and not self._turn_requested and not self._busy:
                self._dispatch_next_turn(self._selected_session_id)
            payload: dict[str, object] = {
                "epoch": self.epoch,
                "requested": False,
                "queued": True,
                "queuedCount": len(self._queued_turns),
            }
            if exclude_image_digests:
                payload["excludeImageDigests"] = sorted(exclude_image_digests)
            return self._reply("turn.start.result", payload)
        if self._busy:
            raise GatewayError("runtime_busy")
        self._require_host()
        try:
            self._submit_host_turn(
                prompt, exclude_image_digests, reasoning_effort, images=images
            )
        except RuntimeError:
            raise GatewayError("runtime_unavailable") from None
        self._turn_requested = True
        payload = {
            "epoch": self.epoch,
            "requested": True,
            "queuedCount": len(self._queued_turns),
        }
        if exclude_image_digests:
            payload["excludeImageDigests"] = sorted(exclude_image_digests)
        return self._reply("turn.start.result", payload)

    def _submit_host_turn(
        self,
        prompt: str,
        exclude_image_digests: frozenset[str],
        reasoning_effort: str | None = None,
        *,
        images: tuple[ImagePart, ...] = (),
    ) -> Future[None]:
        """Submit a turn while keeping legacy test hosts compatible.

        Older injected hosts only accepted ``submit_turn(prompt)``. Pass
        optional keywords only when requested so that call shape still works.
        """
        host = self._host
        if host is None:
            raise RuntimeError("runtime host is unavailable")
        if reasoning_effort is not None and (
            self._provider is None
            or reasoning_effort not in self._supported_turn_reasoning_efforts(self._provider)
        ):
            raise RuntimeError("provider does not support reasoning effort")
        kwargs: dict[str, Any] = {}
        if images:
            kwargs["images"] = images
        if exclude_image_digests:
            kwargs["exclude_image_digests"] = exclude_image_digests
        if reasoning_effort is not None:
            kwargs["reasoning_effort"] = reasoning_effort
        return host.submit_turn(prompt, **kwargs)

    @staticmethod
    def _excluded_image_digests(value: object) -> frozenset[str]:
        if value is None:
            return frozenset()
        if (
            not isinstance(value, list)
            or len(value) > _MAX_EXCLUDED_IMAGE_DIGESTS
            or not all(isinstance(item, str) for item in value)
        ):
            raise GatewayError("invalid_image_digest")
        digests: set[str] = set()
        for item in value:
            if re.fullmatch(r"[0-9a-fA-F]{64}", item) is None:
                raise GatewayError("invalid_image_digest")
            digests.add(item.lower())
        if len(digests) > _MAX_EXCLUDED_IMAGE_DIGESTS:
            raise GatewayError("invalid_image_digest")
        return frozenset(digests)

    def _attachment_references(self, value: object) -> list[str]:
        if value is None:
            return []
        if (
            not isinstance(value, list)
            or len(value) > _MAX_ATTACHMENTS
            or not all(isinstance(item, str) for item in value)
        ):
            raise GatewayError("invalid_attachment")
        if self._workspace is None:
            raise GatewayError("runtime_unconfigured")
        root = self._workspace.resolve()
        references: list[str] = []
        for raw in value:
            if not raw or "\x00" in raw:
                raise GatewayError("invalid_attachment")
            candidate = Path(raw)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise GatewayError("invalid_attachment")
            try:
                resolved = (root / candidate).resolve(strict=True)
                resolved.relative_to(root)
            except (OSError, RuntimeError, ValueError):
                raise GatewayError("invalid_attachment") from None
            if not resolved.is_file():
                raise GatewayError("invalid_attachment")
            references.append(resolved.relative_to(root).as_posix())
        return references

    def _attachment_images(self, references: list[str]) -> tuple[ImagePart, ...]:
        """Carry user-selected image bytes, while documents remain workspace references.

        Inspect the file signature so clipboard screenshots and files with an
        uninformative extension still reach the provider as visual content.
        Validate the opened file against the workspace boundary before reading.
        """
        if not references:
            return ()
        if self._workspace is None:
            raise GatewayError("runtime_unconfigured")
        try:
            paths = WorkspacePaths(self._workspace)
        except (OSError, RuntimeError, ValueError):
            raise GatewayError("invalid_attachment") from None
        root = paths.root
        images: list[ImagePart] = []
        for reference in references:
            try:
                path = paths.resolve(reference)
                path.resolve(strict=True).relative_to(root)
                if not path.is_file():
                    raise GatewayError("invalid_attachment")
                before = path.lstat()
                with _open_identity_checked(path, "rb") as stream:
                    self._verify_attachment_stream(paths, path, stream.fileno(), before)
                    prefix = stream.read(12)
                    media_type = self._attachment_image_media_type(prefix)
                    if media_type is None:
                        self._verify_attachment_stream(paths, path, stream.fileno(), before)
                        if path.suffix.casefold() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                            raise GatewayError("invalid_image_attachment")
                        if path.suffix.casefold() in {
                            ".bmp", ".tif", ".tiff", ".avif", ".heic", ".heif", ".ico"
                        }:
                            raise GatewayError("unsupported_image_type")
                        continue
                    if len(images) >= MAX_IMAGES_PER_MESSAGE:
                        raise GatewayError("too_many_image_attachments")
                    data = prefix + stream.read(MAX_IMAGE_BYTES + 1 - len(prefix))
                    self._verify_attachment_stream(paths, path, stream.fileno(), before)
            except (OSError, RuntimeError, ValueError) as error:
                if isinstance(error, GatewayError):
                    raise
                raise GatewayError("invalid_attachment") from None
            if len(data) > MAX_IMAGE_BYTES:
                raise GatewayError("image_attachment_too_large")
            images.append(ImagePart(media_type, data))
        if images:
            self._require_image_provider()
        return tuple(images)

    @staticmethod
    def _verify_attachment_stream(
        paths: WorkspacePaths, path: Path, descriptor: int, before: os.stat_result
    ) -> None:
        opened = WorkspacePaths.assert_safe_file_descriptor(descriptor, path)
        paths.resolve(path)
        path.resolve(strict=True).relative_to(paths.root)
        after = path.lstat()
        identity = (before.st_dev, before.st_ino)
        if (
            not stat.S_ISREG(opened.st_mode)
            or identity != (opened.st_dev, opened.st_ino)
            or identity != (after.st_dev, after.st_ino)
        ):
            raise GatewayError("invalid_attachment")

    @staticmethod
    def _persist_queued_attachments(
        store: SQLiteEventStore,
        turn_id: str,
        session_id: str,
        references: list[str],
        images: tuple[ImagePart, ...],
    ) -> None:
        """Persist the accepted visual content before admitting the queue row.

        The queue references stay compatible with existing databases. The
        snapshot and its image artifacts commit together; an accepted queued
        turn never needs to reopen its mutable image source to reconstruct them.
        """
        metadata = [
            {
                "media_type": image.media_type,
                "sha256": hashlib.sha256(image.data).hexdigest(),
                "bytes": len(image.data),
            }
            for image in images
        ]
        snapshot = Event(
            id=f"{turn_id}-attachments",
            session_id=session_id,
            type="turn.queued.attachments",
            data={"turn_id": turn_id, "references": references, "images": metadata},
            correlation_id=turn_id,
        )
        image_events = tuple(
            Event(
                session_id=session_id,
                type="image.attached",
                data={
                    **image_metadata,
                    "source": "user",
                    "attempt_id": turn_id,
                    "path": "user_attachment",
                    "queued_turn_id": turn_id,
                },
                correlation_id=turn_id,
                causation_id=snapshot.id,
            )
            for image_metadata in metadata
        )
        artifacts = tuple(
            BinaryArtifact(hashlib.sha256(image.data).hexdigest(), image.data) for image in images
        )
        store.append_many_with_artifacts((snapshot, *image_events), artifacts)

    def _queued_attachment_images(
        self, turn_id: str, session_id: str | None, references: list[str]
    ) -> tuple[ImagePart, ...]:
        if turn_id in self._ephemeral_queued_images:
            return self._ephemeral_queued_images.pop(turn_id)
        try:
            snapshot = SQLiteEventStore.get_event_read_only(
                self._database, f"{turn_id}-attachments"
            )
            if snapshot is None:
                # Queues admitted before attachment snapshots existed still
                # receive the same boundary and image checks as a fresh turn.
                return self._attachment_images(self._attachment_references(references))
            metadata = snapshot.data.get("images")
            if (
                snapshot.type != "turn.queued.attachments"
                or snapshot.session_id != session_id
                or snapshot.correlation_id != turn_id
                or snapshot.data.get("references") != references
                or not isinstance(metadata, list)
                or len(metadata) > MAX_IMAGES_PER_MESSAGE
            ):
                raise GatewayError("invalid_image_attachment")
            images: list[ImagePart] = []
            for entry in metadata:
                if not isinstance(entry, dict):
                    raise GatewayError("invalid_image_attachment")
                digest = entry.get("sha256")
                media_type = entry.get("media_type")
                if (
                    not isinstance(digest, str)
                    or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                    or not isinstance(media_type, str)
                ):
                    raise GatewayError("invalid_image_attachment")
                artifact = SQLiteEventStore.get_binary_artifact_read_only(self._database, digest)
                if (
                    artifact is None
                    or hashlib.sha256(artifact.content).hexdigest() != digest
                    or entry.get("bytes") != len(artifact.content)
                    or self._attachment_image_media_type(artifact.content[:12]) != media_type
                ):
                    raise GatewayError("invalid_image_attachment")
                images.append(ImagePart(media_type, artifact.content))
        except (OSError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        except ValueError as error:
            if isinstance(error, GatewayError):
                raise
            raise GatewayError("invalid_image_attachment") from None
        return tuple(images)

    @staticmethod
    def _attachment_image_media_type(prefix: bytes) -> str | None:
        if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if prefix.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if prefix.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP":
            return "image/webp"
        return None

    def _require_image_provider(self) -> None:
        provider = self._provider
        if provider is None:
            raise GatewayError("runtime_unavailable")
        # Official DeepSeek vision is available in Flash; documented text-only
        # models must not be allowed to appear to accept a pasted screenshot.
        # Unknown gateways/models are attempted with real image content, and
        # their provider rejection is surfaced without silently dropping images.
        if urlsplit(provider.base_url).hostname == "api.deepseek.com":
            model = provider.model.casefold()
            if model.startswith(("deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner")):
                raise GatewayError("unsupported_image_input")

    def _steer_turn(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured(allow_awaiting_approval=True)
        self._require_payload(
            command, {"prompt", "turnId"}, optional={"attachmentPaths", "inputId"}
        )
        self._require_selected_session(command.session_id)
        if command.session_id != self._host_session_id:
            raise GatewayError("session_not_active")
        session_id = command.session_id
        if session_id is None:
            raise GatewayError("invalid_session")
        prompt = command.payload.get("prompt")
        turn_id = command.payload.get("turnId")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > _MAX_PROMPT_CHARS:
            raise GatewayError("invalid_prompt")
        if not isinstance(turn_id, str) or not turn_id or len(turn_id) > 256:
            raise GatewayError("turn_not_active")
        input_id = command.payload.get("inputId", str(uuid4()))
        if (
            not isinstance(input_id, str)
            or not input_id
            or len(input_id) > 128
            or any(not (char.isascii() and (char.isalnum() or char in "-_.")) for char in input_id)
        ):
            raise GatewayError("invalid_turn_input_id")
        references = self._attachment_references(command.payload.get("attachmentPaths"))
        images = self._attachment_images(references)
        prompt = prompt.strip()
        if references:
            prompt += "\n\n" + "\n".join(f"[File reference: {path}]" for path in references)
        # A lost acknowledgement may be retried after the task has already
        # completed. The durable receipt is authoritative in that case too.
        if self._turn_input_received(input_id, session_id, turn_id, prompt, images=images):
            return self._reply(
                "turn.steer.result",
                {"epoch": self.epoch, "accepted": True, "inputId": input_id, "turnId": turn_id},
            )
        if turn_id != self._active_turn:
            raise GatewayError("turn_not_active")
        try:
            host = self._require_host(allow_awaiting_approval=True)
            if images:
                future = host.steer_turn(
                    session_id, prompt, turn_id, input_id=input_id, images=images
                )
            else:
                future = host.steer_turn(session_id, prompt, turn_id, input_id=input_id)
            input_id = future.result(timeout=_COMMAND_TIMEOUT_SECONDS)
        except (RuntimeError, ValueError) as error:
            code = str(error)
            known = {"turn_not_active", "turn_input_full", "invalid_prompt", "turn_input_conflict"}
            raise GatewayError(code if code in known else "runtime_unavailable") from None
        except TimeoutError:
            future.cancel()
            if not self._turn_input_received(input_id, session_id, turn_id, prompt, images=images):
                raise GatewayError("turn_input_timeout") from None
        return self._reply(
            "turn.steer.result",
            {"epoch": self.epoch, "accepted": True, "inputId": input_id, "turnId": turn_id},
        )

    def _turn_input_received(
        self,
        input_id: str,
        session_id: str,
        turn_id: str,
        prompt: str,
        *,
        images: tuple[ImagePart, ...] = (),
    ) -> bool:
        try:
            received = SQLiteEventStore.get_event_read_only(self._database, input_id)
        except (OSError, ValueError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        if received is None:
            return False
        if (
            received.type != "turn.input.received"
            or received.session_id != session_id
            or received.correlation_id != turn_id
            or received.data.get("prompt") != prompt
            or received.data.get("images", [])
            != [
                {
                    "media_type": image.media_type,
                    "sha256": hashlib.sha256(image.data).hexdigest(),
                    "bytes": len(image.data),
                }
                for image in images
            ]
        ):
            raise GatewayError("turn_input_conflict")
        return True

    def _cancel_turn(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, set(), optional={"turnId"})
        self._require_selected_session(command.session_id, allow_unselected=True)
        turn_id = command.payload.get("turnId")
        if "turnId" in command.payload:
            if not isinstance(turn_id, str) or not turn_id:
                raise GatewayError("invalid_turn")
            if turn_id != self._active_turn:
                raise GatewayError("turn_not_active")
        requested = self._busy or len(self._queued_turns) > 0
        future = self._require_host().request_cancel_turn()
        if future is None:
            raise GatewayError("runtime_unavailable")
        if requested:
            if self._selected_session_id is not None and self._database.is_file():
                with suppress(Exception), SQLiteEventStore(self._database) as store:
                    store.clear_queued_turns(self._selected_session_id)
            self._queued_turns.clear()
            self._ephemeral_queued_images.clear()
        return self._reply(
            "turn.cancel.result",
            {"epoch": self.epoch, "requested": requested, "queuedCount": 0},
        )

    def _set_mode(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"mode"})
        self._require_selected_session(command.session_id, allow_unselected=True)
        if command.session_id != self._host_session_id:
            raise GatewayError("session_not_active")
        raw_mode = command.payload.get("mode")
        try:
            mode = Mode(cast(str, raw_mode))
        except (TypeError, ValueError):
            raise GatewayError("invalid_mode") from None
        future = self._require_host().request_mode(mode)
        if future is None:
            raise GatewayError("runtime_unavailable")
        return self._reply(
            "runtime.mode.set.result",
            {"epoch": self.epoch, "queued": True, "mode": mode.value},
        )

    def _set_autonomy(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"autonomy"})
        raw_autonomy = command.payload.get("autonomy")
        try:
            autonomy = Autonomy(cast(str, raw_autonomy))
        except (TypeError, ValueError):
            raise GatewayError("invalid_autonomy") from None
        if self._runtime_state == "switching":
            if self._workspace is None or self._provider is None:
                raise GatewayError("runtime_unconfigured")
            if command.session_id is None:
                raise GatewayError("invalid_session")
            self._require_selected_session(command.session_id)
            previous = self._autonomy
            if autonomy is not previous:
                try:
                    with SQLiteEventStore(self._database) as store:
                        store.append(
                            Event(
                                session_id=command.session_id,
                                type="autonomy.changed",
                                data={
                                    "from_autonomy": previous.value,
                                    "to_autonomy": autonomy.value,
                                },
                            )
                        )
                except (OSError, sqlite3.DatabaseError, ValueError):
                    raise GatewayError("storage_unavailable") from None
            self._pending_autonomy_request = (command.session_id, autonomy)
            return self._reply(
                "runtime.autonomy.set.result",
                {
                    "epoch": self.epoch,
                    "applied": False,
                    "pending": True,
                    "autonomy": autonomy.value,
                    "restarted": True,
                },
                session_id=command.session_id,
            )
        self._require_configured()
        if command.session_id is None:
            raise GatewayError("invalid_session")
        self._require_selected_session(command.session_id)
        if command.session_id != self._host_session_id:
            raise GatewayError("session_not_active")
        if self._busy:
            raise GatewayError("runtime_busy")
        previous = self._autonomy
        if autonomy is previous:
            return self._reply(
                "runtime.autonomy.set.result",
                {
                    "epoch": self.epoch,
                    "applied": True,
                    "autonomy": autonomy.value,
                    "restarted": False,
                },
                session_id=command.session_id,
            )

        assert self._workspace is not None
        assert self._provider is not None
        assert command.session_id is not None
        try:
            with SQLiteEventStore(self._database) as store:
                changed = store.append(
                    Event(
                        session_id=command.session_id,
                        type="autonomy.changed",
                        data={
                            "from_autonomy": previous.value,
                            "to_autonomy": autonomy.value,
                        },
                    )
                )
        except (OSError, sqlite3.DatabaseError, ValueError):
            raise GatewayError("storage_unavailable") from None

        if isinstance(self._host, RuntimeHost):
            self._autonomy = autonomy
            self._autonomy_apply_pending = True
            self._runtime_state = "switching"
            self._autonomy_switch_generation += 1
            generation = self._autonomy_switch_generation
            self._pending_host_events.append(
                Event(
                    session_id=command.session_id,
                    type="runtime.autonomy_pending",
                    data={"autonomy": autonomy.value},
                )
            )
            worker = threading.Thread(
                target=self._apply_autonomy_in_background,
                args=(command.session_id, previous, autonomy, changed, generation),
                name="autonomy-switch",
                daemon=True,
            )
            self._autonomy_switch_thread = worker
            worker.start()
            return self._reply(
                "runtime.autonomy.set.result",
                {
                    "epoch": self.epoch,
                    "applied": False,
                    "pending": True,
                    "autonomy": autonomy.value,
                    "restarted": True,
                },
                session_id=command.session_id,
            )

        deadline = self._clock() + _LIFECYCLE_TIMEOUT_SECONDS
        self._autonomy = autonomy
        try:
            self._stop_host(deadline=deadline)
            self._pending_host_events.append(
                Event(
                    session_id=command.session_id,
                    type="runtime.autonomy_pending",
                    data={"autonomy": autonomy.value},
                )
            )
            self._start_host(session_id=command.session_id, deadline=deadline)
            self._restore_queued_turns(command.session_id)
        except GatewayError:
            if self._host is not None:
                with suppress(GatewayError):
                    self._stop_host()
            try:
                with SQLiteEventStore(self._database) as store:
                    store.append(
                        Event(
                            session_id=command.session_id,
                            type="autonomy.changed",
                            data={
                                "from_autonomy": autonomy.value,
                                "to_autonomy": previous.value,
                            },
                        )
                    )
            except (OSError, sqlite3.DatabaseError, ValueError):
                self._runtime_state = "failed"
                raise GatewayError("storage_unavailable") from None
            self._autonomy = previous
            try:
                self._start_host(session_id=command.session_id)
                self._restore_queued_turns(command.session_id)
            except GatewayError:
                self._runtime_state = "failed"
            raise GatewayError("runtime_start_failed") from None

        self._pending_host_events.extend(
            (
                changed,
                Event(
                    session_id=command.session_id,
                    type="runtime.autonomy_applied",
                    data={"autonomy": autonomy.value},
                ),
            )
        )
        return self._reply(
            "runtime.autonomy.set.result",
            {
                "epoch": self.epoch,
                "applied": True,
                "autonomy": autonomy.value,
                "restarted": True,
            },
            session_id=command.session_id,
        )

    def _resolve_approval(self, command: CommandEnvelope) -> GatewayReply:
        self._require_workspace_provider()
        self._require_payload(command, {"requestId", "scope"})
        request_id = command.payload.get("requestId")
        raw_scope = command.payload.get("scope")
        if not isinstance(request_id, str) or not request_id:
            raise GatewayError("invalid_approval")
        if raw_scope is not None:
            try:
                scope: ApprovalScope | None = ApprovalScope(cast(str, raw_scope))
            except (TypeError, ValueError):
                raise GatewayError("invalid_approval") from None
        else:
            scope = None
        entry = self._approval_ledger.get(request_id)
        if entry is None:
            raise GatewayError("unknown_approval")
        if entry.state == "resolved":
            raise GatewayError("approval_already_resolved")
        if entry.state == "resolving":
            raise GatewayError("approval_resolution_pending")
        if scope is ApprovalScope.SESSION and entry.payload.get("supportsSessionScope") is not True:
            raise GatewayError("invalid_approval")
        if command.session_id != entry.session_id and not (
            entry.run_id is not None and command.session_id == self._selected_session_id
        ):
            raise GatewayError("invalid_session")
        entry.state = "resolving"
        entry.resolution_scope = scope
        try:
            target_host = entry.source_host or self._require_host(allow_awaiting_approval=True)
            future = target_host.resolve_approval(request_id, scope)
        except Exception:
            entry.state = "pending"
            entry.resolution_scope = None
            raise GatewayError("runtime_unavailable") from None
        if future is None:
            entry.state = "pending"
            entry.resolution_scope = None
            raise GatewayError("runtime_unavailable")
        entry.resolution = future
        try:
            future.result(timeout=_COMMAND_TIMEOUT_SECONDS)
        except TimeoutError:
            if future.cancel():
                entry.state = "pending"
                entry.resolution = None
                entry.resolution_scope = None
            else:
                future.add_done_callback(
                    lambda completed: self._settle_approval_resolution(request_id, entry, completed)
                )
            raise GatewayError("runtime_unavailable") from None
        except Exception:
            entry.state = "pending"
            entry.resolution = None
            entry.resolution_scope = None
            raise GatewayError("runtime_unavailable") from None
        self._commit_approval_resolution(request_id, entry, scope)
        self._collect_host_events()
        return self._reply(
            "approval.resolve.result",
            {"epoch": self.epoch, "resolved": True},
            session_id=entry.session_id,
        )

    def _settle_approval_resolution(
        self, request_id: str, entry: _ApprovalEntry, future: Future[None]
    ) -> None:
        with self._lock:
            if (
                self._approval_ledger.get(request_id) is not entry
                or entry.state != "resolving"
                or entry.resolution is not future
            ):
                return
            try:
                future.result()
            except Exception:
                if entry.turn_terminal:
                    del self._approval_ledger[request_id]
                else:
                    entry.state = "pending"
                    entry.resolution = None
                    entry.resolution_scope = None
                return
            self._commit_approval_resolution(request_id, entry, entry.resolution_scope)

    def _commit_approval_resolution(
        self, request_id: str, entry: _ApprovalEntry, scope: ApprovalScope | None
    ) -> None:
        entry.state = "resolved"
        entry.resolution = None
        entry.resolution_scope = scope
        self._pending_host_events.append(
            Event(
                session_id=entry.session_id or "desktop",
                type="approval.resolved",
                data={
                    "request_id": request_id,
                    "allowed": scope is not None,
                    "scope": scope.value if scope is not None else None,
                },
            )
        )
        if entry.run_id is not None:
            with suppress(Exception):
                self._control_service().resolve_attention_by_source(
                    f"approval:{request_id}",
                    resolution={
                        "allowed": scope is not None,
                        "scope": scope.value if scope is not None else None,
                    },
                )
        if entry.turn_terminal:
            del self._approval_ledger[request_id]

    def _start_host(self, *, session_id: str | None, deadline: float | None = None) -> None:
        with self._lock:
            if self._closing:
                raise GatewayError("runtime_unavailable")
            assert self._workspace is not None and self._provider is not None
            deadline = deadline or self._clock() + min(
                _START_TIMEOUT_SECONDS, _LIFECYCLE_TIMEOUT_SECONDS
            )
            settings = RuntimeSettings(
                workspace=self._workspace,
                database=self._database,
                provider=self._provider,
                mode=self._mode,
                autonomy=self._autonomy,
                session_id=session_id,
                writer_lock_group=self._writer_lock_group,
            )
        host: Host | None = None
        try:
            host = self._host_factory(settings)
            with self._lock:
                if self._closing:
                    raise GatewayError("runtime_unavailable")
                self._host = host
                self._host_session_id = session_id
                self._runtime_state = "starting"
            with self._host_startup_lock:
                self._host_startup_outcomes.pop(id(host), None)
            host.start()
            # Startup events can be drained by the UI while this lifecycle
            # worker is waiting. ``_queue_host_events`` records startup
            # outcomes for the current host so this waiter cannot lose the
            # marker to another consumer.
            while self._clock() < deadline:
                events = host.drain_display_events()
                with self._lock:
                    self._queue_host_events(events, source_host=host)
                    with self._host_startup_lock:
                        startup_outcome = self._host_startup_outcomes.get(id(host))
                    if (
                        any(event.type == "runtime.failed" for event in events)
                        or startup_outcome == "runtime.failed"
                    ):
                        raise GatewayError("runtime_start_failed")
                    if (
                        any(event.type == "runtime.started" for event in events)
                        or startup_outcome == "runtime.started"
                    ):
                        self._runtime_state = (
                            "switching" if self._autonomy_apply_pending else "ready"
                        )
                        return
                    if any(event.type == "approval.requested" for event in events):
                        self._runtime_state = "awaiting_extension_approval"
                        return
                if not host.is_alive():
                    break
                self._sleeper(min(0.01, max(0.0, deadline - self._clock())))
        except Exception:
            self._runtime_state = "failed"
            cleanup_failed = False
            if host is not None and self._host is host:
                try:
                    self._stop_host(deadline=deadline)
                except Exception:
                    cleanup_failed = True
            self._runtime_state = "stopping" if cleanup_failed else "failed"
            raise GatewayError("runtime_start_failed") from None
        self._runtime_state = "failed"
        cleanup_failed = False
        try:
            self._stop_host(deadline=deadline)
        except Exception:
            cleanup_failed = True
        self._runtime_state = "stopping" if cleanup_failed else "failed"
        raise GatewayError("runtime_start_failed")

    def _replace_host(
        self,
        *,
        workspace: Path,
        provider: ProviderConfig,
        session_id: str | None,
        mode: Mode,
        deadline: float,
        autonomy: Autonomy | None = None,
    ) -> None:
        with self._lifecycle_lock:
            self._replace_host_unlocked(
                workspace=workspace,
                provider=provider,
                session_id=session_id,
                mode=mode,
                deadline=deadline,
                autonomy=autonomy,
            )

    def _replace_host_unlocked(
        self,
        *,
        workspace: Path,
        provider: ProviderConfig,
        session_id: str | None,
        mode: Mode,
        deadline: float,
        autonomy: Autonomy | None = None,
    ) -> None:
        with self._lock:
            previous_workspace = self._workspace
            previous_provider = self._provider
            previous_session_id = self._selected_session_id
            previous_host_session_id = self._host_session_id
            previous_mode = self._mode
            previous_autonomy = self._autonomy
        self._stop_host_for_lifecycle(deadline=deadline, preserve_session=True)
        with self._lock:
            if self._closing:
                raise GatewayError("runtime_unavailable")
            if self._resume_session_host(session_id):
                return
            self._workspace = workspace
            self._provider = provider
            self._selected_session_id = session_id
            self._mode = mode
            if autonomy is not None:
                self._autonomy = autonomy
        try:
            self._start_host(session_id=session_id, deadline=deadline)
            self._restore_queued_turns(session_id)
            return
        except GatewayError:
            if self._host is not None:
                try:
                    self._stop_host()
                except GatewayError:
                    raise GatewayError("runtime_start_failed") from None
            self._autonomy = previous_autonomy
            self._restore_host_state(
                previous_workspace,
                previous_provider,
                previous_host_session_id,
                previous_mode,
                selected_session_id=previous_session_id,
            )
            raise GatewayError("runtime_start_failed") from None

    def _restore_host_state(
        self,
        workspace: Path | None,
        provider: ProviderConfig | None,
        session_id: str | None,
        mode: Mode,
        *,
        selected_session_id: str | object | None = _CURRENT_SESSION,
    ) -> None:
        with self._lock:
            if self._resume_session_host(session_id):
                if selected_session_id is not _CURRENT_SESSION:
                    self._selected_session_id = cast(str | None, selected_session_id)
                return
            self._workspace = workspace
            self._provider = provider
            self._selected_session_id = (
                session_id
                if selected_session_id is _CURRENT_SESSION
                else cast(str | None, selected_session_id)
            )
            self._mode = mode
        if workspace is None or provider is None:
            self._host = None
            self._host_session_id = None
            self._runtime_state = "unconfigured"
            self._restore_queued_turns(None)
            return
        try:
            self._start_host(session_id=session_id)
            self._restore_queued_turns(session_id)
        except GatewayError:
            raise GatewayError("runtime_start_failed") from None

    def _stop_host_for_lifecycle(
        self, *, deadline: float | None = None, preserve_session: bool = False
    ) -> None:
        if preserve_session and self._park_session_host():
            return
        previous = self._skip_backup_next_stop
        self._skip_backup_next_stop = True
        try:
            self._stop_host(deadline=deadline)
        finally:
            self._skip_backup_next_stop = previous

    def _stop_host(self, *, deadline: float | None = None) -> None:
        deadline = deadline or self._clock() + _LIFECYCLE_TIMEOUT_SECONDS
        with self._lock:
            skip_backup = self._skip_backup_next_stop
            self._skip_backup_next_stop = False
            host = self._host
        if host is not None:
            if hasattr(host, "_create_backup_on_shutdown"):
                future = cast(RuntimeHost, host).request_shutdown(create_backup=not skip_backup)
            else:
                future = host.request_shutdown()
            if future is not None:
                with suppress(Exception):
                    future.result(timeout=max(0.0, deadline - self._clock()))
            host.join(timeout=max(0.0, deadline - self._clock()))
            if host.is_alive():
                with self._lock:
                    self._runtime_state = "stopping"
                raise GatewayError("runtime_shutdown_failed")
        with self._lock:
            self._host = None
            self._host_session_id = None
            self._approval_ledger = {
                request_id: entry
                for request_id, entry in self._approval_ledger.items()
                if entry.run_id is not None or (
                    entry.source_host is not None and entry.source_host is not host
                )
            }
            self._active_turn = None
            self._turn_requested = False
            self._active_queue_id = None
            self._turn_to_queue_id.clear()
            if self._workspace is None:
                self._runtime_state = "unconfigured"
            elif host is not None:
                self._runtime_state = "stopped"

    def _stop_session_hosts(self, *, deadline: float | None = None) -> None:
        deadline = deadline or self._clock() + _LIFECYCLE_TIMEOUT_SECONDS
        contexts = list(self._session_hosts.values())
        for context in contexts:
            host = context.host
            if host is None:
                continue
            if isinstance(host, RuntimeHost):
                host.request_shutdown(create_backup=False)
            else:
                host.request_shutdown()
        for context in contexts:
            if context.host is not None:
                context.host.join(timeout=max(0.0, deadline - self._clock()))
        self._session_hosts = {
            session_id: context for session_id, context in self._session_hosts.items()
            if context.host is not None and context.host.is_alive()
        }

    def _stop_run_hosts(self, *, deadline: float | None = None) -> None:
        deadline = deadline or self._clock() + _LIFECYCLE_TIMEOUT_SECONDS
        self._run_cancel_requested.update(self._run_preparing)
        for entry in list(self._run_hosts.values()):
            future = entry.host.request_shutdown()
            if future is not None:
                with suppress(Exception):
                    future.result(timeout=max(0.0, deadline - self._clock()))
        for entry in list(self._run_hosts.values()):
            entry.host.join(timeout=max(0.0, deadline - self._clock()))
        # Preparation workers acquire ``self._lock`` when they publish the host.
        # This method is called while that lock is held, so joining them here can
        # deadlock application shutdown. They are daemon threads and observe the
        # cancellation set before publishing a host.
        self._run_hosts = {
            run_id: entry for run_id, entry in self._run_hosts.items() if entry.host.is_alive()
        }
        self._run_preparing.intersection_update(self._run_prepare_threads)

    def _event_document(self, event: Event) -> dict[str, object]:
        try:
            payload = self._event_payload(event)
        except GatewayError:
            return self._truncation_document(event.session_id, "event payload is not display safe")
        if event.type == "runtime.display_truncated":
            payload["resyncRequired"] = True
        wire_type = event.type
        if event.type in _COMPACT_CHANGE_EVENTS:
            wire_type = "changes.updated"
            payload = {
                key: payload[key]
                for key in (
                    "epoch",
                    "changesetId",
                    "domainSequence",
                    "eventId",
                    "createdAt",
                    "correlationId",
                    "causationId",
                )
                if key in payload
            }
        elif event.type.startswith("background.job."):
            payload = {
                key: payload[key]
                for key in (
                    "epoch",
                    "jobId",
                    "label",
                    "reason",
                    "domainSequence",
                    "eventId",
                    "createdAt",
                    "correlationId",
                    "causationId",
                )
                if key in payload
            }
            payload["state"] = event.type.removeprefix("background.job.")
        sequence = self._take_sequence()
        document: dict[str, object] = {
            "v": PROTOCOL_VERSION,
            "kind": "event",
            "type": wire_type,
            "payload": payload,
            "sessionId": None if event.session_id == "desktop" else event.session_id,
            "sequence": sequence,
        }
        try:
            encode_message(document)
        except ProtocolError:
            return self._truncation_document(
                event.session_id, "event payload exceeds the wire limit", sequence=sequence
            )
        return document

    def _collect_host_events(self) -> None:
        host = self._host
        if host is not None:
            events = host.drain_display_events()
            host_alive = host.is_alive()
            if not host_alive and self._runtime_state == "stopping":
                # A shutdown timeout is recoverable: the old host may finish
                # closing after the lifecycle worker returned. Detach it before
                # projecting its lifecycle events so a late runtime.stopped or
                # runtime.failed cannot overwrite the replacement state.
                self._host = None
                self._host_session_id = None
                self._approval_ledger = {
                    request_id: entry
                    for request_id, entry in self._approval_ledger.items()
                    if entry.run_id is not None or (
                        entry.source_host is not None and entry.source_host is not host
                    )
                }
                self._active_turn = None
                self._turn_requested = False
                self._active_queue_id = None
                self._turn_to_queue_id.clear()
                self._runtime_state = "stopped" if self._workspace is not None else "unconfigured"
            self._queue_host_events(events, source_host=host)
            # ``Thread.start()`` returns before the new thread has assigned an
            # ident.  During that tiny window ``is_alive()`` is false even
            # though startup is progressing; detaching the host here makes an
            # asynchronous workspace switch race its own first event and
            # permanently report ``failed``.  Only classify a dead host as a
            # startup failure once the thread has actually started.
            host_started = getattr(host, "ident", True) is not None
            if (
                not host_alive
                and host_started
                and self._runtime_state
                in (
                    "starting",
                    "awaiting_extension_approval",
                )
            ):
                self._host = None
                self._host_session_id = None
                self._runtime_state = "failed"
            if not host_alive and self._pending_session_activation_id is not None:
                self._activate_pending_session_if_idle()

        for run_id, entry in list(self._run_hosts.items()):
            try:
                events = entry.host.drain_display_events()
            except Exception as error:
                events = []
                if not entry.terminal:
                    self._fail_agent_run(run_id, entry, "runtime_event_stream_failed", error)
            self._queue_host_events(events, source_host=entry.host, run_id=run_id)
            if not entry.host.is_alive():
                if not entry.terminal:
                    self._fail_agent_run(
                        run_id,
                        entry,
                        "runtime_stopped_unexpectedly",
                        RuntimeError(
                            "The runtime stopped before the run reached a terminal state."
                        ),
                    )
                self._run_hosts.pop(run_id, None)

        for session_id, context in list(self._session_hosts.items()):
            host = context.host
            if host is None:
                continue
            try:
                events = host.drain_display_events()
            except Exception:
                events = [Event(
                    session_id=session_id, type="runtime.failed",
                    data={"reason": "runtime event stream failed"},
                )]
            self._queue_host_events(events, source_host=host)
            if not host.is_alive():
                with self._session_host_scope(context):
                    self._clear_turn_state_after_runtime_failure(session_id)
                self._session_hosts.pop(session_id, None)

    def _queue_host_events(
        self,
        events: list[Event],
        *,
        source_host: Host | None = None,
        run_id: str | None = None,
    ) -> None:
        for event in events:
            session_context = next(
                (item for item in self._session_hosts.values() if item.host is source_host),
                None,
            ) if run_id is None and source_host is not None else None
            if (
                run_id is None
                and source_host is not None
                and source_host is self._host
                and event.type in {"runtime.started", "runtime.failed"}
            ):
                with self._host_startup_lock:
                    self._host_startup_outcomes[id(source_host)] = event.type
            if (
                run_id is None
                and source_host is not None
                and source_host is not self._host
                and session_context is None
                and event.type in _HOST_LIFECYCLE_EVENTS
            ):
                # The old host may still have buffered lifecycle events while
                # a replacement host is already active. Do not expose those
                # stale events to the UI; they describe a host that is no
                # longer authoritative.
                continue
            display_event = event
            if run_id is not None:
                display_event = Event(
                    session_id=event.session_id,
                    type=event.type,
                    data={**event.data, "run_id": run_id},
                    id=event.id,
                    schema_version=event.schema_version,
                    sequence=event.sequence,
                    causation_id=event.causation_id,
                    correlation_id=event.correlation_id,
                    created_at=event.created_at,
                )
            try:
                payload = self._event_payload(display_event)
            except GatewayError:
                pass
            else:
                self._project_event(
                    event.type,
                    payload,
                    event.session_id,
                    source_host=source_host,
                    run_id=run_id,
                )
            self._pending_host_events.append(display_event)

    def _event_payload(self, event: Event) -> dict[str, object]:
        if event.type == "approval.requested":
            payload: dict[str, object] = {}
            run_id = event.data.get("run_id")
            if isinstance(run_id, str):
                payload["runId"] = _bounded_text(run_id)
            request_id = event.data.get("request_id", event.data.get("requestId"))
            if isinstance(request_id, str):
                payload["requestId"] = _bounded_text(request_id)
            tool = event.data.get("tool") or event.data.get("toolName") or event.data.get("name")
            safe_tool = _approval_display_text(tool)
            if safe_tool:
                payload["tool"] = safe_tool
            scope = event.data.get("supports_session_scope", event.data.get("supportsSessionScope"))
            if isinstance(scope, bool):
                payload["supportsSessionScope"] = scope
            summary = _approval_summary(event.data)
            if summary:
                payload["summary"] = summary
        elif event.type in _COMPACT_CHANGE_EVENTS or event.type.startswith("background.job."):
            fields = (
                (("changeset_id", "changesetId"),)
                if event.type in _COMPACT_CHANGE_EVENTS
                else (
                    ("job_id", "jobId"),
                    ("label", "label"),
                    ("reason", "reason"),
                )
            )
            payload = {}
            for source, target in fields:
                if source not in event.data:
                    continue
                payload[target] = _bounded_scalar(event.data[source])
        else:
            # A display delta is already durable in the event store. If a
            # defensive test double or an extension hands the gateway one
            # enormous chunk, keep the sequence alive and send a bounded
            # preview instead of replacing the event with a global resync
            # boundary. RuntimeHost normally splits these before this point.
            raw_data = dict(event.data)
            raw_text = raw_data.get("text")
            display_truncated = (
                event.type == "model.output.delta"
                and isinstance(raw_text, str)
                and len(raw_text) > _MAX_STRING_CHARS
            )
            if display_truncated and isinstance(raw_text, str):
                raw_data["text"] = raw_text[:_MAX_STRING_CHARS]
            safe_data = cast(
                dict[str, object],
                _json_safe(
                    raw_data,
                    max_string_chars=(
                        _HISTORY_ASSISTANT_ENTRY_BYTES
                        if event.type == "message.created" and event.data.get("role") == "assistant"
                        else _MAX_STRING_CHARS
                    ),
                ),
            )
            payload = {_camel_case(key): value for key, value in safe_data.items()}
            if display_truncated and isinstance(raw_text, str):
                payload["displayTruncated"] = True
                payload["displayBytes"] = len(raw_text.encode("utf-8"))
        payload["epoch"] = self.epoch
        if event.sequence is not None:
            payload["domainSequence"] = event.sequence
        payload["eventId"] = event.id
        payload["createdAt"] = event.created_at
        if event.correlation_id is not None:
            payload["correlationId"] = event.correlation_id
        if event.causation_id is not None:
            payload["causationId"] = event.causation_id
        if event.type in _TERMINAL_TURN_EVENTS or event.type == "turn.started":
            payload["queuedCount"] = self._session_queued_count(event.session_id)
        if event.type == "runtime.display_truncated":
            payload["resyncRequired"] = True
        return payload

    def _clear_turn_state_after_runtime_failure(self, session_id: str) -> None:
        """Release turn state when a host dies before emitting a terminal turn event."""

        active_turn = self._active_turn
        queued_ids = [turn_id for turn_id, *_rest in self._queued_turns]
        if self._active_queue_id is not None:
            queued_ids.append(self._active_queue_id)
        if active_turn is not None:
            queued_ids.append(active_turn)

        self._active_turn = None
        self._turn_requested = False
        self._active_queue_id = None
        self._turn_to_queue_id.clear()
        self._queued_turns.clear()
        self._ephemeral_queued_images.clear()

        terminal_session = None if session_id == "desktop" else session_id
        if terminal_session is not None and self._database.is_file():
            with suppress(Exception), SQLiteEventStore(self._database) as store:
                for turn_id in dict.fromkeys(queued_ids):
                    store.mark_turn_state(turn_id, "failed")
                store.clear_queued_turns(terminal_session)

        for request_id in [
            key
            for key, entry in self._approval_ledger.items()
            if entry.session_id in {session_id, None} and (
                entry.source_host is self._host or entry.source_host is None
            )
        ]:
            del self._approval_ledger[request_id]

    def _truncation_document(
        self, session_id: str, reason: str, *, sequence: int | None = None
    ) -> dict[str, object]:
        return {
            "v": PROTOCOL_VERSION,
            "kind": "event",
            "type": "runtime.display_truncated",
            "payload": {
                "epoch": self.epoch,
                "reason": reason,
                "resyncRequired": True,
            },
            "sessionId": None if session_id == "desktop" else session_id,
            "sequence": self._take_sequence() if sequence is None else sequence,
        }

    def _project_event(
        self,
        event_type: str,
        payload: Mapping[str, object],
        session_id: str,
        *,
        source_host: Host | None = None,
        run_id: str | None = None,
    ) -> None:
        if run_id is not None:
            self._project_agent_run_event(
                run_id,
                event_type,
                payload,
                session_id,
                source_host=source_host,
            )
            return
        context = next(
            (item for item in self._session_hosts.values() if item.host is source_host), None,
        ) if source_host is not None and source_host is not self._host else None
        if context is not None:
            with self._session_host_scope(context):
                self._project_event(
                    event_type, payload, session_id, source_host=source_host,
                )
            return
        if (
            source_host is not None
            and source_host is not self._host
        ):
            # Buffered events from a retired host still appear in its timeline;
            # execution bookkeeping belongs to the current host or a retained
            # session context, handled above.
            return
        if event_type == "runtime.started":
            self._runtime_state = "switching" if self._autonomy_apply_pending else "ready"
        elif event_type == "runtime.session_switch_failed":
            target_session_id = payload.get("targetSessionId")
            generation = payload.get("generation")
            retryable = payload.get("retryable") is True
            current_target = self._pending_session_activation_id or self._selected_session_id
            is_current_target = (
                not isinstance(target_session_id, str) or target_session_id == current_target
            )
            is_current_generation = (
                not isinstance(generation, int) or generation == self._session_switch_generation
            )
            if retryable:
                self._runtime_state = "stopping" if self._host is not None else "failed"
            elif is_current_target and is_current_generation:
                self._runtime_state = "ready" if self._host is not None else "failed"
                if isinstance(payload.get("previousSessionId"), str):
                    self._selected_session_id = cast(str, payload["previousSessionId"])
                    if self._pending_session_activation_id == target_session_id:
                        self._pending_session_activation_id = None
        elif event_type == "runtime.autonomy_failed":
            self._autonomy_apply_pending = False
            self._autonomy = Autonomy(cast(str, payload.get("autonomy", self._autonomy.value)))
            restored = payload.get("restored") is True
            host = self._host
            if restored and host is not None and host.is_alive():
                self._runtime_state = "ready"
            elif self._runtime_state == "awaiting_extension_approval" and host is not None:
                # The recovered host is waiting for an extension approval;
                # keep that explicit state instead of advertising readiness.
                self._runtime_state = "awaiting_extension_approval"
            elif host is not None and host.is_alive():
                # A host reference can outlive a failed shutdown. It is not a
                # usable runtime until its accepting loop has been restored.
                self._runtime_state = "stopping"
            else:
                self._runtime_state = "failed"
        elif event_type == "runtime.stopped":
            self._clear_turn_state_after_runtime_failure(session_id)
            self._runtime_state = "stopped"
        elif event_type == "runtime.failed":
            self._clear_turn_state_after_runtime_failure(session_id)
            self._runtime_state = "failed"
        elif event_type == "session.created":
            raw_id = payload.get("sessionId")
            if isinstance(raw_id, str):
                self._selected_session_id = raw_id
                if source_host is self._host and self._host_session_id is None:
                    self._host_session_id = raw_id
        elif event_type == "turn.started":
            raw_turn = payload.get("turnId") or payload.get("correlationId")
            self._active_turn = str(raw_turn or "active")
            if self._active_queue_id is not None:
                self._turn_to_queue_id[self._active_turn] = self._active_queue_id
                corr = payload.get("correlationId")
                if corr:
                    self._turn_to_queue_id[str(corr)] = self._active_queue_id
            self._turn_requested = False
        elif event_type in {"runtime.command_rejected", "runtime.error"}:
            self._clear_turn_state_after_runtime_failure(session_id)
        elif event_type in _TERMINAL_TURN_EVENTS:
            prev_active_turn = self._active_turn
            self._active_turn = None
            self._turn_requested = False
            raw_corr = payload.get("correlationId")
            corr_str = str(raw_corr) if raw_corr else None
            queue_turn_id = (
                (
                    self._turn_to_queue_id.pop(prev_active_turn, None)
                    if prev_active_turn is not None
                    else None
                )
                or (self._turn_to_queue_id.pop(corr_str, None) if corr_str is not None else None)
                or self._active_queue_id
                or prev_active_turn
            )
            self._active_queue_id = None
            terminal_session = None if session_id == "desktop" else session_id
            if queue_turn_id and terminal_session is not None and self._database.is_file():
                final_state = (
                    "completed"
                    if event_type == "turn.completed"
                    else "cancelled"
                    if event_type == "turn.cancelled"
                    else "failed"
                )
                with suppress(Exception), SQLiteEventStore(self._database) as store:
                    store.mark_turn_state(queue_turn_id, final_state)
            for entry in self._approval_ledger.values():
                if (
                    entry.state == "resolving" and entry.session_id in {terminal_session, None}
                    and (entry.source_host is source_host or entry.source_host is None)
                ):
                    entry.turn_terminal = True
            for request_id in [
                key
                for key, entry in self._approval_ledger.items()
                if entry.state != "resolving" and entry.session_id in {session_id, None}
                and (entry.source_host is source_host or entry.source_host is None)
            ]:
                del self._approval_ledger[request_id]
            dispatched = self._dispatch_next_turn(session_id)
            if not dispatched:
                self._activate_pending_session_if_idle()
        elif event_type == "approval.requested":
            approval_request_id = payload.get("requestId")
            if isinstance(approval_request_id, str) and approval_request_id:
                self._approval_ledger.setdefault(
                    approval_request_id,
                    _ApprovalEntry(
                        None if session_id == "desktop" else session_id,
                        {
                            key: _bounded_projection(value)
                            for key, value in payload.items()
                            if key in _APPROVAL_DISPLAY_FIELDS
                        },
                        source_host=source_host,
                    ),
                )
        elif event_type == "runtime.mode_applied":
            raw_mode = payload.get("mode")
            if isinstance(raw_mode, str):
                with suppress(ValueError):
                    self._mode = Mode(raw_mode)
        elif event_type in {"runtime.autonomy_applied", "autonomy.changed"}:
            if event_type == "runtime.autonomy_applied":
                self._autonomy_apply_pending = False
                self._runtime_state = "ready" if self._host is not None else "failed"
            raw_autonomy = payload.get("autonomy") or payload.get("toAutonomy")
            if isinstance(raw_autonomy, str):
                with suppress(ValueError):
                    self._autonomy = Autonomy(raw_autonomy)

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
                entry.host.submit_turn(prompt)
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

    @property
    def _busy(self) -> bool:
        return (
            self._git_delivery_in_progress
            or self._turn_requested
            or self._active_turn is not None
            or any(
                entry.state != "resolved" and entry.run_id is None
                and (
                    entry.source_host is self._host
                    or (entry.source_host is None and entry.session_id in {
                        self._host_session_id, None,
                    })
                )
                for entry in self._approval_ledger.values()
            )
        )

    def _sessions(self, limit: int) -> list[dict[str, object]]:
        if self._workspace is None or not self._database.is_file():
            return []
        try:
            sessions = SQLiteEventStore.list_sessions_read_only(
                self._database, limit, workspace=self._workspace, exclude_run_sessions=True
            )
        except (OSError, ValueError):
            raise GatewayError("storage_unavailable") from None
        return [self._session_document(session) for session in sessions]

    def _stored_session(self, session_id: str) -> Session | None:
        if not self._database.is_file():
            return None
        try:
            return SQLiteEventStore.get_session_read_only(self._database, session_id)
        except (OSError, ValueError):
            raise GatewayError("storage_unavailable") from None

    def _history_page(
        self, session_id: str, *, cutoff: int | None = None, before: int | None = None
    ) -> dict[str, object]:
        if not self._database.is_file():
            return {
                "timeline": [],
                "history": {
                    "hasMore": False,
                    "nextCursor": None,
                    "cutoff": 0,
                    "oversizedTurn": False,
                },
            }
        try:
            durable_cutoff, events, has_more, oversized_turn = (
                SQLiteEventStore.list_complete_turn_window_read_only(
                    self._database,
                    session_id,
                    cutoff=cutoff,
                    before=before,
                    minimum_user_turns=_HISTORY_MINIMUM_USER_TURNS,
                    max_events=_HISTORY_MAX_EVENTS,
                )
            )
            inferred_requests = SQLiteEventStore.model_request_ids_read_only(self._database, events)
        except (OSError, ValueError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None

        projected_descending: list[tuple[Event, dict[str, object], int]] = []
        projection_omitted = False
        applied_input_ids = {
            event.causation_id for event in events if event.type == "turn.input.applied"
        }
        for event in events:
            if event.type == "turn.input.applied" or (
                event.type == "turn.input.received" and event.id in applied_input_ids
            ):
                continue
            request_id = inferred_requests.get(event.id)
            projected = self._timeline_event(
                replace(event, data={**event.data, "model_request_id": request_id})
                if request_id is not None
                else event
            )
            size = len(json.dumps(projected, ensure_ascii=True, separators=(",", ":")).encode())
            entry_limit = (
                _HISTORY_ASSISTANT_ENTRY_BYTES
                if event.type == "message.created" and event.data.get("role") == "assistant"
                else _HISTORY_ENTRY_BYTES
            )
            if size > entry_limit:
                projection_omitted = True
                continue
            projected_descending.append((event, projected, size))

        contains_user_turn = any(
            event.type == "message.created" and event.data.get("role") == "user"
            for event, _projected, _size in projected_descending
        )
        groups: list[list[tuple[Event, dict[str, object], int]]] = []
        if contains_user_turn:
            current: list[tuple[Event, dict[str, object], int]] = []
            for item in projected_descending:
                current.append(item)
                event = item[0]
                if event.type == "message.created" and event.data.get("role") == "user":
                    groups.append(current)
                    current = []
            if current:
                groups.append(current)
        else:
            groups = [[item] for item in projected_descending]

        timeline_descending: list[dict[str, object]] = []
        used = 0
        next_before = before if before is not None else durable_cutoff + 1
        has_more = has_more or projection_omitted
        for group in groups:
            group_size = sum(item[2] for item in group)
            if timeline_descending and used + group_size > _HISTORY_TOTAL_BYTES:
                has_more = True
                break
            if not timeline_descending and group_size > _HISTORY_TOTAL_BYTES:
                oversized_turn = True
                has_more = True
                for event, projected, size in group:
                    if timeline_descending and used + size > _HISTORY_TOTAL_BYTES:
                        break
                    timeline_descending.append(projected)
                    used += size
                    next_before = event.sequence or next_before
                break
            for event, projected, size in group:
                timeline_descending.append(projected)
                used += size
                next_before = event.sequence or next_before
        next_cursor = (
            self._encode_cursor(session_id, durable_cutoff, next_before) if has_more else None
        )
        return {
            "timeline": list(reversed(timeline_descending)),
            "history": {
                "hasMore": has_more,
                "nextCursor": next_cursor,
                "cutoff": durable_cutoff,
                "oversizedTurn": oversized_turn,
            },
        }

    def _acknowledge_history_page(self, session_id: str, page: Mapping[str, object]) -> None:
        history = page.get("history")
        if not isinstance(history, Mapping):
            return
        cutoff = history.get("cutoff")
        if not isinstance(cutoff, int) or isinstance(cutoff, bool):
            return
        # SQLite persistence and the RuntimeHost display queue are separate
        # steps. Remember lifecycle events that were already collected for the
        # snapshot, then allow any later lifecycle event through even when its
        # durable sequence is below this database cutoff. This suppresses true
        # snapshot duplicates without swallowing a just-persisted terminal
        # event whose in-memory projection still says the turn is active.
        self._snapshot_pending_event_ids.update(
            event.id
            for event in self._pending_host_events
            if event.session_id == session_id
            and event.sequence is not None
            and event.sequence <= cutoff
            and (event.type == "turn.started" or event.type in _TERMINAL_TURN_EVENTS)
        )
        self._durable_cutoffs[session_id] = max(cutoff, self._durable_cutoffs.get(session_id, 0))

    def _encode_cursor(self, session_id: str, cutoff: int, after: int) -> str:
        body = json.dumps([session_id, cutoff, after], separators=(",", ":")).encode()
        encoded = base64.urlsafe_b64encode(body).rstrip(b"=").decode()
        signature = hmac.new(self._cursor_key, encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def _decode_cursor(self, cursor: str, session_id: str) -> tuple[int, int]:
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
                or document[0] != session_id
                or type(document[1]) is not int
                or type(document[2]) is not int
                or document[1] < 0
                or document[2] < 0
                or document[2] > document[1]
            ):
                raise ValueError
            return document[1], document[2]
        except (ValueError, TypeError, json.JSONDecodeError):
            raise GatewayError("invalid_cursor") from None

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

    @staticmethod
    def _session_document(session: Session) -> dict[str, object]:
        return {
            "id": _bounded_text(session.id),
            "title": _bounded_text(session.title),
            "workspace": _bounded_text(session.workspace),
            "mode": session.mode.value,
            "autonomy": session.autonomy.value,
            "createdAt": _bounded_text(session.created_at),
            "updatedAt": _bounded_text(session.updated_at),
        }

    @staticmethod
    def _timeline_event(event: Event) -> dict[str, object]:
        data: dict[str, object] = {}
        for key in _DISPLAY_FIELDS:
            if key not in event.data:
                continue
            value = event.data[key]
            if key == "resources":
                if isinstance(value, list):
                    value = [
                        {
                            field: item[field]
                            for field in ("id", "name", "mime", "url", "kind")
                            if isinstance(item, Mapping)
                            and field in item
                            and isinstance(item[field], str)
                        }
                        for item in value[:16]
                        if isinstance(item, Mapping)
                    ]
                else:
                    continue
            canonical_content = (
                key == "content"
                and event.type == "message.created"
                and event.data.get("role") == "assistant"
            )
            # Bound complete assistant entries in _history_page. Cutting their
            # content midway through a Markdown fence corrupts restored code.
            if (
                key in {"text", "content", "error", "reason", "reasoning", "result"}
                and isinstance(value, str)
                and not canonical_content
            ):
                value = value[:12_000]
            try:
                data[_camel_case(key)] = _json_safe(
                    value,
                    max_string_chars=(
                        _HISTORY_ASSISTANT_ENTRY_BYTES if canonical_content else _MAX_STRING_CHARS
                    ),
                )
            except GatewayError:
                continue
        if event.type == "tool.proposed":
            tool_name = event.data.get("name")
            arguments = event.data.get("arguments")
            allowed = (
                _SAFE_HISTORY_TOOL_ARGUMENTS.get(tool_name) if isinstance(tool_name, str) else None
            )
            if allowed is not None and isinstance(arguments, Mapping):
                with suppress(GatewayError):
                    data["arguments"] = _json_safe(
                        {key: value for key, value in arguments.items() if key in allowed}
                    )
        event_type = event.type
        input_id = event.data.get("input_id")
        if event_type == "turn.input.received":
            event_type = "message.created"
            input_id = event.id
            data.update(
                {
                    "role": "user",
                    "content": str(event.data.get("prompt", ""))[:12_000],
                    "inputId": event.id,
                    "inputState": "pending",
                }
            )
        elif event_type == "message.created" and isinstance(input_id, str):
            data["inputState"] = "applied"
        document: dict[str, object] = {
            "eventId": input_id if isinstance(input_id, str) else event.id,
            "type": event_type,
            "domainSequence": event.sequence or 0,
            "createdAt": event.created_at,
            "data": data,
        }
        if event.correlation_id is not None:
            document["correlationId"] = event.correlation_id
        if event.causation_id is not None:
            document["causationId"] = event.causation_id
        return document

    @property
    def _session_switch_in_progress(self) -> bool:
        current = self._session_switch_thread
        return self._runtime_state == "switching" or (current is not None and current.is_alive())

    def _require_host(
        self, *, allow_awaiting_approval: bool = False, allow_switching: bool = False
    ) -> Host:
        valid_states = {"ready"}
        if allow_awaiting_approval:
            valid_states.add("awaiting_extension_approval")
        if allow_switching:
            valid_states.add("switching")
        if self._host is None or self._runtime_state not in valid_states:
            raise GatewayError("runtime_unavailable")
        return self._host

    def _require_workspace_provider(self) -> None:
        if self._workspace is None or self._provider is None:
            raise GatewayError("runtime_unconfigured")

    def _require_configured(
        self, *, allow_awaiting_approval: bool = False, allow_switching: bool = False
    ) -> None:
        self._require_workspace_provider()
        self._require_host(
            allow_awaiting_approval=allow_awaiting_approval,
            allow_switching=allow_switching,
        )

    def _require_selected_session(
        self, requested: str | None, *, allow_unselected: bool = False
    ) -> None:
        selected = self._selected_session_id
        if selected is None and allow_unselected and requested is None:
            return
        if requested != selected:
            raise GatewayError("invalid_session")

    @staticmethod
    def _require_payload(
        command: CommandEnvelope, required: set[str], *, optional: set[str] | None = None
    ) -> None:
        allowed = required | (optional or set())
        if set(command.payload) != allowed.intersection(command.payload) or not required.issubset(
            command.payload
        ):
            raise GatewayError("invalid_command")

    def _reply(
        self,
        message_type: str,
        payload: dict[str, object],
        *,
        session_id: str | object | None = _CURRENT_SESSION,
        should_stop: bool = False,
    ) -> GatewayReply:
        selected = (
            self._selected_session_id
            if session_id is _CURRENT_SESSION
            else cast(str | None, session_id)
        )
        return GatewayReply(
            message_type,
            cast(
                dict[str, object],
                _json_safe(
                    payload,
                    max_string_chars=(
                        _HISTORY_ASSISTANT_ENTRY_BYTES
                        if "timeline" in payload
                        else _MAX_STRING_CHARS
                    ),
                ),
            ),
            selected,
            self._take_sequence(),
            should_stop,
        )

    def _take_sequence(self) -> int:
        with self._wire_sequence_lock:
            sequence = self._next_wire_sequence
            self._next_wire_sequence += 1
            return sequence


def _camel_case(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


def _json_safe(
    value: object,
    *,
    _seen: set[int] | None = None,
    _depth: int = 0,
    max_string_chars: int = _MAX_STRING_CHARS,
) -> object:
    if _depth > _MAX_NESTING:
        raise GatewayError("payload_too_large")
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str) and len(value) > max_string_chars:
            raise GatewayError("payload_too_large")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise GatewayError("invalid_payload")
        return value
    if isinstance(value, Enum):
        return _json_safe(
            value.value, _seen=_seen, _depth=_depth + 1, max_string_chars=max_string_chars
        )
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)) or callable(value):
        raise GatewayError("invalid_payload")
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(
            asdict(value), _seen=_seen, _depth=_depth + 1, max_string_chars=max_string_chars
        )

    seen = _seen if _seen is not None else set()
    identity = id(value)
    if identity in seen:
        raise GatewayError("invalid_payload")
    seen.add(identity)
    try:
        if isinstance(value, Mapping):
            if len(value) > _MAX_COLLECTION_ITEMS:
                raise GatewayError("payload_too_large")
            result: dict[str, object] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise GatewayError("invalid_payload")
                if key in _SENSITIVE_KEYS or _camel_case(key) in _SENSITIVE_KEYS:
                    continue
                result[key] = _json_safe(
                    item, _seen=seen, _depth=_depth + 1, max_string_chars=max_string_chars
                )
            return result
        if isinstance(value, (list, tuple)):
            if len(value) > _MAX_COLLECTION_ITEMS:
                raise GatewayError("payload_too_large")
            return [
                _json_safe(item, _seen=seen, _depth=_depth + 1, max_string_chars=max_string_chars)
                for item in value
            ]
    finally:
        seen.discard(identity)
    raise GatewayError("invalid_payload")
