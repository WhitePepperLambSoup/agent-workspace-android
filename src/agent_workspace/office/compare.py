# ruff: noqa: RUF001 -- the report is written in Chinese.
"""Two versions of a document compared: a Word file with the differences as tracked changes, and
a list of what changed (for Word and PDF files alike).

The redline is the newer document with the older text marked as deleted where it differs:
unchanged paragraphs keep their formatting; in a changed paragraph the differing words (one
character at a time for Chinese) are marked on its own runs, the older words in the format of
the text beside them.
"""

from __future__ import annotations

import copy
import difflib
import hashlib
import html
import io
import re
from dataclasses import dataclass, field
from typing import cast
from xml.etree import ElementTree as ET

from pypdf import PdfReader

from agent_workspace.office.ooxml import OfficeError, Package, R, W, q
from agent_workspace.office.word import (
    DOCUMENT,
    Paragraph,
    Revisions,
    body_paragraphs,
    open_docx,
)

_TOKEN = re.compile(r"[㐀-鿿豈-﫿]|[A-Za-z0-9_]+|\s+|[^\sA-Za-z0-9_㐀-鿿豈-﫿]")
_P, _R, _T, _PPR, _RPR = q(W, "p"), q(W, "r"), q(W, "t"), q(W, "pPr"), q(W, "rPr")
MAX_LISTED = 300


@dataclass
class Change:
    kind: str  # changed, added, removed
    old: str = ""
    new: str = ""
    where: str = ""

    def as_dict(self) -> dict[str, str]:
        out = {"kind": self.kind, "where": self.where}
        if self.old:
            out["old"] = self.old[:400]
        if self.new:
            out["new"] = self.new[:400]
        return out


@dataclass
class Comparison:
    changes: list[Change] = field(default_factory=list)
    redline: bytes | None = None

    def summary(self) -> dict[str, object]:
        counts: dict[str, int] = {}
        for change in self.changes:
            counts[change.kind] = counts.get(change.kind, 0) + 1
        return {
            "counts": counts,
            "changes": [change.as_dict() for change in self.changes[:MAX_LISTED]],
            "more": max(0, len(self.changes) - MAX_LISTED),
        }


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text)


def compare_docx(old: bytes, new: bytes, author: str = "Agent Workspace") -> Comparison:
    old_package = open_docx(old)
    new_package = open_docx(new)
    old_paragraphs = body_paragraphs(old_package)
    new_paragraphs = body_paragraphs(new_package)
    old_texts = [paragraph.text for paragraph in old_paragraphs]
    new_texts = [paragraph.text for paragraph in new_paragraphs]
    revisions = Revisions(new_package, author)
    result = Comparison()
    matcher = difflib.SequenceMatcher(None, old_texts, new_texts, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        pairs = min(i2 - i1, j2 - j1) if tag == "replace" else 0
        for offset in range(pairs):
            old_text, target = old_texts[i1 + offset], new_paragraphs[j1 + offset]
            _rewrite(revisions, target, old_text)
            result.changes.append(
                Change("changed", old_text, target.text, f"paragraph {j1 + offset + 1}")
            )
        for index in range(j1 + pairs, j2):
            _mark_paragraph(revisions, new_paragraphs[index].element, inserted=True)
            result.changes.append(
                Change("added", new=new_texts[index], where=f"paragraph {index + 1}")
            )
        removed = list(range(i1 + pairs, i2))
        if removed:
            # The removed paragraphs go where they were: before the next paragraph of the new
            # version, else after its last one.
            root = new_package.xml(DOCUMENT).root
            if j2 < len(new_paragraphs):
                parent = _parent(root, new_paragraphs[j2].element)
                position = list(parent).index(new_paragraphs[j2].element)
            elif new_paragraphs:
                parent = _parent(root, new_paragraphs[-1].element)
                position = list(parent).index(new_paragraphs[-1].element) + 1
            else:
                body = root.find(q(W, "body"))
                if body is None:
                    raise OfficeError("the document has no body")
                parent = body
                position = len(parent) - (
                    1 if len(parent) and parent[-1].tag == q(W, "sectPr") else 0
                )
            for index in removed:
                element = copy.deepcopy(old_paragraphs[index].element)
                _carry_over(old_package, new_package, element)
                _mark_paragraph(revisions, element, inserted=False)
                parent.insert(position, element)
                position += 1
                result.changes.append(
                    Change("removed", old=old_texts[index], where=f"after paragraph {j1}")
                )
    revisions.finish()
    result.redline = new_package.to_bytes()
    return result


def _parent(root: ET.Element, element: ET.Element) -> ET.Element:
    for candidate in root.iter():
        for child in candidate:
            if child is element:
                return candidate
    raise OfficeError("the paragraph is not in the document")


def _rewrite(revisions: Revisions, paragraph: Paragraph, old: str) -> None:
    """The word diff of old and the paragraph's text marked on the paragraph's own runs, so
    links, fields, content controls, pictures and others' revisions stay where they are. The
    changes go in from the end, so the offsets of the earlier ones still hold."""
    old_tokens, new_tokens = tokens(old), tokens(paragraph.text)
    starts = [0]
    for token in new_tokens:
        starts.append(starts[-1] + len(token))
    matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    for tag, i1, i2, j1, j2 in reversed(matcher.get_opcodes()):
        if tag != "equal":
            paragraph = revisions.mark_change(
                paragraph, starts[j1], starts[j2], "".join(old_tokens[i1:i2])
            )


def _mark_paragraph(revisions: Revisions, paragraph: ET.Element, inserted: bool) -> None:
    """A whole paragraph as inserted or deleted: its runs and its paragraph mark."""
    tag = q(W, "ins") if inserted else q(W, "del")
    properties = paragraph.find(_PPR)
    if properties is None:
        properties = ET.Element(_PPR)
        paragraph.insert(0, properties)
    run_properties = properties.find(_RPR)
    if run_properties is None:
        run_properties = ET.SubElement(properties, _RPR)
    run_properties.append(revisions.mark(tag))
    _mark_runs(revisions, paragraph, tag, inserted)


# Run containers whose runs are marked one by one: w:ins and w:del may hold runs, not a link or
# a content control, so the wrappers go inside them.
_RUN_CONTAINERS = frozenset(
    q(W, name) for name in ("hyperlink", "smartTag", "fldSimple", "customXml", "sdtContent")
)


def _mark_runs(revisions: Revisions, container: ET.Element, tag: str, inserted: bool) -> None:
    for child in list(container):
        if child.tag == q(W, "sdt"):
            content = child.find(q(W, "sdtContent"))
            if content is not None:
                _mark_runs(revisions, content, tag, inserted)
            continue
        if child.tag in _RUN_CONTAINERS:
            _mark_runs(revisions, child, tag, inserted)
            continue
        if child.tag != _R:
            continue
        wrapper = revisions.mark(tag)
        container.insert(list(container).index(child), wrapper)
        container.remove(child)
        if not inserted:
            for text in child.iter(_T):
                text.tag = q(W, "delText")
            for code in child.iter(q(W, "instrText")):
                code.tag = q(W, "delInstrText")
        wrapper.append(child)


# Marks that point into the older document's other parts by number (its comments, notes and
# bookmarks): in the newer one the same numbers are someone else's, or nobody's.
_FOREIGN_MARKS = frozenset(
    q(W, name)
    for name in (
        "bookmarkStart",
        "bookmarkEnd",
        "commentRangeStart",
        "commentRangeEnd",
        "commentReference",
        "footnoteReference",
        "endnoteReference",
    )
)


def _carry_over(old: Package, new: Package, element: ET.Element) -> None:
    """A paragraph of the older document made sound in the newer one, where it goes back as
    deleted text. Its r:id/r:embed name the older document's relationships: a link's address
    and a picture's file are added to the newer document under new ids; a reference that
    cannot be carried (a chart, an embedded object with parts of its own) is removed with its
    element, rather than showing another picture or a broken one."""
    relations = _relationship_details(old, DOCUMENT)
    carried: dict[str, str | None] = {}
    for parent in list(element.iter()):
        for child in list(parent):
            if child.tag in _FOREIGN_MARKS:
                parent.remove(child)
                continue
            for attribute, rid in list(child.attrib.items()):
                if not attribute.startswith("{" + R + "}"):
                    continue
                if rid not in carried:
                    carried[rid] = _carry_relationship(old, new, relations.get(rid))
                if carried[rid] is None:
                    _drop_reference(element, child)
                    break
                child.set(attribute, cast(str, carried[rid]))


def _drop_reference(paragraph: ET.Element, node: ET.Element) -> None:
    """Remove what holds a reference that cannot be carried: the drawing, picture or object
    of a run, or the node itself."""
    holders = {q(W, "drawing"), q(W, "pict"), q(W, "object")}
    for run in paragraph.iter(_R):
        for holder in list(run):
            if holder.tag in holders and (holder is node or node in holder.iter()):
                run.remove(holder)
                return
    for parent in paragraph.iter():
        if node in list(parent):
            parent.remove(node)
            return


def _relationship_details(package: Package, part: str) -> dict[str, tuple[str, str, bool]]:
    """id -> (type, target, external) of a part's relationships."""
    name = Package.rels_name(part)
    if name not in package.parts:
        return {}
    details: dict[str, tuple[str, str, bool]] = {}
    for match in re.finditer(r"<Relationship\b([^>]*)/?>", package.text(name)):
        attributes = dict(re.findall(r'(\w+)="([^"]*)"', match.group(1)))
        details[attributes.get("Id", "")] = (
            attributes.get("Type", ""),
            html.unescape(attributes.get("Target", "")),
            attributes.get("TargetMode", "") == "External",
        )
    return details


def _carry_relationship(
    old: Package, new: Package, relation: tuple[str, str, bool] | None
) -> str | None:
    """The newer document's id for one of the older document's relationships, or None."""
    if relation is None:
        return None
    kind, target, external = relation
    name = kind.rsplit("/", 1)[-1]
    if external:
        return new.add_relationship(DOCUMENT, name, target, external=True)
    if name != "image":
        return None
    source = Package.resolve(DOCUMENT, target)
    data = old.parts.get(source)
    if data is None or Package.rels_name(source) in old.parts:
        return None
    folder, _, base = source.rpartition("/")
    copied = f"{folder}/compared-{hashlib.sha256(data).hexdigest()[:12]}-{base}"
    if copied not in new.parts:
        new.set(copied, data)
    extension = base.rpartition(".")[2].lower()
    content_type = re.search(
        rf'<Default Extension="{re.escape(extension)}" ContentType="([^"]+)"',
        old.text("[Content_Types].xml"),
        re.IGNORECASE,
    )
    if content_type:
        new.default_type(extension, content_type.group(1))
    document_folder = DOCUMENT.rpartition("/")[0]
    relative = copied[len(document_folder) + 1 :] if copied.startswith(document_folder) else copied
    return new.add_relationship(DOCUMENT, "image", relative)


def pdf_lines(data: bytes) -> list[tuple[int, str]]:
    """(page, line) of a PDF's text."""
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as error:  # pypdf raises many kinds on damaged files
        raise OfficeError(f"the PDF could not be read: {error}") from None
    out = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        for line in text.splitlines():
            if line.strip():
                out.append((number, re.sub(r"\s+", " ", line.strip())))
    return out


def compare_lines(old: list[tuple[int, str]], new: list[tuple[int, str]]) -> Comparison:
    """Line differences of two texts (PDF pages, or anything read as lines)."""
    result = Comparison()
    old_text = [line for _, line in old]
    new_text = [line for _, line in new]
    matcher = difflib.SequenceMatcher(None, old_text, new_text, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        pairs = min(i2 - i1, j2 - j1) if tag == "replace" else 0
        for offset in range(pairs):
            result.changes.append(
                Change(
                    "changed",
                    old_text[i1 + offset],
                    new_text[j1 + offset],
                    f"page {new[j1 + offset][0]}",
                )
            )
        for index in range(j1 + pairs, j2):
            result.changes.append(
                Change("added", new=new_text[index], where=f"page {new[index][0]}")
            )
        for index in range(i1 + pairs, i2):
            result.changes.append(
                Change("removed", old=old_text[index], where=f"old page {old[index][0]}")
            )
    return result


def report_markdown(title: str, comparison: Comparison) -> str:
    """The changes as a Markdown report."""
    labels = {"changed": "修改", "added": "新增", "removed": "删除"}
    counts = comparison.summary()["counts"]
    assert isinstance(counts, dict)
    lines = [
        f"# {title}",
        "",
        "、".join(f"{labels[k]} {v} 处" for k, v in counts.items()) or "两份文件内容相同。",
        "",
    ]
    for number, change in enumerate(comparison.changes, start=1):
        lines.append(f"## {number}. {labels[change.kind]}（{change.where}）")
        if change.old:
            lines.append(f"- 原文：{change.old}")
        if change.new:
            lines.append(f"- 现文：{change.new}")
        lines.append("")
    return "\n".join(lines)


__all__ = [
    "Change",
    "Comparison",
    "compare_docx",
    "compare_lines",
    "pdf_lines",
    "report_markdown",
    "tokens",
]
