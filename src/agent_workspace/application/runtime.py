from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Coroutine, Hashable, Sequence
from concurrent.futures import Future
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from agent_workspace.application.background_jobs import BackgroundJobManager
from agent_workspace.application.event_bus import EventBus
from agent_workspace.application.ports import (
    EventListener,
    ManagedModelProvider,
    Tool,
    ToolHooks,
)
from agent_workspace.application.scheduler import (
    ScheduledTaskHost,
    build_scheduled_host,
    load_scheduled_tasks,
)
from agent_workspace.application.service import ApplicationService
from agent_workspace.application.shutdown import settle_tasks
from agent_workspace.application.workspace_recovery import recover_workspace_file_writes
from agent_workspace.config import (
    ProviderConfig,
    database_writer_lock_path,
)
from agent_workspace.core.models import Autonomy, Mode
from agent_workspace.core.prompt_assembly import (
    PromptAssembler,
    PromptContext,
    PromptSection,
)
from agent_workspace.core.raw_trace import RawConversationTrace
from agent_workspace.knowledge import (
    KnowledgeStore,
    knowledge_root,
    knowledge_store,
    knowledge_tools,
)
from agent_workspace.optimizations import (
    ModelOptimizationRegistry,
    ModelRequestOptimizer,
    load_optimization_registry,
)
from agent_workspace.policy import (
    DEFAULT_YOLO_RULES,
    ApprovalCallback,
    EgressApprovalCallback,
    ExtensionApprovalCallback,
    ExtensionApprovalRequiredError,
    ProviderEgressPolicy,
    WorkspaceExtensionRequest,
    WorkspacePolicy,
    YoloRules,
    build_custom_tool_extension_request,
    build_mcp_extension_request,
    workspace_file_decision,
    workspace_file_requests,
)
from agent_workspace.providers import create_provider
from agent_workspace.storage import ProcessWriteLock, SQLiteEventStore, create_verified_backup
from agent_workspace.storage.file_versions import FileVersions
from agent_workspace.storage.lock import ProcessWriteLockGroup, ProcessWriteLockLease
from agent_workspace.tools import ToolRegistry
from agent_workspace.tools.code_map import CodeMapTool
from agent_workspace.tools.custom import CustomCommandTool, load_custom_tool_definitions
from agent_workspace.tools.delegation import DelegateTasksTool, SubagentLauncher
from agent_workspace.tools.file_batches import FileBatchStore
from agent_workspace.tools.mcp_host import (
    McpHost,
    McpServerConfig,
    build_mcp_host,
    load_mcp_servers,
)
from agent_workspace.tools.openapi import OpenApiGetTool, OpenApiOperation, load_openapi_file
from agent_workspace.tools.phone_jobs import PhoneJobLauncher, PhoneTaskTool
from agent_workspace.tools.process_worker import run_in_process
from agent_workspace.tools.sandbox import (
    LocalSandboxConfig,
    SandboxBackend,
    SandboxBackendRegistry,
    SandboxStatus,
    resolve_sandbox_backend_id,
)

_LOGGER = logging.getLogger(__name__)

_CLOSE_BACKUP_TIMEOUT_SECONDS = 5.0
_CLOSE_PROVIDER_TIMEOUT_SECONDS = 5.0
_CLOSE_COMPONENT_TIMEOUT_SECONDS = 5.0


def _close_resource_sync(resource: Any) -> None:
    if resource is None:
        return
    if hasattr(resource, "close_sync"):
        try:
            resource.close_sync()
            return
        except BaseException:
            pass
    if hasattr(resource, "close"):
        try:
            resource.close()
            return
        except BaseException:
            pass
    if hasattr(resource, "aclose"):
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                task = loop.create_task(resource.aclose())
                task.add_done_callback(_consume_close_task)
            else:
                asyncio.run(resource.aclose())
        except BaseException:
            pass


def _create_close_backup(database: str, backup_directory: str) -> str:
    return str(create_verified_backup(database, backup_directory, keep=10))


def _consume_close_task(task: asyncio.Task[Any]) -> None:
    if not task.cancelled():
        task.exception()


async def _close_provider_bounded(provider: ManagedModelProvider) -> None:
    task = asyncio.create_task(provider.aclose())
    errors = await settle_tasks(
        (task,),
        timeout=_CLOSE_PROVIDER_TIMEOUT_SECONDS,
        timeout_message="provider close deadline exceeded",
    )
    if errors:
        if len(errors) == 1:
            raise errors[0]
        raise ExceptionGroup("provider close failed", errors)


async def _close_component_bounded(coroutine: Coroutine[Any, Any, None], label: str) -> None:
    task = asyncio.create_task(coroutine)
    errors = await settle_tasks(
        (task,),
        timeout=_CLOSE_COMPONENT_TIMEOUT_SECONDS,
        timeout_message=f"{label} close deadline exceeded",
    )
    if errors:
        if len(errors) == 1:
            raise errors[0]
        raise ExceptionGroup(f"{label} close failed", errors)


@dataclass(slots=True)
class ApplicationRuntime:
    service: ApplicationService
    provider: ManagedModelProvider
    store: SQLiteEventStore
    write_lock: ProcessWriteLock
    database: Path
    backup_directory: Path
    backup_error: str | None = None
    sandbox: SandboxBackend | None = None
    jobs: BackgroundJobManager | None = None
    mcp: McpHost | None = None
    scheduler: ScheduledTaskHost | None = None
    # The user's documents, shared by every workspace of this data directory.
    knowledge: KnowledgeStore | None = None
    _closed: bool = False
    _closing: bool = False
    _close_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _scheduler_factory: Callable[[], ScheduledTaskHost | None] | None = None
    _scheduler_claim_key: Hashable | None = None
    _scheduler_loop: asyncio.AbstractEventLoop | None = None
    # Approved .agent files this runtime started without because they could not be read, by
    # their workspace path (".agent/prompt-assembly.json"), with why (skip_broken_workspace_files).
    skipped_workspace_files: dict[str, str] = field(default_factory=dict)
    # Custom tools (.agent/tools) left out because a built-in tool has the name: name -> the
    # definition's file.
    skipped_custom_tools: dict[str, str] = field(default_factory=dict)

    def switch_provider(self, provider_config: ProviderConfig) -> ManagedModelProvider:
        """Point this runtime at another model provider without rebuilding it.

        The caller must keep turns from running while it switches (a turn must not change
        provider halfway). Egress approval starts over for the new endpoint. Returns the
        previous provider, which the caller closes once nothing uses it.
        """
        provider = create_provider(provider_config)
        runner = self.service.runner
        previous = self.provider
        policy = getattr(runner, "_egress_policy", None)
        if policy is not None:
            runner._egress_policy = policy.retarget(provider_config.base_url)
        runner._provider = provider
        runner._system_prompt_cache.clear()
        self.service._provider = provider
        self.provider = provider
        return previous

    def _start_scheduler(self) -> None:
        if self._scheduler_factory is not None and self.scheduler is None:
            self.scheduler = self._scheduler_factory()
            if self.scheduler is not None:
                self.scheduler.start()

    async def _release_scheduler_claim(self) -> None:
        if isinstance(self.write_lock, ProcessWriteLockLease):
            key = self._scheduler_claim_key
            if key is not None:
                handoff = self.write_lock.release_claim(key)
                if handoff is not None:
                    await asyncio.wrap_future(handoff)

    async def _activate_scheduler(self) -> None:
        if self._closed or self._closing:
            await self._release_scheduler_claim()
            return
        try:
            self._start_scheduler()
        except BaseException:
            if self.scheduler is not None:
                await _close_component_bounded(self.scheduler.aclose(), "scheduled tasks")
                self.scheduler = None
            await self._release_scheduler_claim()
            raise

    def _queue_scheduler_activation(self) -> Future[None] | None:
        loop = self._scheduler_loop
        if loop is None or loop.is_closed():
            if isinstance(self.write_lock, ProcessWriteLockLease):
                key = self._scheduler_claim_key
                if key is not None:
                    return self.write_lock.release_claim(key)
            return None
        activation = self._activate_scheduler()
        try:
            return asyncio.run_coroutine_threadsafe(activation, loop)
        except BaseException:
            activation.close()
            raise

    async def _close_scheduler(self) -> None:
        try:
            if self.scheduler is not None:
                await _close_component_bounded(self.scheduler.aclose(), "scheduled tasks")
                self.scheduler = None
        finally:
            await _close_component_bounded(
                self._release_scheduler_claim(), "scheduled tasks handoff"
            )

    async def sandbox_status(self) -> SandboxStatus:
        if self._closed or self._closing:
            raise RuntimeError("application runtime is closed")
        if self.sandbox is None:
            return SandboxStatus(
                "none", False, "sandbox backend is not configured", None, None, None
            )
        return await self.sandbox.status()

    async def aclose(self, *, create_backup: bool = True) -> None:
        async with self._close_lock:
            if self._closed:
                return
            self._closing = True
            if isinstance(self.write_lock, ProcessWriteLockLease):
                key = self._scheduler_claim_key
                if key is not None:
                    self.write_lock.retire_claim(key)
            close_error: BaseException | None = None
            try:
                try:
                    await self._close_scheduler()
                except BaseException as exc:
                    close_error = exc
                try:
                    await _close_component_bounded(self.service.aclose(), "application service")
                except BaseException as exc:
                    close_error = (
                        exc
                        if close_error is None
                        else BaseExceptionGroup(
                            "application runtime close failed", [close_error, exc]
                        )
                    )
                if self.jobs is not None:
                    try:
                        await _close_component_bounded(self.jobs.aclose(), "background jobs")
                    except BaseException as exc:
                        close_error = (
                            exc
                            if close_error is None
                            else BaseExceptionGroup(
                                "application runtime close failed",
                                [close_error, exc],
                            )
                        )
                if self.mcp is not None:
                    try:
                        await _close_component_bounded(
                            asyncio.to_thread(self.mcp.close_sync),
                            "MCP servers",
                        )
                    except BaseException as exc:
                        close_error = (
                            exc
                            if close_error is None
                            else BaseExceptionGroup(
                                "application runtime close failed",
                                [close_error, exc],
                            )
                        )
                try:
                    await _close_provider_bounded(self.provider)
                except BaseException as exc:
                    close_error = (
                        exc
                        if close_error is None
                        else BaseExceptionGroup(
                            "application runtime close failed",
                            [close_error, exc],
                        )
                    )
                if close_error is not None:
                    raise close_error
            finally:
                try:
                    if create_backup:
                        task = asyncio.current_task()
                        if task is None or not task.cancelling():
                            try:
                                await asyncio.wait_for(
                                    run_in_process(
                                        _create_close_backup,
                                        str(self.database),
                                        str(self.backup_directory),
                                    ),
                                    timeout=_CLOSE_BACKUP_TIMEOUT_SECONDS,
                                )
                            except Exception as exc:
                                self.backup_error = (
                                    " ".join(str(exc).split())[:1000] or type(exc).__name__
                                )
                finally:
                    try:
                        self.store.close()
                    finally:
                        self.write_lock.release()
                        self._closed = True
                        self._closing = False


def _load_model_optimizer(workspace: Path) -> ModelRequestOptimizer | None:
    """Load the workspace's optional model optimization profiles."""
    candidates = (
        workspace / ".agent" / "optimizations.json",
        workspace / ".agent" / "optimizations.toml",
    )
    for path in candidates:
        if not path.is_file():
            continue
        if path.suffix == ".json":
            registry = load_optimization_registry(path)
        else:
            import tomllib

            try:
                with path.open("rb") as stream:
                    document = tomllib.load(stream)
            except (OSError, tomllib.TOMLDecodeError) as exc:
                raise ValueError(f"cannot read model optimization profiles {path}: {exc}") from exc
            registry = ModelOptimizationRegistry()
            for raw_profile in document.get("profiles", ()):
                from agent_workspace.optimizations import OptimizationProfile

                if not isinstance(raw_profile, dict):
                    raise ValueError(f"invalid model optimization profile in {path}")
                registry.register(OptimizationProfile.from_mapping(dict(raw_profile)))
        return ModelRequestOptimizer(registry)
    return None


def _load_prompt_assembler(workspace: Path) -> PromptAssembler | None:
    path = workspace / ".agent" / "prompt-assembly.json"
    if not path.is_file():
        return None
    import json

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read prompt assembly config {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError(f"prompt assembly config {path} must be an object")
    # A missing field used to surface as a bare KeyError ('order'), which named neither the file
    # nor what was wrong with it.
    try:
        sections = tuple(
            PromptSection(
                name=str(item["name"]),
                order=int(item["order"]),
                text=str(item["text"]),
                complete=bool(item.get("complete", False)),
            )
            for item in document.get("sections", ())
            if isinstance(item, dict)
        )
        contexts = tuple(
            PromptContext(
                name=str(item["name"]),
                order=int(item["order"]),
                text=str(item["text"]),
            )
            for item in document.get("contexts", ())
            if isinstance(item, dict)
        )
    except KeyError as exc:
        raise ValueError(f"prompt assembly config {path}: an entry has no {exc}") from None
    except (TypeError, ValueError) as exc:
        raise ValueError(f"prompt assembly config {path}: {exc}") from None
    return PromptAssembler(sections, contexts)


def _workspace_files_to_ask(
    workspace: Path, autonomy: Autonomy
) -> list[WorkspaceExtensionRequest]:
    # Scheduled tasks run unattended, so only where nobody has to be asked for each step; elsewhere
    # the file is left alone.
    return [
        request
        for request in workspace_file_requests(workspace)
        if request.kind != "schedule" or autonomy in {Autonomy.YOLO, Autonomy.FULL_ACCESS}
    ]


def _decided_now(decision: bool | Awaitable[bool]) -> bool:
    if not inspect.isawaitable(decision):
        return bool(decision)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        raise TypeError(
            "Async extension_approval_callback cannot be awaited in synchronous "
            "build_runtime() from a running event loop; "
            "use build_runtime_async() instead."
        )
    return asyncio.run(cast(Coroutine[Any, Any, bool], decision))


def _build_runtime_core(
    workspace_path: Path,
    database_path: Path,
    provider_config: ProviderConfig,
    autonomy: Autonomy,
    approval_callback: ApprovalCallback | None,
    egress_approval_callback: EgressApprovalCallback | None,
    approved_mcp_servers: list[McpServerConfig],
    approved_custom_defs: list[Any],
    event_listener: EventListener | None,
    sandbox_config: LocalSandboxConfig | None,
    sandbox_backend_id: str,
    sandbox_registry: SandboxBackendRegistry | None,
    parallel_tool_calls: bool,
    profile_turns: bool,
    sqlite_synchronous: str,
    optimizer: Any,
    prompt_assembler: Any,
    scheduled_tasks: Any,
    openapi_operations: Sequence[OpenApiOperation] = (),
    writer_lock_group: ProcessWriteLockGroup | None = None,
    subagents: SubagentLauncher | None = None,
    phone_jobs: PhoneJobLauncher | None = None,
    extra_tools: Sequence[Tool] = (),
    tool_hooks: ToolHooks | None = None,
    yolo_rules: YoloRules = DEFAULT_YOLO_RULES,
    estimate_unlisted_cost: bool = False,
    schedule_local_clock: bool = False,
) -> ApplicationRuntime:
    # Stack-managed resource allocation (R18 & R28)
    cleanup_stack: list[Callable[[], Any]] = []
    try:
        lock_path = database_writer_lock_path(database_path)
        write_lock = (
            ProcessWriteLock(lock_path)
            if writer_lock_group is None
            else writer_lock_group.lease(lock_path)
        )
        write_lock.acquire()
        cleanup_stack.append(write_lock.release)

        store = SQLiteEventStore(database_path, synchronous=sqlite_synchronous)
        cleanup_stack.append(store.close)

        if isinstance(write_lock, ProcessWriteLockLease):
            write_lock.run_once(
                ("workspace_recovery", workspace_path),
                lambda: recover_workspace_file_writes(store, str(workspace_path)),
            )
        else:
            recover_workspace_file_writes(store, str(workspace_path))
        events = EventBus()
        if event_listener is not None:
            events.subscribe(event_listener)

        if isinstance(write_lock, ProcessWriteLockLease):
            jobs = BackgroundJobManager(
                workspace_path, store, events.publish, reconcile_on_start=False
            )
        else:
            jobs = BackgroundJobManager(workspace_path, store, events.publish)
        cleanup_stack.append(lambda: _close_resource_sync(jobs))
        if isinstance(write_lock, ProcessWriteLockLease):
            write_lock.run_once(("background_jobs_recovery", workspace_path), jobs.reconcile)

        selected_sandbox_backend = resolve_sandbox_backend_id(sandbox_backend_id, autonomy)
        registry = sandbox_registry or SandboxBackendRegistry.default(
            sandbox_config,
            include_host_staged=selected_sandbox_backend == "host-staged",
        )
        sandbox = registry.create(
            selected_sandbox_backend,
            workspace_path,
        )
        cleanup_stack.append(lambda: _close_resource_sync(sandbox))

        tools = ToolRegistry.for_workspace(
            workspace_path,
            store,
            sandbox_backend=sandbox,
            allow_host_process=autonomy is not Autonomy.YOLO or yolo_rules.host_process,
            background_jobs=jobs,
            file_versions=FileVersions(database_path.with_name("file-versions")),
            file_batches=FileBatchStore(database_path.with_name("file-batches")),
        )
        tools.register(CodeMapTool(workspace_path))
        if subagents is not None:
            tools.register(DelegateTasksTool(subagents))
        if phone_jobs is not None:
            tools.register(PhoneTaskTool(phone_jobs))
        knowledge = knowledge_store(knowledge_root(database_path))
        for tool in knowledge_tools(knowledge, workspace_path):
            tools.register(tool)
        # Tools the embedding app adds (the desktop's use_skill).
        for extra in extra_tools:
            tools.register(extra)
        for operation in openapi_operations:
            tools.register(OpenApiGetTool(operation))

        mcp_host: McpHost | None = None
        if approved_mcp_servers:
            mcp_host = build_mcp_host(workspace_path, approved_mcp_servers)
            if mcp_host is not None:
                cleanup_stack.append(mcp_host.close_sync)
                for proxy in mcp_host.tools():
                    tools.register(proxy)
        # Last, so a custom tool named like any tool above is the one left out (and named in
        # Agent settings).
        skipped_custom_tools: dict[str, str] = {}
        for definition in approved_custom_defs:
            if not tools.register_unless_taken(CustomCommandTool(workspace_path, definition)):
                skipped_custom_tools[definition.name] = str(definition.path)

        # Hooks that judge a call by what its tool does (the desktop's project rules) see the tools.
        bind_tools = getattr(tool_hooks, "bind_tools", None)
        if callable(bind_tools):
            bind_tools(tools.specs())

        policy = WorkspacePolicy(workspace_path, autonomy, approval_callback, yolo_rules=yolo_rules)
        egress_policy = ProviderEgressPolicy(
            provider_config.base_url,
            autonomy,
            egress_approval_callback,
        )
        provider = create_provider(provider_config)
        cleanup_stack.append(lambda: _close_resource_sync(provider))

        raw_trace = RawConversationTrace.for_database(database_path)
        service = ApplicationService(
            store,
            provider,
            tools,
            policy,
            events,
            egress_policy=egress_policy,
            execution_workspace=workspace_path,
            execution_autonomy=autonomy,
            optimizer=optimizer,
            prompt_assembler=prompt_assembler,
            parallel_tool_calls=parallel_tool_calls,
            profile_turns=profile_turns,
            # With none, the runner does not build each request's payload just to discard it.
            raw_trace=raw_trace if raw_trace.enabled else None,
            tool_hooks=tool_hooks,
            estimate_unlisted_cost=estimate_unlisted_cost,
        )

        scheduler_factory: Callable[[], ScheduledTaskHost | None] | None = None
        if scheduled_tasks:

            def run_prompt(prompt: str) -> Any:
                async def execute() -> None:
                    task_session = service.create_session(
                        workspace_path,
                        mode=Mode.TASK,
                        autonomy=autonomy,
                        title=f"Scheduled: {prompt[:60]}",
                    )
                    await service.run(task_session, prompt, provider_config.model)

                return execute()

            def build_scheduler() -> ScheduledTaskHost | None:
                # The tasks that were allowed, not what the file says by the time this runs.
                return build_scheduled_host(
                    workspace_path,
                    run_prompt,
                    scheduled_tasks,
                    **({"local_clock": True} if schedule_local_clock else {}),
                )

            scheduler_factory = build_scheduler

        runtime = ApplicationRuntime(
            service,
            provider,
            store,
            write_lock,
            database_path,
            database_path.parent / "backups",
            sandbox=sandbox,
            jobs=jobs,
            mcp=mcp_host,
            knowledge=knowledge,
            _scheduler_factory=scheduler_factory,
            skipped_custom_tools=skipped_custom_tools,
        )
        if scheduler_factory is not None:
            cleanup_stack.append(lambda: _close_resource_sync(runtime.scheduler))
            if isinstance(write_lock, ProcessWriteLockLease):
                runtime._scheduler_claim_key = ("scheduled_tasks", workspace_path)
                runtime._scheduler_loop = asyncio.get_running_loop()
                owns_scheduler = write_lock.claim(
                    runtime._scheduler_claim_key,
                    on_available=runtime._queue_scheduler_activation,
                )
            else:
                owns_scheduler = True
            if owns_scheduler:
                runtime._start_scheduler()
        cleanup_stack.clear()
        return runtime
    except BaseException:
        for cleanup_fn in reversed(cleanup_stack):
            with suppress(BaseException):
                cleanup_fn()
        raise


def build_runtime(
    workspace: str | Path,
    database: str | Path,
    provider_config: ProviderConfig,
    *,
    autonomy: Autonomy = Autonomy.WORKSPACE,
    approval_callback: ApprovalCallback | None = None,
    egress_approval_callback: EgressApprovalCallback | None = None,
    extension_approval_callback: ExtensionApprovalCallback | None = None,
    allow_workspace_extensions: bool = False,
    event_listener: EventListener | None = None,
    sandbox_config: LocalSandboxConfig | None = None,
    sandbox_backend_id: str = "host-staged",
    sandbox_registry: SandboxBackendRegistry | None = None,
    parallel_tool_calls: bool = False,
    profile_turns: bool = False,
    sqlite_synchronous: str = "FULL",
) -> ApplicationRuntime:
    provider_config.validate()
    workspace_path = Path(workspace).resolve(strict=True)
    database_path = Path(database).expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    approved_files = {
        request.kind
        for request in _workspace_files_to_ask(workspace_path, autonomy)
        if _decided_now(
            workspace_file_decision(
                request, allow_workspace_extensions, extension_approval_callback
            )
        )
    }
    optimizer = _load_model_optimizer(workspace_path) if "optimizations" in approved_files else None
    prompt_assembler = (
        _load_prompt_assembler(workspace_path) if "prompt_assembly" in approved_files else None
    )
    scheduled_tasks = load_scheduled_tasks(workspace_path) if "schedule" in approved_files else ()
    openapi_operations = (
        load_openapi_file(workspace_path / ".agent" / "openapi.json")
        if "openapi" in approved_files
        else ()
    )

    # Extension discovery & authorization (R01)
    mcp_servers = load_mcp_servers(workspace_path)
    approved_mcp_servers: list[McpServerConfig] = []
    for server in mcp_servers:
        req = build_mcp_extension_request(server, workspace_path)
        if allow_workspace_extensions:
            approved_mcp_servers.append(server)
        elif extension_approval_callback is not None:
            decision = extension_approval_callback(req)
            if inspect.isawaitable(decision):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    raise TypeError(
                        "Async extension_approval_callback cannot be awaited in synchronous "
                        "build_runtime() from a running event loop; "
                        "use build_runtime_async() instead."
                    )
                is_approved = asyncio.run(cast(Coroutine[Any, Any, bool], decision))
            else:
                is_approved = bool(decision)
            if is_approved:
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
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    raise TypeError(
                        "Async extension_approval_callback cannot be awaited in synchronous "
                        "build_runtime() from a running event loop; "
                        "use build_runtime_async() instead."
                    )
                is_approved = asyncio.run(cast(Coroutine[Any, Any, bool], decision))
            else:
                is_approved = bool(decision)
            if is_approved:
                approved_custom_defs.append(cdef)
        else:
            command_str = " ".join((cdef.executable, *cdef.argv_template))
            raise ExtensionApprovalRequiredError(
                f"workspace custom tool {cdef.name!r} requires authorization "
                f"to start command: {command_str}"
            )

    return _build_runtime_core(
        workspace_path=workspace_path,
        database_path=database_path,
        provider_config=provider_config,
        autonomy=autonomy,
        approval_callback=approval_callback,
        egress_approval_callback=egress_approval_callback,
        approved_mcp_servers=approved_mcp_servers,
        approved_custom_defs=approved_custom_defs,
        event_listener=event_listener,
        sandbox_config=sandbox_config,
        sandbox_backend_id=sandbox_backend_id,
        sandbox_registry=sandbox_registry,
        parallel_tool_calls=parallel_tool_calls,
        profile_turns=profile_turns,
        sqlite_synchronous=sqlite_synchronous,
        optimizer=optimizer,
        prompt_assembler=prompt_assembler,
        scheduled_tasks=scheduled_tasks,
        openapi_operations=openapi_operations,
    )


async def build_runtime_async(
    workspace: str | Path,
    database: str | Path,
    provider_config: ProviderConfig,
    *,
    autonomy: Autonomy = Autonomy.WORKSPACE,
    approval_callback: ApprovalCallback | None = None,
    egress_approval_callback: EgressApprovalCallback | None = None,
    extension_approval_callback: ExtensionApprovalCallback | None = None,
    allow_workspace_extensions: bool = False,
    event_listener: EventListener | None = None,
    sandbox_config: LocalSandboxConfig | None = None,
    sandbox_backend_id: str = "host-staged",
    sandbox_registry: SandboxBackendRegistry | None = None,
    parallel_tool_calls: bool = False,
    profile_turns: bool = False,
    sqlite_synchronous: str = "FULL",
    writer_lock_group: ProcessWriteLockGroup | None = None,
    subagents: SubagentLauncher | None = None,
    phone_jobs: PhoneJobLauncher | None = None,
    extra_tools: Sequence[Tool] = (),
    tool_hooks: ToolHooks | None = None,
    yolo_rules: YoloRules = DEFAULT_YOLO_RULES,
    skip_broken_workspace_files: bool = False,
    estimate_unlisted_cost: bool = False,
    schedule_local_clock: bool = False,
) -> ApplicationRuntime:
    provider_config.validate()
    workspace_path = Path(workspace).resolve(strict=True)
    database_path = Path(database).expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    # The approved files by kind, each with its workspace path.
    approved_files: dict[str, str] = {}
    for request in _workspace_files_to_ask(workspace_path, autonomy):
        file_decision = workspace_file_decision(
            request, allow_workspace_extensions, extension_approval_callback
        )
        if inspect.isawaitable(file_decision):
            file_decision = await file_decision
        if file_decision:
            approved_files[request.kind] = request.identifier
    skipped_files: dict[str, str] = {}

    def load_approved(kind: str, load: Callable[[], Any], unused: Any) -> Any:
        if kind not in approved_files:
            return unused
        try:
            return load()
        except Exception as exc:
            # The desktop opens the folder without an approved file that turns out to be broken
            # and says which and why in Agent settings; elsewhere the error, naming the file,
            # still stops the start.
            if not skip_broken_workspace_files:
                raise
            _LOGGER.warning("starting without %s: %s", approved_files[kind], exc)
            skipped_files[approved_files[kind]] = " ".join(str(exc).split())[:1000]
            return unused

    optimizer = load_approved("optimizations", lambda: _load_model_optimizer(workspace_path), None)
    prompt_assembler = load_approved(
        "prompt_assembly", lambda: _load_prompt_assembler(workspace_path), None
    )
    scheduled_tasks = load_approved("schedule", lambda: load_scheduled_tasks(workspace_path), ())
    openapi_operations = load_approved(
        "openapi", lambda: load_openapi_file(workspace_path / ".agent" / "openapi.json"), ()
    )

    # Extension discovery & authorization (R01)
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

    runtime = _build_runtime_core(
        workspace_path=workspace_path,
        database_path=database_path,
        provider_config=provider_config,
        autonomy=autonomy,
        approval_callback=approval_callback,
        egress_approval_callback=egress_approval_callback,
        approved_mcp_servers=approved_mcp_servers,
        approved_custom_defs=approved_custom_defs,
        event_listener=event_listener,
        sandbox_config=sandbox_config,
        sandbox_backend_id=sandbox_backend_id,
        sandbox_registry=sandbox_registry,
        parallel_tool_calls=parallel_tool_calls,
        profile_turns=profile_turns,
        sqlite_synchronous=sqlite_synchronous,
        optimizer=optimizer,
        prompt_assembler=prompt_assembler,
        scheduled_tasks=scheduled_tasks,
        openapi_operations=openapi_operations,
        writer_lock_group=writer_lock_group,
        subagents=subagents,
        phone_jobs=phone_jobs,
        extra_tools=extra_tools,
        tool_hooks=tool_hooks,
        yolo_rules=yolo_rules,
        estimate_unlisted_cost=estimate_unlisted_cost,
        schedule_local_clock=schedule_local_clock,
    )
    runtime.skipped_workspace_files = skipped_files
    return runtime
