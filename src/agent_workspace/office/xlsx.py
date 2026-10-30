# ruff: noqa: E501 -- the XML parts are written as one string each.
"""Excel workbooks written from a description: values and real formulas (with their computed
values stored), number formats, a styled header, borders, highlighted cells, merged cells,
frozen panes, filters, conditional formatting and native charts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from agent_workspace.office import formula
from agent_workspace.office.ooxml import (
    OfficeError,
    content_types,
    escape_attr,
    escape_text,
    relationships,
    zip_parts,
)
from agent_workspace.office.tables import column_index, column_letter

_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?")
_RANGE = re.compile(
    r"(?:(?P<sheet>'[^']+'|[^!]+)!)?\$?(?P<c1>[A-Z]{1,3})\$?(?P<r1>\d+)(?::\$?(?P<c2>[A-Z]{1,3})\$?(?P<r2>\d+))?"
)
_SHEET_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml"
_DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
_CHART_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
MAX_CELLS = 500_000
PALETTE = ["4472C4", "ED7D31", "A5A5A5", "FFC000", "5B9BD5", "70AD47", "264478", "9E480E"]
_BUILTIN_FORMATS = {
    "0": 1,
    "0.00": 2,
    "#,##0": 3,
    "#,##0.00": 4,
    "0%": 9,
    "0.00%": 10,
    "yyyy-mm-dd": 14,
    "@": 49,
}


def _rgb(color: str) -> str:
    value = color.strip().lstrip("#").upper()
    if not re.fullmatch(r"[0-9A-F]{6}", value):
        raise OfficeError(f"colours are written like FFC7CE, not {color!r}")
    return "FF" + value


def excel_serial(moment: date | datetime) -> float:
    base = datetime(1899, 12, 30)
    if not isinstance(moment, datetime):
        moment = datetime(moment.year, moment.month, moment.day)
    delta = moment - base
    return delta.days + delta.seconds / 86400


def parse_range(text: str) -> tuple[str | None, int, int, int, int]:
    """(sheet, first row, first column, last row, last column), 0-based."""
    match = _RANGE.fullmatch(text.strip())
    if not match:
        raise OfficeError(f"cannot read the range {text!r}; write it like A1:C10")
    sheet = match.group("sheet")
    r1, c1 = int(match.group("r1")) - 1, column_index(match.group("c1"))
    r2 = int(match.group("r2")) - 1 if match.group("r2") else r1
    c2 = column_index(match.group("c2")) if match.group("c2") else c1
    return (sheet.strip("'") if sheet else None), min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2)


@dataclass
class _Styles:
    formats: dict[str, int] = field(default_factory=dict)
    fonts: list[str] = field(
        default_factory=lambda: [
            '<font><sz val="11"/><name val="等线"/><family val="2"/><charset val="134"/></font>'
        ]
    )
    fills: list[str] = field(
        default_factory=lambda: [
            '<fill><patternFill patternType="none"/></fill>',
            '<fill><patternFill patternType="gray125"/></fill>',
        ]
    )
    borders: list[str] = field(
        default_factory=lambda: ["<border><left/><right/><top/><bottom/><diagonal/></border>"]
    )
    xfs: list[tuple[int, int, int, int, str]] = field(default_factory=lambda: [(0, 0, 0, 0, "")])
    dxfs: list[str] = field(default_factory=list)

    def _index(self, items: list[str], xml: str) -> int:
        if xml not in items:
            items.append(xml)
        return items.index(xml)

    def number_format(self, code: str) -> int:
        if code in _BUILTIN_FORMATS:
            return _BUILTIN_FORMATS[code]
        if code not in self.formats:
            self.formats[code] = 164 + len(self.formats)
        return self.formats[code]

    def style(
        self,
        *,
        number: str = "",
        bold: bool = False,
        fill: str = "",
        border: bool = False,
        align: str = "",
        wrap: bool = False,
        color: str = "",
    ) -> int:
        number_id = self.number_format(number) if number else 0
        font = 0
        if bold or color:
            font = self._index(
                self.fonts,
                "<font>"
                + ("<b/>" if bold else "")
                + '<sz val="11"/>'
                + (f'<color rgb="{_rgb(color)}"/>' if color else "")
                + '<name val="等线"/><family val="2"/><charset val="134"/></font>',
            )
        fill_id = (
            self._index(
                self.fills,
                f'<fill><patternFill patternType="solid"><fgColor rgb="{_rgb(fill)}"/><bgColor indexed="64"/></patternFill></fill>',
            )
            if fill
            else 0
        )
        border_id = 0
        if border:
            side = '<{0} style="thin"><color rgb="FFBFBFBF"/></{0}>'
            border_id = self._index(
                self.borders,
                "<border>"
                + "".join(side.format(name) for name in ("left", "right", "top", "bottom"))
                + "<diagonal/></border>",
            )
        alignment = ""
        if align or wrap:
            alignment = (
                "<alignment"
                + (f' horizontal="{align}"' if align else "")
                + (' vertical="center" wrapText="1"' if wrap else ' vertical="center"')
                + "/>"
            )
        key = (number_id, font, fill_id, border_id, alignment)
        if key not in self.xfs:
            self.xfs.append(key)
        return self.xfs.index(key)

    def dxf(self, fill: str, color: str = "") -> int:
        xml = (
            "<dxf>"
            + (f'<font><color rgb="{_rgb(color)}"/></font>' if color else "")
            + f'<fill><patternFill><bgColor rgb="{_rgb(fill)}"/></patternFill></fill></dxf>'
        )
        return self._index(self.dxfs, xml)

    def xml(self) -> str:
        formats = "".join(
            f'<numFmt numFmtId="{number}" formatCode="{escape_attr(code)}"/>'
            for code, number in self.formats.items()
        )
        xfs = "".join(
            f'<xf numFmtId="{n}" fontId="{f}" fillId="{fi}" borderId="{b}" xfId="0"'
            + (' applyNumberFormat="1"' if n else "")
            + (' applyFont="1"' if f else "")
            + (' applyFill="1"' if fi else "")
            + (' applyBorder="1"' if b else "")
            + ((' applyAlignment="1">' + a + "</xf>") if a else "/>")
            for n, f, fi, b, a in self.xfs
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            + (f'<numFmts count="{len(self.formats)}">{formats}</numFmts>' if self.formats else "")
            + f'<fonts count="{len(self.fonts)}">{"".join(self.fonts)}</fonts>'
            + f'<fills count="{len(self.fills)}">{"".join(self.fills)}</fills>'
            + f'<borders count="{len(self.borders)}">{"".join(self.borders)}</borders>'
            + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            + f'<cellXfs count="{len(self.xfs)}">{xfs}</cellXfs>'
            + '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            + (f'<dxfs count="{len(self.dxfs)}">{"".join(self.dxfs)}</dxfs>' if self.dxfs else "")
            + "</styleSheet>"
        )


def _width_of(value: Any) -> float:
    text = value if isinstance(value, str) else f"{value}"
    return sum(2 if ord(char) > 0x2E80 else 1 for char in text)


def _quote(sheet: str) -> str:
    return f"'{sheet}'" if re.search(r"[^A-Za-z0-9_]", sheet) else sheet


@dataclass
class _SheetData:
    name: str
    values: list[list[Any]]
    formulas: dict[tuple[int, int], str]


def _cells(sheet_spec: dict[str, Any]) -> list[list[Any]]:
    rows = sheet_spec.get("rows") or []
    if not isinstance(rows, list):
        raise OfficeError("rows must be a list of lists")
    return [list(row) if isinstance(row, list) else [row] for row in rows]


def build(spec: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """The workbook, and per sheet the formulas whose values could not be worked out here."""
    sheets_spec = spec.get("sheets") or []
    if not sheets_spec:
        raise OfficeError("a workbook needs at least one sheet")
    styles = _Styles()
    names: list[str] = []
    data: list[_SheetData] = []
    total = 0
    for index, sheet_spec in enumerate(sheets_spec):
        name = str(sheet_spec.get("name") or f"Sheet{index + 1}")[:31]
        name = re.sub(r"[\\/?*\[\]:]", "-", name)
        if name in names:
            raise OfficeError(f"two sheets are named {name}")
        names.append(name)
        rows = _cells(sheet_spec)
        total += sum(len(row) for row in rows)
        if total > MAX_CELLS:
            raise OfficeError("the workbook would have more than 500,000 cells")
        values: list[list[Any]] = []
        formulas: dict[tuple[int, int], str] = {}
        for r, row in enumerate(rows):
            converted: list[Any] = []
            for c, value in enumerate(row):
                if isinstance(value, str) and value.startswith("=") and len(value) > 1:
                    formulas[(r, c)] = value
                    converted.append(None)
                else:
                    converted.append(value)
            values.append(converted)
        data.append(_SheetData(name, values, formulas))
    computed, unresolved = _compute(data)
    parts: list[tuple[str, str | bytes]] = []
    overrides = {
        "xl/workbook.xml": f"{_SHEET_TYPE}.sheet.main+xml",
        "xl/styles.xml": f"{_SHEET_TYPE}.styles+xml",
    }
    workbook_rels = [("rIdStyles", "styles", "styles.xml")]
    chart_number = 0
    for index, (sheet_spec, sheet) in enumerate(zip(sheets_spec, data, strict=True), start=1):
        xml, drawing = _sheet_xml(sheet_spec, sheet, computed, styles)
        parts.append((f"xl/worksheets/sheet{index}.xml", xml))
        overrides[f"xl/worksheets/sheet{index}.xml"] = f"{_SHEET_TYPE}.worksheet+xml"
        workbook_rels.append((f"rIdSheet{index}", "worksheet", f"worksheets/sheet{index}.xml"))
        charts = sheet_spec.get("charts") or []
        if charts:
            anchors = []
            drawing_rels = []
            for chart_index, chart in enumerate(charts, start=1):
                chart_number += 1
                parts.append((f"xl/charts/chart{chart_number}.xml", _chart_xml(chart, sheet.name)))
                overrides[f"xl/charts/chart{chart_number}.xml"] = (
                    "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"
                )
                drawing_rels.append(
                    (f"rIdChart{chart_index}", "chart", f"../charts/chart{chart_number}.xml")
                )
                anchors.append(_anchor(chart, chart_index))
            parts.append((f"xl/drawings/drawing{index}.xml", _drawing_xml(anchors)))
            overrides[f"xl/drawings/drawing{index}.xml"] = (
                "application/vnd.openxmlformats-officedocument.drawing+xml"
            )
            parts.append(
                (f"xl/drawings/_rels/drawing{index}.xml.rels", relationships(drawing_rels))
            )
            parts.append(
                (
                    f"xl/worksheets/_rels/sheet{index}.xml.rels",
                    relationships([("rIdDrawing", "drawing", f"../drawings/drawing{index}.xml")]),
                )
            )
        _ = drawing
    sheets_xml = "".join(
        f'<sheet name="{escape_attr(name)}" sheetId="{index}" r:id="rIdSheet{index}"/>'
        for index, name in enumerate(names, start=1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="{_R}">'
        f'<sheets>{sheets_xml}</sheets><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>'
    )
    parts = [
        ("[Content_Types].xml", content_types({}, overrides)),
        ("_rels/.rels", relationships([("rId1", "officeDocument", "xl/workbook.xml")])),
        ("xl/workbook.xml", workbook),
        ("xl/_rels/workbook.xml.rels", relationships(workbook_rels)),
        ("xl/styles.xml", styles.xml()),
        *parts,
    ]
    return zip_parts(parts), {"formulas_left_to_excel": unresolved}


def _compute(
    data: list[_SheetData],
) -> tuple[dict[tuple[str, int, int], Any], dict[str, list[str]]]:
    by_name = {sheet.name: sheet for sheet in data}
    values: dict[tuple[str, int, int], Any] = {}
    failed: set[tuple[str, int, int]] = set()
    active: set[tuple[str, int, int]] = set()

    def get(sheet_name: str | None, row: int, column: int, current: str) -> Any:
        name = sheet_name or current
        sheet = by_name.get(name)
        if sheet is None:
            raise formula.Unsupported("#REF!")
        key = (name, row, column)
        if (row, column) in sheet.formulas:
            if key in failed:
                raise formula.Unsupported("depends on an uncomputed formula")
            if key not in values:
                if key in active:
                    raise formula.Unsupported("circular")
                active.add(key)
                try:
                    values[key] = formula.evaluate(
                        sheet.formulas[(row, column)], name, lambda s, r, c: get(s, r, c, name)
                    )
                except formula.Unsupported:
                    failed.add(key)
                    raise
                finally:
                    active.discard(key)
            return values[key]
        if row < len(sheet.values) and column < len(sheet.values[row]):
            return _normalize(sheet.values[row][column])
        return None

    unresolved: dict[str, list[str]] = {}
    for sheet in data:
        for row, column in sheet.formulas:
            try:
                get(sheet.name, row, column, sheet.name)
            except (formula.Unsupported, RecursionError, ValueError, TypeError, OverflowError):
                unresolved.setdefault(sheet.name, []).append(f"{column_letter(column)}{row + 1}")
    return values, unresolved


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        match = _ISO_DATE.fullmatch(value.strip())
        if match:
            return excel_serial(_iso(match))
    return value


def _iso(match: re.Match[str]) -> datetime:
    year, month, day, hour, minute, second = match.groups()
    return datetime(
        int(year), int(month), int(day), int(hour or 0), int(minute or 0), int(second or 0)
    )


def _sheet_xml(
    spec: dict[str, Any],
    sheet: _SheetData,
    computed: dict[tuple[str, int, int], Any],
    styles: _Styles,
) -> tuple[str, bool]:
    rows = sheet.values
    width = max((len(row) for row in rows), default=0)
    header = bool(spec.get("header", True)) and len(rows) > 1
    borders = bool(spec.get("borders", True))
    formats: dict[tuple[int, int], str] = {}
    for reference, code in (spec.get("formats") or {}).items():
        _, r1, c1, r2, c2 = parse_range(reference)
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                formats[(r, c)] = str(code)
    fills: dict[tuple[int, int], str] = {}
    for item in spec.get("highlight") or []:
        _, r1, c1, r2, c2 = parse_range(str(item.get("range", "")))
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                fills[(r, c)] = str(item.get("color") or "FFF2CC")
    bold_rows = {int(number) - 1 for number in spec.get("bold_rows") or []}
    plain_rows = {int(number) - 1 for number in spec.get("plain_rows") or []}
    widths = [0.0] * width
    out_rows = []
    for r, row in enumerate(rows):
        cells = []
        for c in range(width):
            value = row[c] if c < len(row) else None
            formula_text = sheet.formulas.get((r, c))
            bordered = borders and r not in plain_rows
            if value is None and formula_text is None and (r, c) not in fills and not bordered:
                continue
            reference = f"{column_letter(c)}{r + 1}"
            number_format = formats.get((r, c), "")
            if isinstance(value, str) and _ISO_DATE.fullmatch(value.strip()):
                moment = _iso(_ISO_DATE.fullmatch(value.strip()))  # type: ignore[arg-type]
                value = excel_serial(moment)
                number_format = number_format or (
                    "yyyy-mm-dd hh:mm" if moment.hour or moment.minute else "yyyy-mm-dd"
                )
            elif isinstance(value, datetime | date):
                value = excel_serial(value)
                number_format = number_format or "yyyy-mm-dd"
            is_header = header and r == 0
            style = styles.style(
                number=number_format,
                bold=is_header or r in bold_rows,
                fill=fills.get((r, c), "DDEBF7" if is_header or r in bold_rows else ""),
                border=bordered,
                align="center" if is_header else "",
                wrap=is_header,
            )
            style_attribute = f' s="{style}"' if style else ""
            if formula_text is not None:
                result = computed.get((sheet.name, r, c))
                body = f"<f>{escape_text(formula_text[1:])}</f>"
                if isinstance(result, bool):
                    cells.append(
                        f'<c r="{reference}"{style_attribute} t="b">{body}<v>{int(result)}</v></c>'
                    )
                elif isinstance(result, int | float):
                    cells.append(f'<c r="{reference}"{style_attribute}>{body}<v>{result}</v></c>')
                elif isinstance(result, str):
                    cells.append(
                        f'<c r="{reference}"{style_attribute} t="str">{body}<v>{escape_text(result)}</v></c>'
                    )
                else:
                    cells.append(f'<c r="{reference}"{style_attribute}>{body}</c>')
                widths[c] = max(widths[c], 10)
            elif value is None or value == "":
                cells.append(f'<c r="{reference}"{style_attribute}/>')
            elif isinstance(value, bool):
                cells.append(f'<c r="{reference}"{style_attribute} t="b"><v>{int(value)}</v></c>')
            elif isinstance(value, int | float):
                cells.append(f'<c r="{reference}"{style_attribute}><v>{value}</v></c>')
                widths[c] = max(
                    widths[c],
                    len(f"{value:,.2f}") if isinstance(value, float) else len(str(value)) + 2,
                )
            else:
                text = escape_text(str(value))
                cells.append(
                    f'<c r="{reference}"{style_attribute} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'
                )
                widths[c] = max(widths[c], min(60.0, _width_of(value) + 2))
        out_rows.append(f'<row r="{r + 1}">{"".join(cells)}</row>')
    given = {
        column_index(key.upper()): float(value) for key, value in (spec.get("widths") or {}).items()
    }
    columns = "".join(
        f'<col min="{c + 1}" max="{c + 1}" width="{given.get(c, max(8.0, min(60.0, widths[c] * 1.1))):.1f}" customWidth="1"/>'
        for c in range(width)
    )
    freeze = spec.get("freeze", "A2" if header else "")
    view = '<sheetView workbookViewId="0"/>'
    if freeze:
        _, fr, fc, _r2, _c2 = parse_range(str(freeze))
        pane_attributes = (f' xSplit="{fc}"' if fc else "") + (f' ySplit="{fr}"' if fr else "")
        if pane_attributes:
            active = "bottomRight" if fr and fc else "bottomLeft" if fr else "topRight"
            view = (
                f'<sheetView workbookViewId="0"><pane{pane_attributes} topLeftCell="{freeze}" activePane="{active}" state="frozen"/>'
                f'<selection pane="{active}"/></sheetView>'
            )
    merges = spec.get("merge") or []
    merge_xml = (
        f'<mergeCells count="{len(merges)}">'
        + "".join(f'<mergeCell ref="{escape_attr(str(item))}"/>' for item in merges)
        + "</mergeCells>"
        if merges
        else ""
    )
    filter_xml = (
        f'<autoFilter ref="A1:{column_letter(max(width - 1, 0))}{len(rows)}"/>'
        if header and spec.get("filter", True)
        else ""
    )
    conditional = _conditional_xml(spec.get("conditional") or [], styles)
    drawing = bool(spec.get("charts"))
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="{_R}">'
        f"<sheetViews>{view}</sheetViews>"
        '<sheetFormatPr defaultRowHeight="15"/>'
        + (f"<cols>{columns}</cols>" if width else "")
        + f"<sheetData>{''.join(out_rows)}</sheetData>"
        + filter_xml
        + merge_xml
        + conditional
        + ('<drawing r:id="rIdDrawing"/>' if drawing else "")
        + "</worksheet>"
    )
    return xml, drawing


_OPERATORS = {
    "greater_than": "greaterThan",
    "less_than": "lessThan",
    "equal": "equal",
    "not_equal": "notEqual",
    "greater_or_equal": "greaterThanOrEqual",
    "less_or_equal": "lessThanOrEqual",
    "between": "between",
}


def _conditional_xml(rules: list[dict[str, Any]], styles: _Styles) -> str:
    out = []
    for priority, rule in enumerate(rules, start=1):
        reference = str(rule.get("range", ""))
        parse_range(reference.split(" ")[0])
        kind = str(rule.get("type", "greater_than"))
        fill = str(rule.get("color") or "FFC7CE")
        if kind in _OPERATORS:
            values = rule.get("value")
            items = values if isinstance(values, list) else [values]
            formulas = "".join(
                f"<formula>{escape_text(_literal(item))}</formula>"
                for item in items[: 2 if kind == "between" else 1]
            )
            body = f'<cfRule type="cellIs" dxfId="{styles.dxf(fill)}" priority="{priority}" operator="{_OPERATORS[kind]}">{formulas}</cfRule>'
        elif kind == "duplicates":
            body = (
                f'<cfRule type="duplicateValues" dxfId="{styles.dxf(fill)}" priority="{priority}"/>'
            )
        elif kind == "formula":
            body = f'<cfRule type="expression" dxfId="{styles.dxf(fill)}" priority="{priority}"><formula>{escape_text(str(rule.get("formula", "")).lstrip("="))}</formula></cfRule>'
        elif kind == "color_scale":
            low, high = (
                _rgb(str(rule.get("low") or "F8696B")),
                _rgb(str(rule.get("high") or "63BE7B")),
            )
            body = f'<cfRule type="colorScale" priority="{priority}"><colorScale><cfvo type="min"/><cfvo type="max"/><color rgb="{low}"/><color rgb="{high}"/></colorScale></cfRule>'
        elif kind == "data_bar":
            body = f'<cfRule type="dataBar" priority="{priority}"><dataBar><cfvo type="min"/><cfvo type="max"/><color rgb="{_rgb(str(rule.get("color") or "638EC6"))}"/></dataBar></cfRule>'
        else:
            raise OfficeError(f"unknown conditional format {kind}")
        out.append(
            f'<conditionalFormatting sqref="{escape_attr(reference)}">{body}</conditionalFormatting>'
        )
    return "".join(out)


def _literal(value: Any) -> str:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    text = str(value if value is not None else "")
    if text.startswith("="):
        return text[1:]
    try:
        float(text)
        return text
    except ValueError:
        return '"' + text.replace('"', '""') + '"'


def _anchor(chart: dict[str, Any], index: int) -> str:
    _, row, column, _r2, _c2 = parse_range(str(chart.get("at") or "H2"))
    columns = int(chart.get("width") or 8)
    rows = int(chart.get("height") or 16)
    return (
        "<xdr:twoCellAnchor>"
        f"<xdr:from><xdr:col>{column}</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>{row}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>"
        f"<xdr:to><xdr:col>{column + columns}</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>{row + rows}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to>"
        f'<xdr:graphicFrame macro=""><xdr:nvGraphicFramePr><xdr:cNvPr id="{index + 1}" name="Chart {index}"/><xdr:cNvGraphicFramePr/></xdr:nvGraphicFramePr>'
        '<xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm>'
        f'<a:graphic><a:graphicData uri="{_CHART_NS}"><c:chart xmlns:c="{_CHART_NS}" r:id="rIdChart{index}"/></a:graphicData></a:graphic>'
        "</xdr:graphicFrame><xdr:clientData/></xdr:twoCellAnchor>"
    )


def _drawing_xml(anchors: list[str]) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<xdr:wsDr xmlns:xdr="{_DRAWING_NS}" xmlns:a="{_A}" xmlns:r="{_R}">{"".join(anchors)}</xdr:wsDr>'
    )


def _absolute(reference: str, sheet: str) -> str:
    target, r1, c1, r2, c2 = parse_range(reference)
    return f"{_quote(target or sheet)}!${column_letter(c1)}${r1 + 1}:${column_letter(c2)}${r2 + 1}"


def _string_cache(values: list[str]) -> str:
    points = "".join(
        f'<c:pt idx="{index}"><c:v>{escape_text(value)}</c:v></c:pt>'
        for index, value in enumerate(values)
    )
    return f'<c:strCache><c:ptCount val="{len(values)}"/>{points}</c:strCache>'


def _number_cache(values: list[float | None]) -> str:
    points = "".join(
        f'<c:pt idx="{index}"><c:v>{value}</c:v></c:pt>'
        for index, value in enumerate(values)
        if value is not None
    )
    return (
        f"<c:numCache><c:formatCode>General</c:formatCode>"
        f'<c:ptCount val="{len(values)}"/>{points}</c:numCache>'
    )


def chart_xml(
    chart: dict[str, Any],
    sheet: str,
    *,
    caches: tuple[list[str], list[list[float | None]]] | None = None,
    external: str = "",
    text_size: int = 1000,
    theme_fonts: bool = False,
) -> str:
    """A chart part. In a workbook the values are read from the sheet; a PowerPoint chart also
    carries them (caches) and names its embedded workbook (external)."""
    xml = _chart_xml(chart, sheet, caches)
    if theme_fonts:
        # The deck's own fonts and accent colours, so the chart matches its template.
        xml = xml.replace('<a:latin typeface="等线"/><a:ea typeface="等线"/>', "")
        for index, colour in enumerate(PALETTE):
            xml = xml.replace(
                f'<a:srgbClr val="{colour}"/>', f'<a:schemeClr val="accent{index % 6 + 1}"/>'
            )
    if text_size != 1000:
        xml = xml.replace('<a:defRPr sz="1000">', f'<a:defRPr sz="{text_size}">', 1)
    if external:
        xml = xml.replace(
            "</c:chartSpace>",
            f'<c:externalData r:id="{external}"><c:autoUpdate val="0"/></c:externalData></c:chartSpace>',
        )
    return xml


def _chart_xml(
    chart: dict[str, Any],
    sheet: str,
    caches: tuple[list[str], list[list[float | None]]] | None = None,
) -> str:
    kind = str(chart.get("type") or "column")
    title = str(chart.get("title") or "")
    categories = chart.get("categories")
    series = chart.get("series") or []
    if not series:
        raise OfficeError("a chart needs at least one series of values")
    series_xml = []
    for number, item in enumerate(series):
        name = escape_text(str(item.get("name") or f"系列{number + 1}"))
        color = PALETTE[number % len(PALETTE)]
        shape = (
            f'<c:spPr><a:ln w="28575"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln></c:spPr><c:marker><c:symbol val="none"/></c:marker>'
            if kind == "line"
            else ""
            if kind == "pie"
            else f'<c:spPr><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></c:spPr>'
        )
        points = ""
        if kind == "pie":
            points = "".join(
                f'<c:dPt><c:idx val="{index}"/><c:bubble3D val="0"/><c:spPr><a:solidFill><a:srgbClr val="{PALETTE[index % len(PALETTE)]}"/></a:solidFill></c:spPr></c:dPt>'
                for index in range(_length(str(item.get("values", "")), sheet))
            )
        category_cache = _string_cache(caches[0]) if caches else ""
        value_cache = _number_cache(caches[1][number]) if caches else ""
        category_xml = (
            f"<c:cat><c:strRef><c:f>{escape_text(_absolute(str(categories), sheet))}</c:f>{category_cache}</c:strRef></c:cat>"
            if categories
            else ""
        )
        series_xml.append(
            f'<c:ser><c:idx val="{number}"/><c:order val="{number}"/><c:tx><c:v>{name}</c:v></c:tx>{shape}{points}'
            + (
                '<c:dLbls><c:showLegendKey val="0"/><c:showVal val="0"/><c:showCatName val="1"/><c:showSerName val="0"/><c:showPercent val="1"/><c:showBubbleSize val="0"/></c:dLbls>'
                if kind == "pie"
                else ""
            )
            + f"{category_xml}<c:val><c:numRef><c:f>{escape_text(_absolute(str(item.get('values', '')), sheet))}</c:f>{value_cache}</c:numRef></c:val>"
            + ('<c:smooth val="0"/>' if kind == "line" else "")
            + "</c:ser>"
        )
    axes = '<c:axId val="500000001"/><c:axId val="500000002"/>'
    if kind == "pie":
        plot = f'<c:pieChart><c:varyColors val="1"/>{"".join(series_xml)}<c:firstSliceAng val="0"/></c:pieChart>'
        axis_xml = ""
    elif kind == "line":
        plot = f'<c:lineChart><c:grouping val="standard"/><c:varyColors val="0"/>{"".join(series_xml)}<c:marker val="1"/>{axes}</c:lineChart>'
        axis_xml = _axes()
    else:
        direction = "bar" if kind == "bar" else "col"
        stacked = bool(chart.get("stacked"))
        plot = (
            f'<c:barChart><c:barDir val="{direction}"/><c:grouping val="{"stacked" if stacked else "clustered"}"/><c:varyColors val="0"/>'
            f'{"".join(series_xml)}<c:gapWidth val="80"/>'
            + ('<c:overlap val="100"/>' if stacked else "")
            + f"{axes}</c:barChart>"
        )
        axis_xml = _axes(horizontal=kind == "bar")
    title_xml = (
        f'<c:title><c:tx><c:rich><a:bodyPr/><a:p><a:pPr><a:defRPr sz="1400" b="1"/></a:pPr><a:r><a:rPr lang="zh-CN" sz="1400" b="1"/><a:t>{escape_text(title)}</a:t></a:r></a:p></c:rich></c:tx><c:overlay val="0"/></c:title><c:autoTitleDeleted val="0"/>'
        if title
        else '<c:autoTitleDeleted val="1"/>'
    )
    legend = (
        '<c:legend><c:legendPos val="b"/><c:overlay val="0"/></c:legend>'
        if len(series) > 1 or kind == "pie"
        else ""
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<c:chartSpace xmlns:c="{_CHART_NS}" xmlns:a="{_A}" xmlns:r="{_R}"><c:lang val="zh-CN"/>'
        f'<c:chart>{title_xml}<c:plotArea><c:layout/>{plot}{axis_xml}</c:plotArea>{legend}<c:plotVisOnly val="1"/></c:chart>'
        '<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="1000"><a:latin typeface="等线"/><a:ea typeface="等线"/></a:defRPr></a:pPr><a:endParaRPr lang="zh-CN"/></a:p></c:txPr>'
        "</c:chartSpace>"
    )


def _length(reference: str, sheet: str) -> int:
    if not reference:
        return 0
    _, r1, c1, r2, c2 = parse_range(reference)
    _ = sheet
    return max(r2 - r1 + 1, c2 - c1 + 1)


def _axes(horizontal: bool = False) -> str:
    category_position, value_position = ("l", "b") if horizontal else ("b", "l")
    return (
        f'<c:catAx><c:axId val="500000001"/><c:scaling><c:orientation val="{"maxMin" if horizontal else "minMax"}"/></c:scaling><c:delete val="0"/>'
        f'<c:axPos val="{category_position}"/><c:numFmt formatCode="General" sourceLinked="1"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/>'
        '<c:tickLblPos val="nextTo"/><c:crossAx val="500000002"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/></c:catAx>'
        f'<c:valAx><c:axId val="500000002"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="{value_position}"/>'
        '<c:majorGridlines><c:spPr><a:ln w="6350"><a:solidFill><a:srgbClr val="D9D9D9"/></a:solidFill></a:ln></c:spPr></c:majorGridlines>'
        '<c:numFmt formatCode="General" sourceLinked="1"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
        '<c:crossAx val="500000001"/><c:crosses val="autoZero"/><c:crossBetween val="between"/></c:valAx>'
    )


__all__ = ["build", "chart_xml", "column_letter", "excel_serial", "parse_range"]
