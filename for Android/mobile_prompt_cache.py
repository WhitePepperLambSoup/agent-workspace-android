"""Per-conversation system prompt snapshots for providers with prompt-prefix caching.

DeepSeek bills a cached prompt prefix at about 1/50 of the normal input price, others at 1/10 to
1/2, but only a byte-identical prefix counts. The Android system prompt carries today's date, the
memory notes and the knowledge-base list; rebuilding it whenever one of them changes made the next
request of every conversation miss the cache. Each conversation therefore keeps the prompt it
started with, and a later change reaches the model as a short note attached to the next user message.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

# Sections that may change during a conversation, in system prompt order.
SECTIONS = ("date", "memory", "knowledge")
_VERSION = 1
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


# Services that bill a repeated prompt prefix at a lower price. Most do it on their own (DeepSeek,
# OpenAI, Kimi, Qwen on DashScope, GLM, Gemini, Grok, and OpenRouter's upstreams); Anthropic needs
# cache breakpoints, which its provider adds to requests in this mode.
_PREFIX_CACHE_DOMAINS = (
    "deepseek.com",
    "openai.com",
    "moonshot.cn",
    "moonshot.ai",
    "dashscope.aliyuncs.com",
    "dashscope-intl.aliyuncs.com",
    "bigmodel.cn",
    "z.ai",
    "generativelanguage.googleapis.com",
    "x.ai",
    "anthropic.com",
    "openrouter.ai",
)


def prefix_cache_endpoint(base_url: str | None, model: str | None) -> bool:
    """True for providers that cache prompt prefixes (see ``_PREFIX_CACHE_DOMAINS``)."""
    host = (urlsplit(base_url or "").hostname or "").lower()
    if any(host == domain or host.endswith("." + domain) for domain in _PREFIX_CACHE_DOMAINS):
        return True
    return (model or "").lower().startswith("deepseek")


def assemble(base: str, sections: dict[str, str]) -> str:
    """The Android system prompt suffix: guidance and date, then memory, then knowledge."""
    date = sections.get("date", "")
    parts = [f"{base}\n{date}" if date else base, sections.get("memory", ""),
             sections.get("knowledge", "")]
    return "\n\n".join(part for part in parts if part)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _note(section: str, text: str) -> str:
    if section == "date":
        return f"Context update: {text}"
    if section == "memory":
        if not text:
            return "Context update: there are no memory notes any more."
        return (
            "Context update: the memory notes changed after this conversation started. This "
            "replaces the memory section of the system prompt:\n\n" + text
        )
    if not text:
        return (
            "Context update: the knowledge base is now empty or turned off; disregard the "
            "knowledge base section of the system prompt."
        )
    return (
        "Context update: the knowledge base changed after this conversation started. This "
        "replaces the knowledge base section of the system prompt:\n\n" + text
    )


class FrozenPrompts:
    """One small JSON file per conversation under <data>/cache/frozen-prompts."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def for_data_dir(cls) -> FrozenPrompts:
        data = os.getenv("AGENT_WORKSPACE_DATA_DIR")
        if not data:
            # Off the phone (tests, a desktop run) there is no app data folder; never write into
            # the working directory, which is usually the source tree.
            return cls(Path(tempfile.gettempdir()) / "agent-workspace-frozen-prompts")
        return cls(Path(data) / "cache" / "frozen-prompts")

    def _path(self, session_id: str) -> Path:
        if not _SESSION_ID.match(session_id):
            raise ValueError("session id is not a safe file name")
        return self.root / f"{session_id}.json"

    def _read(self, path: Path) -> dict | None:
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if (
            not isinstance(state, dict)
            or state.get("version") != _VERSION
            or not isinstance(state.get("base"), str)
            or not isinstance(state.get("frozen"), dict)
            or not isinstance(state.get("applied"), dict)
        ):
            return None
        return state

    def _write(self, path: Path, state: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)

    def prepare(
        self, session_id: str, base: str, sections: dict[str, str], *, new_turn: bool
    ) -> tuple[str, tuple[str, ...]]:
        """The conversation's frozen suffix and notes for what changed since it was frozen.

        Notes are produced only for a new user turn (a resumed task has no new message to
        carry them) and each change is announced once. Never raises: without a usable
        snapshot the current prompt is used and frozen.
        """
        current = {key: sections.get(key, "") for key in SECTIONS}
        try:
            path = self._path(session_id)
            state = self._read(path)
            if state is None or state["base"] != base:
                # New conversation, or new app guidance after an update: start over once.
                self._write(
                    path,
                    {
                        "version": _VERSION,
                        "base": base,
                        "frozen": current,
                        "applied": {key: _digest(value) for key, value in current.items()},
                    },
                )
                return assemble(base, current), ()
            frozen = {key: str(state["frozen"].get(key, "")) for key in SECTIONS}
            notes = []
            if new_turn:
                for key in SECTIONS:
                    if _digest(current[key]) != state["applied"].get(key):
                        notes.append(_note(key, current[key]))
                        state["applied"][key] = _digest(current[key])
                if notes:
                    self._write(path, state)
            return assemble(base, frozen), tuple(notes)
        except (OSError, ValueError):
            return assemble(base, current), ()

    def prune(self, keep: set[str]) -> int:
        """Delete snapshots of conversations that no longer exist."""
        removed = 0
        try:
            entries = list(self.root.glob("*.json"))
        except OSError:
            return 0
        for path in entries:
            if path.stem not in keep:
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed
