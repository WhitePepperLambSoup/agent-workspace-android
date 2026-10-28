"""Check saved figure files against a journal's rules: a vector format, file size, resolution and
the printed width (single or double column)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from aw_sciplot.figures import JOURNALS


def _dpi(raw: Any) -> int | None:
    # PNG stores pixels per metre: 300 DPI reads back as 299.9994, so round instead of truncate.
    if isinstance(raw, (tuple, list)):
        raw = raw[0] if raw else None
    try:
        return round(float(raw))
    except (TypeError, ValueError, OverflowError):
        return None


def check(path: str | os.PathLike[str], journal: str = "nature") -> dict[str, Any]:
    """The checks for the files saved as ``path`` (``path.png``, ``.pdf``, ``.svg``, ``.eps``)."""
    spec = JOURNALS.get(journal.lower())
    if spec is None:
        raise ValueError(f"unknown journal {journal!r}; choose from {', '.join(JOURNALS)}")
    base = Path(path)
    if base.suffix.lower() in {".png", ".pdf", ".svg", ".eps"}:
        base = base.with_suffix("")
    files = {kind: base.with_name(f"{base.name}.{kind}") for kind in ("png", "pdf", "svg", "eps")}
    found = [kind for kind, file in files.items() if file.is_file()]
    checks: list[dict[str, Any]] = []
    vector = any(kind in found for kind in ("pdf", "svg", "eps"))
    checks.append(
        {"item": "vector format", "passed": vector, "detail": ", ".join(found) or "no files"}
    )
    for kind in found:
        megabytes = files[kind].stat().st_size / (1024 * 1024)
        checks.append(
            {
                "item": f"{kind.upper()} size under {spec['max_mb']} MB",
                "passed": megabytes <= spec["max_mb"],
                "detail": f"{megabytes:.2f} MB",
            }
        )
    if "png" in found:
        from PIL import Image

        with Image.open(files["png"]) as image:
            width_px = image.size[0]
            dpi = _dpi(image.info.get("dpi"))
        checks.append(
            {
                "item": f"resolution at least {spec['min_dpi']} DPI",
                "passed": dpi is not None and dpi >= spec["min_dpi"],
                "detail": f"{dpi} DPI" if dpi else "no DPI recorded",
            }
        )
        if dpi:
            width = round(width_px / dpi, 2)
            fits = abs(width - spec["single"]) < 0.6 or abs(width - spec["double"]) < 1.0
            checks.append(
                {
                    "item": "printed width matches a column",
                    "passed": fits,
                    "detail": f"{width} in (columns {spec['single']} in, {spec['double']} in)",
                }
            )
    return {
        "journal": spec["name"],
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
        "formats": found,
    }
