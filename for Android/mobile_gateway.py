"""Authenticated Android HTTP gateway with legacy and mobile task routes."""

from __future__ import annotations

import asyncio
import base64
import binascii
import concurrent.futures
import contextlib
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sys
import threading
import time
import traceback
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO
from urllib.parse import parse_qs, quote, urlparse
from weakref import WeakValueDictionary

from mobile_artifacts import write_workspace_file_coordinated
from mobile_images import attachment_media_type, attachment_receipt
from mobile_protocol import (
    MobileTaskRequest,
    parse_mobile_task_request,
    parse_mobile_workspace_request,
)
from mobile_runtime_controller import (
    MobileRuntimeController,
    MobileRuntimeNotReady,
    configured_mobile_context_summary,
    experimental_mobile_context_summary,
)
from mobile_workspace import (
    WorkspaceContentTooLargeError,
    WorkspaceStorageFullError,
    archived_sessions,
    import_workspace_upload,
    list_workspace_files,
    open_workspace_download,
    read_workspace_file,
    runtime_workspace,
    save_session_alias,
    save_session_archived,
    session_aliases,
    workspace_upload_filename,
    workspace_upload_media_type,
)
from mobile_workspaces import MobileScopedRuntime, MobileWorkspaceCatalog

from agent_workspace.application.runtime import ApplicationRuntime
from agent_workspace.core.events import Event
from agent_workspace.core.models import Autonomy
from agent_workspace.providers.reasoning import supported_reasoning_efforts
from agent_workspace.storage.durable import fsync_directory
from agent_workspace.tools.base import ConcurrentModificationError, ToolArgumentError, ToolError
from agent_workspace.tools.filesystem import _open_identity_checked
from agent_workspace.tools.paths import WorkspacePaths

_MAX_BODY_BYTES = 1024 * 1024
_MAX_ATTACHMENT_JSON_BYTES = 6 * 1024 * 1024
_MAX_ATTACHMENT_BYTES = 4 * 1024 * 1024
_UPLOAD_RECEIPT_DIRECTORY = ".agent-upload-request"
_UPLOAD_RECEIPT_FILENAME = "receipt.json"
_MAX_UPLOAD_RECEIPT_BYTES = 64 * 1024
_RUN_TIMEOUT_SECONDS = 900.0
_MOBILE_OPERATION_TIMEOUT_SECONDS = 30.0
_ACTIVE_TASK_STATES = frozenset({"queued", "running", "waiting_approval"})
_IDENTITY_CHALLENGE = re.compile(r"[A-Za-z0-9_-]{32,128}")
_IDENTITY_CONTEXT = b"agent-workspace-mobile-identity-v1\n"


class WorkspaceBusyError(RuntimeError):
    """A workspace cannot be removed while one of its conversations has an unfinished task."""


class ProviderRestartRequired(RuntimeError):
    """The requested provider change needs an engine restart (on-device model in or out)."""


class SessionBusyError(RuntimeError):
    """A conversation cannot be archived while it has an unfinished task."""


class AttachmentTooLargeError(ValueError):
    pass


class AttachmentInUseError(ValueError):
    pass


def _upload_identifier(session_id: str, request_id: str) -> str:
    binding = json.dumps([session_id, request_id], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(binding.encode()).hexdigest()[:32]


def _upload_receipt_path(path: Path) -> Path:
    return path.parent / _UPLOAD_RECEIPT_DIRECTORY / _UPLOAD_RECEIPT_FILENAME


def _read_upload_receipt(paths: WorkspacePaths, target: Path) -> dict[str, Any] | None:
    receipt = _upload_receipt_path(target)
    try:
        paths.resolve(receipt)
        with _open_identity_checked(receipt, "rb") as stream:
            WorkspacePaths.assert_safe_file_descriptor(stream.fileno(), receipt)
            raw = stream.read(_MAX_UPLOAD_RECEIPT_BYTES + 1)
        if len(raw) > _MAX_UPLOAD_RECEIPT_BYTES:
            raise ValueError("upload receipt is too large")
        value = json.loads(raw.decode("utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ConcurrentModificationError("upload request receipt is invalid") from error
    if not isinstance(value, dict):
        raise ConcurrentModificationError("upload request receipt is invalid")
    return value


def _remove_upload_receipt(
    paths: WorkspacePaths, target: Path, expected: Mapping[str, Any]
) -> None:
    receipt = _upload_receipt_path(target)
    try:
        paths.resolve(receipt)
        value = _read_upload_receipt(paths, target)
        if value is None:
            return
        keys = (
            "session_id",
            "request_id",
            "name",
            "path",
            "size",
            "sha256",
            "media_type",
            "upload_media_type",
        )
        if type(value.get("version")) is not int or value["version"] != 1 or any(
            value.get(key) != expected.get(key) for key in keys
        ):
            return
        receipt.unlink(missing_ok=True)
        receipt.parent.rmdir()
        fsync_directory(target.parent)
    except FileNotFoundError:
        return


class _ChunkedUploadReader:
    """Decode HTTP chunks while retaining only one bounded read from the socket."""

    def __init__(self, source: BinaryIO) -> None:
        self.source = source
        self.remaining = 0
        self.finished = False

    def read(self, size: int) -> bytes:
        if self.finished:
            return b""
        if not self.remaining:
            line = self.source.readline(8193)
            if len(line) > 8192 or not line.endswith(b"\r\n"):
                raise ValueError("invalid chunked upload body")
            raw_size = line[:-2].split(b";", 1)[0]
            if not re.fullmatch(rb"[0-9a-fA-F]{1,16}", raw_size):
                raise ValueError("invalid chunked upload size")
            self.remaining = int(raw_size, 16)
            if not self.remaining:
                total = 0
                while True:
                    trailer = self.source.readline(8193)
                    total += len(trailer)
                    if len(trailer) > 8192 or total > 64 * 1024 or not trailer.endswith(b"\r\n"):
                        raise ValueError("invalid chunked upload trailer")
                    if trailer == b"\r\n":
                        self.finished = True
                        return b""
        chunk = self.source.read(min(size, self.remaining))
        if not chunk:
            raise ValueError("incomplete upload body")
        self.remaining -= len(chunk)
        if not self.remaining and self.source.read(2) != b"\r\n":
            raise ValueError("invalid chunked upload body")
        return chunk


@dataclass(frozen=True, slots=True)
class MobileAccessToken:
    token: str
    scopes: frozenset[str]
    expires_at: float | None = None
    revoked: bool = False

    def allows(self, scope: str | None, *, now: float) -> bool:
        if self.revoked or (self.expires_at is not None and now >= self.expires_at):
            return False
        return scope is None or scope in self.scopes


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


_GATEWAY_ERROR_LOG_BYTES = 256 * 1024


def _record_gateway_error(method: str, path: str, exc: BaseException) -> None:
    """Append a request failure to <data>/logs/gateway-errors.log (bounded) and stderr."""
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    entry = f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} {method} {path}\n{text}\n"
    print(entry, file=sys.stderr, flush=True)
    data_dir = os.getenv("AGENT_WORKSPACE_DATA_DIR")
    if not data_dir:
        return
    with suppress(OSError):
        log = Path(data_dir) / "logs" / "gateway-errors.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        if log.exists() and log.stat().st_size > _GATEWAY_ERROR_LOG_BYTES:
            log.replace(log.with_suffix(".log.1"))
        with log.open("a", encoding="utf-8") as handle:
            handle.write(entry)


class _Handler(BaseHTTPRequestHandler):
    server_version = "AgentWorkspaceMobileGateway/0.1"

    @property
    def _api(self) -> MobileGateway:
        return self.server.api  # type: ignore[attr-defined,no-any-return]

    def log_message(self, format: str, *args: object) -> None:
        return

    def end_headers(self) -> None:
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def _validate_host(self) -> bool:
        host_header = self.headers.get("Host", "").strip()
        if not host_header:
            return False
        if host_header.startswith("["):
            closing_idx = host_header.find("]")
            raw_host = host_header[: closing_idx + 1] if closing_idx != -1 else host_header
        else:
            raw_host = host_header.split(":", 1)[0]
        allowed = {"127.0.0.1", "localhost", "[::1]", "::1"}
        configured = self._api.host.strip().lower()
        allowed.add(configured)
        if configured.startswith("[") and configured.endswith("]"):
            allowed.add(configured[1:-1])
        else:
            allowed.add(f"[{configured}]")
        return raw_host.lower() in allowed

    def _authorized(self, scope: str | None = None) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        return self._api.validate_token(header.removeprefix("Bearer "), scope=scope)

    def _reply(self, status: int, payload: object) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _reject_request(self, status: int, payload: object) -> None:
        self._reply(status, payload)
        self.wfile.flush()
        # Closing with unread bytes can reset the error response on Windows.
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return
        remaining = min(max(length, 0), _MAX_ATTACHMENT_JSON_BYTES + _MAX_BODY_BYTES)
        deadline = time.monotonic() + 2.0
        previous_timeout = self.connection.gettimeout()
        try:
            while remaining and time.monotonic() < deadline:
                self.connection.settimeout(max(deadline - time.monotonic(), 0.001))
                chunk = self.rfile.read(min(remaining, 64 * 1024))
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            pass
        finally:
            self.connection.settimeout(previous_timeout)

    def _read_json(self, max_bytes: int = _MAX_BODY_BYTES) -> dict[str, Any] | None:
        raw_length = self.headers.get("Content-Length", "0").strip()
        try:
            length = int(raw_length) if raw_length else 0
        except ValueError:
            self._reply(400, {"error": "invalid Content-Length"})
            return None
        if length < 0:
            self._reply(400, {"error": "invalid Content-Length"})
            return None
        if length > max_bytes:
            self._reject_request(413, {"error": "payload too large"})
            return None
        try:
            payload: Any = json.loads(self.rfile.read(length)) if length else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._reply(400, {"error": "invalid JSON"})
            return None
        if not isinstance(payload, dict):
            self._reply(400, {"error": "body must be a JSON object"})
            return None
        return payload

    def send_response(self, code: int, message: str | None = None) -> None:
        self._response_started = True
        super().send_response(code, message)

    def do_GET(self) -> None:
        self._guarded(self._handle_get)

    def do_POST(self) -> None:
        self._guarded(self._handle_post)

    def _guarded(self, handler: Any) -> None:
        # An exception escaping a handler makes http.server drop the connection without a reply;
        # the WebView then only reports "Failed to fetch". Answer with a JSON error instead, and
        # keep the traceback so the cause can be found.
        self._response_started = False
        try:
            handler()
        except (BrokenPipeError, ConnectionResetError):
            return  # the client went away; there is no one to answer
        except Exception as exc:  # noqa: BLE001 - last line of defence for a single request
            busy = isinstance(exc, (TimeoutError, concurrent.futures.TimeoutError))
            _record_gateway_error(self.command, urlparse(self.path).path, exc)
            if self._response_started:
                return  # part of a response is already sent; the client sees it end early
            code = "engine_busy" if busy else "internal_error"
            with suppress(OSError):
                self._reply(503 if busy else 500, {"error": code, "code": code, "retryable": True})

    def _handle_get(self) -> None:
        if not self._validate_host():
            self._reply(400, {"error": "invalid host header"})
            return
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query, keep_blank_values=True)
        query_token = query.get("token", [""])[0]
        if path == "/mobile/identity":
            # Unauthenticated on purpose: the app proves it reached this engine (not another process
            # squatting on the port) before it reveals the token or loads the console.
            challenge = query.get("challenge", [""])[0]
            if not _IDENTITY_CHALLENGE.fullmatch(challenge):
                self._reply(400, {"error": "invalid challenge"})
                return
            self._reply(200, {"proof": self._api.identity_proof(challenge)})
            return
        if path == "/console":
            if not self._authorized("read") and not self._api.validate_token(
                query_token, scope="read"
            ):
                self._reply(401, {"error": "unauthorized"})
                return
            body = (self._api.console_html or "<html><body>Agent Workspace</body></html>").encode(
                "utf-8"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        asset = self._api.static_assets.get(path)
        if asset is not None:
            if not self._authorized("read") and not self._api.validate_token(
                query_token, scope="read"
            ):
                self._reply(401, {"error": "unauthorized"})
                return
            content_type, body = asset
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not self._authorized("read"):
            self._reply(401, {"error": "unauthorized"})
            return
        if path == "/health":
            self._reply(200, {"ok": True, "mobile": True})
            return
        if path == "/mobile/runtime":
            self._reply(200, {**self._api.controller.status(), "idempotent_submissions": True})
            return
        if path == "/mobile/settings":
            self._reply(200, self._api.effective_settings())
            return
        if path == "/mobile/workspaces":
            self._reply(200, self._api.list_workspaces())
            return
        if path.rstrip("/") == "/mobile/attachments":
            try:
                document, _ = attachment_receipt(
                    self._api.scoped_runtime(session_id=query.get("session_id", [""])[0]),
                    query.get("session_id", [""])[0],
                    query.get("path", [""])[0],
                    retain_content=False,
                )
            except KeyError:
                self._reply(404, {"error": "unknown session attachment"})
                return
            except (TypeError, ValueError) as error:
                self._reply(400, {"error": " ".join(str(error).split())[:2000]})
                return
            except OSError:
                self._reply(500, {"error": "could not verify attachment"})
                return
            self._reply(200, document)
            return
        if self._api.management is not None:
            managed = self._api._run_coro(
                self._api.management.dispatch("GET", path, query), _MOBILE_OPERATION_TIMEOUT_SECONDS
            )
            if managed is not None:
                self._reply(*managed)
                return
        if path == "/mobile/workspace/download":
            response_started = False
            try:
                with open_workspace_download(
                    self._api.scoped_runtime(
                        query.get("workspace_id", [None])[0],
                        session_id=query.get("session_id", [None])[0],
                    ),
                    query.get("path", [""])[0],
                    query.get("sha256", [None])[0],
                ) as (stream, document):
                    self.send_response(200)
                    self.send_header("Content-Type", document["mime_type"])
                    self.send_header("Content-Length", str(document["size"]))
                    filename = quote(document["name"], safe="")
                    self.send_header(
                        "Content-Disposition", f"attachment; filename*=UTF-8''{filename}"
                    )
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    response_started = True
                    remaining = document["size"]
                    while remaining:
                        chunk = stream.read(min(remaining, 64 * 1024))
                        if not chunk:
                            self.close_connection = True
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (FileNotFoundError, KeyError):
                self._reply(404, {"error": "workspace file was not found"})
            except ConcurrentModificationError as exc:
                self._reply(409, {"error": str(exc)})
            except (TypeError, ValueError) as exc:
                self._reply(400, {"error": " ".join(str(exc).split())[:2000]})
            except (OSError, ToolError):
                if response_started:
                    self.close_connection = True
                else:
                    self._reply(500, {"error": "could not read workspace file"})
            return
        if path in {"/mobile/workspace/files", "/mobile/workspace/file"}:
            try:
                relative = query.get("path", [""])[0]
                runtime = self._api.scoped_runtime(
                    query.get("workspace_id", [None])[0],
                    session_id=query.get("session_id", [None])[0],
                )
                document = (
                    list_workspace_files(runtime, relative)
                    if path.endswith("/files")
                    else read_workspace_file(runtime, relative, query.get("sha256", [None])[0])
                )
            except (FileNotFoundError, KeyError):
                self._reply(404, {"error": "workspace file or directory was not found"})
                return
            except ConcurrentModificationError as exc:
                self._reply(409, {"error": str(exc)})
                return
            except (TypeError, ValueError) as exc:
                self._reply(400, {"error": " ".join(str(exc).split())[:2000]})
                return
            except (OSError, ToolError):
                self._reply(500, {"error": "could not read workspace files"})
                return
            self._reply(200, document)
            return
        if path == "/mobile/usage":
            from mobile_usage import usage_summary

            try:
                days = _query_int(query, "days", 0, minimum=1) if "days" in query else None
                if days is not None and days > 3660:
                    raise ValueError("days must be at most 3660")
                document = usage_summary(
                    self._api.scoped_runtime(
                        query.get("workspace_id", [None])[0],
                        session_id=query.get("session_id", [None])[0],
                    ),
                    session_id=query.get("session_id", [None])[0],
                    days=days,
                )
            except KeyError:
                self._reply(404, {"error": "unknown session"})
                return
            except ValueError as exc:
                self._reply(400, {"error": str(exc)})
                return
            except OSError:
                self._reply(500, {"error": "could not read usage"})
                return
            self._reply(200, document)
            return
        if path == "/mobile/sessions/search":
            try:
                limit = _query_int(query, "limit", 20, minimum=1)
                if limit > 50:
                    raise ValueError("limit must be at most 50")
                results = self._api.search_sessions(
                    query.get("q", [""])[0],
                    limit,
                    workspace_id=query.get("workspace_id", [None])[0],
                )
            except KeyError:
                self._reply(404, {"error": "unknown workspace"})
                return
            except ValueError as exc:
                self._reply(400, {"error": str(exc)})
                return
            self._reply(200, {"results": results})
            return
        if path in {"/mobile/sync", "/mobile/reconnect"}:
            try:
                after = _query_int(query, "after", 0, minimum=0)
                limit = _query_int(query, "limit", 200, minimum=1)
                cursor = query.get("cursor", [None])[0]
            except ValueError as exc:
                self._reply(400, {"error": str(exc)})
                return
            try:
                snapshot = self._api.controller.sync(
                    after=after, limit=min(limit, 1000), cursor=cursor
                )
            except ValueError as exc:
                self._reply(400, {"error": str(exc)})
                return
            self._reply(200, snapshot)
            return

        parts = [part for part in path.split("/") if part]
        if parts == ["sessions"]:
            try:
                sessions = self._api.list_sessions(query.get("workspace_id", [None])[0])
            except KeyError:
                self._reply(404, {"error": "unknown workspace"})
                return
            except ValueError as exc:
                self._reply(400, {"error": str(exc)})
                return
            self._reply(200, {"sessions": sessions})
            return
        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "events":
            if not self._api.session_exists(parts[1]):
                self._reply(404, {"error": "unknown session"})
                return
            self._reply(200, {"events": self._api.list_events(parts[1])})
            return
        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "comments":
            if not self._api.session_exists(parts[1]):
                self._reply(404, {"error": "unknown session"})
                return
            self._reply(200, {"comments": self._api.list_comments(parts[1])})
            return
        if len(parts) == 4 and parts[0] == "sessions" and parts[2:] == ["events", "stream"]:
            if not self._api.session_exists(parts[1]):
                self._reply(404, {"error": "unknown session"})
                return
            self._stream_legacy_events(parts[1], query)
            return
        if parts == ["mobile", "tasks"]:
            session_id = query.get("session_id", [None])[0]
            workspace_id = query.get("workspace_id", [None])[0]
            try:
                tasks = self._api.controller.list(session_id)
                if workspace_id is not None:
                    selected = self._api.workspace_catalog.get(workspace_id)
                    tasks = [
                        task
                        for task in tasks
                        if self._api.runtime.store.get_session(task.session_id).workspace
                        == selected.path
                    ]
            except KeyError:
                self._reply(404, {"error": "unknown workspace or session"})
                return
            self._reply(
                200,
                {"tasks": [task.to_dict() for task in tasks], "services": _services_summary()},
            )
            return
        if parts == ["mobile", "approvals"]:
            task_id = query.get("task_id", [None])[0]
            self._reply(200, {"approvals": self._api.controller.pending_approvals(task_id)})
            return
        if len(parts) == 3 and parts[:2] == ["mobile", "tasks"]:
            try:
                task = self._api.controller.get(parts[2])
            except KeyError:
                self._reply(404, {"error": "unknown task"})
                return
            self._reply(
                200,
                {
                    "task": task.to_dict(),
                    "approvals": self._api.controller.pending_approvals(task.task_id),
                },
            )
            return
        if len(parts) == 4 and parts[:2] == ["mobile", "tasks"] and parts[3] == "events":
            try:
                events = self._api.controller.events(
                    parts[2],
                    _query_int(query, "after", 0, minimum=0),
                )
            except KeyError:
                self._reply(404, {"error": "unknown task"})
                return
            except ValueError as exc:
                self._reply(400, {"error": str(exc)})
                return
            self._reply(200, {"events": [event.to_dict() for event in events]})
            return
        if (
            len(parts) == 5
            and parts[:2] == ["mobile", "tasks"]
            and parts[3:] == ["events", "stream"]
        ):
            try:
                self._api.controller.get(parts[2])
                after = _query_int(query, "after", 0, minimum=0)
                max_events = _query_int(query, "max_events", 0, minimum=0)
                max_seconds = _query_float(query, "max_seconds", 30.0, minimum=0.1)
            except KeyError:
                self._reply(404, {"error": "unknown task"})
                return
            except ValueError as exc:
                self._reply(400, {"error": str(exc)})
                return
            self._stream_mobile_events(
                parts[2],
                after_sequence=after,
                max_events=max_events,
                max_seconds=min(max_seconds, 120.0),
            )
            return
        self._reply(404, {"error": "not found"})

    def _stream_mobile_events(
        self,
        task_id: str,
        *,
        after_sequence: int,
        max_events: int,
        max_seconds: float,
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        sent = 0
        limit = max_events if max_events > 0 else 1_000_000
        deadline = time.monotonic() + max_seconds
        try:
            while sent < limit and time.monotonic() < deadline:
                events = self._api.controller.events(task_id, after_sequence)
                if events:
                    for event in events:
                        if sent >= limit:
                            break
                        payload = json.dumps(
                            event.to_dict(), ensure_ascii=False, separators=(",", ":")
                        )
                        self.wfile.write(
                            (
                                f"id: {event.sequence}\nevent: {event.event_type}"
                                f"\ndata: {payload}\n\n"
                            ).encode()
                        )
                        self.wfile.flush()
                        after_sequence = event.sequence
                        sent += 1
                    continue
                task = self._api.controller.get(task_id)
                if task.state.value in {"succeeded", "failed", "cancelled"}:
                    break
                time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError, OSError, KeyError):
            return

    def _stream_legacy_events(self, session_id: str, query: Mapping[str, list[str]]) -> None:
        try:
            after_sequence = _query_int(query, "after", 0, minimum=0)
            max_events = _query_int(query, "max_events", 0, minimum=0)
            max_seconds = _query_float(query, "max_seconds", 10.0, minimum=0.1)
        except ValueError as exc:
            self._reply(400, {"error": str(exc)})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        sent = 0
        limit = max_events if max_events > 0 else 1_000_000
        deadline = time.monotonic() + min(max_seconds, 120.0)
        try:
            while sent < limit and time.monotonic() < deadline:
                events = [
                    event
                    for event in self._api.runtime.store.list_events(session_id)
                    if (event.sequence or 0) > after_sequence
                    and not event.type.startswith("mobile.artifacts.")
                ]
                if events:
                    for event in events:
                        if sent >= limit:
                            break
                        payload = json.dumps(
                            {
                                "id": event.id,
                                "type": event.type,
                                "sequence": event.sequence,
                                "created_at": event.created_at,
                                "data": event.data,
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        self.wfile.write(f"data: {payload}\n\n".encode())
                        self.wfile.flush()
                        if event.sequence is not None:
                            after_sequence = max(after_sequence, event.sequence)
                        sent += 1
                else:
                    time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def do_DELETE(self) -> None:
        if not self._validate_host():
            self._reject_request(400, {"error": "invalid host header"})
            return
        if not self._authorized("write"):
            self._reject_request(401, {"error": "unauthorized"})
            return
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") != "/mobile/attachments":
            self._reply(404, {"error": "not found"})
            return
        parameters = parse_qs(parsed.query)
        try:
            result = self._api.delete_mobile_attachment(
                parameters.get("session_id", [""])[0], parameters.get("path", [""])[0]
            )
        except KeyError:
            self._reply(404, {"error": "unknown attachment"})
            return
        except AttachmentInUseError as exc:
            self._reply(409, {"error": str(exc)})
            return
        except (TypeError, ValueError) as exc:
            self._reply(400, {"error": " ".join(str(exc).split())[:2000]})
            return
        except OSError:
            self._reply(500, {"error": "could not remove attachment"})
            return
        self._reply(200, result)

    def _handle_post(self) -> None:
        path = urlparse(self.path).path
        if not self._validate_host():
            self._reject_request(400, {"error": "invalid host header"})
            return
        approval_scope = "approval" if path.rstrip("/").endswith("/resolve") else "write"
        if not self._authorized(approval_scope):
            self._reject_request(401, {"error": "unauthorized"})
            return
        parts = [part for part in path.split("/") if part]
        if parts == ["mobile", "attachments", "upload"]:
            self._upload_attachment()
            return
        payload = self._read_json(
            _MAX_ATTACHMENT_JSON_BYTES if parts == ["mobile", "attachments"] else _MAX_BODY_BYTES
        )
        if payload is None:
            return
        if path.startswith(
            (
                "/mobile/extensions/",
                "/mobile/android-system",
                "/mobile/provider/",
                "/mobile/services/",
                "/mobile/browser/",
                "/mobile/notification-rules",
            )
        ) and not self._authorized("approval"):
            self._reply(401, {"error": "approval scope is required"})
            return
        if parts == ["mobile", "provider", "apply"]:
            try:
                self._reply(200, self._api.apply_provider(payload))
            except ProviderRestartRequired as exc:
                self._reply(409, {"error": str(exc), "code": "restart_required"})
            except (TypeError, ValueError) as exc:
                self._reply(400, {"error": " ".join(str(exc).split())[:1500]})
            return
        if self._api.management is not None:
            managed = self._api._run_coro(
                self._api.management.dispatch("POST", path, payload),
                _MOBILE_OPERATION_TIMEOUT_SECONDS,
            )
            if managed is not None:
                self._reply(*managed)
                return
        if parts == ["mobile", "workspace", "file"]:
            try:
                document = self._api._run_coro(
                    write_workspace_file_coordinated(
                        self._api.scoped_runtime(
                            payload.get("workspace_id"), session_id=payload.get("session_id")
                        ),
                        payload,
                    ),
                    _MOBILE_OPERATION_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                self._reply(
                    503, {"error": "workspace is busy; wait for the current tool before saving"}
                )
                return
            except WorkspaceContentTooLargeError as exc:
                self._reply(413, {"error": str(exc)})
                return
            except ConcurrentModificationError:
                self._reply(
                    409,
                    {"error": "file changed since it was opened; reload before saving"},
                )
                return
            except (FileNotFoundError, KeyError):
                self._reply(404, {"error": "workspace file or parent directory was not found"})
                return
            except (TypeError, ValueError, ToolArgumentError) as exc:
                self._reply(400, {"error": " ".join(str(exc).split())[:2000]})
                return
            except (OSError, ToolError):
                self._reply(500, {"error": "could not save workspace file"})
                return
            self._reply(200, document)
            return
        if parts == ["mobile", "workspaces"]:
            try:
                request = parse_mobile_workspace_request(payload)
                workspace = self._api.create_workspace(
                    request.name, request.path, create=request.create
                )
            except ConcurrentModificationError:
                self._reply(409, {"error": "workspace catalog changed; reload and try again"})
                return
            except ValueError as exc:
                self._reply(400, {"error": " ".join(str(exc).split())[:2000]})
                return
            except (OSError, ToolError):
                self._reply(500, {"error": "could not save workspace"})
                return
            self._reply(201, {"workspace": workspace})
            return
        if parts == ["mobile", "workspaces", "remove"]:
            workspace_id = payload.get("workspace_id")
            if not isinstance(workspace_id, str) or not workspace_id:
                self._reply(400, {"error": "workspace_id is required"})
                return
            try:
                self._api.remove_workspace(workspace_id)
            except KeyError:
                self._reply(404, {"error": "unknown workspace"})
                return
            except WorkspaceBusyError:
                self._reply(409, {"error": "workspace has running tasks; stop them first"})
                return
            except ConcurrentModificationError:
                self._reply(409, {"error": "workspace catalog changed; reload and try again"})
                return
            except ValueError as exc:
                self._reply(400, {"error": " ".join(str(exc).split())[:2000]})
                return
            except OSError:
                self._reply(500, {"error": "could not save workspace catalog"})
                return
            self._reply(200, {"removed": workspace_id, **self._api.list_workspaces()})
            return
        if parts == ["mobile", "usage", "pricing"]:
            from mobile_usage import save_pricing

            try:
                document = save_pricing(self._api.runtime, payload)
            except KeyError:
                self._reply(404, {"error": "unknown session"})
                return
            except ValueError as exc:
                self._reply(400, {"error": str(exc)})
                return
            except OSError:
                self._reply(500, {"error": "could not save pricing"})
                return
            self._reply(200, document)
            return
        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "rename":
            title = payload.get("title")
            if not isinstance(title, str) or not title.strip() or len(title) > 200:
                self._reply(400, {"error": "title is required (max 200 chars)"})
                return
            try:
                document = self._api.rename_session(parts[1], title.strip())
            except KeyError:
                self._reply(404, {"error": "unknown session"})
                return
            except ConcurrentModificationError:
                self._reply(409, {"error": "session presentation changed; retry the rename"})
                return
            except (OSError, ToolError, ValueError):
                self._reply(500, {"error": "could not rename session"})
                return
            self._reply(200, document)
            return
        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "archive":
            archived = payload.get("archived", True)
            if not isinstance(archived, bool):
                self._reply(400, {"error": "archived must be a boolean"})
                return
            try:
                document = self._api.archive_session(parts[1], archived)
            except KeyError:
                self._reply(404, {"error": "unknown session"})
                return
            except SessionBusyError:
                self._reply(409, {"error": "session has a running task; stop it first"})
                return
            except ConcurrentModificationError:
                self._reply(409, {"error": "session presentation changed; retry"})
                return
            except (OSError, ToolError, ValueError):
                self._reply(500, {"error": "could not archive session"})
                return
            self._reply(200, document)
            return
        if parts == ["mobile", "attachments"]:
            try:
                attachment = self._api.import_mobile_attachment(payload)
            except KeyError:
                self._reply(404, {"error": "unknown session"})
                return
            except AttachmentTooLargeError as exc:
                self._reply(413, {"error": str(exc)})
                return
            except (TypeError, ValueError) as exc:
                self._reply(400, {"error": " ".join(str(exc).split())[:2000]})
                return
            except OSError:
                self._reply(500, {"error": "could not import attachment"})
                return
            self._reply(201, attachment)
            return
        if parts == ["mobile", "reconnect"]:
            try:
                snapshot = self._api.reconnect_mobile()
            except (RuntimeError, ValueError) as exc:
                self._reply(409, {"error": " ".join(str(exc).split())[:2000]})
                return
            self._reply(200, snapshot)
            return
        if parts == ["mobile", "tasks"]:
            try:
                request = parse_mobile_task_request(payload)
                task = self._api.submit_mobile_task(request, request_id=payload.get("request_id"))
            except KeyError:
                self._reply(404, {"error": "unknown session"})
                return
            except MobileRuntimeNotReady as exc:
                self._reply(
                    409,
                    {
                        "error": " ".join(str(exc).split())[:2000],
                        "code": exc.code,
                        "retryable": exc.retryable,
                    },
                )
                return
            except (TypeError, ValueError) as exc:
                self._reply(400, {"error": " ".join(str(exc).split())[:2000]})
                return
            self._reply(202, {"task": task.to_dict()})
            return
        if len(parts) == 4 and parts[:2] == ["mobile", "tasks"] and parts[3] == "steer":
            prompt = payload.get("prompt")
            input_id = payload.get("input_id")
            if not isinstance(prompt, str) or not prompt.strip():
                self._reply(400, {"error": "prompt is required"})
                return
            if input_id is not None and not isinstance(input_id, str):
                self._reply(400, {"error": "input_id must be a string"})
                return
            try:
                received = self._api.steer_mobile_task(parts[2], prompt, input_id=input_id)
            except KeyError:
                self._reply(404, {"error": "unknown task"})
                return
            except RuntimeError as exc:
                # turn_not_active: the task finished or has not started its turn yet.
                # turn_input_full: too many unapplied messages are already waiting.
                code = str(exc) if str(exc) in {"turn_not_active", "turn_input_full"} else "steer_failed"
                self._reply(409, {"error": code, "code": code, "retryable": code == "turn_input_full"})
                return
            except ValueError as exc:
                self._reply(400, {"error": " ".join(str(exc).split())[:2000]})
                return
            self._reply(202, received)
            return
        if (
            len(parts) == 4
            and parts[:2] == ["mobile", "tasks"]
            and parts[3] in {"cancel", "resume"}
        ):
            try:
                task = (
                    self._api.cancel_mobile_task(parts[2])
                    if parts[3] == "cancel"
                    else self._api.resume_mobile_task(parts[2])
                )
            except KeyError:
                self._reply(404, {"error": "unknown task"})
                return
            except MobileRuntimeNotReady as exc:
                self._reply(
                    409,
                    {
                        "error": " ".join(str(exc).split())[:2000],
                        "code": exc.code,
                        "retryable": exc.retryable,
                    },
                )
                return
            except ValueError as exc:
                self._reply(409, {"error": " ".join(str(exc).split())[:2000]})
                return
            self._reply(202, {"task": task.to_dict()})
            return
        if len(parts) == 4 and parts[:2] == ["mobile", "approvals"] and parts[3] == "resolve":
            allowed = payload.get("allowed")
            scope = payload.get("scope", "once")
            if not isinstance(allowed, bool) or scope not in {"once", "session"}:
                self._reply(
                    400,
                    {"error": "allowed must be boolean and scope must be once or session"},
                )
                return
            try:
                resolved = self._api.resolve_mobile_approval(parts[2], allowed, scope)
            except ValueError as exc:
                self._reply(400, {"error": str(exc)})
                return
            if not resolved:
                self._reply(404, {"error": "unknown approval"})
                return
            self._reply(200, {"ok": True})
            return
        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "run":
            prompt = payload.get("prompt")
            model = payload.get("model")
            if not isinstance(prompt, str) or not prompt.strip():
                self._reply(400, {"error": "prompt is required"})
                return
            if model is not None and not isinstance(model, str):
                self._reply(400, {"error": "model must be a string"})
                return
            try:
                result = self._api.run_turn(parts[1], prompt, model)
            except KeyError:
                self._reply(404, {"error": "unknown session"})
                return
            except Exception as exc:
                self._reply(500, {"error": " ".join(str(exc).split())[:2000]})
                return
            self._reply(200, {"session_id": result[0], "text": result[1]})
            return
        if parts == ["sessions"]:
            title = payload.get("title", "New session")
            if not isinstance(title, str) or not title.strip() or len(title) > 200:
                self._reply(400, {"error": "title is required (max 200 chars)"})
                return
            try:
                session = self._api.create_session(title.strip(), payload.get("workspace_id"))
            except KeyError:
                self._reply(404, {"error": "unknown workspace"})
                return
            except ValueError as exc:
                self._reply(400, {"error": " ".join(str(exc).split())[:2000]})
                return
            self._reply(201, session)
            return
        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "comment":
            text = payload.get("text")
            author = payload.get("author", "api")
            if not isinstance(text, str) or not text.strip() or len(text) > 4000:
                self._reply(400, {"error": "text is required (max 4000 chars)"})
                return
            try:
                comment_id = self._api.add_comment(parts[1], text, str(author))
            except KeyError:
                self._reply(404, {"error": "unknown session"})
                return
            self._reply(200, {"comment_id": comment_id})
            return
        self._reply(404, {"error": "not found"})

    def _upload_attachment(self) -> None:
        query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        body = self.rfile
        consumed = False
        previous_timeout = self.connection.gettimeout()
        self.connection.settimeout(60)
        try:
            if any(len(values) != 1 for values in query.values()):
                raise ValueError("upload parameters may not repeat")
            length_headers = self.headers.get_all("Content-Length", [])
            transfer_headers = self.headers.get_all("Transfer-Encoding", [])
            if (
                len(length_headers) > 1
                or len(transfer_headers) > 1
                or (length_headers and transfer_headers)
            ):
                raise ValueError("ambiguous upload body framing")
            length = None
            if transfer_headers:
                if transfer_headers[0].strip().lower() != "chunked":
                    raise ValueError("unsupported upload Transfer-Encoding")
                body = _ChunkedUploadReader(self.rfile)
            elif length_headers:
                raw_length = length_headers[0].strip()
                if not re.fullmatch(r"[0-9]{1,19}", raw_length):
                    raise ValueError("invalid Content-Length")
                length = int(raw_length)
            else:
                length = 0
            attachment = self._api.import_mobile_attachment_stream(
                {name: values[0] for name, values in query.items()}, body, content_length=length
            )
            consumed = True
        except KeyError:
            self._reject_request(404, {"error": "unknown session or workspace"})
        except ConcurrentModificationError as error:
            self._reject_request(409, {"error": " ".join(str(error).split())[:2000]})
        except WorkspaceStorageFullError as error:
            self._reject_request(507, {"error": str(error)})
        except (ValueError, TypeError) as error:
            self._reject_request(400, {"error": " ".join(str(error).split())[:2000]})
        except TimeoutError:
            self._reply(408, {"error": "upload timed out; retry this file"})
        except (OSError, ToolError):
            self._reject_request(500, {"error": "could not import attachment"})
        else:
            self._reply(201, attachment)
        finally:
            self.connection.settimeout(previous_timeout)
            if not consumed:
                self.close_connection = True


class MobileGateway:
    """Serve both the legacy companion API and Android task APIs."""

    def __init__(
        self,
        runtime: ApplicationRuntime,
        controller: MobileRuntimeController,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        token: str | None = None,
        token_ttl_seconds: float | None = None,
        token_scopes: tuple[str, ...] = ("read", "write", "approval"),
        clock: Any = time.time,
        default_model: str | None = None,
        settings: Mapping[str, Any] | None = None,
        console_html: str | None = None,
        static_assets: Mapping[str, tuple[str, bytes]] | None = None,
        workspace_catalog: MobileWorkspaceCatalog | None = None,
        provider_models: Any = None,
    ) -> None:
        self.runtime = runtime
        self.controller = controller
        self._provider_models = provider_models
        self.host = host
        self.port = port
        self.token = token or secrets.token_urlsafe(32)
        # The startup token is the identity secret shared with the app through serve.token.
        self._identity_secret = self.token.encode("utf-8")
        if token_ttl_seconds is not None and (
            isinstance(token_ttl_seconds, bool)
            or not isinstance(token_ttl_seconds, (int, float))
            or not math.isfinite(float(token_ttl_seconds))
            or token_ttl_seconds <= 0
        ):
            raise ValueError("token_ttl_seconds must be positive")
        normalized_scopes = frozenset(token_scopes)
        if not normalized_scopes or not normalized_scopes <= {"read", "write", "approval"}:
            raise ValueError("token_scopes are invalid")
        self._clock = clock
        self._tokens: dict[str, MobileAccessToken] = {
            self.token: MobileAccessToken(
                self.token,
                normalized_scopes,
                self._clock() + token_ttl_seconds if token_ttl_seconds is not None else None,
            )
        }
        self.default_model = (
            default_model if default_model is not None else controller.default_model
        )
        self._settings = {
            key: value
            for key, value in (settings or {}).items()
            if key
            in {
                "protocol",
                "base_url",
                "autonomy",
                "models",
                "model_efforts",
                "local_context_tokens",
                "local_memory_mode",
            }
        }
        self.console_html = console_html
        self.static_assets = dict(static_assets or {})
        self._loop = asyncio.get_running_loop()
        self.workspace_catalog = workspace_catalog
        if self.workspace_catalog is None:
            database = getattr(runtime, "database", None)
            root = getattr(getattr(runtime, "service", None), "_execution_workspace", None)
            if database is not None and root is not None:
                self.workspace_catalog = MobileWorkspaceCatalog(database, root)
        self.management = None
        if getattr(getattr(runtime, "service", None), "_execution_workspace", None) is not None:
            from mobile_management import MobileManagement

            self.management = MobileManagement(runtime, controller)
        self._server = ThreadingHTTPServer((host, port), _Handler)
        self._server.api = self  # type: ignore[attr-defined]
        self._thread: threading.Thread | None = None
        self._attachment_locks: WeakValueDictionary = WeakValueDictionary()
        self._attachment_locks_guard = threading.Lock()

    def issue_token(
        self,
        *,
        scopes: tuple[str, ...] = ("read", "write", "approval"),
        ttl_seconds: float | None = 3600.0,
    ) -> str:
        normalized_scopes = frozenset(scopes)
        if not normalized_scopes or not normalized_scopes <= {"read", "write", "approval"}:
            raise ValueError("token scopes are invalid")
        if ttl_seconds is not None and (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, (int, float))
            or not math.isfinite(float(ttl_seconds))
            or ttl_seconds <= 0
        ):
            raise ValueError("token ttl must be positive")
        value = secrets.token_urlsafe(32)
        self._tokens[value] = MobileAccessToken(
            value,
            normalized_scopes,
            self._clock() + ttl_seconds if ttl_seconds is not None else None,
        )
        return value

    def identity_proof(self, challenge: str) -> str:
        """HMAC-SHA256 of the challenge under the startup token; only this engine can produce it."""
        return hmac.new(
            self._identity_secret, _IDENTITY_CONTEXT + challenge.encode("ascii"), hashlib.sha256
        ).hexdigest()

    def validate_token(self, token: str, *, scope: str | None = None) -> bool:
        entry = self._tokens.get(token)
        return entry is not None and entry.allows(scope, now=self._clock())

    def revoke_token(self, token: str) -> bool:
        entry = self._tokens.get(token)
        if entry is None or entry.revoked:
            return False
        self._tokens[token] = MobileAccessToken(
            entry.token,
            entry.scopes,
            entry.expires_at,
            revoked=True,
        )
        return True

    def token_info(self, token: str | None = None) -> dict[str, object] | None:
        entry = self._tokens.get(token or self.token)
        if entry is None:
            return None
        return {
            "scopes": sorted(entry.scopes),
            "expires_at": entry.expires_at,
            "revoked": entry.revoked,
        }

    def rotate_token(self, *, ttl_seconds: float | None = 3600.0) -> str:
        previous = self.token
        previous_entry = self._tokens.get(previous)
        scopes = (
            tuple(sorted(previous_entry.scopes))
            if previous_entry is not None
            else (
                "read",
                "write",
                "approval",
            )
        )
        replacement = self.issue_token(scopes=scopes, ttl_seconds=ttl_seconds)
        self.revoke_token(previous)
        self.token = replacement
        return replacement

    @property
    def address(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> None:
        if self.management is not None:
            self.management.start()
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="agent-workspace-mobile-gateway",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self.management is not None:
            self._loop.call_soon_threadsafe(self.management.stop)
        self._server.shutdown()
        self._server.server_close()

    async def aclose_management(self) -> None:
        if self.management is not None:
            await self.management.aclose()

    def list_workspaces(self) -> dict[str, Any]:
        if self.workspace_catalog is None:
            return {"workspaces": [], "default_workspace_id": None}
        return {
            "workspaces": [item.to_dict() for item in self.workspace_catalog.list()],
            "default_workspace_id": self.workspace_catalog.default().workspace_id,
        }

    def create_workspace(self, name: str, path: str, *, create: bool = False) -> dict[str, Any]:
        if self.workspace_catalog is None:
            raise ValueError("runtime workspace is not configured")
        return self.workspace_catalog.add(name, path, create=create).to_dict()

    def remove_workspace(self, workspace_id: str) -> None:
        """Unregister a workspace; its folder and conversations stay on disk.

        Adding the same folder again brings its conversations back.
        """
        if self.workspace_catalog is None:
            raise ValueError("runtime workspace is not configured")
        selected = self.workspace_catalog.get(workspace_id)
        for task in self.controller.list(None):
            if str(task.state) not in _ACTIVE_TASK_STATES:
                continue
            session = self.runtime.store.get_session(task.session_id)
            if session is not None and session.workspace == selected.path:
                raise WorkspaceBusyError(workspace_id)
        self.workspace_catalog.remove(workspace_id)

    def scoped_runtime(self, workspace_id: str | None = None, *, session_id: str | None = None):
        if self.workspace_catalog is None:
            if workspace_id is not None:
                raise KeyError(workspace_id)
            return self.runtime
        if workspace_id is not None and (not isinstance(workspace_id, str) or not workspace_id):
            raise ValueError("workspace_id must be a nonempty string")
        selected = self.workspace_catalog.get(workspace_id) if workspace_id is not None else None
        if session_id is not None:
            if not isinstance(session_id, str) or not session_id:
                raise ValueError("session_id must be a nonempty string")
            session = self.runtime.store.get_session(session_id)
            if session is None:
                raise KeyError(session_id)
            actual = self.workspace_catalog.by_path(session.workspace)
            if actual is None or (
                selected is not None and selected.workspace_id != actual.workspace_id
            ):
                raise KeyError(session_id)
            selected = actual
        if selected is None:
            selected = self.workspace_catalog.default()
        return MobileScopedRuntime(self.runtime, selected.path)

    def _session_document(self, session) -> dict[str, Any]:
        runtime = self.scoped_runtime(session_id=session.id)
        selected = (
            self.workspace_catalog.by_path(session.workspace) if self.workspace_catalog else None
        )
        aliases = session_aliases(runtime)
        return {
            "id": session.id,
            "title": aliases.get(session.id, session.title),
            "workspace": session.workspace,
            "workspace_id": selected.workspace_id if selected else None,
            "mode": session.mode.value,
            "autonomy": session.autonomy.value,
            "updated_at": session.updated_at,
            "archived": session.id in archived_sessions(runtime),
        }

    def list_sessions(self, workspace_id: str | None = None) -> list[dict[str, Any]]:
        if self.workspace_catalog is None:
            if workspace_id is not None:
                raise KeyError(workspace_id)
            workspace = getattr(self.runtime.service, "_execution_workspace", None)
            sessions = self.runtime.store.list_sessions(limit=2_147_483_647, workspace=workspace)
        else:
            selected = (
                self.workspace_catalog.get(workspace_id) if workspace_id is not None else None
            )
            sessions = [
                session
                for session in self.runtime.store.list_sessions(limit=2_147_483_647)
                if self.workspace_catalog.by_path(session.workspace) is not None
                and (selected is None or selected.path == session.workspace)
            ]
        return [self._session_document(session) for session in sessions]

    def search_sessions(
        self, query: str, limit: int, *, workspace_id: str | None = None
    ) -> list[dict[str, str]]:
        if self.workspace_catalog is None or workspace_id is not None:
            return self._search_workspace_sessions(query, limit, workspace_id=workspace_id)
        results = []
        for workspace in self.workspace_catalog.list():
            results.extend(
                self._search_workspace_sessions(query, limit, workspace_id=workspace.workspace_id)
            )
        return results[:limit]

    def _search_workspace_sessions(
        self, query: str, limit: int, *, workspace_id: str | None = None
    ) -> list[dict[str, str]]:
        runtime = self.scoped_runtime(workspace_id)
        workspace = getattr(runtime.service, "_execution_workspace", None)
        if workspace is None:
            raise ValueError("runtime workspace is not configured")
        aliases = session_aliases(runtime)
        results = [
            {
                "session_id": result.session.id,
                "title": aliases.get(result.session.id, result.session.title),
                "snippet": result.snippet,
                "document_kind": result.document_kind,
            }
            for result in self.runtime.store.search_sessions(query, limit, workspace=workspace)
        ]
        if workspace_id is not None:
            for result in results:
                result["workspace_id"] = workspace_id
        if not aliases or len(results) >= limit:
            return results
        found = {result["session_id"] for result in results}
        needle = query.strip().casefold()
        for session in self.runtime.store.list_sessions(limit=2_147_483_647, workspace=workspace):
            alias = aliases.get(session.id)
            if alias is not None and needle in alias.casefold() and session.id not in found:
                results.append(
                    {
                        "session_id": session.id,
                        "title": alias,
                        "snippet": alias,
                        "document_kind": "title",
                        **({"workspace_id": workspace_id} if workspace_id is not None else {}),
                    }
                )
                found.add(session.id)
            if len(results) >= limit:
                break
        return results[:limit]

    def rename_session(self, session_id: str, title: str) -> dict[str, str]:
        return self._run_coro(
            self._rename_session(session_id, title), _MOBILE_OPERATION_TIMEOUT_SECONDS
        )

    async def _rename_session(self, session_id: str, title: str) -> dict[str, str]:
        if not self.session_exists(session_id):
            raise KeyError(session_id)
        runtime = self.scoped_runtime(session_id=session_id)
        async with self.runtime.store.session_lock(session_id):
            record = save_session_alias(runtime, session_id, title)
            event = self.runtime.store.append(
                Event(session_id=session_id, type="session.presentation.changed", data=record)
            )
        event_bus = getattr(self.runtime.service, "events", None)
        if event_bus is not None:
            await event_bus.publish(event)
        return {"id": session_id, "title": title}

    def archive_session(self, session_id: str, archived: bool) -> dict[str, Any]:
        return self._run_coro(
            self._archive_session(session_id, archived), _MOBILE_OPERATION_TIMEOUT_SECONDS
        )

    async def _archive_session(self, session_id: str, archived: bool) -> dict[str, Any]:
        """Hide or restore a conversation. The event store is append-only, so history is kept."""
        if not self.session_exists(session_id):
            raise KeyError(session_id)
        if archived and any(
            task.session_id == session_id and str(task.state) in _ACTIVE_TASK_STATES
            for task in self.controller.list(session_id)
        ):
            raise SessionBusyError(session_id)
        runtime = self.scoped_runtime(session_id=session_id)
        async with self.runtime.store.session_lock(session_id):
            record = save_session_archived(runtime, session_id, archived)
            event = self.runtime.store.append(
                Event(session_id=session_id, type="session.presentation.changed", data=record)
            )
        event_bus = getattr(self.runtime.service, "events", None)
        if event_bus is not None:
            await event_bus.publish(event)
        return {"id": session_id, "archived": archived}

    def apply_provider(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._run_coro(self._apply_provider(payload), _MOBILE_OPERATION_TIMEOUT_SECONDS)

    async def _apply_provider(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Switch model or cloud provider without restarting the engine.

        Model and reasoning effort only change defaults (each task carries its own). Another cloud
        provider is swapped into every conversation runtime. The on-device model loads native
        weights at engine start, so switching to or from it still needs a restart.
        """
        from mobile_protocol import REASONING_EFFORTS

        from agent_workspace.config import ProviderConfig, ProviderProtocol

        if not isinstance(payload, Mapping):
            raise ValueError("request body must be an object")
        protocol = payload.get("protocol")
        base_url = payload.get("base_url")
        model = payload.get("model")
        api_key = payload.get("api_key")
        effort = payload.get("reasoning_effort", "auto")
        summary = payload.get("context_summary_enabled")
        if not all(isinstance(value, str) and value.strip() for value in (protocol, base_url, model)):
            raise ValueError("protocol, base_url and model are required")
        if api_key is not None and not isinstance(api_key, str):
            raise ValueError("api_key must be text")
        if effort not in REASONING_EFFORTS:
            raise ValueError("reasoning_effort is invalid")
        if summary is not None and not isinstance(summary, bool):
            raise ValueError("context_summary_enabled must be true or false")
        config = ProviderConfig(
            id=protocol, protocol=ProviderProtocol(protocol), base_url=base_url.strip(),
            model=model.strip(), api_key=api_key or None,
        )
        config.validate()
        local = "/embedded-qwen/v1"
        if config.base_url.rstrip("/").endswith(local) or str(
            self._settings.get("base_url", "")
        ).rstrip("/").endswith(local):
            raise ProviderRestartRequired("switching to or from the on-device model restarts the engine")
        previous = await self.controller.switch_provider(config, effort)
        for provider in previous:
            close = getattr(provider, "aclose", None)
            if callable(close):
                with contextlib.suppress(Exception):
                    await close()
        # Code that reads the provider from the environment (memory budget, context summary, the
        # next engine start's defaults) sees the new choice too.
        os.environ.update(
            AGENT_WORKSPACE_PROVIDER=config.id,
            AGENT_WORKSPACE_PROTOCOL=config.protocol.value,
            AGENT_WORKSPACE_BASE_URL=config.base_url,
            AGENT_WORKSPACE_MODEL=config.model,
        )
        if config.api_key:
            os.environ["AGENT_WORKSPACE_API_KEY"] = config.api_key
        else:
            os.environ.pop("AGENT_WORKSPACE_API_KEY", None)
        if effort == "auto":
            os.environ.pop("AGENT_WORKSPACE_REASONING_EFFORT", None)
        else:
            os.environ["AGENT_WORKSPACE_REASONING_EFFORT"] = effort
        if summary is not None:
            os.environ["AGENT_WORKSPACE_CONTEXT_SUMMARY_ENABLED"] = "1" if summary else "0"
        self.default_model = config.model
        self._settings.update(
            protocol=config.protocol.value,
            base_url=config.base_url,
            models=self._provider_models(config) if callable(self._provider_models) else [config.model],
        )
        return self.effective_settings()

    def effective_settings(self) -> dict[str, Any]:
        protocol = str(self._settings.get("protocol", "openai-compatible"))
        base_url = self.controller.base_url or str(self._settings.get("base_url", ""))
        model = self.controller.default_model or self.default_model or ""
        autonomy = getattr(self.runtime.service, "_execution_autonomy", None)
        if autonomy is None:
            autonomy = self._settings.get("autonomy", Autonomy.WORKSPACE.value)
        autonomy = autonomy.value if isinstance(autonomy, Autonomy) else str(autonomy)
        configured_models = self._settings.get("models", ())
        models = [model]
        if isinstance(configured_models, (list, tuple)):
            models.extend(item for item in configured_models if isinstance(item, str))
        models = list(dict.fromkeys(models))
        model_efforts = {
            name: list(supported_reasoning_efforts(protocol, base_url, name))
            if base_url
            else ["auto"]
            for name in models
            if name
        }
        return {
            "protocol": protocol,
            "base_url": base_url,
            "model": model,
            "reasoning_effort": self.controller.default_reasoning_effort,
            "autonomy": autonomy,
            "local_context_tokens": self._settings.get("local_context_tokens", 0),
            "local_memory_mode": self._settings.get("local_memory_mode", "balanced"),
            "context_summary_enabled": configured_mobile_context_summary(base_url),
            "context_summary_experimental": experimental_mobile_context_summary(base_url),
            "local_context_options": [0, 4096, 8192, 16384, 32768, 65536, 131072, 262144],
            "local_memory_modes": ["balanced", "extended"],
            "models": models,
            "model_efforts": model_efforts,
        }

    def import_mobile_attachment(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._run_coro(
            self._import_mobile_attachment(payload), _MOBILE_OPERATION_TIMEOUT_SECONDS
        )

    def import_mobile_attachment_stream(
        self, payload: Mapping[str, Any], source: BinaryIO, *, content_length: int | None
    ) -> dict[str, Any]:
        if content_length is not None and (type(content_length) is not int or content_length < 0):
            raise ValueError("invalid Content-Length")
        session_id = payload.get("session_id")
        if not isinstance(session_id, str) or not session_id or len(session_id) > 256:
            raise ValueError("session_id is required")
        runtime = self.scoped_runtime(payload.get("workspace_id"), session_id=session_id)
        session = runtime.service.get_session(session_id)
        execution_workspace = getattr(runtime.service, "_execution_workspace", None)
        if execution_workspace is not None and WorkspacePaths(
            session.workspace
        ).root != runtime_workspace(runtime):
            raise KeyError(session_id)
        if execution_workspace is None:
            runtime = MobileScopedRuntime(runtime, session.workspace)
        filename = workspace_upload_filename(payload.get("filename"))
        declared = workspace_upload_media_type(payload.get("media_type"))
        request_id = payload.get("request_id")
        if request_id is not None and (
            not isinstance(request_id, str)
            or not re.fullmatch(r"[a-zA-Z0-9._-]{1,128}", request_id)
        ):
            raise ValueError("request_id must be a nonempty identifier of at most 128 characters")
        key = (session_id, request_id or secrets.token_hex(16))
        with self._attachment_locks_guard:
            lock = self._attachment_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._attachment_locks[key] = lock
        with lock:
            paths = WorkspacePaths(session.workspace)
            if request_id is not None:
                recovered = False
                previous = next(
                    (
                        event.data
                        for event in self.runtime.store.list_events(session_id)
                        if event.type == "mobile.attachment.imported"
                        and event.data.get("request_id") == request_id
                    ),
                    None,
                )
                if previous is None:
                    identifier = _upload_identifier(session_id, request_id)
                    target = paths.resolve(f"uploads/{identifier}/{filename}")
                    journal = _read_upload_receipt(paths, target)
                    if journal is not None:
                        name = journal.get("name")
                        if (
                            type(journal.get("version")) is not int
                            or journal["version"] != 1
                            or journal.get("session_id") != session_id
                            or journal.get("request_id") != request_id
                            or not isinstance(name, str)
                            or workspace_upload_filename(name) != name
                            or journal.get("path") != f"uploads/{identifier}/{name}"
                            or type(journal.get("size")) is not int
                            or journal["size"] < 0
                            or not isinstance(journal.get("sha256"), str)
                            or not re.fullmatch(r"[0-9a-f]{64}", journal["sha256"])
                            or not isinstance(journal.get("media_type"), str)
                            or workspace_upload_media_type(journal["media_type"])
                            != journal["media_type"]
                            or (
                                journal.get("content_length") is not None
                                and (
                                    type(journal["content_length"]) is not int
                                    or journal["content_length"] != journal["size"]
                                )
                            )
                        ):
                            raise ConcurrentModificationError("upload request receipt is invalid")
                        previous = journal
                        recovered = True
                    elif target.parent.exists():
                        raise ConcurrentModificationError("upload destination already exists")
                if previous is not None:
                    if (
                        previous.get("name") != filename
                        or previous.get("upload_media_type") != declared
                        or (content_length is not None and previous.get("size") != content_length)
                    ):
                        raise ConcurrentModificationError(
                            "request_id already identifies a different file"
                        )
                    digest = hashlib.sha256()
                    size = 0
                    remaining = content_length
                    while remaining is None or remaining:
                        chunk = source.read(
                            64 * 1024 if remaining is None else min(64 * 1024, remaining)
                        )
                        if not chunk:
                            if remaining:
                                raise ValueError("incomplete upload body")
                            break
                        if len(chunk) > 64 * 1024 or (
                            remaining is not None and len(chunk) > remaining
                        ):
                            raise ValueError("upload stream exceeded its declared length")
                        size += len(chunk)
                        digest.update(chunk)
                        if remaining is not None:
                            remaining -= len(chunk)
                    if size != previous.get("size") or digest.hexdigest() != previous.get("sha256"):
                        raise ConcurrentModificationError(
                            "request_id already identifies different file content"
                        )
                    deleted = any(
                        event.type == "mobile.attachment.deleted"
                        and event.data.get("path") == previous.get("path")
                        for event in self.runtime.store.list_events(session_id)
                    )
                    if deleted:
                        raise ConcurrentModificationError(
                            "this upload was removed; use a new request_id"
                        )
                    with open_workspace_download(
                        runtime, previous["path"], previous["sha256"]
                    ) as (_, metadata):
                        if metadata["size"] != previous["size"]:
                            raise ConcurrentModificationError("uploaded file size changed")
                    attachment = {
                        name: previous[name]
                        for name in ("name", "path", "size", "sha256", "media_type", "request_id")
                    }
                    if recovered:
                        self.runtime.store.append(
                            Event(
                                session_id=session.id,
                                type="mobile.attachment.imported",
                                data={**attachment, "upload_media_type": declared},
                            )
                        )
                    with suppress(OSError, ValueError, ToolError):
                        _remove_upload_receipt(
                            paths,
                            paths.resolve(attachment["path"]),
                            {**previous, "session_id": session_id},
                        )
                    return attachment
            request_metadata = (
                {
                    "version": 1,
                    "session_id": session_id,
                    "request_id": request_id,
                    "upload_media_type": declared,
                    "content_length": content_length,
                }
                if request_id is not None
                else None
            )
            attachment = import_workspace_upload(
                runtime,
                filename,
                source,
                content_length=content_length,
                media_type=declared,
                upload_identifier=_upload_identifier(session_id, request_id)
                if request_id is not None
                else None,
                request_metadata=request_metadata,
            )
            if request_id is not None:
                attachment["request_id"] = request_id
            try:
                self.runtime.store.append(
                    Event(
                        session_id=session.id,
                        type="mobile.attachment.imported",
                        data={**attachment, "upload_media_type": declared},
                    )
                )
            except BaseException:
                if request_id is None:
                    with suppress(OSError, ValueError):
                        destination = paths.resolve(attachment["path"])
                        destination.unlink()
                        destination.parent.rmdir()
                raise
            if request_id is not None:
                with suppress(OSError, ValueError, ToolError):
                    _remove_upload_receipt(
                        paths,
                        paths.resolve(attachment["path"]),
                        {
                            **attachment,
                            "session_id": session_id,
                            "upload_media_type": declared,
                        },
                    )
            return attachment

    async def _import_mobile_attachment(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        session_id = payload.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id is required")
        if not self.session_exists(session_id):
            raise KeyError(session_id)
        runtime = self.scoped_runtime(session_id=session_id)
        session = runtime.service.get_session(session_id)
        execution_workspace = getattr(runtime.service, "_execution_workspace", None)
        if execution_workspace is not None and WorkspacePaths(
            session.workspace
        ).root != runtime_workspace(runtime):
            raise KeyError(session_id)
        filename = payload.get("filename")
        reserved_names = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }
        if (
            not isinstance(filename, str)
            or not filename
            or len(filename) > 180
            or PureWindowsPath(filename).name != filename
            or filename in {".", ".."}
            or filename.endswith((" ", "."))
            or any(ord(character) < 32 or character in '<>:"/\\|?*' for character in filename)
            or filename.split(".", 1)[0].upper() in reserved_names
        ):
            raise ValueError("filename must be a safe file name without a path")
        encoded = payload.get("content_base64")
        if not isinstance(encoded, str):
            raise ValueError("content_base64 must be a base64 string")
        if len(encoded) > ((_MAX_ATTACHMENT_BYTES + 2) // 3) * 4:
            raise AttachmentTooLargeError("attachment exceeds the 4 MiB limit")
        try:
            content = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, binascii.Error) as exc:
            raise ValueError("content_base64 must be valid base64") from exc
        if len(content) > _MAX_ATTACHMENT_BYTES:
            raise AttachmentTooLargeError("attachment exceeds the 4 MiB limit")
        media_type = attachment_media_type(
            content, filename=filename, declared_media_type=payload.get("media_type")
        )
        paths = WorkspacePaths(session.workspace)
        relative = f"uploads/{secrets.token_hex(16)}/{filename}"
        destination = paths.resolve(relative)
        destination.parent.mkdir(parents=True, exist_ok=False)
        destination = paths.resolve(relative)
        with destination.open("xb") as stream:
            paths.assert_safe_file_descriptor(stream.fileno(), destination)
            stream.write(content)
        attachment = {
            "name": filename,
            "path": relative,
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "media_type": media_type,
        }
        self.runtime.store.append(
            Event(
                session_id=session.id,
                type="mobile.attachment.imported",
                data=attachment,
            )
        )
        return attachment

    def delete_mobile_attachment(self, session_id: str, path: str) -> dict[str, bool]:
        return self._run_coro(
            self._delete_mobile_attachment(session_id, path), _MOBILE_OPERATION_TIMEOUT_SECONDS
        )

    async def _delete_mobile_attachment(self, session_id: str, path: str) -> dict[str, bool]:
        if not session_id or not path:
            raise ValueError("session_id and path are required")
        if not self.session_exists(session_id):
            raise KeyError(session_id)
        session = self.scoped_runtime(session_id=session_id).service.get_session(session_id)
        parts = PurePosixPath(path).parts
        if (
            len(parts) != 3
            or parts[0] != "uploads"
            or len(parts[1]) != 32
            or any(character not in "0123456789abcdef" for character in parts[1])
            or PureWindowsPath(path).is_absolute()
            or "\\" in path
            or ".." in parts
        ):
            raise ValueError("path must identify an imported workspace attachment")
        paths = WorkspacePaths(session.workspace)
        destination = paths.resolve(path)
        events = self.runtime.store.list_events(session_id)
        imported = False
        for event in events:
            if event.data.get("path") == path:
                if event.type == "mobile.attachment.imported":
                    imported = True
                elif event.type == "mobile.attachment.deleted":
                    imported = False
        if not imported:
            raise KeyError(path)
        reference = re.compile(r"(?<![\w./\\-])" + re.escape(path) + r"(?![\w./\\-])")
        for event in events:
            content = None
            if event.type == "mobile.task.created":
                content = event.data.get("prompt")
                if any(
                    ref.get("path") == path
                    for ref in event.data.get("image_refs", [])
                    if isinstance(ref, dict)
                ):
                    raise AttachmentInUseError("attachment is referenced by a submitted task")
            elif event.type == "message.created" and event.data.get("role") == "user":
                content = event.data.get("content")
            if isinstance(content, str) and reference.search(content):
                raise AttachmentInUseError("attachment is referenced by a submitted task")
        destination.unlink(missing_ok=True)
        with suppress(OSError):
            destination.parent.rmdir()
        self.runtime.store.append(
            Event(
                session_id=session_id,
                type="mobile.attachment.deleted",
                data={"path": path},
            )
        )
        return {"deleted": True}

    def create_session(self, title: str, workspace_id: str | None = None) -> dict[str, Any]:
        runtime = self.scoped_runtime(workspace_id)
        workspace = getattr(runtime.service, "_execution_workspace", None)
        if workspace is None:
            sessions = self.runtime.store.list_sessions(limit=1)
            if not sessions:
                raise ValueError("runtime workspace is not configured")
            workspace = sessions[0].workspace
        autonomy = getattr(runtime.service, "_execution_autonomy", None) or Autonomy.WORKSPACE
        session = runtime.service.create_session(workspace, autonomy=autonomy, title=title)
        return self._session_document(session)

    def session_exists(self, session_id: str) -> bool:
        try:
            self.scoped_runtime(session_id=session_id).service.get_session(session_id)
        except (KeyError, ValueError):
            return False
        return True

    def list_events(self, session_id: str) -> list[dict[str, Any]]:
        if not self.session_exists(session_id):
            raise KeyError(session_id)
        return [
            {
                "id": event.id,
                "type": event.type,
                "sequence": event.sequence,
                "created_at": event.created_at,
                "data": event.data,
            }
            for event in self.runtime.store.list_events(session_id)
            if not event.type.startswith("mobile.artifacts.")
        ]

    def list_comments(self, session_id: str) -> list[dict[str, Any]]:
        from agent_workspace.core.comments import list_comments

        if not self.session_exists(session_id):
            raise KeyError(session_id)
        return list_comments(self.runtime.store, session_id)

    def add_comment(self, session_id: str, text: str, author: str) -> str:
        from agent_workspace.core.comments import add_comment

        if not self.session_exists(session_id):
            raise KeyError(session_id)
        return add_comment(self.runtime.store, session_id, text, author)

    def submit_mobile_task(self, request: MobileTaskRequest, *, request_id: str | None = None):
        return self._run_coro(
            self.controller.submit(request, request_id=request_id),
            _MOBILE_OPERATION_TIMEOUT_SECONDS,
        )

    def cancel_mobile_task(self, task_id: str):
        return self._run_coro(self.controller.cancel(task_id), _MOBILE_OPERATION_TIMEOUT_SECONDS)

    def resume_mobile_task(self, task_id: str):
        return self._run_coro(self.controller.resume(task_id), _MOBILE_OPERATION_TIMEOUT_SECONDS)

    def steer_mobile_task(self, task_id: str, prompt: str, *, input_id: str | None = None) -> dict[str, Any]:
        steer = getattr(self.controller, "steer", None)
        if not callable(steer):
            raise RuntimeError("steer_failed")
        return self._run_coro(steer(task_id, prompt, input_id=input_id), _MOBILE_OPERATION_TIMEOUT_SECONDS)

    def resolve_mobile_approval(self, request_id: str, allowed: bool, scope: str) -> bool:
        return bool(
            self._run_coro(
                self.controller.resolve_approval(request_id, allowed, scope),
                _MOBILE_OPERATION_TIMEOUT_SECONDS,
            )
        )

    def reconnect_mobile(self) -> dict[str, object]:
        return self._run_coro(
            self.controller.reconnect(),
            _MOBILE_OPERATION_TIMEOUT_SECONDS,
        )

    def run_turn(self, session_id: str, prompt: str, model: str | None) -> tuple[str, str]:
        return self._run_coro(
            self._run_legacy(session_id, prompt, model),
            _RUN_TIMEOUT_SECONDS,
        )

    async def _run_legacy(self, session_id: str, prompt: str, model: str | None) -> tuple[str, str]:
        service_for_session = getattr(self.controller, "service_for_session", None)
        service = (
            await service_for_session(session_id)
            if callable(service_for_session)
            else self.runtime.service
        )
        session = service.get_session(session_id)
        resolved_model = model or self.default_model
        if resolved_model is None:
            raise ValueError("no model configured for the serve API")
        result = await service.run(session, prompt, resolved_model)
        return session.id, result.text

    def _run_coro(self, coroutine: Any, timeout: float) -> Any:
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=timeout)
        except BaseException:
            future.cancel()
            raise


def _services_summary() -> dict[str, Any]:
    """Running services, for the engine notification and wake lock (polled with the tasks)."""
    try:
        from mobile_services import get_service_manager

        manager = get_service_manager()
    except Exception:
        manager = None
    return manager.summary() if manager is not None else {"running": 0, "keep_awake": False}


def _query_int(
    query: Mapping[str, list[str]],
    name: str,
    default: int,
    *,
    minimum: int,
) -> int:
    try:
        value = int(query.get(name, [str(default)])[0])
    except (TypeError, ValueError):
        raise ValueError(f"invalid {name}") from None
    if value < minimum:
        raise ValueError(f"invalid {name}")
    return value


def _query_float(
    query: Mapping[str, list[str]],
    name: str,
    default: float,
    *,
    minimum: float,
) -> float:
    try:
        value = float(query.get(name, [str(default)])[0])
    except (TypeError, ValueError):
        raise ValueError(f"invalid {name}") from None
    if value < minimum:
        raise ValueError(f"invalid {name}")
    return value
