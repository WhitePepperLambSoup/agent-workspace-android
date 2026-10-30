"""The code editor's language-server commands: problems in the open file, where a symbol is
defined, its type; and the Settings list of language servers with their installation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_workspace.application.ports import Tool
from agent_workspace.coding.editor_ai import (
    MAX_SELECTION,
    EditorAiError,
    complete_at_cursor,
    completion_available,
    rewrite_selection,
)
from agent_workspace.coding.install import InstallError
from agent_workspace.coding.lsp_pool import Location, NoServerError
from agent_workspace.config import ProviderConfig
from agent_workspace.tools.lsp import LspClientError
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths
from agent_workspace.ui_gateway.gateway_common import _LOGGER, GatewayError, GatewayReply
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import CommandEnvelope

CODE_COMMANDS = frozenset(
    {
        "code.servers",
        "code.servers.install",
        "code.diagnostics",
        "code.definition",
        "code.hover",
        "editor.rewrite",
        "editor.complete",
    }
)
# They wait for a model: answered off the reader thread with the other model calls.
EDITOR_MODEL_COMMANDS = frozenset({"editor.rewrite", "editor.complete"})
# Answered off the reader thread: a server may take a second to answer.
CODE_QUERY_COMMANDS = frozenset({"code.diagnostics", "code.definition", "code.hover"})
# Downloading a language server takes a while: one at a time, on a thread of its own.
CODE_LONG_COMMANDS = frozenset({"code.servers.install"})
_MAX_TEXT_CHARS = 4 * 1024 * 1024
_MAX_DIAGNOSTICS = 500
_EDITOR_WAIT_SECONDS = 5.0


class CodeCommands(GatewayState):
    def _folder_tools(self, workspace: Path) -> tuple[Tool, ...]:
        """The tools made for each open folder: research and Office ones, and the code tools."""
        return (*self._research_tools(workspace), *self._coding.tools(workspace))

    def _code_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        handler = {
            "code.servers": self._code_servers,
            "code.servers.install": self._code_install,
            "code.diagnostics": self._code_diagnostics,
            "code.definition": self._code_definition,
            "code.hover": self._code_hover,
            "editor.rewrite": self._editor_rewrite,
            "editor.complete": self._editor_complete,
        }[command.type]
        return self._reply(f"{command.type}.result", handler(command.payload), session_id=None)

    def _editor_rewrite(self, payload: dict[str, Any]) -> dict[str, Any]:
        fields = {"path", "language", "before", "selection", "after", "instruction"}
        if set(payload) != fields or not all(isinstance(payload[key], str) for key in fields):
            raise GatewayError("invalid_command")
        if not payload["instruction"].strip() or len(payload["selection"]) > MAX_SELECTION:
            raise GatewayError("invalid_command")
        config = self._quick_provider()
        try:
            text = rewrite_selection(
                config,
                path=payload["path"][:500],
                language=payload["language"][:40],
                before=payload["before"],
                selection=payload["selection"],
                after=payload["after"],
                instruction=payload["instruction"],
            )
        except EditorAiError as error:
            raise GatewayError(str(error)) from None
        return {"text": text, "model": config.model}

    def _editor_complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        if set(payload) != {"path", "prefix", "suffix"} or not all(
            isinstance(payload[key], str) for key in ("path", "prefix", "suffix")
        ):
            raise GatewayError("invalid_command")
        try:
            config: ProviderConfig | None = self._quick_provider()
        except GatewayError:
            config = None
        if config is None or not completion_available(config):
            return {"available": False, "text": ""}
        try:
            text = complete_at_cursor(config, payload["prefix"], payload["suffix"])
        except EditorAiError:
            return {"available": True, "failed": True, "text": ""}
        return {"available": True, "text": text}

    def _code_servers(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload:
            raise GatewayError("invalid_command")
        return {"servers": self._coding.lsp.status()}

    def _code_install(self, payload: dict[str, Any]) -> dict[str, Any]:
        server_id = payload.get("id")
        if set(payload) != {"id"} or not isinstance(server_id, str):
            raise GatewayError("invalid_command")
        try:
            versions = self._coding.lsp.install(server_id)
        except ValueError:
            raise GatewayError("invalid_command") from None
        except InstallError as error:
            _LOGGER.warning("language server install failed: %s", error)
            raise GatewayError("code_install_failed") from None
        return {"installed": versions, "servers": self._coding.lsp.status()}

    def _open_folder(self) -> Path:
        """The folder the window shows, also while its runtime is being replaced (a session
        switch clears the current one for a moment)."""
        with self._lock:
            workspace = self._workspace
            target = self._workspace_activation_target
            selected = self._selected_session_id
        if workspace is not None:
            return workspace
        if target is not None:
            return target[0]
        session = self._stored_session(selected) if selected is not None else None
        if session is not None:
            return Path(session.workspace)
        raise GatewayError("workspace_unavailable")

    def _code_file(self, payload: dict[str, Any]) -> tuple[WorkspacePaths, Path]:
        workspace = self._open_folder()
        value = payload.get("path")
        if not isinstance(value, str) or not value:
            raise GatewayError("invalid_command")
        paths = WorkspacePaths(workspace)
        try:
            path = paths.resolve(value)
        except WorkspacePathError:
            raise GatewayError("invalid_path") from None
        if not path.is_file():
            raise GatewayError("file_not_found")
        return paths, path

    def _code_position(self, payload: dict[str, Any]) -> tuple[WorkspacePaths, Path, int, int]:
        if set(payload) != {"path", "line", "character"}:
            raise GatewayError("invalid_command")
        line, character = payload.get("line"), payload.get("character")
        if not isinstance(line, int) or not isinstance(character, int) or line < 0 or character < 0:
            raise GatewayError("invalid_command")
        paths, path = self._code_file(payload)
        return paths, path, line, character

    def _code_diagnostics(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not set(payload) <= {"path", "text"}:
            raise GatewayError("invalid_command")
        text = payload.get("text")
        if text is not None and (not isinstance(text, str) or len(text) > _MAX_TEXT_CHARS):
            raise GatewayError("invalid_command")
        paths, path = self._code_file(payload)
        pool = self._coding.lsp
        if pool.find(path) is None:
            return {"path": payload["path"], "available": False, "diagnostics": []}
        try:
            report = pool.run(
                lambda: pool.diagnostics(paths.root, path, text, wait=_EDITOR_WAIT_SECONDS),
                timeout=40,
            )
        except (NoServerError, LspClientError, OSError, TimeoutError) as error:
            _LOGGER.info("diagnostics for the editor failed: %s", error)
            return {"path": payload["path"], "available": True, "failed": True, "diagnostics": []}
        return {
            "path": payload["path"],
            "available": True,
            "server": report.server,
            "pending": report.pending,
            "diagnostics": [
                {
                    "line": item.range_start_line,
                    "character": item.range_start_character,
                    "endLine": item.range_end_line,
                    "endCharacter": item.range_end_character,
                    "severity": item.severity,
                    "message": item.message[:2000],
                    "source": item.source,
                    "code": item.code,
                }
                for item in report.diagnostics[:_MAX_DIAGNOSTICS]
            ],
        }

    def _code_location(self, paths: WorkspacePaths, location: Location) -> dict[str, Any]:
        try:
            shown, inside = paths.relative(location.path), True
        except (WorkspacePathError, ValueError):
            shown, inside = str(location.path), False
        return {
            "path": shown,
            "inside": inside,
            "line": location.line,
            "character": location.character,
        }

    def _code_definition(self, payload: dict[str, Any]) -> dict[str, Any]:
        paths, path, line, character = self._code_position(payload)
        pool = self._coding.lsp
        try:
            found = pool.run(lambda: pool.definition(paths.root, path, line, character), 40)
        except NoServerError:
            return {"available": False, "locations": []}
        except (LspClientError, OSError, TimeoutError):
            return {"available": True, "failed": True, "locations": []}
        return {
            "available": True,
            "locations": [self._code_location(paths, item) for item in found[:20]],
        }

    def _code_hover(self, payload: dict[str, Any]) -> dict[str, Any]:
        paths, path, line, character = self._code_position(payload)
        pool = self._coding.lsp
        try:
            text = pool.run(lambda: pool.hover(paths.root, path, line, character), 40)
        except NoServerError:
            return {"available": False, "text": ""}
        except (LspClientError, OSError, TimeoutError):
            return {"available": True, "failed": True, "text": ""}
        return {"available": True, "text": text[:4000]}


__all__ = [
    "CODE_COMMANDS",
    "CODE_LONG_COMMANDS",
    "CODE_QUERY_COMMANDS",
    "EDITOR_MODEL_COMMANDS",
    "CodeCommands",
]
