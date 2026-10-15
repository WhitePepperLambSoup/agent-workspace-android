"""The AI card home-screen widget: the latest reply in the conversation of a schedule the user
chose ("显示在桌面卡片" in Scheduled tasks), such as the morning briefing.

The choice is kept in <data>/widget-card.json; when a task in that conversation finishes, its reply
(plain text, cards and markdown marks taken out) goes to the widget through AgentWidgets.publishCard.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any


def _path() -> Path:
    return Path(os.getenv("AGENT_WORKSPACE_DATA_DIR") or ".") / "widget-card.json"


def source() -> dict[str, str] | None:
    try:
        value = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(value, dict) and isinstance(value.get("session_id"), str) and value["session_id"]:
        return {"session_id": value["session_id"], "title": str(value.get("title") or "")[:80]}
    return None


def set_source(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("expected an object")
    session_id = payload.get("session_id")
    if session_id is None:
        _path().unlink(missing_ok=True)
        return {"source": None}
    if not isinstance(session_id, str) or not 1 <= len(session_id) <= 64:
        raise ValueError("session_id must be a conversation id")
    title = str(payload.get("title") or "")[:80]
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"session_id": session_id, "title": title}, ensure_ascii=False), encoding="utf-8")
    publish(title, f"下次「{title}」运行后，结果会显示在这里。" if title else "下次运行后，结果会显示在这里。", session_id)
    return {"source": source()}


def plain_text(markdown: str, limit: int = 400) -> str:
    """A reply as the widget shows it: no card or code blocks, no markdown marks, short."""
    text = re.sub(r"```card\s.*?```", "", markdown or "", flags=re.DOTALL)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}(#{1,6}|>|[-*+]|\d+\.)\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"(\*\*|__|`|~~)", "", text)
    text = re.sub(r"\n{2,}", "\n", text).strip()
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


def publish(title: str, text: str, session_id: str) -> bool:
    try:
        from java import jclass  # type: ignore[import-not-found]

        card = {"title": title, "text": text, "session_id": session_id, "at": int(time.time() * 1000)}
        return bool(jclass("com.agentworkspace.mobile.embedded.AgentWidgets").publishCard(json.dumps(card, ensure_ascii=False)))
    except Exception:
        return False


def task_finished(session_id: str, reply: str) -> bool:
    """A task in some conversation finished: if it is the card's, show its reply."""
    chosen = source()
    if chosen is None or chosen["session_id"] != session_id:
        return False
    text = plain_text(reply)
    return bool(text) and publish(chosen["title"], text, session_id)
