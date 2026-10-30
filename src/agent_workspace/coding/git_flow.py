"""Git for the Changes page's Git tab: the branch and how it stands against its upstream, a new
branch for a task, a commit message the model writes in the repository's own style, merge
conflicts, the CI runs of the branch with the log of what failed, and the open issues (the last
two through the GitHub CLI)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unicodedata
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from agent_workspace.config import ProviderConfig

from .model_call import ModelCallError, ask_model

GIT_SECONDS = 20
GH_SECONDS = 45
LOG_SECONDS = 90
MESSAGE_SECONDS = 90
MAX_DIFF_CHARS = 40_000
MAX_NEW_FILE_LINES = 60
LOG_LINES = 300
MAX_LOG_LINE = 500
MAX_PATHS = 200

_LANGUAGES = {
    "zh-CN": "Simplified Chinese",
    "zh-TW": "Traditional Chinese",
    "ja-JP": "Japanese",
    "en-US": "English",
}
_CONFLICT_START = re.compile(r"^<{7}(?: |$)", re.MULTILINE)
_LOG_STAMP = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ?")
_RUN_URL = re.compile(r"/actions/runs/(\d+)")

Runner = Callable[[Sequence[str], Path, float], subprocess.CompletedProcess[str]]


class GitFlowError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def _environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GH_PAGER": "cat",
            "GH_PROMPT_DISABLED": "1",
            # A merge or rebase continued from here takes the message git prepared.
            "GIT_EDITOR": "true",
            "NO_COLOR": "1",
        }
    )
    return environment


def _default_runner(
    argv: Sequence[str], cwd: Path, seconds: float
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(argv),
            cwd=cwd,
            env=_environment(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=seconds,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        raise GitFlowError("git_timeout") from None
    except OSError:
        raise GitFlowError("git_unavailable") from None


def slug(text: str, limit: int = 40) -> str:
    """Words of a title for a branch name (letters other than ASCII are left out)."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    words = re.findall(r"[a-z0-9]+", plain)
    joined = ""
    for word in words:
        candidate = f"{joined}-{word}" if joined else word
        if len(candidate) > limit:
            break
        joined = candidate
    return joined


def suggest_branch(title: str, issue: int | None = None) -> str:
    words = slug(title)
    if issue is not None:
        return f"issue-{issue}-{words}" if words else f"issue-{issue}"
    return f"task/{words}" if words else "task/change"


class GitFlow:
    """The git and gh commands of one folder."""

    def __init__(
        self,
        root: Path,
        *,
        runner: Runner = _default_runner,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self.root = root
        self._run = runner
        self._git = which("git")
        self._gh = which("gh")

    # -- running

    def git(self, *arguments: str, seconds: float = GIT_SECONDS, check: bool = True) -> str:
        if self._git is None:
            raise GitFlowError("git_unavailable")
        result = self._run([self._git, *arguments], self.root, seconds)
        if check and result.returncode != 0:
            raise GitFlowError(
                "git_command_failed", (result.stderr or result.stdout).strip()[-800:]
            )
        return result.stdout if result.returncode == 0 else ""

    def _git_ok(self, *arguments: str) -> bool:
        if self._git is None:
            return False
        return self._run([self._git, *arguments], self.root, GIT_SECONDS).returncode == 0

    def gh(self, *arguments: str, seconds: float = GH_SECONDS) -> str:
        if self._gh is None:
            raise GitFlowError("github_cli_unavailable")
        result = self._run([self._gh, *arguments], self.root, seconds)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            code = (
                "github_not_signed_in"
                if "gh auth login" in detail or "not logged" in detail.lower()
                else "github_command_failed"
            )
            raise GitFlowError(code, detail[-800:])
        return result.stdout

    def _gh_json(self, *arguments: str) -> Any:
        try:
            return json.loads(self.gh(*arguments))
        except ValueError:
            raise GitFlowError("invalid_github_response") from None

    # -- where the folder stands

    # Each git command costs a fifth of a second or more on Windows: the status is three.

    def _git_dirs(self) -> tuple[Path, Path]:
        """The repository's own directory (a worktree's) and the one shared by its worktrees."""
        lines = self.git(
            "rev-parse", "--absolute-git-dir", "--git-common-dir", check=False
        ).splitlines()
        if len(lines) < 2:
            raise GitFlowError("not_git_repository")
        common = Path(lines[1])
        return Path(lines[0]), common if common.is_absolute() else self.root / common

    def _require_repository(self) -> None:
        self._git_dirs()

    def operation(self, git_dir: Path | None = None) -> str | None:
        """The merge, rebase or cherry-pick waiting to be finished, if any."""
        git_dir = git_dir or self._git_dirs()[0]
        if (git_dir / "rebase-merge").is_dir() or (git_dir / "rebase-apply").is_dir():
            return "rebase"
        if (git_dir / "MERGE_HEAD").is_file():
            return "merge"
        if (git_dir / "CHERRY_PICK_HEAD").is_file():
            return "cherry-pick"
        return None

    def _with_blocks(self, paths: Sequence[str]) -> list[dict[str, object]]:
        found: list[dict[str, object]] = []
        for path in paths[:MAX_PATHS]:
            try:
                text = (self.root / path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            found.append({"path": path, "blocks": len(_CONFLICT_START.findall(text))})
        return found

    def conflicts(self) -> list[dict[str, object]]:
        output = self.git("diff", "--name-only", "-z", "--diff-filter=U")
        return self._with_blocks([path for path in output.split("\0") if path])

    def status(self) -> dict[str, object]:
        git_dir, common = self._git_dirs()
        branch: str | None = None
        head: str | None = None
        upstream: str | None = None
        ahead = behind = 0
        conflicted: list[str] = []
        entries = iter(
            self.git("status", "--porcelain=v2", "--branch", "--untracked-files=no", "-z").split(
                "\0"
            )
        )
        for entry in entries:
            if entry.startswith("# branch.oid "):
                oid = entry.removeprefix("# branch.oid ")
                head = None if oid == "(initial)" else oid[:7]
            elif entry.startswith("# branch.head "):
                name = entry.removeprefix("# branch.head ")
                branch = None if name == "(detached)" else name
            elif entry.startswith("# branch.upstream "):
                upstream = entry.removeprefix("# branch.upstream ")
            elif entry.startswith("# branch.ab "):
                counts = entry.split()
                ahead, behind = int(counts[2].lstrip("+")), int(counts[3].lstrip("-"))
            elif entry.startswith("2 "):
                next(entries, None)  # a rename: its old path follows as an entry of its own
            elif entry.startswith("u "):
                conflicted.append(entry.split(" ", 10)[10])
        default: str | None = None
        heads: list[str] = []
        for line in self.git(
            "for-each-ref",
            "--sort=-committerdate",
            "--format=%(refname)%09%(symref)",
            "refs/heads",
            "refs/remotes/origin/HEAD",
            check=False,
        ).splitlines():
            ref, _, target = line.partition("\t")
            if ref == "refs/remotes/origin/HEAD":
                default = target.removeprefix("refs/remotes/origin/") or None
            elif ref.startswith("refs/heads/"):
                heads.append(ref.removeprefix("refs/heads/"))
        if default is None:
            default = next((name for name in ("main", "master") if name in heads), None)
        try:
            config = (common / "config").read_text(encoding="utf-8", errors="replace")
        except OSError:
            config = ""
        origin = re.search(r'\[remote "origin"\][^\[]*?\burl\s*=\s*(\S+)', config)
        return {
            "branch": branch,
            "head": head,
            "detached": branch is None,
            "defaultBranch": default,
            "upstream": upstream,
            "ahead": ahead,
            "behind": behind,
            "operation": self.operation(git_dir),
            "conflicts": self._with_blocks(conflicted),
            "github": bool(origin and "github.com" in origin.group(1)),
            "githubCli": self._gh is not None,
            "recentBranches": [name for name in heads if name != branch][:8],
        }

    # -- branches

    def _check_branch_name(self, name: str) -> str:
        name = name.strip()
        if not name or not self._git_ok("check-ref-format", "--branch", name):
            raise GitFlowError("invalid_branch_name")
        return name

    def create_branch(self, name: str) -> dict[str, object]:
        """A new branch from where the folder is, taking the uncommitted changes along."""
        self._require_repository()
        name = self._check_branch_name(name)
        if self._git_ok("show-ref", "--verify", "--quiet", f"refs/heads/{name}"):
            raise GitFlowError("branch_exists")
        self.git("switch", "-c", name)
        return self.status()

    def switch_branch(self, name: str) -> dict[str, object]:
        self._require_repository()
        name = self._check_branch_name(name)
        if not self._git_ok("show-ref", "--verify", "--quiet", f"refs/heads/{name}"):
            raise GitFlowError("branch_missing")
        try:
            self.git("switch", name)
        except GitFlowError as error:
            raise GitFlowError("switch_blocked", error.detail) from None
        return self.status()

    # -- conflicts

    def _conflicted(self, path: str) -> str:
        names = {str(item["path"]) for item in self.conflicts()}
        if path not in names:
            raise GitFlowError("not_conflicted")
        return path

    def take_side(self, path: str, side: str) -> dict[str, object]:
        """The whole file as one side had it: "ours" (this branch) or "theirs"."""
        if side not in {"ours", "theirs"}:
            raise GitFlowError("invalid_side")
        path = self._conflicted(path)
        self.git("checkout", f"--{side}", "--", path)
        self.git("add", "--", path)
        return self.status()

    def mark_resolved(self, path: str) -> dict[str, object]:
        path = self._conflicted(path)
        try:
            text = (self.root / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if _CONFLICT_START.search(text):
            raise GitFlowError("conflict_markers_left")
        self.git("add", "--", path)
        return self.status()

    def finish(self, action: str) -> dict[str, object]:
        """Continue or abort the merge, rebase or cherry-pick in progress."""
        if action not in {"continue", "abort"}:
            raise GitFlowError("invalid_action")
        operation = self.operation()
        if operation is None:
            raise GitFlowError("nothing_in_progress")
        if action == "continue" and self.conflicts():
            raise GitFlowError("conflicts_left")
        try:
            self.git(operation, f"--{action}", seconds=60)
        except GitFlowError as error:
            raise GitFlowError("finish_failed", error.detail) from None
        return self.status()

    # -- the commit message

    def change_for_message(self, paths: Sequence[str]) -> str:
        """The selected files' change against the last commit, new files with their start."""
        self._require_repository()
        chosen = [path for path in paths if isinstance(path, str) and path.strip()][:MAX_PATHS]
        if not chosen:
            raise GitFlowError("invalid_selection")
        has_head = self._git_ok("rev-parse", "--verify", "--quiet", "HEAD")
        base = ["diff", "HEAD"] if has_head else ["diff", "--cached"]
        parts = [
            self.git(*base, "--stat", "--", *chosen, check=False),
            self.git(*base, "--", *chosen, check=False),
        ]
        new_files = self.git(
            "ls-files", "--others", "--exclude-standard", "--", *chosen, check=False
        ).splitlines()
        for path in new_files[:20]:
            try:
                lines = (self.root / path).read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                parts.append(f"new file: {path} (binary or unreadable)")
                continue
            shown = "\n".join(lines[:MAX_NEW_FILE_LINES])
            more = (
                f"\n… {len(lines) - MAX_NEW_FILE_LINES} more lines"
                if len(lines) > MAX_NEW_FILE_LINES
                else ""
            )
            parts.append(f"new file: {path}\n{shown}{more}")
        text = "\n".join(part for part in parts if part.strip())
        if not text.strip():
            raise GitFlowError("nothing_to_commit")
        return text if len(text) <= MAX_DIFF_CHARS else text[:MAX_DIFF_CHARS] + "\n… (cut)"

    def recent_subjects(self) -> list[str]:
        return [
            line.strip()
            for line in self.git("log", "-n", "15", "--format=%s", check=False).splitlines()
            if line.strip()
        ]

    def write_message(
        self, config: ProviderConfig, paths: Sequence[str], language: str = "en-US"
    ) -> dict[str, str]:
        change = self.change_for_message(paths)
        subjects = self.recent_subjects()
        style = (
            "Follow the style of the repository's recent commit subjects below: their prefix "
            "convention, language, tense and length."
            if subjects
            else f"Write in {_LANGUAGES.get(language, 'English')}, in the imperative."
        )
        system = (
            "You write the git commit message for a change. "
            f"{style} The subject is at most 72 characters with no period at the end. The "
            "body says what changed and why in a few short lines wrapped at 72 characters, "
            "and is empty when the subject says it all. Do not mention who or what wrote the "
            "change and add no trailers. Answer with JSON only: "
            '{"title": "...", "body": "..."}'
        )
        user = change
        if subjects:
            user = "Recent commit subjects:\n" + "\n".join(subjects) + "\n\nThe change:\n" + change
        try:
            answer = ask_model(
                config,
                system,
                user,
                max_output_tokens=1024,
                seconds=MESSAGE_SECONDS,
                temperature=0.2,
                error_prefix="message",
            )
        except ModelCallError as error:
            raise GitFlowError(str(error)) from None
        return parse_message(answer)

    # -- CI and issues (GitHub)

    def ci_runs(self, branch: str | None = None) -> list[dict[str, object]]:
        branch = branch or self.git("symbolic-ref", "--short", "-q", "HEAD", check=False).strip()
        if not branch:
            return []
        runs = self._gh_json(
            "run",
            "list",
            "--branch",
            branch,
            "--limit",
            "8",
            "--json",
            "databaseId,displayTitle,status,conclusion,workflowName,url,headSha,createdAt,event",
        )
        return [
            {
                "id": item.get("databaseId"),
                "title": str(item.get("displayTitle") or "")[:300],
                "workflow": str(item.get("workflowName") or "")[:200],
                "status": str(item.get("status") or "").lower(),
                "conclusion": str(item.get("conclusion") or "").lower() or None,
                "url": item.get("url") if str(item.get("url", "")).startswith("https://") else None,
                "headSha": str(item.get("headSha") or "")[:40],
                "createdAt": item.get("createdAt"),
                "event": item.get("event"),
            }
            for item in (runs if isinstance(runs, list) else [])
            if isinstance(item, dict) and type(item.get("databaseId")) is int
        ]

    def ci_log(self, run: int | str) -> dict[str, object]:
        """The end of the failed steps' log of a run (a run id or its Actions URL)."""
        run_id = run if isinstance(run, int) else _run_id(run)
        if run_id is None or run_id <= 0:
            raise GitFlowError("invalid_run")
        raw = self.gh("run", "view", str(run_id), "--log-failed", seconds=LOG_SECONDS)
        lines: list[str] = []
        for line in raw.splitlines():
            _job, _, rest = line.partition("\t")
            step, _, text = rest.partition("\t")
            text = _LOG_STAMP.sub("", text) if rest else line
            prefix = f"{step.strip()} | " if rest and step.strip() else ""
            lines.append(f"{prefix}{text}"[:MAX_LOG_LINE])
        return {
            "runId": run_id,
            "log": "\n".join(lines[-LOG_LINES:]),
            "truncated": len(lines) > LOG_LINES,
        }

    def issues(self, search: str = "") -> list[dict[str, object]]:
        arguments = [
            "issue",
            "list",
            "--state",
            "open",
            "--limit",
            "30",
            "--json",
            "number,title,labels,url,updatedAt,author",
        ]
        if search.strip():
            arguments += ["--search", search.strip()[:200]]
        found = self._gh_json(*arguments)
        return [
            {
                "number": item.get("number"),
                "title": str(item.get("title") or "")[:300],
                "url": item.get("url"),
                "labels": [
                    str(label.get("name"))[:60]
                    for label in item.get("labels") or []
                    if isinstance(label, dict) and label.get("name")
                ][:6],
                "author": str((item.get("author") or {}).get("login") or "")[:80],
                "updatedAt": item.get("updatedAt"),
            }
            for item in (found if isinstance(found, list) else [])
            if isinstance(item, dict) and type(item.get("number")) is int
        ]

    def issue(self, number: int) -> dict[str, object]:
        if type(number) is not int or number <= 0:
            raise GitFlowError("invalid_issue")
        item = self._gh_json(
            "issue", "view", str(number), "--json", "number,title,body,url,labels,comments"
        )
        if not isinstance(item, dict):
            raise GitFlowError("invalid_github_response")
        comments = [
            {
                "author": str((comment.get("author") or {}).get("login") or ""),
                "body": str(comment.get("body") or "")[:2000],
            }
            for comment in (item.get("comments") or [])[-10:]
            if isinstance(comment, dict)
        ]
        return {
            "number": number,
            "title": str(item.get("title") or "")[:300],
            "url": item.get("url"),
            "body": str(item.get("body") or "")[:8000],
            "labels": [
                str(label.get("name"))
                for label in item.get("labels") or []
                if isinstance(label, dict) and label.get("name")
            ],
            "comments": comments,
            "branch": suggest_branch(str(item.get("title") or ""), number),
        }


def _run_id(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    match = _RUN_URL.search(value)
    return int(match.group(1)) if match else None


def parse_message(answer: str) -> dict[str, str]:
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", answer.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    try:
        document = json.loads(cleaned[start : end + 1]) if start >= 0 and end > start else None
    except ValueError:
        document = None
    if isinstance(document, dict):
        title = " ".join(str(document.get("title") or "").split())
        body = str(document.get("body") or "").strip()
    else:
        # A model that answered in plain text: its first line is the subject.
        first, _, rest = cleaned.partition("\n")
        title, body = " ".join(first.split()), rest.strip()
    # Trailers are the user's to add, never the model's.
    body = "\n".join(
        line for line in body.splitlines() if not re.match(r"^[A-Za-z-]+-by:", line.strip())
    ).strip()
    if not title:
        raise GitFlowError("message_unreadable")
    return {"title": title[:200], "body": body[:4000]}


__all__ = ["GitFlow", "GitFlowError", "parse_message", "slug", "suggest_branch"]
