# ruff: noqa: RUF001, RUF003, E501 -- invoice field names and patterns are Chinese.
"""Electronic invoices (数电发票 and the earlier 增值税电子普通/专用发票) read from their XML, OFD
or PDF files: number, date, seller, buyer, amount, tax, total and the items.

The XML file is the original (what accounting keeps); an OFD file carries the same fields in its
custom data or an attached XML, and its pages as text; a PDF is read from its text. Duplicates
are found by number, and each invoice is checked: amount + tax = total.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from pypdf import PdfReader

from agent_workspace.office.ooxml import OfficeError

SUFFIXES = {".xml", ".ofd", ".pdf"}
_FIELDS = {
    "number": ("InvoiceNumber", "InvoiceNo", "EInvoiceNumber", "FPHM", "Fphm", "发票号码"),
    "code": ("InvoiceCode", "FPDM", "Fpdm", "发票代码"),
    "date": ("IssueTime", "IssueDate", "RequestTime", "KPRQ", "Kprq", "开票日期"),
    "seller": ("SellerName", "XSFMC", "Xsfmc", "销售方名称", "销售方"),
    "seller_tax_id": (
        "SellerIdNum",
        "SellerTaxID",
        "XSFNSRSBH",
        "销售方纳税人识别号",
        "销售方识别号",
    ),
    "buyer": ("BuyerName", "GMFMC", "Gmfmc", "购买方名称", "购买方"),
    "buyer_tax_id": ("BuyerIdNum", "BuyerTaxID", "GMFNSRSBH", "购买方纳税人识别号", "购买方识别号"),
    "amount": ("TotalAmWithoutTax", "TotalAmount", "HJJE", "Hjje", "合计金额"),
    "tax": ("TotalTaxAm", "TotalTax", "HJSE", "Hjse", "合计税额"),
    "total": (
        "TotalTax-includedAmount",
        "TotalTaxincludedAmount",
        "AmountTax",
        "JSHJ",
        "Jshj",
        "价税合计",
        "价税合计（小写）",
    ),
}
_ITEM_NAMES = ("ItemName", "Item", "XMMC", "Xmmc", "GoodsName")
_RANK = {"xml": 0, "ofd": 1, "pdf": 2}


@dataclass
class Invoice:
    file: str
    format: str
    number: str = ""
    code: str = ""
    date: str = ""
    seller: str = ""
    seller_tax_id: str = ""
    buyer: str = ""
    buyer_tax_id: str = ""
    amount: str = ""
    tax: str = ""
    total: str = ""
    items: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {key: value for key, value in self.__dict__.items() if value not in ("", [], None)}


def _money(text: str) -> str:
    cleaned = re.sub(r"[¥￥,，\s元]", "", text or "")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return ""
    try:
        return str(Decimal(match.group(0)).quantize(Decimal("0.01")))
    except InvalidOperation:
        return ""


def _date(text: str) -> str:
    match = re.search(r"(20\d\d)\D{0,3}(\d{1,2})\D{0,3}(\d{1,2})", text or "")
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _from_xml(root: ET.Element, invoice: Invoice) -> None:
    values: dict[str, str] = {}
    for element in root.iter():
        name = _local(element.tag)
        text = (element.text or "").strip()
        if not text:
            continue
        for key, names in _FIELDS.items():
            if name in names and key not in values:
                values[key] = text
        if name in _ITEM_NAMES and len(invoice.items) < 50:
            invoice.items.append(text)
    _apply(invoice, values)


def _apply(invoice: Invoice, values: dict[str, str]) -> None:
    for key, value in values.items():
        if key in {"amount", "tax", "total"}:
            value = _money(value)
        elif key == "date":
            value = _date(value)
        if value and not getattr(invoice, key):
            setattr(invoice, key, value)


_TEXT_PATTERNS = {
    "number": r"发票号码[:：]?\s*(\d{8,20})",
    "code": r"发票代码[:：]?\s*(\d{10,12})",
    "date": r"开票日期[:：]?\s*(20\d\d\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|20\d\d[-/.]\d{1,2}[-/.]\d{1,2})",
    "total": r"(?:价税合计[^¥￥\d]{0,40}|小写[)）]?\s*)[¥￥]\s*(-?[\d,]+\.\d{2})",
}


def _from_text(text: str, invoice: Invoice) -> None:
    flat = re.sub(r"[ \t]+", " ", text)
    values: dict[str, str] = {}
    for key, pattern in _TEXT_PATTERNS.items():
        match = re.search(pattern, flat)
        if match:
            values[key] = match.group(1)
    # 名称：… under 购买方 / 销售方 (the buyer comes first on the form).
    names = re.findall(
        r"名\s*称[:：]\s*([^\n:：]{2,60}?)(?:\s{2,}|\n|统一社会信用代码|纳税人识别号|$)", flat
    )
    if names:
        values.setdefault("buyer", names[0].strip())
        if len(names) > 1:
            values.setdefault("seller", names[1].strip())
    ids = re.findall(
        r"(?:统一社会信用代码/纳税人识别号|纳税人识别号)[:：]?\s*([0-9A-Z]{15,20})", flat
    )
    if ids:
        values.setdefault("buyer_tax_id", ids[0])
        if len(ids) > 1:
            values.setdefault("seller_tax_id", ids[1])
    # 合 计 ¥amount ¥tax
    sums = re.search(r"合\s*计\s*[¥￥]\s*(-?[\d,]+\.\d{2})\s*[¥￥]\s*(-?[\d,]+\.\d{2})", flat)
    if sums:
        values.setdefault("amount", sums.group(1))
        values.setdefault("tax", sums.group(2))
    for item in re.findall(r"\*[^*\n]{1,30}\*[^\s\n]{0,40}", flat)[:50]:
        if item not in invoice.items:
            invoice.items.append(item)
    _apply(invoice, values)


def _ofd(data: bytes, invoice: Invoice) -> None:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise OfficeError("not an OFD file") from None
    with archive:
        names = archive.namelist()
        # Custom data of OFD.xml: <ofd:CustomData Name="发票号码">…</ofd:CustomData>
        if "OFD.xml" in names:
            root = ET.fromstring(archive.read("OFD.xml"))
            values = {}
            for element in root.iter():
                if _local(element.tag) == "CustomData":
                    key = (element.get("Name") or "").strip()
                    for field_name, labels in _FIELDS.items():
                        if key in labels and element.text:
                            values[field_name] = element.text.strip()
            _apply(invoice, values)
        # An attached original XML.
        for name in names:
            if name.lower().endswith(".xml") and "/attachs/" in name.lower():
                try:
                    _from_xml(ET.fromstring(archive.read(name)), invoice)
                except ET.ParseError:
                    continue
        # The page text: TextCode elements of each page's content.
        text: list[str] = []
        for name in sorted(names):
            if re.search(r"Pages/Page_\d+/Content\.xml$", name):
                try:
                    root = ET.fromstring(archive.read(name))
                except ET.ParseError:
                    continue
                text.extend(
                    element.text or ""
                    for element in root.iter()
                    if _local(element.tag) == "TextCode"
                )
        if text:
            _from_text("\n".join(text), invoice)


def read_invoice(path: Path, label: str) -> Invoice:
    data = path.read_bytes()
    suffix = path.suffix.lower()
    invoice = Invoice(label, suffix.lstrip("."))
    if suffix == ".xml":
        try:
            _from_xml(ET.fromstring(data), invoice)
        except ET.ParseError as error:
            raise OfficeError(f"{label}: not well-formed XML ({error})") from None
    elif suffix == ".ofd":
        _ofd(data, invoice)
    elif suffix == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:3])
        except Exception as error:
            raise OfficeError(f"{label}: the PDF could not be read ({error})") from None
        _from_text(text, invoice)
        if not text.strip():
            invoice.problems.append("PDF 里没有文字（可能是扫描件），请用 XML 或 OFD 原件")
    else:
        raise OfficeError(f"{label}: invoices are read from .xml, .ofd and .pdf files")
    _check(invoice)
    return invoice


def _check(invoice: Invoice) -> None:
    if not invoice.number:
        invoice.problems.append("没有读到发票号码")
    if not invoice.total:
        invoice.problems.append("没有读到价税合计")
    if (
        invoice.amount
        and invoice.tax
        and invoice.total
        and Decimal(invoice.amount) + Decimal(invoice.tax) != Decimal(invoice.total)
    ):
        invoice.problems.append(
            f"金额 {invoice.amount} + 税额 {invoice.tax} ≠ 价税合计 {invoice.total}"
        )


def summarize(invoices: list[Invoice]) -> dict[str, Any]:
    """Totals, duplicates (the same number twice; an XML and its OFD count once)."""
    seen: dict[str, Invoice] = {}
    duplicates: list[dict[str, str]] = []
    unique: list[Invoice] = []
    for invoice in invoices:
        key = invoice.number or invoice.file
        if invoice.number and key in seen:
            first = seen[key]
            if Path(first.file).stem != Path(invoice.file).stem:
                duplicates.append(
                    {"number": invoice.number, "first": first.file, "again": invoice.file}
                )
            elif _RANK[invoice.format] < _RANK[first.format]:
                # One invoice in two forms: the XML original is the one kept.
                unique[unique.index(first)] = invoice
                seen[key] = invoice
            continue
        seen[key] = invoice
        unique.append(invoice)
    total = sum((Decimal(invoice.total) for invoice in unique if invoice.total), Decimal("0"))
    tax = sum((Decimal(invoice.tax) for invoice in unique if invoice.tax), Decimal("0"))
    amount = sum((Decimal(invoice.amount) for invoice in unique if invoice.amount), Decimal("0"))
    return {
        "count": len(unique),
        "amount": str(amount),
        "tax": str(tax),
        "total": str(total),
        "duplicates": duplicates,
        "with_problems": sum(1 for invoice in unique if invoice.problems),
        "unique": unique,
    }


__all__ = ["SUFFIXES", "Invoice", "read_invoice", "summarize"]
