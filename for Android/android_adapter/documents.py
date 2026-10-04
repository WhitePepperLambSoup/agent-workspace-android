"""Android PDF tools: checked snapshots, local OCR and durable PDF exports."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO
from uuid import UUID

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.events import Event
from agent_workspace.core.models import BinaryArtifact, Capability, FileCheckpoint, ToolSpec
from agent_workspace.storage.durable import durable_replace
from agent_workspace.tools.base import (
    ConcurrentModificationError,
    ToolArgumentError,
    ToolError,
    json_result,
    optional_int,
    require_string,
)
from agent_workspace.tools.document import ReadDocumentTool, _pdf_text
from agent_workspace.tools.filesystem import (
    _check_preimage,
    _open_identity_checked,
    _read_preimage,
    expected_sha256,
)
from agent_workspace.tools.paths import (
    StrPath,
    WorkspacePathError,
    WorkspacePaths,
    is_sensitive_workspace_path,
)

_COPY_CHUNK_BYTES = 64 * 1024
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_TEXT_BYTES = 262144
_PNG = b"\x89PNG\r\n\x1a\n"


def _bridge() -> Any:
    from java import jclass  # type: ignore[import-not-found]

    return jclass("com.agentworkspace.mobile.documents.AndroidDocumentBridge")


def _response(raw: Any) -> dict[str, Any]:
    try:
        result = json.loads(str(raw))
    except (TypeError, ValueError) as exc:
        raise ToolError("Android document bridge returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise ToolError("Android document bridge returned an invalid result")
    return result


def _failure_message(result: dict[str, Any], fallback: str) -> str:
    error = result.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or fallback)
    return str(error or fallback)


def document_status() -> dict[str, Any]:
    try:
        status = _response(_bridge().status())
        if not status.get("available"):
            status.setdefault("reason", "Android PDF bridge has not initialized")
        return status
    except Exception:
        return {
            "available": False,
            "reason": "Native PDF rendering, OCR and export are unavailable in this runtime",
        }


async def _settled[T](operation: Coroutine[Any, Any, T]) -> T:
    """Keep a native worker alive through repeated cancellation, then propagate it."""
    task = asyncio.create_task(operation)
    cancellation: asyncio.CancelledError | None = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as exc:
            cancellation = cancellation or exc
        except Exception:
            break
    if cancellation is not None:
        # Observe a failed native worker as well; its finally has already released the job.
        if not task.cancelled():
            task.exception()
        raise cancellation
    return task.result()


def _checked_bytes(paths: WorkspacePaths, raw_path: str, maximum: int) -> bytes:
    path = paths.resolve(raw_path)
    if is_sensitive_workspace_path(paths.relative(path)):
        raise ToolError("Sensitive workspace files cannot be used as document inputs or outputs")
    try:
        with _open_identity_checked(path, "rb") as source:
            before = WorkspacePaths.assert_safe_file_descriptor(source.fileno(), path)
            if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
                raise ToolError(f"document must be a regular file of at most {maximum} bytes")
            data = bytes(source.read(maximum + 1))
            after = WorkspacePaths.assert_safe_file_descriptor(source.fileno(), path)
            current = paths.resolve(raw_path).lstat()

            def identity(value: Any) -> tuple[int, int, int, int]:
                return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns

            if (
                len(data) > maximum
                or identity(before) != identity(after)
                or identity(after) != identity(current)
            ):
                raise ToolError("Document changed while taking its snapshot; retry reading it")
            return data
    except OSError as exc:
        raise ToolError(f"cannot read document: {raw_path}") from exc


def _checked_copy(
    paths: WorkspacePaths,
    raw_path: str,
    destination: BinaryIO | None = None,
    *,
    signature: bytes = b"%PDF",
) -> tuple[int, str]:
    """Stream a checked file snapshot without imposing a PDF byte-size ceiling."""
    path = paths.resolve(raw_path)
    if is_sensitive_workspace_path(paths.relative(path)):
        raise ToolError("Sensitive workspace files cannot be used as document inputs or outputs")
    try:
        with _open_identity_checked(path, "rb") as source:
            before = WorkspacePaths.assert_safe_file_descriptor(source.fileno(), path)
            if not stat.S_ISREG(before.st_mode):
                raise ToolError("Document must be a regular file")
            digest, count = hashlib.sha256(), 0
            while chunk := bytes(source.read(_COPY_CHUNK_BYTES)):
                if count == 0 and signature and not chunk.startswith(signature):
                    raise ToolError("Document has an invalid file signature")
                if destination is not None:
                    destination.write(chunk)
                digest.update(chunk)
                count += len(chunk)
            after = WorkspacePaths.assert_safe_file_descriptor(source.fileno(), path)
            current = paths.resolve(raw_path).lstat()

            def identity(value: Any) -> tuple[int, int, int, int]:
                return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns

            if (
                count != before.st_size
                or identity(before) != identity(after)
                or identity(after) != identity(current)
            ):
                raise ToolError("Document changed while taking its snapshot; retry reading it")
            if signature and count == 0:
                raise ToolError("Document has an invalid file signature")
            return count, digest.hexdigest()
    except OSError as exc:
        raise ToolError(
            f"Cannot stream document; check available storage: {raw_path}: {exc}"
        ) from exc


class _Job:
    def __init__(self, bridge: Any):
        self.bridge = bridge
        self.identity: str | None = None

    def __enter__(self) -> _Job:
        status = _response(self.bridge.status())
        if not status.get("available"):
            raise ToolError(str(status.get("reason") or "Native PDF tools are unavailable"))
        base = WorkspacePaths(require_string(status, "temp_root")).root
        response = _response(self.bridge.start_job())
        if not response.get("ok"):
            raise ToolError(_failure_message(response, "Cannot start a native document job"))
        try:
            identity = require_string(response, "job_id")
            if str(UUID(identity)) != identity:
                raise ValueError("Noncanonical job identifier")
            self.identity = identity
            self.paths = WorkspacePaths(require_string(response, "root"))
            if self.paths.root != base / identity:
                raise ToolError("Native document job escaped its private directory")
        except Exception:
            if self.identity is not None:
                self.bridge.release(self.identity)
            raise
        return self

    def __exit__(self, *_exc: Any) -> None:
        if self.identity is not None:
            response = _response(self.bridge.release(self.identity))
            if not response.get("ok"):
                raise ToolError(_failure_message(response, "Cannot release native document job"))

    def stage_from(self, paths: WorkspacePaths, raw_path: str) -> tuple[Path, str]:
        path = self.paths.resolve("input.pdf")
        with path.open("xb") as stream:
            _, digest = _checked_copy(paths, raw_path, stream)
        return path, digest

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        result = _response(
            self.bridge.execute(
                json.dumps({**request, "request_id": self.identity}, ensure_ascii=False)
            )
        )
        if not result.get("ok"):
            raise ToolError(_failure_message(result, "Native PDF operation failed"))
        if result.get("request_id", self.identity) != self.identity:
            raise ToolError("Native document result belongs to another job")
        return result

    def output(
        self, output: dict[str, Any], filename: str, maximum: int, signature: bytes
    ) -> bytes:
        path = self.output_path(output, filename)
        data = _checked_bytes(self.paths, str(path), maximum)
        if not data.startswith(signature):
            raise ToolError("Native document output has an invalid file signature")
        return data

    def output_path(self, output: dict[str, Any], filename: str) -> Path:
        if not isinstance(output, dict):
            raise ToolError("Native document output is invalid")
        try:
            path = self.paths.resolve(require_string(output, "path"))
        except WorkspacePathError as exc:
            raise ToolError("Native document output escaped its private job") from exc
        if path != self.paths.root / filename:
            raise ToolError("Native document output has an unexpected private filename")
        return path


def _page_count(path: Path) -> int:
    from pypdf import PdfReader

    try:
        with _open_identity_checked(path, "rb") as stream:
            reader = PdfReader(stream)
            if reader.is_encrypted and not reader.decrypt(""):
                raise ToolError("Encrypted PDF requires a password; import an unlocked copy")
            return len(reader.pages)
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"Cannot parse PDF pages: {exc}") from None


def _page_arguments(arguments: dict[str, Any], maximum: int = 8) -> dict[str, Any]:
    if "pages" in arguments:
        pages = arguments["pages"]
        if (
            not isinstance(pages, list)
            or not 1 <= len(pages) <= maximum
            or any(type(page) is not int or page < 1 for page in pages)
            or len(set(pages)) != len(pages)
        ):
            raise ToolArgumentError(
                f"pages must contain one to {maximum} distinct positive page numbers"
            )
        return {"pages": pages}
    return {
        "start_page": optional_int(arguments, "start_page", 1, minimum=1, maximum=1000000),
        "max_pages": optional_int(arguments, "max_pages", maximum, minimum=1, maximum=maximum),
    }


def _text_page(
    values: list[tuple[int, str, bool]], maximum: int, offset: int, total_pages: int
) -> dict[str, Any]:
    """Return a UTF-8 cursor, including partial individual PDF pages."""
    parts: list[str] = []
    size = 0
    for index, (number, text, incomplete) in enumerate(values):
        encoded = text.encode("utf-8")
        start = offset if index == 0 else 0
        if start > len(encoded) or (start < len(encoded) and encoded[start] & 0xC0 == 0x80):
            raise ToolArgumentError(
                "PDF offset must be within the page at a UTF-8 character boundary"
            )
        separator = "\n\n" if parts else ""
        available = max(0, maximum - size - len(separator))
        fragment = encoded[start : start + available].decode("utf-8", errors="ignore")
        consumed = len(fragment.encode("utf-8"))
        if fragment:
            parts.append(separator + fragment)
            size += len(separator) + consumed
        if consumed < len(encoded) - start or incomplete:
            return {
                "content": "".join(parts),
                "chars": size,
                "truncated": True,
                "next_page": number,
                "next_offset": start + consumed,
            }
    last = values[-1][0]
    return {
        "content": "".join(parts),
        "chars": size,
        "truncated": False,
        "next_page": last + 1 if last < total_pages else None,
        "next_offset": 0 if last < total_pages else None,
    }


def _rendered_outputs(
    job: _Job, result: dict[str, Any], requested: dict[str, Any]
) -> list[tuple[dict[str, Any], bytes]]:
    total = result.get("total_pages")
    outputs = result.get("outputs")
    if (
        type(total) is not int
        or total < 1
        or not isinstance(outputs, list)
        or not 1 <= len(outputs) <= 8
    ):
        raise ToolError("Native PDF renderer returned invalid page metadata")
    expected = requested.get("pages") or list(
        range(
            requested.get("start_page", 1),
            min(total + 1, requested.get("start_page", 1) + requested.get("max_pages", 8)),
        )
    )
    if (
        any(not isinstance(item, dict) or type(item.get("page")) is not int for item in outputs)
        or [item.get("page") for item in outputs] != expected
    ):
        raise ToolError("Native PDF renderer returned unexpected page numbers")
    pages = []
    for item in outputs:
        if item.get("media_type") != "image/png" or any(
            type(item.get(key)) is not int or not 1 <= item[key] <= 1600
            for key in ("width", "height")
        ):
            raise ToolError("Native PDF renderer returned invalid image metadata")
        data = job.output(item, f"page-{item['page']}.png", _MAX_IMAGE_BYTES, _PNG)
        pages.append((item, data))
    return pages


class _NativeTool:
    hard_cancellable = False
    _SPEC: ToolSpec

    def __init__(self, workspace: WorkspacePaths | StrPath, *, bridge: Any = None):
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self._bridge = bridge

    @property
    def bridge(self) -> Any:
        return self._bridge if self._bridge is not None else _bridge()

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC


class AndroidReadDocumentTool(_NativeTool):
    _SPEC = ToolSpec(
        name="read_document",
        description=(
            "Read PDF, DOCX, XLSX or text in the current workspace. PDFs use reliable text "
            "extraction or bundled local Chinese/English OCR for scanned/unmapped pages; OCR "
            "may contain recognition errors. start_page is one-based; read next_page to "
            "continue using next_page as start_page and next_offset as offset "
            "(up to eight PDF pages per call). offset is a UTF-8 byte cursor within the "
            "first returned page. max_chars limits UTF-8 bytes. "
            "PDFs are streamed from disk with no fixed file-size limit."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "max_chars": {"type": "integer", "minimum": 1024, "maximum": 262144},
                "start_page": {"type": "integer", "minimum": 1, "maximum": 1000000},
                "max_pages": {"type": "integer", "minimum": 1, "maximum": 8},
                "offset": {"type": "integer", "minimum": 0},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await _settled(asyncio.to_thread(self._read, arguments))

    def _read(self, arguments: dict[str, Any]) -> str:
        raw = require_string(arguments, "path")
        path = self.paths.resolve(raw)
        if path.suffix.casefold() != ".pdf":
            return ReadDocumentTool(self.paths)._execute_sync(arguments)
        maximum = optional_int(
            arguments, "max_chars", _MAX_TEXT_BYTES, minimum=1024, maximum=_MAX_TEXT_BYTES
        )
        selected = _page_arguments(arguments)
        offset = optional_int(arguments, "offset", 0, minimum=0, maximum=(1 << 63) - 1)
        with _Job(self.bridge) as job:
            snapshot, digest = job.stage_from(self.paths, raw)
            total = _page_count(snapshot)
            start = selected["start_page"]
            if start > total:
                raise ToolError(f"start_page {start} exceeds the {total} PDF pages")
            end = min(total, start + selected["max_pages"] - 1)
            warnings = []
            values_by_page: dict[int, tuple[int, str, bool]] = {}
            ocr_pages = []
            for page in range(start, end + 1):
                try:
                    with _open_identity_checked(snapshot, "rb") as stream:
                        text, incomplete = _pdf_text(
                            snapshot,
                            maximum + (offset if page == start else 0) + 4,
                            start_page=page,
                            max_pages=1,
                            stream=stream,
                        )
                    values_by_page[page] = (page, text.lstrip("\n"), incomplete)
                except ToolError as exc:
                    ocr_pages.append(page)
                    warnings.append(str(exc).replace(str(snapshot), raw))
            empty_pages: list[int] = []
            text_pages = len(values_by_page)
            if ocr_pages:
                warnings.append(
                    "On-device OCR was used; verify critical names, numbers and formatting "
                    "against the original PDF."
                )
                selected_ocr = {"pages": ocr_pages}
                result = job.execute(
                    {"action": "render_pdf", **selected_ocr, "max_dimension": 1600, "ocr": True}
                )
                pages = _rendered_outputs(job, result, selected_ocr)
                if result["total_pages"] != total:
                    raise ToolError("Native renderer and text parser disagree about PDF page count")
                for item, _data in pages:
                    value = item.get("ocr_text")
                    if not isinstance(value, str):
                        raise ToolError("Native OCR returned no text result") from None
                    if not value.strip():
                        empty_pages.append(item["page"])
                    values_by_page[item["page"]] = (
                        item["page"],
                        f"[Page {item['page']}]\n{value}",
                        False,
                    )
                if not text_pages and len(empty_pages) == len(pages):
                    raise ToolError(
                        "No text was recognized in the selected PDF pages; "
                        "the pages may be blank or unreadable"
                    ) from None
            method = "mixed" if ocr_pages and text_pages else "ocr" if ocr_pages else "text"
            values = [values_by_page[page] for page in range(start, end + 1)]
            page_result = _text_page(values, maximum, offset, total)
            return json_result(
                {
                    "path": self.paths.relative(path),
                    "media_type": "application/pdf",
                    "sha256": digest,
                    **page_result,
                    "extraction_method": method,
                    "warnings": warnings,
                    "empty_pages": empty_pages,
                    "total_pages": total,
                    "start_page": start,
                    "offset": offset,
                }
            )


class AndroidRenderPdfTool(_NativeTool):
    _SPEC = ToolSpec(
        name="render_pdf",
        description=(
            "Attach up to four selected PDF pages as real images for visual inspection by "
            "a vision-capable model. pages are one-based. Images are private artifacts and "
            "do not create workspace files. Use read_document for text/OCR. "
            "PDFs are streamed from disk with no fixed file-size limit."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "pages": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 4,
                    "uniqueItems": True,
                    "items": {"type": "integer", "minimum": 1},
                },
                "start_page": {"type": "integer", "minimum": 1, "maximum": 1000000},
                "max_pages": {"type": "integer", "minimum": 1, "maximum": 4},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        raise ToolError("PDF rendering requires session artifact recording support")

    def _render(
        self, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], list[tuple[dict[str, Any], bytes]]]:
        raw = require_string(arguments, "path")
        selected = _page_arguments(arguments, maximum=4)
        with _Job(self.bridge) as job:
            _, digest = job.stage_from(self.paths, raw)
            result = job.execute(
                {"action": "render_pdf", **selected, "max_dimension": 1600, "ocr": False}
            )
            outputs = _rendered_outputs(job, result, selected)
            return {
                "path": self.paths.relative(self.paths.resolve(raw)),
                "sha256": digest,
                "total_pages": result["total_pages"],
                "next_page": result.get("next_page"),
            }, outputs

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        if context.record_artifact is None:
            raise ToolError("PDF rendering requires session artifact recording support")
        result, outputs = await _settled(asyncio.to_thread(self._render, arguments))
        pages = []
        for item, data in outputs:
            digest = hashlib.sha256(data).hexdigest()
            path = f"pdf-pages/{digest}-page-{item['page']}.png"
            await context.record_artifact(BinaryArtifact(digest, data))
            await context.record_event(
                Event(
                    session_id=context.session_id,
                    type="image.attached",
                    data={
                        "attempt_id": context.attempt_id,
                        "path": path,
                        "media_type": "image/png",
                        "sha256": digest,
                        "bytes": len(data),
                    },
                    causation_id=context.started_event_id,
                    correlation_id=context.correlation_id,
                )
            )
            pages.append(
                {
                    "page": item["page"],
                    "path": path,
                    "sha256": digest,
                    "bytes": len(data),
                    "media_type": "image/png",
                    "width": item["width"],
                    "height": item["height"],
                }
            )
        return json_result({**result, "pages": pages, "requires_vision": True})


class AndroidCreatePdfTool(_NativeTool):
    _SPEC = ToolSpec(
        name="create_pdf",
        description=(
            "Create a real paginated A4 PDF with a title and plain text, including Chinese, "
            "in the workspace. Use expected_sha256=null for a new file; replacing an existing "
            "PDF requires its observed SHA-256. Parent directory must exist. Up to 262144 "
            "text characters and 200 pages. Creates text reports; arbitrary existing-PDF "
            "edits require other tools. PDF file bytes have no fixed size limit; available "
            "storage and the device's memory still constrain processing and rollback preimages."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "title": {"type": "string", "maxLength": 1024},
                "content": {"type": "string", "minLength": 1, "maxLength": 262144},
                "font_size": {"type": "integer", "minimum": 8, "maximum": 28},
                "page_size": {"type": "string", "enum": ["A4"]},
                "expected_sha256": {"type": ["string", "null"]},
            },
            "required": ["path", "content", "expected_sha256"],
            "additionalProperties": False,
        },
        side_effect="write",
        capability=Capability.WORKSPACE_WRITE,
        durable_preimage_checkpoint=True,
    )

    def _destination(
        self, arguments: dict[str, Any], *, retain_preimage: bool = True
    ) -> tuple[Path, str | None, bytes | None]:
        path = self.paths.resolve(require_string(arguments, "path"))
        if path.suffix.casefold() != ".pdf" or is_sensitive_workspace_path(
            self.paths.relative(path)
        ):
            raise ToolArgumentError("PDF output must use an allowed workspace path ending in .pdf")
        if not path.parent.is_dir():
            raise ToolError("PDF output parent directory must already exist")
        expected = expected_sha256(arguments)
        if retain_preimage:
            preimage = _read_preimage(path, expected, None)
        else:
            _check_preimage(path, expected, None)
            preimage = None
        return path, expected, preimage

    def _build(self, arguments: dict[str, Any], job: _Job) -> _PdfExport:
        content = require_string(arguments, "content")
        title = require_string(arguments, "title", allow_empty=True) if "title" in arguments else ""
        if len(title) > 1024 or len(content) > 262144:
            raise ToolArgumentError("PDF title or content exceeds its character limit")
        if arguments.get("page_size", "A4") != "A4":
            raise ToolArgumentError("PDF page_size must be A4")
        font_size = optional_int(arguments, "font_size", 12, minimum=8, maximum=28)
        result = job.execute(
            {
                "action": "create_pdf",
                "title": title,
                "content": content,
                "page_size": "A4",
                "font_size": font_size,
            }
        )
        outputs = result.get("outputs")
        if (
            not isinstance(outputs, list)
            or len(outputs) != 1
            or not isinstance(outputs[0], dict)
            or outputs[0].get("media_type") != "application/pdf"
        ):
            raise ToolError("Native PDF export returned an invalid output")
        output = job.output_path(outputs[0], "output.pdf")
        size, digest = _checked_copy(job.paths, str(output))
        total = _page_count(output)
        if not 1 <= total <= 200 or result.get("total_pages") != total:
            raise ToolError("Native PDF export returned invalid page metadata")
        return _PdfExport(output, total, digest, size)

    def _write(
        self, path: Path, expected: str | None, job: _Job, export: _PdfExport
    ) -> str:
        target = self.paths.resolve(path)
        parent = self.paths.resolve(target.parent)
        _check_preimage(target, expected, None)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                size, digest = _checked_copy(job.paths, str(export.path), stream)
                if (size, digest) != (export.byte_count, export.sha256):
                    raise ConcurrentModificationError("Native PDF output changed before saving")
                stream.flush()
                os.fsync(stream.fileno())
            if self.paths.resolve(target) != target or self.paths.resolve(parent) != parent:
                raise ConcurrentModificationError("PDF output path changed during write")
            _check_preimage(target, expected, None)
            durable_replace(temporary, target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return json_result(
            {
                "path": self.paths.relative(target),
                "media_type": "application/pdf",
                "sha256": export.sha256,
                "bytes_written": export.byte_count,
                "total_pages": export.total_pages,
            }
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        path, expected, _ = await _settled(
            asyncio.to_thread(self._destination, arguments, retain_preimage=False)
        )
        with _Job(self.bridge) as job:
            export = await _settled(asyncio.to_thread(self._build, arguments, job))
            return await _settled(asyncio.to_thread(self._write, path, expected, job, export))

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        path, expected, preimage = await _settled(asyncio.to_thread(self._destination, arguments))
        with _Job(self.bridge) as job:
            export = await _settled(asyncio.to_thread(self._build, arguments, job))

            async def commit() -> str:
                await context.prepare_file_checkpoint(
                    FileCheckpoint(
                        attempt_id=context.attempt_id,
                        session_id=context.session_id,
                        workspace=str(self.paths.root),
                        started_event_id=context.started_event_id,
                        relative_path=self.paths.relative(path),
                        preimage_sha256=expected,
                        preimage=preimage,
                        postimage_sha256=export.sha256,
                        created_at=datetime.now(UTC).isoformat(),
                    )
                )
                result = await asyncio.to_thread(self._write, path, expected, job, export)
                await context.record_event(
                    Event(
                        session_id=context.session_id,
                        type="file.version.recorded",
                        data={
                            "attempt_id": context.attempt_id,
                            "path": self.paths.relative(path),
                            "sha256": export.sha256,
                            "bytes": export.byte_count,
                        },
                        causation_id=context.started_event_id,
                        correlation_id=context.correlation_id,
                    )
                )
                return result

            return await _settled(commit())


@dataclass(frozen=True)
class _PdfExport:
    path: Path
    total_pages: int
    sha256: str
    byte_count: int
