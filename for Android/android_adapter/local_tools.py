"""Tools registered only for on-device models.

A small model copies a file by reading it into its context and generating every byte again:
slow on a phone CPU (a 2B model writes about 11 tokens per second) and lossy (it pasted the
read result's JSON wrapper into a copy). copy_file does the same in one call. It reads the
source here and saves through the workspace's own write_file, so the write keeps write_file's
policy check, durable rollback checkpoint and never-overwrite rule for a new file.

make_directory here also creates missing parent folders and treats an existing folder as done:
a 0.8B model otherwise retried "directory target already exists" until its step budget ran out.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.storage.durable import fsync_directory
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result
from agent_workspace.tools.paths import StrPath, WorkspacePaths, is_sensitive_workspace_path

from .chaquopy_runtime import run_in_process

# write_file's own content limit.
_MAX_COPY_BYTES = 16 * 1024 * 1024


def _workspace(workspace: WorkspacePaths | StrPath) -> WorkspacePaths:
    return workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)


def _make_directories_sync(workspace: str, raw_path: str) -> str:
    paths = WorkspacePaths(workspace)
    target = paths.resolve(raw_path)
    relative = paths.relative(target)
    if target.exists():
        if not target.is_dir():
            raise ToolError(f"a file already uses this path: {relative}")
        return json_result({"path": relative, "created": False, "already_existed": True})
    missing = []
    current = target
    while not current.exists():
        missing.append(current)
        current = current.parent
    if not current.is_dir():
        raise ToolError(f"a file is in the way of this folder: {paths.relative(current)}")
    try:
        for folder in reversed(missing):
            paths.resolve(folder)  # still inside the workspace once its parent exists
            folder.mkdir()
            fsync_directory(folder.parent)
    except FileExistsError:
        if not target.is_dir():
            raise ToolError(f"cannot create folder: {relative}") from None
    except OSError as exc:
        raise ToolError(f"cannot create folder: {relative}") from exc
    return json_result({"path": relative, "created": True})


class MakeDirectoriesTool:
    """The core make_directory contract, forgiving about parents and existing folders."""

    hard_cancellable = False

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        from agent_workspace.tools.manage import MakeDirectoryTool

        self.spec = replace(
            MakeDirectoryTool._SPEC,
            description="Create a folder, including any missing parent folders.",
        )
        self.paths = _workspace(workspace)

    async def execute(self, arguments: dict[str, Any]) -> str:
        raw_path = arguments.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise ToolArgumentError("'path' must be a non-empty string")
        return await run_in_process(_make_directories_sync, str(self.paths.root), raw_path)


class CopyFileTool:
    hard_cancellable = False

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        from agent_workspace.tools.filesystem import WriteFileTool

        self.paths = _workspace(workspace)
        self._write = WriteFileTool(self.paths)
        self.spec = ToolSpec(
            name="copy_file",
            description=(
                "Copy a UTF-8 text file in the workspace to another path, byte for byte. Use "
                "this instead of reading and rewriting a file. To replace an existing "
                "destination, pass the sha256 it was read with as expected_sha256."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "minLength": 1},
                    "path": {"type": "string", "minLength": 1},
                    "expected_sha256": {"type": ["string", "null"]},
                },
                "required": ["source", "path"],
                "additionalProperties": False,
            },
            side_effect="write",
            capability=Capability.WORKSPACE_WRITE,
            # The save is write_file's, including its preimage checkpoint.
            durable_preimage_checkpoint=True,
        )

    def _write_arguments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        raw_source, raw_path = arguments.get("source"), arguments.get("path")
        if not all(isinstance(value, str) and value for value in (raw_source, raw_path)):
            raise ToolArgumentError("copy_file requires source and path")
        assert isinstance(raw_source, str)
        source = self.paths.resolve(raw_source)
        relative = self.paths.relative(source)
        # The write policy only sees the destination; a sensitive source needs read_file,
        # whose own approval rules apply.
        if is_sensitive_workspace_path(relative):
            raise ToolError(f"copy_file does not copy sensitive files: {relative}")
        if source == self.paths.resolve(raw_path):
            raise ToolArgumentError("source and path must differ")
        try:
            with source.open("rb") as stream:
                metadata = WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), source)
                if metadata.st_size > _MAX_COPY_BYTES:
                    raise ToolError(f"file exceeds the {_MAX_COPY_BYTES}-byte copy limit")
                content = stream.read(_MAX_COPY_BYTES + 1)
        except FileNotFoundError as exc:
            raise ToolError(f"file does not exist: {relative}") from exc
        except (IsADirectoryError, PermissionError) as exc:
            raise ToolError(f"cannot read file: {relative}") from exc
        if len(content) > _MAX_COPY_BYTES:
            raise ToolError(f"file exceeds the {_MAX_COPY_BYTES}-byte copy limit")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(f"copy_file copies UTF-8 text files only: {relative}") from exc
        expected = arguments.get("expected_sha256")
        if expected is not None and not isinstance(expected, str):
            raise ToolArgumentError("'expected_sha256' must be a sha256 or null")
        # write_file checks it: a new destination needs null, an existing one its digest.
        return {"path": raw_path, "content": text, "expected_sha256": expected}

    @staticmethod
    def _with_source(result: str, arguments: dict[str, Any]) -> str:
        data = json.loads(result)
        return json_result({"source": arguments["source"], **data})

    async def execute(self, arguments: dict[str, Any]) -> str:
        write = await run_in_process(self._write_arguments, arguments)
        return self._with_source(await self._write.execute(write), arguments)

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        write = await run_in_process(self._write_arguments, arguments)
        result = await self._write.execute_with_context(write, context)
        return self._with_source(result, arguments)


_ESCAPE = re.compile(r'\\([ntr"\\/])')
_ESCAPED = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/"}


def _unescape(text: str) -> str:
    return _ESCAPE.sub(lambda match: _ESCAPED[match[1]], text)


class UnescapingPatchTool:
    """apply_patch for on-device models, which copy old_text out of a read_file result with its
    JSON escapes: asked to delete "  引用 \\t\\n", a 2B model sent a backslash and a t where the
    file has a tab, failed "found 0 matches" eleven times and then deleted the wrong text.

    When old_text as given is not in the file but its unescaped form is, exactly once, the patch
    uses the unescaped old_text and new_text. The wrapped tool still checks the digest and the
    match, so nothing else changes.
    """

    def __init__(self, tool: Any, workspace: WorkspacePaths | StrPath) -> None:
        self._tool = tool
        self.spec = tool.spec
        self.hard_cancellable = getattr(tool, "hard_cancellable", False)
        self.paths = _workspace(workspace)

    def _arguments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        old, path = arguments.get("old_text"), arguments.get("path")
        if not isinstance(old, str) or not isinstance(path, str) or "\\" not in old:
            return arguments
        decoded = _unescape(old)
        try:
            text = self.paths.resolve(path).read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError, ValueError, ToolError):
            return arguments
        if decoded == old or old in text or text.count(decoded) != 1:
            return arguments
        new = arguments.get("new_text")
        return {**arguments, "old_text": decoded,
                "new_text": _unescape(new) if isinstance(new, str) else new}  # fmt: skip

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await self._tool.execute(await run_in_process(self._arguments, arguments))

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        fixed = await run_in_process(self._arguments, arguments)
        return await self._tool.execute_with_context(fixed, context)


class AppendFileTool:
    """Adds text at the end of a file, through write_file like copy_file.

    Asked to append a line, a 2B model patched after the last line it could match and left
    the file's trailing blank lines after the new text.
    """

    hard_cancellable = False

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        from agent_workspace.tools.filesystem import WriteFileTool

        self.paths = _workspace(workspace)
        self._write = WriteFileTool(self.paths)
        self.spec = ToolSpec(
            name="append_file",
            description=(
                "Add text at the very end of a UTF-8 text file in the workspace, keeping "
                "everything already in it. expected_sha256 is the sha256 the file was read with."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "text": {"type": "string", "minLength": 1},
                    "expected_sha256": {"type": "string"},
                },
                "required": ["path", "text", "expected_sha256"],
                "additionalProperties": False,
            },
            side_effect="write",
            capability=Capability.WORKSPACE_WRITE,
            durable_preimage_checkpoint=True,
        )

    def _write_arguments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        raw_path, text = arguments.get("path"), arguments.get("text")
        expected = arguments.get("expected_sha256")
        if not isinstance(raw_path, str) or not raw_path:
            raise ToolArgumentError("'path' must be a file in the workspace")
        if not isinstance(text, str) or not text:
            raise ToolArgumentError("'text' must be the text to add")
        if not isinstance(expected, str):
            raise ToolArgumentError("'expected_sha256' must be the sha256 the file was read with")
        path = self.paths.resolve(raw_path)
        relative = self.paths.relative(path)
        try:
            with path.open("rb") as stream:
                metadata = WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), path)
                if metadata.st_size > _MAX_COPY_BYTES:
                    raise ToolError(f"file exceeds the {_MAX_COPY_BYTES}-byte edit limit")
                content = stream.read(_MAX_COPY_BYTES + 1)
        except FileNotFoundError as exc:
            raise ToolError(
                f"file does not exist: {relative}; create it with write_file"
            ) from exc
        except (IsADirectoryError, PermissionError) as exc:
            raise ToolError(f"cannot read file: {relative}") from exc
        try:
            existing = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(f"append_file edits UTF-8 text files only: {relative}") from exc
        # write_file refuses the save unless the file still has the digest the model read.
        return {"path": raw_path, "content": existing + text, "expected_sha256": expected}

    async def execute(self, arguments: dict[str, Any]) -> str:
        write = await run_in_process(self._write_arguments, arguments)
        return await self._write.execute(write)

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        write = await run_in_process(self._write_arguments, arguments)
        return await self._write.execute_with_context(write, context)
