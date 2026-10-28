"""The open folder's reference library in the window: list it, search the scholarly databases and
Zotero, add works, and cite them in a LaTeX document (the entries go into its .bib file)."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

from agent_workspace.latex import compile as latex_compile
from agent_workspace.latex import project as latex_project
from agent_workspace.latex import rules as latex_rules
from agent_workspace.scholar import bibtex, sources, zotero
from agent_workspace.scholar.library import LibraryError, ReferenceLibrary
from agent_workspace.scholar.sources import SearchFilters
from agent_workspace.scholar.works import Work
from agent_workspace.tools.base import ToolError
from agent_workspace.tools.paths import WorkspacePaths
from agent_workspace.ui_gateway.gateway_common import GatewayError, GatewayReply
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import CommandEnvelope

REFERENCE_COMMANDS = frozenset(
    {
        "references.list",
        "references.search",
        "references.zotero",
        "references.add",
        "references.cite",
    }
)
_MAX_RESULTS = 25
_MAX_LISTED = 500
_BIBLIOGRAPHY = re.compile(r"^[^%\n]*\\bibliography\{([^}]+)\}", re.MULTILINE)
_BIBRESOURCE = re.compile(r"^[^%\n]*\\addbibresource(?:\[[^\]]*\])?\{([^}]+)\}", re.MULTILINE)


def _row(work: Work, identifier: str | None = None) -> dict[str, Any]:
    authors = [person.display() for person in work.authors[:3]]
    if len(work.authors) > 3:
        authors.append("…")
    row: dict[str, Any] = {
        "title": work.title,
        "authors": authors,
        "year": work.year,
        "venue": work.container,
        "doi": work.doi,
        "type": work.type,
    }
    if work.key:
        row["key"] = work.key
    if identifier:
        row["id"] = identifier
    if work.retracted:
        row["retracted"] = True
    return {name: value for name, value in row.items() if value not in ("", None, [])}


def bibliography_file(main: Path, text: str) -> tuple[Path, bool]:
    """The .bib file a document reads (the first one), and whether it names any at all."""
    for pattern in (_BIBLIOGRAPHY, _BIBRESOURCE):
        match = pattern.search(text)
        if match is not None:
            name = match.group(1).split(",")[0].strip()
            path = main.parent / name
            if path.suffix.lower() != ".bib":
                path = path.with_name(path.name + ".bib")
            return path, True
    return main.parent / "refs.bib", False


class ReferenceCommands(GatewayState):
    """The reference library's commands."""

    def _references_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        handler = {
            "references.list": self._references_list,
            "references.search": self._references_search,
            "references.zotero": self._references_zotero,
            "references.add": self._references_add,
            "references.cite": self._references_cite,
        }[command.type]
        return self._reply(f"{command.type}.result", handler(command), session_id=None)

    def _reference_paths(self) -> WorkspacePaths:
        with self._lock:
            workspace = self._workspace
        if workspace is None:
            raise GatewayError("runtime_unconfigured")
        return WorkspacePaths(workspace)

    def _references_list(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, set(), optional={"query"})
        query = command.payload.get("query", "")
        if not isinstance(query, str) or len(query) > 300:
            raise GatewayError("invalid_payload")
        library = ReferenceLibrary(self._reference_paths().root)
        try:
            works = library.search(query, limit=500) if query.strip() else library.works()[:500]
        except (OSError, LibraryError):
            raise GatewayError("storage_unavailable") from None
        return {"works": [_row(work) for work in works]}

    def _references_search(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, {"query"}, optional={"limit"})
        query, limit = command.payload["query"], command.payload.get("limit", 10)
        if not isinstance(query, str) or not query.strip() or len(query) > 300:
            raise GatewayError("invalid_payload")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= _MAX_RESULTS:
            raise GatewayError("invalid_payload")
        result = sources.search(query.strip(), sources.DEFAULT_SOURCES, limit, SearchFilters())
        self._research_tools.recent.remember(result.works)
        if not result.works and result.errors:
            raise GatewayError("references_offline")
        return {
            "works": [_row(work, self._research_tools.found.keep(work)) for work in result.works]
        }

    def _references_zotero(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, set(), optional={"collection"})
        collection = command.payload.get("collection")
        if collection is not None and not isinstance(collection, str):
            raise GatewayError("invalid_payload")
        try:
            works = zotero.items(collection)
            groups = zotero.collections() if collection is None else []
        except zotero.ZoteroUnavailable:
            raise GatewayError("zotero_unavailable") from None
        return {
            "works": [
                _row(work, self._research_tools.found.keep(work)) for work in works[:_MAX_LISTED]
            ],
            "collections": groups,
        }

    def _references_add(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, {"ids"})
        identifiers = command.payload["ids"]
        if (
            not isinstance(identifiers, list)
            or not 1 <= len(identifiers) <= 50
            or not all(isinstance(item, str) for item in identifiers)
        ):
            raise GatewayError("invalid_payload")
        works = [self._research_tools.found.get(identifier) for identifier in identifiers]
        if any(work is None for work in works):
            raise GatewayError("references_unknown")
        library = ReferenceLibrary(self._reference_paths().root)
        try:
            added, known = library.add(work for work in works if work is not None)
        except LibraryError:
            raise GatewayError("references_full") from None
        except OSError:
            raise GatewayError("storage_unavailable") from None
        return {"works": [_row(work) for work in [*added, *known]], "added": len(added)}

    def _references_cite(self, command: CommandEnvelope) -> dict[str, object]:
        """Put library works into the .bib file of the document a LaTeX file belongs to."""
        self._require_payload(command, {"path", "keys"})
        raw, keys = command.payload["path"], command.payload["keys"]
        if (
            not isinstance(raw, str)
            or not isinstance(keys, list)
            or not 1 <= len(keys) <= 50
            or not all(isinstance(key, str) and key for key in keys)
        ):
            raise GatewayError("invalid_payload")
        paths = self._reference_paths()
        try:
            file = paths.resolve(raw)
        except (OSError, ToolError, ValueError):
            raise GatewayError("invalid_path") from None
        if file.suffix.lower() != ".tex" or not file.is_file():
            raise GatewayError("unsupported_type")
        main = latex_compile.find_root(paths.root, file)
        text = latex_project.decode(main.read_bytes())
        target, named = bibliography_file(main, text)
        try:
            target = paths.resolve(target)
        except (OSError, ToolError, ValueError):
            raise GatewayError("invalid_path") from None
        works, missing = ReferenceLibrary(paths.root).find(keys)
        existing_text = latex_project.decode(target.read_bytes()) if target.is_file() else ""
        present = {record.key for record in latex_rules.parse_bib_records(existing_text)}
        added = [work for work in works if work.key not in present]
        if added:
            entries = "\n".join(bibtex.write_entry(work) for work in added)
            joined = existing_text.rstrip("\n")
            content = f"{joined}\n\n{entries}\n" if joined else f"{entries}\n"
            try:
                _write_text(target, content)
            except OSError:
                raise GatewayError("storage_unavailable") from None
        return {
            "bib": paths.relative(target),
            "added": [work.key for work in added],
            "present": [work.key for work in works if work.key in present],
            "missing": missing,
            "bibliographyNamed": named,
        }


def _write_text(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
