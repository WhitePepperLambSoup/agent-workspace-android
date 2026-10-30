# ruff: noqa: E501, RUF001 -- the PowerShell scripts keep their statements on one line each; page ranges may use Chinese punctuation.
"""PDF pages merged, split, picked, deleted and rotated; page numbers and watermarks stamped;
pictures put on pages; scanned pages given a text layer so they can be searched and copied.

Text is drawn in Helvetica, or for Chinese in the standard CJK font STSong-Light (Adobe-GB1),
which PDF readers supply themselves, so nothing is embedded.
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PageObject, PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    StreamObject,
    TextStringObject,
)

from agent_workspace.office.ooxml import OfficeError

MAX_PAGES = 5000
_CREATE_NO_WINDOW = 0x08000000
A4 = (595.276, 841.89)
_HELVETICA_WIDTHS = {
    " ": 278,
    "-": 333,
    "/": 278,
    "—": 1000,
    "(": 333,
    ")": 333,
    ".": 278,
    ",": 278,
    ":": 278,
}


def read(data: bytes, password: str = "") -> PdfReader:
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as error:
        raise OfficeError(f"the PDF could not be read: {error}") from None
    if reader.is_encrypted:
        try:
            if not reader.decrypt(password):
                raise OfficeError("the PDF is protected by a password")
        except Exception as error:
            raise OfficeError(f"the PDF is protected by a password ({error})") from None
    if len(reader.pages) > MAX_PAGES:
        raise OfficeError("the PDF has more than 5000 pages")
    return reader


def _bytes(writer: PdfWriter) -> bytes:
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def parse_pages(spec: str, count: int) -> list[int]:
    """Pages written like "1-3,5,8-" (1-based, "-3" for the first three, "8-" to the end) as
    0-based indexes in the order given; "all" for every page; "odd"/"even"."""
    text = (
        spec.strip()
        .replace("，", ",")
        .replace("～", "-")
        .replace("~", "-")
        .replace("—", "-")
        .lower()
    )
    if text in {"", "all", "全部"}:
        return list(range(count))
    if text in {"odd", "奇数"}:
        return list(range(0, count, 2))
    if text in {"even", "偶数"}:
        return list(range(1, count, 2))
    out: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(r"(\d*)\s*-\s*(\d*)", part)
        if match:
            start = int(match.group(1)) if match.group(1) else 1
            end = int(match.group(2)) if match.group(2) else count
        elif part.isdigit():
            start = end = int(part)
        else:
            raise OfficeError(f"cannot read the pages {part!r}; write them like 1-3,5,8-")
        if start < 1 or end > count or start > end:
            raise OfficeError(f"pages {part} are outside 1-{count}")
        out.extend(range(start - 1, end))
    return out


def merge(documents: list[tuple[bytes, str]]) -> bytes:
    """The documents' pages (each with its page spec) one after another."""
    writer = PdfWriter()
    for data, pages in documents:
        reader = read(data)
        for index in parse_pages(pages, len(reader.pages)):
            writer.add_page(reader.pages[index])
    return _bytes(writer)


def pick(data: bytes, pages: str) -> bytes:
    reader = read(data)
    writer = PdfWriter()
    for index in parse_pages(pages, len(reader.pages)):
        writer.add_page(reader.pages[index])
    return _bytes(writer)


def delete(data: bytes, pages: str) -> bytes:
    reader = read(data)
    removed = set(parse_pages(pages, len(reader.pages)))
    if len(removed) >= len(reader.pages):
        raise OfficeError("that would delete every page")
    writer = PdfWriter()
    for index, page in enumerate(reader.pages):
        if index not in removed:
            writer.add_page(page)
    return _bytes(writer)


def split(
    data: bytes, ranges: list[str] | None = None, every: int | None = None
) -> list[tuple[str, bytes]]:
    """Parts by page ranges ("1-3", "4-"), or of ``every`` pages each; named by their pages."""
    reader = read(data)
    count = len(reader.pages)
    if every:
        ranges = [
            f"{start}-{min(start + every - 1, count)}" for start in range(1, count + 1, every)
        ]
    if not ranges:
        ranges = [str(number) for number in range(1, count + 1)]
    out = []
    for spec in ranges:
        indexes = parse_pages(spec, count)
        writer = PdfWriter()
        for index in indexes:
            writer.add_page(reader.pages[index])
        label = f"{indexes[0] + 1}-{indexes[-1] + 1}" if len(indexes) > 1 else f"{indexes[0] + 1}"
        out.append((label, _bytes(writer)))
    return out


def rotate(data: bytes, pages: str, angle: int) -> bytes:
    if angle % 90:
        raise OfficeError("pages turn by 90, 180 or 270 degrees")
    reader = read(data)
    chosen = set(parse_pages(pages, len(reader.pages)))
    writer = PdfWriter()
    for index, page in enumerate(reader.pages):
        added = writer.add_page(page)
        if index in chosen:
            added.rotate(angle)
    return _bytes(writer)


# ---- text on pages -------------------------------------------------------------------------------


def _cjk(text: str) -> bool:
    return any(ord(char) > 0xFF for char in text)


def _fonts() -> DictionaryObject:
    descriptor = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/FontDescriptor"),
            NameObject("/FontName"): NameObject("/STSong-Light"),
            NameObject("/Flags"): NumberObject(6),
            NameObject("/FontBBox"): ArrayObject(
                [NumberObject(-25), NumberObject(-254), NumberObject(1000), NumberObject(880)]
            ),
            NameObject("/ItalicAngle"): NumberObject(0),
            NameObject("/Ascent"): NumberObject(880),
            NameObject("/Descent"): NumberObject(-120),
            NameObject("/CapHeight"): NumberObject(880),
            NameObject("/StemV"): NumberObject(93),
        }
    )
    descendant = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/CIDFontType0"),
            NameObject("/BaseFont"): NameObject("/STSong-Light"),
            NameObject("/CIDSystemInfo"): DictionaryObject(
                {
                    NameObject("/Registry"): TextStringObject("Adobe"),
                    NameObject("/Ordering"): TextStringObject("GB1"),
                    NameObject("/Supplement"): NumberObject(4),
                }
            ),
            NameObject("/FontDescriptor"): descriptor,
            NameObject("/DW"): NumberObject(1000),
            # The Latin characters (CIDs 1-95) are half as wide.
            NameObject("/W"): ArrayObject([NumberObject(1), NumberObject(95), NumberObject(500)]),
        }
    )
    chinese = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type0"),
            NameObject("/BaseFont"): NameObject("/STSong-Light-UniGB-UCS2-H"),
            NameObject("/Encoding"): NameObject("/UniGB-UCS2-H"),
            NameObject("/DescendantFonts"): ArrayObject([descendant]),
        }
    )
    latin = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    return DictionaryObject({NameObject("/AWCJK"): chinese, NameObject("/AWLatin"): latin})


def _encode(text: str) -> tuple[str, str, float]:
    """(font, PDF string operand, width in 1/1000 em)."""
    if _cjk(text):
        units = sum(500 if ord(char) < 0x80 else 1000 for char in text)
        encoded = "".join(f"{ord(char):04X}" for char in text if ord(char) <= 0xFFFF)
        return "/AWCJK", f"<{encoded}>", units
    data = text.replace("—", "\x97").encode("cp1252", errors="replace")
    units = sum(_HELVETICA_WIDTHS.get(char, 556) for char in text)
    return "/AWLatin", "<" + data.hex().upper() + ">", units


def _overlay(
    width: float, height: float, content: str, transparent: float | None = None
) -> PageObject:
    page = PageObject.create_blank_page(width=width, height=height)
    resources = DictionaryObject({NameObject("/Font"): _fonts()})
    if transparent is not None:
        resources[NameObject("/ExtGState")] = DictionaryObject(
            {
                NameObject("/AWGS"): DictionaryObject(
                    {
                        NameObject("/Type"): NameObject("/ExtGState"),
                        NameObject("/ca"): FloatObject(transparent),
                        NameObject("/CA"): FloatObject(transparent),
                    }
                )
            }
        )
    page[NameObject("/Resources")] = resources
    stream = DecodedStreamObject()
    stream.set_data(content.encode("latin-1"))
    page[NameObject("/Contents")] = stream
    return page


def _box(page: PageObject) -> tuple[float, float, float, float]:
    box = page.mediabox
    return float(box.left), float(box.bottom), float(box.width), float(box.height)


def page_numbers(
    data: bytes,
    pattern: str = "— {n} —",
    position: str = "bottom-center",
    start: int = 1,
    size: float = 10.5,
    pages: str = "all",
    skip_first: bool = False,
) -> bytes:
    """Numbers stamped on the pages: pattern with {n} and {total}; position top/bottom and
    left/center/right, or "outside" (right on odd pages, left on even ones, as official documents)."""
    reader = read(data)
    writer = PdfWriter(clone_from=reader)
    chosen = parse_pages(pages, len(reader.pages))
    if skip_first and chosen and chosen[0] == 0:
        chosen = chosen[1:]
    total = len(chosen)
    for number, index in enumerate(chosen, start=start):
        page = writer.pages[index]
        left, bottom, width, height = _box(page)
        text = pattern.replace("{n}", str(number)).replace("{total}", str(total + start - 1))
        font, operand, units = _encode(text)
        text_width = units * size / 1000
        margin = 36
        vertical, _, horizontal = position.partition("-")
        horizontal = horizontal or "center"
        if horizontal == "outside":
            # Odd pages (1st, 3rd … of the file) on the right, even ones on the left.
            horizontal = "right" if index % 2 == 0 else "left"
        x = {"left": margin, "right": width - margin - text_width}.get(
            horizontal, (width - text_width) / 2
        )
        y = height - margin if vertical == "top" else margin - size / 2 + 6
        content = (
            f"q BT {font} {size:.2f} Tf 0 g {left + x:.2f} {bottom + y:.2f} Td {operand} Tj ET Q"
        )
        page.merge_page(_overlay(float(page.mediabox.width), float(page.mediabox.height), content))
    return _bytes(writer)


def watermark(
    data: bytes,
    text: str,
    size: float = 54,
    opacity: float = 0.15,
    angle: float = 45,
    pages: str = "all",
    gray: float = 0.3,
) -> bytes:
    reader = read(data)
    writer = PdfWriter(clone_from=reader)
    font, operand, units = _encode(text)
    radians = math.radians(angle)
    cos, sin = math.cos(radians), math.sin(radians)
    for index in parse_pages(pages, len(reader.pages)):
        page = writer.pages[index]
        left, bottom, width, height = _box(page)
        text_width = units * size / 1000
        # Centred: move back half the text along its direction.
        x = left + width / 2 - cos * text_width / 2 + sin * size / 3
        y = bottom + height / 2 - sin * text_width / 2 - cos * size / 3
        content = (
            f"q /AWGS gs {gray:.2f} g BT {font} {size:.2f} Tf "
            f"{cos:.4f} {sin:.4f} {-sin:.4f} {cos:.4f} {x:.2f} {y:.2f} Tm {operand} Tj ET Q"
        )
        page.merge_page(_overlay(width, height, content, transparent=max(0.02, min(1.0, opacity))))
    return _bytes(writer)


def compress(data: bytes) -> bytes:
    reader = read(data)
    writer = PdfWriter(clone_from=reader)
    for page in writer.pages:
        try:
            page.compress_content_streams()
        except Exception:
            continue
    writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
    return _bytes(writer)


def info(data: bytes) -> dict[str, object]:
    reader = read(data)
    sizes = []
    scanned = 0
    for page in reader.pages[:200]:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        sizes.append(f"{width / 72 * 25.4:.0f}×{height / 72 * 25.4:.0f} mm")
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if len(text.strip()) < 20:
            scanned += 1
    metadata: Any = reader.metadata or {}
    return {
        "pages": len(reader.pages),
        "page_sizes": sorted(set(sizes)),
        "pages_without_text": scanned,
        "title": str(metadata.get("/Title", "") or ""),
        "author": str(metadata.get("/Author", "") or ""),
    }


# ---- pictures --------------------------------------------------------------------------------


@dataclass
class Jpeg:
    data: bytes
    width: int
    height: int
    components: int


def jpeg_info(data: bytes) -> Jpeg | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        length = struct.unpack(">H", data[index + 2 : index + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", data[index + 5 : index + 9])
            components = data[index + 9]
            return Jpeg(data, width, height, components)
        index += 2 + length
    return None


_TO_JPEG = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Drawing
$request = $env:AGENT_WORKSPACE_IMAGE_REQUEST | ConvertFrom-Json
foreach ($item in $request.items) {
  $image = [System.Drawing.Image]::FromFile($item.source)
  try {
    $bitmap = New-Object System.Drawing.Bitmap $image.Width, $image.Height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.Clear([System.Drawing.Color]::White)
    $graphics.DrawImage($image, 0, 0, $image.Width, $image.Height)
    $graphics.Dispose()
    $codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
    $parameters = New-Object System.Drawing.Imaging.EncoderParameters 1
    $parameters.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality), 90L
    $bitmap.Save($item.target, $codec, $parameters)
    $bitmap.Dispose()
  } finally { $image.Dispose() }
}
'ok'
"""


def to_jpeg(paths: list[Path], folder: Path) -> list[Path]:
    """Pictures (PNG, BMP, GIF, TIFF) as JPEG files on white, with Windows' own imaging."""
    if sys.platform != "win32":
        raise OfficeError("pictures other than JPEG are converted on Windows only")
    folder.mkdir(parents=True, exist_ok=True)
    items = [
        {"source": str(path), "target": str(folder / f"{index}.jpg")}
        for index, path in enumerate(paths)
    ]
    environment = dict(os.environ)
    environment["AGENT_WORKSPACE_IMAGE_REQUEST"] = json.dumps({"items": items})
    powershell = shutil.which("powershell") or "powershell"
    done = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            _TO_JPEG,
        ],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        creationflags=_CREATE_NO_WINDOW,
        check=False,
    )
    if done.returncode != 0:
        raise OfficeError(
            f"the pictures could not be converted: {(done.stderr or '').strip()[-300:]}"
        )
    return [Path(item["target"]) for item in items]


def images_to_pdf(images: list[Jpeg], page: str = "a4", margin: float = 28.35) -> bytes:
    """One picture per page: on A4 (portrait or landscape to suit), or a page its own size."""
    writer = PdfWriter()
    for number, image in enumerate(images):
        pixels_w, pixels_h = image.width, image.height
        if page == "image":
            width, height = pixels_w * 72 / 150, pixels_h * 72 / 150
            draw_w, draw_h, x, y = width, height, 0.0, 0.0
        else:
            width, height = A4 if pixels_h >= pixels_w else (A4[1], A4[0])
            scale = min((width - 2 * margin) / pixels_w, (height - 2 * margin) / pixels_h)
            draw_w, draw_h = pixels_w * scale, pixels_h * scale
            x, y = (width - draw_w) / 2, (height - draw_h) / 2
        stream = StreamObject()
        stream._data = image.data  # already DCT-encoded
        stream.update(
            {
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Image"),
                NameObject("/Width"): NumberObject(pixels_w),
                NameObject("/Height"): NumberObject(pixels_h),
                NameObject("/ColorSpace"): NameObject(
                    "/DeviceGray"
                    if image.components == 1
                    else "/DeviceCMYK"
                    if image.components == 4
                    else "/DeviceRGB"
                ),
                NameObject("/BitsPerComponent"): NumberObject(8),
                NameObject("/Filter"): NameObject("/DCTDecode"),
            }
        )
        if image.components == 4:
            stream[NameObject("/Decode")] = ArrayObject([NumberObject(1), NumberObject(0)] * 4)
        blank = writer.add_blank_page(width=width, height=height)
        name = f"/AWImg{number}"
        blank[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/XObject"): DictionaryObject(
                    {NameObject(name): writer._add_object(stream)}
                )
            }
        )
        content = DecodedStreamObject()
        content.set_data(
            f"q {draw_w:.2f} 0 0 {draw_h:.2f} {x:.2f} {y:.2f} cm {name} Do Q".encode("latin-1")
        )
        blank[NameObject("/Contents")] = writer._add_object(content)
    return _bytes(writer)


# ---- text layer for scanned pages ------------------------------------------------------------

_OCR_WORDS = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { throw 'no text recognition language is installed' }
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$extensions = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 }
$operationTask = $extensions | Where-Object { $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
$actionTask = $extensions | Where-Object { $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' } | Select-Object -First 1
function Await($operation, [Type] $type) { $task = $operationTask.MakeGenericMethod($type).Invoke($null, @($operation)); $null = $task.Wait(); $task.Result }
function Finish($action) { $task = $actionTask.Invoke($null, @($action)); $null = $task.Wait() }
$request = $env:AGENT_WORKSPACE_OCR_REQUEST | ConvertFrom-Json
$out = @{}
if ($request.kind -eq 'pdf') {
  $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($request.path)) ([Windows.Storage.StorageFile])
  $pdf = Await ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
  $limit = [Windows.Media.Ocr.OcrEngine]::MaxImageDimension
  foreach ($number in $request.pages) {
    if ($number -lt 1 -or $number -gt $pdf.PageCount) { continue }
    $page = $pdf.GetPage([uint32]($number - 1))
    $scale = [Math]::Min(3.0, ($limit - 1) / [Math]::Max($page.Size.Width, $page.Size.Height))
    $options = New-Object Windows.Data.Pdf.PdfPageRenderOptions
    $options.DestinationWidth = [uint32]([Math]::Floor($page.Size.Width * $scale))
    $options.DestinationHeight = [uint32]([Math]::Floor($page.Size.Height * $scale))
    $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
    Finish ($page.RenderToStreamAsync($stream, $options))
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $lines = @($result.Lines | ForEach-Object { @{ words = @($_.Words | ForEach-Object { @{ t = $_.Text; x = $_.BoundingRect.X; y = $_.BoundingRect.Y; w = $_.BoundingRect.Width; h = $_.BoundingRect.Height } }) } })
    $out["$number"] = @{ width = $options.DestinationWidth; height = $options.DestinationHeight; lines = $lines }
    $bitmap.Dispose(); $stream.Dispose(); $page.Dispose()
  }
} else {
  $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($request.path)) ([Windows.Storage.StorageFile])
  $stream = Await ($file.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  # Small screenshots are enlarged (recognition misses short words in small text); large ones are brought within the engine's limit.
  $limit = [Windows.Media.Ocr.OcrEngine]::MaxImageDimension
  $longest = [Math]::Max($decoder.PixelWidth, $decoder.PixelHeight)
  $scale = 1.0
  if ($longest -lt 1600) { $scale = [Math]::Min(3.0, 2400.0 / $longest) } elseif ($longest -ge $limit) { $scale = ($limit - 1) / $longest }
  if ($scale -ne 1.0) {
    $transform = New-Object Windows.Graphics.Imaging.BitmapTransform
    $transform.ScaledWidth = [uint32][Math]::Floor($decoder.PixelWidth * $scale)
    $transform.ScaledHeight = [uint32][Math]::Floor($decoder.PixelHeight * $scale)
    $transform.InterpolationMode = [Windows.Graphics.Imaging.BitmapInterpolationMode]::Fant
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync([Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8, [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied, $transform, [Windows.Graphics.Imaging.ExifOrientationMode]::RespectExifOrientation, [Windows.Graphics.Imaging.ColorManagementMode]::DoNotColorManage)) ([Windows.Graphics.Imaging.SoftwareBitmap])
  } else {
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  }
  $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  $lines = @($result.Lines | ForEach-Object { @{ words = @($_.Words | ForEach-Object { @{ t = $_.Text; x = $_.BoundingRect.X; y = $_.BoundingRect.Y; w = $_.BoundingRect.Width; h = $_.BoundingRect.Height } }) } })
  $out["1"] = @{ width = $bitmap.PixelWidth; height = $bitmap.PixelHeight; lines = $lines }
  $bitmap.Dispose(); $stream.Dispose()
}
@{ pages = $out } | ConvertTo-Json -Compress -Depth 7
"""


def recognize(
    path: Path, pages: list[int] | None = None, kind: str = "pdf", timeout: float = 600
) -> dict[int, dict[str, object]]:
    """Words and their boxes (in pixels of the rendered page or picture), by page."""
    if sys.platform != "win32":
        raise OfficeError("text recognition uses Windows' own (Windows 10 or later)")
    environment = dict(os.environ)
    environment["AGENT_WORKSPACE_OCR_REQUEST"] = json.dumps(
        {"path": str(path), "pages": pages or [1], "kind": kind}
    )
    powershell = shutil.which("powershell") or "powershell"
    done = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            _OCR_WORDS,
        ],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
        creationflags=_CREATE_NO_WINDOW,
        check=False,
    )
    output = done.stdout.decode("utf-8", errors="replace").strip()
    if done.returncode != 0 or not output:
        message = done.stderr.decode("utf-8", errors="replace").strip()
        raise OfficeError(f"text recognition failed: {message[-300:]}")
    document = json.loads(output.splitlines()[-1])
    return {int(number): page for number, page in (document.get("pages") or {}).items()}


_SPACED_CJK = re.compile(r"(?<=[　-鿿＀-￯]) (?=[　-鿿＀-￯])")
# Chinese recognition reads the marks inside numbers as full-width ones, and a hyphen as 一.
_IN_NUMBERS = (
    (re.compile(r"(?<=\d) ?[，,] ?(?=\d{3}(?!\d))"), ","),
    # A comma before one or two final digits is a decimal point read wrongly.
    (re.compile(r"(?<=\d) ?[，,] ?(?=\d{1,2}(?![\d,，]))"), "."),
    (re.compile(r"(?<=\d) ?[．。.] ?(?=\d)"), "."),
    (re.compile(r"(?<=\d) ?[一—－‐·・-] ?(?=\d)"), "-"),
    (re.compile(r"(?<=\d) ?[：:] ?(?=\d)"), ":"),
    (re.compile(r"(?<=\d) ?[／/] ?(?=\d)"), "/"),
    (re.compile(r"(?<=\d) ?％"), "%"),
    (re.compile(r"[￥¥] ?(?=\d)"), "¥"),
)


def clean_recognized(text: str) -> str:
    text = _SPACED_CJK.sub("", text)
    for pattern, mark in _IN_NUMBERS:
        text = pattern.sub(mark, text)
    return text


def recognized_lines(page: dict[str, Any]) -> list[tuple[float, float, float, float, str]]:
    """(x, y, width, height, text) of each recognized line, in pixels."""
    out = []
    for line in page.get("lines") or []:
        words = line.get("words") or []
        if not words:
            continue
        x0 = min(word["x"] for word in words)
        y0 = min(word["y"] for word in words)
        x1 = max(word["x"] + word["w"] for word in words)
        y1 = max(word["y"] + word["h"] for word in words)
        text = clean_recognized(" ".join(word["t"] for word in words))
        out.append((x0, y0, x1 - x0, y1 - y0, text))
    return out


def add_text_layer(data: bytes, recognized: dict[int, dict[str, object]]) -> bytes:
    """Invisible text (render mode 3) over each recognized line, so it can be searched."""
    reader = read(data)
    writer = PdfWriter(clone_from=reader)
    for number, page_words in recognized.items():
        if not 1 <= number <= len(writer.pages):
            continue
        page = writer.pages[number - 1]
        left, bottom, width, height = _box(page)
        pixel_w = float(page_words.get("width") or 1)  # type: ignore[arg-type]
        pixel_h = float(page_words.get("height") or 1)  # type: ignore[arg-type]
        scale_x, scale_y = width / pixel_w, height / pixel_h
        parts = ["BT 3 Tr"]
        for x, y, w, h, text in recognized_lines(page_words):
            if not text.strip():
                continue
            size = max(4.0, h * scale_y * 0.9)
            font, operand, units = _encode(text)
            natural = units * size / 1000
            stretch = 100 * (w * scale_x) / natural if natural else 100
            parts.append(
                f"{font} {size:.2f} Tf {max(10, min(400, stretch)):.1f} Tz 1 0 0 1 {left + x * scale_x:.2f} "
                f"{bottom + height - (y + h) * scale_y + size * 0.15:.2f} Tm {operand} Tj"
            )
        parts.append("ET")
        page.merge_page(_overlay(width, height, " ".join(parts)))
    return _bytes(writer)


def table_from_lines(lines: list[tuple[float, float, float, float, str]]) -> list[list[str]]:
    """A table read from recognized words: rows by their vertical position, columns by gaps."""
    words: list[tuple[float, float, float, float, str]] = []
    for x, y, w, h, text in lines:
        words.append((x, y, w, h, text))
    if not words:
        return []
    words.sort(key=lambda item: item[1] + item[3] / 2)
    heights = sorted(item[3] for item in words)
    tolerance = heights[len(heights) // 2] * 0.6
    rows: list[list[tuple[float, float, float, float, str]]] = []
    for item in words:
        middle = item[1] + item[3] / 2
        if rows and abs((rows[-1][0][1] + rows[-1][0][3] / 2) - middle) <= tolerance:
            rows[-1].append(item)
        else:
            rows.append([item])
    # Column starts: x positions shared by several rows.
    starts = sorted(item[0] for row in rows for item in row)
    columns: list[float] = []
    gap = max(8.0, tolerance * 2)
    for x in starts:
        if not columns or x - columns[-1] > gap:
            columns.append(x)
    out = []
    for row in rows:
        cells = [""] * len(columns)
        for x, _y, _w, _h, text in sorted(row):
            column = max(index for index, start in enumerate(columns) if start <= x + gap / 2)
            cells[column] = (cells[column] + " " + text).strip() if cells[column] else text
        out.append(cells)
    return out


__all__ = [
    "A4",
    "Jpeg",
    "add_text_layer",
    "compress",
    "delete",
    "images_to_pdf",
    "info",
    "jpeg_info",
    "merge",
    "page_numbers",
    "parse_pages",
    "pick",
    "read",
    "recognize",
    "recognized_lines",
    "rotate",
    "split",
    "table_from_lines",
    "to_jpeg",
    "watermark",
]
