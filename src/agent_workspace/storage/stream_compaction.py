"""Blanking the streamed chunks of old turns whose messages hold their text.

A reply streams as many ``model.output.delta`` events, and the message that ends its model request
stores the same text again; the chunks were kept for good. A month after a turn completed, a pass
in the background blanks each chunk whose request's message holds its text in full, thinking
included. The chunk keeps its row, id, sequence number and type and says how many characters it
had (``compacted``), so the window, a resync, a replay or a fork shows what it showed before: they
take a request's text from its message, and a copy of a conversation takes the chunks' text back
from it (``restore_compacted_text``). A turn that failed, was cancelled or never ended keeps its
chunks, and so does a request whose message was cut off by a broken stream, joins the text of
several requests, or differs from what streamed.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from agent_workspace.core.events import Event
from agent_workspace.storage.sqlite import STREAM_COMPACTION_SCHEMA_VERSION

COMPACT_AFTER = timedelta(days=30)
_BUSY_TIMEOUT_MS = 5_000
# Turns per transaction: a writer of a running turn waits for one batch at most.
_TURNS_PER_BATCH = 20
_STREAM_KINDS = ("text", "reasoning")


def compact_finished_streams(
    database: str | Path,
    *,
    now: datetime | None = None,
    older_than: timedelta = COMPACT_AFTER,
    turns_per_batch: int = _TURNS_PER_BATCH,
    max_seconds: float | None = None,
    pause_seconds: float = 0.05,
) -> int:
    """Blank the chunks of turns that completed more than ``older_than`` ago; how many were.

    A few turns go per transaction with a pause between them, so a running turn waits for one
    batch at most; with ``max_seconds`` the pass stops after that and the next one goes on from
    there. Every turn looked at is recorded, so it is not read again.
    """
    database_path = Path(database).expanduser().resolve()
    if not database_path.is_file():
        return 0
    cutoff = ((now or datetime.now(UTC)) - older_than).isoformat()
    deadline = None if max_seconds is None else time.monotonic() + max_seconds
    connection = sqlite3.connect(
        str(database_path), timeout=_BUSY_TIMEOUT_MS / 1_000, isolation_level=None
    )
    connection.row_factory = sqlite3.Row
    blanked = 0
    try:
        connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA foreign_keys = ON")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if type(version) is not int or version < STREAM_COMPACTION_SCHEMA_VERSION:
            return 0  # the app migrates it when it opens it
        turns = connection.execute(
            """
            SELECT e.session_id, e.correlation_id, e.sequence
            FROM events AS e
            WHERE e.type = 'turn.completed'
              AND e.correlation_id IS NOT NULL
              AND e.created_at < ?
              AND NOT EXISTS (
                  SELECT 1 FROM compacted_turns AS c
                  WHERE c.session_id = e.session_id AND c.correlation_id = e.correlation_id
              )
            ORDER BY e.created_at, e.session_id, e.sequence
            """,
            (cutoff,),
        ).fetchall()
        for start in range(0, len(turns), turns_per_batch):
            if start and deadline is not None and time.monotonic() >= deadline:
                break
            compacted_at = datetime.now(UTC).isoformat()
            connection.execute("BEGIN IMMEDIATE")
            try:
                for turn in turns[start : start + turns_per_batch]:
                    blanked += _compact_turn(
                        connection, turn[0], turn[1], turn[2], compacted_at=compacted_at
                    )
                connection.commit()
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise
            time.sleep(pause_seconds)
    finally:
        connection.close()
    return blanked


def _compact_turn(
    connection: sqlite3.Connection,
    session_id: str,
    correlation_id: str,
    completed_sequence: int,
    *,
    compacted_at: str,
) -> int:
    started = connection.execute(
        """
        SELECT MIN(sequence) FROM events
        WHERE session_id = ? AND type = 'turn.started' AND correlation_id = ?
        """,
        (session_id, correlation_id),
    ).fetchone()[0]
    chunks = (
        _covered_chunks(connection, session_id, correlation_id, started, completed_sequence)
        if isinstance(started, int)
        else []
    )
    recorded = connection.execute(
        """
        INSERT INTO compacted_turns (
            session_id, correlation_id, text_chunks, reasoning_chunks, characters, compacted_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (session_id, correlation_id) DO NOTHING
        """,
        (
            session_id,
            correlation_id,
            sum(1 for _, kind, _ in chunks if kind == "text"),
            sum(1 for _, kind, _ in chunks if kind == "reasoning"),
            sum(length for _, _, length in chunks),
            compacted_at,
        ),
    )
    if recorded.rowcount != 1:
        return 0  # another pass got there first
    for event_id, _, _ in chunks:
        # The one update the events table takes (migration 28); it keeps the text's length.
        connection.execute(
            """
            UPDATE events
            SET data_json = json_set(
                data_json, '$.text', '', '$.compacted', length(json_extract(data_json, '$.text'))
            )
            WHERE id = ?
            """,
            (event_id,),
        )
    return len(chunks)


def _covered_chunks(
    connection: sqlite3.Connection,
    session_id: str,
    correlation_id: str,
    started: int,
    completed: int,
) -> list[tuple[str, str, int]]:
    """The turn's chunks (event id, kind, characters) that its messages hold in full."""
    streams: dict[tuple[str, str], list[tuple[str, str]]] = {}
    replies: dict[str, list[dict[str, Any]]] = {}
    unusable: set[str] = set()
    for row in connection.execute(
        """
        SELECT id, type, data_json, causation_id
        FROM events
        WHERE session_id = ? AND sequence BETWEEN ? AND ? AND correlation_id = ?
          AND type IN ('model.output.delta', 'message.created', 'turn.failed', 'turn.cancelled')
        ORDER BY sequence
        """,
        (session_id, started, completed, correlation_id),
    ):
        if row["type"] in ("turn.failed", "turn.cancelled"):
            return []
        data = json.loads(row["data_json"])
        request = row["causation_id"]
        if not isinstance(data, dict) or not isinstance(request, str):
            continue
        if row["type"] == "message.created":
            if data.get("role") == "assistant" and data.get("model_request_id") == request:
                replies.setdefault(request, []).append(data)
            continue
        kind = data.get("kind")
        text = data.get("text")
        if (
            data.get("model_request_id") != request
            or kind not in _STREAM_KINDS
            or not isinstance(text, str)
            or "compacted" in data
        ):
            unusable.add(request)
            continue
        streams.setdefault((request, kind), []).append((row["id"], text))
    chunks: list[tuple[str, str, int]] = []
    for (request, kind), parts in streams.items():
        reply = replies.get(request, [])
        if request in unusable or len(reply) != 1 or _cut_off(reply[0]):
            continue
        held = reply[0].get("content" if kind == "text" else "reasoning", "")
        # SQLite counts characters up to a NUL; such a text keeps its chunks.
        if not isinstance(held, str) or not held or "\x00" in held:
            continue
        if "".join(text for _, text in parts) == held:
            chunks.extend((event_id, kind, len(text)) for event_id, text in parts if text)
    return chunks


def _cut_off(message: dict[str, Any]) -> bool:
    """A message a broken stream cut off: the window shows its chunks instead of it."""
    metadata = message.get("provider_metadata")
    return isinstance(metadata, dict) and bool(metadata.get("agent_workspace.stream_interrupted"))


def restore_compacted_text(events: Sequence[Event]) -> list[Event]:
    """A conversation's events with each blanked chunk's text taken back from its message.

    For a copy that leaves this database (an export, a fork): it reads as it did before the
    chunks were blanked. ``events`` hold whole turns.
    """
    replies: dict[str, dict[str, Any]] = {}
    for event in events:
        request = event.data.get("model_request_id")
        if (
            event.type == "message.created"
            and event.data.get("role") == "assistant"
            and isinstance(request, str)
            and request == event.causation_id
        ):
            replies[request] = event.data
    offsets: dict[tuple[str, str], int] = {}
    restored: list[Event] = []
    for event in events:
        length = event.data.get("compacted") if event.type == "model.output.delta" else None
        if not isinstance(length, int):
            restored.append(event)
            continue
        kind = event.data.get("kind")
        request = event.causation_id
        reply = replies.get(request) if request is not None else None
        held = reply.get("content" if kind == "text" else "reasoning") if reply else None
        start = offsets.get((str(request), str(kind)), 0)
        if not isinstance(held, str) or start + length > len(held):
            raise ValueError("a compacted stream chunk has no message that holds its text")
        offsets[(str(request), str(kind))] = start + length
        data = {key: value for key, value in event.data.items() if key != "compacted"}
        data["text"] = held[start : start + length]
        restored.append(replace(event, data=data))
    return restored


class CompactionAudit:
    """What the full check notes while it reads every event, to tell blanked chunks from damage.

    A blanked chunk must belong to a recorded turn that completed, every other chunk of its
    request and kind must be blanked or empty, and their lengths must add up to the message that
    holds them, a message of the same turn that no broken stream cut off. Events come in session
    order, so only the session being read is held.
    """

    def __init__(self) -> None:
        self._session: str | None = None
        # (request, kind) -> [blanked chunks, their characters, kept chunks with text]
        self._chunks: dict[tuple[str, str], list[int]] = {}
        self._chunk_turns: dict[str, str | None] = {}
        # request -> (messages, turn, cut off, content characters, reasoning characters)
        self._replies: dict[str, tuple[int, str | None, bool, int, int]] = {}
        self._completed: set[str | None] = set()
        # (session, turn) -> [text chunks, reasoning chunks, characters], as the events tell
        self._turns: dict[tuple[str, str], list[int]] = {}
        self._problem: str | None = None

    def note(self, row: sqlite3.Row, data: dict[str, Any]) -> None:
        session = str(row["session_id"])
        if session != self._session:
            self._settle()
            self._session = session
        event_type = row["type"]
        request = row["causation_id"]
        turn = row["correlation_id"]
        if event_type == "turn.completed":
            self._completed.add(turn)
        elif event_type == "message.created":
            if (
                data.get("role") == "assistant"
                and isinstance(request, str)
                and data.get("model_request_id") == request
            ):
                count = self._replies.get(request, (0, None, False, 0, 0))[0]
                content = data.get("content")
                reasoning = data.get("reasoning", "")
                self._replies[request] = (
                    count + 1,
                    turn,
                    _cut_off(data),
                    len(content) if isinstance(content, str) else -1,
                    len(reasoning) if isinstance(reasoning, str) else -1,
                )
        elif event_type == "model.output.delta":
            length = data.get("compacted")
            if not isinstance(request, str) or data.get("model_request_id") != request:
                if length is not None:
                    self._problem = "a compacted stream chunk names no model request"
                return
            entry = self._chunks.setdefault((request, str(data.get("kind"))), [0, 0, 0])
            if length is None:
                entry[2] += 1 if data.get("text") else 0
                return
            entry[0] += 1
            entry[1] += length
            if self._chunk_turns.setdefault(request, turn) != turn:
                self._problem = "a compacted stream is spread over several turns"

    def _settle(self) -> None:
        session = self._session
        for (request, kind), (blanked, characters, kept) in self._chunks.items():
            if not blanked or session is None:
                continue
            turn = self._chunk_turns.get(request)
            reply = self._replies.get(request)
            if (
                kept
                or turn is None
                or turn not in self._completed
                or reply is None
                or reply[0] != 1
                or reply[1] != turn
                or reply[2]
                or characters != (reply[3] if kind == "text" else reply[4])
            ):
                self._problem = "compacted stream chunks do not match the message that holds them"
                continue
            counts = self._turns.setdefault((session, turn), [0, 0, 0])
            counts[0 if kind == "text" else 1] += blanked
            counts[2] += characters
        self._chunks.clear()
        self._chunk_turns.clear()
        self._replies.clear()
        self._completed.clear()

    def problem(self, recorded: Iterable[sqlite3.Row]) -> str | None:
        """What is wrong, given the rows of compacted_turns; None when nothing is."""
        self._settle()
        self._session = None
        if self._problem is not None:
            return self._problem
        turns = dict(self._turns)
        for row in recorded:
            counts = turns.pop((row["session_id"], row["correlation_id"]), [0, 0, 0])
            if [row["text_chunks"], row["reasoning_chunks"], row["characters"]] != counts:
                return "a compacted turn's record does not match its chunks"
        if turns:
            return "compacted stream chunks belong to a turn with no record"
        return None
