"""Safe Git worktree and stash operations.

Every command runs with an explicit bounded timeout, a clean environment, and
no optional locks. Paths passed to worktree add/remove are resolved and must
remain inside the requested worktrees root so a stale argument cannot remove
an unrelated checkout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_TIMEOUT_SECONDS = 20
_SAFE_ENVIRONMENT = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_PAGER": "cat",
    "NO_COLOR": "1",
}


class GitOpsError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GitWorktreeInfo:
    path: str
    head: str
    branch: str
    detached: bool

    def to_document(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "head": self.head,
            "branch": self.branch,
            "detached": self.detached,
        }


@dataclass(frozen=True, slots=True)
class GitStashInfo:
    reference: str
    branch: str
    message: str

    def to_document(self) -> dict[str, Any]:
        return {
            "reference": self.reference,
            "branch": self.branch,
            "message": self.message,
        }


def _environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(_SAFE_ENVIRONMENT)
    return environment


def _git(
    repository: Path, arguments: list[str], *, timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git")
    if git is None:
        raise GitOpsError("Git executable is unavailable")
    try:
        return subprocess.run(
            [git, *arguments],
            cwd=repository,
            env=_environment(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise GitOpsError(f"Git operation timed out after {timeout_seconds}s") from exc
    except OSError as exc:
        raise GitOpsError(f"cannot run Git: {exc}") from exc


def _require_success(completed: subprocess.CompletedProcess[str], operation: str) -> None:
    if completed.returncode != 0:
        detail = completed.stderr.strip()[:1000]
        raise GitOpsError(
            f"Git {operation} failed: {detail or f'exit code {completed.returncode}'}"
        )


def _ensure_repository(repository: str | Path) -> Path:
    root = Path(repository).expanduser().resolve()
    if not root.is_dir():
        raise GitOpsError("Git repository is not a directory")
    result = _git(root, ["rev-parse", "--git-dir"])
    _require_success(result, "repository discovery")
    return root


def _worktrees_root(repository: Path) -> Path:
    return repository / ".worktrees"


def _validate_worktree_path(_root: Path, worktrees_root: Path, path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = worktrees_root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(worktrees_root)
    except ValueError as exc:
        raise GitOpsError(f"worktree path must live under {worktrees_root}") from exc
    return resolved


def git_worktree_add(
    repository: str | Path,
    path: str | Path,
    *,
    branch: str | None = None,
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
) -> GitWorktreeInfo:
    root = _ensure_repository(repository)
    worktrees_root = _worktrees_root(root)
    target = _validate_worktree_path(root, worktrees_root, path)
    if target.exists():
        raise GitOpsError(f"worktree path already exists: {target}")
    worktrees_root.mkdir(parents=True, exist_ok=True)
    arguments = ["worktree", "add"]
    if branch:
        arguments.extend(["-b", branch])
    arguments.append(str(target))
    result = _git(root, arguments, timeout_seconds=timeout_seconds)
    _require_success(result, "worktree add")
    return _info_from_path(root, target)


def git_worktree_list(repository: str | Path) -> tuple[GitWorktreeInfo, ...]:
    root = _ensure_repository(repository)
    result = _git(root, ["worktree", "list", "--porcelain"])
    _require_success(result, "worktree list")
    entries: list[GitWorktreeInfo] = []
    current_path = ""
    current_head = ""
    current_branch = ""
    detached = False
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree ") :]
            current_head = ""
            current_branch = ""
            detached = False
        elif line.startswith("HEAD "):
            current_head = line[len("HEAD ") :]
        elif line.startswith("branch "):
            current_branch = line[len("branch ") :]
            if current_branch.startswith("refs/heads/"):
                current_branch = current_branch[len("refs/heads/") :]
        elif line.startswith("detached"):
            detached = True
        elif line == "" and current_path:
            entries.append(
                GitWorktreeInfo(
                    path=current_path,
                    head=current_head,
                    branch=current_branch,
                    detached=detached,
                )
            )
            current_path = ""
    if current_path:
        entries.append(
            GitWorktreeInfo(
                path=current_path,
                head=current_head,
                branch=current_branch,
                detached=detached,
            )
        )
    return tuple(entries)


def _info_from_path(repository: Path, path: Path) -> GitWorktreeInfo:
    for info in git_worktree_list(repository):
        if Path(info.path).resolve() == path:
            return info
    raise GitOpsError(f"worktree metadata is missing for {path}")


def git_worktree_remove(
    repository: str | Path,
    path: str | Path,
    *,
    force: bool = False,
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
) -> bool:
    root = _ensure_repository(repository)
    worktrees_root = _worktrees_root(root)
    target = _validate_worktree_path(root, worktrees_root, path)
    existing = _info_from_path(root, target)
    arguments = ["worktree", "remove"]
    if force:
        arguments.append("--force")
    arguments.append(str(Path(existing.path).resolve()))
    result = _git(root, arguments, timeout_seconds=timeout_seconds)
    _require_success(result, "worktree remove")
    return True


def git_head_sha(repository: str | Path) -> str:
    root = _ensure_repository(repository)
    result = _git(root, ["rev-parse", "HEAD"])
    _require_success(result, "HEAD discovery")
    sha = result.stdout.strip()
    if len(sha) != 40 or any(character not in "0123456789abcdef" for character in sha.lower()):
        raise GitOpsError("Git returned an invalid HEAD revision")
    return sha


def git_worktree_is_clean(repository: str | Path) -> bool:
    root = _ensure_repository(repository)
    result = _git(root, ["status", "--porcelain=v1", "-uall"])
    _require_success(result, "worktree status")
    return result.stdout.strip() == ""


def git_stash_push(
    repository: str | Path,
    message: str = "",
    *,
    include_untracked: bool = False,
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
) -> str:
    root = _ensure_repository(repository)
    arguments = ["stash", "push"]
    if include_untracked:
        arguments.append("--include-untracked")
    if message:
        arguments.extend(["-m", message])
    result = _git(root, arguments, timeout_seconds=timeout_seconds)
    _require_success(result, "stash push")
    return result.stdout.strip()


def git_stash_list(repository: str | Path) -> tuple[GitStashInfo, ...]:
    root = _ensure_repository(repository)
    result = _git(root, ["stash", "list", "--format=%gd%x00%gs"])
    _require_success(result, "stash list")
    entries: list[GitStashInfo] = []
    for line in result.stdout.splitlines():
        if "\x00" not in line:
            continue
        reference, message = line.split("\x00", 1)
        branch = ""
        if message.startswith("On ") and ":" in message:
            branch = message.split(":", 1)[0][len("On ") :]
        entries.append(GitStashInfo(reference=reference, branch=branch, message=message))
    return tuple(entries)


def git_stash_pop(
    repository: str | Path,
    reference: str = "stash@{0}",
    *,
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
) -> str:
    root = _ensure_repository(repository)
    if not reference.startswith("stash@{"):
        raise GitOpsError("stash reference must look like stash@{n}")
    result = _git(root, ["stash", "pop", reference], timeout_seconds=timeout_seconds)
    _require_success(result, "stash pop")
    return result.stdout.strip()


__all__ = [
    "GitOpsError",
    "GitStashInfo",
    "GitWorktreeInfo",
    "git_head_sha",
    "git_stash_list",
    "git_stash_pop",
    "git_stash_push",
    "git_worktree_add",
    "git_worktree_is_clean",
    "git_worktree_list",
    "git_worktree_remove",
]
