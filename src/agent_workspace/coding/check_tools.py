"""The agent's run_checks: the project's own checks (tests, type check, lint), as the user set
them up, with what failed."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolError, json_result, validate_tool_arguments

from .project import (
    CheckResult,
    ProjectConfigError,
    TrustBook,
    detect_checks,
    load_config,
    run_checks,
)

_OUTPUT_CHARS = 3000


class RunChecksTool:
    _spec = ToolSpec(
        name="run_checks",
        description=(
            "Run the project's checks (its tests, type check, lint: the commands the user set "
            "up for this folder) and get which failed with the end of their output. Run them "
            "before saying the work is done; fix what fails rather than weakening the checks. "
            "name runs one check only."
        ),
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string", "minLength": 1, "maxLength": 60}},
            "additionalProperties": False,
        },
        side_effect="process",
        capability=Capability.PROCESS_EXECUTE,
    )

    def __init__(
        self,
        workspace: Path,
        trust: TrustBook,
        report: Callable[[Path, list[CheckResult]], None] | None = None,
    ) -> None:
        self.root = workspace
        self.trust = trust
        # Tells the window of the results, as if the checks had been run from it.
        self.report = report

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        try:
            config = load_config(self.root)
        except ProjectConfigError as error:
            raise ToolError(f".agent/project.json cannot be read: {error}") from None
        if config is None or not config.checks:
            suggested = [item.to_dict() for item in detect_checks(self.root)]
            return json_result(
                {
                    "configured": False,
                    "note": (
                        "No checks are set up for this folder. Run the project's tests with "
                        "run_process (run_sandbox where run_process is not offered) instead; the "
                        "user can set up checks in the Changes page."
                    ),
                    "suggested": suggested,
                }
            )
        if not self.trust.trusted(self.root, config):
            raise ToolError(
                "the folder's checks come from .agent/project.json and the user has not accepted "
                "them yet (Changes page); run the tests with run_process (or run_sandbox) "
                "meanwhile"
            )
        name = arguments.get("name")
        checks = [check for check in config.checks if name is None or check.name == name]
        if not checks:
            names = ", ".join(check.name for check in config.checks)
            raise ToolError(f"there is no check named {name!r}; the checks are: {names}")
        results = await asyncio.to_thread(run_checks, self.root, checks)
        if self.report is not None:
            self.report(self.root, results)
        return json_result(
            {
                "passed": all(result.ok for result in results),
                "checks": [
                    {
                        "name": result.name,
                        "command": result.command,
                        "ok": result.ok,
                        "exit_code": result.exit_code,
                        "seconds": round(result.seconds, 1),
                        **({} if result.ok else {"output": result.output[-_OUTPUT_CHARS:]}),
                    }
                    for result in results
                ],
            }
        )


__all__ = ["RunChecksTool"]
