"""Apply point corrections made in the app: ``python -m aw_sciplot.correct --points
figures/x.points.json --edits edits.json [--note text]``.

The original data file is never changed. The first correction writes ``<name>.corrected<ext>``
beside it, later ones change that copy; every changed cell (old and new value, time, note) is
appended to ``<name>.corrections.csv``. Prints a JSON summary.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aw_sciplot import data as data_module
from aw_sciplot import points


def corrected_path(original: Path) -> Path:
    return original.with_name(f"{original.stem}.corrected{original.suffix or '.csv'}")


def log_path(original: Path) -> Path:
    return original.with_name(f"{original.stem}.corrections.csv")


def _write(frame: Any, target: Path) -> None:
    suffix = target.suffix.lower()
    temporary = target.with_name(f".{target.name}.part")
    if suffix in {".xlsx", ".xlsm"}:
        frame.to_excel(temporary, index=False, engine="openpyxl")
    elif suffix == ".json":
        frame.to_json(temporary, orient="records", force_ascii=False)
    elif suffix in {".tsv", ".tab"}:
        frame.to_csv(temporary, sep="\t", index=False)
    else:
        frame.to_csv(temporary, index=False)
    os.replace(temporary, target)


def run(points_file: Path, edits: list[dict[str, Any]], note: str = "") -> dict[str, Any]:
    document = json.loads(points_file.read_text(encoding="utf-8"))
    cwd = Path(document.get("cwd") or points_file.parent)
    original = Path(document["data"])
    if not original.is_absolute():
        original = cwd / original
    copy = corrected_path(original)
    frame = data_module.read(copy if copy.is_file() else original)
    result, log = points.apply_edits(frame, edits)
    _write(result, copy)
    history = log_path(original)
    new_log = not history.is_file()
    stamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    with history.open("a", encoding="utf-8-sig" if new_log else "utf-8", newline="") as stream:
        writer = csv.writer(stream)
        if new_log:
            writer.writerow(["data_row", "column", "old_value", "new_value", "edited_at", "note"])
        for entry in log:
            writer.writerow(
                [entry["row"] + 1, entry["column"], entry["old"], entry["new"], stamp, note]
            )
    return {
        "original": str(original),
        "corrected": str(copy),
        "log": str(history),
        "changed": log,
        "override": {str(original.resolve()): str(copy.resolve())},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aw_sciplot.correct")
    parser.add_argument("--points", required=True)
    parser.add_argument("--edits", required=True)
    parser.add_argument("--note", default="")
    arguments = parser.parse_args(argv)
    try:
        edits = json.loads(Path(arguments.edits).read_text(encoding="utf-8"))
        summary = run(Path(arguments.points), edits, arguments.note)
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stdout)
        return 2
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
