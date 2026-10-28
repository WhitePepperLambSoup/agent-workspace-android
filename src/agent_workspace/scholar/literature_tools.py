"""The agent's literature tools: search and look up works, keep the folder's reference library,
write it out as BibTeX, RIS or a formatted list, and check a reference list."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.scholar import bibtex, checks, imports, sources, styles, zotero
from agent_workspace.scholar.library import LibraryError, RecentWorks, ReferenceLibrary
from agent_workspace.scholar.sources import SearchFilters
from agent_workspace.scholar.works import Work, identifier_kind
from agent_workspace.tools.base import (
    ToolArgumentError,
    ToolError,
    json_result,
    validate_tool_arguments,
)
from agent_workspace.tools.filesystem import WriteFileTool
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

_STYLE_NAMES = sorted(styles.STYLES)
_IMPORT_SUFFIXES = {".bib", ".ris", ".enw", ".txt", ".json", ".nbib", ".csl"}
_MAX_IMPORT_BYTES = 20 * 1024 * 1024
_WATCH_SEEN = 5000


class WatchBook:
    """What each literature watch has already reported, so a scheduled search shows only news."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def unseen(self, name: str, works: list[Work]) -> list[Work]:
        with self._lock:
            try:
                document = json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, ValueError, OSError):
                document = {}
            stored = document.get("watches") if isinstance(document, dict) else None
            watches: dict[str, Any] = stored if isinstance(stored, dict) else {}
            entry = watches.get(name)
            earlier = entry.get("seen") if isinstance(entry, dict) else None
            earlier = earlier if isinstance(earlier, list) else []
            seen = [item for item in earlier if isinstance(item, str)]
            known = set(seen)
            fresh = [work for work in works if work.identity() not in known]
            seen.extend(work.identity() for work in fresh)
            watches[name] = {
                "seen": seen[-_WATCH_SEEN:],
                "updated": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "first_run": not known,
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix=".watches-", dir=self.path.parent)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump({"version": 1, "watches": watches}, stream, ensure_ascii=False)
                os.replace(temporary, self.path)
            except BaseException:
                Path(temporary).unlink(missing_ok=True)
                raise
            return fresh


class PaperSearchTool:
    hard_cancellable = True

    def __init__(self, recent: RecentWorks, watches: WatchBook) -> None:
        self.recent = recent
        self.watches = watches
        self._spec = ToolSpec(
            name="paper_search",
            description=(
                "Search scholarly databases for papers, books and theses: OpenAlex (all fields), "
                "arXiv (preprints), PubMed (biomedicine), Crossref (DOI registry) and Semantic "
                "Scholar. Returns titles, authors, year, venue, DOI, citation counts, abstracts "
                "and open-access PDF links. Use English key words for international literature. "
                "sort=cited finds the classic papers of a topic, sort=newest the latest. With "
                "watch, only works this watch has not reported before come back (for scheduled "
                "literature updates). Add works you will cite to the folder's library with "
                "reference_library. Queries are network egress: ASK/WORKSPACE require approval."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 300},
                    "sources": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(sources.SOURCES)},
                        "minItems": 1,
                        "maxItems": 5,
                        "description": "Default: openalex and arxiv",
                    },
                    "year_from": {"type": "integer", "minimum": 1800, "maximum": 2100},
                    "year_to": {"type": "integer", "minimum": 1800, "maximum": 2100},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8},
                    "sort": {"type": "string", "enum": ["relevance", "cited", "newest"]},
                    "open_access": {"type": "boolean", "description": "Only works with a free PDF"},
                    "watch": {
                        "type": "string",
                        "pattern": r"^[\w\- .]{1,60}$",
                        "description": "A name for a recurring search; returns only new works",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            side_effect="network",
            capability=Capability.NETWORK_READ,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self.spec, arguments)
        query = str(arguments["query"]).strip()
        if not query:
            raise ToolArgumentError("query must not be empty")
        filters = SearchFilters(
            year_from=arguments.get("year_from"),
            year_to=arguments.get("year_to"),
            open_access=arguments.get("open_access", False),
            sort=arguments.get("sort", "relevance"),
        )
        limit = arguments.get("limit", 8)
        chosen = arguments.get("sources") or list(sources.DEFAULT_SOURCES)
        result = await asyncio.to_thread(sources.search, query, chosen, limit, filters)
        if not result.works and result.errors and len(result.errors) == len(set(chosen)):
            raise ToolError(
                "no database could be reached: "
                + "; ".join(f"{k}: {v}" for k, v in result.errors.items())
            )
        works = result.works
        self.recent.remember(works)
        payload: dict[str, Any] = {"query": query, "sources": chosen}
        watch = arguments.get("watch")
        if watch:
            works = await asyncio.to_thread(self.watches.unseen, watch, works)
            payload["watch"] = watch
            payload["new"] = len(works)
        payload["results"] = [work.summary() for work in works]
        if result.errors:
            payload["errors"] = result.errors
        if not works:
            payload["note"] = (
                "No new works since this watch last ran."
                if watch
                else "No works matched; try other key words or sources."
            )
        return json_result(payload)


class PaperLookupTool:
    hard_cancellable = True

    def __init__(self, recent: RecentWorks) -> None:
        self.recent = recent
        self._spec = ToolSpec(
            name="paper_lookup",
            description=(
                "Look works up by DOI, arXiv id, PMID, or by a citation or title, and return their "
                "full records (authors, venue, volume, pages, abstract, retraction status, "
                "open-access PDF). Use it before citing a work you know only by name, and to "
                "complete a reference. Network egress: ASK/WORKSPACE require approval."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "identifiers": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 3, "maxLength": 500},
                        "minItems": 1,
                        "maxItems": 20,
                    }
                },
                "required": ["identifiers"],
                "additionalProperties": False,
            },
            side_effect="network",
            capability=Capability.NETWORK_READ,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def execution_timeout_seconds(self, arguments: dict[str, Any]) -> float:
        identifiers = arguments.get("identifiers")
        return 30.0 + 8.0 * (len(identifiers) if isinstance(identifiers, list) else 1)

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self.spec, arguments)

        def one(reference: str) -> dict[str, Any]:
            kind, value = identifier_kind(reference)
            try:
                work = sources.lookup(kind, value)
            except ToolError as exc:
                return {"reference": reference, "error": str(exc)[:300]}
            if work is None:
                return {"reference": reference, "found": None}
            self.recent.remember([work])
            return {"reference": reference, "found": work.summary(abstract_chars=2000)}

        results = await asyncio.gather(
            *(asyncio.to_thread(one, reference) for reference in arguments["identifiers"])
        )
        return json_result({"results": list(results)})


class ReferenceLibraryTool:
    """The folder's reference library. It reads and writes .agent/references.json only."""

    def __init__(self, workspace: Path, recent: RecentWorks) -> None:
        self.paths = WorkspacePaths(workspace)
        self.library = ReferenceLibrary(self.paths.root)
        self.recent = recent
        self._spec = ToolSpec(
            name="reference_library",
            description=(
                "The reference library of the open folder (the works this project cites). "
                "list: works by key (filter with query). add: works by DOI, arXiv id or PMID "
                "that paper_search or paper_lookup returned, or BibTeX text. import: a .bib, "
                ".ris, EndNote, RefWorks, NoteExpress or CSL-JSON file in the folder (what CNKI, "
                "Wanfang, Web of Science and Zotero export), or zotero=true for the user's Zotero "
                "(collection optional). remove: by keys. update: fix fields of one work. format: "
                "the reference list and in-text citation of keys (in citation order) in a style: "
                + ", ".join(f"{key} ({name})" for key, name in styles.STYLES.items())
                + ". To write the list or a .bib file, use export_references."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "add", "import", "remove", "update", "format"],
                    },
                    "query": {"type": "string", "maxLength": 200},
                    "references": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1, "maxLength": 300},
                        "maxItems": 200,
                        "description": "DOIs, arXiv ids, PMIDs or keys",
                    },
                    "bibtex": {"type": "string", "maxLength": 200000},
                    "path": {"type": "string", "maxLength": 1024},
                    "zotero": {"type": "boolean"},
                    "collection": {"type": "string", "maxLength": 200},
                    "keys": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 120},
                        "maxItems": 500,
                    },
                    "key": {"type": "string", "maxLength": 120},
                    "fields": {"type": "object"},
                    "style": {"type": "string", "enum": _STYLE_NAMES},
                    "markdown": {"type": "boolean"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                },
                "required": ["action"],
                "additionalProperties": False,
            },
            side_effect="session_state",
            capability=Capability.WORKSPACE_READ,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def execution_timeout_seconds(self, arguments: dict[str, Any]) -> float:
        return 300.0 if arguments.get("zotero") else 60.0

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self.spec, arguments)
        try:
            return await asyncio.to_thread(self._run, arguments)
        except LibraryError as exc:
            raise ToolError(str(exc)) from None

    def _run(self, arguments: dict[str, Any]) -> str:
        action = arguments["action"]
        if action == "list":
            query = str(arguments.get("query") or "").strip()
            works = (
                self.library.search(query, arguments.get("limit", 200))
                if query
                else self.library.works()
            )
            total = len(self.library.works()) if query else len(works)
            shown = works[: arguments.get("limit", 200)]
            return json_result(
                {
                    "total": total,
                    "works": [_brief(work) for work in shown],
                    **(
                        {
                            "note": "The library is empty. Add works found with paper_search, "
                            "or import a file."
                        }
                        if not total
                        else {}
                    ),
                }
            )
        if action == "add":
            incoming: list[Work] = []
            missing: list[str] = []
            for reference in arguments.get("references") or []:
                work = self.recent.get(reference)
                if work is None:
                    missing.append(reference)
                else:
                    incoming.append(work)
            if arguments.get("bibtex"):
                try:
                    incoming.extend(bibtex.parse(arguments["bibtex"]))
                except bibtex.BibtexError as exc:
                    raise ToolArgumentError(f"the BibTeX could not be read: {exc}") from None
            if not incoming and not missing:
                raise ToolArgumentError("add needs references or bibtex")
            added, known = self.library.add(incoming)
            payload: dict[str, Any] = {
                "added": [_brief(work) for work in added],
                "already_there": [work.key for work in known],
            }
            if missing:
                payload["not_looked_up"] = missing
                payload["note"] = "Look these up with paper_lookup first, then add them."
            return json_result(payload)
        if action == "import":
            if arguments.get("zotero"):
                try:
                    works = zotero.items(arguments.get("collection") or None)
                except zotero.ZoteroUnavailable as exc:
                    raise ToolError(str(exc)) from None
                kind = "zotero"
            else:
                raw_path = arguments.get("path")
                if not isinstance(raw_path, str) or not raw_path.strip():
                    raise ToolArgumentError("import needs path or zotero=true")
                path = self._file(raw_path)
                text = path.read_bytes()[: _MAX_IMPORT_BYTES + 1]
                if len(text) > _MAX_IMPORT_BYTES:
                    raise ToolArgumentError("the file is larger than 20 MB")
                try:
                    kind, works = imports.parse_any(_decode(text))
                except (imports.ImportError_, bibtex.BibtexError) as exc:
                    raise ToolError(str(exc)) from None
            added, known = self.library.add(works)
            return json_result(
                {
                    "format": kind,
                    "read": len(works),
                    "added": len(added),
                    "already_there": len(known),
                    "keys": [work.key for work in added][:200],
                }
            )
        if action == "remove":
            keys = arguments.get("keys") or arguments.get("references") or []
            if not keys:
                raise ToolArgumentError("remove needs keys")
            return json_result({"removed": self.library.remove(keys)})
        if action == "update":
            key, fields = arguments.get("key"), arguments.get("fields")
            if not isinstance(key, str) or not isinstance(fields, dict) or not fields:
                raise ToolArgumentError("update needs key and fields")
            return json_result(
                {"updated": self.library.update(key, fields).summary(abstract_chars=0)}
            )
        style = arguments.get("style", "gb7714-numeric")
        keys = arguments.get("keys")
        works, missing = self.library.find(keys) if keys else (self.library.works(), [])
        if not works:
            raise ToolError(
                "none of these keys are in the library" if keys else "the library is empty"
            )
        lines = styles.bibliography(works, style, markdown=arguments.get("markdown", False))
        numbers = list(range(1, len(works) + 1))
        return json_result(
            {
                "style": styles.STYLES[style],
                "citation": styles.citation(works, style, numbers),
                "references": lines,
                **({"missing": missing} if missing else {}),
            }
        )

    def _file(self, raw_path: str) -> Path:
        try:
            path = self.paths.resolve(raw_path.strip())
        except WorkspacePathError as exc:
            raise ToolArgumentError(str(exc)) from None
        if path.suffix.casefold() not in _IMPORT_SUFFIXES:
            raise ToolArgumentError("import reads .bib, .ris, .enw, .txt, .json or .nbib files")
        if not path.is_file():
            raise ToolArgumentError(f"no such file: {raw_path}")
        return path


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _brief(work: Work) -> dict[str, Any]:
    names = [person.display() for person in work.authors[:3]]
    if len(work.authors) > 3:
        names.append("et al.")
    brief: dict[str, Any] = {
        "key": work.key,
        "title": work.title,
        "authors": names,
        "year": work.year,
    }
    for name, value in (("venue", work.container), ("doi", work.doi), ("arxiv", work.arxiv)):
        if value:
            brief[name] = value
    if work.retracted:
        brief["retracted"] = True
    return brief


class ExportReferencesTool:
    """Writes the library (or some works) to one file, through the checkpointed file writer."""

    def __init__(self, workspace: Path, writer: WriteFileTool) -> None:
        self.paths = WorkspacePaths(workspace)
        self.library = ReferenceLibrary(self.paths.root)
        self.writer = writer
        self._spec = ToolSpec(
            name="export_references",
            description=(
                "Write the folder's reference library, or the works with the given keys (in that "
                "order), to a file: bibtex (.bib for LaTeX), ris (for EndNote, NoteExpress, "
                "Mendeley), csl-json (for Pandoc and Zotero), or list (a numbered or author-year "
                "reference list in a style, as text or Markdown)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1, "maxLength": 1024},
                    "format": {"type": "string", "enum": ["bibtex", "ris", "csl-json", "list"]},
                    "keys": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 120},
                        "maxItems": 2000,
                    },
                    "style": {"type": "string", "enum": _STYLE_NAMES},
                    "markdown": {"type": "boolean"},
                },
                "required": ["path", "format"],
                "additionalProperties": False,
            },
            side_effect="write",
            capability=Capability.WORKSPACE_WRITE,
            durable_preimage_checkpoint=True,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any]) -> str:
        raise ToolError("export_references requires the current session context")

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        validate_tool_arguments(self.spec, arguments)
        keys = arguments.get("keys")
        try:
            works, missing = (
                await asyncio.to_thread(self.library.find, keys)
                if keys
                else (await asyncio.to_thread(self.library.works), [])
            )
        except LibraryError as exc:
            raise ToolError(str(exc)) from None
        if not works:
            raise ToolError("nothing to write: the library has none of these works")
        kind = arguments["format"]
        if kind == "bibtex":
            content = bibtex.write(works)
        elif kind == "ris":
            content = imports.write_ris(works)
        elif kind == "csl-json":
            content = (
                json.dumps([work.to_csl() for work in works], ensure_ascii=False, indent=2) + "\n"
            )
        else:
            style = arguments.get("style", "gb7714-numeric")
            content = (
                "\n".join(
                    styles.bibliography(works, style, markdown=arguments.get("markdown", False))
                )
                + "\n"
            )
        result = await write_checkpointed(
            self.writer, self.paths, arguments["path"], content, context
        )
        return json_result(
            {
                **result,
                "format": kind,
                "works": len(works),
                **({"missing": missing} if missing else {}),
            }
        )


async def write_checkpointed(
    writer: WriteFileTool,
    paths: WorkspacePaths,
    raw_path: str,
    content: str,
    context: ToolExecutionContext,
) -> dict[str, Any]:
    """Write one workspace file through write_file, so it is checkpointed, listed and undoable."""
    try:
        target = paths.resolve(raw_path)
    except WorkspacePathError as exc:
        raise ToolArgumentError(str(exc)) from None
    expected = None
    if target.is_file():
        expected = hashlib.sha256(await asyncio.to_thread(target.read_bytes)).hexdigest()
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
    result = json.loads(
        await writer.execute_with_context(
            {"path": paths.relative(target), "content": content, "expected_sha256": expected},
            context,
        )
    )
    return {"path": result.get("path"), "bytes": result.get("bytes_written")}


class CheckReferencesTool:
    hard_cancellable = True

    def __init__(self, workspace: Path) -> None:
        self.paths = WorkspacePaths(workspace)
        self._spec = ToolSpec(
            name="check_references",
            description=(
                "Check a reference list against Crossref, OpenAlex, arXiv and PubMed: each "
                "reference is looked up by DOI or text and compared (title, first author, year), "
                "and retracted papers are flagged. Statuses: verified, mismatch (wrong DOI, title, "
                "author or year), not_found (no database knows it: mistyped or made up), "
                "retracted, unverifiable (Chinese works the open databases do not cover). Give a "
                "manuscript (.tex, .md, .txt, .docx), a .bib file, or the list as text. Network "
                "egress: ASK/WORKSPACE require approval."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "maxLength": 1024},
                    "text": {"type": "string", "maxLength": 200000},
                    "limit": {"type": "integer", "minimum": 1, "maximum": checks.MAX_REFERENCES},
                },
                "additionalProperties": False,
            },
            side_effect="network",
            capability=Capability.NETWORK_READ,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def execution_timeout_seconds(self, arguments: dict[str, Any]) -> float:
        return 60.0 + 4.0 * float(arguments.get("limit", 60))

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self.spec, arguments)
        return await asyncio.to_thread(self._run, arguments)

    def _run(self, arguments: dict[str, Any]) -> str:
        limit = arguments.get("limit", 60)
        if arguments.get("path"):
            try:
                path = self.paths.resolve(arguments["path"])
            except WorkspacePathError as exc:
                raise ToolArgumentError(str(exc)) from None
            if not path.is_file():
                raise ToolArgumentError(f"no such file: {arguments['path']}")
            if path.suffix.casefold() == ".docx":
                from agent_workspace.tools.document import _docx_text

                text, _ = _docx_text(path, 2 * 1024 * 1024)
            else:
                text = _decode(path.read_bytes()[: 8 * 1024 * 1024])
            references = checks.references_from_file(path, text)
        elif arguments.get("text"):
            references = checks.references_from_text(arguments["text"])
        else:
            raise ToolArgumentError("give path or text")
        if not references:
            raise ToolError("no reference list was found; give the list as text")
        report = checks.check(references[:limit])
        if len(references) > limit:
            report["not_checked"] = len(references) - limit
        return json_result(report)


def literature_tools(
    workspace: Path, *, data_dir: Path, writer: WriteFileTool, recent: RecentWorks
) -> tuple[Any, ...]:
    watches = WatchBook(data_dir / "scholar" / "watches.json")
    return (
        PaperSearchTool(recent, watches),
        PaperLookupTool(recent),
        ReferenceLibraryTool(workspace, recent),
        ExportReferencesTool(workspace, writer),
        CheckReferencesTool(workspace),
    )


__all__ = [
    "CheckReferencesTool",
    "ExportReferencesTool",
    "PaperLookupTool",
    "PaperSearchTool",
    "ReferenceLibraryTool",
    "WatchBook",
    "literature_tools",
    "write_checkpointed",
]
