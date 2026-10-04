from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from agent_workspace.application.ports import EventStore, ToolExecutionContext
from agent_workspace.core.events import Event
from agent_workspace.core.models import Capability, FileCheckpoint, ToolSpec
from agent_workspace.core.sandbox_changes import get_sandbox_change, sandbox_change_dependencies

from .base import (
    ConcurrentModificationError,
    ToolArgumentError,
    ToolError,
    json_result,
    require_string,
)
from .filesystem import (
    _MAX_EDIT_BYTES,
    _check_expected_executable,
    _checkpoint_node_state,
    _checkpoint_node_state_with_identity,
    _node_state_matches,
    _read_preimage,
    _remove_checkpoint_node,
    atomic_write,
    sha256_bytes,
)
from .paths import StrPath, WorkspacePaths
from .process_worker import run_in_process


@dataclass(frozen=True, slots=True)
class _PreparedSandboxChange:
    changeset_id: str
    path: str
    before_type: str | None
    after_type: str | None
    before_sha256: str | None
    after_sha256: str | None
    before_executable: bool | None
    after_executable: bool | None
    postimage: bytes | None
    format_version: int
    dependencies: tuple[_DependencyState, ...] = ()


@dataclass(frozen=True, slots=True)
class _DependencyState:
    path: str
    kind: str
    sha256: str | None
    executable: bool | None


def _apply_sandbox_change_sync(
    paths: WorkspacePaths,
    change: _PreparedSandboxChange,
) -> str:
    target = paths.resolve(change.path)
    before_kind = change.before_type or "missing"
    after_kind = change.after_type or "missing"
    actual_kind, actual_sha256, actual_executable, directory_identity = (
        _checkpoint_node_state_with_identity(target)
    )
    if not _node_state_matches(
        actual_kind,
        actual_sha256,
        actual_executable,
        before_kind,
        change.before_sha256,
        change.before_executable,
    ):
        raise ConcurrentModificationError("sandbox change source state changed before apply")
    for dependency in change.dependencies:
        dependency_target = paths.resolve(dependency.path)
        dependency_kind, dependency_sha256, dependency_executable = _checkpoint_node_state(
            dependency_target
        )
        if not _node_state_matches(
            dependency_kind,
            dependency_sha256,
            dependency_executable,
            dependency.kind,
            dependency.sha256,
            dependency.executable,
        ):
            raise ConcurrentModificationError(
                f"sandbox change dependency drifted before mutation: {dependency.path}"
            )
    if after_kind == "file":
        if change.postimage is None or change.after_sha256 is None:
            raise ToolError("sandbox file postimage is unavailable")
        if actual_kind == "directory":
            _remove_checkpoint_node(
                paths,
                target,
                actual_kind,
                actual_sha256,
                actual_executable,
                directory_identity=directory_identity,
            )
            actual_sha256 = None
            actual_executable = None
        _, digest = atomic_write(
            paths,
            change.path,
            change.postimage,
            actual_sha256,
            expected_executable=actual_executable,
            target_executable=change.after_executable,
        )
    elif after_kind == "directory":
        if actual_kind != "missing":
            _remove_checkpoint_node(
                paths,
                target,
                actual_kind,
                actual_sha256,
                actual_executable,
                directory_identity=directory_identity,
            )
        target.mkdir()
        from agent_workspace.storage.durable import fsync_directory

        fsync_directory(paths.resolve(target.parent))
        digest = None
    else:
        _remove_checkpoint_node(
            paths,
            target,
            actual_kind,
            actual_sha256,
            actual_executable,
            directory_identity=directory_identity,
        )
        digest = None
    final_kind, final_sha256, final_executable = _checkpoint_node_state(target)
    if not _node_state_matches(
        final_kind,
        final_sha256,
        final_executable,
        after_kind,
        change.after_sha256,
        change.after_executable,
    ):
        raise ToolError("sandbox change postimage verification failed")
    return json_result(
        {
            "changeset_id": change.changeset_id,
            "path": change.path,
            "sha256": digest,
            "node_type": change.after_type,
            "applied": True,
        }
    )


class ApplySandboxChangeTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="apply_sandbox_change",
        description=(
            "Apply one supported file or directory transition from a durable sandbox changeset. "
            "The live source state and ordered dependencies are checked before a durable rollback "
            "checkpoint is prepared."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "changeset_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                "path": {"type": "string", "minLength": 1, "maxLength": 512},
                "expected_after_sha256": {
                    "type": ["string", "null"],
                    "pattern": "^[0-9a-f]{64}$",
                },
            },
            "required": ["changeset_id", "path", "expected_after_sha256"],
            "additionalProperties": False,
        },
        side_effect="delete",
        capability=Capability.WORKSPACE_WRITE,
        durable_preimage_checkpoint=True,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath, store: EventStore) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self.store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def prepare_for_approval(self, arguments: dict[str, Any]) -> dict[str, Any]:
        relative = require_string(arguments, "path")
        resolved = self.paths.resolve(relative)
        if self.paths.relative(resolved) != relative:
            raise ToolArgumentError("sandbox change path is not canonical")
        return dict(arguments)

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolError("apply_sandbox_change requires a durable tool execution context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        change = self._load_change(arguments, session_id=context.session_id)
        if (
            self.store.get_sandbox_change_applied_event(
                context.session_id,
                str(self.paths.root),
                change.changeset_id,
                change.path,
            )
            is not None
        ):
            raise ToolError("sandbox change was already applied")
        review = self.store.get_sandbox_change_review_event(
            context.session_id,
            str(self.paths.root),
            change.changeset_id,
            change.path,
        )
        if review is not None and review.data.get("decision") == "rejected":
            raise ToolError("sandbox change was explicitly rejected")
        if change.postimage is not None and len(change.postimage) > _MAX_EDIT_BYTES:
            raise ToolError("sandbox change postimage exceeds the edit limit")
        if change.postimage is not None and sha256_bytes(change.postimage) != change.after_sha256:
            raise ToolError("sandbox change postimage digest does not match its content")
        target = self.paths.resolve(change.path)
        before_kind = change.before_type or "missing"
        after_kind = change.after_type or "missing"
        if os.name == "nt" and change.after_executable is True:
            raise ToolError("executable sandbox changes are unavailable on Windows")
        if before_kind == "file":
            preimage = _read_preimage(target, change.before_sha256, _MAX_EDIT_BYTES)
            if change.before_executable is not None:
                _check_expected_executable(target, change.before_executable)
        else:
            actual_kind, actual_sha256, actual_executable = _checkpoint_node_state(target)
            if not _node_state_matches(
                actual_kind,
                actual_sha256,
                actual_executable,
                before_kind,
                None,
                None,
            ):
                raise ConcurrentModificationError(
                    "sandbox change source state changed before apply"
                )
            preimage = None
        await context.prepare_file_checkpoint(
            FileCheckpoint(
                attempt_id=context.attempt_id,
                session_id=context.session_id,
                workspace=str(self.paths.root),
                started_event_id=context.started_event_id,
                relative_path=change.path,
                preimage_sha256=change.before_sha256,
                preimage=preimage,
                postimage_sha256=change.after_sha256,
                created_at=datetime.now(UTC).isoformat(),
                preimage_executable=change.before_executable,
                postimage_executable=change.after_executable,
                preimage_kind=before_kind,
                postimage_kind=after_kind,
            )
        )
        result = await run_in_process(
            _apply_sandbox_change_sync,
            self.paths,
            change,
        )
        event_data: dict[str, Any] = {
            "attempt_id": context.attempt_id,
            "changeset_id": change.changeset_id,
            "path": change.path,
            "before_sha256": change.before_sha256,
            "after_sha256": change.after_sha256,
        }
        if change.format_version == 2:
            event_data.update(
                {
                    "format_version": 2,
                    "before_type": change.before_type,
                    "after_type": change.after_type,
                }
            )
        if review is None:
            await context.record_event(
                Event(
                    session_id=context.session_id,
                    type="sandbox.change.reviewed",
                    data={
                        "attempt_id": context.attempt_id,
                        "changeset_id": change.changeset_id,
                        "path": change.path,
                        "decision": "approved",
                    },
                    causation_id=context.started_event_id,
                    correlation_id=context.correlation_id,
                )
            )
        await context.record_event(
            Event(
                session_id=context.session_id,
                type="sandbox.change.applied",
                data=event_data,
                causation_id=context.started_event_id,
                correlation_id=context.correlation_id,
            )
        )
        return result

    def _load_change(
        self,
        arguments: dict[str, Any],
        *,
        session_id: str,
    ) -> _PreparedSandboxChange:
        changeset_id = require_string(arguments, "changeset_id")
        relative = require_string(arguments, "path")
        if "expected_after_sha256" not in arguments:
            raise ToolArgumentError("'expected_after_sha256' is required")
        expected_after_sha256 = arguments["expected_after_sha256"]
        if expected_after_sha256 is not None and (
            not isinstance(expected_after_sha256, str) or not _is_sha256(expected_after_sha256)
        ):
            raise ToolArgumentError("'expected_after_sha256' must be a SHA-256 digest or null")
        event = self.store.get_sandbox_changeset_event(
            session_id,
            str(self.paths.root),
            changeset_id,
        )
        if event is None:
            raise ToolError("sandbox changeset is unknown in this workspace or session")
        change = get_sandbox_change(event.data, relative)
        if change is None:
            raise ToolError("sandbox changeset does not contain this path")
        if change.get("apply_supported") is not True:
            raise ToolError("sandbox change is not a supported text-file addition or modification")
        dependencies = sandbox_change_dependencies(event.data, relative)
        missing_dependencies = [
            dependency
            for dependency in dependencies
            if self.store.get_sandbox_change_applied_event(
                session_id,
                str(self.paths.root),
                changeset_id,
                dependency,
            )
            is None
        ]
        if missing_dependencies:
            raise ToolError(
                "sandbox change dependencies must be applied first: "
                + ", ".join(missing_dependencies)
            )
        prepared_dependencies: list[_DependencyState] = []
        for dependency in dependencies:
            dependency_change = get_sandbox_change(event.data, dependency)
            if dependency_change is None:
                raise ToolError("sandbox change dependency is unavailable")
            dependency_target = self.paths.resolve(dependency)
            actual_kind, actual_sha256, actual_executable = _checkpoint_node_state(
                dependency_target
            )
            expected_kind = dependency_change.get("after_type") or "missing"
            if not _node_state_matches(
                actual_kind,
                actual_sha256,
                actual_executable,
                expected_kind,
                dependency_change.get("after_sha256"),
                dependency_change.get("after_executable"),
            ):
                raise ConcurrentModificationError(
                    f"sandbox change dependency drifted after apply: {dependency}"
                )
            prepared_dependencies.append(
                _DependencyState(
                    dependency,
                    expected_kind,
                    dependency_change.get("after_sha256"),
                    dependency_change.get("after_executable"),
                )
            )
        before_sha256 = change.get("before_sha256")
        before_executable = change.get("before_executable")
        after_sha256 = change.get("after_sha256")
        after_text = change.get("after_text")
        if before_sha256 is not None and not isinstance(before_sha256, str):
            raise ToolError("sandbox change preimage digest is invalid")
        if before_executable is not None and type(before_executable) is not bool:
            raise ToolError("sandbox change preimage mode is invalid")
        before_type = change.get("before_type") if event.data.get("format_version") == 2 else None
        after_type = change.get("after_type") if event.data.get("format_version") == 2 else "file"
        if event.data.get("format_version") != 2:
            before_type = None if change.get("kind") == "added" else "file"
        if event.data.get("format_version") == 2 and after_type == "file":
            artifact_sha256 = change.get("artifact_sha256")
            if not isinstance(artifact_sha256, str):
                raise ToolError("sandbox change artifact is unavailable")
            artifact = self.store.get_binary_artifact(artifact_sha256)
            if artifact is None:
                raise ToolError("sandbox change artifact is unavailable")
            postimage = artifact.content
        elif after_type == "file" and isinstance(after_text, str):
            postimage = after_text.encode("utf-8")
        else:
            postimage = None
        if postimage is not None and sha256_bytes(postimage) != after_sha256:
            raise ToolError("sandbox change artifact digest is invalid")
        if expected_after_sha256 != after_sha256:
            raise ToolArgumentError("expected_after_sha256 does not match the sandbox changeset")
        resolved = self.paths.resolve(relative)
        if self.paths.relative(resolved) != relative:
            raise ToolArgumentError("sandbox change path is not canonical")
        return _PreparedSandboxChange(
            changeset_id=changeset_id,
            path=relative,
            before_type=before_type if isinstance(before_type, str) else None,
            after_type=after_type if isinstance(after_type, str) else None,
            before_sha256=before_sha256,
            after_sha256=after_sha256 if isinstance(after_sha256, str) else None,
            before_executable=before_executable,
            after_executable=(
                change.get("after_executable")
                if type(change.get("after_executable")) is bool
                else None
            ),
            postimage=postimage,
            format_version=2 if event.data.get("format_version") == 2 else 1,
            dependencies=tuple(prepared_dependencies),
        )


class ReviewSandboxChangeTool:
    _SPEC = ToolSpec(
        name="review_sandbox_change",
        description="Approve or reject one path in a durable sandbox changeset.",
        input_schema={
            "type": "object",
            "properties": {
                "changeset_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                "path": {"type": "string", "minLength": 1, "maxLength": 512},
                "decision": {"type": "string", "enum": ["approved", "rejected"]},
            },
            "required": ["changeset_id", "path", "decision"],
            "additionalProperties": False,
        },
        side_effect="write_state",
        capability=Capability.WORKSPACE_WRITE,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath, store: EventStore) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self.store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolError("review_sandbox_change requires the current session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        changeset_id, relative, _change = _load_changeset_change(
            self.store,
            self.paths,
            arguments,
            context.session_id,
        )
        decision = arguments.get("decision")
        if decision not in {"approved", "rejected"}:
            raise ToolArgumentError("'decision' must be approved or rejected")
        if (
            self.store.get_sandbox_change_applied_event(
                context.session_id,
                str(self.paths.root),
                changeset_id,
                relative,
            )
            is not None
        ):
            raise ToolError("an applied sandbox change cannot be reviewed again")
        await context.record_event(
            Event(
                session_id=context.session_id,
                type="sandbox.change.reviewed",
                data={
                    "attempt_id": context.attempt_id,
                    "changeset_id": changeset_id,
                    "path": relative,
                    "decision": decision,
                },
                causation_id=context.started_event_id,
                correlation_id=context.correlation_id,
            )
        )
        return json_result({"changeset_id": changeset_id, "path": relative, "decision": decision})


class ListSandboxChangesetsTool:
    _SPEC = ToolSpec(
        name="list_sandbox_changesets",
        description=(
            "List durable sandbox changesets in the current session without returning file content."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}
            },
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.WORKSPACE_READ,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath, store: EventStore) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self.store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolError("list_sandbox_changesets requires the current session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        raw_limit = arguments.get("limit", 20)
        if type(raw_limit) is not int or not 1 <= raw_limit <= 100:
            raise ToolArgumentError("'limit' must be an integer from 1 to 100")
        events = self.store.list_sandbox_changeset_events(
            context.session_id,
            str(self.paths.root),
            limit=raw_limit + 1,
        )
        documents: list[dict[str, Any]] = []
        for event in events[:raw_limit]:
            changes = event.data.get("changes")
            if not isinstance(changes, list):
                raise ToolError("stored sandbox changeset is invalid")
            changeset_id = event.data.get("changeset_id")
            if not isinstance(changeset_id, str):
                raise ToolError("stored sandbox changeset identity is invalid")
            applied_paths = {
                applied.data.get("path")
                for applied in self.store.list_sandbox_change_applied_events(
                    context.session_id,
                    str(self.paths.root),
                    changeset_id,
                )
                if isinstance(applied.data.get("path"), str)
            }
            supported_paths: set[str] = set()
            for change in changes:
                if not isinstance(change, dict) or change.get("apply_supported") is not True:
                    continue
                path = change.get("path")
                if isinstance(path, str):
                    supported_paths.add(path)
            applied_supported = len(applied_paths & supported_paths)
            supported_count = len(supported_paths)
            rejected_count = 0
            for path in supported_paths:
                review = self.store.get_sandbox_change_review_event(
                    context.session_id,
                    str(self.paths.root),
                    changeset_id,
                    path,
                )
                if review is not None and review.data.get("decision") == "rejected":
                    rejected_count += 1
            state = (
                "rejected"
                if rejected_count
                else "review_only"
                if supported_count == 0
                else "applied"
                if applied_supported == supported_count
                else "partially_applied"
                if applied_supported
                else "pending"
            )
            documents.append(
                {
                    "changeset_id": changeset_id,
                    "created_at": event.created_at,
                    "manifest_sha256": event.data.get("manifest_sha256"),
                    "source_tree_sha256": event.data.get("source_tree_sha256"),
                    "staged_tree_sha256": event.data.get("staged_tree_sha256"),
                    "change_count": len(changes),
                    "supported_count": supported_count,
                    "applied_count": applied_supported,
                    "rejected_count": rejected_count,
                    "state": state,
                }
            )
        return json_result(
            {
                "changesets": documents,
                "truncated": len(events) > raw_limit,
            }
        )


class InspectSandboxChangeTool:
    _SPEC = ToolSpec(
        name="inspect_sandbox_change",
        description=(
            "Inspect one path in a durable sandbox changeset, including its bounded retained "
            "postimage text when available."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "changeset_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                "path": {"type": "string", "minLength": 1, "maxLength": 512},
                "offset_bytes": {"type": "integer", "minimum": 0, "default": 0},
                "max_bytes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 1048576,
                    "default": 65536,
                },
            },
            "required": ["changeset_id", "path"],
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath, store: EventStore) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self.store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolError("inspect_sandbox_change requires the current session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        changeset_id, relative, change = _load_changeset_change(
            self.store,
            self.paths,
            arguments,
            context.session_id,
        )
        applied = self.store.get_sandbox_change_applied_event(
            context.session_id,
            str(self.paths.root),
            changeset_id,
            relative,
        )
        event = self.store.get_sandbox_changeset_event(
            context.session_id,
            str(self.paths.root),
            changeset_id,
        )
        if event is None:
            raise ToolError("sandbox changeset is unavailable")
        review = self.store.get_sandbox_change_review_event(
            context.session_id,
            str(self.paths.root),
            changeset_id,
            relative,
        )
        content_document: dict[str, Any] | None = None
        if change.get("artifact_sha256") is not None:
            artifact_sha256 = change.get("artifact_sha256")
            if not isinstance(artifact_sha256, str):
                raise ToolError("sandbox change artifact identity is invalid")
            artifact = self.store.get_binary_artifact(artifact_sha256)
            if artifact is None:
                raise ToolError("sandbox change artifact is unavailable")
            content_document = _artifact_page(
                artifact.content,
                change.get("content_kind"),
                arguments,
            )
        elif isinstance(change.get("after_text"), str):
            content = change["after_text"].encode("utf-8")
            content_document = _artifact_page(content, "utf8", arguments)
        return json_result(
            {
                "changeset_id": changeset_id,
                "path": relative,
                "kind": change.get("kind"),
                "before_type": change.get("before_type"),
                "after_type": change.get("after_type"),
                "before_bytes": change.get("before_bytes"),
                "after_bytes": change.get("after_bytes"),
                "before_sha256": change.get("before_sha256"),
                "after_sha256": change.get("after_sha256"),
                "before_executable": change.get("before_executable"),
                "after_executable": change.get("after_executable"),
                "apply_supported": change.get("apply_supported"),
                "applied": applied is not None,
                "review": review.data.get("decision") if review is not None else None,
                "dependencies": list(sandbox_change_dependencies(event.data, relative)),
                "content": content_document,
            }
        )


class SandboxChangeStatusTool:
    _SPEC = ToolSpec(
        name="sandbox_change_status",
        description=(
            "Compare one durable sandbox change with the current workspace without modifying it."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "changeset_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                "path": {"type": "string", "minLength": 1, "maxLength": 512},
            },
            "required": ["changeset_id", "path"],
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath, store: EventStore) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self.store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolError("sandbox_change_status requires the current session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        changeset_id, relative, change = _load_changeset_change(
            self.store,
            self.paths,
            arguments,
            context.session_id,
        )
        applied = self.store.get_sandbox_change_applied_event(
            context.session_id,
            str(self.paths.root),
            changeset_id,
            relative,
        )
        target = self.paths.resolve(relative)
        if change.get("apply_supported") is not True:
            state = "unsupported"
            actual_sha256 = None
            actual_executable = None
        else:
            try:
                actual_kind, actual_sha256, actual_executable = _checkpoint_node_state(target)
            except ToolError:
                state = "unscannable"
                actual_kind = "unscannable"
                actual_sha256 = None
                actual_executable = None
            else:
                before_kind = change.get("before_type")
                after_kind = change.get("after_type")
                if before_kind is None and "before_type" not in change:
                    before_kind = "missing" if change.get("kind") == "added" else "file"
                if after_kind is None and "after_type" not in change:
                    after_kind = "file"
                before_matches = _node_state_matches(
                    actual_kind,
                    actual_sha256,
                    actual_executable,
                    before_kind or "missing",
                    change.get("before_sha256"),
                    change.get("before_executable"),
                )
                after_matches = _node_state_matches(
                    actual_kind,
                    actual_sha256,
                    actual_executable,
                    after_kind or "missing",
                    change.get("after_sha256"),
                    change.get("after_executable"),
                )
                state = (
                    "applied"
                    if applied is not None and after_matches
                    else "post_apply_drift"
                    if applied is not None
                    else "ready"
                    if before_matches
                    else "already_matches"
                    if after_matches
                    else "drifted"
                )
        return json_result(
            {
                "changeset_id": changeset_id,
                "path": relative,
                "state": state,
                "applied_event": applied is not None,
                "actual_type": actual_kind,
                "actual_sha256": actual_sha256,
                "actual_executable": actual_executable,
                "before_sha256": change.get("before_sha256"),
                "after_sha256": change.get("after_sha256"),
            }
        )


def _load_changeset_change(
    store: EventStore,
    paths: WorkspacePaths,
    arguments: dict[str, Any],
    session_id: str,
) -> tuple[str, str, dict[str, Any]]:
    changeset_id = require_string(arguments, "changeset_id")
    relative = require_string(arguments, "path")
    resolved = paths.resolve(relative)
    if paths.relative(resolved) != relative:
        raise ToolArgumentError("sandbox change path is not canonical")
    event = store.get_sandbox_changeset_event(session_id, str(paths.root), changeset_id)
    if event is None:
        raise ToolError("sandbox changeset is unknown in this workspace or session")
    change = get_sandbox_change(event.data, relative)
    if change is None:
        raise ToolError("sandbox changeset does not contain this path")
    return changeset_id, relative, change


def _artifact_page(
    content: bytes,
    content_kind: object,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    offset = arguments.get("offset_bytes", 0)
    maximum = arguments.get("max_bytes", 64 * 1024)
    if type(offset) is not int or offset < 0:
        raise ToolArgumentError("'offset_bytes' must be a non-negative integer")
    if type(maximum) is not int or not 1 <= maximum <= 1024 * 1024:
        raise ToolArgumentError("'max_bytes' must be an integer from 1 to 1048576")
    if offset > len(content):
        raise ToolArgumentError("'offset_bytes' exceeds the artifact size")
    end = min(len(content), offset + maximum)
    page = content[offset:end]
    if content_kind == "utf8":
        try:
            content[:offset].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ToolArgumentError("'offset_bytes' must be on a UTF-8 boundary") from exc
        while page:
            try:
                text = page.decode("utf-8")
                break
            except UnicodeDecodeError as exc:
                if exc.reason != "unexpected end of data":
                    raise ToolError("stored UTF-8 artifact is invalid") from exc
                end -= 1
                page = content[offset:end]
        else:
            text = ""
        encoded = text
        encoding = "utf-8"
    else:
        encoded = base64.b64encode(page).decode("ascii")
        encoding = "base64"
    return {
        "encoding": encoding,
        "data": encoded,
        "offset_bytes": offset,
        "end_bytes": end,
        "total_bytes": len(content),
        "truncated": end < len(content),
    }


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
