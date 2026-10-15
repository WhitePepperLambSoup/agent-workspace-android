"""What this phone can and cannot run, told to the agent once at the start of a conversation.

Without it the agent spends its first steps probing (``which pdflatex``, ``pip list``, ``ls
/usr/bin``) before it finds out what a phone does not have. The section is built from what the app
actually found (registered tools, probed executables, the optional developer toolchain), so it is
as true as the tool list itself. It changes only when that state changes, which keeps cached prompt
prefixes intact.
"""

from __future__ import annotations

from typing import Any

# What people ask for that a phone does not have, named so the agent stops looking at once.
_NOT_HERE = (
    "LaTeX (pdflatex, xelatex, latexmk, tectonic), pandoc, LibreOffice, ImageMagick, ffmpeg and C/C++ "
    "compilers"
)
_TOOLCHAIN_PROGRAMS = (("python", "Python 3"), ("git", "Git"), ("node", "Node.js"))


def _registry_state(registry: Any | None) -> tuple[set[str], dict[str, Any]]:
    tools = set(getattr(registry, "_tools", {}) or {}) if registry is not None else set()
    capabilities = getattr(registry, "_android_capabilities", None) or {}
    executables = capabilities.get("executables") if isinstance(capabilities, dict) else None
    return tools, executables if isinstance(executables, dict) else {}


def _pdf_line(tools: set[str]) -> str | None:
    if "create_pdf" not in tools:
        return None
    from android_adapter.documents import CREATE_PDF_FORMATS

    if "latex" in CREATE_PDF_FORMATS:
        return (
            "create_pdf makes the PDF directly from plain text, Markdown or LaTeX source: headings, "
            "lists, tables, theorems and formulas (\\newcommand macros too) are typeset; TikZ, "
            "pictures and other TeX packages are not. For a LaTeX request, write the .tex file if "
            "the user wants it and call create_pdf with format latex and the same source; there is "
            "nothing to compile."
        )
    return "create_pdf makes text-only PDFs (no formula typesetting)."


def environment_section(registry: Any | None) -> str:
    """The environment section of the Android system prompt; empty without a tool registry."""
    tools, executables = _registry_state(registry)
    if not tools:
        return ""
    lines = [
        "Environment (checked by the app when this conversation started; trust it instead of "
        "probing with which, --version, ls of system folders or package lists):"
    ]
    if "run_terminal" in tools:
        lines.append(
            "- run_terminal runs Android's /system/bin/sh with toybox commands (ls, cat, grep, sed, "
            "awk, find, tar, gzip, sha256sum). There is no package manager: apt, pkg, pip install "
            "and npm install do not work."
        )
    installed = [label for key, label in _TOOLCHAIN_PROGRAMS if key in executables]
    if installed:
        lines.append(
            f"- The optional developer toolchain is installed: {', '.join(installed)}; run them "
            "with run_process (or run_terminal)."
        )
    else:
        lines.append(
            "- No Python, Git or Node executable is installed (the app's own Python is not "
            "available to commands). The user can add them under Device & tools → Developer "
            "toolchain."
        )
    lines.append(f"- Not on this phone: {_NOT_HERE}. Do not look for them.")
    documents = []
    if "read_document" in tools:
        documents.append(
            "read_document reads PDF, Word, Excel, PowerPoint and EPUB files (scanned pages "
            "with OCR)"
        )
    pdf = _pdf_line(tools)
    if pdf:
        documents.append(pdf)
    if "render_pdf" in tools:
        documents.append("render_pdf turns PDF pages into images")
    if documents:
        lines.append("- Documents: " + "; ".join(documents))
    ways = _ways(tools)
    if ways:
        lines.append("- How common requests are done here: " + "; ".join(ways) + ".")
    lines.append(
        "- When something cannot be done here, say so at once and offer the closest way that works."
    )
    return "\n".join(lines)


def _ways(tools: set[str]) -> list[str]:
    """Requests people make, and the tool that does them on this phone (only tools that are here)."""
    ways = []
    if {"create_docx", "create_xlsx"} <= tools:
        ways.append("Word or Excel files → create_docx (from Markdown) or create_xlsx (rows, formulas)")
    if "create_pdf" in tools:
        ways.append("a PDF → create_pdf (text, markdown or latex)")
    if "write_file" in tools:
        ways.append(
            "a chart or diagram → an HTML file with inline SVG (or a ```mermaid block in the reply)"
        )
    if "transcribe_audio" in tools:
        ways.append("speech in an audio file → transcribe_audio (no audio or video converting)")
    else:
        ways.append("no audio or video converting")
    if "browser" in tools:
        ways.append("a web page → browser (no curl or wget needed)")
    if "android_action" in tools:
        ways.append("anything in another app or in Settings → the android_* tools (open_page opens system pages)")
    ways.append("editing pictures → not possible here")
    return ways
