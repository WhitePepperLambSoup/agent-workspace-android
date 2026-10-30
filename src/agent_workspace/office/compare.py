# ruff: noqa: RUF001 -- the report is written in Chinese.
"""Two versions of a document compared: a Word file with the differences as tracked changes, and
a list of what changed (for Word and PDF files alike).

The redline is the newer document with the older text marked as deleted where it differs:
unchanged paragraphs keep their formatting; a changed paragraph is rewritten word by word (one
character at a time for Chinese) in the formatting of its first run.
"""

from __future__ import annotations

import copy
import difflib
import io
import re
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from pypdf import PdfReader

from agent_workspace.office.ooxml import OfficeError, W, clean, q
from agent_workspace.office.word import DOCUMENT, Revisions, body_paragraphs, open_docx

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
            _rewrite(revisions, target.element, old_text, target.text)
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


def _rewrite(revisions: Revisions, paragraph: ET.Element, old: str, new: str) -> None:
    """The paragraph's runs replaced by the word diff of old and new, in its first run's format."""
    first = next(paragraph.iter(_R), None)
    properties = (
        copy.deepcopy(first.find(_RPR))
        if first is not None and first.find(_RPR) is not None
        else None
    )
    keep = [child for child in paragraph if child.tag == _PPR]
    # Pictures and other non-text runs stay; text runs are rebuilt.
    others = [child for child in paragraph if child.tag != _PPR and not _is_text(child)]
    for child in list(paragraph):
        paragraph.remove(child)
    for child in keep:
        paragraph.append(child)

    def run(text: str, tag: str = "t") -> ET.Element:
        element = ET.Element(_R)
        if properties is not None:
            element.append(copy.deepcopy(properties))
        text_element = ET.SubElement(element, q(W, tag))
        text_element.text = clean(text)
        text_element.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        return element

    old_tokens, new_tokens = tokens(old), tokens(new)
    matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            paragraph.append(run("".join(new_tokens[j1:j2])))
            continue
        if i2 > i1:
            deleted = revisions.mark(q(W, "del"))
            deleted.append(run("".join(old_tokens[i1:i2]), "delText"))
            paragraph.append(deleted)
        if j2 > j1:
            inserted = revisions.mark(q(W, "ins"))
            inserted.append(run("".join(new_tokens[j1:j2])))
            paragraph.append(inserted)
    for child in others:
        paragraph.append(child)


def _is_text(element: ET.Element) -> bool:
    if element.tag != _R:
        return element.tag in {q(W, "hyperlink"), q(W, "ins"), q(W, "del"), q(W, "smartTag")}
    return any(child.tag in {_T, q(W, "tab"), q(W, "br")} for child in element) and not any(
        child.tag
        in {q(W, "drawing"), q(W, "pict"), q(W, "object"), q(W, "fldChar"), q(W, "instrText")}
        for child in element
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
    for child in list(paragraph):
        if child.tag != _R:
            continue
        wrapper = revisions.mark(tag)
        paragraph.insert(list(paragraph).index(child), wrapper)
        paragraph.remove(child)
        if not inserted:
            for text in child.iter(_T):
                text.tag = q(W, "delText")
        wrapper.append(child)


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
