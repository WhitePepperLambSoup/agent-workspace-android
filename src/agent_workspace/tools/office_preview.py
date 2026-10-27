"""What a Word, Excel or PowerPoint file shows, as data the desktop window can draw.

``preview_office`` reads a .docx into headings, paragraphs (with bold and italic), list items,
tables and image markers; an .xlsx into sheets of cells (shared strings, dates from number
formats, formula results, merged areas); a .pptx into slides in presentation order (title,
bullets with levels, tables, picture counts, speaker notes). It reads only: nothing executes,
and parts larger than a set size are refused, so a crafted archive cannot exhaust memory.
"""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from datetime import datetime, timedelta
from typing import Any
from xml.etree import ElementTree

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

_MAX_PART_BYTES = 48 * 1024 * 1024
_MAX_TOTAL_BYTES = 192 * 1024 * 1024
MAX_BLOCKS = 3000
MAX_TEXT = 300_000
MAX_ROWS = 500
MAX_COLUMNS = 60
MAX_SLIDES = 300
_HEADING = re.compile(r"^(?:heading|标题|見出し)\s*(\d)$", re.I)
_DATE_FORMATS = frozenset({14, 15, 16, 17, 18, 19, 20, 21, 22, 45, 46, 47})


class PreviewError(ValueError):
    """The file is not a readable document of its kind; the message is a short reason code."""


class _Package:
    def __init__(self, data: bytes) -> None:
        try:
            self.archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise PreviewError("not_office") from None
        infos = self.archive.infolist()
        if sum(info.file_size for info in infos) > _MAX_TOTAL_BYTES:
            raise PreviewError("too_large")
        self.names = {info.filename for info in infos}
        self.sizes = {info.filename: info.file_size for info in infos}

    def xml(self, name: str) -> ElementTree.Element | None:
        if name not in self.names:
            return None
        if self.sizes[name] > _MAX_PART_BYTES:
            raise PreviewError("too_large")
        try:
            return ElementTree.fromstring(self.archive.read(name))
        except ElementTree.ParseError:
            raise PreviewError("unreadable") from None

    def relationships(self, part: str) -> dict[str, tuple[str, str]]:
        """A part's relationships: id -> (type name, target part)."""
        folder, file = posixpath.split(part)
        root = self.xml(posixpath.join(folder, "_rels", f"{file}.rels"))
        found: dict[str, tuple[str, str]] = {}
        for item in root.iter(f"{_REL}Relationship") if root is not None else ():
            target = item.get("Target", "")
            if item.get("TargetMode") == "External":
                resolved = target
            elif target.startswith("/"):
                resolved = target.lstrip("/")
            else:
                resolved = posixpath.normpath(posixpath.join(folder, target))
            found[item.get("Id", "")] = (item.get("Type", "").rsplit("/", 1)[-1], resolved)
        return found


class _Budget:
    def __init__(self) -> None:
        self.text = 0
        self.truncated = False

    def take(self, text: str) -> str:
        room = MAX_TEXT - self.text
        if room <= 0:
            self.truncated = True
            return ""
        if len(text) > room:
            self.truncated = True
            text = text[:room]
        self.text += len(text)
        return text


# ---- Word ---------------------------------------------------------------------------------------


def _word_styles(package: _Package) -> dict[str, tuple[str, int | None]]:
    """Style id -> (kind, heading level): headings by name or outline level, title, quote, code."""
    root = package.xml("word/styles.xml")
    styles: dict[str, tuple[str, int | None]] = {}
    for style in root.iter(f"{_W}style") if root is not None else ():
        style_id = style.get(f"{_W}styleId") or ""
        name_element = style.find(f"{_W}name")
        name = (name_element.get(f"{_W}val") if name_element is not None else "") or ""
        outline = style.find(f"{_W}pPr/{_W}outlineLvl")
        heading = _HEADING.match(name.strip())
        if heading:
            styles[style_id] = ("heading", int(heading.group(1)))
        elif name.lower() in {"title", "标题"}:
            styles[style_id] = ("title", None)
        elif outline is not None and (outline.get(f"{_W}val") or "").isdigit():
            styles[style_id] = ("heading", int(outline.get(f"{_W}val") or "0") + 1)
        elif "quote" in name.lower() or "引用" in name:
            styles[style_id] = ("quote", None)
        elif name.lower() in {"code", "html preformatted", "plain text"}:
            styles[style_id] = ("code", None)
    return styles


def _ordered_lists(package: _Package) -> set[tuple[str, str]]:
    """(numId, level) pairs that number their items instead of using bullets."""
    root = package.xml("word/numbering.xml")
    if root is None:
        return set()
    formats: dict[str, dict[str, str]] = {}
    for abstract in root.iter(f"{_W}abstractNum"):
        levels: dict[str, str] = {}
        for level_element in abstract.iter(f"{_W}lvl"):
            format_element = level_element.find(f"{_W}numFmt")
            levels[level_element.get(f"{_W}ilvl") or "0"] = (
                format_element.get(f"{_W}val") or "" if format_element is not None else ""
            )
        formats[abstract.get(f"{_W}abstractNumId") or ""] = levels
    ordered: set[tuple[str, str]] = set()
    for number in root.iter(f"{_W}num"):
        abstract_id = number.find(f"{_W}abstractNumId")
        levels = formats.get(
            abstract_id.get(f"{_W}val") or "" if abstract_id is not None else "", {}
        )
        for level, number_format in levels.items():
            if number_format not in {"bullet", "none", ""}:
                ordered.add((number.get(f"{_W}numId") or "", level))
    return ordered


def _word_runs(paragraph: ElementTree.Element, budget: _Budget) -> tuple[list[dict[str, Any]], int]:
    runs: list[dict[str, Any]] = []
    images = 0
    for run in paragraph.iter(f"{_W}r"):
        properties = run.find(f"{_W}rPr")
        bold_element = properties.find(f"{_W}b") if properties is not None else None
        bold = bold_element is not None and bold_element.get(f"{_W}val") not in {"0", "false"}
        italic = properties is not None and properties.find(f"{_W}i") is not None
        parts: list[str] = []
        for child in run:
            if child.tag == f"{_W}t":
                parts.append(child.text or "")
            elif child.tag == f"{_W}tab":
                parts.append("\t")
            elif child.tag in {f"{_W}br", f"{_W}cr"}:
                parts.append("\n")
            elif child.tag in {f"{_W}drawing", f"{_W}pict"}:
                images += 1
        text = budget.take("".join(parts))
        if not text:
            continue
        entry: dict[str, Any] = {"text": text}
        if bold:
            entry["bold"] = True
        if italic:
            entry["italic"] = True
        if runs and {k: v for k, v in runs[-1].items() if k != "text"} == {
            k: v for k, v in entry.items() if k != "text"
        }:
            runs[-1]["text"] += text
        else:
            runs.append(entry)
    return runs, images


def _docx_blocks(package: _Package) -> dict[str, Any]:
    root = package.xml("word/document.xml")
    body = root.find(f"{_W}body") if root is not None else None
    if body is None:
        raise PreviewError("not_office")
    styles = _word_styles(package)
    ordered = _ordered_lists(package)
    budget = _Budget()
    blocks: list[dict[str, Any]] = []

    def paragraph_block(paragraph: ElementTree.Element) -> None:
        runs, images = _word_runs(paragraph, budget)
        properties = paragraph.find(f"{_W}pPr")
        style_element = properties.find(f"{_W}pStyle") if properties is not None else None
        style_id = style_element.get(f"{_W}val") or "" if style_element is not None else ""
        kind, level = styles.get(style_id, ("paragraph", None))
        numbering = properties.find(f"{_W}numPr") if properties is not None else None
        text = "".join(run["text"] for run in runs)
        if kind in {"heading", "title"} and text.strip():
            blocks.append(
                {"type": "heading", "level": 0 if kind == "title" else level, "text": text}
            )
        elif numbering is not None and text.strip():
            level_element = numbering.find(f"{_W}ilvl")
            number_element = numbering.find(f"{_W}numId")
            list_level = level_element.get(f"{_W}val") or "0" if level_element is not None else "0"
            number_id = number_element.get(f"{_W}val") or "" if number_element is not None else ""
            blocks.append(
                {
                    "type": "list",
                    "ordered": (number_id, list_level) in ordered,
                    "level": int(list_level) if list_level.isdigit() else 0,
                    "runs": runs,
                }
            )
        elif runs:
            block: dict[str, Any] = {"type": "paragraph", "runs": runs}
            if kind in {"quote", "code"}:
                block["style"] = kind
            blocks.append(block)
        for _ in range(images):
            blocks.append({"type": "image"})

    for element in body:
        if len(blocks) >= MAX_BLOCKS:
            budget.truncated = True
            break
        if element.tag == f"{_W}p":
            paragraph_block(element)
        elif element.tag == f"{_W}tbl":
            rows = []
            for row in element.iter(f"{_W}tr"):
                cells = []
                for cell in row.findall(f"{_W}tc"):
                    texts = [
                        "".join(run["text"] for run in _word_runs(paragraph, budget)[0])
                        for paragraph in cell.iter(f"{_W}p")
                    ]
                    cells.append("\n".join(text for text in texts if text))
                rows.append(cells)
                if len(rows) >= MAX_ROWS:
                    budget.truncated = True
                    break
            blocks.append({"type": "table", "rows": rows})
    return {"kind": "docx", "blocks": blocks, "truncated": budget.truncated}


# ---- Excel --------------------------------------------------------------------------------------


def _column(reference: str) -> tuple[int, int]:
    match = re.match(r"([A-Z]+)(\d+)$", reference)
    if match is None:
        return -1, -1
    index = 0
    for character in match.group(1):
        index = index * 26 + ord(character) - 64
    return int(match.group(2)), index - 1


def _shared_strings(package: _Package) -> list[str]:
    root = package.xml("xl/sharedStrings.xml")
    if root is None:
        return []
    return [
        "".join(text.text or "" for text in item.iter(f"{_S}t")) for item in root.iter(f"{_S}si")
    ]


def _date_styles(package: _Package) -> set[int]:
    root = package.xml("xl/styles.xml")
    if root is None:
        return set()
    custom: set[int] = set()
    for number_format in root.iter(f"{_S}numFmt"):
        code = re.sub(r'"[^"]*"|\[[^\]]*\]', "", number_format.get("formatCode") or "").lower()
        if re.search(r"[ymdhs]", code) and not re.fullmatch(r"[#0.,%\s]*", code):
            custom.add(int(number_format.get("numFmtId") or "0"))
    dates: set[int] = set()
    cell_formats = root.find(f"{_S}cellXfs")
    for index, xf in enumerate(cell_formats.findall(f"{_S}xf") if cell_formats is not None else []):
        number_format_id = int(xf.get("numFmtId") or "0")
        if number_format_id in _DATE_FORMATS or number_format_id in custom:
            dates.add(index)
    return dates


def _excel_date(serial: float, base_1904: bool) -> str:
    start = datetime(1904, 1, 1) if base_1904 else datetime(1899, 12, 30)
    moment = start + timedelta(days=serial)
    if serial == int(serial):
        return moment.strftime("%Y-%m-%d")
    return moment.strftime("%Y-%m-%d %H:%M" if moment.second == 0 else "%Y-%m-%d %H:%M:%S")


def _number(text: str) -> str:
    try:
        value = float(text)
    except ValueError:
        return text
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.10g}"


def _xlsx_sheets(package: _Package) -> dict[str, Any]:
    workbook = package.xml("xl/workbook.xml")
    if workbook is None:
        raise PreviewError("not_office")
    relations = package.relationships("xl/workbook.xml")
    properties = workbook.find(f"{_S}workbookPr")
    base_1904 = properties is not None and properties.get("date1904") in {"1", "true"}
    strings = _shared_strings(package)
    dates = _date_styles(package)
    budget = _Budget()
    sheets: list[dict[str, Any]] = []
    for sheet in workbook.iter(f"{_S}sheet"):
        name = sheet.get("name") or ""
        relation = relations.get(sheet.get(f"{_R}id") or "")
        root = package.xml(relation[1]) if relation else None
        if root is None:
            sheets.append({"name": name, "rows": [], "merges": [], "rowCount": 0})
            continue
        rows: list[dict[str, Any]] = []
        row_count = 0
        truncated_columns = False
        for row in root.iter(f"{_S}row"):
            row_count += 1
            if len(rows) >= MAX_ROWS:
                budget.truncated = True
                continue
            cells: list[dict[str, Any]] = []
            number = int(row.get("r") or row_count)
            for cell in row.findall(f"{_S}c"):
                row_number, column = _column(cell.get("r") or "")
                if column < 0:
                    continue
                if column >= MAX_COLUMNS:
                    truncated_columns = True
                    continue
                value_type = cell.get("t") or "n"
                value_element = cell.find(f"{_S}v")
                formula = cell.find(f"{_S}f")
                raw = value_element.text if value_element is not None and value_element.text else ""
                if value_type == "s":
                    text = strings[int(raw)] if raw.isdigit() and int(raw) < len(strings) else ""
                elif value_type == "inlineStr":
                    text = "".join(item.text or "" for item in cell.iter(f"{_S}t"))
                elif value_type == "b":
                    text = "TRUE" if raw == "1" else "FALSE" if raw else ""
                elif value_type in {"str", "e"}:
                    text = raw
                elif raw and int(cell.get("s") or "0") in dates:
                    try:
                        text = _excel_date(float(raw), base_1904)
                    except (ValueError, OverflowError):
                        text = raw
                else:
                    text = _number(raw) if raw else ""
                entry: dict[str, Any] = {"c": column, "v": budget.take(text)}
                if formula is not None and formula.text:
                    entry["f"] = budget.take("=" + formula.text)
                if entry["v"] or "f" in entry:
                    cells.append(entry)
                del row_number
            if cells:
                rows.append({"r": number, "cells": cells})
        merges = [item.get("ref") or "" for item in root.iter(f"{_S}mergeCell") if item.get("ref")][
            :500
        ]
        sheets.append(
            {
                "name": name,
                "rows": rows,
                "merges": merges,
                "rowCount": row_count,
                **({"columnsTruncated": True} if truncated_columns else {}),
            }
        )
    return {"kind": "xlsx", "sheets": sheets, "truncated": budget.truncated}


# ---- PowerPoint ---------------------------------------------------------------------------------


def _drawing_paragraphs(body: ElementTree.Element, budget: _Budget) -> list[dict[str, Any]]:
    paragraphs: list[dict[str, Any]] = []
    for paragraph in body.iter(f"{_A}p"):
        parts: list[str] = []
        for child in paragraph:
            if child.tag in {f"{_A}r", f"{_A}fld"}:
                text_element = child.find(f"{_A}t")
                parts.append(text_element.text or "" if text_element is not None else "")
            elif child.tag == f"{_A}br":
                parts.append("\n")
        text = budget.take("".join(parts))
        if not text.strip():
            continue
        properties = paragraph.find(f"{_A}pPr")
        level = properties.get("lvl") if properties is not None else None
        paragraphs.append({"text": text, "level": int(level) if level and level.isdigit() else 0})
    return paragraphs


def _slide_contents(root: ElementTree.Element, budget: _Budget) -> dict[str, Any]:
    slide: dict[str, Any] = {"title": "", "paragraphs": [], "tables": [], "images": 0}
    tree = root.find(f"{_P}cSld/{_P}spTree")
    for element in tree.iter() if tree is not None else ():
        if element.tag == f"{_P}sp":
            placeholder = element.find(f"{_P}nvSpPr/{_P}nvPr/{_P}ph")
            kind = placeholder.get("type") if placeholder is not None else None
            body = element.find(f"{_P}txBody")
            if body is None:
                continue
            paragraphs = _drawing_paragraphs(body, budget)
            if kind in {"title", "ctrTitle"} and not slide["title"]:
                slide["title"] = " ".join(item["text"] for item in paragraphs)
            elif kind in {"sldNum", "dt", "ftr"}:
                continue
            else:
                slide["paragraphs"].extend(paragraphs)
        elif element.tag == f"{_A}tbl":
            rows = []
            for row in element.iter(f"{_A}tr"):
                rows.append(
                    [
                        "\n".join(item["text"] for item in _drawing_paragraphs(cell, budget))
                        for cell in row.findall(f"{_A}tc")
                    ]
                )
            slide["tables"].append(rows[:MAX_ROWS])
        elif element.tag == f"{_P}pic":
            slide["images"] += 1
    return slide


def _pptx_slides(package: _Package) -> dict[str, Any]:
    presentation = package.xml("ppt/presentation.xml")
    if presentation is None:
        raise PreviewError("not_office")
    relations = package.relationships("ppt/presentation.xml")
    budget = _Budget()
    slides: list[dict[str, Any]] = []
    size = presentation.find(f"{_P}sldSz")
    for index, item in enumerate(presentation.iter(f"{_P}sldId"), start=1):
        if len(slides) >= MAX_SLIDES:
            budget.truncated = True
            break
        relation = relations.get(item.get(f"{_R}id") or "")
        root = package.xml(relation[1]) if relation else None
        if root is None:
            continue
        slide = _slide_contents(root, budget)
        slide["index"] = index
        for kind, target in package.relationships(relation[1]).values() if relation else ():
            if kind == "notesSlide":
                notes = package.xml(target)
                if notes is not None:
                    texts: list[str] = []
                    for shape in notes.iter(f"{_P}sp"):
                        placeholder = shape.find(f"{_P}nvSpPr/{_P}nvPr/{_P}ph")
                        body = shape.find(f"{_P}txBody")
                        if (
                            placeholder is not None
                            and placeholder.get("type") == "body"
                            and body is not None
                        ):
                            texts.extend(item["text"] for item in _drawing_paragraphs(body, budget))
                    if texts:
                        slide["notes"] = "\n".join(texts)
        slides.append(slide)
    width = int(size.get("cx") or 0) if size is not None else 0
    height = int(size.get("cy") or 0) if size is not None else 0
    return {
        "kind": "pptx",
        "slides": slides,
        "aspect": round(width / height, 4) if width and height else 16 / 9,
        "truncated": budget.truncated,
    }


def preview_office(data: bytes, suffix: str) -> dict[str, Any]:
    """The preview of a .docx, .xlsx or .pptx file's content, or PreviewError."""
    package = _Package(data)
    suffix = suffix.casefold()
    if suffix == ".docx":
        return _docx_blocks(package)
    if suffix == ".xlsx":
        return _xlsx_sheets(package)
    if suffix == ".pptx":
        return _pptx_slides(package)
    raise PreviewError("unsupported_type")
