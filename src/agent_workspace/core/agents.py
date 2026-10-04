from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

StrPath = str | Path

_AGENT_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
_SUPPORTED_MODES = frozenset({"coding", "research", "task"})
MAX_AGENT_PROMPT_BYTES = 64 * 1024


class AgentDefinitionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    id: str
    name: str
    description: str
    system_prompt: str
    allowed_tools: tuple[str, ...]
    mode: str | None = None
    path: str = ""

    @property
    def tool_allowlist(self) -> frozenset[str] | None:
        return frozenset(self.allowed_tools) if self.allowed_tools else None


def _agent_files(workspace: StrPath) -> tuple[Path, ...]:
    root = Path(workspace)
    try:
        root = root.resolve(strict=True)
    except (OSError, RuntimeError):
        return ()
    directory = root / ".agent" / "agents"
    if not directory.is_dir():
        return ()
    return tuple(sorted(directory.glob("*.toml")))


def load_agents(workspace: StrPath) -> tuple[AgentDefinition, ...]:
    agents: list[AgentDefinition] = []
    for path in _agent_files(workspace):
        try:
            with path.open("rb") as stream:
                raw: object = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
            raise AgentDefinitionError(f"cannot read agent file {path}: {exc}") from None
        if not isinstance(raw, dict):
            raise AgentDefinitionError(f"agent file {path} must contain a table")
        agent_id = raw.get("id")
        name = raw.get("name")
        description = raw.get("description")
        system_prompt = raw.get("system_prompt")
        allowed_tools = raw.get("allowed_tools", [])
        mode = raw.get("mode")
        if (
            not isinstance(agent_id, str)
            or _AGENT_ID_PATTERN.fullmatch(agent_id) is None
            or not isinstance(name, str)
            or not name.strip()
            or len(name) > 200
            or not isinstance(description, str)
            or len(description) > 4000
            or not isinstance(system_prompt, str)
            or not system_prompt.strip()
            or len(system_prompt.encode("utf-8")) > MAX_AGENT_PROMPT_BYTES
            or not isinstance(allowed_tools, list)
            or any(
                not isinstance(tool, str) or not tool.strip() or len(tool) > 128
                for tool in allowed_tools
            )
            or len({tool.strip() for tool in allowed_tools}) != len(allowed_tools)
            or (mode is not None and mode not in _SUPPORTED_MODES)
        ):
            raise AgentDefinitionError(f"agent file {path} contains invalid fields")
        if any(agent.id == agent_id for agent in agents):
            raise AgentDefinitionError(f"agent id {agent_id!r} is duplicated")
        agents.append(
            AgentDefinition(
                id=agent_id,
                name=name.strip(),
                description=description.strip(),
                system_prompt=system_prompt.strip(),
                allowed_tools=tuple(tool.strip() for tool in allowed_tools),
                mode=mode,
                path=str(path),
            )
        )
    return tuple(agents)


def find_agent(workspace: StrPath, agent_id: str) -> AgentDefinition | None:
    if _AGENT_ID_PATTERN.fullmatch(agent_id) is None:
        return None
    for agent in load_agents(workspace):
        if agent.id == agent_id:
            return agent
    return None
