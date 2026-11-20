"""What the desktop gateway keeps for coding: the language servers of every open folder, which
folders' checks the user accepted, the latest check results, the user's terminals, and the tools
and hooks it gives each folder's conversations."""

from __future__ import annotations

import os
import shutil
import threading
import time
from collections.abc import Callable
from pathlib import Path

from agent_workspace.application.ports import Tool, ToolHooks

from .check_tools import RunChecksTool
from .code_tools import code_tools
from .debugger import DebugDesk, DebugPythonTool
from .hooks import CodingHooks
from .lsp_pool import LspPool
from .page_check import CheckPageTool
from .project import CheckResult, ProjectState, TrustBook
from .shell import ReadTerminalTool, ShellDesk
from .wsl import RunWslTool


class CodingDesk:
    def __init__(
        self,
        tools_dir: Path,
        trust_path: Path,
        *,
        pool: LspPool | None = None,
        shells: ShellDesk | None = None,
    ) -> None:
        self.tools_dir = tools_dir
        self.trust = TrustBook(trust_path)
        self.lsp = pool or LspPool(tools_dir, runs_folder_code=self.trust.accepted)
        self.shells = shells or ShellDesk()
        self.debug = DebugDesk(tools_dir)
        self._states: dict[str, ProjectState] = {}
        self._lock = threading.Lock()
        # Told when a folder's check results change (the gateway sends them to the window).
        self.on_results: Callable[[Path, ProjectState], None] | None = None

    @staticmethod
    def _key(root: Path) -> str:
        return os.path.normcase(str(root.resolve()))

    def state(self, root: Path) -> ProjectState:
        with self._lock:
            return self._states.setdefault(self._key(root), ProjectState())

    def try_start(self, root: Path) -> bool:
        """Mark the folder's checks as running, unless they already are. The Changes page, the
        run after a turn and the agent's run_checks take turns: two runs of one test suite trip
        over its caches and locks."""
        state = self.state(root)
        with self._lock:
            if state.running:
                return False
            state.running = True
            return True

    def finish(self, root: Path) -> None:
        state = self.state(root)
        with self._lock:
            state.running = False

    def record(self, root: Path, results: list[CheckResult]) -> None:
        # Not the running mark: that belongs to whoever started a run (finish), and results
        # reported by one run must not end another that is still going.
        state = self.state(root)
        with self._lock:
            state.results = [result.to_dict() for result in results]
            state.finished_at = time.time()
        if self.on_results is not None:
            self.on_results(root, state)

    def tools(self, workspace: Path) -> tuple[Tool, ...]:
        return (
            *code_tools(workspace, self.lsp),
            RunChecksTool(
                workspace, self.trust, self.record, start=self.try_start, finish=self.finish
            ),
            ReadTerminalTool(self.shells, workspace),
            CheckPageTool(workspace),
            DebugPythonTool(workspace, self.debug.home),
            # Linux commands in the folder, where Windows has WSL.
            *((RunWslTool(workspace),) if shutil.which("wsl") else ()),
        )

    def hooks(self, workspace: Path) -> ToolHooks:
        return CodingHooks(workspace, self.lsp, self.trust)

    def close(self) -> None:
        self.debug.close()
        self.shells.close()
        self.lsp.close()


__all__ = ["CodingDesk"]
