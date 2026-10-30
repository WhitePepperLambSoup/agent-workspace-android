# ruff: noqa: RUF001, E501 -- the templates are Chinese documents.
"""Templates for everyday documents: official documents laid out to GB/T 9704 (通知, 请示, 报告,
函, 会议纪要, 会议通知), forms and letters (请假单, 出差申请, 在职证明, 收入证明, 介绍信, 邀请函,
工作总结, 述职报告, 项目周报) and workbooks (报销单, 考勤表, 工资表). Fields are written {{字段}};
the user's own .docx/.xlsx/.pptx files in the templates folder are listed beside them.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from agent_workspace.office import gongwen, merge, xlsx
from agent_workspace.office.ooxml import A, OfficeError, Package, S, clean, q
from agent_workspace.tools.office_formats import markdown_docx

_FIELD = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
USER_SUFFIXES = {".docx", ".xlsx", ".pptx"}


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    category: str
    kind: str
    build: Callable[[], bytes]
    description: str = ""


def _official(**values: Any) -> Callable[[], bytes]:
    return lambda: gongwen.build(gongwen.Document.from_dict(values))


_NOTICE_BODY = "为{{目的}}，现将有关事项通知如下。\n一、{{第一项}}\n{{第一项内容}}\n二、{{第二项}}\n{{第二项内容}}\n三、有关要求\n{{要求}}"
_MEETING_BODY = (
    "经研究，决定召开{{会议名称}}。现将有关事项通知如下。\n一、会议时间\n{{会议时间}}\n二、会议地点\n{{会议地点}}\n"
    "三、参会人员\n{{参会人员}}\n四、会议议程\n{{会议议程}}\n五、有关要求\n请参会人员于{{报名截止}}前将回执报{{联系部门}}，联系人：{{联系人}}，电话：{{联系电话}}。"
)


def _markdown(text: str, title: str) -> Callable[[], bytes]:
    return lambda: markdown_docx(text, title)


_LEAVE = """# 请假申请单

| 项目 | 内容 |
| --- | --- |
| 姓名 | {{姓名}} |
| 部门 | {{部门}} |
| 岗位 | {{岗位}} |
| 请假类型 | {{请假类型}}（事假／病假／年休假／婚假／产假／其他） |
| 请假时间 | {{开始日期}} 至 {{结束日期}}，共 {{天数}} 天 |
| 请假事由 | {{事由}} |
| 工作交接人 | {{交接人}} |
| 联系电话 | {{联系电话}} |

申请人：{{姓名}}　　　　日期：{{申请日期}}

部门负责人意见：

人事部门意见：
"""

_TRIP = """# 出差申请单

| 项目 | 内容 |
| --- | --- |
| 申请人 | {{姓名}} |
| 部门 | {{部门}} |
| 出差地点 | {{出差地点}} |
| 出差时间 | {{开始日期}} 至 {{结束日期}}，共 {{天数}} 天 |
| 出差事由 | {{事由}} |
| 同行人员 | {{同行人员}} |
| 交通方式 | {{交通方式}} |
| 预计费用 | 交通 {{交通费}} 元，住宿 {{住宿费}} 元，其他 {{其他费用}} 元，合计 {{合计}} 元 |

申请人：{{姓名}}　　　　日期：{{申请日期}}

部门负责人意见：

分管领导意见：
"""

_EMPLOYMENT = """# 在职证明

兹证明{{姓名}}（身份证号：{{身份证号}}）自{{入职日期}}起在我单位工作，现任{{部门}}{{岗位}}职务，为我单位正式在职员工。

特此证明。

本证明仅用于{{用途}}，不作其他用途。

{{单位名称}}（盖章）

{{开具日期}}
"""

_INCOME = """# 收入证明

兹证明{{姓名}}（身份证号：{{身份证号}}）系我单位员工，自{{入职日期}}起在我单位工作，现任{{岗位}}。该员工近一年税前月平均收入为人民币{{月收入}}元（大写：{{月收入大写}}）。

特此证明。

本证明仅用于{{用途}}。

单位名称：{{单位名称}}（盖章）

联系人：{{联系人}}　　联系电话：{{联系电话}}

{{开具日期}}
"""

_INTRODUCTION = """# 介绍信

{{接收单位}}：

兹介绍我单位{{姓名}}等{{人数}}名同志（身份证号：{{身份证号}}）前往贵处联系{{事由}}，请予接洽为盼。

此致

敬礼！

{{单位名称}}（盖章）

{{开具日期}}

（有效期 {{有效天数}} 天）
"""

_INVITATION = """# 邀请函

尊敬的{{受邀人}}：

{{单位名称}}定于{{活动时间}}在{{活动地点}}举办{{活动名称}}。{{活动简介}}

诚挚邀请您拨冗出席。

敬请于{{回复截止}}前回复是否出席。联系人：{{联系人}}，电话：{{联系电话}}。

{{单位名称}}

{{发出日期}}
"""

_SUMMARY = """# {{年度}}年度工作总结

{{部门}}　{{姓名}}

## 一、主要工作完成情况

{{主要工作}}

## 二、取得的成效与亮点

{{成效}}

## 三、存在的问题与不足

{{问题}}

## 四、下一步工作计划

{{计划}}
"""

_REPORT = """# 述职报告

{{单位}}　{{岗位}}　{{姓名}}

各位领导、同事：

根据安排，现将本人{{期间}}的履职情况报告如下。

## 一、履职基本情况

{{履职情况}}

## 二、主要工作成绩

{{工作成绩}}

## 三、廉洁自律情况

{{廉洁自律}}

## 四、存在的不足和改进方向

{{不足与改进}}

以上报告，请予审议。

{{日期}}
"""

_WEEKLY = """# 项目周报（{{开始日期}}—{{结束日期}}）

项目名称：{{项目名称}}　　负责人：{{负责人}}

## 本周完成

| 事项 | 负责人 | 完成情况 |
| --- | --- | --- |
| {{事项1}} | {{负责人1}} | {{完成情况1}} |
| {{事项2}} | {{负责人2}} | {{完成情况2}} |

## 下周计划

{{下周计划}}

## 风险与需协调事项

{{风险}}
"""


def _expenses() -> bytes:
    rows: list[list[Any]] = [["日期", "费用类别", "摘要", "发票张数", "金额（元）", "备注"]]
    rows += [["", "", "", None, None, ""] for _ in range(8)]
    rows.append(["合计", "", "", "=SUM(D2:D9)", "=SUM(E2:E9)", ""])
    data, _ = xlsx.build(
        {
            "sheets": [
                {
                    "name": "费用报销单",
                    "rows": rows,
                    "formats": {"E2:E10": "#,##0.00"},
                    "bold_rows": [10],
                    "widths": {"A": 12, "B": 12, "C": 30, "D": 10, "E": 14, "F": 16},
                }
            ]
        }
    )
    return data


def _attendance() -> bytes:
    header: list[Any] = ["姓名", "部门", *[f"{day}日" for day in range(1, 32)], "出勤天数"]
    rows: list[list[Any]] = [header]
    for row in range(2, 12):
        rows.append(["", "", *[""] * 31, f'=COUNTIF(C{row}:AG{row},"√")'])
    data, _ = xlsx.build(
        {"sheets": [{"name": "{{年月}}考勤表", "rows": rows, "widths": {"A": 10, "B": 10}}]}
    )
    return data


def _salary() -> bytes:
    rows: list[list[Any]] = [
        [
            "工号",
            "姓名",
            "部门",
            "基本工资",
            "岗位工资",
            "绩效",
            "补贴",
            "应发合计",
            "社保公积金",
            "个税",
            "实发工资",
        ]
    ]
    for row in range(2, 12):
        rows.append(
            [
                "",
                "",
                "",
                None,
                None,
                None,
                None,
                f"=SUM(D{row}:G{row})",
                None,
                None,
                f"=H{row}-I{row}-J{row}",
            ]
        )
    data, _ = xlsx.build(
        {"sheets": [{"name": "工资表", "rows": rows, "formats": {"D2:K11": "#,##0.00"}}]}
    )
    return data


BUILTIN: tuple[Template, ...] = (
    Template(
        "notice",
        "通知（红头文件）",
        "公文",
        "docx",
        _official(
            kind="文件",
            organ="{{发文机关}}",
            number="{{发文字号}}",
            title="关于{{事项}}的通知",
            recipients="{{主送机关}}",
            body=_NOTICE_BODY,
            date="{{成文日期}}",
            cc="{{抄送机关}}",
            printer="{{印发机关}}",
            print_date="{{印发日期}}印发",
        ),
    ),
    Template(
        "request",
        "请示",
        "公文",
        "docx",
        _official(
            kind="文件",
            organ="{{发文机关}}",
            number="{{发文字号}}",
            signer="{{签发人}}",
            title="关于{{事项}}的请示",
            recipients="{{上级机关}}",
            body="{{请示缘由}}\n一、{{请示事项一}}\n二、{{请示事项二}}\n妥否，请批示。",
            date="{{成文日期}}",
            note="联系人：{{联系人}}，电话：{{联系电话}}",
        ),
    ),
    Template(
        "report",
        "报告",
        "公文",
        "docx",
        _official(
            kind="文件",
            organ="{{发文机关}}",
            number="{{发文字号}}",
            title="关于{{事项}}的报告",
            recipients="{{主送机关}}",
            body="{{报告缘由}}\n一、基本情况\n{{基本情况}}\n二、主要做法\n{{主要做法}}\n三、存在问题\n{{存在问题}}\n四、下一步工作\n{{下一步工作}}\n特此报告。",
            date="{{成文日期}}",
        ),
    ),
    Template(
        "letter",
        "函",
        "公文",
        "docx",
        _official(
            kind="普通",
            organ="{{发文机关}}",
            number="{{发文字号}}",
            title="关于{{事项}}的函",
            recipients="{{受文单位}}",
            body="{{来函缘由}}\n{{具体事项}}\n请予函复。",
            date="{{成文日期}}",
            note="联系人：{{联系人}}，电话：{{联系电话}}",
        ),
    ),
    Template(
        "minutes",
        "会议纪要",
        "公文",
        "docx",
        _official(
            kind="纪要",
            organ="{{机关}}",
            number="第{{期数}}期",
            title="{{会议名称}}纪要",
            body="{{会议时间}}，{{主持人}}在{{会议地点}}主持召开{{会议名称}}，研究{{议题}}。现将会议议定事项纪要如下。\n一、{{议定事项一}}\n二、{{议定事项二}}",
            attendees="{{出席人员}}",
            absent="{{请假人员}}",
            observers="{{列席人员}}",
            date="{{成文日期}}",
        ),
    ),
    Template(
        "meeting-notice",
        "会议通知",
        "公文",
        "docx",
        _official(
            kind="普通",
            organ="{{发文单位}}",
            title="关于召开{{会议名称}}的通知",
            recipients="{{主送单位}}",
            body=_MEETING_BODY,
            date="{{成文日期}}",
        ),
    ),
    Template("leave", "请假申请单", "表单", "docx", _markdown(_LEAVE, "请假申请单")),
    Template("trip", "出差申请单", "表单", "docx", _markdown(_TRIP, "出差申请单")),
    Template("employment", "在职证明", "证明信函", "docx", _markdown(_EMPLOYMENT, "在职证明")),
    Template("income", "收入证明", "证明信函", "docx", _markdown(_INCOME, "收入证明")),
    Template("introduction", "介绍信", "证明信函", "docx", _markdown(_INTRODUCTION, "介绍信")),
    Template("invitation", "邀请函", "证明信函", "docx", _markdown(_INVITATION, "邀请函")),
    Template("summary", "年度工作总结", "总结报告", "docx", _markdown(_SUMMARY, "工作总结")),
    Template("duty-report", "述职报告", "总结报告", "docx", _markdown(_REPORT, "述职报告")),
    Template("weekly", "项目周报", "总结报告", "docx", _markdown(_WEEKLY, "项目周报")),
    Template("expenses", "费用报销单", "表格", "xlsx", _expenses),
    Template("attendance", "考勤表", "表格", "xlsx", _attendance),
    Template("salary", "工资表", "表格", "xlsx", _salary),
)


def fields_of(data: bytes, kind: str) -> list[str]:
    if kind == "docx":
        return merge.template_fields(data)
    package = Package.read(data)
    names: list[str] = []
    for text in _texts(package, kind):
        for match in _FIELD.finditer(text.text or ""):
            if match.group(1) not in names:
                names.append(match.group(1))
    return names


def _texts(package: Package, kind: str) -> list[ET.Element]:
    out: list[ET.Element] = []
    if kind == "xlsx":
        parts = [name for name in ("xl/sharedStrings.xml",) if package.has(name)]
        parts += [name for name in package.names("xl/worksheets/") if name.endswith(".xml")]
        parts += ["xl/workbook.xml"] if package.has("xl/workbook.xml") else []
        for part in parts:
            out.extend(package.xml(part).root.iter(q(S, "t")))
    else:
        for part in sorted(package.names("ppt/slides/")):
            if part.endswith(".xml") and "/_rels/" not in part:
                out.extend(package.xml(part).root.iter(q(A, "t")))
    return out


def fill(data: bytes, kind: str, values: dict[str, Any]) -> tuple[bytes, list[str]]:
    """The template with its fields filled; the fields left without a value."""
    if kind == "docx":
        return merge.fill(data, values)
    package = Package.read(data)
    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in values:
            return clean(str(values[name]))
        missing.add(name)
        return ""

    for text in _texts(package, kind):
        if text.text and "{{" in text.text:
            text.text = _FIELD.sub(replace, text.text)
    if kind == "xlsx" and package.has("xl/workbook.xml"):
        for sheet in package.xml("xl/workbook.xml").root.iter(q(S, "sheet")):
            name = sheet.get("name", "")
            if "{{" in name:
                sheet.set(
                    "name", re.sub(r"[\\/?*\[\]:]", "-", _FIELD.sub(replace, name))[:31] or "Sheet1"
                )
    return package.to_bytes(), sorted(missing)


def user_templates(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file()
        and path.suffix.lower() in USER_SUFFIXES
        and not path.name.startswith("~$")
    )


def listing(folder: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for template in BUILTIN:
        data = template.build()
        out.append(
            {
                "id": template.id,
                "name": template.name,
                "category": template.category,
                "kind": template.kind,
                "fields": fields_of(data, template.kind),
                "source": "builtin",
            }
        )
    for path in user_templates(folder):
        kind = path.suffix.lower().lstrip(".")
        try:
            fields = fields_of(path.read_bytes(), kind)
        except (OSError, OfficeError):
            continue
        relative = path.relative_to(folder).as_posix()
        out.append(
            {
                "id": f"user:{relative}",
                "name": path.stem,
                "category": "我的模板",
                "kind": kind,
                "fields": fields,
                "source": "user",
            }
        )
    return out


def create(
    template_id: str, folder: Path, values: dict[str, Any]
) -> tuple[bytes, str, list[str], str]:
    """(bytes, suffix, fields left empty, the template's name)."""
    if template_id.startswith("user:"):
        relative = template_id[5:]
        path = (folder / relative).resolve()
        if (
            folder.resolve() not in path.parents
            or not path.is_file()
            or path.suffix.lower() not in USER_SUFFIXES
        ):
            raise OfficeError(f"no template {relative} in the templates folder")
        kind = path.suffix.lower().lstrip(".")
        data, missing = fill(path.read_bytes(), kind, values)
        return data, f".{kind}", missing, path.stem
    for template in BUILTIN:
        if template.id == template_id:
            data, missing = fill(template.build(), template.kind, values)
            return data, f".{template.kind}", missing, template.name
    raise OfficeError(
        f"no template {template_id}; templates: {', '.join(template.id for template in BUILTIN)}"
    )


__all__ = ["BUILTIN", "Template", "create", "fields_of", "fill", "listing", "user_templates"]
