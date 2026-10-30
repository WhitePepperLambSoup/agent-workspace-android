"""Reviewing code changes from a paired phone (device link 2, feature "code_review"): the open
folder's changes and a file's diff, the review snapshots with their comments, freezing the changes
into a new snapshot, a comment on a line, and a comment handed to the agent. Each goes through the
same handler as the window's Changes page, so the phone and the window cannot disagree."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from agent_workspace.ui_gateway.device_link import DeviceLinkError, PairedDevice, TaskOptions
from agent_workspace.ui_gateway.gateway_common import GatewayReply
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import CommandEnvelope

MAX_DIFF_LINES = 3000
MAX_SNAPSHOTS = 20
MAX_COMMENT_CHARS = 4000
# The window's refusals in the endpoint's terms (code, status); any other is 503 with its code.
REFUSALS: dict[str, tuple[str, int]] = {
    "runtime_unconfigured": ("no_workspace", 503),
    "snapshot_not_found": ("unknown_review", 404),
    "unknown_snapshot": ("unknown_review", 404),
    "comment_not_found": ("unknown_comment", 404),
    "unknown_comment": ("unknown_comment", 404),
    "invalid_session": ("invalid_session", 400),
    "invalid_comment_anchor": ("invalid_comment_anchor", 400),
    "review_empty": ("no_changes", 409),
    "followup_already_exists": ("followup_already_exists", 409),
    "review_snapshot_too_large": ("review_too_large", 413),
    "snapshot_too_large": ("review_too_large", 413),
}


def _lines(hunks: list[dict[str, Any]], budget: int) -> tuple[list[dict[str, object]], bool, int]:
    """Hunks with their lines as the phone reads them (snake_case), cut at a number of lines;
    whether it was cut, and how many lines it used."""
    shown: list[dict[str, object]] = []
    used = 0
    for hunk in hunks:
        lines = hunk.get("lines") or []
        if used + len(lines) > budget:
            return shown, True, used
        used += len(lines)
        shown.append(
            {
                "header": hunk.get("header"),
                "lines": [
                    {
                        "kind": line.get("kind"),
                        "content": line.get("content"),
                        "old_line": line.get("oldLineno"),
                        "new_line": line.get("newLineno"),
                    }
                    for line in lines
                ],
            }
        )
    return shown, False, used


def _session(payload: dict[str, Any]) -> str | None:
    """The optional ``session_id`` of a request."""
    session_id = payload.get("session_id")
    if session_id is None:
        return None
    if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
        raise DeviceLinkError("invalid_session")
    return session_id


def _comment(document: dict[str, Any]) -> dict[str, object]:
    return {
        "id": document.get("id"),
        "path": document.get("path"),
        "side": document.get("side"),
        "line": document.get("line"),
        "body": document.get("body"),
        "state": document.get("state"),
        "author": document.get("author"),
        "followup_run_id": document.get("followupRunId"),
        "created_at": document.get("createdAt"),
    }


class DeviceReviewCommands(GatewayState):
    def _refusing[T](self, function: Callable[..., T], *arguments: object) -> T:
        try:
            return self._device_call(function, *arguments)
        except DeviceLinkError as error:
            if error.code not in REFUSALS:
                raise
            raise DeviceLinkError(*REFUSALS[error.code]) from None

    def _as_window(
        self,
        handler: Callable[[CommandEnvelope], GatewayReply],
        command_type: str,
        payload: dict[str, Any],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """The window's handler for a command, its refusals as the endpoint's."""
        envelope = CommandEnvelope(
            1, f"phone-{uuid4().hex[:12]}", command_type, payload, session_id
        )
        reply = self._refusing(handler, envelope)
        return dict(reply.payload)

    def device_changes(self, device: PairedDevice) -> dict[str, object]:
        diff = self._as_window(self._get_git_diff, "workspace.git.diff", {})
        files = diff.get("files") or []
        return {
            "git": diff.get("isGitRepo") is True,
            "error": diff.get("error"),
            "files": [
                {
                    "path": item.get("filePath"),
                    "status": item.get("status"),
                    "additions": item.get("additions"),
                    "deletions": item.get("deletions"),
                    "hunks": len(item.get("hunks") or []),
                }
                for item in files
            ],
        }

    def device_change_diff(self, device: PairedDevice, path: str) -> dict[str, object]:
        diff = self._as_window(self._get_git_diff, "workspace.git.diff", {})
        found = next(
            (item for item in diff.get("files") or [] if item.get("filePath") == path), None
        )
        if found is None:
            raise DeviceLinkError("unknown_path", 404)
        hunks, cut, _used = _lines(found.get("hunks") or [], MAX_DIFF_LINES)
        return {"path": path, "status": found.get("status"), "hunks": hunks, "truncated": cut}

    def device_reviews(self, device: PairedDevice) -> dict[str, object]:
        listed = self._as_window(
            self._list_review_snapshots, "workspace.review.list", {"limit": MAX_SNAPSHOTS}
        )
        return {
            "snapshots": [
                {
                    "id": item.get("id"),
                    "created_at": item.get("createdAt"),
                    "files": item.get("fileCount"),
                    "additions": item.get("additions"),
                    "deletions": item.get("deletions"),
                    "uncommitted": item.get("workingTreeDirty"),
                    "session_id": item.get("sessionId"),
                    "run_id": item.get("runId"),
                }
                for item in listed.get("snapshots") or []
            ]
        }

    def device_review(self, device: PairedDevice, snapshot_id: str) -> dict[str, object]:
        details = self._as_window(
            self._get_review_snapshot, "workspace.review.get", {"snapshotId": snapshot_id}
        )
        return self._review_document(details)

    def _review_document(self, details: dict[str, Any]) -> dict[str, object]:
        snapshot = details.get("snapshot") or {}
        budget = MAX_DIFF_LINES
        files = []
        for item in snapshot.get("files") or []:
            hunks, cut, used = _lines(item.get("hunks") or [], max(0, budget))
            budget -= used
            files.append(
                {
                    "path": item.get("filePath"),
                    "status": item.get("status"),
                    "additions": item.get("additions"),
                    "deletions": item.get("deletions"),
                    "hunks": hunks,
                    "truncated": cut,
                }
            )
        return {
            "snapshot": {
                "id": snapshot.get("id"),
                "created_at": snapshot.get("createdAt"),
                "base": snapshot.get("baseSha"),
                "head": snapshot.get("headSha"),
                "uncommitted": snapshot.get("workingTreeDirty"),
                "session_id": snapshot.get("sessionId"),
                "files": files,
            },
            "comments": [_comment(item) for item in details.get("comments") or []],
        }

    def device_review_create(
        self, device: PairedDevice, payload: dict[str, Any]
    ) -> dict[str, object]:
        """Freeze the folder's changes, under the conversation named or the window's own."""
        details = self._as_window(
            self._create_review_snapshot,
            "workspace.review.create",
            {},
            _session(payload),
        )
        return self._review_document(details)

    def device_review_comment(
        self, device: PairedDevice, snapshot_id: str, payload: dict[str, Any]
    ) -> dict[str, object]:
        path, side, line, body = (payload.get(key) for key in ("path", "side", "line", "body"))
        if (
            not isinstance(path, str)
            or side not in {"old", "new"}
            or type(line) is not int
            or line < 1
            or not isinstance(body, str)
            or not body.strip()
            or len(body) > MAX_COMMENT_CHARS
        ):
            raise DeviceLinkError("invalid_comment")
        created = self._as_window(
            self._create_review_comment,
            "workspace.review.comments.create",
            {
                "snapshotId": snapshot_id,
                "path": path,
                "side": side,
                "line": line,
                "body": body.strip(),
            },
        )
        self._device_hub.log(device, "review_comment", f"{path}:{line}")
        return {"comment": _comment(created.get("comment") or {})}

    def device_review_followup(
        self, device: PairedDevice, comment_id: str, payload: dict[str, Any]
    ) -> dict[str, object]:
        session_id = _session(payload)
        # The run works with the window's autonomy: where that approves everything on its own,
        # the phone must have confirmed it, as for a task.
        self._check_device_autonomy(device, self._autonomy, TaskOptions.from_payload(payload))
        # A phone repeats a request whose answer it lost; the window's handler would start a
        # second run before finding the first.
        existing = self._refusing(lambda: self._review_service().get_comment(comment_id))
        if existing is not None and existing.followup_run_id is not None:
            raise DeviceLinkError("followup_already_exists", 409, run_id=existing.followup_run_id)
        body: dict[str, Any] = {"commentId": comment_id, "start": True}
        if session_id:
            body["sessionId"] = session_id
        started = self._as_window(
            self._followup_review_comment, "workspace.review.comments.followup", body
        )
        run = started.get("run") or {}
        self._device_hub.log(device, "review_followup", str(run.get("id") or ""))
        return {
            "comment": _comment(started.get("comment") or {}),
            "run_id": run.get("id"),
            "started": started.get("started") is True,
        }


__all__ = ["DeviceReviewCommands"]
