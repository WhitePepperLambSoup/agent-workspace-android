from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.background_jobs import BackgroundJobLimits
from agent_workspace.core.models import Capability, ToolSpec

from .base import ToolArgumentError, ToolError, json_result
from .command import RunProcessTool

if TYPE_CHECKING:
    from agent_workspace.application.background_jobs import BackgroundJobManager


class StartBackgroundJobTool:
    def __init__(self, manager: BackgroundJobManager) -> None:
        self.manager = manager
        process_schema = RunProcessTool(manager.paths).spec.input_schema
        properties = dict(process_schema["properties"])
        properties.pop("timeout_seconds", None)
        properties.update(
            {
                "label": {"type": "string", "minLength": 1, "maxLength": 200},
                "max_seconds": {"type": "integer", "minimum": 1, "maximum": 110},
                "max_output_bytes": {
                    "type": "integer",
                    "minimum": 1024,
                    "maximum": 1048576,
                },
            }
        )
        self._spec = ToolSpec(
            name="start_background_job",
            description=(
                "Start a bounded non-interactive background host process. stdin is closed; use "
                "background_job_status, background_job_logs, or stop_background_job to manage it."
            ),
            input_schema={
                "type": "object",
                "properties": properties,
                "required": list(process_schema.get("required", [])),
                "additionalProperties": False,
            },
            side_effect="process",
            capability=Capability.PROCESS_EXECUTE,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def prepare_for_approval(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if "timeout_seconds" in arguments:
            raise ToolArgumentError("use 'max_seconds' for a background job timeout")
        process_arguments = {
            key: value
            for key, value in arguments.items()
            if key not in {"label", "max_seconds", "max_output_bytes"}
        }
        prepared = RunProcessTool(self.manager.paths).prepare_for_approval(process_arguments)
        prepared["label"] = arguments.get("label", "background job")
        if "max_seconds" in arguments:
            prepared["max_seconds"] = arguments["max_seconds"]
        if "max_output_bytes" in arguments:
            prepared["max_output_bytes"] = arguments["max_output_bytes"]
        return prepared

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolError("start_background_job requires the current session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        prepared = self.prepare_for_approval(arguments)
        label = prepared.pop("label", "background job")
        max_seconds = prepared.pop("max_seconds", 110)
        max_output_bytes = prepared.pop("max_output_bytes", 128 * 1024)
        prepared["timeout_seconds"] = max_seconds
        if not isinstance(label, str):
            raise ToolArgumentError("'label' must be a string")
        status = await self.manager.start(
            context.session_id,
            prepared,
            label,
            BackgroundJobLimits(max_seconds, max_output_bytes),
            causation_id=context.started_event_id,
            correlation_id=context.correlation_id,
        )
        return json_result(_status_document(status))


class BackgroundJobStatusTool:
    _spec = ToolSpec(
        name="background_job_status",
        description="Return the durable status of one background job.",
        input_schema={
            "type": "object",
            "properties": {"job_id": {"type": "string", "minLength": 1, "maxLength": 128}},
            "required": ["job_id"],
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.PROCESS_EXECUTE,
    )

    def __init__(self, manager: BackgroundJobManager) -> None:
        self.manager = manager

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolError("background_job_status requires the current session context")

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        job_id = _job_id(arguments)
        return json_result(_status_document(self.manager.status(context.session_id, job_id)))


class BackgroundJobLogsTool:
    _spec = ToolSpec(
        name="background_job_logs",
        description="Return bounded retained output from one background job.",
        input_schema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "max_bytes": {"type": "integer", "minimum": 1, "maximum": 1048576},
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
        side_effect="read_state",
        capability=Capability.PROCESS_EXECUTE,
    )

    def __init__(self, manager: BackgroundJobManager) -> None:
        self.manager = manager

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolError("background_job_logs requires the current session context")

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        job_id = _job_id(arguments)
        max_bytes = arguments.get("max_bytes", 128 * 1024)
        if type(max_bytes) is not int or not 1 <= max_bytes <= 1048576:
            raise ToolArgumentError("'max_bytes' must be from 1 to 1048576")
        return json_result(self.manager.logs(context.session_id, job_id, max_bytes=max_bytes))


class StopBackgroundJobTool:
    _spec = ToolSpec(
        name="stop_background_job",
        description="Stop one running background job and its process tree.",
        input_schema=BackgroundJobStatusTool._spec.input_schema,
        side_effect="process",
        capability=Capability.PROCESS_EXECUTE,
    )

    def __init__(self, manager: BackgroundJobManager) -> None:
        self.manager = manager

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolError("stop_background_job requires the current session context")

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        job_id = _job_id(arguments)
        return json_result(_status_document(await self.manager.stop(context.session_id, job_id)))


def _job_id(arguments: dict[str, Any]) -> str:
    value = arguments.get("job_id")
    if not isinstance(value, str) or not value:
        raise ToolArgumentError("'job_id' is required")
    return value


def _status_document(status: Any) -> dict[str, Any]:
    return {
        "job_id": status.job_id,
        "session_id": status.session_id,
        "label": status.label,
        "state": status.state,
        "created_at": status.created_at,
        "updated_at": status.updated_at,
        "result": status.result,
        "terminal_reason": status.terminal_reason,
    }
