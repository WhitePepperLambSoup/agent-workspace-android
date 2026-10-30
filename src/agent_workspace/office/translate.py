# ruff: noqa: RUF001 -- Chinese punctuation is recognised on purpose.
"""Translation that keeps a document's layout: its text is listed as numbered segments (Word
paragraphs, the paragraphs of PowerPoint text boxes and tables, Excel text cells), the agent
translates them, and the translations are written back where the text was — replacing it, or
below it (bilingual). A paragraph takes the formatting of its first run.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from agent_workspace.office.ooxml import XML_SPACE, A, OfficeError, P, Package, S, W, clean, q
from agent_workspace.office.word import read_paragraph, text_parts

_SKIP = re.compile(r"^[\s\d.,:;%+\-*/=()（）、，。：；·…\[\]#@]*$")


@dataclass
class Segment:
    id: str
    text: str


def kind_of(name: str) -> str:
    suffix = name.lower().rsplit(".", 1)[-1]
    if suffix in {"docx", "pptx", "xlsx"}:
        return suffix
    raise OfficeError("translation keeps the layout of .docx, .pptx and .xlsx files")


def _slides(package: Package) -> list[str]:
    """Slide parts in presentation order."""
    root = package.xml("ppt/presentation.xml").root
    targets = {
        rid: package.resolve("ppt/presentation.xml", target)
        for rid, _kind, target in package.relationships("ppt/presentation.xml")
    }
    relationship = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    out = []
    listing = root.find(q(P, "sldIdLst"))
    for entry in listing if listing is not None else []:
        name = targets.get(entry.get(relationship, ""))
        if name and package.has(name):
            out.append(name)
    return out


def _notes(package: Package, slide: str) -> str | None:
    for _rid, kind, target in package.relationships(slide):
        if kind.endswith("/notesSlide"):
            name = package.resolve(slide, target)
            return name if package.has(name) else None
    return None


def _drawing_text(paragraph: ET.Element) -> str:
    parts = []
    for child in paragraph:
        if child.tag in {q(A, "r"), q(A, "fld")}:
            parts.append(child.findtext(q(A, "t")) or "")
        elif child.tag == q(A, "br"):
            parts.append("\n")
    return "".join(parts)


def _units(package: Package, kind: str, notes: bool = True) -> list[tuple[str, str, ET.Element]]:
    """(id, part, element) of every translatable unit, in reading order."""
    out: list[tuple[str, str, ET.Element]] = []
    if kind == "docx":
        for part_index, part in enumerate(text_parts(package)):
            for index, element in enumerate(package.xml(part).root.iter(q(W, "p"))):
                out.append((f"d{part_index}.{index}", part, element))
    elif kind == "pptx":
        for slide_index, slide in enumerate(_slides(package), start=1):
            parts = [(slide, "s")]
            note = _notes(package, slide) if notes else None
            if note:
                parts.append((note, "n"))
            for part, prefix in parts:
                for index, element in enumerate(package.xml(part).root.iter(q(A, "p"))):
                    out.append((f"{prefix}{slide_index}.{index}", part, element))
    else:
        if package.has("xl/sharedStrings.xml"):
            for index, element in enumerate(
                package.xml("xl/sharedStrings.xml").root.findall(q(S, "si"))
            ):
                out.append((f"x{index}", "xl/sharedStrings.xml", element))
        for part in sorted(
            name for name in package.names("xl/worksheets/") if name.endswith(".xml")
        ):
            for index, cell in enumerate(package.xml(part).root.iter(q(S, "c"))):
                if cell.get("t") == "inlineStr":
                    holder = cell.find(q(S, "is"))
                    if holder is not None:
                        out.append((f"i{part.rsplit('/', 1)[-1][:-4]}.{index}", part, holder))
    return out


def _text(kind: str, part: str, element: ET.Element) -> str:
    if kind == "docx":
        return read_paragraph(part, element).text
    if kind == "pptx":
        return _drawing_text(element)
    return "".join(
        text.text or "" for text in element.iter(q(S, "t")) if not _phonetic(element, text)
    )


def _phonetic(holder: ET.Element, text: ET.Element) -> bool:
    return any(text in list(item.iter(q(S, "t"))) for item in holder.findall(q(S, "rPh")))


def segments(data: bytes, name: str, notes: bool = True) -> list[Segment]:
    kind = kind_of(name)
    package = Package.read(data)
    out = []
    for identifier, part, element in _units(package, kind, notes):
        text = _text(kind, part, element)
        if text.strip() and not _SKIP.fullmatch(text):
            out.append(Segment(identifier, text))
    return out


def _put_docx(paragraph: ET.Element, part: str, text: str) -> None:
    current = read_paragraph(part, paragraph)
    pieces = [piece for piece in current.pieces if piece.child.tag == q(W, "t")]
    if not pieces:
        return
    for index, piece in enumerate(pieces):
        piece.child.text = clean(text) if index == 0 else ""
        piece.child.set(XML_SPACE, "preserve")
    # Breaks and tabs inside the old text no longer belong to it.
    for piece in current.pieces:
        if piece.child.tag != q(W, "t") and piece.child in list(piece.run):
            piece.run.remove(piece.child)


def _put_drawing(paragraph: ET.Element, text: str) -> None:
    runs = [child for child in paragraph if child.tag in {q(A, "r"), q(A, "fld")}]
    for child in [child for child in paragraph if child.tag == q(A, "br")]:
        paragraph.remove(child)
    if not runs:
        return
    for index, run in enumerate(runs):
        element = run.find(q(A, "t"))
        if element is not None:
            element.text = clean(text) if index == 0 else ""


def _put_cell(holder: ET.Element, text: str) -> None:
    texts = [element for element in holder.iter(q(S, "t")) if not _phonetic(holder, element)]
    for phonetic in holder.findall(q(S, "rPh")):
        holder.remove(phonetic)
    if not texts:
        element = ET.SubElement(holder, q(S, "t"))
        texts = [element]
    for index, element in enumerate(texts):
        element.text = clean(text) if index == 0 else ""
        element.set(XML_SPACE, "preserve")


def apply(
    data: bytes,
    name: str,
    translations: dict[str, str],
    bilingual: bool = False,
    notes: bool = True,
) -> tuple[bytes, int]:
    """The document with the translations in place (or under the original text); how many."""
    kind = kind_of(name)
    package = Package.read(data)
    applied = 0
    parents: dict[str, dict[ET.Element, ET.Element]] = {}
    for identifier, part, element in _units(package, kind, notes):
        translation = translations.get(identifier)
        if translation is None:
            continue
        if kind == "xlsx":
            original = _text(kind, part, element)
            _put_cell(element, f"{original}\n{translation}" if bilingual else translation)
        else:
            target = element
            if bilingual:
                if part not in parents:
                    parents[part] = {
                        child: parent
                        for parent in package.xml(part).root.iter()
                        for child in parent
                    }
                parent = parents[part][element]
                target = copy.deepcopy(element)
                parent.insert(list(parent).index(element) + 1, target)
            if kind == "docx":
                _put_docx(target, part, translation)
            else:
                _put_drawing(target, translation)
        applied += 1
    return package.to_bytes(), applied


__all__ = ["Segment", "apply", "kind_of", "segments"]
