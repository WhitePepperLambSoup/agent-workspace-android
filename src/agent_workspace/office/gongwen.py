# ruff: noqa: RUF001, RUF002, E501 -- the layout rules are written in Chinese, as GB/T 9704 states them.
"""Official documents (党政机关公文) laid out to GB/T 9704-2012, and existing ones checked and
corrected against it.

Page: A4, margins top 37 mm, bottom 35 mm, left 28 mm, right 26 mm (版心 156 × 225 mm); body in
三号仿宋 (16 pt), 22 lines of 28 characters; title in 二号小标宋 (22 pt); levels 一、（黑体）
（一）（楷体）1.（仿宋）（1）（仿宋）; page numbers 四号 "— 1 —", right on odd pages and left on
even ones, one character in from the edge; 成文日期 in Arabic numerals, four characters in from
the right; 版记 (抄送, 印发机关和印发日期) between lines at the end.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET

from agent_workspace.office import proofread
from agent_workspace.office.ooxml import (
    OfficeError,
    Package,
    W,
    content_types,
    escape_attr,
    escape_text,
    q,
    relationships,
    zip_parts,
)
from agent_workspace.office.word import DOCUMENT, body_paragraphs, open_docx, read_paragraph

FANGSONG = "仿宋_GB2312"
KAITI = "楷体_GB2312"
HEITI = "黑体"
XIAOBIAOSONG = "方正小标宋简体"
SONGTI = "宋体"
# Fonts Word may lack on a computer; it falls back to the alternative.
_ALTERNATIVES = {
    FANGSONG: "仿宋",
    KAITI: "楷体",
    XIAOBIAOSONG: "宋体",
    HEITI: "SimHei",
    SONGTI: "SimSun",
}
BODY_SIZE = 32  # half-points: 三号 16 pt
TITLE_SIZE = 44  # 二号 22 pt
NOTE_SIZE = 28  # 四号 14 pt
LINE = 579  # twips: 225 mm / 22 lines
MARGINS = {"top": 2098, "bottom": 1984, "left": 1588, "right": 1474}  # 37, 35, 28, 26 mm
PAGE = (11906, 16838)  # A4
_MM = 56.7  # twips per millimetre

_WORD_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml"
_NS = f'xmlns:w="{W}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
LEVELS = (
    (re.compile(r"^[一二三四五六七八九十]+、"), 1),
    (re.compile(r"^（[一二三四五六七八九十]+）"), 2),
    (re.compile(r"^\d{1,2}\.(?!\d)"), 3),
    (re.compile(r"^（\d{1,2}）"), 4),
)
LEVEL_FONTS = {1: HEITI, 2: KAITI, 3: FANGSONG, 4: FANGSONG}


def level_of(text: str) -> int:
    for pattern, level in LEVELS:
        if pattern.match(text.strip()):
            return level
    return 0


# ---- building ------------------------------------------------------------------------------------


def _run(
    text: str, font: str = FANGSONG, size: int = BODY_SIZE, bold: bool = False, color: str = ""
) -> str:
    properties = (
        f'<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="{font}" w:hint="eastAsia"/>'
        + ("<w:b/>" if bold else "")
        + (f'<w:color w:val="{color}"/>' if color else "")
        + f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    )
    return (
        f'<w:r><w:rPr>{properties}</w:rPr><w:t xml:space="preserve">{escape_text(text)}</w:t></w:r>'
    )


def _paragraph(
    runs: str,
    *,
    align: str = "both",
    first_chars: int = 0,
    left_chars: int = 0,
    right_chars: int = 0,
    line: int = LINE,
    border: str = "",
    tabs: str = "",
    keep_next: bool = False,
) -> str:
    indent = ""
    if first_chars or left_chars or right_chars:
        indent = (
            "<w:ind"
            + (f' w:firstLineChars="{first_chars * 100}"' if first_chars else "")
            + (f' w:leftChars="{left_chars * 100}"' if left_chars else "")
            + (f' w:rightChars="{right_chars * 100}"' if right_chars else "")
            + "/>"
        )
    properties = (
        ("<w:keepNext/>" if keep_next else "")
        + (f"<w:pBdr>{border}</w:pBdr>" if border else "")
        + (f"<w:tabs>{tabs}</w:tabs>" if tabs else "")
        + f'<w:spacing w:before="0" w:after="0" w:line="{line}" w:lineRule="exact"/>'
        + indent
        + f'<w:jc w:val="{align}"/>'
    )
    return f"<w:p><w:pPr>{properties}</w:pPr>{runs}</w:p>"


def _blank(count: int = 1) -> str:
    return "".join(_paragraph("") for _ in range(count))


def body_paragraph(text: str) -> str:
    """A line of the body: levels 1 and 2 in 黑体/楷体 up to their first 。, the rest 仿宋."""
    stripped = text.strip()
    level = level_of(stripped)
    if level in {1, 2}:
        end = stripped.find("。")
        head, tail = (stripped, "") if end < 0 else (stripped[: end + 1], stripped[end + 1 :])
        runs = _run(head, LEVEL_FONTS[level]) + (_run(tail) if tail else "")
    else:
        runs = _run(stripped)
    return _paragraph(runs, first_chars=2)


@dataclass
class Document:
    """What an official document says; empty fields are left out of the layout."""

    title: str
    body: str = ""
    kind: str = "文件"  # 文件 (red header), 纪要, 普通 (no header)
    organ: str = ""
    organ_mark: str = ""
    number: str = ""
    signer: str = ""
    copy_number: str = ""
    secret: str = ""
    urgency: str = ""
    recipients: str = ""
    attachments: list[str] = field(default_factory=list)
    signature: str = ""
    date: str = ""
    note: str = ""
    cc: str = ""
    printer: str = ""
    print_date: str = ""
    attendees: str = ""
    absent: str = ""
    observers: str = ""
    mark_size: int = 52  # half-points of 发文机关标志

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> Document:
        known = {name for name in cls.__dataclass_fields__}
        data = {
            key: value
            for key, value in values.items()
            if key in known and value not in (None, "", [])
        }
        if "attachments" in data and isinstance(data["attachments"], str):
            data["attachments"] = [
                line for line in data["attachments"].splitlines() if line.strip()
            ]
        # Models often send the body (and names) as a list of paragraphs: one per line.
        for key, value in list(data.items()):
            if key == "attachments":
                data[key] = (
                    [str(item).strip() for item in value if str(item).strip()]
                    if isinstance(value, list)
                    else value
                )
            elif isinstance(value, list):
                separator = (
                    "、"
                    if key in {"attendees", "absent", "observers"}
                    else "，"
                    if key in {"recipients", "cc"}
                    else "\n"
                )
                data[key] = separator.join(str(item).strip() for item in value if str(item).strip())
            elif not isinstance(value, str) and key != "mark_size":
                data[key] = str(value)
        if not str(data.get("title", "")).strip():
            raise OfficeError("an official document needs a title")
        return cls(**data)


def _header(doc: Document) -> str:
    out = []
    corner = [value for value in (doc.copy_number, doc.secret, doc.urgency) if value]
    for value in corner:
        out.append(_paragraph(_run(value, HEITI), align="left"))
    if doc.kind == "普通":
        return "".join(out)
    mark = doc.organ_mark or (
        f"{doc.organ}会议纪要" if doc.kind == "纪要" else f"{doc.organ}文件" if doc.organ else ""
    )
    if mark:
        if not corner:
            out.append(_blank(1))
        out.append(
            _paragraph(
                _run(mark, XIAOBIAOSONG, doc.mark_size, color="FF0000"),
                align="center",
                line=int(doc.mark_size * 20 * 1.3),
            )
        )
        out.append(_blank(2))
    red_line = '<w:bottom w:val="single" w:sz="12" w:space="6" w:color="FF0000"/>'
    if doc.number and doc.signer:
        # 上行文: 发文字号 left, 签发人 right, on one line.
        width = PAGE[0] - MARGINS["left"] - MARGINS["right"] - 320
        tabs = f'<w:tab w:val="right" w:pos="{width}"/>'
        runs = _run(doc.number) + "<w:r><w:tab/></w:r>" + _run("签发人：") + _run(doc.signer, KAITI)
        out.append(_paragraph(runs, align="left", left_chars=1, border=red_line, tabs=tabs))
    elif doc.number:
        out.append(_paragraph(_run(doc.number), align="center", border=red_line))
    else:
        out.append(_paragraph("", border=red_line))
    out.append(_blank(2))
    return "".join(out)


def _closing(doc: Document) -> str:
    out = []
    if doc.attachments:
        out.append(_blank(1))
        for index, name in enumerate(doc.attachments, start=1):
            label = f"{index}. {name}" if len(doc.attachments) > 1 else name
            if index == 1:
                out.append(_paragraph(_run("附件：" + label), align="left", first_chars=2))
            else:
                out.append(_paragraph(_run(label), align="left", left_chars=5))
    if doc.kind == "纪要":
        lines = [("出席：", doc.attendees), ("请假：", doc.absent), ("列席：", doc.observers)]
        lines = [(label, value) for label, value in lines if value]
        if lines:
            out.append(_blank(1))
            for label, value in lines:
                out.append(
                    _paragraph(_run(label, HEITI) + _run(value), align="left", first_chars=2)
                )
    signature = doc.signature or (doc.organ if doc.kind != "纪要" else "")
    if signature or doc.date:
        out.append(_blank(2 if not doc.attachments else 1))
        date_length = len(doc.date) or len(signature)
        if signature:
            offset = 4 + max(0, (date_length - len(signature)) // 2)
            out.append(_paragraph(_run(signature), align="right", right_chars=offset))
        if doc.date:
            out.append(_paragraph(_run(doc.date), align="right", right_chars=4))
    if doc.note:
        note = doc.note if doc.note.startswith("（") else f"（{doc.note}）"
        out.append(_paragraph(_run(note), align="left", first_chars=2))
    if doc.cc or doc.printer or doc.print_date:
        out.append(_blank(2))
        thick = '<w:top w:val="single" w:sz="8" w:space="1" w:color="000000"/>'
        thin = '<w:bottom w:val="single" w:sz="6" w:space="1" w:color="000000"/>'
        last = '<w:bottom w:val="single" w:sz="8" w:space="1" w:color="000000"/>'
        if doc.cc:
            text = doc.cc if doc.cc.endswith("。") else doc.cc + "。"
            out.append(
                _paragraph(
                    _run("抄送：" + text, size=NOTE_SIZE),
                    align="left",
                    left_chars=1,
                    right_chars=1,
                    border=thick + thin,
                )
            )
        if doc.printer or doc.print_date:
            width = PAGE[0] - MARGINS["left"] - MARGINS["right"] - 320
            tabs = f'<w:tab w:val="right" w:pos="{width}"/>'
            runs = (
                _run(doc.printer, size=NOTE_SIZE)
                + "<w:r><w:tab/></w:r>"
                + _run(doc.print_date, size=NOTE_SIZE)
            )
            top = "" if doc.cc else thick
            out.append(_paragraph(runs, align="left", left_chars=1, border=top + last, tabs=tabs))
    return "".join(out)


def _section() -> str:
    return (
        '<w:sectPr><w:footerReference w:type="default" r:id="rIdFooterOdd"/>'
        '<w:footerReference w:type="even" r:id="rIdFooterEven"/>'
        f'<w:pgSz w:w="{PAGE[0]}" w:h="{PAGE[1]}"/>'
        f'<w:pgMar w:top="{MARGINS["top"]}" w:right="{MARGINS["right"]}" w:bottom="{MARGINS["bottom"]}" '
        f'w:left="{MARGINS["left"]}" w:header="851" w:footer="1304" w:gutter="0"/>'
        f'<w:docGrid w:type="linesAndChars" w:linePitch="{LINE}" w:charSpace="-849"/></w:sectPr>'
    )


def footer(odd: bool) -> str:
    """Page numbers: "— 1 —" in 四号宋体, one character in from the outer edge."""
    side = 'w:rightChars="100"' if odd else 'w:leftChars="100"'
    run_properties = (
        f'<w:rFonts w:ascii="{SONGTI}" w:hAnsi="{SONGTI}" w:eastAsia="{SONGTI}"/>'
        f'<w:sz w:val="{NOTE_SIZE}"/><w:szCs w:val="{NOTE_SIZE}"/>'
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:ftr {_NS}><w:p><w:pPr>'
        f'<w:jc w:val="{"right" if odd else "left"}"/><w:ind {side}/></w:pPr>'
        f'<w:r><w:rPr>{run_properties}</w:rPr><w:t xml:space="preserve">— </w:t></w:r>'
        f'<w:r><w:rPr>{run_properties}</w:rPr><w:fldChar w:fldCharType="begin"/></w:r>'
        f'<w:r><w:rPr>{run_properties}</w:rPr><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
        f'<w:r><w:rPr>{run_properties}</w:rPr><w:fldChar w:fldCharType="separate"/></w:r>'
        f"<w:r><w:rPr>{run_properties}</w:rPr><w:t>1</w:t></w:r>"
        f'<w:r><w:rPr>{run_properties}</w:rPr><w:fldChar w:fldCharType="end"/></w:r>'
        f'<w:r><w:rPr>{run_properties}</w:rPr><w:t xml:space="preserve"> —</w:t></w:r></w:p></w:ftr>'
    )


def _styles() -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:styles {_NS}>'
        "<w:docDefaults><w:rPrDefault><w:rPr>"
        f'<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="{FANGSONG}" w:cs="Times New Roman"/>'
        f'<w:kern w:val="2"/><w:sz w:val="{BODY_SIZE}"/><w:szCs w:val="{BODY_SIZE}"/><w:lang w:val="en-US" w:eastAsia="zh-CN"/>'
        "</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>"
        f'<w:spacing w:before="0" w:after="0" w:line="{LINE}" w:lineRule="exact"/><w:jc w:val="both"/>'
        "</w:pPr></w:pPrDefault></w:docDefaults>"
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
        '<w:style w:type="character" w:default="1" w:styleId="DefaultParagraphFont"><w:name w:val="Default Paragraph Font"/><w:uiPriority w:val="1"/><w:semiHidden/></w:style>'
        '<w:style w:type="paragraph" w:styleId="CommentText"><w:name w:val="annotation text"/><w:basedOn w:val="Normal"/></w:style>'
        '<w:style w:type="character" w:styleId="CommentReference"><w:name w:val="annotation reference"/><w:rPr><w:sz w:val="18"/></w:rPr></w:style>'
        "</w:styles>"
    )


def _font_table() -> str:
    fonts = "".join(
        f'<w:font w:name="{escape_attr(name)}"><w:altName w:val="{escape_attr(alternative)}"/><w:charset w:val="86"/></w:font>'
        for name, alternative in _ALTERNATIVES.items()
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:fonts {_NS}>{fonts}</w:fonts>'
    )


def _settings() -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:settings {_NS}>'
        '<w:evenAndOddHeaders/><w:defaultTabStop w:val="420"/><w:characterSpacingControl w:val="compressPunctuation"/>'
        '<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>'
        "</w:settings>"
    )


def build(doc: Document) -> bytes:
    """A .docx of the document, laid out to GB/T 9704."""
    body = [_header(doc)]
    title_lines = [line for line in doc.title.split("\n") if line.strip()]
    for line in title_lines:
        body.append(
            _paragraph(
                _run(line.strip(), XIAOBIAOSONG, TITLE_SIZE), align="center", line=int(LINE * 1.2)
            )
        )
    body.append(_blank(1))
    if doc.recipients:
        recipients = doc.recipients.rstrip("：:") + "："
        body.append(_paragraph(_run(recipients), align="left"))
    for line in doc.body.splitlines():
        if line.strip():
            body.append(body_paragraph(line))
    body.append(_closing(doc))
    document = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {_NS}><w:body>'
        f"{''.join(body)}{_section()}</w:body></w:document>"
    )
    main = f"{_WORD_TYPE}.document.main+xml"
    return zip_parts(
        [
            (
                "[Content_Types].xml",
                content_types(
                    {},
                    {
                        "word/document.xml": main,
                        "word/styles.xml": f"{_WORD_TYPE}.styles+xml",
                        "word/settings.xml": f"{_WORD_TYPE}.settings+xml",
                        "word/fontTable.xml": f"{_WORD_TYPE}.fontTable+xml",
                        "word/footer1.xml": f"{_WORD_TYPE}.footer+xml",
                        "word/footer2.xml": f"{_WORD_TYPE}.footer+xml",
                    },
                ),
            ),
            ("_rels/.rels", relationships([("rId1", "officeDocument", "word/document.xml")])),
            (
                "word/_rels/document.xml.rels",
                relationships(
                    [
                        ("rIdStyles", "styles", "styles.xml"),
                        ("rIdSettings", "settings", "settings.xml"),
                        ("rIdFonts", "fontTable", "fontTable.xml"),
                        ("rIdFooterOdd", "footer", "footer1.xml"),
                        ("rIdFooterEven", "footer", "footer2.xml"),
                    ]
                ),
            ),
            ("word/document.xml", document),
            ("word/styles.xml", _styles()),
            ("word/settings.xml", _settings()),
            ("word/fontTable.xml", _font_table()),
            ("word/footer1.xml", footer(True)),
            ("word/footer2.xml", footer(False)),
        ]
    )


# ---- checking ------------------------------------------------------------------------------------


@dataclass
class Issue:
    where: str
    problem: str
    expected: str
    found: str = ""

    def as_dict(self) -> dict[str, str]:
        return {key: value for key, value in self.__dict__.items() if value}


class _Styles:
    """Font and size a run ends up with: run, paragraph style chain, document defaults."""

    def __init__(self, package: Package) -> None:
        self.styles: dict[str, ET.Element] = {}
        self.defaults = ET.Element("none")
        if package.has("word/styles.xml"):
            root = package.xml("word/styles.xml").root
            for style in root.iter(q(W, "style")):
                self.styles[style.get(q(W, "styleId"), "")] = style
            found = root.find(f"{q(W, 'docDefaults')}/{q(W, 'rPrDefault')}/{q(W, 'rPr')}")
            if found is not None:
                self.defaults = found
            for style in self.styles.values():
                if style.get(q(W, "default")) == "1" and style.get(q(W, "type")) == "paragraph":
                    self.normal = style.get(q(W, "styleId"), "")
        self.normal = getattr(self, "normal", "Normal")

    def _chain(self, style_id: str) -> list[ET.Element]:
        out = []
        seen = set()
        while style_id and style_id not in seen and style_id in self.styles:
            seen.add(style_id)
            style = self.styles[style_id]
            properties = style.find(q(W, "rPr"))
            if properties is not None:
                out.append(properties)
            based = style.find(q(W, "basedOn"))
            style_id = based.get(q(W, "val"), "") if based is not None else ""
        return out

    def resolve(self, paragraph: ET.Element, run: ET.Element) -> tuple[str, int]:
        chain: list[ET.Element] = []
        own = run.find(q(W, "rPr"))
        if own is not None:
            chain.append(own)
        style = paragraph.find(f"{q(W, 'pPr')}/{q(W, 'pStyle')}")
        chain.extend(self._chain(style.get(q(W, "val"), "") if style is not None else self.normal))
        chain.append(self.defaults)
        font, size = "", 0
        for properties in chain:
            fonts = properties.find(q(W, "rFonts"))
            if not font and fonts is not None:
                font = fonts.get(q(W, "eastAsia")) or (
                    "主题字体" if fonts.get(q(W, "eastAsiaTheme")) else ""
                )
            element = properties.find(q(W, "sz"))
            if not size and element is not None and (element.get(q(W, "val")) or "").isdigit():
                size = int(element.get(q(W, "val"), "0"))
        return font or "（默认）", size or 21


def _font_ok(found: str, wanted: str) -> bool:
    names = {wanted, _ALTERNATIVES.get(wanted, wanted)}
    if wanted == FANGSONG:
        names |= {"仿宋", "FangSong", "仿宋_GB2312"}
    elif wanted == KAITI:
        names |= {"楷体", "KaiTi", "楷体_GB2312"}
    elif wanted == HEITI:
        names |= {"黑体", "SimHei"}
    elif wanted == XIAOBIAOSONG:
        names |= {"方正小标宋简体", "方正小标宋_GBK", "小标宋", "FZXiaoBiaoSong-B05S"}
    return found in names


def _roles(texts: list[str], centers: list[bool], sizes: list[int]) -> list[str]:
    """title, recipients, level1-4, body, signature, date, blank — by text and position."""
    roles = _roles_from(texts, centers, sizes, None)
    if "title" not in roles:
        # No centred title: the first short line that names the document is the title.
        first = next(
            (
                index
                for index, text in enumerate(texts)
                if text.strip()
                and len(text.strip()) <= 60
                and not re.search(r"〔\d{4}〕|文件$", text.strip())
            ),
            None,
        )
        roles = _roles_from(texts, centers, sizes, first)
    return roles


def _roles_from(
    texts: list[str], centers: list[bool], sizes: list[int], title_at: int | None
) -> list[str]:
    roles: list[str] = []
    title_seen = False
    for index, text in enumerate(texts):
        stripped = text.strip()
        if not stripped:
            roles.append("blank")
        elif not title_seen and (
            index == title_at
            or (
                title_at is None
                and centers[index]
                and (
                    sizes[index] >= 36
                    or re.search(r"关于|通知|报告|请示|函|纪要|决定|意见|方案", stripped)
                )
                and not re.search(r"〔\d{4}〕|文件$", stripped)
            )
        ):
            roles.append("title")
            title_seen = True
        elif not title_seen:
            roles.append("header")
        elif re.fullmatch(r"(19|20)\d\d年\d{1,2}月\d{1,2}日", stripped) or re.fullmatch(
            r"[〇零一二三四五六七八九]{4}年[一二三四五六七八九十]{1,2}月[一二三四五六七八九十]{1,3}日",
            stripped,
        ):
            roles.append("date")
        elif (
            stripped.endswith(("：", ":"))
            and len(stripped) < 60
            and index > 0
            and "title" in roles
            and roles[-1] in {"title", "blank"}
        ):
            roles.append("recipients")
        elif stripped.startswith(("抄送", "附件")) or stripped.endswith("印发"):
            roles.append("other")
        elif level_of(stripped):
            roles.append(f"level{level_of(stripped)}")
        else:
            roles.append("body")
    # A short line just above the date is the 署名.
    for index, role in enumerate(roles):
        if (
            role == "date"
            and index > 0
            and roles[index - 1] == "body"
            and len(texts[index - 1].strip()) < 30
        ):
            roles[index - 1] = "signature"
    return roles


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)


def _layout(package: Package) -> tuple[list[Any], list[str], list[str], list[int], list[str]]:
    """Body paragraphs with their text, first run's font and size, and role."""
    styles = _Styles(package)
    paragraph_list = body_paragraphs(package)
    texts = [paragraph.text for paragraph in paragraph_list]
    centers, sizes, fonts = [], [], []
    for paragraph in paragraph_list:
        jc = paragraph.element.find(f"{q(W, 'pPr')}/{q(W, 'jc')}")
        centers.append(jc is not None and jc.get(q(W, "val")) == "center")
        run = next((piece.run for piece in paragraph.pieces), None)
        font, size = styles.resolve(paragraph.element, run) if run is not None else ("", 0)
        fonts.append(font)
        sizes.append(size)
    return paragraph_list, texts, fonts, sizes, _roles(texts, centers, sizes)


def check(data: bytes) -> Report:
    package = open_docx(data)
    report = Report()
    root = package.xml(DOCUMENT).root
    section = root.find(f"{q(W, 'body')}/{q(W, 'sectPr')}")
    if section is not None:
        size = section.find(q(W, "pgSz"))
        if size is not None:
            width, height = int(size.get(q(W, "w"), "0") or 0), int(size.get(q(W, "h"), "0") or 0)
            if abs(width - PAGE[0]) > 60 or abs(height - PAGE[1]) > 60:
                report.issues.append(
                    Issue(
                        "页面",
                        "纸张不是 A4",
                        "210 × 297 mm",
                        f"{width / _MM:.0f} × {height / _MM:.0f} mm",
                    )
                )
        margins = section.find(q(W, "pgMar"))
        if margins is not None:
            labels = {"top": "上（天头）", "bottom": "下", "left": "左（订口）", "right": "右"}
            for side, wanted in MARGINS.items():
                value = margins.get(q(W, side), "0") or "0"
                found = abs(int(value)) if value.lstrip("-").isdigit() else 0
                if abs(found - wanted) > 2 * _MM:
                    report.issues.append(
                        Issue(
                            "页边距",
                            f"{labels[side]}边距不符",
                            f"{wanted / _MM:.0f} mm",
                            f"{found / _MM:.0f} mm",
                        )
                    )
    footers = [rid for rid, kind, _ in package.relationships(DOCUMENT) if kind.endswith("/footer")]
    if not footers:
        report.issues.append(
            Issue("页码", "没有页码", "四号宋体“— 1 —”，单页居右、双页居左各空一字")
        )
    paragraph_list, texts, fonts, sizes, roles = _layout(package)
    report.roles = roles
    expected = {
        "title": (XIAOBIAOSONG, TITLE_SIZE, "二号方正小标宋简体"),
        "body": (FANGSONG, BODY_SIZE, "三号仿宋_GB2312"),
        "recipients": (FANGSONG, BODY_SIZE, "三号仿宋_GB2312"),
        "level1": (HEITI, BODY_SIZE, "三号黑体"),
        "level2": (KAITI, BODY_SIZE, "三号楷体_GB2312"),
        "level3": (FANGSONG, BODY_SIZE, "三号仿宋_GB2312"),
        "level4": (FANGSONG, BODY_SIZE, "三号仿宋_GB2312"),
        "signature": (FANGSONG, BODY_SIZE, "三号仿宋_GB2312"),
        "date": (FANGSONG, BODY_SIZE, "三号仿宋_GB2312"),
    }
    for index, (role, text) in enumerate(zip(roles, texts, strict=True)):
        where = f"第 {index + 1} 段“{text.strip()[:16]}”"
        if role in expected:
            font, points, label = expected[role]
            if not _font_ok(fonts[index], font) or sizes[index] != points:
                report.issues.append(
                    Issue(where, "字体或字号不符", label, f"{fonts[index]} {sizes[index] / 2:g} 磅")
                )
            spacing = paragraph_list[index].element.find(f"{q(W, 'pPr')}/{q(W, 'spacing')}")
            if role != "title" and spacing is not None and spacing.get(q(W, "lineRule")) == "exact":
                exact = int(spacing.get(q(W, "line"), "0") or 0)
                if abs(exact - LINE) > 30:
                    report.issues.append(
                        Issue(
                            where,
                            "行距不符",
                            "固定值约 28.95 磅（每页 22 行）",
                            f"{exact / 20:g} 磅",
                        )
                    )
        if role == "date" and not re.fullmatch(r"(19|20)\d\d年\d{1,2}月\d{1,2}日", text.strip()):
            report.issues.append(
                Issue(where, "成文日期应使用阿拉伯数字", "2026年10月28日", text.strip())
            )
    for finding in proofread.check_paragraphs(texts, ["serial", "document_number", "numbers"]):
        report.issues.append(
            Issue(f"第 {finding.paragraph} 段", finding.reason, finding.suggestion, finding.text)
        )
    return report


# ---- fixing --------------------------------------------------------------------------------------


def _set_run_format(run: ET.Element, font: str, size: int, bold: bool | None = None) -> None:
    properties = run.find(q(W, "rPr"))
    if properties is None:
        properties = ET.Element(q(W, "rPr"))
        run.insert(0, properties)
    fonts = properties.find(q(W, "rFonts"))
    if fonts is None:
        fonts = ET.Element(q(W, "rFonts"))
        properties.insert(0, fonts)
    for attribute in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        fonts.attrib.pop(q(W, attribute), None)
    fonts.set(q(W, "eastAsia"), font)
    fonts.set(q(W, "ascii"), "Times New Roman")
    fonts.set(q(W, "hAnsi"), "Times New Roman")
    for name in ("sz", "szCs"):
        element = properties.find(q(W, name))
        if element is None:
            element = ET.SubElement(properties, q(W, name))
        element.set(q(W, "val"), str(size))
    if bold is not None:
        existing = properties.find(q(W, "b"))
        if bold and existing is None:
            ET.SubElement(properties, q(W, "b"))
        elif not bold and existing is not None:
            properties.remove(existing)


def _paragraph_properties(paragraph: ET.Element) -> ET.Element:
    properties = paragraph.find(q(W, "pPr"))
    if properties is None:
        properties = ET.Element(q(W, "pPr"))
        paragraph.insert(0, properties)
    return properties


def _set_child(properties: ET.Element, name: str, attributes: dict[str, str]) -> None:
    element = properties.find(q(W, name))
    if element is None:
        element = ET.SubElement(properties, q(W, name))
    element.attrib.clear()
    for key, value in attributes.items():
        element.set(q(W, key), value)


def fix(data: bytes) -> tuple[bytes, list[str]]:
    """A copy laid out to the standard: page, fonts and sizes by role, line spacing, indents,
    page numbers, and the numbering, 发文字号 and date fixes of the text."""
    package = open_docx(data)
    done: list[str] = []
    root = package.xml(DOCUMENT).root
    body = root.find(q(W, "body"))
    if body is None:
        raise OfficeError("the document has no body")
    section = body.find(q(W, "sectPr"))
    if section is None:
        section = ET.SubElement(body, q(W, "sectPr"))
    _set_child(section, "pgSz", {"w": str(PAGE[0]), "h": str(PAGE[1])})
    _set_child(
        section,
        "pgMar",
        {
            **{side: str(value) for side, value in MARGINS.items()},
            "header": "851",
            "footer": "1304",
            "gutter": "0",
        },
    )
    _set_child(
        section, "docGrid", {"type": "linesAndChars", "linePitch": str(LINE), "charSpace": "-849"}
    )
    done.append("页面设为 A4，页边距上 37、下 35、左 28、右 26 mm，每页 22 行、每行 28 字")
    # Text first (numbering, 发文字号, dates), so the roles are read from the corrected text.
    paragraph_list, texts, _fonts, _sizes, roles = _layout(package)
    replacements = 0
    for paragraph_index, finding in _text_fixes(texts):
        paragraph = read_paragraph(DOCUMENT, paragraph_list[paragraph_index].element)
        if _replace_text(paragraph, finding.start, finding.end, finding.suggestion):
            replacements += 1
    for paragraph, role in zip(paragraph_list, roles, strict=True):
        current = read_paragraph(DOCUMENT, paragraph.element)
        converted = arabic_date(current.text) if role == "date" else None
        if converted and _replace_text(current, 0, len(current.text), converted):
            replacements += 1
    if replacements:
        done.append(f"改正了 {replacements} 处序号、发文字号或日期的写法")
    paragraph_list, texts, _fonts, _sizes, roles = _layout(package)
    formats = {
        "title": (XIAOBIAOSONG, TITLE_SIZE),
        "level1": (HEITI, BODY_SIZE),
        "level2": (KAITI, BODY_SIZE),
    }
    counted: dict[str, int] = {}
    for paragraph, role, text in zip(paragraph_list, roles, texts, strict=True):
        if role in {"blank", "header", "other"}:
            continue
        font, size = formats.get(role, (FANGSONG, BODY_SIZE))
        heading_end = len(text)
        if role in {"level1", "level2"} and "。" in text:
            heading_end = text.find("。") + 1
        for piece in paragraph.pieces:
            if role in {"level1", "level2"} and piece.start >= heading_end:
                _set_run_format(piece.run, FANGSONG, BODY_SIZE)
            else:
                _set_run_format(piece.run, font, size)
        properties = _paragraph_properties(paragraph.element)
        if role == "title":
            _set_child(properties, "jc", {"val": "center"})
            _set_child(
                properties,
                "spacing",
                {"before": "0", "after": "0", "line": str(int(LINE * 1.2)), "lineRule": "exact"},
            )
        else:
            _set_child(
                properties,
                "spacing",
                {"before": "0", "after": "0", "line": str(LINE), "lineRule": "exact"},
            )
            if role in {"body", "level1", "level2", "level3", "level4"}:
                _set_child(properties, "ind", {"firstLineChars": "200", "firstLine": "640"})
            if role == "date":
                _set_child(properties, "jc", {"val": "right"})
                _set_child(properties, "ind", {"rightChars": "400", "right": "1280"})
        counted[role] = counted.get(role, 0) + 1
    if counted:
        done.append("按标题、正文和各级层次设置了字体字号、行距和缩进")
    if not [rid for rid, kind, _ in package.relationships(DOCUMENT) if kind.endswith("/footer")]:
        _add_page_numbers(package, section)
        done.append("加了页码（四号宋体“— 1 —”，单页居右、双页居左）")
    return package.to_bytes(), done


_DIGITS = {
    "〇": 0,
    "零": 0,
    "○": 0,
    "Ｏ": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _small_number(text: str) -> int | None:
    """一 … 三十一 as a number."""
    if not text:
        return None
    if "十" not in text:
        return _DIGITS.get(text) if len(text) == 1 else None
    tens, _, ones = text.partition("十")
    value = (_DIGITS.get(tens, -100) if tens else 1) * 10 + (_DIGITS.get(ones, -100) if ones else 0)
    return value if value > 0 else None


def arabic_date(text: str) -> str | None:
    """二〇二六年十月二十八日 → 2026年10月28日; None when it is not such a date."""
    match = re.fullmatch(
        r"\s*([〇零○Ｏ一二三四五六七八九]{4})年([一二三四五六七八九十]{1,3})月([一二三四五六七八九十]{1,3})日\s*",
        text,
    )
    if not match:
        return None
    year = "".join(str(_DIGITS[char]) for char in match.group(1))
    month, day = _small_number(match.group(2)), _small_number(match.group(3))
    if month is None or day is None or not 1 <= month <= 12 or not 1 <= day <= 31:
        return None
    return f"{year}年{month}月{day}日"


def _text_fixes(texts: list[str]) -> list[tuple[int, proofread.Finding]]:
    out = []
    for finding in proofread.check_paragraphs(texts, ["serial", "document_number", "numbers"]):
        if (
            finding.rule in {"serial", "document_number", "date", "full_width_digits"}
            and finding.suggestion
        ):
            out.append((finding.paragraph - 1, finding))
    # Later spans first, so earlier offsets stay right.
    out.sort(key=lambda item: (item[0], -item[1].start))
    return out


def _replace_text(paragraph: Any, start: int, end: int, replacement: str) -> bool:
    """Replace [start, end) inside the paragraph's runs, keeping the first run's format."""
    pieces = [piece for piece in paragraph.pieces if piece.end > start and piece.start < end]
    if not pieces or any(piece.child.tag != q(W, "t") for piece in pieces):
        return False
    first = pieces[0]
    for index, piece in enumerate(pieces):
        value = piece.child.text or ""
        local_start = max(0, start - piece.start)
        local_end = min(len(value), end - piece.start)
        inserted = replacement if index == 0 else ""
        piece.child.text = value[:local_start] + inserted + value[local_end:]
        piece.child.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return first is not None


def _add_page_numbers(package: Package, section: ET.Element) -> None:
    number = 1
    while package.has(f"word/footer{number}.xml"):
        number += 1
    odd_name, even_name = f"footer{number}.xml", f"footer{number + 1}.xml"
    package.set(f"word/{odd_name}", footer(True))
    package.set(f"word/{even_name}", footer(False))
    for name in (odd_name, even_name):
        package.content_type(f"word/{name}", f"{_WORD_TYPE}.footer+xml")
    odd = package.add_relationship(DOCUMENT, "footer", odd_name)
    even = package.add_relationship(DOCUMENT, "footer", even_name)
    relationship = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    for kind, rid in (("even", even), ("default", odd)):
        reference = ET.Element(q(W, "footerReference"), {q(W, "type"): kind, relationship: rid})
        section.insert(0, reference)
    if package.has("word/settings.xml"):
        settings = package.xml("word/settings.xml").root
        if settings.find(q(W, "evenAndOddHeaders")) is None:
            settings.insert(0, ET.Element(q(W, "evenAndOddHeaders")))


__all__ = [
    "BODY_SIZE",
    "Document",
    "Issue",
    "Report",
    "body_paragraph",
    "build",
    "check",
    "fix",
    "footer",
    "level_of",
]
