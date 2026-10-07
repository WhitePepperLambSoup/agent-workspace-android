from __future__ import annotations

import asyncio
import contextlib
import hashlib
import http.client
import ssl
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urljoin, urlsplit

from agent_workspace.core.events import Event
from agent_workspace.core.models import Capability, FileCheckpoint, ToolSpec

from . import web
from .base import ToolArgumentError, ToolError, json_result, optional_int, require_string
from .filesystem import _read_preimage, atomic_write, expected_sha256
from .paths import StrPath, WorkspacePaths, is_sensitive_workspace_path
from .process_worker import run_in_process

if TYPE_CHECKING:
    from agent_workspace.application.ports import ToolExecutionContext


_MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024

_CREDENTIAL_QUERY_NAMES = frozenset(
    {
        "accesskey",
        "accesstoken",
        "apikey",
        "auth",
        "authorization",
        "credential",
        "credentials",
        "idtoken",
        "key",
        "password",
        "passwd",
        "privatekey",
        "refreshtoken",
        "secret",
        "secretkey",
        "sessiontoken",
        "sig",
        "signature",
        "token",
        "xamzcredential",
        "xamzsecuritytoken",
        "xamzsignature",
    }
)
_CREDENTIAL_QUERY_SUFFIXES = (
    "apikey",
    "auth",
    "credential",
    "password",
    "passwd",
    "secret",
    "signature",
    "token",
)


def _reject_credential_query(raw_url: str) -> None:
    try:
        query = urlsplit(raw_url).query
    except ValueError:
        return
    for name, _value in parse_qsl(query, keep_blank_values=True):
        normalized = "".join(character for character in name.casefold() if character.isalnum())
        if normalized in _CREDENTIAL_QUERY_NAMES or any(
            normalized.endswith(suffix) for suffix in _CREDENTIAL_QUERY_SUFFIXES
        ):
            raise ToolArgumentError("download_file URL query contains a credential-like parameter")


def _download_bytes(
    raw_url: str, maximum: int, timeout_seconds: int
) -> tuple[bytes, dict[str, object]]:
    current_url = raw_url
    original_origin: tuple[str, str, int] | None = None
    redirects: list[str] = []
    for redirect_count in range(web._MAX_REDIRECTS + 1):
        normalized, parsed, addresses = web._normalize_public_https_url(current_url)
        _reject_credential_query(normalized)
        origin = (parsed.scheme, parsed.hostname or "", parsed.port or 443)
        if original_origin is None:
            original_origin = origin
        elif origin != original_origin:
            raise ToolError("download_file blocks cross-origin redirects")
        connection = web._PinnedHTTPSConnection(
            parsed.hostname or "", addresses[0], parsed.port or 443, float(timeout_seconds)
        )
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        try:
            connection.request(
                "GET",
                path,
                headers={
                    "Accept": "application/pdf,application/octet-stream,image/*,*/*",
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                    "User-Agent": "AgentWorkspace/0.1",
                },
            )
            response = connection.getresponse()
            header_bytes = sum(
                len(name.encode("latin-1")) + len(value.encode("latin-1")) + 4
                for name, value in response.getheaders()
            )
            if header_bytes > web._MAX_HEADER_BYTES:
                raise ToolError("download_file response headers exceed the safety limit")
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise ToolError("download_file redirect is missing Location")
                if redirect_count >= web._MAX_REDIRECTS:
                    raise ToolError("download_file redirect limit exceeded")
                current_url = urljoin(normalized, location)
                redirects.append(current_url)
                continue
            if response.status != 200:
                raise ToolError(f"download_file returned HTTP status {response.status}")
            if (response.getheader("Content-Encoding") or "identity").casefold() != "identity":
                raise ToolError("download_file compressed responses are unsupported")
            raw_media_type = response.getheader("Content-Type")
            if not raw_media_type:
                raise ToolError("download_file response is missing Content-Type")
            media_type = raw_media_type.split(";", 1)[0].strip().casefold()
            if not media_type or media_type == "text/html":
                raise ToolError("download_file response media type is unsupported")
            raw_content_length = response.getheader("Content-Length")
            content_length: int | None = None
            if raw_content_length is not None:
                try:
                    content_length = int(raw_content_length.strip(), 10)
                except (AttributeError, ValueError):
                    raise ToolError("download_file response Content-Length is invalid") from None
                if content_length < 0:
                    raise ToolError("download_file response Content-Length is invalid")
                if content_length > maximum:
                    raise ToolError("download_file response exceeds the byte limit")
            body = response.read(maximum + 1)
        except (OSError, ssl.SSLError, http.client.HTTPException, TimeoutError) as exc:
            raise ToolError(
                f"download_file transport failed: {web._transport_reason(exc)}"
            ) from exc
        finally:
            connection.close()
        if len(body) > maximum:
            raise ToolError("download_file response exceeds the byte limit")
        if content_length is not None and content_length != len(body):
            raise ToolError("download_file response Content-Length does not match bytes received")
        if not body:
            raise ToolError("download_file response is empty")
        if urlsplit(normalized).path.casefold().endswith(".pdf") and not body.startswith(b"%PDF-"):
            raise ToolError("download_file PDF response has an invalid signature")
        return body, {
            "url": normalized,
            "redirects": redirects,
            "status": response.status,
            "media_type": media_type,
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes_written": len(body),
        }
    raise ToolError("download_file redirect limit exceeded")


class DownloadFileTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="download_file",
        description=(
            "Download bounded public HTTPS bytes into a workspace file with a complete "
            "SHA-256 receipt. Same-origin redirects only; provide the existing file digest "
            "when replacing a file. Requires network approval."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "minLength": 1, "maxLength": 4096},
                "path": {"type": "string", "minLength": 1},
                "expected_sha256": {"type": ["string", "null"]},
                "max_bytes": {"type": "integer", "minimum": 1024, "maximum": _MAX_DOWNLOAD_BYTES},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 30},
            },
            "required": ["url", "path", "expected_sha256"],
            "additionalProperties": False,
        },
        side_effect="network",
        capability=Capability.NETWORK_READ,
        durable_preimage_checkpoint=True,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def _arguments(self, arguments: dict[str, Any]) -> tuple[str, Path, str | None, int, int]:
        url = require_string(arguments, "url")
        _reject_credential_query(url)
        raw_path = require_string(arguments, "path")
        if is_sensitive_workspace_path(raw_path):
            raise ToolArgumentError("download_file cannot target sensitive workspace paths")
        path = self.paths.resolve(raw_path)
        if not self.paths.resolve(path.parent).is_dir():
            raise ToolError("download_file parent directory does not exist")
        expected = expected_sha256(arguments)
        maximum = optional_int(
            arguments, "max_bytes", 8 * 1024 * 1024, minimum=1024, maximum=_MAX_DOWNLOAD_BYTES
        )
        timeout = optional_int(arguments, "timeout_seconds", 15, minimum=1, maximum=30)
        return url, path, expected, maximum, timeout

    def _write(
        self, path: Path, body: bytes, expected: str | None, receipt: dict[str, object]
    ) -> str:
        written, digest = atomic_write(self.paths, path, body, expected)
        return json_result({**receipt, "path": self.paths.relative(written), "sha256": digest})

    def _execute_sync(self, arguments: dict[str, Any]) -> str:
        url, path, expected, maximum, timeout = self._arguments(arguments)
        body, receipt = _download_bytes(url, maximum, timeout)
        return self._write(path, body, expected, receipt)

    async def execute(self, arguments: dict[str, Any]) -> str:
        url, path, expected, maximum, timeout = self._arguments(arguments)
        download_task = asyncio.create_task(
            asyncio.to_thread(_download_bytes, url, maximum, timeout)
        )
        try:
            body, receipt = await asyncio.shield(download_task)
        except asyncio.CancelledError:
            with contextlib.suppress(BaseException):
                await download_task
            raise
        return self._write(path, body, expected, receipt)

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        url, path, expected, maximum, timeout = self._arguments(arguments)
        body, receipt = await run_in_process(_download_bytes, url, maximum, timeout)
        preimage = _read_preimage(path, expected, _MAX_DOWNLOAD_BYTES)
        digest = hashlib.sha256(body).hexdigest()
        relative = self.paths.relative(path)
        await context.prepare_file_checkpoint(
            FileCheckpoint(
                attempt_id=context.attempt_id,
                session_id=context.session_id,
                workspace=str(self.paths.root),
                started_event_id=context.started_event_id,
                relative_path=relative,
                preimage_sha256=expected,
                preimage=preimage,
                postimage_sha256=digest,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
        result = await run_in_process(self._write, path, body, expected, receipt)
        await context.record_event(
            Event(
                session_id=context.session_id,
                type="file.version.recorded",
                data={
                    "attempt_id": context.attempt_id,
                    "path": relative,
                    "sha256": digest,
                    "bytes": len(body),
                },
                causation_id=context.started_event_id,
                correlation_id=context.correlation_id,
            )
        )
        return result
