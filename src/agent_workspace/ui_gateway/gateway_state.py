"""What the command groups of GatewayRuntime read and call; set up in its __init__.

The groups are mixins of GatewayRuntime (ui_gateway.runtime). This class declares the state they
share and, for the type checker only, the methods they call that another group or GatewayRuntime
itself defines.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from agent_workspace.application.agent_control import AgentControlService
from agent_workspace.application.ports import Tool
from agent_workspace.application.review_workflow import ReviewWorkflowService
from agent_workspace.application.runtime_host import RuntimeSettings
from agent_workspace.coding.desk import CodingDesk
from agent_workspace.config import (
    ProviderConfig,
)
from agent_workspace.core.budgets import (
    TaskLimits,
)
from agent_workspace.core.events import Event
from agent_workspace.core.git_diff_review import GitDiffReviewService
from agent_workspace.core.models import (
    AgentRun,
    ApprovalScope,
    Autonomy,
    ImagePart,
    Mode,
)
from agent_workspace.core.session import Session
from agent_workspace.core.workspace_catalog import WorkspaceCatalog
from agent_workspace.knowledge.watch import FolderWatch
from agent_workspace.providers.health import (
    ProviderHealthResult,
)
from agent_workspace.settings import (
    ProviderSettingsStore,
)
from agent_workspace.storage.file_versions import FileVersions
from agent_workspace.storage.lock import ProcessWriteLockGroup
from agent_workspace.tools.file_batches import (
    FileBatchStore,
)
from agent_workspace.ui_gateway.device_hub import DeviceHub
from agent_workspace.ui_gateway.device_link import (
    DeviceLink,
    PairedDevice,
    TaskOptions,
)
from agent_workspace.ui_gateway.gateway_common import (
    _CURRENT_SESSION,
    GatewayReply,
    Host,
    _ApprovalEntry,
    _Delegation,
    _GatewayPhoneJobs,
    _GatewaySubagents,
    _RunHostEntry,
    _SessionHostContext,
    _TeamTurn,
)
from agent_workspace.ui_gateway.latex_desk import LatexDesk
from agent_workspace.ui_gateway.protocol import (
    CommandEnvelope,
)
from agent_workspace.ui_gateway.research import ResearchTools
from agent_workspace.ui_gateway.schedules import (
    ScheduleBook,
)
from agent_workspace.ui_gateway.science_desk import ScienceDesk
from agent_workspace.ui_gateway.skills import (
    SkillLibrary,
    UseSkillTool,
)


class GatewayState:
    """Shared state of GatewayRuntime and its command groups."""

    _active_queue_id: str | None
    _active_turn: str | None
    _agent_control: AgentControlService | None
    _approval_ledger: dict[str, _ApprovalEntry]
    _async_workspace_switch: bool
    _audio_transcriber: Callable[[ProviderConfig, str, bytes, str, str], str]
    _autonomy: Autonomy
    _autonomy_apply_pending: bool
    _autonomy_switch_generation: int
    _autonomy_switch_thread: threading.Thread | None
    _backup_next_check: float
    _backup_thread: threading.Thread | None
    _clock: Callable[[], float]
    _closing: bool
    _coding: CodingDesk
    _check_fix_rounds: dict[str, int]
    _cursor_key: bytes
    _daily_backup: Callable[[Path], object] | None
    _database: Path
    _delegations: dict[str, _Delegation]
    _team_turns: dict[str, _TeamTurn]
    _device_host_starting: set[str]
    _device_hosted_sessions: dict[str, float]
    _device_hub: DeviceHub
    _device_link: DeviceLink
    _device_turn_origins: dict[str, list[tuple[str, dict[str, object], str, str]]]
    _device_turn_owners: dict[str, str]
    _durable_cutoffs: dict[str, int]
    _ephemeral_queued_images: dict[str, tuple[ImagePart, ...]]
    _file_batches: FileBatchStore
    _file_versions: FileVersions
    _finished_turns: queue.SimpleQueue[tuple[str, str, str, str, str | None]]
    _folder_watch: FolderWatch | None
    _git_delivery_in_progress: bool
    _git_review_service: GitDiffReviewService | None
    _host: Host | None
    _latex: LatexDesk
    _host_factory: Callable[[RuntimeSettings], Host]
    _host_session_id: str | None
    _host_startup_lock: threading.Lock
    _host_startup_outcomes: dict[int, str]
    _lifecycle_lock: threading.RLock
    _lock: threading.RLock
    _mode: Mode
    _month_cost: tuple[str, float, float] | None
    _next_wire_sequence: int
    _orchestration_runtime: object | None
    _pending_autonomy_request: tuple[str, Autonomy] | None
    _pending_host_events: list[Event]
    _pending_session_activation_id: str | None
    _pending_workspace_activation: tuple[Path, ProviderConfig] | None
    _phone_jobs: _GatewayPhoneJobs
    _projecting_background_session: bool
    _provider: ProviderConfig | None
    _provider_health_checker: Callable[[ProviderConfig], ProviderHealthResult]
    _provider_resolver: Callable[[], ProviderConfig] | None
    _provider_settings_store: ProviderSettingsStore | None
    _provider_tester: Callable[[ProviderConfig], None]
    _queued_turns: list[tuple[str, str, list[str], frozenset[str], str | None]]
    _review_delivery_in_progress: set[str]
    _review_workflow: ReviewWorkflowService | None
    _run_cancel_requested: set[str]
    _run_hosts: dict[str, _RunHostEntry]
    _run_prepare_threads: dict[str, threading.Thread]
    _run_preparing: set[str]
    _runtime_state: str
    _schedule_pass_thread: threading.Thread | None
    _schedules: ScheduleBook
    _science: ScienceDesk
    _schedules_checked: float
    _selected_session_id: str | None
    _session_hosts: dict[str, _SessionHostContext]
    _session_presentation: dict[str, dict[str, object]]
    _session_switch_generation: int
    _session_switch_thread: threading.Thread | None
    _skill_tool: UseSkillTool
    _skills: SkillLibrary
    _research_tools: ResearchTools
    _sleeper: Callable[[float], None]
    _snapshot_pending_event_ids: set[str]
    _subagents: _GatewaySubagents
    _turn_answers: dict[str, str]
    _turn_recorder: threading.Thread | None
    _turn_requested: bool
    _turn_to_queue_id: dict[str, str]
    _unsent_replies: threading.local
    _watch_thread: threading.Thread | None
    _wire_sequence_lock: threading.Lock
    _workspace: Path | None
    _workspace_activation_target: tuple[Path, ProviderConfig] | None
    _workspace_catalog: WorkspaceCatalog | None
    _workspace_catalog_path: Path
    _workspace_switch_generation: int
    _workspace_switch_thread: threading.Thread | None
    _writer_lock_group: ProcessWriteLockGroup
    epoch: str

    if TYPE_CHECKING:

        def execute(self, command: CommandEnvelope) -> GatewayReply: ...

        def _await_lifecycle_settle(self) -> None: ...

        def _workspace_presentations(self) -> dict[str, dict[str, object]]: ...

        def _workspace_session(self, session_id: object) -> Session: ...

        def _dispatch_prompt(
            self, request_id: str, session: Session, prompt: str, pictures: Sequence[str] = ()
        ) -> None: ...

        def _task_limits(self) -> TaskLimits | None: ...

        def _system_note(self) -> str: ...

        def _folder_tools(self, workspace: Path) -> tuple[Tool, ...]: ...

        def _open_folder(self) -> Path: ...

        def _quick_provider(self) -> ProviderConfig: ...

        # Used by the phone's code review (device_review.py), defined by other mixins.
        def _device_call[T](self, function: Callable[..., T], *arguments: object) -> T: ...

        def _get_git_diff(self, command: CommandEnvelope) -> GatewayReply: ...

        def _list_review_snapshots(self, command: CommandEnvelope) -> GatewayReply: ...

        def _get_review_snapshot(self, command: CommandEnvelope) -> GatewayReply: ...

        def _create_review_snapshot(self, command: CommandEnvelope) -> GatewayReply: ...

        def _create_review_comment(self, command: CommandEnvelope) -> GatewayReply: ...

        def _followup_review_comment(self, command: CommandEnvelope) -> GatewayReply: ...

        def _review_service(self) -> ReviewWorkflowService: ...

        @staticmethod
        def _check_device_autonomy(
            device: PairedDevice, autonomy: Autonomy, options: TaskOptions
        ) -> list[str]: ...

        def _control_service(self) -> AgentControlService: ...

        @staticmethod
        def _run_document(run: AgentRun) -> dict[str, object]: ...

        def _start_agent_run(self, command: CommandEnvelope) -> GatewayReply: ...

        def _check_monthly_cap(self) -> None: ...

        def _tick_folder_watch(self) -> None: ...

        @contextmanager
        def _unsent(self) -> Iterator[None]: ...

        def _refresh_open_schedule_runs(self) -> None: ...

        @staticmethod
        def _turn_model_override(value: object) -> str: ...

        def _attachment_references(self, value: object) -> list[str]: ...

        def _attachment_images(self, references: list[str]) -> tuple[ImagePart, ...]: ...

        def _commit_approval_resolution(
            self, request_id: str, entry: _ApprovalEntry, scope: ApprovalScope | None
        ) -> None: ...

        def _start_host(self, *, session_id: str | None, deadline: float | None = None) -> None: ...

        def _stop_host_for_lifecycle(
            self, *, deadline: float | None = None, preserve_session: bool = False
        ) -> None: ...

        def _stop_host(self, *, deadline: float | None = None) -> None: ...

        def _queue_host_events(
            self,
            events: list[Event],
            *,
            source_host: Host | None = None,
            run_id: str | None = None,
        ) -> None: ...

        def _record_finished_turn(
            self, session_id: str, turn_id: str, state: str, summary: str, owner: str | None
        ) -> None: ...

        @property
        def _busy(self) -> bool: ...

        def _stored_session(self, session_id: str) -> Session | None: ...

        def _device_task_origins(self, session_id: str) -> dict[str, dict[str, object]]: ...

        @staticmethod
        def _timeline_event(event: Event) -> dict[str, object]: ...

        def _require_host(
            self, *, allow_awaiting_approval: bool = False, allow_switching: bool = False
        ) -> Host: ...

        def _require_configured(
            self, *, allow_awaiting_approval: bool = False, allow_switching: bool = False
        ) -> None: ...

        def _require_selected_session(
            self, requested: str | None, *, allow_unselected: bool = False
        ) -> None: ...

        @staticmethod
        def _require_payload(
            command: CommandEnvelope, required: set[str], *, optional: set[str] | None = None
        ) -> None: ...

        def _reply(
            self,
            message_type: str,
            payload: dict[str, object],
            *,
            session_id: str | object | None = _CURRENT_SESSION,
            should_stop: bool = False,
        ) -> GatewayReply: ...

        def _execute_unsent(self, command: CommandEnvelope) -> None: ...
