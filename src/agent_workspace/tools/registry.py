from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from agent_workspace.application.ports import ContextualTool, EventStore, Tool
from agent_workspace.core.models import Mode, ToolSpec, capabilities_for_mode

from .background_jobs import (
    BackgroundJobLogsTool,
    BackgroundJobStatusTool,
    StartBackgroundJobTool,
    StopBackgroundJobTool,
)
from .base import ToolError, check_tool_schema
from .browser import BrowserTool
from .command import DiscoverExecutablesTool, PreviewProcessTool, RunProcessTool
from .document import ReadDocumentTool
from .download import DownloadFileTool
from .filesystem import ListFilesTool, ReadFileTool, WriteFileTool
from .git import GitBlameTool, GitCommitTool, GitDiffTool, GitLogTool, GitStatusTool
from .host_staged_sandbox import HostStagedSandboxBackend
from .http_request import HttpRequestTool
from .image import AttachImageTool
from .lsp import LspDiagnosticsTool
from .manage import DeletePathTool, MakeDirectoryTool, MovePathTool
from .memory import MemorySearchTool, MemoryWriteTool
from .patch import ApplyPatchTool
from .paths import StrPath, WorkspacePaths
from .pty import RunTerminalTool
from .research import (
    AddCitationTool,
    ListCitationsTool,
    ListResearchSourcesTool,
    ReadResearchSourceTool,
    SaveResearchSourceTool,
)
from .sandbox import (
    RunSandboxTool,
    SandboxBackend,
    SandboxStatusTool,
)
from .sandbox_changes import (
    ApplySandboxChangeTool,
    InspectSandboxChangeTool,
    ListSandboxChangesetsTool,
    ReviewSandboxChangeTool,
    SandboxChangeStatusTool,
)
from .search import SearchFilesTool
from .session_history import SessionHistoryTool
from .structured_data import QueryTableTool
from .todo import TodoTool
from .voice import SpeakTool, TranscribeTool
from .web import WebFetchTool
from .web_search import WebSearchTool

if TYPE_CHECKING:
    from agent_workspace.application.background_jobs import BackgroundJobManager


class ToolRegistry:
    def __init__(
        self,
        tools: Iterable[Tool] = (),
        *,
        sandbox_backend: SandboxBackend | None = None,
    ) -> None:
        self._tools: dict[str, Tool] = {}
        self.sandbox_backend = sandbox_backend
        for tool in tools:
            self.register(tool)

    @classmethod
    def for_workspace(
        cls,
        workspace: WorkspacePaths | StrPath,
        store: EventStore | None = None,
        *,
        sandbox_backend: SandboxBackend | None = None,
        allow_host_process: bool = True,
        background_jobs: BackgroundJobManager | None = None,
        custom_tools: Iterable[Tool] = (),
    ) -> ToolRegistry:
        paths = workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        if sandbox_backend is not None:
            backend_paths = getattr(sandbox_backend, "paths", None)
            if isinstance(backend_paths, WorkspacePaths) and backend_paths.root != paths.root:
                raise ValueError("sandbox backend workspace does not match the registry workspace")
            backend_id_value = getattr(sandbox_backend, "backend_id", "")
            if isinstance(backend_id_value, str) and backend_id_value.casefold() == "docker":
                raise ToolError("the legacy Docker sandbox backend is disabled")
        resolved_sandbox = sandbox_backend or HostStagedSandboxBackend(paths)
        tools: list[Tool] = [
            ListFilesTool(paths),
            ReadFileTool(paths),
            ReadDocumentTool(paths),
            QueryTableTool(paths),
            SearchFilesTool(paths),
            WriteFileTool(paths),
            ApplyPatchTool(paths),
            MakeDirectoryTool(paths),
            MovePathTool(paths),
            DeletePathTool(paths),
            AttachImageTool(paths),
            LspDiagnosticsTool(paths),
            SandboxStatusTool(resolved_sandbox),
            RunSandboxTool(paths, resolved_sandbox),
            GitStatusTool(paths),
            GitLogTool(paths),
            GitBlameTool(paths),
            GitDiffTool(paths),
            GitCommitTool(paths),
            WebFetchTool(),
            WebSearchTool(),
            DownloadFileTool(paths),
            HttpRequestTool(),
            BrowserTool(paths),
            RunTerminalTool(paths),
            SpeakTool(),
            TranscribeTool(paths),
        ]
        if allow_host_process:
            tools.extend(
                (
                    DiscoverExecutablesTool(),
                    RunProcessTool(paths),
                    PreviewProcessTool(paths),
                )
            )
        tools.extend(custom_tools)
        if store is not None:
            tools.extend(
                (
                    ApplySandboxChangeTool(paths, store),
                    ListSandboxChangesetsTool(paths, store),
                    InspectSandboxChangeTool(paths, store),
                    ReviewSandboxChangeTool(paths, store),
                    SandboxChangeStatusTool(paths, store),
                    TodoTool(store),
                    SaveResearchSourceTool(store),
                    ListResearchSourcesTool(store),
                    ReadResearchSourceTool(store),
                    AddCitationTool(store),
                    ListCitationsTool(store),
                    MemorySearchTool(store),
                    SessionHistoryTool(store, paths),
                    MemoryWriteTool(store),
                )
            )
        if background_jobs is not None and allow_host_process:
            tools.extend(
                (
                    StartBackgroundJobTool(background_jobs),
                    BackgroundJobStatusTool(background_jobs),
                    BackgroundJobLogsTool(background_jobs),
                    StopBackgroundJobTool(background_jobs),
                )
            )
        return cls(tools, sandbox_backend=resolved_sandbox)

    def register(self, tool: Tool) -> None:
        name = tool.spec.name
        if not name:
            raise ValueError("tool name may not be empty")
        if name in self._tools:
            raise ValueError(f"tool is already registered: {name}")
        if tool.spec.capability is None:
            raise ValueError(f"tool capability must be declared: {name}")
        if tool.spec.durable_preimage_checkpoint and not isinstance(tool, ContextualTool):
            raise ValueError(f"checkpointed tool must accept execution context: {name}")
        check_tool_schema(tool.spec)
        self._tools[name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc

    async def aclose(self) -> None:
        """Release processes owned by built-in browser tools in this registry."""
        errors: list[Exception] = []
        for tool in self._tools.values():
            if isinstance(tool, BrowserTool):
                try:
                    await tool.aclose()
                except Exception as error:
                    errors.append(error)
        if errors:
            raise ExceptionGroup("browser tool shutdown failed", errors)

    def specs(self, mode: Mode | None = None) -> tuple[ToolSpec, ...]:
        capabilities = capabilities_for_mode(mode) if mode is not None else None
        matching = [
            tool.spec
            for tool in self._tools.values()
            if capabilities is None or tool.spec.capability in capabilities
        ]
        # Deterministic lexicographic order keeps provider requests stable
        # across sessions (and friendly to provider-side caching).
        matching.sort(key=lambda spec: spec.name)
        return tuple(matching)
