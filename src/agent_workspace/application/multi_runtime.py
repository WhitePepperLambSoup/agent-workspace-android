from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
from collections.abc import Callable, Coroutine, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from agent_workspace.application.background_jobs import BackgroundJobManager
from agent_workspace.application.collaboration import (
    CollaborationCoordinator,
    CollaborationRoute,
)
from agent_workspace.application.delivery import DeliveryLoop
from agent_workspace.application.event_bus import EventBus
from agent_workspace.application.ports import EventListener, ManagedModelProvider
from agent_workspace.application.service import ApplicationService
from agent_workspace.application.shutdown import settle_tasks
from agent_workspace.application.workspace_recovery import recover_workspace_file_writes
from agent_workspace.config import (
    ProviderConfig,
    database_writer_lock_path,
)
from agent_workspace.config import (
    default_writer_lock_path as _config_default_writer_lock_path,
)
from agent_workspace.core.events import Event
from agent_workspace.core.models import Autonomy, Mode
from agent_workspace.core.orchestration import (
    CollaborationHandle,
    CollaborationRequest,
    CollaborationResult,
    CollaborationStatus,
    DeliveryHandle,
    DeliveryLimits,
    DeliveryResult,
    DeliveryStatus,
    RunProjection,
    build_run_projection,
)
from agent_workspace.policy import (
    ApprovalCallback,
    EgressApprovalCallback,
    ExtensionApprovalCallback,
    ExtensionApprovalRequiredError,
    ProviderEgressPolicy,
    WorkspacePolicy,
    build_custom_tool_extension_request,
    build_mcp_extension_request,
)
from agent_workspace.providers import create_provider
from agent_workspace.storage import ProcessWriteLock, SQLiteEventStore, create_verified_backup
from agent_workspace.tools import ToolRegistry
from agent_workspace.tools.code_map import CodeMapTool
from agent_workspace.tools.custom import CustomCommandTool, load_custom_tool_definitions
from agent_workspace.tools.mcp_host import (
    McpHost,
    McpServerConfig,
    build_mcp_host,
    load_mcp_servers,
)
from agent_workspace.tools.openapi import OpenApiGetTool, load_openapi_file
from agent_workspace.tools.process_worker import run_in_process
from agent_workspace.tools.sandbox import (
    LocalSandboxConfig,
    SandboxBackend,
    SandboxBackendRegistry,
    SandboxStatus,
    resolve_sandbox_backend_id,
)

_T = TypeVar("_T")
_BACKUP_TIMEOUT_SECONDS = 5.0
_PROVIDER_CLOSE_TIMEOUT_SECONDS = 5.0
_NOTIFICATION_QUEUE_LIMIT = 1024
_LOGGER = logging.getLogger(__name__)

default_writer_lock_path = _config_default_writer_lock_path


def _create_multi_runtime_backup(database: str, backup_directory: str) -> str:
    return str(create_verified_backup(database, backup_directory, keep=10))


async def _settle_provider_close(
    providers: tuple[ManagedModelProvider, ...],
) -> tuple[list[Exception], bool]:
    if not providers:
        return [], False
    tasks = {asyncio.create_task(provider.aclose()) for provider in providers}
    try:
        errors = await settle_tasks(
            tasks,
            timeout=_PROVIDER_CLOSE_TIMEOUT_SECONDS,
            timeout_message="provider close deadline exceeded",
        )
    except asyncio.CancelledError:
        return [], True
    return errors, False


async def _notification_worker(
    queue: asyncio.Queue[Event],
    listener: EventListener,
) -> None:
    while True:
        event = await queue.get()
        try:
            result = listener(event)
            if inspect.isawaitable(result):
                await result
        except asyncio.CancelledError:
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise
            _LOGGER.exception("runtime event listener cancelled itself for %s", event.type)
        except Exception:
            _LOGGER.exception("runtime event listener failed for %s", event.type)


@dataclass(slots=True)
class MultiProviderRuntime:
    coordinator: CollaborationCoordinator
    routes: dict[str, CollaborationRoute]
    providers: dict[str, ManagedModelProvider]
    store: SQLiteEventStore
    write_lock: ProcessWriteLock
    database: Path
    backup_directory: Path
    autonomy: Autonomy
    events: EventBus
    sandbox: SandboxBackend
    jobs: BackgroundJobManager
    mcp_host: McpHost | None = None
    backup_error: str | None = None
    _closed: bool = False
    _closing: bool = False
    _active: set[asyncio.Task[Any]] = field(default_factory=set)
    _notification_tasks: set[asyncio.Task[None]] = field(default_factory=set)
    _close_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def collaborate(self, request: CollaborationRequest) -> CollaborationResult:
        self._ensure_open()
        if request.autonomy is not self.autonomy:
            raise ValueError("collaboration autonomy must match the runtime policy")
        return await self._run_tracked(self.coordinator.start(request))

    async def resume_collaboration(
        self,
        handle: CollaborationHandle,
    ) -> CollaborationResult:
        self._ensure_open()
        if self.coordinator.get_request(handle).autonomy is not self.autonomy:
            raise ValueError("collaboration autonomy must match the runtime policy")
        return await self._run_tracked(self.coordinator.resume(handle))

    def inspect_collaboration(self, handle: CollaborationHandle) -> CollaborationStatus:
        self._ensure_open()
        return self.coordinator.inspect(handle)

    def list_collaborations(self, *, limit: int = 50) -> tuple[CollaborationStatus, ...]:
        self._ensure_open()
        return self.coordinator.list_statuses(limit=limit)

    async def cancel_collaboration(
        self,
        handle: CollaborationHandle,
        *,
        reason: str = "collaboration cancelled by caller",
    ) -> CollaborationResult:
        return await self._run_tracked(self.coordinator.cancel(handle, reason=reason))

    def inspect_delivery(self, handle: DeliveryHandle) -> DeliveryStatus:
        self._ensure_open()
        return self._delivery_inspector_for_handle(handle).inspect(handle)

    def list_deliveries(self, *, limit: int = 50) -> tuple[DeliveryStatus, ...]:
        self._ensure_open()
        if type(limit) is not int or not 1 <= limit <= 250:
            raise ValueError("delivery status limit must be from 1 to 250")
        statuses: list[DeliveryStatus] = []
        for event in self.store.list_events_by_type(
            "delivery.started",
            limit=limit,
            workspace=str(self.coordinator.workspace),
        ):
            delivery_id = event.data.get("delivery_id")
            if not isinstance(delivery_id, str):
                continue
            handle = DeliveryHandle(delivery_id, event.session_id)
            statuses.append(self._delivery_inspector_for_handle(handle).inspect(handle))
        return tuple(statuses)

    async def cancel_delivery(
        self,
        handle: DeliveryHandle,
        *,
        reason: str = "delivery cancelled by caller",
    ) -> DeliveryResult:
        loop = self._delivery_inspector_for_handle(handle)
        return await self._run_tracked(loop.cancel(handle, reason=reason))

    def list_run_projections(self, *, limit: int = 50) -> tuple[RunProjection, ...]:
        """Return collaboration and delivery statuses through one stable view.

        The runtime keeps its richer status objects for lifecycle operations,
        while callers that render a dashboard can consume one projection shape.
        Ordering follows the existing status queries so the newest records stay
        first and the two sources remain deterministic.
        """

        if type(limit) is not int or not 1 <= limit <= 250:
            raise ValueError("run projection limit must be from 1 to 250")
        self._ensure_open()
        collaborations = self.list_collaborations(limit=limit)
        deliveries = self.list_deliveries(limit=limit)
        workspace = str(self.coordinator.workspace)
        projections: list[RunProjection] = []
        for status in collaborations:
            failure = None
            if status.state.value in {"blocked", "failed"}:
                failure = {"code": status.state.value, "detail": status.detail}
            projections.append(
                build_run_projection(
                    status,
                    workspace=workspace,
                    artifact={
                        "kind": "collaboration_document",
                        "revision": status.document_revision,
                    },
                    failure=failure,
                )
            )
        for delivery_status in deliveries:
            failure = None
            if delivery_status.state.value in {"blocked", "failed"}:
                failure = {
                    "code": delivery_status.block_code or delivery_status.state.value,
                    "detail": delivery_status.detail,
                }
            projections.append(
                build_run_projection(
                    delivery_status,
                    workspace=workspace,
                    artifact=(
                        {"kind": "delivery_checkpoint", "value": delivery_status.checkpoint}
                        if delivery_status.checkpoint
                        else None
                    ),
                    failure=failure,
                )
            )
        return tuple(projections[:limit])

    def subscribe(self, listener: EventListener) -> Callable[[], None]:
        self._ensure_open()
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=_NOTIFICATION_QUEUE_LIMIT)
        worker = asyncio.create_task(_notification_worker(queue, listener))
        self._notification_tasks.add(worker)

        def dispatch(event: Event) -> None:
            if queue.full():
                _LOGGER.warning("runtime event listener queue overflow; newest event dropped")
                return
            queue.put_nowait(event)

        unsubscribe_bus = self.events.subscribe(dispatch)
        subscribed = True

        def unsubscribe() -> None:
            nonlocal subscribed
            if not subscribed:
                return
            subscribed = False
            unsubscribe_bus()
            worker.cancel()

            def _retire(_task: asyncio.Task[None]) -> None:
                self._notification_tasks.discard(_task)
                if not _task.cancelled():
                    _task.exception()

            worker.add_done_callback(_retire)

        return unsubscribe

    async def sandbox_status(self) -> SandboxStatus:
        self._ensure_open()
        return await self.sandbox.status()

    def delivery_loop(
        self,
        route_id: str,
        *,
        allowed_tools: frozenset[str] | None = None,
    ) -> RuntimeDeliveryLoop:
        self._ensure_open()
        try:
            route = self.routes[route_id]
        except KeyError:
            raise KeyError(f"unknown provider route: {route_id}") from None
        return RuntimeDeliveryLoop(
            self,
            DeliveryLoop(
                self.coordinator.workspace,
                route,
                autonomy=self.autonomy,
                allowed_tools=allowed_tools,
            ),
        )

    def _ensure_open(self) -> None:
        if self._closing or self._closed:
            raise RuntimeError("multi-provider runtime is closing")

    def _delivery_inspector_for_handle(self, handle: DeliveryHandle) -> DeliveryLoop:
        started = next(
            (
                event
                for event in self.store.list_events(handle.session_id)
                if event.type == "delivery.started" and event.data.get("delivery_id") == handle.id
            ),
            None,
        )
        if started is None:
            raise KeyError(f"unknown delivery: {handle.id}")
        route_id = started.data.get("route_id")
        route = self.routes.get(route_id) if isinstance(route_id, str) else None
        if route is None:
            route = next(iter(self.routes.values()))
        return DeliveryLoop(
            self.coordinator.workspace,
            route,
            autonomy=self.autonomy,
        )

    async def _run_tracked(self, operation: Coroutine[Any, Any, _T]) -> _T:
        try:
            self._ensure_open()
        except RuntimeError:
            operation.close()
            raise
        task = asyncio.create_task(operation)
        self._active.add(task)
        try:
            return await task
        finally:
            self._active.discard(task)

    async def aclose(self) -> None:
        async with self._close_lock:
            if self._closed:
                return
            self._closing = True
            cancelled = False
            close_errors: list[Exception] = []
            try:
                for task in tuple(self._active):
                    task.cancel()
                if self._active:
                    try:
                        close_errors.extend(
                            await settle_tasks(
                                tuple(self._active),
                                timeout=_PROVIDER_CLOSE_TIMEOUT_SECONDS,
                                timeout_message="active operation close deadline exceeded",
                            )
                        )
                    except asyncio.CancelledError:
                        cancelled = True
                for task in tuple(self._notification_tasks):
                    task.cancel()
                if self._notification_tasks:
                    try:
                        await settle_tasks(
                            tuple(self._notification_tasks),
                            timeout=_PROVIDER_CLOSE_TIMEOUT_SECONDS,
                            timeout_message="notification worker close deadline exceeded",
                        )
                    except asyncio.CancelledError:
                        cancelled = True
                    self._notification_tasks.clear()
                service_tasks = tuple(
                    asyncio.create_task(route.service.aclose()) for route in self.routes.values()
                )
                try:
                    close_errors.extend(
                        await settle_tasks(
                            service_tasks,
                            timeout=_PROVIDER_CLOSE_TIMEOUT_SECONDS,
                            timeout_message="application service close deadline exceeded",
                        )
                    )
                except asyncio.CancelledError:
                    cancelled = True
                if self.mcp_host is not None:
                    try:
                        await self.mcp_host.aclose()
                    except Exception as exc:
                        close_errors.append(exc)
                try:
                    await self.jobs.aclose()
                except asyncio.CancelledError:
                    cancelled = True
                except Exception as exc:
                    close_errors.append(exc)
                provider_errors, close_cancelled = await _settle_provider_close(
                    tuple(self.providers.values())
                )
                close_errors.extend(provider_errors)
                cancelled = cancelled or close_cancelled
                if not cancelled and not close_errors:
                    try:
                        await asyncio.wait_for(
                            run_in_process(
                                _create_multi_runtime_backup,
                                str(self.database),
                                str(self.backup_directory),
                            ),
                            timeout=_BACKUP_TIMEOUT_SECONDS,
                        )
                    except Exception as exc:
                        self.backup_error = " ".join(str(exc).split())[:1000] or type(exc).__name__
            finally:
                try:
                    self.store.close()
                finally:
                    self.write_lock.release()
                    self._closed = True
                    self._closing = False
            if cancelled:
                raise asyncio.CancelledError
            if close_errors:
                raise ExceptionGroup("one or more runtime resources failed to close", close_errors)


@dataclass(frozen=True, slots=True)
class RuntimeDeliveryLoop:
    _runtime: MultiProviderRuntime
    _loop: DeliveryLoop

    @property
    def route_id(self) -> str:
        return self._loop.route_id

    def inspect(self, handle: DeliveryHandle) -> DeliveryStatus:
        self._runtime._ensure_open()
        return self._loop.inspect(handle)

    def list_statuses(self, *, limit: int = 50) -> tuple[DeliveryStatus, ...]:
        self._runtime._ensure_open()
        return self._loop.list_statuses(limit=limit)

    async def start(
        self,
        goal: str,
        *,
        title: str = "Long-running delivery",
        mode: Mode = Mode.TASK,
        limits: DeliveryLimits | None = None,
        max_cycles: int | None = None,
    ) -> DeliveryResult:
        return await self._runtime._run_tracked(
            self._loop.start(
                goal,
                title=title,
                mode=mode,
                limits=limits,
                max_cycles=max_cycles,
            )
        )

    async def resume(
        self,
        handle: DeliveryHandle,
        *,
        max_cycles: int | None = None,
        resume_blocked: bool = False,
    ) -> DeliveryResult:
        return await self._runtime._run_tracked(
            self._loop.resume(
                handle,
                max_cycles=max_cycles,
                resume_blocked=resume_blocked,
            )
        )

    async def cancel(
        self,
        handle: DeliveryHandle,
        *,
        reason: str = "delivery cancelled by caller",
    ) -> DeliveryResult:
        return await self._runtime._run_tracked(self._loop.cancel(handle, reason=reason))


async def build_multi_provider_runtime(
    workspace: str | Path,
    database: str | Path,
    provider_configs: Iterable[ProviderConfig],
    *,
    autonomy: Autonomy = Autonomy.WORKSPACE,
    approval_callback: ApprovalCallback | None = None,
    egress_approval_callback: EgressApprovalCallback | None = None,
    event_listener: EventListener | None = None,
    sandbox_config: LocalSandboxConfig | None = None,
    sandbox_backend_id: str = "host-staged",
    sandbox_registry: SandboxBackendRegistry | None = None,
    allow_workspace_extensions: bool = False,
    extension_approval_callback: ExtensionApprovalCallback | None = None,
) -> MultiProviderRuntime:
    configs = tuple(provider_configs)
    if not configs:
        raise ValueError("at least one provider configuration is required")
    for config in configs:
        config.validate()
    if len({config.id for config in configs}) != len(configs):
        raise ValueError("provider configuration ids must be unique")

    workspace_path = Path(workspace).resolve(strict=True)
    if not workspace_path.is_dir():
        raise ValueError("workspace is not a directory")
    database_path = Path(database).expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    # Extension discovery & authorization (R01 & R27)
    mcp_servers = load_mcp_servers(workspace_path)
    approved_mcp_servers: list[McpServerConfig] = []
    for server in mcp_servers:
        req = build_mcp_extension_request(server, workspace_path)
        if allow_workspace_extensions:
            approved_mcp_servers.append(server)
        elif extension_approval_callback is not None:
            decision = extension_approval_callback(req)
            if inspect.isawaitable(decision):
                decision = await decision
            if decision:
                approved_mcp_servers.append(server)
        else:
            cmd_list = list(server.command)
            raise ExtensionApprovalRequiredError(
                f"workspace MCP extension {server.id!r} requires authorization "
                f"to start command: {cmd_list}"
            )

    custom_defs = tuple(load_custom_tool_definitions(workspace_path))
    approved_custom_defs = []
    for cdef in custom_defs:
        req = build_custom_tool_extension_request(cdef, workspace_path)
        if allow_workspace_extensions:
            approved_custom_defs.append(cdef)
        elif extension_approval_callback is not None:
            decision = extension_approval_callback(req)
            if inspect.isawaitable(decision):
                decision = await decision
            if decision:
                approved_custom_defs.append(cdef)
        else:
            command_str = " ".join((cdef.executable, *cdef.argv_template))
            raise ExtensionApprovalRequiredError(
                f"workspace custom tool {cdef.name!r} requires authorization "
                f"to start command: {command_str}"
            )

    if default_writer_lock_path is not _config_default_writer_lock_path:
        lock_path = default_writer_lock_path()
    else:
        lock_path = database_writer_lock_path(database_path)
    write_lock = ProcessWriteLock(lock_path)
    write_lock.acquire()
    store: SQLiteEventStore | None = None
    providers: dict[str, ManagedModelProvider] = {}
    jobs: BackgroundJobManager | None = None
    mcp_host: McpHost | None = None
    try:
        store = SQLiteEventStore(database_path)
        recover_workspace_file_writes(store, str(workspace_path))
        events = EventBus()
        if event_listener is not None:
            events.subscribe(event_listener)
        jobs = BackgroundJobManager(workspace_path, store, events.publish)
        selected_sandbox_backend = resolve_sandbox_backend_id(sandbox_backend_id, autonomy)
        registry = sandbox_registry or SandboxBackendRegistry.default(
            sandbox_config,
            include_host_staged=selected_sandbox_backend == "host-staged",
        )
        sandbox = registry.create(selected_sandbox_backend, workspace_path)
        tools = ToolRegistry.for_workspace(
            workspace_path,
            store,
            sandbox_backend=sandbox,
            allow_host_process=autonomy is not Autonomy.YOLO,
            background_jobs=jobs,
            custom_tools=(
                CustomCommandTool(workspace_path, definition) for definition in approved_custom_defs
            ),
        )
        tools.register(CodeMapTool(workspace_path))
        openapi_path = workspace_path / ".agent" / "openapi.json"
        if openapi_path.is_file():
            for operation in load_openapi_file(openapi_path):
                tools.register(OpenApiGetTool(operation))

        if approved_mcp_servers:
            mcp_host = build_mcp_host(workspace_path, approved_mcp_servers)
            if mcp_host is not None:
                for proxy in mcp_host.tools():
                    tools.register(proxy)

        policy = WorkspacePolicy(workspace_path, autonomy, approval_callback)
        routes: dict[str, CollaborationRoute] = {}
        for config in configs:
            provider = create_provider(config)
            providers[config.id] = provider
            service = ApplicationService(
                store,
                provider,
                tools,
                policy,
                events,
                egress_policy=ProviderEgressPolicy(
                    config.base_url,
                    autonomy,
                    egress_approval_callback,
                ),
                execution_workspace=workspace_path,
                execution_autonomy=autonomy,
            )
            routes[config.id] = CollaborationRoute(config.id, service, config.model)
        coordinator = CollaborationCoordinator(workspace_path, tuple(routes.values()))
        return MultiProviderRuntime(
            coordinator=coordinator,
            routes=routes,
            providers=providers,
            store=store,
            write_lock=write_lock,
            database=database_path,
            backup_directory=database_path.parent / "backups",
            autonomy=autonomy,
            events=events,
            sandbox=sandbox,
            jobs=jobs,
            mcp_host=mcp_host,
        )
    except BaseException:
        try:
            if mcp_host is not None:
                with contextlib.suppress(BaseException):
                    await mcp_host.aclose()
        finally:
            try:
                if providers:
                    await _settle_provider_close(tuple(providers.values()))
            finally:
                try:
                    if jobs is not None:
                        with contextlib.suppress(BaseException):
                            await asyncio.wait_for(
                                jobs.aclose(),
                                timeout=_PROVIDER_CLOSE_TIMEOUT_SECONDS,
                            )
                finally:
                    try:
                        if store is not None:
                            store.close()
                    finally:
                        write_lock.release()
        raise


build_multi_runtime = build_multi_provider_runtime
