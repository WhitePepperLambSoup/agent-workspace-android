"""Make, lay out and save figures: one-call figures in a journal style, multi-panel layouts with
panel letters, journal column widths, and saving PNG/PDF/SVG together with a map of the data
points the app uses to let the user drag them."""

from __future__ import annotations

import contextlib
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from aw_sciplot import data as data_module
from aw_sciplot import points, style
from matplotlib.gridspec import GridSpec

JOURNALS: dict[str, dict[str, Any]] = {
    "nature": {
        "name": "Nature Portfolio",
        "single": 3.5,
        "double": 7.2,
        "min_dpi": 300,
        "max_mb": 10,
        "formats": ["pdf", "svg", "eps"],
    },
    "ieee": {
        "name": "IEEE Transactions",
        "single": 3.5,
        "double": 7.16,
        "min_dpi": 300,
        "max_mb": 15,
        "formats": ["pdf", "eps"],
    },
    "cell": {
        "name": "Cell Press",
        "single": 3.35,
        "double": 6.85,
        "min_dpi": 300,
        "max_mb": 10,
        "formats": ["pdf", "svg"],
    },
    "science": {
        "name": "Science",
        "single": 2.25,
        "double": 4.75,
        "min_dpi": 300,
        "max_mb": 10,
        "formats": ["pdf", "eps"],
    },
}

LAYOUTS: dict[str, tuple[int, int]] = {
    "1x2": (1, 2),
    "2x1": (2, 1),
    "2x2": (2, 2),
    "1x3": (1, 3),
    "3x1": (3, 1),
    "2x3": (2, 3),
    "1+2": (2, 2),
    "2+1": (2, 2),
}


def figure(
    style_name: str = "science",
    *,
    journal: str | None = None,
    column: str = "single",
    aspect: float = 0.75,
    size: tuple[float, float] | None = None,
) -> tuple[Any, Any]:
    """A figure and its axes in a journal style; ``journal`` sizes it to a column width."""
    style.use(style_name)
    if size is None and journal is not None:
        width = column_width(journal, column)
        size = (width, width * aspect)
    fig, ax = plt.subplots(figsize=size) if size else plt.subplots()
    return fig, ax


def column_width(journal: str, column: str = "single") -> float:
    spec = JOURNALS.get(journal.lower())
    if spec is None:
        raise ValueError(f"unknown journal {journal!r}; choose from {', '.join(JOURNALS)}")
    if column not in {"single", "double"}:
        raise ValueError("column is 'single' or 'double'")
    return float(spec[column])


def fit_to_journal(fig: Any, journal: str, column: str = "single") -> float:
    """Resize a figure to a journal column width, keeping its aspect ratio; returns the width."""
    width = column_width(journal, column)
    current_width, current_height = fig.get_size_inches()
    fig.set_size_inches(width, width * current_height / max(current_width, 1e-6))
    return width


def panels(
    layout: str = "2x2",
    style_name: str = "science",
    *,
    journal: str | None = None,
    column: str = "double",
    aspect: float = 0.75,
    letters: str = "A",
) -> tuple[Any, list[Any]]:
    """A multi-panel figure (1x2, 2x1, 2x2, 1x3, 3x1, 2x3, 1+2, 2+1) with panel letters;
    ``letters`` is "A", "a" or "(a)"."""
    if layout not in LAYOUTS:
        raise ValueError(f"unknown layout {layout!r}; choose from {', '.join(LAYOUTS)}")
    style.use(style_name)
    rows, columns = LAYOUTS[layout]
    width = column_width(journal, column) if journal else 3.2 * columns
    fig = plt.figure(figsize=(width, width * aspect * rows / columns))
    grid = GridSpec(rows, columns, figure=fig)
    if layout == "1+2":
        axes = [
            fig.add_subplot(grid[:, 0]),
            fig.add_subplot(grid[0, 1]),
            fig.add_subplot(grid[1, 1]),
        ]
    elif layout == "2+1":
        axes = [
            fig.add_subplot(grid[0, 0]),
            fig.add_subplot(grid[1, 0]),
            fig.add_subplot(grid[:, 1]),
        ]
    else:
        axes = [fig.add_subplot(grid[row, col]) for row in range(rows) for col in range(columns)]
    label_panels(axes, letters)
    return fig, axes


def label_panels(axes: list[Any], letters: str = "A") -> None:
    for index, ax in enumerate(axes):
        letter = chr(ord("A") + index)
        text = {"a": letter.lower(), "(a)": f"({letter.lower()})"}.get(letters, letter)
        ax.text(
            -0.14,
            1.05,
            text,
            transform=ax.transAxes,
            fontsize="large",
            fontweight="bold",
            va="bottom",
            ha="right",
        )


def _caller_code() -> tuple[str, str]:
    """The source and path of the script that called save(), to order candidate columns."""
    script = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    for frame in inspect.stack()[2:]:
        if (
            frame.filename
            and not frame.filename.startswith("<")
            and "aw_sciplot" not in frame.filename
        ):
            script = frame.filename
            break
    try:
        return Path(script).read_text(encoding="utf-8"), script
    except OSError:
        return "", script


def save(
    fig: Any,
    path: str | os.PathLike[str],
    *,
    formats: tuple[str, ...] = ("png", "pdf", "svg"),
    dpi: int = 300,
    data: str | os.PathLike[str] | None = None,
    frame: Any = None,
) -> list[str]:
    """Save a figure as ``path.png``, ``.pdf``, ``.svg`` (TrueType fonts, tight box). With the data
    file it was drawn from (``data``, or the last file read with ``read``), also write
    ``path.points.json`` so its points can be dragged in the app. Returns the files written."""
    style.keep_fonts()
    base = Path(path)
    if base.suffix.lower() in {".png", ".pdf", ".svg", ".eps", ".tif", ".tiff", ".jpg"}:
        base = base.with_suffix("")
    base.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(ValueError, RuntimeError):
        fig.tight_layout()
    written: list[str] = []
    for kind in formats:
        target = base.with_name(f"{base.name}.{kind}")
        fig.savefig(target, format=kind, dpi=dpi, bbox_inches="tight")
        written.append(str(target))
    source = data if data is not None else data_module.last_read()
    if source is not None and "png" in formats:
        written.append(_write_points(fig, base, str(source), frame))
    return written


def _write_points(fig: Any, base: Path, source: str, frame: Any) -> str:
    code, script = _caller_code()
    if frame is None:
        frame = data_module.read(source)
    drawn = points.figure_points(fig)
    matched = points.match(drawn, frame, code)
    document = {
        "version": 1,
        "image": f"{base.name}.png",
        "cwd": os.getcwd(),
        "data": source,
        "source": data_module.source_of(source),
        "script": script,
        "axes": drawn["axes"],
        "sets": matched["sets"],
        "unmatched": matched["unmatched"],
        "columns": [str(column) for column in frame.columns],
        "rows": len(frame),
    }
    target = base.with_name(f"{base.name}.points.json")
    target.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return str(target)
