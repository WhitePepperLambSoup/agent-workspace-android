"""Journal styles: figure size, fonts and line widths for Nature, IEEE, Science-like and lighter
figures; TrueType fonts in PDF and PostScript (what journals ask for); Chinese text that renders
instead of boxes."""

from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

CJK_FONTS = ["Microsoft YaHei", "SimHei", "PingFang SC", "Noto Sans CJK SC", "WenQuanYi Micro Hei"]

STYLES: dict[str, dict[str, Any]] = {
    "default": {},
    "science": {
        "figure.figsize": (3.5, 2.625),
        "axes.linewidth": 0.8,
        "axes.grid": False,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "legend.frameon": False,
        "font.size": 9,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
    },
    "nature": {
        "figure.figsize": (3.35, 2.5),
        "axes.linewidth": 0.8,
        "axes.grid": False,
        "font.family": "sans-serif",
        "font.size": 8,
        "axes.labelsize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.frameon": False,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.04,
    },
    "ieee": {
        "figure.figsize": (3.5, 2.625),
        "axes.linewidth": 0.7,
        "axes.grid": False,
        "font.family": "serif",
        "font.size": 8,
        "lines.linewidth": 1.0,
        "legend.frameon": False,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.04,
    },
    "lovely": {
        "figure.figsize": (6.4, 4.2),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "font.size": 10,
        "legend.frameon": False,
        "savefig.bbox": "tight",
    },
}


def keep_fonts() -> None:
    """Fonts every style keeps: TrueType in vector files, Chinese fallbacks, a plain minus."""
    matplotlib.rcParams["pdf.fonttype"] = 42
    matplotlib.rcParams["ps.fonttype"] = 42
    sans = list(matplotlib.rcParams["font.sans-serif"])
    matplotlib.rcParams["font.sans-serif"] = sans + [font for font in CJK_FONTS if font not in sans]
    matplotlib.rcParams["axes.unicode_minus"] = False


def use(name: str = "science") -> None:
    """Apply a style (``science``, ``nature``, ``ieee``, ``lovely`` or ``default``); SciencePlots'
    own styles are used too when that package is installed."""
    if name not in STYLES:
        raise ValueError(f"unknown style {name!r}; choose from {', '.join(STYLES)}")
    plt.rcdefaults()
    if name in {"science", "nature", "ieee"}:
        try:
            import scienceplots  # noqa: F401

            plt.style.use(["science", "no-latex"] + ([name] if name != "science" else []))
        except (ImportError, OSError):
            pass
    plt.rcParams.update(STYLES[name])
    keep_fonts()
