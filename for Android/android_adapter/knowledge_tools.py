"""knowledge_search / knowledge_add / knowledge_use backed by the phone-wide knowledge base
(mobile_knowledge).

The knowledge base holds the user's own documents, shared by every workspace and listed on the
Knowledge page. Documents are grouped into knowledge bases; each conversation uses the ones
chosen for it (in the composer, or by asking: knowledge_use). Searching is a plain read. Adding a
workspace file copies its text into the knowledge base, not into the workspace, so like memory
it runs without an approval prompt (the "session_state" effect); the user sees and can remove
every document on the Knowledge page. Choosing knowledge bases changes only this conversation.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result, optional_int
from agent_workspace.tools.paths import StrPath, WorkspacePaths, is_sensitive_workspace_path

# How long knowledge_add waits for a document to be indexed before reporting it as in progress.
_ADD_WAIT_SECONDS = 90
_NAMES_SCHEMA = {
    "type": "array",
    "items": {"type": "string", "minLength": 1, "maxLength": 60},
    "maxItems": 10,
}


def _store():
    from mobile_knowledge import get_knowledge_store

    return get_knowledge_store()


def _require_enabled(store: Any) -> None:
    if not store.settings()["enabled"]:
        raise ToolError("the knowledge base is turned off on this phone")


def _session_id(context: Any) -> str | None:
    session_id = getattr(context, "session_id", None)
    return session_id if isinstance(session_id, str) and session_id else None


def _names(arguments: dict[str, Any], key: str) -> list[str] | None:
    value = arguments.get(key)
    if value is None:
        return None
    if (
        not isinstance(value, list)
        or len(value) > 20
        or not all(isinstance(item, str) and item.strip() and len(item) <= 60 for item in value)
    ):
        raise ToolArgumentError(f"'{key}' must be a list of knowledge base names")
    return value


def _resolve(store: Any, names: list[str], *, create: bool = False) -> list[dict[str, Any]]:
    from mobile_knowledge import KnowledgeError

    try:
        return store.resolve_collections(names, create=create)
    except KnowledgeError as exc:
        raise ToolError(str(exc)) from None


class KnowledgeSearchTool:
    _SPEC = ToolSpec(
        name="knowledge_search",
        description=(
            "Search the user's knowledge base on this phone (documents they added on the "
            "Knowledge page) and return matching passages with their document and page. Use "
            "key words from the documents rather than a whole question; try other words if "
            "nothing matches. Cite the document (and page, when given) you use."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 500},
                "document": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Only search this document (its title or id)",
                },
                "knowledge_bases": {
                    **_NAMES_SCHEMA,
                    "description": "Search these knowledge bases (names) instead of the ones "
                    "this conversation uses",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await asyncio.to_thread(self._search, arguments, None)

    async def execute_with_context(self, arguments: dict[str, Any], context: Any) -> str:
        return await asyncio.to_thread(self._search, arguments, _session_id(context))

    def _search(self, arguments: dict[str, Any], session_id: str | None) -> str:
        store = _store()
        _require_enabled(store)
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise ToolArgumentError("'query' must be text of at most 500 characters")
        document = arguments.get("document")
        if document is not None and (not isinstance(document, str) or len(document) > 200):
            raise ToolArgumentError("'document' must be a document title or id")
        limit = optional_int(arguments, "limit", 5, minimum=1, maximum=10)
        names = _names(arguments, "knowledge_bases")
        known = store.collections()
        if names is not None:
            searched = _resolve(store, names)
        else:
            selected = store.selected_collections(session_id)
            searched = [item for item in known if item["id"] in selected]
        ids = [item["id"] for item in searched]
        payload: dict[str, Any] = {}
        if len(known) > 1 or not searched:
            payload["knowledge_bases"] = [item["label"] for item in searched]
        if not searched:
            payload["results"] = []
            payload["note"] = (
                "This conversation uses no knowledge base. Search one the user names with "
                "knowledge_bases, or ask which one to use. Knowledge bases: "
                + ", ".join(item["label"] for item in known)
            )
            return json_result(payload)
        results = store.search(query, limit=limit, document=document or None, collections=ids)
        payload["results"] = [store.public(result, excerpt=1200) for result in results]
        if not results:
            documents = [
                item
                for item in store.documents(ready_only=True)
                if item["collection_id"] in ids
            ]
            payload["note"] = (
                (
                    "No passage matched. The knowledge base is empty; the user can add documents "
                    "on the Knowledge page."
                    if len(known) == 1
                    else "No passage matched. These knowledge bases have no documents yet."
                )
                if not documents
                else "No passage matched. Try other key words, or answer that these documents do "
                "not cover it."
            )
            others = [item["label"] for item in known if item["id"] not in ids and item["ready"]]
            if others and names is None:
                payload["note"] += (
                    " The user chose not to use these knowledge bases in this conversation: "
                    + ", ".join(others)
                    + ". Do not search them unless the user asks; you may say the answer might "
                    "be there."
                )
            titles = [item["title"] for item in documents[:30]]
            if titles:
                payload["documents"] = titles
        return json_result(payload)


class KnowledgeAddTool:
    hard_cancellable = False
    _SPEC = ToolSpec(
        name="knowledge_add",
        description=(
            "Add a document from the workspace (PDF, DOCX, XLSX, EPUB, HTML, Markdown or text) "
            "to the user's knowledge base on this phone, so later conversations can search it. "
            "Use it only when the user asks to add, save or index a document for later."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1, "maxLength": 1024},
                "knowledge_base": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 60,
                    "description": "The knowledge base to add it to (a new name creates one); "
                    "by default the one this conversation uses",
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        # Copies text into the phone-wide store, never into the workspace; the user reviews
        # and removes documents on the Knowledge page, as with memory.
        side_effect="session_state",
        capability=Capability.MEMORY_WRITE,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await asyncio.to_thread(self._add, arguments, None)

    async def execute_with_context(self, arguments: dict[str, Any], context: Any) -> str:
        return await asyncio.to_thread(self._add, arguments, _session_id(context))

    def _add(self, arguments: dict[str, Any], session_id: str | None) -> str:
        from mobile_knowledge import DEFAULT_COLLECTION, KnowledgeError

        store = _store()
        _require_enabled(store)
        raw = arguments.get("path")
        if not isinstance(raw, str) or not raw.strip():
            raise ToolArgumentError("'path' must be a file in the workspace")
        name = arguments.get("knowledge_base")
        if name is not None and (not isinstance(name, str) or not name.strip() or len(name) > 60):
            raise ToolArgumentError("'knowledge_base' must be a knowledge base name")
        path = self.paths.resolve(raw)
        relative = self.paths.relative(path)
        if is_sensitive_workspace_path(relative):
            raise ToolError("sensitive files (keys, credentials, .env) cannot be added")
        if not Path(path).is_file():
            raise ToolError(f"not a file: {relative}")
        created = False
        if name is not None:
            target = _resolve(store, [name], create=True)[0]
            created = bool(target.get("created"))
        else:
            # A conversation that uses a single knowledge base adds to that one.
            selected = store.selected_collections(session_id)
            target_id = selected[0] if len(selected) == 1 else DEFAULT_COLLECTION
            target = next(item for item in store.collections() if item["id"] == target_id)
        labels = {item["id"]: item["label"] for item in store.collections()}
        several = len(labels) > 1
        try:
            document = store.add_file(
                path,
                Path(path).name,
                origin="workspace",
                origin_path=relative,
                collection_id=target["id"],
            )
        except KnowledgeError as exc:
            raise ToolError(str(exc)) from None
        if document.get("duplicate"):
            result = {"document": document["title"], "state": document["state"],
                      "already_added": True}  # fmt: skip
            if several:
                result["knowledge_base"] = labels.get(document["collection_id"], "")
            return json_result(result)
        document = store.wait(document["id"], _ADD_WAIT_SECONDS)
        if document["state"] == "failed":
            raise ToolError(f"could not add {relative}: {document['error']}")
        result: dict[str, Any] = {
            "document": document["title"],
            "document_id": document["id"],
            "state": document["state"],
        }
        if several:
            result["knowledge_base"] = target["label"]
        if created:
            result["created_knowledge_base"] = True
        if document["state"] == "ready":
            result.update(passages=document["passages"], pages=document["pages"])
            if document["warnings"]:
                result["warnings"] = document["warnings"]
        else:
            result["note"] = (
                "still being indexed; it can be searched once the Knowledge page shows it ready"
            )
        return json_result(result)


class KnowledgeUseTool:
    _SPEC = ToolSpec(
        name="knowledge_use",
        description=(
            "Choose which of the user's knowledge bases this conversation uses (for knowledge "
            "search and the passages attached to requests). Use it when the user asks to use, "
            "switch to or stop using knowledge bases here. Pass every knowledge base to use from "
            "now on; [] to use none."
        ),
        input_schema={
            "type": "object",
            "properties": {"knowledge_bases": {**_NAMES_SCHEMA, "maxItems": 20}},
            "required": ["knowledge_bases"],
            "additionalProperties": False,
        },
        # Changes only which documents this conversation looks at; the user sees the choice in
        # the composer and changes it there.
        side_effect="session_state",
        capability=Capability.MEMORY_WRITE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        raise ToolError("knowledge_use needs a conversation")

    async def execute_with_context(self, arguments: dict[str, Any], context: Any) -> str:
        return await asyncio.to_thread(self._use, arguments, _session_id(context))

    def _use(self, arguments: dict[str, Any], session_id: str | None) -> str:
        from mobile_knowledge import KnowledgeError

        if session_id is None:
            raise ToolError("knowledge_use needs a conversation")
        store = _store()
        _require_enabled(store)
        names = _names(arguments, "knowledge_bases")
        if names is None:
            raise ToolArgumentError("'knowledge_bases' must be a list of knowledge base names")
        chosen = _resolve(store, names)
        try:
            selection = store.set_session_selection(session_id, [item["id"] for item in chosen])
        except KnowledgeError as exc:
            raise ToolError(str(exc)) from None
        used = set(selection["collections"])
        return json_result(
            {
                "knowledge_bases": [
                    item["label"] for item in selection["available"] if item["id"] in used
                ],
                "not_used": [
                    item["label"] for item in selection["available"] if item["id"] not in used
                ],
            }
        )


__all__ = ["KnowledgeAddTool", "KnowledgeSearchTool", "KnowledgeUseTool"]
