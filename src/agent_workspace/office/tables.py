"""Tables read from Excel workbooks (.xlsx) and CSV files: values as Excel shows them (dates as
dates), formulas kept beside them, and the header row as column names."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agent_workspace.office.ooxml import OfficeError, Package, S, q

MAX_CELLS = 2_000_000
_BUILTIN_DATES = {14, 15, 16, 17, 18, 19, 20, 21, 22, 45, 46, 47, 57, 58}
_CELL = re.compile(r"([A-Z]+)(\d+)")


def column_index(letters: str) -> int:
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - 64
    return value - 1


def column_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


@dataclass
class Sheet:
    name: str
    rows: list[list[Any]] = field(default_factory=list)
    formulas: dict[tuple[int, int], str] = field(default_factory=dict)
    merged: list[str] = field(default_factory=list)

    @property
    def header(self) -> list[str]:
        return [
            str(value).strip() if value is not None else ""
            for value in (self.rows[0] if self.rows else [])
        ]

    def records(self, header_row: int = 1) -> list[dict[str, Any]]:
        """The rows under the header as {column name: value}; blank rows left out."""
        if len(self.rows) < header_row:
            return []
        names = [
            str(value).strip() if value not in (None, "") else column_letter(index)
            for index, value in enumerate(self.rows[header_row - 1])
        ]
        out = []
        for row in self.rows[header_row:]:
            if all(value in (None, "") for value in row):
                continue
            out.append(
                {name: row[index] if index < len(row) else None for index, name in enumerate(names)}
            )
        return out


def _date_formats(package: Package) -> set[int]:
    """Style indexes (cellXfs) whose number format shows a date or time."""
    if not package.has("xl/styles.xml"):
        return set()
    root = package.xml("xl/styles.xml").root
    custom = {}
    formats = root.find(q(S, "numFmts"))
    if formats is not None:
        for item in formats.findall(q(S, "numFmt")):
            code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", item.get("formatCode", ""))
            custom[int(item.get("numFmtId", "0"))] = bool(
                re.search(r"[ymdhs]", code, re.IGNORECASE)
            )
    out = set()
    xfs = root.find(q(S, "cellXfs"))
    if xfs is not None:
        for index, xf in enumerate(xfs.findall(q(S, "xf"))):
            number = int(xf.get("numFmtId", "0"))
            if number in _BUILTIN_DATES or custom.get(number):
                out.add(index)
    return out


def _excel_date(value: float, system_1904: bool) -> str:
    base = datetime(1904, 1, 1) if system_1904 else datetime(1899, 12, 30)
    moment = base + timedelta(days=value)
    if abs(value - round(value)) < 1e-9:
        return moment.strftime("%Y-%m-%d")
    if value < 1:
        return moment.strftime("%H:%M:%S")
    return moment.strftime("%Y-%m-%d %H:%M")


def _number(text: str) -> int | float:
    value = float(text)
    return (
        int(value)
        if value.is_integer() and abs(value) < 1e15 and "." not in text and "E" not in text.upper()
        else value
    )


def read_xlsx(data: bytes) -> list[Sheet]:
    package = Package.read(data)
    if not package.has("xl/workbook.xml"):
        raise OfficeError("not an Excel workbook (.xlsx)")
    workbook = package.xml("xl/workbook.xml").root
    properties = workbook.find(q(S, "workbookPr"))
    system_1904 = properties is not None and properties.get("date1904") in {"1", "true"}
    targets = {
        rid: package.resolve("xl/workbook.xml", target)
        for rid, _kind, target in package.relationships("xl/workbook.xml")
    }
    shared: list[str] = []
    if package.has("xl/sharedStrings.xml"):
        for item in package.xml("xl/sharedStrings.xml").root.findall(q(S, "si")):
            shared.append(
                "".join(
                    text.text or "" for text in item.iter(q(S, "t")) if not _in_phonetic(item, text)
                )
            )
    dates = _date_formats(package)
    sheets = []
    cells = 0
    relationship = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    for entry in workbook.iter(q(S, "sheet")):
        part = targets.get(entry.get(relationship, ""), "")
        if not part or not package.has(part):
            continue
        sheet = Sheet(entry.get("name", ""))
        root = package.xml(part).root
        for row in root.iter(q(S, "row")):
            row_number = int(row.get("r", len(sheet.rows) + 1))
            while len(sheet.rows) < row_number:
                sheet.rows.append([])
            values = sheet.rows[row_number - 1]
            for position, cell in enumerate(row.findall(q(S, "c"))):
                reference = cell.get("r", "")
                match = _CELL.fullmatch(reference)
                column = column_index(match.group(1)) if match else position
                kind = cell.get("t", "n")
                raw = cell.findtext(q(S, "v"))
                value: Any = None
                if kind == "s" and raw is not None:
                    value = shared[int(raw)] if raw.isdigit() and int(raw) < len(shared) else ""
                elif kind == "inlineStr":
                    value = "".join(text.text or "" for text in cell.iter(q(S, "t")))
                elif kind in {"str", "e"}:
                    value = raw
                elif kind == "b":
                    value = raw == "1"
                elif raw not in (None, ""):
                    try:
                        number = _number(raw)
                    except ValueError:
                        value = raw
                    else:
                        style = int(cell.get("s", "0"))
                        value = (
                            _excel_date(float(number), system_1904) if style in dates else number
                        )
                formula = cell.findtext(q(S, "f"))
                if formula:
                    sheet.formulas[(row_number - 1, column)] = "=" + formula
                while len(values) <= column:
                    values.append(None)
                values[column] = value
                cells += 1
                if cells > MAX_CELLS:
                    raise OfficeError("the workbook has more than 2,000,000 cells")
        merges = root.find(q(S, "mergeCells"))
        if merges is not None:
            sheet.merged = [item.get("ref", "") for item in merges.findall(q(S, "mergeCell"))]
        width = max((len(values) for values in sheet.rows), default=0)
        for values in sheet.rows:
            values.extend([None] * (width - len(values)))
        sheets.append(sheet)
    return sheets


def _in_phonetic(item: Any, text: Any) -> bool:
    return any(text in list(phonetic.iter(q(S, "t"))) for phonetic in item.findall(q(S, "rPh")))


def read_csv(data: bytes) -> list[Sheet]:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise OfficeError("the CSV file is neither UTF-8 nor GBK")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows: list[list[Any]] = []
    for row in csv.reader(io.StringIO(text), dialect):
        rows.append([_csv_value(value) for value in row])
    width = max((len(row) for row in rows), default=0)
    padding: list[Any] = [None]
    for row in rows:
        row.extend(padding * (width - len(row)))
    return [Sheet("Sheet1", rows)]


def _csv_value(text: str) -> Any:
    stripped = text.strip()
    if re.fullmatch(r"-?\d+(\.\d+)?", stripped) and not (
        len(stripped) > 1 and stripped.lstrip("-").startswith("0") and "." not in stripped
    ):
        return _number(stripped)
    return text


def read_table_file(path: Path) -> list[Sheet]:
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        return read_xlsx(data)
    if suffix in {".csv", ".tsv", ".txt"}:
        return read_csv(data)
    raise OfficeError("tables are read from .xlsx and .csv files")


def pick_sheet(sheets: list[Sheet], name: str | None) -> Sheet:
    if not sheets:
        raise OfficeError("the file has no sheets")
    if not name:
        return sheets[0]
    for sheet in sheets:
        if sheet.name == name:
            return sheet
    raise OfficeError(f"no sheet named {name}; sheets: {', '.join(sheet.name for sheet in sheets)}")


def display(value: Any) -> str:
    """A value as text the way a person reads it (no 3.0 for 3)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        return f"{value:.10g}"
    return str(value)


__all__ = [
    "Sheet",
    "column_index",
    "column_letter",
    "display",
    "pick_sheet",
    "read_csv",
    "read_table_file",
    "read_xlsx",
]
