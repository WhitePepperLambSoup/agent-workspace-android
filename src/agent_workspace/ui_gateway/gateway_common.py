"""Definitions shared by GatewayRuntime and its command groups (ui_gateway.runtime)."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import sqlite3
import time
from collections.abc import Awaitable, Mapping, Sequence
from concurrent.futures import Future
from contextlib import suppress
from dataclasses import asdict, dataclass, is_dataclass
from dataclasses import field as dataclass_field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol
from urllib.parse import urlsplit

from agent_workspace.application.runtime_host import RuntimeHost, RuntimeSettings
from agent_workspace.config import (
    ProviderConfig,
)
from agent_workspace.core.budgets import (
    TaskLimits,
)
from agent_workspace.core.events import Event
from agent_workspace.core.models import (
    ApprovalScope,
    Autonomy,
    ChatMessage,
    DeltaKind,
    ImagePart,
    Mode,
    ProviderRequest,
    Role,
)
from agent_workspace.core.task_graph import TaskGraph
from agent_workspace.policy.redaction import Redactor
from agent_workspace.providers import create_provider
from agent_workspace.tools.base import ToolArgumentError, ToolError
from agent_workspace.tools.delegation import SubagentOutcome, SubagentTask
from agent_workspace.tools.phone_jobs import PhoneJobOutcome, PhoneJobRequest
from agent_workspace.ui_gateway.device_link import (
    PairedDevice,
)
from agent_workspace.ui_gateway.device_store import PhoneJob
from agent_workspace.ui_gateway.protocol import (
    PROTOCOL_VERSION,
)

if TYPE_CHECKING:
    from agent_workspace.ui_gateway.runtime import GatewayRuntime

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
# How often a conversation waiting on its sub-agents looks at them, and how much of each
# sub-agent's final answer goes back to it.
_DELEGATION_POLL_SECONDS = 1.0
_DELEGATION_ANSWER_CHARS = 6_000
_MAX_PROVIDER_NAME_CHARS = 128
_MAX_PROVIDER_BASE_URL_CHARS = 2_048
_MAX_PROVIDER_MODEL_CHARS = 512
_MAX_PROVIDER_CREDENTIAL_BYTES = 2_560
_PROVIDER_TEST_TIMEOUT_SECONDS = 20.0
_CONTEXT_ESTIMATE_BYTES_PER_TOKEN = 3
# The composer's cost estimate draws on two weeks of tasks; with none, a desktop request (system
# prompt and tool schemas) is about this large.
_COST_ESTIMATE_DAYS = 14
_TYPICAL_REQUEST_TOKENS = 7_000
_DEVICE_COMMANDS = frozenset(
    {
        "devices.status",
        "devices.configure",
        "devices.pairing.start",
        "devices.token.create",
        "devices.revoke",
        "devices.update",
        "devices.reset",
        "devices.send",
        "devices.firewall.allow",
    }
)
# A phone reads recent messages only; long replies are cut for the phone's screen.
_DEVICE_EVENT_LIMIT = 200
# Finished scheduled runs and waiting approvals one inbox request returns.
_DEVICE_INBOX_LIMIT = 50
_DEVICE_CONTENT_CHARS = 20_000
_DEVICE_RESULT_CHARS = 64 * 1024
# A runtime started for a phone's task stops once its work is done and this long has passed.
_DEVICE_HOST_GRACE_SECONDS = 15.0
_DEVICE_TURN_ENDS = {
    "turn.completed": "succeeded",
    "turn.failed": "failed",
    "turn.cancelled": "cancelled",
}
# Phones' tasks waiting for their message to show, per conversation.
_DEVICE_PENDING_ORIGINS = 20
# What a phone's task is doing right now (GET /mobile/tasks/{id} "activity").
_DEVICE_ACTIVITY_CHARS = 120
_DEVICE_ACTIVITY_ARGUMENTS = ("command", "path", "url", "query", "task", "title", "source")
# Latest answers kept per running turn, for the finished-turn summaries phones see.
_TURN_ANSWERS_KEPT = 64
_KNOWLEDGE_COMMANDS = frozenset(
    {
        "knowledge.status",
        "knowledge.configure",
        "knowledge.add",
        "knowledge.document.update",
        "knowledge.document.delete",
        "knowledge.collection.create",
        "knowledge.collection.update",
        "knowledge.collection.delete",
        "knowledge.session.get",
        "knowledge.session.set",
        "knowledge.search",
    }
)
_SCHEDULE_COMMANDS = frozenset(
    {
        "schedules.list",
        "schedules.save",
        "schedules.delete",
        "schedules.run",
        "schedules.runs",
        "schedules.read",
    }
)
_FILE_BATCH_COMMANDS = frozenset({"files.batches.list", "files.batches.undo"})
_USAGE_COMMANDS = frozenset({"usage.bill", "usage.cap.set"})
_WATCH_COMMANDS = frozenset(
    {
        "knowledge.watch.list",
        "knowledge.watch.add",
        "knowledge.watch.remove",
        "knowledge.watch.scan",
    }
)
# A month-to-date cost is read again after this long; the monthly cap checks it per task.
_MONTH_COST_SECONDS = 60.0
_MAX_MONTHLY_CAP_USD = 100_000.0
# Changes of a file batch listed in its approval; the rest are counted.
_APPROVAL_PLAN_ITEMS = 100
# How often the gateway looks for due scheduled tasks, and how much of an answer a run keeps.
_SCHEDULE_TICK_SECONDS = 15.0
_SCHEDULE_RESULT_CHARS = 4000
# The daily backup is looked at this long after the sidecar starts, then every hour.
_BACKUP_FIRST_CHECK_SECONDS = 60.0
_BACKUP_CHECK_SECONDS = 3600.0
# Office files larger than this are not previewed in the window.
_DOCUMENT_PREVIEW_BYTES = 64 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LOGGER = logging.getLogger(__name__)


def _is_directory(path: str) -> bool:
    try:
        return Path(path).expanduser().is_dir()
    except OSError:
        return False


# Files picked or dropped at once on the Knowledge page.
_KNOWLEDGE_MAX_FILES = 50
_KNOWLEDGE_SEARCH_LIMIT = 8
_KNOWLEDGE_EXCERPT_CHARS = 600
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
        # A turn a phone handed over, or a conversation it handed over (device link 2).
        "origin",
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
    # Office files: which file, and whether one was replaced (the window offers a comparison).
    "create_docx": frozenset({"path", "expected_sha256"}),
    "edit_docx": frozenset({"path", "expected_sha256"}),
    "create_xlsx": frozenset({"path", "expected_sha256"}),
    "update_xlsx": frozenset({"path", "sheet", "expected_sha256"}),
    "create_pptx": frozenset({"path", "expected_sha256"}),
    "organize_files": frozenset({"summary"}),
    "phone_task": frozenset({"task", "operate_phone", "device"}),
}
_APPROVAL_DISPLAY_FIELDS = frozenset(
    {"tool", "toolName", "name", "summary", "supportsSessionScope", "plan", "planTotal"}
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


def _plan_text(value: object) -> str | None:
    """A workspace path for an approval's list of changes (names may say 'token')."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > 260 or any(ord(char) < 32 for char in text):
        return None
    return text if Redactor().redact(text) == text else None


def _approval_plan(data: Mapping[str, object]) -> tuple[list[dict[str, str]], int] | None:
    """Every change of a file batch, for the user to read before approving it."""
    tool = data.get("tool") or data.get("toolName") or data.get("name")
    arguments = data.get("arguments")
    if tool != "organize_files" or not isinstance(arguments, Mapping):
        return None
    operations = arguments.get("operations")
    if not isinstance(operations, list) or not operations:
        return None
    plan: list[dict[str, str]] = []
    for operation in operations[:_APPROVAL_PLAN_ITEMS]:
        if not isinstance(operation, Mapping):
            continue
        action = operation.get("action")
        path = _plan_text(operation.get("path"))
        if action not in {"move", "copy", "recycle", "make_folder"} or path is None:
            continue
        item = {"action": str(action), "path": path}
        target = _plan_text(operation.get("to"))
        if target is not None:
            item["to"] = target
        plan.append(item)
    return (plan, len(operations)) if plan else None


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
    if tool == "organize_files":
        operations = args.get("operations")
        if isinstance(operations, list) and operations:
            return f"Organize files: {len(operations)} changes"
    if tool == "delegate_tasks":
        tasks = args.get("tasks")
        if isinstance(tasks, list) and tasks:
            titles = [
                title
                for task in tasks
                if isinstance(task, Mapping)
                and (title := _approval_display_text(task.get("title")))
            ]
            text = f"Sub-agents ({len(tasks)}): " + ", ".join(titles)
            return text if len(text) <= 160 else text[:157] + "..."
    if tool == "phone_task":
        task = args.get("task")
        if isinstance(task, str) and task.strip():
            # The whole request is shown on the phone; the window shows its start.
            line = " ".join(task.split())
            text = f"Ask the phone: {line[:120]}{'...' if len(line) > 120 else ''}"
            return _approval_display_text(text) or "Ask the phone to do something"
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
        model: str | None = None,
        limits: TaskLimits | None = None,
        plan_only: bool = False,
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


@dataclass(frozen=True, slots=True)
class _Delegation:
    """An agent run a conversation started with delegate_tasks."""

    parent_session_id: str
    title: str


class _GatewaySubagents:
    """The delegate_tasks launcher: each task runs as one of this gateway's agent runs."""

    def __init__(self, gateway: GatewayRuntime) -> None:
        self._gateway = gateway

    async def run_tasks(
        self, parent_session_id: str, tasks: Sequence[SubagentTask]
    ) -> list[SubagentOutcome]:
        return await self._gateway._run_delegated_tasks(parent_session_id, tasks)


class _GatewayPhoneJobs:
    """The phone_task launcher: requests go to a paired phone's inbox as phone jobs.

    Called from runtime threads, so nothing here waits for the gateway lock except the
    window's notice of a job's state, which is queued from a worker thread."""

    _OFFERED_SECONDS = 5.0

    def __init__(self, gateway: GatewayRuntime) -> None:
        self._gateway = gateway
        self._offered: tuple[float, bool] | None = None

    def _devices(self) -> list[PairedDevice]:
        link = self._gateway._device_link
        if not link.settings()["enabled"]:
            return []
        return [device for device in link.registry.list() if device.accepts_jobs]

    def offered(self) -> bool:
        now = time.monotonic()
        cached = self._offered
        if cached is None or now - cached[0] > self._OFFERED_SECONDS:
            with suppress(OSError, ValueError):
                cached = self._offered = (now, bool(self._devices()))
        return cached is not None and cached[1]

    def submit(self, request: PhoneJobRequest) -> PhoneJobOutcome:
        devices = self._devices()
        if not devices:
            raise ToolError("no paired phone takes requests from this computer right now")
        if request.device is None:
            if len(devices) > 1:
                names = ", ".join(device.name for device in devices)
                raise ToolArgumentError(f"several phones take requests; name one: {names}")
            device = devices[0]
        else:
            wanted = request.device.casefold()
            matches = [
                item
                for item in devices
                if item.device_id == request.device or item.name.casefold() == wanted
            ]
            if len(matches) != 1:
                names = ", ".join(item.name for item in devices)
                raise ToolArgumentError(f"name one of the phones that take requests: {names}")
            device = matches[0]
        gateway = self._gateway
        title = ""
        with suppress(GatewayError, OSError, ValueError, sqlite3.Error):
            title = gateway._session_title(gateway._workspace_session(request.session_id))
        hub = gateway._device_hub
        job = hub.store.add_job(
            device.device_id, request.session_id, title, request.task, request.operate_phone
        )
        hub.log(device, "job_sent", request.task)
        hub.job_updated(job, device.name)
        return PhoneJobOutcome(job.job_id, device.name, job.state)

    def _outcome(self, job: PhoneJob) -> PhoneJobOutcome:
        device = self._gateway._device_link.registry.get(job.device_id)
        return PhoneJobOutcome(
            job.job_id, device.name if device else "", job.state, job.result, job.error
        )

    def poll(self, job_id: str) -> PhoneJobOutcome:
        hub = self._gateway._device_hub
        job = hub.store.job(job_id)
        if job is None:
            raise ToolError("the request to the phone is gone")
        if job.state == "expired":
            hub.job_updated(job, self._outcome(job).device)  # shown once it is noticed
        return self._outcome(job)

    def cancel(self, job_id: str) -> None:
        hub = self._gateway._device_hub
        with suppress(OSError, sqlite3.Error):
            job = hub.store.cancel_job(job_id)
            if job is not None and job.state == "cancelled":
                hub.job_updated(job, self._outcome(job).device)


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


def _camel_case(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


def _camel_keys(value: object) -> object:
    """A document with every key in the desktop protocol's camelCase."""
    if isinstance(value, Mapping):
        return {_camel_case(str(key)): _camel_keys(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_camel_keys(item) for item in value]
    return value


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
