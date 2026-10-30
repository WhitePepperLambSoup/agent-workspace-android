# ruff: noqa: RUF001, E501 -- descriptions name Chinese document types.
"""The agent's office tools (desktop): reading and checking documents, Word revisions and
official documents, spreadsheets, PDF pages, slides from a template, e-mail drafts and
invitations, document templates, and meeting transcripts."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from agent_workspace.application.ports import Tool, ToolExecutionContext
from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.office import (
    compare,
    convert,
    gongwen,
    invoices,
    mail,
    meeting,
    merge,
    pdf,
    proofread,
    slides,
    table_ops,
    tables,
    templates,
    translate,
    xlsx,
)
from agent_workspace.office.ooxml import OfficeError
from agent_workspace.office.output import Folder, safe_name
from agent_workspace.office.word import Revisions, body_paragraphs, locate, open_docx, read_comments
from agent_workspace.storage.file_versions import FileVersions
from agent_workspace.tools.base import (
    ToolArgumentError,
    ToolError,
    json_result,
    validate_tool_arguments,
)

DOCX = {".docx"}
TABLES = {".xlsx", ".xlsm", ".csv"}
_STR = {"type": "string", "maxLength": 1000}
_STRS = {"type": "array", "items": {"type": "string", "maxLength": 1000}, "maxItems": 500}
_OBJ = {"type": "object"}
SpeechSource = Callable[[], tuple[str, str, str] | None]


class _OfficeTool:
    hard_cancellable = True
    _spec: ToolSpec

    def __init__(self, folder: Folder, data_dir: Path) -> None:
        self.folder = folder
        self.data_dir = data_dir

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def execution_timeout_seconds(self, arguments: dict[str, Any]) -> float:
        # Large workbooks and documents; the office suite converting a file; text recognition
        # of scanned pages; a long recording, ten minutes at a time.
        if arguments.get("action") in {"searchable", "transcribe"}:
            return 3600.0
        if arguments.get("action") in {"office_to_pdf", "mail_merge", "invoices"}:
            return 900.0
        return 300.0

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await self.execute_with_context(arguments, None)

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> str:
        validate_tool_arguments(self._spec, arguments)
        try:
            return json_result(await self._run(arguments, context))
        except OfficeError as error:
            raise ToolError(str(error)) from None

    async def _run(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        raise NotImplementedError

    def _require(self, arguments: dict[str, Any], *names: str) -> None:
        missing = [name for name in names if arguments.get(name) in (None, "", [])]
        if missing:
            raise ToolArgumentError(
                f"the action {arguments.get('action')} needs {', '.join(missing)}"
            )


def _spec(
    name: str,
    description: str,
    actions: list[str],
    properties: dict[str, Any],
    effect: str = "write",
) -> ToolSpec:
    capability = (
        Capability.WORKSPACE_READ
        if effect == "read"
        else Capability.NETWORK_READ
        if effect == "network"
        else Capability.WORKSPACE_WRITE
    )
    return ToolSpec(
        name=name,
        description=description,
        input_schema={
            "type": "object",
            "properties": {"action": {"type": "string", "enum": actions}, **properties},
            "required": ["action"],
            "additionalProperties": False,
        },
        side_effect=effect,
        capability=capability,
        durable_preimage_checkpoint=effect != "read",
    )


def _int(arguments: dict[str, Any], name: str, default: int) -> int:
    value = arguments.get(name)
    return default if value is None else int(value)


def _paths(folder: Folder, items: list[str], suffixes: set[str]) -> list[Path]:
    """Files named one by one, or every matching file of the folders named."""
    out: list[Path] = []
    for raw in items:
        path = folder.resolve(raw, must_exist=False)
        if path.is_dir():
            out.extend(
                sorted(
                    item
                    for item in path.rglob("*")
                    if item.is_file() and item.suffix.lower() in suffixes
                )
            )
        else:
            out.append(folder.resolve(raw, suffixes))
    if not out:
        raise ToolArgumentError("no matching files were found")
    return out[:2000]


def _read_invoices(folder: Folder, items: list[str]) -> list[invoices.Invoice]:
    """The invoices of the files and folders named; a file that cannot be read is listed with
    its problem instead of stopping the rest."""
    out = []
    for path in _paths(folder, items, invoices.SUFFIXES):
        label = folder.relative(path)
        try:
            out.append(invoices.read_invoice(path, label))
        except (OfficeError, OSError) as error:
            out.append(
                invoices.Invoice(label, path.suffix.lower().lstrip("."), problems=[str(error)])
            )
    return out


def _deck_folders(data_dir: Path) -> list[tuple[str, Path]]:
    """The app's own templates folder, listed before the system's."""
    return [("app", data_dir / "templates")]


def _table(folder: Folder, item: dict[str, Any] | str) -> tuple[str, tables.Sheet]:
    spec = {"path": item} if isinstance(item, str) else item
    path = folder.resolve(str(spec.get("path", "")), TABLES)
    sheet = tables.pick_sheet(tables.read_table_file(path), spec.get("sheet"))
    return str(spec.get("label") or path.stem), sheet


# ---- reading -------------------------------------------------------------------------------------


class OfficeReadTool(_OfficeTool):
    hard_cancellable = True

    def __init__(self, folder: Folder, data_dir: Path) -> None:
        super().__init__(folder, data_dir)
        self._spec = _spec(
            "office_read",
            "Read and check office files of the folder, without changing them. Actions: "
            "paragraphs (a Word file's paragraphs, numbered); comments (a Word file's comments and "
            "the text each marks); check_official (a Word document against the official document "
            "format GB/T 9704: page, fonts, sizes, line spacing, numbering 一、（一）1.（1）, "
            "发文字号, 成文日期, page numbers); proofread (mechanical problems of Chinese text: "
            "half-width punctuation, unpaired brackets, doubled words, common miswritten words, "
            "numbers and dates — you judge meaning and word choice yourself); compare (two "
            "versions of a .docx, .pdf, .txt or .md: what changed); segments (the numbered text "
            "segments of a .docx, .pptx or .xlsx, for translate in word_document); inspect (an "
            ".xlsx or .csv: sheets, values and formulas); email (an .eml or Outlook .msg: headers, "
            "body, attachments); pdf_info; invoices (e-invoices from .xml, .ofd or .pdf files or "
            "folders: number, date, seller, amounts, duplicates, checks); templates (the document "
            "templates); deck_templates (PowerPoint templates on this computer, for "
            "slides_from_template); layouts (a PowerPoint template's slide layouts, by file or "
            "installed id); template_fields (the {{fields}} and merge fields of a Word template).",
            [
                "paragraphs",
                "comments",
                "check_official",
                "proofread",
                "compare",
                "segments",
                "inspect",
                "email",
                "pdf_info",
                "invoices",
                "templates",
                "deck_templates",
                "layouts",
                "template_fields",
            ],
            {
                "file": _STR,
                "old": _STR,
                "new": _STR,
                "paths": _STRS,
                "text": {"type": "string", "maxLength": 200_000},
                "sheet": _STR,
                "offset": {"type": "integer", "minimum": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 2000},
            },
            effect="read",
        )

    async def _run(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._read, arguments)

    def _read(self, arguments: dict[str, Any]) -> dict[str, Any]:
        action = arguments["action"]
        offset, limit = int(arguments.get("offset") or 0), int(arguments.get("limit") or 200)
        if action == "deck_templates":
            found = slides.installed_templates(_deck_folders(self.data_dir))
            return {
                "templates": [
                    {key: item[key] for key in ("id", "name", "source")} for item in found
                ],
                "note": "app = the app's templates folder; personal = the user's own Office "
                "templates; office = the ones that come with Microsoft Office. A .pptx/.potx in "
                "the open folder can be used by its path too.",
            }
        if action == "templates":
            return {
                "templates": templates.listing(self.data_dir / "templates"),
                "user_folder": str(self.data_dir / "templates"),
            }
        if action == "invoices":
            self._require(arguments, "paths")
            read = _read_invoices(self.folder, arguments["paths"])
            summary = invoices.summarize(read)
            unique = summary.pop("unique")
            return {**summary, "invoices": [invoice.as_dict() for invoice in unique][:500]}
        if action == "compare":
            self._require(arguments, "old", "new")
            return _compare_summary(self.folder, arguments["old"], arguments["new"])
        if action == "proofread" and arguments.get("text"):
            texts = str(arguments["text"]).split("\n")
            findings = proofread.check_paragraphs(texts)
            return {
                "findings": [_finding(f, texts) for f in findings[:300]],
                "count": len(findings),
            }
        self._require(arguments, "file")
        raw = arguments["file"]
        if action == "paragraphs":
            _, data = self.folder.read(raw, DOCX)
            rows = [
                {"n": number, "text": paragraph.text}
                for number, paragraph in enumerate(body_paragraphs(open_docx(data)), start=1)
                if paragraph.text.strip()
            ]
            return {"paragraphs": rows[offset : offset + limit], "count": len(rows)}
        if action == "comments":
            _, data = self.folder.read(raw, DOCX)
            return {"comments": read_comments(open_docx(data))}
        if action == "check_official":
            _, data = self.folder.read(raw, DOCX)
            report = gongwen.check(data)
            return {
                "issues": [issue.as_dict() for issue in report.issues],
                "count": len(report.issues),
                "roles": _role_counts(report.roles),
            }
        if action == "proofread":
            path, data = self.folder.read(raw, {".docx", ".txt", ".md"})
            texts = (
                [p.text for p in body_paragraphs(open_docx(data))]
                if path.suffix.lower() == ".docx"
                else data.decode("utf-8", errors="replace").split("\n")
            )
            findings = proofread.check_paragraphs(texts)
            return {
                "findings": [_finding(f, texts) for f in findings[:300]],
                "count": len(findings),
            }
        if action == "segments":
            path, data = self.folder.read(raw, {".docx", ".pptx", ".xlsx"})
            items = translate.segments(data, path.name)
            return {
                "segments": [
                    {"id": item.id, "text": item.text} for item in items[offset : offset + limit]
                ],
                "count": len(items),
                "next_offset": offset + limit if offset + limit < len(items) else None,
            }
        if action == "inspect":
            path = self.folder.resolve(raw, TABLES)
            sheets = tables.read_table_file(path)
            chosen = (
                [tables.pick_sheet(sheets, arguments.get("sheet"))]
                if arguments.get("sheet")
                else sheets
            )
            out = []
            for sheet in chosen[:10]:
                window = sheet.rows[offset : offset + min(limit, 200)]
                formulas = {
                    f"{tables.column_letter(c)}{r + 1}": text
                    for (r, c), text in sheet.formulas.items()
                    if offset <= r < offset + len(window)
                }
                out.append(
                    {
                        "name": sheet.name,
                        "rows": len(sheet.rows),
                        "columns": len(sheet.rows[0]) if sheet.rows else 0,
                        "values": table_ops.preview(window, len(window)),
                        "formulas": formulas,
                        "merged": sheet.merged[:50],
                    }
                )
            return {"sheets": out, "sheet_names": [sheet.name for sheet in sheets]}
        if action == "email":
            path = self.folder.resolve(raw, {".eml", ".msg"})
            return mail.read_mail(path).as_dict()
        if action == "pdf_info":
            _, data = self.folder.read(raw, {".pdf"})
            return pdf.info(data)
        if action == "layouts":
            if str(raw).startswith("installed:"):
                data = slides.installed_template(str(raw), _deck_folders(self.data_dir))
            else:
                _, data = self.folder.read(raw, {".pptx", ".potx"})
            return {"layouts": slides.describe(slides.open_template(data))}
        if action == "template_fields":
            _, data = self.folder.read(raw, DOCX)
            return {"fields": merge.template_fields(data)}
        raise ToolArgumentError(f"unknown action {action}")


def _finding(finding: proofread.Finding, texts: list[str]) -> dict[str, object]:
    out = finding.as_dict()
    out["context"] = proofread.context(texts[finding.paragraph - 1], finding.start, finding.end)
    return out


def _role_counts(roles: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for role in roles:
        if role != "blank":
            counts[role] = counts.get(role, 0) + 1
    return counts


def _compare_summary(folder: Folder, old: str, new: str) -> dict[str, Any]:
    old_path, old_data = folder.read(old, {".docx", ".pdf", ".txt", ".md"})
    new_path, new_data = folder.read(new, {".docx", ".pdf", ".txt", ".md"})
    if old_path.suffix.lower() == ".docx" and new_path.suffix.lower() == ".docx":
        result = compare.compare_docx(old_data, new_data)
    else:
        result = compare.compare_lines(_lines(old_path, old_data), _lines(new_path, new_data))
    return result.summary()


def _lines(path: Path, data: bytes) -> list[tuple[int, str]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return compare.pdf_lines(data)
    if suffix == ".docx":
        return [
            (1, text) for text in (p.text for p in body_paragraphs(open_docx(data))) if text.strip()
        ]
    return [
        (1, line.strip())
        for line in data.decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]


# ---- Word ----------------------------------------------------------------------------------------


class WordDocumentTool(_OfficeTool):
    def __init__(self, folder: Folder, data_dir: Path) -> None:
        super().__init__(folder, data_dir)
        self._spec = _spec(
            "word_document",
            "Change and make Word documents of the folder. Actions: revise (edits as tracked "
            "changes the user accepts or rejects in Word, with optional comments; each edit finds "
            "text within one paragraph — read it with office_read paragraphs first; replace '' "
            "deletes, a comment without replace only comments); compare (two versions of a .docx: "
            "a copy of the new one with the differences as tracked changes, and a summary); "
            "fix_official (a copy laid out to GB/T 9704: page, fonts and sizes by role, line "
            "spacing, numbering, 发文字号, dates, page numbers); create_official (file: the new "
            ".docx; an official document — 通知, 请示, 报告, 函, 纪要 — laid out to GB/T 9704 "
            "from document: title, "
            "organ, number, signer (上行文), recipients, body (one paragraph per line; levels 一、 "
            "（一） 1. （1） are set in their fonts), attachments, signature, date, note, cc, printer, "
            "print_date, kind 文件/纪要/普通, attendees/absent/observers for 纪要); mail_merge (a "
            "Word template with {{字段}} or merge fields filled once per row of an .xlsx/.csv: "
            "one file per row named by name_pattern like '{{姓名}}-录用通知', or combine into one "
            "document, pdf for one PDF too); translate (write translations of the segments listed "
            "by office_read segments into a copy of a .docx, .pptx or .xlsx, replacing the text or "
            "below it with mode bilingual; send them in batches, each call adds to the earlier ones "
            "and writes the copy again).",
            ["revise", "compare", "fix_official", "create_official", "mail_merge", "translate"],
            {
                "file": _STR,
                "output": _STR,
                "old": _STR,
                "new": _STR,
                "author": {"type": "string", "maxLength": 60},
                "edits": {
                    "type": "array",
                    "maxItems": 300,
                    "items": {
                        "type": "object",
                        "properties": {
                            "find": {"type": "string", "minLength": 1, "maxLength": 2000},
                            "replace": {"type": "string", "maxLength": 5000},
                            "comment": {"type": "string", "maxLength": 2000},
                            "occurrence": {"type": "integer", "minimum": 1},
                            "all": {"type": "boolean"},
                        },
                        "required": ["find"],
                        "additionalProperties": False,
                    },
                },
                "document": _OBJ,
                "template": _STR,
                "data": _STR,
                "sheet": _STR,
                "name_pattern": _STR,
                "folder": _STR,
                "combine": {"type": "boolean"},
                "pdf": {"type": "boolean"},
                "rows": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 1},
                    "maxItems": 5000,
                },
                "translations": {
                    "type": "array",
                    "maxItems": 2000,
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "maxLength": 40},
                            "text": {"type": "string", "maxLength": 20000},
                        },
                        "required": ["id", "text"],
                        "additionalProperties": False,
                    },
                },
                "mode": {"type": "string", "enum": ["replace", "bilingual"]},
                "report": {"type": "boolean"},
            },
        )

    async def _run(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        action = arguments["action"]
        handler = {
            "revise": self._revise,
            "compare": self._compare,
            "fix_official": self._fix,
            "create_official": self._create,
            "mail_merge": self._merge,
            "translate": self._translate,
        }[action]
        return await handler(arguments, context)

    async def _revise(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        self._require(arguments, "file", "edits")
        path, data = self.folder.read(arguments["file"], DOCX)

        def work() -> tuple[bytes, list[dict[str, Any]]]:
            package = open_docx(data)
            revisions = Revisions(package, str(arguments.get("author") or "Agent Workspace"))
            results = []
            for edit in arguments["edits"]:
                spans = locate(
                    body_paragraphs(package),
                    edit["find"],
                    None if edit.get("all") else edit.get("occurrence") or 1,
                )
                if not spans:
                    results.append({"find": edit["find"][:80], "applied": 0})
                    continue
                count = 0
                # Later matches first, so earlier offsets stay right.
                for paragraph, start, end in reversed(spans):
                    current = next(
                        p for p in body_paragraphs(package) if p.element is paragraph.element
                    )
                    if "replace" in edit:
                        revisions.replace(
                            current, start, end, edit["replace"], edit.get("comment", "")
                        )
                    elif edit.get("comment"):
                        revisions.comment(current, start, end, edit["comment"])
                    count += 1
                results.append({"find": edit["find"][:80], "applied": count})
            revisions.finish()
            return package.to_bytes(), results

        out, results = await asyncio.to_thread(work)
        target = arguments.get("output") or self.folder.relative(path)
        written = await self.folder.write(context, target, out, replace=not arguments.get("output"))
        missing = [item["find"] for item in results if not item["applied"]]
        return {**written, "edits": results, "not_found": missing}

    async def _compare(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        self._require(arguments, "old", "new")
        _, old = self.folder.read(arguments["old"], DOCX)
        new_path, new = self.folder.read(arguments["new"], DOCX)
        result = await asyncio.to_thread(
            compare.compare_docx, old, new, str(arguments.get("author") or "比对")
        )
        assert result.redline is not None
        written = await self.folder.write(
            context, arguments.get("output") or self.folder.beside(new_path, "比对"), result.redline
        )
        out: dict[str, Any] = {**written, **result.summary()}
        if arguments.get("report"):
            report = compare.report_markdown(f"{new_path.stem} 修改说明", result)
            out["report"] = (
                await self.folder.write(
                    context, self.folder.beside(new_path, "修改说明", ".md"), report.encode("utf-8")
                )
            )["path"]
        return out

    async def _fix(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        self._require(arguments, "file")
        path, data = self.folder.read(arguments["file"], DOCX)
        fixed, done = await asyncio.to_thread(gongwen.fix, data)
        written = await self.folder.write(
            context, arguments.get("output") or self.folder.beside(path, "已按公文格式调整"), fixed
        )
        remaining = [issue.as_dict() for issue in gongwen.check(fixed).issues]
        return {**written, "done": done, "remaining_issues": remaining[:50]}

    async def _create(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        self._require(arguments, "file", "document")
        if not str(arguments["file"]).lower().endswith(".docx"):
            raise ToolArgumentError("file must end in .docx")
        document = gongwen.Document.from_dict(arguments["document"])
        data = await asyncio.to_thread(gongwen.build, document)
        written = await self.folder.write(context, arguments["file"], data)
        issues = [issue.as_dict() for issue in gongwen.check(data).issues]
        return {**written, "issues": issues[:20]}

    async def _merge(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        self._require(arguments, "template", "data")
        template_path, template = self.folder.read(arguments["template"], DOCX)
        label, sheet = _table(
            self.folder, {"path": arguments["data"], "sheet": arguments.get("sheet")}
        )
        records = sheet.records()
        wanted = arguments.get("rows")
        if wanted:
            records = [records[number - 1] for number in wanted if 0 < number <= len(records)]
        if not records:
            raise ToolArgumentError(f"{label} has no rows to merge")
        if len(records) > 2000:
            raise ToolArgumentError("at most 2000 rows are merged at a time")
        filled: list[bytes] = []
        missing: set[str] = set()
        for record in records:
            data, gaps = await asyncio.to_thread(merge.fill, template, record)
            filled.append(data)
            missing.update(gaps)
        outputs: list[str] = []
        folder = str(arguments.get("folder") or f"{template_path.stem}-合并")
        if arguments.get("combine") or arguments.get("pdf"):
            combined = await asyncio.to_thread(merge.combine, filled)
            written = await self.folder.write(
                context,
                f"{folder}/{template_path.stem}-合并.docx"
                if not arguments.get("combine")
                else arguments.get("output") or f"{template_path.stem}-合并.docx",
                combined,
            )
            outputs.append(written["path"])
            if arguments.get("pdf"):
                source = self.folder.resolve(written["path"])
                pdf_data = await asyncio.to_thread(convert.to_pdf, source)
                outputs.append(
                    (
                        await self.folder.write(
                            context,
                            str(Path(written["path"]).with_suffix(".pdf").as_posix()),
                            pdf_data,
                        )
                    )["path"]
                )
        else:
            pattern = str(arguments.get("name_pattern") or "")
            for number, (record, data) in enumerate(zip(records, filled, strict=True), start=1):
                name = merge.file_name(pattern, record, number)
                outputs.append(
                    (await self.folder.write(context, f"{folder}/{name}.docx", data))["path"]
                )
        return {
            "files": outputs[:200],
            "count": len(outputs),
            "rows": len(records),
            "fields_without_data": sorted(missing),
        }

    async def _translate(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        self._require(arguments, "file", "translations")
        path, data = self.folder.read(arguments["file"], {".docx", ".pptx", ".xlsx"})
        cache_path = (
            self.folder.paths.root
            / ".agent"
            / "translations"
            / f"{hashlib.sha256(data).hexdigest()[:24]}.json"
        )
        stored: dict[str, str] = {}
        if cache_path.is_file():
            try:
                stored = json.loads(cache_path.read_text(encoding="utf-8")).get("translations", {})
            except (OSError, ValueError):
                stored = {}
        known = {item.id for item in translate.segments(data, path.name)}
        unknown = [item["id"] for item in arguments["translations"] if item["id"] not in known]
        stored.update(
            {item["id"]: item["text"] for item in arguments["translations"] if item["id"] in known}
        )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {"source": self.folder.relative(path), "translations": stored}, ensure_ascii=False
            ),
            encoding="utf-8",
        )
        mode = arguments.get("mode") or "replace"
        out, applied = await asyncio.to_thread(
            translate.apply, data, path.name, stored, mode == "bilingual"
        )
        target = arguments.get("output") or self.folder.beside(
            path, "译文" if mode == "replace" else "对照"
        )
        written = await self.folder.write(context, target, out, replace=True)
        return {
            **written,
            "translated": applied,
            "segments": len(known),
            "remaining": len(known - set(stored)),
            "unknown_ids": unknown[:20],
        }


# ---- spreadsheets --------------------------------------------------------------------------------

_SHEET_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "maxLength": 31},
        "rows": {"type": "array", "maxItems": 100_000, "items": {"type": "array"}},
        "header": {"type": "boolean"},
        "borders": {"type": "boolean"},
        "filter": {"type": "boolean"},
        "freeze": {"type": "string"},
        "widths": {"type": "object"},
        "formats": {"type": "object"},
        "merge": _STRS,
        "highlight": {"type": "array", "items": _OBJ},
        "bold_rows": {"type": "array", "items": {"type": "integer"}},
        "conditional": {"type": "array", "items": _OBJ},
        "charts": {"type": "array", "items": _OBJ, "maxItems": 10},
    },
    "required": ["rows"],
    "additionalProperties": False,
}
_TABLE_REF = {
    "type": "object",
    "properties": {"path": _STR, "sheet": _STR, "label": {"type": "string", "maxLength": 40}},
    "required": ["path"],
    "additionalProperties": False,
}


class SpreadsheetTool(_OfficeTool):
    def __init__(self, folder: Folder, data_dir: Path) -> None:
        super().__init__(folder, data_dir)
        self._spec = _spec(
            "spreadsheet",
            "Make Excel workbooks in the folder. Actions: build (sheets of rows; a cell starting "
            "with = is a real formula (=SUM(B2:B9), =B2*C2, =IF(..), =SUMIF(..) …) whose value is "
            "worked out and stored; dates as 2026-10-28; options: header (bold, coloured, frozen, "
            "filter; default on), formats {range: '#,##0.00' | '0.0%' | 'yyyy-mm-dd'}, widths "
            "{column: width}, merge ['A1:D1'], highlight [{range, color}], bold_rows, conditional "
            "[{range, type: greater_than|less_than|between|equal|duplicates|formula|color_scale|"
            "data_bar, value, formula, color}], charts [{type: column|bar|line|pie, title, "
            "categories 'A2:A9', series [{name, values 'B2:B9'}], at 'H2', stacked}]); merge "
            "(tables one under another with a source column, or how=join to look up columns of "
            "the others by key columns like VLOOKUP); compare (two tables by key columns: rows only "
            "in one, cells that differ highlighted); payslips (工资条: each row under its own "
            "header, a blank row between); invoices (an e-invoice summary workbook from .xml, "
            ".ofd and .pdf files or folders: details, totals by seller and category with formulas, "
            "duplicates and problems).",
            ["build", "merge", "compare", "payslips", "invoices"],
            {
                "file": _STR,
                "output": _STR,
                "sheets": {"type": "array", "items": _SHEET_SCHEMA, "maxItems": 30},
                "inputs": {"type": "array", "items": _TABLE_REF, "maxItems": 50},
                "first": _TABLE_REF,
                "second": _TABLE_REF,
                "how": {"type": "string", "enum": ["stack", "join"]},
                "keys": _STRS,
                "columns": _STRS,
                "header_rows": {"type": "integer", "minimum": 1, "maximum": 5},
                "blank_rows": {"type": "integer", "minimum": 0, "maximum": 3},
                "paths": _STRS,
            },
        )

    async def _run(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        action = arguments["action"]
        if action == "build":
            self._require(arguments, "file", "sheets")
            data, details = await asyncio.to_thread(xlsx.build, {"sheets": arguments["sheets"]})
            written = await self.folder.write(
                context, _xlsx_name(arguments["file"]), data, replace=True
            )
            return {**written, **details}
        if action == "merge":
            self._require(arguments, "inputs")
            inputs = [_table(self.folder, item) for item in arguments["inputs"]]
            if arguments.get("how") == "join":
                self._require(arguments, "keys")
                result = table_ops.join(
                    inputs[0], inputs[1:], arguments["keys"], arguments.get("columns")
                )
            else:
                result = table_ops.stack(inputs)
            return await self._save(result, arguments.get("output") or "合并结果.xlsx", context)
        if action == "compare":
            self._require(arguments, "first", "second")
            result = table_ops.compare(
                _table(self.folder, arguments["first"]),
                _table(self.folder, arguments["second"]),
                arguments.get("keys") or [],
                arguments.get("columns"),
            )
            return await self._save(result, arguments.get("output") or "比对结果.xlsx", context)
        if action == "payslips":
            self._require(arguments, "first")
            _label, sheet = _table(self.folder, arguments["first"])
            result = table_ops.payslips(
                sheet,
                int(arguments.get("header_rows") or 1),
                _int(arguments, "blank_rows", 1),
            )
            return await self._save(result, arguments.get("output") or "工资条.xlsx", context)
        self._require(arguments, "paths")
        read = await asyncio.to_thread(_read_invoices, self.folder, arguments["paths"])
        summary = invoices.summarize(read)
        spec = invoice_workbook(summary)
        result = table_ops.Result(
            spec, {key: value for key, value in summary.items() if key != "unique"}
        )
        return await self._save(result, arguments.get("output") or "发票汇总.xlsx", context)

    async def _save(
        self, result: table_ops.Result, output: str, context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        data, details = await asyncio.to_thread(xlsx.build, result.spec)
        written = await self.folder.write(context, _xlsx_name(output), data)
        first = result.spec["sheets"][0]["rows"]
        return {**written, **result.summary, "preview": table_ops.preview(first, 8), **details}


def _xlsx_name(name: str) -> str:
    return name if name.lower().endswith(".xlsx") else f"{name}.xlsx"


def _category(invoice: invoices.Invoice) -> str:
    for item in invoice.items:
        if item.startswith("*") and item.count("*") >= 2:
            return item.split("*")[1]
    return "其他"


def invoice_workbook(summary: dict[str, Any]) -> dict[str, Any]:
    unique: list[invoices.Invoice] = summary["unique"]
    detail: list[list[Any]] = [
        [
            "序号",
            "发票号码",
            "开票日期",
            "销售方",
            "购买方",
            "类别",
            "项目",
            "金额",
            "税额",
            "价税合计",
            "文件",
            "问题",
        ]
    ]
    for number, invoice in enumerate(unique, start=1):
        detail.append(
            [
                number,
                invoice.number,
                invoice.date,
                invoice.seller,
                invoice.buyer,
                _category(invoice),
                "；".join(invoice.items[:3]),
                float(Decimal(invoice.amount)) if invoice.amount else None,
                float(Decimal(invoice.tax)) if invoice.tax else None,
                float(Decimal(invoice.total)) if invoice.total else None,
                invoice.file,
                "；".join(invoice.problems),
            ]
        )
    last = len(detail)
    detail.append(
        [
            "合计",
            "",
            "",
            "",
            "",
            "",
            "",
            f"=SUM(H2:H{last})",
            f"=SUM(I2:I{last})",
            f"=SUM(J2:J{last})",
            "",
            "",
        ]
    )
    categories = sorted({_category(invoice) for invoice in unique})
    by_category: list[list[Any]] = [["类别", "张数", "价税合计"]]
    for row, name in enumerate(categories, start=2):
        by_category.append(
            [
                name,
                f"=COUNTIF(明细!F2:F{last},A{row})",
                f"=SUMIF(明细!F2:F{last},A{row},明细!J2:J{last})",
            ]
        )
    sellers = sorted({invoice.seller for invoice in unique if invoice.seller})
    by_seller: list[list[Any]] = [["销售方", "张数", "价税合计"]]
    for row, name in enumerate(sellers, start=2):
        by_seller.append(
            [
                name,
                f"=COUNTIF(明细!D2:D{last},A{row})",
                f"=SUMIF(明细!D2:D{last},A{row},明细!J2:J{last})",
            ]
        )
    problems = [["文件", "发票号码", "问题"]] + [
        [invoice.file, invoice.number, "；".join(invoice.problems)]
        for invoice in unique
        if invoice.problems
    ]
    problems += [
        [item["again"], item["number"], f"与 {item['first']} 重复"]
        for item in summary.get("duplicates", [])
    ]
    highlight = [
        {"range": f"A{row}:L{row}", "color": "FFC7CE"}
        for row, invoice in enumerate(unique, start=2)
        if invoice.problems
    ]
    sheets = [
        {
            "name": "明细",
            "rows": detail,
            "formats": {f"H2:J{last + 1}": "#,##0.00"},
            "bold_rows": [last + 1],
            "highlight": highlight,
        },
        {
            "name": "按类别",
            "rows": by_category,
            "formats": {f"C2:C{len(by_category)}": "#,##0.00"},
            "charts": [
                {
                    "type": "pie",
                    "title": "价税合计（按类别）",
                    "categories": f"A2:A{len(by_category)}",
                    "series": [{"name": "价税合计", "values": f"C2:C{len(by_category)}"}],
                    "at": "E2",
                }
            ]
            if len(by_category) > 1
            else [],
        },
        {"name": "按销售方", "rows": by_seller, "formats": {f"C2:C{len(by_seller)}": "#,##0.00"}},
        {"name": "问题与重复", "rows": problems},
    ]
    return {"sheets": sheets}


# ---- PDF -----------------------------------------------------------------------------------------


class PdfTool(_OfficeTool):
    def __init__(self, folder: Folder, data_dir: Path) -> None:
        super().__init__(folder, data_dir)
        self._spec = _spec(
            "pdf_tools",
            "Work on PDF files of the folder; results are new files. Actions: merge (inputs in "
            "order, each 'file.pdf' or 'file.pdf#1-3'); split (ranges like ['1-3','4-'] or every "
            "n pages); pick (pages into a new file); delete (pages removed); rotate (pages by "
            "90/180/270); page_numbers (pattern with {n} and {total} like '— {n} —' or '第{n}页 "
            "共{total}页', position bottom-center|bottom-right|bottom-outside|top-…, start, "
            "skip_first); watermark (text, opacity, angle, size); compress; images_to_pdf "
            "(pictures one per page, fit a4 or image); office_to_pdf (a Word, Excel or PowerPoint "
            "file, with the office suite on this computer); searchable (scanned pages given a "
            "hidden text layer by Windows text recognition, so they can be searched and copied). "
            "Pages are written like '1-3,5,8-', 'odd', 'even' or 'all'.",
            [
                "merge",
                "split",
                "pick",
                "delete",
                "rotate",
                "page_numbers",
                "watermark",
                "compress",
                "images_to_pdf",
                "office_to_pdf",
                "searchable",
            ],
            {
                "file": _STR,
                "inputs": _STRS,
                "output": _STR,
                "pages": {"type": "string", "maxLength": 500},
                "ranges": _STRS,
                "every": {"type": "integer", "minimum": 1},
                "angle": {"type": "integer", "enum": [90, 180, 270, -90]},
                "pattern": {"type": "string", "maxLength": 60},
                "position": {"type": "string", "maxLength": 30},
                "start": {"type": "integer", "minimum": 0},
                "size": {"type": "number", "minimum": 5, "maximum": 200},
                "skip_first": {"type": "boolean"},
                "text": {"type": "string", "maxLength": 100},
                "opacity": {"type": "number", "minimum": 0.02, "maximum": 1},
                "fit": {"type": "string", "enum": ["a4", "image"]},
                "password": {"type": "string", "maxLength": 200},
            },
        )

    async def _run(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        action = arguments["action"]
        if action == "merge":
            self._require(arguments, "inputs")
            documents = []
            for item in arguments["inputs"]:
                name, _, pages = item.partition("#")
                _, data = self.folder.read(name, {".pdf"})
                documents.append((data, pages or "all"))
            out = await asyncio.to_thread(pdf.merge, documents)
            first = self.folder.resolve(arguments["inputs"][0].partition("#")[0])
            written = await self.folder.write(
                context, arguments.get("output") or self.folder.beside(first, "合并"), out
            )
            return {**written, "pages": len(pdf.read(out).pages)}
        if action == "images_to_pdf":
            self._require(arguments, "inputs")
            images = await asyncio.to_thread(self._images, arguments["inputs"])
            out = await asyncio.to_thread(pdf.images_to_pdf, images, arguments.get("fit") or "a4")
            written = await self.folder.write(
                context, arguments.get("output") or "图片合成.pdf", out
            )
            return {**written, "pages": len(images)}
        self._require(arguments, "file")
        if action == "office_to_pdf":
            source = self.folder.resolve(arguments["file"], set(convert.KINDS))
            out = await asyncio.to_thread(convert.to_pdf, source)
            written = await self.folder.write(
                context,
                arguments.get("output")
                or self.folder.beside(source, "PDF", ".pdf").replace("（PDF）", ""),
                out,
            )
            return {**written, "converter": convert.available()}
        path, data = self.folder.read(arguments["file"], {".pdf"})
        if arguments.get("password"):
            data = await asyncio.to_thread(_decrypted, data, arguments["password"])
        pages = str(arguments.get("pages") or "all")
        if action == "split":
            parts = await asyncio.to_thread(
                pdf.split, data, arguments.get("ranges"), arguments.get("every")
            )
            files = []
            for label, part in parts:
                files.append(
                    (
                        await self.folder.write(
                            context,
                            f"{self.folder.relative(path.parent / path.stem) if path.parent != self.folder.paths.root else path.stem}-拆分/{path.stem}-{label}.pdf",
                            part,
                        )
                    )["path"]
                )
            return {"files": files[:200], "count": len(files)}
        label, work = {
            "pick": ("选页", lambda: pdf.pick(data, pages)),
            "delete": ("删页", lambda: pdf.delete(data, pages)),
            "rotate": ("旋转", lambda: pdf.rotate(data, pages, int(arguments.get("angle") or 90))),
            "page_numbers": (
                "页码",
                lambda: pdf.page_numbers(
                    data,
                    str(arguments.get("pattern") or "— {n} —"),
                    str(arguments.get("position") or "bottom-center"),
                    _int(arguments, "start", 1),
                    float(arguments.get("size") or 10.5),
                    pages,
                    bool(arguments.get("skip_first")),
                ),
            ),
            "watermark": (
                "水印",
                lambda: pdf.watermark(
                    data,
                    str(arguments.get("text") or "内部资料"),
                    float(arguments.get("size") or 54),
                    float(arguments.get("opacity") or 0.15),
                    float(arguments.get("angle") or 45),
                    pages,
                ),
            ),
            "compress": ("压缩", lambda: pdf.compress(data)),
            "searchable": ("可搜索", lambda: self._searchable(path, data, pages)),
        }[action]
        out = await asyncio.to_thread(work)
        written = await self.folder.write(
            context, arguments.get("output") or self.folder.beside(path, label), out
        )
        result: dict[str, Any] = {**written, "pages": len(pdf.read(out).pages)}
        if action == "compress":
            result["bytes_before"] = len(data)
        return result

    def _images(self, raw_items: list[str]) -> list[pdf.Jpeg]:
        import tempfile

        files = _paths(
            self.folder, raw_items, {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff"}
        )
        out: list[pdf.Jpeg | None] = [None] * len(files)
        others: list[tuple[int, Path]] = []
        for index, path in enumerate(files):
            info = (
                pdf.jpeg_info(path.read_bytes())
                if path.suffix.lower() in {".jpg", ".jpeg"}
                else None
            )
            if info:
                out[index] = info
            else:
                others.append((index, path))
        if others:
            with tempfile.TemporaryDirectory(prefix="aw-images-") as folder:
                converted = pdf.to_jpeg([path for _, path in others], Path(folder))
                for (index, _path), jpeg in zip(others, converted, strict=True):
                    out[index] = pdf.jpeg_info(jpeg.read_bytes())
        return [item for item in out if item is not None]

    def _searchable(self, path: Path, data: bytes, pages: str) -> bytes:
        reader = pdf.read(data)
        numbers = [index + 1 for index in pdf.parse_pages(pages, len(reader.pages))]
        recognized = pdf.recognize(path, numbers)
        return pdf.add_text_layer(data, recognized)


def _decrypted(data: bytes, password: str) -> bytes:
    from pypdf import PdfWriter

    reader = pdf.read(data, password)
    writer = PdfWriter(clone_from=reader)
    import io

    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


# ---- slides, e-mail, templates, meetings -------------------------------------------------------------


class SlidesTool(_OfficeTool):
    def __init__(self, folder: Folder, data_dir: Path) -> None:
        super().__init__(folder, data_dir)
        self._spec = _spec(
            "slides_from_template",
            "Make a PowerPoint deck on a template, with its layouts, fonts and colours: the "
            "user's own (.pptx or .potx of the folder), or one installed on this computer "
            "(an id from office_read deck_templates, like 'installed:office/2052/"
            "WidescreenPresentation'). Each slide: layout (a layout name from office_read "
            "layouts, or title, section, content, two, title_only, blank), title, subtitle, "
            "bullets (text, or [text, level] with level 0-4), picture (an image of the folder) "
            "or chart (a native chart the user can edit in PowerPoint: {type: column|bar|line|"
            "pie, title, categories [..], series [{name, values [..]}], stacked}) — beside the "
            "text when both are given, notes (speaker notes). The template's own "
            "sample slides are dropped unless keep_template_slides. The result lists warnings "
            "for crowded slides: fix them and build again. Follow the slide-deck skill.",
            ["build"],
            {
                "template": _STR,
                "path": _STR,
                "slides": {"type": "array", "items": _OBJ, "minItems": 1, "maxItems": 200},
                "keep_template_slides": {"type": "boolean"},
            },
        )

    async def _run(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        self._require(arguments, "template", "path", "slides")
        name = str(arguments["template"])
        if name.startswith("installed:"):
            template = await asyncio.to_thread(
                slides.installed_template, name, _deck_folders(self.data_dir)
            )
        else:
            _, template = self.folder.read(name, {".pptx", ".potx"})
        pictures: dict[str, bytes] = {}
        for slide in arguments["slides"]:
            if slide.get("picture"):
                _, data = self.folder.read(
                    str(slide["picture"]), {".png", ".jpg", ".jpeg", ".gif", ".bmp"}
                )
                pictures[str(slide["picture"])] = data
        data, details = await asyncio.to_thread(
            slides.build,
            template,
            arguments["slides"],
            pictures,
            bool(arguments.get("keep_template_slides")),
        )
        target = (
            arguments["path"]
            if str(arguments["path"]).lower().endswith(".pptx")
            else f"{arguments['path']}.pptx"
        )
        written = await self.folder.write(context, target, data, replace=True)
        return {**written, **details}


class EmailTool(_OfficeTool):
    def __init__(self, folder: Folder, data_dir: Path) -> None:
        super().__init__(folder, data_dir)
        self._spec = _spec(
            "email_files",
            "E-mail and calendar files in the folder; nothing is sent. Actions: draft (an .eml "
            "the user double-clicks: Outlook opens it as an unsent message to check and send; "
            "reply_to names an .eml/.msg of the folder to answer, quoting it; attachments are "
            "files of the folder); invite (an .ics invitation: title, start like '2026-11-05 "
            "14:30' in local time, end or minutes, location, description, attendees, reminder "
            "minutes); save_attachments (the attachments of an .eml/.msg saved into a folder).",
            ["draft", "invite", "save_attachments"],
            {
                "file": _STR,
                "to": _STRS,
                "cc": _STRS,
                "subject": {"type": "string", "maxLength": 500},
                "body": {"type": "string", "maxLength": 100_000},
                "reply_to": _STR,
                "attachments": _STRS,
                "title": {"type": "string", "maxLength": 300},
                "start": {"type": "string", "maxLength": 40},
                "end": {"type": "string", "maxLength": 40},
                "minutes": {"type": "integer", "minimum": 5, "maximum": 1440},
                "location": {"type": "string", "maxLength": 300},
                "description": {"type": "string", "maxLength": 10_000},
                "attendees": _STRS,
                "organizer": {"type": "string", "maxLength": 300},
                "reminder": {"type": "integer", "minimum": 0, "maximum": 10080},
                "folder": _STR,
            },
        )

    async def _run(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        action = arguments["action"]
        if action == "draft":
            self._require(arguments, "body")
            original = (
                mail.read_mail(self.folder.resolve(arguments["reply_to"], {".eml", ".msg"}))
                if arguments.get("reply_to")
                else None
            )
            to = mail.addresses(arguments.get("to"))
            if not to and original is not None:
                to = mail.addresses(original.sender)
            attachments = []
            for raw in arguments.get("attachments") or []:
                path, data = self.folder.read(raw)
                attachments.append((path.name, data))
            data = mail.draft(
                to,
                str(arguments.get("subject") or ""),
                str(arguments["body"]),
                mail.addresses(arguments.get("cc")),
                original,
                attachments,
            )
            subject = str(
                arguments.get("subject") or (original.subject if original else "") or "草稿"
            )
            written = await self.folder.write(
                context, arguments.get("file") or f"邮件草稿/{safe_name(subject, '草稿')}.eml", data
            )
            return {
                **written,
                "to": to,
                "note": "Double-click the file: Outlook opens it as a draft to send.",
            }
        if action == "invite":
            self._require(arguments, "title", "start")
            data = mail.invitation(
                str(arguments["title"]),
                str(arguments["start"]),
                arguments.get("end"),
                int(arguments.get("minutes") or 60),
                str(arguments.get("location") or ""),
                str(arguments.get("description") or ""),
                arguments.get("attendees"),
                str(arguments.get("organizer") or ""),
                _int(arguments, "reminder", 15),
            )
            written = await self.folder.write(
                context,
                arguments.get("file") or f"{safe_name(str(arguments['title']), '会议')}.ics",
                data,
            )
            return {
                **written,
                "note": "Opening the .ics adds it to Outlook or the system calendar.",
            }
        self._require(arguments, "file")
        source = self.folder.resolve(arguments["file"], {".eml", ".msg"})
        message = mail.read_mail(source)
        folder = str(arguments.get("folder") or f"{source.stem}-附件")
        saved = [
            (
                await self.folder.write(
                    context, f"{folder}/{safe_name(item.name, 'attachment')}", item.data
                )
            )["path"]
            for item in message.attachments
        ]
        return {"files": saved, "count": len(saved)}


class TemplateTool(_OfficeTool):
    def __init__(self, folder: Folder, data_dir: Path) -> None:
        super().__init__(folder, data_dir)
        self._spec = _spec(
            "office_template",
            "Make a document from a template (office_read templates lists them: official "
            "documents to GB/T 9704, forms, letters, reports, workbooks, and the user's own) with "
            "its {{fields}} filled from values; fields without a value stay empty for the user.",
            ["create"],
            {"template": _STR, "file": _STR, "values": {"type": "object"}},
        )

    async def _run(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        self._require(arguments, "template")
        values = {str(key): value for key, value in (arguments.get("values") or {}).items()}
        data, suffix, missing, name = await asyncio.to_thread(
            templates.create, arguments["template"], self.data_dir / "templates", values
        )
        target = str(arguments.get("file") or f"{name}{suffix}")
        if not target.lower().endswith(suffix):
            target += suffix
        written = await self.folder.write(context, target, data)
        return {**written, "fields_left_empty": missing}


class MeetingTool(_OfficeTool):
    def __init__(self, folder: Folder, data_dir: Path, speech: SpeechSource) -> None:
        super().__init__(folder, data_dir)
        self.speech = speech
        self._spec = _spec(
            "meeting_transcribe",
            "Transcribe a meeting recording of the folder (mp3, m4a, wav, ogg, flac, webm, mp4) "
            "with the speech-to-text service chosen in Settings → Voice: long recordings are cut "
            "into ten-minute parts; the transcript (with times) is written as Markdown beside it. "
            "Then write the minutes from it (the meeting-minutes skill), put the action items in "
            "the task list (todo) and make .ics invitations for follow-up meetings if asked.",
            ["transcribe"],
            {"path": _STR, "output": _STR},
            effect="network",
        )

    async def _run(
        self, arguments: dict[str, Any], context: ToolExecutionContext | None
    ) -> dict[str, Any]:
        self._require(arguments, "path")
        source = self.folder.resolve(arguments["path"], set(meeting._MIME))
        choice = self.speech()
        if choice is None:
            raise ToolError(
                "no speech-to-text service is chosen: Settings → Voice picks a provider and its model"
            )
        base_url, api_key, model = choice
        lines = await asyncio.to_thread(
            meeting.transcribe, source, meeting.http_transcriber(base_url, api_key, model)
        )
        if not lines:
            raise ToolError("the service returned no text for the recording")
        text = meeting.markdown(f"{source.stem} 转写", lines)
        written = await self.folder.write(
            context,
            arguments.get("output") or self.folder.beside(source, "转写", ".md"),
            text.encode("utf-8"),
        )
        return {
            **written,
            "lines": len(lines),
            "duration": meeting.clock(lines[-1].start),
            "start_of_text": text[:4000],
        }


def office_tools(
    workspace: Path, data_dir: Path, versions: FileVersions | None, speech: SpeechSource
) -> tuple[Tool, ...]:
    folder = Folder(workspace, versions)
    return (
        OfficeReadTool(folder, data_dir),
        WordDocumentTool(folder, data_dir),
        SpreadsheetTool(folder, data_dir),
        PdfTool(folder, data_dir),
        SlidesTool(folder, data_dir),
        EmailTool(folder, data_dir),
        TemplateTool(folder, data_dir),
        MeetingTool(folder, data_dir, speech),
    )


__all__ = ["office_tools"]
