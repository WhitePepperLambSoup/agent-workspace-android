from __future__ import annotations

import asyncio
import unicodedata
import zipfile
from pathlib import Path
from typing import Any, BinaryIO
from xml.etree import ElementTree

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import (
    ToolError,
    json_result,
    optional_int,
    require_string,
)
from agent_workspace.tools.paths import StrPath, WorkspacePaths

_MAX_DOCUMENT_BYTES = 16 * 1024 * 1024
_MAX_ZIP_MEMBER_BYTES = 64 * 1024 * 1024
_MAX_TEXT_CHARS = 256 * 1024
_PDF_MAGIC = b"%PDF"
_DOCX_CONTENT_TYPES = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
)
_XLSX_CONTENT_TYPES = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
)
_NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}


def _bounded_text(value: str, maximum: int) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum:
        return value, False
    return encoded[:maximum].decode("utf-8", errors="ignore"), True


def _pdf_text(
    path: Path,
    maximum: int,
    *,
    start_page: int = 1,
    max_pages: int | None = None,
    stream: BinaryIO | None = None,
) -> tuple[str, bool]:
    """Read a one-based page range, rejecting text that cannot be decoded reliably."""
    from pypdf import PdfReader
    from pypdf.generic import ArrayObject, DictionaryObject, NullObject, StreamObject

    try:
        reader = PdfReader(stream if stream is not None else str(path))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ToolError(
                f"encrypted PDF requires a password: {path}; save an unlocked copy before reading"
            )
    except ToolError:
        raise
    except Exception as exc:  # pypdf raises several error types across versions
        raise ToolError(f"cannot parse PDF: {path}: {exc}") from None
    parts: list[str] = []
    total = 0
    truncated = False
    has_text = False
    mapping_problems: list[str] = []
    try:
        pages = reader.pages
        page_count = len(pages)
        if start_page < 1 or (max_pages is not None and max_pages < 1):
            raise ToolError("PDF start_page and max_pages must be positive integers")
        if start_page > page_count and page_count:
            raise ToolError(f"PDF start_page {start_page} exceeds the {page_count} pages: {path}")
        end_page = min(page_count, start_page + max_pages - 1) if max_pages else page_count
        for index in range(start_page, end_page + 1):
            mapping_problems.clear()

            def check_unicode_mapping(
                text: str,
                _cm: list[float],
                _tm: list[float],
                font: DictionaryObject | None,
                _font_size: float,
                _page_number: int = index,
            ) -> None:
                if (
                    mapping_problems
                    or not text.strip()
                    or font is None
                    or font.get("/Subtype") != "/Type0"
                ):
                    return
                encoding = font.get("/Encoding")
                if encoding is None:
                    return
                encoding = encoding.get_object()
                if encoding not in ("/Identity-H", "/Identity-V"):
                    return
                unicode_map = font.get("/ToUnicode")
                if unicode_map is not None:
                    unicode_map = unicode_map.get_object()
                if isinstance(unicode_map, StreamObject) and unicode_map.get_data().strip():
                    return
                font_name = str(font.get("/BaseFont", "unknown font"))[:160]
                # pypdf catches visitor exceptions inside Form XObjects. Report the
                # problem after extraction so nested text cannot hide a missing map.
                mapping_problems.append(
                    f"cannot reliably extract PDF page {_page_number}: "
                    f"font {font_name} ({encoding}) "
                    "has no usable ToUnicode mapping; CID identifiers are not Unicode text. "
                    "Use page rendering and OCR."
                )

            try:
                page = pages[index - 1]
                contents = page.get("/Contents")
                if contents is not None and not isinstance(
                    contents.get_object(), (StreamObject, ArrayObject, NullObject)
                ):
                    raise ToolError(
                        f"cannot extract PDF page {index}: invalid page contents; "
                        "use page rendering and OCR"
                    )
                text = page.extract_text(visitor_text=check_unicode_mapping) or ""
                if mapping_problems:
                    raise ToolError(mapping_problems[0])
                # Android fonts can map ordinary Han glyphs to compatibility radicals.
                text = "".join(
                    unicodedata.normalize("NFKC", char)
                    if 0x2F00 <= ord(char) <= 0x2FDF
                    or 0xF900 <= ord(char) <= 0xFAFF
                    or 0x2F800 <= ord(char) <= 0x2FA1F
                    else char
                    for char in text
                )
            except ToolError:
                raise
            except Exception as exc:
                raise ToolError(
                    f"cannot extract PDF page {index}: {path}: {exc}; use page rendering and OCR"
                ) from None
            has_text = has_text or bool(text.strip())
            rendered = f"\n[Page {index}]\n{text}" if index > 1 else text
            encoded = rendered.encode("utf-8")
            if total + len(encoded) > maximum:
                remaining = max(0, maximum - total)
                parts.append(encoded[:remaining].decode("utf-8", errors="ignore"))
                truncated = True
                break
            parts.append(rendered)
            total += len(encoded)
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(
            f"cannot parse PDF pages: {path}: {exc}; use page rendering and OCR"
        ) from None
    if not has_text:
        raise ToolError(
            f"no extractable text in PDF: {path}; "
            "the selected pages may be scanned images or blank. "
            "Use page rendering and OCR."
        )
    return "".join(parts), truncated


def _read_zip_member(archive: zipfile.ZipFile, name: str, maximum: int) -> bytes:
    """Read a ZIP member after checking its decompressed size (ZIP-bomb guard)."""
    info = archive.getinfo(name)
    if info.file_size > maximum:
        raise ToolError(f"{name} decompresses beyond the {maximum}-byte limit")
    raw = archive.read(info)
    if len(raw) > maximum:
        raise ToolError(f"{name} decompresses beyond the {maximum}-byte limit")
    return raw


def _docx_text(path: Path, maximum: int) -> tuple[str, bool]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            target = next(
                (name for name in names if name == "word/document.xml"),
                None,
            )
            if target is None:
                raise ToolError("DOCX archive has no word/document.xml")
            raw = _read_zip_member(archive, target, _MAX_ZIP_MEMBER_BYTES)
    except zipfile.BadZipFile:
        raise ToolError("document is not a valid ZIP-based Office file") from None
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise ToolError(f"cannot parse DOCX XML: {exc}") from None
    paragraphs: list[str] = []
    total = 0
    truncated = False
    for paragraph in root.iter(f"{{{_NAMESPACES['w']}}}p"):
        runs = [(node.text or "") for node in paragraph.iter(f"{{{_NAMESPACES['w']}}}t")]
        text = "".join(runs)
        if not text.strip():
            continue
        encoded = (text + "\n").encode("utf-8")
        if total + len(encoded) > maximum:
            prefix, _ = _bounded_text(text, maximum - total)
            if prefix:
                paragraphs.append(prefix)
            truncated = True
            break
        paragraphs.append(text)
        total += len(encoded)
    return "\n".join(paragraphs), truncated


def _xlsx_text(path: Path, maximum: int) -> tuple[str, bool]:
    try:
        with zipfile.ZipFile(path) as archive:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared_root = None
                try:
                    shared_root = ElementTree.fromstring(
                        _read_zip_member(archive, "xl/sharedStrings.xml", _MAX_ZIP_MEMBER_BYTES)
                    )
                except (ToolError, ElementTree.ParseError):
                    shared_root = None
                if shared_root is not None:
                    for item in shared_root.iter(f"{{{_NAMESPACES['s']}}}si"):
                        shared.append(
                            "".join(
                                node.text or "" for node in item.iter(f"{{{_NAMESPACES['s']}}}t")
                            )
                        )
            sheet_names = [
                name
                for name in archive.namelist()
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
            ]
            sheet_names.sort()
            parts: list[str] = []
            total = 0
            truncated = False
            for sheet in sheet_names:
                try:
                    root = ElementTree.fromstring(
                        _read_zip_member(archive, sheet, _MAX_ZIP_MEMBER_BYTES)
                    )
                except (ToolError, ElementTree.ParseError):
                    continue
                wrote_sheet = False
                for row in root.iter(f"{{{_NAMESPACES['s']}}}row"):
                    cells: list[str] = []
                    for cell in row.iter(f"{{{_NAMESPACES['s']}}}c"):
                        cell_type = cell.get("t")
                        value = ""
                        inline = next(cell.iter(f"{{{_NAMESPACES['s']}}}t"), None)
                        if inline is not None and inline.text:
                            value = inline.text
                        else:
                            raw_value = next(cell.iter(f"{{{_NAMESPACES['s']}}}v"), None)
                            if raw_value is not None and raw_value.text:
                                if cell_type == "s":
                                    try:
                                        value = shared[int(raw_value.text)]
                                    except (ValueError, IndexError):
                                        value = ""
                                else:
                                    value = raw_value.text
                        cells.append(value)
                    line = "\t".join(cells).rstrip("\t")
                    rendered = (f"[{sheet}]\n" if not wrote_sheet else "") + line + "\n"
                    encoded_line = rendered.encode("utf-8")
                    if total + len(encoded_line) > maximum:
                        prefix, _ = _bounded_text(rendered, maximum - total)
                        if prefix:
                            parts.append(prefix)
                            total += len(prefix.encode("utf-8"))
                        truncated = True
                        break
                    parts.append(rendered)
                    total += len(encoded_line)
                    wrote_sheet = True
                if truncated:
                    break
            return "".join(parts), truncated
    except zipfile.BadZipFile:
        raise ToolError("document is not a valid ZIP-based Office file") from None


def _read_document_sync(paths: WorkspacePaths, raw_path: str, maximum: int) -> str:
    path = paths.resolve(raw_path)
    if path.is_dir():
        raise ToolError(f"path is a directory: {path}")
    try:
        metadata = path.stat()
    except OSError as exc:
        raise ToolError(f"cannot read document: {path}") from exc
    if metadata.st_size > _MAX_DOCUMENT_BYTES:
        raise ToolError(f"document exceeds the {_MAX_DOCUMENT_BYTES}-byte limit: {path}")
    try:
        with path.open("rb") as stream:
            prefix = stream.read(8)
    except OSError as exc:
        raise ToolError(f"cannot read document: {path}") from exc
    suffix = path.suffix.casefold()
    if suffix == ".pdf" and (prefix.startswith(_PDF_MAGIC) or not prefix.startswith(b"PK")):
        text, truncated = _pdf_text(path, maximum)
        media_type = "application/pdf"
    elif suffix in {".docx", ".doc"} and prefix.startswith(b"PK"):
        text, truncated = _docx_text(path, maximum)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif suffix in {".xlsx", ".xls"} and prefix.startswith(b"PK"):
        text, truncated = _xlsx_text(path, maximum)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif suffix in {".txt", ".md", ".csv", ".json", ".log", ".toml", ".yaml", ".yml"}:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ToolError(f"cannot read document: {path}") from exc
        text, truncated = _bounded_text(
            raw.decode("utf-8", errors="replace"),
            maximum,
        )
        media_type = "text/plain"
    else:
        raise ToolError(f"unsupported document format: {suffix or path.name}")
    return json_result(
        {
            "path": paths.relative(path),
            "media_type": media_type,
            "chars": len(text.encode("utf-8")),
            "truncated": truncated,
            "content": text,
        }
    )


class ReadDocumentTool:
    """Extract bounded text from PDF, DOCX, XLSX, and plain-text documents."""

    hard_cancellable = True
    _SPEC = ToolSpec(
        name="read_document",
        description=(
            "Extract bounded UTF-8 text from a workspace document: PDF, DOCX, XLSX, or a "
            "plain-text file. max_chars limits UTF-8 bytes. PDF fonts need readable Unicode "
            "mappings; scanned or unmapped PDFs need page rendering and OCR. "
            "Binary Word/Excel files and PDFs over 16 MiB are unsupported."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "max_chars": {"type": "integer", "minimum": 1024, "maximum": 262144},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await asyncio.to_thread(self._execute_sync, arguments)

    def _execute_sync(self, arguments: dict[str, Any]) -> str:
        raw_path = require_string(arguments, "path")
        maximum = optional_int(
            arguments,
            "max_chars",
            _MAX_TEXT_CHARS,
            minimum=1024,
            maximum=262144,
        )
        return _read_document_sync(self.paths, raw_path, maximum)
