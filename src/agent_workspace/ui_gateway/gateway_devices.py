"""Paired phones (device link): what they read and send, the tasks they hand over and the runtimes
started for them.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent_workspace.application.runtime_host import RuntimeHost, RuntimeSettings
from agent_workspace.config import (
    ProviderConfig,
)
from agent_workspace.core.events import Event
from agent_workspace.core.models import (
    MAX_IMAGES_PER_MESSAGE,
    ApprovalScope,
    Autonomy,
)
from agent_workspace.core.session import Session
from agent_workspace.policy.redaction import Redactor
from agent_workspace.providers.health import (
    provider_capabilities,
)
from agent_workspace.storage import (
    SQLiteEventStore,
)
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths
from agent_workspace.ui_gateway.device_hub import model_location
from agent_workspace.ui_gateway.device_link import (
    DeviceLinkError,
    DeviceTask,
    PairedDevice,
    TaskOptions,
    Upload,
)
from agent_workspace.ui_gateway.device_store import DeviceStoreError
from agent_workspace.ui_gateway.gateway_common import (
    _DEVICE_ACTIVITY_ARGUMENTS,
    _DEVICE_ACTIVITY_CHARS,
    _DEVICE_CONTENT_CHARS,
    _DEVICE_EVENT_LIMIT,
    _DEVICE_HOST_GRACE_SECONDS,
    _DEVICE_INBOX_LIMIT,
    _DEVICE_PENDING_ORIGINS,
    _DEVICE_RESULT_CHARS,
    _DEVICE_TURN_ENDS,
    _MAX_PROMPT_CHARS,
    _MAX_SESSIONS,
    _START_TIMEOUT_SECONDS,
    _TURN_ANSWERS_KEPT,
    GatewayError,
    GatewayReply,
    Host,
    _approval_display_text,
    _SessionHostContext,
)
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import (
    PROTOCOL_VERSION,
    CommandEnvelope,
)
from agent_workspace.ui_gateway.schedules import (
    OPEN_RUN_STATES,
)
from agent_workspace.ui_gateway.turn_files import start_turn_watch


class DeviceCommands(GatewayState):
    """Paired phones (device link): what they read and send, the tasks they hand over and the
    runtimes started for them.
    """

    def _device_command(self, command: CommandEnvelope) -> GatewayReply:
        """Phone connections: their settings, pairing and the paired phones."""
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        link = self._device_link
        try:
            if command.type == "devices.status":
                self._require_payload(command, set())
                document = link.status()
            elif command.type == "devices.configure":
                switches = ("enabled", "secure", "wake", "clipboard")
                self._require_payload(command, set(), optional={"port", *switches})
                values: dict[str, bool] = {}
                for key in switches:
                    value = command.payload.get(key)
                    if value is not None and type(value) is not bool:
                        raise GatewayError("invalid_command")
                    if value is not None:
                        values[key] = value
                port = command.payload.get("port")
                if port is not None and type(port) is not int:
                    raise GatewayError("invalid_command")
                document = link.configure(port=port, **values)
            elif command.type == "devices.update":
                self._require_payload(command, {"deviceId"}, optional={"scopes", "notifyTurns"})
                notify = command.payload.get("notifyTurns")
                if notify is not None and type(notify) is not bool:
                    raise GatewayError("invalid_command")
                document = link.update_device(
                    command.payload["deviceId"],
                    scopes=command.payload.get("scopes"),
                    notify_turns=notify,
                )
            elif command.type == "devices.reset":
                self._require_payload(command, set())
                document = link.reset()
            elif command.type == "devices.firewall.allow":
                # Returns at once; Windows' administrator confirmation is answered meanwhile.
                self._require_payload(command, set())
                document = link.allow_through_firewall()
            elif command.type == "devices.send":
                self._require_payload(
                    command, {"deviceId", "kind"}, optional={"path", "text", "sessionId"}
                )
                document = {**link.status(), "transfer": self._device_send(command.payload)}
            elif command.type == "devices.pairing.start":
                self._require_payload(command, {"scopes"})
                document = link.start_pairing(command.payload["scopes"])
            elif command.type == "devices.token.create":
                self._require_payload(command, {"name", "scopes"})
                device, device_token = link.create_token(
                    command.payload["name"], command.payload["scopes"]
                )
                # Shown once so the user can type it into the phone; only its hash is kept.
                document = {
                    **link.status(),
                    "created": {"device": device.document(), "deviceToken": device_token},
                }
            else:
                self._require_payload(command, {"deviceId"})
                document = link.revoke(command.payload["deviceId"])
        except DeviceLinkError as error:
            raise GatewayError(error.code) from None
        except (OSError, sqlite3.Error):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            f"{command.type}.result", {"epoch": self.epoch, **document}, session_id=None
        )

    def _device_send(self, payload: Mapping[str, object]) -> dict[str, object]:
        """Something for a paired phone to collect from its inbox: a file of the open folder, a
        text or link, or a conversation to continue on the phone."""
        device_id, kind = payload.get("deviceId"), payload.get("kind")
        if not isinstance(device_id, str) or self._device_link.registry.get(device_id) is None:
            raise GatewayError("unknown_device")
        hub = self._device_hub
        if kind == "file":
            raw = payload.get("path")
            if not isinstance(raw, str) or not raw:
                raise GatewayError("invalid_path")
            with self._lock:
                workspace = self._workspace
            if workspace is None:
                raise GatewayError("runtime_unconfigured")
            try:
                path = WorkspacePaths(workspace).resolve(raw)
            except WorkspacePathError:
                raise GatewayError("invalid_path") from None
            source = payload.get("sessionId")
            title = None
            if isinstance(source, str):
                with suppress(GatewayError):
                    title = self._workspace_session(source).title
            return hub.send_file(device_id, path, title)
        if kind == "text":
            text = payload.get("text")
            if not isinstance(text, str):
                raise GatewayError("invalid_text")
            return hub.send_text(device_id, text)
        if kind == "conversation":
            session_id = payload.get("sessionId")
            if not isinstance(session_id, str):
                raise GatewayError("invalid_session")
            return hub.send_conversation(device_id, session_id)
        raise GatewayError("invalid_command")

    def device_sessions(self) -> list[dict[str, object]]:
        """The open folder's conversations, for a paired phone (archived ones left out)."""
        with self._lock:
            workspace = self._workspace
            running = {
                session_id
                for session_id, context in self._session_hosts.items()
                if context.active_turn is not None or context.turn_requested
            }
            if self._host_session_id is not None and (self._active_turn or self._turn_requested):
                running.add(self._host_session_id)
            presentations = self._workspace_presentations()
            # A conversation open in a runtime runs with that runtime's autonomy.
            autonomies = {
                session_id: context.autonomy for session_id, context in self._session_hosts.items()
            }
            if self._host_session_id is not None and self._host is not None:
                autonomies[self._host_session_id] = self._autonomy
        if workspace is None or not self._database.is_file():
            return []
        try:
            sessions = SQLiteEventStore.list_sessions_read_only(
                self._database, _MAX_SESSIONS, workspace=workspace, exclude_run_sessions=True
            )
        except (OSError, ValueError, sqlite3.DatabaseError):
            raise DeviceLinkError("storage_unavailable", 503) from None
        documents: list[dict[str, object]] = []
        for session in sessions:
            presentation = presentations.get(session.id, {})
            if presentation.get("archived") is True:
                continue
            alias = presentation.get("alias")
            documents.append(
                {
                    "id": session.id,
                    "title": alias if isinstance(alias, str) and alias else session.title,
                    "workspace": session.workspace,
                    "updated_at": session.updated_at,
                    "running": session.id in running,
                    "autonomy": autonomies.get(session.id, session.autonomy).value,
                }
            )
        return documents

    def device_session_events(self, session_id: str) -> list[dict[str, object]] | None:
        """A conversation's recent messages and failures, in the Serve API's event shape."""
        try:
            session = self._workspace_session(session_id)
            events = SQLiteEventStore.list_session_events_of_types_read_only(
                self._database, session.id, frozenset({"message.created", "turn.failed"})
            )
        except GatewayError:
            return None
        except (OSError, ValueError, sqlite3.DatabaseError):
            raise DeviceLinkError("storage_unavailable", 503) from None
        documents: list[dict[str, object]] = []
        for event in events:
            data: dict[str, object]
            if event.type == "message.created":
                role = event.data.get("role")
                content = event.data.get("content")
                if role not in {"user", "assistant"} or not isinstance(content, str):
                    continue
                if not content.strip():
                    continue  # an assistant step that only called tools
                data = {"role": role, "content": content[:_DEVICE_CONTENT_CHARS]}
            else:
                message = event.data.get("message")
                data = {
                    "error_type": str(event.data.get("error_type", ""))[:128],
                    "message": Redactor().redact(message[:600]) if isinstance(message, str) else "",
                }
            documents.append(
                {
                    "id": event.id,
                    "type": event.type,
                    "sequence": event.sequence,
                    "created_at": event.created_at,
                    "data": data,
                }
            )
        return documents[-_DEVICE_EVENT_LIMIT:]

    def _device_session_autonomy(self, session: Session) -> Autonomy:
        if session.id == self._host_session_id and self._host is not None:
            return self._autonomy
        context = self._session_hosts.get(session.id)
        return context.autonomy if context is not None else session.autonomy

    @staticmethod
    def _check_device_autonomy(
        device: PairedDevice, autonomy: Autonomy, options: TaskOptions
    ) -> list[str]:
        """Whether a phone's task may run with the conversation's autonomy, and what the window
        marks the turn with.

        A task from another device is an outside instruction. Where this desktop approves
        everything on its own (YOLO, full access) it runs only when the phone's user confirmed
        that very setting and the phone was given ``broad_autonomy``; otherwise its approvals
        are given here or on the phone.
        """
        labels: list[str] = []
        if autonomy in {Autonomy.YOLO, Autonomy.FULL_ACCESS}:
            if options.accept_autonomy is None:
                raise DeviceLinkError("desktop_autonomy_too_broad", 409, autonomy=autonomy.value)
            if "broad_autonomy" not in device.scopes:
                raise DeviceLinkError("scope_denied", 403)
            if options.accept_autonomy != autonomy.value:
                raise DeviceLinkError("autonomy_changed", 409, autonomy=autonomy.value)
            labels.append("broad_autonomy")
        if options.private_accepted:
            labels.append("private")
        if options.from_agent:
            labels.append("subtask")
        return labels

    def device_submit(
        self,
        device: PairedDevice,
        request_id: str,
        session_id: str,
        prompt: str,
        options: TaskOptions | None = None,
        *,
        handoff: bool = False,
        files: Sequence[str] = (),
    ) -> dict[str, object]:
        """Run a phone's task in one of this desktop's conversations, once per request id.

        ``files`` are the open folder's paths of what the phone sent with it; the pictures
        among them go to the model with the request when it is known to look at pictures."""
        prompt = prompt.strip()
        if not prompt or len(prompt) > _MAX_PROMPT_CHARS:
            raise DeviceLinkError("invalid_prompt")
        try:
            session = self._workspace_session(session_id)
        except GatewayError as error:
            if str(error) == "unknown_session":
                raise DeviceLinkError("unknown_session", 404) from None
            raise DeviceLinkError(str(error), 503) from None
        tasks = self._device_link.tasks
        if tasks.find(device.device_id, request_id) is not None:
            # Sent again: the first answer stands, even if the conversation changed since.
            task, _created = tasks.create(device.device_id, request_id, session.id, prompt)
            return self._device_task_document(task)
        with self._lock:
            if self._provider is None or self._closing:
                raise DeviceLinkError("desktop_not_ready", 503)
            autonomy = self._device_session_autonomy(session)
            provider = self._provider
        labels = self._check_device_autonomy(device, autonomy, options or TaskOptions())
        if handoff:
            labels.append("handoff")
        task, created = tasks.create(
            device.device_id,
            request_id,
            session.id,
            prompt,
            autonomy=autonomy.value,
            model_location=model_location(provider.base_url),
            labels=labels,
        )
        if created:
            origin: dict[str, object] = {"device": device.name, "labels": labels}
            pictures = self._device_pictures(provider, files)
            # The message the turn writes: the request, then the attached pictures' paths.
            message = task.prompt + (
                "\n\n" + "\n".join(f"[File reference: {path}]" for path in pictures)
                if pictures
                else ""
            )
            pending = (message, origin, task.task_id, device.device_id)
            with self._lock:
                origins = self._device_turn_origins.setdefault(session.id, [])
                origins.append(pending)
                del origins[:-_DEVICE_PENDING_ORIGINS]
            try:
                self._dispatch_prompt(f"device-{task.task_id}", session, task.prompt, pictures)
            except GatewayError as error:
                # Nothing ran: the phone may send the same request again.
                tasks.discard(task.task_id)
                with self._lock, suppress(ValueError):
                    self._device_turn_origins.get(session.id, []).remove(pending)
                raise DeviceLinkError(str(error), 503) from None
            tasks.update(task.task_id, state="queued")
            self._device_hub.log(device, "task_sent", prompt)
        refreshed = tasks.get(task.task_id)
        assert refreshed is not None
        return self._device_task_document(refreshed)

    def device_inbox(self, device: PairedDevice) -> dict[str, object]:
        """Finished runs of the schedules shared with phones, and the approvals waiting here."""
        self._refresh_open_schedule_runs()
        shared = {item.id for item in self._schedules.all() if item.notify_phone}
        runs = [
            {
                "run_id": run.run_id,
                "schedule_id": run.schedule_id,
                "title": run.title,
                "state": run.state,
                "due_at": run.due_at,
                "updated_at": run.updated_at,
                **({"session_id": run.session_id} if run.session_id else {}),
                **({"result": run.result} if run.result else {}),
                **({"error": run.error} if run.error else {}),
            }
            for run in self._schedules.runs(limit=200)
            if run.schedule_id in shared and run.state not in OPEN_RUN_STATES
        ][:_DEVICE_INBOX_LIMIT]
        approvals: list[dict[str, object]] = []
        if "approvals" in device.scopes:
            with self._lock:
                for request_id, entry in self._approval_ledger.items():
                    if entry.state != "pending" or entry.run_id is not None or not entry.session_id:
                        continue
                    tool = entry.payload.get("toolName") or entry.payload.get("tool")
                    approvals.append(
                        {
                            "request_id": request_id,
                            "session_id": entry.session_id,
                            "tool": tool if isinstance(tool, str) else "",
                            "summary": _approval_display_text(entry.payload.get("summary")) or "",
                        }
                    )
        store = self._device_link.store
        current = self._device_link.registry.get(device.device_id) or device
        try:
            turns = store.turns(device.device_id) if current.notify_turns else []
            transfers = [item.inbox_item() for item in store.transfers(device.device_id)]
            jobs = [job.document() for job in store.open_jobs(device.device_id)]
        except (OSError, sqlite3.Error):
            raise DeviceLinkError("storage_unavailable", 503) from None
        return {
            "runs": runs,
            "approvals": approvals[-_DEVICE_INBOX_LIMIT:],
            "turns": turns,
            "transfers": transfers[:_DEVICE_INBOX_LIMIT],
            "phone_jobs": jobs,
        }

    def _device_call[T](self, function: Callable[..., T], *arguments: object) -> T:
        """A device link 2 request, with the hub's and the store's refusals as the endpoint's."""
        try:
            return function(*arguments)
        except DeviceStoreError as error:
            raise DeviceLinkError(error.code, error.status) from None
        except GatewayError as error:
            code = str(error)
            raise DeviceLinkError(code, 404 if code == "unknown_session" else 503) from None
        except (OSError, sqlite3.Error):
            raise DeviceLinkError("storage_unavailable", 503) from None

    def device_runtime(self) -> dict[str, object]:
        return self._device_hub.runtime()

    def device_stop(self, device: PairedDevice, session_id: str) -> dict[str, object]:
        """Stop the turn running in a conversation, as the window's stop button does."""
        try:
            session = self._workspace_session(session_id)
        except GatewayError as error:
            code = str(error)
            raise DeviceLinkError(code, 404 if code == "unknown_session" else 503) from None
        with self._lock:
            context = self._session_hosts.get(session.id)
            if session.id == self._host_session_id and self._host is not None:
                running = (
                    self._active_turn is not None
                    or self._turn_requested
                    or bool(self._queued_turns)
                )
            elif context is not None and context.host is not None:
                running = (
                    context.active_turn is not None
                    or context.turn_requested
                    or bool(context.queued_turns)
                )
            else:
                running = False
            if not running:
                raise DeviceLinkError("not_running", 409)
            command = CommandEnvelope(
                PROTOCOL_VERSION, f"device-stop-{uuid4()}", "turn.cancel", {}, session.id
            )
            try:
                self._execute_unsent(command)
            except GatewayError as error:
                raise DeviceLinkError(str(error), 503) from None
        self._device_hub.log(device, "turn_stopped", self._session_title(session))
        return {"stopped": True}

    def device_inbox_read(self, device: PairedDevice, run_ids: list[str]) -> None:
        self._device_call(self._schedules.mark_read, run_ids)

    def device_job_report(
        self, device: PairedDevice, job_id: str, payload: dict[str, Any]
    ) -> dict[str, object]:
        return self._device_call(self._device_hub.job_report, device, job_id, payload)

    def device_receive_file(
        self, device: PairedDevice, transfer_id: str, upload: Upload
    ) -> dict[str, object]:
        return self._device_call(self._device_hub.receive_file, device, transfer_id, upload)

    def device_files(self, device: PairedDevice, path: str) -> dict[str, object]:
        return self._device_call(self._device_hub.files, path)

    def device_file(self, device: PairedDevice, path: str) -> tuple[Path, str]:
        return self._device_call(self._device_hub.file, device, path)

    def device_transfer(self, device: PairedDevice, transfer_id: str) -> tuple[Path | None, Any]:
        return self._device_call(self._device_hub.transfer, device, transfer_id)

    def device_transfer_done(self, device: PairedDevice, transfer_id: str) -> None:
        self._device_call(self._device_hub.transfer_done, device, transfer_id)

    def device_message(self, device: PairedDevice, payload: dict[str, Any]) -> None:
        self._device_call(self._device_hub.message, device, payload)

    def device_conversation(
        self, device: PairedDevice, payload: dict[str, Any]
    ) -> dict[str, object]:
        return self._device_call(self._device_hub.conversation, device, payload)

    def device_knowledge(self, device: PairedDevice) -> dict[str, object]:
        return self._device_call(self._device_hub.knowledge)

    def device_knowledge_document(
        self, device: PairedDevice, document_id: str
    ) -> dict[str, object]:
        return self._device_call(self._device_hub.knowledge_document, document_id)

    def device_knowledge_add(
        self, device: PairedDevice, payload: dict[str, Any]
    ) -> tuple[int, dict[str, object]]:
        return self._device_call(self._device_hub.knowledge_add, device, payload)

    def device_info(self, device: PairedDevice) -> dict[str, object]:
        return self._device_call(self._device_hub.info, device)

    def device_settings(self, device: PairedDevice, payload: dict[str, Any]) -> dict[str, object]:
        return self._device_call(self._device_hub.settings, device, payload)

    def device_unpair(self, device: PairedDevice) -> None:
        self._device_call(self._device_hub.unpair, device)

    def _session_title(self, session: Session) -> str:
        """A conversation's title as the window shows it (the user's own name for it first)."""
        with self._lock:
            alias = self._workspace_presentations().get(session.id, {}).get("alias")
        return alias if isinstance(alias, str) and alias else session.title

    def device_resolve_approval(
        self, device: PairedDevice, request_id: str, approve: bool
    ) -> dict[str, object]:
        """Answer an approval this desktop is waiting for, once, as the window would."""
        if "approvals" not in device.scopes:
            raise DeviceLinkError("scope_denied", 403)
        with self._lock:
            entry = self._approval_ledger.get(request_id)
            session_id = entry.session_id if entry is not None else None
            unknown = entry is None or entry.run_id is not None or session_id is None
            tool = (entry.payload.get("toolName") or entry.payload.get("tool")) if entry else None
        if unknown:
            raise DeviceLinkError("unknown_approval", 404)
        command = CommandEnvelope(
            PROTOCOL_VERSION,
            f"device-approval-{request_id}",
            "approval.resolve",
            {"requestId": request_id, "scope": ApprovalScope.ONCE.value if approve else None},
            session_id,
        )
        self._unsent_replies.active = True
        try:
            self.execute(command)
        except GatewayError as error:
            code = str(error)
            if code in {"approval_already_resolved", "approval_resolution_pending"}:
                raise DeviceLinkError(code, 409) from None
            if code == "unknown_approval":
                raise DeviceLinkError(code, 404) from None
            raise DeviceLinkError(code, 503) from None
        finally:
            self._unsent_replies.active = False
        self._device_hub.log(
            device,
            "approval_decided",
            f"{'approved' if approve else 'rejected'}: {tool if isinstance(tool, str) else ''}",
        )
        return {"request_id": request_id, "approved": approve}

    def device_task(self, device: PairedDevice, task_id: str) -> dict[str, object] | None:
        task = self._device_link.tasks.get(task_id)
        if task is None or task.device_id != device.device_id:
            return None
        return self._device_task_document(task)

    def _device_pictures(self, provider: ProviderConfig, files: Sequence[str]) -> list[str]:
        """The pictures among files a phone sent (open-folder paths), to attach to its request
        as the window attaches them. Only for a model known to look at pictures (what the window
        shows as vision ready): another could refuse the request; it still sees every path."""
        if not files or provider_capabilities(provider).vision is not True:
            return []
        pictures: list[str] = []
        for path in files:
            if len(pictures) == MAX_IMAGES_PER_MESSAGE:
                break
            try:
                [reference] = self._attachment_references([path])
                if self._attachment_images([reference]):
                    pictures.append(reference)
            except GatewayError:
                continue  # not a picture this model takes, or too large: its path is enough
        return pictures

    def _dispatch_prompt(
        self, request_id: str, session: Session, prompt: str, pictures: Sequence[str] = ()
    ) -> None:
        """Send a prompt to a conversation, starting a background runtime when it is closed."""
        payload: dict[str, object] = {"prompt": prompt}
        if pictures:
            payload["attachmentPaths"] = list(pictures)
        command = CommandEnvelope(
            PROTOCOL_VERSION,
            request_id,
            "turn.start",
            payload,
            session.id,
        )
        with self._lock:
            hosted = session.id in self._session_hosts and session.id != self._host_session_id
        if not hosted:
            self._await_lifecycle_settle()
        with self._lock:
            if self._closing:
                raise GatewayError("runtime_unavailable")
            if session.id == self._host_session_id and self._host is not None:
                self._execute_unsent(command)
                return
            if session.id in self._session_hosts:
                self._execute_unsent(command)
                return
        self._start_device_session_host(session, command)

    @staticmethod
    def _shutdown_quietly(host: Host) -> None:
        with suppress(Exception):
            if isinstance(host, RuntimeHost):
                host.request_shutdown(create_backup=False)
            else:
                host.request_shutdown()

    def _start_device_session_host(self, session: Session, command: CommandEnvelope) -> None:
        """A background runtime for a conversation not open in the window, then the task."""
        with self._lock:
            if self._closing or self._provider is None:
                raise GatewayError("runtime_unavailable")
            if session.id in self._device_host_starting:
                raise GatewayError("runtime_busy")
            provider = self._provider
            self._device_host_starting.add(session.id)
        host: Host | None = None
        try:
            workspace = Path(session.workspace).resolve()
            host = self._host_factory(
                RuntimeSettings(
                    workspace=workspace,
                    database=self._database,
                    provider=provider,
                    mode=session.mode,
                    autonomy=session.autonomy,
                    session_id=session.id,
                    writer_lock_group=self._writer_lock_group,
                    # The same tools as in the window: the conversation may be opened there next.
                    subagents=self._subagents,
                    phone_jobs=self._phone_jobs,
                    extra_tools=(self._skill_tool,),
                    system_note=self._system_note,
                    turn_files=start_turn_watch,
                    workspace_tools=self._research_tools,
                )
            )
            host.start()
            startup: list[Event] = []
            started = False
            deadline = self._clock() + _START_TIMEOUT_SECONDS
            while self._clock() < deadline:
                events = host.drain_display_events()
                startup.extend(events)
                kinds = {event.type for event in events}
                if kinds & {"runtime.failed", "approval.requested"}:
                    break  # an extension approval at startup is answered in the window
                if "runtime.started" in kinds:
                    started = True
                    break
                if not host.is_alive() and getattr(host, "ident", True) is not None:
                    break
                self._sleeper(0.01)
            if not started:
                raise GatewayError("runtime_start_failed")
            with self._lock:
                if self._closing:
                    raise GatewayError("runtime_unavailable")
                if session.id in self._session_hosts or session.id == self._host_session_id:
                    # Opened in the window meanwhile: that runtime takes the task.
                    self._execute_unsent(command)
                    return
                self._session_hosts[session.id] = _SessionHostContext(
                    host,
                    workspace,
                    provider,
                    session.id,
                    session.id,
                    session.mode,
                    session.autonomy,
                    "ready",
                    None,
                    False,
                    [],
                    {},
                    None,
                    {},
                )
                self._device_hosted_sessions[session.id] = self._clock()
                owned, host = host, None
                self._queue_host_events(startup, source_host=owned)
                self._execute_unsent(command)
        finally:
            if host is not None:
                self._shutdown_quietly(host)
            with self._lock:
                self._device_host_starting.discard(session.id)

    def _retire_idle_device_hosts(self) -> None:
        """Stop runtimes started for phones' tasks once their work is done (gateway lock held)."""
        for session_id, started_at in list(self._device_hosted_sessions.items()):
            context = self._session_hosts.get(session_id)
            if context is None or context.host is None:
                self._device_hosted_sessions.pop(session_id, None)
                continue
            if self._clock() - started_at < _DEVICE_HOST_GRACE_SECONDS:
                continue
            busy = (
                context.active_turn is not None
                or context.turn_requested
                or bool(context.queued_turns)
                or getattr(context.host, "has_background_work", False)
                or any(
                    entry.session_id == session_id and entry.state != "resolved"
                    for entry in self._approval_ledger.values()
                )
            )
            if busy:
                continue
            self._session_hosts.pop(session_id, None)
            self._device_hosted_sessions.pop(session_id, None)
            self._shutdown_quietly(context.host)

    def _refresh_device_task(self, task: DeviceTask) -> DeviceTask:
        """Follow a handed-over task through its conversation's turn events."""
        if task.state in {"succeeded", "failed", "cancelled", "interrupted", "dispatching"}:
            return task
        tasks = self._device_link.tasks
        try:
            events = SQLiteEventStore.list_session_events_of_types_read_only(
                self._database,
                task.session_id,
                frozenset({"message.created", *_DEVICE_TURN_ENDS}),
            )
        except (OSError, ValueError, sqlite3.DatabaseError):
            return task
        correlation = task.correlation_id
        if correlation is None:
            claimed = tasks.claimed_messages(task.session_id)
            for event in events:
                if (
                    event.type == "message.created"
                    and event.data.get("role") == "user"
                    and event.data.get("content") == task.prompt
                    and event.created_at >= task.created_at
                    and event.id not in claimed
                    and event.correlation_id
                ):
                    correlation = event.correlation_id
                    tasks.update(
                        task.task_id,
                        state="running",
                        message_event_id=event.id,
                        correlation_id=correlation,
                    )
                    break
            if correlation is None:
                return task
        for event in events:
            if event.correlation_id == correlation and event.type in _DEVICE_TURN_ENDS:
                error = None
                if event.type == "turn.failed":
                    message = event.data.get("message")
                    error = Redactor().redact(message[:600]) if isinstance(message, str) else None
                state = _DEVICE_TURN_ENDS[event.type]
                tasks.update(task.task_id, state=state, error=error)
                self._device_hub.log(task.device_id, "task_finished", f"{state}: {task.prompt}")
                break
        refreshed = tasks.get(task.task_id)
        return refreshed if refreshed is not None else task

    def _device_task_document(self, task: DeviceTask) -> dict[str, object]:
        task = self._refresh_device_task(task)
        document: dict[str, object] = {
            "task_id": task.task_id,
            "state": task.state,
            "session_id": task.session_id,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }
        if task.autonomy:
            document["autonomy"] = task.autonomy
        if task.model_location:
            document["model_location"] = task.model_location
        if task.error:
            document["error"] = task.error
        if task.state == "running" and task.correlation_id:
            activity = self._device_task_activity(task.session_id, task.correlation_id)
            if activity:
                document["activity"] = activity
        if task.state == "succeeded" and task.correlation_id:
            with suppress(OSError, ValueError, sqlite3.DatabaseError):
                answers = [
                    event.data.get("content")
                    for event in SQLiteEventStore.list_session_events_of_types_read_only(
                        self._database, task.session_id, frozenset({"message.created"})
                    )
                    if event.correlation_id == task.correlation_id
                    and event.data.get("role") == "assistant"
                    and isinstance(event.data.get("content"), str)
                    and str(event.data.get("content")).strip()
                ]
                if answers:
                    document["result"] = str(answers[-1])[:_DEVICE_RESULT_CHARS]
        return document

    def _device_task_activity(self, session_id: str, correlation_id: str) -> str | None:
        """The step a running task is on: the tool it is using and what on, or None."""
        try:
            events = SQLiteEventStore.list_session_events_of_types_read_only(
                self._database,
                session_id,
                frozenset(
                    {
                        "tool.proposed",
                        "tool.settled",
                        "tool.failed",
                        "tool.rejected",
                        "tool.cancelled",
                    }
                ),
            )
        except (OSError, ValueError, sqlite3.DatabaseError):
            return None
        finished = {
            event.data.get("tool_call_id")
            for event in events
            if event.correlation_id == correlation_id and event.type != "tool.proposed"
        }
        for event in reversed(events):
            if event.correlation_id != correlation_id or event.type != "tool.proposed":
                continue
            if event.data.get("tool_call_id") in finished:
                return None  # between steps
            name = event.data.get("name")
            if not isinstance(name, str):
                return None
            arguments = event.data.get("arguments")
            detail = next(
                (
                    arguments[key]
                    for key in _DEVICE_ACTIVITY_ARGUMENTS
                    if isinstance(arguments, Mapping)
                    and isinstance(arguments.get(key), str)
                    and arguments[key].strip()
                ),
                "",
            )
            text = " ".join(Redactor().redact(f"{name} {detail}").split())
            return text[:_DEVICE_ACTIVITY_CHARS]
        return None

    def _settle_device_tasks_after_restart(self) -> None:
        """Tasks a phone handed over before the desktop restarted: those that had not finished
        are reported interrupted, and a queued copy of one never runs later by surprise."""
        if not (self._database.with_name("device-link") / "tasks.db").is_file():
            return
        with suppress(OSError, sqlite3.DatabaseError):
            tasks = self._device_link.tasks
            for task in tasks.open_tasks():
                if self._refresh_device_task(task).state in {
                    "succeeded",
                    "failed",
                    "cancelled",
                    "interrupted",
                }:
                    continue
                tasks.update(
                    task.task_id,
                    state="interrupted",
                    error="the desktop restarted before the task finished",
                )
                if not self._database.is_file():
                    continue
                with SQLiteEventStore(self._database) as store:
                    for queued in store.list_queued_turns(task.session_id):
                        if queued.prompt == task.prompt:
                            store.mark_turn_state(queued.turn_id, "cancelled")
                            break

    def _note_device_turn(self, event: Event) -> Event:
        """Mark a phone's task where its message shows, and keep finished turns for the phones'
        inboxes (gateway lock held)."""
        correlation = event.correlation_id
        if event.type == "message.created":
            role, content = event.data.get("role"), event.data.get("content")
            if role == "assistant" and correlation and isinstance(content, str) and content.strip():
                self._turn_answers[correlation] = content[:300]
                while len(self._turn_answers) > _TURN_ANSWERS_KEPT:
                    self._turn_answers.pop(next(iter(self._turn_answers)))
            elif role == "user" and isinstance(content, str) and "origin" not in event.data:
                pending = self._device_turn_origins.get(event.session_id) or []
                match = next((item for item in pending if item[0] == content), None)
                if match is not None:
                    pending.remove(match)
                    _prompt, origin, task_id, device_id = match
                    if correlation:
                        self._device_turn_owners[correlation] = device_id
                        with suppress(OSError, sqlite3.Error):
                            self._device_link.tasks.update(
                                task_id,
                                state="running",
                                message_event_id=event.id,
                                correlation_id=correlation,
                            )
                    return replace(event, data={**event.data, "origin": origin})
        elif event.type in _DEVICE_TURN_ENDS and correlation:
            summary = self._turn_answers.pop(correlation, "")
            owner = self._device_turn_owners.pop(correlation, None)
            if event.type == "turn.failed":
                message = event.data.get("message")
                summary = Redactor().redact(message[:300]) if isinstance(message, str) else ""
            self._record_finished_turn(
                event.session_id, correlation, _DEVICE_TURN_ENDS[event.type], summary, owner
            )
        return event

    def _device_task_origins(self, session_id: str) -> dict[str, dict[str, object]]:
        """How the window marks each turn a phone handed over in a conversation, by turn."""
        if not (self._database.with_name("device-link") / "tasks.db").is_file():
            return {}
        try:
            tasks = self._device_link.tasks.for_session(session_id)
            names = {device.device_id: device.name for device in self._device_link.registry.list()}
        except (OSError, sqlite3.Error):
            return {}
        return {
            task.correlation_id: {
                "device": names.get(task.device_id, ""),
                "labels": list(task.labels),
            }
            for task in tasks
            if task.correlation_id
        }
