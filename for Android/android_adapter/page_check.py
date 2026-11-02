"""check_page on the phone: an HTML page of the workspace as the user will see it.

The app opens the pages and small tools the agent writes in an isolated preview: offline, no other
files, inline scripts and styles only (WorkspaceHtmlPreviewActivity). The native side draws the
file the same way off screen (browser/PageCheck.kt); this tool hands the model the picture and what
went wrong: console errors and uncaught exceptions, the resources the preview blocks, and whether
the page shows anything at all. Same name as the desktop's tool, so the runner sends the picture
along with the result.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
from typing import Any

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.events import Event
from agent_workspace.core.models import MAX_IMAGE_BYTES, BinaryArtifact, Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result
from agent_workspace.tools.paths import WorkspacePaths

from .browser import BrowserSession

_MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024


def _problems(report: dict[str, Any]) -> list[str]:
    """The report's findings in a few plain lines, the most likely cause first."""
    found: list[str] = []
    blocked = [str(item) for item in report.get("blocked") or []]
    console = list({str(item.get("text")): item for item in report.get("console") or [] if isinstance(item, dict)}.values())
    refused = [item["text"] for item in console if "Content Security Policy" in str(item.get("text"))]
    errors = [
        item["text"]
        for item in console
        if item.get("level") == "error" and "Content Security Policy" not in str(item.get("text"))
    ]
    if blocked or refused:
        found.append(
            f"{len(set(blocked)) + len(refused)} resource(s) did not load: the preview has no "
            "network and no other files, so scripts, styles, fonts and pictures must be inline "
            "(inline <script>/<style>, data: URLs, inline SVG)."
        )
    if errors:
        found.append(f"{len(errors)} script error(s) in the console: " + " | ".join(errors[:3]))
    if not report.get("scripts_run"):
        found.append("This phone's preview cannot run scripts: the page shows as static HTML.")
    page = report.get("page")
    if report.get("scripts_run") and not isinstance(page, dict):
        found.append("The page did not finish loading (no report from inside it).")
    elif isinstance(page, dict):
        if page.get("error"):
            found.append(f"The page could not be measured: {page['error']}")
        elif not page.get("visible") and not page.get("text"):
            found.append("The page shows nothing: no visible elements and no text.")
        if page.get("wide"):
            found.append("The page is wider than the phone's screen: people must scroll sideways.")
    if report.get("navigations"):
        found.append("The page tried to open other addresses, which the preview does not follow.")
    return found


class AndroidCheckPageTool:
    hard_cancellable = False
    _SPEC = ToolSpec(
        name="check_page",
        description=(
            "Look at an HTML file of the workspace as the user will see it in the app's preview: "
            "offline and isolated, so only inline scripts, styles and data: pictures work (no "
            "CDN, no separate .js/.css files, no network). Returns a screenshot at the phone's "
            "size (attached for you to look at), console errors and uncaught exceptions, the "
            "resources the preview blocked, whether the page shows anything, and a list of "
            "problems. Use it after writing or changing a page or a small tool, fix what it "
            "reports, and check again before you answer."
        ),
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "minLength": 1, "maxLength": 1024}},
            "required": ["path"],
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.WORKSPACE_READ,
    )

    def __init__(self, workspace: Any, session: BrowserSession | None = None) -> None:
        self.paths = workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        self.session = session or BrowserSession()

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def _check(self, arguments: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
        raw = arguments.get("path")
        if not isinstance(raw, str) or not raw.strip():
            raise ToolArgumentError("'path' must be an HTML file in the workspace")
        target = self.paths.resolve(raw)
        if target.suffix.lower() not in {".html", ".htm"}:
            raise ToolArgumentError("check_page looks at .html files")
        if not target.is_file():
            raise ToolError(f"{raw} does not exist; write the page first")
        root = Path(self.paths.root).resolve()
        response = self.session.call(
            {"action": "check_html", "root": str(root), "path": target.relative_to(root).as_posix()}
        )
        screenshot = response.get("screenshot")
        if not isinstance(screenshot, dict) or not isinstance(screenshot.get("absolute_path"), str):
            raise ToolError("check_page: no picture was drawn")
        picture = Path(screenshot["absolute_path"]).resolve()
        captures = Path(os.environ.get("AGENT_WORKSPACE_ANDROID_WORKSPACE") or root) / "automation" / "screenshots"
        if not picture.is_relative_to(captures.resolve()):
            raise ToolError("check_page: the picture is outside the private capture folder")
        data = picture.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > min(_MAX_SCREENSHOT_BYTES, MAX_IMAGE_BYTES):
            raise ToolError("check_page: the picture is not a usable PNG")
        report = {key: value for key, value in response.items() if key not in {"ok", "screenshot"}}
        report["screenshot"] = {
            key: value for key, value in screenshot.items() if key != "absolute_path"
        } | {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        problems = _problems(report)
        report["problems"] = problems
        page = report.get("page") if isinstance(report.get("page"), dict) else {}
        # Said plainly, so a model that cannot see the picture does not check again for nothing.
        report["summary"] = (
            f"No problems found: the page loads without errors, nothing is blocked, and it shows "
            f"{page.get('visible', 0)} visible elements and {page.get('text', 0)} characters of text."
            if not problems
            else f"{len(problems)} problem(s) found; fix them and check again."
        )
        return report, data

    async def execute(self, arguments: dict[str, Any]) -> str:
        report, _data = await asyncio.to_thread(self._check, arguments)
        return json_result(report)

    async def execute_with_context(self, arguments: dict[str, Any], context: ToolExecutionContext) -> str:
        report, data = await asyncio.to_thread(self._check, arguments)
        if context.record_artifact is not None:
            digest = report["screenshot"]["sha256"]
            await context.record_artifact(BinaryArtifact(digest, data))
            await context.record_event(
                Event(
                    session_id=context.session_id,
                    type="image.attached",
                    data={
                        "attempt_id": context.attempt_id,
                        "path": report["screenshot"].get("path", ""),
                        "media_type": "image/png",
                        "sha256": digest,
                        "bytes": len(data),
                    },
                    causation_id=context.started_event_id,
                    correlation_id=context.correlation_id,
                )
            )
        return json_result(report)


__all__ = ["AndroidCheckPageTool"]
