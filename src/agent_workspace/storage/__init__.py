"""Local persistence adapters."""

from agent_workspace.core.search import SearchIndexUnavailableError
from agent_workspace.storage.analytics import (
    export_events_ndjson,
    tool_call_summary,
    tool_latency_summary,
)
from agent_workspace.storage.lock import AlreadyRunningError, ProcessWriteLock
from agent_workspace.storage.recovery import (
    BackupValidationError,
    DatabaseValidation,
    SessionArchiveValidation,
    SessionExportError,
    create_verified_backup,
    export_session,
    import_session_archive,
    read_backup_manifest,
    restore_dry_run,
    restore_verified_backup,
    session_checkpoint_report,
    validate_database,
    verify_backup,
    verify_session_archive,
)
from agent_workspace.storage.sqlite import (
    CURRENT_SCHEMA_VERSION,
    FileCheckpointConflictError,
    SQLiteEventStore,
)
from agent_workspace.storage.workspace_snapshot import (
    WorkspaceSnapshotError,
    WorkspaceSnapshotReport,
    snapshot_workspace_tree,
)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "AlreadyRunningError",
    "BackupValidationError",
    "DatabaseValidation",
    "FileCheckpointConflictError",
    "ProcessWriteLock",
    "SQLiteEventStore",
    "SearchIndexUnavailableError",
    "SessionArchiveValidation",
    "SessionExportError",
    "WorkspaceSnapshotError",
    "WorkspaceSnapshotReport",
    "create_verified_backup",
    "export_events_ndjson",
    "export_session",
    "import_session_archive",
    "read_backup_manifest",
    "restore_dry_run",
    "restore_verified_backup",
    "session_checkpoint_report",
    "snapshot_workspace_tree",
    "tool_call_summary",
    "tool_latency_summary",
    "validate_database",
    "verify_backup",
    "verify_session_archive",
]
