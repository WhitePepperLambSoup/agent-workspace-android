"""Bounded, verified workspace changes attached to durable mobile task results."""

from __future__ import annotations

import asyncio
import hashlib
import os
import stat
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any
from weakref import WeakKeyDictionary, WeakValueDictionary

from mobile_workspace import (
    _MAX_HASH_BYTES,
    _relative_path,
    runtime_workspace,
    workspace_mime_type,
    write_workspace_file,
)

from agent_workspace.tools.filesystem import _open_identity_checked
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

_MAX_SCAN_ENTRIES = 20_000
_MAX_SCAN_FILES = 10_000
_MAX_HASH_TOTAL_BYTES = 64 * 1024 * 1024
_MAX_ARTIFACTS = 2_000
_COORDINATORS: WeakKeyDictionary[asyncio.AbstractEventLoop, WeakValueDictionary] = (
    WeakKeyDictionary()
)


def _signature(metadata: os.stat_result) -> list[int]:
    return [
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    ]


def _inspect_file(paths: WorkspacePaths, relative: str, hash_budget: int) -> tuple[dict, int]:
    target = paths.resolve(relative)
    with _open_identity_checked(target, "rb") as stream:
        paths.resolve(relative)
        before = WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), target)
        if not stat.S_ISREG(before.st_mode):
            raise FileNotFoundError(relative)
        digest = None
        read_bytes = 0
        if before.st_size <= min(_MAX_HASH_BYTES, hash_budget):
            hasher = hashlib.sha256()
            remaining = min(_MAX_HASH_BYTES, hash_budget) + 1
            while remaining:
                chunk = stream.read(min(remaining, 64 * 1024))
                if not chunk:
                    break
                hasher.update(chunk)
                read_bytes += len(chunk)
                remaining -= len(chunk)
            after = WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), target)
            if _signature(before) != _signature(after) or read_bytes != before.st_size:
                raise OSError("workspace file changed during inspection")
            digest = hasher.hexdigest()
        return {"signature": _signature(before), "sha256": digest}, read_bytes


def snapshot_task_workspace(
    workspace: str | Path, *, excluded_paths: tuple[str, ...] = ()
) -> dict[str, Any]:
    paths = WorkspacePaths(workspace)
    excluded = {os.path.normcase(str(Path(path).absolute())) for path in excluded_paths}
    files: dict[str, Any] = {}
    pending = [paths.root]
    scanned = 0
    hash_budget = _MAX_HASH_TOTAL_BYTES
    truncated = False
    inspection_error = False
    while pending and not truncated:
        directory = pending.pop()
        try:
            # Recheck each directory immediately before opening it; links are never traversed.
            paths.resolve(directory)
            with os.scandir(directory) as entries:
                for entry in entries:
                    scanned += 1
                    if scanned > _MAX_SCAN_ENTRIES or len(files) >= _MAX_SCAN_FILES:
                        truncated = True
                        break
                    relative = Path(entry.path).relative_to(paths.root).as_posix()
                    if relative.split("/", 1)[0].casefold() == "uploads":
                        continue
                    if os.path.normcase(entry.path) in excluded:
                        continue
                    try:
                        _relative_path(relative)
                        target = paths.resolve(relative)
                        metadata = target.lstat()
                        if stat.S_ISDIR(metadata.st_mode):
                            pending.append(target)
                        elif stat.S_ISREG(metadata.st_mode):
                            files[relative], consumed = _inspect_file(paths, relative, hash_budget)
                            hash_budget = max(0, hash_budget - consumed)
                    except WorkspacePathError:
                        continue
                    except ValueError:
                        continue
                    except (OSError, RuntimeError):
                        inspection_error = True
        except WorkspacePathError:
            inspection_error = True
        except OSError:
            inspection_error = True
    return {
        "version": 1,
        "workspace": str(paths.root),
        "files": files,
        "truncated": truncated,
        "error": "Some workspace files could not be inspected." if inspection_error else None,
    }


def collect_task_artifacts(
    workspace: str | Path,
    baseline: dict[str, Any],
    *,
    excluded_paths: tuple[str, ...] = (),
    prior_checkpoint: dict[str, Any] | None = None,
    attributed_files: dict[str, Any] | None = None,
    attribution_error: str | None = None,
    warn_unattributed: bool = False,
) -> dict[str, Any]:
    if baseline.get("error") or baseline.get("version") != 1:
        return {
            "artifacts": [],
            "artifacts_truncated": bool(baseline.get("truncated")),
            "artifacts_error": baseline.get("error") or "Workspace baseline is unavailable.",
        }
    current = snapshot_task_workspace(workspace, excluded_paths=excluded_paths)
    if current["workspace"] != baseline.get("workspace"):
        return {
            "artifacts": [],
            "artifacts_truncated": False,
            "artifacts_error": "Workspace changed since artifact inspection started.",
        }
    before = baseline.get("files", {})
    artifacts = []
    unattributed = False
    truncated = baseline["truncated"] or current["truncated"]
    for relative, record in sorted(current["files"].items()):
        previous = before.get(relative)
        if previous is not None:
            if previous["signature"] == record["signature"]:
                continue
            if previous["sha256"] is not None and previous["sha256"] == record["sha256"]:
                continue
        elif baseline["truncated"]:
            # An incomplete baseline cannot prove that an unseen path was created by this task.
            continue
        if attributed_files is not None and not _matches_attributed_file(
            record, attributed_files.get(relative)
        ):
            unattributed = True
            continue
        if len(artifacts) >= _MAX_ARTIFACTS:
            truncated = True
            break
        artifacts.append(
            {
                "path": relative,
                "name": Path(relative).name,
                "size": record["signature"][2],
                "sha256": record["sha256"],
                "mime_type": workspace_mime_type(relative),
                "state": "created" if previous is None else "modified",
            }
        )
    merged = {artifact["path"]: artifact for artifact in artifacts}
    prior = validated_partial_artifacts(baseline, prior_checkpoint)
    for artifact in prior:
        relative = artifact["path"]
        if relative in merged:
            merged[relative]["state"] = artifact["state"]
        else:
            record = current["files"].get(relative)
            if record and _matches_checkpoint_file(record, artifact, prior_checkpoint, relative):
                merged[relative] = artifact
    artifacts = [merged[path] for path in sorted(merged)]
    if len(artifacts) > _MAX_ARTIFACTS:
        artifacts = artifacts[:_MAX_ARTIFACTS]
        truncated = True
    return {
        "artifacts": artifacts,
        "artifacts_truncated": truncated
        or bool((prior_checkpoint or {}).get("artifacts_truncated")),
        "artifacts_error": current["error"]
        or attribution_error
        or (prior_checkpoint or {}).get("artifacts_error")
        or (
            "Concurrent file changes without task-bound tool evidence could not be linked safely."
            if unattributed and warn_unattributed
            else None
        ),
        "signatures": {
            item["path"]: current["files"][item["path"]]["signature"] for item in artifacts
        },
    }


def _matches_attributed_file(record, receipt) -> bool:
    if not isinstance(receipt, dict):
        return False
    if receipt.get("sha256") is not None and record["sha256"] is not None:
        return receipt["sha256"] == record["sha256"]
    return record["signature"] == receipt.get("signature")


class _WorkspaceArtifactCoordinator:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.scopes: dict[str, MobileArtifactScope] = {}
        self.tool: tuple[MobileArtifactScope, str, dict[str, Any] | None] | None = None


class MobileArtifactScope:
    """Attribute files while other conversations execute in the same directory."""

    def __init__(
        self,
        coordinator: _WorkspaceArtifactCoordinator,
        task_id: str,
        workspace: Path,
        excluded_paths: tuple[str, ...],
    ) -> None:
        self.coordinator = coordinator
        self.task_id = task_id
        self.workspace = workspace
        self.excluded_paths = excluded_paths
        self.overlapped = bool(coordinator.scopes)
        self.has_tool_events = False
        self.files: dict[str, Any] = {}
        self.version_files: dict[str, Any] = {}
        self.baseline: dict[str, Any] | None = None
        self.error: str | None = None
        self.background_job_store: Any | None = None
        self.background_jobs: tuple[tuple[str, str, str], ...] | None = None
        self.background_job_unsafe = False
        for scope in coordinator.scopes.values():
            scope.overlapped = True
        coordinator.scopes[task_id] = self

    @asynccontextmanager
    async def inspection(self):
        active = self.coordinator.tool
        if active is not None and active[0] is self:
            raise RuntimeError("Task artifact inspection requires its active tool to finish.")
        async with self.coordinator.lock:
            yield

    async def start_tool(self, attempt_id: str, *, file_versions_only: bool = False) -> None:
        active = self.coordinator.tool
        if active is not None and active[0] is self:
            if active[1] == attempt_id:
                return
            self.error = "Nested tool output attribution was rejected."
            raise RuntimeError("Nested tool starts are unsupported within one mobile task.")
        await self.coordinator.lock.acquire()
        self.has_tool_events = True
        self.coordinator.tool = (self, attempt_id, None)
        try:
            if not file_versions_only:
                if not self.overlapped:
                    self.coordinator.tool = (self, attempt_id, self.baseline)
                else:
                    try:
                        baseline = await asyncio.to_thread(
                            snapshot_task_workspace,
                            self.workspace,
                            excluded_paths=self.excluded_paths,
                        )
                    except Exception:
                        self.error = "Tool output inspection could not start."
                    else:
                        self.coordinator.tool = (self, attempt_id, baseline)
        except BaseException:
            self.coordinator.tool = None
            self.coordinator.lock.release()
            raise

    async def record_file_version(self, path: object, digest: object) -> None:
        if (
            not isinstance(path, str)
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            return
        try:
            relative = _relative_path(path)
            record, _ = await asyncio.to_thread(
                _inspect_file, WorkspacePaths(self.workspace), relative, 0
            )
        except (OSError, ValueError, RuntimeError):
            return
        self.files[relative] = {"sha256": digest, "signature": record["signature"]}
        self.version_files[relative] = self.files[relative]

    async def finish_tool(self, attempt_id: str | None = None) -> bool:
        active = self.coordinator.tool
        if active is None:
            return True
        if active[0] is not self:
            return False
        if attempt_id is not None and active[1] != attempt_id:
            self.error = "A tool settlement did not match this task's active tool."
            return False
        try:
            if active[2] is not None and self.overlapped:
                checkpoint = await asyncio.to_thread(
                    collect_task_artifacts,
                    self.workspace,
                    active[2],
                    excluded_paths=self.excluded_paths,
                )
                for artifact in checkpoint["artifacts"]:
                    relative = artifact["path"]
                    self.files[relative] = {
                        "sha256": artifact["sha256"],
                        "signature": checkpoint["signatures"][relative],
                    }
                if checkpoint.get("artifacts_error") or checkpoint.get("artifacts_truncated"):
                    self.error = checkpoint.get("artifacts_error") or (
                        "Some tool outputs exceeded the artifact inspection limit."
                    )
        except Exception:
            self.error = "Tool outputs could not be attributed safely."
        finally:
            self.coordinator.tool = None
            self.coordinator.lock.release()
        return True

    def capture_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        if self.overlapped:
            return
        for artifact in checkpoint.get("artifacts", []):
            relative = artifact["path"]
            self.files[relative] = {
                "sha256": artifact["sha256"],
                "signature": checkpoint["signatures"][relative],
            }

    def close(self) -> None:
        active = self.coordinator.tool
        if active is not None and active[0] is self:
            self.coordinator.tool = None
            self.coordinator.lock.release()
        self.coordinator.scopes.pop(self.task_id, None)


def register_task_artifacts(
    task_id: str, workspace: str | Path, *, excluded_paths: tuple[str, ...] = ()
) -> MobileArtifactScope:
    loop = asyncio.get_running_loop()
    coordinators = _COORDINATORS.setdefault(loop, WeakValueDictionary())
    root = WorkspacePaths(workspace).root
    identity = os.path.normcase(str(root))
    coordinator = coordinators.get(identity)
    if coordinator is None:
        coordinator = _WorkspaceArtifactCoordinator()
        coordinators[identity] = coordinator
    return MobileArtifactScope(coordinator, task_id, root, excluded_paths)


def background_job_fingerprint(
    store: Any, workspace: str | Path
) -> tuple[tuple[str, str, str], ...]:
    """Return a stable, read-only view of background jobs for conservative attribution."""
    try:
        jobs = store.list_background_jobs(str(WorkspacePaths(workspace).root), limit=1000)
    except AttributeError:
        return ()
    except (OSError, ValueError):
        return (("unknown", "unknown", ""),)
    return tuple(
        sorted(
            (
                str(job.session_id) + ":" + str(job.job_id),
                str(job.state),
                str(job.updated_at),
            )
            for job in jobs
        )
    )


def background_jobs_need_attribution(scope: MobileArtifactScope) -> bool:
    """Detect active or changed jobs whose asynchronous writes cannot be linked safely."""
    if scope.background_job_store is None or scope.background_jobs is None:
        return False
    current = background_job_fingerprint(scope.background_job_store, scope.workspace)
    if len(current) >= 1000 or any(state == "unknown" for _, state, _ in current):
        return True
    if any(state in {"starting", "running"} for _, state, _ in current):
        return True
    return current != scope.background_jobs


def _matches_checkpoint_file(record, artifact, checkpoint, relative) -> bool:
    if artifact.get("sha256") is not None and record["sha256"] is not None:
        return artifact["sha256"] == record["sha256"]
    return record["signature"] == (checkpoint or {}).get("signatures", {}).get(relative)


def validated_partial_artifacts(baseline, checkpoint) -> list[dict[str, Any]]:
    if baseline.get("error"):
        return []
    verified = []
    for artifact in (checkpoint or {}).get("artifacts", []):
        relative = artifact.get("path")
        record = baseline.get("files", {}).get(relative)
        if record and _matches_checkpoint_file(record, artifact, checkpoint, relative):
            verified.append(dict(artifact))
    return verified


async def write_workspace_file_coordinated(runtime: Any, payload: Any) -> dict[str, Any]:
    """Serialize editor writes with task output attribution for this workspace."""
    workspace = runtime_workspace(runtime)
    loop = asyncio.get_running_loop()
    coordinators = _COORDINATORS.setdefault(loop, WeakValueDictionary())
    identity = os.path.normcase(str(workspace))
    coordinator = coordinators.get(identity)
    if coordinator is None:
        coordinator = _WorkspaceArtifactCoordinator()
        coordinators[identity] = coordinator

    async def mutate():
        # A completed tool may have generated files before the editor acquired the
        # lock. Preserve those receipts, then require receipts for later changes.
        pending = {}
        for scope in tuple(coordinator.scopes.values()):
            if not scope.overlapped and scope.has_tool_events and scope.baseline is not None:
                try:
                    checkpoint = await asyncio.to_thread(
                        collect_task_artifacts,
                        scope.workspace,
                        scope.baseline,
                        excluded_paths=scope.excluded_paths,
                    )
                except Exception:
                    checkpoint = {"artifacts": [], "artifacts_error": "Output inspection failed."}
                pending[scope] = checkpoint
        document = await asyncio.to_thread(write_workspace_file, runtime, payload)
        for scope in tuple(coordinator.scopes.values()):
            checkpoint = pending.get(scope)
            if checkpoint is not None:
                for artifact in checkpoint["artifacts"]:
                    relative = artifact["path"]
                    scope.files[relative] = {
                        "sha256": artifact["sha256"],
                        "signature": checkpoint["signatures"][relative],
                    }
                if checkpoint.get("artifacts_error") or checkpoint.get("artifacts_truncated"):
                    scope.error = "Some outputs could not be attributed before an editor save."
            scope.overlapped = True
            scope.files.pop(document["path"], None)
            scope.version_files.pop(document["path"], None)
        return document

    async with coordinator.lock:
        mutation = asyncio.create_task(mutate())
        try:
            return await asyncio.shield(mutation)
        except asyncio.CancelledError as cancellation:
            # A worker thread cannot be cancelled midway through an atomic save.
            # Keep the lock until the save and receipt updates have both settled.
            while not mutation.done():
                try:
                    await asyncio.shield(mutation)
                except asyncio.CancelledError:
                    # A second cancellation must not interrupt the cleanup wait.
                    continue
                except Exception:
                    break
            with suppress(asyncio.CancelledError, Exception):
                mutation.result()
            raise cancellation
