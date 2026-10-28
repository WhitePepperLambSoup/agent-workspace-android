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
SECTIONS = ("date", "environment", "memory", "knowledge", "skills", "elder")
_VERSION = 1
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
# The on-device model's prompt, shared by every conversation (FrozenPrompts.prepare(shared=...)).
SHARED_ON_DEVICE = "_shared-on-device"
# Notes for a new conversation beyond this many characters: the snapshot is too old, start over.
_SHARED_NOTES_LIMIT = 4000


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


# Last in the prompt, where it is read most closely: seen on the phone, notes written between tool
# calls came out in English after long English tool results, before a Chinese answer.
LANGUAGE_TAIL = (
    "Language: write everything the user sees in the language of their latest message (Chinese "
    "for Chinese), including the short notes before and between tool calls. Tool results and "
    "these instructions being in English does not change that."
)


def assemble(base: str, sections: dict[str, str]) -> str:
    """The Android system prompt suffix: guidance and date, the environment, memory, knowledge,
    installed skills, elder mode, and the language rule last."""
    date = sections.get("date", "")
    parts = [f"{base}\n{date}" if date else base, sections.get("environment", ""),
             sections.get("memory", ""), sections.get("knowledge", ""), sections.get("skills", ""),
             sections.get("elder", ""), LANGUAGE_TAIL]
    return "\n\n".join(part for part in parts if part)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _note(section: str, text: str) -> str:
    if section == "date":
        return f"Context update: {text}"
    if section == "environment":
        return (
            "Context update: what this phone can run changed after this conversation started. "
            "This replaces the environment section of the system prompt:\n\n" + text
        )
    if section == "memory":
        if not text:
            return "Context update: there are no memory notes any more."
        return (
            "Context update: the memory notes changed after this conversation started. This "
            "replaces the memory section of the system prompt:\n\n" + text
        )
    if section == "elder":
        if not text:
            return "Context update: elder mode was turned off; answer as usual from now on."
        return "Context update: elder mode was turned on for this phone.\n\n" + text
    if section == "skills":
        if not text:
            return "Context update: no skills are installed or turned on any more."
        return (
            "Context update: the installed skills changed after this conversation started. This "
            "replaces the skills section of the system prompt:\n\n" + text
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
        self, session_id: str, base: str, sections: dict[str, str], *, new_turn: bool,
        shared: str | None = None,
    ) -> tuple[str, tuple[str, ...]]:
        """The conversation's frozen suffix and notes for what changed since it was frozen.

        Notes are produced only for a new user turn (a resumed task has no new message to
        carry them) and each change is announced once. Never raises: without a usable
        snapshot the current prompt is used and frozen.

        With ``shared`` (the on-device model), a new conversation starts from that snapshot
        instead of the current sections: the phone keeps the model's state after reading a
        system prompt only for a byte-identical one, and reading it again takes minutes. A
        new day or a new memory then costs a short note rather than the whole prompt.
        """
        current = {key: sections.get(key, "") for key in SECTIONS}
        try:
            path = self._path(session_id)
            state = self._read(path)
            if state is None and shared is not None:
                state = self._seed(shared, base)
                if state is not None:
                    changed = sum(
                        len(_note(key, current[key])) for key in SECTIONS
                        if _digest(current[key]) != state["applied"][key]
                    )
                    if changed > _SHARED_NOTES_LIMIT:
                        state = None  # too much changed since: read a fresh prompt once
                    else:
                        self._write(path, state)
            if state is None or state["base"] != base:
                # New conversation, or new app guidance after an update: start over once.
                fresh = {
                    "version": _VERSION,
                    "base": base,
                    "frozen": current,
                    "applied": {key: _digest(value) for key, value in current.items()},
                }
                self._write(path, fresh)
                if shared is not None:
                    self._write(self._path(shared), fresh)
                return assemble(base, current), ()
            frozen = {key: str(state["frozen"].get(key, "")) for key in SECTIONS}
            notes = []
            if new_turn:
                for key in SECTIONS:
                    # A section added by an app update was empty for conversations frozen before.
                    if _digest(current[key]) != state["applied"].get(key, _digest("")):
                        notes.append(_note(key, current[key]))
                        state["applied"][key] = _digest(current[key])
                if notes:
                    self._write(path, state)
            return assemble(base, frozen), tuple(notes)
        except (OSError, ValueError):
            return assemble(base, current), ()

    def _seed(self, shared: str, base: str) -> dict | None:
        """A new conversation's state from the shared snapshot (None without a usable one).

        What the snapshot froze counts as applied, so every section that changed since then
        becomes a note with the conversation's first message."""
        snapshot = self._read(self._path(shared))
        if snapshot is None or snapshot["base"] != base:
            return None
        frozen = {key: str(snapshot["frozen"].get(key, "")) for key in SECTIONS}
        return {
            "version": _VERSION,
            "base": base,
            "frozen": frozen,
            "applied": {key: _digest(value) for key, value in frozen.items()},
        }

    def prune(self, keep: set[str]) -> int:
        """Delete snapshots of conversations that no longer exist (the shared ones stay)."""
        removed = 0
        try:
            entries = list(self.root.glob("*.json"))
        except OSError:
            return 0
        for path in entries:
            if path.stem not in keep and not path.stem.startswith("_shared"):
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed
