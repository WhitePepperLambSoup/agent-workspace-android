"""Mail merge: a Word template filled once per row of a table.

Fields are written ``{{姓名}}`` (also when Word split them across runs) or as Word merge fields
(MERGEFIELD 姓名). A field keeps the formatting of the text where it starts.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any
from xml.etree import ElementTree as ET

from agent_workspace.office.ooxml import XML_SPACE, OfficeError, Package, W, clean, q
from agent_workspace.office.tables import display
from agent_workspace.office.word import DOCUMENT, open_docx, paragraphs, read_paragraph, text_parts

_FIELD = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_MERGEFIELD = re.compile(r"MERGEFIELD\s+\"?([^\"\\]+?)\"?(?:\s+\\|\s*$)")
_R, _T, _RPR = q(W, "r"), q(W, "t"), q(W, "rPr")


def template_fields(data: bytes) -> list[str]:
    """The field names a template uses, in order of first use."""
    package = open_docx(data)
    names: list[str] = []
    for paragraph in paragraphs(package, text_parts(package)):
        for match in _FIELD.finditer(paragraph.text):
            if match.group(1) not in names:
                names.append(match.group(1))
    for part in text_parts(package):
        for name in _merge_field_names(package.xml(part).root):
            if name not in names:
                names.append(name)
    return names


def _merge_field_names(root: ET.Element) -> list[str]:
    names = []
    for simple in root.iter(q(W, "fldSimple")):
        match = _MERGEFIELD.search(simple.get(q(W, "instr"), "").strip())
        if match:
            names.append(match.group(1).strip())
    for instruction in root.iter(q(W, "instrText")):
        match = _MERGEFIELD.search((instruction.text or "").strip())
        if match:
            names.append(match.group(1).strip())
    return names


def _value(values: Mapping[str, Any], name: str, missing: set[str]) -> str:
    if name in values:
        return display(values[name])
    for key, value in values.items():
        if key.strip().casefold() == name.strip().casefold():
            return display(value)
    missing.add(name)
    return ""


def _fill_braces(package: Package, part: str, values: Mapping[str, Any], missing: set[str]) -> int:
    count = 0
    for element in list(package.xml(part).root.iter(q(W, "p"))):
        paragraph = read_paragraph(part, element)
        matches = list(_FIELD.finditer(paragraph.text))
        for match in reversed(matches):
            paragraph = read_paragraph(part, element)
            pieces = [
                piece
                for piece in paragraph.pieces
                if piece.end > match.start() and piece.start < match.end()
            ]
            if not pieces or any(piece.child.tag != _T for piece in pieces):
                continue
            replacement = _value(values, match.group(1), missing)
            for index, piece in enumerate(pieces):
                text = piece.child.text or ""
                local_start = max(0, match.start() - piece.start)
                local_end = min(len(text), match.end() - piece.start)
                new = (
                    text[:local_start]
                    + (clean(replacement) if index == 0 else "")
                    + text[local_end:]
                )
                piece.child.text = new
                piece.child.set(XML_SPACE, "preserve")
            count += 1
    return count


def _fill_merge_fields(root: ET.Element, values: Mapping[str, Any], missing: set[str]) -> int:
    count = 0
    # Simple fields: replaced by their result runs holding the value.
    parents = {child: parent for parent in root.iter() for child in parent}
    for simple in list(root.iter(q(W, "fldSimple"))):
        match = _MERGEFIELD.search(simple.get(q(W, "instr"), "").strip())
        if not match:
            continue
        parent = parents[simple]
        first_run = simple.find(_R)
        run = ET.Element(_R)
        properties = first_run.find(_RPR) if first_run is not None else None
        if properties is not None:
            run.append(copy.deepcopy(properties))
        text = ET.SubElement(run, _T)
        text.text = clean(_value(values, match.group(1).strip(), missing))
        text.set(XML_SPACE, "preserve")
        position = list(parent).index(simple)
        parent.remove(simple)
        parent.insert(position, run)
        count += 1
    # Complex fields: begin … instrText … separate … result … end, within one paragraph.
    for paragraph in list(root.iter(q(W, "p"))):
        runs = [child for child in paragraph if child.tag == _R]
        index = 0
        while index < len(runs):
            char = runs[index].find(q(W, "fldChar"))
            if char is None or char.get(q(W, "fldCharType")) != "begin":
                index += 1
                continue
            instruction, separate, end = "", None, None
            for later in range(index + 1, len(runs)):
                piece = runs[later].find(q(W, "instrText"))
                if piece is not None:
                    instruction += piece.text or ""
                mark = runs[later].find(q(W, "fldChar"))
                if mark is not None and mark.get(q(W, "fldCharType")) == "separate":
                    separate = later
                if mark is not None and mark.get(q(W, "fldCharType")) == "end":
                    end = later
                    break
            match = _MERGEFIELD.search(instruction.strip())
            if not match or end is None:
                index += 1
                continue
            template = (
                runs[separate + 1] if separate is not None and separate + 1 < end else runs[index]
            )
            run = ET.Element(_R)
            properties = template.find(_RPR)
            if properties is not None:
                run.append(copy.deepcopy(properties))
            text = ET.SubElement(run, _T)
            text.text = clean(_value(values, match.group(1).strip(), missing))
            text.set(XML_SPACE, "preserve")
            position = list(paragraph).index(runs[index])
            for old in runs[index : end + 1]:
                paragraph.remove(old)
            paragraph.insert(position, run)
            count += 1
            runs = [child for child in paragraph if child.tag == _R]
            index = runs.index(run) + 1
    return count


def fill(template: bytes, values: Mapping[str, Any]) -> tuple[bytes, list[str]]:
    """The template with every field filled; the field names that had no value."""
    package = open_docx(template)
    missing: set[str] = set()
    for part in text_parts(package):
        _fill_merge_fields(package.xml(part).root, values, missing)
        _fill_braces(package, part, values, missing)
    return package.to_bytes(), sorted(missing)


def combine(documents: list[bytes]) -> bytes:
    """One document holding each filled copy on its own pages (the first copy's layout)."""
    if not documents:
        raise OfficeError("nothing to combine")
    first = open_docx(documents[0])
    root = first.xml(DOCUMENT).root
    body = root.find(q(W, "body"))
    if body is None:
        raise OfficeError("the template has no body")
    section = body.find(q(W, "sectPr"))
    if section is not None:
        body.remove(section)
    for data in documents[1:]:
        page_break = ET.SubElement(body, q(W, "p"))
        run = ET.SubElement(page_break, _R)
        ET.SubElement(run, q(W, "br"), {q(W, "type"): "page"})
        other = open_docx(data).xml(DOCUMENT).root.find(q(W, "body"))
        if other is None:
            continue
        for child in other:
            if child.tag != q(W, "sectPr"):
                body.append(copy.deepcopy(child))
    if section is not None:
        body.append(section)
    return first.to_bytes()


def file_name(pattern: str, values: Mapping[str, Any], number: int) -> str:
    """A file name from a pattern like "{{姓名}}-录用通知" (without the extension)."""
    missing: set[str] = set()
    name = (
        _FIELD.sub(lambda match: _value(values, match.group(1), missing), pattern)
        if pattern
        else ""
    )
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "-", name).strip(" .-")
    return name[:80] or f"{number:03d}"


__all__ = ["combine", "file_name", "fill", "template_fields"]
