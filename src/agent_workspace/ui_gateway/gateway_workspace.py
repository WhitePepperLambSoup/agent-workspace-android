"""The open folder: files, memory, research sources, changesets, context, background jobs and
terminals.
"""

from __future__ import annotations

import base64
import os
import re
import sqlite3
from collections.abc import Mapping
from concurrent.futures import Future
from pathlib import Path, PurePosixPath
from typing import cast

from agent_workspace.core.background_jobs import BackgroundJobStatus
from agent_workspace.core.events import Event, validate_event_payload
from agent_workspace.core.instructions import INSTRUCTION_FILENAMES, discover_skill_files
from agent_workspace.core.models import (
    MemoryItem,
    capabilities_for_mode,
)
from agent_workspace.core.skills import SkillError, load_skills
from agent_workspace.storage import (
    SQLiteEventStore,
)
from agent_workspace.tools.base import ConcurrentModificationError, ToolError
from agent_workspace.tools.custom import CustomToolError, load_custom_tool_definitions
from agent_workspace.tools.filesystem import atomic_write, sha256_bytes
from agent_workspace.tools.mcp_host import McpHostError, load_mcp_servers
from agent_workspace.tools.paths import WorkspacePaths
from agent_workspace.tools.terminal_sessions import TerminalSessionError
from agent_workspace.ui_gateway.gateway_common import (
    _COMMAND_TIMEOUT_SECONDS,
    _MAX_CHANGE_PAGE_BYTES,
    _MAX_COLLECTION_ITEMS,
    _MAX_JOB_LOG_BYTES,
    _MAX_STRING_CHARS,
    _MAX_WORKSPACE_EDIT_BYTES,
    _MAX_WORKSPACE_READ_BYTES,
    _TERMINAL_JOB_STATES,
    GatewayError,
    GatewayReply,
    _bounded_projection,
    _context_budget_from_manifest,
    _json_safe,
    _workspace_error_text,
)
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import (
    CommandEnvelope,
)


class WorkspaceCommands(GatewayState):
    """The open folder: files, memory, research sources, changesets, context, background jobs and
    terminals.
    """

    def _memory_scope(self) -> tuple[str, str | None]:
        """Return the workspace key memories use and a session to attribute edits to."""
        with self._lock:
            workspace = self._workspace
            selected = self._selected_session_id
        if workspace is None:
            raise GatewayError("runtime_unconfigured")
        if selected:
            session = self._stored_session(selected)
            if session is not None and Path(session.workspace).resolve() == workspace:
                return session.workspace, session.id
        if not self._database.is_file():
            return str(workspace), None
        try:
            sessions = SQLiteEventStore.list_sessions_read_only(
                self._database, 1, workspace=workspace, exclude_run_sessions=True
            )
        except (OSError, ValueError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        if sessions:
            return sessions[0].workspace, sessions[0].id
        return str(workspace), None

    @staticmethod
    def _memory_document(memory: MemoryItem) -> dict[str, object]:
        return {
            "id": memory.id,
            "content": memory.content,
            "tags": list(memory.tags),
            "sourceSessionId": memory.source_session_id,
            "createdAt": memory.created_at,
            "updatedAt": memory.updated_at,
            "expiresAt": memory.expires_at,
        }

    def _list_memories(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"query", "limit"})
        query = command.payload.get("query", "")
        limit = command.payload.get("limit", 200)
        if not isinstance(query, str) or len(query) > 500:
            raise GatewayError("invalid_query")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise GatewayError("invalid_limit")
        workspace, _session_id = self._memory_scope()
        try:
            memories = (
                SQLiteEventStore.list_memories_read_only(
                    self._database, workspace, query=query.strip(), limit=limit
                )
                if self._database.is_file()
                else []
            )
        except (OSError, ValueError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "memory.list.result",
            {
                "epoch": self.epoch,
                "memories": [self._memory_document(memory) for memory in memories],
                "truncated": len(memories) >= limit,
            },
            session_id=None,
        )

    def _write_memory(self, command: CommandEnvelope) -> GatewayReply:
        """Edit or delete one memory through the same events the memory tool appends."""
        deleting = command.type == "memory.delete"
        if deleting:
            self._require_payload(command, {"memoryId"})
        else:
            self._require_payload(command, {"memoryId", "content"}, optional={"tags"})
        memory_id = command.payload.get("memoryId")
        if not isinstance(memory_id, str) or not memory_id or len(memory_id) > 128:
            raise GatewayError("invalid_memory")
        workspace, session_id = self._memory_scope()
        if session_id is None:
            raise GatewayError("session_required")
        data: dict[str, object] = {"memory_id": memory_id, "workspace": workspace}
        try:
            with SQLiteEventStore(self._database) as store:
                existing = store.get_memory(workspace, memory_id)
                if existing is None:
                    raise GatewayError("unknown_memory")
                if not deleting:
                    content = command.payload.get("content")
                    tags = command.payload.get("tags", list(existing.tags))
                    if not isinstance(content, str) or not content.strip() or len(content) > 10_000:
                        raise GatewayError("invalid_memory")
                    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
                        raise GatewayError("invalid_memory")
                    cleaned: list[str] = []
                    for tag in (tag.strip() for tag in tags):
                        if tag and tag.casefold() not in {item.casefold() for item in cleaned}:
                            cleaned.append(tag[:64])
                    if len(cleaned) > 16:
                        raise GatewayError("invalid_memory")
                    data["content"] = content.strip()
                    data["tags"] = cleaned
                    data["expires_at"] = existing.expires_at
                event_type = "memory.deleted" if deleting else "memory.upserted"
                validate_event_payload(event_type, data)
                store.append(Event(session_id=session_id, type=event_type, data=data))
                updated = None if deleting else store.get_memory(workspace, memory_id)
        except GatewayError:
            raise
        except ValueError:
            raise GatewayError("invalid_memory") from None
        except (OSError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            f"{command.type}.result",
            {
                "epoch": self.epoch,
                "memoryId": memory_id,
                "deleted": deleting,
                "memory": self._memory_document(updated) if updated is not None else None,
            },
            session_id=None,
        )

    def _inspect_agent_setup(self, command: CommandEnvelope) -> GatewayReply:
        """Report the instruction, skill, MCP and custom-tool files the agent loads.

        Editing goes through the ordinary workspace file commands; this read-only
        view shows what parses and why a file is rejected.
        """
        self._require_payload(command, set())
        with self._lock:
            workspace = self._workspace
        if workspace is None:
            raise GatewayError("runtime_unconfigured")
        paths = WorkspacePaths(workspace)

        def file_fact(relative: str) -> dict[str, object]:
            try:
                target = paths.resolve(relative)
                exists = target.is_file()
                size = target.stat().st_size if exists else 0
            except (OSError, ValueError, ToolError):
                exists, size = False, 0
            return {"path": relative, "exists": exists, "bytes": size}

        instructions = [file_fact(name) for name in INSTRUCTION_FILENAMES]
        skills: list[dict[str, object]] = []
        skill_error: str | None = None
        try:
            for skill in load_skills(workspace):
                skills.append(
                    {
                        "id": skill.id,
                        "name": skill.name,
                        "description": skill.description[:500],
                        "path": paths.relative(Path(skill.path)),
                    }
                )
        except SkillError as exc:
            skill_error = _workspace_error_text(exc, workspace)
        skill_files = [paths.relative(path) for path in discover_skill_files(workspace)]
        servers: list[dict[str, object]] = []
        mcp_error: str | None = None
        try:
            for server in load_mcp_servers(workspace):
                servers.append({"id": server.id, "command": list(server.command)[:32]})
        except McpHostError as exc:
            mcp_error = _workspace_error_text(exc, workspace)
        custom_tools: list[dict[str, object]] = []
        custom_error: str | None = None
        try:
            for definition in load_custom_tool_definitions(workspace):
                custom_tools.append(
                    {
                        "name": definition.name,
                        "description": definition.description[:500],
                        "path": paths.relative(Path(definition.path)),
                    }
                )
        except CustomToolError as exc:
            custom_error = _workspace_error_text(exc, workspace)
        return self._reply(
            "workspace.agent.inspect.result",
            {
                "epoch": self.epoch,
                "instructions": instructions,
                "skills": skills,
                "skillFiles": skill_files[:200],
                "skillError": skill_error,
                "mcp": {**file_fact(".agent/mcp.toml"), "servers": servers, "error": mcp_error},
                "customTools": custom_tools,
                "customToolError": custom_error,
            },
            session_id=None,
        )

    def _workspace_summary(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured(allow_awaiting_approval=True)
        self._require_payload(command, set())
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        assert self._workspace is not None
        provider = self._provider
        try:
            sessions = (
                SQLiteEventStore.list_sessions_read_only(
                    self._database,
                    _MAX_COLLECTION_ITEMS,
                    workspace=self._workspace,
                    exclude_run_sessions=True,
                )
                if self._database.is_file()
                else []
            )
        except (OSError, sqlite3.DatabaseError, ValueError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "workspace.summary.get.result",
            {
                "epoch": self.epoch,
                "name": self._workspace.name,
                "path": str(self._workspace),
                "sessionCount": len(sessions),
                "provider": (
                    None if provider is None else {"id": provider.id, "model": provider.model}
                ),
                "runtime": {
                    "state": self._runtime_state,
                    "mode": self._mode.value,
                    "activeTurn": self._active_turn,
                },
                "capabilities": sorted(
                    capability.value for capability in capabilities_for_mode(self._mode)
                ),
            },
            session_id=None,
        )

    @staticmethod
    def _research_page_bounds(command: CommandEnvelope, *, max_limit: int) -> tuple[int, int]:
        offset = command.payload.get("offset", 0)
        limit = command.payload.get("limit", 20)
        if type(offset) is not int or not 0 <= offset <= 100_000:
            raise GatewayError("invalid_offset")
        if type(limit) is not int or not 1 <= limit <= max_limit:
            raise GatewayError("invalid_limit")
        return offset, limit

    def _list_research_sources(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"offset", "limit"})
        self._require_selected_session(command.session_id)
        assert command.session_id is not None
        offset, limit = self._research_page_bounds(command, max_limit=50)
        try:
            with SQLiteEventStore(self._database) as store:
                all_sources = store.list_research_sources(command.session_id)
        except (OSError, sqlite3.DatabaseError, ValueError):
            raise GatewayError("storage_unavailable") from None
        page = all_sources[offset : offset + limit]
        next_offset = offset + len(page) if len(all_sources) > offset + limit else None
        return self._reply(
            "research.sources.list.result",
            {
                "epoch": self.epoch,
                "sources": [
                    {
                        "id": source.id,
                        "url": source.url,
                        "title": source.title,
                        "summary": source.summary[:2_000],
                        "mediaType": source.media_type,
                        "fetchedAt": source.fetched_at,
                        "truncated": source.truncated,
                        "artifactSha256": source.artifact_sha256,
                        "artifactBytes": source.artifact_bytes,
                    }
                    for source in page
                ],
                "truncated": next_offset is not None,
                "nextOffset": next_offset,
            },
            session_id=command.session_id,
        )

    def _read_research_source(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"sourceId"}, optional={"offset", "maxChars"})
        self._require_selected_session(command.session_id)
        assert command.session_id is not None
        source_id = command.payload.get("sourceId")
        if not isinstance(source_id, str) or re.fullmatch(r"[0-9a-fA-F]{64}", source_id) is None:
            raise GatewayError("invalid_source_id")
        offset = command.payload.get("offset", 0)
        maximum = command.payload.get("maxChars", 16_000)
        if type(offset) is not int or not 0 <= offset <= 131_072:
            raise GatewayError("invalid_offset")
        if type(maximum) is not int or not 1 <= maximum <= 32_768:
            raise GatewayError("invalid_limit")
        try:
            with SQLiteEventStore(self._database) as store:
                source = next(
                    (
                        item
                        for item in store.list_research_sources(command.session_id)
                        if item.id == source_id.lower()
                    ),
                    None,
                )
                if source is None:
                    raise GatewayError("research_source_not_found")
                artifact = store.get_text_artifact(source.artifact_sha256)
                if artifact is None:
                    raise GatewayError("research_source_unavailable")
                content = artifact.content.decode("utf-8")
        except GatewayError:
            raise
        except (OSError, sqlite3.DatabaseError, UnicodeDecodeError, ValueError):
            raise GatewayError("storage_unavailable") from None
        part = content[offset : offset + maximum]
        next_offset = offset + len(part) if offset + len(part) < len(content) else None
        return self._reply(
            "research.source.read.result",
            {
                "epoch": self.epoch,
                "sourceId": source_id.lower(),
                "content": part,
                "offset": offset,
                "totalChars": len(content),
                "truncated": next_offset is not None,
                "nextOffset": next_offset,
            },
            session_id=command.session_id,
        )

    def _list_research_citations(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"offset", "limit"})
        self._require_selected_session(command.session_id)
        assert command.session_id is not None
        offset, limit = self._research_page_bounds(command, max_limit=20)
        try:
            with SQLiteEventStore(self._database) as store:
                all_citations = store.list_citations(command.session_id)
        except (OSError, sqlite3.DatabaseError, ValueError):
            raise GatewayError("storage_unavailable") from None
        page = all_citations[offset : offset + limit]
        next_offset = offset + len(page) if len(all_citations) > offset + limit else None
        return self._reply(
            "research.citations.list.result",
            {
                "epoch": self.epoch,
                "citations": [
                    {
                        "id": citation.id,
                        "sourceId": citation.source_id,
                        "claim": citation.claim,
                        "locator": citation.locator,
                        "quote": citation.quote,
                        "createdAt": citation.created_at,
                    }
                    for citation in page
                ],
                "truncated": next_offset is not None,
                "nextOffset": next_offset,
            },
            session_id=command.session_id,
        )

    def _list_changes(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, set(), optional={"limit"})
        self._require_selected_session(command.session_id)
        limit = command.payload.get("limit", 20)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise GatewayError("invalid_limit")
        assert self._workspace is not None and command.session_id is not None
        try:
            with SQLiteEventStore(self._database) as store:
                events = store.list_sandbox_changeset_events(
                    command.session_id, str(self._workspace), limit=limit + 1
                )
                documents = [
                    self._changeset_summary(store, command.session_id, event)
                    for event in events[:limit]
                ]
        except (OSError, ValueError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "changes.list.result",
            {
                "epoch": self.epoch,
                "changesets": documents,
                "truncated": len(events) > limit,
            },
            session_id=command.session_id,
        )

    def _changeset_summary(
        self, store: SQLiteEventStore, session_id: str, event: Event
    ) -> dict[str, object]:
        assert self._workspace is not None
        changes = event.data.get("changes")
        changeset_id = event.data.get("changeset_id")
        if not isinstance(changes, list) or not isinstance(changeset_id, str):
            raise GatewayError("invalid_change")
        supported: set[str] = set()
        files_summary: list[dict[str, object]] = []
        for change in changes:
            if not isinstance(change, Mapping):
                continue
            path = change.get("path")
            if isinstance(path, str):
                is_supported = change.get("apply_supported") is True
                if is_supported:
                    supported.add(path)
                files_summary.append(
                    {
                        "path": path,
                        "kind": change.get("kind", "modified"),
                        "applySupported": is_supported,
                        "beforeBytes": change.get("before_bytes"),
                        "afterBytes": change.get("after_bytes"),
                    }
                )
        applied = {
            item.data.get("path")
            for item in store.list_sandbox_change_applied_events(
                session_id, str(self._workspace), changeset_id
            )
            if isinstance(item.data.get("path"), str)
        }
        rejected = 0
        for path in supported:
            review = store.get_sandbox_change_review_event(
                session_id, str(self._workspace), changeset_id, path
            )
            if review is not None and review.data.get("decision") == "rejected":
                rejected += 1
        applied_count = len(applied & supported)
        state = (
            "rejected"
            if rejected
            else "review_only"
            if not supported
            else "applied"
            if applied_count == len(supported)
            else "partially_applied"
            if applied_count
            else "pending"
        )
        return {
            "changesetId": changeset_id,
            "createdAt": event.created_at,
            "changeCount": len(changes),
            "supportedCount": len(supported),
            "appliedCount": applied_count,
            "rejectedCount": rejected,
            "state": state,
            "files": files_summary,
        }

    def _inspect_change(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(
            command,
            {"changesetId", "path"},
            optional={"offsetBytes", "maxBytes"},
        )
        self._require_selected_session(command.session_id)
        changeset_id = command.payload.get("changesetId")
        raw_path = command.payload.get("path")
        offset = command.payload.get("offsetBytes", 0)
        max_bytes = command.payload.get("maxBytes", 65_536)
        if not isinstance(changeset_id, str) or re.fullmatch(r"[0-9a-f]{64}", changeset_id) is None:
            raise GatewayError("invalid_change")
        if not isinstance(raw_path, str) or not self._is_canonical_relative_path(raw_path):
            raise GatewayError("invalid_change")
        if type(offset) is not int or offset < 0:
            raise GatewayError("invalid_change")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 1_048_576:
            raise GatewayError("invalid_change")
        assert self._workspace is not None and command.session_id is not None
        try:
            with SQLiteEventStore(self._database) as store:
                event = store.get_sandbox_changeset_event(
                    command.session_id, str(self._workspace), changeset_id
                )
                if event is None:
                    raise GatewayError("unknown_change")
                changes = event.data.get("changes")
                change = (
                    next(
                        (
                            item
                            for item in changes
                            if isinstance(item, Mapping) and item.get("path") == raw_path
                        ),
                        None,
                    )
                    if isinstance(changes, list)
                    else None
                )
                if change is None:
                    raise GatewayError("unknown_change")
                applied = store.get_sandbox_change_applied_event(
                    command.session_id, str(self._workspace), changeset_id, raw_path
                )
                review = store.get_sandbox_change_review_event(
                    command.session_id, str(self._workspace), changeset_id, raw_path
                )
                content: bytes | None = None
                utf8 = False
                artifact_id = change.get("artifact_sha256")
                if isinstance(artifact_id, str):
                    artifact = store.get_binary_artifact(artifact_id)
                    if artifact is None:
                        raise GatewayError("storage_unavailable")
                    content = artifact.content
                    utf8 = change.get("content_kind") == "utf8"
                elif isinstance(change.get("after_text"), str):
                    content = cast(str, change["after_text"]).encode("utf-8")
                    utf8 = True
        except GatewayError:
            raise
        except (OSError, ValueError):
            raise GatewayError("storage_unavailable") from None
        page = None
        if content is not None:
            cap = min(max_bytes, _MAX_CHANGE_PAGE_BYTES)
            raw_page = content[offset : offset + cap]
            encoding = "utf-8" if utf8 else "base64"
            data = (
                raw_page.decode("utf-8", errors="ignore")
                if utf8
                else base64.b64encode(raw_page).decode("ascii")
            )
            page = {
                "encoding": encoding,
                "data": data,
                "offsetBytes": offset,
                "bytes": len(content),
                "truncated": offset + len(raw_page) < len(content),
            }
        payload: dict[str, object] = {
            "epoch": self.epoch,
            "changesetId": changeset_id,
            "path": raw_path,
            "kind": change.get("kind"),
            "beforeType": change.get("before_type"),
            "afterType": change.get("after_type"),
            "beforeBytes": change.get("before_bytes"),
            "afterBytes": change.get("after_bytes"),
            "beforeSha256": change.get("before_sha256"),
            "afterSha256": change.get("after_sha256"),
            "applySupported": change.get("apply_supported") is True,
            "applied": applied is not None,
            "review": review.data.get("decision") if review is not None else None,
            "content": page,
        }
        return self._reply("changes.inspect.result", payload, session_id=command.session_id)

    @staticmethod
    def _is_canonical_relative_path(path: str) -> bool:
        if not path or path != path.strip() or len(path) > 512 or "\\" in path or ":" in path:
            return False
        pure = PurePosixPath(path)
        return (
            not pure.is_absolute()
            and pure.as_posix() == path
            and all(part not in {"", ".", ".."} for part in pure.parts)
        )

    def _list_workspace_files_tree(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, set(), optional={"path", "maxDepth", "limit"})
        assert self._workspace is not None
        root_path = self._workspace
        paths = WorkspacePaths(root_path)
        rel_sub = command.payload.get("path", "")
        if not isinstance(rel_sub, str):
            raise GatewayError("invalid_path")
        max_depth = command.payload.get("maxDepth", 6)
        if type(max_depth) is not int or max_depth < 1:
            max_depth = 6
        raw_limit = command.payload.get("limit", 1000)
        limit = min(raw_limit if type(raw_limit) is int and raw_limit > 0 else 1000, 3000)

        try:
            target_dir = paths.resolve(rel_sub) if rel_sub.strip() else root_path
        except Exception:
            raise GatewayError("invalid_path") from None

        if not target_dir.is_dir():
            raise GatewayError("workspace_not_found")

        ignore_dirs = {
            ".git",
            "node_modules",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "dist",
            "build",
            "out",
            "output",
            ".gemini",
        }

        items: list[dict[str, object]] = []
        target_depth = len(target_dir.parts)
        try:
            for current_root, dirnames, filenames in os.walk(target_dir):
                dirnames[:] = [
                    d for d in dirnames if d not in ignore_dirs and not d.startswith(".")
                ]
                curr_path = Path(current_root)
                curr_depth = len(curr_path.parts) - target_depth
                if curr_depth >= max_depth:
                    dirnames.clear()

                if curr_path != target_dir:
                    rel_dir = paths.relative(curr_path)
                    try:
                        st = curr_path.stat()
                        mtime = st.st_mtime
                    except OSError:
                        mtime = 0.0
                    items.append(
                        {
                            "path": rel_dir,
                            "name": curr_path.name,
                            "type": "directory",
                            "size": 0,
                            "modified": mtime,
                        }
                    )
                    if len(items) >= limit:
                        break

                for f in sorted(filenames):
                    if f.startswith("."):
                        continue
                    file_path = curr_path / f
                    try:
                        st = file_path.stat()
                        items.append(
                            {
                                "path": paths.relative(file_path),
                                "name": f,
                                "type": "file",
                                "size": st.st_size,
                                "modified": st.st_mtime,
                            }
                        )
                    except OSError:
                        continue
                    if len(items) >= limit:
                        break
                if len(items) >= limit:
                    break
        except (OSError, ValueError):
            raise GatewayError("storage_unavailable") from None

        return self._reply(
            "workspace.files.tree.result",
            {"epoch": self.epoch, "files": items, "truncated": len(items) >= limit},
            session_id=command.session_id,
        )

    def _read_workspace_file(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"path"}, optional={"offset", "maxBytes"})
        assert self._workspace is not None
        raw_path = command.payload.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise GatewayError("invalid_path")
        offset = command.payload.get("offset", 0)
        if type(offset) is not int or offset < 0:
            raise GatewayError("invalid_offset")
        max_bytes = command.payload.get("maxBytes", 512 * 1024)
        if type(max_bytes) is not int or not 1 <= max_bytes <= _MAX_WORKSPACE_READ_BYTES:
            raise GatewayError("invalid_limit")
        paths = WorkspacePaths(self._workspace)
        try:
            target = paths.resolve(raw_path.strip())
            if not target.is_file():
                raise GatewayError("file_not_found")

            size = target.stat().st_size
            if size > _MAX_WORKSPACE_EDIT_BYTES:
                with target.open("rb") as f:
                    sample = f.read(64 * 1024)
                    if offset > 0:
                        f.seek(offset)
                    slice_bytes = f.read(max_bytes)
                sha256 = "unavailable_large_file"
                try:
                    sample.decode("utf-8")
                    is_binary = b"\x00" in sample
                except UnicodeDecodeError:
                    is_binary = True
            else:
                content_bytes = target.read_bytes()
                sha256 = sha256_bytes(content_bytes)
                slice_bytes = content_bytes[offset : offset + max_bytes]
                try:
                    content_bytes.decode("utf-8")
                    is_binary = b"\x00" in content_bytes
                except UnicodeDecodeError:
                    is_binary = True

            content_str = slice_bytes.decode("utf-8", errors="replace")
            truncated = (offset + len(slice_bytes)) < size
            editable = (
                offset == 0
                and (not truncated)
                and (not is_binary)
                and sha256 != "unavailable_large_file"
            )
            line_count = len(content_str.splitlines())
        except GatewayError:
            raise
        except (OSError, ValueError):
            raise GatewayError("file_read_failed") from None

        return self._reply(
            "workspace.file.read.result",
            {
                "epoch": self.epoch,
                "path": paths.relative(target),
                "content": content_str,
                "sha256": sha256,
                "size": size,
                "lineCount": line_count,
                "truncated": truncated,
                "isBinary": is_binary,
                "editable": editable,
            },
            session_id=command.session_id,
        )

    def _write_workspace_file(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"path", "content"}, optional={"expectedSha256"})
        assert self._workspace is not None
        raw_path = command.payload.get("path")
        content = command.payload.get("content")
        expected_sha = command.payload.get("expectedSha256")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise GatewayError("invalid_path")
        if not isinstance(content, str):
            raise GatewayError("invalid_content")
        if expected_sha is not None and (
            not isinstance(expected_sha, str)
            or re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha) is None
        ):
            raise GatewayError("invalid_digest")

        paths = WorkspacePaths(self._workspace)
        try:
            target = paths.resolve(raw_path.strip())
            content_bytes = content.encode("utf-8")
            if len(content_bytes) > _MAX_WORKSPACE_EDIT_BYTES:
                raise GatewayError("content_too_large")
            if target.exists():
                if expected_sha is None:
                    raise GatewayError("invalid_digest")
                if not target.is_file() or target.stat().st_size > _MAX_WORKSPACE_EDIT_BYTES:
                    raise GatewayError("file_not_editable")
                actual_bytes = target.read_bytes()
                try:
                    actual_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    raise GatewayError("binary_file_not_editable") from None
                if b"\x00" in actual_bytes:
                    raise GatewayError("binary_file_not_editable")
                actual_sha = sha256_bytes(actual_bytes)
                if expected_sha.lower() != actual_sha:
                    raise GatewayError("concurrent_modification")
            elif expected_sha is not None:
                raise GatewayError("concurrent_modification")

            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(paths, target, content_bytes, expected_sha)
            new_sha = sha256_bytes(content_bytes)
        except GatewayError:
            raise
        except ConcurrentModificationError:
            raise GatewayError("concurrent_modification") from None
        except ToolError:
            raise GatewayError("file_write_failed") from None
        except (OSError, ValueError):
            raise GatewayError("file_write_failed") from None

        return self._reply(
            "workspace.file.write.result",
            {
                "epoch": self.epoch,
                "path": paths.relative(target),
                "sha256": new_sha,
                "size": len(content_bytes),
            },
            session_id=command.session_id,
        )

    def _get_workspace_context(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, set())
        assert self._workspace is not None
        memory_items: list[dict[str, object]] = []
        try:
            memories = SQLiteEventStore.list_memories_read_only(
                self._database, str(self._workspace), limit=50
            )
            memory_items = [
                {
                    "id": item.id,
                    "type": "workspace_memory",
                    "summary": item.content[:500],
                    "createdAt": item.created_at,
                    "updatedAt": item.updated_at,
                }
                for item in memories
            ]
        except (OSError, sqlite3.Error, ValueError):
            raise GatewayError("storage_unavailable") from None

        caps = sorted(capability.value for capability in capabilities_for_mode(self._mode))
        manifest: dict[str, object] | None = None
        measured_usage: dict[str, object] | None = None
        context_session = command.session_id or self._selected_session_id
        if context_session:
            stored_session = self._stored_session(context_session)
            if (
                stored_session is None
                or Path(stored_session.workspace).resolve() != self._workspace
            ):
                raise GatewayError("invalid_session")
            requested, usage = SQLiteEventStore.latest_model_context_read_only(
                self._database, context_session
            )
            if requested is not None and isinstance(requested.data.get("context_manifest"), dict):
                manifest = dict(requested.data["context_manifest"])
                manifest.update(
                    requestId=requested.id,
                    createdAt=requested.created_at,
                    correlationId=requested.correlation_id,
                )
            if usage is not None:
                measured_usage = {
                    "inputTokens": usage.data.get("input_tokens"),
                    "outputTokens": usage.data.get("output_tokens"),
                    "cachedTokens": usage.data.get("cached_tokens"),
                    "estimated": usage.data.get("estimated", True),
                    "requestId": usage.causation_id,
                    "createdAt": usage.created_at,
                }
        budget = _context_budget_from_manifest(manifest, measured_usage)
        if budget is None:
            budget = {
                "available": False,
                "source": "provider_telemetry_unavailable",
            }
        instructions = [
            {
                "title": "Runtime Mode",
                "detail": f"Agent Workspace active mode: {self._mode.value}.",
            },
            {
                "title": "Autonomy Policy",
                "detail": (
                    f"Execution policy set to {self._autonomy.value} with "
                    "explicit user approval gates."
                ),
            },
        ]

        return self._reply(
            "workspace.context.get.result",
            {
                "epoch": self.epoch,
                "memory": memory_items,
                "manifest": manifest,
                "lastUsage": measured_usage,
                "skills": caps,
                "budget": budget,
                "instructions": instructions,
            },
            session_id=command.session_id,
        )

    def _run_doctor(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"workspace"})
        from agent_workspace.core.doctor import diagnose_environment
        from agent_workspace.tools.native_isolation import inspect_native_isolation

        with self._lock:
            ws = self._workspace
            database = self._database
            provider = self._provider
            epoch = self.epoch
        req_ws = command.payload.get("workspace")
        if isinstance(req_ws, str) and req_ws.strip():
            ws = Path(req_ws).expanduser().resolve()

        report = diagnose_environment(
            workspace=ws,
            db_path=database,
            provider_config=provider,
            isolation_probe=inspect_native_isolation,
        )

        return self._reply(
            "system.doctor.result",
            {
                "epoch": epoch,
                "timestamp": report.timestamp,
                "overallStatus": report.overall_status,
                "checks": [c.to_dict() for c in report.checks],
            },
            session_id=command.session_id,
        )

    def _list_jobs(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, set(), optional={"limit", "sessionScope", "activeOnly"})
        limit = command.payload.get("limit", 50)
        scope = command.payload.get("sessionScope", "selected")
        active_only = command.payload.get("activeOnly", False)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise GatewayError("invalid_limit")
        if scope not in {"selected", "workspace"} or type(active_only) is not bool:
            raise GatewayError("invalid_command")
        if command.session_id not in {None, self._selected_session_id}:
            raise GatewayError("invalid_session")
        session_id = None
        if scope == "selected":
            self._require_selected_session(command.session_id)
            session_id = command.session_id
        assert self._workspace is not None
        try:
            with SQLiteEventStore(self._database) as store:
                jobs = store.list_background_jobs(
                    str(self._workspace),
                    session_id=session_id,
                    limit=limit,
                    active_only=active_only,
                )
        except (OSError, ValueError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "jobs.list.result",
            {"epoch": self.epoch, "jobs": [self._job_document(job) for job in jobs]},
        )

    def _job_logs(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"jobId"}, optional={"maxBytes", "offset"})
        self._require_selected_session(command.session_id)
        job_id = command.payload.get("jobId")
        max_bytes = command.payload.get("maxBytes", 65_536)
        offset = command.payload.get("offset", 0)
        if not isinstance(job_id, str) or not job_id or len(job_id) > 128:
            raise GatewayError("invalid_job")
        if type(max_bytes) is not int or not 1 <= max_bytes <= _MAX_JOB_LOG_BYTES:
            raise GatewayError("invalid_job")
        if type(offset) is not int or offset < 0:
            raise GatewayError("invalid_offset")
        assert command.session_id is not None
        self._selected_job(command.session_id, job_id)
        host = self._require_host()
        try:
            future = host.request_job_logs(command.session_id, job_id, max_bytes, offset)
        except TypeError:
            if offset != 0:
                raise GatewayError("runtime_unavailable") from None
            future = host.request_job_logs(command.session_id, job_id, max_bytes)
        if future is None:
            raise GatewayError("runtime_unavailable")
        try:
            raw = future.result(timeout=_COMMAND_TIMEOUT_SECONDS)
        except Exception:
            raise GatewayError("runtime_unavailable") from None
        if not isinstance(raw, Mapping):
            raise GatewayError("runtime_unavailable")
        data = raw.get("data")
        if not isinstance(data, str):
            raise GatewayError("runtime_unavailable")
        encoded = data.encode("utf-8")
        wire_cap = min(max_bytes, _MAX_STRING_CHARS)
        if len(encoded) > wire_cap:
            data = encoded[:wire_cap].decode("utf-8", errors="ignore")
        raw_bytes = raw.get("bytes")
        raw_state = raw.get("state")
        if type(raw_bytes) is not int or not isinstance(raw_state, str):
            raise GatewayError("runtime_unavailable")
        return self._reply(
            "jobs.logs.result",
            {
                "epoch": self.epoch,
                "jobId": job_id,
                "state": raw_state,
                "data": data,
                "bytes": raw_bytes,
                "offset": raw.get("offset", offset),
                "nextOffset": raw.get("next_offset", raw.get("nextOffset", offset + len(encoded))),
                "eof": raw.get("eof") is True,
                "truncated": raw.get("truncated") is True or len(encoded) > wire_cap,
            },
            session_id=command.session_id,
        )

    def _stop_job(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"jobId"})
        self._require_selected_session(command.session_id)
        job_id = command.payload.get("jobId")
        if not isinstance(job_id, str) or not job_id or len(job_id) > 128:
            raise GatewayError("invalid_job")
        assert command.session_id is not None
        status = self._selected_job(command.session_id, job_id)
        if status.state in _TERMINAL_JOB_STATES:
            raise GatewayError("job_not_stoppable")
        future = self._require_host().request_job_stop(command.session_id, job_id)
        if future is None:
            raise GatewayError("runtime_unavailable")
        try:
            stopped = future.result(timeout=_COMMAND_TIMEOUT_SECONDS)
        except Exception:
            raise GatewayError("runtime_unavailable") from None
        return self._reply(
            "jobs.stop.result",
            {"epoch": self.epoch, "job": self._job_document(stopped)},
            session_id=command.session_id,
        )

    def _terminal_scope(self, command: CommandEnvelope) -> None:
        self._require_configured()
        if command.session_id not in {None, self._selected_session_id}:
            raise GatewayError("invalid_session")
        if command.session_id is not None:
            self._require_selected_session(command.session_id)

    def _terminal_result(
        self,
        command: CommandEnvelope,
        future: Future[object] | None,
        response_type: str,
    ) -> GatewayReply:
        if future is None:
            raise GatewayError("runtime_unavailable")
        try:
            raw = future.result(timeout=_COMMAND_TIMEOUT_SECONDS)
        except TerminalSessionError as error:
            raise GatewayError(error.code) from None
        except TimeoutError:
            raise GatewayError("runtime_timeout") from None
        except Exception:
            raise GatewayError("runtime_unavailable") from None
        if not isinstance(raw, Mapping):
            raise GatewayError("runtime_unavailable")
        terminal = _bounded_projection(raw)
        if not isinstance(terminal, Mapping):
            raise GatewayError("runtime_unavailable")
        return self._reply(
            response_type,
            {"epoch": self.epoch, "terminal": dict(terminal)},
            session_id=command.session_id,
        )

    def _terminal_start(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(
            command,
            {"argv"},
            optional={"cwd", "owner", "deadlineSeconds", "maxOutputBytes"},
        )
        raw_argv = command.payload.get("argv")
        cwd = command.payload.get("cwd", ".")
        owner = command.payload.get("owner")
        deadline = command.payload.get("deadlineSeconds")
        max_output = command.payload.get("maxOutputBytes", 512 * 1024)
        if (
            not isinstance(raw_argv, list)
            or not raw_argv
            or len(raw_argv) > 256
            or any(not isinstance(item, str) or not item for item in raw_argv)
        ):
            raise GatewayError("invalid_argv")
        if not isinstance(cwd, str) or len(cwd) > 32_767:
            raise GatewayError("invalid_cwd")
        if owner is not None and (not isinstance(owner, str) or not owner.strip()):
            raise GatewayError("invalid_owner")
        if deadline is not None and (
            isinstance(deadline, bool)
            or not isinstance(deadline, (int, float))
            or deadline <= 0
            or deadline > 86_400
        ):
            raise GatewayError("invalid_deadline")
        if type(max_output) is not int or not 1 <= max_output <= 8 * 1024 * 1024:
            raise GatewayError("invalid_output_limit")
        future = self._require_host().request_terminal_start(
            tuple(raw_argv),
            cwd=cwd,
            owner=owner.strip() if isinstance(owner, str) else None,
            deadline=float(deadline) if deadline is not None else None,
            max_output_bytes=max_output,
        )
        return self._terminal_result(command, future, "terminal.start.result")

    def _terminal_input(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(command, {"terminalId", "data"}, optional={"owner"})
        terminal_id = command.payload.get("terminalId")
        data = command.payload.get("data")
        owner = command.payload.get("owner")
        if not isinstance(terminal_id, str) or not terminal_id:
            raise GatewayError("invalid_terminal")
        if not isinstance(data, str) or "\x00" in data or len(data.encode()) > 256 * 1024:
            raise GatewayError("invalid_input")
        if owner is not None and not isinstance(owner, str):
            raise GatewayError("invalid_owner")
        future = self._require_host().request_terminal_input(
            terminal_id, data, owner=owner if isinstance(owner, str) else None
        )
        return self._terminal_result(command, future, "terminal.input.result")

    def _terminal_resize(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(command, {"terminalId", "columns", "rows"}, optional={"owner"})
        terminal_id = command.payload.get("terminalId")
        columns = command.payload.get("columns")
        rows = command.payload.get("rows")
        owner = command.payload.get("owner")
        if not isinstance(terminal_id, str) or not terminal_id:
            raise GatewayError("invalid_terminal")
        if type(columns) is not int or not 1 <= columns <= 1000:
            raise GatewayError("invalid_resize")
        if type(rows) is not int or not 1 <= rows <= 1000:
            raise GatewayError("invalid_resize")
        future = self._require_host().request_terminal_resize(
            terminal_id,
            columns,
            rows,
            owner=owner if isinstance(owner, str) else None,
        )
        return self._terminal_result(command, future, "terminal.resize.result")

    def _terminal_status(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(command, {"terminalId"})
        terminal_id = command.payload.get("terminalId")
        if not isinstance(terminal_id, str) or not terminal_id:
            raise GatewayError("invalid_terminal")
        future = self._require_host().request_terminal_status(terminal_id)
        return self._terminal_result(command, future, "terminal.status.result")

    def _terminal_list(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(command, set(), optional={"limit"})
        limit = command.payload.get("limit", 32)
        if type(limit) is not int or not 1 <= limit <= 32:
            raise GatewayError("invalid_limit")
        future = self._require_host().request_terminal_list(limit)
        if future is None:
            raise GatewayError("runtime_unavailable")
        try:
            raw = future.result(timeout=_COMMAND_TIMEOUT_SECONDS)
        except TimeoutError:
            raise GatewayError("runtime_timeout") from None
        except Exception:
            raise GatewayError("runtime_unavailable") from None
        if not isinstance(raw, (list, tuple)):
            raise GatewayError("runtime_unavailable")
        terminals = _bounded_projection(list(raw[:limit]))
        if not isinstance(terminals, list):
            raise GatewayError("runtime_unavailable")
        return self._reply(
            "terminal.list.result",
            {"epoch": self.epoch, "terminals": terminals},
            session_id=command.session_id,
        )

    def _terminal_replay(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(command, {"terminalId"}, optional={"offset", "maxBytes"})
        terminal_id = command.payload.get("terminalId")
        offset = command.payload.get("offset", 0)
        max_bytes = command.payload.get("maxBytes")
        if not isinstance(terminal_id, str) or not terminal_id:
            raise GatewayError("invalid_terminal")
        if type(offset) is not int or offset < 0:
            raise GatewayError("invalid_offset")
        if max_bytes is not None and (
            type(max_bytes) is not int or not 1 <= max_bytes <= 8 * 1024 * 1024
        ):
            raise GatewayError("invalid_output_limit")
        future = self._require_host().request_terminal_replay(
            terminal_id, offset=offset, max_bytes=max_bytes
        )
        return self._terminal_result(command, future, "terminal.replay.result")

    def _terminal_stop(self, command: CommandEnvelope) -> GatewayReply:
        self._terminal_scope(command)
        self._require_payload(command, {"terminalId"}, optional={"owner", "reason"})
        terminal_id = command.payload.get("terminalId")
        owner = command.payload.get("owner")
        reason = command.payload.get("reason", "stopped")
        if not isinstance(terminal_id, str) or not terminal_id:
            raise GatewayError("invalid_terminal")
        if owner is not None and not isinstance(owner, str):
            raise GatewayError("invalid_owner")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 256:
            raise GatewayError("invalid_reason")
        future = self._require_host().request_terminal_stop(
            terminal_id,
            owner=owner if isinstance(owner, str) else None,
            reason=reason.strip(),
        )
        return self._terminal_result(command, future, "terminal.stop.result")

    def _selected_job(self, session_id: str | None, job_id: str) -> BackgroundJobStatus:
        assert session_id is not None
        try:
            with SQLiteEventStore(self._database) as store:
                status = store.get_background_job(session_id, job_id)
        except (OSError, ValueError):
            raise GatewayError("storage_unavailable") from None
        if status is None:
            raise GatewayError("unknown_job")
        return status

    @staticmethod
    def _job_document(status: object) -> dict[str, object]:
        safe = _json_safe(status)
        if not isinstance(safe, Mapping):
            raise GatewayError("runtime_unavailable")
        return {
            "jobId": safe.get("job_id", safe.get("jobId")),
            "sessionId": safe.get("session_id", safe.get("sessionId")),
            "label": safe.get("label"),
            "state": safe.get("state"),
            "createdAt": safe.get("created_at", safe.get("createdAt")),
            "updatedAt": safe.get("updated_at", safe.get("updatedAt")),
            "terminalReason": safe.get("terminal_reason", safe.get("terminalReason")),
        }
