"""Repair the text layer of PDFs written by Android's PdfDocument.

Noto Sans CJK draws many radicals (U+2E80-U+2FDF) and their ideographs (用 and ⽤, 长 and ⻓)
with one shared glyph. Skia's PDF writer maps each glyph back to the lowest code point that
uses it, so copying, searching or extracting text yields radicals: "⽤户" instead of "用户".
This module reads which ideograph shares each radical's glyph from the font the PDF was drawn
with and rewrites the ToUnicode maps; the pages themselves are untouched.
"""

from __future__ import annotations

import contextlib
import functools
import io
import re
import struct
import unicodedata
from pathlib import Path
from typing import Any, BinaryIO

# The font and face AndroidDocumentBridge.pdfFont draws with (Simplified Chinese face of the TTC).
NOTO_CJK = Path("/system/fonts/NotoSansCJK-Regular.ttc")
NOTO_CJK_SC_FACE = 2

_RADICALS = (0x2E80, 0x2FDF)
# Preferred replacements first: unified ideographs, extension A, supplementary planes, then the
# compatibility block.
_IDEOGRAPHS = ((0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0x20000, 0x3FFFF), (0xF900, 0xFAFF))


def _read(stream: BinaryIO, offset: int, size: int) -> bytes:
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("font table is truncated")
    return data


def _cmap_table(stream: BinaryIO, face: int) -> bytes:
    header = _read(stream, 0, 12)
    base = 0
    if header[:4] == b"ttcf":
        count = struct.unpack(">I", header[8:12])[0]
        if not 0 <= face < count:
            raise ValueError("font collection has no such face")
        base = struct.unpack(">I", _read(stream, 12 + 4 * face, 4))[0]
    tables = struct.unpack(">H", _read(stream, base + 4, 2))[0]
    directory = _read(stream, base + 12, 16 * tables)
    for index in range(tables):
        tag, _checksum, offset, length = struct.unpack(
            ">4sIII", directory[16 * index : 16 * index + 16]
        )
        if tag == b"cmap":
            return _read(stream, offset, length)
    raise ValueError("font has no cmap table")


def _cmap_groups(table: bytes) -> list[tuple[int, int, int]]:
    """(first code point, last code point, glyph of the first) runs of the best Unicode subtable."""
    count = struct.unpack(">H", table[2:4])[0]
    subtables: dict[tuple[int, int, int], int] = {}
    for index in range(count):
        platform, encoding, offset = struct.unpack(">HHI", table[4 + 8 * index : 12 + 8 * index])
        subtables[(platform, encoding, struct.unpack(">H", table[offset : offset + 2])[0])] = offset
    for key in ((3, 10, 12), (0, 4, 12), (0, 6, 12)):
        if key in subtables:
            offset = subtables[key]
            groups = struct.unpack(">I", table[offset + 12 : offset + 16])[0]
            return [
                struct.unpack(">III", table[offset + 16 + 12 * i : offset + 28 + 12 * i])
                for i in range(groups)
            ]
    for key in ((3, 1, 4), (0, 3, 4)):
        if key in subtables:
            return _format4_groups(table, subtables[key])
    raise ValueError("font has no Unicode cmap")


def _format4_groups(table: bytes, offset: int) -> list[tuple[int, int, int]]:
    segments = struct.unpack(">H", table[offset + 6 : offset + 8])[0] // 2
    ends = struct.unpack(f">{segments}H", table[offset + 14 : offset + 14 + 2 * segments])
    starts_at = offset + 16 + 2 * segments
    starts = struct.unpack(f">{segments}H", table[starts_at : starts_at + 2 * segments])
    deltas = struct.unpack(
        f">{segments}h", table[starts_at + 2 * segments : starts_at + 4 * segments]
    )
    ranges_at = starts_at + 4 * segments
    range_offsets = struct.unpack(f">{segments}H", table[ranges_at : ranges_at + 2 * segments])
    groups = []
    for index, (start, end, delta, range_offset) in enumerate(
        zip(starts, ends, deltas, range_offsets, strict=True)
    ):
        if start == 0xFFFF:
            continue
        for code in range(start, end + 1):
            if range_offset == 0:
                glyph = (code + delta) & 0xFFFF
            else:
                at = ranges_at + 2 * index + range_offset + 2 * (code - start)
                glyph = struct.unpack(">H", table[at : at + 2])[0]
                glyph = (glyph + delta) & 0xFFFF if glyph else 0
            if glyph:
                groups.append((code, code, glyph))
    return groups


def radical_replacements(groups: list[tuple[int, int, int]]) -> dict[int, int]:
    """Each radical whose glyph an ideograph also uses, mapped to that ideograph."""
    radical_glyphs: dict[int, int] = {}
    for first, last, glyph in groups:
        for code in range(max(first, _RADICALS[0]), min(last, _RADICALS[1]) + 1):
            radical_glyphs.setdefault(glyph + code - first, code)
    if not radical_glyphs:
        return {}
    shared: dict[int, int] = {}
    for low, high in _IDEOGRAPHS:
        for first, last, glyph in groups:
            for code in range(max(first, low), min(last, high) + 1):
                radical = radical_glyphs.get(glyph + code - first)
                if radical is not None and radical not in shared:
                    shared[radical] = code
    return shared


@functools.lru_cache(maxsize=1)
def _font_replacements(path: str, face: int) -> dict[int, int]:
    with open(path, "rb") as stream:
        return radical_replacements(_cmap_groups(_cmap_table(stream, face)))


def replacements(font: Path = NOTO_CJK, face: int = NOTO_CJK_SC_FACE) -> dict[int, int]:
    """Radical to ideograph pairs of the PDF font; Kangxi radicals by NFKC without the font."""
    found: dict[int, int] = {}
    for code in range(0x2F00, 0x2FD6):
        normalized = unicodedata.normalize("NFKC", chr(code))
        if len(normalized) == 1 and normalized != chr(code):
            found[code] = ord(normalized)
    with contextlib.suppress(OSError, ValueError, struct.error):
        found.update(_font_replacements(str(font), face))
    return found


_BLOCK = re.compile(rb"(\d+)\s+begin(bfchar|bfrange)(.*?)end\2", re.S)
_TOKEN = re.compile(rb"<([0-9A-Fa-f]*)>|\[|\]")


def _text(hex_code: bytes) -> str:
    return bytes.fromhex(hex_code.decode()).decode("utf-16-be")


def _mappings(block_kind: bytes, body: bytes) -> list[tuple[str, str]]:
    tokens = [
        match.group(1) if match.group(1) is not None else match.group(0)
        for match in _TOKEN.finditer(body)
    ]
    pairs: list[tuple[str, str]] = []
    position = 0
    if block_kind == b"bfchar":
        while position + 1 < len(tokens):
            pairs.append((tokens[position].decode(), _text(tokens[position + 1])))
            position += 2
        return pairs
    while position + 2 < len(tokens):
        low, high = tokens[position], tokens[position + 1]
        width, first, last = len(low), int(low, 16), int(high, 16)
        if tokens[position + 2] == b"[":
            end = tokens.index(b"]", position + 3)
            targets = [_text(item) for item in tokens[position + 3 : end]]
            position = end + 1
        else:
            start = _text(tokens[position + 2])
            # A range increments the last character of its destination.
            targets = [start[:-1] + chr(ord(start[-1]) + step) for step in range(last - first + 1)]
            position += 3
        for step, target in enumerate(targets[: last - first + 1]):
            pairs.append((format(first + step, f"0{width}X"), target))
    return pairs


def repair_cmap(data: bytes, table: dict[int, int]) -> bytes | None:
    """The CMap with radical targets replaced, or None when nothing needed changing."""
    blocks = list(_BLOCK.finditer(data))
    if not blocks:
        return None
    pairs = [pair for block in blocks for pair in _mappings(block.group(2), block.group(3))]
    fixed = [
        (source, "".join(chr(table.get(ord(char), ord(char))) for char in target))
        for source, target in pairs
    ]
    if fixed == pairs:
        return None
    lines = []
    for start in range(0, len(fixed), 100):
        chunk = fixed[start : start + 100]
        lines.append(f"{len(chunk)} beginbfchar")
        lines.extend(
            f"<{source}> <{target.encode('utf-16-be').hex().upper()}>" for source, target in chunk
        )
        lines.append("endbfchar")
    mapping = "\n".join(lines).encode()
    return data[: blocks[0].start()] + mapping + data[blocks[-1].end() :]


def _fonts(resources: Any, seen: set[int]) -> list[Any]:
    found = []
    if resources is None:
        return found
    resources = resources.get_object()
    if id(resources) in seen:
        return found
    seen.add(id(resources))
    fonts = resources.get("/Font")
    if fonts is not None:
        found.extend(font.get_object() for font in fonts.get_object().values())
    xobjects = resources.get("/XObject")
    if xobjects is not None:
        for xobject in xobjects.get_object().values():
            found.extend(_fonts(xobject.get_object().get("/Resources"), seen))
    for font in list(found):
        found.extend(_fonts(font.get("/Resources"), seen))
    return found


def repair_pdf(data: bytes, table: dict[int, int] | None = None) -> bytes | None:
    """The PDF with its ToUnicode maps repaired, or None when it needed no change."""
    from pypdf import PdfWriter
    from pypdf.generic import StreamObject

    table = replacements() if table is None else table
    if not table:
        return None
    writer = PdfWriter(clone_from=io.BytesIO(data))
    changed, done, seen = False, set(), set()
    for page in writer.pages:
        for font in _fonts(page.get("/Resources"), seen):
            stream = font.get("/ToUnicode")
            stream = stream.get_object() if stream is not None else None
            if not isinstance(stream, StreamObject) or id(stream) in done:
                continue
            done.add(id(stream))
            repaired = repair_cmap(stream.get_data(), table)
            if repaired is not None:
                stream.set_data(repaired)
                changed = True
    if not changed:
        return None
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
