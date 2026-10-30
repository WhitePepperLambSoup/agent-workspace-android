"""check_page: the agent looks at a web page of the project as a person would, in a headless
browser: a screenshot it sees, what went wrong in the console, and the requests that failed."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.events import Event
from agent_workspace.core.models import MAX_IMAGE_BYTES, BinaryArtifact, Capability, ToolSpec
from agent_workspace.tools.base import (
    ToolArgumentError,
    ToolError,
    json_result,
    validate_tool_arguments,
)
from agent_workspace.tools.browser import BrowserError, CdpSession
from agent_workspace.tools.managed_browser import ManagedBrowser, ManagedBrowserError
from agent_workspace.tools.paths import WorkspacePaths

VIEWPORTS = {"desktop": (1280, 800, False), "mobile": (390, 844, True)}
SCREENSHOTS = Path(".agent") / "screenshots"
LOAD_SECONDS = 20.0
QUIET_SECONDS = 0.8
SETTLE_SECONDS = 10.0
WAIT_FOR_SECONDS = 10.0
MAX_STEPS = 10
MAX_ITEMS = 30
MAX_TEXT = 500
MAX_PAGE_HEIGHT = 6000

_TYPE_SCRIPT = (
    "((selector, text) => {const el = document.querySelector(selector);"
    " if (!el) return false; el.focus();"
    " const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype"
    " : HTMLInputElement.prototype;"
    " const setter = Object.getOwnPropertyDescriptor(proto, 'value');"
    " const field = el.tagName === 'INPUT' || el.tagName === 'TEXTAREA';"
    " if (setter && field) setter.set.call(el, text);"
    " else el.textContent = text;"
    " el.dispatchEvent(new Event('input', {bubbles: true}));"
    " el.dispatchEvent(new Event('change', {bubbles: true})); return true})"
)


def _short(text: object) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= MAX_TEXT else value[: MAX_TEXT - 1] + "…"


def _console_text(params: dict[str, Any]) -> str:
    parts = []
    for argument in params.get("args") or []:
        if not isinstance(argument, dict):
            continue
        value = argument.get("value", argument.get("description", argument.get("type")))
        parts.append(str(value))
    return _short(" ".join(parts))


def _drain(queue: asyncio.Queue[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


class CheckPageTool:
    hard_cancellable = False
    _SPEC = ToolSpec(
        name="check_page",
        description=(
            "Open a web page of the project in a headless browser and see it as a person "
            "would: a screenshot (attached for you to look at), errors and warnings in the "
            "console, uncaught exceptions, failed requests and HTTP errors, and the page "
            "title. Use it after changing a web interface: start the dev server first (a "
            "background job), then check the page it serves, e.g. http://localhost:5173. "
            "steps click, type or wait before the screenshot (CSS selectors); wait_for then "
            "waits until a selector appears. viewport 'mobile' is a 390x844 phone. The screenshot "
            "is also saved under .agent/screenshots for the user."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "minLength": 1, "maxLength": 2048},
                "viewport": {"type": "string", "enum": ["desktop", "mobile"]},
                "wait_for": {"type": "string", "minLength": 1, "maxLength": 300},
                "full_page": {"type": "boolean"},
                "steps": {
                    "type": "array",
                    "maxItems": MAX_STEPS,
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["click", "type", "wait"]},
                            "selector": {"type": "string", "maxLength": 300},
                            "text": {"type": "string", "maxLength": 2000},
                            "ms": {"type": "integer", "minimum": 0, "maximum": 5000},
                        },
                        "required": ["action"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        side_effect="network",
        capability=Capability.NETWORK_READ,
    )

    def __init__(
        self,
        workspace: Path,
        *,
        browser: Callable[[], ManagedBrowser] = ManagedBrowser,
    ) -> None:
        self.paths = WorkspacePaths(workspace)
        self._browser = browser

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await self._run(arguments, None)

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        return await self._run(arguments, context)

    async def _run(self, arguments: dict[str, Any], context: ToolExecutionContext | None) -> str:
        validate_tool_arguments(self._SPEC, arguments)
        url = str(arguments["url"]).strip()
        if urlsplit(url).scheme not in {"http", "https", "file"}:
            raise ToolArgumentError("url must be an http(s) or file address")
        browser = self._browser()
        try:
            try:
                endpoint = await browser.ensure_endpoint()
            except ManagedBrowserError as error:
                raise ToolError(str(error)) from None
            session = CdpSession(endpoint, timeout=15.0)
            await session.connect()
            target_id: str | None = None
            try:
                created = await session.command("Target.createTarget", {"url": "about:blank"})
                target_id = str(created.get("targetId") or "")
                attached = await session.command(
                    "Target.attachToTarget", {"targetId": target_id, "flatten": True}
                )
                session.session_id = str(attached.get("sessionId") or "")
                report, image = await self._inspect(session, url, arguments)
            finally:
                session.session_id = None
                if target_id:
                    with contextlib.suppress(Exception):
                        await session.command("Target.closeTarget", {"targetId": target_id}, 3)
                await session.aclose()
        except BrowserError as error:
            raise ToolError(f"the browser could not check the page: {error}") from None
        finally:
            with contextlib.suppress(Exception):
                await browser.aclose()
        if image is not None:
            report["screenshot"] = self._save(image)
            if context is not None and context.record_artifact is not None:
                # As attach_image: the image goes to the model with the result, and the event
                # is what the store keeps it by.
                digest = hashlib.sha256(image).hexdigest()
                await context.record_artifact(BinaryArtifact(digest, image))
                await context.record_event(
                    Event(
                        session_id=context.session_id,
                        type="image.attached",
                        data={
                            "attempt_id": context.attempt_id,
                            "path": report["screenshot"],
                            "media_type": "image/png"
                            if image.startswith(b"\x89PNG")
                            else "image/jpeg",
                            "sha256": digest,
                            "bytes": len(image),
                        },
                        causation_id=context.started_event_id,
                        correlation_id=context.correlation_id,
                    )
                )
        return json_result(report)

    def _save(self, image: bytes) -> str:
        folder = self.paths.resolve(str(SCREENSHOTS))
        folder.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        extension = "png" if image.startswith(b"\x89PNG") else "jpg"
        destination = folder / f"check-{stamp}.{extension}"
        counter = 2
        while destination.exists():
            destination = folder / f"check-{stamp}-{counter}.{extension}"
            counter += 1
        destination.write_bytes(image)
        return self.paths.relative(destination)

    async def _inspect(
        self, session: CdpSession, url: str, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], bytes | None]:
        console = session.subscribe("Runtime.consoleAPICalled")
        exceptions = session.subscribe("Runtime.exceptionThrown")
        logs = session.subscribe("Log.entryAdded")
        sent = session.subscribe("Network.requestWillBeSent")
        responses = session.subscribe("Network.responseReceived")
        finished = session.subscribe("Network.loadingFinished")
        failed = session.subscribe("Network.loadingFailed")
        loaded = session.subscribe("Page.loadEventFired")
        # Their own copies of the request events, to tell when the page has gone quiet.
        traffic = (
            session.subscribe("Network.requestWillBeSent"),
            session.subscribe("Network.loadingFinished"),
            session.subscribe("Network.loadingFailed"),
        )
        for domain in ("Page", "Runtime", "Log", "Network"):
            await session.command(f"{domain}.enable")
        width, height, mobile = VIEWPORTS[str(arguments.get("viewport", "desktop"))]
        await session.command(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": mobile},
        )
        navigation = await session.command("Page.navigate", {"url": url}, LOAD_SECONDS)
        if navigation.get("errorText"):
            return {
                "url": url,
                "loaded": False,
                "error": navigation["errorText"],
                "hint": (
                    "The page did not load. If it is the project's dev server, start it first "
                    "(as a background job) and check the address and port it prints."
                ),
            }, None
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(loaded.get(), LOAD_SECONDS)
        open_requests: set[str] = set()
        await self._settle(traffic, open_requests)

        notes: list[str] = []
        for index, step in enumerate(arguments.get("steps") or [], start=1):
            note = await self._step(session, step)
            if note:
                notes.append(f"step {index}: {note}")
            await self._settle(traffic, open_requests)
        selector = arguments.get("wait_for")
        if isinstance(selector, str) and not await self._wait_for(session, selector):
            notes.append(f"wait_for: {selector!r} did not appear within {WAIT_FOR_SECONDS:g} s")

        title = await self._value(session, "document.title")
        final_url = await self._value(session, "location.href")
        image = await self._screenshot(session, bool(arguments.get("full_page")), width)

        console_items = [
            {"level": item.get("type"), "text": _console_text(item)}
            for item in _drain(console)
            if item.get("type") in {"error", "warning", "assert"}
        ]
        exception_items = [
            _short(
                (item.get("exceptionDetails") or {}).get("exception", {}).get("description")
                or (item.get("exceptionDetails") or {}).get("text")
            )
            for item in _drain(exceptions)
        ]
        log_items = [
            {
                "level": (item.get("entry") or {}).get("level"),
                "text": _short((item.get("entry") or {}).get("text")),
            }
            for item in _drain(logs)
            if (item.get("entry") or {}).get("level") in {"error", "warning"}
            # A failed load is in http_errors already.
            and not str((item.get("entry") or {}).get("text", "")).startswith(
                "Failed to load resource"
            )
        ]
        _drain(finished)
        requests = {
            str(item.get("requestId")): str((item.get("request") or {}).get("url", ""))
            for item in _drain(sent)
        }
        failed_items = [
            {
                "url": _short(requests.get(str(item.get("requestId")), "")),
                "error": item.get("errorText"),
            }
            for item in _drain(failed)
            if not item.get("canceled")
        ]
        http_errors = [
            {
                "url": _short((item.get("response") or {}).get("url")),
                "status": (item.get("response") or {}).get("status"),
            }
            for item in _drain(responses)
            if int((item.get("response") or {}).get("status") or 0) >= 400
            # The browser asks for it by itself; a site without one is not broken.
            and not urlsplit(str((item.get("response") or {}).get("url", ""))).path.endswith(
                "/favicon.ico"
            )
        ]
        report: dict[str, Any] = {
            "url": final_url or url,
            "title": title,
            "loaded": True,
            "viewport": f"{width}x{height}",
            "console": console_items[:MAX_ITEMS],
            "exceptions": exception_items[:MAX_ITEMS],
            "browser_log": log_items[:MAX_ITEMS],
            "failed_requests": failed_items[:MAX_ITEMS],
            "http_errors": http_errors[:MAX_ITEMS],
        }
        if notes:
            report["notes"] = notes
        problems = len(console_items) + len(exception_items) + len(failed_items) + len(http_errors)
        report["summary"] = (
            "No errors in the console or the network."
            if problems == 0
            else f"{problems} problem(s) found; see the lists."
        )
        return report, image

    async def _settle(
        self,
        traffic: tuple[
            asyncio.Queue[dict[str, Any]],
            asyncio.Queue[dict[str, Any]],
            asyncio.Queue[dict[str, Any]],
        ],
        open_requests: set[str],
    ) -> None:
        """Waits until no request has been open for a moment (or gives up after a while)."""
        sent, finished, failed = traffic
        quiet_since = time.monotonic()
        deadline = time.monotonic() + SETTLE_SECONDS
        while time.monotonic() < deadline:
            open_requests.update(str(item.get("requestId")) for item in _drain(sent))
            for item in _drain(finished) + _drain(failed):
                open_requests.discard(str(item.get("requestId")))
            if open_requests:
                quiet_since = time.monotonic()
            elif time.monotonic() - quiet_since >= QUIET_SECONDS:
                return
            await asyncio.sleep(0.1)

    async def _value(self, session: CdpSession, expression: str) -> Any:
        response = await session.command(
            "Runtime.evaluate", {"expression": expression, "returnByValue": True}
        )
        result = response.get("result")
        return result.get("value") if isinstance(result, dict) else None

    async def _wait_for(self, session: CdpSession, selector: str) -> bool:
        deadline = time.monotonic() + WAIT_FOR_SECONDS
        expression = f"document.querySelector({_js(selector)}) !== null"
        while time.monotonic() < deadline:
            if await self._value(session, expression) is True:
                return True
            await asyncio.sleep(0.2)
        return False

    async def _step(self, session: CdpSession, step: dict[str, Any]) -> str | None:
        action = step.get("action")
        if action == "wait":
            await asyncio.sleep(min(5000, int(step.get("ms", 500))) / 1000)
            return None
        selector = step.get("selector")
        if not isinstance(selector, str) or not selector:
            return f"{action} needs a selector"
        if action == "click":
            clicked = await self._value(
                session,
                f"(() => {{const el = document.querySelector({_js(selector)});"
                " if (!el) return false; el.scrollIntoView({block: 'center'}); el.click();"
                " return true})()",
            )
            return None if clicked else f"no element matches {selector!r}"
        typed = await self._value(
            session, f"{_TYPE_SCRIPT}({_js(selector)}, {_js(str(step.get('text', '')))})"
        )
        return None if typed else f"no element matches {selector!r}"

    async def _screenshot(self, session: CdpSession, full_page: bool, width: int) -> bytes:
        params: dict[str, Any] = {"format": "png"}
        if full_page:
            height = await self._value(
                session,
                "Math.max(document.documentElement.scrollHeight,"
                " document.body ? document.body.scrollHeight : 0)",
            )
            params["captureBeyondViewport"] = True
            params["clip"] = {
                "x": 0,
                "y": 0,
                "width": width,
                "height": min(MAX_PAGE_HEIGHT, int(height or 0) or 800),
                "scale": 1,
            }
        capture = await session.command("Page.captureScreenshot", params, 30)
        image = base64.b64decode(str(capture.get("data") or ""))
        if len(image) > MAX_IMAGE_BYTES:
            params["format"], params["quality"] = "jpeg", 70
            capture = await session.command("Page.captureScreenshot", params, 30)
            image = base64.b64decode(str(capture.get("data") or ""))
        if not image:
            raise ToolError("the browser returned no screenshot")
        return image


def _js(value: str) -> str:
    return json.dumps(value)


__all__ = ["CheckPageTool"]
