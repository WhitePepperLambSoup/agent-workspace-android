# ruff: noqa: E501 -- the PowerShell script below keeps its pipelines on one line each.
"""Text recognition for scanned PDF pages with what Windows itself provides.

Windows 10 and later render PDF pages (Windows.Data.Pdf) and recognize text (Windows.Media.Ocr)
for the languages the user installed, with no extra download. A fixed PowerShell script calls
them; which file and pages to read comes in an environment variable as JSON, never as part of
the script. Without the platform pieces recognition is unavailable, and scanned pages are
skipped with a note.
"""

from __future__ import annotations

import base64
import functools
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .store import OcrPages

_CJK = "぀-ヿ㐀-䶿一-鿿豈-﫿가-힯　-〿＀-￯"
# The recognizer separates East Asian characters with spaces; the index pairs characters that
# touch, so they are joined again.
_SPACED_CJK = re.compile(f"(?<=[{_CJK}]) +(?=[{_CJK}])")
_REQUEST_VARIABLE = "AGENT_WORKSPACE_OCR_REQUEST"
_BATCH_TIMEOUT_SECONDS = 180
_PROBE_TIMEOUT_SECONDS = 30

_PRELUDE = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
"""

_PROBE = (
    _PRELUDE
    + r"""
if ($null -eq $engine) { 'none' } else { $engine.RecognizerLanguage.LanguageTag }
"""
)

_RECOGNIZE = (
    _PRELUDE
    + r"""
if ($null -eq $engine) { throw 'no text recognition language is installed' }
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$extensions = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1
}
$operationTask = $extensions | Where-Object { $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
$actionTask = $extensions | Where-Object { $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' } | Select-Object -First 1
function Await($operation, [Type] $type) {
  $task = $operationTask.MakeGenericMethod($type).Invoke($null, @($operation))
  $null = $task.Wait()
  $task.Result
}
function Finish($action) {
  $task = $actionTask.Invoke($null, @($action))
  $null = $task.Wait()
}
$request = $env:AGENT_WORKSPACE_OCR_REQUEST | ConvertFrom-Json
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($request.path)) ([Windows.Storage.StorageFile])
$pdf = Await ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
$limit = [Windows.Media.Ocr.OcrEngine]::MaxImageDimension
$pages = @{}
foreach ($number in $request.pages) {
  if ($number -lt 1 -or $number -gt $pdf.PageCount) { continue }
  $page = $pdf.GetPage([uint32]($number - 1))
  # About 290 dpi for a letter or A4 page, within what the recognizer accepts.
  $scale = [Math]::Min(3.0, ($limit - 1) / [Math]::Max($page.Size.Width, $page.Size.Height))
  $options = New-Object Windows.Data.Pdf.PdfPageRenderOptions
  $options.DestinationWidth = [uint32]([Math]::Floor($page.Size.Width * $scale))
  $options.DestinationHeight = [uint32]([Math]::Floor($page.Size.Height * $scale))
  $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
  Finish ($page.RenderToStreamAsync($stream, $options))
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  $pages["$number"] = (@($result.Lines | ForEach-Object { $_.Text }) -join "`n")
  $bitmap.Dispose()
  $stream.Dispose()
  $page.Dispose()
}
@{ pages = $pages } | ConvertTo-Json -Compress -Depth 3
"""
)


class WindowsOcrError(RuntimeError):
    """Windows could not recognize the pages; the message says why."""


def _powershell() -> str | None:
    return shutil.which("powershell.exe") or shutil.which("powershell")


def _run(script: str, *, request: str = "", timeout: float) -> str:
    executable = _powershell()
    if executable is None:
        raise WindowsOcrError("Windows PowerShell is not available")
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        completed = subprocess.run(
            [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            env={**os.environ, _REQUEST_VARIABLE: request},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise WindowsOcrError("text recognition took too long") from None
    except OSError as exc:
        raise WindowsOcrError(f"Windows PowerShell could not start: {exc}") from None
    if completed.returncode != 0:
        detail = " ".join(completed.stderr.split())[:300] or f"exit code {completed.returncode}"
        raise WindowsOcrError(detail)
    return completed.stdout


@functools.cache
def recognizer_language() -> str | None:
    """The language Windows recognizes for this user ("zh-Hans-CN"), or None without one."""
    if sys.platform != "win32" or _powershell() is None:
        return None
    try:
        answer = _run(_PROBE, timeout=_PROBE_TIMEOUT_SECONDS).strip()
    except WindowsOcrError:
        return None
    return None if not answer or answer == "none" else answer


def recognize_pdf_pages(path: Path, pages: list[int]) -> dict[int, str]:
    """The recognized text of the given one-based pages of a PDF ({} for pages it skipped)."""
    request = json.dumps(
        {"path": str(Path(path).resolve()), "pages": [int(page) for page in pages]}
    )
    output = _run(_RECOGNIZE, request=request, timeout=_BATCH_TIMEOUT_SECONDS).strip()
    try:
        document = json.loads(output.splitlines()[-1]) if output else {}
    except ValueError:
        raise WindowsOcrError("text recognition returned no result") from None
    recognized = document.get("pages") if isinstance(document, dict) else None
    if not isinstance(recognized, dict):
        return {}
    return {
        int(key): _SPACED_CJK.sub("", value)
        for key, value in recognized.items()
        if isinstance(value, str) and str(key).isdigit()
    }


def windows_ocr() -> OcrPages | None:
    """The recognizer for scanned PDF pages on this computer, or None without one."""
    return recognize_pdf_pages if recognizer_language() is not None else None
