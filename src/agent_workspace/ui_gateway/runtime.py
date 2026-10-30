from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import sqlite3
import stat
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from concurrent.futures import Future
from contextlib import contextmanager, suppress
from dataclasses import replace
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import urlsplit
from uuid import uuid4

from agent_workspace.application.agent_control import AgentControlService
from agent_workspace.application.review_workflow import ReviewWorkflowService
from agent_workspace.application.runtime_host import RuntimeHost, RuntimeSettings
from agent_workspace.coding.desk import CodingDesk
from agent_workspace.coding.team_desk import team_lead_note
from agent_workspace.config import (
    ProviderConfig,
    default_database_path,
    default_workspace_catalog_path,
)
from agent_workspace.core.events import Event
from agent_workspace.core.experts import ExpertError, lead_instructions, parse_team
from agent_workspace.core.git_diff_review import GitDiffReviewService
from agent_workspace.core.models import (
    MAX_IMAGE_BYTES,
    MAX_IMAGES_PER_MESSAGE,
    ApprovalScope,
    Autonomy,
    BinaryArtifact,
    ImagePart,
    Mode,
)
from agent_workspace.core.session import Session
from agent_workspace.core.workspace_catalog import WorkspaceCatalog, WorkspaceCatalogError
from agent_workspace.knowledge.watch import FolderWatch
from agent_workspace.providers.health import (
    ProviderHealthResult,
    provider_health_check,
)
from agent_workspace.settings import (
    ProviderSettingsError,
    ProviderSettingsStore,
)
from agent_workspace.storage import (
    SQLiteEventStore,
)
from agent_workspace.storage.file_versions import FileVersions
from agent_workspace.storage.lock import ProcessWriteLockGroup
from agent_workspace.tools.file_batches import (
    FileBatchStore,
)
from agent_workspace.tools.filesystem import _open_identity_checked
from agent_workspace.tools.paths import WorkspacePaths
from agent_workspace.ui_gateway.backups import backup_due
from agent_workspace.ui_gateway.device_hub import DeviceHub
from agent_workspace.ui_gateway.device_link import (
    DeviceLink,
)
from agent_workspace.ui_gateway.device_review import DeviceReviewCommands
from agent_workspace.ui_gateway.gateway_code import CODE_COMMANDS, CodeCommands
from agent_workspace.ui_gateway.gateway_common import (
    _APPROVAL_DISPLAY_FIELDS,
    _BACKUP_CHECK_SECONDS,
    _BACKUP_FIRST_CHECK_SECONDS,
    _BOOTSTRAP_RESERVED_BYTES,
    _COMMAND_TIMEOUT_SECONDS,
    _COMPACT_CHANGE_EVENTS,
    _CURRENT_SESSION,
    _DEVICE_COMMANDS,
    _FILE_BATCH_COMMANDS,
    _HISTORY_ASSISTANT_ENTRY_BYTES,
    _HOST_LIFECYCLE_EVENTS,
    _KNOWLEDGE_COMMANDS,
    _LIFECYCLE_TIMEOUT_SECONDS,
    _LOGGER,
    _MAX_ATTACHMENTS,
    _MAX_BOOTSTRAP_APPROVALS,
    _MAX_EXCLUDED_IMAGE_DIGESTS,
    _MAX_PROMPT_CHARS,
    _MAX_PROVIDER_MODEL_CHARS,
    _MAX_SESSIONS,
    _MAX_STRING_CHARS,
    _MAX_TURN_QUEUE,
    _SCHEDULE_COMMANDS,
    _START_TIMEOUT_SECONDS,
    _TERMINAL_TURN_EVENTS,
    _USAGE_COMMANDS,
    _WATCH_COMMANDS,
    GatewayError,
    GatewayReply,
    Host,
    _approval_display_text,
    _approval_plan,
    _approval_summary,
    _ApprovalEntry,
    _bounded_projection,
    _bounded_scalar,
    _bounded_text,
    _camel_case,
    _default_provider_test,
    _Delegation,
    _GatewayPhoneJobs,
    _GatewayRuntimeHost,
    _GatewaySubagents,
    _json_safe,
    _RunHostEntry,
    _SessionHostContext,
    _TeamTurn,
)
from agent_workspace.ui_gateway.gateway_debug import DEBUG_COMMANDS, DebugCommands
from agent_workspace.ui_gateway.gateway_devices import DeviceCommands
from agent_workspace.ui_gateway.gateway_exports import EXPORT_COMMANDS, ExportCommands
from agent_workspace.ui_gateway.gateway_git import GIT_COMMANDS, GitCommands
from agent_workspace.ui_gateway.gateway_knowledge import KnowledgeCommands
from agent_workspace.ui_gateway.gateway_latex import LATEX_COMMANDS, LatexCommands
from agent_workspace.ui_gateway.gateway_office import OFFICE_COMMANDS, OfficeCommands
from agent_workspace.ui_gateway.gateway_project import PROJECT_COMMANDS, ProjectCommands
from agent_workspace.ui_gateway.gateway_providers import ProviderCommands
from agent_workspace.ui_gateway.gateway_references import REFERENCE_COMMANDS, ReferenceCommands
from agent_workspace.ui_gateway.gateway_review import ReviewCommands
from agent_workspace.ui_gateway.gateway_runs import RunCommands
from agent_workspace.ui_gateway.gateway_schedules import ScheduleCommands
from agent_workspace.ui_gateway.gateway_science import SCIENCE_COMMANDS, ScienceCommands
from agent_workspace.ui_gateway.gateway_sessions import SessionCommands
from agent_workspace.ui_gateway.gateway_shell import SHELL_COMMANDS, ShellCommands
from agent_workspace.ui_gateway.gateway_specs import SPEC_COMMANDS, SpecCommands
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.gateway_tour import TOUR_COMMANDS, TourCommands
from agent_workspace.ui_gateway.gateway_usage import UsageCommands
from agent_workspace.ui_gateway.gateway_workspace import WorkspaceCommands
from agent_workspace.ui_gateway.latex_desk import LatexDesk
from agent_workspace.ui_gateway.protocol import (
    MAX_MESSAGE_BYTES,
    PROTOCOL_VERSION,
    CommandEnvelope,
    ProtocolError,
    encode_message,
)
from agent_workspace.ui_gateway.research import ResearchTools
from agent_workspace.ui_gateway.schedules import (
    ScheduleBook,
)
from agent_workspace.ui_gateway.science_desk import ScienceDesk, refresh_science_helpers
from agent_workspace.ui_gateway.skills import (
    SkillLibrary,
    UseSkillTool,
    bundled_skills_directory,
)
from agent_workspace.ui_gateway.transcription import transcribe
from agent_workspace.ui_gateway.turn_files import (
    TURN_FILES_EVENT,
    display_record,
    start_turn_watch,
)

__all__ = ["GatewayError", "GatewayReply", "GatewayRuntime"]


def _handler_table(*groups: tuple[Iterable[str], str]) -> dict[str, str]:
    """Command type -> GatewayRuntime method; the first group naming a type wins."""
    table: dict[str, str] = {}
    for types, handler in groups:
        for command_type in types:
            table.setdefault(command_type, handler)
    return table


# Commands answered without the gateway lock: they take it themselves for the state they read,
# and wait on slow work (a model, git, a phone, a file) outside it.
_UNLOCKED_HANDLERS: Final = _handler_table(
    (["prompt.optimize"], "_optimize_prompt"),
    (["provider.test"], "_test_saved_provider"),
    (["provider.health"], "_health_saved_provider"),
    (["workspace.git.deliver"], "_deliver_git_changes"),
    (["session.history"], "_session_history"),
    (["events.replay"], "_events_replay"),
    (_SCHEDULE_COMMANDS, "_schedules_command"),
    (["workspace.queue.list", "workspace.queue.get"], "_queue_command"),
    (
        [
            "workspace.collaborations.list",
            "workspace.collaborations.get",
            "workspace.collaborations.cancel",
            "workspace.collaborations.resume",
            "workspace.deliveries.list",
            "workspace.deliveries.get",
            "workspace.deliveries.cancel",
            "workspace.deliveries.resume",
        ],
        "_orchestration_command",
    ),
    (
        [
            "run.history.page",
            "workspace.runs.history",
            "run.evidence.page",
            "workspace.runs.evidence",
            "workspace.plan.retry",
            "workspace.plan.skip",
            "workspace.runs.failure.action",
        ],
        "_run_continuity_command",
    ),
    (["system.doctor"], "_run_doctor"),
    (["session.export"], "_export_session"),
    (["session.import"], "_import_session"),
    (["session.fork"], "_fork_session"),
    (["session.compare"], "_compare_session"),
    (["session.rewind"], "_rewind_session"),
    (["turn.files.diff"], "_turn_file_diff"),
    (["turn.files.undo"], "_undo_turn_files"),
    (["turn.files.hunk.undo"], "_undo_turn_hunk"),
    (["skills.list", "skills.set", "skills.folder.open"], "_skills_command"),
    (["limits.get", "limits.set"], "_task_limits_command"),
    (["cost.estimate"], "_estimate_cost"),
    (_DEVICE_COMMANDS, "_device_command"),
    (_KNOWLEDGE_COMMANDS, "_knowledge_command"),
    (LATEX_COMMANDS, "_latex_command"),
    (CODE_COMMANDS, "_code_command"),
    (PROJECT_COMMANDS, "_project_command"),
    (SHELL_COMMANDS, "_shell_command"),
    (GIT_COMMANDS, "_git_command"),
    (SPEC_COMMANDS, "_spec_command"),
    (DEBUG_COMMANDS, "_debug_command"),
    (TOUR_COMMANDS, "_tour_command"),
    (REFERENCE_COMMANDS, "_references_command"),
    (SCIENCE_COMMANDS, "_science_command"),
    (EXPORT_COMMANDS, "_export_command"),
    (OFFICE_COMMANDS, "_office_command"),
    (_FILE_BATCH_COMMANDS, "_file_batches_command"),
    (_USAGE_COMMANDS, "_usage_command"),
    (_WATCH_COMMANDS, "_watch_command"),
    (["document.preview"], "_document_preview"),
    (["session.usage"], "_session_usage"),
    (["memory.list"], "_list_memories"),
    (["workspace.agent.inspect"], "_inspect_agent_setup"),
    (["audio.transcribe"], "_transcribe_audio"),
    (["workspace.git.diff"], "_get_git_diff"),
    (["memory.update", "memory.delete"], "_write_memory"),
    (["workspace.review.create"], "_create_review_snapshot"),
    (["workspace.review.pr.create"], "_create_review_pull_request"),
    (["workspace.review.pr.refresh"], "_refresh_review_pull_request"),
    (["workspace.review.ai"], "_review_with_model"),
)
# Commands answered holding the gateway lock.
_LOCKED_HANDLERS: Final = _handler_table(
    (["app.handshake"], "_handshake"),
    (["app.bootstrap"], "_bootstrap_command"),
    (["workspace.open"], "_open_workspace"),
    (["workspace.sessions.list"], "_list_workspace_sessions"),
    (["session.list"], "_list_sessions"),
    (["session.open"], "_open_session"),
    (["session.create"], "_create_session"),
    (["session.presentation.set"], "_set_session_presentation"),
    (["session.search"], "_search_sessions"),
    (["research.sources.list"], "_list_research_sources"),
    (["research.source.read"], "_read_research_source"),
    (["research.citations.list"], "_list_research_citations"),
    (["workspace.summary.get"], "_workspace_summary"),
    (["changes.list"], "_list_changes"),
    (["changes.inspect"], "_inspect_change"),
    (
        [
            "jobs.list",
            "jobs.logs",
            "jobs.stop",
            "terminal.start",
            "terminal.input",
            "terminal.resize",
            "terminal.status",
            "terminal.list",
            "terminal.replay",
            "terminal.stop",
            "turn.start",
            "turn.steer",
            "turn.cancel",
            "runtime.mode.set",
        ],
        "_execute_session_command",
    ),
    (["provider.list"], "_list_providers"),
    (["provider.get"], "_get_provider"),
    (["provider.set"], "_set_provider"),
    (["provider.clear"], "_clear_provider"),
    (["provider.delete"], "_delete_provider"),
    (["provider.default"], "_set_default_provider"),
    (["provider.bootstrap"], "_bootstrap_provider"),
    (["runtime.autonomy.set"], "_set_autonomy"),
    (["approval.resolve"], "_resolve_approval"),
    (["workspace.files.tree"], "_list_workspace_files_tree"),
    (["workspace.file.read"], "_read_workspace_file"),
    (["workspace.file.write"], "_write_workspace_file"),
    (["workspace.git.revert"], "_revert_git_diff"),
    (["workspace.git.undo"], "_undo_git_diff"),
    (["workspace.context.get"], "_get_workspace_context"),
    (["workspace.tasks.list"], "_list_tasks"),
    (["workspace.tasks.create"], "_create_task"),
    (["workspace.tasks.update"], "_update_task"),
    (["workspace.tasks.delete"], "_delete_task"),
    (["workspace.runs.list"], "_list_agent_runs"),
    (["workspace.runs.get"], "_get_agent_run"),
    (["workspace.runs.create"], "_create_agent_run"),
    (["workspace.runs.update"], "_update_agent_run"),
    (["workspace.runs.start"], "_start_agent_run"),
    (["workspace.runs.pause"], "_pause_agent_run"),
    (["workspace.runs.resume"], "_resume_agent_run"),
    (["workspace.runs.cancel"], "_cancel_agent_run"),
    (["workspace.runs.cleanup"], "_cleanup_agent_run"),
    (["workspace.plan.list"], "_list_plan_steps"),
    (["workspace.plan.create"], "_create_plan_step"),
    (["workspace.plan.update"], "_update_plan_step"),
    (["workspace.plan.delete"], "_delete_plan_step"),
    (["workspace.attention.list"], "_list_attention"),
    (["workspace.attention.resolve"], "_resolve_attention"),
    (["workspace.review.list"], "_list_review_snapshots"),
    (["workspace.review.get"], "_get_review_snapshot"),
    (["workspace.review.comments.create"], "_create_review_comment"),
    (["workspace.review.comments.resolve"], "_resolve_review_comment"),
    (["workspace.review.comments.followup"], "_followup_review_comment"),
    (["app.shutdown"], "_shutdown_command"),
)


class GatewayRuntime(
    ProviderCommands,
    CodeCommands,
    ProjectCommands,
    ShellCommands,
    GitCommands,
    SpecCommands,
    DebugCommands,
    TourCommands,
    DeviceReviewCommands,
    SessionCommands,
    DeviceCommands,
    KnowledgeCommands,
    LatexCommands,
    ReferenceCommands,
    ScienceCommands,
    ExportCommands,
    OfficeCommands,
    UsageCommands,
    WorkspaceCommands,
    ReviewCommands,
    RunCommands,
    ScheduleCommands,
    GatewayState,
):
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
        daily_backup: Callable[[Path], object] | None = None,
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
        # Set on a thread whose replies are never written (a phone's task): they take no sequence.
        self._unsent_replies = threading.local()
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
        # The day's database backup (ui_gateway.backups), checked a minute after start and
        # then hourly; None turns it off (tests, embedders).
        self._daily_backup = daily_backup
        self._backup_next_check = clock() + _BACKUP_FIRST_CHECK_SECONDS
        self._backup_thread: threading.Thread | None = None
        self._load_session_presentation()
        # Phones paired with this desktop (device_link). The endpoint stays off until the user
        # turns it on; tasks handed over run in sessions of this gateway.
        self._device_link = DeviceLink(self._database.with_name("device-link"), self)
        self._device_hosted_sessions: dict[str, float] = {}
        self._device_host_starting: set[str] = set()
        self._settle_device_tasks_after_restart()
        # Scheduled tasks run in new conversations the way a phone's tasks do.
        self._schedules = ScheduleBook(self._database.with_name("schedules"))
        self._schedules_checked = float("-inf")
        self._schedule_pass_thread: threading.Thread | None = None
        # Skills every conversation can use: the official pack that ships with the app and the
        # ones the user copies into the skills folder; the agent reads one with use_skill.
        self._skills = SkillLibrary(
            bundled_skills_directory(),
            self._database.with_name("skills"),
            self._database.with_name("skills.json"),
        )
        self._skill_tool = UseSkillTool(self._skills)
        # Literature search, the folder's references, paper reading and the other research tools.
        self._research_tools = ResearchTools(self._database, self.speech_choice)
        self._latex = LatexDesk(self._database.parent)
        # Language servers for the editor and the agent's code tools, and the project rules.
        self._coding = CodingDesk(
            self._database.parent / "tools", self._database.with_name("project-trust.json")
        )
        self._coding.on_results = lambda root, state: self._report_checks(root, state.results)
        # Automatic fixes of failed checks handed to each conversation since its user last wrote.
        self._check_fix_rounds: dict[str, int] = {}
        self._science = ScienceDesk(self._database.parent)
        self._science.publish_python()
        refresh_science_helpers(self._database.parent)
        # Earlier contents of files the agent replaced, for comparing a change afterwards.
        self._file_versions = FileVersions(self._database.with_name("file-versions"))
        # Batches of file changes the agent made, each undoable from the window.
        self._file_batches = FileBatchStore(self._database.with_name("file-batches"))
        # Both stores exist before the thread that prunes them starts.
        threading.Thread(
            target=self._prune_file_versions, name="gateway-file-versions", daemon=True
        ).start()
        # (month, when it was read, estimated cost) for the monthly cap.
        self._month_cost: tuple[str, float, float] | None = None
        self._folder_watch: FolderWatch | None = None
        self._watch_thread: threading.Thread | None = None
        # Agent runs a conversation started with delegate_tasks: their approvals and progress
        # also show in that conversation.
        self._delegations: dict[str, _Delegation] = {}
        self._subagents = _GatewaySubagents(self)
        # The expert team of each conversation's turn in progress (turn.start "team"), by session:
        # conversations left running in the background keep their own team.
        self._team_turns: dict[str, _TeamTurn] = {}
        # Device link 2: what phones send and collect, and requests this desktop's AI sends them.
        self._device_hub = DeviceHub(self)
        self._phone_jobs = _GatewayPhoneJobs(self)
        # Tasks phones handed over, by conversation, until their message shows:
        # (prompt, how the window marks the turn, task id, device id).
        self._device_turn_origins: dict[str, list[tuple[str, dict[str, object], str, str]]] = {}
        # Turns a phone's task started (correlation id -> device id), and each turn's latest
        # answer, for the finished turns phones are told about.
        self._device_turn_owners: dict[str, str] = {}
        self._turn_answers: dict[str, str] = {}
        self._finished_turns: queue.SimpleQueue[tuple[str, str, str, str, str | None]] = (
            queue.SimpleQueue()
        )
        self._turn_recorder: threading.Thread | None = None
        if self._workspace_catalog is not None:
            with suppress(OSError):  # older versions kept schedules inside each folder
                self._schedules.import_legacy(
                    entry.path for entry in self._workspace_catalog.entries()
                )
        self._settle_schedule_runs_after_restart()
        with suppress(Exception):  # a busy port is reported in the status, never at startup
            self._device_link.start_if_enabled()

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
                shutdown_timed_out = str(error) == "runtime_shutdown_failed"
                if shutdown_timed_out and self._host is None:
                    # The old host exited just after the deadline and
                    # _collect_host_events detached it before this worker got
                    # the lock. Its retry found this worker still holding the
                    # switch slot, so nothing failed: keep the target pending
                    # and let the finally block below start the retry.
                    return
                retryable = (
                    shutdown_timed_out
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
            self._host,
            self._workspace,
            self._provider,
            self._selected_session_id,
            self._host_session_id,
            self._mode,
            self._autonomy,
            self._runtime_state,
            self._active_turn,
            self._turn_requested,
            self._queued_turns,
            self._ephemeral_queued_images,
            self._active_queue_id,
            self._turn_to_queue_id,
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
            if (
                self._host is None
                or session_id is None
                or not (
                    self._busy
                    or self._queued_turns
                    or getattr(self._host, "has_background_work", False)
                )
            ):
                return False
            context = self._capture_session_host()
            context.selected_session_id = session_id
            if context.runtime_state == "switching" and (
                context.active_turn is not None
                or context.turn_requested
                or context.queued_turns
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
                    reply,
                    payload={
                        **reply.payload,
                        "runtime": self._session_runtime_document(),
                        "approvals": self._session_approval_documents(),
                    },
                )
        if command.type.startswith(
            ("workspace.runs.", "workspace.plan.", "workspace.attention.", "workspace.review.")
        ):
            return replace(reply, session_id=command.session_id)
        return reply

    def _session_approval_documents(self) -> list[dict[str, object]]:
        documents: list[dict[str, object]] = []
        for request_id, entry in self._approval_ledger.items():
            if entry.state == "resolved":
                continue
            delegation = self._delegations.get(entry.run_id) if entry.run_id is not None else None
            if delegation is not None and delegation.parent_session_id == self._selected_session_id:
                documents.append(
                    {
                        **entry.payload,
                        "requestId": request_id,
                        "sessionId": delegation.parent_session_id,
                        "subagent": delegation.title,
                    }
                )
            elif entry.session_id == self._selected_session_id or (
                entry.session_id is None and entry.source_host is self._host
            ):
                documents.append(
                    {**entry.payload, "requestId": request_id, "sessionId": entry.session_id}
                )
        return documents[-_MAX_BOOTSTRAP_APPROVALS:]

    def _execute(self, command: CommandEnvelope) -> GatewayReply:
        # ``workspace.open`` deliberately returns before a production
        # RuntimeHost has finished starting. Commands sent immediately after
        # that response still need a coherent ready host; wait outside the
        # gateway lock so the lifecycle worker can make progress. Session
        # creation also writes the shared SQLite store, so it must join this
        # wait rather than racing the host's startup transaction. Lifecycle
        # commands themselves remain non-blocking and can replace/cancel the
        # pending target.
        background_control = (
            command.type
            in {
                "turn.start",
                "turn.steer",
                "turn.cancel",
                "jobs.logs",
                "jobs.stop",
            }
            and command.session_id in self._session_hosts
        )
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
        handler = _UNLOCKED_HANDLERS.get(command.type)
        if handler is not None:
            return cast(Callable[[CommandEnvelope], GatewayReply], getattr(self, handler))(command)
        handler = _LOCKED_HANDLERS.get(command.type)
        if handler is None:
            raise GatewayError("unsupported_command")
        with self._lock:
            return cast(Callable[[CommandEnvelope], GatewayReply], getattr(self, handler))(command)

    def _bootstrap_command(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set())
        return self._bootstrap_reply(command.request_id)

    def _shutdown_command(self, command: CommandEnvelope) -> GatewayReply:
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
            self._collect_shell_output()
            self._collect_debug_events()
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
        # Outside the gateway lock: a phone request in flight may be waiting for it.
        self._device_link.stop()
        with self._lock:
            self._begin_close()
            self._stop_run_hosts()
            self._stop_session_hosts()
            self._stop_host()
        self._coding.close()

    def _begin_close(self) -> None:
        self._closing = True
        self._pending_workspace_activation = None
        self._workspace_activation_target = None
        self._pending_session_activation_id = None
        self._workspace_switch_generation += 1
        self._session_switch_generation += 1
        self._autonomy_switch_generation += 1

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
                **({"subagents": subagents} if (subagents := self._subagent_documents()) else {}),
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
        unresolved: list[dict[str, object]] = []
        for request_id, entry in self._approval_ledger.items():
            if entry.state == "resolved":
                continue
            delegation = self._delegations.get(entry.run_id) if entry.run_id is not None else None
            unresolved.append(
                {
                    **entry.payload,
                    "requestId": request_id,
                    "sessionId": entry.session_id,
                }
                if delegation is None
                else {
                    **entry.payload,
                    "requestId": request_id,
                    "sessionId": delegation.parent_session_id,
                    "subagent": delegation.title,
                }
            )
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
            **({"subagents": subagents} if (subagents := self._subagent_documents()) else {}),
            **({"approvalsTruncated": True} if len(unresolved) > len(approvals) else {}),
        }

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
            parked is not None
            and parked.host is not None
            and parked.host.is_alive()
            and not self._session_switch_in_progress
            and self._workspace_switch_thread is None
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

    def _prune_file_versions(self) -> None:
        with suppress(OSError):
            self._file_versions.prune()
        with suppress(OSError):
            self._file_batches.prune()

    @contextmanager
    def _unsent(self) -> Iterator[None]:
        """Commands the gateway gives itself; their replies take no wire sequence."""
        previous = getattr(self._unsent_replies, "active", False)
        self._unsent_replies.active = True
        try:
            yield
        finally:
            self._unsent_replies.active = previous

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

    def _start_turn(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(
            command,
            {"prompt"},
            optional={
                "attachmentPaths",
                "excludeImageDigests",
                "reasoningEffort",
                "model",
                "planFirst",
                "team",
                "teamReview",
            },
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
        model = (
            self._turn_model_override(command.payload["model"])
            if "model" in command.payload
            else None
        )
        plan_first = command.payload.get("planFirst", False)
        if type(plan_first) is not bool:
            raise GatewayError("invalid_payload")
        team = None
        if "team" in command.payload:
            if plan_first:
                raise GatewayError("invalid_payload")
            review = command.payload.get("teamReview", True)
            if type(review) is not bool:
                raise GatewayError("invalid_payload")
            try:
                chosen = parse_team(command.payload["team"])
            except ExpertError:
                raise GatewayError("invalid_team") from None
            team = (_TeamTurn(chosen), team_lead_note(lead_instructions(chosen, review=review)))
        self._check_monthly_cap()
        prompt = prompt.strip()
        if references:
            prompt = f"{prompt}\n\n" + "\n".join(f"[File reference: {path}]" for path in references)
        busy = self._active_turn is not None or self._turn_requested or len(self._queued_turns) > 0
        if (model is not None or plan_first or team is not None) and (busy or self._busy):
            # A queued turn keeps only what the queue stores; another model, a plan, or an
            # expert team is asked at once.
            raise GatewayError("runtime_busy")
        if busy:
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
                prompt,
                exclude_image_digests,
                reasoning_effort,
                images=images,
                model=model,
                plan_only=plan_first,
                team=team[1] if team is not None else None,
            )
        except RuntimeError:
            raise GatewayError("runtime_unavailable") from None
        owner = cast(str, command.session_id)
        if team is not None:
            self._team_turns[owner] = team[0]
        else:
            self._team_turns.pop(owner, None)
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
        model: str | None = None,
        plan_only: bool = False,
        team: str | None = None,
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
        if model is not None:
            kwargs["model"] = model
        if plan_only:
            kwargs["plan_only"] = True
        if team is not None:
            kwargs["team"] = team
        limits = self._task_limits()
        if limits is not None:
            kwargs["limits"] = limits
        return host.submit_turn(prompt, **kwargs)

    @staticmethod
    def _turn_model_override(value: object) -> str:
        """A model id for one turn on the current Provider (a comparison with another model)."""
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > _MAX_PROVIDER_MODEL_CHARS
            or any(ord(char) < 32 or char.isspace() for char in value.strip())
        ):
            raise GatewayError("invalid_model")
        return value.strip()

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
                            ".bmp",
                            ".tif",
                            ".tiff",
                            ".avif",
                            ".heic",
                            ".heif",
                            ".ico",
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
        delegation = self._delegations.get(entry.run_id) if entry.run_id is not None else None
        if delegation is not None:
            self._pending_host_events.append(
                Event(
                    session_id=delegation.parent_session_id,
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
                subagents=self._subagents,
                phone_jobs=self._phone_jobs,
                extra_tools=(self._skill_tool,),
                system_note=self._system_note,
                turn_files=start_turn_watch,
                workspace_tools=self._folder_tools,
                tool_hooks=self._coding.hooks,
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
        self._stop_host(deadline=deadline)

    def _stop_host(self, *, deadline: float | None = None) -> None:
        deadline = deadline or self._clock() + _LIFECYCLE_TIMEOUT_SECONDS
        with self._lock:
            host = self._host
        if host is not None:
            # No backup while closing: the database is backed up once a day (_tick_backup).
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
                if entry.run_id is not None
                or (entry.source_host is not None and entry.source_host is not host)
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
            session_id: context
            for session_id, context in self._session_hosts.items()
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
                    if entry.run_id is not None
                    or (entry.source_host is not None and entry.source_host is not host)
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
                events = [
                    Event(
                        session_id=session_id,
                        type="runtime.failed",
                        data={"reason": "runtime event stream failed"},
                    )
                ]
            self._queue_host_events(events, source_host=host)
            if not host.is_alive():
                with self._session_host_scope(context):
                    self._clear_turn_state_after_runtime_failure(session_id)
                self._session_hosts.pop(session_id, None)
        self._retire_idle_device_hosts()
        self._tick_schedules()
        self._tick_backup()

    def _tick_backup(self) -> None:
        """Start the day's database backup when one is due (gateway lock held, so no work here)."""
        if self._daily_backup is None or self._closing:
            return
        now = self._clock()
        if now < self._backup_next_check:
            return
        self._backup_next_check = now + _BACKUP_CHECK_SECONDS
        if self._backup_thread is not None and self._backup_thread.is_alive():
            return
        thread = threading.Thread(target=self._backup_pass, name="gateway-backup", daemon=True)
        self._backup_thread = thread
        thread.start()

    def _backup_pass(self) -> None:
        backup = self._daily_backup
        try:
            if backup is not None and backup_due(self._database):
                backup(self._database)
        except Exception:
            # The next check tries again; a failed backup must not disturb the window.
            _LOGGER.exception("daily database backup failed")

    def _queue_host_events(
        self,
        events: list[Event],
        *,
        source_host: Host | None = None,
        run_id: str | None = None,
    ) -> None:
        for event in events:
            session_context = (
                next(
                    (item for item in self._session_hosts.values() if item.host is source_host),
                    None,
                )
                if run_id is None and source_host is not None
                else None
            )
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
            if run_id is None and event.type == TURN_FILES_EVENT:
                self._after_turn_files(event)
            elif (
                run_id is None
                and event.type == "message.created"
                and (event.data.get("role") == "user")
            ):
                self._note_user_turn(event)
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
            else:
                display_event = self._note_device_turn(event)
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

    def _record_finished_turn(
        self, session_id: str, turn_id: str, state: str, summary: str, owner: str | None
    ) -> None:
        """Keep a finished turn for paired phones, in order, off the event path."""
        with suppress(OSError, ValueError):
            if not self._device_link.settings()["enabled"]:
                return
        self._finished_turns.put((session_id, turn_id, state, summary, owner))
        if self._turn_recorder is None or not self._turn_recorder.is_alive():
            self._turn_recorder = threading.Thread(
                target=self._record_turns, name="device-link-turns", daemon=True
            )
            self._turn_recorder.start()

    def _record_turns(self) -> None:
        link = self._device_link
        while True:
            session_id, turn_id, state, summary, owner = self._finished_turns.get()
            with suppress(Exception):
                if not link.registry.list():
                    continue
                session = self._stored_session(session_id)
                if session is not None:
                    title = self._session_title(session)
                    link.store.add_turn(turn_id, session_id, title, state, summary, owner)

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
            summary = _approval_summary(event.data) or _approval_display_text(
                event.data.get("summary")
            )
            if summary:
                payload["summary"] = summary
            subagent = _approval_display_text(event.data.get("subagent"))
            if subagent:
                payload["subagent"] = subagent
            plan = _approval_plan(event.data)
            if plan is not None:
                payload["plan"], payload["planTotal"] = cast(list[object], plan[0]), plan[1]
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
            raw_data = (
                display_record(event.data) if event.type == TURN_FILES_EVENT else dict(event.data)
            )
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
            if entry.session_id in {session_id, None}
            and (entry.source_host is self._host or entry.source_host is None)
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
        context = (
            next(
                (item for item in self._session_hosts.values() if item.host is source_host),
                None,
            )
            if source_host is not None and source_host is not self._host
            else None
        )
        if context is not None:
            with self._session_host_scope(context):
                self._project_event(
                    event_type,
                    payload,
                    session_id,
                    source_host=source_host,
                )
            return
        if source_host is not None and source_host is not self._host:
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
                    entry.state == "resolving"
                    and entry.session_id in {terminal_session, None}
                    and (entry.source_host is source_host or entry.source_host is None)
                ):
                    entry.turn_terminal = True
            for request_id in [
                key
                for key, entry in self._approval_ledger.items()
                if entry.state != "resolving"
                and entry.session_id in {session_id, None}
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

    @property
    def _busy(self) -> bool:
        return (
            self._git_delivery_in_progress
            or self._turn_requested
            or self._active_turn is not None
            or any(
                entry.state != "resolved"
                and entry.run_id is None
                and (
                    entry.source_host is self._host
                    or (
                        entry.source_host is None
                        and entry.session_id
                        in {
                            self._host_session_id,
                            None,
                        }
                    )
                )
                for entry in self._approval_ledger.values()
            )
        )

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
            0 if getattr(self._unsent_replies, "active", False) else self._take_sequence(),
            should_stop,
        )

    def _execute_unsent(self, command: CommandEnvelope) -> None:
        """Run a command for something other than the window; its reply is never written."""
        self._unsent_replies.active = True
        try:
            self._execute_session_command(command)
        finally:
            self._unsent_replies.active = False

    def _take_sequence(self) -> int:
        with self._wire_sequence_lock:
            sequence = self._next_wire_sequence
            self._next_wire_sequence += 1
            return sequence
