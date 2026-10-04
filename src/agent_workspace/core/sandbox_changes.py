from __future__ import annotations

import hashlib
import json
from typing import Any

from agent_workspace.core.models import BinaryArtifact

_MAX_CHANGESET_BYTES = 512 * 1024
_MAX_CHANGE_CONTENT_BYTES = 64 * 1024
_MAX_APPLY_PREIMAGE_BYTES = 16 * 1024 * 1024
_MAX_CHANGES = 128
_MAX_PATH_CHARS = 512
_CHANGE_FIELDS = frozenset(
    {
        "path",
        "kind",
        "before_bytes",
        "before_sha256",
        "after_sha256",
        "before_executable",
        "after_executable",
        "after_text",
        "apply_supported",
    }
)
_CHANGESET_FIELDS = frozenset(
    {
        "attempt_id",
        "changeset_id",
        "workspace",
        "manifest_sha256",
        "source_tree_sha256",
        "staged_tree_sha256",
        "changes",
    }
)
_V2_CHANGE_FIELDS = frozenset(
    {
        "path",
        "kind",
        "before_type",
        "after_type",
        "before_bytes",
        "after_bytes",
        "before_sha256",
        "after_sha256",
        "before_executable",
        "after_executable",
        "artifact_sha256",
        "artifact_bytes",
        "content_kind",
        "apply_supported",
    }
)
_V2_CHANGESET_FIELDS = frozenset(
    {
        "format_version",
        "attempt_id",
        "changeset_id",
        "workspace",
        "manifest_sha256",
        "source_tree_sha256",
        "staged_tree_sha256",
        "changes",
    }
)
_APPLIED_FIELDS = frozenset(
    {
        "attempt_id",
        "changeset_id",
        "path",
        "before_sha256",
        "after_sha256",
    }
)
_APPLIED_V2_FIELDS = frozenset(
    {
        "format_version",
        "attempt_id",
        "changeset_id",
        "path",
        "before_type",
        "after_type",
        "before_sha256",
        "after_sha256",
    }
)
_REVIEW_FIELDS = frozenset({"attempt_id", "changeset_id", "path", "decision"})


def build_sandbox_changeset_data(
    attempt_id: str,
    workspace: str,
    manifest: dict[str, Any],
    artifacts: dict[str, BinaryArtifact] | None = None,
) -> dict[str, Any] | None:
    if manifest.get("complete") is not True:
        return None
    raw_changes = manifest.get("changes")
    if not isinstance(raw_changes, list) or not raw_changes or len(raw_changes) > _MAX_CHANGES:
        return None
    if artifacts is not None:
        return _build_v2_changeset(attempt_id, workspace, manifest, raw_changes, artifacts)
    changes: list[dict[str, Any]] = []
    for raw_change in raw_changes:
        if not isinstance(raw_change, dict):
            return None
        path = raw_change.get("path")
        kind = raw_change.get("kind")
        before_sha256 = raw_change.get("before_sha256")
        before_bytes = raw_change.get("before_bytes")
        after_sha256 = raw_change.get("after_sha256")
        before_executable = raw_change.get("before_executable")
        after_executable = raw_change.get("after_executable")
        after_text = raw_change.get("after_text")
        apply_supported = (
            kind in {"added", "modified"}
            and raw_change.get("after_type") == "file"
            and (kind != "modified" or raw_change.get("before_type") == "file")
            and isinstance(after_text, str)
            and isinstance(after_sha256, str)
            and hashlib.sha256(after_text.encode("utf-8")).hexdigest() == after_sha256
            and len(after_text.encode("utf-8")) <= _MAX_CHANGE_CONTENT_BYTES
            and (
                (kind == "added" and before_executable is None)
                or (kind == "modified" and before_executable is False)
            )
            and after_executable is False
            and (
                (kind == "added" and before_bytes is None)
                or (
                    kind == "modified"
                    and isinstance(before_bytes, int)
                    and not isinstance(before_bytes, bool)
                    and 0 <= before_bytes <= _MAX_APPLY_PREIMAGE_BYTES
                )
            )
        )
        changes.append(
            {
                "path": path,
                "kind": kind,
                "before_bytes": before_bytes,
                "before_sha256": before_sha256,
                "after_sha256": after_sha256,
                "before_executable": before_executable,
                "after_executable": after_executable,
                "after_text": after_text if apply_supported else None,
                "apply_supported": apply_supported,
            }
        )
    identity = {
        "manifest_sha256": manifest.get("manifest_sha256"),
        "source_tree_sha256": manifest.get("source_tree_sha256"),
        "staged_tree_sha256": manifest.get("staged_tree_sha256"),
        "changes": changes,
    }
    changeset_id = hashlib.sha256(_canonical_bytes(identity)).hexdigest()
    data = {
        "attempt_id": attempt_id,
        "changeset_id": changeset_id,
        "workspace": workspace,
        **identity,
    }
    validate_sandbox_changeset_event("sandbox.changeset.created", data)
    return data


def validate_sandbox_changeset_event(event_type: str, data: dict[str, Any]) -> bool:
    if event_type == "sandbox.changeset.created":
        if data.get("format_version") == 2:
            _validate_created_v2(data)
        else:
            _validate_created(data)
        return True
    if event_type in {"sandbox.change.applied", "sandbox.change.applied.imported"}:
        if data.get("format_version") == 2:
            _validate_applied_v2(data)
        else:
            _validate_applied(data)
        return True
    if event_type == "sandbox.change.reviewed":
        _validate_review(data)
        return True
    return False


def get_sandbox_change(data: dict[str, Any], path: str) -> dict[str, Any] | None:
    if data.get("format_version") == 2:
        _validate_created_v2(data)
    else:
        _validate_created(data)
    changes = data["changes"]
    assert isinstance(changes, list)
    for change in changes:
        assert isinstance(change, dict)
        if change.get("path") == path:
            return change
    return None


def sandbox_change_dependencies(data: dict[str, Any], path: str) -> tuple[str, ...]:
    target = get_sandbox_change(data, path)
    if target is None:
        return ()
    changes = data["changes"]
    assert isinstance(changes, list)
    dependencies: set[str] = set()
    for candidate in changes:
        if not isinstance(candidate, dict):
            continue
        candidate_path = candidate.get("path")
        if not isinstance(candidate_path, str) or candidate_path == path:
            continue
        if (
            path.startswith(f"{candidate_path}/")
            and candidate.get("after_type") == "directory"
            and candidate.get("kind") in {"added", "type_changed"}
        ):
            dependencies.add(candidate_path)
        if (
            candidate_path.startswith(f"{path}/")
            and target.get("before_type") == "directory"
            and target.get("after_type") != "directory"
            and candidate.get("after_type") is None
        ):
            dependencies.add(candidate_path)
        if (
            target.get("kind") == "deleted"
            and target.get("before_type") == "file"
            and candidate.get("kind") == "added"
            and candidate.get("after_type") == "file"
            and candidate.get("after_sha256") == target.get("before_sha256")
        ):
            dependencies.add(candidate_path)
    return tuple(sorted(dependencies))


def _build_v2_changeset(
    attempt_id: str,
    workspace: str,
    manifest: dict[str, Any],
    raw_changes: list[object],
    artifacts: dict[str, BinaryArtifact],
) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    for raw_change in raw_changes:
        if not isinstance(raw_change, dict):
            raise ValueError("sandbox manifest contains an invalid change")
        after_sha256 = raw_change.get("after_sha256")
        artifact = artifacts.get(after_sha256) if isinstance(after_sha256, str) else None
        content_kind: str | None = None
        if artifact is not None:
            try:
                artifact.content.decode("utf-8")
            except UnicodeDecodeError:
                content_kind = "binary"
            else:
                content_kind = "utf8"
        kind = raw_change.get("kind")
        before_bytes = raw_change.get("before_bytes")
        before_executable = raw_change.get("before_executable")
        after_executable = raw_change.get("after_executable")
        before_type = raw_change.get("before_type")
        after_type = raw_change.get("after_type")
        after_bytes = raw_change.get("after_bytes")
        before_supported = (
            (
                before_type is None
                and before_bytes is None
                and raw_change.get("before_sha256") is None
                and before_executable is None
            )
            or (
                before_type == "directory"
                and before_bytes is None
                and raw_change.get("before_sha256") is None
                and before_executable is None
            )
            or (
                before_type == "file"
                and isinstance(before_bytes, int)
                and not isinstance(before_bytes, bool)
                and 0 <= before_bytes <= _MAX_APPLY_PREIMAGE_BYTES
                and _is_sha256(raw_change.get("before_sha256"))
                and type(before_executable) is bool
            )
        )
        after_supported = (
            (
                after_type is None
                and after_bytes is None
                and after_sha256 is None
                and after_executable is None
            )
            or (
                after_type == "directory"
                and after_bytes is None
                and after_sha256 is None
                and after_executable is None
            )
            or (
                after_type == "file"
                and artifact is not None
                and artifact.sha256 == after_sha256
                and artifact.byte_count == after_bytes
                and type(after_executable) is bool
            )
        )
        transition_matches = (
            (kind == "added" and before_type is None and after_type is not None)
            or (kind == "deleted" and before_type is not None and after_type is None)
            or (kind == "modified" and before_type == after_type == "file")
            or (
                kind == "type_changed"
                and before_type in {"file", "directory"}
                and after_type in {"file", "directory"}
                and before_type != after_type
            )
        )
        apply_supported = before_supported and after_supported and transition_matches
        changes.append(
            {
                "path": raw_change.get("path"),
                "kind": kind,
                "before_type": before_type,
                "after_type": after_type,
                "before_bytes": before_bytes,
                "after_bytes": after_bytes,
                "before_sha256": raw_change.get("before_sha256"),
                "after_sha256": after_sha256,
                "before_executable": before_executable,
                "after_executable": after_executable,
                "artifact_sha256": artifact.sha256 if artifact is not None else None,
                "artifact_bytes": artifact.byte_count if artifact is not None else None,
                "content_kind": content_kind,
                "apply_supported": apply_supported,
            }
        )
    identity = {
        "format_version": 2,
        "manifest_sha256": manifest.get("manifest_sha256"),
        "source_tree_sha256": manifest.get("source_tree_sha256"),
        "staged_tree_sha256": manifest.get("staged_tree_sha256"),
        "changes": changes,
    }
    data = {
        **identity,
        "attempt_id": attempt_id,
        "changeset_id": hashlib.sha256(_canonical_bytes(identity)).hexdigest(),
        "workspace": workspace,
    }
    _validate_created_v2(data)
    return data


def _validate_created(data: dict[str, Any]) -> None:
    if set(data) != _CHANGESET_FIELDS:
        raise ValueError("sandbox.changeset.created contains unexpected fields")
    attempt_id = data.get("attempt_id")
    changeset_id = data.get("changeset_id")
    workspace = data.get("workspace")
    manifest_sha256 = data.get("manifest_sha256")
    source_tree_sha256 = data.get("source_tree_sha256")
    staged_tree_sha256 = data.get("staged_tree_sha256")
    changes = data.get("changes")
    if (
        not isinstance(attempt_id, str)
        or not attempt_id
        or len(attempt_id) > 128
        or not _is_sha256(changeset_id)
        or not isinstance(workspace, str)
        or not workspace
        or len(workspace) > 32767
        or not _is_sha256(manifest_sha256)
        or not _is_sha256(source_tree_sha256)
        or not _is_sha256(staged_tree_sha256)
        or not isinstance(changes, list)
        or not changes
        or len(changes) > _MAX_CHANGES
    ):
        raise ValueError("sandbox.changeset.created contains invalid metadata")
    paths: list[str] = []
    for change in changes:
        _validate_change(change)
        assert isinstance(change, dict)
        paths.append(change["path"])
    if paths != sorted(paths) or len(set(paths)) != len(paths):
        raise ValueError("sandbox changes must have sorted unique paths")
    identity = {
        "manifest_sha256": manifest_sha256,
        "source_tree_sha256": source_tree_sha256,
        "staged_tree_sha256": staged_tree_sha256,
        "changes": changes,
    }
    if changeset_id != hashlib.sha256(_canonical_bytes(identity)).hexdigest():
        raise ValueError("sandbox changeset id does not match its content")
    if len(_canonical_bytes(data)) > _MAX_CHANGESET_BYTES:
        raise ValueError("sandbox changeset exceeds its event size limit")


def _validate_created_v2(data: dict[str, Any]) -> None:
    if set(data) != _V2_CHANGESET_FIELDS:
        raise ValueError("sandbox format-2 changeset contains unexpected fields")
    changes = data.get("changes")
    if (
        data.get("format_version") != 2
        or not isinstance(data.get("attempt_id"), str)
        or not data["attempt_id"]
        or len(data["attempt_id"]) > 128
        or not _is_sha256(data.get("changeset_id"))
        or not isinstance(data.get("workspace"), str)
        or not data["workspace"]
        or len(data["workspace"]) > 32767
        or not _is_sha256(data.get("manifest_sha256"))
        or not _is_sha256(data.get("source_tree_sha256"))
        or not _is_sha256(data.get("staged_tree_sha256"))
        or not isinstance(changes, list)
        or not changes
        or len(changes) > _MAX_CHANGES
    ):
        raise ValueError("sandbox format-2 changeset contains invalid metadata")
    paths: list[str] = []
    for change in changes:
        _validate_change_v2(change)
        assert isinstance(change, dict)
        paths.append(change["path"])
    if paths != sorted(paths) or len(set(paths)) != len(paths):
        raise ValueError("sandbox changes must have sorted unique paths")
    identity = {
        "format_version": 2,
        "manifest_sha256": data["manifest_sha256"],
        "source_tree_sha256": data["source_tree_sha256"],
        "staged_tree_sha256": data["staged_tree_sha256"],
        "changes": changes,
    }
    if data["changeset_id"] != hashlib.sha256(_canonical_bytes(identity)).hexdigest():
        raise ValueError("sandbox changeset id does not match its content")
    if len(_canonical_bytes(data)) > _MAX_CHANGESET_BYTES:
        raise ValueError("sandbox changeset exceeds its event size limit")


def _validate_change_v2(change: object) -> None:
    if not isinstance(change, dict) or set(change) != _V2_CHANGE_FIELDS:
        raise ValueError("sandbox format-2 changeset contains invalid change fields")
    path = change.get("path")
    kind = change.get("kind")
    before_type = change.get("before_type")
    after_type = change.get("after_type")
    before_bytes = change.get("before_bytes")
    after_bytes = change.get("after_bytes")
    before_sha256 = change.get("before_sha256")
    after_sha256 = change.get("after_sha256")
    before_executable = change.get("before_executable")
    after_executable = change.get("after_executable")
    artifact_sha256 = change.get("artifact_sha256")
    artifact_bytes = change.get("artifact_bytes")
    content_kind = change.get("content_kind")
    apply_supported = change.get("apply_supported")
    if (
        not _is_relative_path(path)
        or kind not in {"added", "modified", "deleted", "type_changed"}
        or before_type not in {None, "file", "directory"}
        or after_type not in {None, "file", "directory"}
        or not _is_optional_nonnegative_int(before_bytes)
        or not _is_optional_nonnegative_int(after_bytes)
        or (before_sha256 is not None and not _is_sha256(before_sha256))
        or (after_sha256 is not None and not _is_sha256(after_sha256))
        or not _is_optional_bool(before_executable)
        or not _is_optional_bool(after_executable)
        or (artifact_sha256 is not None and not _is_sha256(artifact_sha256))
        or not _is_optional_nonnegative_int(artifact_bytes)
        or content_kind not in {None, "utf8", "binary"}
        or not isinstance(apply_supported, bool)
    ):
        raise ValueError("sandbox format-2 changeset contains invalid change metadata")
    has_artifact = artifact_sha256 is not None
    if has_artifact != (artifact_bytes is not None) or has_artifact != (content_kind is not None):
        raise ValueError("sandbox format-2 artifact metadata is inconsistent")
    if has_artifact and (
        after_type != "file"
        or artifact_sha256 != after_sha256
        or artifact_bytes != after_bytes
        or not isinstance(artifact_bytes, int)
        or artifact_bytes > _MAX_APPLY_PREIMAGE_BYTES
    ):
        raise ValueError("sandbox format-2 artifact does not match its postimage")
    if apply_supported:
        before_supported = _v2_state_supported(
            before_type,
            before_bytes,
            before_sha256,
            before_executable,
            artifact_present=True,
        )
        after_supported = _v2_state_supported(
            after_type,
            after_bytes,
            after_sha256,
            after_executable,
            artifact_present=has_artifact,
        )
        transition_matches = (
            (kind == "added" and before_type is None and after_type is not None)
            or (kind == "deleted" and before_type is not None and after_type is None)
            or (kind == "modified" and before_type == after_type == "file")
            or (
                kind == "type_changed"
                and before_type in {"file", "directory"}
                and after_type in {"file", "directory"}
                and before_type != after_type
            )
        )
        if not before_supported or not after_supported or not transition_matches:
            raise ValueError("sandbox format-2 changeset contains an invalid applicable change")


def _validate_change(change: object) -> None:
    if not isinstance(change, dict) or set(change) != _CHANGE_FIELDS:
        raise ValueError("sandbox changeset contains invalid change fields")
    path = change.get("path")
    kind = change.get("kind")
    before_bytes = change.get("before_bytes")
    before_sha256 = change.get("before_sha256")
    after_sha256 = change.get("after_sha256")
    before_executable = change.get("before_executable")
    after_executable = change.get("after_executable")
    after_text = change.get("after_text")
    apply_supported = change.get("apply_supported")
    if (
        not _is_relative_path(path)
        or kind not in {"added", "modified", "deleted", "type_changed"}
        or (
            before_bytes is not None
            and (
                not isinstance(before_bytes, int)
                or isinstance(before_bytes, bool)
                or before_bytes < 0
            )
        )
        or (before_sha256 is not None and not _is_sha256(before_sha256))
        or (after_sha256 is not None and not _is_sha256(after_sha256))
        or not _is_optional_bool(before_executable)
        or not _is_optional_bool(after_executable)
        or not isinstance(apply_supported, bool)
        or (after_text is not None and not isinstance(after_text, str))
    ):
        raise ValueError("sandbox changeset contains invalid change metadata")
    if apply_supported:
        content = after_text.encode("utf-8") if isinstance(after_text, str) else b""
        if (
            kind not in {"added", "modified"}
            or not _is_sha256(after_sha256)
            or len(content) > _MAX_CHANGE_CONTENT_BYTES
            or hashlib.sha256(content).hexdigest() != after_sha256
            or after_executable is not False
            or (kind == "added" and before_sha256 is not None)
            or (kind == "added" and before_bytes is not None)
            or (kind == "added" and before_executable is not None)
            or (kind == "modified" and not _is_sha256(before_sha256))
            or (kind == "modified" and before_executable is not False)
            or (
                kind == "modified"
                and (
                    not isinstance(before_bytes, int)
                    or isinstance(before_bytes, bool)
                    or before_bytes > _MAX_APPLY_PREIMAGE_BYTES
                )
            )
        ):
            raise ValueError("sandbox changeset contains an invalid applicable change")
    elif after_text is not None:
        raise ValueError("unsupported sandbox changes may not retain postimage text")


def _validate_applied(data: dict[str, Any]) -> None:
    if set(data) != _APPLIED_FIELDS:
        raise ValueError("sandbox.change.applied contains unexpected fields")
    if (
        not isinstance(data.get("attempt_id"), str)
        or not data["attempt_id"]
        or len(data["attempt_id"]) > 128
        or not _is_sha256(data.get("changeset_id"))
        or not _is_relative_path(data.get("path"))
        or (data.get("before_sha256") is not None and not _is_sha256(data.get("before_sha256")))
        or not _is_sha256(data.get("after_sha256"))
    ):
        raise ValueError("sandbox.change.applied contains invalid metadata")


def _validate_applied_v2(data: dict[str, Any]) -> None:
    if set(data) != _APPLIED_V2_FIELDS:
        raise ValueError("sandbox format-2 applied event contains unexpected fields")
    if (
        data.get("format_version") != 2
        or not isinstance(data.get("attempt_id"), str)
        or not data["attempt_id"]
        or len(data["attempt_id"]) > 128
        or not _is_sha256(data.get("changeset_id"))
        or not _is_relative_path(data.get("path"))
        or data.get("before_type") not in {None, "file", "directory"}
        or data.get("after_type") not in {None, "file", "directory"}
        or (data.get("before_sha256") is not None and not _is_sha256(data.get("before_sha256")))
        or (data.get("after_sha256") is not None and not _is_sha256(data.get("after_sha256")))
    ):
        raise ValueError("sandbox format-2 applied event contains invalid metadata")


def _validate_review(data: dict[str, Any]) -> None:
    if set(data) != _REVIEW_FIELDS or (
        not isinstance(data.get("attempt_id"), str)
        or not data["attempt_id"]
        or len(data["attempt_id"]) > 128
        or not _is_sha256(data.get("changeset_id"))
        or not _is_relative_path(data.get("path"))
        or data.get("decision") not in {"approved", "rejected"}
    ):
        raise ValueError("sandbox.change.reviewed contains invalid metadata")


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_optional_bool(value: object) -> bool:
    return value is None or type(value) is bool


def _is_optional_nonnegative_int(value: object) -> bool:
    return value is None or (type(value) is int and value >= 0)


def _v2_state_supported(
    node_type: object,
    byte_count: object,
    sha256: object,
    executable: object,
    *,
    artifact_present: bool,
) -> bool:
    if node_type is None:
        return byte_count is None and sha256 is None and executable is None
    if node_type == "directory":
        return byte_count is None and sha256 is None and executable is None
    return (
        node_type == "file"
        and type(byte_count) is int
        and 0 <= byte_count <= _MAX_APPLY_PREIMAGE_BYTES
        and _is_sha256(sha256)
        and type(executable) is bool
        and artifact_present
    )


def _is_relative_path(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= _MAX_PATH_CHARS
        and "\\" not in value
        and not value.startswith("/")
        and all(part not in {"", ".", ".."} for part in value.split("/"))
        and all(ord(character) >= 32 for character in value)
    )


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
