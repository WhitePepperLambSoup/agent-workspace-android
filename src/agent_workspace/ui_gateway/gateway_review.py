"""Git: the working-tree diff, reverting and delivering changes, review snapshots, comments and pull
requests.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path
from typing import cast

from agent_workspace.application.agent_control import AgentControlError
from agent_workspace.application.github_delivery import GitHubDeliveryError, GitHubDeliveryService
from agent_workspace.application.review_workflow import ReviewWorkflowError, ReviewWorkflowService
from agent_workspace.coding.review_ai import ReviewAiError, review_change
from agent_workspace.core.git_diff_review import FileDiff, GitDiffReviewService
from agent_workspace.core.git_ops import (
    GitOpsError,
    git_head_sha,
    git_worktree_is_clean,
)
from agent_workspace.core.models import (
    AttentionKind,
    DeliveryCheck,
    DeliveryState,
    ReviewComment,
    ReviewDelivery,
    ReviewSnapshot,
    RunIsolation,
)
from agent_workspace.storage import (
    SQLiteEventStore,
)
from agent_workspace.tools.paths import WorkspacePaths
from agent_workspace.ui_gateway.gateway_common import (
    GatewayError,
    GatewayReply,
    _camel_case,
    _json_safe,
)
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import (
    CommandEnvelope,
)


class ReviewCommands(GatewayState):
    """Git: the working-tree diff, reverting and delivering changes, review snapshots, comments and
    pull requests.
    """

    def _get_git_diff(self, command: CommandEnvelope) -> GatewayReply:
        # Git runs outside the gateway lock, with a service of its own (a diff of a large
        # repository takes a while, and the shared service keeps the last diff's truncation).
        with self._lock:
            self._require_configured()
            self._require_payload(command, set())
            workspace = self._workspace
        assert workspace is not None
        files_payload: list[dict[str, object]] = []
        is_git_repo = True
        error: str | None = None
        try:
            service = GitDiffReviewService(workspace)
            if not service.is_git_repository():
                is_git_repo = False
                error = "not_git_repository"
            else:
                file_diffs = service.get_working_tree_diffs()
                for fd in file_diffs:
                    files_payload.append(self._file_diff_document(fd))
                if service.last_diff_truncated:
                    error = "diff_output_too_large"
        except (OSError, ValueError):
            files_payload = []
            error = "git_diff_unavailable"

        return self._reply(
            "workspace.git.diff.result",
            {
                "epoch": self.epoch,
                "isGitRepo": is_git_repo,
                "files": files_payload,
                "error": error,
            },
            session_id=command.session_id,
        )

    @staticmethod
    def _file_diff_document(file_diff: FileDiff) -> dict[str, object]:
        hunks_payload: list[dict[str, object]] = []
        for hunk in file_diff.hunks:
            hunks_payload.append(
                {
                    "hunkIndex": hunk.hunk_index,
                    "oldStart": hunk.old_start,
                    "oldCount": hunk.old_count,
                    "newStart": hunk.new_start,
                    "newCount": hunk.new_count,
                    "header": hunk.header,
                    "lines": [
                        {
                            "kind": line.kind,
                            "content": line.content,
                            "oldLineno": line.old_lineno,
                            "newLineno": line.new_lineno,
                        }
                        for line in hunk.lines
                    ],
                }
            )
        return {
            "filePath": file_diff.file_path,
            "status": file_diff.status,
            "additions": file_diff.additions,
            "deletions": file_diff.deletions,
            "summary": file_diff.summary,
            "isStaged": file_diff.is_staged,
            "isBinary": file_diff.is_binary,
            "hunks": hunks_payload,
        }

    def _get_git_service(self) -> GitDiffReviewService:
        assert self._workspace is not None
        if (
            self._git_review_service is None
            or self._git_review_service.workspace != self._workspace
        ):
            self._git_review_service = GitDiffReviewService(self._workspace)
        return self._git_review_service

    def _revert_git_diff(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"filePath"}, optional={"hunkIndex"})
        assert self._workspace is not None
        file_path = command.payload.get("filePath")
        hunk_index = command.payload.get("hunkIndex")
        if not isinstance(file_path, str) or not file_path.strip():
            raise GatewayError("invalid_path")
        if hunk_index is not None and type(hunk_index) is not int:
            raise GatewayError("invalid_hunk_index")

        service = self._get_git_service()
        success = False
        checkpoint_id: str | None = None
        error: str | None = None
        try:
            if hunk_index is None:
                success = service.revert_file(file_path)
            else:
                file_diffs = service.get_working_tree_diffs()
                match_fd = next((fd for fd in file_diffs if fd.file_path == file_path), None)
                if match_fd:
                    match_hunk = next(
                        (h for h in match_fd.hunks if h.hunk_index == hunk_index), None
                    )
                    if match_hunk:
                        success = service.revert_hunk(file_path, match_hunk)
            if success:
                checkpoint_id = service.last_checkpoint_id
        except ValueError:
            error = "invalid_path"
            success = False
        except (OSError, subprocess.SubprocessError):
            error = "git_revert_failed"
            success = False
        if not success and error is None:
            error = "git_revert_failed"

        return self._reply(
            "workspace.git.revert.result",
            {
                "epoch": self.epoch,
                "filePath": file_path,
                "hunkIndex": hunk_index,
                "success": success,
                "checkpointId": checkpoint_id,
                "error": error,
            },
            session_id=command.session_id,
        )

    def _undo_git_diff(self, command: CommandEnvelope) -> GatewayReply:
        self._require_configured()
        self._require_payload(command, {"checkpointId"})
        assert self._workspace is not None
        checkpoint_id = command.payload.get("checkpointId")
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise GatewayError("invalid_checkpoint_id")

        service = self._get_git_service()
        success = False
        error: str | None = None
        try:
            success = service.undo_checkpoint(checkpoint_id.strip())
        except (OSError, ValueError):
            success = False
        if not success:
            error = "checkpoint_changed_or_unavailable"

        return self._reply(
            "workspace.git.undo.result",
            {
                "epoch": self.epoch,
                "checkpointId": checkpoint_id,
                "success": success,
                "error": error,
            },
            session_id=command.session_id,
        )

    def _deliver_git_changes(self, command: CommandEnvelope) -> GatewayReply:
        with self._lock:
            self._require_configured()
            self._require_payload(
                command, {"title"}, optional={"description", "stageAll", "selectedFiles"}
            )
            assert self._workspace is not None
            if self._git_delivery_in_progress:
                raise GatewayError("runtime_busy")
            title = command.payload.get("title")
            description = command.payload.get("description", "")
            stage_all = command.payload.get("stageAll", False)
            selected_files = command.payload.get("selectedFiles")
            if not isinstance(title, str) or not title.strip():
                raise GatewayError("invalid_title")
            if not isinstance(description, str):
                raise GatewayError("invalid_description")
            if len(title.strip()) > 200 or len(description) > 4_000:
                raise GatewayError("invalid_commit_message")
            if type(stage_all) is not bool or stage_all:
                raise GatewayError("stage_all_not_supported")
            if not isinstance(selected_files, list) or not 1 <= len(selected_files) <= 200:
                raise GatewayError("invalid_selection")
            workspace = self._workspace
            self._git_delivery_in_progress = True

        commit_message = f"{title.strip()}\n\n{description.strip()}".strip()
        git_cmd = shutil.which("git")
        branch = "HEAD"
        commit_sha: str | None = None
        success = False
        summary = ""
        error_code: str | None = None

        try:
            if not git_cmd:
                summary = "Git executable unavailable"
            else:
                import os

                env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}
                service = GitDiffReviewService(workspace)
                if not service.is_git_repository():
                    summary = "Workspace is not a Git repository"
                else:
                    paths = WorkspacePaths(workspace)
                    valid_paths: list[str] = []
                    for raw_path in selected_files:
                        if (
                            not isinstance(raw_path, str)
                            or not raw_path.strip()
                            or any(ord(char) < 32 for char in raw_path)
                        ):
                            raise GatewayError("invalid_selection")
                        normalized = paths.relative(paths.resolve(raw_path.strip()))
                        if normalized in valid_paths:
                            raise GatewayError("invalid_selection")
                        valid_paths.append(normalized)

                    available_paths = {
                        item.file_path for item in service.get_working_tree_diffs(max_files=200)
                    }
                    if service.last_diff_truncated:
                        summary = "Selected diff is too large to deliver safely"
                    elif not set(valid_paths).issubset(available_paths):
                        summary = "Selection no longer matches the working tree"
                    else:
                        pre_staged = subprocess.run(
                            [git_cmd, "diff", "--cached", "--quiet", "--", *valid_paths],
                            cwd=workspace,
                            stdin=subprocess.DEVNULL,
                            capture_output=True,
                            timeout=10.0,
                            env=env,
                        )
                        if pre_staged.returncode == 1:
                            summary = "Selected files contain pre-existing staged changes"
                            error_code = "selected_files_have_staged_changes"
                        elif pre_staged.returncode != 0:
                            summary = "Unable to inspect selected staged changes"
                        else:
                            subprocess.run(
                                [git_cmd, "add", "--", *valid_paths],
                                cwd=workspace,
                                stdin=subprocess.DEVNULL,
                                check=True,
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                                timeout=15.0,
                                env=env,
                            )

                    if not summary:
                        st_res = subprocess.run(
                            [git_cmd, "diff", "--cached", "--quiet", "--", *valid_paths],
                            cwd=workspace,
                            stdin=subprocess.DEVNULL,
                            capture_output=True,
                            timeout=10.0,
                            env=env,
                        )
                        if st_res.returncode == 0:
                            summary = "No selected changes to commit"
                        elif st_res.returncode == 1:
                            proc = subprocess.run(
                                [
                                    git_cmd,
                                    "commit",
                                    "--only",
                                    "-m",
                                    commit_message,
                                    "--",
                                    *valid_paths,
                                ],
                                cwd=workspace,
                                stdin=subprocess.DEVNULL,
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                                timeout=15.0,
                                env=env,
                            )
                            if proc.returncode == 0:
                                success = True
                                summary = proc.stdout.strip()[:2000]
                                rev_proc = subprocess.run(
                                    [git_cmd, "rev-parse", "HEAD"],
                                    cwd=workspace,
                                    stdin=subprocess.DEVNULL,
                                    capture_output=True,
                                    text=True,
                                    timeout=5.0,
                                    env=env,
                                )
                                if rev_proc.returncode == 0:
                                    commit_sha = rev_proc.stdout.strip()
                                branch_proc = subprocess.run(
                                    [git_cmd, "rev-parse", "--abbrev-ref", "HEAD"],
                                    cwd=workspace,
                                    stdin=subprocess.DEVNULL,
                                    capture_output=True,
                                    text=True,
                                    timeout=5.0,
                                    env=env,
                                )
                                if branch_proc.returncode == 0:
                                    branch = branch_proc.stdout.strip()
                            else:
                                summary = "Git commit failed"
                        else:
                            summary = "Unable to inspect selected changes"
        except GatewayError:
            raise
        except (OSError, subprocess.SubprocessError):
            summary = "Git delivery command failed"
        finally:
            with self._lock:
                self._git_delivery_in_progress = False

        err_msg = None if success else (error_code or summary or "delivery_failed")
        if summary == "Workspace is not a Git repository":
            err_msg = "not_git_repository"

        with self._lock:
            return self._reply(
                "workspace.git.deliver.result",
                {
                    "epoch": self.epoch,
                    "commitSha": commit_sha,
                    "branch": branch,
                    "success": success,
                    "summary": summary,
                    "error": err_msg,
                },
                session_id=command.session_id,
            )

    def _review_service(self) -> ReviewWorkflowService:
        if self._workspace is None:
            raise GatewayError("runtime_unconfigured")
        service = self._review_workflow
        if service is None:
            try:
                service = ReviewWorkflowService(self._database)
            except (OSError, sqlite3.DatabaseError, RuntimeError):
                raise GatewayError("storage_unavailable") from None
            self._review_workflow = service
        return service

    @staticmethod
    def _review_snapshot_document(
        snapshot: ReviewSnapshot, *, include_files: bool = False
    ) -> dict[str, object]:
        additions = sum(
            value for file in snapshot.files if type(value := file.get("additions")) is int
        )
        deletions = sum(
            value for file in snapshot.files if type(value := file.get("deletions")) is int
        )
        document: dict[str, object] = {
            "id": snapshot.id,
            "workspace": snapshot.workspace,
            "checkoutPath": snapshot.checkout_path,
            "sessionId": snapshot.session_id,
            "runId": snapshot.run_id,
            "baseSha": snapshot.base_sha,
            "headSha": snapshot.head_sha,
            "diffSha256": snapshot.diff_sha256,
            "workingTreeDirty": snapshot.working_tree_dirty,
            "fileCount": len(snapshot.files),
            "additions": additions,
            "deletions": deletions,
            "createdAt": snapshot.created_at,
        }
        if include_files:
            document["files"] = list(snapshot.files)
        return document

    @staticmethod
    def _review_comment_document(comment: ReviewComment) -> dict[str, object]:
        raw = cast(dict[str, object], asdict(comment))
        return {_camel_case(key): _json_safe(value) for key, value in raw.items()}

    @staticmethod
    def _review_delivery_document(delivery: ReviewDelivery | None) -> dict[str, object] | None:
        if delivery is None:
            return None
        raw = cast(dict[str, object], asdict(delivery))
        return {_camel_case(key): _json_safe(value) for key, value in raw.items()}

    @staticmethod
    def _delivery_check_document(check: DeliveryCheck) -> dict[str, object]:
        raw = cast(dict[str, object], asdict(check))
        return {_camel_case(key): _json_safe(value) for key, value in raw.items()}

    def _review_details_payload(
        self, service: ReviewWorkflowService, snapshot: ReviewSnapshot
    ) -> dict[str, object]:
        comments = service.list_comments(snapshot.id)
        delivery = service.get_delivery(snapshot.id)
        checks = service.list_delivery_checks(snapshot.id) if delivery is not None else []
        return {
            "epoch": self.epoch,
            "snapshot": self._review_snapshot_document(snapshot, include_files=True),
            "comments": [self._review_comment_document(comment) for comment in comments],
            "delivery": self._review_delivery_document(delivery),
            "checks": [self._delivery_check_document(check) for check in checks],
        }

    def _list_review_snapshots(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"limit"})
        if self._workspace is None:
            raise GatewayError("runtime_unconfigured")
        limit = command.payload.get("limit", 100)
        if type(limit) is not int or not 1 <= limit <= 500:
            raise GatewayError("invalid_limit")
        try:
            snapshots = self._review_service().list_snapshots(self._workspace, limit=limit)
        except (ReviewWorkflowError, OSError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "workspace.review.list.result",
            {
                "epoch": self.epoch,
                "snapshots": [self._review_snapshot_document(item) for item in snapshots],
            },
            session_id=command.session_id,
        )

    def _get_review_snapshot(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"snapshotId"})
        snapshot_id = command.payload.get("snapshotId")
        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise GatewayError("invalid_snapshot")
        service = self._review_service()
        snapshot = service.get_snapshot(snapshot_id)
        if (
            snapshot is None
            or self._workspace is None
            or snapshot.workspace != str(self._workspace)
        ):
            raise GatewayError("snapshot_not_found")
        return self._reply(
            "workspace.review.get.result",
            self._review_details_payload(service, snapshot),
            session_id=snapshot.session_id,
        )

    def _create_review_snapshot(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, set(), optional={"runId", "baseSha"})
        with self._lock:
            if self._workspace is None:
                raise GatewayError("runtime_unconfigured")
            root = self._workspace
            service = self._review_service()
            run_id = command.payload.get("runId")
            if run_id is not None and (not isinstance(run_id, str) or not run_id):
                raise GatewayError("invalid_run")
            run = self._control_service().get_run(run_id) if isinstance(run_id, str) else None
            if run_id is not None and (run is None or run.workspace != str(root)):
                raise GatewayError("run_not_found")
            if run is not None:
                checkout = Path(run.checkout_path or run.workspace).resolve()
                session_id = run.session_id
                default_base = run.base_sha
            else:
                checkout = root
                candidate_session_id = command.session_id or self._selected_session_id
                default_base = None
                if candidate_session_id is None:
                    raise GatewayError("invalid_session")
                session_id = candidate_session_id
                with SQLiteEventStore(self._database) as store:
                    session = store.get_session(session_id)
                if session is None or Path(session.workspace).resolve() != root:
                    raise GatewayError("invalid_session")
        try:
            head_sha = git_head_sha(checkout)
            raw_base = command.payload.get("baseSha") or default_base or head_sha
            if not isinstance(raw_base, str):
                raise GatewayError("invalid_base_revision")
            git_service = GitDiffReviewService(checkout)
            files = git_service.get_review_diffs(raw_base)
            if git_service.last_diff_truncated:
                raise GatewayError("review_snapshot_too_large")
            if not files:
                raise GatewayError("review_empty")
            file_documents = [self._file_diff_document(file) for file in files]
            diff_text = json.dumps(
                file_documents,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            dirty = not git_worktree_is_clean(checkout)
            with self._lock:
                if self._workspace != root:
                    raise GatewayError("workspace_changed")
                snapshot = service.create_snapshot(
                    workspace=root,
                    checkout_path=checkout,
                    session_id=session_id,
                    run_id=run_id if isinstance(run_id, str) else None,
                    base_sha=raw_base,
                    head_sha=head_sha,
                    files=file_documents,
                    diff_text=diff_text,
                    working_tree_dirty=dirty,
                )
                return self._reply(
                    "workspace.review.create.result",
                    self._review_details_payload(service, snapshot),
                    session_id=session_id,
                )
        except GatewayError:
            raise
        except ReviewWorkflowError as error:
            raise GatewayError(str(error)) from None
        except (GitOpsError, OSError, ValueError):
            raise GatewayError("review_capture_failed") from None

    def _review_with_model(self, command: CommandEnvelope) -> GatewayReply:
        """The model reviews a snapshot; its findings become comments by "ai" on the diff."""
        self._require_payload(command, {"snapshotId"}, optional={"language"})
        snapshot_id = command.payload.get("snapshotId")
        language = command.payload.get("language", "en-US")
        if not isinstance(snapshot_id, str) or not snapshot_id or not isinstance(language, str):
            raise GatewayError("invalid_snapshot")
        service = self._review_service()
        snapshot = service.get_snapshot(snapshot_id)
        with self._lock:
            workspace = self._workspace
        if snapshot is None or workspace is None or snapshot.workspace != str(workspace):
            raise GatewayError("snapshot_not_found")
        config = self._quick_provider()
        try:
            findings, skipped = review_change(
                config,
                snapshot.files,
                checkout=Path(snapshot.checkout_path),
                language=language,
            )
        except ReviewAiError as error:
            raise GatewayError(str(error)) from None
        created = 0
        for finding in findings:
            try:
                service.create_comment(
                    snapshot.id,
                    path=finding.path,
                    side=finding.side,
                    line=finding.line,
                    body=finding.comment(),
                    author="ai",
                )
            except ReviewWorkflowError:
                skipped += 1
            else:
                created += 1
        return self._reply(
            "workspace.review.ai.result",
            {
                **self._review_details_payload(service, snapshot),
                "aiFindings": created,
                "aiSkipped": skipped,
                "model": config.model,
            },
            session_id=snapshot.session_id,
        )

    def _create_review_comment(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"snapshotId", "path", "side", "line", "body"})
        snapshot_id = command.payload.get("snapshotId")
        path = command.payload.get("path")
        side = command.payload.get("side")
        line = command.payload.get("line")
        body = command.payload.get("body")
        if not all(isinstance(value, str) for value in (snapshot_id, path, side, body)):
            raise GatewayError("invalid_review_comment")
        if type(line) is not int:
            raise GatewayError("invalid_review_comment")
        service = self._review_service()
        snapshot = service.get_snapshot(cast(str, snapshot_id))
        if (
            snapshot is None
            or self._workspace is None
            or snapshot.workspace != str(self._workspace)
        ):
            raise GatewayError("snapshot_not_found")
        try:
            comment = service.create_comment(
                snapshot.id,
                path=cast(str, path),
                side=cast(str, side),
                line=line,
                body=cast(str, body),
            )
        except ReviewWorkflowError as error:
            raise GatewayError(str(error)) from None
        return self._reply(
            "workspace.review.comments.create.result",
            {"epoch": self.epoch, "comment": self._review_comment_document(comment)},
            session_id=snapshot.session_id,
        )

    def _resolve_review_comment(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"commentId"})
        comment_id = command.payload.get("commentId")
        if not isinstance(comment_id, str) or not comment_id:
            raise GatewayError("invalid_review_comment")
        service = self._review_service()
        existing = service.get_comment(comment_id)
        if existing is None:
            raise GatewayError("comment_not_found")
        snapshot = service.get_snapshot(existing.snapshot_id)
        if (
            snapshot is None
            or self._workspace is None
            or snapshot.workspace != str(self._workspace)
        ):
            raise GatewayError("comment_not_found")
        try:
            comment = service.resolve_comment(comment_id)
        except ReviewWorkflowError as error:
            raise GatewayError(str(error)) from None
        return self._reply(
            "workspace.review.comments.resolve.result",
            {"epoch": self.epoch, "comment": self._review_comment_document(comment)},
            session_id=snapshot.session_id,
        )

    def _followup_review_comment(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(
            command,
            {"commentId"},
            optional={"sessionId", "isolation", "start"},
        )
        comment_id = command.payload.get("commentId")
        owner_session_id = (
            command.payload.get("sessionId") or command.session_id or self._selected_session_id
        )
        raw_isolation = command.payload.get("isolation", RunIsolation.WORKTREE.value)
        start = command.payload.get("start", True)
        if not isinstance(comment_id, str) or not comment_id:
            raise GatewayError("invalid_review_comment")
        if not isinstance(owner_session_id, str) or type(start) is not bool:
            raise GatewayError("invalid_session")
        try:
            isolation = RunIsolation(cast(str, raw_isolation))
        except (TypeError, ValueError):
            raise GatewayError("invalid_isolation") from None
        service = self._review_service()
        comment = service.get_comment(comment_id)
        snapshot = service.get_snapshot(comment.snapshot_id) if comment is not None else None
        if (
            comment is None
            or snapshot is None
            or self._workspace is None
            or snapshot.workspace != str(self._workspace)
        ):
            raise GatewayError("comment_not_found")
        goal = (
            f"Address review comment {comment.id} from immutable snapshot {snapshot.id} "
            f"({snapshot.diff_sha256}) at {comment.path}:{comment.line} "
            f"on the {comment.side} side.\n\n"
            f"Reviewer feedback:\n{comment.body}\n\n"
            "Implement the correction, add appropriate verification, and report evidence against "
            "the frozen review anchor."
        )
        try:
            run = self._control_service().create_run(
                workspace=self._workspace,
                session_id=owner_session_id,
                goal=goal,
                title=f"Review follow-up: {comment.path}:{comment.line}",
                isolation=isolation,
                parent_run_id=snapshot.run_id,
            )
            comment = service.link_comment_followup(comment.id, run.id)
        except (AgentControlError, ReviewWorkflowError) as error:
            raise GatewayError(str(error)) from None
        started = False
        if start:
            self._start_agent_run(
                CommandEnvelope(
                    v=command.v,
                    request_id=command.request_id,
                    type="workspace.runs.start",
                    payload={"runId": run.id},
                    session_id=owner_session_id,
                )
            )
            started = True
        return self._reply(
            "workspace.review.comments.followup.result",
            {
                "epoch": self.epoch,
                "comment": self._review_comment_document(comment),
                "run": self._run_document(run),
                "started": started,
            },
            session_id=owner_session_id,
        )

    def _assert_review_snapshot_current(
        self,
        snapshot: ReviewSnapshot,
        *,
        prepared_commit_sha: str | None = None,
    ) -> None:
        checkout = Path(snapshot.checkout_path).resolve()
        try:
            current_head = git_head_sha(checkout)
            if current_head != snapshot.head_sha:
                if (
                    snapshot.working_tree_dirty
                    and prepared_commit_sha is not None
                    and current_head == prepared_commit_sha
                ):
                    return
                raise GatewayError("review_snapshot_stale")
            files = GitDiffReviewService(checkout).get_review_diffs(snapshot.base_sha)
            documents = [self._file_diff_document(file) for file in files]
            current = json.dumps(
                documents,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            if hashlib.sha256(current.encode("utf-8")).hexdigest() != snapshot.diff_sha256:
                raise GatewayError("review_snapshot_stale")
        except GatewayError:
            raise
        except (GitOpsError, OSError, ValueError):
            raise GatewayError("review_validation_failed") from None

    def _create_review_pull_request(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(
            command,
            {"snapshotId", "title", "baseBranch"},
            optional={"body", "commitTitle"},
        )
        snapshot_id = command.payload.get("snapshotId")
        title = command.payload.get("title")
        body = command.payload.get("body", "")
        base_branch = command.payload.get("baseBranch")
        commit_title = command.payload.get("commitTitle")
        if not all(isinstance(value, str) for value in (snapshot_id, title, body, base_branch)):
            raise GatewayError("invalid_pull_request")
        if commit_title is not None and not isinstance(commit_title, str):
            raise GatewayError("invalid_pull_request")
        with self._lock:
            service = self._review_service()
            snapshot = service.get_snapshot(cast(str, snapshot_id))
            existing_delivery = service.get_delivery(snapshot.id) if snapshot is not None else None
            if (
                snapshot is None
                or self._workspace is None
                or snapshot.workspace != str(self._workspace)
            ):
                raise GatewayError("snapshot_not_found")
            if existing_delivery is not None and existing_delivery.pr_url is not None:
                raise GatewayError("pull_request_exists")
            if snapshot.id in self._review_delivery_in_progress:
                raise GatewayError("delivery_in_progress")
            self._review_delivery_in_progress.add(snapshot.id)
        try:
            self._assert_review_snapshot_current(
                snapshot,
                prepared_commit_sha=(
                    existing_delivery.commit_sha if existing_delivery is not None else None
                ),
            )
            result = GitHubDeliveryService().create_draft(
                snapshot,
                title=cast(str, title),
                body=cast(str, body),
                base_branch=cast(str, base_branch),
                commit_title=commit_title,
                resume_commit_sha=(
                    existing_delivery.commit_sha if existing_delivery is not None else None
                ),
            )
            delivery = service.upsert_delivery(
                snapshot.id,
                pr_url=cast(str, result["prUrl"]),
                pr_number=cast(int, result["prNumber"]),
                state=DeliveryState(cast(str, result["state"])),
                is_draft=cast(bool, result["isDraft"]),
                head_branch=cast(str | None, result["headBranch"]),
                base_branch=cast(str | None, result["baseBranch"]),
                commit_sha=cast(str, result["commitSha"]),
            )
            checks = service.replace_delivery_checks(
                snapshot.id,
                cast(list[Mapping[str, object]], result["checks"]),
            )
            with suppress(Exception):
                self._control_service().resolve_attention_by_source(
                    f"delivery:{snapshot.id}", resolution={"state": delivery.state.value}
                )
        except (GitHubDeliveryError, ReviewWorkflowError, GatewayError) as error:
            code = str(error)
            delivery_error = error if isinstance(error, GitHubDeliveryError) else None
            with suppress(Exception):
                service.upsert_delivery(
                    snapshot.id,
                    pr_url=delivery_error.pr_url if delivery_error is not None else None,
                    pr_number=(delivery_error.pr_number if delivery_error is not None else None),
                    state=DeliveryState.ERROR,
                    is_draft=True,
                    head_branch=(
                        delivery_error.head_branch if delivery_error is not None else None
                    ),
                    base_branch=cast(str, base_branch),
                    commit_sha=(delivery_error.commit_sha if delivery_error is not None else None),
                    last_error=code,
                )
                self._control_service().open_attention(
                    run_id=snapshot.run_id,
                    session_id=snapshot.session_id,
                    kind=AttentionKind.CI,
                    severity="critical",
                    title="Pull request delivery failed",
                    detail=code,
                    source_key=f"delivery:{snapshot.id}",
                    action={"kind": "inspect_review", "snapshotId": snapshot.id},
                )
            raise GatewayError(
                code if re.fullmatch(r"[a-z][a-z0-9_]*", code) else "delivery_failed"
            ) from None
        finally:
            with self._lock:
                self._review_delivery_in_progress.discard(snapshot.id)
        with self._lock:
            return self._reply(
                "workspace.review.pr.create.result",
                {
                    "epoch": self.epoch,
                    "delivery": self._review_delivery_document(delivery),
                    "checks": [self._delivery_check_document(check) for check in checks],
                },
                session_id=snapshot.session_id,
            )

    def _refresh_review_pull_request(self, command: CommandEnvelope) -> GatewayReply:
        self._require_payload(command, {"snapshotId"})
        snapshot_id = command.payload.get("snapshotId")
        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise GatewayError("invalid_snapshot")
        with self._lock:
            service = self._review_service()
            snapshot = service.get_snapshot(snapshot_id)
            delivery = service.get_delivery(snapshot_id)
            if (
                snapshot is None
                or self._workspace is None
                or snapshot.workspace != str(self._workspace)
            ):
                raise GatewayError("snapshot_not_found")
            if delivery is None or delivery.pr_url is None:
                raise GatewayError("pull_request_not_found")
        try:
            result = GitHubDeliveryService().inspect(
                delivery.pr_url, checkout=snapshot.checkout_path
            )
            delivery = service.upsert_delivery(
                snapshot.id,
                pr_url=cast(str, result["prUrl"]),
                pr_number=cast(int, result["prNumber"]),
                state=DeliveryState(cast(str, result["state"])),
                is_draft=cast(bool, result["isDraft"]),
                head_branch=cast(str | None, result["headBranch"]),
                base_branch=cast(str | None, result["baseBranch"]),
            )
            checks = service.replace_delivery_checks(
                snapshot.id,
                cast(list[Mapping[str, object]], result["checks"]),
            )
        except (GitHubDeliveryError, ReviewWorkflowError) as error:
            raise GatewayError(str(error)) from None
        with self._lock:
            return self._reply(
                "workspace.review.pr.refresh.result",
                {
                    "epoch": self.epoch,
                    "delivery": self._review_delivery_document(delivery),
                    "checks": [self._delivery_check_document(check) for check in checks],
                },
                session_id=snapshot.session_id,
            )
