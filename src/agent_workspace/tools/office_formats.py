"""Word, Excel and PowerPoint files written and edited with the standard library only.

``markdown_docx`` turns Markdown into a .docx, ``rows_xlsx`` writes rows into the sheets of an
.xlsx and ``slides_pptx`` lays out title, section and bullet slides in a 16:9 .pptx. The Word
and Excel writers are the Android app's. ``replace_in_docx`` replaces text inside the
paragraphs of an existing document and keeps each run's formatting; ``set_xlsx_cells`` writes
values and formulas into the cells of an existing workbook and keeps their styles. Both edit
the package's XML as text: an XML parser would rename namespace prefixes that Office files
refer to by name.
"""

from __future__ import annotations

import html
import io
import re
import zipfile
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_CJK = re.compile(r"[⺀-鿿豈-﫿＀-￯]")

_PACKAGE = "http://schemas.openxmlformats.org/package/2006"
_RELATIONSHIPS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_SHEET = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DRAWING = "http://schemas.openxmlformats.org/drawingml/2006/main"
_SLIDE = "http://schemas.openxmlformats.org/presentationml/2006/main"
_OFFICE_TYPE = "application/vnd.openxmlformats-officedocument"
_XML_HEADER = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


class OfficeFormatError(ValueError):
    """A file that is not the Office document it claims to be, or an edit that cannot apply."""


def _xml(text: str) -> str:
    return escape(_CONTROL.sub("", text), {'"': "&quot;"})


def _zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, text.encode("utf-8"))
    return buffer.getvalue()


def _relationships(
    entries: list[tuple[str, str, str]], external: frozenset[str] = frozenset()
) -> str:
    """A relationships part: (id, type name, target), types relative to the 2006 namespace."""
    items = "".join(
        f'<Relationship Id="{rid}" Type="{_RELATIONSHIPS}/{kind}" Target="{_xml(target)}"'
        + (' TargetMode="External"' if rid in external else "")
        + "/>"
        for rid, kind, target in entries
    )
    return f'{_XML_HEADER}<Relationships xmlns="{_PACKAGE}/relationships">{items}</Relationships>'


def _content_types(overrides: list[tuple[str, str]]) -> str:
    items = "".join(
        f'<Override PartName="{part}" ContentType="{kind}"/>' for part, kind in overrides
    )
    return (
        f'{_XML_HEADER}<Types xmlns="{_PACKAGE}/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
        'relationships+xml"/>'
        f'<Default Extension="xml" ContentType="application/xml"/>{items}</Types>'
    )


# ---- Word ---------------------------------------------------------------------------------------

_INLINE = re.compile(
    r"(?P<code>`[^`\n]+`)|(?P<link>\[(?P<label>[^\]\n]+)\]\((?P<url>[^)\s]+)\))"
    # Chinese counts as a boundary (snake_case words do not turn italic).
    r"|(?P<bold>\*\*(?=\S)(?P<btext>.+?)(?<=\S)\*\*)"
    r"|(?P<italic>(?<![A-Za-z0-9*])[*_](?=\S)(?P<itext>[^*_\n]+?)(?<=\S)[*_](?![A-Za-z0-9*]))"
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
                out.append(
                    self.run(match.group("code")[1:-1], style + '<w:rStyle w:val="CodeChar"/>')
                )
            elif match.group("link"):
                url = match.group("url")
                if re.match(r"https?://", url):
                    self.links.append(url)
                    rid = f"rIdLink{len(self.links)}"
                    label = self.run(match.group("label"), style + '<w:rStyle w:val="Hyperlink"/>')
                    out.append(f'<w:hyperlink r:id="{rid}">{label}</w:hyperlink>')
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
        body = "<w:br/>".join(f'<w:t xml:space="preserve">{_xml(part)}</w:t>' for part in parts)
        return f"<w:r>{properties}{body}</w:r>"

    def paragraph(self, text: str, style: str | None = None, extra: str = "") -> None:
        properties = (f'<w:pStyle w:val="{style}"/>' if style else "") + extra
        self.body.append(f"<w:p><w:pPr>{properties}</w:pPr>{self.runs(text)}</w:p>")

    def code(self, lines: list[str]) -> None:
        for line in lines or [""]:
            self.body.append(f'<w:p><w:pPr><w:pStyle w:val="Code"/></w:pPr>{self.run(line)}</w:p>')

    def list_item(self, text: str, level: int, list_id: int) -> None:
        self.paragraph(
            text,
            "ListParagraph",
            f'<w:numPr><w:ilvl w:val="{min(level, 8)}"/><w:numId w:val="{list_id}"/></w:numPr>',
        )

    def table(self, rows: list[list[str]], aligns: list[str]) -> None:
        width = max(len(row) for row in rows)
        grid = "".join('<w:gridCol w:w="2000"/>' for _ in range(width))
        out = [
            '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="pct"/>'
            f"</w:tblPr><w:tblGrid>{grid}</w:tblGrid>"
        ]
        for index, row in enumerate(rows):
            cells = []
            for column in range(width):
                text = row[column] if column < len(row) else ""
                align = aligns[column] if column < len(aligns) else ""
                jc = f'<w:jc w:val="{align}"/>' if align else ""
                runs = self.runs(text, "<w:b/>" if index == 0 else "")
                cells.append(
                    '<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr>'
                    f"<w:p><w:pPr>{jc}</w:pPr>{runs}</w:p></w:tc>"
                )
            header = "<w:trPr><w:tblHeader/></w:trPr>" if index == 0 else ""
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


# A table's rule line: |---|:-:|--:| (one dash is enough, as in GitHub Markdown).
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


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
            and _TABLE_RULE.match(lines[index + 1])
        ):
            flush()
            rows = [_cells(line)]
            aligns = [
                "center"
                if cell.startswith(":") and cell.endswith(":")
                else "right"
                if cell.endswith(":")
                else ""
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
            if item.group(2)[0].isdigit():
                if level not in lists:
                    document.numbered += 1
                    lists[level] = 2 + document.numbered
                list_id = lists[level]
            else:
                list_id = 1
            for deeper in [key for key in lists if key > level]:
                del lists[deeper]
            document.list_item(item.group(3), level, list_id)
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
                '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" '
                'w:color="999999"/></w:pBdr></w:pPr></w:p>'
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
    body = "".join(document.body) + (
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1304" w:bottom="1440" w:left="1304" w:header="720" '
        'w:footer="720" w:gutter="0"/></w:sectPr>'
    )
    links = [
        (f"rIdLink{index}", "hyperlink", url) for index, url in enumerate(document.links, start=1)
    ]
    numbered = "".join(
        f'<w:num w:numId="{2 + index}"><w:abstractNumId w:val="1"/>'
        '<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'
        for index in range(1, document.numbered + 1)
    )
    word = f"{_OFFICE_TYPE}.wordprocessingml"
    files = {
        "[Content_Types].xml": _content_types(
            [
                ("/word/document.xml", f"{word}.document.main+xml"),
                ("/word/styles.xml", f"{word}.styles+xml"),
                ("/word/numbering.xml", f"{word}.numbering+xml"),
            ]
        ),
        "_rels/.rels": _relationships([("rId1", "officeDocument", "word/document.xml")]),
        "word/_rels/document.xml.rels": _relationships(
            [
                ("rIdStyles", "styles", "styles.xml"),
                ("rIdNumbering", "numbering", "numbering.xml"),
                *links,
            ],
            frozenset(rid for rid, _, _ in links),
        ),
        "word/document.xml": (
            f'{_XML_HEADER}<w:document xmlns:w="{_WORD}" xmlns:r="{_RELATIONSHIPS}">'
            f"<w:body>{body}</w:body></w:document>"
        ),
        "word/styles.xml": _DOCX_STYLES,
        "word/numbering.xml": _DOCX_NUMBERING.replace(
            "</w:numbering>", numbered + "</w:numbering>"
        ),
    }
    return _zip(files)


def _heading_style(level: int) -> str:
    size = {1: 32, 2: 28, 3: 26, 4: 24, 5: 22, 6: 22}[level]
    return (
        f'<w:style w:type="paragraph" w:styleId="Heading{level}"><w:name w:val="heading {level}"/>'
        '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
        f'<w:pPr><w:keepNext/><w:spacing w:before="{240 if level <= 2 else 160}" w:after="120"/>'
        f'<w:outlineLvl w:val="{level - 1}"/></w:pPr><w:rPr><w:b/><w:sz w:val="{size}"/></w:rPr>'
        "</w:style>"
    )


_BORDER = 'w:val="single" w:sz="4" w:color="999999"'
_DOCX_STYLES = (
    f'{_XML_HEADER}<w:styles xmlns:w="{_WORD}">'
    '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" '
    'w:eastAsia="等线" w:cs="Arial"/><w:sz w:val="22"/><w:lang w:val="zh-CN" w:eastAsia="zh-CN"/>'
    '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="300" '
    'w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
    "<w:qFormat/></w:style>"
    '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
    '<w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:jc w:val="center"/>'
    '<w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>'
    + "".join(_heading_style(level) for level in range(1, 7))
    + '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="60"/></w:pPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="567"/><w:pBdr><w:left w:val="single" '
    'w:sz="12" w:space="8" w:color="C8CDCC"/></w:pBdr></w:pPr><w:rPr><w:color w:val="404040"/>'
    "</w:rPr></w:style>"
    '<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
    '<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/></w:pPr><w:rPr><w:rFonts '
    'w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="等线"/><w:sz w:val="19"/></w:rPr>'
    "</w:style>"
    '<w:style w:type="character" w:styleId="CodeChar"><w:name w:val="Code Char"/><w:rPr>'
    '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:shd w:val="clear" w:color="auto" '
    'w:fill="F2F2F2"/></w:rPr></w:style>'
    '<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/>'
    '<w:rPr><w:color w:val="0B5E55"/><w:u w:val="single"/></w:rPr></w:style>'
    '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr>'
    f"<w:tblBorders><w:top {_BORDER}/><w:left {_BORDER}/><w:bottom {_BORDER}/>"
    f"<w:right {_BORDER}/><w:insideH {_BORDER}/><w:insideV {_BORDER}/></w:tblBorders>"
    '<w:tblCellMar><w:left w:w="100" w:type="dxa"/><w:right w:w="100" w:type="dxa"/>'
    "</w:tblCellMar></w:tblPr></w:style></w:styles>"
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
    f'{_XML_HEADER}<w:numbering xmlns:w="{_WORD}">'
    f'<w:abstractNum w:abstractNumId="0">{_levels(True)}</w:abstractNum>'
    f'<w:abstractNum w:abstractNumId="1">{_levels(False)}</w:abstractNum>'
    '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
    '<w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>'
    "</w:numbering>"
)


# ---- Editing Word -------------------------------------------------------------------------------

# A run's text element (not w:tab or w:tbl), and the end of a paragraph.
_TEXT_TOKEN = re.compile(
    r"<w:t(?=[\s>/])(?P<attributes>[^>]*?)(?:/>|>(?P<text>.*?)</w:t>)|</w:p>", re.S
)
_EDITABLE_PART = re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$")


@dataclass(slots=True)
class _Token:
    start: int
    end: int
    attributes: str
    text: str


def _paragraph_tokens(xml: str) -> list[list[_Token]]:
    paragraphs: list[list[_Token]] = []
    current: list[_Token] = []
    for match in _TEXT_TOKEN.finditer(xml):
        if match.group(0) == "</w:p>":
            if current:
                paragraphs.append(current)
            current = []
            continue
        text = html.unescape(match.group("text") or "")
        current.append(_Token(match.start(), match.end(), match.group("attributes") or "", text))
    if current:
        paragraphs.append(current)
    return paragraphs


def _replace_in_part(xml: str, find: str, replacement: str) -> tuple[str, int]:
    edits: list[tuple[_Token, str]] = []
    count = 0
    for tokens in _paragraph_tokens(xml):
        texts = [token.text for token in tokens]
        joined = "".join(texts)
        if find not in joined:
            continue
        # Where each element's text begins within the paragraph.
        starts = []
        position = 0
        for text in texts:
            starts.append(position)
            position += len(text)
        changed = list(texts)
        index = joined.find(find)
        occurrences = []
        while index != -1:
            occurrences.append(index)
            index = joined.find(find, index + len(find))
        for begin in reversed(occurrences):
            finish = begin + len(find)
            first = max(i for i, start in enumerate(starts) if start <= begin)
            last = max(i for i, start in enumerate(starts) if start < finish or i == first)
            head = changed[first][: begin - starts[first]]
            tail = changed[last][finish - starts[last] :]
            if first == last:
                changed[first] = head + replacement + tail
            else:
                # The text takes the formatting of the run where the match begins.
                changed[first] = head + replacement
                for middle in range(first + 1, last):
                    changed[middle] = ""
                changed[last] = tail
            count += 1
        for token, before, after in zip(tokens, texts, changed, strict=True):
            if before != after:
                edits.append((token, after))
    for token, text in sorted(edits, key=lambda item: item[0].start, reverse=True):
        attributes = token.attributes.rstrip("/")
        if "xml:space" not in attributes:
            attributes += ' xml:space="preserve"'
        element = f"<w:t{attributes}>{_xml(text)}</w:t>"
        xml = xml[: token.start] + element + xml[token.end :]
    return xml, count


def replace_in_docx(data: bytes, replacements: list[tuple[str, str]]) -> tuple[bytes, list[int]]:
    """The document with each (find, replacement) applied in turn, and how often each matched.

    Matches are found in the text of one paragraph at a time (also in headers, footers and
    notes), across the runs the paragraph is split into.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        names = archive.namelist()
        if "word/document.xml" not in names:
            raise OfficeFormatError("not a Word document")
        parts = {name: archive.read(name) for name in names}
    except zipfile.BadZipFile:
        raise OfficeFormatError("not a Word document") from None
    counts = [0] * len(replacements)
    for name in names:
        if not _EDITABLE_PART.match(name):
            continue
        xml = parts[name].decode("utf-8")
        for index, (find, replacement) in enumerate(replacements):
            xml, matched = _replace_in_part(xml, find, replacement)
            counts[index] += matched
        parts[name] = xml.encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as output:
        for info in archive.infolist():
            output.writestr(info, parts[info.filename])
    return buffer.getvalue(), counts


# ---- Excel --------------------------------------------------------------------------------------


def column_name(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def column_index(name: str) -> int:
    index = 0
    for character in name:
        index = index * 26 + ord(character) - 64
    return index - 1


def _width(value: Any) -> int:
    return sum(2 if _CJK.match(character) else 1 for character in str(value))


def _cell_xml(reference: str, value: Any, style: str = "") -> str:
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"{style}><v>{int(value)}</v></c>'
    if isinstance(value, int | float):
        return f'<c r="{reference}"{style}><v>{value!r}</v></c>'
    if isinstance(value, str) and value.startswith("=") and len(value) > 1:
        return f'<c r="{reference}"{style}><f>{_xml(value[1:])}</f></c>'
    text = _xml(str(value))
    return (
        f'<c r="{reference}" t="inlineStr"{style}><is><t xml:space="preserve">{text}</t></is></c>'
    )


def rows_xlsx(sheets: list[dict[str, Any]], header: bool = True) -> bytes:
    """An .xlsx of named sheets of rows: numbers stay numbers, '=...' is a formula, the first row
    is the bold, frozen header unless header is false."""
    names: list[str] = []
    parts: dict[str, str] = {}
    for number, sheet in enumerate(sheets, start=1):
        raw_name = str(sheet.get("name") or f"Sheet{number}")
        name = re.sub(r"[\[\]:*?/\\]", " ", raw_name).strip()[:31] or f"Sheet{number}"
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
            for index, value in enumerate(row):
                if value is None or value == "":
                    continue
                style = ' s="1"' if header and row_index == 1 else ""
                cells.append(_cell_xml(f"{column_name(index)}{row_index}", value, style))
                widths[index] = max(widths.get(index, 0), _width(value))
            xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
        columns = "".join(
            f'<col min="{index + 1}" max="{index + 1}" width="{min(60, max(8, width + 2))}" '
            'customWidth="1"/>'
            for index, width in sorted(widths.items())
        )
        frozen = (
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
            'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            if header and len(rows) > 1
            else ""
        )
        column_list = f"<cols>{columns}</cols>" if columns else ""
        parts[f"xl/worksheets/sheet{number}.xml"] = (
            f'{_XML_HEADER}<worksheet xmlns="{_SHEET}">'
            f"{frozen}{column_list}<sheetData>{''.join(xml_rows)}</sheetData></worksheet>"
        )
    sheet_entries = "".join(
        f'<sheet name="{_xml(name)}" sheetId="{index}" r:id="rIdSheet{index}"/>'
        for index, name in enumerate(names, start=1)
    )
    sheet_type = f"{_OFFICE_TYPE}.spreadsheetml"
    files = {
        "[Content_Types].xml": _content_types(
            [
                ("/xl/workbook.xml", f"{sheet_type}.sheet.main+xml"),
                ("/xl/styles.xml", f"{sheet_type}.styles+xml"),
            ]
            + [
                (f"/xl/worksheets/sheet{index}.xml", f"{sheet_type}.worksheet+xml")
                for index in range(1, len(names) + 1)
            ]
        ),
        "_rels/.rels": _relationships([("rId1", "officeDocument", "xl/workbook.xml")]),
        "xl/workbook.xml": (
            f'{_XML_HEADER}<workbook xmlns="{_SHEET}" xmlns:r="{_RELATIONSHIPS}">'
            f'<sheets>{sheet_entries}</sheets><calcPr fullCalcOnLoad="1"/></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": _relationships(
            [
                (f"rIdSheet{index}", "worksheet", f"worksheets/sheet{index}.xml")
                for index in range(1, len(names) + 1)
            ]
            + [("rIdStyles", "styles", "styles.xml")]
        ),
        "xl/styles.xml": (
            f'{_XML_HEADER}<styleSheet xmlns="{_SHEET}">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/>'
            '<sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill><fill>'
            '<patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border>'
            '</borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" '
            'borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" '
            'fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" '
            'borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1">'
            '<cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
        ),
        **parts,
    }
    return _zip(files)


# ---- Editing Excel ------------------------------------------------------------------------------

_REFERENCE = re.compile(r"^(?P<column>[A-Z]{1,3})(?P<row>[1-9]\d{0,6})$")
_ROW = re.compile(r'<row\b[^>]*\br="(?P<number>\d+)"[^>]*?(?:/>|>(?P<body>.*?)</row>)', re.S)
_CELL = re.compile(r"<c\b(?P<attributes>[^>]*?)(?:/>|>.*?</c>)", re.S)
_SHEET_DATA = re.compile(r"<sheetData\s*/>|<sheetData>(?P<body>.*?)</sheetData>", re.S)


def _worksheet_path(parts: dict[str, bytes], sheet: str | None) -> str:
    workbook = parts.get("xl/workbook.xml", b"").decode("utf-8")
    relations = parts.get("xl/_rels/workbook.xml.rels", b"").decode("utf-8")
    entries = re.findall(r'<sheet\b[^>]*?name="([^"]*)"[^>]*?r:id="([^"]+)"', workbook)
    if not entries:
        raise OfficeFormatError("not an Excel workbook")
    names = [html.unescape(name) for name, _ in entries]
    if sheet is None:
        rid = entries[0][1]
    else:
        matches = [rid for (name, rid) in entries if html.unescape(name) == sheet]
        if not matches:
            raise OfficeFormatError(f"no sheet named {sheet!r}; the sheets are {names}")
        rid = matches[0]
    target = re.search(
        rf'<Relationship\b[^>]*?Id="{re.escape(rid)}"[^>]*?Target="([^"]+)"', relations
    )
    if target is None:
        target = re.search(
            rf'<Relationship\b[^>]*?Target="([^"]+)"[^>]*?Id="{re.escape(rid)}"', relations
        )
    if target is None:
        raise OfficeFormatError("the workbook does not say where the sheet is")
    path = target.group(1).lstrip("/")
    return path if path.startswith("xl/") else f"xl/{path}"


def _cell_column(cell: str) -> int | None:
    reference = re.search(r'\sr="([A-Z]{1,3})\d+"', cell[: cell.find(">") + 1])
    return column_index(reference.group(1)) if reference else None


def _set_cells_in_sheet(xml: str, values: list[tuple[str, Any]]) -> str:
    """Sheet XML with the cells written, keeping each existing cell's style."""
    data = _SHEET_DATA.search(xml)
    if data is None:
        raise OfficeFormatError("the sheet has no cell data")
    rows: dict[int, tuple[str, dict[int, str]]] = {}
    for match in _ROW.finditer(data.group("body") or ""):
        opening = match.group(0)[: match.group(0).index(">") + 1].replace("/>", ">")
        cells: dict[int, str] = {}
        for cell in _CELL.finditer(match.group("body") or ""):
            column = _cell_column(cell.group(0))
            if column is not None:
                cells[column] = cell.group(0)
        rows[int(match.group("number"))] = (opening, cells)
    for reference, value in values:
        parsed = _REFERENCE.match(reference)
        assert parsed is not None
        row_number = int(parsed["row"])
        column = column_index(parsed["column"])
        opening, cells = rows.get(row_number, (f'<row r="{row_number}">', {}))
        # The row's column span is a hint that would no longer match its cells.
        opening = re.sub(r'\sspans="[^"]*"', "", opening)
        existing = cells.get(column, "")
        style = re.search(r'\ss="(\d+)"', existing[: existing.find(">") + 1]) if existing else None
        style_attribute = f' s="{style.group(1)}"' if style else ""
        if value is None:
            cells.pop(column, None)
        else:
            cells[column] = _cell_xml(reference, value, style_attribute)
        rows[row_number] = (opening, cells)
    body = "".join(
        opening + "".join(cells[column] for column in sorted(cells)) + "</row>"
        for _number, (opening, cells) in sorted(rows.items())
    )
    return xml[: data.start()] + f"<sheetData>{body}</sheetData>" + xml[data.end() :]


def set_xlsx_cells(data: bytes, sheet: str | None, values: list[tuple[str, Any]]) -> bytes:
    """The workbook with the given cells of one sheet (the first when unnamed) set or cleared.

    A value is a number, true/false, text, text starting with = (a formula) or None (clear).
    Formulas are recalculated when the workbook opens.
    """
    for reference, _ in values:
        if not _REFERENCE.match(reference):
            raise OfficeFormatError(f"{reference!r} is not a cell reference such as B3")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        parts = {name: archive.read(name) for name in archive.namelist()}
    except zipfile.BadZipFile:
        raise OfficeFormatError("not an Excel workbook") from None
    path = _worksheet_path(parts, sheet)
    if path not in parts:
        raise OfficeFormatError("the sheet is missing from the workbook")
    parts[path] = _set_cells_in_sheet(parts[path].decode("utf-8"), values).encode("utf-8")
    workbook = parts["xl/workbook.xml"].decode("utf-8")
    if "<calcPr" in workbook:
        workbook = re.sub(r"<calcPr\b([^>]*?)/?>", _full_calc, workbook, count=1)
    else:
        workbook = workbook.replace("</workbook>", '<calcPr fullCalcOnLoad="1"/></workbook>')
    parts["xl/workbook.xml"] = workbook.encode("utf-8")
    # Cached results of other formulas would be stale; Excel rebuilds the chain on load.
    parts.pop("xl/calcChain.xml", None)
    content_types = parts["[Content_Types].xml"].decode("utf-8")
    parts["[Content_Types].xml"] = re.sub(
        r'<Override PartName="/xl/calcChain\.xml"[^>]*/>', "", content_types
    ).encode("utf-8")
    relations = parts.get("xl/_rels/workbook.xml.rels", b"").decode("utf-8")
    parts["xl/_rels/workbook.xml.rels"] = re.sub(
        r'<Relationship\b[^>]*Target="calcChain\.xml"[^>]*/>', "", relations
    ).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as output:
        for info in archive.infolist():
            if info.filename in parts:
                output.writestr(info, parts[info.filename])
    return buffer.getvalue()


def _full_calc(match: re.Match[str]) -> str:
    attributes = re.sub(r'\sfullCalcOnLoad="[^"]*"', "", match.group(1))
    return f'<calcPr{attributes} fullCalcOnLoad="1"/>'


# ---- PowerPoint ---------------------------------------------------------------------------------

_SLIDE_WIDTH = 12192000
_SLIDE_HEIGHT = 6858000
_NAMESPACES = f'xmlns:a="{_DRAWING}" xmlns:r="{_RELATIONSHIPS}" xmlns:p="{_SLIDE}"'
_GROUP = (
    '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
    '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/>'
    '<a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
)
_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")


def _slide_runs(text: str, size: int | None = None) -> str:
    """Runs of one line of slide text; **bold** becomes bold."""
    runs = []
    position = 0
    size_attribute = f' sz="{size}"' if size else ""
    for match in _BOLD.finditer(text):
        if match.start() > position:
            runs.append((text[position : match.start()], False))
        runs.append((match.group(1), True))
        position = match.end()
    if position < len(text) or not runs:
        runs.append((text[position:], False))
    return "".join(
        f'<a:r><a:rPr lang="zh-CN" altLang="en-US"{size_attribute}{' b="1"' if bold else ""}'
        f' dirty="0"/><a:t>{_xml(part)}</a:t></a:r>'
        for part, bold in runs
    )


def _shape(shape_id: int, name: str, placeholder: str, paragraphs: str, position: str = "") -> str:
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvSpPr>'
        f'<a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr>{placeholder}</p:nvPr></p:nvSpPr>'
        f"<p:spPr>{position}</p:spPr><p:txBody><a:bodyPr/><a:lstStyle/>{paragraphs}"
        "</p:txBody></p:sp>"
    )


def _xfrm(x: int, y: int, width: int, height: int) -> str:
    return f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm>'


def _paragraphs(lines: list[tuple[str, int]]) -> str:
    if not lines:
        return '<a:p><a:endParaRPr lang="zh-CN" dirty="0"/></a:p>'
    return "".join(
        f"<a:p>{f'<a:pPr lvl="{level}"/>' if level else ''}{_slide_runs(text)}</a:p>"
        for text, level in lines
    )


@dataclass(frozen=True, slots=True)
class Slide:
    """One slide: a title, then bullet lines (text, level 0-4) or, for a title slide, a subtitle."""

    kind: str  # "title", "section" or "content"
    title: str
    lines: tuple[tuple[str, int], ...] = ()


def _slide_xml(slide: Slide) -> str:
    if slide.kind in {"title", "section"}:
        title = _shape(2, "Title 1", '<p:ph type="ctrTitle"/>', _paragraphs([(slide.title, 0)]))
        subtitle = _shape(
            3,
            "Subtitle 2",
            '<p:ph type="subTitle" idx="1"/>',
            _paragraphs([(text, 0) for text, _ in slide.lines]),
        )
        shapes = title + subtitle
    else:
        title = _shape(2, "Title 1", '<p:ph type="title"/>', _paragraphs([(slide.title, 0)]))
        body = _shape(3, "Content 2", '<p:ph idx="1"/>', _paragraphs(list(slide.lines)))
        shapes = title + body
    return (
        f"{_XML_HEADER}<p:sld {_NAMESPACES}><p:cSld><p:spTree>{_GROUP}{shapes}</p:spTree>"
        "</p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )


def _text_style(levels: list[tuple[int, int, int]], bullets: bool) -> str:
    out = []
    for number, (margin, size, before) in enumerate(levels, start=1):
        bullet = (
            '<a:buFont typeface="Arial" panose="020B0604020202020204"/><a:buChar char="•"/>'
            if bullets
            else "<a:buNone/>"
        )
        indent = f' marL="{margin}" indent="-{228600}"' if bullets else ""
        out.append(
            f'<a:lvl{number}pPr{indent} algn="l" defTabSz="914400" eaLnBrk="1" '
            'latinLnBrk="0" hangingPunct="1"><a:lnSpc><a:spcPct val="100000"/></a:lnSpc>'
            f'<a:spcBef><a:spcPts val="{before}"/></a:spcBef>{bullet}'
            f'<a:defRPr sz="{size}" kern="1200"><a:solidFill><a:schemeClr val="tx1"/>'
            '</a:solidFill><a:latin typeface="+mn-lt"/><a:ea typeface="+mn-ea"/>'
            '<a:cs typeface="+mn-cs"/></a:defRPr></a:lvl'
            f"{number}pPr>"
        )
    return "".join(out)


_TITLE_STYLE = (
    '<a:lvl1pPr algn="l" defTabSz="914400" eaLnBrk="1" latinLnBrk="0" hangingPunct="1">'
    '<a:lnSpc><a:spcPct val="90000"/></a:lnSpc><a:spcBef><a:spcPct val="0"/></a:spcBef>'
    '<a:buNone/><a:defRPr sz="3600" b="1" kern="1200"><a:solidFill><a:schemeClr val="tx2"/>'
    '</a:solidFill><a:latin typeface="+mj-lt"/><a:ea typeface="+mj-ea"/>'
    '<a:cs typeface="+mj-cs"/></a:defRPr></a:lvl1pPr>'
)
_BODY_LEVELS = [(228600, 2400, 1000), (685800, 2000, 500), (1143000, 1800, 500),
                (1600200, 1600, 500), (2057400, 1600, 500)]  # fmt: skip


def _master_xml() -> str:
    title = _shape(
        2,
        "Title Placeholder 1",
        '<p:ph type="title"/>',
        _paragraphs([]),
        _xfrm(838200, 365125, 10515600, 1325563)
        + '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>',
    )
    body = _shape(
        3,
        "Text Placeholder 2",
        '<p:ph type="body" idx="1"/>',
        _paragraphs([]),
        _xfrm(838200, 1825625, 10515600, 4351338)
        + '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>',
    )
    colors = (
        'bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" '
        'accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" '
        'hlink="hlink" folHlink="folHlink"'
    )
    return (
        f'{_XML_HEADER}<p:sldMaster {_NAMESPACES}><p:cSld><p:bg><p:bgRef idx="1001">'
        f'<a:schemeClr val="bg1"/></p:bgRef></p:bg><p:spTree>{_GROUP}{title}{body}</p:spTree>'
        f"</p:cSld><p:clrMap {colors}/><p:sldLayoutIdLst>"
        '<p:sldLayoutId id="2147483649" r:id="rId1"/><p:sldLayoutId id="2147483650" r:id="rId2"/>'
        f"</p:sldLayoutIdLst><p:txStyles><p:titleStyle>{_TITLE_STYLE}</p:titleStyle>"
        f"<p:bodyStyle>{_text_style(_BODY_LEVELS, True)}</p:bodyStyle>"
        '<p:otherStyle><a:defPPr><a:defRPr lang="zh-CN"/></a:defPPr></p:otherStyle>'
        "</p:txStyles></p:sldMaster>"
    )


def _layout_xml(kind: str) -> str:
    if kind == "title":
        centered = '<a:lvl1pPr algn="ctr"><a:buNone/><a:defRPr sz="2400"/></a:lvl1pPr>'
        title = (
            '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Title 1"/><p:cNvSpPr><a:spLocks noGrp="1"/>'
            '</p:cNvSpPr><p:nvPr><p:ph type="ctrTitle"/></p:nvPr></p:nvSpPr><p:spPr>'
            + _xfrm(1524000, 1122363, 9144000, 2387600)
            + '</p:spPr><p:txBody><a:bodyPr anchor="b"><a:normAutofit/></a:bodyPr><a:lstStyle>'
            '<a:lvl1pPr algn="ctr"><a:defRPr sz="5400"/></a:lvl1pPr></a:lstStyle>'
            '<a:p><a:endParaRPr lang="zh-CN"/></a:p></p:txBody></p:sp>'
        )
        subtitle = (
            '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Subtitle 2"/><p:cNvSpPr><a:spLocks noGrp="1"/>'
            '</p:cNvSpPr><p:nvPr><p:ph type="subTitle" idx="1"/></p:nvPr></p:nvSpPr><p:spPr>'
            + _xfrm(1524000, 3602038, 9144000, 1655762)
            + f"</p:spPr><p:txBody><a:bodyPr><a:normAutofit/></a:bodyPr><a:lstStyle>{centered}"
            '</a:lstStyle><a:p><a:endParaRPr lang="zh-CN"/></a:p></p:txBody></p:sp>'
        )
        name, layout_type, shapes = "Title Slide", "title", title + subtitle
    else:
        title = _shape(2, "Title 1", '<p:ph type="title"/>', _paragraphs([]))
        body = _shape(3, "Content Placeholder 2", '<p:ph idx="1"/>', _paragraphs([]))
        name, layout_type, shapes = "Title and Content", "obj", title + body
    return (
        f'{_XML_HEADER}<p:sldLayout {_NAMESPACES} type="{layout_type}" preserve="1">'
        f'<p:cSld name="{name}"><p:spTree>{_GROUP}{shapes}</p:spTree></p:cSld>'
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"
    )


def _theme_xml() -> str:
    accents = ["0B5E55", "2F6FB2", "C2410C", "7C3AED", "0F766E", "B45309"]
    colors = "".join(
        f'<a:accent{index}><a:srgbClr val="{color}"/></a:accent{index}>'
        for index, color in enumerate(accents, start=1)
    )
    fill = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    line = f'<a:ln w="9525">{fill}</a:ln>'
    font = (
        '<a:latin typeface="Calibri"/><a:ea typeface="等线"/><a:cs typeface=""/>'
        '<a:font script="Hans" typeface="等线"/><a:font script="Jpan" typeface="游ゴシック"/>'
    )
    return (
        f'{_XML_HEADER}<a:theme xmlns:a="{_DRAWING}" name="Agent Workspace"><a:themeElements>'
        '<a:clrScheme name="Agent Workspace"><a:dk1><a:sysClr val="windowText" '
        'lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
        '<a:dk2><a:srgbClr val="1F2A37"/></a:dk2><a:lt2><a:srgbClr val="EEF1F4"/></a:lt2>'
        f'{colors}<a:hlink><a:srgbClr val="2F6FB2"/></a:hlink><a:folHlink>'
        '<a:srgbClr val="7C3AED"/></a:folHlink></a:clrScheme>'
        f'<a:fontScheme name="Agent Workspace"><a:majorFont>{font}</a:majorFont>'
        f"<a:minorFont>{font}</a:minorFont></a:fontScheme>"
        f'<a:fmtScheme name="Agent Workspace"><a:fillStyleLst>{fill * 3}</a:fillStyleLst>'
        f"<a:lnStyleLst>{line * 3}</a:lnStyleLst><a:effectStyleLst>"
        + "<a:effectStyle><a:effectLst/></a:effectStyle>"
        * 3
        + f"</a:effectStyleLst><a:bgFillStyleLst>{fill * 3}</a:bgFillStyleLst></a:fmtScheme>"
        "</a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>"
    )


def slides_pptx(slides: list[Slide]) -> bytes:
    """A 16:9 presentation of title, section and bullet slides in a plain theme."""
    if not slides:
        raise OfficeFormatError("a presentation needs at least one slide")
    presentation_type = f"{_OFFICE_TYPE}.presentationml"
    count = len(slides)
    slide_ids = "".join(
        f'<p:sldId id="{256 + index}" r:id="rIdSlide{index}"/>' for index in range(1, count + 1)
    )
    files = {
        "[Content_Types].xml": _content_types(
            [
                ("/ppt/presentation.xml", f"{presentation_type}.presentation.main+xml"),
                ("/ppt/slideMasters/slideMaster1.xml", f"{presentation_type}.slideMaster+xml"),
                ("/ppt/slideLayouts/slideLayout1.xml", f"{presentation_type}.slideLayout+xml"),
                ("/ppt/slideLayouts/slideLayout2.xml", f"{presentation_type}.slideLayout+xml"),
                ("/ppt/theme/theme1.xml", f"{_OFFICE_TYPE}.theme+xml"),
                ("/ppt/presProps.xml", f"{presentation_type}.presProps+xml"),
                ("/ppt/viewProps.xml", f"{presentation_type}.viewProps+xml"),
                ("/ppt/tableStyles.xml", f"{presentation_type}.tableStyles+xml"),
            ]
            + [
                (f"/ppt/slides/slide{index}.xml", f"{presentation_type}.slide+xml")
                for index in range(1, count + 1)
            ]
        ),
        "_rels/.rels": _relationships([("rId1", "officeDocument", "ppt/presentation.xml")]),
        "ppt/presentation.xml": (
            f'{_XML_HEADER}<p:presentation {_NAMESPACES} saveSubsetFonts="1">'
            '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rIdMaster"/>'
            f"</p:sldMasterIdLst><p:sldIdLst>{slide_ids}</p:sldIdLst>"
            f'<p:sldSz cx="{_SLIDE_WIDTH}" cy="{_SLIDE_HEIGHT}"/>'
            '<p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
        ),
        "ppt/_rels/presentation.xml.rels": _relationships(
            [("rIdMaster", "slideMaster", "slideMasters/slideMaster1.xml")]
            + [
                (f"rIdSlide{index}", "slide", f"slides/slide{index}.xml")
                for index in range(1, count + 1)
            ]
            + [
                ("rIdTheme", "theme", "theme/theme1.xml"),
                ("rIdPresProps", "presProps", "presProps.xml"),
                ("rIdViewProps", "viewProps", "viewProps.xml"),
                ("rIdTableStyles", "tableStyles", "tableStyles.xml"),
            ]
        ),
        "ppt/presProps.xml": f"{_XML_HEADER}<p:presentationPr {_NAMESPACES}/>",
        "ppt/viewProps.xml": f"{_XML_HEADER}<p:viewPr {_NAMESPACES}/>",
        "ppt/tableStyles.xml": (
            f'{_XML_HEADER}<a:tblStyleLst xmlns:a="{_DRAWING}" '
            'def="{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"/>'
        ),
        "ppt/slideMasters/slideMaster1.xml": _master_xml(),
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": _relationships(
            [
                ("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"),
                ("rId2", "slideLayout", "../slideLayouts/slideLayout2.xml"),
                ("rId3", "theme", "../theme/theme1.xml"),
            ]
        ),
        "ppt/slideLayouts/slideLayout1.xml": _layout_xml("title"),
        "ppt/slideLayouts/slideLayout2.xml": _layout_xml("content"),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": _relationships(
            [("rId1", "slideMaster", "../slideMasters/slideMaster1.xml")]
        ),
        "ppt/slideLayouts/_rels/slideLayout2.xml.rels": _relationships(
            [("rId1", "slideMaster", "../slideMasters/slideMaster1.xml")]
        ),
        "ppt/theme/theme1.xml": _theme_xml(),
    }
    for index, slide in enumerate(slides, start=1):
        layout = 1 if slide.kind in {"title", "section"} else 2
        files[f"ppt/slides/slide{index}.xml"] = _slide_xml(slide)
        files[f"ppt/slides/_rels/slide{index}.xml.rels"] = _relationships(
            [("rId1", "slideLayout", f"../slideLayouts/slideLayout{layout}.xml")]
        )
    return _zip(files)
