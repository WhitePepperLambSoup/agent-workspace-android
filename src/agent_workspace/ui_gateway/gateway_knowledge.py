"""The knowledge base, watched folders and document previews."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from agent_workspace.knowledge import (
    KnowledgeError,
    KnowledgeStore,
    knowledge_root,
    knowledge_store,
)
from agent_workspace.knowledge import error_code as knowledge_error_code
from agent_workspace.knowledge.watch import FolderWatch, suggested_folders
from agent_workspace.tools.base import ToolError
from agent_workspace.tools.filesystem import sha256_bytes
from agent_workspace.tools.office_preview import PreviewError, preview_office
from agent_workspace.tools.paths import WorkspacePaths
from agent_workspace.ui_gateway.gateway_common import (
    _DOCUMENT_PREVIEW_BYTES,
    _KNOWLEDGE_EXCERPT_CHARS,
    _KNOWLEDGE_MAX_FILES,
    _KNOWLEDGE_SEARCH_LIMIT,
    _LOGGER,
    _SHA256,
    GatewayError,
    GatewayReply,
    _camel_keys,
)
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import (
    CommandEnvelope,
)


class KnowledgeCommands(GatewayState):
    """The knowledge base, watched folders and document previews."""

    def _knowledge_command(self, command: CommandEnvelope) -> GatewayReply:
        """The knowledge base: documents, knowledge bases and each conversation's choice."""
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        payload = command.payload
        store = knowledge_store(knowledge_root(self._database))
        added: dict[str, object] = {}
        try:
            if command.type == "knowledge.status":
                self._require_payload(command, set())
            elif command.type == "knowledge.configure":
                self._require_payload(command, set(), optional={"enabled", "auto", "synonyms"})
                if "enabled" in payload or "auto" in payload:
                    store.set_settings(enabled=payload.get("enabled"), auto=payload.get("auto"))
                if "synonyms" in payload:
                    store.set_synonyms(payload["synonyms"])
            elif command.type == "knowledge.add":
                self._require_payload(command, set(), optional={"paths", "url", "collectionId"})
                added = self._knowledge_add(store, payload)
            elif command.type == "knowledge.document.update":
                self._require_payload(command, {"documentId"}, optional={"title", "collectionId"})
                if "title" in payload:
                    store.rename(payload["documentId"], payload["title"])
                if "collectionId" in payload:
                    store.move_document(payload["documentId"], payload["collectionId"])
            elif command.type == "knowledge.document.delete":
                self._require_payload(command, {"documentId"})
                store.delete(payload["documentId"])
            elif command.type == "knowledge.collection.create":
                self._require_payload(command, {"name"}, optional={"defaultOn"})
                created = store.create_collection(
                    payload["name"], default_on=payload.get("defaultOn", True)
                )
                added = {"collection": created}
            elif command.type == "knowledge.collection.update":
                self._require_payload(command, {"collectionId"}, optional={"name", "defaultOn"})
                if "name" in payload:
                    store.rename_collection(payload["collectionId"], payload["name"])
                if "defaultOn" in payload:
                    store.set_collection_default(payload["collectionId"], payload["defaultOn"])
            elif command.type == "knowledge.collection.delete":
                self._require_payload(command, {"collectionId"})
                store.delete_collection(payload["collectionId"])
            elif command.type == "knowledge.session.get":
                self._require_payload(command, {"sessionId"})
                selection = store.session_selection(payload["sessionId"])
                return self._knowledge_reply(command, selection)
            elif command.type == "knowledge.session.set":
                self._require_payload(command, {"sessionId", "collections"})
                selection = store.set_session_selection(
                    payload["sessionId"], payload["collections"]
                )
                return self._knowledge_reply(command, selection)
            else:
                self._require_payload(command, {"query"}, optional={"collections"})
                query, collections = payload["query"], payload.get("collections")
                if not isinstance(query, str) or not query.strip() or len(query) > 500:
                    raise GatewayError("invalid_command")
                if collections is not None and (
                    not isinstance(collections, list)
                    or not all(isinstance(item, str) for item in collections)
                ):
                    raise GatewayError("invalid_command")
                results = store.search(
                    query, limit=_KNOWLEDGE_SEARCH_LIMIT, collections=collections
                )
                return self._knowledge_reply(
                    command,
                    {
                        "results": [
                            store.public(result, excerpt=_KNOWLEDGE_EXCERPT_CHARS)
                            for result in results
                        ]
                    },
                )
            snapshot = store.snapshot()
        except KnowledgeError as error:
            raise GatewayError(f"knowledge_{knowledge_error_code(str(error))}") from None
        except KeyError:
            raise GatewayError("knowledge_not_found") from None
        except (OSError, sqlite3.Error):
            raise GatewayError("storage_unavailable") from None
        for document in snapshot["documents"]:
            if document.get("error"):
                document["error_code"] = knowledge_error_code(document["error"])
        return self._knowledge_reply(command, {**snapshot, **added})

    @staticmethod
    def _knowledge_add(store: KnowledgeStore, payload: Mapping[str, object]) -> dict[str, object]:
        """Files picked on this computer, or one web page; each file is added on its own."""
        paths, url = payload.get("paths"), payload.get("url")
        collection_id = payload.get("collectionId")
        if (paths is None) == (url is None) or (
            collection_id is not None and not isinstance(collection_id, str)
        ):
            raise GatewayError("invalid_command")
        if url is not None:
            return {"added": [store.add_url(url, collection_id=collection_id)], "failed": []}
        if (
            not isinstance(paths, list)
            or not paths
            or len(paths) > _KNOWLEDGE_MAX_FILES
            or not all(isinstance(path, str) and 0 < len(path) <= 4096 for path in paths)
        ):
            raise GatewayError("invalid_command")
        documents: list[dict[str, Any]] = []
        failed: list[dict[str, str]] = []
        for raw in paths:
            source = Path(raw)
            try:
                if not source.is_absolute() or not source.is_file():
                    raise KnowledgeError("a file name is required")
                documents.append(
                    store.add_file(
                        source, source.name, origin="upload", collection_id=collection_id
                    )
                )
            except KnowledgeError as error:
                failed.append({"name": source.name, "code": knowledge_error_code(str(error))})
            except OSError:
                failed.append({"name": source.name, "code": "unreadable"})
        return {"added": documents, "failed": failed}

    def _knowledge_reply(
        self, command: CommandEnvelope, document: Mapping[str, object]
    ) -> GatewayReply:
        return self._reply(
            f"{command.type}.result",
            {"epoch": self.epoch, **cast(dict[str, object], _camel_keys(document))},
            session_id=None,
        )

    def _watch(self) -> FolderWatch:
        if self._folder_watch is None:
            root = knowledge_root(self._database)
            self._folder_watch = FolderWatch(root, knowledge_store(root))
        return self._folder_watch

    def _tick_folder_watch(self) -> None:
        """Scan the watched folders when it is time (gateway lock held, so the scan runs apart)."""
        if self._closing or (self._watch_thread is not None and self._watch_thread.is_alive()):
            return
        if not self._watch().due():
            return
        self._start_watch_scan()

    def _start_watch_scan(self) -> None:
        thread = threading.Thread(
            target=self._scan_watched_folders, name="gateway-folder-watch", daemon=True
        )
        self._watch_thread = thread
        thread.start()

    def _scan_watched_folders(self) -> None:
        try:
            self._watch().scan()
        except Exception:
            _LOGGER.exception("watched folder scan failed")

    def _watch_command(self, command: CommandEnvelope) -> GatewayReply:
        """Folders whose new documents join a knowledge base by themselves."""
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        watch = self._watch()
        payload: dict[str, object] = {"epoch": self.epoch}
        try:
            if command.type == "knowledge.watch.list":
                self._require_payload(command, set())
                payload["folders"] = [folder.document() for folder in watch.folders()]
                payload["suggested"] = suggested_folders()
            elif command.type == "knowledge.watch.add":
                self._require_payload(command, {"path"}, optional={"collectionId"})
                folder = watch.add(command.payload.get("path"), command.payload.get("collectionId"))
                payload["folder"] = folder.document()
                if self._watch_thread is None or not self._watch_thread.is_alive():
                    self._start_watch_scan()  # its documents start arriving now
            elif command.type == "knowledge.watch.remove":
                self._require_payload(command, {"path"})
                payload["removed"] = watch.remove(command.payload.get("path"))
            else:
                self._require_payload(command, set())
                report = watch.scan()
                payload.update(added=report.added, waiting=report.waiting, failed=report.failed)
        except KnowledgeError as error:
            raise GatewayError(knowledge_error_code(str(error))) from None
        except OSError:
            raise GatewayError("storage_unavailable") from None
        return self._reply(f"{command.type}.result", payload, session_id=None)

    def _document_preview(self, command: CommandEnvelope) -> GatewayReply:
        """What a Word, Excel or PowerPoint file of the open folder shows; with the digest of the
        content a tool call replaced, also that earlier version (from the version store)."""
        self._require_payload(command, {"path"}, optional={"previousSha256", "resultSha256"})
        raw_path = command.payload["path"]
        previous = command.payload.get("previousSha256")
        produced = command.payload.get("resultSha256")
        if not isinstance(raw_path, str) or not raw_path or len(raw_path) > 4096:
            raise GatewayError("invalid_path")
        for digest in (previous, produced):
            if digest is not None and (not isinstance(digest, str) or not _SHA256.match(digest)):
                raise GatewayError("unknown_change")
        with self._lock:
            workspace = self._workspace
        if workspace is None:
            raise GatewayError("runtime_unconfigured")
        paths = WorkspacePaths(workspace)
        try:
            target = paths.resolve(raw_path)
            relative = paths.relative(target)
        except (OSError, ToolError, ValueError):
            raise GatewayError("invalid_path") from None
        suffix = target.suffix.casefold()
        if suffix not in {".docx", ".xlsx", ".pptx"}:
            raise GatewayError("unsupported_type")
        try:
            if not target.is_file():
                raise GatewayError("file_not_found")
            if target.stat().st_size > _DOCUMENT_PREVIEW_BYTES:
                raise GatewayError("too_large")
            data = target.read_bytes()
        except OSError:
            raise GatewayError("file_not_found") from None
        try:
            preview = preview_office(data, suffix)
        except PreviewError as error:
            raise GatewayError(str(error)) from None
        payload: dict[str, object] = {"epoch": self.epoch, "path": relative, "preview": preview}
        if isinstance(previous, str):
            earlier = self._file_versions.read(previous)
            before = None
            if earlier is not None:
                with suppress(PreviewError):
                    before = preview_office(earlier, suffix)
            payload["before"] = before
            payload["beforeAvailable"] = before is not None
            if isinstance(produced, str):
                payload["changedLater"] = sha256_bytes(data) != produced
        return self._reply("document.preview.result", payload, session_id=command.session_id)
