"""What the desktop runs around the agent's tool calls in a folder: the project's rules (no
writes to protected paths, formatters on written files, no secrets in commits) and the
language server's report on each file the agent edits."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from agent_workspace.tools.lsp import LspClientError
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

from .code_tools import problem_line
from .lsp_pool import LspPool, NoServerError
from .project import (
    ProjectConfig,
    ProjectConfigError,
    TrustBook,
    config_path,
    format_file,
    load_config,
    protected_reason,
    scan_secrets,
    staged_diff,
)

_EDIT_TOOLS = frozenset({"write_file", "apply_patch"})
# Tools that change files, and the arguments naming them.
_WRITING_TOOLS: Mapping[str, tuple[str, ...]] = {
    "write_file": ("path",),
    "apply_patch": ("path",),
    "delete_path": ("path",),
    "make_directory": ("path",),
    "move_path": ("source", "destination"),
    "create_docx": ("path",),
    "edit_docx": ("path",),
    "create_xlsx": ("path",),
    "update_xlsx": ("path",),
    "create_pptx": ("path",),
}
_MAX_REPORTED = 12
_EDIT_WAIT_SECONDS = 6.0


class CodingHooks:
    def __init__(
        self,
        workspace: Path,
        pool: LspPool,
        trust: TrustBook | None = None,
        *,
        diff: Callable[[Path], str] = staged_diff,
    ) -> None:
        self.paths = WorkspacePaths(workspace)
        self.pool = pool
        self.trust = trust
        self._diff = diff
        self._config: tuple[float | None, ProjectConfig | None] = (None, None)

    def config(self) -> ProjectConfig | None:
        """The folder's settings, read again when the file changes; a broken file counts as none."""
        path = config_path(self.paths.root)
        try:
            stamp: float | None = path.stat().st_mtime_ns
        except OSError:
            stamp = None
        if stamp != self._config[0]:
            try:
                loaded = load_config(self.paths.root) if stamp is not None else None
            except ProjectConfigError:
                loaded = None
            self._config = (stamp, loaded)
        return self._config[1]

    def _commands_allowed(self, config: ProjectConfig) -> bool:
        return self.trust is not None and self.trust.trusted(self.paths.root, config)

    async def before_tool(
        self, name: str, arguments: Mapping[str, Any], *, session_id: str
    ) -> str | None:
        config = self.config()
        if config is not None and config.protected and name in _WRITING_TOOLS:
            values = [arguments.get(key) for key in _WRITING_TOOLS[name]]
            reason = protected_reason(self.paths.root, config, values)
            if reason is not None:
                return reason
        if config is not None and config.protected and name == "organize_files":
            operations = arguments.get("operations")
            values = [
                value
                for operation in (operations if isinstance(operations, list) else ())
                if isinstance(operation, dict)
                for value in (operation.get("path"), operation.get("to"))
            ]
            reason = protected_reason(self.paths.root, config, values)
            if reason is not None:
                return reason
        if name == "git_commit" and (config is None or config.secret_scan):
            try:
                diff = await asyncio.to_thread(self._diff, self.paths.root)
            except (OSError, ValueError):
                return None
            found = scan_secrets(diff)
            if found:
                listed = "; ".join(found[:8])
                return (
                    f"the staged changes contain what looks like a secret ({listed}). Remove it "
                    "from the files (use an environment variable or an ignored config file), "
                    "stage again and commit."
                )
        return None

    async def after_tool(
        self, name: str, arguments: Mapping[str, Any], result: str, *, session_id: str
    ) -> str | None:
        if name not in _EDIT_TOOLS:
            return None
        value = arguments.get("path")
        notes = [await self.format_report(value), await self.edit_report(value)]
        text = "\n".join(note for note in notes if note)
        return text or None

    async def format_report(self, value: object) -> str | None:
        """Run the project's formatter on a file just written, and say if it changed it."""
        config = self.config()
        if config is None or not config.formatters or not isinstance(value, str):
            return None
        if not self._commands_allowed(config):
            return None
        try:
            path = self.paths.resolve(value)
            shown = self.paths.relative(path)
        except (WorkspacePathError, ValueError):
            return None
        outcome = await asyncio.to_thread(format_file, self.paths.root, config, shown)
        if outcome is None:
            return None
        if not outcome.ok:
            detail = outcome.output.strip().splitlines()[-1:] or [""]
            return f"The project's formatter (`{outcome.command}`) failed: {detail[0][:300]}"
        if not outcome.changed:
            return None
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return (
            f"The project's formatter (`{outcome.command}`) reformatted {shown}; its SHA-256 is "
            f"now {digest}. Read it again before the next edit."
        )

    async def edit_report(self, value: object) -> str | None:
        """The language server's errors in a file just written, so the agent fixes them now."""
        if not isinstance(value, str):
            return None
        try:
            path = self.paths.resolve(value)
            shown = self.paths.relative(path)
        except (WorkspacePathError, ValueError):
            return None
        if self.pool.find(path) is None or not path.is_file():
            return None
        try:
            report = await self.pool.call(
                lambda: self.pool.diagnostics(self.paths.root, path, wait=_EDIT_WAIT_SECONDS)
            )
        except (NoServerError, LspClientError, OSError, RuntimeError):
            return None
        errors = [item for item in report.diagnostics if item.severity == 1]
        if report.pending and not errors:
            return f"{report.server} had not finished checking {shown}."
        if not errors:
            return f"{report.server}: no errors in {shown}."
        lines = [f"{report.server} reports {len(errors)} error(s) in {shown} after this edit:"]
        lines += [f"- {problem_line(item)}" for item in errors[:_MAX_REPORTED]]
        if len(errors) > _MAX_REPORTED:
            lines.append(f"- … {len(errors) - _MAX_REPORTED} more (code_diagnostics lists all)")
        return "\n".join(lines)


__all__ = ["CodingHooks"]
