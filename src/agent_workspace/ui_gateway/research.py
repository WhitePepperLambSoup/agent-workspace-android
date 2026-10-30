"""The research and office tools each conversation gets for its folder (agent_workspace.scholar,
agent_workspace.latex and agent_workspace.office)."""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from pathlib import Path

from agent_workspace.application.ports import Tool
from agent_workspace.latex.tools import latex_tools
from agent_workspace.office.tools import SpeechSource, office_tools
from agent_workspace.scholar.labbook import LabNotebookAddTool, LabNotebookSearchTool
from agent_workspace.scholar.library import RecentWorks
from agent_workspace.scholar.literature_tools import literature_tools
from agent_workspace.scholar.papers import ReadPaperTool
from agent_workspace.scholar.works import Work
from agent_workspace.science.remote import remote_tools
from agent_workspace.storage.file_versions import FileVersions
from agent_workspace.tools.filesystem import WriteFileTool

_MAX_FOUND = 500


class FoundWorks:
    """Works the window was shown from a search or from Zotero, so it can add them by id."""

    def __init__(self) -> None:
        self._items: OrderedDict[str, Work] = OrderedDict()
        self._lock = threading.Lock()

    def keep(self, work: Work) -> str:
        identifier = hashlib.sha256(work.identity().encode("utf-8")).hexdigest()[:20]
        with self._lock:
            self._items[identifier] = work
            self._items.move_to_end(identifier)
            while len(self._items) > _MAX_FOUND:
                self._items.popitem(last=False)
        return identifier

    def get(self, identifier: str) -> Work | None:
        with self._lock:
            return self._items.get(identifier)


class ResearchTools:
    """Makes the research tools for a folder; works looked up lately are shared by all folders."""

    def __init__(self, database: Path, speech: SpeechSource | None = None) -> None:
        self.data_dir = database.parent
        self.versions = database.with_name("file-versions")
        self.recent = RecentWorks()
        self.found = FoundWorks()
        # The speech-to-text service meeting transcription uses (Settings → Voice).
        self.speech: SpeechSource = speech or (lambda: None)

    def __call__(self, workspace: Path) -> tuple[Tool, ...]:
        # Files these tools write are checkpointed and kept like write_file's, so the change list
        # under a turn shows them and can put them back.
        versions = FileVersions(self.versions)
        writer = WriteFileTool(workspace, versions)
        return (
            *literature_tools(workspace, data_dir=self.data_dir, writer=writer, recent=self.recent),
            *latex_tools(workspace, data_dir=self.data_dir),
            ReadPaperTool(workspace),
            LabNotebookAddTool(workspace, writer),
            LabNotebookSearchTool(workspace),
            *remote_tools(workspace),
            *office_tools(workspace, self.data_dir, versions, lambda: self.speech()),
        )


__all__ = ["FoundWorks", "ResearchTools"]
