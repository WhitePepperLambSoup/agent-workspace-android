"""run_wsl: the agent runs a command in Linux (WSL) in the open folder, for projects that build or
test there (a Makefile, shell scripts, a Linux-only toolchain)."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import (
    ToolArgumentError,
    ToolError,
    json_result,
    validate_tool_arguments,
)
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

from .shell import wsl_distributions, wsl_environment, wsl_output

MAX_OUTPUT_CHARS = 20_000
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _tail(text: str) -> str:
    return text if len(text) <= MAX_OUTPUT_CHARS else "… (start cut)\n" + text[-MAX_OUTPUT_CHARS:]


class RunWslTool:
    _spec = ToolSpec(
        name="run_wsl",
        description=(
            "Run a shell command in Linux (Windows Subsystem for Linux) in a folder of the "
            "project, for projects that build, test or run there: make, shell scripts, a Linux "
            "toolchain, Docker inside WSL. The folder is the same files seen from Linux "
            "(/mnt/c/...). bash -lc runs the command, so pipes and && work. distro picks a "
            "distribution (the default one otherwise). Returns the exit code and the output."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "minLength": 1, "maxLength": 4000},
                "cwd": {"type": "string", "maxLength": 500},
                "distro": {"type": "string", "minLength": 1, "maxLength": 100},
                "timeout": {"type": "integer", "minimum": 1, "maximum": 1800},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        side_effect="process",
        capability=Capability.PROCESS_EXECUTE,
    )

    def __init__(
        self, workspace: Path, *, which: Callable[[str], str | None] = shutil.which
    ) -> None:
        self.paths = WorkspacePaths(workspace)
        self._which = which

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        wsl = self._which("wsl")
        if wsl is None:
            raise ToolError("WSL is not installed on this computer (wsl.exe not found)")
        distributions = await asyncio.to_thread(wsl_distributions, wsl)
        if not distributions:
            raise ToolError("WSL has no Linux distribution installed (wsl --install sets one up)")
        distro = arguments.get("distro")
        if distro is not None and distro not in distributions:
            raise ToolArgumentError(
                f"no WSL distribution named {distro!r}; there are: {', '.join(distributions)}"
            )
        try:
            folder = self.paths.resolve(str(arguments.get("cwd") or "."))
        except WorkspacePathError as error:
            raise ToolArgumentError(str(error)) from None
        argv = [
            wsl,
            *(["-d", distro] if distro else []),
            "--cd",
            str(folder),
            "--",
            "bash",
            "-lc",
            arguments["command"],
        ]
        seconds = int(arguments.get("timeout", 300))
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                argv,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=seconds,
                env=wsl_environment(),
                check=False,
                creationflags=_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as error:
            output = wsl_output(error.stdout or b"") + wsl_output(error.stderr or b"")
            return json_result({"timed_out": True, "seconds": seconds, "output": _tail(output)})
        except OSError as error:
            raise ToolError(f"wsl could not be started: {error}") from None
        return json_result(
            {
                "exit_code": completed.returncode,
                "distro": distro or "(default)",
                "stdout": _tail(wsl_output(completed.stdout)),
                "stderr": _tail(wsl_output(completed.stderr)),
            }
        )


__all__ = ["RunWslTool"]
