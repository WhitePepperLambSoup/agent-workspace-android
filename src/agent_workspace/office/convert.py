# ruff: noqa: E501 -- the PowerShell script keeps its statements on one line each.
"""Word, Excel and PowerPoint files saved as PDF by the office suite on this computer.

Microsoft Office or WPS do it through their automation interface, hidden, from a fixed
PowerShell script that reads the file names from an environment variable (never from its own
text); LibreOffice does it from the command line. An instance that already has documents open
(the user's own) is neither hidden nor closed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from agent_workspace.office.ooxml import OfficeError

_CREATE_NO_WINDOW = 0x08000000
_REQUEST = "AGENT_WORKSPACE_CONVERT_REQUEST"
TIMEOUT_SECONDS = 180

_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$request = $env:AGENT_WORKSPACE_CONVERT_REQUEST | ConvertFrom-Json
$source = $request.source
$target = $request.target
$kind = $request.kind
function Open-App($names) {
  foreach ($name in $names) {
    try { return New-Object -ComObject $name } catch { }
  }
  throw 'no office suite answered'
}
# A suite that is still starting, or calculating, rejects calls for a while (RPC_E_CALL_REJECTED,
# RPC_E_SERVERCALL_RETRYLATER): ask again.
function Retry([scriptblock]$block) {
  for ($attempt = 0; $attempt -lt 120; $attempt++) {
    try { return & $block }
    catch [System.Runtime.InteropServices.COMException] {
      if ($_.Exception.HResult -ne -2147418111 -and $_.Exception.HResult -ne -2147417846) { throw }
      Start-Sleep -Milliseconds 250
    }
  }
  throw 'the office suite stayed busy'
}
if ($kind -eq 'word') {
  $app = Open-App @('Word.Application', 'KWPS.Application')
  $fresh = Retry { $app.Documents.Count -eq 0 }
  if ($fresh) { Retry { $app.Visible = $false } }
  Retry { $app.DisplayAlerts = 0 }
  $doc = Retry { $app.Documents.Open($source, $false, $true, $false) }
  try { Retry { $doc.ExportAsFixedFormat($target, 17) } } finally { Retry { $doc.Close(0) } }
  if ($fresh -and (Retry { $app.Documents.Count }) -eq 0) { Retry { $app.Quit() } }
} elseif ($kind -eq 'excel') {
  $app = Open-App @('Excel.Application', 'KET.Application')
  # Excel made through automation is already hidden; setting Visible on a new instance makes
  # it reject every call after.
  $fresh = Retry { $app.Workbooks.Count -eq 0 }
  Retry { $app.DisplayAlerts = $false }
  $book = Retry { $app.Workbooks.Open($source, 0, $true) }
  try { Retry { $book.ExportAsFixedFormat(0, $target) } } finally { Retry { $book.Close($false) } }
  if ($fresh -and (Retry { $app.Workbooks.Count }) -eq 0) { Retry { $app.Quit() } }
} else {
  $app = Open-App @('PowerPoint.Application', 'KWPP.Application')
  $fresh = Retry { $app.Presentations.Count -eq 0 }
  $deck = Retry { $app.Presentations.Open($source, -1, 0, 0) }
  try { Retry { $deck.SaveAs($target, 32) } } finally { Retry { $deck.Close() } }
  if ($fresh -and (Retry { $app.Presentations.Count }) -eq 0) { Retry { $app.Quit() } }
}
'ok'
"""

KINDS = {
    ".docx": "word",
    ".doc": "word",
    ".rtf": "word",
    ".xlsx": "excel",
    ".xls": "excel",
    ".pptx": "powerpoint",
    ".ppt": "powerpoint",
}


def _soffice() -> str | None:
    found = shutil.which("soffice")
    if found:
        return found
    for root in (os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", "")):
        candidate = Path(root) / "LibreOffice" / "program" / "soffice.exe"
        if root and candidate.is_file():
            return str(candidate)
    return None


def _has_com(name: str) -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{name}\\CLSID"):
            return True
    except OSError:
        return False


def available() -> str | None:
    """Which converter this computer has: "office", "wps", "libreoffice" or None."""
    if _has_com("Word.Application"):
        return "office"
    if _has_com("KWPS.Application"):
        return "wps"
    if _soffice():
        return "libreoffice"
    return None


def to_pdf(source: Path, timeout: float = TIMEOUT_SECONDS) -> bytes:
    """The file as PDF bytes (the source is read, never changed)."""
    kind = KINDS.get(source.suffix.lower())
    if kind is None:
        raise OfficeError("only Word, Excel and PowerPoint files are converted to PDF")
    converter = available()
    if converter is None:
        raise OfficeError(
            "no office suite on this computer (Microsoft Office, WPS or LibreOffice) to convert with"
        )
    with tempfile.TemporaryDirectory(prefix="aw-convert-") as folder:
        # A copy, so the suite never locks or changes the user's file.
        copied = Path(folder) / f"source{source.suffix.lower()}"
        shutil.copyfile(source, copied)
        target = Path(folder) / "out.pdf"
        flags = _CREATE_NO_WINDOW if sys.platform == "win32" else 0
        if converter in {"office", "wps"}:
            powershell = shutil.which("powershell") or "powershell"
            environment = dict(os.environ)
            environment[_REQUEST] = json.dumps(
                {"source": str(copied), "target": str(target), "kind": kind}
            )
            command = [
                powershell,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                _SCRIPT,
            ]
        else:
            command = [
                _soffice() or "soffice",
                "--headless",
                "--norestore",
                "--convert-to",
                "pdf",
                "--outdir",
                folder,
                str(copied),
            ]
            environment = dict(os.environ)
        try:
            done = subprocess.run(
                command,
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=flags,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise OfficeError("the office suite did not finish converting in time") from None
        produced = target if target.is_file() else Path(folder) / "source.pdf"
        if done.returncode != 0 or not produced.is_file():
            detail = " ".join((done.stderr or done.stdout or "").split())
            raise OfficeError(f"the conversion failed: {detail[:400]}")
        return produced.read_bytes()


__all__ = ["KINDS", "available", "to_pdf"]
