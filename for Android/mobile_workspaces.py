"""Persistent workspace registration and per-session mobile routing.

The desktop runtime historically exposed one execution directory.  Android can
have several user-selected directories, so this module keeps the directory
catalog independent from the UI and routes tasks by their durable session id.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import threading
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from mobile_protocol import MobileEvent, MobileTask, MobileTaskRequest, TaskState
from mobile_runtime_controller import _decode_sync_cursor, _encode_sync_cursor
from mobile_task_store import MobileTaskStore

from agent_workspace.core.session import Session
from agent_workspace.storage.sqlite import SQLiteEventStore
from agent_workspace.tools.base import ToolError
from agent_workspace.tools.filesystem import _scan_file, atomic_write
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

_CATALOG_VERSION = 1
_MAX_CATALOG_BYTES = 512 * 1024
_MAX_WORKSPACE_NAME = 120
_active_controller: ContextVar[Any | None] = ContextVar("mobile_workspace_controller", default=None)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _canonical_directory(value: str | Path, *, create: bool = False) -> Path:
    if not isinstance(value, (str, Path)):
        raise ValueError("workspace path must be a directory")
    raw = Path(value).expanduser()
    if not raw.is_absolute():
        raise ValueError("workspace path must be absolute")
    if create and not raw.exists():
        try:
            raw.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError("workspace directory could not be created") from exc
    try:
        return WorkspacePaths(raw).root
    except (OSError, RuntimeError, WorkspacePathError) as exc:
        raise ValueError("workspace path must be an existing safe directory") from exc


@dataclass(frozen=True, slots=True)
class MobileWorkspace:
    workspace_id: str
    name: str
    path: str
    created_at: str
    updated_at: str
    is_default: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.workspace_id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "path": self.path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_default": self.is_default,
        }


class MobileWorkspaceCatalog:
    """A small, atomic, versioned catalog of user-selected directories."""

    def __init__(self, database: str | Path, default_path: str | Path) -> None:
        self.database = Path(database).expanduser().resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.path = self.database.with_name("mobile-workspaces-v1.json")
        self._lock = threading.RLock()
        self._workspaces: dict[str, MobileWorkspace] = {}
        self._default_id = ""
        self._digest: str | None = None
        self._load(default_path)

    def _load(self, default_path: str | Path) -> None:
        with self._lock:
            try:
                self._digest, raw = _scan_file(
                    self.path,
                    max_scan_bytes=_MAX_CATALOG_BYTES,
                    retain_limit=_MAX_CATALOG_BYTES,
                )
            except (OSError, ToolError) as exc:
                raise OSError("mobile workspace catalog cannot be read") from exc
            if raw is None:
                root = _canonical_directory(default_path)
                stamp = _now()
                workspace = MobileWorkspace(
                    workspace_id=str(uuid4()),
                    name=root.name or "Workspace",
                    path=str(root),
                    created_at=stamp,
                    updated_at=stamp,
                    is_default=True,
                )
                self._workspaces = {workspace.workspace_id: workspace}
                self._default_id = workspace.workspace_id
                self._save()
                return
            try:
                document = json.loads(raw.decode("utf-8"))
                self._decode(document)
            except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise OSError("mobile workspace catalog is invalid") from exc
            if not self._workspaces:
                raise OSError("mobile workspace catalog has no workspaces")

    def _decode(self, document: object) -> None:
        if (
            not isinstance(document, dict)
            or type(document.get("version")) is not int
            or document["version"] != _CATALOG_VERSION
        ):
            raise ValueError("unsupported workspace catalog version")
        default_id = document.get("default_workspace_id")
        entries = document.get("workspaces")
        if not isinstance(default_id, str) or not isinstance(entries, list) or not entries:
            raise ValueError("workspace catalog fields are invalid")
        decoded: dict[str, MobileWorkspace] = {}
        for item in entries:
            if not isinstance(item, dict):
                raise ValueError("workspace catalog entry is invalid")
            workspace_id = item.get("id", item.get("workspace_id"))
            name = item.get("name")
            path = item.get("path")
            created_at = item.get("created_at")
            updated_at = item.get("updated_at")
            if (
                not isinstance(workspace_id, str)
                or not workspace_id
                or not isinstance(name, str)
                or not name.strip()
                or len(name) > _MAX_WORKSPACE_NAME
                or not isinstance(path, str)
                or any(ord(character) < 32 for character in name + path)
                or not isinstance(created_at, str)
                or not isinstance(updated_at, str)
                or workspace_id in decoded
            ):
                raise ValueError("workspace catalog entry is invalid")
            root = Path(path).expanduser()
            if not root.is_absolute():
                raise ValueError("workspace catalog path is not absolute")
            root = root.resolve()
            decoded[workspace_id] = MobileWorkspace(
                workspace_id,
                name.strip(),
                str(root),
                created_at,
                updated_at,
                workspace_id == default_id,
            )
        if default_id not in decoded:
            raise ValueError("workspace catalog default is missing")
        if len({os.path.normcase(item.path) for item in decoded.values()}) != len(decoded):
            raise ValueError("workspace catalog contains duplicate paths")
        self._workspaces = decoded
        self._default_id = default_id

    def _save(self) -> None:
        document = {
            "version": _CATALOG_VERSION,
            "default_workspace_id": self._default_id,
            "workspaces": [item.to_dict() for item in self._workspaces.values()],
        }
        encoded = json.dumps(
            document, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ).encode()
        if len(encoded) > _MAX_CATALOG_BYTES:
            raise OSError("mobile workspace catalog exceeds its storage limit")
        try:
            _, self._digest = atomic_write(
                WorkspacePaths(self.path.parent), self.path, encoded, self._digest
            )
        except (OSError, WorkspacePathError) as exc:
            raise OSError("mobile workspace catalog cannot be saved") from exc

    def list(self) -> list[MobileWorkspace]:
        with self._lock:
            return list(self._workspaces.values())

    def default(self) -> MobileWorkspace:
        with self._lock:
            return self._workspaces[self._default_id]

    def get(self, workspace_id: str) -> MobileWorkspace:
        if not isinstance(workspace_id, str) or not workspace_id:
            raise ValueError("workspace_id must be a nonempty string")
        with self._lock:
            try:
                return self._workspaces[workspace_id]
            except KeyError:
                raise KeyError(workspace_id) from None

    def by_path(self, path: str | Path) -> MobileWorkspace | None:
        root = Path(path).expanduser().resolve()
        with self._lock:
            return next(
                (item for item in self._workspaces.values() if Path(item.path) == root), None
            )

    def ensure(self, path: str | Path, *, name: str | None = None) -> MobileWorkspace:
        existing = self.by_path(path)
        if existing is not None:
            return existing
        root = _canonical_directory(path)
        return self.add(name or root.name or "Workspace", root)

    def add(self, name: str, path: str | Path, *, create: bool = False) -> MobileWorkspace:
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name.strip()) > _MAX_WORKSPACE_NAME
            or any(ord(character) < 32 or ord(character) == 127 for character in name)
        ):
            raise ValueError("workspace name must contain 1 to 120 characters")
        if type(create) is not bool:
            raise ValueError("create must be boolean")
        root = _canonical_directory(path, create=create)
        with self._lock:
            for item in self._workspaces.values():
                if Path(item.path) == root:
                    return item
                if item.name.casefold() == name.strip().casefold():
                    raise ValueError("workspace name is already in use")
            stamp = _now()
            item = MobileWorkspace(str(uuid4()), name.strip(), str(root), stamp, stamp, False)
            self._workspaces[item.workspace_id] = item
            try:
                self._save()
            except BaseException:
                self._workspaces.pop(item.workspace_id, None)
                raise
            return item

    def remove(self, workspace_id: str) -> None:
        with self._lock:
            self.get(workspace_id)
            if workspace_id == self._default_id:
                raise ValueError("the default workspace cannot be removed")
            previous = self._workspaces.pop(workspace_id)
            try:
                self._save()
            except BaseException:
                self._workspaces[workspace_id] = previous
                raise


class _ScopedService:
    def __init__(
        self, runtime: Any, path: str | Path, catalog: MobileWorkspaceCatalog | None = None
    ):
        self._runtime = runtime
        self._execution_workspace = Path(path).resolve()
        self._catalog = catalog

    def __getattr__(self, name: str) -> Any:
        return getattr(self._runtime.service, name)

    def get_session(self, session_id: str) -> Session:
        session = self._runtime.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        if self._catalog is not None:
            if self._catalog.by_path(session.workspace) is None:
                raise KeyError(session_id)
        elif Path(session.workspace).resolve() != self._execution_workspace:
            raise KeyError(session_id)
        return session

    def create_session(self, workspace: str | Path, **options: Any) -> Session:
        root = _canonical_directory(workspace)
        if self._catalog is not None:
            if self._catalog.by_path(root) is None:
                raise ValueError("workspace is not registered")
        elif root != self._execution_workspace:
            raise ValueError("workspace does not match the selected scope")
        autonomy = getattr(self._runtime.service, "_execution_autonomy", None)
        if autonomy is not None and options.get("autonomy", autonomy) != autonomy:
            raise ValueError("session autonomy does not match the runtime execution scope")
        session = Session(workspace=str(root), **options)
        self._runtime.store.create_session(session)
        return session


class MobileScopedRuntime:
    """Reuse the event store while selecting a directory for presentation APIs."""

    def __init__(
        self, runtime: Any, path: str | Path, *, catalog: MobileWorkspaceCatalog | None = None
    ):
        self._runtime = runtime
        self.service = _ScopedService(runtime, path, catalog)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._runtime, name)


ControllerFactory = Callable[[Session], Awaitable[Any] | Any]


class MobileWorkspaceController:
    """Route mobile operations to a controller owned by each conversation.

    A factory is deliberately injected: creating a second ``ApplicationRuntime``
    needs provider credentials and Android lifecycle state, which belongs to the
    embedding layer.  The router only owns session and task isolation.
    """

    def __init__(
        self,
        store: SQLiteEventStore,
        catalog: MobileWorkspaceCatalog,
        controller_factory: ControllerFactory | None = None,
        *,
        base_controller: Any | None = None,
    ) -> None:
        self.store = store
        self.catalog = catalog
        self.controller_factory = controller_factory
        self.base_controller = base_controller
        self._controllers: dict[str, Any] = {}
        self._owned_runtimes: dict[str, Any] = {}
        self._starts: set[str] = set()
        self._lock = asyncio.Lock()
        self._started = False
        self._closing = False
        self._maintenance = False
        self._admitting = 0
        self._connection_epoch = 0
        self._recovered_tasks = 0
        self._runtime_view = (
            MobileScopedRuntime(base_controller.runtime, catalog.default().path, catalog=catalog)
            if base_controller is not None
            else None
        )

    def set_controller_factory(self, factory: ControllerFactory) -> None:
        self.controller_factory = factory

    @property
    def runtime(self) -> Any:
        if self.base_controller is None:
            raise RuntimeError("workspace controller has no base controller")
        active = _active_controller.get()
        return active.runtime if active is not None else self._runtime_view

    @property
    def default_model(self) -> str | None:
        return getattr(self.base_controller, "default_model", None)

    @property
    def default_reasoning_effort(self) -> str:
        return getattr(self.base_controller, "default_reasoning_effort", "auto")

    @property
    def protocol(self) -> str | None:
        return getattr(self.base_controller, "protocol", None)

    @property
    def base_url(self) -> str | None:
        return getattr(self.base_controller, "base_url", None)

    @property
    def tasks(self) -> MobileTaskStore:
        return MobileTaskStore(self.store)

    def __getattr__(self, name: str) -> Any:
        base = object.__getattribute__(self, "base_controller")
        if base is not None:
            return getattr(base, name)
        raise AttributeError(name)

    def _session(self, session_id: str) -> Session:
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        if self.catalog.by_path(session.workspace) is None:
            raise KeyError(session_id)
        return session

    def session_for_task(self, task_id: str) -> Session:
        task = MobileTaskStore(self.store).get(task_id)
        return self._session(task.session_id)

    async def controller_for(self, session_id: str) -> Any:
        if self._closing:
            raise RuntimeError("mobile workspace controller is closing")
        session = self._session(session_id)
        async with self._lock:
            existing = self._controllers.get(session_id)
            if existing is not None:
                return existing
            if self.controller_factory is not None:
                value = self.controller_factory(session)
                value = await value if inspect.isawaitable(value) else value
                runtime = None
                if isinstance(value, tuple) and len(value) == 2:
                    value, runtime = value
                controller = value
                if controller is None:
                    raise RuntimeError("workspace controller factory returned no controller")
                tasks = getattr(controller, "tasks", None)
                if tasks is not None and getattr(tasks, "session_id", None) != session_id:
                    raise ValueError("child controller task store must be scoped to its session_id")
                self._controllers[session_id] = controller
                if runtime is not None:
                    self._owned_runtimes[session_id] = runtime
                elif getattr(controller, "runtime", None) is not getattr(
                    self.base_controller, "runtime", None
                ):
                    self._owned_runtimes[session_id] = getattr(controller, "runtime", None)
            elif self.base_controller is not None:
                execution = getattr(
                    self.base_controller.runtime.service, "_execution_workspace", None
                )
                if (
                    execution is None
                    or Path(execution).resolve() != Path(session.workspace).resolve()
                ):
                    raise RuntimeError("workspace runtime is not available")
                controller = self.base_controller
                self._controllers[session_id] = controller
            else:
                raise RuntimeError("workspace controller factory is not configured")
            try:
                if session_id not in self._starts:
                    start = getattr(controller, "start", None)
                    if callable(start):
                        result = start()
                        if inspect.isawaitable(result):
                            await result
                    self._starts.add(session_id)
            except BaseException:
                self._controllers.pop(session_id, None)
                owned = self._owned_runtimes.pop(session_id, None)
                if owned is not None:
                    close = getattr(owned, "aclose", None)
                    if callable(close):
                        await close()
                raise
            return controller

    def list_sessions(self, workspace_id: str | None = None) -> list[Session]:
        root = self.catalog.get(workspace_id).path if workspace_id is not None else None
        return [
            session
            for session in self.store.list_sessions(limit=2_147_483_647)
            if self.catalog.by_path(session.workspace) is not None
            and (root is None or Path(session.workspace).resolve() == Path(root).resolve())
        ]

    def _tasks(
        self, *, workspace_id: str | None = None, session_id: str | None = None
    ) -> list[MobileTask]:
        root = self.catalog.get(workspace_id).path if workspace_id is not None else None
        visible = {session.id for session in self.list_sessions(workspace_id)}
        return [
            task
            for task in MobileTaskStore(self.store, workspace=root, session_id=session_id).list()
            if task.session_id in visible
        ]

    def get(self, task_id: str) -> MobileTask:
        task = MobileTaskStore(self.store).get(task_id)
        self._session(task.session_id)
        return task

    def list(
        self, session_id: str | None = None, workspace_id: str | None = None
    ) -> list[MobileTask]:
        if session_id is not None:
            self._session(session_id)
        return self._tasks(workspace_id=workspace_id, session_id=session_id)

    def events(self, task_id: str, after: int = 0) -> list[MobileEvent]:
        task = self.get(task_id)
        return MobileTaskStore(self.store, session_id=task.session_id).events(task_id, after)

    def pending_approvals(self, task_id: str | None = None) -> list[dict[str, object]]:
        if task_id is not None:
            task = self.get(task_id)
            controller = self._controllers.get(task.session_id)
            if controller is not None:
                return controller.pending_approvals(task_id)
            return []
        result: list[dict[str, object]] = []
        for controller in tuple(self._controllers.values()):
            result.extend(controller.pending_approvals())
        return result

    async def submit(self, request: MobileTaskRequest, **kwargs: Any) -> MobileTask:
        self._ensure_admission()
        self._admitting += 1
        try:
            controller = await self.controller_for(request.session_id)
            self._bind_execution(controller, kwargs)
            self._ensure_admission()
            return await controller.submit(request, **kwargs)
        finally:
            self._admitting -= 1

    async def cancel(self, task_id: str) -> MobileTask:
        controller = await self.controller_for(self.get(task_id).session_id)
        return await controller.cancel(task_id)

    async def resume(self, task_id: str, **kwargs: Any) -> MobileTask:
        self._ensure_admission()
        self._admitting += 1
        try:
            controller = await self.controller_for(self.get(task_id).session_id)
            self._bind_execution(controller, kwargs)
            self._ensure_admission()
            return await controller.resume(task_id, **kwargs)
        finally:
            self._admitting -= 1

    async def steer(self, task_id: str, prompt: str, *, input_id: str | None = None) -> dict[str, Any]:
        """Add a user message to a running task; the runner applies it between model/tool rounds."""
        task = self.get(task_id)
        if str(task.state) not in {"running", "waiting_approval"}:
            raise RuntimeError("turn_not_active")
        service = await self.service_for_session(task.session_id)
        received_id = await service.runner.steer_turn(task.session_id, prompt, input_id=input_id)
        return {"task_id": task.task_id, "input_id": received_id}

    async def wait(self, task_id: str) -> MobileTask:
        controller = await self.controller_for(self.get(task_id).session_id)
        return await controller.wait(task_id)

    async def resolve_approval(self, request_id: str, allowed: bool, scope: str) -> bool:
        for controller in tuple(self._controllers.values()):
            if await controller.resolve_approval(request_id, allowed, scope):
                return True
        return False

    def status(self) -> dict[str, Any]:
        anchor = self.base_controller.status() if self.base_controller is not None else {}
        states = [controller.status() for controller in tuple(self._controllers.values())]
        active = [item.get("active_task_id") for item in states if item.get("active_task_id")]
        queued = sum(int(item.get("queued_tasks", 0)) for item in states)
        restart = bool(anchor.get("restart_required")) or any(
            bool(item.get("restart_required")) for item in states
        )
        maintenance = self._maintenance or bool(anchor.get("maintenance"))
        stopping = self._closing or restart or anchor.get("state") == "stopping"
        return {
            **anchor,
            "state": "stopping" if stopping else "ready",
            "maintenance": maintenance,
            "active_task_id": active[0] if active else None,
            "active_task_ids": active,
            "active_tasks": len(active),
            "running_tasks": len(active),
            "queued_tasks": queued,
            "pending_approvals": len(self.pending_approvals()),
            "restart_required": restart,
            "task_admission_ready": not stopping
            and not maintenance
            and bool(anchor.get("task_admission_ready", True)),
            "connection_epoch": self._connection_epoch,
            "recovered_tasks": self._recovered_tasks,
            "last_sequence": max((task.last_sequence for task in self._tasks()), default=0),
        }

    def sync(
        self, *, after: int = 0, limit: int = 200, cursor: str | None = None
    ) -> dict[str, Any]:
        if after < 0 or limit < 1 or limit > 1000:
            raise ValueError("sync cursor or limit is invalid")
        positions: dict[str, int] = {}
        if cursor is not None:
            if after:
                raise ValueError("after and cursor cannot be combined")
            positions = _decode_sync_cursor(cursor)
        elif after:
            sessions = {task.session_id for task in self._tasks()}
            if len(sessions) > 1:
                raise ValueError("cursor is required for sync across multiple sessions")
            positions = {session_id: after for session_id in sessions}
        events: list[tuple[str, MobileEvent]] = []
        for task in self._tasks():
            for event in self.events(task.task_id, positions.get(task.session_id, 0)):
                events.append((task.session_id, event))
        events.sort(key=lambda item: (item[1].sequence, item[0], item[1].event_id))
        visible = events[:limit]
        next_positions = dict(positions)
        for session_id, event in visible:
            next_positions[session_id] = event.sequence
        encoded = _encode_sync_cursor(next_positions)
        return {
            "tasks": [task.to_dict() for task in self._tasks()],
            "events": [event.to_dict() for _, event in visible],
            "after": after,
            "next_sequence": max(next_positions.values(), default=after),
            "next_cursor": encoded,
            "has_more": len(events) > len(visible),
            "connection_epoch": self.status()["connection_epoch"],
        }

    async def start(self) -> list[MobileTask]:
        if self._started:
            return []
        self._started = True
        self._connection_epoch += 1
        recovered = []
        for task in self._tasks():
            if task.state in {TaskState.QUEUED, TaskState.RUNNING, TaskState.WAITING_APPROVAL}:
                recovered.append(
                    self.tasks.transition(
                        task.task_id,
                        TaskState.INTERRUPTED,
                        reason="runtime restarted",
                        resume_available=True,
                    )
                )
        self._recovered_tasks = len(recovered)
        return recovered

    async def reconnect(self) -> dict[str, Any]:
        if not self._started:
            await self.start()
        return self.sync()

    async def handle_runtime_event(self, event) -> None:
        controller = self._controllers.get(event.session_id)
        if controller is not None:
            await controller.handle_runtime_event(event)

    def _ensure_admission(self) -> None:
        if self._closing:
            raise RuntimeError("mobile workspace controller is closing")
        if self._maintenance:
            from mobile_runtime_controller import MobileRuntimeNotReady

            raise MobileRuntimeNotReady(
                "wait for model or tool maintenance to finish before starting tasks",
                code="runtime_maintenance",
            )
        if self.base_controller is not None:
            self.base_controller._ensure_task_admission()

    @asynccontextmanager
    async def maintenance(self):
        if self.base_controller is None:
            raise RuntimeError("workspace controller has no maintenance anchor")
        self._ensure_admission()
        state = self.status()
        if state["active_task_id"] or state["queued_tasks"] or self._admitting:
            raise ValueError(
                "stop or finish active and queued tasks before changing models or tools"
            )
        self._maintenance = True
        try:
            async with self.base_controller.maintenance():
                yield
        finally:
            self._maintenance = False

    def prepare_provider_restart(self) -> None:
        if self.base_controller is None:
            raise RuntimeError("workspace controller has no maintenance anchor")
        self.base_controller.prepare_provider_restart()

    def _bound_controller(self) -> Any:
        controller = _active_controller.get()
        if controller is None:
            raise RuntimeError("workflow action is not bound to an active mobile session")
        return controller

    @staticmethod
    def _bind_execution(controller, options) -> None:
        execution = options.get("execution")
        if execution is None:
            return

        async def bound_execution(task):
            token = _active_controller.set(controller)
            try:
                return await execution(task)
            finally:
                _active_controller.reset(token)

        options["execution"] = bound_execution

    async def service_for_session(self, session_id: str) -> Any:
        controller = await self.controller_for(session_id)
        return controller.runtime.service

    async def authorize_replay_action(self, arguments, **kwargs):
        return await self._bound_controller().authorize_replay_action(arguments, **kwargs)

    async def dispatch_replay_action(self, arguments, execute):
        return await self._bound_controller().dispatch_replay_action(arguments, execute)

    async def aclose(self) -> None:
        self._closing = True
        errors = []
        for controller in tuple(dict.fromkeys(self._controllers.values())):
            if controller is self.base_controller:
                continue
            close = getattr(controller, "aclose", None)
            if callable(close):
                try:
                    result = close()
                    if inspect.isawaitable(result):
                        await result
                except Exception as exc:
                    errors.append(exc)
        seen = set()
        for runtime in tuple(self._owned_runtimes.values()):
            if runtime is None or id(runtime) in seen:
                continue
            seen.add(id(runtime))
            close = getattr(runtime, "aclose", None)
            if callable(close):
                try:
                    result = close()
                    if inspect.isawaitable(result):
                        await result
                except Exception as exc:
                    errors.append(exc)
        if errors:
            raise ExceptionGroup("mobile workspace shutdown failed", errors)
