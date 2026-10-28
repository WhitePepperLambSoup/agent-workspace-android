"""SyncTeX: from a source line to the place in the PDF (forward), and from a point in the PDF to
the source line (inverse), read from the ``.synctex.gz`` file the engine writes.

Coordinates are PDF points (1/72 in) from the top-left corner of the page.
"""

from __future__ import annotations

import gzip
import os
import re
from dataclasses import dataclass
from pathlib import Path

MAX_SYNCTEX_BYTES = 200 * 1024 * 1024
_RECORD = re.compile(
    r"^([(\[hvkgx$])(\d+),(\d+):(-?\d+),(-?\d+)(?::(-?\d+)(?:,(-?\d+))?(?:,(-?\d+))?)?"
)


@dataclass(frozen=True)
class PdfBox:
    page: int
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "page": self.page,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "width": round(self.width, 2),
            "height": round(self.height, 2),
        }


@dataclass(frozen=True)
class _Record:
    kind: str
    tag: int
    line: int
    x: float
    y: float
    width: float
    height: float
    depth: float


class SyncTex:
    """One document's SyncTeX data."""

    def __init__(self, text: str, base: Path | None = None) -> None:
        self.inputs: dict[int, str] = {}
        self.pages: dict[int, list[_Record]] = {}
        unit, magnification, x_offset, y_offset = 1.0, 1000.0, 0.0, 0.0
        page: list[_Record] | None = None
        scale = 0.0
        for line in text.splitlines():
            if line.startswith("Input:"):
                tag, _, path = line[6:].partition(":")
                if tag.isdigit():
                    self.inputs[int(tag)] = _absolute(path, base)
                continue
            if page is None:
                if line.startswith("Unit:"):
                    unit = _number(line[5:], 1.0)
                elif line.startswith("Magnification:"):
                    magnification = _number(line[14:], 1000.0)
                elif line.startswith("X Offset:"):
                    x_offset = _number(line[9:], 0.0)
                elif line.startswith("Y Offset:"):
                    y_offset = _number(line[9:], 0.0)
                if line.startswith("{") and line[1:].isdigit():
                    scale = unit * magnification / 1000.0 / 65536.0 * 72.0 / 72.27
                    page = self.pages.setdefault(int(line[1:]), [])
                continue
            if line.startswith("}"):
                page = None
                continue
            match = _RECORD.match(line)
            if match is None:
                continue
            kind, tag, number, x, y, width, height, depth = match.groups()
            if number == "0":
                continue
            page.append(
                _Record(
                    kind,
                    int(tag),
                    int(number),
                    (int(x) + x_offset) * scale,
                    (int(y) + y_offset) * scale,
                    int(width or 0) * scale,
                    int(height or 0) * scale,
                    int(depth or 0) * scale,
                )
            )

    def _tags_for(self, file: Path) -> set[int]:
        wanted = _key(str(file))
        tags = {tag for tag, path in self.inputs.items() if _key(path) == wanted}
        if tags:
            return tags
        name = file.name.lower()
        named = {tag for tag, path in self.inputs.items() if Path(path).name.lower() == name}
        return named if len(named) == 1 else set()

    def forward(self, file: Path, line: int) -> PdfBox | None:
        """Where a source line is typeset: the first page showing it, and the lines' box."""
        tags = self._tags_for(file)
        if not tags:
            return None
        best: tuple[int, int, list[_Record]] | None = None
        for number, records in sorted(self.pages.items()):
            for record in records:
                if record.tag not in tags:
                    continue
                distance = record.line - line
                if distance < 0:
                    continue  # a later line is the closest stand-in for a line not typeset
                if best is None or distance < best[0]:
                    best = (distance, number, [record])
                elif distance == best[0] and number == best[1]:
                    best[2].append(record)
            if best is not None and best[0] == 0:
                break
        if best is None:
            return None
        page_records = self.pages[best[1]]
        # pdfTeX files a paragraph's line boxes under the line where the paragraph ended, and a
        # small box (a citation's) may carry the line: show the whole lines holding its nodes.
        boxes: list[_Record] = []
        for record in best[2]:
            box = _line_box(page_records, record) if record.kind != "[" else None
            if box is not None and box not in boxes:
                boxes.append(box)
        if not boxes:
            boxes = [record for record in best[2] if record.kind == "("]
        # A box around a whole frame or float also carries the line: keep the line-sized ones.
        records = boxes or best[2]
        lowest = min(record.height + record.depth for record in records)
        records = [
            record for record in records if record.height + record.depth <= max(lowest * 4, 30.0)
        ] or records
        left = min(record.x for record in records)
        top = min(record.y - record.height for record in records)
        right = max(record.x + record.width for record in records)
        bottom = max(record.y + record.depth for record in records)
        return PdfBox(best[1], left, top, max(right - left, 0.0), max(bottom - top, 1.0))

    def inverse(self, page: int, x: float, y: float) -> tuple[str, int] | None:
        """The source file and line typeset nearest a point of a page: the line box under the
        point, then the node of that line just left of it."""
        records = self.pages.get(page, ())
        best: tuple[tuple[float, float], _Record] | None = None
        for record in records:
            top, bottom = record.y - record.height, record.y + record.depth
            dy = top - y if y < top else y - bottom if y > bottom else 0.0
            if record.width > 0:
                right = record.x + record.width
                dx = record.x - x if x < record.x else x - right if x > right else 0.0
            else:
                dx = abs(x - record.x)
            # A vertical box spans many lines: only a last resort.
            penalty = 1000.0 if record.kind in "[v" else 0.0
            score = (dy * 10 + dx * 0.1 + penalty, record.width * (record.height + record.depth))
            if best is None or score < best[0]:
                best = (score, record)
        if best is None:
            return None
        chosen = best[1]
        if chosen.kind == "(":
            nodes = [
                record
                for record in records
                if record.kind in "hxkg$"
                and abs(record.y - chosen.y) < 0.5
                and chosen.x - 0.5 <= record.x <= chosen.x + chosen.width + 0.5
            ]
            # Nodes filed under the box's own line (where its paragraph ended) are the least
            # telling; the others name the line their text came from.
            own = (chosen.tag, chosen.line)
            nodes = [record for record in nodes if (record.tag, record.line) != own] or nodes
            before = [record for record in nodes if record.x <= x + 0.5]
            if before:
                chosen = max(before, key=lambda record: record.x)
            elif nodes:
                chosen = min(nodes, key=lambda record: record.x)
        if chosen.tag not in self.inputs:
            return None
        return self.inputs[chosen.tag], chosen.line


def _line_box(records: list[_Record], node: _Record) -> _Record | None:
    """The horizontal line box a node sits on (same baseline, inside its width)."""
    for record in records:
        if (
            record.kind == "("
            and abs(record.y - node.y) < 0.5
            and record.x - 0.5 <= node.x <= record.x + record.width + 0.5
        ):
            return record
    return None


def _number(text: str, default: float) -> float:
    try:
        return float(text.strip())
    except ValueError:
        return default


def _absolute(path: str, base: Path | None) -> str:
    candidate = Path(path)
    if not candidate.is_absolute() and base is not None:
        candidate = base / candidate
    return os.path.normpath(str(candidate))


def _key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path)).replace("\\", "/")


def synctex_path(build: Path, stem: str) -> Path | None:
    for name in (f"{stem}.synctex.gz", f"{stem}.synctex"):
        candidate = build / name
        if candidate.is_file():
            return candidate
    return None


def load(path: Path, base: Path | None = None) -> SyncTex:
    """Read a ``.synctex.gz`` (or plain ``.synctex``) file; paths are resolved against ``base``."""
    if path.stat().st_size > MAX_SYNCTEX_BYTES:
        raise ValueError("synctex file too large")
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as stream:
            data = stream.read(MAX_SYNCTEX_BYTES * 4)
    else:
        data = path.read_bytes()
    return SyncTex(data.decode("utf-8", errors="replace"), base)
