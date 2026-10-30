"""Let the agent hand separate parts of a request to sub-agents that work at the same time.

The desktop supplies the launcher. Each task becomes an agent run with its own session (and
its own git worktree when asked for), listed on the Agent runs page and bound by the same
autonomy and approvals as the conversation. The call waits for every task and returns their
answers for the agent to combine. Sub-agents get no launcher, so they cannot delegate again.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result

MAX_TASKS = 4
_MAX_TITLE = 80
_MAX_GOAL = 8000
_MAX_CONTEXT = 8000
_MAX_EXPERT = 32
# Sub-agents can work for a long time; the call may wait up to the runner's ceiling.
_WAIT_SECONDS = 3600.0

type Isolation = Literal["shared", "worktree"]


@dataclass(frozen=True, slots=True)
class SubagentTask:
    title: str
    goal: str
    isolation: Isolation = "shared"
    # On an expert team's turn: the expert (id) who does the task.
    expert: str | None = None


@dataclass(frozen=True, slots=True)
class SubagentOutcome:
    run_id: str
    title: str
    # succeeded, failed, cancelled, or needs_attention (stopped for something only the user can do)
    state: str
    answer: str
    branch: str | None = None
    reason: str | None = None


class SubagentLaunchError(ToolError):
    """The sub-agents could not be started; the message says why."""


class SubagentLauncher(Protocol):
    async def run_tasks(
        self, parent_session_id: str, tasks: Sequence[SubagentTask]
    ) -> list[SubagentOutcome]: ...


def _text(value: object, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolArgumentError(f"{name!r} must be a non-empty string")
    if len(value) > limit:
        raise ToolArgumentError(f"{name!r} must be at most {limit} characters")
    return value.strip()


def parse_tasks(arguments: dict[str, Any]) -> list[SubagentTask]:
    raw_tasks = arguments.get("tasks")
    if not isinstance(raw_tasks, list) or not 1 <= len(raw_tasks) <= MAX_TASKS:
        raise ToolArgumentError(f"'tasks' must list 1 to {MAX_TASKS} tasks")
    context = arguments.get("context")
    shared = _text(context, "context", _MAX_CONTEXT) if context is not None else ""
    tasks: list[SubagentTask] = []
    for raw in raw_tasks:
        if not isinstance(raw, dict):
            raise ToolArgumentError("each task must be an object")
        isolation = raw.get("isolation", "shared")
        if isolation not in {"shared", "worktree"}:
            raise ToolArgumentError("'isolation' must be shared or worktree")
        goal = _text(raw.get("goal"), "goal", _MAX_GOAL)
        if shared:
            goal = f"{goal}\n\nBackground from the conversation:\n{shared}"
        expert = raw.get("expert")
        tasks.append(
            SubagentTask(
                _text(raw.get("title"), "title", _MAX_TITLE),
                goal,
                isolation,
                _text(expert, "expert", _MAX_EXPERT) if expert is not None else None,
            )
        )
    if len({task.title.casefold() for task in tasks}) != len(tasks):
        raise ToolArgumentError("each task needs its own title")
    return tasks


class DelegateTasksTool:
    hard_cancellable = False
    _SPEC = ToolSpec(
        name="delegate_tasks",
        description=(
            "Hand separate parts of the user's request to sub-agents that work at the same "
            "time, then use their answers in your reply. Use it when the request has two or "
            "more parts that do not depend on each other and each takes real work: researching "
            "several topics, reviewing or changing separate modules, drafting several documents, "
            "checking a change from different angles. Also use it whenever the user asks for "
            "sub-agents or for parts to be done in parallel. Otherwise do not use it for a single "
            "step, for quick lookups, or when parts must happen in order. Sub-agents do not see "
            "this conversation: give each task a complete goal with what to deliver and how to "
            "check it, and put shared facts in 'context'. They work in the same folder ('shared') "
            "unless two tasks change files that could collide; in a git repository 'worktree' "
            "gives a task its own copy on a separate branch, named in the result, which you then "
            "merge or report. The call waits until every task has finished. The user sees the "
            "sub-agents on the Agent runs page and answers their approvals in this conversation. "
            "When you lead an expert team, 'expert' names the expert (by id) who does a task."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_TASKS,
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "minLength": 1, "maxLength": _MAX_TITLE},
                            "goal": {"type": "string", "minLength": 1, "maxLength": _MAX_GOAL},
                            "isolation": {"type": "string", "enum": ["shared", "worktree"]},
                            "expert": {"type": "string", "minLength": 1, "maxLength": _MAX_EXPERT},
                        },
                        "required": ["title", "goal"],
                        "additionalProperties": False,
                    },
                },
                "context": {"type": "string", "minLength": 1, "maxLength": _MAX_CONTEXT},
            },
            "required": ["tasks"],
            "additionalProperties": False,
        },
        side_effect="write_state",
        # Splitting up work is planning, available wherever the to-do list is.
        capability=Capability.TODO,
    )

    def __init__(self, launcher: SubagentLauncher) -> None:
        self.launcher = launcher

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def execution_timeout_seconds(self, arguments: dict[str, Any]) -> float:
        return _WAIT_SECONDS

    async def execute(self, arguments: dict[str, Any]) -> str:
        raise ToolError("delegate_tasks runs only inside a conversation")

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        tasks = parse_tasks(arguments)
        outcomes = await self.launcher.run_tasks(context.session_id, tasks)
        return json_result(
            {
                "results": [
                    {
                        "title": outcome.title,
                        "state": outcome.state,
                        "answer": outcome.answer,
                        "run_id": outcome.run_id,
                        **({"branch": outcome.branch} if outcome.branch else {}),
                        **({"reason": outcome.reason} if outcome.reason else {}),
                    }
                    for outcome in outcomes
                ]
            }
        )
