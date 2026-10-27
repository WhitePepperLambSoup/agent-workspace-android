"""Device link 2 for the desktop gateway: files, transfers, hand-offs, jobs and knowledge.

The endpoint (device_link) checks tokens and scopes and parses requests; this module does the
work against the gateway: it saves what a phone sends into the open folder, lists and serves
that folder's files, keeps transfers and phone jobs, writes a phone's conversation into a new
desktop conversation, and exchanges knowledge-base passages. Every action a phone takes is
written to that phone's activity record.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
import shutil
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit
from uuid import uuid4

from agent_workspace.core.events import Event
from agent_workspace.core.models import Mode
from agent_workspace.core.session import Session
from agent_workspace.knowledge import (
    DEFAULT_COLLECTION,
    KnowledgeError,
    KnowledgeStore,
    knowledge_root,
    knowledge_store,
)
from agent_workspace.storage.sqlite import SQLiteEventStore
from agent_workspace.tools.paths import (
    WorkspacePathError,
    WorkspacePaths,
    is_sensitive_workspace_path,
)
from agent_workspace.ui_gateway.device_link import (
    MAX_FILE_BYTES,
    DeviceLinkError,
    PairedDevice,
    TaskOptions,
    Upload,
)
from agent_workspace.ui_gateway.device_store import (
    FINISHED_JOB_STATES,
    DeviceStore,
    DeviceStoreError,
    PhoneJob,
)

if TYPE_CHECKING:
    from agent_workspace.ui_gateway.runtime import GatewayRuntime

FROM_PHONE_FOLDER = "来自手机"
_MAX_LISTED = 500
_MAX_TEXT = 64 * 1024
_MAX_RESULT = 64 * 1024
_MAX_ERROR = 2000
_MAX_MESSAGES = 200
_MAX_CONVERSATION_BYTES = 1024 * 1024
_MAX_KNOWLEDGE_DOCUMENTS = 2000
_NAME_CHARS = 200
_ID_CHARS = 128


def _clean_filename(raw: str) -> str:
    """A file name without folders or control characters, at most 200 characters."""
    name = raw.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(char for char in name if ord(char) >= 32 and char not in '<>:"|?*').strip(" .")
    if not name:
        name = "file"
    if len(name) > _NAME_CHARS:
        stem, dot, suffix = name.rpartition(".")
        if dot and 0 < len(suffix) < 20:
            name = f"{stem[: _NAME_CHARS - len(suffix) - 1]}.{suffix}"
        else:
            name = name[:_NAME_CHARS]
    return name


def _free_name(folder: Path, name: str) -> Path:
    """``name`` in ``folder``, or "name (2).ext" and so on when it is taken."""
    candidate = folder / name
    if not candidate.exists():
        return candidate
    stem, dot, suffix = name.rpartition(".")
    if not dot or not stem:
        stem, suffix = name, ""
    for number in range(2, 10_000):
        candidate = folder / (f"{stem} ({number}).{suffix}" if suffix else f"{stem} ({number})")
        if not candidate.exists():
            return candidate
    raise DeviceLinkError("storage_unavailable", 503)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _request_id(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > _ID_CHARS:
        raise DeviceLinkError("invalid_request_id")
    return value


def model_location(base_url: str) -> str:
    """Where a provider's model runs: this computer or the local network ("computer"), or a
    service on the internet ("cloud")."""
    host = urlsplit(base_url).hostname or ""
    if host in {"", "localhost"} or host.endswith(".local"):
        return "computer"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "cloud"
    return "computer" if address.is_loopback or address.is_private else "cloud"


def _message_data(role: str, content: str, origin: dict[str, object] | None) -> dict[str, object]:
    data: dict[str, object] = {
        "role": role,
        "content": content,
        "reasoning": "",
        "tool_calls": [],
        "tool_call_id": None,
        # The phone's own messages are the user's; its replies were made by a model.
        "trust": "trusted" if role == "user" else "derived",
        "sensitivity": "normal",
        "provider_metadata": {},
    }
    if origin is not None:
        data["origin"] = origin
    return data


class DeviceHub:
    def __init__(self, gateway: GatewayRuntime) -> None:
        self._gateway = gateway

    @property
    def store(self) -> DeviceStore:
        return self._gateway._device_link.store

    def _knowledge(self) -> KnowledgeStore:
        return knowledge_store(knowledge_root(self._gateway._database))

    def log(self, device: PairedDevice | str, action: str, detail: str) -> None:
        device_id = device if isinstance(device, str) else device.device_id
        with suppress(OSError, sqlite3.Error, ValueError):
            self.store.log(device_id, action, detail)

    def _workspace(self) -> Path:
        with self._gateway._lock:
            workspace = self._gateway._workspace
        if workspace is None:
            raise DeviceLinkError("no_workspace", 503)
        return workspace

    def notice(self, session_id: str, event_type: str, data: dict[str, object]) -> None:
        """A display event for the window (not kept in any conversation)."""
        with self._gateway._lock:
            self._gateway._pending_host_events.append(
                Event(session_id=session_id, type=event_type, data=data)
            )

    # ---- runtime ------------------------------------------------------------------------------

    def runtime(self) -> dict[str, object]:
        gateway = self._gateway
        with gateway._lock:
            provider = gateway._provider
            workspace = gateway._workspace
            autonomy = gateway._autonomy
        return {
            "model": (
                {"name": provider.model, "location": model_location(provider.base_url)}
                if provider is not None
                else None
            ),
            "workspace": {"name": workspace.name} if workspace is not None else None,
            "defaults": {"autonomy": autonomy.value},
        }

    # ---- files a phone sends ---------------------------------------------------------------------

    def receive_file(
        self, device: PairedDevice, transfer_id: str, upload: Upload
    ) -> dict[str, object]:
        earlier = self.store.received(device.device_id, transfer_id)
        if earlier is not None:
            return earlier
        workspace = self._workspace()
        folder = workspace / FROM_PHONE_FOLDER
        folder.mkdir(parents=True, exist_ok=True)
        target = _free_name(folder, _clean_filename(upload.name))
        shutil.copyfile(upload.path, target)
        relative = target.relative_to(workspace).as_posix()
        document: dict[str, object] = {
            "transfer_id": transfer_id,
            "path": relative,
            "size": upload.size,
        }
        if upload.knowledge is not None:
            store = self._knowledge()
            # The file is saved either way; a file the knowledge base cannot read stays out of it.
            with suppress(KnowledgeError, OSError, sqlite3.Error):
                added = store.add_file(
                    target,
                    target.name,
                    origin="phone",
                    origin_path=relative,
                    collection_id=store.collection_named(upload.knowledge),
                )
                document["knowledge_document_id"] = added["id"]
        self.store.remember_received(device.device_id, transfer_id, document)
        self.log(device, "file_received", target.name)
        self.notice(
            "desktop",
            "device.received",
            {"kind": "file", "device": device.name, "name": target.name, "path": relative},
        )
        return document

    # ---- the open folder, for a phone to browse --------------------------------------------------

    def _resolve(self, raw: str) -> tuple[WorkspacePaths, Path]:
        workspace = self._workspace()
        paths = WorkspacePaths(workspace)
        wanted = raw.replace("\\", "/").strip().strip("/")
        if wanted and is_sensitive_workspace_path(wanted):
            raise DeviceLinkError("unknown_path", 404)
        try:
            target = paths.resolve(wanted or ".")
            relative = paths.relative(target)
        except WorkspacePathError:
            raise DeviceLinkError("invalid_path", 400) from None
        if relative != "." and is_sensitive_workspace_path(relative):
            raise DeviceLinkError("unknown_path", 404)
        return paths, target

    def files(self, path: str) -> dict[str, object]:
        paths, folder = self._resolve(path)
        if not folder.is_dir():
            raise DeviceLinkError("unknown_path", 404)
        listed = paths.relative(folder)
        prefix = "" if listed == "." else f"{listed}/"
        entries: list[dict[str, object]] = []
        truncated = False
        children = sorted(folder.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        for child in children:
            if child.is_symlink() or is_sensitive_workspace_path(prefix + child.name):
                continue  # links, .git, .env, keys and credentials stay on this computer
            if len(entries) >= _MAX_LISTED:
                truncated = True
                break
            with suppress(OSError):
                metadata = child.stat()
                directory = child.is_dir()
                entries.append(
                    {
                        "name": child.name,
                        "kind": "dir" if directory else "file",
                        "size": 0 if directory else metadata.st_size,
                        "modified_at": datetime.fromtimestamp(metadata.st_mtime, UTC).isoformat(
                            timespec="seconds"
                        ),
                    }
                )
        return {"path": prefix.rstrip("/"), "entries": entries, "truncated": truncated}

    def file(self, device: PairedDevice, path: str) -> tuple[Path, str]:
        _, target = self._resolve(path)
        if not target.is_file():
            raise DeviceLinkError("unknown_path", 404)
        if target.stat().st_size > MAX_FILE_BYTES:
            raise DeviceLinkError("payload_too_large", 413)
        self.log(device, "file_sent", target.name)
        return target, _sha256(target)

    # ---- what the desktop sends a phone ----------------------------------------------------------

    def send_file(self, device_id: str, path: Path, source: str | None) -> dict[str, object]:
        if not path.is_file():
            raise DeviceLinkError("unknown_path", 404)
        if path.stat().st_size > MAX_FILE_BYTES:
            raise DeviceLinkError("payload_too_large", 413)
        transfer = self.store.add_transfer(
            device_id, "file", file=path, name=path.name, sha256=_sha256(path), source=source
        )
        self.log(device_id, "file_sent", path.name)
        return transfer.inbox_item()

    def send_text(self, device_id: str, text: str) -> dict[str, object]:
        text = text.strip()
        if not text or len(text.encode("utf-8")) > _MAX_TEXT:
            raise DeviceLinkError("invalid_text")
        kind = "link" if re.fullmatch(r"https?://\S+", text) else "text"
        transfer = self.store.add_transfer(device_id, kind, text=text)
        self.log(device_id, "text_sent", text)
        return transfer.inbox_item()

    def send_conversation(self, device_id: str, session_id: str) -> dict[str, object]:
        gateway = self._gateway
        session = gateway._workspace_session(session_id)
        events = SQLiteEventStore.list_session_events_of_types_read_only(
            gateway._database, session.id, frozenset({"message.created"})
        )
        messages: list[dict[str, str]] = []
        for event in events:
            role, content = event.data.get("role"), event.data.get("content")
            if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
                messages.append({"role": str(role), "content": content})
        # The newest messages, within the limits a phone takes from a hand-off.
        messages = messages[-_MAX_MESSAGES:]
        size = sum(len(item["content"].encode("utf-8")) for item in messages)
        while messages and size > _MAX_CONVERSATION_BYTES:
            size -= len(messages.pop(0)["content"].encode("utf-8"))
        title = gateway._session_title(session)
        transfer = self.store.add_transfer(
            device_id,
            "conversation",
            title=title,
            conversation={"title": title, "messages": messages},
        )
        self.log(device_id, "conversation_sent", title)
        return transfer.inbox_item()

    def transfer(self, device: PairedDevice, transfer_id: str) -> tuple[Path | None, Any]:
        try:
            transfer, content = self.store.transfer_content(device.device_id, transfer_id)
        except DeviceStoreError as error:
            raise DeviceLinkError(error.code, error.status) from None
        if transfer.kind == "file":
            return content, transfer.sha256 or _sha256(content)
        return None, content

    def transfer_done(self, device: PairedDevice, transfer_id: str) -> None:
        if not self.store.finish_transfer(device.device_id, transfer_id):
            raise DeviceLinkError("unknown_transfer", 404)

    # ---- text and links a phone sends -----------------------------------------------------------

    def message(self, device: PairedDevice, payload: dict[str, Any]) -> None:
        request_id = _request_id(payload.get("request_id"))
        kind, text = payload.get("kind"), payload.get("text")
        if kind not in {"text", "link"}:
            raise DeviceLinkError("invalid_kind")
        if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > _MAX_TEXT:
            raise DeviceLinkError("invalid_text")
        if not self.store.add_message(device.device_id, request_id, kind, text):
            return  # the same message sent again
        self.log(device, "text_received", text)
        self.notice(
            "desktop",
            "device.received",
            {
                "kind": kind,
                "device": device.name,
                "text": text,
                "copy": self._gateway._device_link.settings()["clipboard"],
            },
        )

    # ---- jobs this desktop hands a phone -------------------------------------------------------

    def job_report(
        self, device: PairedDevice, job_id: str, payload: dict[str, Any]
    ) -> dict[str, object]:
        state = payload.get("state")
        if state not in {"accepted", "rejected", "running", "succeeded", "failed"}:
            raise DeviceLinkError("invalid_state")
        result, error = payload.get("result"), payload.get("error")
        if result is not None and (not isinstance(result, str) or len(result) > _MAX_RESULT):
            raise DeviceLinkError("invalid_result")
        if error is not None and (not isinstance(error, str) or len(error) > _MAX_ERROR):
            raise DeviceLinkError("invalid_error")
        try:
            before = self.store.job(job_id)
            job = self.store.report_job(device.device_id, job_id, state, result=result, error=error)
        except DeviceStoreError as failure:
            raise DeviceLinkError(failure.code, failure.status) from None
        if before is None or before.state != job.state:
            self.job_updated(job, device.name)
            if job.state in FINISHED_JOB_STATES:
                self.log(device, "job_finished", f"{job.state}: {job.prompt}")
        return job.document()

    def job_updated(self, job: PhoneJob, device_name: str) -> None:
        """Show the job's state in the conversation that asked for it."""
        self.notice(
            job.session_id,
            "device.job.updated",
            {
                "job_id": job.job_id,
                "state": job.state,
                "device": device_name,
                "prompt": job.prompt[:200],
                "operate_phone": job.operate_phone,
            },
        )

    # ---- conversations a phone hands over ------------------------------------------------------

    def conversation(self, device: PairedDevice, payload: dict[str, Any]) -> dict[str, object]:
        gateway = self._gateway
        request_id = _request_id(payload.get("request_id"))
        earlier = self.store.handoff(device.device_id, request_id)
        if earlier is not None:
            return earlier
        title, messages = payload.get("title"), payload.get("messages")
        files, prompt = payload.get("files") or [], payload.get("prompt")
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise DeviceLinkError("invalid_title")
        if not isinstance(messages, list) or len(messages) > _MAX_MESSAGES:
            raise DeviceLinkError("invalid_messages")
        history: list[tuple[str, str]] = []
        for item in messages:
            if (
                not isinstance(item, dict)
                or item.get("role") not in {"user", "assistant"}
                or not isinstance(item.get("content"), str)
            ):
                raise DeviceLinkError("invalid_messages")
            if item["content"].strip():
                history.append((item["role"], item["content"]))
        if not isinstance(files, list) or not all(
            isinstance(item, str) and 0 < len(item) <= _ID_CHARS for item in files
        ):
            raise DeviceLinkError("invalid_files")
        if files and "files" not in device.scopes:
            raise DeviceLinkError("scope_denied", 403)
        if prompt is not None and (not isinstance(prompt, str) or not prompt.strip()):
            raise DeviceLinkError("invalid_prompt")
        options = TaskOptions.from_payload(payload) if prompt else None
        workspace = self._workspace()
        with gateway._lock:
            autonomy = gateway._autonomy
            ready = gateway._provider is not None
        if prompt and options is not None:
            if not ready:
                raise DeviceLinkError("desktop_not_ready", 503)
            # Refused the same way as a task, before anything is made.
            gateway._check_device_autonomy(device, autonomy, options)
        paths: list[str] = []
        for transfer_id in files:
            received = self.store.received(device.device_id, transfer_id)
            if received is None:
                raise DeviceLinkError("unknown_transfer", 404)
            paths.append(str(received["path"]))
        session = Session(
            workspace=str(workspace.resolve()),
            mode=Mode.TASK,
            autonomy=autonomy,
            title=" ".join(title.split()),
        )
        origin: dict[str, object] = {"device": device.name, "labels": ["handoff"]}
        if paths:
            listing = "\n".join(f"- {path}" for path in paths)
            history.insert(0, ("user", f"Files from the phone, in this folder:\n{listing}"))
        with SQLiteEventStore(gateway._database) as store:
            store.create_session(session)
            self._write_history(store, session, history, origin)
        with gateway._lock:
            gateway._pending_host_events.append(
                Event(
                    session_id=session.id,
                    type="session.created",
                    data={
                        "session_id": session.id,
                        "title": session.title,
                        "mode": session.mode.value,
                        "autonomy": session.autonomy.value,
                        "activated": False,
                        # Listed in the window; the conversation open there stays open.
                        "selected": False,
                    },
                )
            )
        document: dict[str, object] = {"session_id": session.id, "title": session.title}
        if prompt and options is not None:
            document["task"] = gateway.device_submit(
                device, request_id, session.id, prompt, options, handoff=True, files=paths
            )
        self.store.remember_handoff(device.device_id, request_id, document)
        self.log(device, "conversation_received", session.title)
        return document

    @staticmethod
    def _write_history(
        store: SQLiteEventStore,
        session: Session,
        history: list[tuple[str, str]],
        origin: dict[str, object],
    ) -> None:
        """The phone's messages as earlier turns: each user message opens a finished turn. The
        first one carries where the conversation came from, for the window to show."""
        correlation: str | None = None

        def close() -> None:
            if correlation is not None:
                store.append(
                    Event(
                        session_id=session.id,
                        type="turn.completed",
                        data={},
                        correlation_id=correlation,
                    )
                )

        for index, (role, content) in enumerate(history):
            if role == "user" or correlation is None:
                close()
                correlation = str(uuid4())
                store.append(
                    Event(
                        session_id=session.id,
                        type="turn.started",
                        data={"continuation": False},
                        correlation_id=correlation,
                    )
                )
            store.append(
                Event(
                    session_id=session.id,
                    type="message.created",
                    data=_message_data(role, content, origin if index == 0 else None),
                    correlation_id=correlation,
                )
            )
        close()

    # ---- knowledge -------------------------------------------------------------------------------

    def knowledge(self) -> dict[str, object]:
        store = self._knowledge()
        bases: dict[str, dict[str, Any]] = {
            str(collection["id"]): {
                "id": collection["id"],
                # The default knowledge base is "" on both sides, whatever it is called.
                "name": "" if collection["id"] == DEFAULT_COLLECTION else collection["name"],
                "documents": [],
            }
            for collection in store.collections()
        }
        for document in store.documents(ready_only=True)[:_MAX_KNOWLEDGE_DOCUMENTS]:
            base = bases.get(str(document.get("collection_id") or DEFAULT_COLLECTION))
            if base is not None:
                base["documents"].append(
                    {
                        "id": document["id"],
                        "title": document["title"],
                        "sha256": document["sha256"],
                        "pages": document.get("pages"),
                        "passages": document.get("passages"),
                        "updated_at": document.get("updated_at"),
                    }
                )
        return {"bases": list(bases.values())}

    def knowledge_document(self, document_id: str) -> dict[str, object]:
        try:
            return self._knowledge().extracted(document_id)
        except (KeyError, KnowledgeError):
            raise DeviceLinkError("unknown_document", 404) from None

    def knowledge_add(
        self, device: PairedDevice, payload: dict[str, Any]
    ) -> tuple[int, dict[str, object]]:
        store = self._knowledge()
        try:
            collection = store.collection_named(payload.get("base", ""))
            added = store.add_extracted(payload, collection_id=collection, origin="phone")
        except KnowledgeError:
            raise DeviceLinkError("invalid_document") from None
        if added.get("duplicate"):
            return 200, {"document_id": added["id"], "duplicate": True}
        self.log(device, "knowledge_synced", str(added.get("title") or ""))
        return 201, {"document_id": added["id"]}

    # ---- the phone itself ----------------------------------------------------------------------

    def info(self, device: PairedDevice) -> dict[str, object]:
        current = self._gateway._device_link.registry.get(device.device_id) or device
        return {
            "device_id": current.device_id,
            "name": current.name,
            "scopes": list(current.scopes),
            "created_at": current.created_at,
            "last_seen_at": current.last_seen_at,
            "accepts_jobs": current.accepts_jobs,
            "notify": {"turns": current.notify_turns},
            "activity": self.store.activity(current.device_id),
        }

    def settings(self, device: PairedDevice, payload: dict[str, Any]) -> dict[str, object]:
        accepts = payload.get("accepts_jobs")
        if accepts is not None:
            if type(accepts) is not bool:
                raise DeviceLinkError("invalid_settings")
            self._gateway._device_link.registry.update(device.device_id, accepts_jobs=accepts)
        return self.info(device)

    def unpair(self, device: PairedDevice) -> None:
        self._gateway._device_link.revoke(device.device_id)


__all__ = ["FROM_PHONE_FOLDER", "DeviceHub", "model_location"]
