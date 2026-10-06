"""Agent tools for long-running services (mobile_services): start, list, read logs, stop.

run_terminal is for commands that finish on their own. A service is for a program that has to
keep running after the task ends, such as a local web server; the user sees it on the Services
page, can open its port in a browser and can stop it at any time.
"""

from __future__ import annotations

import asyncio
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result, optional_int
from agent_workspace.tools.paths import StrPath, WorkspacePaths

_STARTUP_WAIT_SECONDS = 4.0
_KEY_SCHEMA = {
    "type": "object",
    "properties": {
        "service": {
            "type": "string",
            "minLength": 1,
            "maxLength": 64,
            "description": "The service id or name",
        }
    },
    "required": ["service"],
    "additionalProperties": False,
}


def _manager() -> Any:
    from mobile_services import get_service_manager

    manager = get_service_manager()
    if manager is None:
        raise ToolError("services are unavailable in this runtime")
    return manager


def _key(arguments: dict[str, Any]) -> str:
    value = arguments.get("service")
    if not isinstance(value, str) or not value:
        raise ToolArgumentError("'service' must be a service id or name")
    return value


async def _call(function: Any, *arguments: Any, **options: Any) -> Any:
    from mobile_services import ServiceError

    try:
        return await asyncio.to_thread(function, *arguments, **options)
    except KeyError:
        raise ToolError("no service has that id or name; use list_services") from None
    except ServiceError as error:
        raise ToolError(str(error)) from None


class StartServiceTool:
    hard_cancellable = False

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self._spec = ToolSpec(
            name="start_service",
            description=(
                "Start a program that keeps running after this task ends, such as a local web "
                "server, a bot or a file watcher. It runs until the user or stop_service stops "
                "it, or the app's engine stops. Do not use it for commands that finish on their "
                "own (installs, builds, scripts): use run_terminal with a longer timeout_seconds. "
                "stdin is closed, so pass flags that avoid prompts. Output goes to a log read "
                "with service_logs. If it serves on a local port, pass port so the user can open "
                "it. Starting a name that already exists replaces that service's command. At most "
                "4 services run at once."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 60},
                    "argv": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1, "maxLength": 32767},
                        "minItems": 1,
                        "maxItems": 256,
                    },
                    "cwd": {"type": "string", "minLength": 1, "default": "."},
                    "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                    "autostart": {
                        "type": "boolean",
                        "description": "Start it again whenever the app's engine starts",
                    },
                },
                "required": ["name", "argv"],
                "additionalProperties": False,
            },
            side_effect="process",
            capability=Capability.PROCESS_EXECUTE,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def prepare_for_approval(self, arguments: dict[str, Any]) -> dict[str, Any]:
        from mobile_services import ServiceError, validate_argv

        try:
            argv = validate_argv(arguments.get("argv"))
        except ServiceError as error:
            raise ToolArgumentError(str(error)) from None
        name = arguments.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 60:
            raise ToolArgumentError("'name' must be 1 to 60 characters")
        cwd = arguments.get("cwd", ".")
        if not isinstance(cwd, str) or not cwd:
            raise ToolArgumentError("'cwd' must be a workspace folder")
        prepared: dict[str, Any] = {"name": name.strip(), "argv": argv, "cwd": cwd}
        if "port" in arguments:
            prepared["port"] = arguments["port"]
        if arguments.get("autostart") is True:
            prepared["autostart"] = True
        return prepared

    async def execute(self, arguments: dict[str, Any]) -> str:
        prepared = self.prepare_for_approval(arguments)
        cwd = self.paths.resolve(prepared["cwd"])
        if not cwd.is_dir():
            raise ToolError("the service's working folder is not a directory")
        manager = _manager()
        status = await _call(
            manager.start,
            prepared["name"],
            prepared["argv"],
            cwd,
            workspace=self.paths.root,
            port=prepared.get("port"),
            autostart=prepared.get("autostart", False),
        )
        # Report an immediate crash, or the port opening, instead of a bare "started".
        from mobile_services import _port_open

        loop = asyncio.get_running_loop()
        deadline = loop.time() + _STARTUP_WAIT_SECONDS
        port = prepared.get("port")
        while loop.time() < deadline:
            await asyncio.sleep(0.25)
            if not manager.is_running(status["id"]):
                break
            if port is not None and await asyncio.to_thread(_port_open, port):
                break
        status = await _call(manager.status, status["id"], probe=True)
        logs = await _call(manager.logs, status["id"], 2048)
        return json_result({**status, "log_tail": logs["text"]})

    async def execute_with_context(self, arguments: dict[str, Any], _context: Any) -> str:
        return await self.execute(arguments)


class ListServicesTool:
    _SPEC = ToolSpec(
        name="list_services",
        description="List the long-running services on this phone with their state and URLs.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        side_effect="none",
        capability=Capability.PROCESS_EXECUTE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        manager = _manager()
        snapshot = await asyncio.to_thread(manager.snapshot, probe=True)
        for service in snapshot["services"]:
            service.pop("source", None)
        return json_result(snapshot)


class ServiceLogsTool:
    _SPEC = ToolSpec(
        name="service_logs",
        description="Read the end of a service's output log.",
        input_schema={
            "type": "object",
            "properties": {
                **_KEY_SCHEMA["properties"],
                "max_bytes": {"type": "integer", "minimum": 256, "maximum": 65536},
            },
            "required": ["service"],
            "additionalProperties": False,
        },
        side_effect="read_state",
        capability=Capability.PROCESS_EXECUTE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        max_bytes = optional_int(arguments, "max_bytes", 8192, minimum=256, maximum=65536)
        return json_result(await _call(_manager().logs, _key(arguments), max_bytes))


class StopServiceTool:
    _SPEC = ToolSpec(
        name="stop_service",
        description="Stop a running service and every process it started.",
        input_schema=_KEY_SCHEMA,
        # Stopping only ends what was already approved to run.
        side_effect="write_state",
        capability=Capability.PROCESS_EXECUTE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        return json_result(await _call(_manager().stop, _key(arguments), "stopped by the agent"))


__all__ = ["ListServicesTool", "ServiceLogsTool", "StartServiceTool", "StopServiceTool"]
