"""Read a data file the way the figure helpers expect, and honour corrections: when points were
dragged in the app, the corrected copy is read in place of the original (the original is never
changed)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

# Set by the app when it re-runs a script after a correction: {"original path": "corrected copy"}.
OVERRIDE_VARIABLE = "AW_SCIPLOT_DATA"
_READ: dict[str, str] = {}


def _overrides() -> dict[str, str]:
    try:
        mapping = json.loads(os.environ.get(OVERRIDE_VARIABLE) or "{}")
    except ValueError:
        return {}
    if not isinstance(mapping, dict):
        return {}
    return {
        os.path.normcase(os.path.abspath(key)): value
        for key, value in mapping.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def source_of(path: str | os.PathLike[str]) -> str:
    """The file actually read for ``path`` (its corrected copy when there is one)."""
    key = os.path.normcase(os.path.abspath(path))
    return _overrides().get(key, str(path))


def read(path: str | os.PathLike[str], **options: Any) -> pd.DataFrame:
    """A table from CSV, TSV, TXT (separator detected), Excel or JSON; column names trimmed."""
    actual = source_of(path)
    suffix = Path(actual).suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        frame = pd.read_excel(actual, **options)
    elif suffix == ".json":
        frame = pd.read_json(actual, **options)
    elif suffix in {".tsv", ".tab"}:
        frame = pd.read_csv(actual, sep="\t", **options)
    elif suffix == ".txt":
        frame = pd.read_csv(actual, sep=None, engine="python", **options)
    else:
        frame = pd.read_csv(actual, **options)
    frame.columns = [str(column).strip() for column in frame.columns]
    _READ[os.path.normcase(os.path.abspath(path))] = str(path)
    return frame


def last_read() -> str | None:
    """The data file read last (as the script named it), for figures that do not name one."""
    return next(reversed(_READ.values()), None)
