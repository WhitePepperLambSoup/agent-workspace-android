"""Data points of a saved figure, mapped back to the rows of its data, so the app can let the user
drag a point and have the change written to a corrected copy of the data.

* :func:`figure_points` records each axes' place in the saved image and the marks drawn on it
  (line vertices, scatter offsets, bar values);
* :func:`match` binds every point of a mark to a distinct row with the same (x, y) values,
  comparing numbers with a tight tolerance, categories through their labels and dates as
  Matplotlib date numbers; only numeric, linear or log axes are editable;
* :func:`apply_edits` returns a corrected copy and a log of every changed cell.

Follows Quick SciPlot's point editor (MIT, Copyright 2026 WhitePepperLambSoup).
"""

from __future__ import annotations

import ast
import contextlib
import math
import warnings
from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

MAX_SET_POINTS = 2000
MAX_TOTAL_POINTS = 5000
MAX_SETS = 200
MAX_EDITS = 5000
MAX_COLUMN_PAIRS = 60
REL_TOLERANCE = 1e-9
DATE_TOLERANCE = 1e-6  # days
CATEGORY_SNAP = 0.45  # how far a mark may sit from its category (jitter, dodge)
INDEX_COLUMN = "__index__"
EDITABLE_SCALES = {"linear", "log"}
_EPOCH = pd.Timestamp("1970-01-01")
# Matplotlib writes negative tick labels with the minus sign, not a hyphen.
_MINUS = chr(0x2212)


class EditError(ValueError):
    """An edit that cannot be applied (a row or column that does not exist, a wrong value)."""


# -- what the figure drew ---------------------------------------------------------------------


def figure_points(fig: Any, pad_inches: float | None = None) -> dict[str, Any]:
    """Each axes' box in the saved (tight-cropped) image as fractions, and the marks drawn."""
    import matplotlib
    import matplotlib.ticker as ticker
    from matplotlib.collections import PathCollection
    from matplotlib.container import BarContainer

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    if pad_inches is None:
        try:
            pad_inches = float(matplotlib.rcParams.get("savefig.pad_inches", 0.1))
        except (TypeError, ValueError):
            pad_inches = 0.1
    box = fig.get_tightbbox(renderer).padded(pad_inches)
    dpi = float(fig.dpi)

    def image_point(x: float, y: float) -> tuple[float, float]:
        return (x / dpi - box.x0) / box.width, (box.y1 - y / dpi) / box.height

    def image_box(ax: Any) -> list[float]:
        left, top = image_point(ax.bbox.x0, ax.bbox.y1)
        right, bottom = image_point(ax.bbox.x1, ax.bbox.y0)
        return [left, top, right - left, bottom - top]

    def axis_info(axis: Any) -> dict[str, Any]:
        info: dict[str, Any] = {"scale": axis.get_scale(), "kind": "num"}
        mapping = getattr(getattr(axis, "units", None), "_mapping", None)
        if mapping:
            info["kind"] = "cat"
            info["labels"] = [
                [float(value), str(key)] for key, value in list(mapping.items())[:2000]
            ]
            return info
        converter = (
            axis.get_converter()
            if hasattr(axis, "get_converter")
            else getattr(axis, "converter", None)
        )
        if converter is not None and "Date" in type(converter).__name__:
            info["kind"] = "date"
            return info
        # Numeric positions relabelled with words (set_xticklabels): keep the labels.
        locations = [float(location) for location in axis.get_majorticklocs()]
        texts = [label.get_text() for label in axis.get_majorticklabels()]
        relabelled = isinstance(axis.get_major_formatter(), ticker.FixedFormatter) or any(
            text and not _is_number(text) for text in texts
        )
        if relabelled and len(locations) == len(texts) and any(texts):
            info["ticks"] = [
                [location, text] for location, text in zip(locations, texts, strict=True)
            ][:2000]
        return info

    total = 0
    axes: list[dict[str, Any]] = []
    sets: list[dict[str, Any]] = []
    for index, ax in enumerate(fig.axes):
        axes.append(
            {
                "box": image_box(ax),
                "xlim": [float(value) for value in ax.get_xlim()],
                "ylim": [float(value) for value in ax.get_ylim()],
                "x": axis_info(ax.xaxis),
                "y": axis_info(ax.yaxis),
            }
        )
        if not ax.get_visible() or ax.name != "rectilinear":
            continue
        marks: list[tuple[str, Any, Any]] = []
        for line in ax.get_lines():
            if line.get_visible() and line.get_transform() == ax.transData:
                marks.append(("line", line, np.asarray(line.get_xydata(), dtype=float)))
        for collection in ax.collections:
            if (
                isinstance(collection, PathCollection)
                and collection.get_visible()
                and collection.get_offset_transform() == ax.transData
            ):
                offsets = np.ma.filled(np.ma.asarray(collection.get_offsets(), dtype=float), np.nan)
                marks.append(("scatter", collection, offsets))
        for kind, artist, xy in marks:
            xy = xy.reshape(-1, 2)
            keep = np.flatnonzero(np.isfinite(xy).all(axis=1))
            if keep.size == 0 or keep.size > MAX_SET_POINTS or total + keep.size > MAX_TOTAL_POINTS:
                continue
            total += int(keep.size)
            sets.append(
                {
                    "axes": index,
                    "kind": kind,
                    "label": str(artist.get_label() or "")[:120],
                    "x": xy[keep, 0].tolist(),
                    "y": xy[keep, 1].tolist(),
                }
            )
        for container in ax.containers:
            if not isinstance(container, BarContainer):
                continue
            horizontal = getattr(container, "orientation", None) == "horizontal"
            datavalues = getattr(container, "datavalues", None)
            positions: list[float] = []
            values: list[float] = []
            bases: list[float] = []
            for number, patch in enumerate(container.patches):
                if not patch.get_visible():
                    continue
                if horizontal:
                    where, base, value = (
                        patch.get_y() + patch.get_height() / 2,
                        patch.get_x(),
                        patch.get_width(),
                    )
                else:
                    where, base, value = (
                        patch.get_x() + patch.get_width() / 2,
                        patch.get_y(),
                        patch.get_height(),
                    )
                if datavalues is not None and number < len(datavalues):
                    with contextlib.suppress(TypeError, ValueError):
                        value = float(datavalues[number])
                if all(math.isfinite(float(item)) for item in (where, base, value)):
                    positions.append(float(where))
                    bases.append(float(base))
                    values.append(float(value))
            if (
                not positions
                or len(positions) > MAX_SET_POINTS
                or total + len(positions) > MAX_TOTAL_POINTS
            ):
                continue
            total += len(positions)
            sets.append(
                {
                    "axes": index,
                    "kind": "bar",
                    "orientation": "h" if horizontal else "v",
                    "label": str(container.get_label() or "")[:120],
                    "pos": positions,
                    "value": values,
                    "base": bases,
                }
            )
    return {"axes": axes, "sets": sets}


def _is_number(text: str) -> bool:
    try:
        float(text.replace(_MINUS, "-").replace(",", ""))
    except ValueError:
        return False
    return True


# -- matching marks to rows --------------------------------------------------------------------


def _finite_list(values: Any, limit: int) -> list[float] | None:
    if not isinstance(values, list) or len(values) > limit:
        return None
    out: list[float] = []
    for value in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            return None
        out.append(float(value))
    return out


def referenced_columns(code: str, columns: list[str]) -> list[str]:
    """Columns the code names (string literals or ``df.attribute``), in order of appearance."""
    known = set(columns)
    found: list[str] = []
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return found
    nodes = sorted(
        (node for node in ast.walk(tree) if hasattr(node, "lineno")),
        key=lambda node: (node.lineno, getattr(node, "col_offset", 0)),
    )
    for node in nodes:
        name = None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            name = node.value
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            name = node.attr
        if name in known and name not in found:
            found.append(name)
    return found


def _is_numeric(series: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)


def _parse_dates(series: pd.Series) -> pd.Series | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return pd.to_datetime(series, errors="coerce")
    except (TypeError, ValueError, OverflowError):
        return None


class _Column:
    """One candidate column prepared for matching on an axis kind."""

    def __init__(self, name: str, kind: str, values: np.ndarray, editable: bool) -> None:
        self.name = name
        self.kind = kind  # "num" or "cat"
        self.values = values
        self.editable = editable
        if kind == "num":
            self.sorted = np.unique(values[np.isfinite(values)])
        else:
            self.lookup = set(values.tolist())

    def codes(self, points: list[Any]) -> list[Any] | None:
        """Each point's value as the column holds it, or None when one is absent."""
        if self.kind == "cat":
            return list(points) if all(point in self.lookup for point in points) else None
        if self.sorted.size == 0:
            return None
        values = np.asarray(points, dtype=float)
        index = np.searchsorted(self.sorted, values)
        lower = self.sorted[np.clip(index - 1, 0, self.sorted.size - 1)]
        upper = self.sorted[np.clip(index, 0, self.sorted.size - 1)]
        nearest = np.where(np.abs(lower - values) <= np.abs(upper - values), lower, upper)
        if self.name.startswith("date:"):
            limit: Any = DATE_TOLERANCE
        else:
            limit = REL_TOLERANCE * np.maximum(1.0, np.maximum(np.abs(values), np.abs(nearest)))
        if not bool(np.all(np.abs(nearest - values) <= limit)):
            return None
        return list(nearest.tolist())


def _category_labels(labels: Any, positions: list[Any]) -> list[str] | None:
    """The label of the category each position sits on (within CATEGORY_SNAP)."""
    if not (
        isinstance(labels, list)
        and labels
        and all(isinstance(item, (list, tuple)) and len(item) == 2 for item in labels)
    ):
        return None
    pairs = sorted(
        (float(where), str(text))
        for where, text in labels
        if isinstance(where, (int, float)) and math.isfinite(where)
    )
    if not pairs:
        return None
    locations = np.array([where for where, _ in pairs])
    texts = [text.replace(_MINUS, "-").strip() for _, text in pairs]
    out = []
    for value in positions:
        if not isinstance(value, (int, float)):
            return None
        index = int(np.argmin(np.abs(locations - value)))
        if abs(locations[index] - value) > CATEGORY_SNAP or not texts[index]:
            return None
        out.append(texts[index])
    return out


class _Matcher:
    def __init__(self, frame: pd.DataFrame, code: str) -> None:
        self.frame = frame
        self.columns = [str(column) for column in frame.columns]
        named = referenced_columns(code, self.columns)
        self.order = named + [column for column in self.columns if column not in named]
        self._prepared: dict[tuple[str, str], _Column | None] = {}
        # Rows already bound to a mark, per column pair: another mark of the same columns
        # prefers other rows (repeated values).
        self._claimed: dict[tuple[str, ...], set[int]] = defaultdict(set)

    def _numeric(self, name: str) -> _Column | None:
        key = ("num", name)
        if key not in self._prepared:
            column = None
            if name == INDEX_COLUMN:
                column = _Column(
                    INDEX_COLUMN, "num", np.arange(len(self.frame), dtype=float), editable=False
                )
            elif _is_numeric(self.frame[name]):
                values = pd.to_numeric(self.frame[name], errors="coerce").to_numpy(
                    dtype=float, na_value=np.nan
                )
                column = _Column(name, "num", values, editable=True)
            self._prepared[key] = column
        return self._prepared[key]

    def _date(self, name: str) -> _Column | None:
        key = ("date", name)
        if key not in self._prepared:
            column = None
            series = self.frame[name]
            if not _is_numeric(series) and not pd.api.types.is_bool_dtype(series):
                parsed = _parse_dates(series)
                if parsed is not None and getattr(parsed.dt, "tz", None) is not None:
                    parsed = parsed.dt.tz_convert("UTC").dt.tz_localize(None)
                if parsed is not None and parsed.notna().sum() >= max(
                    1, int(0.9 * series.notna().sum())
                ):
                    days = (parsed - _EPOCH) / pd.Timedelta(days=1)
                    column = _Column(
                        f"date:{name}",
                        "num",
                        days.to_numpy(dtype=float, na_value=np.nan),
                        editable=False,
                    )
            self._prepared[key] = column
        return self._prepared[key]

    def _category(self, name: str) -> _Column:
        key = ("cat", name)
        if key not in self._prepared:
            labels = [
                None
                if value is None or (isinstance(value, float) and math.isnan(value))
                else str(value)
                for value in self.frame[name].tolist()
            ]
            self._prepared[key] = _Column(
                name, "cat", np.array(labels, dtype=object), editable=False
            )
        column = self._prepared[key]
        assert column is not None
        return column

    def candidates(
        self, axis: dict[str, Any], values: list[Any]
    ) -> list[tuple[_Column, list[Any]]]:
        """Columns holding every value of one axis, with each point's code."""
        kind = axis.get("kind")
        out: list[tuple[_Column, list[Any]]] = []
        if kind == "cat":
            labels = _category_labels(axis.get("labels"), values)
            if labels is None:
                return out
            for name in self.order:
                column = self._category(name)
                codes = column.codes(labels)
                if codes is not None:
                    out.append((column, codes))
            return out
        if kind == "date":
            for name in self.order:
                date_column = self._date(name)
                codes = date_column.codes(values) if date_column else None
                if date_column is not None and codes is not None:
                    out.append((date_column, codes))
            return out
        for name in [*self.order, INDEX_COLUMN]:
            numeric = self._numeric(name)
            codes = numeric.codes(values) if numeric else None
            if numeric is not None and codes is not None:
                out.append((numeric, codes))
        if axis.get("ticks"):  # numeric axes relabelled with set_xticklabels
            labels = _category_labels(axis.get("ticks"), values)
            if labels is not None:
                for name in self.order:
                    column = self._category(name)
                    codes = column.codes(labels)
                    if codes is not None:
                        out.append((column, codes))
        return out

    def assign(
        self, x_col: _Column, x_codes: list[Any], y_col: _Column, y_codes: list[Any]
    ) -> tuple[list[int], int] | None:
        """Bind each point to a distinct row with the same (x, y) values."""
        mask = (
            pd.Series(x_col.values).isin(set(x_codes)).to_numpy()
            & pd.Series(y_col.values).isin(set(y_codes)).to_numpy()
        )
        buckets: dict[tuple[Any, Any], list[int]] = defaultdict(list)
        for row in np.flatnonzero(mask).tolist():
            buckets[(x_col.values[row], y_col.values[row])].append(row)
        claimed = self._claimed[(x_col.kind, x_col.name, y_col.kind, y_col.name)]
        for avoid_claimed in (True, False):
            used: set[int] = set()
            rows: list[int] = []
            ambiguous = 0
            for key in zip(x_codes, y_codes, strict=True):
                bucket = buckets.get(key, [])
                row = next(
                    (r for r in bucket if r not in used and not (avoid_claimed and r in claimed)),
                    None,
                )
                if row is None:
                    break
                ambiguous += len(bucket) > 1
                used.add(row)
                rows.append(row)
            else:
                claimed.update(rows)
                return rows, ambiguous
        return None

    def match(
        self, x_axis: dict[str, Any], xs: list[Any], y_axis: dict[str, Any], ys: list[Any]
    ) -> dict[str, Any] | None:
        x_candidates = self.candidates(x_axis, xs)
        y_candidates = self.candidates(y_axis, ys) if x_candidates else []
        tried = 0
        for x_col, x_codes in x_candidates:
            for y_col, y_codes in y_candidates:
                if (x_col.name, x_col.kind) == (y_col.name, y_col.kind):
                    continue
                if x_col.name == INDEX_COLUMN and y_col.name == INDEX_COLUMN:
                    continue
                tried += 1
                if tried > MAX_COLUMN_PAIRS:
                    return None
                assigned = self.assign(x_col, x_codes, y_col, y_codes)
                if assigned is not None:
                    return {
                        "x_col": x_col,
                        "y_col": y_col,
                        "rows": assigned[0],
                        "ambiguous": assigned[1],
                        "x_display": _display_values(x_col, x_codes),
                        "y_display": _display_values(y_col, y_codes),
                    }
        return None


def _display_values(column: _Column, codes: list[Any]) -> list[str] | None:
    if column.kind == "cat":
        return [str(code) for code in codes]
    if column.name.startswith("date:"):
        out = []
        for days in codes:
            stamp = _EPOCH + pd.Timedelta(days=float(days))
            out.append(
                stamp.date().isoformat() if stamp == stamp.normalize() else stamp.isoformat(sep=" ")
            )
        return out
    return None


def _axis_spec(column: _Column | None, axis: dict[str, Any], editable_axis: bool) -> dict[str, Any]:
    numeric = column is not None and column.kind == "num" and column.editable
    spec: dict[str, Any] = {
        "column": None
        if column is None or column.name == INDEX_COLUMN
        else column.name.removeprefix("date:"),
        "kind": axis.get("kind", "num"),
        "scale": axis.get("scale", "linear"),
        "editable": bool(
            editable_axis
            and numeric
            and axis.get("kind", "num") == "num"
            and axis.get("scale", "linear") in EDITABLE_SCALES
        ),
    }
    if column is not None and column.name == INDEX_COLUMN:
        spec["index"] = True
    return spec


def match(drawn: dict[str, Any], frame: pd.DataFrame, code: str = "") -> dict[str, Any]:
    """The editable point sets of a figure: each matched mark with its rows and axes."""
    axes = drawn.get("axes") or []
    matcher = _Matcher(frame, code)
    sets: list[dict[str, Any]] = []
    unmatched = 0
    total = 0
    for raw in (drawn.get("sets") or [])[:MAX_SETS]:
        index = raw.get("axes")
        if not isinstance(index, int) or not 0 <= index < len(axes):
            continue
        geometry = axes[index]
        kind = raw.get("kind")
        horizontal = False
        bases = None
        if kind == "bar":
            positions = _finite_list(raw.get("pos"), MAX_SET_POINTS)
            values = _finite_list(raw.get("value"), MAX_SET_POINTS)
            bases = _finite_list(raw.get("base"), MAX_SET_POINTS)
            if (
                not positions
                or values is None
                or bases is None
                or not len(positions) == len(values) == len(bases)
            ):
                continue
            horizontal = raw.get("orientation") == "h"
            xs, ys = (values, positions) if horizontal else (positions, values)
        elif kind in {"line", "scatter"}:
            xs_raw = _finite_list(raw.get("x"), MAX_SET_POINTS)
            ys_raw = _finite_list(raw.get("y"), MAX_SET_POINTS)
            if not xs_raw or ys_raw is None or len(xs_raw) != len(ys_raw):
                continue
            xs, ys = xs_raw, ys_raw
        else:
            continue
        if total + len(xs) > MAX_TOTAL_POINTS:
            break
        found = matcher.match(geometry["x"], xs, geometry["y"], ys)
        if found is None:
            unmatched += 1
            continue
        total += len(xs)
        label = str(raw.get("label") or "")[:120]
        point_set: dict[str, Any] = {
            "id": f"m{len(sets)}",
            "axes": index,
            "kind": kind,
            # Matplotlib names unlabelled artists "_child0", "_container1", ...
            "label": "" if label.startswith("_") else label,
            "x": _axis_spec(
                found["x_col"], geometry["x"], editable_axis=kind != "bar" or horizontal
            ),
            "y": _axis_spec(
                found["y_col"], geometry["y"], editable_axis=kind != "bar" or not horizontal
            ),
            "rows": found["rows"],
            "xs": xs,
            "ys": ys,
            "ambiguous": found["ambiguous"],
        }
        for key in ("x_display", "y_display"):
            if found[key] is not None:
                point_set[key] = found[key]
        if kind == "bar":
            point_set["orientation"] = "h" if horizontal else "v"
            point_set["bases"] = bases
        sets.append(point_set)
    return {"sets": sets, "unmatched": unmatched}


# -- corrections -------------------------------------------------------------------------------


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return None if pd.isna(value) else str(value)


def apply_edits(
    frame: pd.DataFrame, edits: list[dict[str, Any]]
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """A copy of ``frame`` with ``edits`` ({row, column, value}; None clears a cell) applied, and a
    log of the cells that changed. Later edits of the same cell win."""
    if not isinstance(edits, list) or not edits:
        raise EditError("there is nothing to change")
    if len(edits) > MAX_EDITS:
        raise EditError(f"at most {MAX_EDITS} cells can change at once")
    result = frame.copy()
    final: dict[tuple[int, str], Any] = {}
    for edit in edits:
        row, column = edit.get("row"), edit.get("column")
        if isinstance(row, bool) or not isinstance(row, int) or not 0 <= row < len(result):
            raise EditError(f"row {row} does not exist")
        if not isinstance(column, str) or column not in result.columns:
            raise EditError(f"column {column} does not exist")
        final[(row, column)] = edit.get("value")
    log: list[dict[str, Any]] = []
    for (row, column), value in final.items():
        series = result[column]
        old = series.iloc[row]
        new_value: Any
        if _is_numeric(series):
            if value is None or (isinstance(value, str) and not value.strip()):
                new_value = np.nan
            else:
                try:
                    new_value = float(value)
                except (TypeError, ValueError):
                    raise EditError(
                        f"{column} holds numbers; row {row + 1} needs a number"
                    ) from None
                if not math.isfinite(new_value):
                    raise EditError(f"{column} row {row + 1} needs a finite number")
            if pd.api.types.is_integer_dtype(series):
                if (
                    isinstance(new_value, float)
                    and not math.isnan(new_value)
                    and new_value.is_integer()
                ):
                    new_value = int(new_value)
                else:
                    result[column] = series.astype("float64")
            old_missing = pd.isna(old)
            new_missing = isinstance(new_value, float) and math.isnan(new_value)
            same = (old_missing and new_missing) or (
                not old_missing and not new_missing and float(old) == float(new_value)
            )
        else:
            if value is None:
                new_value = None
            elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
                new_value = (
                    value
                    if isinstance(value, str)
                    else (str(int(value)) if float(value).is_integer() else str(value))
                )
            else:
                raise EditError(f"{column} row {row + 1}: that kind of value is not supported")
            if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
                result[column] = series.astype(object)
            same = (pd.isna(old) and new_value is None) or (
                not pd.isna(old) and str(old) == new_value
            )
        if same:
            continue
        result.iloc[row, result.columns.get_loc(column)] = new_value
        log.append(
            {"row": row, "column": column, "old": _json_value(old), "new": _json_value(new_value)}
        )
    if not log:
        raise EditError("the new values are the same as the old ones")
    return result, log
