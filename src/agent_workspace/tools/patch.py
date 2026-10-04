from __future__ import annotations

import asyncio
import difflib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.models import Capability, FileCheckpoint, ToolSpec

from .base import ToolArgumentError, ToolError, json_result, require_string
from .filesystem import (
    _MAX_EDIT_BYTES,
    _encode_edit_text,
    _read_preimage,
    _workspace_paths,
    atomic_write,
    expected_sha256,
    sha256_bytes,
)
from .paths import StrPath, WorkspacePaths
from .process_worker import run_in_process


class ApplyPatchTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="apply_patch",
        description="Replace one unique exact text block in a UTF-8 file using SHA-256 CAS.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string", "maxLength": _MAX_EDIT_BYTES},
                "new_text": {"type": "string", "maxLength": _MAX_EDIT_BYTES},
                "expected_sha256": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text", "expected_sha256"],
            "additionalProperties": False,
        },
        side_effect="write",
        capability=Capability.WORKSPACE_WRITE,
        durable_preimage_checkpoint=True,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = _workspace_paths(workspace)

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await asyncio.to_thread(self._execute_sync, arguments)

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        path, relative, original_bytes, updated_bytes, expected, diff = self._prepare(arguments)
        postimage_digest = sha256_bytes(updated_bytes)
        await context.prepare_file_checkpoint(
            FileCheckpoint(
                attempt_id=context.attempt_id,
                session_id=context.session_id,
                workspace=str(self.paths.root),
                started_event_id=context.started_event_id,
                relative_path=relative,
                preimage_sha256=expected,
                preimage=original_bytes,
                postimage_sha256=postimage_digest,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
        return await run_in_process(
            self._execute_prepared,
            path,
            relative,
            updated_bytes,
            expected,
            diff,
        )

    def _execute_sync(self, arguments: dict[str, Any]) -> str:
        path, relative, _, updated_bytes, expected, diff = self._prepare(arguments)
        return self._execute_prepared(path, relative, updated_bytes, expected, diff)

    def _execute_prepared(
        self,
        path: Path,
        relative: str,
        updated_bytes: bytes,
        expected: str,
        diff: str,
    ) -> str:
        _, digest = atomic_write(self.paths, path, updated_bytes, expected)
        return json_result({"path": relative, "sha256": digest, "diff": diff})

    def _prepare(
        self,
        arguments: dict[str, Any],
    ) -> tuple[Path, str, bytes, bytes, str, str]:
        raw_path = require_string(arguments, "path")
        old_text = require_string(arguments, "old_text")
        new_text = require_string(arguments, "new_text", allow_empty=True)
        _encode_edit_text(old_text, "old_text")
        _encode_edit_text(new_text, "new_text")
        expected = expected_sha256(arguments)
        if expected is None:
            raise ToolArgumentError("'expected_sha256' may not be null for apply_patch")

        path = self.paths.resolve(raw_path)
        original_bytes = _read_preimage(path, expected, _MAX_EDIT_BYTES)
        if original_bytes is None:
            raise ToolError(f"file does not exist: {path}")
        try:
            original = original_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(f"file is not valid UTF-8: {path}") from exc
        matches = original.count(old_text)
        if matches != 1:
            raise ToolArgumentError(f"old_text must match exactly once; found {matches} matches")

        updated = original.replace(old_text, new_text, 1)
        updated_bytes = _encode_edit_text(updated, "patched content")
        relative = self.paths.relative(path)
        diff_lines = difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
            lineterm="",
        )
        diff = "\n".join(diff_lines) + "\n"
        return path, relative, original_bytes, updated_bytes, expected, diff
