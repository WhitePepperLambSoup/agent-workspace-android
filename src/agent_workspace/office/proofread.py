# ruff: noqa: RUF001, RUF002 -- the rules are about Chinese punctuation.
"""Mechanical checks of Chinese text: punctuation in Chinese context, paired brackets and quotes,
doubled characters and punctuation, numbers and dates, the numbering of official documents
(一、 （一） 1. （1）) and a list of commonly miswritten words.

Each finding names the paragraph, the text, a suggestion when one is certain, and why. Meaning
(的地得, word choice, consistency of names and figures) is left to the model reading the text.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

_HAN = r"㐀-鿿豈-﫿"
_CJK_CONTEXT = rf"[{_HAN}，。；：？！、“”‘’（）《》]"

# Common miswritings: (wrong, right). Only unambiguous ones.
TYPOS: tuple[tuple[str, str], ...] = (
    ("以经", "已经"),
    ("在接再厉", "再接再厉"),
    ("再接再励", "再接再厉"),
    ("迫不急待", "迫不及待"),
    ("不径而走", "不胫而走"),
    ("一愁莫展", "一筹莫展"),
    ("按步就班", "按部就班"),
    ("变本加利", "变本加厉"),
    ("别出新裁", "别出心裁"),
    ("病入膏肓", "病入膏肓"),
    ("出奇不意", "出其不意"),
    ("穿流不息", "川流不息"),
    ("鼎立相助", "鼎力相助"),
    ("发挥极至", "发挥极致"),
    ("负隅顽抗", "负隅顽抗"),
    ("甘败下风", "甘拜下风"),
    ("功亏一匮", "功亏一篑"),
    ("轻而易举", "轻而易举"),
    ("急不可奈", "急不可耐"),
    ("既往不究", "既往不咎"),
    ("娇揉造作", "矫揉造作"),
    ("金榜提名", "金榜题名"),
    ("精兵减政", "精兵简政"),
    ("坚苦卓绝", "艰苦卓绝"),
    ("哭笑不得", "哭笑不得"),
    ("滥芋充数", "滥竽充数"),
    ("励精图冶", "励精图治"),
    ("美仑美奂", "美轮美奂"),
    ("默守成规", "墨守成规"),
    ("名符其实", "名副其实"),
    ("谈笑风声", "谈笑风生"),
    ("天翻地复", "天翻地覆"),
    ("挺而走险", "铤而走险"),
    ("委屈求全", "委曲求全"),
    ("相形见拙", "相形见绌"),
    ("消声匿迹", "销声匿迹"),
    ("言简意骇", "言简意赅"),
    ("一股作气", "一鼓作气"),
    ("一如继往", "一如既往"),
    ("义不容词", "义不容辞"),
    ("再所不辞", "在所不辞"),
    ("震耳欲隆", "震耳欲聋"),
    ("直接了当", "直截了当"),
    ("走头无路", "走投无路"),
    ("座无虚席", "座无虚席"),
    ("黄梁美梦", "黄粱美梦"),
    ("世外桃园", "世外桃源"),
    ("迄今未止", "迄今为止"),
    ("截止目前", "截至目前"),
    ("截止到目前", "截至目前"),
    ("截止今年", "截至今年"),
    ("其它", "其他"),
    ("做为", "作为"),
    ("坐阵", "坐镇"),
    ("部署安排", "部署安排"),
    ("必需品", "必需品"),
    ("必须品", "必需品"),
    ("贯彻落实", "贯彻落实"),
    ("通谍", "通牒"),
    ("气慨", "气概"),
    ("脉博", "脉搏"),
    ("松驰", "松弛"),
    ("寒喧", "寒暄"),
    ("渲泄", "宣泄"),
    ("颠沛留离", "颠沛流离"),
    ("一副对联", "一副对联"),
    ("一幅对联", "一副对联"),
    ("戮力同心", "戮力同心"),
    ("融汇贯通", "融会贯通"),
    ("恪守职责", "恪尽职守"),
    ("关怀倍至", "关怀备至"),
    ("不落巢臼", "不落窠臼"),
    ("出谋化策", "出谋划策"),
    ("事必躬亲", "事必躬亲"),
    ("莫名其妙", "莫名其妙"),
    ("食不果腹", "食不果腹"),
    ("提纲携领", "提纲挈领"),
    ("文过是非", "文过饰非"),
    ("修茸", "修葺"),
    ("一诺千斤", "一诺千金"),
    ("原原本本", "原原本本"),
    ("真知卓见", "真知灼见"),
    ("重蹈复辙", "重蹈覆辙"),
)
TYPOS = tuple(pair for pair in TYPOS if pair[0] != pair[1])


@dataclass
class Finding:
    paragraph: int  # 1-based
    text: str
    suggestion: str
    reason: str
    start: int
    end: int
    rule: str

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "paragraph": self.paragraph,
            "text": self.text,
            "reason": self.reason,
            "rule": self.rule,
        }
        if self.suggestion != self.text:
            out["suggestion"] = self.suggestion
        return out


_HALF_TO_FULL = {",": "，", ";": "；", ":": "：", "?": "？", "!": "！"}


def _punctuation(text: str) -> Iterator[tuple[int, int, str, str, str]]:
    # A half-width mark right after a Chinese character, and not inside a number or a URL.
    for match in re.finditer(rf"(?<=[{_HAN}])([,;:?!])(?![0-9/])", text):
        mark = match.group(1)
        yield (
            match.start(1),
            match.end(1),
            _HALF_TO_FULL[mark],
            "中文语句中应使用全角标点",
            "punctuation",
        )
    for match in re.finditer(rf"(?<=[{_HAN}])\.(?=\s*(?:[{_HAN}]|$))", text):
        yield match.start(), match.end(), "。", "中文句末应使用全角句号", "punctuation"
    for match in re.finditer(rf"\(([^()]*[{_HAN}][^()]*)\)", text):
        yield (
            match.start(),
            match.end(),
            f"（{match.group(1)}）",
            "中文内容的括号应使用全角",
            "brackets",
        )
    for match in re.finditer(rf'"([^"]*[{_HAN}][^"]*)"', text):
        yield match.start(), match.end(), f"“{match.group(1)}”", "中文引号应使用“”", "quotes"
    for match in re.finditer(r"([，。、；：？！])\1+", text):
        yield match.start(), match.end(), match.group(1), "标点重复", "doubled_punctuation"
    for match in re.finditer(r"[，、；：][。！？]|[。！？][，、；]", text):
        yield match.start(), match.end(), match.group(0)[-1], "标点连用", "punctuation_pair"


def _paired(text: str) -> Iterator[tuple[int, int, str, str, str]]:
    for opening, closing, name in (
        ("（", "）", "括号"),
        ("《", "》", "书名号"),
        ("“", "”", "引号"),
        ("【", "】", "方括号"),
    ):
        depth = 0
        for index, char in enumerate(text):
            if char == opening:
                depth += 1
            elif char == closing:
                depth -= 1
                if depth < 0:
                    yield index, index + 1, char, f"{name}不成对：多了一个“{closing}”", "unpaired"
                    depth = 0
        if depth > 0:
            index = text.rfind(opening)
            yield (
                index,
                index + 1,
                opening,
                f"{name}不成对：“{opening}”没有对应的“{closing}”",
                "unpaired",
            )


def _doubled(text: str) -> Iterator[tuple[int, int, str, str, str]]:
    for match in re.finditer(r"(的|了|是|在|和|与|对|把|将|为)\1(?!\1)", text):
        before = text[max(0, match.start() - 1) : match.start()]
        if match.group(1) == "了" and before in {"为", "受", "了"}:
            continue
        yield match.start(), match.end(), match.group(1), f"“{match.group(1)}”重复", "doubled_word"


def _numbers(text: str) -> Iterator[tuple[int, int, str, str, str]]:
    for match in re.finditer(r"[０-９]+", text):
        half = match.group(0).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        yield match.start(), match.end(), half, "数字应使用半角阿拉伯数字", "full_width_digits"
    for match in re.finditer(r"[二〇零○]{1}[0-9〇零○一二三四五六七八九]{3}年", text):
        value = match.group(0)
        if re.search(r"[0-9]", value) and re.search(r"[〇零○一二三四五六七八九]", value):
            yield match.start(), match.end(), value, "年份中汉字与阿拉伯数字混用", "mixed_year"
    for match in re.finditer(
        rf"(?<![0-9.])(20\d\d|19\d\d)[.\-/](\d{{1,2}})[.\-/](\d{{1,2}})(?![0-9])(?=[^0-9]*[{_HAN}]|$)",
        text,
    ):
        year, month, day = match.groups()
        if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            yield (
                match.start(),
                match.end(),
                f"{year}年{int(month)}月{int(day)}日",
                "公文中日期应写作“××××年×月×日”",
                "date",
            )


_SERIAL = re.compile(
    r"^\s*(?:([一二三四五六七八九十]+)[.．,，:：]|[(]([一二三四五六七八九十]+)[)）]|（([一二三四五六七八九十]+)[)]|(\d{1,2})[、，,]|(\d{1,2})[)）](?!\S*\d))"
)


def serial_numbers(text: str) -> Iterator[tuple[int, int, str, str, str]]:
    """The numbering of official documents: 一、 （一） 1. （1）."""
    match = _SERIAL.match(text)
    if not match:
        return
    chinese, half_open, half_close, digit_comma, digit_paren = match.groups()
    span = match.span()
    raw = text[span[0] : span[1]]
    lead = raw[: len(raw) - len(raw.lstrip())]
    if chinese:
        yield span[0], span[1], f"{lead}{chinese}、", "一级标题序号应为“一、”", "serial"
    elif half_open:
        yield (
            span[0],
            span[1],
            f"{lead}（{half_open}）",
            "二级标题序号应为全角括号“（一）”",
            "serial",
        )
    elif half_close:
        yield (
            span[0],
            span[1],
            f"{lead}（{half_close}）",
            "二级标题序号应为全角括号“（一）”",
            "serial",
        )
    elif digit_comma:
        yield span[0], span[1], f"{lead}{digit_comma}.", "三级标题序号应为“1.”", "serial"
    elif digit_paren:
        yield span[0], span[1], f"{lead}（{digit_paren}）", "四级标题序号应为“（1）”", "serial"


def _document_numbers(text: str) -> Iterator[tuple[int, int, str, str, str]]:
    """发文字号: the year in 六角括号 〔2026〕."""
    for match in re.finditer(
        rf"(?<=[{_HAN}A-Za-z])[\[【(（]((?:19|20)\d\d)[\]】)）](?=\d+号)", text
    ):
        yield (
            match.start(),
            match.end(),
            f"〔{match.group(1)}〕",
            "发文字号的年份应使用六角括号〔〕",
            "document_number",
        )


def _typos(text: str) -> Iterator[tuple[int, int, str, str, str]]:
    for wrong, right in TYPOS:
        if wrong == right:
            continue
        for match in re.finditer(re.escape(wrong), text):
            yield match.start(), match.end(), right, f"常见错别字：应为“{right}”", "typo"


def _spaces(text: str) -> Iterator[tuple[int, int, str, str, str]]:
    for match in re.finditer(rf"(?<=[{_HAN}]) +(?=[{_HAN}])", text):
        yield match.start(), match.end(), "", "汉字之间多了空格", "space"


# The more specific rules first: a span one of them reports is not reported again.
RULES = {
    "serial": serial_numbers,
    "document_number": _document_numbers,
    "numbers": _numbers,
    "typos": _typos,
    "punctuation": _punctuation,
    "paired": _paired,
    "doubled": _doubled,
    "spaces": _spaces,
}


def check_paragraphs(texts: list[str], rules: list[str] | None = None) -> list[Finding]:
    chosen = [RULES[name] for name in (rules or list(RULES)) if name in RULES]
    findings: list[Finding] = []
    for number, text in enumerate(texts, start=1):
        if not re.search(f"[{_HAN}]", text):
            continue
        seen: set[tuple[int, int]] = set()
        for rule in chosen:
            for start, end, suggestion, reason, name in rule(text):
                if (start, end) in seen:
                    continue
                seen.add((start, end))
                findings.append(
                    Finding(number, text[start:end], suggestion, reason, start, end, name)
                )
    findings.sort(key=lambda finding: (finding.paragraph, finding.start))
    return findings


def context(text: str, start: int, end: int, width: int = 12) -> str:
    return (
        text[max(0, start - width) : start]
        + "【"
        + text[start:end]
        + "】"
        + text[end : end + width]
    )


__all__ = ["RULES", "TYPOS", "Finding", "check_paragraphs", "context", "serial_numbers"]
