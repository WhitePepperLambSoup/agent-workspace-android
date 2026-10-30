"""The terminal panel's commands: open a shell in the folder, type into it, resize it, stop or
close it, and show what it printed again after the window reloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_workspace.coding.shell import ShellError
from agent_workspace.core.events import Event
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths
from agent_workspace.ui_gateway.gateway_common import GatewayError, GatewayReply
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import CommandEnvelope

SHELL_COMMANDS = frozenset(
    {
        "shell.list",
        "shell.start",
        "shell.input",
        "shell.resize",
        "shell.stop",
        "shell.close",
        "shell.replay",
    }
)
# Finding the shells asks WSL for its distributions (a second or more), and starting one
# creates a console: off the reader thread, so typing in another terminal is not held up.
SHELL_QUERY_COMMANDS = frozenset({"shell.list", "shell.start"})


class ShellCommands(GatewayState):
    def _shell_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        handler = {
            "shell.list": self._shell_list,
            "shell.start": self._shell_start,
            "shell.input": self._shell_input,
            "shell.resize": self._shell_resize,
            "shell.stop": self._shell_stop,
            "shell.close": self._shell_close,
            "shell.replay": self._shell_replay,
        }[command.type]
        try:
            payload = handler(command.payload)
        except ShellError as error:
            raise GatewayError(error.code) from None
        return self._reply(f"{command.type}.result", payload, session_id=None)

    def _shell_list(self, payload: dict[str, Any]) -> dict[str, object]:
        if payload:
            raise GatewayError("invalid_command")
        shells = self._coding.shells
        return {
            "shells": shells.listing(),
            "programs": [program.to_dict() for program in shells.programs()],
        }

    def _shell_start(self, payload: dict[str, Any]) -> dict[str, object]:
        if not set(payload) <= {"program", "cwd", "columns", "rows"}:
            raise GatewayError("invalid_command")
        program = payload.get("program")
        if program is not None and not isinstance(program, str):
            raise GatewayError("invalid_command")
        try:
            root = self._open_folder()
        except GatewayError:
            root = Path.home()
        cwd = payload.get("cwd", "")
        if not isinstance(cwd, str):
            raise GatewayError("invalid_command")
        try:
            folder = WorkspacePaths(root).resolve(cwd or ".")
        except WorkspacePathError:
            raise GatewayError("invalid_cwd") from None
        shell = self._coding.shells.start(
            folder, program=program, columns=payload.get("columns"), rows=payload.get("rows")
        )
        return {"shell": shell.info()}

    def _shell_input(self, payload: dict[str, Any]) -> dict[str, object]:
        if set(payload) != {"shellId", "data"}:
            raise GatewayError("invalid_command")
        self._coding.shells.write(payload["shellId"], payload["data"])
        return {"ok": True}

    def _shell_resize(self, payload: dict[str, Any]) -> dict[str, object]:
        if set(payload) != {"shellId", "columns", "rows"}:
            raise GatewayError("invalid_command")
        self._coding.shells.resize(payload["shellId"], payload["columns"], payload["rows"])
        return {"ok": True}

    def _shell_stop(self, payload: dict[str, Any]) -> dict[str, object]:
        if set(payload) != {"shellId"}:
            raise GatewayError("invalid_command")
        self._coding.shells.stop(payload["shellId"])
        return {"ok": True}

    def _shell_close(self, payload: dict[str, Any]) -> dict[str, object]:
        if set(payload) != {"shellId"}:
            raise GatewayError("invalid_command")
        self._coding.shells.remove(payload["shellId"])
        return {"ok": True}

    def _shell_replay(self, payload: dict[str, Any]) -> dict[str, object]:
        if set(payload) != {"shellId"}:
            raise GatewayError("invalid_command")
        return {"replay": self._coding.shells.get(payload["shellId"]).replay()}

    def _collect_shell_output(self) -> None:
        """Called under the gateway lock with the other host events: what the terminals
        printed since the last time, for the window."""
        for event_type, data in self._coding.shells.drain():
            self._pending_host_events.append(
                Event(session_id="desktop", type=event_type, data=data)
            )


__all__ = ["SHELL_COMMANDS", "SHELL_QUERY_COMMANDS", "ShellCommands"]
