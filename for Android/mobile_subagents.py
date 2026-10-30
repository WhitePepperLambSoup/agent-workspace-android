"""Helper agents for independent parts of a task (the run_subagents tool).

A task can hand up to four separate pieces of work (read these files, look up these sources,
compare these options) to helpers that work side by side, at most three at a time, and hand back a
short report each; the task that started them combines the reports and does the rest.

Each helper works in a conversation of its own, titled 「子任务：…」 and archived, so it stays out of
the conversation list but can be opened to see what it did. Helpers only look: files and documents
in the workspace, the knowledge base, memory search, web search and web pages. They cannot change
files, run commands, operate the phone, read personal data (location, contacts, calendar,
notifications) or start helpers of their own. Their approvals are the parent task's: they show up
in its conversation, and "allow for this task" covers them. Requests to the model go out under the
parent conversation's grants: what it may send, they may send, and what the user allows for one
of them counts for the whole task.

On an expert team's task (core.experts) the helpers are the team's experts: the task's agent leads,
names an expert per part, and each helper gets that expert's brief and the looking tools of their
field. The first call hands out the parts, a later one is the review of the draft answer.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_workspace.core.budgets import TaskBudget
from agent_workspace.core.expert_library import expert_tools
from agent_workspace.core.experts import Team, expert_goal, find_expert, lead_instructions, parse_team
from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result

MAX_TASKS = 4
MAX_PARALLEL = 3
MAX_PROMPT_CHARS = 6000
MAX_CONTEXT_CHARS = 4000
MAX_REPORT_CHARS = 6000
# A helper is a short errand, not a second task: these keep a stuck one from running on.
HELPER_MODEL_CALLS = 24
HELPER_TOOL_CALLS = 40
HELPER_SECONDS = 600
# Remembered so usage can be shown as "sub-tasks" and the parent can be found from a helper.
_REGISTRY_LIMIT = 500

# Looking only: never files written, commands run, the phone operated, or personal data read.
# Network tools that only read (a search, a page, a paper's record). Each call still asks as it would
# for the task itself (once, or covered by "allow for this task"); http_request, which can POST, is
# left out.
_WEB_READING = frozenset({"web_search", "web_fetch", "paper_search", "paper_lookup", "check_references"})
_NOT_FOR_HELPERS = frozenset(
    {
        "run_subagents",
        "browser",
        "browser_view",
        "speak_text",
        "current_location",
        "find_contacts",
        "list_calendar_events",
        "recent_notifications",
        "active_notifications",
        "system_status",
        "android_battery",
        "android_clipboard",
        "memory_write",
    }
)

_HELPER_NOTE = (
    "[Helper] You are a helper working on one part of a larger task for another agent, which will "
    "use your report. You can only look: files and documents in the workspace, the knowledge base, "
    "memory, web search and web pages. You cannot change files, run commands, operate the phone "
    "or ask the user anything. Do the part below as well as you can, then reply with a concise "
    "report: what you found, with its sources (file paths and page numbers, or URLs), and what "
    "you could not find or verify. Nothing else. Write in the language of the part below."
)


@dataclass(slots=True)
class SubagentHost:
    """What a running task lends its helpers (bound by the runtime controller around a run)."""

    runtime: Any
    session: Any
    # The helpers' model (the helper role, else the task's) and the task's own model.
    model: str
    task_model: str = ""
    reasoning_effort: str | None = None
    summary_model: str | None = None
    # Spending checks of the parent task (mobile_task_limits); None when there is no limit.
    limits: Any | None = None
    started: list[str] = field(default_factory=list)
    # The task's expert team, if it has one, and how many times it was called on.
    team: Team | None = None
    rounds: int = 0
    # The knowledge base the user gave an expert (by expert id); the others use the task's.
    knowledge: dict[str, str] = field(default_factory=dict)
    # Told when an expert starts or ends their part: {session_id, expert, name, phase, state}.
    notify: Any | None = None


_HOST: contextvars.ContextVar[SubagentHost | None] = contextvars.ContextVar(
    "mobile_subagent_host", default=None
)


def bind_host(host: SubagentHost) -> contextvars.Token[SubagentHost | None]:
    return _HOST.set(host)


def reset_host(token: contextvars.Token[SubagentHost | None]) -> None:
    _HOST.reset(token)


def helper_tools(registry: Any) -> frozenset[str]:
    """The tools a helper gets: the ones that only look (web search and pages too), minus the
    phone and personal data."""
    tools = getattr(registry, "_tools", None) or {}
    return frozenset(
        name
        for name, tool in tools.items()
        if (
            getattr(getattr(tool, "spec", None), "side_effect", None) in ("none", "read")
            or name in _WEB_READING
        )
        and not name.startswith("android_")
        and name not in _NOT_FOR_HELPERS
    )


# --- helper conversations ------------------------------------------------------------------------

_registry_lock = threading.Lock()


def _registry_path() -> Path:
    return Path(os.getenv("AGENT_WORKSPACE_DATA_DIR") or ".") / "helper-sessions.json"


def helper_sessions() -> dict[str, str]:
    """Helper conversation id -> the conversation that started it. Never raises."""
    try:
        document = json.loads(_registry_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(document, dict):
        return {}
    return {
        key: value
        for key, value in document.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _remember(helper_id: str, parent_id: str) -> None:
    with _registry_lock:
        sessions = helper_sessions()
        sessions[helper_id] = parent_id
        while len(sessions) > _REGISTRY_LIMIT:
            sessions.pop(next(iter(sessions)))
        path = _registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(sessions), encoding="utf-8")
        os.replace(temporary, path)


_open_lock = threading.Lock()


def _share_knowledge(host: SubagentHost, helper_id: str, expert_id: str | None) -> None:
    """A helper searches the knowledge bases its task's conversation uses, or the one the user gave
    this expert (team settings)."""
    try:
        from mobile_knowledge import get_knowledge_store

        store = get_knowledge_store()
        known = {item["id"] for item in store.collections()}
        bound = host.knowledge.get(expert_id) if expert_id else None
        chosen = [bound] if bound in known else store.selected_collections(host.session.id)
        store.set_session_selection(helper_id, chosen)
    except Exception:
        pass  # it then searches the default knowledge bases


def _open_helper(host: SubagentHost, title: str, expert_id: str | None = None) -> Any:
    service = host.runtime.service
    session = service.create_session(
        host.session.workspace,
        mode=host.session.mode,
        autonomy=host.session.autonomy,
        title=f"子任务：{title}"[:80],
    )
    # Out of the conversation list, still there to open from the archive. The archive marks share
    # one file written compare-and-swap: helpers opening together take turns, and a write that lost
    # to another one (a rename in the app) is tried again.
    with _open_lock:
        for attempt in range(3):
            try:
                from mobile_workspace import save_session_archived

                save_session_archived(host.runtime, session.id, True)
                break
            except Exception:
                time.sleep(0.05 * (attempt + 1))
    try:
        _remember(session.id, host.session.id)
    except OSError:
        pass
    _share_knowledge(host, session.id, expert_id)
    policy = getattr(getattr(service, "runner", None), "_egress_policy", None)
    link = getattr(policy, "link_session", None)
    if callable(link):
        link(host.session.workspace, host.session.id, session.id)
    return session


def _note() -> str:
    today = datetime.now().astimezone()
    return f"{_HELPER_NOTE}\nToday is {today:%A %Y-%m-%d}."


def _expert_toolset(tools: frozenset[str], expert_id: str) -> frozenset[str]:
    """A library expert's tools of their field among the ones helpers may use (all of those for a
    custom expert, or when none of their field's tools is on the phone)."""
    wanted = expert_tools(expert_id)
    if wanted is None:
        return tools
    chosen = frozenset(
        name
        for name in tools
        if name in wanted or any(item.endswith("*") and name.startswith(item[:-1]) for item in wanted)
    )
    return chosen or tools


def _tell(host: SubagentHost, payload: dict[str, Any]) -> None:
    if host.notify is not None:
        try:
            host.notify(payload)
        except Exception:
            pass  # the expert list is shown from the tool's result as well


async def _run_one(
    host: SubagentHost,
    item: dict[str, str],
    tools: frozenset[str],
    expert: Any = None,
    phase: str | None = None,
) -> dict[str, Any]:
    title = item["title"]
    who = {"expert": expert.id, "name": expert.name, "phase": phase} if expert is not None else {}
    try:
        if host.limits is not None:
            host.limits.check()
        session = await asyncio.to_thread(_open_helper, host, title, expert.id if expert is not None else None)
    except Exception as exc:
        return {"title": title, **who, "status": "failed", "error": " ".join(str(exc).split())[:300]}
    host.started.append(session.id)
    if expert is not None:
        _tell(host, {"session_id": session.id, "title": title, **who, "state": "working"})
    outcome = await _helper_run(host, item, tools, session)
    if expert is not None:
        _tell(host, {"session_id": session.id, "title": title, **who, "state": outcome["status"]})
    return {"title": title, **who, **outcome}


async def _helper_run(
    host: SubagentHost, item: dict[str, str], tools: frozenset[str], session: Any
) -> dict[str, Any]:
    options: dict[str, Any] = {}
    if host.summary_model:
        options["summary_model"] = host.summary_model
    try:
        result = await host.runtime.service.run(
            session,
            item["prompt"],
            host.model,
            reasoning_effort=host.reasoning_effort,
            system_suffix=_note(),
            allowed_tools=tools,
            budget=TaskBudget(
                max_model_calls=HELPER_MODEL_CALLS,
                max_provider_attempts=HELPER_MODEL_CALLS,
                max_tool_calls=HELPER_TOOL_CALLS,
                max_turn_seconds=HELPER_SECONDS,
            ),
            include_skills=False,
            **options,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return {
            "status": "failed",
            "session_id": session.id,
            "error": " ".join(str(exc).split())[:300] or type(exc).__name__,
        }
    report = str(getattr(result, "text", "") or "").strip()
    clipped = len(report) > MAX_REPORT_CHARS
    return {
        "status": "done",
        "session_id": session.id,
        "report": report[:MAX_REPORT_CHARS] + ("\n…(clipped)" if clipped else ""),
    }


def _tasks(arguments: dict[str, Any]) -> list[dict[str, str]]:
    raw = arguments.get("tasks")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_TASKS:
        raise ToolArgumentError(f"'tasks' must list 1 to {MAX_TASKS} parts")
    context = arguments.get("context")
    if context is not None and (not isinstance(context, str) or len(context) > MAX_CONTEXT_CHARS):
        raise ToolArgumentError(f"'context' must be text of at most {MAX_CONTEXT_CHARS} characters")
    shared = f"Shared facts:\n{context.strip()}\n\n" if context and context.strip() else ""
    tasks: list[dict[str, str]] = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ToolArgumentError(f"part {index} must be an object with title and prompt")
        title = item.get("title")
        # 'goal' is the expert team's word for it (core.experts.lead_instructions).
        prompt = item.get("prompt", item.get("goal"))
        expert = item.get("expert")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT_CHARS:
            raise ToolArgumentError(f"part {index}: 'prompt' must be 1 to {MAX_PROMPT_CHARS} characters")
        if title is None:
            # Left out now and then (a team's review round on the phone): named after its goal.
            title = " ".join(prompt.split())[:40]
        if not isinstance(title, str) or not title.strip() or len(title) > 60:
            raise ToolArgumentError(f"part {index}: 'title' must be 1 to 60 characters")
        if expert is not None and (not isinstance(expert, str) or not expert.strip() or len(expert) > 60):
            raise ToolArgumentError(f"part {index}: 'expert' must be an expert's id")
        # Models put the facts in each part as often as beside the parts: both are taken.
        own = item.get("context")
        if own is not None and (not isinstance(own, str) or len(own) > MAX_CONTEXT_CHARS):
            raise ToolArgumentError(f"part {index}: 'context' must be text of at most {MAX_CONTEXT_CHARS} characters")
        facts = f"Facts for this part:\n{own.strip()}\n\n" if own and own.strip() else ""
        tasks.append({
            "title": " ".join(title.split()),
            "prompt": shared + facts + prompt.strip(),
            **({"expert": expert.strip()} if expert else {}),
        })
    return tasks


@dataclass(frozen=True, slots=True)
class TaskTeam:
    team: Team
    review: bool
    knowledge: dict[str, str]


def task_team(events: Any) -> TaskTeam | None:
    """The team of a task from its task.team event, or None."""
    for event in events:
        if getattr(event, "event_type", None) == "task.team":
            payload = event.payload or {}
            try:
                team = parse_team(payload.get("team"))
            except ValueError:
                return None
            knowledge = payload.get("knowledge")
            return TaskTeam(
                team,
                payload.get("review") is not False,
                {key: value for key, value in knowledge.items() if isinstance(key, str) and isinstance(value, str)}
                if isinstance(knowledge, dict)
                else {},
            )
    return None


_PROGRESS_LANGUAGES = {"zh": ("zh-CN", "专家团：", " · "), "en": ("en-US", "Expert team: ", " · "),
                       "ja": ("ja-JP", "専門家チーム：", " · "), "ko": ("en-US", "전문가 팀: ", " · ")}
_PROGRESS_WORDS = {
    "search": {"zh": "查资料", "en": "looking things up", "ja": "調べ物", "ko": "자료 찾는 중"},
    "read": {"zh": "看文件", "en": "reading", "ja": "資料を読む", "ko": "읽는 중"},
    "thinking": {"zh": "思考中", "en": "thinking", "ja": "考え中", "ko": "생각 중"},
    "done": {"zh": "完成", "en": "done", "ja": "完了", "ko": "완료"},
    "failed": {"zh": "出错了", "en": "failed", "ja": "エラー", "ko": "오류"},
}
_PROGRESS_SEARCH = ("web_", "paper_", "knowledge_", "memory_search", "check_references")


def team_progress(events: Any) -> dict[str, str] | None:
    """One line per language for a team task at work, for the engine's ongoing notification:
    each expert of the latest round and what they do ("研究员 查资料 · 分析师 完成")."""
    from agent_workspace.core.expert_library import EXPERTS, LOCALES
    from mobile_expert_names_ko import EXPERTS as KOREAN

    experts: dict[str, dict[str, Any]] = {}
    tools: dict[str, str] = {}
    for event in events:
        kind = getattr(event, "event_type", None)
        payload = getattr(event, "payload", None) or {}
        if kind == "task.team.expert" and isinstance(payload.get("expert"), str):
            experts[payload["expert"]] = payload
        elif kind == "task.subagent.step" and isinstance(payload.get("session_id"), str):
            tools[payload["session_id"]] = str(payload.get("tool") or "")
    if not experts:
        return None
    lines: dict[str, str] = {}
    for language, (locale, label, joiner) in _PROGRESS_LANGUAGES.items():
        parts = []
        for expert_id, payload in experts.items():
            item = EXPERTS.get(expert_id)
            if language == "ko" and expert_id in KOREAN:
                name = KOREAN[expert_id][0]
            elif item is not None:
                name = item.names[LOCALES.index(locale)]
            else:
                name = str(payload.get("name") or expert_id)
            state = payload.get("state")
            if state == "working":
                tool = tools.get(str(payload.get("session_id")), "")
                word = "search" if tool.startswith(_PROGRESS_SEARCH) else "read" if tool else "thinking"
            else:
                word = "done" if state == "done" else "failed"
            parts.append(f"{name} {_PROGRESS_WORDS[word][language]}")
        lines[language] = label + joiner.join(parts)
    return lines


def team_note(team: Team, review: bool) -> str:
    """The lead's instructions for this task, in the words of the phone's helper tool."""
    return (
        lead_instructions(team, review=review).replace("delegate_tasks", "run_subagents")
        + "\nOn this phone the experts can only look things up (files, documents, the knowledge "
        "base, the web); they cannot change files or run commands. Anything to compute, write or "
        "change, do yourself before you answer."
    )


class RunSubagentsTool:
    _SPEC = ToolSpec(
        name="run_subagents",
        description=(
            "Hand independent parts of the current task to helper agents that work at the same "
            f"time (up to {MAX_TASKS} parts, {MAX_PARALLEL} at once) and get a short report from "
            "each. Use it when the parts do not depend on each other and each needs several steps "
            "of looking: reading many files or documents, researching several sources, comparing "
            "options. Helpers can only read the workspace, documents, the knowledge base, memory "
            "and the web; they cannot change files, run commands, operate the phone or ask the "
            "user. Each prompt must stand alone: state the goal, what to look at and what to "
            "report, because a helper does not see this conversation. Do the rest yourself with "
            "their reports; check anything important before relying on it. On an expert team's "
            "task, 'expert' names the expert who does a part ('goal' may stand for 'prompt', and "
            "'context' holds facts every part shares)."
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
                            "title": {"type": "string", "minLength": 1, "maxLength": 60},
                            "prompt": {"type": "string", "minLength": 1, "maxLength": MAX_PROMPT_CHARS},
                            "goal": {"type": "string", "minLength": 1, "maxLength": MAX_PROMPT_CHARS},
                            "expert": {"type": "string", "minLength": 1, "maxLength": 60},
                            "context": {"type": "string", "maxLength": MAX_CONTEXT_CHARS},
                        },
                        "additionalProperties": False,
                    },
                },
                "context": {"type": "string", "maxLength": MAX_CONTEXT_CHARS},
            },
            "required": ["tasks"],
            "additionalProperties": False,
        },
        # The helpers only look; the model requests they make are approved like the parent's.
        side_effect="none",
        capability=Capability.WORKSPACE_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def execution_timeout_seconds(self, arguments: dict[str, Any]) -> float:
        """Room for each helper's own time limit, MAX_PARALLEL at a time (read by the runner, whose
        default of two minutes cut a team off while its experts waited for the user's approval)."""
        raw = arguments.get("tasks")
        count = min(len(raw), MAX_TASKS) if isinstance(raw, list) and raw else 1
        return float(-(-count // MAX_PARALLEL) * HELPER_SECONDS + 60)

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolError("helpers can only be started from a running task")

    async def execute_with_context(self, arguments: dict[str, Any], _context: Any) -> str:
        host = _HOST.get()
        if host is None:
            raise ToolError("helpers can only be started from a running task in this app")
        if host.session.id in helper_sessions():
            raise ToolError("a helper cannot start helpers of its own")
        tasks = _tasks(arguments)
        if host.limits is not None:
            host.limits.check()
        runner = getattr(host.runtime.service, "runner", None)
        tools = helper_tools(getattr(runner, "_tools", None))
        if not tools:
            raise ToolError("no read-only tools are available for helpers")
        phase = None
        if host.team is not None and any("expert" in item for item in tasks):
            # The first call hands out the parts, later ones review the draft answer.
            phase = "review" if host.rounds else "work"
            host.rounds += 1
        gate = asyncio.Semaphore(MAX_PARALLEL)

        async def bounded(item: dict[str, str]) -> dict[str, Any]:
            expert = find_expert(host.team, item.get("expert")) if host.team is not None else None
            if expert is not None:
                item = {**item, "prompt": expert_goal(expert, item["prompt"])}
            async with gate:
                return await _run_one(
                    host,
                    item,
                    _expert_toolset(tools, expert.id) if expert is not None else tools,
                    expert,
                    phase if expert is not None else None,
                )

        results = await asyncio.gather(*(bounded(item) for item in tasks))
        done = sum(1 for result in results if result["status"] == "done")
        return json_result(
            {
                "results": list(results),
                "note": (
                    f"{done} of {len(results)} helpers finished. Their reports are their own "
                    "findings: combine them, check what matters, and answer the user yourself."
                ),
            }
        )


__all__ = [
    "MAX_PARALLEL",
    "MAX_TASKS",
    "RunSubagentsTool",
    "SubagentHost",
    "TaskTeam",
    "bind_host",
    "helper_sessions",
    "helper_tools",
    "reset_host",
    "task_team",
    "team_note",
    "team_progress",
]
