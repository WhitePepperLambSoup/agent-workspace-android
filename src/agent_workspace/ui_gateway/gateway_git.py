"""The Changes page's Git tab: the branch, a new branch for a task, a commit message from the
model, merge conflicts, CI runs with their failed log, and the repository's open issues."""

from __future__ import annotations

from typing import Any

from agent_workspace.coding.git_flow import GitFlow, GitFlowError
from agent_workspace.ui_gateway.gateway_common import GatewayError, GatewayReply
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import CommandEnvelope

GIT_COMMANDS = frozenset(
    {
        "git.status",
        "git.branch.create",
        "git.branch.switch",
        "git.message",
        "git.conflict.take",
        "git.conflict.resolved",
        "git.finish",
        "git.ci.runs",
        "git.ci.log",
        "git.issues",
        "git.issue",
    }
)
# The model writes the commit message: with the other model calls.
GIT_MODEL_COMMANDS = frozenset({"git.message"})
# GitHub over the network (seconds, up to a minute and a half for a log): their own threads.
GIT_GITHUB_COMMANDS = frozenset({"git.ci.runs", "git.ci.log", "git.issues", "git.issue"})
# Local git: off the reader thread, with the other queries.
GIT_QUERY_COMMANDS = GIT_COMMANDS - GIT_MODEL_COMMANDS - GIT_GITHUB_COMMANDS
# Failures whose git or gh message tells the user what to do: answered with it, not refused.
_TOLD_FAILURES = frozenset(
    {"switch_blocked", "finish_failed", "git_command_failed", "github_command_failed"}
)


def _text(payload: dict[str, Any], key: str, limit: int = 500) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise GatewayError("invalid_command")
    return value


class GitCommands(GatewayState):
    def _git_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        flow = GitFlow(self._open_folder())
        payload = command.payload
        try:
            result = self._git_dispatch(flow, command.type, payload)
        except GitFlowError as error:
            if error.code not in _TOLD_FAILURES:
                raise GatewayError(error.code) from None
            result = {"error": error.code, "detail": error.detail}
        return self._reply(f"{command.type}.result", result, session_id=None)

    def _git_dispatch(self, flow: GitFlow, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        if kind == "git.status":
            return {"status": flow.status()}
        if kind == "git.branch.create":
            return {"status": flow.create_branch(_text(payload, "name", 250))}
        if kind == "git.branch.switch":
            return {"status": flow.switch_branch(_text(payload, "name", 250))}
        if kind == "git.conflict.take":
            side = payload.get("side")
            return {"status": flow.take_side(_text(payload, "path"), str(side))}
        if kind == "git.conflict.resolved":
            return {"status": flow.mark_resolved(_text(payload, "path"))}
        if kind == "git.finish":
            return {"status": flow.finish(str(payload.get("action")))}
        if kind == "git.message":
            paths = payload.get("paths")
            language = payload.get("language", "en-US")
            if not isinstance(paths, list) or not paths or not isinstance(language, str):
                raise GatewayError("invalid_command")
            return {"message": flow.write_message(self._quick_provider(), paths, language)}
        if kind == "git.ci.runs":
            branch = payload.get("branch")
            if branch is not None and not isinstance(branch, str):
                raise GatewayError("invalid_command")
            return {"runs": flow.ci_runs(branch)}
        if kind == "git.ci.log":
            run = payload.get("run")
            if not isinstance(run, (int, str)) or isinstance(run, bool):
                raise GatewayError("invalid_command")
            return flow.ci_log(run)
        if kind == "git.issues":
            search = payload.get("search", "")
            if not isinstance(search, str):
                raise GatewayError("invalid_command")
            return {"issues": flow.issues(search)}
        if kind == "git.issue":
            number = payload.get("number")
            if type(number) is not int:
                raise GatewayError("invalid_command")
            return {"issue": flow.issue(number)}
        raise GatewayError("unknown_command")


__all__ = [
    "GIT_COMMANDS",
    "GIT_GITHUB_COMMANDS",
    "GIT_MODEL_COMMANDS",
    "GIT_QUERY_COMMANDS",
    "GitCommands",
]
