"""Mail merge: a Word template filled once per row of a table.

Fields are written ``{{姓名}}`` (also when Word split them across runs) or as Word merge fields
(MERGEFIELD 姓名). A field keeps the formatting of the text where it starts.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET

from agent_workspace.office.ooxml import XML_SPACE, OfficeError, Package, R, W, clean, q
from agent_workspace.office.tables import display
from agent_workspace.office.word import DOCUMENT, open_docx, paragraphs, read_paragraph, text_parts

_FIELD = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_MERGEFIELD = re.compile(r"MERGEFIELD\s+\"?([^\"\\]+?)\"?(?:\s+\\|\s*$)")
_R, _T, _RPR = q(W, "r"), q(W, "t"), q(W, "rPr")
_INSTR, _FLD_CHAR = q(W, "instrText"), q(W, "fldChar")


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
    # Complex fields: begin … instrText … separate … result … end, within one paragraph. They
    # nest, as in { IF { MERGEFIELD 性别 } = "男" "先生" "女士" }: only the merge field itself
    # is replaced, and the field holding it is worked out again.
    for paragraph in list(root.iter(q(W, "p"))):
        holders: list[ET.Element] = []
        for found in _complex_fields(paragraph):
            match = _MERGEFIELD.search(found.code.strip())
            if not match or found.nested or found.end is None:
                continue
            value = clean(_value(values, match.group(1).strip(), missing))
            template = found.begin
            if found.separate is not None:
                results = _runs_between(paragraph, found.separate, found.end)
                template = results[0] if results else found.begin
            run = ET.Element(_R)
            properties = template.find(_RPR)
            if properties is not None:
                run.append(copy.deepcopy(properties))
            if found.in_code:
                # The value becomes part of the outer field's code, as Word's own merge does.
                quoted = value.replace("\\", "\\\\").replace('"', '\\"')
                text = ET.SubElement(run, _INSTR)
                text.text = quoted if found.quoted else f'"{quoted}"'
            else:
                text = ET.SubElement(run, _T)
                text.text = value
            text.set(XML_SPACE, "preserve")
            first = list(paragraph).index(found.begin)
            for old in [found.begin, *_runs_between(paragraph, found.begin, found.end), found.end]:
                paragraph.remove(old)
            paragraph.insert(first, run)
            count += 1
            holder = found.parent
            while holder is not None:
                holders.append(holder.begin)
                holder = holder.parent
        for found in _complex_fields(paragraph):
            if found.begin in holders:
                _work_out(paragraph, found)
    return count


@dataclass
class _Field:
    """A complex field within one paragraph, by the runs holding its marks."""

    begin: ET.Element
    parent: _Field | None
    code: str = ""
    separate: ET.Element | None = None
    end: ET.Element | None = None
    nested: list[_Field] = field(default_factory=list)
    # A field inside another sits in its code (perhaps within quotes there) or in its result.
    in_code: bool = False
    quoted: bool = False


def _complex_fields(paragraph: ET.Element) -> list[_Field]:
    """The paragraph's fields, each after the fields nested in it."""
    done: list[_Field] = []
    open_fields: list[_Field] = []
    for run in [child for child in paragraph if child.tag == _R]:
        for item in run:
            if item.tag == _INSTR and open_fields:
                open_fields[-1].code += item.text or ""
            elif item.tag == _FLD_CHAR:
                kind = item.get(q(W, "fldCharType"))
                if kind == "begin":
                    parent = open_fields[-1] if open_fields else None
                    found = _Field(run, parent)
                    if parent is not None:
                        found.in_code = parent.separate is None
                        found.quoted = found.in_code and _in_quotes(parent.code)
                        parent.nested.append(found)
                    open_fields.append(found)
                elif kind == "separate" and open_fields:
                    open_fields[-1].separate = run
                elif kind == "end" and open_fields:
                    found = open_fields.pop()
                    found.end = run
                    done.append(found)
    return done


def _in_quotes(code: str) -> bool:
    return len(re.findall(r'(?<!\\)"', code)) % 2 == 1


def _runs_between(paragraph: ET.Element, first: ET.Element, last: ET.Element) -> list[ET.Element]:
    children = list(paragraph)
    inside = children[children.index(first) + 1 : children.index(last)]
    return [child for child in inside if child.tag == _R]


def _work_out(paragraph: ET.Element, found: _Field) -> None:
    """A field that held a merge field shows its new result: worked out here for IF "a" = "b"
    "yes" "no", otherwise left for Word to update when the document opens."""
    result = None if found.nested or found.end is None else _if_result(found.code)
    if result is None or found.end is None:
        mark = found.begin.find(_FLD_CHAR)
        if mark is not None:
            mark.set(q(W, "dirty"), "true")
        return
    if found.separate is None:
        found.separate = ET.Element(_R)
        ET.SubElement(found.separate, _FLD_CHAR, {q(W, "fldCharType"): "separate"})
        paragraph.insert(list(paragraph).index(found.end), found.separate)
    results = _runs_between(paragraph, found.separate, found.end)
    run = ET.Element(_R)
    properties = (results[0] if results else found.begin).find(_RPR)
    if properties is not None:
        run.append(copy.deepcopy(properties))
    text = ET.SubElement(run, _T)
    text.text = clean(result)
    text.set(XML_SPACE, "preserve")
    for old in results:
        paragraph.remove(old)
    paragraph.insert(list(paragraph).index(found.end), run)


_CODE_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|(<>|<=|>=|=|<|>)|([^\s"<>=]+)')


def _if_result(code: str) -> str | None:
    """What IF a op b "yes" "no" shows (numbers compared as numbers, * and ? as wildcards with
    = and <>), or None for any other field code."""
    items: list[tuple[str, str]] = []
    for match in _CODE_TOKEN.finditer(code):
        if match.group(1) is not None:
            items.append(("text", re.sub(r"\\(.)", r"\1", match.group(1))))
        elif match.group(2):
            items.append(("op", match.group(2)))
        elif match.group(3).startswith("\\"):
            break  # switches such as \* MERGEFORMAT
        else:
            items.append(("text", match.group(3)))
    if len(items) not in (5, 6) or items[0][1].upper() != "IF" or items[2][0] != "op":
        return None
    if any(kind != "text" for kind, _ in [items[1], *items[3:]]):
        return None
    left, op, right = items[1][1], items[2][1], items[3][1]
    yes, no = items[4][1], items[5][1] if len(items) == 6 else ""
    try:
        a, b = float(left), float(right)
    except ValueError:
        if op in {"=", "<>"} and ("*" in right or "?" in right):
            pattern = re.escape(right).replace(r"\*", ".*").replace(r"\?", ".")
            same = re.fullmatch(pattern, left, re.DOTALL) is not None
            return yes if same == (op == "=") else no
        outcome = {"=": left == right, "<>": left != right, "<": left < right}
        outcome |= {">": left > right, "<=": left <= right, ">=": left >= right}
        return yes if outcome[op] else no
    numeric = {"=": a == b, "<>": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}
    return yes if numeric[op] else no


def fill(template: bytes, values: Mapping[str, Any]) -> tuple[bytes, list[str]]:
    """The template with every field filled; the field names that had no value."""
    package = open_docx(template)
    missing: set[str] = set()
    for part in text_parts(package):
        _fill_merge_fields(package.xml(part).root, values, missing)
        _fill_braces(package, part, values, missing)
    return package.to_bytes(), sorted(missing)


def combine(documents: list[bytes]) -> bytes:
    """One document holding each filled copy on its own pages. Each copy is a section of its
    own, with its own headers and footers, since those may hold its fields too."""
    if not documents:
        raise OfficeError("nothing to combine")
    first = open_docx(documents[0])
    root = first.xml(DOCUMENT).root
    body = root.find(q(W, "body"))
    if body is None:
        raise OfficeError("the template has no body")
    section = body.find(_SECTION)
    if section is not None:
        body.remove(section)
    numbers = _Numbers(first)
    for data in documents[1:]:
        package = open_docx(data)
        other = package.xml(DOCUMENT).root.find(q(W, "body"))
        if other is None:
            continue
        if section is not None:
            _end_section(body, section)
        else:
            page_break = ET.SubElement(body, q(W, "p"))
            run = ET.SubElement(page_break, _R)
            ET.SubElement(run, q(W, "br"), {q(W, "type"): "page"})
        copied = [copy.deepcopy(child) for child in other if child.tag != _SECTION]
        numbers.renumber(copied)
        body.extend(copied)
        own = other.find(_SECTION)
        if own is not None:
            section = _with_own_parts(first, package, copy.deepcopy(own), numbers)
    if section is not None:
        body.append(section)
    return first.to_bytes()


_SECTION, _PPR = q(W, "sectPr"), q(W, "pPr")
_DOC_PR = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr"
_BOOKMARKS = {q(W, "bookmarkStart"), q(W, "bookmarkEnd")}
_PART_TYPES = {
    "header": "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml",
    "footer": "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml",
}


class _Numbers:
    """Fresh ids for the drawings and bookmarks of each copy: Word wants them unique."""

    def __init__(self, package: Package) -> None:
        drawings, marks = [0], [0]
        for part in text_parts(package):
            for element in package.xml(part).root.iter():
                if element.tag == _DOC_PR:
                    drawings.append(_number(element.get("id")))
                marks.append(_number(element.get(q(W, "id"))))
        self.next_drawing = max(drawings) + 1
        self.next_mark = max(marks) + 1

    def renumber(self, elements: list[ET.Element]) -> None:
        marks: dict[str, str] = {}
        for top in elements:
            for element in top.iter():
                if element.tag == _DOC_PR:
                    element.set("id", str(self.next_drawing))
                    self.next_drawing += 1
                elif element.tag in _BOOKMARKS:
                    old = element.get(q(W, "id"), "")
                    if old not in marks:
                        marks[old] = str(self.next_mark)
                        self.next_mark += 1
                    element.set(q(W, "id"), marks[old])


def _number(value: str | None) -> int:
    return int(value) if value and value.isdigit() else 0


def _end_section(body: ET.Element, section: ET.Element) -> None:
    """The section ends with the last paragraph so far, as Word stores a section break."""
    last = body[-1] if len(body) else None
    properties = last.find(_PPR) if last is not None and last.tag == q(W, "p") else None
    if (
        last is None
        or last.tag != q(W, "p")
        or (properties is not None and properties.find(_SECTION) is not None)
    ):
        last = ET.SubElement(body, q(W, "p"))
        properties = None
    if properties is None:
        properties = ET.Element(_PPR)
        last.insert(0, properties)
    change = properties.find(q(W, "pPrChange"))
    if change is not None:
        properties.insert(list(properties).index(change), section)
    else:
        properties.append(section)


def _with_own_parts(
    first: Package, package: Package, section: ET.Element, numbers: _Numbers
) -> ET.Element:
    """The copy's section, its headers and footers copied into the combined document."""
    targets = {rid: target for rid, _kind, target in package.relationships(DOCUMENT)}
    for reference in list(section):
        kind = reference.tag.rpartition("}")[2].removesuffix("Reference")
        rid = reference.get(f"{{{R}}}id", "")
        if kind not in _PART_TYPES or rid not in targets:
            continue
        source = package.resolve(DOCUMENT, targets[rid])
        if not package.has(source):
            continue
        number = 1
        while first.has(f"word/{kind}{number}.xml"):
            number += 1
        name = f"word/{kind}{number}.xml"
        part = package.xml(source)
        numbers.renumber([part.root])
        first.set_xml(name, part)
        # A picture in it points at media the copies share: they come from one template.
        rels = package.rels_name(source)
        if package.has(rels):
            first.set(first.rels_name(name), package.parts[rels])
        first.content_type(name, _PART_TYPES[kind])
        reference.set(f"{{{R}}}id", first.add_relationship(DOCUMENT, kind, f"{kind}{number}.xml"))
    start = section.find(q(W, "type"))
    if start is not None and start.get(q(W, "val")) == "continuous":
        section.remove(start)  # each copy starts on a new page
    return section


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
