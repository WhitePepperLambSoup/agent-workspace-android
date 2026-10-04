"""Git Diff Review Service and Chunk-Level Revert/Acceptance.

Parses unified diffs into structured file diffs and hunks. Supports file-level
and chunk-level staging and reverting with both Git command execution and
pure-Python file buffer manipulation fallback.
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_HUNK_HEADER_PATTERN = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")
_MAX_GIT_OUTPUT_BYTES = 8 * 1024 * 1024
_MAX_CHECKPOINT_BYTES = 4 * 1024 * 1024
_MAX_CHECKPOINT_TOTAL_BYTES = 16 * 1024 * 1024
_MAX_CHECKPOINTS = 30


@dataclass(frozen=True, slots=True)
class UndoCheckpoint:
    checkpoint_id: str
    timestamp: str
    file_path: str
    kind: str  # "file" | "hunk"
    existed: bool
    original_content: bytes | None
    hunk_index: int | None = None
    post_revert_existed: bool | None = None
    post_revert_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class _GitCommandResult:
    returncode: int
    stdout: str
    stderr: str
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.truncated


@dataclass(frozen=True, slots=True)
class DiffLine:
    kind: str  # "add", "delete", "context", "marker"
    content: str
    old_lineno: int | None = None
    new_lineno: int | None = None


@dataclass(frozen=True, slots=True)
class DiffHunk:
    hunk_index: int
    file_path: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    header: str
    lines: tuple[DiffLine, ...]

    def to_patch(self, old_file_path: str | None = None) -> str:
        """Render this single hunk as a valid unified diff patch."""
        path_a = old_file_path or self.file_path
        path_b = self.file_path
        header_lines = [
            f"--- a/{path_a}",
            f"+++ b/{path_b}",
            f"@@ -{self.old_start},{self.old_count} +{self.new_start},{self.new_count} @@",
        ]
        body_lines: list[str] = []
        for line in self.lines:
            if line.kind == "add":
                body_lines.append("+" + line.content)
            elif line.kind == "delete":
                body_lines.append("-" + line.content)
            elif line.kind == "context":
                body_lines.append(" " + line.content)
            elif line.kind == "marker":
                body_lines.append(line.content)
        return "\n".join(header_lines + body_lines) + "\n"


@dataclass(frozen=True, slots=True)
class FileDiff:
    file_path: str
    status: str  # "modified", "added", "deleted", "untracked"
    hunks: tuple[DiffHunk, ...]
    old_path: str | None = None
    is_staged: bool = False
    is_binary: bool = False

    @property
    def additions(self) -> int:
        return sum(1 for hunk in self.hunks for line in hunk.lines if line.kind == "add")

    @property
    def deletions(self) -> int:
        return sum(1 for hunk in self.hunks for line in hunk.lines if line.kind == "delete")

    @property
    def summary(self) -> str:
        return f"+{self.additions} -{self.deletions}"


def parse_unified_diff(diff_text: str) -> list[FileDiff]:
    """Parse unified diff text into a list of FileDiff objects."""
    file_diffs: list[FileDiff] = []
    lines = diff_text.splitlines()
    i = 0
    total_lines = len(lines)

    while i < total_lines:
        line = lines[i]
        if line.startswith("diff --git "):
            try:
                parts = shlex.split(line)
            except ValueError:
                parts = line.split()
            file_a = parts[2][2:] if len(parts) > 2 and parts[2].startswith("a/") else ""
            file_b = parts[3][2:] if len(parts) > 3 and parts[3].startswith("b/") else file_a
            i += 1
            status = "modified"
            old_path = None
            hunks: list[DiffHunk] = []

            while i < total_lines and not lines[i].startswith("diff --git "):
                subline = lines[i]
                if subline.startswith("new file mode"):
                    status = "added"
                elif subline.startswith("deleted file mode"):
                    status = "deleted"
                elif subline.startswith("rename from "):
                    old_path = subline[12:].strip()
                elif subline.startswith("rename to "):
                    file_b = subline[10:].strip()
                elif subline.startswith("@@ "):
                    hunk, next_i = _parse_single_hunk(lines, i, file_b, len(hunks))
                    hunks.append(hunk)
                    i = next_i
                    continue
                i += 1

            file_diffs.append(
                FileDiff(
                    file_path=file_b or file_a,
                    status=status,
                    hunks=tuple(hunks),
                    old_path=old_path,
                )
            )
        elif line.startswith("--- ") and i + 1 < total_lines and lines[i + 1].startswith("+++ "):
            file_a = line[4:].strip().removeprefix("a/").removeprefix("b/")
            file_b = lines[i + 1][4:].strip().removeprefix("a/").removeprefix("b/")
            i += 2
            hunks = []
            while i < total_lines and not (
                lines[i].startswith("--- ") or lines[i].startswith("diff --git ")
            ):
                if lines[i].startswith("@@ "):
                    hunk, next_i = _parse_single_hunk(lines, i, file_b, len(hunks))
                    hunks.append(hunk)
                    i = next_i
                    continue
                i += 1
            file_diffs.append(
                FileDiff(
                    file_path=file_b or file_a,
                    status="modified",
                    hunks=tuple(hunks),
                )
            )
        else:
            i += 1

    return file_diffs


def _parse_single_hunk(
    lines: list[str], start_idx: int, file_path: str, hunk_index: int
) -> tuple[DiffHunk, int]:
    header_line = lines[start_idx]
    match = _HUNK_HEADER_PATTERN.match(header_line)
    if not match:
        return DiffHunk(hunk_index, file_path, 1, 0, 1, 0, header_line, ()), start_idx + 1

    old_start = int(match.group(1))
    old_count = int(match.group(2)) if match.group(2) is not None else 1
    new_start = int(match.group(3))
    new_count = int(match.group(4)) if match.group(4) is not None else 1

    diff_lines: list[DiffLine] = []
    i = start_idx + 1
    curr_old = old_start
    curr_new = new_start

    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git ") or line.startswith("@@ ") or line.startswith("--- "):
            break
        if line.startswith("+"):
            diff_lines.append(DiffLine("add", line[1:], old_lineno=None, new_lineno=curr_new))
            curr_new += 1
        elif line.startswith("-"):
            diff_lines.append(DiffLine("delete", line[1:], old_lineno=curr_old, new_lineno=None))
            curr_old += 1
        elif line.startswith(" "):
            diff_lines.append(
                DiffLine("context", line[1:], old_lineno=curr_old, new_lineno=curr_new)
            )
            curr_old += 1
            curr_new += 1
        elif line.startswith("\\ No newline at end of file"):
            diff_lines.append(DiffLine("marker", line))
        else:
            break
        i += 1

    return (
        DiffHunk(
            hunk_index=hunk_index,
            file_path=file_path,
            old_start=old_start,
            old_count=old_count,
            new_start=new_start,
            new_count=new_count,
            header=header_line,
            lines=tuple(diff_lines),
        ),
        i,
    )


class GitDiffReviewService:
    """Service to discover working tree changes and perform chunk/file reverts."""

    def __init__(self, workspace: Path | str) -> None:
        self.workspace = Path(workspace).resolve()
        self._checkpoints: dict[str, UndoCheckpoint] = {}
        self._checkpoint_order: list[str] = []
        self._checkpoint_bytes = 0
        self.last_checkpoint_id: str | None = None
        self.last_diff_truncated = False

    def is_git_repository(self) -> bool:
        """Check if the workspace itself is an initialized Git work tree.

        Git normally discovers a repository in a parent directory. A Gateway
        workspace can be a temporary directory below the application's source
        checkout, so accepting that implicit parent would expose unrelated
        files and make relative diff paths unsafe. Require Git's reported root
        to match the configured workspace exactly.
        """
        result = self._run_git_result(["rev-parse", "--show-toplevel"])
        if not result.ok:
            return False
        try:
            return Path(result.stdout.strip()).resolve() == self.workspace
        except (OSError, ValueError):
            return False

    def get_working_tree_diffs(
        self, max_files: int = 200, max_file_bytes: int = 256 * 1024
    ) -> list[FileDiff]:
        """Get all working tree diffs (both unstaged and untracked) with bounds."""
        return self._collect_diffs(
            ["diff", "--no-color", "--no-ext-diff"],
            max_files=max_files,
            max_file_bytes=max_file_bytes,
        )

    def get_review_diffs(
        self,
        base_sha: str,
        *,
        max_files: int = 500,
        max_file_bytes: int = 512 * 1024,
    ) -> list[FileDiff]:
        """Capture committed, staged, unstaged, and untracked changes from a fixed base."""
        normalized = base_sha.strip().lower()
        if len(normalized) != 40 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("base SHA must be a full hexadecimal revision")
        return self._collect_diffs(
            ["diff", "--no-color", "--no-ext-diff", normalized],
            max_files=max_files,
            max_file_bytes=max_file_bytes,
        )

    def _collect_diffs(
        self,
        arguments: list[str],
        *,
        max_files: int,
        max_file_bytes: int,
    ) -> list[FileDiff]:
        if not self.is_git_repository():
            return []

        diff_result = self._run_git_result(arguments)
        self.last_diff_truncated = diff_result.truncated
        if not diff_result.ok:
            return []
        diff_text = diff_result.stdout
        file_diffs = parse_unified_diff(diff_text)[:max_files]
        diff_paths = {d.file_path for d in file_diffs}

        # Check for untracked files
        status_result = self._run_git_result(["status", "--porcelain=v1", "-uall"])
        if not status_result.ok:
            return file_diffs
        status_out = status_result.stdout
        for status_line in status_out.splitlines():
            if len(file_diffs) >= max_files:
                break
            if len(status_line) < 4:
                continue
            code = status_line[:2]
            filepath = status_line[3:].strip().strip('"')
            if filepath in diff_paths:
                continue
            try:
                full_path = self._resolve_target(filepath)
            except ValueError:
                continue
            if code.strip() == "??" and full_path.is_file():
                try:
                    file_size = full_path.stat().st_size
                    # Check for binary file
                    with full_path.open("rb") as f:
                        sample = f.read(1024)
                    is_binary = b"\x00" in sample

                    if is_binary:
                        file_diffs.append(
                            FileDiff(
                                file_path=filepath,
                                status="untracked",
                                hunks=(),
                                is_binary=True,
                            )
                        )
                        continue

                    if file_size > max_file_bytes:
                        file_diffs.append(
                            FileDiff(
                                file_path=filepath,
                                status="untracked",
                                hunks=(),
                                is_binary=False,
                            )
                        )
                        continue

                    content = full_path.read_text(encoding="utf-8", errors="replace")
                    content_lines = content.splitlines()
                    lines = tuple(
                        DiffLine("add", line, old_lineno=None, new_lineno=idx + 1)
                        for idx, line in enumerate(content_lines)
                    )
                    hunk = DiffHunk(
                        hunk_index=0,
                        file_path=filepath,
                        old_start=0,
                        old_count=0,
                        new_start=1,
                        new_count=len(content_lines),
                        header=f"@@ -0,0 +1,{len(content_lines)} @@",
                        lines=lines,
                    )
                    file_diffs.append(
                        FileDiff(
                            file_path=filepath,
                            status="untracked",
                            hunks=(hunk,),
                        )
                    )
                except OSError:
                    continue

        return file_diffs

    def create_checkpoint(
        self,
        file_path: str,
        kind: str,
        hunk_index: int | None = None,
    ) -> UndoCheckpoint:
        target = self._resolve_target(file_path)
        existed = target.exists()
        original_content: bytes | None = None
        if existed:
            if not target.is_file():
                raise ValueError("checkpoint target is not a file")
            try:
                if target.stat().st_size > _MAX_CHECKPOINT_BYTES:
                    raise ValueError("checkpoint exceeds size limit")
                original_content = target.read_bytes()
            except OSError as error:
                raise ValueError("checkpoint could not read target") from error
        cp = UndoCheckpoint(
            checkpoint_id=uuid.uuid4().hex[:12],
            timestamp=datetime.now(UTC).isoformat(),
            file_path=file_path,
            kind=kind,
            existed=existed,
            original_content=original_content,
            hunk_index=hunk_index,
        )
        self._checkpoints[cp.checkpoint_id] = cp
        self._checkpoint_order.append(cp.checkpoint_id)
        self._checkpoint_bytes += len(original_content or b"")
        while (
            len(self._checkpoint_order) > _MAX_CHECKPOINTS
            or self._checkpoint_bytes > _MAX_CHECKPOINT_TOTAL_BYTES
        ):
            stale_id = self._checkpoint_order.pop(0)
            stale = self._checkpoints.pop(stale_id, None)
            if stale is not None:
                self._checkpoint_bytes -= len(stale.original_content or b"")
        self.last_checkpoint_id = cp.checkpoint_id
        return cp

    def undo_checkpoint(self, checkpoint_id: str) -> bool:
        """Undo a previously executed revert checkpoint, restoring original content or unlinking."""
        cp = self._checkpoints.get(checkpoint_id)
        if cp is None:
            return False
        target = self._resolve_target(cp.file_path)
        try:
            if cp.post_revert_existed is not None:
                current_exists = target.is_file()
                if current_exists != cp.post_revert_existed:
                    return False
                if current_exists and self._file_digest(target) != cp.post_revert_sha256:
                    return False
            if not cp.existed:
                if target.exists():
                    target.unlink()
                self._discard_checkpoint(checkpoint_id)
                return True
            if cp.original_content is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(cp.original_content)
                self._discard_checkpoint(checkpoint_id)
                return True
            return False
        except OSError:
            return False

    def get_checkpoint(self, checkpoint_id: str) -> UndoCheckpoint | None:
        return self._checkpoints.get(checkpoint_id)

    def revert_file(self, file_path: str) -> bool:
        """Revert working tree changes for an entire file."""
        target = self._resolve_target(file_path)
        checkpoint = self.create_checkpoint(file_path, kind="file")
        status_result = self._run_git_result(["status", "--porcelain=v1", "--", file_path])
        if not status_result.ok:
            self._discard_checkpoint(checkpoint.checkpoint_id)
            return False
        if status_result.stdout.startswith("??") and target.is_file():
            try:
                target.unlink()
            except OSError:
                self._discard_checkpoint(checkpoint.checkpoint_id)
                return False
            self._arm_checkpoint(checkpoint.checkpoint_id, target)
            return True

        # The diff shown by this service is index -> worktree. Restore the
        # worktree from the index so an unrelated staged version is preserved.
        result = self._run_git_result(["checkout", "--", file_path])
        if not result.ok:
            self._discard_checkpoint(checkpoint.checkpoint_id)
            return False
        self._arm_checkpoint(checkpoint.checkpoint_id, target)
        return True

    def revert_hunk(self, file_path: str, hunk: DiffHunk) -> bool:
        """Revert a single hunk in the file."""
        target = self._resolve_target(file_path)
        if not target.exists():
            return False

        checkpoint = self.create_checkpoint(file_path, kind="hunk", hunk_index=hunk.hunk_index)
        patch = hunk.to_patch()
        git_cmd = shutil.which("git")
        if git_cmd:
            proc = subprocess.run(
                [git_cmd, "apply", "--reverse", "--unidiff-zero"],
                cwd=self.workspace,
                input=patch,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            )
            if proc.returncode == 0:
                self._arm_checkpoint(checkpoint.checkpoint_id, target)
                return True

        success = self._revert_hunk_pure_python(target, hunk)
        if success:
            self._arm_checkpoint(checkpoint.checkpoint_id, target)
        else:
            self._discard_checkpoint(checkpoint.checkpoint_id)
        return success

    def stage_file(self, file_path: str) -> bool:
        """Stage an entire file to git index."""
        self._resolve_target(file_path)
        return self._run_git_result(["add", "--", file_path]).ok

    def stage_hunk(self, file_path: str, hunk: DiffHunk) -> bool:
        """Stage a single hunk to git index."""
        patch = hunk.to_patch()
        git_cmd = shutil.which("git")
        if not git_cmd:
            return False
        proc = subprocess.run(
            [git_cmd, "apply", "--cached", "--unidiff-zero"],
            cwd=self.workspace,
            input=patch,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        return proc.returncode == 0

    def _revert_hunk_pure_python(self, target: Path, hunk: DiffHunk) -> bool:
        """Pure-Python fallback to revert hunk changes in file lines at hunk position."""
        try:
            content = target.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            return False
        lines = content.splitlines(keepends=True)
        raw_lines = [line.rstrip("\r\n") for line in lines]

        new_hunk_lines = [item.content for item in hunk.lines if item.kind in ("context", "add")]
        old_hunk_lines = [item.content for item in hunk.lines if item.kind in ("context", "delete")]

        if not new_hunk_lines:
            return False

        hunk_len = len(new_hunk_lines)
        exact_start = max(0, hunk.new_start - 1)

        # Check exact position first, then bounded ±3 lines fuzz
        candidate_starts = [exact_start]
        for offset in (1, -1, 2, -2, 3, -3):
            pos = exact_start + offset
            if 0 <= pos <= len(lines) - hunk_len and pos not in candidate_starts:
                candidate_starts.append(pos)

        for pos in candidate_starts:
            if raw_lines[pos : pos + hunk_len] == new_hunk_lines:
                newline = "\r\n" if "\r\n" in content else "\n"
                matched_last = lines[pos + hunk_len - 1]
                matched_had_terminator = matched_last.endswith(("\n", "\r"))
                replacement = [
                    item
                    + (newline if index < len(old_hunk_lines) - 1 or matched_had_terminator else "")
                    for index, item in enumerate(old_hunk_lines)
                ]
                new_file_lines = lines[:pos] + replacement + lines[pos + hunk_len :]
                target.write_bytes("".join(new_file_lines).encode("utf-8"))
                return True

        return False

    def _resolve_target(self, file_path: str) -> Path:
        if not isinstance(file_path, str) or not file_path or "\x00" in file_path:
            raise ValueError("invalid workspace path")
        candidate = Path(file_path)
        if candidate.is_absolute():
            raise ValueError("path is outside workspace")
        target = (self.workspace / candidate).resolve()
        if target == self.workspace or not target.is_relative_to(self.workspace):
            raise ValueError("path is outside workspace")
        return target

    @staticmethod
    def _file_digest(target: Path) -> str:
        digest = hashlib.sha256()
        with target.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def _arm_checkpoint(self, checkpoint_id: str, target: Path) -> None:
        checkpoint = self._checkpoints.get(checkpoint_id)
        if checkpoint is None:
            return
        exists = target.is_file()
        armed = UndoCheckpoint(
            checkpoint_id=checkpoint.checkpoint_id,
            timestamp=checkpoint.timestamp,
            file_path=checkpoint.file_path,
            kind=checkpoint.kind,
            existed=checkpoint.existed,
            original_content=checkpoint.original_content,
            hunk_index=checkpoint.hunk_index,
            post_revert_existed=exists,
            post_revert_sha256=self._file_digest(target) if exists else None,
        )
        self._checkpoints[checkpoint_id] = armed

    def _discard_checkpoint(self, checkpoint_id: str) -> None:
        checkpoint = self._checkpoints.pop(checkpoint_id, None)
        if checkpoint is not None:
            self._checkpoint_bytes -= len(checkpoint.original_content or b"")
        if checkpoint_id in self._checkpoint_order:
            self._checkpoint_order.remove(checkpoint_id)
        if self.last_checkpoint_id == checkpoint_id:
            self.last_checkpoint_id = self._checkpoint_order[-1] if self._checkpoint_order else None

    def _run_git(self, args: list[str]) -> str:
        result = self._run_git_result(args)
        return result.stdout if result.ok else ""

    def _run_git_result(self, args: list[str]) -> _GitCommandResult:
        git = shutil.which("git")
        if not git:
            return _GitCommandResult(127, "", "git executable unavailable")
        try:
            env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}
            with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
                proc = subprocess.run(
                    [git, "-c", "core.quotePath=false", *args],
                    cwd=self.workspace,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    timeout=15,
                    env=env,
                )
                stdout_size = stdout_file.tell()
                stderr_size = stderr_file.tell()
                stdout_file.seek(0)
                stderr_file.seek(0)
                stdout = stdout_file.read(_MAX_GIT_OUTPUT_BYTES).decode("utf-8", errors="replace")
                stderr = stderr_file.read(_MAX_GIT_OUTPUT_BYTES).decode("utf-8", errors="replace")
                return _GitCommandResult(
                    proc.returncode,
                    stdout,
                    stderr,
                    stdout_size > _MAX_GIT_OUTPUT_BYTES or stderr_size > _MAX_GIT_OUTPUT_BYTES,
                )
        except subprocess.TimeoutExpired:
            return _GitCommandResult(124, "", "git command timed out")
        except OSError:
            return _GitCommandResult(126, "", "git command failed")


__all__ = [
    "DiffHunk",
    "DiffLine",
    "FileDiff",
    "GitDiffReviewService",
    "parse_unified_diff",
]
