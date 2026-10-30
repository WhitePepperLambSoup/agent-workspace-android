"""What an expert team gets on this computer for code, beyond the shared expert library (which the
phone uses as well): more tools for the experts and a note on how to use them.

The library lets an expert run commands through run_process, which a conversation in YOLO does
not have: there commands run in the sandbox, so an expert who may run commands gets the sandbox's
tools too. Experts who write code also get the coding desk (the language server, the project's
checks, the debugger) in place of the library's research tools, and the lead hands out code by
what can be built and tested on its own.
"""

from __future__ import annotations

from agent_workspace.core.expert_library import EXPERTS
from agent_workspace.core.experts import Expert, expert_goal

SANDBOX_TOOLS = ("run_sandbox", "sandbox_status", "apply_sandbox_change")
DESK_TOOLS = (
    "code_diagnostics",
    "find_definition",
    "find_references",
    "list_symbols",
    "run_checks",
    "debug_python",
)
# Web pages and Linux commands, for the experts whose parts need them.
_MORE_TOOLS: dict[str, tuple[str, ...]] = {
    "engineer": ("check_page", "run_wsl"),
    "frontend": ("check_page",),
    "qa": ("check_page",),
    "backend": ("run_wsl",),
    "devops": ("run_wsl",),
}
# Papers and references are not what a software engineer works from; run_diagnostics needs the
# language server's command, which code_diagnostics finds itself.
_NOT_FOR_CODE = frozenset(
    {
        "paper_search",
        "paper_lookup",
        "read_paper",
        "list_research_sources",
        "read_research_source",
        "reference_library",
        "list_citations",
        "check_references",
        "science_*",
        "run_diagnostics",
    }
)
_DATA_CODERS = frozenset({"ml_engineer", "llm_engineer", "data_engineer"})

CODE_METHOD = (
    "On this computer: find code by symbol (list_symbols, find_definition, find_references) "
    "rather than reading whole files. Before you change behaviour, run the tests that cover it, "
    "or a small one that shows the problem, so you know what fails. An edit reports the "
    "language server's errors in the file; code_diagnostics checks others. When a result is "
    "wrong and one reading of the code does not show why, debug_python stops at a line and "
    "shows the variables; use it instead of adding prints. Run commands with run_process, or "
    "run_sandbox where run_process is not offered. A change to code takes the tool calls it "
    "needs; reply with the command you ran last and its result."
)

LEAD_CODE_NOTE = (
    "Code on this computer: the experts can run code and tests as you can. Give an expert a "
    "part of a code change only when it can be built and tested on its own (a module with its "
    "tests, a bug in files nobody else edits); name the files it owns and the test command that "
    "shows it works, and do the rest yourself. An expert who reviews code gets the files and the "
    "tests to run, and reports each failure with the command that shows it."
)


def writes_code(expert_id: str | None) -> bool:
    item = EXPERTS.get(expert_id or "")
    return item is not None and (item.domain == "software" or item.id in _DATA_CODERS)


def team_tools(expert_id: str | None, tools: frozenset[str] | None) -> frozenset[str] | None:
    """An expert's tools on this computer, from the library's (None: no limit)."""
    if tools is None:
        return None
    extra: tuple[str, ...] = SANDBOX_TOOLS if "run_process" in tools else ()
    item = EXPERTS.get(expert_id or "")
    if item is not None and writes_code(item.id):
        extra += DESK_TOOLS + _MORE_TOOLS.get(item.id, ())
        tools -= _NOT_FOR_CODE if item.domain == "software" else {"run_diagnostics"}
    return tools | frozenset(extra)


def team_goal(expert: Expert, goal: str) -> str:
    """A delegated task's goal as the expert gets it here: the library's, with the coding method
    after the brief of an expert who writes code."""
    if writes_code(expert.id):
        expert = Expert(expert.id, expert.name, f"{expert.brief} {CODE_METHOD}")
    return expert_goal(expert, goal)


def team_lead_note(note: str) -> str:
    """The lead's note for a team turn here."""
    return f"{note}\n{LEAD_CODE_NOTE}"


__all__ = [
    "CODE_METHOD",
    "DESK_TOOLS",
    "LEAD_CODE_NOTE",
    "SANDBOX_TOOLS",
    "team_goal",
    "team_lead_note",
    "team_tools",
    "writes_code",
]
