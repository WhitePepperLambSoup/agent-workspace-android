"""The LaTeX editor: compile the open folder's documents, check and fix their sources, map between
source lines and the PDF, install Tectonic and start a document from a template."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Any

from agent_workspace.latex import compile as latex_compile
from agent_workspace.latex import install, project, rules, synctex, templates
from agent_workspace.latex.issues import Issue
from agent_workspace.tools.base import ToolError
from agent_workspace.tools.paths import WorkspacePaths
from agent_workspace.ui_gateway.gateway_common import _LOGGER, GatewayError, GatewayReply
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.latex_desk import LatexBusy
from agent_workspace.ui_gateway.protocol import CommandEnvelope

LATEX_COMMANDS = frozenset(
    {
        "latex.status",
        "latex.settings.set",
        "latex.compile",
        "latex.cancel",
        "latex.check",
        "latex.fix",
        "latex.synctex",
        "latex.engine.install",
        "latex.template.create",
    }
)
# Commands that wait on an engine or a download: answered off the reader thread, one at a time.
LATEX_LONG_COMMANDS = frozenset({"latex.compile", "latex.engine.install"})
_MAX_CONTENT_CHARS = 4 * 1024 * 1024
_MAX_REPLY_ISSUES = 200
_RAW_CHARS = 1500


def _issue_document(issue: Issue) -> dict[str, Any]:
    document = issue.to_dict()
    if "raw" in document:
        document["raw"] = document["raw"][-_RAW_CHARS:]
    return document


class LatexCommands(GatewayState):
    """The LaTeX editor's commands."""

    def _latex_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        handler = {
            "latex.status": self._latex_status,
            "latex.settings.set": self._latex_settings,
            "latex.compile": self._latex_compile,
            "latex.cancel": self._latex_cancel,
            "latex.check": self._latex_check,
            "latex.fix": self._latex_fix,
            "latex.synctex": self._latex_synctex,
            "latex.engine.install": self._latex_install,
            "latex.template.create": self._latex_template,
        }[command.type]
        payload = handler(command)
        return self._reply(f"{command.type}.result", payload, session_id=None)

    def stop_latex(self) -> None:
        """Stop a running compile or install (the app is closing)."""
        with self._latex.lock:
            if self._latex.cancel is not None:
                self._latex.cancel.set()

    def _latex_start(self, job: str) -> threading.Event:
        try:
            return self._latex.start(job)
        except LatexBusy:
            raise GatewayError("latex_busy") from None

    def _latex_paths(self) -> WorkspacePaths:
        with self._lock:
            workspace = self._workspace
        if workspace is None:
            raise GatewayError("runtime_unconfigured")
        return WorkspacePaths(workspace)

    @staticmethod
    def _latex_file(paths: WorkspacePaths, raw: object, suffixes: set[str]) -> Path:
        if not isinstance(raw, str) or not raw.strip() or len(raw) > 4096:
            raise GatewayError("invalid_path")
        try:
            target = paths.resolve(raw.strip())
        except (OSError, ToolError, ValueError):
            raise GatewayError("invalid_path") from None
        if target.suffix.lower() not in suffixes:
            raise GatewayError("unsupported_type")
        if not target.is_file():
            raise GatewayError("file_not_found")
        return target

    def _latex_status(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, set(), optional={"refresh"})
        return self._latex_status_document(fresh=command.payload.get("refresh") is True)

    def _latex_status_document(self, *, fresh: bool) -> dict[str, object]:
        desk = self._latex
        engines = latex_compile.detect_engines(desk.data_dir, fresh=fresh)
        with desk.lock:
            job = desk.job
        return {
            "engines": engines.to_dict(),
            "available": engines.available(),
            "installable": install.installable(),
            "tectonicVersion": install.TECTONIC_VERSION,
            "settings": desk.settings(),
            "rules": [
                {"id": info.id, "defaultEnabled": info.default_enabled, "fixable": info.fixable}
                for info in rules.RULES.values()
            ],
            "templates": list(templates.TEMPLATES),
            "job": job,
        }

    def _latex_settings(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, set(), optional={"engine", "autoCompile", "rules"})
        desk = self._latex
        current = desk.settings()
        payload = command.payload
        if "engine" in payload:
            if payload["engine"] not in latex_compile.ENGINES:
                raise GatewayError("invalid_payload")
            current["engine"] = payload["engine"]
        if "autoCompile" in payload:
            if not isinstance(payload["autoCompile"], bool):
                raise GatewayError("invalid_payload")
            current["autoCompile"] = payload["autoCompile"]
        if "rules" in payload:
            toggles = payload["rules"]
            if not isinstance(toggles, dict) or not all(
                key in rules.RULES and isinstance(value, bool) for key, value in toggles.items()
            ):
                raise GatewayError("invalid_payload")
            current["rules"] = {**current["rules"], **toggles}
        try:
            desk.save(current)
        except OSError:
            raise GatewayError("storage_unavailable") from None
        return self._latex_status_document(fresh=False)

    def _latex_compile(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, {"path"}, optional={"engine"})
        paths = self._latex_paths()
        file = self._latex_file(paths, command.payload["path"], {".tex"})
        desk = self._latex
        engine = command.payload.get("engine") or desk.settings()["engine"]
        if engine not in latex_compile.ENGINES:
            raise GatewayError("invalid_payload")
        engines = latex_compile.detect_engines(desk.data_dir)
        if not engines.available():
            raise GatewayError("latex_no_engine")
        main = latex_compile.find_root(paths.root, file)
        cancel = self._latex_start("compile")
        try:
            result = latex_compile.compile_document(
                paths.root, main, engines=engines, preference=engine, cancel=cancel
            )
            pdf = project.publish_pdf(result)
        except latex_compile.CompileError as error:
            raise GatewayError(f"latex_{error}") from None
        except OSError:
            raise GatewayError("storage_unavailable") from None
        finally:
            desk.finish()
        pdf_digest = None
        if pdf is not None:
            pdf_digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        return {
            "ok": result.ok,
            "engine": result.engine,
            "main": paths.relative(result.main),
            "pdf": paths.relative(pdf) if pdf is not None else None,
            "pdfSha256": pdf_digest,
            "log": paths.relative(result.log) if result.log is not None else None,
            "passes": result.passes,
            "seconds": result.seconds,
            "cancelled": result.cancelled,
            "timedOut": result.timed_out,
            "synctex": synctex.synctex_path(result.build, result.main.stem) is not None,
            "issues": [_issue_document(issue) for issue in result.issues[:_MAX_REPLY_ISSUES]],
            "issueCount": len(result.issues),
        }

    def _latex_cancel(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, set())
        desk = self._latex
        with desk.lock:
            cancel = desk.cancel
        if cancel is not None:
            cancel.set()
        return {"cancelled": cancel is not None}

    def _latex_check(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, {"path"}, optional={"content"})
        paths = self._latex_paths()
        file = self._latex_file(paths, command.payload["path"], {".tex", ".bib"})
        content = command.payload.get("content")
        if content is not None and (
            not isinstance(content, str) or len(content) > _MAX_CONTENT_CHARS
        ):
            raise GatewayError("invalid_payload")
        try:
            report = project.check(
                paths.root, file, content=content, settings=self._latex.settings()["rules"]
            )
        except OSError:
            raise GatewayError("file_read_failed") from None
        return {
            "path": paths.relative(file),
            "main": report.main,
            "issues": [_issue_document(issue) for issue in report.issues[:_MAX_REPLY_ISSUES]],
            "issueCount": len(report.issues),
            "labels": report.labels,
            "citations": report.citations,
            "truncated": report.truncated,
        }

    def _latex_fix(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, {"rule", "content"})
        rule, content = command.payload["rule"], command.payload["content"]
        if rule not in rules.RULES or not rules.RULES[rule].fixable:
            raise GatewayError("invalid_payload")
        if not isinstance(content, str) or len(content) > _MAX_CONTENT_CHARS:
            raise GatewayError("invalid_payload")
        return {"rule": rule, "content": rules.fix(content, rule)}

    def _latex_synctex(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, {"path", "direction"}, optional={"line", "page", "x", "y"})
        paths = self._latex_paths()
        payload = command.payload

        def number(key: str, *, whole: bool) -> float:
            value = payload.get(key)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise GatewayError("invalid_payload")
            if whole and (not isinstance(value, int) or value < 1):
                raise GatewayError("invalid_payload")
            return float(value)

        if payload["direction"] == "forward":
            file = self._latex_file(paths, payload["path"], {".tex"})
            line = int(number("line", whole=True))
            main = latex_compile.find_root(paths.root, file)
            data = self._latex_synctex_data(main)
            box = data.forward(file, line) if data is not None else None
            if box is None:
                return {"found": False}
            return {"found": True, "pdf": paths.relative(project.pdf_beside(main)), **box.to_dict()}
        if payload["direction"] != "inverse":
            raise GatewayError("invalid_payload")
        pdf = self._latex_file(paths, payload["path"], {".pdf"})
        page = int(number("page", whole=True))
        x, y = number("x", whole=False), number("y", whole=False)
        data = self._latex_synctex_data(pdf.with_suffix(".tex"))
        hit = data.inverse(page, x, y) if data is not None else None
        if hit is None:
            return {"found": False}
        try:
            relative = paths.relative(Path(hit[0]))
        except (OSError, ToolError, ValueError):
            return {"found": False}
        return {"found": True, "file": relative, "line": hit[1]}

    @staticmethod
    def _latex_synctex_data(main: Path) -> synctex.SyncTex | None:
        found = synctex.synctex_path(main.parent / latex_compile.BUILD_DIRECTORY, main.stem)
        if found is None:
            return None
        try:
            return synctex.load(found, main.parent)
        except (OSError, ValueError, EOFError):
            return None

    def _latex_install(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, set())
        desk = self._latex
        cancel = self._latex_start("install")
        try:
            installed = install.install_tectonic(desk.data_dir, cancel=cancel)
        except install.InstallError as error:
            _LOGGER.warning("Tectonic install failed: %s", error)
            raise GatewayError(f"latex_install_{error}") from None
        except OSError:
            raise GatewayError("storage_unavailable") from None
        finally:
            desk.finish()
        latex_compile.detect_engines(desk.data_dir, fresh=True)
        return {"tectonic": str(installed)}

    def _latex_template(self, command: CommandEnvelope) -> dict[str, object]:
        self._require_payload(command, {"template"}, optional={"directory"})
        paths = self._latex_paths()
        template, directory = command.payload["template"], command.payload.get("directory", "")
        if not isinstance(template, str) or not isinstance(directory, str):
            raise GatewayError("invalid_payload")
        try:
            created = templates.create(paths.root, directory, template)
        except templates.TemplateError as error:
            raise GatewayError(f"latex_template_{error}") from None
        except OSError:
            raise GatewayError("storage_unavailable") from None
        return {"main": created[0], "files": created}
