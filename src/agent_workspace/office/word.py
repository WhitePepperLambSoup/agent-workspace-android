"""Word documents as paragraphs of text, with changes written as tracked revisions.

A paragraph's text is what Word shows: runs, hyperlinks, inserted text and content controls,
without deleted text and without the paragraphs of text boxes (those are paragraphs of their
own). ``Revisions`` turns "replace this text with that" into ``w:del``/``w:ins`` marks and adds
comments, so the user accepts or rejects each change in Word.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

from agent_workspace.office.ooxml import XML_SPACE, OfficeError, Package, W, XmlPart, clean, q

DOCUMENT = "word/document.xml"
COMMENTS = "word/comments.xml"
_COMMENTS_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"

_P, _R, _T, _DEL_TEXT = q(W, "p"), q(W, "r"), q(W, "t"), q(W, "delText")
_RPR, _PPR = q(W, "rPr"), q(W, "pPr")
_DEL, _INS = q(W, "del"), q(W, "ins")
_ID, _AUTHOR, _DATE = q(W, "id"), q(W, "author"), q(W, "date")
# Inline containers whose runs are part of the paragraph's text.
_CONTAINERS = {
    q(W, name)
    for name in (
        "hyperlink",
        "ins",
        "smartTag",
        "customXml",
        "fldSimple",
        "moveTo",
        "sdt",
        "sdtContent",
        "dir",
        "bdo",
    )
}
_SKIPPED = {_DEL, q(W, "moveFrom")}
_CHARS = {q(W, "tab"): "\t", q(W, "br"): "\n", q(W, "cr"): "\n", q(W, "noBreakHyphen"): "-"}


@dataclass
class Piece:
    """Text of one run child: a w:t (editable) or a tab or break."""

    run: ET.Element
    parent: ET.Element
    child: ET.Element
    start: int
    end: int


@dataclass
class Paragraph:
    part: str
    element: ET.Element
    text: str
    pieces: list[Piece]


def _walk(container: ET.Element, pieces: list[Piece], text: list[str], offset: int) -> int:
    for child in list(container):
        tag = child.tag
        if tag in _SKIPPED:
            continue
        if tag == _R:
            for item in list(child):
                if item.tag == _T:
                    value = item.text or ""
                elif item.tag in _CHARS:
                    value = _CHARS[item.tag]
                else:
                    continue
                if value:
                    pieces.append(Piece(child, container, item, offset, offset + len(value)))
                    text.append(value)
                    offset += len(value)
        elif tag in _CONTAINERS:
            offset = _walk(child, pieces, text, offset)
    return offset


def read_paragraph(part: str, element: ET.Element) -> Paragraph:
    pieces: list[Piece] = []
    text: list[str] = []
    _walk(element, pieces, text, 0)
    return Paragraph(part, element, "".join(text), pieces)


def text_parts(package: Package) -> list[str]:
    """The document body, then its headers and footers, footnotes and endnotes."""
    parts = [DOCUMENT]
    for _rid, kind, target in package.relationships(DOCUMENT):
        if kind.rsplit("/", 1)[-1] in {"header", "footer", "footnotes", "endnotes"}:
            name = package.resolve(DOCUMENT, target)
            if package.has(name):
                parts.append(name)
    return parts


def paragraphs(package: Package, parts: list[str] | None = None) -> list[Paragraph]:
    out = []
    for part in parts or [DOCUMENT]:
        for element in package.xml(part).root.iter(_P):
            out.append(read_paragraph(part, element))
    return out


def body_paragraphs(package: Package) -> list[Paragraph]:
    return paragraphs(package, [DOCUMENT])


def open_docx(data: bytes) -> Package:
    package = Package.read(data)
    if not package.has(DOCUMENT):
        raise OfficeError("not a Word document (.docx)")
    return package


def plain_text(data: bytes) -> list[str]:
    return [paragraph.text for paragraph in body_paragraphs(open_docx(data))]


# ---- runs ----------------------------------------------------------------------------------------


def _set_text(element: ET.Element, value: str) -> None:
    element.text = value
    if value != value.strip() or "  " in value:
        element.set(XML_SPACE, "preserve")


def _split_run(paragraph: Paragraph, offset: int) -> bool:
    """Split the run holding ``offset`` so a run starts there; False when one already does."""
    for piece in paragraph.pieces:
        if piece.start < offset < piece.end:
            if piece.child.tag != _T:
                return False
            run, parent = piece.run, piece.parent
            children = list(run)
            at = children.index(piece.child)
            cut = offset - piece.start
            value = piece.child.text or ""
            head, tail = value[:cut], value[cut:]
            _set_text(piece.child, head)
            new_run = ET.Element(_R, dict(run.attrib))
            properties = run.find(_RPR)
            if properties is not None:
                new_run.append(copy.deepcopy(properties))
            tail_text = ET.SubElement(new_run, _T)
            _set_text(tail_text, tail)
            for later in children[at + 1 :]:
                run.remove(later)
                new_run.append(later)
            parent.insert(list(parent).index(run) + 1, new_run)
            return True
        if piece.start == offset:
            # A run boundary inside one run (several w:t): split between children.
            run = piece.run
            children = list(run)
            at = children.index(piece.child)
            earlier = [child for child in children[:at] if child.tag != _RPR]
            if not earlier:
                return False
            new_run = ET.Element(_R, dict(run.attrib))
            properties = run.find(_RPR)
            if properties is not None:
                new_run.append(copy.deepcopy(properties))
            for later in children[at:]:
                run.remove(later)
                new_run.append(later)
            piece.parent.insert(list(piece.parent).index(run) + 1, new_run)
            return True
    return False


def _runs_between(paragraph: Paragraph, start: int, end: int) -> list[Piece]:
    """One piece per run of the text [start, end), in order (the runs are split at both ends)."""
    seen: list[ET.Element] = []
    out = []
    for piece in paragraph.pieces:
        if piece.start >= start and piece.end <= end and piece.run not in seen:
            seen.append(piece.run)
            out.append(piece)
    return out


class Revisions:
    """Tracked changes and comments made to one document."""

    def __init__(self, package: Package, author: str = "Agent Workspace") -> None:
        self.package = package
        self.author = author[:60] or "Agent Workspace"
        self.date = datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._next_id = self._highest_id() + 1
        self._comments: list[tuple[int, str]] = []

    def _highest_id(self) -> int:
        highest = 0
        for part in [DOCUMENT, *[name for name in (COMMENTS,) if self.package.has(name)]]:
            for element in self.package.xml(part).root.iter():
                value = element.get(_ID)
                if value and value.isdigit():
                    highest = max(highest, int(value))
        return highest

    def _id(self) -> str:
        value = self._next_id
        self._next_id += 1
        return str(value)

    def mark(self, tag: str) -> ET.Element:
        return ET.Element(tag, {_ID: self._id(), _AUTHOR: self.author, _DATE: self.date})

    def replace(
        self, paragraph: Paragraph, start: int, end: int, text: str, comment: str = ""
    ) -> Paragraph:
        """Delete [start, end) and insert ``text`` there as revisions; comment on the change."""
        element = paragraph.element
        for offset in (start, end):
            paragraph = read_paragraph(paragraph.part, element)
            _split_run(paragraph, offset)
        paragraph = read_paragraph(paragraph.part, element)
        deleted = _runs_between(paragraph, start, end) if end > start else []
        template = deleted[0].run if deleted else self._run_before(paragraph, start)
        anchor_first: tuple[ET.Element, ET.Element] | None = None
        anchor_last: tuple[ET.Element, ET.Element] | None = None
        # Deleted runs: wrapped in w:del, adjacent runs of one parent together.
        groups: list[list[Piece]] = []
        for piece in deleted:
            if (
                groups
                and groups[-1][-1].parent is piece.parent
                and _adjacent(piece.parent, groups[-1][-1].run, piece.run)
            ):
                groups[-1].append(piece)
            else:
                groups.append([piece])
        for group in groups:
            parent = group[0].parent
            wrapper = self.mark(_DEL)
            parent.insert(list(parent).index(group[0].run), wrapper)
            for piece in group:
                parent.remove(piece.run)
                for child in piece.run.iter(_T):
                    child.tag = _DEL_TEXT
                wrapper.append(piece.run)
            anchor_first = anchor_first or (parent, wrapper)
            anchor_last = (parent, wrapper)
        if text:
            inserted = self.mark(_INS)
            run = ET.SubElement(inserted, _R)
            properties = template.find(_RPR) if template is not None else None
            if properties is not None:
                run.append(copy.deepcopy(properties))
            for index, line in enumerate(clean(text).split("\n")):
                if index:
                    ET.SubElement(run, q(W, "br"))
                _set_text(ET.SubElement(run, _T), line)
            parent, position = self._insert_point(paragraph, start, anchor_last)
            parent.insert(position, inserted)
            anchor_first = anchor_first or (parent, inserted)
            anchor_last = (parent, inserted)
        if comment and anchor_first and anchor_last:
            self._comment_around(anchor_first, anchor_last, comment)
        return read_paragraph(paragraph.part, element)

    def comment(self, paragraph: Paragraph, start: int, end: int, text: str) -> None:
        """A comment on [start, end) of the paragraph, the text unchanged."""
        element = paragraph.element
        for offset in (start, end):
            paragraph = read_paragraph(paragraph.part, element)
            _split_run(paragraph, offset)
        paragraph = read_paragraph(paragraph.part, element)
        runs = _runs_between(paragraph, start, end)
        if not runs:
            # An empty range: the comment marks where the paragraph's text starts.
            first = next(iter(element.iter(_R)), None)
            parent = element if first is None else _parent_of(element, first)
            run = first if first is not None else None
            if run is None:
                holder = ET.SubElement(element, _R)
                runs_anchor = (parent, holder)
            else:
                runs_anchor = (parent, run)
            self._comment_around(runs_anchor, runs_anchor, text)
            return
        self._comment_around((runs[0].parent, runs[0].run), (runs[-1].parent, runs[-1].run), text)

    def _comment_around(
        self, first: tuple[ET.Element, ET.Element], last: tuple[ET.Element, ET.Element], text: str
    ) -> None:
        number = self._id()
        start = ET.Element(q(W, "commentRangeStart"), {_ID: number})
        end = ET.Element(q(W, "commentRangeEnd"), {_ID: number})
        reference = ET.Element(_R)
        properties = ET.SubElement(reference, _RPR)
        ET.SubElement(properties, q(W, "rStyle"), {q(W, "val"): "CommentReference"})
        ET.SubElement(reference, q(W, "commentReference"), {_ID: number})
        parent, element = first
        parent.insert(list(parent).index(element), start)
        parent, element = last
        position = list(parent).index(element) + 1
        parent.insert(position, end)
        parent.insert(position + 1, reference)
        self._comments.append((int(number), text))

    @staticmethod
    def _run_before(paragraph: Paragraph, offset: int) -> ET.Element | None:
        before = [piece.run for piece in paragraph.pieces if piece.end <= offset]
        if before:
            return before[-1]
        return paragraph.pieces[0].run if paragraph.pieces else None

    @staticmethod
    def _insert_point(
        paragraph: Paragraph, offset: int, after: tuple[ET.Element, ET.Element] | None
    ) -> tuple[ET.Element, int]:
        if after is not None:
            parent, element = after
            return parent, list(parent).index(element) + 1
        before = [piece for piece in paragraph.pieces if piece.end <= offset]
        if before:
            parent = before[-1].parent
            return parent, list(parent).index(before[-1].run) + 1
        element = paragraph.element
        children = list(element)
        position = 1 if children and children[0].tag == _PPR else 0
        return element, position

    def finish(self) -> None:
        """Write the comments part (new comments appended to any the document has)."""
        if not self._comments:
            return
        package = self.package
        if package.has(COMMENTS):
            root = package.xml(COMMENTS).root
        else:
            part = XmlPart.parse(
                f'<w:comments xmlns:w="{W}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"></w:comments>'.encode()
            )
            package.set_xml(COMMENTS, part)
            package.content_type(COMMENTS, _COMMENTS_TYPE)
            package.add_relationship(DOCUMENT, "comments", "comments.xml")
            root = part.root
        initials = "".join(word[0] for word in self.author.split()[:3]).upper() or "AW"
        for number, text in self._comments:
            comment = ET.SubElement(
                root,
                q(W, "comment"),
                {
                    _ID: str(number),
                    _AUTHOR: self.author,
                    _DATE: self.date,
                    q(W, "initials"): initials,
                },
            )
            for line in clean(text).split("\n") or [""]:
                paragraph = ET.SubElement(comment, _P)
                properties = ET.SubElement(paragraph, _PPR)
                ET.SubElement(properties, q(W, "pStyle"), {q(W, "val"): "CommentText"})
                run = ET.SubElement(paragraph, _R)
                _set_text(ET.SubElement(run, _T), line)
        self._comments.clear()


def _adjacent(parent: ET.Element, first: ET.Element, second: ET.Element) -> bool:
    children = list(parent)
    return children.index(second) == children.index(first) + 1


def _parent_of(root: ET.Element, element: ET.Element) -> ET.Element:
    for candidate in root.iter():
        if element in list(candidate):
            return candidate
    raise OfficeError("the run is not in its paragraph")


# ---- finding text --------------------------------------------------------------------------------


def find_all(text: str, find: str) -> list[tuple[int, int]]:
    """Where ``find`` occurs: exactly, else ignoring differences in white space."""
    if not find:
        return []
    spans = [(match.start(), match.end()) for match in re.finditer(re.escape(find), text)]
    if spans:
        return spans
    compact = re.sub(r"\s+", "", find)
    if not compact:
        return []
    pattern = r"\s*".join(re.escape(char) for char in compact)
    return [(match.start(), match.end()) for match in re.finditer(pattern, text)]


def locate(
    paragraph_list: list[Paragraph], find: str, occurrence: int | None
) -> list[tuple[Paragraph, int, int]]:
    """Paragraph and span of each match; only the n-th (1-based) when ``occurrence`` is given."""
    found = [
        (paragraph, start, end)
        for paragraph in paragraph_list
        for start, end in find_all(paragraph.text, find)
    ]
    if occurrence is not None:
        return found[occurrence - 1 : occurrence] if 0 < occurrence <= len(found) else []
    return found


# ---- comments ------------------------------------------------------------------------------------


def read_comments(package: Package) -> list[dict[str, object]]:
    """Each comment: id, author, date, text, and the document text it marks."""
    if not package.has(COMMENTS):
        return []
    comments: dict[str, dict[str, object]] = {}
    for element in package.xml(COMMENTS).root.iter(q(W, "comment")):
        text = "\n".join(read_paragraph(COMMENTS, paragraph).text for paragraph in element.iter(_P))
        comments[element.get(_ID, "")] = {
            "id": element.get(_ID, ""),
            "author": element.get(_AUTHOR, ""),
            "date": element.get(_DATE, ""),
            "text": text.strip(),
            "anchor": "",
        }
    open_ids: dict[str, list[str]] = {}
    for kind, value in _document_stream(package.xml(DOCUMENT).root):
        if kind == "start":
            open_ids[value] = []
        elif kind == "end":
            if value in open_ids and value in comments:
                comments[value]["anchor"] = "".join(open_ids.pop(value))[:500]
        else:
            for collected in open_ids.values():
                collected.append(value)
    return list(comments.values())


def _document_stream(root: ET.Element) -> Iterator[tuple[str, str]]:
    """Comment range marks and visible text, in document order."""
    start, end = q(W, "commentRangeStart"), q(W, "commentRangeEnd")

    def visit(element: ET.Element) -> Iterator[tuple[str, str]]:
        for child in element:
            if child.tag in _SKIPPED:
                continue
            if child.tag == start:
                yield "start", child.get(_ID, "")
            elif child.tag == end:
                yield "end", child.get(_ID, "")
            elif child.tag == _T:
                yield "text", child.text or ""
            elif child.tag in _CHARS:
                yield "text", _CHARS[child.tag]
            else:
                yield from visit(child)
                if child.tag == _P:
                    yield "text", "\n"

    yield from visit(root)


__all__ = [
    "COMMENTS",
    "DOCUMENT",
    "Paragraph",
    "Piece",
    "Revisions",
    "body_paragraphs",
    "find_all",
    "locate",
    "open_docx",
    "paragraphs",
    "plain_text",
    "read_comments",
    "read_paragraph",
    "text_parts",
]
