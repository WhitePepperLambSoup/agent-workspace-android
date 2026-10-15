"""Word and Excel files made on the phone, without Office or a Python package to install.

create_docx turns Markdown (headings, paragraphs, bold and italic, code, links, lists, tables,
quotes) into a .docx; create_xlsx writes rows (numbers, text, formulas) into the sheets of an
.xlsx. Both write plain Office Open XML with zipfile, check the file a call expects to replace
(expected_sha256) and keep a rollback copy like the other file tools.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
import re
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.events import Event
from agent_workspace.core.models import Capability, FileCheckpoint, ToolSpec
from agent_workspace.storage.durable import durable_replace
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result, require_string
from agent_workspace.tools.filesystem import _check_preimage, _read_preimage, expected_sha256
from agent_workspace.tools.paths import StrPath, WorkspacePaths, is_sensitive_workspace_path

_MAX_CONTENT = 262144
_MAX_ROWS = 50_000
_MAX_COLUMNS = 200
_MAX_CELLS = 500_000
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_CJK = re.compile(r"[⺀-鿿豈-﫿＀-￯]")


def _xml(text: str) -> str:
    return escape(_CONTROL.sub("", text), {'"': "&quot;"})


# ---- Word ---------------------------------------------------------------------------------------

_INLINE = re.compile(
    r"(?P<code>`[^`\n]+`)|(?P<link>\[(?P<label>[^\]\n]+)\]\((?P<url>[^)\s]+)\))"
    # Chinese counts as a boundary (snake_case words do not turn italic).
    r"|(?P<bold>\*\*(?=\S)(?P<btext>.+?)(?<=\S)\*\*)|(?P<italic>(?<![A-Za-z0-9*])[*_](?=\S)(?P<itext>[^*_\n]+?)(?<=\S)[*_](?![A-Za-z0-9*]))"
)


class _Docx:
    def __init__(self) -> None:
        self.body: list[str] = []
        self.links: list[str] = []
        self.numbered = 0

    def runs(self, text: str, style: str = "") -> str:
        """Inline Markdown as runs: **bold**, *italic*, `code`, [links](https://...)."""
        out: list[str] = []
        position = 0
        for match in _INLINE.finditer(text):
            if match.start() > position:
                out.append(self.run(text[position : match.start()], style))
            if match.group("code"):
                out.append(self.run(match.group("code")[1:-1], style + '<w:rStyle w:val="CodeChar"/>'))
            elif match.group("link"):
                url = match.group("url")
                if re.match(r"https?://", url):
                    self.links.append(url)
                    rid = f"rIdLink{len(self.links)}"
                    out.append(
                        f'<w:hyperlink r:id="{rid}">'
                        + self.run(match.group("label"), style + '<w:rStyle w:val="Hyperlink"/>')
                        + "</w:hyperlink>"
                    )
                else:
                    out.append(self.run(match.group("label"), style))
            elif match.group("bold"):
                out.append(self.runs(match.group("btext"), style + "<w:b/>"))
            else:
                out.append(self.runs(match.group("itext"), style + "<w:i/>"))
            position = match.end()
        if position < len(text):
            out.append(self.run(text[position:], style))
        return "".join(out)

    @staticmethod
    def run(text: str, style: str = "") -> str:
        properties = f"<w:rPr>{style}</w:rPr>" if style else ""
        parts = text.split("\n")
        body = '<w:br/>'.join(f'<w:t xml:space="preserve">{_xml(part)}</w:t>' for part in parts)
        return f"<w:r>{properties}{body}</w:r>"

    def paragraph(self, text: str, style: str | None = None, extra: str = "", run_style: str = "") -> None:
        properties = f'<w:pStyle w:val="{style}"/>' if style else ""
        properties += extra
        self.body.append(f"<w:p><w:pPr>{properties}</w:pPr>{self.runs(text, run_style)}</w:p>")

    def code(self, lines: list[str]) -> None:
        for line in lines or [""]:
            self.body.append(f'<w:p><w:pPr><w:pStyle w:val="Code"/></w:pPr>{self.run(line)}</w:p>')

    def list_item(self, text: str, ordered: bool, level: int, list_id: int) -> None:
        self.paragraph(
            text,
            "ListParagraph",
            f'<w:numPr><w:ilvl w:val="{min(level, 8)}"/><w:numId w:val="{list_id}"/></w:numPr>',
        )

    def table(self, rows: list[list[str]], aligns: list[str]) -> None:
        width = max(len(row) for row in rows)
        grid = "".join('<w:gridCol w:w="2000"/>' for _ in range(width))
        out = [
            '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="pct"/></w:tblPr>'
            f"<w:tblGrid>{grid}</w:tblGrid>"
        ]
        for index, row in enumerate(rows):
            cells = []
            for column in range(width):
                text = row[column] if column < len(row) else ""
                align = aligns[column] if column < len(aligns) else ""
                jc = f'<w:jc w:val="{align}"/>' if align else ""
                cells.append(
                    f'<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr><w:p><w:pPr>{jc}</w:pPr>'
                    f'{self.runs(text, "<w:b/>" if index == 0 else "")}</w:p></w:tc>'
                )
            header = '<w:trPr><w:tblHeader/></w:trPr>' if index == 0 else ""
            out.append(f"<w:tr>{header}{''.join(cells)}</w:tr>")
        out.append("</w:tbl>")
        self.body.append("".join(out))
        self.body.append("<w:p/>")


def _join(lines: list[str]) -> str:
    """A paragraph's lines as one text: no space between Chinese characters."""
    text = ""
    for line in lines:
        line = line.strip()
        if not text:
            text = line
        elif line.endswith("  ") or text.endswith("\\"):
            text = text.rstrip("\\") + "\n" + line
        elif _CJK.match(text[-1:]) or _CJK.match(line[:1]):
            text += line
        else:
            text += " " + line
    return text


def _cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line)]


def markdown_docx(content: str, title: str = "") -> bytes:
    """A .docx of Markdown text."""
    document = _Docx()
    if title:
        document.paragraph(title, "Title")
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    index = 0
    paragraph: list[str] = []
    lists: dict[int, int] = {}

    def flush() -> None:
        if paragraph:
            document.paragraph(_join(paragraph))
            paragraph.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        fence = re.match(r"^\s*(```|~~~)", line)
        if fence:
            flush()
            block = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith(fence.group(1)):
                block.append(lines[index])
                index += 1
            document.code(block)
            index += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if heading:
            flush()
            document.paragraph(heading.group(2), f"Heading{len(heading.group(1))}")
            index += 1
            continue
        if (
            stripped.startswith("|")
            and index + 1 < len(lines)
            and re.match(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$", lines[index + 1])
        ):
            flush()
            rows = [_cells(line)]
            aligns = [
                "center" if cell.startswith(":") and cell.endswith(":") else "right" if cell.endswith(":") else ""
                for cell in _cells(lines[index + 1])
            ]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(_cells(lines[index]))
                index += 1
            document.table(rows, aligns)
            continue
        item = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if item:
            flush()
            level = len(item.group(1).replace("\t", "    ")) // 2
            ordered = item.group(2)[0].isdigit()
            if ordered:
                if level not in lists:
                    document.numbered += 1
                    lists[level] = 2 + document.numbered
                list_id = lists[level]
            else:
                list_id = 1
            for deeper in [key for key in lists if key > level]:
                del lists[deeper]
            document.list_item(item.group(3), ordered, level, list_id)
            index += 1
            continue
        if stripped.startswith(">"):
            flush()
            quote = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip()[1:].strip())
                index += 1
            document.paragraph(_join(quote), "Quote")
            continue
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            flush()
            document.body.append(
                '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="999999"/></w:pBdr></w:pPr></w:p>'
            )
            index += 1
            continue
        if stripped in ("\\newpage", "\\pagebreak", "<!-- pagebreak -->"):
            flush()
            document.body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
            index += 1
            continue
        if not stripped:
            flush()
            lists.clear()
            index += 1
            continue
        paragraph.append(line)
        index += 1
    flush()
    return _docx_package(document)


def _docx_package(document: _Docx) -> bytes:
    namespaces = (
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    )
    body = "".join(document.body) + (
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1304" w:bottom="1440" w:left="1304" w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    links = "".join(
        f'<Relationship Id="rIdLink{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
        f'Target="{_xml(url)}" TargetMode="External"/>'
        for index, url in enumerate(document.links, start=1)
    )
    numbered = "".join(
        f'<w:num w:numId="{2 + index}"><w:abstractNumId w:val="1"/>'
        '<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'
        for index in range(1, document.numbered + 1)
    )
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        ),
        "word/_rels/document.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rIdNumbering" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>'
            f"{links}</Relationships>"
        ),
        "word/document.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {namespaces}><w:body>{body}</w:body></w:document>'
        ),
        "word/styles.xml": _DOCX_STYLES,
        "word/numbering.xml": _DOCX_NUMBERING.replace("</w:numbering>", numbered + "</w:numbering>"),
    }
    return _zip(files)


def _heading_style(level: int) -> str:
    size = {1: 32, 2: 28, 3: 26, 4: 24, 5: 22, 6: 22}[level]
    return (
        f'<w:style w:type="paragraph" w:styleId="Heading{level}"><w:name w:val="heading {level}"/>'
        '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
        f'<w:pPr><w:keepNext/><w:spacing w:before="{240 if level <= 2 else 160}" w:after="120"/>'
        f'<w:outlineLvl w:val="{level - 1}"/></w:pPr><w:rPr><w:b/><w:sz w:val="{size}"/></w:rPr></w:style>'
    )


_DOCX_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="等线" w:cs="Arial"/>'
    '<w:sz w:val="22"/><w:lang w:val="zh-CN" w:eastAsia="zh-CN"/></w:rPr></w:rPrDefault>'
    '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
    '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/>'
    '<w:pPr><w:jc w:val="center"/><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>'
    + "".join(_heading_style(level) for level in range(1, 7))
    + '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/>'
    '<w:pPr><w:spacing w:after="60"/></w:pPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/>'
    '<w:pPr><w:ind w:left="567"/><w:pBdr><w:left w:val="single" w:sz="12" w:space="8" w:color="C8CDCC"/></w:pBdr></w:pPr>'
    '<w:rPr><w:color w:val="404040"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/>'
    '<w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/></w:pPr>'
    '<w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="等线"/><w:sz w:val="19"/></w:rPr></w:style>'
    '<w:style w:type="character" w:styleId="CodeChar"><w:name w:val="Code Char"/>'
    '<w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/></w:rPr></w:style>'
    '<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/>'
    '<w:rPr><w:color w:val="0B5E55"/><w:u w:val="single"/></w:rPr></w:style>'
    '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr>'
    '<w:tblBorders><w:top w:val="single" w:sz="4" w:color="999999"/><w:left w:val="single" w:sz="4" w:color="999999"/>'
    '<w:bottom w:val="single" w:sz="4" w:color="999999"/><w:right w:val="single" w:sz="4" w:color="999999"/>'
    '<w:insideH w:val="single" w:sz="4" w:color="999999"/><w:insideV w:val="single" w:sz="4" w:color="999999"/></w:tblBorders>'
    '<w:tblCellMar><w:left w:w="100" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>'
    "</w:styles>"
)


def _levels(bullet: bool) -> str:
    marks = ["•", "◦", "▪"]
    levels = []
    for level in range(9):
        if bullet:
            format_, text = "bullet", marks[level % 3]
        else:
            format_, text = "decimal", "".join(f"%{index + 1}." for index in range(level + 1))
        levels.append(
            f'<w:lvl w:ilvl="{level}"><w:start w:val="1"/><w:numFmt w:val="{format_}"/>'
            f'<w:lvlText w:val="{text}"/><w:lvlJc w:val="left"/>'
            f'<w:pPr><w:ind w:left="{420 * (level + 1)}" w:hanging="420"/></w:pPr></w:lvl>'
        )
    return "".join(levels)


_DOCX_NUMBERING = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    f'<w:abstractNum w:abstractNumId="0">{_levels(True)}</w:abstractNum>'
    f'<w:abstractNum w:abstractNumId="1">{_levels(False)}</w:abstractNum>'
    '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
    '<w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>'
    "</w:numbering>"
)


# ---- Excel --------------------------------------------------------------------------------------


def _column(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _width(value: Any) -> int:
    text = str(value)
    return sum(2 if _CJK.match(character) else 1 for character in text)


def rows_xlsx(sheets: list[dict[str, Any]], header: bool = True) -> bytes:
    """An .xlsx of named sheets of rows: numbers stay numbers, '=...' is a formula, the first row
    is the bold, frozen header unless header is false."""
    names: list[str] = []
    parts: dict[str, str] = {}
    for number, sheet in enumerate(sheets, start=1):
        name = re.sub(r"[\[\]:*?/\\]", " ", str(sheet.get("name") or f"Sheet{number}")).strip()[:31] or f"Sheet{number}"
        base, suffix = name, 2
        while name.lower() in (existing.lower() for existing in names):
            name = f"{base[:28]} {suffix}"
            suffix += 1
        names.append(name)
        rows = sheet["rows"]
        widths: dict[int, int] = {}
        xml_rows = []
        for row_index, row in enumerate(rows, start=1):
            cells = []
            for column_index, value in enumerate(row):
                if value is None or value == "":
                    continue
                reference = f"{_column(column_index)}{row_index}"
                style = ' s="1"' if header and row_index == 1 else ""
                if isinstance(value, bool):
                    cells.append(f'<c r="{reference}" t="b"{style}><v>{int(value)}</v></c>')
                elif isinstance(value, (int, float)):
                    cells.append(f'<c r="{reference}"{style}><v>{value!r}</v></c>')
                elif isinstance(value, str) and value.startswith("=") and len(value) > 1:
                    cells.append(f'<c r="{reference}"{style}><f>{_xml(value[1:])}</f></c>')
                else:
                    cells.append(
                        f'<c r="{reference}" t="inlineStr"{style}><is><t xml:space="preserve">{_xml(str(value))}</t></is></c>'
                    )
                widths[column_index] = max(widths.get(column_index, 0), _width(value))
            xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
        columns = "".join(
            f'<col min="{index + 1}" max="{index + 1}" width="{min(60, max(8, width + 2))}" customWidth="1"/>'
            for index, width in sorted(widths.items())
        )
        frozen = (
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
            'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            if header and len(rows) > 1
            else ""
        )
        parts[f"xl/worksheets/sheet{number}.xml"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"{frozen}{f'<cols>{columns}</cols>' if columns else ''}<sheetData>{''.join(xml_rows)}</sheetData></worksheet>"
        )
    sheet_entries = "".join(
        f'<sheet name="{_xml(name)}" sheetId="{index}" r:id="rIdSheet{index}"/>' for index, name in enumerate(names, start=1)
    )
    sheet_rels = "".join(
        f'<Relationship Id="rIdSheet{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(names) + 1)
    )
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(names) + 1)
    )
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            f"{overrides}</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{sheet_entries}</sheets><calcPr fullCalcOnLoad=\"1\"/></workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{sheet_rels}<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            "</Relationships>"
        ),
        "xl/styles.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            "</styleSheet>"
        ),
        **parts,
    }
    return _zip(files)


def _zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, text.encode("utf-8"))
    return buffer.getvalue()


# ---- Tools --------------------------------------------------------------------------------------


class _OfficeFileTool:
    hard_cancellable = False
    _SPEC: ToolSpec
    _SUFFIX = ""

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def _make(self, arguments: dict[str, Any]) -> bytes:
        raise NotImplementedError

    def _destination(self, arguments: dict[str, Any]) -> tuple[Path, str | None, bytes | None]:
        path = self.paths.resolve(require_string(arguments, "path"))
        if path.suffix.casefold() != self._SUFFIX or is_sensitive_workspace_path(self.paths.relative(path)):
            raise ToolArgumentError(f"The file must use an allowed workspace path ending in {self._SUFFIX}")
        if not path.parent.is_dir():
            raise ToolError("The parent folder must already exist")
        expected = expected_sha256(arguments)
        return path, expected, _read_preimage(path, expected, None)

    def _write(self, path: Path, expected: str | None, data: bytes) -> dict[str, Any]:
        _check_preimage(path, expected, None)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            _check_preimage(path, expected, None)
            durable_replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return {
            "path": self.paths.relative(path),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes_written": len(data),
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        path, expected, _ = await asyncio.to_thread(self._destination, arguments)
        data = await asyncio.to_thread(self._make, arguments)
        return json_result(await asyncio.to_thread(self._write, path, expected, data))

    async def execute_with_context(self, arguments: dict[str, Any], context: ToolExecutionContext) -> str:
        path, expected, preimage = await asyncio.to_thread(self._destination, arguments)
        data = await asyncio.to_thread(self._make, arguments)
        digest = hashlib.sha256(data).hexdigest()
        await context.prepare_file_checkpoint(
            FileCheckpoint(
                attempt_id=context.attempt_id,
                session_id=context.session_id,
                workspace=str(self.paths.root),
                started_event_id=context.started_event_id,
                relative_path=self.paths.relative(path),
                preimage_sha256=expected,
                preimage=preimage,
                postimage_sha256=digest,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
        result = await asyncio.to_thread(self._write, path, expected, data)
        await context.record_event(
            Event(
                session_id=context.session_id,
                type="file.version.recorded",
                data={"attempt_id": context.attempt_id, "path": result["path"], "sha256": digest, "bytes": len(data)},
                causation_id=context.started_event_id,
                correlation_id=context.correlation_id,
            )
        )
        return json_result(result)


class CreateDocxTool(_OfficeFileTool):
    _SUFFIX = ".docx"
    _SPEC = ToolSpec(
        name="create_docx",
        description=(
            "Create a Word document (.docx) in the workspace from Markdown: # headings, paragraphs, "
            "**bold**, *italic*, `code`, [links](https://...), - and 1. lists (nested by indent), "
            "| tables |, > quotes, ``` code blocks, --- rules, \\newpage. title is an optional "
            "title line. Use expected_sha256=null for a new file; replacing one needs its observed "
            "SHA-256. The parent folder must exist."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "content": {"type": "string", "minLength": 1, "maxLength": _MAX_CONTENT},
                "title": {"type": "string", "maxLength": 1024},
                "expected_sha256": {"type": ["string", "null"]},
            },
            "required": ["path", "content", "expected_sha256"],
            "additionalProperties": False,
        },
        side_effect="write",
        capability=Capability.WORKSPACE_WRITE,
        durable_preimage_checkpoint=True,
    )

    def _make(self, arguments: dict[str, Any]) -> bytes:
        content = require_string(arguments, "content")
        title = arguments.get("title") or ""
        if not isinstance(title, str) or len(title) > 1024 or len(content) > _MAX_CONTENT:
            raise ToolArgumentError("title or content is too long")
        return markdown_docx(content, title)


class CreateXlsxTool(_OfficeFileTool):
    _SUFFIX = ".xlsx"
    _SPEC = ToolSpec(
        name="create_xlsx",
        description=(
            "Create an Excel workbook (.xlsx) in the workspace: sheets, each a name and rows (lists "
            "of cells: numbers stay numbers, true/false, text, and text starting with = is a "
            "formula such as =SUM(B2:B9)). The first row is a bold, frozen header unless header is "
            "false. Use expected_sha256=null for a new file; replacing one needs its observed "
            "SHA-256. The parent folder must exist."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "sheets": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 50,
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "maxLength": 31},
                            "rows": {
                                "type": "array",
                                "maxItems": _MAX_ROWS,
                                "items": {
                                    "type": "array",
                                    "maxItems": _MAX_COLUMNS,
                                    "items": {"type": ["string", "number", "boolean", "null"]},
                                },
                            },
                        },
                        "required": ["rows"],
                        "additionalProperties": False,
                    },
                },
                "header": {"type": "boolean"},
                "expected_sha256": {"type": ["string", "null"]},
            },
            "required": ["path", "sheets", "expected_sha256"],
            "additionalProperties": False,
        },
        side_effect="write",
        capability=Capability.WORKSPACE_WRITE,
        durable_preimage_checkpoint=True,
    )

    def _make(self, arguments: dict[str, Any]) -> bytes:
        sheets = arguments.get("sheets")
        if not isinstance(sheets, list) or not 1 <= len(sheets) <= 50:
            raise ToolArgumentError("'sheets' must list 1 to 50 sheets")
        cells = 0
        for sheet in sheets:
            rows = sheet.get("rows") if isinstance(sheet, dict) else None
            if not isinstance(rows, list) or len(rows) > _MAX_ROWS or not all(
                isinstance(row, list) and len(row) <= _MAX_COLUMNS for row in rows
            ):
                raise ToolArgumentError(f"each sheet needs rows: up to {_MAX_ROWS} lists of up to {_MAX_COLUMNS} cells")
            for row in rows:
                for value in row:
                    if value is not None and not isinstance(value, (str, int, float, bool)):
                        raise ToolArgumentError("cells are numbers, text, true/false or null")
                    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
                        raise ToolArgumentError("cells cannot hold NaN or infinity")
                    if isinstance(value, str) and len(value) > 32767:
                        raise ToolArgumentError("a cell holds at most 32767 characters")
                cells += len(row)
        if cells > _MAX_CELLS:
            raise ToolArgumentError(f"at most {_MAX_CELLS} cells")
        header = arguments.get("header", True)
        if not isinstance(header, bool):
            raise ToolArgumentError("'header' must be true or false")
        return rows_xlsx(sheets, header)
