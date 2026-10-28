"""The agent's LaTeX tools: compile a document and read its errors, and check its sources."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.events import Event
from agent_workspace.core.models import Capability, FileCheckpoint, ToolSpec
from agent_workspace.latex import compile as latex_compile
from agent_workspace.latex import project, rules
from agent_workspace.latex.issues import Issue
from agent_workspace.tools.base import (
    ToolArgumentError,
    ToolError,
    json_result,
    validate_tool_arguments,
)
from agent_workspace.tools.filesystem import _read_preimage, atomic_write
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

MAX_PDF_BYTES = 200 * 1024 * 1024
_MAX_ERRORS = 15
_MAX_WARNINGS = 10


def _issue_summary(issue: Issue, *, raw: bool) -> dict[str, Any]:
    document: dict[str, Any] = {"message": issue.message}
    if issue.file:
        document["file"] = issue.file
    if issue.line:
        document["line"] = issue.line
    if raw and issue.raw:
        document["log"] = issue.raw[:600]
    return document


class CompileLatexTool:
    hard_cancellable = True

    def __init__(self, workspace: Path, data_dir: Path) -> None:
        self.paths = WorkspacePaths(workspace)
        self.data_dir = data_dir
        self._spec = ToolSpec(
            name="compile_latex",
            description=(
                "Compile a LaTeX document with the TeX installed on this computer (MiKTeX or "
                "TeX Live; Tectonic when the app installed it) and report the errors with file "
                "and line. Runs as many passes as cross-references need and BibTeX or Biber "
                "for the bibliography. Pass the main document or any file it includes. Writes "
                "<name>.pdf beside the document; build files go to .latex-build/. Engine: auto "
                "picks XeLaTeX for Chinese (ctex) or fontspec documents, else pdfLaTeX; a "
                "'% !TEX program = ...' comment overrides it. MiKTeX installs no packages here: "
                "a missing .sty is reported as a missing file. Use another package, or tell the "
                "user to install it in MiKTeX Console (or to compile once from the LaTeX editor, "
                "which offers to install it)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1, "maxLength": 1024},
                    "engine": {"type": "string", "enum": list(latex_compile.ENGINES)},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            side_effect="write",
            capability=Capability.WORKSPACE_WRITE,
            durable_preimage_checkpoint=True,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def execution_timeout_seconds(self, arguments: dict[str, Any]) -> float:
        return latex_compile.TOTAL_SECONDS + 60

    def _document(self, arguments: dict[str, Any]) -> tuple[Path, str]:
        validate_tool_arguments(self._spec, arguments)
        try:
            file = self.paths.resolve(arguments["path"])
        except WorkspacePathError as error:
            raise ToolArgumentError(str(error)) from None
        if file.suffix.lower() != ".tex" or not file.is_file():
            raise ToolArgumentError("path must be an existing .tex file")
        return file, str(arguments.get("engine") or "auto")

    def _compile(
        self, file: Path, engine: str, cancel: threading.Event
    ) -> latex_compile.CompileResult:
        root = self.paths.root
        main = latex_compile.find_root(root, file)
        engines = latex_compile.detect_engines(self.data_dir)
        if not engines.available():
            raise ToolError(
                "no TeX engine on this computer: install MiKTeX or TeX Live, or Tectonic "
                "from the app's LaTeX editor"
            )
        try:
            # MiKTeX's install prompt is a window of its own: in a turn nobody may be there to
            # answer it, and the compile would wait for it until the time is up.
            return latex_compile.compile_document(
                root, main, engines=engines, preference=engine, cancel=cancel, installer=False
            )
        except latex_compile.CompileError as error:
            raise ToolError(f"cannot compile: {error}") from None

    async def execute(self, arguments: dict[str, Any]) -> str:
        file, engine = self._document(arguments)
        cancel = threading.Event()
        try:
            result = await asyncio.to_thread(self._compile, file, engine, cancel)
        except asyncio.CancelledError:
            cancel.set()
            raise
        pdf = await asyncio.to_thread(project.publish_pdf, result)
        return self._report(result, pdf)

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        file, engine = self._document(arguments)
        cancel = threading.Event()
        try:
            result = await asyncio.to_thread(self._compile, file, engine, cancel)
        except asyncio.CancelledError:
            cancel.set()
            raise
        pdf: Path | None = None
        if result.pdf is not None:
            pdf = await self._write_pdf(result, context)
        return self._report(result, pdf)

    async def _write_pdf(
        self, result: latex_compile.CompileResult, context: ToolExecutionContext
    ) -> Path:
        """Put the PDF beside the document with a checkpoint of the one it replaces."""
        assert result.pdf is not None
        body = await asyncio.to_thread(result.pdf.read_bytes)
        target = project.pdf_beside(result.main)
        relative = self.paths.relative(target)
        expected: str | None = None
        if target.is_file():
            expected = hashlib.sha256(await asyncio.to_thread(target.read_bytes)).hexdigest()
        preimage = await asyncio.to_thread(_read_preimage, target, expected, MAX_PDF_BYTES)
        digest = hashlib.sha256(body).hexdigest()
        await context.prepare_file_checkpoint(
            FileCheckpoint(
                attempt_id=context.attempt_id,
                session_id=context.session_id,
                workspace=str(self.paths.root),
                started_event_id=context.started_event_id,
                relative_path=relative,
                preimage_sha256=expected,
                preimage=preimage,
                postimage_sha256=digest,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
        written, _ = await asyncio.to_thread(
            atomic_write, self.paths, target, body, expected, maximum=MAX_PDF_BYTES
        )
        await context.record_event(
            Event(
                session_id=context.session_id,
                type="file.version.recorded",
                data={
                    "attempt_id": context.attempt_id,
                    "path": relative,
                    "sha256": digest,
                    "bytes": len(body),
                },
                causation_id=context.started_event_id,
                correlation_id=context.correlation_id,
            )
        )
        return written

    def _report(self, result: latex_compile.CompileResult, pdf: Path | None) -> str:
        errors = result.errors
        warnings = [issue for issue in result.issues if issue.severity == "warning"]
        report: dict[str, Any] = {
            "ok": result.ok,
            "document": self.paths.relative(result.main),
            "engine": result.engine,
            "passes": result.passes,
            "seconds": result.seconds,
            "pdf": self.paths.relative(pdf) if pdf is not None else None,
            "log": self.paths.relative(result.log) if result.log is not None else None,
            "errors": [_issue_summary(issue, raw=True) for issue in errors[:_MAX_ERRORS]],
            "error_count": len(errors),
            "warnings": [_issue_summary(issue, raw=False) for issue in warnings[:_MAX_WARNINGS]],
            "warning_count": len(warnings),
        }
        if result.cancelled:
            report["cancelled"] = True
        if result.timed_out:
            report["timed_out"] = True
        if errors and pdf is not None:
            report["note"] = "the PDF was written despite the errors and may be incomplete"
        return json_result(report)


class CheckLatexTool:
    def __init__(self, workspace: Path) -> None:
        self.paths = WorkspacePaths(workspace)
        self._spec = ToolSpec(
            name="check_latex",
            description=(
                "Check LaTeX sources without compiling: \\ref or \\cite keys with no \\label or "
                "bibliography entry, duplicate labels, a bare % after a number, \\textit around "
                "Chinese, & inside \\textbf, unrounded numbers, a missing \\end{document}, "
                "bibliography entries missing required (GB/T 7714) fields or with authors not "
                "separated by 'and'. Pass a .tex or .bib file, or a folder."
            ),
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string", "minLength": 1, "maxLength": 1024}},
                "required": ["path"],
                "additionalProperties": False,
            },
            side_effect="read",
            capability=Capability.WORKSPACE_READ,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def _check(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        try:
            target = self.paths.resolve(arguments["path"])
        except WorkspacePathError as error:
            raise ToolArgumentError(str(error)) from None
        root = self.paths.root
        if target.is_dir():
            sources = project.gather_sources(root, target)
            found: list[Issue] = []
            enabled = rules.enabled_rules()
            for path, text in sources.tex.items():
                found.extend(rules.check_source(text, path, enabled))
            found.extend(rules.check_project(sources.tex, sources.bib, enabled))
            checked = len(sources.tex) + len(sources.bib)
            truncated = sources.truncated
        elif target.suffix.lower() in {".tex", ".bib"} and target.is_file():
            report = project.check(root, target)
            found, checked, truncated = report.issues, 1, report.truncated
        else:
            raise ToolArgumentError("path must be a .tex or .bib file or a folder")
        counts: dict[str, int] = {}
        for issue in found:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return json.dumps(
            {
                "checked_files": checked,
                "truncated": truncated,
                "counts": counts,
                "issues": [
                    {
                        key: value
                        for key, value in issue.to_dict().items()
                        if key in {"severity", "code", "message", "file", "line", "rule"}
                    }
                    for issue in found[:80]
                ],
            },
            ensure_ascii=False,
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await asyncio.to_thread(self._check, arguments)


def latex_tools(workspace: Path, *, data_dir: Path) -> tuple[CompileLatexTool, CheckLatexTool]:
    return CompileLatexTool(workspace, data_dir), CheckLatexTool(workspace)
