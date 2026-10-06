from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from itertools import zip_longest
from pathlib import Path
from threading import Lock, RLock
from types import TracebackType
from typing import Any, Self, cast

from agent_workspace.core.background_jobs import BackgroundJobStatus
from agent_workspace.core.events import (
    CURRENT_EVENT_SCHEMA_VERSION,
    Event,
    validate_event_payload,
    web_fetch_receipt_matches,
)
from agent_workspace.core.models import (
    Autonomy,
    BinaryArtifact,
    Citation,
    FileCheckpoint,
    MemoryItem,
    Mode,
    QueuedTurn,
    ResearchSource,
    Role,
    SessionMessagePreview,
    TextArtifact,
    TodoItem,
    TodoStatus,
    ToolAttempt,
    ToolAttemptState,
)
from agent_workspace.core.sandbox_changes import get_sandbox_change
from agent_workspace.core.search import SearchIndexUnavailableError, SessionSearchResult
from agent_workspace.core.session import Session
from agent_workspace.storage.checkpoint_crypto import (
    protect_checkpoint_preimage,
    unprotect_checkpoint_preimage,
)

_BUSY_TIMEOUT_MS = 5_000


class FileCheckpointConflictError(RuntimeError):
    """A second active tool attempt tried to checkpoint a path another attempt is writing."""


def _checkpoint_path_row(
    connection: sqlite3.Connection,
    workspace: str,
    relative_path: str,
) -> sqlite3.Row | None:
    row = connection.execute(
        "SELECT attempt_id FROM file_checkpoints WHERE workspace = ? AND relative_path = ?",
        (workspace, relative_path),
    ).fetchone()
    return cast(sqlite3.Row | None, row)


_MAX_SEARCH_QUERY_CHARACTERS = 512
_MAX_SEARCH_TERMS = 16
_MAX_SEARCH_RESULTS = 100
_MAX_CONTEXT_EVENT_ROWS = 5000
_MAX_CONTEXT_EVENT_DATA_BYTES = 4 * 1024 * 1024
_MAX_ACTIVITY_PREVIEW_ROWS = 500
_MAX_BINARY_ARTIFACT_STORAGE_BYTES = 512 * 1024 * 1024
_MAX_LIVE_ARTIFACT_BATCH_BYTES = 64 * 1024 * 1024
_MAX_LIVE_ARTIFACT_BATCH_COUNT = 100_000
# SQLite caps bound variables per statement at 32766; chunk dedup queries well
# below that so legitimate large changesets never fail with "too many SQL
# variables".
_ARTIFACT_DIGEST_QUERY_CHUNK = 500
_MAX_SESSION_LOCKS = 4096
# Full open-time validation (event replay + search-index rebuild) is cached
# against the database file identity so a clean, unchanged database only pays
# for it once per process; any write invalidates the cache through file
# metadata changes.
_OPEN_VALIDATION_CACHE: dict[Path, tuple[int, int]] = {}
_OPEN_VALIDATION_CACHE_LOCK = Lock()
_MAX_OPEN_VALIDATION_CACHE_ENTRIES = 64
_MAX_IMPORT_ARTIFACT_BATCH_BYTES = 128 * 1024 * 1024
_CONTEXT_EVENT_TYPES = (
    "message.created",
    "tool.settled",
    "tool.failed",
    "tool.rejected",
    "tool.cancelled",
    "tool.unknown",
    # A provider refused this image; later requests must leave it out (see AgentRunner).
    "image.rejected",
)
_SCHEMA_MIGRATIONS_DEFINITION = """
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
) STRICT
"""

_MIGRATIONS: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (
        1,
        "initial_event_store",
        (
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                workspace TEXT NOT NULL,
                mode TEXT NOT NULL,
                autonomy TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                next_sequence INTEGER NOT NULL DEFAULT 1
                    CHECK (next_sequence > 0)
            ) STRICT
            """,
            """
            CREATE TABLE events (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                type TEXT NOT NULL,
                data_json TEXT NOT NULL CHECK (json_valid(data_json)),
                schema_version INTEGER NOT NULL CHECK (schema_version > 0),
                sequence INTEGER NOT NULL CHECK (sequence > 0),
                causation_id TEXT,
                correlation_id TEXT,
                created_at TEXT NOT NULL,
                UNIQUE (session_id, sequence)
            ) STRICT
            """,
            """
            CREATE INDEX sessions_recent_idx
            ON sessions (updated_at DESC, created_at DESC, id DESC)
            """,
            """
            CREATE TRIGGER events_no_update
            BEFORE UPDATE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are immutable');
            END
            """,
            """
            CREATE TRIGGER events_no_delete
            BEFORE DELETE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are immutable');
            END
            """,
        ),
    ),
    (
        2,
        "tool_attempt_projection",
        (
            """
            CREATE TABLE tool_attempts (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                tool_call_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL CHECK (state IN (
                    'proposed', 'approved', 'started', 'settled', 'failed',
                    'rejected', 'cancelled', 'unknown'
                )),
                proposed_event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
                started_event_id TEXT REFERENCES events(id) ON DELETE RESTRICT,
                terminal_event_id TEXT REFERENCES events(id) ON DELETE RESTRICT,
                updated_at TEXT NOT NULL
            ) STRICT
            """,
            """
            CREATE INDEX tool_attempts_session_state_idx
            ON tool_attempts (session_id, state, updated_at, id)
            """,
        ),
    ),
    (
        3,
        "todo_projection",
        (
            """
            CREATE TABLE todos (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                content TEXT NOT NULL CHECK (length(content) > 0),
                status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed')),
                position INTEGER NOT NULL CHECK (position >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            ) STRICT
            """,
            """
            CREATE INDEX todos_session_status_position_idx
            ON todos (session_id, status, position, id)
            """,
        ),
    ),
    (
        4,
        "todo_id_ownership",
        (
            """
            CREATE TABLE todo_id_owners (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT
            ) STRICT
            """,
        ),
    ),
    (
        5,
        "session_full_text_search",
        (
            """
            CREATE TABLE search_documents (
                rowid INTEGER PRIMARY KEY,
                id TEXT NOT NULL UNIQUE,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                kind TEXT NOT NULL CHECK (kind IN ('title', 'user_message')),
                sequence INTEGER NOT NULL CHECK (sequence >= 0),
                text TEXT NOT NULL CHECK (length(text) > 0),
                integrity_token TEXT NOT NULL
            ) STRICT
            """,
            """
            CREATE INDEX search_documents_session_sequence_idx
            ON search_documents (session_id, sequence, id)
            """,
            """
            CREATE INDEX sessions_workspace_recent_idx
            ON sessions (workspace, updated_at DESC, created_at DESC, id DESC)
            """,
            """
            CREATE VIRTUAL TABLE session_search USING fts5(
                text,
                integrity_token,
                content='search_documents',
                content_rowid='rowid',
                tokenize='unicode61 remove_diacritics 2'
            )
            """,
            """
            CREATE VIRTUAL TABLE session_search_vocab USING fts5vocab(session_search, 'instance')
            """,
            """
            CREATE TRIGGER search_documents_ai
            AFTER INSERT ON search_documents
            BEGIN
                INSERT INTO session_search(rowid, text, integrity_token)
                VALUES (new.rowid, new.text, new.integrity_token);
            END
            """,
            """
            CREATE TRIGGER search_documents_ad
            AFTER DELETE ON search_documents
            BEGIN
                INSERT INTO session_search(session_search, rowid, text, integrity_token)
                VALUES ('delete', old.rowid, old.text, old.integrity_token);
            END
            """,
            """
            CREATE TRIGGER search_documents_au
            AFTER UPDATE ON search_documents
            BEGIN
                INSERT INTO session_search(session_search, rowid, text, integrity_token)
                VALUES ('delete', old.rowid, old.text, old.integrity_token);
                INSERT INTO session_search(rowid, text, integrity_token)
                VALUES (new.rowid, new.text, new.integrity_token);
            END
            """,
        ),
    ),
    (
        6,
        "workspace_file_checkpoints",
        (
            """
            CREATE TABLE file_checkpoints (
                attempt_id TEXT PRIMARY KEY REFERENCES tool_attempts(id) ON DELETE RESTRICT,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                workspace TEXT NOT NULL,
                started_event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
                relative_path TEXT NOT NULL CHECK (length(relative_path) > 0),
                preimage_sha256 TEXT CHECK (
                    preimage_sha256 IS NULL OR length(preimage_sha256) = 64
                ),
                protected_preimage BLOB CHECK (
                    protected_preimage IS NULL OR length(protected_preimage) <= 16779264
                ),
                postimage_sha256 TEXT NOT NULL CHECK (length(postimage_sha256) = 64),
                created_at TEXT NOT NULL,
                CHECK (
                    (preimage_sha256 IS NULL AND protected_preimage IS NULL)
                    OR (preimage_sha256 IS NOT NULL AND protected_preimage IS NOT NULL)
                ),
                UNIQUE (workspace, relative_path)
            ) STRICT
            """,
            """
            CREATE INDEX file_checkpoints_session_idx
            ON file_checkpoints (session_id, created_at, attempt_id)
            """,
        ),
    ),
    (
        7,
        "research_evidence_projection",
        (
            """
            CREATE TABLE text_artifacts (
                sha256 TEXT PRIMARY KEY CHECK (length(sha256) = 64),
                content BLOB NOT NULL CHECK (length(content) <= 131072),
                byte_count INTEGER NOT NULL CHECK (
                    byte_count >= 0 AND byte_count = length(content)
                )
            ) STRICT
            """,
            """
            CREATE TABLE research_sources (
                id TEXT NOT NULL CHECK (length(id) = 64),
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                url TEXT NOT NULL CHECK (length(url) > 0 AND length(url) <= 4096),
                title TEXT CHECK (title IS NULL OR length(title) <= 500),
                artifact_sha256 TEXT NOT NULL REFERENCES text_artifacts(sha256) ON DELETE RESTRICT,
                response_sha256 TEXT NOT NULL CHECK (length(response_sha256) = 64),
                response_bytes INTEGER NOT NULL CHECK (
                    response_bytes >= 0 AND response_bytes <= 131073
                ),
                media_type TEXT NOT NULL CHECK (
                    length(media_type) > 0 AND length(media_type) <= 255
                ),
                fetched_at TEXT NOT NULL,
                truncated INTEGER NOT NULL CHECK (truncated IN (0, 1)),
                summary TEXT NOT NULL CHECK (length(summary) <= 10000),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (session_id, id)
            ) STRICT
            """,
            """
            CREATE INDEX research_sources_session_updated_idx
            ON research_sources (session_id, updated_at DESC, id ASC)
            """,
            """
            CREATE TABLE research_citations (
                id TEXT PRIMARY KEY CHECK (length(id) > 0 AND length(id) <= 128),
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                source_id TEXT NOT NULL CHECK (length(source_id) = 64),
                claim TEXT NOT NULL CHECK (length(claim) > 0 AND length(claim) <= 10000),
                locator TEXT CHECK (locator IS NULL OR length(locator) <= 2000),
                quote TEXT CHECK (quote IS NULL OR length(quote) <= 10000),
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id, source_id)
                    REFERENCES research_sources(session_id, id) ON DELETE RESTRICT
            ) STRICT
            """,
            """
            CREATE INDEX research_citations_session_source_idx
            ON research_citations (session_id, source_id, created_at, id)
            """,
        ),
    ),
    (
        8,
        "workspace_memory_projection",
        (
            """
            CREATE TABLE memory_id_owners (
                id TEXT PRIMARY KEY,
                workspace TEXT NOT NULL CHECK (length(workspace) > 0),
                source_session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                created_at TEXT NOT NULL,
                created_event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT
            ) STRICT
            """,
            """
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                workspace TEXT NOT NULL CHECK (length(workspace) > 0),
                content TEXT NOT NULL CHECK (length(content) <= 10000),
                tags_json TEXT NOT NULL CHECK (
                    json_valid(tags_json) AND json_type(tags_json) = 'array'
                ),
                deleted INTEGER NOT NULL CHECK (deleted IN (0, 1)),
                updated_by_session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                updated_at TEXT NOT NULL,
                updated_event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
                CHECK (deleted = 0 OR (content = '' AND tags_json = '[]'))
            ) STRICT
            """,
            """
            CREATE INDEX memories_workspace_updated_idx
            ON memories (workspace, deleted, updated_at DESC, id ASC)
            """,
        ),
    ),
    (
        9,
        "event_type_activity_index",
        (
            """
            CREATE INDEX events_type_session_created_idx
            ON events (type, session_id, created_at DESC, id DESC)
            """,
        ),
    ),
    (
        10,
        "file_checkpoint_modes",
        (
            """
            ALTER TABLE file_checkpoints
            ADD COLUMN preimage_executable INTEGER
                CHECK (preimage_executable IS NULL OR preimage_executable = 0)
            """,
            """
            ALTER TABLE file_checkpoints
            ADD COLUMN postimage_executable INTEGER
                CHECK (postimage_executable IS NULL OR postimage_executable = 0)
            """,
        ),
    ),
    (
        11,
        "sandbox_binary_artifacts",
        (
            """
            CREATE TABLE binary_artifacts (
                sha256 TEXT PRIMARY KEY CHECK (length(sha256) = 64),
                content BLOB NOT NULL CHECK (length(content) <= 16777216),
                byte_count INTEGER NOT NULL CHECK (
                    byte_count >= 0 AND byte_count = length(content)
                )
            ) STRICT
            """,
            """
            CREATE TABLE sandbox_change_artifacts (
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                changeset_id TEXT NOT NULL CHECK (length(changeset_id) = 64),
                path TEXT NOT NULL CHECK (length(path) > 0 AND length(path) <= 512),
                artifact_sha256 TEXT NOT NULL
                    REFERENCES binary_artifacts(sha256) ON DELETE RESTRICT,
                created_event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
                PRIMARY KEY (session_id, changeset_id, path)
            ) STRICT
            """,
            """
            CREATE INDEX sandbox_change_artifacts_digest_idx
            ON sandbox_change_artifacts (artifact_sha256, session_id, changeset_id, path)
            """,
        ),
    ),
    (
        12,
        "workspace_node_checkpoints",
        (
            "DROP INDEX file_checkpoints_session_idx",
            "ALTER TABLE file_checkpoints RENAME TO file_checkpoints_v11",
            """
            CREATE TABLE file_checkpoints (
                attempt_id TEXT PRIMARY KEY REFERENCES tool_attempts(id) ON DELETE RESTRICT,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                workspace TEXT NOT NULL,
                started_event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
                relative_path TEXT NOT NULL CHECK (length(relative_path) > 0),
                preimage_kind TEXT NOT NULL CHECK (
                    preimage_kind IN ('missing', 'file', 'directory')
                ),
                preimage_sha256 TEXT CHECK (
                    preimage_sha256 IS NULL OR length(preimage_sha256) = 64
                ),
                protected_preimage BLOB CHECK (
                    protected_preimage IS NULL OR length(protected_preimage) <= 16779264
                ),
                preimage_executable INTEGER CHECK (
                    preimage_executable IS NULL OR preimage_executable IN (0, 1)
                ),
                postimage_kind TEXT NOT NULL CHECK (
                    postimage_kind IN ('missing', 'file', 'directory')
                ),
                postimage_sha256 TEXT CHECK (
                    postimage_sha256 IS NULL OR length(postimage_sha256) = 64
                ),
                postimage_executable INTEGER CHECK (
                    postimage_executable IS NULL OR postimage_executable IN (0, 1)
                ),
                created_at TEXT NOT NULL,
                CHECK (
                    (preimage_kind = 'missing' AND preimage_sha256 IS NULL
                        AND protected_preimage IS NULL AND preimage_executable IS NULL)
                    OR (preimage_kind = 'directory' AND preimage_sha256 IS NULL
                        AND protected_preimage IS NULL AND preimage_executable IS NULL)
                    OR (preimage_kind = 'file' AND preimage_sha256 IS NOT NULL
                        AND protected_preimage IS NOT NULL
                        AND preimage_executable IS NOT NULL)
                ),
                CHECK (
                    (postimage_kind IN ('missing', 'directory') AND postimage_sha256 IS NULL
                        AND postimage_executable IS NULL)
                    OR (postimage_kind = 'file' AND postimage_sha256 IS NOT NULL
                        AND postimage_executable IS NOT NULL)
                ),
                UNIQUE (workspace, relative_path)
            ) STRICT
            """,
            """
            INSERT INTO file_checkpoints (
                attempt_id, session_id, workspace, started_event_id, relative_path,
                preimage_kind, preimage_sha256, protected_preimage, preimage_executable,
                postimage_kind, postimage_sha256, postimage_executable, created_at
            )
            SELECT attempt_id, session_id, workspace, started_event_id, relative_path,
                   CASE WHEN preimage_sha256 IS NULL THEN 'missing' ELSE 'file' END,
                   preimage_sha256, protected_preimage,
                   CASE WHEN preimage_sha256 IS NULL THEN NULL
                        ELSE COALESCE(preimage_executable, 0) END,
                   'file', postimage_sha256, COALESCE(postimage_executable, 0), created_at
            FROM file_checkpoints_v11
            """,
            "DROP TABLE file_checkpoints_v11",
            """
            CREATE INDEX file_checkpoints_session_idx
            ON file_checkpoints (session_id, created_at, attempt_id)
            """,
        ),
    ),
    (
        13,
        "durable_operation_states",
        (
            """
            CREATE TABLE sandbox_change_states (
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                changeset_id TEXT NOT NULL CHECK (length(changeset_id) = 64),
                path TEXT NOT NULL CHECK (length(path) > 0 AND length(path) <= 512),
                review_decision TEXT CHECK (
                    review_decision IS NULL OR review_decision IN ('approved', 'rejected')
                ),
                review_event_id TEXT REFERENCES events(id) ON DELETE RESTRICT,
                applied INTEGER NOT NULL DEFAULT 0 CHECK (applied IN (0, 1)),
                applied_event_id TEXT REFERENCES events(id) ON DELETE RESTRICT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (session_id, changeset_id, path),
                CHECK ((review_decision IS NULL) = (review_event_id IS NULL)),
                CHECK ((applied = 0) = (applied_event_id IS NULL))
            ) STRICT
            """,
            """
            CREATE INDEX sandbox_change_states_session_idx
            ON sandbox_change_states (session_id, updated_at DESC, changeset_id, path)
            """,
            """
            CREATE TABLE background_jobs (
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                job_id TEXT NOT NULL CHECK (length(job_id) > 0 AND length(job_id) <= 128),
                label TEXT NOT NULL CHECK (length(label) > 0 AND length(label) <= 200),
                state TEXT NOT NULL CHECK (
                    state IN (
                        'starting', 'running', 'succeeded',
                        'failed', 'stopped', 'interrupted'
                    )
                ),
                arguments_sha256 TEXT NOT NULL CHECK (length(arguments_sha256) = 64),
                max_seconds INTEGER NOT NULL CHECK (max_seconds BETWEEN 1 AND 110),
                max_output_bytes INTEGER NOT NULL CHECK (
                    max_output_bytes BETWEEN 1024 AND 1048576
                ),
                result TEXT CHECK (
                    result IS NULL OR length(CAST(result AS BLOB)) <= 1048576
                ),
                terminal_reason TEXT,
                created_event_id TEXT NOT NULL UNIQUE REFERENCES events(id) ON DELETE RESTRICT,
                started_event_id TEXT REFERENCES events(id) ON DELETE RESTRICT,
                terminal_event_id TEXT UNIQUE REFERENCES events(id) ON DELETE RESTRICT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (session_id, job_id),
                CHECK (
                    (state = 'starting' AND started_event_id IS NULL
                        AND terminal_event_id IS NULL)
                    OR (state = 'running' AND started_event_id IS NOT NULL
                        AND terminal_event_id IS NULL)
                    OR (state IN ('succeeded', 'failed', 'stopped', 'interrupted')
                        AND terminal_event_id IS NOT NULL)
                )
            ) STRICT
            """,
            """
            CREATE INDEX background_jobs_session_recent_idx
            ON background_jobs (session_id, updated_at DESC, job_id)
            """,
            """
            CREATE INDEX background_jobs_active_idx
            ON background_jobs (state, session_id, updated_at, job_id)
            WHERE state IN ('starting', 'running')
            """,
        ),
    ),
    (
        14,
        "queued_turns_projection",
        (
            """
            CREATE TABLE queued_turns (
                turn_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                prompt TEXT NOT NULL,
                references_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(references_json)),
                state TEXT NOT NULL CHECK (
                    state IN ('queued', 'running', 'completed', 'failed', 'cancelled')
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            ) STRICT
            """,
            """
            CREATE INDEX queued_turns_session_state_idx
            ON queued_turns (session_id, state, created_at, turn_id)
            """,
        ),
    ),
    (
        15,
        "agent_control_plane",
        (
            """
            CREATE TABLE agent_runs (
                id TEXT PRIMARY KEY,
                workspace TEXT NOT NULL,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                parent_run_id TEXT REFERENCES agent_runs(id) ON DELETE RESTRICT,
                title TEXT NOT NULL CHECK (length(title) > 0),
                goal TEXT NOT NULL CHECK (length(goal) > 0),
                state TEXT NOT NULL CHECK (state IN (
                    'draft', 'queued', 'starting', 'running', 'needs_attention',
                    'succeeded', 'failed', 'cancelled'
                )),
                resume_state TEXT NOT NULL CHECK (resume_state IN (
                    'draft', 'queued', 'starting', 'running', 'succeeded', 'failed', 'cancelled'
                )),
                isolation TEXT NOT NULL CHECK (isolation IN ('shared', 'worktree')),
                checkout_path TEXT,
                branch TEXT,
                base_sha TEXT,
                active_turn_id TEXT,
                active_step_id TEXT,
                blocking_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            ) STRICT
            """,
            """
            CREATE INDEX agent_runs_workspace_state_recent_idx
            ON agent_runs (workspace, state, updated_at DESC, id)
            """,
            """
            CREATE INDEX agent_runs_session_recent_idx
            ON agent_runs (session_id, updated_at DESC, id)
            """,
            """
            CREATE TABLE plan_steps (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
                title TEXT NOT NULL CHECK (length(title) > 0),
                detail TEXT NOT NULL DEFAULT '',
                acceptance TEXT NOT NULL DEFAULT '',
                state TEXT NOT NULL CHECK (state IN (
                    'pending', 'running', 'blocked', 'completed', 'failed', 'skipped'
                )),
                position INTEGER NOT NULL CHECK (position >= 0),
                dependencies_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(dependencies_json)),
                evidence_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(evidence_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            ) STRICT
            """,
            """
            CREATE INDEX plan_steps_run_position_idx
            ON plan_steps (run_id, position, id)
            """,
            """
            CREATE TABLE attention_items (
                id TEXT PRIMARY KEY,
                run_id TEXT REFERENCES agent_runs(id) ON DELETE CASCADE,
                session_id TEXT REFERENCES sessions(id) ON DELETE RESTRICT,
                kind TEXT NOT NULL CHECK (kind IN (
                    'approval', 'input', 'failure', 'conflict', 'review', 'ci'
                )),
                severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
                title TEXT NOT NULL CHECK (length(title) > 0),
                detail TEXT NOT NULL DEFAULT '',
                state TEXT NOT NULL CHECK (state IN ('open', 'resolved', 'dismissed')),
                source_key TEXT,
                action_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(action_json)),
                resolution_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(resolution_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            ) STRICT
            """,
            """
            CREATE UNIQUE INDEX attention_items_open_source_idx
            ON attention_items (source_key)
            WHERE source_key IS NOT NULL AND state = 'open'
            """,
            """
            CREATE INDEX attention_items_state_recent_idx
            ON attention_items (state, severity DESC, updated_at DESC, id)
            """,
        ),
    ),
    (
        16,
        "immutable_review_workflow",
        (
            """
            CREATE TABLE review_snapshots (
                id TEXT PRIMARY KEY,
                workspace TEXT NOT NULL,
                checkout_path TEXT NOT NULL,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                run_id TEXT REFERENCES agent_runs(id) ON DELETE RESTRICT,
                base_sha TEXT NOT NULL CHECK (length(base_sha) = 40),
                head_sha TEXT NOT NULL CHECK (length(head_sha) = 40),
                diff_sha256 TEXT NOT NULL CHECK (length(diff_sha256) = 64),
                diff_text TEXT NOT NULL,
                files_json TEXT NOT NULL CHECK (json_valid(files_json)),
                working_tree_dirty INTEGER NOT NULL CHECK (working_tree_dirty IN (0, 1)),
                created_at TEXT NOT NULL
            ) STRICT
            """,
            """
            CREATE INDEX review_snapshots_workspace_recent_idx
            ON review_snapshots (workspace, created_at DESC, id)
            """,
            """
            CREATE TRIGGER review_snapshots_no_update
            BEFORE UPDATE ON review_snapshots
            BEGIN SELECT RAISE(ABORT, 'review_snapshot_immutable'); END
            """,
            """
            CREATE TRIGGER review_snapshots_no_delete
            BEFORE DELETE ON review_snapshots
            BEGIN SELECT RAISE(ABORT, 'review_snapshot_immutable'); END
            """,
            """
            CREATE TABLE review_comments (
                id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL REFERENCES review_snapshots(id) ON DELETE RESTRICT,
                path TEXT NOT NULL,
                side TEXT NOT NULL CHECK (side IN ('old', 'new')),
                line INTEGER NOT NULL CHECK (line > 0),
                body TEXT NOT NULL CHECK (length(body) > 0),
                state TEXT NOT NULL CHECK (state IN ('open', 'resolved')),
                author TEXT NOT NULL CHECK (length(author) > 0),
                followup_run_id TEXT REFERENCES agent_runs(id) ON DELETE RESTRICT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            ) STRICT
            """,
            """
            CREATE INDEX review_comments_snapshot_state_idx
            ON review_comments (snapshot_id, state, path, line, created_at, id)
            """,
            """
            CREATE TABLE review_deliveries (
                snapshot_id TEXT PRIMARY KEY REFERENCES review_snapshots(id) ON DELETE RESTRICT,
                provider TEXT NOT NULL CHECK (provider IN ('github')),
                pr_url TEXT,
                pr_number INTEGER,
                state TEXT NOT NULL CHECK (state IN ('draft', 'open', 'merged', 'closed', 'error')),
                is_draft INTEGER NOT NULL CHECK (is_draft IN (0, 1)),
                head_branch TEXT,
                base_branch TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            ) STRICT
            """,
            """
            CREATE TABLE delivery_checks (
                snapshot_id TEXT NOT NULL
                    REFERENCES review_deliveries(snapshot_id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN (
                    'queued', 'in_progress', 'success', 'failure', 'neutral',
                    'skipped', 'cancelled', 'timed_out', 'action_required', 'unknown'
                )),
                url TEXT,
                detail TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (snapshot_id, name)
            ) STRICT
            """,
        ),
    ),
    (
        17,
        "recoverable_review_delivery",
        (
            """
            ALTER TABLE review_deliveries ADD COLUMN commit_sha TEXT
                CHECK (commit_sha IS NULL OR length(commit_sha) = 40)
            """,
        ),
    ),
    (
        18,
        "durable_agent_run_pause_request",
        (
            """
            ALTER TABLE agent_runs ADD COLUMN pause_requested INTEGER NOT NULL DEFAULT 0
                CHECK (pause_requested IN (0, 1))
            """,
        ),
    ),
    (
        19,
        "queued_turn_exclusion_digests",
        (
            """
            ALTER TABLE queued_turns ADD COLUMN exclude_image_digests_json TEXT
                NOT NULL DEFAULT '[]' CHECK (json_valid(exclude_image_digests_json))
            """,
        ),
    ),
    (
        20,
        "run_checkpoints_and_operation_ledger",
        (
            """
            CREATE TABLE run_checkpoints (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
                revision INTEGER NOT NULL CHECK (revision > 0),
                state_json TEXT NOT NULL CHECK (json_valid(state_json)),
                reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE (run_id, revision)
            ) STRICT
            """,
            """
            CREATE INDEX run_checkpoints_run_revision_idx
            ON run_checkpoints (run_id, revision DESC, id)
            """,
            """
            CREATE TABLE operation_ledger (
                idempotency_key TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
                phase_id TEXT,
                tool_name TEXT,
                request_json TEXT NOT NULL CHECK (json_valid(request_json)),
                state TEXT NOT NULL CHECK (state IN ('started', 'completed', 'failed')),
                result_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(result_json)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            ) STRICT
            """,
            """
            CREATE INDEX operation_ledger_run_updated_idx
            ON operation_ledger (run_id, updated_at DESC, idempotency_key)
            """,
        ),
    ),
    (
        21,
        "memory_expiration",
        (
            """
            ALTER TABLE memories
            ADD COLUMN expires_at TEXT
                CHECK (expires_at IS NULL OR length(expires_at) <= 64)
            """,
            """
            CREATE INDEX memories_workspace_expiry_idx
            ON memories (workspace, deleted, expires_at, updated_at DESC, id)
            """,
        ),
    ),
    (
        22,
        "queued_turn_reasoning_effort",
        (
            """
            ALTER TABLE queued_turns ADD COLUMN reasoning_effort TEXT
                CHECK (reasoning_effort IS NULL OR reasoning_effort IN
                    ('off', 'low', 'medium', 'high', 'max'))
            """,
        ),
    ),
    (
        23,
        "large_document_checkpoints",
        (
            "DROP INDEX file_checkpoints_session_idx",
            "ALTER TABLE file_checkpoints RENAME TO file_checkpoints_v22",
            """
            CREATE TABLE file_checkpoints (
                attempt_id TEXT PRIMARY KEY REFERENCES tool_attempts(id) ON DELETE RESTRICT,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                workspace TEXT NOT NULL,
                started_event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
                relative_path TEXT NOT NULL CHECK (length(relative_path) > 0),
                preimage_kind TEXT NOT NULL CHECK (
                    preimage_kind IN ('missing', 'file', 'directory')
                ),
                preimage_sha256 TEXT CHECK (
                    preimage_sha256 IS NULL OR length(preimage_sha256) = 64
                ),
                protected_preimage BLOB,
                preimage_executable INTEGER CHECK (
                    preimage_executable IS NULL OR preimage_executable IN (0, 1)
                ),
                postimage_kind TEXT NOT NULL CHECK (
                    postimage_kind IN ('missing', 'file', 'directory')
                ),
                postimage_sha256 TEXT CHECK (
                    postimage_sha256 IS NULL OR length(postimage_sha256) = 64
                ),
                postimage_executable INTEGER CHECK (
                    postimage_executable IS NULL OR postimage_executable IN (0, 1)
                ),
                created_at TEXT NOT NULL,
                CHECK (
                    (preimage_kind = 'missing' AND preimage_sha256 IS NULL
                        AND protected_preimage IS NULL AND preimage_executable IS NULL)
                    OR (preimage_kind = 'directory' AND preimage_sha256 IS NULL
                        AND protected_preimage IS NULL AND preimage_executable IS NULL)
                    OR (preimage_kind = 'file' AND preimage_sha256 IS NOT NULL
                        AND protected_preimage IS NOT NULL
                        AND preimage_executable IS NOT NULL)
                ),
                CHECK (
                    (postimage_kind IN ('missing', 'directory') AND postimage_sha256 IS NULL
                        AND postimage_executable IS NULL)
                    OR (postimage_kind = 'file' AND postimage_sha256 IS NOT NULL
                        AND postimage_executable IS NOT NULL)
                ),
                UNIQUE (workspace, relative_path)
            ) STRICT
            """,
            """
            INSERT INTO file_checkpoints
            SELECT * FROM file_checkpoints_v22
            """,
            "DROP TABLE file_checkpoints_v22",
            """
            CREATE INDEX file_checkpoints_session_idx
            ON file_checkpoints (session_id, created_at, attempt_id)
            """,
        ),
    ),
)

CURRENT_SCHEMA_VERSION = _MIGRATIONS[-1][0]
CURRENT_SCHEMA_MIGRATIONS = tuple((version, name) for version, name, _ in _MIGRATIONS)


def normalize_schema_definition(sql: str) -> str:
    return " ".join(sql.split())


def _schema_definitions_by_version() -> dict[int, frozenset[str]]:
    connection = sqlite3.connect(":memory:")
    by_version: dict[int, frozenset[str]] = {}
    try:
        connection.execute(_SCHEMA_MIGRATIONS_DEFINITION)
        for version, _, statements in _MIGRATIONS:
            for statement in statements:
                connection.execute(statement)
            definitions = {
                normalize_schema_definition(cast(str, row[0]))
                for row in connection.execute(
                    "SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL"
                ).fetchall()
            }
            by_version[version] = frozenset(definitions)
        return by_version
    finally:
        connection.close()


SCHEMA_DEFINITIONS_BY_VERSION = _schema_definitions_by_version()


class SQLiteEventStore:
    """SQLite-backed append-only event store."""

    def __init__(
        self,
        database: str | Path,
        *,
        create_migration_backup: bool = True,
        synchronous: str = "FULL",
    ) -> None:
        if synchronous not in {"OFF", "NORMAL", "FULL", "EXTRA"}:
            raise ValueError("SQLite synchronous mode is invalid")
        self._synchronous = synchronous
        database_path = Path(database).expanduser().resolve()
        # Capture the file identity before this connection creates its WAL:
        # only cleanly closed databases (no WAL) are eligible for the
        # open-validation cache.
        pre_open_identity = SQLiteEventStore._database_open_identity(database_path)
        existing_version = self._validate_before_migration(database_path)
        if (
            create_migration_backup
            and existing_version is not None
            and 0 < existing_version < CURRENT_SCHEMA_VERSION
        ):
            self._backup_before_migration(database_path)
        self._lock = RLock()
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._connection: sqlite3.Connection | None = sqlite3.connect(
            str(database_path),
            timeout=_BUSY_TIMEOUT_MS / 1_000,
            isolation_level=None,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row

        try:
            self._configure()
            self._migrate()
            from agent_workspace.storage.recovery import validate_database

            if not SQLiteEventStore._open_validation_cached(database_path, pre_open_identity):
                validate_database(database_path)
                SQLiteEventStore._cache_open_validation(database_path, pre_open_identity)
        except BaseException:
            self.close()
            raise

    def _configure(self) -> None:
        connection = self._get_connection()
        connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(f"PRAGMA synchronous = {self._synchronous}")

    @staticmethod
    def _validate_before_migration(database: Path) -> int | None:
        if not database.is_file() or database.stat().st_size == 0:
            return None
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                f"{database.as_uri()}?mode=ro",
                timeout=_BUSY_TIMEOUT_MS / 1_000,
                uri=True,
            )
            quick_check = connection.execute("PRAGMA quick_check").fetchall()
            if [row[0] for row in quick_check] != ["ok"]:
                raise RuntimeError("Database quick_check failed before migration")
            raw_version = connection.execute("PRAGMA user_version").fetchone()[0]
            schema_rows = connection.execute(
                "SELECT COUNT(*) FROM sqlite_schema WHERE sql IS NOT NULL"
            ).fetchone()[0]
        except sqlite3.Error:
            raise RuntimeError("Database schema version cannot be read before migration") from None
        finally:
            if connection is not None:
                connection.close()
        if raw_version == 0 and schema_rows == 0:
            return None
        if type(raw_version) is not int:
            raise RuntimeError("Database schema version is invalid before migration")

        if raw_version == CURRENT_SCHEMA_VERSION:
            return raw_version

        from agent_workspace.storage.recovery import BackupValidationError, validate_database

        try:
            return validate_database(database).schema_version
        except BackupValidationError as exc:
            message = str(exc)
            repairable_search_error = (
                message == "session search index is inconsistent"
                or message == "session search index terms are inconsistent"
            )
            if repairable_search_error and raw_version >= 5:
                SQLiteEventStore._repair_search_index_before_open(database)
                return validate_database(database).schema_version
            raise

    @staticmethod
    def migration_dry_run(database: str | Path) -> dict[str, object]:
        """Report pending schema migrations without changing the database."""
        database_path = Path(database).expanduser().resolve()
        if not database_path.is_file() or database_path.stat().st_size == 0:
            return {
                "current_version": 0,
                "target_version": CURRENT_SCHEMA_VERSION,
                "pending": [
                    {"version": version, "name": name}
                    for version, name in CURRENT_SCHEMA_MIGRATIONS
                ],
                "backup_will_be_created": False,
            }
        connection = sqlite3.connect(
            f"{database_path.as_uri()}?mode=ro",
            timeout=_BUSY_TIMEOUT_MS / 1_000,
            uri=True,
        )
        try:
            raw_version = connection.execute("PRAGMA user_version").fetchone()[0]
        except sqlite3.Error as exc:
            raise RuntimeError("cannot read database schema version") from exc
        finally:
            connection.close()
        if type(raw_version) is not int or raw_version < 0 or raw_version > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(f"database schema version is invalid: {raw_version!r}")
        pending = [
            {"version": version, "name": name}
            for version, name in CURRENT_SCHEMA_MIGRATIONS
            if version > raw_version
        ]
        return {
            "current_version": raw_version,
            "target_version": CURRENT_SCHEMA_VERSION,
            "pending": pending,
            "backup_will_be_created": bool(pending) and raw_version > 0,
        }

    @staticmethod
    def _repair_search_index_before_open(database: Path) -> None:
        connection = sqlite3.connect(
            str(database),
            timeout=_BUSY_TIMEOUT_MS / 1_000,
            isolation_level=None,
        )
        try:
            connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("BEGIN EXCLUSIVE")
            SQLiteEventStore._repair_search_index(connection)
            connection.commit()
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def run_maintenance(database: str | Path, *, vacuum: bool = False) -> dict[str, object]:
        """Run bounded, non-destructive database maintenance.

        The routine checkpoints the WAL, optimizes the FTS index, and
        optionally executes ``VACUUM``. It intentionally does not rewrite
        projected state or rebuild the search index, so it is safe to run
        while a desktop application is idle.
        """
        database_path = Path(database).expanduser().resolve()
        if not database_path.is_file() or database_path.stat().st_size == 0:
            return {"checkpointed": False, "fts_optimized": False, "vacuumed": False}
        connection = sqlite3.connect(
            str(database_path),
            timeout=_BUSY_TIMEOUT_MS / 1_000,
            isolation_level=None,
        )
        checkpointed = False
        fts_optimized = False
        vacuumed = False
        try:
            connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
            checkpoint_row = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            checkpointed = checkpoint_row is not None and checkpoint_row[0] == 0
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_schema "
                    "WHERE type = 'table' AND name = 'session_search'"
                )
            }
            if "session_search" in tables:
                connection.execute("INSERT INTO session_search(session_search) VALUES ('optimize')")
                fts_optimized = True
            if vacuum:
                connection.execute("VACUUM")
                vacuumed = True
        except sqlite3.Error as exc:
            raise RuntimeError(f"database maintenance failed: {exc}") from exc
        finally:
            connection.close()
        return {
            "checkpointed": checkpointed,
            "fts_optimized": fts_optimized,
            "vacuumed": vacuumed,
        }

    @staticmethod
    def _backup_before_migration(database: Path) -> None:

        from agent_workspace.storage.recovery import create_verified_backup

        create_verified_backup(database, database.parent / "migration-backups", keep=10)

    def _migrate(self) -> None:
        connection = self._get_connection()
        try:
            connection.execute("BEGIN EXCLUSIVE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                ) STRICT
                """
            )
            rows = connection.execute(
                "SELECT version, name FROM schema_migrations ORDER BY version"
            ).fetchall()
            applied_versions = [cast(int, row["version"]) for row in rows]
            applied_migrations = [
                (cast(int, row["version"]), cast(str, row["name"])) for row in rows
            ]
            known_versions = {version for version, _, _ in _MIGRATIONS}

            if any(version not in known_versions for version in applied_versions):
                raise RuntimeError("Database schema is newer than this application")
            if applied_versions and applied_versions != list(range(1, applied_versions[-1] + 1)):
                raise RuntimeError("Database schema migration history is incomplete")
            if tuple(applied_migrations) != CURRENT_SCHEMA_MIGRATIONS[: len(applied_migrations)]:
                raise RuntimeError("Database schema migration history is inconsistent")
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
            expected_version = applied_versions[-1] if applied_versions else 0
            if type(user_version) is not int or user_version != expected_version:
                raise RuntimeError("Database schema version does not match migration history")

            for version, name, statements in _MIGRATIONS:
                if version in applied_versions:
                    continue
                for statement in statements:
                    try:
                        connection.execute(statement)
                    except sqlite3.OperationalError as exc:
                        # A process can be interrupted after applying a DDL
                        # statement but before recording its migration row.
                        # Treat an existing object as already applied; later
                        # validation still checks the complete current schema.
                        message = str(exc).casefold()
                        if "already exists" not in message and not (
                            version == 21 and "duplicate column name: expires_at" in message
                        ):
                            raise
                if version == 2:
                    self._backfill_legacy_tool_attempts(connection)
                if version == 4:
                    self._backfill_todo_id_owners(connection)
                if version == 5:
                    self._backfill_search_documents(connection)
                if version == 7:
                    self._backfill_research_evidence(connection)
                if version == 8:
                    self._backfill_memories(connection)
                if version == 11:
                    self._backfill_sandbox_artifacts(connection)
                if version == 13:
                    self._backfill_durable_operation_states(connection)
                connection.execute(
                    """
                    INSERT INTO schema_migrations (version, name, applied_at)
                    VALUES (?, ?, ?)
                    """,
                    (version, name, datetime.now(UTC).isoformat()),
                )
                connection.execute(f"PRAGMA user_version = {version}")
            self._repair_search_index(connection)
            connection.commit()
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise

    def create_session(self, session: Session) -> None:
        with self._lock:
            connection = self._get_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    INSERT INTO sessions (
                        id, workspace, mode, autonomy, title, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        session.id,
                        session.workspace,
                        session.mode.value,
                        session.autonomy.value,
                        session.title,
                        session.created_at,
                        session.updated_at,
                    ),
                )
                if cursor.rowcount == 0:
                    row = connection.execute(
                        """
                        SELECT workspace, mode, autonomy, title, created_at
                        FROM sessions
                        WHERE id = ?
                        """,
                        (session.id,),
                    ).fetchone()
                    assert row is not None
                    identity = (
                        row["workspace"],
                        row["mode"],
                        row["autonomy"],
                        row["title"],
                        row["created_at"],
                    )
                    requested_identity = (
                        session.workspace,
                        session.mode.value,
                        session.autonomy.value,
                        session.title,
                        session.created_at,
                    )
                    if identity != requested_identity:
                        raise ValueError(f"Session id already exists: {session.id}")
                else:
                    self._project_session(connection, session)
                connection.commit()
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def append(self, event: Event) -> Event:
        return self.append_many((event,))[0]

    def import_session(
        self,
        session: Session,
        events: tuple[Event, ...],
        artifacts: tuple[BinaryArtifact, ...] = (),
    ) -> list[Event]:
        if any(event.session_id != session.id for event in events):
            raise ValueError("imported events must belong to the imported session")
        if any(event.schema_version != CURRENT_EVENT_SCHEMA_VERSION for event in events):
            raise ValueError("event schema version is unsupported")
        for event in events:
            validate_event_payload(event.type, event.data)
        data_documents = [
            json.dumps(
                event.data,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            for event in events
        ]
        self._validate_binary_artifacts(
            artifacts,
            max_batch_bytes=_MAX_IMPORT_ARTIFACT_BATCH_BYTES,
        )
        with self._lock:
            connection = self._get_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    connection.execute(
                        """
                        INSERT INTO sessions (
                            id, workspace, mode, autonomy, title, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            session.id,
                            session.workspace,
                            session.mode.value,
                            session.autonomy.value,
                            session.title,
                            session.created_at,
                            session.updated_at,
                        ),
                    )
                except sqlite3.IntegrityError:
                    raise ValueError(f"Session id already exists: {session.id}") from None
                self._project_session(connection, session)
                self._insert_binary_artifacts(connection, artifacts)
                stored_events = self._append_events(
                    connection,
                    events,
                    data_documents,
                )
                self._validate_artifact_references(connection, artifacts, events)
                connection.commit()
                return stored_events
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def delete_session_if_empty(self, session_id: str) -> bool:
        """Delete a newly-created session only while it has no durable events.

        This is intentionally narrow: it exists for lifecycle rollback and will
        never erase a session that a runtime has begun to use.
        """

        with self._lock:
            connection = self._get_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                if (
                    connection.execute(
                        "SELECT 1 FROM events WHERE session_id = ? LIMIT 1",
                        (session_id,),
                    ).fetchone()
                    is not None
                ):
                    connection.rollback()
                    return False
                connection.execute(
                    "DELETE FROM search_documents WHERE session_id = ?",
                    (session_id,),
                )
                deleted = connection.execute(
                    "DELETE FROM sessions WHERE id = ?",
                    (session_id,),
                ).rowcount
                connection.commit()
                return deleted == 1
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def append_many(self, events: tuple[Event, ...]) -> list[Event]:
        return self.append_many_with_artifacts(events, ())

    def append_many_with_artifacts(
        self,
        events: tuple[Event, ...],
        artifacts: tuple[BinaryArtifact, ...],
    ) -> list[Event]:
        if not events:
            raise ValueError("at least one event is required")
        session_id = events[0].session_id
        if any(event.session_id != session_id for event in events):
            raise ValueError("batched events must belong to one session")
        if any(event.schema_version != CURRENT_EVENT_SCHEMA_VERSION for event in events):
            raise ValueError("event schema version is unsupported")
        for event in events:
            validate_event_payload(event.type, event.data)
        data_documents = [
            json.dumps(
                event.data,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            for event in events
        ]
        self._validate_binary_artifacts(artifacts)

        with self._lock:
            connection = self._get_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._insert_binary_artifacts(connection, artifacts)
                stored_events = self._append_events(connection, events, data_documents)
                self._validate_artifact_references(connection, artifacts, events)
                connection.commit()
                return stored_events
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    @staticmethod
    def _validate_binary_artifacts(
        artifacts: tuple[BinaryArtifact, ...],
        *,
        max_batch_bytes: int | None = None,
    ) -> None:
        max_batch_bytes = max_batch_bytes or _MAX_LIVE_ARTIFACT_BATCH_BYTES
        if sum(artifact.byte_count for artifact in artifacts) > max_batch_bytes:
            raise ValueError("sandbox artifacts exceed the batch byte limit")
        if len(artifacts) > _MAX_LIVE_ARTIFACT_BATCH_COUNT:
            raise ValueError("sandbox artifacts exceed the batch entry limit")
        identities: dict[str, bytes] = {}
        for artifact in artifacts:
            if (
                not SQLiteEventStore._is_sha256(artifact.sha256)
                or artifact.byte_count > 16 * 1024 * 1024
                or hashlib.sha256(artifact.content).hexdigest() != artifact.sha256
            ):
                raise ValueError("sandbox artifact metadata is invalid")
            existing = identities.setdefault(artifact.sha256, artifact.content)
            if existing != artifact.content:
                raise ValueError("sandbox artifact digest collision detected")

    @staticmethod
    def _insert_binary_artifacts(
        connection: sqlite3.Connection,
        artifacts: tuple[BinaryArtifact, ...],
        *,
        enforce_storage_limit: bool = True,
    ) -> None:
        digest_set = {artifact.sha256 for artifact in artifacts}
        existing_digests: set[str] = set()
        if digest_set:
            ordered_digests = tuple(digest_set)
            for start in range(0, len(ordered_digests), _ARTIFACT_DIGEST_QUERY_CHUNK):
                chunk = ordered_digests[start : start + _ARTIFACT_DIGEST_QUERY_CHUNK]
                placeholders = ",".join("?" for _ in chunk)
                existing_digests.update(
                    cast(str, row["sha256"])
                    for row in connection.execute(
                        f"SELECT sha256 FROM binary_artifacts WHERE sha256 IN ({placeholders})",
                        chunk,
                    )
                )
        if enforce_storage_limit:
            existing_bytes = connection.execute(
                "SELECT COALESCE(SUM(byte_count), 0) AS bytes FROM binary_artifacts"
            ).fetchone()
            new_bytes = sum(
                artifact.byte_count
                for artifact in artifacts
                if artifact.sha256 not in existing_digests
            )
            if (
                new_bytes > 0
                and existing_bytes is not None
                and existing_bytes["bytes"] + new_bytes > _MAX_BINARY_ARTIFACT_STORAGE_BYTES
            ):
                raise ValueError("sandbox binary artifact storage exceeds its 512 MiB limit")
        for artifact in artifacts:
            connection.execute(
                """
                INSERT INTO binary_artifacts (sha256, content, byte_count)
                VALUES (?, ?, ?)
                ON CONFLICT (sha256) DO NOTHING
                """,
                (artifact.sha256, artifact.content, artifact.byte_count),
            )
            row = connection.execute(
                "SELECT content, byte_count FROM binary_artifacts WHERE sha256 = ?",
                (artifact.sha256,),
            ).fetchone()
            if (
                row is None
                or row["content"] != artifact.content
                or row["byte_count"] != artifact.byte_count
            ):
                raise ValueError("sandbox artifact digest collision detected")

    @staticmethod
    def _validate_artifact_references(
        connection: sqlite3.Connection,
        artifacts: tuple[BinaryArtifact, ...],
        events: tuple[Event, ...],
    ) -> None:
        for sha256 in {artifact.sha256 for artifact in artifacts}:
            referenced = connection.execute(
                "SELECT 1 FROM sandbox_change_artifacts WHERE artifact_sha256 = ? LIMIT 1",
                (sha256,),
            ).fetchone()
            if referenced is None:
                referenced = connection.execute(
                    """
                    SELECT 1 FROM events
                    WHERE type = 'image.attached'
                      AND json_extract(data_json, '$.sha256') = ?
                    LIMIT 1
                    """,
                    (sha256,),
                ).fetchone()
            if referenced is None:
                raise ValueError("artifact is not referenced by its event batch")
        batch = {artifact.sha256: artifact for artifact in artifacts}
        for event in events:
            if event.type != "image.attached":
                continue
            event_sha256 = event.data.get("sha256")
            artifact = batch.get(event_sha256) if isinstance(event_sha256, str) else None
            if artifact is None:
                continue
            byte_count = event.data.get("bytes")
            if type(byte_count) is int and byte_count != len(artifact.content):
                raise ValueError("image.attached byte count does not match its artifact content")

    @staticmethod
    def _append_events(
        connection: sqlite3.Connection,
        events: tuple[Event, ...],
        data_documents: list[str],
    ) -> list[Event]:
        stored_events: list[Event] = []
        for event, data_json in zip(events, data_documents, strict=True):
            row = connection.execute(
                """
                UPDATE sessions
                SET next_sequence = next_sequence + 1,
                    updated_at = CASE
                        WHEN updated_at < ? THEN ?
                        ELSE updated_at
                    END
                WHERE id = ?
                RETURNING next_sequence - 1 AS sequence
                """,
                (event.created_at, event.created_at, event.session_id),
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown session: {event.session_id}")

            stored_event = event.with_sequence(cast(int, row["sequence"]))
            connection.execute(
                """
                INSERT INTO events (
                    id, session_id, type, data_json, schema_version, sequence,
                    causation_id, correlation_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stored_event.id,
                    stored_event.session_id,
                    stored_event.type,
                    data_json,
                    stored_event.schema_version,
                    stored_event.sequence,
                    stored_event.causation_id,
                    stored_event.correlation_id,
                    stored_event.created_at,
                ),
            )
            SQLiteEventStore._project_event(connection, stored_event)
            stored_events.append(stored_event)
        return stored_events

    def list_events(self, session_id: str) -> list[Event]:
        with self._lock:
            rows = (
                self._get_connection()
                .execute(
                    """
                SELECT id, session_id, type, data_json, schema_version, sequence,
                       causation_id, correlation_id, created_at
                FROM events
                WHERE session_id = ?
                ORDER BY sequence ASC
                """,
                    (session_id,),
                )
                .fetchall()
            )

        return self._events_from_rows(rows)

    def list_pending_turn_inputs(self, session_id: str) -> list[Event]:
        with self._lock:
            rows = (
                self._get_connection()
                .execute(
                    """
                SELECT received.id, received.session_id, received.type, received.data_json,
                       received.schema_version, received.sequence, received.causation_id,
                       received.correlation_id, received.created_at
                FROM events AS received
                WHERE received.session_id = ? AND received.type = 'turn.input.received'
                  AND NOT EXISTS (
                    SELECT 1 FROM events AS applied
                    WHERE applied.session_id = received.session_id
                      AND applied.type = 'turn.input.applied'
                      AND applied.causation_id = received.id
                  )
                ORDER BY received.sequence ASC
                """,
                    (session_id,),
                )
                .fetchall()
            )
        return self._events_from_rows(rows)

    def list_events_paged(
        self,
        session_id: str,
        *,
        cursor: int | None = None,
        limit: int = 100,
        reverse: bool = False,
    ) -> list[Event]:
        if type(limit) is not int or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("event page limit must be from 1 to 1000")
        if cursor is not None and (
            type(cursor) is not int or isinstance(cursor, bool) or cursor < 1
        ):
            raise ValueError("event page cursor must be a positive sequence number")
        with self._lock:
            if reverse:
                rows = self._list_events_paged_backward(session_id, cursor, limit)
            else:
                rows = self._list_events_paged_forward(session_id, cursor, limit)
        return self._events_from_rows(rows)

    def replay_events(
        self,
        session_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> tuple[list[Event], int, int, bool]:
        """Read a bounded forward event page with durable stream metadata.

        ``after_sequence`` is exclusive.  The extra row used for ``has_more``
        keeps replay callers from loading the full event stream just to decide
        whether a cursor can advance.
        """

        if not isinstance(session_id, str) or not session_id:
            raise ValueError("event replay session id is invalid")
        if type(after_sequence) is not int or after_sequence < 0:
            raise ValueError("event replay cursor must be non-negative")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("event replay limit must be from 1 to 1000")
        with self._lock:
            connection = self._get_connection()
            rows = connection.execute(
                """
                SELECT id, session_id, type, data_json, schema_version, sequence,
                       causation_id, correlation_id, created_at
                FROM events
                WHERE session_id = ? AND sequence > ?
                ORDER BY sequence ASC
                LIMIT ?
                """,
                (session_id, after_sequence, limit + 1),
            ).fetchall()
            bounds = connection.execute(
                """
                SELECT MIN(sequence) AS oldest_sequence, MAX(sequence) AS newest_sequence
                FROM events
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        has_more = len(rows) > limit
        events = self._events_from_rows(rows[:limit])
        oldest = int(bounds["oldest_sequence"] or 0)
        newest = int(bounds["newest_sequence"] or 0)
        return events, oldest, newest, has_more

    def _list_events_paged_forward(
        self,
        session_id: str,
        cursor: int | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        if cursor is None:
            query = """
                SELECT id, session_id, type, data_json, schema_version, sequence,
                       causation_id, correlation_id, created_at
                FROM events
                WHERE session_id = ?
                ORDER BY sequence ASC
                LIMIT ?
            """
            return self._get_connection().execute(query, (session_id, limit)).fetchall()
        query = """
            SELECT id, session_id, type, data_json, schema_version, sequence,
                   causation_id, correlation_id, created_at
            FROM events
            WHERE session_id = ? AND sequence > ?
            ORDER BY sequence ASC
            LIMIT ?
        """
        return self._get_connection().execute(query, (session_id, cursor, limit)).fetchall()

    def _list_events_paged_backward(
        self,
        session_id: str,
        cursor: int | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        if cursor is None:
            query = """
                SELECT id, session_id, type, data_json, schema_version, sequence,
                       causation_id, correlation_id, created_at
                FROM events
                WHERE session_id = ?
                ORDER BY sequence DESC
                LIMIT ?
            """
            rows = self._get_connection().execute(query, (session_id, limit)).fetchall()
        else:
            query = """
                SELECT id, session_id, type, data_json, schema_version, sequence,
                       causation_id, correlation_id, created_at
                FROM events
                WHERE session_id = ? AND sequence < ?
                ORDER BY sequence DESC
                LIMIT ?
            """
            rows = (
                self._get_connection()
                .execute(
                    query,
                    (session_id, cursor, limit),
                )
                .fetchall()
            )
        rows.reverse()
        return rows

    def list_events_by_type(
        self,
        event_type: str,
        *,
        limit: int = 50,
        workspace: str | None = None,
        route_id: str | None = None,
    ) -> list[Event]:
        if not isinstance(event_type, str) or not event_type or len(event_type) > 200:
            raise ValueError("event type is invalid")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("event query limit must be from 1 to 1000")
        if workspace is not None and (not workspace or len(workspace) > 32767):
            raise ValueError("event query workspace is invalid")
        if route_id is not None and (not route_id or len(route_id) > 128):
            raise ValueError("event query route id is invalid")
        with self._lock:
            rows = (
                self._get_connection()
                .execute(
                    """
                    SELECT e.id, e.session_id, e.type, e.data_json, e.schema_version,
                           e.sequence, e.causation_id, e.correlation_id, e.created_at
                    FROM events AS e
                    JOIN sessions AS s ON s.id = e.session_id
                    WHERE e.type = ?
                      AND (? IS NULL OR s.workspace = ?)
                      AND (
                          ? IS NULL
                          OR json_extract(e.data_json, '$.route_id') = ?
                      )
                    ORDER BY s.updated_at DESC, e.created_at DESC, e.id DESC
                    LIMIT ?
                    """,
                    (event_type, workspace, workspace, route_id, route_id, limit),
                )
                .fetchall()
            )
        return self._events_from_rows(rows)

    def list_background_jobs(
        self,
        workspace: str,
        *,
        session_id: str | None = None,
        limit: int = 50,
        active_only: bool = False,
    ) -> list[BackgroundJobStatus]:
        if not workspace or len(workspace) > 32767:
            raise ValueError("background job workspace is invalid")
        if session_id is not None and not session_id:
            raise ValueError("background job session is invalid")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("background job limit must be from 1 to 1000")
        if type(active_only) is not bool:
            raise ValueError("background job active filter is invalid")
        with self._lock:
            rows = (
                self._get_connection()
                .execute(
                    """
                    SELECT j.job_id, j.session_id, j.label, j.state,
                           j.created_at, j.updated_at, NULL AS result, j.terminal_reason
                    FROM background_jobs AS j
                    JOIN sessions AS s ON s.id = j.session_id
                    WHERE s.workspace = ?
                      AND (? IS NULL OR j.session_id = ?)
                      AND (? = 0 OR j.state IN ('starting', 'running'))
                    ORDER BY j.updated_at DESC, j.job_id DESC
                    LIMIT ?
                    """,
                    (workspace, session_id, session_id, int(active_only), limit),
                )
                .fetchall()
            )
        return [self._background_job_from_row(row) for row in rows]

    def get_background_job(
        self,
        session_id: str,
        job_id: str,
    ) -> BackgroundJobStatus | None:
        if not session_id or not job_id or len(job_id) > 128:
            raise ValueError("background job identity is invalid")
        with self._lock:
            row = (
                self._get_connection()
                .execute(
                    """
                    SELECT job_id, session_id, label, state, created_at, updated_at,
                           result, terminal_reason
                    FROM background_jobs
                    WHERE session_id = ? AND job_id = ?
                    """,
                    (session_id, job_id),
                )
                .fetchone()
            )
        return self._background_job_from_row(row) if row is not None else None

    def get_background_job_active_event(
        self,
        session_id: str,
        job_id: str,
    ) -> Event | None:
        if not session_id or not job_id or len(job_id) > 128:
            raise ValueError("background job identity is invalid")
        with self._lock:
            row = (
                self._get_connection()
                .execute(
                    """
                    SELECT e.id, e.session_id, e.type, e.data_json, e.schema_version,
                           e.sequence, e.causation_id, e.correlation_id, e.created_at
                    FROM background_jobs AS j
                    JOIN events AS e ON e.id = CASE
                        WHEN j.state = 'running' THEN j.started_event_id
                        ELSE j.created_event_id
                    END
                    WHERE j.session_id = ? AND j.job_id = ?
                      AND j.state IN ('starting', 'running')
                    """,
                    (session_id, job_id),
                )
                .fetchone()
            )
        return self._events_from_rows([row])[0] if row is not None else None

    def enqueue_turn(
        self,
        turn_id: str,
        session_id: str,
        prompt: str,
        references: Sequence[str] = (),
        *,
        exclude_image_digests: Iterable[str] = (),
        reasoning_effort: str | None = None,
    ) -> QueuedTurn:
        if not turn_id or len(turn_id) > 128:
            raise ValueError("queued turn id is invalid")
        if not session_id or len(session_id) > 128:
            raise ValueError("queued turn session id is invalid")
        if not prompt or not prompt.strip():
            raise ValueError("queued turn prompt is invalid")
        if reasoning_effort is not None and reasoning_effort not in {
            "off",
            "low",
            "medium",
            "high",
            "max",
        }:
            raise ValueError("queued turn reasoning effort is invalid")
        references_tuple = tuple(str(r) for r in references)
        references_json = json.dumps(list(references_tuple), separators=(",", ":"))
        exclude_image_digests_tuple = tuple(dict.fromkeys(str(d) for d in exclude_image_digests))
        exclude_image_digests_json = json.dumps(
            list(exclude_image_digests_tuple), separators=(",", ":")
        )
        now = datetime.now(UTC).isoformat()
        with self._lock:
            self._get_connection().execute(
                """
                INSERT INTO queued_turns (
                    turn_id, session_id, prompt, references_json,
                    exclude_image_digests_json, reasoning_effort, state, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?)
                """,
                (
                    turn_id,
                    session_id,
                    prompt,
                    references_json,
                    exclude_image_digests_json,
                    reasoning_effort,
                    now,
                    now,
                ),
            )
        return QueuedTurn(
            turn_id=turn_id,
            session_id=session_id,
            prompt=prompt,
            references=references_tuple,
            state="queued",
            created_at=now,
            updated_at=now,
            exclude_image_digests=frozenset(exclude_image_digests_tuple),
            reasoning_effort=reasoning_effort,
        )

    def list_queued_turns(
        self,
        session_id: str,
        *,
        states: Sequence[str] = ("queued",),
    ) -> list[QueuedTurn]:
        if not session_id or len(session_id) > 128:
            raise ValueError("queued turn session id is invalid")
        if not states:
            return []
        placeholders = ",".join("?" for _ in states)
        with self._lock:
            rows = (
                self._get_connection()
                .execute(
                    f"""
                    SELECT turn_id, session_id, prompt, references_json,
                           exclude_image_digests_json, state, created_at, updated_at,
                           reasoning_effort
                    FROM queued_turns
                    WHERE session_id = ? AND state IN ({placeholders})
                    ORDER BY created_at ASC, turn_id ASC
                    """,
                    (session_id, *states),
                )
                .fetchall()
            )
        result: list[QueuedTurn] = []
        for row in rows:
            refs = tuple(json.loads(row[3])) if row[3] else ()
            excluded = frozenset(json.loads(row[4])) if row[4] else frozenset()
            result.append(
                QueuedTurn(
                    turn_id=row[0],
                    session_id=row[1],
                    prompt=row[2],
                    references=refs,
                    state=row[5],
                    created_at=row[6],
                    updated_at=row[7],
                    exclude_image_digests=excluded,
                    reasoning_effort=row[8],
                )
            )
        return result

    def mark_turn_state(
        self,
        turn_id: str,
        state: str,
    ) -> None:
        if not turn_id or len(turn_id) > 128:
            raise ValueError("queued turn id is invalid")
        if state not in {"queued", "running", "completed", "failed", "cancelled"}:
            raise ValueError("queued turn state is invalid")
        now = datetime.now(UTC).isoformat()
        with self._lock:
            self._get_connection().execute(
                """
                UPDATE queued_turns
                SET state = ?, updated_at = ?
                WHERE turn_id = ?
                """,
                (state, now, turn_id),
            )

    def clear_queued_turns(
        self,
        session_id: str,
    ) -> None:
        if not session_id or len(session_id) > 128:
            raise ValueError("queued turn session id is invalid")
        now = datetime.now(UTC).isoformat()
        with self._lock:
            self._get_connection().execute(
                """
                UPDATE queued_turns
                SET state = 'cancelled', updated_at = ?
                WHERE session_id = ? AND state = 'queued'
                """,
                (now, session_id),
            )

    def get_event(self, event_id: str) -> Event | None:
        with self._lock:
            row = (
                self._get_connection()
                .execute(
                    """
                    SELECT id, session_id, type, data_json, schema_version, sequence,
                           causation_id, correlation_id, created_at
                    FROM events
                    WHERE id = ?
                    """,
                    (event_id,),
                )
                .fetchone()
            )
        return self._events_from_rows([row])[0] if row is not None else None

    @staticmethod
    def get_event_read_only(database: str | Path, event_id: str) -> Event | None:
        database_path = Path(database)
        if not database_path.is_file():
            return None
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            return SQLiteEventStore._events_from_rows([row])[0] if row is not None else None
        finally:
            connection.close()

    @staticmethod
    def model_request_ids_read_only(database: str | Path, events: list[Event]) -> dict[str, str]:
        """Infer old stream boundaries without changing stored conversation events.

        History can start halfway through a request. Seed each turn from its
        preceding request, then advance using the requests in the page itself.
        """
        database_path = Path(database)
        if not database_path.is_file() or not events:
            return {}
        associated_types = {
            "model.output.delta",
            "model.completed",
            "model.output.limited",
            "model.stream.interrupted",
            "model.stream.recovered",
        }
        current: dict[tuple[str, str | None], str | None] = {}
        inferred: dict[str, str] = {}
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            connection.execute("BEGIN")
            for event in sorted(events, key=lambda item: item.sequence or 0):
                key = (event.session_id, event.correlation_id)
                if event.type == "model.requested":
                    current[key] = event.id
                    continue
                if event.type not in associated_types and not (
                    event.type == "message.created" and event.data.get("role") == "assistant"
                ):
                    continue
                if isinstance(event.data.get("model_request_id"), str):
                    continue
                if key not in current:
                    row = connection.execute(
                        "SELECT id FROM events WHERE session_id = ? AND correlation_id IS ? "
                        "AND type = 'model.requested' AND sequence < ? "
                        "ORDER BY sequence DESC LIMIT 1",
                        (*key, event.sequence or 0),
                    ).fetchone()
                    current[key] = str(row["id"]) if row is not None else None
                request_id = current[key]
                if request_id is not None:
                    inferred[event.id] = request_id
            return inferred
        finally:
            connection.close()

    def get_sandbox_changeset_event(
        self,
        session_id: str,
        workspace: str,
        changeset_id: str,
    ) -> Event | None:
        return self._get_sandbox_event(
            "sandbox.changeset.created",
            session_id,
            workspace,
            changeset_id,
        )

    def get_sandbox_change_applied_event(
        self,
        session_id: str,
        workspace: str,
        changeset_id: str,
        path: str,
    ) -> Event | None:
        return self._get_sandbox_event(
            "sandbox.change.applied",
            session_id,
            workspace,
            changeset_id,
            path=path,
        )

    def get_sandbox_change_review_event(
        self,
        session_id: str,
        workspace: str,
        changeset_id: str,
        path: str,
    ) -> Event | None:
        return self._get_sandbox_event(
            "sandbox.change.reviewed",
            session_id,
            workspace,
            changeset_id,
            path=path,
        )

    def list_sandbox_changeset_events(
        self,
        session_id: str,
        workspace: str,
        *,
        limit: int = 50,
    ) -> list[Event]:
        if not session_id or not workspace or len(workspace) > 32767:
            raise ValueError("sandbox changeset query scope is invalid")
        if type(limit) is not int or not 1 <= limit <= 101:
            raise ValueError("sandbox changeset query limit must be from 1 to 101")
        with self._lock:
            rows = (
                self._get_connection()
                .execute(
                    """
                    WITH latest AS (
                        SELECT json_extract(e.data_json, '$.changeset_id') AS changeset_id,
                               MAX(e.sequence) AS sequence
                        FROM events AS e
                        JOIN sessions AS s ON s.id = e.session_id
                        WHERE e.type = 'sandbox.changeset.created'
                          AND e.session_id = ?
                          AND s.workspace = ?
                        GROUP BY changeset_id
                    )
                    SELECT e.id, e.session_id, e.type, e.data_json, e.schema_version,
                           e.sequence, e.causation_id, e.correlation_id, e.created_at
                    FROM latest
                    JOIN events AS e ON e.session_id = ? AND e.sequence = latest.sequence
                    ORDER BY e.sequence DESC
                    LIMIT ?
                    """,
                    (session_id, workspace, session_id, limit),
                )
                .fetchall()
            )
        return self._events_from_rows(rows)

    def list_sandbox_change_applied_events(
        self,
        session_id: str,
        workspace: str,
        changeset_id: str,
    ) -> list[Event]:
        if (
            not session_id
            or not workspace
            or len(workspace) > 32767
            or not self._is_sha256(changeset_id)
        ):
            raise ValueError("sandbox applied-event query identity is invalid")
        with self._lock:
            rows = (
                self._get_connection()
                .execute(
                    """
                    SELECT e.id, e.session_id, e.type, e.data_json, e.schema_version,
                           e.sequence, e.causation_id, e.correlation_id, e.created_at
                    FROM events AS e
                    JOIN sessions AS s ON s.id = e.session_id
                    WHERE e.type = 'sandbox.change.applied'
                      AND e.session_id = ?
                      AND s.workspace = ?
                      AND json_extract(e.data_json, '$.changeset_id') = ?
                    ORDER BY e.sequence ASC
                    """,
                    (session_id, workspace, changeset_id),
                )
                .fetchall()
            )
        return self._events_from_rows(rows)

    def _get_sandbox_event(
        self,
        event_type: str,
        session_id: str,
        workspace: str,
        changeset_id: str,
        *,
        path: str | None = None,
    ) -> Event | None:
        if (
            not session_id
            or not workspace
            or len(workspace) > 32767
            or not self._is_sha256(changeset_id)
            or (path is not None and (not path or len(path) > 512))
        ):
            raise ValueError("sandbox event query identity is invalid")
        with self._lock:
            row = (
                self._get_connection()
                .execute(
                    """
                SELECT e.id, e.session_id, e.type, e.data_json, e.schema_version,
                       e.sequence, e.causation_id, e.correlation_id, e.created_at
                FROM events AS e
                JOIN sessions AS s ON s.id = e.session_id
                WHERE e.type = ?
                  AND e.session_id = ?
                  AND s.workspace = ?
                  AND json_extract(e.data_json, '$.changeset_id') = ?
                  AND (? IS NULL OR json_extract(e.data_json, '$.path') = ?)
                ORDER BY e.sequence DESC
                LIMIT 1
                """,
                    (event_type, session_id, workspace, changeset_id, path, path),
                )
                .fetchone()
            )
        return self._events_from_rows([row])[0] if row is not None else None

    def list_settled_tool_results(
        self,
        session_id: str,
        tool_name: str,
        *,
        limit: int = 1000,
    ) -> list[str]:
        if not 1 <= limit <= 1000:
            raise ValueError("settled tool result limit must be from 1 to 1000")
        with self._lock:
            rows = (
                self._get_connection()
                .execute(
                    """
                SELECT json_extract(data_json, '$.result') AS result
                FROM events
                WHERE session_id = ?
                  AND type = 'tool.settled'
                  AND json_extract(data_json, '$.name') = ?
                  AND json_extract(data_json, '$.output_truncated') = 0
                  AND json_type(data_json, '$.result') = 'text'
                ORDER BY sequence DESC
                LIMIT ?
                """,
                    (session_id, tool_name, limit),
                )
                .fetchall()
            )
        return [cast(str, row["result"]) for row in rows]

    def list_context_events(self, session_id: str) -> list[Event]:
        placeholders = ", ".join("?" for _ in _CONTEXT_EVENT_TYPES)
        with self._lock:
            connection = self._get_connection()
            boundary_row = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) AS sequence
                FROM events
                WHERE session_id = ? AND type = 'session.imported'
                """,
                (session_id,),
            ).fetchone()
            boundary = cast(int, boundary_row["sequence"]) if boundary_row is not None else 0
            # "Edit and resend" / "regenerate" record context.rewound: the events from
            # from_sequence up to the rewind leave the model's context (history keeps them).
            rewound: list[tuple[int, int]] = []
            for row in connection.execute(
                """
                SELECT sequence, json_extract(data_json, '$.from_sequence') AS from_sequence
                FROM events
                WHERE session_id = ? AND type = 'context.rewound' AND sequence > ?
                """,
                (session_id, boundary),
            ):
                start = row["from_sequence"]
                if isinstance(start, int) and 0 < start < cast(int, row["sequence"]):
                    rewound.append((start, cast(int, row["sequence"])))

            def kept(sequence: int) -> bool:
                return not any(start <= sequence < end for start, end in rewound)

            metadata = connection.execute(
                f"""
                SELECT sequence, type, length(CAST(data_json AS BLOB)) AS data_bytes,
                       json_extract(data_json, '$.role') AS role
                FROM events
                WHERE session_id = ? AND sequence > ? AND type IN ({placeholders})
                ORDER BY sequence DESC
                LIMIT ?
                """,
                (session_id, boundary, *_CONTEXT_EVENT_TYPES, _MAX_CONTEXT_EVENT_ROWS + 1),
            ).fetchall()
            total_bytes = 0
            cutoff: int | None = None
            fallback_cutoff: int | None = None
            for row in metadata[:_MAX_CONTEXT_EVENT_ROWS]:
                if not kept(cast(int, row["sequence"])):
                    continue
                data_bytes = cast(int, row["data_bytes"])
                if total_bytes + data_bytes > _MAX_CONTEXT_EVENT_DATA_BYTES:
                    break
                total_bytes += data_bytes
                fallback_cutoff = cast(int, row["sequence"])
                if row["type"] == "message.created" and row["role"] == Role.USER.value:
                    cutoff = cast(int, row["sequence"])
            selected_cutoff = cutoff if cutoff is not None else fallback_cutoff
            if selected_cutoff is None:
                return []
            rows = connection.execute(
                f"""
                SELECT id, session_id, type, data_json, schema_version, sequence,
                       causation_id, correlation_id, created_at
                FROM events
                WHERE session_id = ?
                  AND sequence >= ?
                  AND sequence > ?
                  AND type IN ({placeholders})
                ORDER BY sequence ASC
                """,
                (session_id, selected_cutoff, boundary, *_CONTEXT_EVENT_TYPES),
            ).fetchall()
            if rewound:
                rows = [row for row in rows if kept(cast(int, row["sequence"]))]
        return self._events_from_rows(rows)

    @staticmethod
    def list_events_read_only(database: str | Path, session_id: str) -> list[Event]:
        database_path = Path(database)
        if not database_path.is_file():
            return []
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'events'"
            ).fetchone()
            if table is None:
                return []
            rows = connection.execute(
                """
                SELECT id, session_id, type, data_json, schema_version, sequence,
                       causation_id, correlation_id, created_at
                FROM events
                WHERE session_id = ?
                ORDER BY sequence ASC
                """,
                (session_id,),
            ).fetchall()
            return SQLiteEventStore._events_from_rows(rows)
        finally:
            connection.close()

    @staticmethod
    def list_session_events_of_types_read_only(
        database: str | Path, session_id: str, event_types: frozenset[str]
    ) -> list[Event]:
        """Read one session's events of the given types in sequence order."""

        if not session_id or not event_types or len(event_types) > 32:
            raise ValueError("event type query is invalid")
        database_path = Path(database)
        if not database_path.is_file():
            return []
        types = sorted(event_types)
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'events'"
            ).fetchone()
            if table is None:
                return []
            placeholders = ", ".join("?" for _ in types)
            rows = connection.execute(
                f"""
                SELECT id, session_id, type, data_json, schema_version, sequence,
                       causation_id, correlation_id, created_at
                FROM events
                WHERE session_id = ? AND type IN ({placeholders})
                ORDER BY sequence ASC
                """,
                (session_id, *types),
            ).fetchall()
            return SQLiteEventStore._events_from_rows(rows)
        finally:
            connection.close()

    @staticmethod
    def list_events_page_read_only(
        database: str | Path,
        session_id: str,
        *,
        before_sequence: int | None = None,
        cutoff_sequence: int | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Read a bounded newest-first event page from an execution database."""

        if not session_id:
            raise ValueError("event page session id is invalid")
        if before_sequence is not None and (
            type(before_sequence) is not int or before_sequence <= 0
        ):
            raise ValueError("event page cursor must be positive")
        if cutoff_sequence is not None and (
            type(cutoff_sequence) is not int or cutoff_sequence < 0
        ):
            raise ValueError("event page cutoff must be non-negative")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("event page limit must be from 1 to 1000")
        database_path = Path(database)
        if not database_path.is_file():
            return []
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'events'"
            ).fetchone()
            if table is None:
                return []
            rows = connection.execute(
                """
                SELECT id, session_id, type, data_json, schema_version, sequence,
                       causation_id, correlation_id, created_at
                FROM events
                WHERE session_id = ?
                  AND (? IS NULL OR sequence < ?)
                  AND (? IS NULL OR sequence <= ?)
                ORDER BY sequence DESC
                LIMIT ?
                """,
                (
                    session_id,
                    before_sequence,
                    before_sequence,
                    cutoff_sequence,
                    cutoff_sequence,
                    limit,
                ),
            ).fetchall()
            return SQLiteEventStore._events_from_rows(rows)
        finally:
            connection.close()

    @staticmethod
    def latest_model_context_read_only(
        database: str | Path, session_id: str
    ) -> tuple[Event | None, Event | None]:
        if not Path(database).is_file():
            return None, None
        connection = SQLiteEventStore._open_read_only(Path(database))
        try:
            connection.execute("BEGIN")
            row = connection.execute(
                "SELECT * FROM events WHERE session_id = ? AND type = 'model.requested' "
                "ORDER BY sequence DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            if row is None:
                return None, None
            request = SQLiteEventStore._events_from_rows([row])[0]
            usage_row = connection.execute(
                "SELECT * FROM events WHERE session_id = ? AND type = 'usage.updated' "
                "AND causation_id = ? ORDER BY sequence DESC LIMIT 1",
                (session_id, request.id),
            ).fetchone()
            usage = SQLiteEventStore._events_from_rows([usage_row])[0] if usage_row else None
            return request, usage
        finally:
            connection.close()

    @staticmethod
    def list_event_window_read_only(
        database: str | Path,
        session_id: str,
        *,
        cutoff: int | None = None,
        before: int | None = None,
        limit: int = 65,
    ) -> tuple[int, list[Event]]:
        if not session_id or len(session_id) > 256:
            raise ValueError("event window session is invalid")
        if cutoff is not None and (type(cutoff) is not int or cutoff < 0):
            raise ValueError("event window cutoff is invalid")
        if before is not None and (type(before) is not int or before < 0):
            raise ValueError("event window boundary is invalid")
        if type(limit) is not int or not 1 <= limit <= 1001:
            raise ValueError("event window limit must be from 1 to 1001")
        database_path = Path(database)
        if not database_path.is_file():
            return cutoff or 0, []
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'events'"
            ).fetchone()
            if table is None:
                return cutoff or 0, []
            resolved_cutoff = cutoff
            if resolved_cutoff is None:
                row = connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) AS cutoff FROM events WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                resolved_cutoff = cast(int, row["cutoff"])
            boundary = before if before is not None else resolved_cutoff + 1
            if boundary > resolved_cutoff + 1:
                raise ValueError("event window boundary exceeds cutoff")
            rows = connection.execute(
                """
                SELECT id, session_id, type, data_json, schema_version, sequence,
                       causation_id, correlation_id, created_at
                FROM events
                WHERE session_id = ? AND sequence <= ? AND sequence < ?
                ORDER BY sequence DESC
                LIMIT ?
                """,
                (session_id, resolved_cutoff, boundary, limit),
            ).fetchall()
            return resolved_cutoff, SQLiteEventStore._events_from_rows(rows)
        finally:
            connection.close()

    @staticmethod
    def list_complete_turn_window_read_only(
        database: str | Path,
        session_id: str,
        *,
        cutoff: int | None = None,
        before: int | None = None,
        minimum_user_turns: int = 8,
        max_events: int = 1001,
    ) -> tuple[int, list[Event], bool, bool]:
        """Read a newest-first history window ending on a user-turn boundary.

        The signed cursor still supplies the stable ``cutoff`` and exclusive
        ``before`` boundary. Normal pages contain at least the requested number
        of user turns. A pathological turn that alone exceeds ``max_events`` is
        returned as a bounded partial page and flagged as oversized.
        """
        if not session_id or len(session_id) > 256:
            raise ValueError("complete turn window session is invalid")
        if cutoff is not None and (type(cutoff) is not int or cutoff < 0):
            raise ValueError("complete turn window cutoff is invalid")
        if before is not None and (type(before) is not int or before < 0):
            raise ValueError("complete turn window boundary is invalid")
        if type(minimum_user_turns) is not int or not 1 <= minimum_user_turns <= 100:
            raise ValueError("minimum user turns must be from 1 to 100")
        if type(max_events) is not int or not 1 <= max_events <= 10_001:
            raise ValueError("complete turn window event limit must be from 1 to 10001")

        database_path = Path(database)
        if not database_path.is_file():
            return cutoff or 0, [], False, False
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'events'"
            ).fetchone()
            if table is None:
                return cutoff or 0, [], False, False
            resolved_cutoff = cutoff
            if resolved_cutoff is None:
                row = connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) AS cutoff FROM events WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                resolved_cutoff = cast(int, row["cutoff"])
            boundary = before if before is not None else resolved_cutoff + 1
            if boundary > resolved_cutoff + 1:
                raise ValueError("complete turn window boundary exceeds cutoff")

            turn_rows = connection.execute(
                """
                SELECT sequence
                FROM events
                WHERE session_id = ? AND sequence <= ? AND sequence < ?
                  AND type = 'message.created'
                  AND json_extract(data_json, '$.role') = 'user'
                ORDER BY sequence DESC
                LIMIT ?
                """,
                (session_id, resolved_cutoff, boundary, minimum_user_turns),
            ).fetchall()
            if len(turn_rows) == minimum_user_turns:
                oldest_turn_sequence = cast(int, turn_rows[-1]["sequence"])
            elif turn_rows:
                oldest_turn_sequence = 1
            else:
                # Recovery and legacy databases can contain orphan events with
                # no user message. Keep those pages small and cursorable.
                oldest_turn_sequence = max(1, boundary - 64)
            rows = connection.execute(
                """
                SELECT id, session_id, type, data_json, schema_version, sequence,
                       causation_id, correlation_id, created_at
                FROM events
                WHERE session_id = ? AND sequence <= ? AND sequence < ?
                  AND sequence >= ?
                ORDER BY sequence DESC
                LIMIT ?
                """,
                (
                    session_id,
                    resolved_cutoff,
                    boundary,
                    oldest_turn_sequence,
                    max_events + 1,
                ),
            ).fetchall()
            oversized = len(rows) > max_events
            selected_rows = rows[:max_events]
            events = SQLiteEventStore._events_from_rows(selected_rows)
            if not events:
                return resolved_cutoff, [], False, False
            oldest_returned = events[-1].sequence
            assert oldest_returned is not None
            has_more = oversized or (
                connection.execute(
                    "SELECT 1 FROM events WHERE session_id = ? AND sequence < ? LIMIT 1",
                    (session_id, oldest_returned),
                ).fetchone()
                is not None
            )
            return resolved_cutoff, events, has_more, oversized
        finally:
            connection.close()

    @staticmethod
    def _events_from_rows(rows: list[sqlite3.Row]) -> list[Event]:
        events: list[Event] = []
        for row in rows:
            data = json.loads(cast(str, row["data_json"]))
            if not isinstance(data, dict):
                raise ValueError(f"Event {row['id']} data is not a JSON object")
            events.append(
                Event(
                    id=cast(str, row["id"]),
                    session_id=cast(str, row["session_id"]),
                    type=cast(str, row["type"]),
                    data=cast(dict[str, Any], data),
                    schema_version=cast(int, row["schema_version"]),
                    sequence=cast(int, row["sequence"]),
                    causation_id=cast(str | None, row["causation_id"]),
                    correlation_id=cast(str | None, row["correlation_id"]),
                    created_at=cast(str, row["created_at"]),
                )
            )
        return events

    def list_incomplete_tool_attempts(self, session_id: str) -> list[ToolAttempt]:
        with self._lock:
            rows = (
                self._get_connection()
                .execute(
                    """
                    SELECT id, session_id, tool_call_id, tool_name, idempotency_key, state,
                           proposed_event_id, started_event_id, terminal_event_id
                    FROM tool_attempts
                    WHERE session_id = ? AND state IN ('proposed', 'approved', 'started')
                    ORDER BY updated_at ASC, id ASC
                    """,
                    (session_id,),
                )
                .fetchall()
            )
        return [self._tool_attempt_from_row(row) for row in rows]

    def list_incomplete_tool_attempts_for_workspace(self, workspace: str) -> list[ToolAttempt]:
        with self._lock:
            rows = (
                self._get_connection()
                .execute(
                    """
                    SELECT t.id, t.session_id, t.tool_call_id, t.tool_name,
                           t.idempotency_key, t.state, t.proposed_event_id,
                           t.started_event_id, t.terminal_event_id
                    FROM tool_attempts AS t
                    JOIN sessions AS s ON s.id = t.session_id
                    WHERE s.workspace = ? AND t.state IN ('proposed', 'approved', 'started')
                    ORDER BY t.updated_at ASC, t.id ASC
                    """,
                    (workspace,),
                )
                .fetchall()
            )
        return [self._tool_attempt_from_row(row) for row in rows]

    def prepare_file_checkpoint(self, checkpoint: FileCheckpoint) -> None:
        preimage_kind = checkpoint.preimage_kind or (
            "missing" if checkpoint.preimage is None else "file"
        )
        postimage_kind = checkpoint.postimage_kind
        preimage_executable = (
            False
            if preimage_kind == "file" and checkpoint.preimage_executable is None
            else checkpoint.preimage_executable
        )
        postimage_executable = (
            False
            if postimage_kind == "file" and checkpoint.postimage_executable is None
            else checkpoint.postimage_executable
        )
        try:
            created_at = datetime.fromisoformat(checkpoint.created_at)
        except ValueError:
            created_at = None
        if (
            not checkpoint.workspace
            or not self._is_relative_checkpoint_path(checkpoint.relative_path)
            or created_at is None
            or created_at.tzinfo is None
            or created_at.utcoffset() is None
            or (preimage_executable is not None and type(preimage_executable) is not bool)
            or (postimage_executable is not None and type(postimage_executable) is not bool)
            or preimage_kind not in {"missing", "file", "directory"}
            or postimage_kind not in {"missing", "file", "directory"}
        ):
            raise ValueError("file checkpoint metadata is invalid")
        if checkpoint.preimage is not None:
            digest = hashlib.sha256(checkpoint.preimage).hexdigest()
            if digest != checkpoint.preimage_sha256:
                raise ValueError("file checkpoint preimage digest does not match its content")
        if preimage_kind == "file":
            if (
                checkpoint.preimage is None
                or not self._is_sha256(checkpoint.preimage_sha256)
                or preimage_executable is None
            ):
                raise ValueError("file checkpoint preimage metadata is inconsistent")
        elif (
            checkpoint.preimage is not None
            or checkpoint.preimage_sha256 is not None
            or preimage_executable is not None
        ):
            raise ValueError("file checkpoint preimage metadata is inconsistent")
        if postimage_kind == "file":
            if not self._is_sha256(checkpoint.postimage_sha256) or postimage_executable is None:
                raise ValueError("file checkpoint postimage metadata is inconsistent")
        elif checkpoint.postimage_sha256 is not None or postimage_executable is not None:
            raise ValueError("file checkpoint postimage metadata is inconsistent")
        protected_preimage = (
            protect_checkpoint_preimage(
                checkpoint.preimage,
                attempt_id=checkpoint.attempt_id,
                session_id=checkpoint.session_id,
                workspace=checkpoint.workspace,
                relative_path=checkpoint.relative_path,
            )
            if checkpoint.preimage is not None
            else None
        )
        with self._lock:
            connection = self._get_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                attempt = connection.execute(
                    """
                    SELECT t.session_id, t.started_event_id, t.state, s.workspace
                    FROM tool_attempts AS t
                    JOIN sessions AS s ON s.id = t.session_id
                    WHERE t.id = ?
                    """,
                    (checkpoint.attempt_id,),
                ).fetchone()
                if (
                    attempt is None
                    or attempt["session_id"] != checkpoint.session_id
                    or attempt["started_event_id"] != checkpoint.started_event_id
                    or attempt["state"] != ToolAttemptState.STARTED.value
                    or attempt["workspace"] != checkpoint.workspace
                ):
                    raise ValueError("file checkpoint does not belong to an active tool attempt")
                connection.execute(
                    """
                    INSERT INTO file_checkpoints (
                        attempt_id, session_id, workspace, started_event_id, relative_path,
                        preimage_kind, preimage_sha256, protected_preimage, preimage_executable,
                        postimage_kind, postimage_sha256, postimage_executable, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        checkpoint.attempt_id,
                        checkpoint.session_id,
                        checkpoint.workspace,
                        checkpoint.started_event_id,
                        checkpoint.relative_path,
                        preimage_kind,
                        checkpoint.preimage_sha256,
                        protected_preimage,
                        preimage_executable,
                        postimage_kind,
                        checkpoint.postimage_sha256,
                        postimage_executable,
                        checkpoint.created_at,
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                if connection.in_transaction:
                    connection.rollback()
                existing = _checkpoint_path_row(
                    connection, checkpoint.workspace, checkpoint.relative_path
                )
                if existing is not None:
                    if existing["attempt_id"] == checkpoint.attempt_id:
                        raise ValueError(
                            f"a file checkpoint for attempt {checkpoint.attempt_id!r} "
                            f"at {checkpoint.relative_path!r} already exists"
                        ) from exc
                    raise FileCheckpointConflictError(
                        f"file {checkpoint.relative_path!r} is already being written by "
                        "another active tool attempt in this workspace"
                    ) from exc
                raise ValueError(
                    f"file checkpoint for {checkpoint.relative_path!r} violates a "
                    "database constraint"
                ) from exc
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def get_file_checkpoint(self, attempt_id: str) -> FileCheckpoint | None:
        with self._lock:
            row = (
                self._get_connection()
                .execute(
                    """
                    SELECT attempt_id, session_id, workspace, started_event_id, relative_path,
                           preimage_kind, preimage_sha256, protected_preimage, preimage_executable,
                           postimage_kind, postimage_sha256, postimage_executable, created_at
                    FROM file_checkpoints
                    WHERE attempt_id = ?
                    """,
                    (attempt_id,),
                )
                .fetchone()
            )
        return self._file_checkpoint_from_row(row) if row is not None else None

    def session_lock(self, session_id: str) -> asyncio.Lock:
        with self._lock:
            if (
                session_id not in self._session_locks
                and len(self._session_locks) >= _MAX_SESSION_LOCKS
            ):
                # Best-effort eviction: remove only entries with no holder and
                # no waiters, and never the lock being requested. A lock handed
                # out but not yet acquired (a same-tick window) can still be
                # evicted under extreme concurrency; the requested key itself
                # is protected so this caller always receives a live entry.
                for key, lock in tuple(self._session_locks.items()):
                    if key == session_id or lock.locked():
                        continue
                    if getattr(lock, "_waiters", None):
                        continue
                    self._session_locks.pop(key, None)
            return self._session_locks.setdefault(session_id, asyncio.Lock())

    @staticmethod
    def _database_open_identity(database: Path) -> tuple[int, int] | None:
        # Only cache cleanly closed databases: a live WAL means the last
        # process may not have checkpointed, so validation must run.
        if not database.is_file():
            return None
        wal = database.with_name(f"{database.name}-wal")
        if wal.is_file():
            return None
        metadata = database.stat()
        return metadata.st_mtime_ns, metadata.st_size

    @staticmethod
    def _open_validation_cached(
        database: Path,
        identity: tuple[int, int] | None,
    ) -> bool:
        if identity is None:
            return False
        with _OPEN_VALIDATION_CACHE_LOCK:
            return _OPEN_VALIDATION_CACHE.get(database) == identity

    @staticmethod
    def _cache_open_validation(
        database: Path,
        identity: tuple[int, int] | None,
    ) -> None:
        if identity is None:
            return
        with _OPEN_VALIDATION_CACHE_LOCK:
            if len(_OPEN_VALIDATION_CACHE) >= _MAX_OPEN_VALIDATION_CACHE_ENTRIES:
                oldest = next(iter(_OPEN_VALIDATION_CACHE))
                _OPEN_VALIDATION_CACHE.pop(oldest, None)
            _OPEN_VALIDATION_CACHE[database] = identity

    def list_todos(self, session_id: str) -> list[TodoItem]:
        with self._lock:
            rows = (
                self._get_connection()
                .execute(
                    """
                    SELECT id, session_id, content, status, position, created_at, updated_at
                    FROM todos
                    WHERE session_id = ?
                    ORDER BY position ASC, id ASC
                    """,
                    (session_id,),
                )
                .fetchall()
            )
        return [
            TodoItem(
                id=cast(str, row["id"]),
                session_id=cast(str, row["session_id"]),
                content=cast(str, row["content"]),
                status=TodoStatus(cast(str, row["status"])),
                position=cast(int, row["position"]),
                created_at=cast(str, row["created_at"]),
                updated_at=cast(str, row["updated_at"]),
            )
            for row in rows
        ]

    @staticmethod
    def list_todos_read_only(database: str | Path, session_id: str) -> list[TodoItem]:
        database_path = Path(database)
        if not database_path.is_file():
            return []
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'todos'"
            ).fetchone()
            if table is None:
                return []
            rows = connection.execute(
                """
                SELECT id, session_id, content, status, position, created_at, updated_at
                FROM todos
                WHERE session_id = ?
                ORDER BY position ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
            return [SQLiteEventStore._todo_from_row(row) for row in rows]
        finally:
            connection.close()

    @staticmethod
    def list_file_checkpoints_read_only(
        database: str | Path,
        session_id: str,
    ) -> list[tuple[str, str]]:
        """Return checkpoints whose writes are active or still have an unknown outcome."""
        database_path = Path(database)
        if not database_path.is_file():
            return []
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'file_checkpoints'"
            ).fetchone()
            if table is None:
                return []
            rows = connection.execute(
                """
                SELECT c.attempt_id, c.relative_path
                FROM file_checkpoints AS c
                JOIN tool_attempts AS a
                  ON a.id = c.attempt_id AND a.session_id = c.session_id
                WHERE c.session_id = ? AND a.state IN ('started', 'unknown')
                ORDER BY c.created_at ASC
                """,
                (session_id,),
            ).fetchall()
            return [(cast(str, row["attempt_id"]), cast(str, row["relative_path"])) for row in rows]
        finally:
            connection.close()

    def list_research_sources(self, session_id: str) -> list[ResearchSource]:
        with self._lock:
            rows = (
                self._get_connection()
                .execute(
                    """
                SELECT s.id, s.session_id, s.url, s.title, s.artifact_sha256,
                       a.byte_count AS artifact_bytes, s.response_sha256, s.response_bytes,
                       s.media_type, s.fetched_at, s.truncated, s.summary,
                       s.created_at, s.updated_at
                FROM research_sources AS s
                JOIN text_artifacts AS a ON a.sha256 = s.artifact_sha256
                WHERE s.session_id = ?
                ORDER BY s.updated_at DESC, s.id ASC
                """,
                    (session_id,),
                )
                .fetchall()
            )
        return [self._research_source_from_row(row) for row in rows]

    @staticmethod
    def list_research_sources_read_only(
        database: str | Path,
        session_id: str,
    ) -> list[ResearchSource]:
        database_path = Path(database)
        if not database_path.is_file():
            return []
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'research_sources'"
            ).fetchone()
            if table is None:
                return []
            rows = connection.execute(
                """
                SELECT s.id, s.session_id, s.url, s.title, s.artifact_sha256,
                       a.byte_count AS artifact_bytes, s.response_sha256, s.response_bytes,
                       s.media_type, s.fetched_at, s.truncated, s.summary,
                       s.created_at, s.updated_at
                FROM research_sources AS s
                JOIN text_artifacts AS a ON a.sha256 = s.artifact_sha256
                WHERE s.session_id = ?
                ORDER BY s.updated_at DESC, s.id ASC
                """,
                (session_id,),
            ).fetchall()
            return [SQLiteEventStore._research_source_from_row(row) for row in rows]
        finally:
            connection.close()

    def list_citations(self, session_id: str) -> list[Citation]:
        with self._lock:
            rows = (
                self._get_connection()
                .execute(
                    """
                SELECT id, session_id, source_id, claim, locator, quote, created_at
                FROM research_citations
                WHERE session_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                    (session_id,),
                )
                .fetchall()
            )
        return [self._citation_from_row(row) for row in rows]

    @staticmethod
    def list_citations_read_only(database: str | Path, session_id: str) -> list[Citation]:
        database_path = Path(database)
        if not database_path.is_file():
            return []
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'research_citations'"
            ).fetchone()
            if table is None:
                return []
            rows = connection.execute(
                """
                SELECT id, session_id, source_id, claim, locator, quote, created_at
                FROM research_citations
                WHERE session_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
            return [SQLiteEventStore._citation_from_row(row) for row in rows]
        finally:
            connection.close()

    def get_text_artifact(self, sha256: str) -> TextArtifact | None:
        with self._lock:
            row = (
                self._get_connection()
                .execute(
                    "SELECT sha256, content, byte_count FROM text_artifacts WHERE sha256 = ?",
                    (sha256,),
                )
                .fetchone()
            )
        return self._text_artifact_from_row(row) if row is not None else None

    def get_binary_artifact(self, sha256: str) -> BinaryArtifact | None:
        if not self._is_sha256(sha256):
            raise ValueError("binary artifact digest is invalid")
        with self._lock:
            row = (
                self._get_connection()
                .execute(
                    "SELECT sha256, content, byte_count FROM binary_artifacts WHERE sha256 = ?",
                    (sha256,),
                )
                .fetchone()
            )
        return self._binary_artifact_from_row(row) if row is not None else None

    def binary_artifact_stats(self) -> tuple[int, int]:
        with self._lock:
            row = (
                self._get_connection()
                .execute(
                    """
                SELECT COUNT(*) AS count, COALESCE(SUM(byte_count), 0) AS bytes
                FROM binary_artifacts
                """
                )
                .fetchone()
            )
        assert row is not None
        return cast(int, row["count"]), cast(int, row["bytes"])

    def garbage_collect_binary_artifacts(self) -> int:
        with self._lock:
            connection = self._get_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    DELETE FROM binary_artifacts
                    WHERE NOT EXISTS (
                        SELECT 1 FROM sandbox_change_artifacts AS r
                        WHERE r.artifact_sha256 = binary_artifacts.sha256
                    )
                      AND NOT EXISTS (
                          SELECT 1 FROM events AS e
                          WHERE e.type = 'image.attached'
                            AND json_extract(e.data_json, '$.sha256') = binary_artifacts.sha256
                      )
                    """
                )
                connection.commit()
                return cursor.rowcount
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    @staticmethod
    def get_binary_artifact_read_only(
        database: str | Path,
        sha256: str,
    ) -> BinaryArtifact | None:
        database_path = Path(database)
        if not database_path.is_file():
            return None
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'binary_artifacts'"
            ).fetchone()
            if table is None:
                return None
            row = connection.execute(
                "SELECT sha256, content, byte_count FROM binary_artifacts WHERE sha256 = ?",
                (sha256,),
            ).fetchone()
            return SQLiteEventStore._binary_artifact_from_row(row) if row is not None else None
        finally:
            connection.close()

    @staticmethod
    def get_text_artifact_read_only(
        database: str | Path,
        sha256: str,
    ) -> TextArtifact | None:
        database_path = Path(database)
        if not database_path.is_file():
            return None
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'text_artifacts'"
            ).fetchone()
            if table is None:
                return None
            row = connection.execute(
                "SELECT sha256, content, byte_count FROM text_artifacts WHERE sha256 = ?",
                (sha256,),
            ).fetchone()
            return SQLiteEventStore._text_artifact_from_row(row) if row is not None else None
        finally:
            connection.close()

    def list_memories(
        self,
        workspace: str,
        *,
        query: str = "",
        limit: int = 100,
    ) -> list[MemoryItem]:
        with self._lock:
            return self._list_memories(
                self._get_connection(),
                workspace,
                query=query,
                limit=limit,
            )

    @staticmethod
    def list_memories_read_only(
        database: str | Path,
        workspace: str,
        *,
        query: str = "",
        limit: int = 100,
    ) -> list[MemoryItem]:
        database_path = Path(database)
        if not database_path.is_file():
            return []
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'memories'"
            ).fetchone()
            if table is None:
                return []
            return SQLiteEventStore._list_memories(
                connection,
                workspace,
                query=query,
                limit=limit,
            )
        finally:
            connection.close()

    def get_memory(self, workspace: str, memory_id: str) -> MemoryItem | None:
        if not isinstance(workspace, str) or not workspace:
            raise ValueError("memory workspace must be non-empty")
        if not isinstance(memory_id, str) or not memory_id or len(memory_id) > 128:
            raise ValueError("memory id must be from 1 to 128 characters")
        with self._lock:
            row = (
                self._get_connection()
                .execute(
                    """
                    SELECT m.id, m.workspace, m.content, m.tags_json, o.source_session_id,
                           m.updated_by_session_id, o.created_at, m.updated_at, m.expires_at
                    FROM memories AS m
                    JOIN memory_id_owners AS o ON o.id = m.id
                    WHERE m.workspace = ? AND m.id = ? AND m.deleted = 0
                      AND (
                          m.expires_at IS NULL
                          OR m.expires_at > strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now')
                      )
                    """,
                    (workspace, memory_id),
                )
                .fetchone()
            )
        return SQLiteEventStore._memory_from_row(row) if row is not None else None

    def get_memory_owner_workspace(self, memory_id: str) -> str | None:
        if not isinstance(memory_id, str) or not memory_id or len(memory_id) > 128:
            raise ValueError("memory id must be from 1 to 128 characters")
        with self._lock:
            row = (
                self._get_connection()
                .execute(
                    "SELECT workspace FROM memory_id_owners WHERE id = ?",
                    (memory_id,),
                )
                .fetchone()
            )
        return cast(str, row["workspace"]) if row is not None else None

    @staticmethod
    def _list_memories(
        connection: sqlite3.Connection,
        workspace: str,
        *,
        query: str,
        limit: int,
    ) -> list[MemoryItem]:
        if not isinstance(workspace, str) or not workspace:
            raise ValueError("memory workspace must be non-empty")
        if not isinstance(query, str) or len(query) > 512:
            raise ValueError("memory query must be at most 512 characters")
        if not 1 <= limit <= 500:
            raise ValueError("memory result limit must be from 1 to 500")
        rows = connection.execute(
            """
            SELECT m.id, m.workspace, m.content, m.tags_json, o.source_session_id,
                   m.updated_by_session_id, o.created_at, m.updated_at, m.expires_at
            FROM memories AS m
            JOIN memory_id_owners AS o ON o.id = m.id
            WHERE m.workspace = ? AND m.deleted = 0
              AND (
                  m.expires_at IS NULL
                  OR m.expires_at > strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now')
              )
              AND (
                  ? = ''
                  OR instr(lower(m.content), lower(?)) > 0
                  OR instr(lower(m.tags_json), lower(?)) > 0
              )
            ORDER BY m.updated_at DESC, m.id ASC
            LIMIT ?
            """,
            (workspace, query, query, query, limit),
        ).fetchall()
        return [SQLiteEventStore._memory_from_row(row) for row in rows]

    @staticmethod
    def list_message_previews_read_only(
        database: str | Path,
        session_id: str,
        *,
        limit: int = 100,
        before_sequence: int | None = None,
        max_content_chars: int = 8192,
    ) -> list[SessionMessagePreview]:
        if not 0 <= limit <= 200:
            raise ValueError("message preview limit must be from 0 to 200")
        if not 1 <= max_content_chars <= 32768:
            raise ValueError("message preview content limit must be from 1 to 32768")
        if before_sequence is not None and before_sequence <= 0:
            raise ValueError("before_sequence must be positive")
        database_path = Path(database)
        if not database_path.is_file() or limit == 0:
            return []
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'events'"
            ).fetchone()
            if table is None:
                return []
            rows = connection.execute(
                """
                WITH recent AS (
                    SELECT sequence,
                           json_extract(data_json, '$.role') AS role,
                           json_extract(data_json, '$.content') AS content
                    FROM events
                    WHERE session_id = ?
                      AND (? IS NULL OR sequence < ?)
                      AND type = 'message.created'
                      AND json_extract(data_json, '$.role') IN ('user', 'assistant')
                    ORDER BY sequence DESC
                    LIMIT ?
                )
                SELECT role, substr(content, 1, ?) AS content, sequence,
                       length(content) > ? AS truncated
                FROM recent
                ORDER BY sequence ASC
                """,
                (
                    session_id,
                    before_sequence,
                    before_sequence,
                    limit,
                    max_content_chars,
                    max_content_chars,
                ),
            ).fetchall()
            return [
                SessionMessagePreview(
                    role=Role(cast(str, row["role"])),
                    content=cast(str, row["content"]),
                    sequence=cast(int, row["sequence"]),
                    truncated=bool(row["truncated"]),
                )
                for row in rows
            ]
        finally:
            connection.close()

    @staticmethod
    def get_message_content_read_only(
        database: str | Path,
        session_id: str,
        sequence: int,
    ) -> str | None:
        database_path = Path(database)
        if not database_path.is_file():
            return None
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            row = connection.execute(
                """
                SELECT json_extract(data_json, '$.content') AS content
                FROM events
                WHERE session_id = ? AND sequence = ? AND type = 'message.created'
                """,
                (session_id, sequence),
            ).fetchone()
            return cast(str, row["content"]) if row and row["content"] is not None else None
        finally:
            connection.close()

    @staticmethod
    def count_messages_read_only(
        database: str | Path,
        session_id: str,
    ) -> int:
        database_path = Path(database)
        if not database_path.is_file():
            return 0
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            row = connection.execute(
                """
                SELECT COUNT(1) AS count
                FROM events
                WHERE session_id = ?
                  AND type = 'message.created'
                  AND json_extract(data_json, '$.role') IN ('user', 'assistant')
                """,
                (session_id,),
            ).fetchone()
            return int(row["count"]) if row else 0
        finally:
            connection.close()

    @staticmethod
    def list_activity_events_read_only(
        database: str | Path,
        session_id: str,
        *,
        limit: int = 200,
    ) -> list[Event]:
        if not 0 <= limit <= _MAX_ACTIVITY_PREVIEW_ROWS:
            raise ValueError(
                f"activity preview limit must be from 0 to {_MAX_ACTIVITY_PREVIEW_ROWS}"
            )
        database_path = Path(database)
        if not database_path.is_file() or limit == 0:
            return []
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            rows = connection.execute(
                """
                WITH recent AS (
                    SELECT id, session_id, type, schema_version, sequence,
                           causation_id, correlation_id, created_at,
                           json_object(
                               'attempt_id', json_extract(data_json, '$.attempt_id'),
                               'tool_call_id', json_extract(data_json, '$.tool_call_id'),
                               'name', json_extract(data_json, '$.name'),
                               'tool', json_extract(data_json, '$.tool'),
                               'arguments', json_object(
                                   'path', substr(
                                       json_extract(data_json, '$.arguments.path'), 1, 1000
                                   ),
                                   'query', substr(
                                       json_extract(data_json, '$.arguments.query'), 1, 1000
                                   ),
                                   'pattern', substr(
                                       json_extract(data_json, '$.arguments.pattern'), 1, 1000
                                   )
                               ),
                                'error', substr(json_extract(data_json, '$.error'), 1, 2000),
                                'reason', substr(json_extract(data_json, '$.reason'), 1, 2000),
                                'message', substr(json_extract(data_json, '$.message'), 1, 2000),
                                'dropped_messages', json_extract(
                                    data_json, '$.dropped_messages'
                                )
                            ) AS data_json
                    FROM events
                    WHERE session_id = ?
                      AND (
                          type LIKE 'tool.%'
                          OR type IN ('turn.failed', 'turn.cancelled', 'context.compacted')
                      )
                    ORDER BY sequence DESC
                    LIMIT ?
                )
                SELECT id, session_id, type, data_json, schema_version, sequence,
                       causation_id, correlation_id, created_at
                FROM recent
                ORDER BY sequence ASC
                """,
                (session_id, limit),
            ).fetchall()
            return SQLiteEventStore._events_from_rows(rows)
        finally:
            connection.close()

    def list_sessions(
        self,
        limit: int = 50,
        *,
        workspace: str | Path | None = None,
        include_ids: Sequence[str] | None = None,
    ) -> list[Session]:
        if limit < 0:
            raise ValueError("limit must be non-negative")

        with self._lock:
            return self._query_sessions(
                self._get_connection(),
                limit,
                workspace=str(Path(workspace).resolve()) if workspace is not None else None,
                include_ids=include_ids,
            )

    def search_sessions(
        self,
        query: str,
        limit: int = 50,
        *,
        workspace: str | Path | None = None,
    ) -> list[SessionSearchResult]:
        with self._lock:
            return self._query_session_search(
                self._get_connection(),
                query,
                limit,
                workspace=str(Path(workspace).resolve()) if workspace is not None else None,
            )

    def get_session(self, session_id: str) -> Session | None:
        with self._lock:
            row = (
                self._get_connection()
                .execute(
                    """
                SELECT id, workspace, mode, autonomy, title, created_at, updated_at
                FROM sessions
                WHERE id = ?
                """,
                    (session_id,),
                )
                .fetchone()
            )
        return self._session_from_row(row) if row is not None else None

    @staticmethod
    def get_session_read_only(database: str | Path, session_id: str) -> Session | None:
        database_path = Path(database)
        if not database_path.is_file():
            return None
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'sessions'"
            ).fetchone()
            if table is None:
                return None
            row = connection.execute(
                """
                SELECT id, workspace, mode, autonomy, title, created_at, updated_at
                FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
            return SQLiteEventStore._session_from_row(row) if row is not None else None
        finally:
            connection.close()

    @staticmethod
    def list_sessions_read_only(
        database: str | Path,
        limit: int = 50,
        *,
        workspace: str | Path | None = None,
        include_ids: Sequence[str] | None = None,
        exclude_run_sessions: bool = False,
        offset: int = 0,
    ) -> list[Session]:
        if limit < 0:
            raise ValueError("limit must be non-negative")
        if offset < 0:
            raise ValueError("offset must be non-negative")

        connection = SQLiteEventStore._open_read_only(Path(database))
        try:
            connection.execute("PRAGMA query_only = ON")
            sessions_table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'sessions'"
            ).fetchone()
            if sessions_table is None:
                return []
            return SQLiteEventStore._query_sessions(
                connection,
                limit,
                workspace=str(Path(workspace).resolve()) if workspace is not None else None,
                include_ids=include_ids,
                exclude_run_sessions=exclude_run_sessions,
                offset=offset,
            )
        finally:
            connection.close()

    @staticmethod
    def list_queued_turns_read_only(
        database: str | Path,
        session_id: str,
        *,
        states: Sequence[str] = ("queued",),
    ) -> list[QueuedTurn]:
        if not session_id or len(session_id) > 128:
            raise ValueError("queued turn session id is invalid")
        if not states:
            return []
        database_path = Path(database)
        if not database_path.is_file():
            return []
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            connection.execute("PRAGMA query_only = ON")
            queued_table = connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'queued_turns'"
            ).fetchone()
            if queued_table is None:
                return []
            placeholders = ",".join("?" for _ in states)
            rows = connection.execute(
                f"""
                SELECT turn_id, session_id, prompt, references_json,
                       exclude_image_digests_json, state, created_at, updated_at,
                       reasoning_effort
                FROM queued_turns
                WHERE session_id = ? AND state IN ({placeholders})
                ORDER BY created_at ASC, turn_id ASC
                """,
                (session_id, *states),
            ).fetchall()
            result: list[QueuedTurn] = []
            for row in rows:
                refs = tuple(json.loads(row[3])) if row[3] else ()
                excluded = frozenset(json.loads(row[4])) if row[4] else frozenset()
                result.append(
                    QueuedTurn(
                        turn_id=row[0],
                        session_id=row[1],
                        prompt=row[2],
                        references=refs,
                        state=row[5],
                        created_at=row[6],
                        updated_at=row[7],
                        exclude_image_digests=excluded,
                        reasoning_effort=row[8],
                    )
                )
            return result
        finally:
            connection.close()

    @staticmethod
    def search_sessions_read_only(
        database: str | Path,
        query: str,
        limit: int = 50,
        *,
        workspace: str | Path | None = None,
        exclude_run_sessions: bool = False,
    ) -> list[SessionSearchResult]:
        SQLiteEventStore._validate_search_request(query, limit)
        database_path = Path(database)
        if not database_path.is_file():
            return []
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            tables = {
                cast(str, row[0])
                for row in connection.execute(
                    """
                    SELECT name FROM sqlite_schema
                    WHERE type = 'table' AND name IN ('search_documents', 'session_search')
                    """
                ).fetchall()
            }
            if tables != {"search_documents", "session_search"}:
                raise SearchIndexUnavailableError(
                    "session search index is unavailable; open the database with the current "
                    "writable runtime to migrate it"
                )
            if not SQLiteEventStore._search_index_is_consistent(connection):
                raise SearchIndexUnavailableError(
                    "session search index is inconsistent; open the database with the current "
                    "writable runtime to rebuild it"
                )
            return SQLiteEventStore._query_session_search(
                connection,
                query,
                limit,
                workspace=str(Path(workspace).resolve()) if workspace is not None else None,
                exclude_run_sessions=exclude_run_sessions,
            )
        finally:
            connection.close()

    @staticmethod
    def search_sessions_hybrid(
        database: str | Path,
        query: str,
        limit: int = 50,
        *,
        workspace: str | Path | None = None,
    ) -> list[SessionSearchResult]:
        """Search FTS first, then always backfill with literal substring hits.

        The regular search path only falls back to literal matching for
        non-ASCII queries. Hybrid mode uses both retrievers for every query,
        which improves recall for punctuation-heavy and short ASCII terms
        while keeping FTS BM25-ranked hits first.
        """
        results = SQLiteEventStore.search_sessions_read_only(
            database,
            query,
            limit=limit,
            workspace=workspace,
        )
        if not results or len(results) >= limit:
            return results
        terms = query.split()
        if not terms:
            return results
        database_path = Path(database)
        connection = SQLiteEventStore._open_read_only(database_path)
        try:
            seen = {result.session.id for result in results}
            for result in SQLiteEventStore._query_session_substrings(
                connection,
                terms,
                limit=limit,
                workspace=str(Path(workspace).resolve()) if workspace is not None else None,
            ):
                if result.session.id not in seen:
                    results.append(result)
                    seen.add(result.session.id)
                    if len(results) >= limit:
                        break
            return results
        finally:
            connection.close()

    @staticmethod
    def _open_read_only(database: Path) -> sqlite3.Connection:
        uri = f"{database.resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(
            uri,
            timeout=_BUSY_TIMEOUT_MS / 1_000,
            isolation_level=None,
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    @staticmethod
    def _query_sessions(
        connection: sqlite3.Connection,
        limit: int,
        *,
        workspace: str | None = None,
        include_ids: Sequence[str] | None = None,
        exclude_run_sessions: bool = False,
        offset: int = 0,
    ) -> list[Session]:
        visible = SQLiteEventStore._conversation_session_filter(
            connection, "sessions", exclude_run_sessions
        )
        rows = connection.execute(
            f"""
            SELECT id, workspace, mode, autonomy, title, created_at, updated_at
            FROM sessions
            WHERE (? IS NULL OR workspace = ?) AND {visible}
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (workspace, workspace, limit, offset),
        ).fetchall()

        sessions = [SQLiteEventStore._session_from_row(row) for row in rows]
        if include_ids:
            found_ids = {s.id for s in sessions}
            missing_ids = [sid for sid in include_ids if sid not in found_ids]
            if missing_ids:
                placeholders = ",".join("?" for _ in missing_ids)
                if workspace is None:
                    extra_rows = connection.execute(
                        f"""
                        SELECT id, workspace, mode, autonomy, title, created_at, updated_at
                        FROM sessions
                        WHERE id IN ({placeholders})
                          AND {visible}
                        """,
                        missing_ids,
                    ).fetchall()
                else:
                    extra_rows = connection.execute(
                        f"""
                        SELECT id, workspace, mode, autonomy, title, created_at, updated_at
                        FROM sessions
                        WHERE workspace = ? AND id IN ({placeholders})
                          AND {visible}
                        """,
                        [workspace, *missing_ids],
                    ).fetchall()
                sessions.extend(SQLiteEventStore._session_from_row(r) for r in extra_rows)

        return sessions

    @staticmethod
    def _conversation_session_filter(
        connection: sqlite3.Connection, alias: str, enabled: bool
    ) -> str:
        if (
            not enabled
            or connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type='table' AND name='agent_runs'"
            ).fetchone()
            is None
        ):
            return "1"
        # Execution sessions are surfaced by the task center, not as empty chats.
        # Execution sessions are created after their run. Keep excluding them
        # after checkout cleanup; owner sessions predate the run and remain visible.
        return (
            f"NOT EXISTS (SELECT 1 FROM agent_runs r WHERE r.session_id = {alias}.id "
            f"AND {alias}.created_at > r.created_at)"
        )

    @staticmethod
    def _query_session_search(
        connection: sqlite3.Connection,
        query: str,
        limit: int,
        *,
        workspace: str | None,
        exclude_run_sessions: bool = False,
    ) -> list[SessionSearchResult]:
        terms = SQLiteEventStore._validate_search_request(query, limit)
        normalized_query = SQLiteEventStore._fts_literal_query(terms)
        if limit == 0:
            return []
        visible = SQLiteEventStore._conversation_session_filter(
            connection, "s", exclude_run_sessions
        )
        rows = connection.execute(
            f"""
            WITH hits AS (
                SELECT d.session_id, d.kind, d.sequence,
                       snippet(session_search, 0, '[', ']', '...', 18) AS snippet,
                       bm25(session_search) AS rank
                FROM session_search
                JOIN search_documents AS d ON d.rowid = session_search.rowid
                WHERE session_search MATCH ?
            ),
            ranked AS (
                SELECT session_id, kind, sequence, snippet, rank,
                       ROW_NUMBER() OVER (
                           PARTITION BY session_id
                           ORDER BY rank ASC, sequence DESC
                       ) AS hit_number
                FROM hits
            )
            SELECT s.id, s.workspace, s.mode, s.autonomy, s.title,
                   s.created_at, s.updated_at,
                   ranked.kind, ranked.snippet, ranked.rank
            FROM ranked
            JOIN sessions AS s ON s.id = ranked.session_id
            WHERE ranked.hit_number = 1
              AND (? IS NULL OR s.workspace = ?)
              AND {visible}
            ORDER BY ranked.rank ASC, s.updated_at DESC, s.id DESC
            LIMIT ?
            """,
            (normalized_query, workspace, workspace, limit),
        ).fetchall()
        results = [
            SessionSearchResult(
                session=SQLiteEventStore._session_from_row(row),
                snippet=cast(str, row["snippet"]),
                document_kind=cast(str, row["kind"]),
                rank=float(row["rank"]),
            )
            for row in rows
        ]
        if len(results) >= limit or not any(not term.isascii() for term in terms):
            return results
        seen = {result.session.id for result in results}
        for result in SQLiteEventStore._query_session_substrings(
            connection,
            terms,
            limit=limit,
            workspace=workspace,
            exclude_run_sessions=exclude_run_sessions,
        ):
            if result.session.id not in seen:
                results.append(result)
                seen.add(result.session.id)
                if len(results) >= limit:
                    break
        return results

    @staticmethod
    def _validate_search_request(query: str, limit: int) -> list[str]:
        if not 0 <= limit <= _MAX_SEARCH_RESULTS:
            raise ValueError(f"session search limit must be from 0 to {_MAX_SEARCH_RESULTS}")
        if len(query) > _MAX_SEARCH_QUERY_CHARACTERS:
            raise ValueError(
                f"session search query exceeds {_MAX_SEARCH_QUERY_CHARACTERS} characters"
            )
        terms = query.split()
        if not terms:
            raise ValueError("session search query may not be empty")
        if len(terms) > _MAX_SEARCH_TERMS:
            raise ValueError(f"session search query may contain at most {_MAX_SEARCH_TERMS} terms")
        return terms

    @staticmethod
    def _fts_literal_query(terms: list[str]) -> str:
        expression = " AND ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)
        return f"text : ({expression})"

    @staticmethod
    def _query_session_substrings(
        connection: sqlite3.Connection,
        terms: list[str],
        *,
        limit: int,
        workspace: str | None,
        exclude_run_sessions: bool = False,
    ) -> list[SessionSearchResult]:
        predicates = " AND ".join("d.text LIKE ? ESCAPE '\\'" for _ in terms)
        patterns = [f"%{SQLiteEventStore._escape_like(term)}%" for term in terms]
        visible = SQLiteEventStore._conversation_session_filter(
            connection, "s", exclude_run_sessions
        )
        rows = connection.execute(
            f"""
            WITH ranked AS (
                SELECT s.id, s.workspace, s.mode, s.autonomy, s.title,
                       s.created_at, s.updated_at,
                       d.kind, d.sequence, d.text,
                       ROW_NUMBER() OVER (
                           PARTITION BY s.id
                           ORDER BY d.sequence DESC, d.id DESC
                       ) AS hit_number
                FROM search_documents AS d
                JOIN sessions AS s ON s.id = d.session_id
                WHERE {predicates}
                  AND (? IS NULL OR s.workspace = ?)
                  AND {visible}
            )
            SELECT id, workspace, mode, autonomy, title, created_at, updated_at,
                   kind, text
            FROM ranked
            WHERE hit_number = 1
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (*patterns, workspace, workspace, limit),
        ).fetchall()
        return [
            SessionSearchResult(
                session=SQLiteEventStore._session_from_row(row),
                snippet=SQLiteEventStore._substring_snippet(cast(str, row["text"]), terms),
                document_kind=cast(str, row["kind"]),
                rank=0.0,
            )
            for row in rows
        ]

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @staticmethod
    def _search_integrity_token(document_id: str, text: str) -> str:
        payload = f"{document_id}\0{text}".encode()
        return f"z{hashlib.sha256(payload).hexdigest()}"

    @staticmethod
    def _substring_snippet(text: str, terms: list[str]) -> str:
        flattened = " ".join(text.split())
        matches = [(index, len(term)) for term in terms if (index := flattened.find(term)) >= 0]
        if not matches:
            return flattened[:160]
        index, length = min(matches)
        start = max(index - 60, 0)
        end = min(index + length + 80, len(flattened))
        prefix = "..." if start else ""
        suffix = "..." if end < len(flattened) else ""
        return (
            f"{prefix}{flattened[start:index]}[{flattened[index : index + length]}]"
            f"{flattened[index + length : end]}{suffix}"
        )

    @staticmethod
    def _session_from_row(row: sqlite3.Row) -> Session:
        return Session(
            id=cast(str, row["id"]),
            workspace=cast(str, row["workspace"]),
            mode=Mode(cast(str, row["mode"])),
            autonomy=Autonomy(cast(str, row["autonomy"])),
            title=cast(str, row["title"]),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
        )

    @staticmethod
    def _todo_from_row(row: sqlite3.Row) -> TodoItem:
        return TodoItem(
            id=cast(str, row["id"]),
            session_id=cast(str, row["session_id"]),
            content=cast(str, row["content"]),
            status=TodoStatus(cast(str, row["status"])),
            position=cast(int, row["position"]),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
        )

    @staticmethod
    def _research_source_from_row(row: sqlite3.Row) -> ResearchSource:
        return ResearchSource(
            id=cast(str, row["id"]),
            session_id=cast(str, row["session_id"]),
            url=cast(str, row["url"]),
            title=cast(str | None, row["title"]),
            artifact_sha256=cast(str, row["artifact_sha256"]),
            artifact_bytes=cast(int, row["artifact_bytes"]),
            response_sha256=cast(str, row["response_sha256"]),
            response_bytes=cast(int, row["response_bytes"]),
            media_type=cast(str, row["media_type"]),
            fetched_at=cast(str, row["fetched_at"]),
            truncated=bool(row["truncated"]),
            summary=cast(str, row["summary"]),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
        )

    @staticmethod
    def _citation_from_row(row: sqlite3.Row) -> Citation:
        return Citation(
            id=cast(str, row["id"]),
            session_id=cast(str, row["session_id"]),
            source_id=cast(str, row["source_id"]),
            claim=cast(str, row["claim"]),
            locator=cast(str | None, row["locator"]),
            quote=cast(str | None, row["quote"]),
            created_at=cast(str, row["created_at"]),
        )

    @staticmethod
    def _text_artifact_from_row(row: sqlite3.Row) -> TextArtifact:
        return TextArtifact(
            sha256=cast(str, row["sha256"]),
            content=cast(bytes, row["content"]),
            byte_count=cast(int, row["byte_count"]),
        )

    @staticmethod
    def _binary_artifact_from_row(row: sqlite3.Row) -> BinaryArtifact:
        content = cast(bytes, row["content"])
        if len(content) != cast(int, row["byte_count"]):
            raise ValueError("binary artifact byte count is invalid")
        return BinaryArtifact(sha256=cast(str, row["sha256"]), content=content)

    @staticmethod
    def _background_job_from_row(row: sqlite3.Row) -> BackgroundJobStatus:
        return BackgroundJobStatus(
            job_id=cast(str, row["job_id"]),
            session_id=cast(str, row["session_id"]),
            label=cast(str, row["label"]),
            state=cast(str, row["state"]),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
            result=cast(str | None, row["result"]),
            terminal_reason=cast(str | None, row["terminal_reason"]),
        )

    @staticmethod
    def _memory_from_row(row: sqlite3.Row) -> MemoryItem:
        raw_tags = json.loads(cast(str, row["tags_json"]))
        if not isinstance(raw_tags, list) or any(not isinstance(tag, str) for tag in raw_tags):
            raise ValueError("memory tags projection is invalid")
        return MemoryItem(
            id=cast(str, row["id"]),
            workspace=cast(str, row["workspace"]),
            content=cast(str, row["content"]),
            tags=tuple(raw_tags),
            source_session_id=cast(str, row["source_session_id"]),
            updated_by_session_id=cast(str, row["updated_by_session_id"]),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
            expires_at=cast(str | None, row["expires_at"]),
        )

    @staticmethod
    def _tool_attempt_from_row(row: sqlite3.Row) -> ToolAttempt:
        return ToolAttempt(
            id=cast(str, row["id"]),
            session_id=cast(str, row["session_id"]),
            tool_call_id=cast(str, row["tool_call_id"]),
            tool_name=cast(str, row["tool_name"]),
            idempotency_key=cast(str, row["idempotency_key"]),
            state=ToolAttemptState(cast(str, row["state"])),
            proposed_event_id=cast(str, row["proposed_event_id"]),
            started_event_id=cast(str | None, row["started_event_id"]),
            terminal_event_id=cast(str | None, row["terminal_event_id"]),
        )

    @staticmethod
    def _file_checkpoint_from_row(row: sqlite3.Row) -> FileCheckpoint:
        protected_preimage = cast(bytes | None, row["protected_preimage"])
        preimage = (
            unprotect_checkpoint_preimage(
                protected_preimage,
                attempt_id=cast(str, row["attempt_id"]),
                session_id=cast(str, row["session_id"]),
                workspace=cast(str, row["workspace"]),
                relative_path=cast(str, row["relative_path"]),
            )
            if protected_preimage is not None
            else None
        )
        return FileCheckpoint(
            attempt_id=cast(str, row["attempt_id"]),
            session_id=cast(str, row["session_id"]),
            workspace=cast(str, row["workspace"]),
            started_event_id=cast(str, row["started_event_id"]),
            relative_path=cast(str, row["relative_path"]),
            preimage_sha256=cast(str | None, row["preimage_sha256"]),
            preimage=preimage,
            postimage_sha256=cast(str | None, row["postimage_sha256"]),
            created_at=cast(str, row["created_at"]),
            preimage_executable=(
                bool(row["preimage_executable"]) if row["preimage_executable"] is not None else None
            ),
            postimage_executable=(
                bool(row["postimage_executable"])
                if row["postimage_executable"] is not None
                else None
            ),
            preimage_kind=cast(str, row["preimage_kind"]),
            postimage_kind=cast(str, row["postimage_kind"]),
        )

    def close(self) -> None:
        with self._lock:
            if self._connection is None:
                return
            self._connection.close()
            self._connection = None

    @staticmethod
    def _project_event(
        connection: sqlite3.Connection,
        event: Event,
        *,
        projection_version: int = CURRENT_SCHEMA_VERSION,
    ) -> None:
        if event.type == "mode.changed":
            from_mode = event.data.get("from_mode")
            to_mode = event.data.get("to_mode")
            try:
                source = Mode(cast(str, from_mode))
                target = Mode(cast(str, to_mode))
            except (TypeError, ValueError):
                raise ValueError("mode.changed contains invalid projection fields") from None
            if source is target:
                raise ValueError("mode.changed must change the session mode")
            cursor = connection.execute(
                "UPDATE sessions SET mode = ? WHERE id = ? AND mode = ?",
                (target.value, event.session_id, source.value),
            )
            if cursor.rowcount != 1:
                raise ValueError("mode.changed does not match the current session mode")
            return
        if event.type == "autonomy.changed":
            from_autonomy = event.data.get("from_autonomy")
            to_autonomy = event.data.get("to_autonomy")
            try:
                source_autonomy = Autonomy(cast(str, from_autonomy))
                target_autonomy = Autonomy(cast(str, to_autonomy))
            except (TypeError, ValueError):
                raise ValueError("autonomy.changed contains invalid projection fields") from None
            if source_autonomy is target_autonomy:
                raise ValueError("autonomy.changed must change the session autonomy")
            cursor = connection.execute(
                "UPDATE sessions SET autonomy = ? WHERE id = ? AND autonomy = ?",
                (target_autonomy.value, event.session_id, source_autonomy.value),
            )
            if cursor.rowcount != 1:
                raise ValueError("autonomy.changed does not match the current session autonomy")
            return
        if (
            projection_version >= 5
            and event.type == "message.created"
            and event.data.get("role") == "user"
        ):
            content = event.data.get("content")
            if isinstance(content, str) and content:
                document_id = f"event:{event.id}"
                connection.execute(
                    """
                    INSERT INTO search_documents (
                        id, session_id, kind, sequence, text, integrity_token
                    )
                    VALUES (?, ?, 'user_message', ?, ?, ?)
                    """,
                    (
                        document_id,
                        event.session_id,
                        event.sequence,
                        content,
                        SQLiteEventStore._search_integrity_token(document_id, content),
                    ),
                )
            return
        if projection_version >= 3 and event.type == "todo.upserted":
            SQLiteEventStore._project_todo_upsert(
                connection,
                event,
                enforce_ownership=projection_version >= 4,
            )
            return
        if projection_version >= 3 and event.type == "todo.deleted":
            SQLiteEventStore._validate_todo_attempt(connection, event)
            todo_id = SQLiteEventStore._event_string(event, "todo_id")
            if todo_id is None:
                raise ValueError("todo.deleted is missing its todo id")
            cursor = connection.execute(
                "DELETE FROM todos WHERE id = ? AND session_id = ?",
                (todo_id, event.session_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("cannot delete an unknown todo")
            SQLiteEventStore._normalize_todo_positions(connection, event.session_id)
            return
        if projection_version >= 7 and event.type == "research.source.saved":
            SQLiteEventStore._project_research_source(connection, event)
            return
        if projection_version >= 7 and event.type == "research.citation.added":
            SQLiteEventStore._project_research_citation(connection, event)
            return
        if projection_version >= 8 and event.type == "memory.upserted":
            SQLiteEventStore._project_memory_upsert(connection, event)
            return
        if projection_version >= 8 and event.type == "memory.deleted":
            SQLiteEventStore._project_memory_delete(connection, event)
            return
        if projection_version >= 9 and event.type == "sandbox.changeset.created":
            SQLiteEventStore._validate_sandbox_changeset_creation(
                connection,
                event,
                project_artifacts=projection_version >= 11,
                project_state=projection_version >= 13,
            )
            return
        if projection_version >= 9 and event.type == "sandbox.change.applied":
            SQLiteEventStore._validate_sandbox_change_application(
                connection,
                event,
                project_state=projection_version >= 13,
            )
            return
        if projection_version >= 9 and event.type == "sandbox.change.applied.imported":
            # Imported application records are audit-only by design: an archive
            # carries no workspace files, so operational application state is
            # reset and these events must not project onto sandbox_change_states.
            return
        if projection_version >= 9 and event.type == "sandbox.change.reviewed":
            SQLiteEventStore._validate_sandbox_change_review(
                connection,
                event,
                project_state=projection_version >= 13,
            )
            return
        if projection_version >= 13 and event.type.startswith("background.job."):
            SQLiteEventStore._project_background_job(connection, event)
            return

        if projection_version < 2:
            return
        transitions: dict[str, tuple[tuple[str, ...], ToolAttemptState]] = {
            "tool.approved": ((ToolAttemptState.PROPOSED.value,), ToolAttemptState.APPROVED),
            "tool.started": ((ToolAttemptState.APPROVED.value,), ToolAttemptState.STARTED),
            "tool.settled": ((ToolAttemptState.STARTED.value,), ToolAttemptState.SETTLED),
            "tool.failed": ((ToolAttemptState.STARTED.value,), ToolAttemptState.FAILED),
            "tool.rejected": ((ToolAttemptState.PROPOSED.value,), ToolAttemptState.REJECTED),
            "tool.cancelled": (
                (ToolAttemptState.PROPOSED.value, ToolAttemptState.APPROVED.value),
                ToolAttemptState.CANCELLED,
            ),
            "tool.unknown": ((ToolAttemptState.STARTED.value,), ToolAttemptState.UNKNOWN),
        }
        if event.type == "tool.proposed":
            attempt_id = SQLiteEventStore._event_string(event, "attempt_id")
            tool_call_id = SQLiteEventStore._event_string(event, "tool_call_id")
            tool_name = SQLiteEventStore._event_string(event, "name")
            idempotency_key = SQLiteEventStore._event_string(event, "idempotency_key")
            if attempt_id is None:
                return
            if tool_call_id is None or tool_name is None or idempotency_key is None:
                raise ValueError("tool.proposed is missing projection fields")
            connection.execute(
                """
                INSERT INTO tool_attempts (
                    id, session_id, tool_call_id, tool_name, idempotency_key, state,
                    proposed_event_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'proposed', ?, ?)
                """,
                (
                    attempt_id,
                    event.session_id,
                    tool_call_id,
                    tool_name,
                    idempotency_key,
                    event.id,
                    event.created_at,
                ),
            )
            return

        transition = transitions.get(event.type)
        if transition is None:
            return
        attempt_id = SQLiteEventStore._event_string(event, "attempt_id")
        if attempt_id is None:
            return
        tool_call_id = SQLiteEventStore._event_string(event, "tool_call_id")
        if tool_call_id is None:
            raise ValueError(f"{event.type} is missing its tool call id")
        allowed_states, next_state = transition
        placeholders = ", ".join("?" for _ in allowed_states)
        columns = "state = ?, updated_at = ?"
        values: list[object] = [next_state.value, event.created_at]
        if event.type == "tool.started":
            columns += ", started_event_id = ?"
            values.append(event.id)
        if next_state in {
            ToolAttemptState.SETTLED,
            ToolAttemptState.FAILED,
            ToolAttemptState.REJECTED,
            ToolAttemptState.CANCELLED,
            ToolAttemptState.UNKNOWN,
        }:
            columns += ", terminal_event_id = ?"
            values.append(event.id)
        values.extend((attempt_id, event.session_id, tool_call_id, *allowed_states))
        cursor = connection.execute(
            f"UPDATE tool_attempts SET {columns} "
            f"WHERE id = ? AND session_id = ? AND tool_call_id = ? "
            f"AND state IN ({placeholders})",
            values,
        )
        if cursor.rowcount != 1:
            raise ValueError(f"invalid tool attempt transition: {event.type}")
        checkpoint_terminal_states = {
            ToolAttemptState.SETTLED,
            ToolAttemptState.FAILED,
            ToolAttemptState.REJECTED,
            ToolAttemptState.CANCELLED,
        }
        if projection_version < 23:
            checkpoint_terminal_states.add(ToolAttemptState.UNKNOWN)
        if projection_version >= 6 and next_state in checkpoint_terminal_states:
            connection.execute(
                "DELETE FROM file_checkpoints WHERE attempt_id = ? AND session_id = ?",
                (attempt_id, event.session_id),
            )

    @staticmethod
    def _project_session(connection: sqlite3.Connection, session: Session) -> None:
        if not session.title:
            return
        document_id = f"session:{session.id}:title"
        connection.execute(
            """
            INSERT INTO search_documents (
                id, session_id, kind, sequence, text, integrity_token
            ) VALUES (?, ?, 'title', 0, ?, ?)
            """,
            (
                document_id,
                session.id,
                session.title,
                SQLiteEventStore._search_integrity_token(document_id, session.title),
            ),
        )

    @staticmethod
    def _event_string(event: Event, key: str) -> str | None:
        value = event.data.get(key)
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _is_sha256(value: object) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    @staticmethod
    def _is_relative_checkpoint_path(value: str) -> bool:
        return (
            bool(value)
            and "\\" not in value
            and not value.startswith("/")
            and all(part not in {"", ".", ".."} for part in value.split("/"))
        )

    @staticmethod
    def _validate_sandbox_changeset_creation(
        connection: sqlite3.Connection,
        event: Event,
        *,
        project_artifacts: bool = True,
        project_state: bool = False,
    ) -> None:
        SQLiteEventStore._validate_sandbox_attempt(connection, event, "run_sandbox")
        workspace = SQLiteEventStore._event_string(event, "workspace")
        session = connection.execute(
            "SELECT workspace FROM sessions WHERE id = ?",
            (event.session_id,),
        ).fetchone()
        if session is None or workspace != session["workspace"]:
            raise ValueError("sandbox changeset workspace does not match its session")
        if project_artifacts:
            SQLiteEventStore._project_sandbox_change_artifacts(connection, event)
        if project_state:
            changeset_id = SQLiteEventStore._event_string(event, "changeset_id")
            changes = event.data.get("changes")
            if changeset_id is None or not isinstance(changes, list):
                raise ValueError("sandbox changeset state fields are invalid")
            for change in changes:
                path = change.get("path") if isinstance(change, dict) else None
                if not isinstance(path, str):
                    raise ValueError("sandbox changeset state path is invalid")
                try:
                    connection.execute(
                        """
                        INSERT INTO sandbox_change_states (
                            session_id, changeset_id, path, updated_at
                        ) VALUES (?, ?, ?, ?)
                        ON CONFLICT (session_id, changeset_id, path) DO NOTHING
                        """,
                        (event.session_id, changeset_id, path, event.created_at),
                    )
                except sqlite3.IntegrityError:
                    raise ValueError("sandbox changeset state identity conflicts") from None

    @staticmethod
    def _project_sandbox_change_artifacts(
        connection: sqlite3.Connection,
        event: Event,
        *,
        enforce_storage_limit: bool = True,
    ) -> None:
        changeset_id = SQLiteEventStore._event_string(event, "changeset_id")
        changes = event.data.get("changes")
        if changeset_id is None or not isinstance(changes, list):
            raise ValueError("sandbox changeset artifact projection fields are invalid")
        for change in changes:
            if not isinstance(change, dict):
                raise ValueError("sandbox changeset artifact projection is invalid")
            path = change.get("path")
            artifact_sha256 = change.get("artifact_sha256")
            if event.data.get("format_version") != 2:
                after_text = change.get("after_text")
                artifact_sha256 = (
                    hashlib.sha256(after_text.encode("utf-8")).hexdigest()
                    if isinstance(after_text, str)
                    else None
                )
                if artifact_sha256 is not None:
                    content = cast(str, after_text).encode("utf-8")
                    SQLiteEventStore._insert_binary_artifacts(
                        connection,
                        (BinaryArtifact(artifact_sha256, content),),
                        enforce_storage_limit=enforce_storage_limit,
                    )
            if artifact_sha256 is None:
                continue
            if not isinstance(path, str):
                raise ValueError("sandbox changeset artifact path is invalid")
            artifact = connection.execute(
                "SELECT content, byte_count FROM binary_artifacts WHERE sha256 = ?",
                (artifact_sha256,),
            ).fetchone()
            if (
                artifact is None
                or hashlib.sha256(cast(bytes, artifact["content"])).hexdigest() != artifact_sha256
                or artifact["byte_count"] != len(cast(bytes, artifact["content"]))
                or (
                    event.data.get("format_version") == 2
                    and artifact["byte_count"] != change.get("artifact_bytes")
                )
            ):
                raise ValueError("sandbox changeset artifact is unavailable or corrupt")
            connection.execute(
                """
                INSERT INTO sandbox_change_artifacts (
                    session_id, changeset_id, path, artifact_sha256, created_event_id
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (session_id, changeset_id, path) DO NOTHING
                """,
                (event.session_id, changeset_id, path, artifact_sha256, event.id),
            )
            projected = connection.execute(
                """
                SELECT artifact_sha256
                FROM sandbox_change_artifacts
                WHERE session_id = ? AND changeset_id = ? AND path = ?
                """,
                (event.session_id, changeset_id, path),
            ).fetchone()
            if projected is None or projected["artifact_sha256"] != artifact_sha256:
                raise ValueError("sandbox changeset artifact projection conflicts")

    @staticmethod
    def _validate_sandbox_change_application(
        connection: sqlite3.Connection,
        event: Event,
        *,
        project_state: bool = False,
    ) -> None:
        SQLiteEventStore._validate_sandbox_attempt(connection, event, "apply_sandbox_change")
        changeset_id = SQLiteEventStore._event_string(event, "changeset_id")
        path = SQLiteEventStore._event_string(event, "path")
        if changeset_id is None or path is None:
            raise ValueError("sandbox change application is missing its identity")
        created = connection.execute(
            """
            SELECT data_json
            FROM events
            WHERE session_id = ?
              AND sequence < ?
              AND type = 'sandbox.changeset.created'
              AND json_extract(data_json, '$.changeset_id') = ?
            ORDER BY sequence DESC
            LIMIT 1
            """,
            (event.session_id, event.sequence, changeset_id),
        ).fetchone()
        if created is None:
            raise ValueError("sandbox change application has no changeset in this session")
        raw_data = json.loads(cast(str, created["data_json"]))
        if not isinstance(raw_data, dict):
            raise ValueError("sandbox changeset event data is invalid")
        change = get_sandbox_change(cast(dict[str, Any], raw_data), path)
        if (
            change is None
            or change.get("apply_supported") is not True
            or change.get("before_sha256") != event.data.get("before_sha256")
            or change.get("after_sha256") != event.data.get("after_sha256")
            or (
                event.data.get("format_version") == 2
                and (
                    change.get("before_type") != event.data.get("before_type")
                    or change.get("after_type") != event.data.get("after_type")
                )
            )
        ):
            raise ValueError("sandbox applied event does not match its changeset")
        prior = connection.execute(
            """
            SELECT 1
            FROM events
            WHERE session_id = ?
              AND sequence < ?
              AND type = 'sandbox.change.applied'
              AND json_extract(data_json, '$.changeset_id') = ?
              AND json_extract(data_json, '$.path') = ?
            LIMIT 1
            """,
            (event.session_id, event.sequence, changeset_id, path),
        ).fetchone()
        if prior is not None:
            raise ValueError("sandbox change was already applied")
        if project_state:
            state = connection.execute(
                """
                SELECT review_decision, applied
                FROM sandbox_change_states
                WHERE session_id = ? AND changeset_id = ? AND path = ?
                """,
                (event.session_id, changeset_id, path),
            ).fetchone()
            if state is None:
                raise ValueError("sandbox change application state is unavailable")
            if state["review_decision"] == "rejected":
                raise ValueError("sandbox change was explicitly rejected")
            if state["applied"] == 1:
                raise ValueError("sandbox change was already applied")
            cursor = connection.execute(
                """
                UPDATE sandbox_change_states
                SET applied = 1, applied_event_id = ?, updated_at = ?
                WHERE session_id = ? AND changeset_id = ? AND path = ?
                  AND applied = 0
                  AND (review_decision IS NULL OR review_decision = 'approved')
                """,
                (event.id, event.created_at, event.session_id, changeset_id, path),
            )
            if cursor.rowcount != 1:
                raise ValueError("sandbox change application state changed concurrently")

    @staticmethod
    def _validate_sandbox_change_review(
        connection: sqlite3.Connection,
        event: Event,
        *,
        project_state: bool = False,
    ) -> None:
        tool_name = SQLiteEventStore._validate_sandbox_attempt(
            connection,
            event,
            ("review_sandbox_change", "apply_sandbox_change"),
        )
        changeset_id = SQLiteEventStore._event_string(event, "changeset_id")
        path = SQLiteEventStore._event_string(event, "path")
        if changeset_id is None or path is None:
            raise ValueError("sandbox change review is missing its identity")
        created = connection.execute(
            """
            SELECT data_json
            FROM events
            WHERE session_id = ?
              AND sequence < ?
              AND type = 'sandbox.changeset.created'
              AND json_extract(data_json, '$.changeset_id') = ?
            ORDER BY sequence DESC
            LIMIT 1
            """,
            (event.session_id, event.sequence, changeset_id),
        ).fetchone()
        if created is None:
            raise ValueError("sandbox change review has no changeset in this session")
        data = json.loads(cast(str, created["data_json"]))
        if (
            not isinstance(data, dict)
            or get_sandbox_change(cast(dict[str, Any], data), path) is None
        ):
            raise ValueError("sandbox change review path is unknown")
        if project_state:
            decision = event.data.get("decision")
            state = connection.execute(
                """
                SELECT review_decision, applied
                FROM sandbox_change_states
                WHERE session_id = ? AND changeset_id = ? AND path = ?
                """,
                (event.session_id, changeset_id, path),
            ).fetchone()
            if state is None:
                raise ValueError("sandbox change review state is unavailable")
            if state["applied"] == 1:
                raise ValueError("an applied sandbox change cannot be reviewed again")
            if tool_name == "apply_sandbox_change":
                if decision != "approved" or state["review_decision"] == "rejected":
                    raise ValueError("apply approval cannot override a sandbox rejection")
                if state["review_decision"] == "approved":
                    return
            cursor = connection.execute(
                """
                UPDATE sandbox_change_states
                SET review_decision = ?, review_event_id = ?, updated_at = ?
                WHERE session_id = ? AND changeset_id = ? AND path = ? AND applied = 0
                """,
                (
                    decision,
                    event.id,
                    event.created_at,
                    event.session_id,
                    changeset_id,
                    path,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("sandbox change review state changed concurrently")

    @staticmethod
    def _validate_sandbox_attempt(
        connection: sqlite3.Connection,
        event: Event,
        tool_name: str | tuple[str, ...],
    ) -> str:
        attempt_id = SQLiteEventStore._event_string(event, "attempt_id")
        if attempt_id is None:
            raise ValueError("sandbox event is missing its attempt id")
        tool_names = (tool_name,) if isinstance(tool_name, str) else tool_name
        placeholders = ", ".join("?" for _ in tool_names)
        attempt = connection.execute(
            f"""
            SELECT started_event_id, tool_name
            FROM tool_attempts
            WHERE id = ? AND session_id = ? AND tool_name IN ({placeholders})
              AND state = 'started'
            """,
            (attempt_id, event.session_id, *tool_names),
        ).fetchone()
        if attempt is None or attempt["started_event_id"] != event.causation_id:
            raise ValueError("sandbox event is not caused by its active tool attempt")
        return cast(str, attempt["tool_name"])

    @staticmethod
    def _project_background_job(connection: sqlite3.Connection, event: Event) -> None:
        job_id = SQLiteEventStore._event_string(event, "job_id")
        if job_id is None:
            raise ValueError("background job projection identity is invalid")
        if event.type == "background.job.created":
            cursor = connection.execute(
                """
                INSERT INTO background_jobs (
                    session_id, job_id, label, state, arguments_sha256,
                    max_seconds, max_output_bytes, created_event_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 'starting', ?, ?, ?, ?, ?, ?)
                ON CONFLICT (session_id, job_id) DO UPDATE SET
                    label = excluded.label,
                    state = 'starting',
                    arguments_sha256 = excluded.arguments_sha256,
                    max_seconds = excluded.max_seconds,
                    max_output_bytes = excluded.max_output_bytes,
                    result = NULL,
                    terminal_reason = NULL,
                    created_event_id = excluded.created_event_id,
                    started_event_id = NULL,
                    terminal_event_id = NULL,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                WHERE background_jobs.state IN ('succeeded', 'failed', 'stopped', 'interrupted')
                """,
                (
                    event.session_id,
                    job_id,
                    event.data["label"],
                    event.data["arguments_sha256"],
                    event.data["max_seconds"],
                    event.data["max_output_bytes"],
                    event.id,
                    event.created_at,
                    event.created_at,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("background job identity is already active")
            return
        if event.type == "background.job.started":
            cursor = connection.execute(
                """
                UPDATE background_jobs
                SET state = 'running', started_event_id = ?, updated_at = ?
                WHERE session_id = ? AND job_id = ? AND state = 'starting'
                  AND created_event_id = ?
                """,
                (
                    event.id,
                    event.created_at,
                    event.session_id,
                    job_id,
                    event.causation_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("background job cannot transition to running")
            return
        state = event.type.removeprefix("background.job.")
        if state not in {"succeeded", "failed", "stopped", "interrupted"}:
            raise ValueError("background job projection transition is unsupported")
        result = event.data.get("result")
        reason = event.data.get("reason")
        cursor = connection.execute(
            """
            UPDATE background_jobs
            SET state = ?, result = ?, terminal_reason = ?,
                terminal_event_id = ?, updated_at = ?
            WHERE session_id = ? AND job_id = ? AND state IN ('starting', 'running')
              AND CASE state
                    WHEN 'starting' THEN created_event_id
                    ELSE started_event_id
                  END = ?
            """,
            (
                state,
                result if isinstance(result, str) else None,
                reason if isinstance(reason, str) else None,
                event.id,
                event.created_at,
                event.session_id,
                job_id,
                event.causation_id,
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("background job cannot transition to a terminal state")

    @staticmethod
    def _project_todo_upsert(
        connection: sqlite3.Connection,
        event: Event,
        *,
        enforce_ownership: bool = True,
    ) -> None:
        SQLiteEventStore._validate_todo_attempt(connection, event)
        todo_id = SQLiteEventStore._event_string(event, "todo_id")
        content = SQLiteEventStore._event_string(event, "content")
        status = SQLiteEventStore._event_string(event, "status")
        position = event.data.get("position")
        if (
            todo_id is None
            or content is None
            or status not in {item.value for item in TodoStatus}
            or not isinstance(position, int)
            or isinstance(position, bool)
            or position < 0
        ):
            raise ValueError("todo.upserted contains invalid projection fields")
        existing = connection.execute(
            "SELECT session_id, created_at FROM todos WHERE id = ?",
            (todo_id,),
        ).fetchone()
        if enforce_ownership:
            owner = connection.execute(
                "SELECT session_id FROM todo_id_owners WHERE id = ?",
                (todo_id,),
            ).fetchone()
            if owner is not None and owner["session_id"] != event.session_id:
                raise ValueError("todo id belongs to a different session")
            if owner is None:
                connection.execute(
                    "INSERT INTO todo_id_owners (id, session_id) VALUES (?, ?)",
                    (todo_id, event.session_id),
                )
        if existing is not None and existing["session_id"] != event.session_id:
            raise ValueError("todo id belongs to a different session")
        created_at = event.created_at if existing is None else cast(str, existing["created_at"])
        ordered_ids = [
            cast(str, row["id"])
            for row in connection.execute(
                "SELECT id FROM todos WHERE session_id = ? ORDER BY position ASC, id ASC",
                (event.session_id,),
            ).fetchall()
            if row["id"] != todo_id
        ]
        target_position = min(position, len(ordered_ids))
        ordered_ids.insert(target_position, todo_id)
        connection.execute(
            """
            INSERT INTO todos (
                id, session_id, content, status, position, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                content = excluded.content,
                status = excluded.status,
                position = excluded.position,
                updated_at = excluded.updated_at
            WHERE todos.session_id = excluded.session_id
            """,
            (
                todo_id,
                event.session_id,
                content,
                status,
                position,
                created_at,
                event.created_at,
            ),
        )
        for normalized_position, ordered_id in enumerate(ordered_ids):
            connection.execute(
                "UPDATE todos SET position = ? WHERE id = ? AND session_id = ?",
                (normalized_position, ordered_id, event.session_id),
            )

    @staticmethod
    def _normalize_todo_positions(connection: sqlite3.Connection, session_id: str) -> None:
        rows = connection.execute(
            "SELECT id FROM todos WHERE session_id = ? ORDER BY position ASC, id ASC",
            (session_id,),
        ).fetchall()
        for position, row in enumerate(rows):
            connection.execute(
                "UPDATE todos SET position = ? WHERE id = ? AND session_id = ?",
                (position, row["id"], session_id),
            )

    @staticmethod
    def _validate_todo_attempt(connection: sqlite3.Connection, event: Event) -> None:
        attempt_id = SQLiteEventStore._event_string(event, "attempt_id")
        if attempt_id is None:
            return
        row = connection.execute(
            """
            SELECT started_event_id
            FROM tool_attempts
            WHERE id = ? AND session_id = ? AND state = 'started'
            """,
            (attempt_id, event.session_id),
        ).fetchone()
        if row is None or row["started_event_id"] != event.causation_id:
            raise ValueError("Todo event is not caused by its active tool attempt")

    @staticmethod
    def _project_research_source(
        connection: sqlite3.Connection,
        event: Event,
        *,
        validate_attempt: bool = True,
    ) -> None:
        if validate_attempt:
            SQLiteEventStore._validate_research_attempt(connection, event)
        source_id = SQLiteEventStore._event_string(event, "source_id")
        url = SQLiteEventStore._event_string(event, "url")
        title = event.data.get("title")
        content = event.data.get("content")
        artifact_sha256 = SQLiteEventStore._event_string(event, "artifact_sha256")
        response_sha256 = SQLiteEventStore._event_string(event, "response_sha256")
        response_bytes = event.data.get("response_bytes")
        media_type = SQLiteEventStore._event_string(event, "media_type")
        fetched_at = SQLiteEventStore._event_string(event, "fetched_at")
        truncated = event.data.get("truncated")
        summary = event.data.get("summary")
        if (
            source_id is None
            or url is None
            or (title is not None and not isinstance(title, str))
            or not isinstance(content, str)
            or artifact_sha256 is None
            or response_sha256 is None
            or not isinstance(response_bytes, int)
            or isinstance(response_bytes, bool)
            or media_type is None
            or fetched_at is None
            or not isinstance(truncated, bool)
            or not isinstance(summary, str)
        ):
            raise ValueError("research.source.saved is missing projection fields")
        receipt_rows = connection.execute(
            """
            SELECT json_extract(data_json, '$.result') AS result
            FROM events
            WHERE session_id = ?
              AND sequence < ?
              AND type = 'tool.settled'
              AND json_extract(data_json, '$.name') = 'web_fetch'
              AND json_extract(data_json, '$.output_truncated') = 0
              AND json_type(data_json, '$.result') = 'text'
            ORDER BY sequence DESC
            LIMIT 1000
            """,
            (event.session_id, event.sequence),
        ).fetchall()
        if not any(web_fetch_receipt_matches(row["result"], event.data) for row in receipt_rows):
            raise ValueError("research source has no matching prior web_fetch receipt")
        content_bytes = content.encode("utf-8")
        connection.execute(
            """
            INSERT INTO text_artifacts (sha256, content, byte_count)
            VALUES (?, ?, ?)
            ON CONFLICT (sha256) DO NOTHING
            """,
            (artifact_sha256, content_bytes, len(content_bytes)),
        )
        artifact = connection.execute(
            "SELECT content, byte_count FROM text_artifacts WHERE sha256 = ?",
            (artifact_sha256,),
        ).fetchone()
        if (
            artifact is None
            or artifact["content"] != content_bytes
            or artifact["byte_count"] != len(content_bytes)
        ):
            raise ValueError("research artifact digest collision detected")
        existing = connection.execute(
            "SELECT created_at FROM research_sources WHERE session_id = ? AND id = ?",
            (event.session_id, source_id),
        ).fetchone()
        created_at = event.created_at if existing is None else cast(str, existing["created_at"])
        connection.execute(
            """
            INSERT INTO research_sources (
                id, session_id, url, title, artifact_sha256, response_sha256,
                response_bytes, media_type, fetched_at, truncated, summary,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (session_id, id) DO UPDATE SET
                title = excluded.title,
                response_sha256 = excluded.response_sha256,
                response_bytes = excluded.response_bytes,
                media_type = excluded.media_type,
                fetched_at = excluded.fetched_at,
                truncated = excluded.truncated,
                summary = excluded.summary,
                updated_at = excluded.updated_at
            WHERE research_sources.url = excluded.url
              AND research_sources.artifact_sha256 = excluded.artifact_sha256
            """,
            (
                source_id,
                event.session_id,
                url,
                title,
                artifact_sha256,
                response_sha256,
                response_bytes,
                media_type,
                fetched_at,
                int(truncated),
                summary,
                created_at,
                event.created_at,
            ),
        )

    @staticmethod
    def _project_research_citation(
        connection: sqlite3.Connection,
        event: Event,
        *,
        validate_attempt: bool = True,
    ) -> None:
        if validate_attempt:
            SQLiteEventStore._validate_research_attempt(connection, event)
        citation_id = SQLiteEventStore._event_string(event, "citation_id")
        source_id = SQLiteEventStore._event_string(event, "source_id")
        claim = SQLiteEventStore._event_string(event, "claim")
        locator = event.data.get("locator")
        quote = event.data.get("quote")
        if (
            citation_id is None
            or source_id is None
            or claim is None
            or (locator is not None and not isinstance(locator, str))
            or (quote is not None and not isinstance(quote, str))
        ):
            raise ValueError("research.citation.added is missing projection fields")
        source = connection.execute(
            """
            SELECT a.content
            FROM research_sources AS s
            JOIN text_artifacts AS a ON a.sha256 = s.artifact_sha256
            WHERE s.session_id = ? AND s.id = ?
            """,
            (event.session_id, source_id),
        ).fetchone()
        if source is None:
            raise ValueError("citation references an unknown research source")
        if quote:
            try:
                artifact_content = cast(bytes, source["content"]).decode("utf-8")
            except UnicodeDecodeError:
                raise ValueError("citation source artifact is not valid UTF-8") from None
            if quote not in artifact_content:
                raise ValueError("citation quote does not occur in its research source")
        connection.execute(
            """
            INSERT INTO research_citations (
                id, session_id, source_id, claim, locator, quote, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                citation_id,
                event.session_id,
                source_id,
                claim,
                locator,
                quote,
                event.created_at,
            ),
        )

    @staticmethod
    def _validate_research_attempt(connection: sqlite3.Connection, event: Event) -> None:
        attempt_id = SQLiteEventStore._event_string(event, "attempt_id")
        if attempt_id is None:
            return
        row = connection.execute(
            """
            SELECT started_event_id
            FROM tool_attempts
            WHERE id = ? AND session_id = ? AND state = 'started'
            """,
            (attempt_id, event.session_id),
        ).fetchone()
        if row is None or row["started_event_id"] != event.causation_id:
            raise ValueError("research event is not caused by its active tool attempt")

    @staticmethod
    def _project_memory_upsert(
        connection: sqlite3.Connection,
        event: Event,
        *,
        validate_attempt: bool = True,
    ) -> None:
        if validate_attempt:
            SQLiteEventStore._validate_memory_attempt(connection, event)
        memory_id = SQLiteEventStore._event_string(event, "memory_id")
        workspace = SQLiteEventStore._event_string(event, "workspace")
        content = SQLiteEventStore._event_string(event, "content")
        tags = event.data.get("tags")
        expires_at = event.data.get("expires_at")
        if (
            memory_id is None
            or workspace is None
            or content is None
            or not isinstance(tags, list)
            or any(not isinstance(tag, str) for tag in tags)
            or (expires_at is not None and not isinstance(expires_at, str))
        ):
            raise ValueError("memory.upserted is missing projection fields")
        if expires_at is not None:
            try:
                expires_at = datetime.fromisoformat(expires_at).astimezone(UTC).isoformat()
            except ValueError:
                raise ValueError("memory.upserted contains invalid expiration") from None
        SQLiteEventStore._validate_memory_workspace(connection, event, workspace)
        owner = SQLiteEventStore._project_memory_owner(
            connection,
            event,
            memory_id=memory_id,
            workspace=workspace,
        )
        if owner["workspace"] != workspace:
            return
        if not SQLiteEventStore._memory_state_accepts(connection, event, memory_id):
            return
        tags_json = json.dumps(tags, ensure_ascii=False, separators=(",", ":"))
        if SQLiteEventStore._memory_has_expiry_column(connection):
            connection.execute(
                """
                INSERT INTO memories (
                    id, workspace, content, tags_json, deleted,
                    updated_by_session_id, updated_at, updated_event_id, expires_at
                ) VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    workspace = excluded.workspace,
                    content = excluded.content,
                    tags_json = excluded.tags_json,
                    deleted = 0,
                    updated_by_session_id = excluded.updated_by_session_id,
                    updated_at = excluded.updated_at,
                    updated_event_id = excluded.updated_event_id,
                    expires_at = excluded.expires_at
                """,
                (
                    memory_id,
                    workspace,
                    content,
                    tags_json,
                    event.session_id,
                    event.created_at,
                    event.id,
                    expires_at,
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO memories (
                    id, workspace, content, tags_json, deleted,
                    updated_by_session_id, updated_at, updated_event_id
                ) VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    workspace = excluded.workspace,
                    content = excluded.content,
                    tags_json = excluded.tags_json,
                    deleted = 0,
                    updated_by_session_id = excluded.updated_by_session_id,
                    updated_at = excluded.updated_at,
                    updated_event_id = excluded.updated_event_id
                """,
                (
                    memory_id,
                    workspace,
                    content,
                    tags_json,
                    event.session_id,
                    event.created_at,
                    event.id,
                ),
            )

    @staticmethod
    def _project_memory_delete(
        connection: sqlite3.Connection,
        event: Event,
        *,
        validate_attempt: bool = True,
    ) -> None:
        if validate_attempt:
            SQLiteEventStore._validate_memory_attempt(connection, event)
        memory_id = SQLiteEventStore._event_string(event, "memory_id")
        workspace = SQLiteEventStore._event_string(event, "workspace")
        if memory_id is None or workspace is None:
            raise ValueError("memory.deleted is missing projection fields")
        SQLiteEventStore._validate_memory_workspace(connection, event, workspace)
        owner = SQLiteEventStore._project_memory_owner(
            connection,
            event,
            memory_id=memory_id,
            workspace=workspace,
        )
        if owner["workspace"] != workspace:
            return
        if not SQLiteEventStore._memory_state_accepts(connection, event, memory_id):
            return
        if SQLiteEventStore._memory_has_expiry_column(connection):
            connection.execute(
                """
                INSERT INTO memories (
                    id, workspace, content, tags_json, deleted,
                    updated_by_session_id, updated_at, updated_event_id, expires_at
                ) VALUES (?, ?, '', '[]', 1, ?, ?, ?, NULL)
                ON CONFLICT (id) DO UPDATE SET
                    workspace = excluded.workspace,
                    content = '',
                    tags_json = '[]',
                    deleted = 1,
                    updated_by_session_id = excluded.updated_by_session_id,
                    updated_at = excluded.updated_at,
                    updated_event_id = excluded.updated_event_id,
                    expires_at = NULL
                """,
                (memory_id, workspace, event.session_id, event.created_at, event.id),
            )
        else:
            connection.execute(
                """
                INSERT INTO memories (
                    id, workspace, content, tags_json, deleted,
                    updated_by_session_id, updated_at, updated_event_id
                ) VALUES (?, ?, '', '[]', 1, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    workspace = excluded.workspace,
                    content = '',
                    tags_json = '[]',
                    deleted = 1,
                    updated_by_session_id = excluded.updated_by_session_id,
                    updated_at = excluded.updated_at,
                    updated_event_id = excluded.updated_event_id
                """,
                (memory_id, workspace, event.session_id, event.created_at, event.id),
            )

    @staticmethod
    def _memory_state_accepts(
        connection: sqlite3.Connection,
        event: Event,
        memory_id: str,
    ) -> bool:
        existing = connection.execute(
            "SELECT updated_at, updated_event_id FROM memories WHERE id = ?",
            (memory_id,),
        ).fetchone()
        if existing is None:
            return True
        current_version = (
            datetime.fromisoformat(cast(str, existing["updated_at"])),
            cast(str, existing["updated_event_id"]),
        )
        return (datetime.fromisoformat(event.created_at), event.id) > current_version

    @staticmethod
    def _memory_has_expiry_column(connection: sqlite3.Connection) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM pragma_table_info('memories') WHERE name = 'expires_at'"
            ).fetchone()
            is not None
        )

    @staticmethod
    def _project_memory_owner(
        connection: sqlite3.Connection,
        event: Event,
        *,
        memory_id: str,
        workspace: str,
    ) -> sqlite3.Row:
        owner = connection.execute(
            """
            SELECT workspace, source_session_id, created_at, created_event_id
            FROM memory_id_owners
            WHERE id = ?
            """,
            (memory_id,),
        ).fetchone()
        candidate_version = (datetime.fromisoformat(event.created_at), event.id)
        if owner is None:
            connection.execute(
                """
                INSERT INTO memory_id_owners (
                    id, workspace, source_session_id, created_at, created_event_id
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (memory_id, workspace, event.session_id, event.created_at, event.id),
            )
        else:
            if owner["workspace"] != workspace:
                raise ValueError("memory id belongs to a different workspace")
            owner_version = (
                datetime.fromisoformat(cast(str, owner["created_at"])),
                cast(str, owner["created_event_id"]),
            )
            if candidate_version < owner_version:
                connection.execute(
                    """
                    UPDATE memory_id_owners
                    SET workspace = ?, source_session_id = ?, created_at = ?,
                        created_event_id = ?
                    WHERE id = ?
                    """,
                    (workspace, event.session_id, event.created_at, event.id, memory_id),
                )
        current_owner = connection.execute(
            """
            SELECT workspace, source_session_id, created_at, created_event_id
            FROM memory_id_owners
            WHERE id = ?
            """,
            (memory_id,),
        ).fetchone()
        if current_owner is None:
            raise RuntimeError("memory owner projection was not created")
        return cast(sqlite3.Row, current_owner)

    @staticmethod
    def _validate_memory_workspace(
        connection: sqlite3.Connection,
        event: Event,
        workspace: str,
    ) -> None:
        row = connection.execute(
            "SELECT workspace FROM sessions WHERE id = ?",
            (event.session_id,),
        ).fetchone()
        if row is None or row["workspace"] != workspace:
            raise ValueError("memory event workspace does not match its session")

    @staticmethod
    def _validate_memory_attempt(connection: sqlite3.Connection, event: Event) -> None:
        attempt_id = SQLiteEventStore._event_string(event, "attempt_id")
        if attempt_id is None:
            return
        row = connection.execute(
            """
            SELECT started_event_id
            FROM tool_attempts
            WHERE id = ? AND session_id = ? AND state = 'started'
            """,
            (attempt_id, event.session_id),
        ).fetchone()
        if row is None or row["started_event_id"] != event.causation_id:
            raise ValueError("memory event is not caused by its active tool attempt")

    @staticmethod
    def _backfill_legacy_tool_attempts(connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT id, session_id, type, data_json, created_at
            FROM events
            WHERE type LIKE 'tool.%'
            ORDER BY session_id ASC, sequence ASC
            """
        ).fetchall()
        active: dict[tuple[str, str], list[dict[str, str | None]]] = {}
        terminal_states = {
            "tool.settled": ToolAttemptState.SETTLED.value,
            "tool.failed": ToolAttemptState.FAILED.value,
            "tool.rejected": ToolAttemptState.REJECTED.value,
            "tool.cancelled": ToolAttemptState.CANCELLED.value,
            "tool.unknown": ToolAttemptState.UNKNOWN.value,
        }

        for row in rows:
            data = json.loads(cast(str, row["data_json"]))
            if not isinstance(data, dict) or isinstance(data.get("attempt_id"), str):
                continue
            call_id = data.get("tool_call_id")
            if not isinstance(call_id, str) or not call_id:
                continue
            session_id = cast(str, row["session_id"])
            key = (session_id, call_id)
            event_type = cast(str, row["type"])
            event_id = cast(str, row["id"])
            created_at = cast(str, row["created_at"])

            if event_type == "tool.proposed":
                tool_name = data.get("name")
                if not isinstance(tool_name, str) or not tool_name:
                    continue
                attempt_id = f"legacy-{event_id}"
                connection.execute(
                    """
                    INSERT INTO tool_attempts (
                        id, session_id, tool_call_id, tool_name, idempotency_key, state,
                        proposed_event_id, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'proposed', ?, ?)
                    """,
                    (
                        attempt_id,
                        session_id,
                        call_id,
                        tool_name,
                        f"legacy-{event_id}",
                        event_id,
                        created_at,
                    ),
                )
                active.setdefault(key, []).append(
                    {
                        "id": attempt_id,
                        "state": ToolAttemptState.PROPOSED.value,
                        "started_event_id": None,
                    }
                )
                continue

            attempts = active.get(key)
            if not attempts:
                continue
            attempt = attempts[-1]
            if event_type == "tool.approved" and attempt["state"] == "proposed":
                attempt["state"] = ToolAttemptState.APPROVED.value
                connection.execute(
                    "UPDATE tool_attempts SET state = 'approved', updated_at = ? WHERE id = ?",
                    (created_at, attempt["id"]),
                )
                continue
            if event_type == "tool.started" and attempt["state"] == "approved":
                attempt["state"] = ToolAttemptState.STARTED.value
                attempt["started_event_id"] = event_id
                connection.execute(
                    """
                    UPDATE tool_attempts
                    SET state = 'started', started_event_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (event_id, created_at, attempt["id"]),
                )
                continue
            terminal_state = terminal_states.get(event_type)
            if terminal_state is None:
                continue
            connection.execute(
                """
                UPDATE tool_attempts
                SET state = ?, terminal_event_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (terminal_state, event_id, created_at, attempt["id"]),
            )
            attempts.pop()
            if not attempts:
                active.pop(key, None)

    @staticmethod
    def _backfill_todo_id_owners(connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT session_id, data_json
            FROM events
            WHERE type = 'todo.upserted'
            ORDER BY sequence ASC
            """
        ).fetchall()
        owners: dict[str, str] = {}
        for row in rows:
            data = json.loads(cast(str, row["data_json"]))
            if not isinstance(data, dict):
                continue
            todo_id = data.get("todo_id")
            session_id = cast(str, row["session_id"])
            if not isinstance(todo_id, str) or not todo_id:
                continue
            existing_owner = owners.get(todo_id)
            if existing_owner is not None and existing_owner != session_id:
                raise RuntimeError("Todo id ownership conflict found during migration")
            owners[todo_id] = session_id
        connection.executemany(
            "INSERT INTO todo_id_owners (id, session_id) VALUES (?, ?)",
            owners.items(),
        )

    @staticmethod
    def _repair_search_index(connection: sqlite3.Connection) -> None:
        table = connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'session_search_docsize'"
        ).fetchone()
        if table is None:
            return
        if not SQLiteEventStore._search_index_is_consistent(connection):
            connection.execute("INSERT INTO session_search(session_search) VALUES ('rebuild')")
        try:
            connection.execute(
                "INSERT INTO session_search(session_search, rank) VALUES ('integrity-check', 1)"
            )
        except sqlite3.DatabaseError:
            connection.execute("INSERT INTO session_search(session_search) VALUES ('rebuild')")
            connection.execute(
                "INSERT INTO session_search(session_search, rank) VALUES ('integrity-check', 1)"
            )

    @staticmethod
    def _search_index_is_consistent(connection: sqlite3.Connection) -> bool:
        mismatch = connection.execute(
            """
            WITH missing AS (
                SELECT rowid FROM search_documents
                EXCEPT
                SELECT id FROM session_search_docsize
            ),
            unexpected AS (
                SELECT id FROM session_search_docsize
                EXCEPT
                SELECT rowid FROM search_documents
            )
            SELECT 1 FROM missing
            UNION ALL
            SELECT 1 FROM unexpected
            UNION ALL
            SELECT 1
            FROM search_documents AS d
            LEFT JOIN session_search_vocab AS v
              ON v.doc = d.rowid
             AND v.col = 'integrity_token'
             AND v.term = d.integrity_token
            WHERE v.doc IS NULL
            UNION ALL
            SELECT 1
            FROM session_search_vocab AS v
            LEFT JOIN search_documents AS d
              ON d.rowid = v.doc
             AND d.integrity_token = v.term
            WHERE v.col = 'integrity_token' AND d.rowid IS NULL
            LIMIT 1
            """
        ).fetchone()
        return mismatch is None

    @staticmethod
    def _backfill_search_documents(connection: sqlite3.Connection) -> None:
        title_rows = connection.execute(
            """
            SELECT id, title
            FROM sessions
            WHERE length(title) > 0
            """
        ).fetchall()
        connection.executemany(
            """
            INSERT INTO search_documents (
                id, session_id, kind, sequence, text, integrity_token
            ) VALUES (?, ?, 'title', 0, ?, ?)
            """,
            (
                (
                    f"session:{row['id']}:title",
                    row["id"],
                    row["title"],
                    SQLiteEventStore._search_integrity_token(
                        f"session:{row['id']}:title", cast(str, row["title"])
                    ),
                )
                for row in title_rows
            ),
        )
        message_rows = connection.execute(
            """
            SELECT e.id, e.session_id, e.sequence, json_extract(e.data_json, '$.content') AS content
            FROM events AS e
            WHERE e.type = 'message.created'
              AND json_extract(e.data_json, '$.role') = 'user'
              AND json_type(e.data_json, '$.content') = 'text'
              AND length(json_extract(e.data_json, '$.content')) > 0
            """
        ).fetchall()
        connection.executemany(
            """
            INSERT INTO search_documents (
                id, session_id, kind, sequence, text, integrity_token
            ) VALUES (?, ?, 'user_message', ?, ?, ?)
            """,
            (
                (
                    f"event:{row['id']}",
                    row["session_id"],
                    row["sequence"],
                    row["content"],
                    SQLiteEventStore._search_integrity_token(
                        f"event:{row['id']}", cast(str, row["content"])
                    ),
                )
                for row in message_rows
            ),
        )

    @staticmethod
    def _backfill_research_evidence(connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT id, session_id, type, data_json, schema_version, sequence,
                   causation_id, correlation_id, created_at
            FROM events
            WHERE type IN ('research.source.saved', 'research.citation.added')
            ORDER BY session_id ASC, sequence ASC
            """
        ).fetchall()
        for row in rows:
            data = json.loads(cast(str, row["data_json"]))
            if not isinstance(data, dict):
                raise ValueError(f"event {row['id']} data is not a JSON object")
            event = Event(
                id=cast(str, row["id"]),
                session_id=cast(str, row["session_id"]),
                type=cast(str, row["type"]),
                data=cast(dict[str, Any], data),
                schema_version=cast(int, row["schema_version"]),
                sequence=cast(int, row["sequence"]),
                causation_id=cast(str | None, row["causation_id"]),
                correlation_id=cast(str | None, row["correlation_id"]),
                created_at=cast(str, row["created_at"]),
            )
            validate_event_payload(event.type, event.data)
            if event.type == "research.source.saved":
                SQLiteEventStore._project_research_source(
                    connection,
                    event,
                    validate_attempt=False,
                )
            else:
                SQLiteEventStore._project_research_citation(
                    connection,
                    event,
                    validate_attempt=False,
                )

    @staticmethod
    def _backfill_memories(connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT id, session_id, type, data_json, schema_version, sequence,
                   causation_id, correlation_id, created_at
            FROM events
            WHERE type IN ('memory.upserted', 'memory.deleted')
            ORDER BY session_id ASC, sequence ASC
            """
        ).fetchall()
        for row in rows:
            data = json.loads(cast(str, row["data_json"]))
            if not isinstance(data, dict):
                raise ValueError(f"event {row['id']} data is not a JSON object")
            event = Event(
                id=cast(str, row["id"]),
                session_id=cast(str, row["session_id"]),
                type=cast(str, row["type"]),
                data=cast(dict[str, Any], data),
                schema_version=cast(int, row["schema_version"]),
                sequence=cast(int, row["sequence"]),
                causation_id=cast(str | None, row["causation_id"]),
                correlation_id=cast(str | None, row["correlation_id"]),
                created_at=cast(str, row["created_at"]),
            )
            validate_event_payload(event.type, event.data)
            if event.type == "memory.upserted":
                SQLiteEventStore._project_memory_upsert(
                    connection,
                    event,
                    validate_attempt=False,
                )
            else:
                SQLiteEventStore._project_memory_delete(
                    connection,
                    event,
                    validate_attempt=False,
                )

    @staticmethod
    def _backfill_sandbox_artifacts(connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT id, session_id, type, data_json, schema_version, sequence,
                   causation_id, correlation_id, created_at
            FROM events
            WHERE type = 'sandbox.changeset.created'
            ORDER BY session_id ASC, sequence ASC
            """
        ).fetchall()
        for row in rows:
            data = json.loads(cast(str, row["data_json"]))
            if not isinstance(data, dict):
                raise ValueError(f"event {row['id']} data is not a JSON object")
            event = Event(
                id=cast(str, row["id"]),
                session_id=cast(str, row["session_id"]),
                type=cast(str, row["type"]),
                data=cast(dict[str, Any], data),
                schema_version=cast(int, row["schema_version"]),
                sequence=cast(int, row["sequence"]),
                causation_id=cast(str | None, row["causation_id"]),
                correlation_id=cast(str | None, row["correlation_id"]),
                created_at=cast(str, row["created_at"]),
            )
            validate_event_payload(event.type, event.data)
            SQLiteEventStore._project_sandbox_change_artifacts(
                connection,
                event,
                enforce_storage_limit=False,
            )

    @staticmethod
    def _backfill_durable_operation_states(connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT id, session_id, type, data_json, schema_version, sequence,
                   causation_id, correlation_id, created_at
            FROM events
            WHERE type IN (
                'sandbox.changeset.created',
                'sandbox.change.reviewed',
                'sandbox.change.applied',
                'background.job.created',
                'background.job.started',
                'background.job.succeeded',
                'background.job.failed',
                'background.job.stopped',
                'background.job.interrupted'
            )
            ORDER BY session_id ASC, sequence ASC
            """
        ).fetchall()
        for row in rows:
            data = json.loads(cast(str, row["data_json"]))
            if not isinstance(data, dict):
                raise ValueError(f"event {row['id']} data is not a JSON object")
            event = Event(
                id=cast(str, row["id"]),
                session_id=cast(str, row["session_id"]),
                type=cast(str, row["type"]),
                data=cast(dict[str, Any], data),
                schema_version=cast(int, row["schema_version"]),
                sequence=cast(int, row["sequence"]),
                causation_id=cast(str | None, row["causation_id"]),
                correlation_id=cast(str | None, row["correlation_id"]),
                created_at=cast(str, row["created_at"]),
            )
            if event.type.startswith("background.job."):
                SQLiteEventStore._project_background_job(connection, event)
                continue
            changeset_id = SQLiteEventStore._event_string(event, "changeset_id")
            if changeset_id is None:
                raise ValueError("sandbox state backfill identity is invalid")
            if event.type == "sandbox.changeset.created":
                changes = event.data.get("changes")
                if not isinstance(changes, list):
                    raise ValueError("sandbox state backfill changes are invalid")
                for change in changes:
                    path = change.get("path") if isinstance(change, dict) else None
                    if not isinstance(path, str):
                        raise ValueError("sandbox state backfill path is invalid")
                    connection.execute(
                        """
                        INSERT INTO sandbox_change_states (
                            session_id, changeset_id, path, updated_at
                        ) VALUES (?, ?, ?, ?)
                        ON CONFLICT (session_id, changeset_id, path) DO NOTHING
                        """,
                        (event.session_id, changeset_id, path, event.created_at),
                    )
                continue
            path = SQLiteEventStore._event_string(event, "path")
            if path is None:
                raise ValueError("sandbox state backfill path is invalid")
            if event.type == "sandbox.change.reviewed":
                cursor = connection.execute(
                    """
                    UPDATE sandbox_change_states
                    SET review_decision = ?, review_event_id = ?, updated_at = ?
                    WHERE session_id = ? AND changeset_id = ? AND path = ? AND applied = 0
                    """,
                    (
                        event.data.get("decision"),
                        event.id,
                        event.created_at,
                        event.session_id,
                        changeset_id,
                        path,
                    ),
                )
            else:
                cursor = connection.execute(
                    """
                    UPDATE sandbox_change_states
                    SET applied = 1, applied_event_id = ?, updated_at = ?
                    WHERE session_id = ? AND changeset_id = ? AND path = ?
                      AND applied = 0
                      AND (review_decision IS NULL OR review_decision = 'approved')
                    """,
                    (event.id, event.created_at, event.session_id, changeset_id, path),
                )
            if cursor.rowcount != 1:
                raise ValueError("sandbox durable state history is inconsistent")

    @staticmethod
    def projection_replay_error(
        connection: sqlite3.Connection,
        schema_version: int,
    ) -> str | None:
        expected = sqlite3.connect("")
        expected.row_factory = sqlite3.Row
        try:
            expected.execute("PRAGMA foreign_keys = ON")
            expected.execute("PRAGMA temp_store = FILE")
            expected.execute(_SCHEMA_MIGRATIONS_DEFINITION)
            for version, _, statements in _MIGRATIONS:
                if version > schema_version:
                    break
                for statement in statements:
                    expected.execute(statement)

            for row in connection.execute(
                """
                SELECT id, workspace, mode, autonomy, title, created_at, updated_at,
                       next_sequence
                FROM sessions
                ORDER BY id
                """
            ):
                first_mode_change = connection.execute(
                    """
                    SELECT json_extract(data_json, '$.from_mode')
                    FROM events
                    WHERE session_id = ? AND type = 'mode.changed'
                    ORDER BY sequence
                    LIMIT 1
                    """,
                    (row["id"],),
                ).fetchone()
                initial_mode = (
                    first_mode_change[0]
                    if first_mode_change is not None and isinstance(first_mode_change[0], str)
                    else row["mode"]
                )
                first_autonomy_change = connection.execute(
                    """
                    SELECT json_extract(data_json, '$.from_autonomy')
                    FROM events
                    WHERE session_id = ? AND type = 'autonomy.changed'
                    ORDER BY sequence
                    LIMIT 1
                    """,
                    (row["id"],),
                ).fetchone()
                initial_autonomy = (
                    first_autonomy_change[0]
                    if first_autonomy_change is not None
                    and isinstance(first_autonomy_change[0], str)
                    else row["autonomy"]
                )
                expected.execute(
                    """
                    INSERT INTO sessions (
                        id, workspace, mode, autonomy, title, created_at, updated_at,
                        next_sequence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        row["workspace"],
                        initial_mode,
                        initial_autonomy,
                        row["title"],
                        row["created_at"],
                        row["updated_at"],
                        row["next_sequence"],
                    ),
                )
                if schema_version >= 5:
                    SQLiteEventStore._project_session(
                        expected,
                        SQLiteEventStore._session_from_row(row),
                    )

            if schema_version >= 11:
                expected.executemany(
                    "INSERT INTO binary_artifacts (sha256, content, byte_count) VALUES (?, ?, ?)",
                    (
                        tuple(row)
                        for row in connection.execute(
                            """
                            SELECT sha256, content, byte_count
                            FROM binary_artifacts
                            ORDER BY sha256
                            """
                        )
                    ),
                )

            for row in connection.execute(
                """
                SELECT id, session_id, type, data_json, schema_version, sequence,
                       causation_id, correlation_id, created_at
                FROM events
                ORDER BY session_id, sequence
                """
            ):
                expected.execute(
                    """
                    INSERT INTO events (
                        id, session_id, type, data_json, schema_version, sequence,
                        causation_id, correlation_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(row),
                )
                data = json.loads(cast(str, row["data_json"]))
                if not isinstance(data, dict):
                    raise ValueError(f"event {row['id']} data is not a JSON object")
                SQLiteEventStore._project_event(
                    expected,
                    Event(
                        id=cast(str, row["id"]),
                        session_id=cast(str, row["session_id"]),
                        type=cast(str, row["type"]),
                        data=cast(dict[str, Any], data),
                        schema_version=cast(int, row["schema_version"]),
                        sequence=cast(int, row["sequence"]),
                        causation_id=cast(str | None, row["causation_id"]),
                        correlation_id=cast(str | None, row["correlation_id"]),
                        created_at=cast(str, row["created_at"]),
                    ),
                    projection_version=schema_version,
                )
            if schema_version >= 2:
                SQLiteEventStore._backfill_legacy_tool_attempts(expected)

            comparisons = (
                (
                    1,
                    "session mode projection is inconsistent",
                    "SELECT id, mode FROM sessions ORDER BY id",
                ),
                (
                    2,
                    "tool attempt projection is inconsistent",
                    """
                    SELECT id, session_id, tool_call_id, tool_name, idempotency_key, state,
                           proposed_event_id, started_event_id, terminal_event_id, updated_at
                    FROM tool_attempts
                    ORDER BY id
                    """,
                ),
                (
                    3,
                    "Todo projection is inconsistent",
                    """
                    SELECT id, session_id, content, status, position, created_at, updated_at
                    FROM todos
                    ORDER BY id
                    """,
                ),
                (
                    4,
                    "Todo ownership projection is inconsistent",
                    """
                    SELECT id, session_id
                    FROM todo_id_owners
                    ORDER BY id
                    """,
                ),
                (
                    5,
                    "session search projection is inconsistent",
                    """
                    SELECT id, session_id, kind, sequence, text, integrity_token
                    FROM search_documents
                    ORDER BY id
                    """,
                ),
                (
                    7,
                    "text artifact projection is inconsistent",
                    """
                    SELECT sha256, content, byte_count
                    FROM text_artifacts
                    ORDER BY sha256
                    """,
                ),
                (
                    7,
                    "research source projection is inconsistent",
                    """
                    SELECT id, session_id, url, title, artifact_sha256, response_sha256,
                           response_bytes, media_type, fetched_at, truncated, summary,
                           created_at, updated_at
                    FROM research_sources
                    ORDER BY session_id, id
                    """,
                ),
                (
                    7,
                    "research citation projection is inconsistent",
                    """
                    SELECT id, session_id, source_id, claim, locator, quote, created_at
                    FROM research_citations
                    ORDER BY id
                    """,
                ),
                (
                    8,
                    "memory ownership projection is inconsistent",
                    """
                    SELECT id, workspace, source_session_id, created_at, created_event_id
                    FROM memory_id_owners
                    ORDER BY id
                    """,
                ),
                (
                    8,
                    "memory projection is inconsistent",
                    """
                    SELECT id, workspace, content, tags_json, deleted,
                           updated_by_session_id, updated_at, updated_event_id
                    FROM memories
                    ORDER BY id
                    """,
                ),
                (
                    11,
                    "sandbox artifact reference projection is inconsistent",
                    """
                    SELECT session_id, changeset_id, path, artifact_sha256, created_event_id
                    FROM sandbox_change_artifacts
                    ORDER BY session_id, changeset_id, path
                    """,
                ),
                (
                    13,
                    "sandbox change state projection is inconsistent",
                    """
                    SELECT session_id, changeset_id, path, review_decision,
                           review_event_id, applied, applied_event_id, updated_at
                    FROM sandbox_change_states
                    ORDER BY session_id, changeset_id, path
                    """,
                ),
                (
                    13,
                    "background job projection is inconsistent",
                    """
                    SELECT session_id, job_id, label, state, arguments_sha256,
                           max_seconds, max_output_bytes, result, terminal_reason,
                           created_event_id, started_event_id, terminal_event_id,
                           created_at, updated_at
                    FROM background_jobs
                    ORDER BY session_id, job_id
                    """,
                ),
            )
            for minimum_version, message, query in comparisons:
                if schema_version >= minimum_version and not SQLiteEventStore._query_rows_match(
                    connection,
                    expected,
                    query,
                ):
                    return message
            return None
        finally:
            expected.close()

    @staticmethod
    def _query_rows_match(
        actual: sqlite3.Connection,
        expected: sqlite3.Connection,
        query: str,
    ) -> bool:
        actual_rows = actual.execute(query)
        expected_rows = expected.execute(query)
        try:
            return all(
                current is not None and rebuilt is not None and tuple(current) == tuple(rebuilt)
                for current, rebuilt in zip_longest(actual_rows, expected_rows)
            )
        finally:
            actual_rows.close()
            expected_rows.close()

    def __enter__(self) -> Self:
        self._get_connection()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _get_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise sqlite3.ProgrammingError("SQLiteEventStore is closed")
        return self._connection
