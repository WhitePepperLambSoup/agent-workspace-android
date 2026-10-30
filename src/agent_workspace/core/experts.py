"""Expert teams: the conversation's agent leads a few named experts who work a request together.

A team turn makes the agent the team's lead, the way multi-agent assistants split a question
among specialists: it divides the request, hands each expert its part through delegate_tasks
(the experts work at the same time, each as its own agent run), has them review each other's
findings, and writes the answer from what holds up. The team is either picked by the lead for
each request from the expert library (core.expert_library), or fixed by the user: experts from
the library, and any of their own with a name and a brief.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from agent_workspace.core.expert_library import (
    EXPERTS,
    REPLY_RULE,
    WORKING_RULES,
    library_catalog,
)

MAX_EXPERTS = 4
_MAX_NAME = 24
_MAX_BRIEF = 1200
_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")


@dataclass(frozen=True, slots=True)
class Expert:
    id: str
    # What the user calls them; the model uses it as the task title.
    name: str
    brief: str


@dataclass(frozen=True, slots=True)
class Team:
    """Who may work on a team turn; with ``auto`` the lead picks from the whole library."""

    experts: tuple[Expert, ...]
    auto: bool = False


# Every library expert's brief by id.
BUILT_IN_BRIEFS: Mapping[str, str] = {expert_id: item.brief for expert_id, item in EXPERTS.items()}


class ExpertError(ValueError):
    """The team as sent cannot be used; the message says why."""


def _library_team() -> Team:
    return Team(
        tuple(Expert(item.id, item.names[2], item.brief) for item in EXPERTS.values()), auto=True
    )


def parse_team(raw: object) -> Team:
    """The team of a turn: ``"auto"``, or ``[{id, name, brief?}]`` (library ids bring a brief)."""
    if raw == "auto":
        return _library_team()
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_EXPERTS:
        raise ExpertError(f"a team is 'auto' or 1 to {MAX_EXPERTS} experts")
    experts: list[Expert] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ExpertError("each expert must be an object")
        expert_id = item.get("id")
        if not isinstance(expert_id, str) or not _ID.fullmatch(expert_id):
            raise ExpertError("an expert id is 1 to 32 lowercase letters, digits, '-' or '_'")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > _MAX_NAME:
            raise ExpertError(f"an expert name is 1 to {_MAX_NAME} characters")
        brief = item.get("brief")
        if brief is None:
            brief = BUILT_IN_BRIEFS.get(expert_id)
            if brief is None:
                raise ExpertError(f"expert {expert_id!r} needs a brief")
        elif not isinstance(brief, str) or not brief.strip() or len(brief) > _MAX_BRIEF:
            raise ExpertError(f"an expert brief is 1 to {_MAX_BRIEF} characters")
        experts.append(Expert(expert_id, " ".join(name.split()), brief.strip()))
    if len({expert.id for expert in experts}) != len(experts):
        raise ExpertError("each expert needs its own id")
    if len({expert.name.casefold() for expert in experts}) != len(experts):
        raise ExpertError("each expert needs its own name")
    return Team(tuple(experts))


def lead_instructions(team: Team, *, review: bool) -> str:
    """The system note that makes the conversation's agent the team's lead for one turn."""
    if team.auto:
        pick = (
            "1. Pick the team from the expert library below: the fewest experts the request "
            "needs. If you can answer it reliably yourself in a few lines (one short calculation "
            "whose method surely fits the case, a definition, a sentence to translate), answer "
            "directly without the team and say so in one line. One expert for a task within a "
            "single skill (a document to translate, a notice to draft, a function to write); two "
            "or three for most questions; four only "
            "when four distinct fields really matter. Prefer the narrowest specialist that fits "
            "over a generalist (a labour "
            "dispute needs labor_law, not legal); never two experts for the same field. Add "
            "critic only when the user faces a consequential decision (money, health, legal "
            "exposure) where being wrong is costly, not for drafting or explaining. A "
            "calculation, derivation or simulation you can run with your own tools, and a change "
            "to one codebase, are best done by you or one specialist. When whether the method or "
            "the user's premise fits the case is itself in question (conditions near the edge of "
            "a model's validity, a source or figure that may not exist), have the specialist of "
            "that field check it. Add experts only for parts "
            "that need another field or can be worked separately at the same time (independent "
            "modules, a literature check beside a computation). Then split the request: decide "
            "what each chosen expert should find out, work through or check."
        )
        title = "'title' their name in the user's language"
        roster = "The expert library (id, name: scope):\n" + library_catalog()
    else:
        pick = (
            "1. Split the request: decide what each expert should find out, work through or "
            "check. Leave out an expert with nothing to add, but use at least two (or all of "
            "them if the team is smaller)."
        )
        title = "'title' their name"
        roster = "The experts:\n" + "\n".join(
            f"- {expert.id} ({expert.name}): {expert.brief}" for expert in team.experts
        )
    steps = [
        pick,
        f"2. Call delegate_tasks once with one task per expert: 'expert' is the expert's id and "
        f"{title}. Each goal stands on its own: the user's question with the facts they gave, "
        "this expert's part, and the findings you need back (short, not a full report). Shared "
        "facts go in 'context'. The experts "
        "work at the same time and do not see this conversation. Experts who change files get "
        "files or modules of their own, never the same file; when they are done, run the whole "
        "test suite yourself and fix what fails before you answer.",
    ]
    if review:
        steps.append(
            "3. Review your draft when the answer carries several figures, the findings conflict, "
            "or the user faces a consequential decision: call delegate_tasks again with one "
            "reviewer, the critic, or the expert best placed to judge it (their same 'expert' and "
            "'title'), and put your full draft answer in its goal, not in your reply. "
            "The goal holds "
            "the user's question, the experts' key findings and your whole draft, and asks the "
            "reviewer to recompute every figure, check each claim against the findings, and list "
            "contradictions between figures, errors, overstatements and gaps. Otherwise skip it. "
            "Weigh the review against what the user asked for: fix errors, but do not give up a "
            "stated requirement (speed, simplicity, length) for cases the user did not raise."
        )
    steps.append(
        f"{len(steps) + 1}. Answer the user yourself from the findings that hold up, with the "
        "reviewer's corrections: the conclusion first, then the reasons, the figures and sources "
        "the experts found, where they disagreed and how you decided, and what is still "
        "uncertain. State only figures the experts or the reviewer worked out or that you "
        "recomputed, and make them agree with each other (totals, ratios, payback, thresholds). "
        "Keep the experts' specifics (article numbers, steps, code) instead of summarising them "
        "away; give a requested deliverable (translation, draft, code) in full, and nothing the "
        "user did not ask for. Do not state as absolute what has exceptions. A shorter answer "
        "with nothing wrong beats a longer one with a doubtful detail: leave out what neither the "
        "experts nor the reviewer could check; for a plan or design, give the key decisions with "
        "their reasons rather than a long schedule. Check your own figures once by an "
        "independent route (a limiting case, substituting back, a second formula, the tests); "
        "repeat an analysis at finer settings only when that check disagrees or the user asked "
        "for it. Keep the user's stated requirements (speed, limits, length) for ordinary inputs; "
        "a rare input gets its special handling alone. Name the expert behind a key point only "
        "where it helps the reader."
    )
    return (
        "Expert team: for this request you lead a team of experts and do not answer alone. "
        "Work in these steps:\n"
        + "\n".join(steps)
        + "\nIf delegate_tasks is not available or fails, say so and answer as well as you can.\n"
        + roster
    )


def expert_goal(expert: Expert, goal: str) -> str:
    """A delegated task's goal as the expert gets it: who they are, how they work, their part."""
    return (
        f"You are the team's {expert.name}. {expert.brief}\n{WORKING_RULES}\n\nYour part:\n{goal}"
        f"\n\n{REPLY_RULE}"
    )


def find_expert(team: Team, key: str | None) -> Expert | None:
    """The team's expert by id, or by name as the model may write it."""
    if not key:
        return None
    folded = key.strip().casefold()
    found = next(
        (expert for expert in team.experts if folded in {expert.id, expert.name.casefold()}), None
    )
    if found is None and team.auto:
        # The lead may write a library expert's name in the user's language.
        item = next(
            (
                item
                for item in EXPERTS.values()
                if folded in {name.casefold() for name in item.names}
            ),
            None,
        )
        if item is not None:
            found = Expert(item.id, item.names[2], item.brief)
    return found
