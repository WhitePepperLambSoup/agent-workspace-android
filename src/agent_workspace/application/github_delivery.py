"""Non-interactive GitHub draft PR delivery for frozen review snapshots."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from agent_workspace.core.models import DeliveryState, ReviewSnapshot

CommandRunner = Callable[[Sequence[str], Path, int], subprocess.CompletedProcess[str]]
_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,254}\Z")
_PR_URL = re.compile(r"https://[^\s]+/pull/(\d+)")


class GitHubDeliveryError(RuntimeError):
    """Stable external delivery failure."""

    def __init__(
        self,
        code: str,
        *,
        commit_sha: str | None = None,
        head_branch: str | None = None,
        pr_url: str | None = None,
        pr_number: int | None = None,
    ) -> None:
        super().__init__(code)
        self.commit_sha = commit_sha
        self.head_branch = head_branch
        self.pr_url = pr_url
        self.pr_number = pr_number

    def with_progress(
        self,
        *,
        commit_sha: str | None,
        head_branch: str,
        pr_url: str | None = None,
        pr_number: int | None = None,
    ) -> GitHubDeliveryError:
        return GitHubDeliveryError(
            str(self),
            commit_sha=commit_sha or self.commit_sha,
            head_branch=head_branch or self.head_branch,
            pr_url=pr_url or self.pr_url,
            pr_number=pr_number or self.pr_number,
        )


def _default_runner(
    arguments: Sequence[str], cwd: Path, timeout_seconds: int
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment.update(
        {
            "GH_PROMPT_DISABLED": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_PAGER": "cat",
            "GH_PAGER": "cat",
            "NO_COLOR": "1",
        }
    )
    try:
        return subprocess.run(
            list(arguments),
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as error:
        raise GitHubDeliveryError("delivery_timeout") from error
    except OSError as error:
        raise GitHubDeliveryError("delivery_unavailable") from error


class GitHubDeliveryService:
    def __init__(self, runner: CommandRunner = _default_runner) -> None:
        self._runner = runner
        self._git = shutil.which("git")
        self._gh = shutil.which("gh")

    def create_draft(
        self,
        snapshot: ReviewSnapshot,
        *,
        title: str,
        body: str,
        base_branch: str,
        commit_title: str | None = None,
        resume_commit_sha: str | None = None,
    ) -> dict[str, Any]:
        checkout = Path(snapshot.checkout_path).resolve()
        if not checkout.is_dir():
            raise GitHubDeliveryError("review_checkout_missing")
        normalized_title = title.strip()
        normalized_body = body.strip()
        base = base_branch.strip()
        if not normalized_title or len(normalized_title) > 256:
            raise GitHubDeliveryError("invalid_pull_request_title")
        if len(normalized_body) > 50_000:
            raise GitHubDeliveryError("invalid_pull_request_body")
        if _BRANCH.fullmatch(base) is None:
            raise GitHubDeliveryError("invalid_base_branch")

        branch = self._git_stdout(checkout, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        if branch == "HEAD" or _BRANCH.fullmatch(branch) is None or branch == base:
            raise GitHubDeliveryError("invalid_head_branch")
        current_head = self._git_stdout(checkout, ["rev-parse", "HEAD"]).strip().lower()
        prepared_commit_sha: str | None = None
        normalized_resume = (resume_commit_sha or "").strip().lower()
        if current_head != snapshot.head_sha:
            if (
                not snapshot.working_tree_dirty
                or len(normalized_resume) != 40
                or any(character not in "0123456789abcdef" for character in normalized_resume)
                or current_head != normalized_resume
            ):
                raise GitHubDeliveryError("review_snapshot_stale")
            parent = self._git_stdout(checkout, ["rev-parse", "HEAD^"]).strip().lower()
            status = self._git_stdout(checkout, ["status", "--porcelain=v1", "-uall"])
            if parent != snapshot.head_sha or status.strip():
                raise GitHubDeliveryError("review_snapshot_stale")
            prepared_commit_sha = current_head

        if snapshot.working_tree_dirty and prepared_commit_sha is None:
            commit = (commit_title or "").strip()
            if not commit or len(commit) > 500:
                raise GitHubDeliveryError("review_commit_required")
            paths = [str(file["filePath"]) for file in snapshot.files]
            if sum(len(path) + 1 for path in paths) > 20_000:
                raise GitHubDeliveryError("review_pathset_too_large")
            self._git_call(checkout, ["add", "--", *paths], timeout_seconds=60)
            self._git_call(
                checkout,
                ["commit", "--only", "-m", commit, "--", *paths],
                timeout_seconds=60,
            )
            prepared_commit_sha = self._git_stdout(checkout, ["rev-parse", "HEAD"]).strip().lower()

        delivery_commit = prepared_commit_sha or current_head
        try:
            self._git_call(
                checkout,
                ["push", "--set-upstream", "origin", branch],
                timeout_seconds=120,
            )
            output = self._gh_stdout(
                checkout,
                [
                    "pr",
                    "create",
                    "--draft",
                    "--title",
                    normalized_title,
                    "--body",
                    normalized_body,
                    "--base",
                    base,
                    "--head",
                    branch,
                ],
                timeout_seconds=120,
            )
        except GitHubDeliveryError as error:
            raise error.with_progress(
                commit_sha=delivery_commit,
                head_branch=branch,
            ) from error
        match = _PR_URL.search(output)
        if match is None:
            raise GitHubDeliveryError(
                "pull_request_url_missing",
                commit_sha=delivery_commit,
                head_branch=branch,
            )
        pr_url = match.group(0)
        pr_number = int(match.group(1))
        try:
            result = self.inspect(pr_url, checkout=checkout)
        except GitHubDeliveryError as error:
            raise error.with_progress(
                commit_sha=delivery_commit,
                head_branch=branch,
                pr_url=pr_url,
                pr_number=pr_number,
            ) from error
        result["commitSha"] = delivery_commit
        return result

    def retry_draft(
        self,
        snapshot: ReviewSnapshot,
        *,
        title: str,
        body: str,
        base_branch: str,
        failure: GitHubDeliveryError | Mapping[str, object] | None = None,
        commit_title: str | None = None,
        resume_commit_sha: str | None = None,
    ) -> dict[str, Any]:
        """Retry delivery while preserving a commit prepared by an earlier attempt."""

        prepared = (resume_commit_sha or "").strip() or None
        if prepared is None and isinstance(failure, GitHubDeliveryError):
            prepared = failure.commit_sha
        elif prepared is None and isinstance(failure, Mapping):
            raw = failure.get("commitSha", failure.get("commit_sha"))
            if isinstance(raw, str):
                prepared = raw
        return self.create_draft(
            snapshot,
            title=title,
            body=body,
            base_branch=base_branch,
            commit_title=commit_title,
            resume_commit_sha=prepared,
        )

    @staticmethod
    def build_evidence(value: GitHubDeliveryError | Mapping[str, object]) -> dict[str, object]:
        """Return a bounded, copyable delivery record for UI and audit logs."""

        if isinstance(value, GitHubDeliveryError):
            return {
                "status": "failed",
                "failure": str(value),
                "commitSha": value.commit_sha,
                "headBranch": value.head_branch,
                "prUrl": value.pr_url,
                "prNumber": value.pr_number,
            }
        pr_url = value.get("prUrl")
        return {
            "status": "delivered" if isinstance(pr_url, str) and pr_url else "prepared",
            "failure": value.get("failure") if isinstance(value.get("failure"), str) else None,
            "commitSha": value.get("commitSha"),
            "headBranch": value.get("headBranch"),
            "prUrl": pr_url if isinstance(pr_url, str) else None,
            "prNumber": value.get("prNumber") if type(value.get("prNumber")) is int else None,
        }

    def inspect(self, pr_url: str, *, checkout: str | Path) -> dict[str, Any]:
        path = Path(checkout).resolve()
        output = self._gh_stdout(
            path,
            [
                "pr",
                "view",
                pr_url,
                "--json",
                "number,url,state,isDraft,headRefName,baseRefName,statusCheckRollup",
            ],
            timeout_seconds=45,
        )
        try:
            import json

            document = json.loads(output)
        except (TypeError, ValueError) as error:
            raise GitHubDeliveryError("invalid_github_response") from error
        if not isinstance(document, dict):
            raise GitHubDeliveryError("invalid_github_response")
        url = document.get("url")
        number = document.get("number")
        if not isinstance(url, str) or _PR_URL.fullmatch(url) is None:
            raise GitHubDeliveryError("invalid_github_response")
        if type(number) is not int or number <= 0:
            raise GitHubDeliveryError("invalid_github_response")
        is_draft = document.get("isDraft") is True
        raw_state = str(document.get("state", "OPEN")).upper()
        state = (
            DeliveryState.DRAFT
            if is_draft and raw_state == "OPEN"
            else DeliveryState.OPEN
            if raw_state == "OPEN"
            else DeliveryState.MERGED
            if raw_state == "MERGED"
            else DeliveryState.CLOSED
            if raw_state == "CLOSED"
            else DeliveryState.ERROR
        )
        raw_checks = document.get("statusCheckRollup")
        checks = (
            [self._check_document(item) for item in raw_checks if isinstance(item, Mapping)]
            if isinstance(raw_checks, list)
            else []
        )
        return {
            "prUrl": url,
            "prNumber": number,
            "state": state.value,
            "isDraft": is_draft,
            "headBranch": document.get("headRefName")
            if isinstance(document.get("headRefName"), str)
            else None,
            "baseBranch": document.get("baseRefName")
            if isinstance(document.get("baseRefName"), str)
            else None,
            "checks": checks,
        }

    @staticmethod
    def _check_document(item: Mapping[str, object]) -> dict[str, str | None]:
        name = item.get("name") or item.get("context") or "Unnamed check"
        raw_status = str(item.get("status") or "").upper()
        raw_conclusion = str(item.get("conclusion") or item.get("state") or "").upper()
        if raw_status in {"QUEUED", "PENDING", "EXPECTED", "WAITING", "REQUESTED"}:
            state = "queued"
        elif raw_status in {"IN_PROGRESS", "STARTED"}:
            state = "in_progress"
        else:
            state = {
                "SUCCESS": "success",
                "FAILURE": "failure",
                "ERROR": "failure",
                "NEUTRAL": "neutral",
                "SKIPPED": "skipped",
                "CANCELLED": "cancelled",
                "TIMED_OUT": "timed_out",
                "ACTION_REQUIRED": "action_required",
            }.get(raw_conclusion, "unknown")
        url = item.get("detailsUrl") or item.get("targetUrl")
        return {
            "name": str(name)[:500],
            "state": state,
            "url": url if isinstance(url, str) and url.startswith("https://") else None,
            "detail": str(item.get("workflowName") or item.get("description") or "")[:10_000],
        }

    def _git_call(
        self, cwd: Path, arguments: Sequence[str], *, timeout_seconds: int = 30
    ) -> subprocess.CompletedProcess[str]:
        if self._git is None:
            raise GitHubDeliveryError("git_unavailable")
        result = self._runner([self._git, *arguments], cwd, timeout_seconds)
        if result.returncode != 0:
            raise GitHubDeliveryError("git_command_failed")
        return result

    def _git_stdout(self, cwd: Path, arguments: Sequence[str]) -> str:
        return self._git_call(cwd, arguments).stdout

    def _gh_stdout(self, cwd: Path, arguments: Sequence[str], *, timeout_seconds: int) -> str:
        if self._gh is None:
            raise GitHubDeliveryError("github_cli_unavailable")
        result = self._runner([self._gh, *arguments], cwd, timeout_seconds)
        if result.returncode != 0:
            raise GitHubDeliveryError("github_command_failed")
        return result.stdout


__all__ = ["GitHubDeliveryError", "GitHubDeliveryService"]
