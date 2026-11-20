from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec

from .base import (
    ConcurrentModificationError,
    ToolArgumentError,
    ToolError,
    json_result,
    optional_int,
)
from .command import _required_executable_sha256, _resolve_executable, _run_command_sync
from .paths import PathOutsideWorkspaceError, StrPath, WorkspacePaths
from .process_worker import run_in_process

_MAX_GIT_PATHS = 128
_MAX_DIFF_BYTES = 128 * 1024


def _git_executable(workspace: Path) -> Path:
    path_value = os.environ.get("PATH", "")
    suffixes = ("git.exe", "git.com") if os.name == "nt" else ("git",)
    for raw_directory in path_value.split(os.pathsep):
        normalized_directory = raw_directory.strip().strip('"')
        directory = Path(normalized_directory)
        if not normalized_directory or not directory.is_absolute():
            continue
        for suffix in suffixes:
            try:
                candidate = _resolve_executable(str(directory / suffix))
            except (ToolArgumentError, ToolError):
                continue
            if candidate.is_relative_to(workspace):
                continue
            return candidate
    raise ToolError("Git executable is unavailable outside the workspace")


def _git_arguments(*arguments: str, read_only: bool = True) -> list[str]:
    result = [
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "diff.external=",
        "-c",
        "pager.status=false",
        "-c",
        "pager.diff=false",
    ]
    if read_only:
        result.insert(0, "--no-optional-locks")
    result.extend(arguments)
    return result


def _invoke_git(
    workspace: str,
    repository: str,
    arguments: list[str],
    executable: str,
    expected_executable_sha256: str,
    *,
    timeout_seconds: int = 60,
    index_file: Path | None = None,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    raw = _run_command_sync(
        workspace,
        "direct",
        executable,
        arguments,
        None,
        repository,
        timeout_seconds,
        {
            **({"GIT_INDEX_FILE": str(index_file)} if index_file is not None else {}),
            # Prevent Git from walking above the selected workspace. A packaged
            # project often lives inside the source checkout, which otherwise
            # makes Git discover the outer repository and leak a path escape.
            # The ceiling is the workspace's parent: Git never enters a ceiling
            # directory, so the workspace itself would hide a repository at its
            # root from a subfolder.
            "GIT_CEILING_DIRECTORIES": str(Path(workspace).parent),
            **(environment or {}),
        },
        expected_executable_sha256,
    )
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ToolError("Git returned an invalid result")
    return result


def _filter_overrides(
    workspace: str,
    repository: str,
    executable: str,
    expected_executable_sha256: str,
) -> list[str]:
    """`-c` settings that switch off the filter commands the repository's config names.

    Comparing the work tree (status, a work-tree diff, blame of a changed file) runs a
    filter's clean or process command, and that command comes from the repository's own
    config: a downloaded folder with a planted .git/config would run it from a read-only
    tool. Read with includes, so a driver in an included file is found too."""
    result = _invoke_git(
        workspace,
        repository,
        _git_arguments(
            "config", "-z", "--name-only", "--get-regexp", r"^filter\..+\.(clean|smudge|process)$"
        ),
        executable,
        expected_executable_sha256,
    )
    if result.get("exit_code") == 1:  # Nothing matched.
        return []
    drivers = {
        name.rsplit(".", 1)[0]
        for name in _git_stdout(result, "filter lookup").split("\x00")
        if name.strip()
    }
    overrides: list[str] = []
    for driver in sorted(drivers):
        for setting in ("clean=", "smudge=", "process=", "required=false"):
            overrides.extend(("-c", f"{driver}.{setting}"))
    return overrides


def _git_stdout(
    result: dict[str, Any],
    operation: str,
    *,
    allow_truncated_stdout: bool = False,
) -> str:
    exit_code = result.get("exit_code")
    stdout = result.get("stdout")
    stderr = result.get("stderr")
    if not isinstance(stdout, dict) or not isinstance(stderr, dict):
        raise ToolError("Git returned invalid process streams")
    if result.get("timed_out") is True:
        raise ToolError(f"Git {operation} timed out")
    if exit_code != 0:
        detail = str(stderr.get("text", "")).strip()[:1000]
        raise ToolError(f"Git {operation} failed: {detail or f'exit code {exit_code}'}")
    if (stdout.get("truncated") is True and not allow_truncated_stdout) or stderr.get(
        "truncated"
    ) is True:
        raise ToolError(f"Git {operation} output exceeded its safety limit")
    text = stdout.get("text")
    if not isinstance(text, str):
        raise ToolError("Git returned invalid text output")
    return text


def _validate_repository(
    paths: WorkspacePaths,
    repository: str,
    executable: str,
    expected_executable_sha256: str,
) -> tuple[Path, Path, Path]:
    root = paths.resolve(repository)
    if not root.is_dir():
        raise ToolError(f"Git repository path is not a directory: {root}")
    workspace = str(paths.root)
    top = _git_stdout(
        _invoke_git(
            workspace,
            paths.relative(root),
            _git_arguments("rev-parse", "--show-toplevel"),
            executable,
            expected_executable_sha256,
        ),
        "repository discovery",
    ).strip()
    git_dir = _git_stdout(
        _invoke_git(
            workspace,
            paths.relative(root),
            _git_arguments("rev-parse", "--absolute-git-dir"),
            executable,
            expected_executable_sha256,
        ),
        "git-dir discovery",
    ).strip()
    common_dir = _git_stdout(
        _invoke_git(
            workspace,
            paths.relative(root),
            _git_arguments("rev-parse", "--git-common-dir"),
            executable,
            expected_executable_sha256,
        ),
        "common-dir discovery",
    ).strip()
    top_path = paths.resolve(top)
    git_dir_path = paths.resolve(git_dir)
    common_candidate = Path(common_dir)
    if not common_candidate.is_absolute():
        # Relative to where git ran (the folder asked for), not to the top level.
        common_candidate = root / common_candidate
    common_dir_path = paths.resolve(common_candidate)
    if not top_path.is_dir() or not git_dir_path.is_dir() or not common_dir_path.is_dir():
        raise ToolError("Git repository metadata is invalid")
    return top_path, git_dir_path, common_dir_path


def _file_sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ToolError(f"cannot read Git index: {path}") from exc


def _valid_object_id(value: str) -> bool:
    return len(value) in {40, 64} and all(character in "0123456789abcdef" for character in value)


def _git_status_sync(
    workspace: str,
    repository: str,
    include_ignored: bool,
    maximum: int,
    executable: str,
    expected_executable_sha256: str,
) -> str:
    paths = WorkspacePaths(workspace)
    try:
        top, git_dir, _ = _validate_repository(
            paths,
            repository,
            executable,
            expected_executable_sha256,
        )
    except (PathOutsideWorkspaceError, ToolError) as exc:
        # `git rev-parse` can legitimately report no repository when the
        # selected workspace is nested inside another checkout. Return a
        # structured result so the model can recover instead of receiving a
        # worker exception that looks like a conversation failure. Anything
        # else (a timeout, dubious ownership, a changed git executable) is
        # reported as itself rather than as "not a repository".
        if not isinstance(exc, PathOutsideWorkspaceError) and (
            "not a git repository" not in str(exc).casefold()
        ):
            raise
        return json_result(
            {
                "repository": repository,
                "is_repository": False,
                "reason": "not_git_repository",
                "entries": [],
                "truncated": False,
                "index_sha256": None,
                "git_executable": executable,
                "git_executable_sha256": expected_executable_sha256,
            }
        )
    arguments = _git_arguments(
        *_filter_overrides(workspace, paths.relative(top), executable, expected_executable_sha256),
        "status",
        "--porcelain=v1",
        "-z",
        "--branch",
        "--untracked-files=all",
        *(("--ignored",) if include_ignored else ()),
    )
    result = _invoke_git(
        workspace,
        paths.relative(top),
        arguments,
        executable,
        expected_executable_sha256,
    )
    # A large status (node_modules with --ignored) passes the output limit: the complete
    # records before the cut are listed and the result is marked truncated.
    output = _git_stdout(result, "status", allow_truncated_stdout=True)
    cut = result["stdout"].get("truncated") is True
    # Every record ends with NUL; what follows the last one is empty or cut short.
    records = output.split("\x00")[:-1]
    branch = ""
    entries: list[dict[str, Any]] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if record.startswith("## "):
            branch = record[3:]
            continue
        if len(record) < 4 or record[2] != " ":
            raise ToolError("Git status returned malformed porcelain data")
        xy = record[:2]
        path = record[3:]
        original: str | None = None
        if "R" in xy or "C" in xy:
            if index >= len(records):
                if cut:
                    break
                raise ToolError("Git status returned an incomplete rename")
            original = records[index]
            index += 1
        entries.append({"xy": xy, "path": path, "original_path": original})
        if len(entries) >= maximum:
            break
    return json_result(
        {
            "repository": paths.relative(top),
            "branch": branch,
            "entries": entries,
            "truncated": cut or (len(entries) >= maximum and any(records[index:])),
            "index_sha256": _file_sha256(git_dir / "index"),
            "git_executable": executable,
            "git_executable_sha256": expected_executable_sha256,
        }
    )


def _git_diff_sync(
    workspace: str,
    repository: str,
    scope: str,
    raw_paths: list[str],
    context: int,
    maximum: int,
    executable: str,
    expected_executable_sha256: str,
) -> str:
    paths = WorkspacePaths(workspace)
    top, _, _ = _validate_repository(
        paths,
        repository,
        executable,
        expected_executable_sha256,
    )
    selected_paths: list[str] = []
    for raw_path in raw_paths:
        resolved = paths.resolve(top / raw_path)
        relative_to_top = os.path.relpath(resolved, top)
        if relative_to_top == ".." or relative_to_top.startswith(f"..{os.sep}"):
            raise ToolArgumentError(f"path is outside the repository: {raw_path}")
        # Git pathspecs are relative to the repository top-level working
        # directory and always use forward slashes.
        selected_paths.append(Path(relative_to_top).as_posix())
    arguments = _git_arguments(
        *_filter_overrides(workspace, paths.relative(top), executable, expected_executable_sha256),
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        f"--unified={context}",
    )
    if scope == "index":
        arguments.append("--cached")
    elif scope == "head":
        arguments.append("HEAD")
    if selected_paths:
        arguments.extend(("--", *selected_paths))
    process_result = _invoke_git(
        workspace,
        paths.relative(top),
        arguments,
        executable,
        expected_executable_sha256,
    )
    output = _git_stdout(process_result, "diff", allow_truncated_stdout=True)
    stdout = process_result.get("stdout")
    if not isinstance(stdout, dict):
        raise ToolError("Git diff returned invalid process output")
    encoded = output.encode("utf-8")
    retained = encoded[:maximum].decode("utf-8", errors="ignore")
    total_bytes = stdout.get("bytes")
    digest = stdout.get("sha256")
    if not isinstance(total_bytes, int) or not isinstance(digest, str):
        raise ToolError("Git diff returned invalid stream metadata")
    return json_result(
        {
            "repository": paths.relative(top),
            "scope": scope,
            "patch": retained,
            "bytes": total_bytes,
            "sha256": digest,
            "truncated": total_bytes > len(retained.encode("utf-8")),
            "git_executable": executable,
            "git_executable_sha256": expected_executable_sha256,
        }
    )


def _commit_identity(
    workspace: str,
    repository: str,
    executable: str,
    expected_executable_sha256: str,
) -> dict[str, str]:
    """The user's own name and email, as Git reads them from the environment.

    Git runs here without the global config, which is where most people set them, so
    these keys alone are read from it. The repository's own config still comes first.
    """
    home = os.environ.get("HOME") or os.path.expanduser("~")
    config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    # In the order Git reads them: what is read later wins.
    global_configs = [
        {"GIT_CONFIG_GLOBAL": str(path), "HOME": home}
        for path in (Path(config_home) / "git" / "config", Path(home) / ".gitconfig")
        if path.is_file()
    ]
    values: dict[str, str] = {}
    for environment in global_configs or [{}]:
        result = _invoke_git(
            workspace,
            repository,
            _git_arguments(
                "config", "-z", "--get-regexp", r"^(user|author|committer)\.(name|email)$"
            ),
            executable,
            expected_executable_sha256,
            environment=environment,
        )
        # Exit code 1 only says that nothing matched.
        if result.get("exit_code") == 0:
            for entry in _git_stdout(result, "identity lookup").split("\x00"):
                key, _, value = entry.partition("\n")
                values[key] = value
    identity: dict[str, str] = {}
    for role in ("author", "committer"):
        for field in ("name", "email"):
            chosen = values.get(f"{role}.{field}") or values.get(f"user.{field}")
            if not chosen:
                raise ToolError(
                    "Git has no identity to commit with; set user.name and user.email "
                    "with git config"
                )
            identity[f"GIT_{role.upper()}_{field.upper()}"] = chosen
    return identity


def _git_commit_sync(
    workspace: str,
    repository: str,
    message: str,
    expected_head: str | None,
    expected_index_sha256: str,
    executable: str,
    expected_executable_sha256: str,
) -> str:
    paths = WorkspacePaths(workspace)
    top, git_dir, _ = _validate_repository(
        paths,
        repository,
        executable,
        expected_executable_sha256,
    )
    current_index = _file_sha256(git_dir / "index")
    if current_index != expected_index_sha256:
        raise ConcurrentModificationError("Git index changed before commit")
    head_result = _invoke_git(
        workspace,
        paths.relative(top),
        _git_arguments("rev-parse", "--verify", "HEAD"),
        executable,
        expected_executable_sha256,
    )
    current_head = (
        _git_stdout(head_result, "HEAD discovery").strip()
        if head_result.get("exit_code") == 0
        else None
    )
    if current_head != expected_head:
        raise ConcurrentModificationError("Git HEAD changed before commit")
    identity = _commit_identity(
        workspace, paths.relative(top), executable, expected_executable_sha256
    )
    index_path = git_dir / "index"
    try:
        index_snapshot = index_path.read_bytes()
    except OSError as exc:
        raise ToolError("cannot snapshot Git index") from exc
    if hashlib.sha256(index_snapshot).hexdigest() != expected_index_sha256:
        raise ConcurrentModificationError("Git index changed while creating commit snapshot")
    with tempfile.TemporaryDirectory(prefix="agent-workspace-git-index-") as temporary:
        snapshot_path = Path(temporary) / "index"
        snapshot_path.write_bytes(index_snapshot)
        tree = _git_stdout(
            _invoke_git(
                workspace,
                paths.relative(top),
                _git_arguments(
                    "write-tree",
                    read_only=False,
                ),
                executable,
                expected_executable_sha256,
                index_file=snapshot_path,
            ),
            "tree creation",
        ).strip()
    if not _valid_object_id(tree):
        raise ToolError("Git tree creation returned an invalid object id")

    commit_arguments = ["commit-tree", tree]
    if current_head is not None:
        commit_arguments.extend(("-p", current_head))
    commit_arguments.extend(("-m", message))
    new_head = _git_stdout(
        _invoke_git(
            workspace,
            paths.relative(top),
            _git_arguments(*commit_arguments, read_only=False),
            executable,
            expected_executable_sha256,
            timeout_seconds=110,
            environment=identity,
        ),
        "commit object creation",
    ).strip()
    if not _valid_object_id(new_head):
        raise ToolError("Git commit creation returned an invalid object id")
    old_head = current_head or ("0" * len(new_head))
    try:
        _git_stdout(
            _invoke_git(
                workspace,
                paths.relative(top),
                _git_arguments(
                    "update-ref",
                    "-m",
                    "commit: Agent Workspace",
                    "HEAD",
                    new_head,
                    old_head,
                    read_only=False,
                ),
                executable,
                expected_executable_sha256,
                environment=identity,  # for the reflog
            ),
            "atomic reference update",
        )
    except ToolError as exc:
        raise ConcurrentModificationError("Git HEAD changed before commit publication") from exc
    published_head = _git_stdout(
        _invoke_git(
            workspace,
            paths.relative(top),
            _git_arguments("rev-parse", "--verify", "HEAD"),
            executable,
            expected_executable_sha256,
        ),
        "HEAD verification",
    ).strip()
    if published_head != new_head:
        raise ToolError("Git commit reference verification failed")
    # Sync the real repository index to the committed tree so subsequent
    # status/--cached output and repeated commits stay consistent with HEAD.
    current_index = _file_sha256(git_dir / "index")
    if current_index != expected_index_sha256:
        raise ConcurrentModificationError("Git index changed before index refresh")
    _git_stdout(
        _invoke_git(
            workspace,
            paths.relative(top),
            _git_arguments("read-tree", tree, read_only=False),
            executable,
            expected_executable_sha256,
        ),
        "index refresh",
    )
    refreshed_index_sha256 = _file_sha256(git_dir / "index")
    return json_result(
        {
            "repository": paths.relative(top),
            "previous_head": current_head,
            "head": new_head,
            "tree": tree,
            "index_sha256": refreshed_index_sha256,
            "git_executable": executable,
            "git_executable_sha256": expected_executable_sha256,
        }
    )


def _git_log_sync(
    workspace: str,
    repository: str,
    max_count: int,
    executable: str,
    expected_executable_sha256: str,
) -> str:
    paths = WorkspacePaths(workspace)
    top, _, _ = _validate_repository(
        paths,
        repository,
        executable,
        expected_executable_sha256,
    )
    result = _invoke_git(
        workspace,
        paths.relative(top),
        _git_arguments(
            "log",
            f"--max-count={max_count}",
            "--format=%H%x1f%h%x1f%an%x1f%aI%x1f%s",
        ),
        executable,
        expected_executable_sha256,
    )
    # Long subjects can pass the output limit before max_count: list the complete commits.
    output = _git_stdout(result, "log", allow_truncated_stdout=True)
    cut = result["stdout"].get("truncated") is True
    if cut:
        output = output[: output.rfind("\n") + 1]
    commits: list[dict[str, str]] = []
    for line in output.splitlines():
        fields = line.split("\x1f", 4)
        if len(fields) != 5:
            raise ToolError("Git log returned a malformed commit")
        commits.append(
            {
                "commit": fields[0],
                "short": fields[1],
                "author": fields[2],
                "date": fields[3],
                "subject": fields[4],
            }
        )
    return json_result(
        {
            "repository": paths.relative(top),
            "commits": commits,
            **({"truncated": True} if cut else {}),
        }
    )


def _git_blame_sync(
    workspace: str,
    repository: str,
    relative_path: str,
    maximum: int,
    executable: str,
    expected_executable_sha256: str,
) -> str:
    paths = WorkspacePaths(workspace)
    top, _, _ = _validate_repository(
        paths,
        repository,
        executable,
        expected_executable_sha256,
    )
    resolved_path = paths.resolve(relative_path)
    if not resolved_path.is_file():
        raise ToolError(f"Git blame path is not a file: {relative_path}")
    top_relative = str(resolved_path.relative_to(top))
    # Only the lines asked for, each commit's details once (--porcelain): the whole file
    # with every line's details repeated (--line-porcelain) passed the output limit at a few
    # hundred lines.
    wanted = min(maximum, _line_count(resolved_path))
    if wanted == 0:
        return json_result({"repository": paths.relative(top), "path": top_relative, "lines": []})
    result = _invoke_git(
        workspace,
        paths.relative(top),
        _git_arguments(
            *_filter_overrides(
                workspace, paths.relative(top), executable, expected_executable_sha256
            ),
            "blame",
            "--no-textconv",
            "--porcelain",
            f"-L1,{wanted}",
            "--",
            top_relative,
        ),
        executable,
        expected_executable_sha256,
    )
    output = _git_stdout(result, "blame", allow_truncated_stdout=True)
    truncated = result["stdout"].get("truncated") is True
    if truncated:
        output = output[: output.rfind("\n") + 1]  # the last line may be cut short
    lines: list[dict[str, Any]] = []
    commits: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    line_number = 0
    for raw in output.splitlines():
        if raw.startswith("\t"):
            lines.append({**current, "line": line_number, "content": raw[1:]})
            if len(lines) >= maximum:
                break
            continue
        parts = raw.split()
        if len(parts) >= 3 and _valid_object_id(parts[0]) and parts[2].isdecimal():
            current = commits.setdefault(parts[0], {"commit": parts[0]})
            line_number = int(parts[2])
        elif raw.startswith("author "):
            current["author"] = raw[7:]
        elif raw.startswith("author-time "):
            current["author_time"] = raw[12:]
        elif raw.startswith("summary "):
            current["summary"] = raw[8:]
    return json_result(
        {
            "repository": paths.relative(top),
            "path": top_relative,
            "lines": lines,
            **({"truncated": True} if truncated else {}),
        }
    )


def _line_count(path: Path) -> int:
    """Lines in a work-tree file as blame counts them (a last line without a newline too)."""
    count = 0
    last = b""
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                count += chunk.count(b"\n")
                last = chunk
    except OSError as exc:
        raise ToolError(f"cannot read the file to blame: {path.name}") from exc
    return count + (1 if last and not last.endswith(b"\n") else 0)


class _GitTool:
    hard_cancellable = True

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )

    def prepare_for_approval(self, arguments: dict[str, Any]) -> dict[str, Any]:
        executable = _git_executable(self.paths.root)
        prepared = dict(arguments)
        prepared["git_executable"] = str(executable)
        prepared["git_executable_sha256"] = _required_executable_sha256(executable)
        return prepared

    def _execution_identity(self, arguments: dict[str, Any]) -> tuple[str, str]:
        if "git_executable" not in arguments or "git_executable_sha256" not in arguments:
            arguments = self.prepare_for_approval(arguments)
        executable = arguments.get("git_executable")
        digest = arguments.get("git_executable_sha256")
        if not isinstance(executable, str) or not isinstance(digest, str):
            raise ToolArgumentError("Git executable identity is invalid")
        return executable, digest.casefold()


class GitLogTool(_GitTool):
    _SPEC = ToolSpec(
        name="git_log",
        description=("Return bounded Git commit history for a workspace repository without hooks."),
        input_schema={
            "type": "object",
            "properties": {
                "repository": {"type": "string", "minLength": 1, "default": "."},
                "max_count": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            "additionalProperties": False,
        },
        side_effect="git_read",
        capability=Capability.GIT_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        repository = arguments.get("repository", ".")
        if not isinstance(repository, str) or not repository:
            raise ToolArgumentError("'repository' must be a non-empty string")
        maximum = optional_int(arguments, "max_count", 20, minimum=1, maximum=500)
        executable, executable_sha256 = self._execution_identity(arguments)
        return await run_in_process(
            _git_log_sync,
            str(self.paths.root),
            repository,
            maximum,
            executable,
            executable_sha256,
            allow_children=True,
        )


class GitBlameTool(_GitTool):
    _SPEC = ToolSpec(
        name="git_blame",
        description="Return bounded line-by-line Git blame for a workspace file.",
        input_schema={
            "type": "object",
            "properties": {
                "repository": {"type": "string", "minLength": 1, "default": "."},
                "path": {"type": "string", "minLength": 1},
                "max_lines": {"type": "integer", "minimum": 1, "maximum": 2000},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        side_effect="git_read",
        capability=Capability.GIT_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        repository = arguments.get("repository", ".")
        raw_path = arguments.get("path")
        if not isinstance(repository, str) or not repository:
            raise ToolArgumentError("'repository' must be a non-empty string")
        if not isinstance(raw_path, str) or not raw_path:
            raise ToolArgumentError("'path' must be a non-empty string")
        maximum = optional_int(arguments, "max_lines", 200, minimum=1, maximum=2000)
        executable, executable_sha256 = self._execution_identity(arguments)
        return await run_in_process(
            _git_blame_sync,
            str(self.paths.root),
            repository,
            raw_path,
            maximum,
            executable,
            executable_sha256,
            allow_children=True,
        )


class GitStatusTool(_GitTool):
    _SPEC = ToolSpec(
        name="git_status",
        description="Return bounded, NUL-delimited Git worktree status without hooks or prompts.",
        input_schema={
            "type": "object",
            "properties": {
                "repository": {"type": "string", "minLength": 1, "default": "."},
                "include_ignored": {"type": "boolean", "default": False},
                "max_entries": {"type": "integer", "minimum": 1, "maximum": 5000},
            },
            "additionalProperties": False,
        },
        side_effect="git_read",
        capability=Capability.GIT_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        repository = arguments.get("repository", ".")
        if not isinstance(repository, str) or not repository:
            raise ToolArgumentError("'repository' must be a non-empty string")
        include_ignored = arguments.get("include_ignored", False)
        if not isinstance(include_ignored, bool):
            raise ToolArgumentError("'include_ignored' must be a boolean")
        maximum = optional_int(arguments, "max_entries", 1000, minimum=1, maximum=5000)
        executable, executable_sha256 = self._execution_identity(arguments)
        return await run_in_process(
            _git_status_sync,
            str(self.paths.root),
            repository,
            include_ignored,
            maximum,
            executable,
            executable_sha256,
            allow_children=True,
        )


class GitDiffTool(_GitTool):
    _SPEC = ToolSpec(
        name="git_diff",
        description=(
            "Return a bounded Git patch without external diff, textconv, hooks, or prompts."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "repository": {"type": "string", "minLength": 1, "default": "."},
                "scope": {
                    "type": "string",
                    "enum": ["worktree", "index", "head"],
                    "default": "worktree",
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "maxItems": _MAX_GIT_PATHS,
                    "default": [],
                },
                "context": {"type": "integer", "minimum": 0, "maximum": 20},
                "max_patch_bytes": {
                    "type": "integer",
                    "minimum": 4096,
                    "maximum": _MAX_DIFF_BYTES,
                },
            },
            "additionalProperties": False,
        },
        side_effect="git_read",
        capability=Capability.GIT_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        repository = arguments.get("repository", ".")
        scope = arguments.get("scope", "worktree")
        raw_paths = arguments.get("paths", [])
        if not isinstance(repository, str) or not repository:
            raise ToolArgumentError("'repository' must be a non-empty string")
        if scope not in {"worktree", "index", "head"}:
            raise ToolArgumentError("'scope' is unsupported")
        if not isinstance(raw_paths, list) or any(not isinstance(path, str) for path in raw_paths):
            raise ToolArgumentError("'paths' must be an array of strings")
        context = optional_int(arguments, "context", 3, minimum=0, maximum=20)
        maximum = optional_int(
            arguments,
            "max_patch_bytes",
            _MAX_DIFF_BYTES,
            minimum=4096,
            maximum=_MAX_DIFF_BYTES,
        )
        executable, executable_sha256 = self._execution_identity(arguments)
        return await run_in_process(
            _git_diff_sync,
            str(self.paths.root),
            repository,
            scope,
            list(raw_paths),
            context,
            maximum,
            executable,
            executable_sha256,
            allow_children=True,
        )


class GitCommitTool(_GitTool):
    hard_cancellable = False
    _SPEC = ToolSpec(
        name="git_commit",
        description=(
            "Commit only the already-staged Git index after HEAD and index CAS checks. "
            "Hooks, signing, and prompts are disabled; of the global config only the user's "
            "name and email are read. After a successful commit the repository index is "
            "refreshed to the committed tree."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "repository": {"type": "string", "minLength": 1, "default": "."},
                "message": {"type": "string", "minLength": 1, "maxLength": 4096},
                "expected_head": {
                    "anyOf": [
                        {"type": "null"},
                        {"type": "string", "pattern": "^[0-9a-fA-F]{40}([0-9a-fA-F]{24})?$"},
                    ]
                },
                "expected_index_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-fA-F]{64}$",
                },
            },
            "required": ["message", "expected_head", "expected_index_sha256"],
            "additionalProperties": False,
        },
        side_effect="git_write",
        capability=Capability.GIT_WRITE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        repository = arguments.get("repository", ".")
        message = arguments.get("message")
        expected_head = arguments.get("expected_head")
        expected_index = arguments.get("expected_index_sha256")
        if not isinstance(repository, str) or not repository:
            raise ToolArgumentError("'repository' must be a non-empty string")
        if not isinstance(message, str) or not message.strip():
            raise ToolArgumentError("'message' must be a non-empty string")
        if expected_head is not None and not isinstance(expected_head, str):
            raise ToolArgumentError("'expected_head' must be a Git object id or null")
        if not isinstance(expected_index, str):
            raise ToolArgumentError("'expected_index_sha256' must be a SHA-256 digest")
        executable, executable_sha256 = self._execution_identity(arguments)
        return await run_in_process(
            _git_commit_sync,
            str(self.paths.root),
            repository,
            message,
            expected_head.lower() if isinstance(expected_head, str) else None,
            expected_index.lower(),
            executable,
            executable_sha256,
            allow_children=True,
        )
