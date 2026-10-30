"""The editor's debugger: start the open Python file under debugpy, step through it, and read
the stack, the variables and expressions while it is stopped."""

from __future__ import annotations

from typing import Any

from agent_workspace.coding.debugger import DebugError
from agent_workspace.core.events import Event
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths
from agent_workspace.ui_gateway.gateway_common import GatewayError, GatewayReply
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import CommandEnvelope

DEBUG_COMMANDS = frozenset(
    {
        "debug.status",
        "debug.install",
        "debug.start",
        "debug.control",
        "debug.stack",
        "debug.scopes",
        "debug.variables",
        "debug.evaluate",
        "debug.breakpoints",
        "debug.stop",
    }
)
# Installing debugpy downloads it (seconds to a minute): one at a time, on its own thread.
DEBUG_LONG_COMMANDS = frozenset({"debug.install"})
# Each waits for the debugger (starting it takes seconds): off the reader thread.
DEBUG_QUERY_COMMANDS = DEBUG_COMMANDS - DEBUG_LONG_COMMANDS
_MAX_BREAKPOINT_FILES = 200


def _int(value: object) -> int:
    if type(value) is not int:
        raise GatewayError("invalid_command")
    return value


class DebugCommands(GatewayState):
    def _debug_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        root = self._open_folder()
        desk = self._coding.debug
        payload: dict[str, Any] = command.payload
        try:
            if command.type == "debug.status":
                result: dict[str, object] = desk.status(root)
            elif command.type == "debug.install":
                result = desk.install(root)
            elif command.type == "debug.start":
                result = self._debug_start(root, payload)
            elif command.type == "debug.control":
                thread = payload.get("threadId")
                desk.current().control(
                    str(payload.get("action")), _int(thread) if thread is not None else None
                )
                result = {"ok": True}
            elif command.type == "debug.stack":
                session = desk.current()
                thread = payload.get("threadId")
                result = {
                    "frames": session.stack(_int(thread) if thread is not None else None),
                    "exception": session.exception(),
                }
            elif command.type == "debug.scopes":
                session = desk.current()
                scopes = session.scopes(_int(payload.get("frameId")))
                # The first scope that is cheap to read (the locals) comes with its variables.
                first = next((scope for scope in scopes if not scope["expensive"]), None)
                result = {
                    "scopes": scopes,
                    "variables": session.variables(_int(first["reference"])) if first else [],
                }
            elif command.type == "debug.variables":
                result = {"variables": desk.current().variables(_int(payload.get("reference")))}
            elif command.type == "debug.evaluate":
                expression = payload.get("expression")
                frame = payload.get("frameId")
                if (
                    not isinstance(expression, str)
                    or not expression.strip()
                    or len(expression) > 2000
                ):
                    raise GatewayError("invalid_command")
                result = desk.current().evaluate(
                    expression, _int(frame) if frame is not None else None
                )
            elif command.type == "debug.breakpoints":
                path, lines = payload.get("path"), payload.get("lines")
                if not isinstance(path, str) or not isinstance(lines, list):
                    raise GatewayError("invalid_command")
                live = desk.session
                result = {
                    "breakpoints": live.set_breakpoints(
                        self._debug_file(root, path), self._debug_lines(lines)
                    )
                    if live is not None and live.state != "terminated"
                    else []
                }
            else:
                desk.stop()
                result = {"ok": True}
        except DebugError as error:
            raise GatewayError(error.code) from None
        return self._reply(f"{command.type}.result", result, session_id=None)

    @staticmethod
    def _debug_file(root: Any, path: str) -> str:
        try:
            return str(WorkspacePaths(root).resolve(path))
        except WorkspacePathError:
            raise GatewayError("invalid_path") from None

    @staticmethod
    def _debug_lines(lines: list[Any]) -> list[dict[str, Any]]:
        points: list[dict[str, Any]] = []
        for item in lines[:500]:
            if type(item) is int and item > 0:
                points.append({"line": item})
            elif isinstance(item, dict) and type(item.get("line")) is int and item["line"] > 0:
                condition = item.get("condition")
                points.append(
                    {
                        "line": item["line"],
                        **(
                            {"condition": condition}
                            if isinstance(condition, str) and condition
                            else {}
                        ),
                    }
                )
            else:
                raise GatewayError("invalid_command")
        return points

    def _debug_start(self, root: Any, payload: dict[str, Any]) -> dict[str, object]:
        path, module, args = payload.get("path"), payload.get("module"), payload.get("args", [])
        if (
            bool(path) == bool(module)
            or not isinstance(args, list)
            or not all(isinstance(item, str) for item in args)
        ):
            raise GatewayError("invalid_command")
        program = self._debug_file(root, path) if isinstance(path, str) else None
        raw = payload.get("breakpoints", {})
        if not isinstance(raw, dict) or len(raw) > _MAX_BREAKPOINT_FILES:
            raise GatewayError("invalid_command")
        breakpoints = {
            self._debug_file(root, file): self._debug_lines(lines)
            for file, lines in raw.items()
            if isinstance(file, str) and isinstance(lines, list)
        }
        self._coding.debug.start(
            root,
            program=program,
            module=module if isinstance(module, str) else None,
            args=args,
            breakpoints=breakpoints,
        )
        return self._coding.debug.status(root)

    def _collect_debug_events(self) -> None:
        """Called under the gateway lock with the other host events."""
        for event_type, data in self._coding.debug.drain():
            self._pending_host_events.append(
                Event(session_id="desktop", type=event_type, data=data)
            )


__all__ = ["DEBUG_COMMANDS", "DEBUG_LONG_COMMANDS", "DEBUG_QUERY_COMMANDS", "DebugCommands"]
