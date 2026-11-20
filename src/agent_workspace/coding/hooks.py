"""What the desktop runs around the agent's tool calls in a folder: the project's rules (no
writes to protected paths, formatters on written files, no secrets in commits) and the
language server's report on each file the agent edits."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from agent_workspace.core.models import ToolSpec
from agent_workspace.tools.lsp import LspClientError
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

from .code_tools import problem_line
from .lsp_pool import LspPool, NoServerError
from .project import (
    PROJECT_FILE,
    ProjectConfig,
    ProjectConfigError,
    TrustBook,
    config_path,
    format_file,
    load_config,
    parse_config,
    protected_reason,
    scan_secrets,
    staged_diff,
)

_EDIT_TOOLS = frozenset({"write_file", "apply_patch"})
# Tools that change files, and the arguments naming what they change. Any other tool is judged by
# its spec once the runtime hands its tools over (bind_tools): one that writes, deletes, moves or
# makes a folder, or keeps a checkpoint of what it changes, by its _PATH_ARGUMENTS.
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
    "export_references": ("path",),
    # Writes the PDF and its build folder beside the document.
    "compile_latex": ("path",),
    "apply_sandbox_change": ("path",),
    "download_file": ("path",),
    # A screenshot or PDF saved to a file.
    "browser": ("path",),
    "office_template": ("file",),
    "email_files": ("file",),
    "slides_from_template": ("path",),
    # Its path is the recording it reads.
    "meeting_transcribe": ("output",),
}
# Office tools that write to output when given, and otherwise change the file or write beside it.
_OUTPUT_OR_FILE_TOOLS = frozenset({"word_document", "spreadsheet", "pdf_tools"})
_PATH_ARGUMENTS = ("path", "paths", "destination", "output")
_WRITING_EFFECTS = frozenset({"write", "delete", "move", "mkdir"})
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
        self._specs: dict[str, ToolSpec] = {}

    def bind_tools(self, specs: Iterable[ToolSpec]) -> None:
        """The runtime's tools: one not named above is judged by what its spec says it does."""
        self._specs = {spec.name: spec for spec in specs}

    def _written(self, name: str, arguments: Mapping[str, Any]) -> list[object]:
        """The paths a call would change, as given."""
        if name == "organize_files":
            operations = arguments.get("operations")
            return [
                value
                for operation in (operations if isinstance(operations, list) else ())
                if isinstance(operation, dict)
                for value in (operation.get("path"), operation.get("to"))
            ]
        if name == "remote_copy":
            return [arguments.get("path")] if arguments.get("direction") == "download" else []
        if name in _OUTPUT_OR_FILE_TOOLS:
            return [arguments.get("output") or arguments.get("file")]
        keys = _WRITING_TOOLS.get(name)
        if keys is None:
            spec = self._specs.get(name)
            if spec is None or not (
                spec.side_effect in _WRITING_EFFECTS or spec.durable_preimage_checkpoint
            ):
                return []
            properties = spec.input_schema.get("properties") or {}
            keys = tuple(key for key in _PATH_ARGUMENTS if key in properties)
        values: list[object] = []
        for key in keys:
            value = arguments.get(key)
            values.extend(value if isinstance(value, list) else [value])
        return values

    def config(self) -> ProjectConfig | None:
        """The folder's settings, read again when the file changes. A file broken since it was
        last read keeps the settings read then: breaking it must not lift its rules."""
        path = config_path(self.paths.root)
        try:
            stamp: float | None = path.stat().st_mtime_ns
        except OSError:
            stamp = None
        if stamp != self._config[0]:
            try:
                loaded = load_config(self.paths.root) if stamp is not None else None
            except ProjectConfigError:
                loaded = self._config[1]
            self._config = (stamp, loaded)
        return self._config[1]

    def _is_project_file(self, value: object) -> bool:
        if not isinstance(value, str) or not value:
            return False
        try:
            relative = self.paths.relative(self.paths.resolve(value))
        except (WorkspacePathError, ValueError, OSError):
            return False
        return os.path.normcase(relative) == os.path.normcase(str(PROJECT_FILE))

    def _project_file_after(
        self, name: str, arguments: Mapping[str, Any]
    ) -> tuple[bool, ProjectConfig | None]:
        """What .agent/project.json would hold after this call: (known, settings), where known
        settings of None are a file that does not parse."""
        text: str | None = None
        if name == "write_file":
            text = str(arguments.get("content") or "")
        elif name == "apply_patch":
            try:
                current = config_path(self.paths.root).read_text(encoding="utf-8-sig")
            except OSError:
                return False, None
            old, new = arguments.get("old_text"), arguments.get("new_text")
            if not isinstance(old, str) or not isinstance(new, str) or old not in current:
                return True, self.config()  # The patch does not apply; nothing changes.
            text = current.replace(old, new, 1)
        elif name == "delete_path" or (
            name == "move_path" and self._is_project_file(arguments.get("source"))
        ):
            return True, ProjectConfig()  # No file: no protected paths, secrets still checked.
        else:
            return False, None
        try:
            return True, parse_config(json.loads(text))
        except (ValueError, ProjectConfigError):
            return True, None

    def _rules_lifted(self, name: str, arguments: Mapping[str, Any]) -> str | None:
        """Why a change the agent makes to the project's settings is refused: the rules that only
        forbid (protected paths, the secret check) are for the user to lift, not the agent."""
        before = self.config() or ProjectConfig()
        known, after = self._project_file_after(name, arguments)
        if known and after is not None:
            dropped = [pattern for pattern in before.protected if pattern not in after.protected]
            if not dropped and (after.secret_scan or not before.secret_scan):
                return None
        elif not before.protected and not before.secret_scan:
            return None
        return (
            f"this change to {PROJECT_FILE} would lift or break the project's rules (protected "
            "paths, the secret check). Only the user changes those, on the Changes page or in an "
            "editor; tell them what you would change. Adding checks or rules is fine."
        )

    def _commands_allowed(self, config: ProjectConfig) -> bool:
        return self.trust is not None and self.trust.trusted(self.paths.root, config)

    async def before_tool(
        self, name: str, arguments: Mapping[str, Any], *, session_id: str
    ) -> str | None:
        config = self.config()
        written = self._written(name, arguments)
        if any(self._is_project_file(value) for value in written):
            lifted = self._rules_lifted(name, arguments)
            if lifted is not None:
                return lifted
        if config is not None and config.protected:
            reason = protected_reason(self.paths.root, config, written)
            if reason is not None:
                return reason
        if name == "git_commit" and (config is None or config.secret_scan):
            # The repository the commit goes to, which can be one inside the folder.
            try:
                repository = self.paths.resolve(str(arguments.get("repository") or "."))
            except (WorkspacePathError, ValueError):
                return None  # git_commit refuses a repository outside the folder itself.
            try:
                diff = await asyncio.to_thread(self._diff, repository)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                # Unchecked is not clean: the commit waits until the check can run.
                return (
                    f"the staged changes could not be checked for secrets ({error}). Make sure "
                    "the repository is valid, then commit again."
                )
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
