"""knowledge_search / knowledge_add backed by the phone-wide knowledge base (mobile_knowledge).

The knowledge base holds the user's own documents, shared by every workspace and listed on the
Knowledge page. Searching is a plain read. Adding a workspace file copies its text into the
knowledge base, not into the workspace, so like memory it runs without an approval prompt (the
"session_state" effect); the user sees and can remove every document on the Knowledge page.
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


def _store():
    from mobile_knowledge import get_knowledge_store

    return get_knowledge_store()


def _require_enabled(store: Any) -> None:
    if not store.settings()["enabled"]:
        raise ToolError("the knowledge base is turned off on this phone")


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
        return await asyncio.to_thread(self._search, arguments)

    async def execute_with_context(self, arguments: dict[str, Any], _context: Any) -> str:
        return await self.execute(arguments)

    def _search(self, arguments: dict[str, Any]) -> str:
        store = _store()
        _require_enabled(store)
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise ToolArgumentError("'query' must be text of at most 500 characters")
        document = arguments.get("document")
        if document is not None and (not isinstance(document, str) or len(document) > 200):
            raise ToolArgumentError("'document' must be a document title or id")
        limit = optional_int(arguments, "limit", 5, minimum=1, maximum=10)
        results = store.search(query, limit=limit, document=document or None)
        documents = store.documents(ready_only=True)
        payload: dict[str, Any] = {
            "results": [store.public(result, excerpt=1200) for result in results]
        }
        if not results:
            titles = [item["title"] for item in documents[:30]]
            payload["note"] = (
                "No passage matched. The knowledge base is empty; the user can add documents on "
                "the Knowledge page."
                if not documents
                else "No passage matched. Try other key words, or answer that these documents do "
                "not cover it."
            )
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
            "properties": {"path": {"type": "string", "minLength": 1, "maxLength": 1024}},
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
        return await asyncio.to_thread(self._add, arguments)

    async def execute_with_context(self, arguments: dict[str, Any], _context: Any) -> str:
        return await self.execute(arguments)

    def _add(self, arguments: dict[str, Any]) -> str:
        from mobile_knowledge import KnowledgeError

        store = _store()
        _require_enabled(store)
        raw = arguments.get("path")
        if not isinstance(raw, str) or not raw.strip():
            raise ToolArgumentError("'path' must be a file in the workspace")
        path = self.paths.resolve(raw)
        relative = self.paths.relative(path)
        if is_sensitive_workspace_path(relative):
            raise ToolError("sensitive files (keys, credentials, .env) cannot be added")
        if not Path(path).is_file():
            raise ToolError(f"not a file: {relative}")
        try:
            document = store.add_file(
                path, Path(path).name, origin="workspace", origin_path=relative
            )
        except KnowledgeError as exc:
            raise ToolError(str(exc)) from None
        if document.get("duplicate"):
            return json_result(
                {"document": document["title"], "state": document["state"], "already_added": True}
            )
        document = store.wait(document["id"], _ADD_WAIT_SECONDS)
        if document["state"] == "failed":
            raise ToolError(f"could not add {relative}: {document['error']}")
        result: dict[str, Any] = {
            "document": document["title"],
            "document_id": document["id"],
            "state": document["state"],
        }
        if document["state"] == "ready":
            result.update(passages=document["passages"], pages=document["pages"])
            if document["warnings"]:
                result["warnings"] = document["warnings"]
        else:
            result["note"] = (
                "still being indexed; it can be searched once the Knowledge page shows it ready"
            )
        return json_result(result)


__all__ = ["KnowledgeAddTool", "KnowledgeSearchTool"]
