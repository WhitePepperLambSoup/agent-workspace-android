"""Structured Deliverable and Research Report Exporter.

Generates verifiable research and deliverable reports in Markdown, HTML, and
archive bundle formats, linking claims directly to evidentiary artifacts,
citations, and source URLs.
"""

from __future__ import annotations

import html
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_workspace.storage.sqlite import SQLiteEventStore


@dataclass(frozen=True, slots=True)
class ReportSource:
    source_id: str
    title: str
    url: str
    artifact_sha256: str
    artifact_bytes: int
    fetched_at: str
    summary: str = ""
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class ReportCitation:
    citation_id: str
    source_id: str
    claim: str
    quote: str
    locator: str = ""


@dataclass(frozen=True, slots=True)
class ReportMetadata:
    title: str
    session_id: str
    workspace: str
    model: str = "default"
    generated_at: str = ""
    executive_summary: str = ""
    findings: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DeliverableReport:
    metadata: ReportMetadata
    sources: tuple[ReportSource, ...] = ()
    citations: tuple[ReportCitation, ...] = ()
    deliverable_files: tuple[dict[str, Any], ...] = ()

    def to_markdown(self) -> str:
        """Render report as verifiable GitHub-flavored Markdown."""
        lines: list[str] = [
            f"# {self.metadata.title}",
            "",
            "> **Executive Deliverable & Research Report**  ",
            f"> **Generated:** {self.metadata.generated_at or datetime.now(UTC).isoformat()}  ",
            f"> **Session ID:** `{self.metadata.session_id}`  ",
            f"> **Workspace:** `{self.metadata.workspace}`  ",
            f"> **Model:** `{self.metadata.model}`",
            "",
            "## 1. Executive Summary",
            "",
            self.metadata.executive_summary or "No executive summary provided.",
            "",
        ]

        # Key Findings
        if self.metadata.findings:
            lines.extend(
                [
                    "## 2. Key Findings & Inferences",
                    "",
                ]
            )
            for idx, finding in enumerate(self.metadata.findings, start=1):
                lines.append(f"{idx}. {finding}")
            lines.append("")

        # Citations & Evidence
        if self.citations:
            lines.extend(
                [
                    "## 3. Verified Citations & Evidence",
                    "",
                    "| ID | Claim | Source Ref | Locator | Verifiable Quote |",
                    "|---|---|---|---|---|",
                ]
            )
            source_map = {s.source_id: (s.title or s.url) for s in self.sources}
            for c in self.citations:
                source_name = source_map.get(c.source_id, c.source_id)
                clean_claim = c.claim.replace("|", "\\|")
                clean_quote = f'"{c.quote.replace("|", "\\|")}"' if c.quote else "-"
                clean_loc = c.locator or "-"
                lines.append(
                    f"| `{c.citation_id[:8]}` | {clean_claim} | {source_name} | "
                    f"{clean_loc} | {clean_quote} |"
                )
            lines.append("")

        # Sources Verification Table
        if self.sources:
            header_row = (
                "| Source | URL | Artifact Hash (SHA-256) | Bytes | Fetched At | Completeness |"
            )
            lines.extend(
                [
                    "## 4. Sources Verification Table",
                    "",
                    header_row,
                    "|---|---|---|---|---|---|",
                ]
            )
            for s in self.sources:
                name = s.title or "Source"
                url_cell = f"[{s.url}]({s.url})" if s.url.startswith("http") else s.url
                hash_cell = f"`{s.artifact_sha256[:16]}...`" if s.artifact_sha256 else "-"
                complete_cell = "Truncated" if s.truncated else "Complete"
                lines.append(
                    f"| {name} | {url_cell} | {hash_cell} | "
                    f"{s.artifact_bytes} | {s.fetched_at} | {complete_cell} |"
                )
            lines.append("")

        # Uncertainties and Open Questions
        if self.metadata.uncertainties:
            lines.extend(
                [
                    "## 5. Uncertainties, Conflicts & Open Questions",
                    "",
                ]
            )
            for unc in self.metadata.uncertainties:
                lines.append(f"- {unc}")
            lines.append("")

        # Deliverables Manifest
        if self.deliverable_files:
            lines.extend(
                [
                    "## 6. Deliverable Artifacts",
                    "",
                ]
            )
            for f in self.deliverable_files:
                path = f.get("path", "unnamed")
                desc = f.get("description", "")
                lines.append(f"- **{path}**: {desc}")
            lines.append("")

        return "\n".join(lines)

    def to_html(self) -> str:
        """Render report as a standalone modern HTML document."""
        title_esc = html.escape(self.metadata.title)
        summary_esc = html.escape(self.metadata.executive_summary)

        findings_html = ""
        if self.metadata.findings:
            items = "".join(f"<li>{html.escape(f)}</li>" for f in self.metadata.findings)
            findings_html = f"<h2>Key Findings & Inferences</h2><ol>{items}</ol>"

        citations_rows = ""
        source_map = {s.source_id: (s.title or s.url) for s in self.sources}
        for c in self.citations:
            s_name = html.escape(source_map.get(c.source_id, c.source_id))
            claim_esc = html.escape(c.claim)
            quote_esc = f"<em>{html.escape(c.quote)}</em>" if c.quote else "-"
            loc_esc = html.escape(c.locator or "-")
            citations_rows += (
                f"<tr><td><code>{c.citation_id[:8]}</code></td><td>{claim_esc}</td>"
                f"<td>{s_name}</td><td>{loc_esc}</td><td>{quote_esc}</td></tr>"
            )

        citations_html = ""
        if citations_rows:
            citations_html = f"""
            <h2>Verified Citations & Evidence</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th><th>Claim</th><th>Source</th>
                        <th>Locator</th><th>Verifiable Quote</th>
                    </tr>
                </thead>
                <tbody>{citations_rows}</tbody>
            </table>
            """

        sources_rows = ""
        for s in self.sources:
            name_esc = html.escape(s.title or "Source")
            url_esc = html.escape(s.url)
            hash_esc = html.escape(s.artifact_sha256[:16] + "..." if s.artifact_sha256 else "-")
            status_esc = "Truncated" if s.truncated else "Complete"
            sources_rows += (
                f"<tr><td>{name_esc}</td><td><a href='{url_esc}'>{url_esc}</a></td>"
                f"<td><code>{hash_esc}</code></td><td>{s.artifact_bytes}</td>"
                f"<td>{s.fetched_at}</td><td>{status_esc}</td></tr>"
            )

        sources_html = ""
        if sources_rows:
            sources_html = f"""
            <h2>Sources Verification Table</h2>
            <table>
                <thead>
                    <tr>
                        <th>Source</th><th>URL</th><th>SHA-256</th>
                        <th>Bytes</th><th>Fetched At</th><th>Status</th>
                    </tr>
                </thead>
                <tbody>{sources_rows}</tbody>
            </table>
            """

        uncertainties_html = ""
        if self.metadata.uncertainties:
            items = "".join(f"<li>{html.escape(u)}</li>" for u in self.metadata.uncertainties)
            uncertainties_html = f"<h2>Uncertainties & Open Questions</h2><ul>{items}</ul>"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title_esc}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            color: #24292e;
            max-width: 960px;
            margin: 0 auto;
            padding: 32px 20px;
        }}
        h1 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
        h2 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; margin-top: 24px; }}
        .metadata-box {{
            background: #f6f8fa;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 24px;
        }}
        table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
        th, td {{ border: 1px solid #dfe2e5; padding: 8px 12px; text-align: left; }}
        th {{ background: #f6f8fa; }}
        code {{
            background: rgba(27,31,35,0.05);
            padding: 0.2em 0.4em;
            border-radius: 3px;
            font-family: SFMono-Regular, Consolas, monospace;
            font-size: 85%;
        }}
    </style>
</head>
<body>
    <h1>{title_esc}</h1>
    <div class="metadata-box">
        <strong>Session:</strong> <code>{self.metadata.session_id}</code> |
        <strong>Workspace:</strong> <code>{self.metadata.workspace}</code> |
        <strong>Generated:</strong> {self.metadata.generated_at}
    </div>
    <h2>Executive Summary</h2>
    <p>{summary_esc}</p>
    {findings_html}
    {citations_html}
    {sources_html}
    {uncertainties_html}
</body>
</html>
"""

    def export_bundle(self, output_dir: Path | str) -> dict[str, str]:
        """Export full deliverable bundle: report.md, report.html, manifest.json."""
        out_path = Path(output_dir).resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        md_file = out_path / "report.md"
        html_file = out_path / "report.html"
        manifest_file = out_path / "manifest.json"

        md_file.write_text(self.to_markdown(), encoding="utf-8")
        html_file.write_text(self.to_html(), encoding="utf-8")

        manifest = {
            "title": self.metadata.title,
            "session_id": self.metadata.session_id,
            "workspace": self.metadata.workspace,
            "generated_at": self.metadata.generated_at or datetime.now(UTC).isoformat(),
            "sources_count": len(self.sources),
            "citations_count": len(self.citations),
            "files": ["report.md", "report.html", "manifest.json"],
        }
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return {
            "markdown": str(md_file),
            "html": str(html_file),
            "manifest": str(manifest_file),
        }


class ReportExporterService:
    """Extracts research and conversation evidence from SQLite and builds deliverable reports."""

    @staticmethod
    def build_from_session(
        database_path: Path | str,
        session_id: str,
        *,
        title: str | None = None,
        executive_summary: str | None = None,
        workspace: str | None = None,
    ) -> DeliverableReport:
        db_file = Path(database_path)
        sources: list[ReportSource] = []
        citations: list[ReportCitation] = []
        findings: list[str] = []
        uncertainties: list[str] = []
        session_title = title or "Deliverable Report"

        if db_file.is_file():
            try:
                # 1. Fetch sources
                raw_sources = SQLiteEventStore.list_research_sources_read_only(db_file, session_id)
                for s in raw_sources:
                    sources.append(
                        ReportSource(
                            source_id=s.id,
                            title=s.title or s.url,
                            url=s.url,
                            artifact_sha256=s.artifact_sha256,
                            artifact_bytes=s.artifact_bytes,
                            fetched_at=s.fetched_at,
                            summary=s.summary,
                            truncated=s.truncated,
                        )
                    )

                # 2. Fetch citations
                raw_citations = SQLiteEventStore.list_citations_read_only(db_file, session_id)
                for c in raw_citations:
                    citations.append(
                        ReportCitation(
                            citation_id=c.id,
                            source_id=c.source_id,
                            claim=c.claim,
                            quote=c.quote or "",
                            locator=c.locator or "",
                        )
                    )
                    findings.append(c.claim)

                # 3. Fallback: inspect events directly if tables were not projected
                with sqlite3.connect(f"file:{db_file}?mode=ro", uri=True) as conn:
                    cursor = conn.cursor()
                    if not sources or not citations:
                        query = (
                            "SELECT type, data_json FROM events "
                            "WHERE session_id = ? ORDER BY sequence ASC"
                        )
                        cursor.execute(query, (session_id,))
                        existing_src_ids = {s.source_id for s in sources}
                        existing_cit_ids = {c.citation_id for c in citations}
                        for ev_type, data_json in cursor.fetchall():
                            if not data_json:
                                continue
                            try:
                                data = json.loads(data_json)
                            except Exception:
                                continue
                            if ev_type in {"research.source_fetched", "research.source_added"}:
                                sid = str(data.get("source_id", ""))
                                if sid and sid not in existing_src_ids:
                                    raw_title = data.get("title") or data.get("url", "Source")
                                    sources.append(
                                        ReportSource(
                                            source_id=sid,
                                            title=str(raw_title),
                                            url=str(data.get("url", "")),
                                            artifact_sha256=str(data.get("artifact_sha256", "")),
                                            artifact_bytes=int(data.get("artifact_bytes", 0)),
                                            fetched_at=str(data.get("fetched_at", "")),
                                            summary=str(data.get("summary", "")),
                                            truncated=bool(data.get("truncated", False)),
                                        )
                                    )
                                    existing_src_ids.add(sid)
                            elif ev_type in (
                                "research.citation_verified",
                                "research.citation_added",
                            ):
                                cid = str(data.get("citation_id", ""))
                                if cid and cid not in existing_cit_ids:
                                    citations.append(
                                        ReportCitation(
                                            citation_id=cid,
                                            source_id=str(data.get("source_id", "")),
                                            claim=str(data.get("claim", "")),
                                            quote=str(data.get("quote", "")),
                                            locator=str(data.get("locator", "")),
                                        )
                                    )
                                    findings.append(str(data.get("claim", "")))
                                    existing_cit_ids.add(cid)

                    # Read session title and messages for summary if not supplied
                    cursor.execute(
                        "SELECT title, workspace FROM sessions WHERE id = ?",
                        (session_id,),
                    )
                    row = cursor.fetchone()
                    if row:
                        if not title and row[0]:
                            session_title = row[0]
                        if not workspace and row[1]:
                            workspace = row[1]

                    if not executive_summary:
                        msg_query = (
                            "SELECT content FROM messages "
                            "WHERE session_id = ? AND role = 'assistant' "
                            "ORDER BY sequence DESC LIMIT 1"
                        )
                        cursor.execute(msg_query, (session_id,))
                        last_msg = cursor.fetchone()
                        if last_msg and last_msg[0]:
                            executive_summary = last_msg[0][:800]
            except Exception:
                pass

        metadata = ReportMetadata(
            title=session_title,
            session_id=session_id,
            workspace=workspace or ".",
            generated_at=datetime.now(UTC).isoformat(),
            executive_summary=executive_summary or "Autonomous investigation deliverable summary.",
            findings=tuple(findings),
            uncertainties=tuple(uncertainties),
        )

        return DeliverableReport(
            metadata=metadata,
            sources=tuple(sources),
            citations=tuple(citations),
        )


__all__ = [
    "DeliverableReport",
    "ReportCitation",
    "ReportExporterService",
    "ReportMetadata",
    "ReportSource",
]
