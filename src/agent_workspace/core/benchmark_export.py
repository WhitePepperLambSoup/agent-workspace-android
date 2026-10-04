"""Benchmark report export helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from agent_workspace.core.benchmarks import BenchmarkReport


def benchmark_report_document(report: BenchmarkReport) -> dict[str, Any]:
    return {
        "cases": report.cases,
        "passed": report.passed,
        "weighted_score": report.weighted_score,
        "by_category": {category.value: score for category, score in report.by_category.items()},
        "verdicts": [
            {
                "case_id": verdict.case_id,
                "category": verdict.category.value,
                "passed": verdict.passed,
                "score": verdict.score,
                "failures": list(verdict.failures),
            }
            for verdict in report.verdicts
        ],
    }


def export_benchmark_report(
    report: BenchmarkReport,
    destination: str | Path,
    *,
    format: str = "json",
) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = benchmark_report_document(report)
    if format == "json":
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path
    if format == "csv":
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            writer = csv.writer(stream)
            writer.writerow(("case_id", "category", "passed", "score", "failures"))
            for verdict in report.verdicts:
                writer.writerow(
                    (
                        verdict.case_id,
                        verdict.category.value,
                        "true" if verdict.passed else "false",
                        verdict.score,
                        "; ".join(verdict.failures),
                    )
                )
        return path
    raise ValueError("benchmark export format must be json or csv")


__all__ = [
    "benchmark_report_document",
    "export_benchmark_report",
]
