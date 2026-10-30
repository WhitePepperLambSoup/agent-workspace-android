"""Office Open XML packages, edited as element trees without losing what Office relies on.

An XML parser rewrites namespace declarations to the ones a part still uses, and Office files
name prefixes in attributes (``mc:Ignorable="w14 wp14"``): a part written back with fewer
declarations is a file Word calls damaged. Parts are parsed with every prefix they declare
registered, and written back with their original root start tag (plus any declaration a change
added), so prefixes and declarations stay as they were.
"""

from __future__ import annotations

import contextlib
import io
import re
import threading
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
PACKAGE_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
XML_HEADER = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
MAX_PART_BYTES = 64 * 1024 * 1024
MAX_PACKAGE_BYTES = 200 * 1024 * 1024

_START_TAG = re.compile(r"<(?![?!])[^>]*>", re.DOTALL)
_DECLARATION = re.compile(r'\sxmlns(?::([\w.-]+))?="([^"]*)"')
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_REGISTER = threading.Lock()
_STANDARD = {
    "w": W,
    "r": R,
    "a": A,
    "p": P,
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "x14ac": "http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac",
}


class OfficeError(ValueError):
    """Not the Office file it should be, or a change that cannot be made to it."""


def clean(text: str) -> str:
    """Text without the control characters XML 1.0 refuses."""
    return _CONTROL.sub("", text)


def q(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def _register(prefix: str, uri: str) -> None:
    if not prefix or re.fullmatch(r"ns\d+", prefix):
        return
    with _REGISTER, contextlib.suppress(ValueError):
        ET.register_namespace(prefix, uri)


for _prefix, _uri in _STANDARD.items():
    _register(_prefix, _uri)


@dataclass
class XmlPart:
    root: ET.Element
    start_tag: str
    default: str | None = None

    @classmethod
    def parse(cls, data: bytes) -> XmlPart:
        default = None
        try:
            for _event, (prefix, uri) in ET.iterparse(io.BytesIO(data), events=("start-ns",)):
                if prefix:
                    _register(prefix, uri)
                elif default is None:
                    default = uri
            root = ET.fromstring(data)
        except ET.ParseError as error:
            raise OfficeError(f"a part of the file is not well-formed XML: {error}") from None
        text = data.decode("utf-8", errors="replace")
        match = _START_TAG.search(text)
        start = match.group(0) if match else ""
        return cls(root, start, default)

    def to_bytes(self) -> bytes:
        # Elements of the default namespace are written without a prefix, under the original
        # root tag's xmlns="…". (ElementTree's default_namespace option refuses the plain
        # attributes spreadsheets are full of.)
        renamed: list[tuple[ET.Element, str]] = []
        if self.default:
            prefix = f"{{{self.default}}}"
            for element in self.root.iter():
                if isinstance(element.tag, str) and element.tag.startswith(prefix):
                    renamed.append((element, element.tag))
                    element.tag = element.tag[len(prefix) :]
        try:
            text = ET.tostring(self.root, encoding="unicode")
        finally:
            for element, tag in renamed:
                element.tag = tag
        if self.default and not self.start_tag:
            text = re.sub(r"^<([^\s>/]+)", rf'<\1 xmlns="{self.default}"', text, count=1)
        match = _START_TAG.match(text)
        if match and self.start_tag:
            written = match.group(0)
            original = self.start_tag
            have = {prefix or "" for prefix, _ in _DECLARATION.findall(original)}
            extra = "".join(
                f' xmlns{":" + prefix if prefix else ""}="{uri}"'
                for prefix, uri in _DECLARATION.findall(written)
                if (prefix or "") not in have
            )
            if extra:
                closing = "/>" if original.endswith("/>") else ">"
                original = original[: -len(closing)] + extra + closing
            if written.endswith("/>") and not original.endswith("/>"):
                original = original[:-1] + "/>"
            text = original + text[match.end() :]
        return (XML_HEADER + text).encode("utf-8")


@dataclass
class Package:
    """The parts of a zip package, in their order; changed parts are written back."""

    parts: dict[str, bytes] = field(default_factory=dict)
    _xml: dict[str, XmlPart] = field(default_factory=dict)

    @classmethod
    def read(cls, data: bytes) -> Package:
        if len(data) > MAX_PACKAGE_BYTES:
            raise OfficeError("the file is larger than 200 MB")
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise OfficeError("not an Office file (.docx, .xlsx or .pptx)") from None
        package = cls()
        total = 0
        with archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                if info.file_size > MAX_PART_BYTES:
                    raise OfficeError(f"{info.filename} is larger than 64 MB")
                total += info.file_size
                if total > MAX_PACKAGE_BYTES:
                    raise OfficeError("the file unpacks to more than 200 MB")
                package.parts[info.filename] = archive.read(info)
        if "[Content_Types].xml" not in package.parts:
            raise OfficeError("not an Office file: it has no [Content_Types].xml")
        return package

    def has(self, name: str) -> bool:
        return name in self.parts or name in self._xml

    def xml(self, name: str) -> XmlPart:
        if name not in self._xml:
            if name not in self.parts:
                raise OfficeError(f"the file has no {name}")
            self._xml[name] = XmlPart.parse(self.parts[name])
        return self._xml[name]

    def set_xml(self, name: str, part: XmlPart) -> None:
        self._xml[name] = part
        self.parts.setdefault(name, b"")

    def text(self, name: str) -> str:
        return self.parts[name].decode("utf-8")

    def set(self, name: str, data: bytes | str) -> None:
        self._xml.pop(name, None)
        self.parts[name] = data.encode("utf-8") if isinstance(data, str) else data

    def remove(self, name: str) -> None:
        self._xml.pop(name, None)
        self.parts.pop(name, None)

    def names(self, prefix: str = "") -> Iterator[str]:
        return (name for name in list(self.parts) if name.startswith(prefix))

    def to_bytes(self) -> bytes:
        for name, part in self._xml.items():
            self.parts[name] = part.to_bytes()
        self._xml.clear()
        buffer = io.BytesIO()
        order = [
            "[Content_Types].xml",
            *[name for name in self.parts if name != "[Content_Types].xml"],
        ]
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in order:
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, self.parts[name])
        return buffer.getvalue()

    # ---- content types and relationships (simple parts, edited as text)

    def content_type(self, part: str, kind: str) -> None:
        """Declare a part's content type (an Override)."""
        text = self.text("[Content_Types].xml")
        name = "/" + part.lstrip("/")
        if f'PartName="{name}"' in text:
            return
        entry = f'<Override PartName="{name}" ContentType="{kind}"/>'
        self.set("[Content_Types].xml", text.replace("</Types>", entry + "</Types>"))

    def default_type(self, extension: str, kind: str) -> None:
        text = self.text("[Content_Types].xml")
        if re.search(rf'<Default Extension="{re.escape(extension)}"', text, re.IGNORECASE):
            return
        entry = f'<Default Extension="{extension}" ContentType="{kind}"/>'
        self.set("[Content_Types].xml", text.replace("</Types>", entry + "</Types>", 1))

    def drop_content_type(self, part: str) -> None:
        text = self.text("[Content_Types].xml")
        name = re.escape("/" + part.lstrip("/"))
        self.set("[Content_Types].xml", re.sub(rf'<Override PartName="{name}"[^>]*/>', "", text))

    @staticmethod
    def rels_name(part: str) -> str:
        folder, _, name = part.rpartition("/")
        return f"{folder}/_rels/{name}.rels" if folder else f"_rels/{name}.rels"

    def relationships(self, part: str) -> list[tuple[str, str, str]]:
        """(id, type, target) of a part's relationships."""
        name = self.rels_name(part)
        if name not in self.parts:
            return []
        text = self.text(name)
        out = []
        for match in re.finditer(r"<Relationship\b([^>]*)/?>", text):
            attributes = dict(re.findall(r'(\w+)="([^"]*)"', match.group(1)))
            out.append(
                (attributes.get("Id", ""), attributes.get("Type", ""), attributes.get("Target", ""))
            )
        return out

    def add_relationship(self, part: str, kind: str, target: str, external: bool = False) -> str:
        """A new relationship of the part; returns its id (an existing one to the same target)."""
        name = self.rels_name(part)
        existing = self.relationships(part)
        for rid, rtype, rtarget in existing:
            if rtype.endswith("/" + kind) and rtarget == target:
                return rid
        taken = {rid for rid, _, _ in existing}
        number = len(existing) + 1
        while f"rId{number}" in taken:
            number += 1
        rid = f"rId{number}"
        entry = (
            f'<Relationship Id="{rid}" Type="{REL_TYPE}/{kind}" Target="{escape_attr(target)}"'
            + (' TargetMode="External"' if external else "")
            + "/>"
        )
        if name in self.parts:
            text = self.text(name).replace("</Relationships>", entry + "</Relationships>")
        else:
            text = f'{XML_HEADER}<Relationships xmlns="{PACKAGE_RELS}">{entry}</Relationships>'
        self.set(name, text)
        return rid

    def remove_relationship(self, part: str, rid: str) -> None:
        name = self.rels_name(part)
        if name in self.parts:
            text = re.sub(
                rf'<Relationship\b[^>]*\bId="{re.escape(rid)}"[^>]*/>', "", self.text(name)
            )
            self.set(name, text)

    @staticmethod
    def resolve(part: str, target: str) -> str:
        """A relationship target as a part name."""
        if target.startswith("/"):
            return target.lstrip("/")
        folder = part.rpartition("/")[0]
        segments = [*folder.split("/"), *target.split("/")] if folder else target.split("/")
        out: list[str] = []
        for segment in segments:
            if segment == "..":
                if out:
                    out.pop()
            elif segment and segment != ".":
                out.append(segment)
        return "/".join(out)


def escape_attr(text: str) -> str:
    return (
        clean(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def escape_text(text: str) -> str:
    return clean(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def zip_parts(parts: Iterable[tuple[str, str | bytes]]) -> bytes:
    """A new package from (name, content) pairs; [Content_Types].xml goes first."""
    items = list(parts)
    items.sort(key=lambda item: item[0] != "[Content_Types].xml")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in items:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content.encode("utf-8") if isinstance(content, str) else content)
    return buffer.getvalue()


def content_types(defaults: dict[str, str], overrides: dict[str, str]) -> str:
    rels = "application/vnd.openxmlformats-package.relationships+xml"
    items = [
        f'<Default Extension="rels" ContentType="{rels}"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        *(f'<Default Extension="{ext}" ContentType="{kind}"/>' for ext, kind in defaults.items()),
        *(
            f'<Override PartName="/{part}" ContentType="{kind}"/>'
            for part, kind in overrides.items()
        ),
    ]
    return f'{XML_HEADER}<Types xmlns="{CONTENT_TYPES}">{"".join(items)}</Types>'


def relationships(entries: list[tuple[str, str, str]]) -> str:
    """A relationships part from (id, type name, target)."""
    items = "".join(
        f'<Relationship Id="{rid}" Type="{REL_TYPE}/{kind}" Target="{escape_attr(target)}"/>'
        for rid, kind, target in entries
    )
    return f'{XML_HEADER}<Relationships xmlns="{PACKAGE_RELS}">{items}</Relationships>'


__all__ = [
    "XML_HEADER",
    "XML_SPACE",
    "A",
    "OfficeError",
    "P",
    "Package",
    "R",
    "S",
    "W",
    "XmlPart",
    "clean",
    "content_types",
    "escape_attr",
    "escape_text",
    "q",
    "relationships",
    "zip_parts",
]
