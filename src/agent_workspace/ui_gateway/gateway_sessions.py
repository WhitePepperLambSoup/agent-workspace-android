"""Conversations: lists, history pages and cursors, names and pins, search, export and import, fork,
compare and rewind, and the files each turn changed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

from agent_workspace.application.rewind import rewind_files
from agent_workspace.core.events import Event
from agent_workspace.core.session import Session
from agent_workspace.core.workspace_catalog import WorkspaceCatalog, WorkspaceCatalogError
from agent_workspace.policy.redaction import Redactor
from agent_workspace.storage import (
    BackupValidationError,
    SearchIndexUnavailableError,
    SessionExportError,
    SQLiteEventStore,
    export_session,
    import_session_archive,
)
from agent_workspace.ui_gateway.fork import ForkError, comparison, fork_conversation, fork_marker
from agent_workspace.ui_gateway.gateway_common import (
    _DISPLAY_FIELDS,
    _HISTORY_ASSISTANT_ENTRY_BYTES,
    _HISTORY_ENTRY_BYTES,
    _HISTORY_MAX_EVENTS,
    _HISTORY_MINIMUM_USER_TURNS,
    _HISTORY_TOTAL_BYTES,
    _MAX_COLLECTION_ITEMS,
    _MAX_PROVIDER_MODEL_CHARS,
    _MAX_SEARCH_RESULTS,
    _MAX_SESSIONS,
    _MAX_STRING_CHARS,
    _SAFE_HISTORY_TOOL_ARGUMENTS,
    _TERMINAL_TURN_EVENTS,
    GatewayError,
    GatewayReply,
    _archive_path,
    _bounded_text,
    _camel_case,
    _json_safe,
)
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import (
    CommandEnvelope,
)
from agent_workspace.ui_gateway.turn_files import (
    TURN_FILES_EVENT,
    TURN_FILES_UNDONE_EVENT,
    changed_file,
    display_record,
    file_diff,
    undo_hunk,
    undo_turn_files,
)


class SessionCommands(GatewayState):
    """Conversations: lists, history pages and cursors, names and pins, search, export and import,
    fork, compare and rewind, and the files each turn changed.
    """

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

    def _fork_session(self, command: CommandEnvelope) -> GatewayReply:
        """Continue a conversation from one of its user messages in a new session.

        ``keepReply`` false keeps what came before the message's turn and returns the message
        for the composer; true keeps that turn with its reply. ``compareModel`` makes a
        comparison fork: the returned prompt is sent again in it with that model.
        """
        self._require_payload(
            command,
            {"sessionId", "messageId", "keepReply"},
            optional={"title", "compareModel"},
        )
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        session = self._workspace_session(command.payload.get("sessionId"))
        message_id = command.payload.get("messageId")
        if not isinstance(message_id, str) or not message_id or len(message_id) > 128:
            raise GatewayError("invalid_message")
        keep_reply = command.payload.get("keepReply")
        if type(keep_reply) is not bool:
            raise GatewayError("invalid_fork")
        raw_title = command.payload.get("title", session.title)
        if not isinstance(raw_title, str) or not raw_title.strip() or len(raw_title) > 200:
            raise GatewayError("invalid_title")
        compare_model = None
        if "compareModel" in command.payload:
            compare_model = self._turn_model_override(command.payload["compareModel"])
            if keep_reply:
                raise GatewayError("invalid_fork")
        try:
            with SQLiteEventStore(self._database) as store:
                result = fork_conversation(
                    store,
                    session.id,
                    message_id,
                    keep_reply=keep_reply,
                    title=raw_title.strip(),
                    compare_model=compare_model,
                )
        except ForkError as error:
            raise GatewayError(error.code) from None
        except (OSError, KeyError, ValueError, RuntimeError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        forked = result.session
        with self._lock:
            self._pending_host_events.append(
                Event(
                    session_id=forked.id,
                    type="session.created",
                    data={
                        "session_id": forked.id,
                        "title": forked.title,
                        "mode": forked.mode.value,
                        "autonomy": forked.autonomy.value,
                        "activated": False,
                    },
                )
            )
            document = self._session_document(forked)
        payload: dict[str, object] = {
            "epoch": self.epoch,
            "session": document,
            "sourceSessionId": session.id,
            "prompt": result.prompt,
        }
        if result.source_model is not None:
            payload["sourceModel"] = result.source_model
        if compare_model is not None:
            payload["compareModel"] = compare_model
        return self._reply("session.fork.result", payload, session_id=None)

    def _compare_session(self, command: CommandEnvelope) -> GatewayReply:
        """Both answers of a comparison fork: the original model's and the other model's."""
        self._require_payload(command, {"sessionId"})
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        fork = self._workspace_session(command.payload.get("sessionId"))
        try:
            fork_events = SQLiteEventStore.list_events_read_only(self._database, fork.id)
            marker = fork_marker(fork_events)
            source_id = marker[1].data.get("source_session_id") if marker is not None else None
            source_events = (
                SQLiteEventStore.list_events_read_only(self._database, source_id)
                if isinstance(source_id, str) and self._stored_session(source_id) is not None
                else []
            )
            document = cast(dict[str, object], _json_safe(comparison(source_events, fork_events)))
        except ForkError as error:
            raise GatewayError(error.code) from None
        except (OSError, ValueError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "session.compare.result",
            {"epoch": self.epoch, "sessionId": fork.id, **document},
            session_id=None,
        )

    def _rewind_session(self, command: CommandEnvelope) -> GatewayReply:
        """Files the agent changed after a message, and putting them back as they were."""
        self._require_payload(command, {"sessionId", "messageId"}, optional={"apply"})
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        session = self._workspace_session(command.payload.get("sessionId"))
        message_id = command.payload.get("messageId")
        apply = command.payload.get("apply", False)
        if not isinstance(message_id, str) or not message_id or type(apply) is not bool:
            raise GatewayError("invalid_payload")
        with self._lock:
            running = session.id == self._host_session_id and (
                self._active_turn is not None or self._turn_requested
            )
        if apply and running:
            raise GatewayError("runtime_busy")  # the agent may still be changing these files
        try:
            events = SQLiteEventStore.list_events_read_only(self._database, session.id)
            report = rewind_files(
                Path(session.workspace), self._file_versions, events, message_id, apply=apply
            )
        except KeyError:
            raise GatewayError("unknown_message") from None
        except ValueError:
            raise GatewayError("workspace_unavailable") from None
        except (OSError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "session.rewind.result",
            {
                "epoch": self.epoch,
                "applied": apply,
                "files": [item.document() for item in report],
            },
            session_id=None,
        )

    def _turn_files_record(self, command: CommandEnvelope) -> tuple[Session, Event]:
        """The conversation and its ``turn.files.changed`` record a command names."""
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        session = self._workspace_session(command.payload.get("sessionId"))
        event_id = command.payload.get("eventId")
        if not isinstance(event_id, str) or not event_id or len(event_id) > 128:
            raise GatewayError("invalid_payload")
        try:
            record = SQLiteEventStore.get_event_read_only(self._database, event_id)
        except (OSError, ValueError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        if record is None or record.session_id != session.id or record.type != TURN_FILES_EVENT:
            raise GatewayError("unknown_turn_files")
        return session, record

    def _turn_file_diff(self, command: CommandEnvelope) -> GatewayReply:
        """What a turn changed in one file the agent wrote, against the file as it is now."""
        self._require_payload(command, {"sessionId", "eventId", "path"})
        session, record = self._turn_files_record(command)
        path = command.payload.get("path")
        if not isinstance(path, str) or not path or len(path) > 1024:
            raise GatewayError("invalid_payload")
        try:
            entry = changed_file(record, path)
        except KeyError:
            raise GatewayError("unknown_path") from None
        document = file_diff(Path(session.workspace), self._file_versions, entry)
        return self._reply(
            "turn.files.diff.result",
            {"epoch": self.epoch, "eventId": record.id, "path": path, **document},
            session_id=None,
        )

    def _undo_turn_hunk(self, command: CommandEnvelope) -> GatewayReply:
        """Put one part of a turn's change in a file back (the hunk the window shows)."""
        self._require_payload(command, {"sessionId", "eventId", "path", "hunk", "sha256"})
        session, record = self._turn_files_record(command)
        path, hunk, sha256 = (command.payload.get(key) for key in ("path", "hunk", "sha256"))
        if (
            not isinstance(path, str)
            or not path
            or type(hunk) is not int
            or not isinstance(sha256, str)
        ):
            raise GatewayError("invalid_payload")
        try:
            entry = changed_file(record, path)
        except KeyError:
            raise GatewayError("unknown_path") from None
        with self._lock:
            running = session.id == self._host_session_id and (
                self._active_turn is not None or self._turn_requested
            )
        if running:
            raise GatewayError("runtime_busy")  # the agent may still be changing the file
        try:
            current = undo_hunk(Path(session.workspace), self._file_versions, entry, hunk, sha256)
        except ValueError as reason:
            return self._reply(
                "turn.files.hunk.undo.result",
                {"epoch": self.epoch, "path": path, "undone": False, "reason": str(reason)},
                session_id=None,
            )
        except OSError:
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "turn.files.hunk.undo.result",
            {"epoch": self.epoch, "path": path, "undone": True, "currentSha256": current},
            session_id=None,
        )

    def _undo_turn_files(self, command: CommandEnvelope) -> GatewayReply:
        """Put files a turn created or changed back as they were before it (or preview that)."""
        self._require_payload(command, {"sessionId", "eventId"}, optional={"paths", "apply"})
        session, record = self._turn_files_record(command)
        raw_paths = command.payload.get("paths")
        apply = command.payload.get("apply", False)
        if type(apply) is not bool:
            raise GatewayError("invalid_payload")
        paths: list[str] | None = None
        if raw_paths is not None:
            if (
                not isinstance(raw_paths, list)
                or not 0 < len(raw_paths) <= 500
                or not all(isinstance(item, str) and 0 < len(item) <= 1024 for item in raw_paths)
            ):
                raise GatewayError("invalid_payload")
            paths = cast(list[str], raw_paths)
        with self._lock:
            running = session.id == self._host_session_id and (
                self._active_turn is not None or self._turn_requested
            )
        if apply and running:
            raise GatewayError("runtime_busy")  # the agent may still be changing these files
        try:
            report = undo_turn_files(
                Path(session.workspace), self._file_versions, record, paths, apply=apply
            )
        except ValueError:
            raise GatewayError("workspace_unavailable") from None
        except OSError:
            raise GatewayError("storage_unavailable") from None
        restored = [item.path for item in report if item.reason is None]
        if apply and restored:
            try:
                with SQLiteEventStore(self._database) as store:
                    stored = store.append(
                        Event(
                            session_id=session.id,
                            type=TURN_FILES_UNDONE_EVENT,
                            data={"changes_event_id": record.id, "paths": restored},
                            correlation_id=record.correlation_id,
                        )
                    )
            except (OSError, ValueError, sqlite3.DatabaseError):
                pass  # the files are back; only the note in the conversation is missing
            else:
                with self._lock:
                    self._pending_host_events.append(stored)
        return self._reply(
            "turn.files.undo.result",
            {
                "epoch": self.epoch,
                "eventId": record.id,
                "applied": apply,
                "files": [item.document() for item in report],
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
        origins = self._device_task_origins(session_id)
        for event in events:
            if event.type == "turn.input.applied" or (
                event.type == "turn.input.received" and event.id in applied_input_ids
            ):
                continue
            origin = origins.get(event.correlation_id or "")
            if (
                origin is not None
                and event.type == "message.created"
                and event.data.get("role") == "user"
                and "origin" not in event.data
            ):
                event = replace(event, data={**event.data, "origin": origin})
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
        if event.type == "session.forked":
            for key in ("source_session_id", "source_model", "compare_model", "keep_reply"):
                value = event.data.get(key)
                if isinstance(value, bool) or (
                    isinstance(value, str) and len(value) <= _MAX_PROVIDER_MODEL_CHARS
                ):
                    data[_camel_case(key)] = value
        elif event.type in {TURN_FILES_EVENT, TURN_FILES_UNDONE_EVENT}:
            shown = display_record(event.data) if event.type == TURN_FILES_EVENT else event.data
            for key in ("turn_id", "files", "omitted", "listed", "changes_event_id", "paths"):
                if key in shown:
                    with suppress(GatewayError):
                        data[_camel_case(key)] = _json_safe(shown[key])
        elif event.type == "turn.failed":
            error_type = event.data.get("error_type")
            if isinstance(error_type, str) and len(error_type) <= 128:
                data["errorType"] = error_type
            message = event.data.get("message")
            if isinstance(message, str):
                data["message"] = Redactor().redact(message[:600])
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
