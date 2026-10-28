"""Statistics for figures: two-group tests (Welch t, Mann-Whitney U, paired t, Wilcoxon), Tukey
HSD, one-way ANOVA or Kruskal-Wallis across groups, multiple-comparison correction (Bonferroni,
Benjamini-Hochberg), significance brackets with stars, and regression fits with the equation and
R² on the plot."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

TESTS = {"welch", "t-test", "mann-whitney", "paired-t", "wilcoxon", "tukey"}
CORRECTIONS = {"bonferroni", "fdr_bh", "none"}


def stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def format_p(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3g}"


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or len(b) < 2:
        return 0.0
    pooled = np.sqrt(
        ((len(a) - 1) * np.var(a, ddof=1) + (len(b) - 1) * np.var(b, ddof=1))
        / (len(a) + len(b) - 2)
    )
    if pooled == 0 or np.isnan(pooled):
        return 0.0
    return round(float(np.mean(a) - np.mean(b)) / float(pooled), 3)


def adjust(p_values: list[float], method: str = "fdr_bh") -> list[float]:
    """Correct p values for multiple comparisons."""
    if method not in CORRECTIONS:
        raise ValueError(f"unknown correction {method!r}")
    count = len(p_values)
    if count <= 1 or method == "none":
        return list(p_values)
    if method == "bonferroni":
        return [min(p * count, 1.0) for p in p_values]
    ranked = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * count
    smallest = 1.0
    for rank in range(count - 1, -1, -1):
        index, value = ranked[rank]
        smallest = min(smallest, value * count / (rank + 1))
        adjusted[index] = min(smallest, 1.0)
    return adjusted


def _values(frame: pd.DataFrame, group: str, value: str, name: Any) -> np.ndarray:
    selected = frame[frame[group].astype(str) == str(name)][value]
    return np.asarray(pd.to_numeric(selected, errors="coerce").dropna().values, dtype=float)


def compare(
    frame: pd.DataFrame,
    group: str,
    value: str,
    a: Any,
    b: Any,
    test: str = "welch",
    pair: str | None = None,
) -> dict[str, Any]:
    """Compare two groups; ``pair`` names the column matching rows for paired tests."""
    if test in {"paired-t", "wilcoxon"}:
        if not pair:
            raise ValueError("a paired test needs the column that pairs the rows (e.g. subject)")
        subset = frame[frame[group].astype(str).isin([str(a), str(b)])][[pair, group, value]].copy()
        subset[value] = pd.to_numeric(subset[value], errors="coerce")
        subset[group] = subset[group].astype(str)
        wide = (
            subset.dropna()
            .groupby([pair, group])[value]
            .mean()
            .unstack(group)[[str(a), str(b)]]
            .dropna()
        )
        if len(wide) < 2:
            raise ValueError("fewer than 2 pairs")
        first, second = wide[str(a)].to_numpy(float), wide[str(b)].to_numpy(float)
        if np.allclose(first - second, 0):
            statistic, p = 0.0, 1.0
        elif test == "wilcoxon":
            statistic, p = scipy_stats.wilcoxon(first, second)
        else:
            statistic, p = scipy_stats.ttest_rel(first, second)
        name = "Wilcoxon signed-rank" if test == "wilcoxon" else "paired t-test"
    else:
        first, second = _values(frame, group, value, a), _values(frame, group, value, b)
        if len(first) == 0 or len(second) == 0:
            raise ValueError(f"group {a} or {b} has no numbers")
        if test == "mann-whitney":
            statistic, p = scipy_stats.mannwhitneyu(first, second, alternative="two-sided")
            name = "Mann-Whitney U"
        else:
            statistic, p = scipy_stats.ttest_ind(first, second, equal_var=test == "t-test")
            name = "Student's t-test" if test == "t-test" else "Welch's t-test"
        if np.isnan(p):
            statistic, p = 0.0, 1.0
    p = float(p)
    return {
        "a": str(a),
        "b": str(b),
        "test": name,
        "statistic": round(float(statistic), 4),
        "p": p,
        "p_text": format_p(p),
        "stars": stars(p),
        "mean_a": round(float(np.mean(first)), 4),
        "mean_b": round(float(np.mean(second)), 4),
        "n_a": len(first),
        "n_b": len(second),
        "cohens_d": cohens_d(first, second),
    }


def across(
    frame: pd.DataFrame, group: str, value: str, nonparametric: bool = False
) -> dict[str, Any] | None:
    """One-way ANOVA (or Kruskal-Wallis) over three or more groups."""
    samples = [
        sample
        for name in frame[group].dropna().unique()
        if len(sample := _values(frame, group, value, name))
    ]
    if len(samples) < 3:
        return None
    if nonparametric:
        statistic, p = scipy_stats.kruskal(*samples)
        name = "Kruskal-Wallis"
    else:
        statistic, p = scipy_stats.f_oneway(*samples)
        name = "one-way ANOVA"
    return {
        "test": name,
        "statistic": round(float(statistic), 4),
        "p": float(p),
        "p_text": format_p(float(p)),
    }


def annotate_pairs(
    ax: Any,
    frame: pd.DataFrame,
    group: str,
    value: str,
    pairs: list[tuple[Any, Any]],
    *,
    test: str = "welch",
    correction: str = "bonferroni",
    pair: str | None = None,
) -> list[dict[str, Any]]:
    """Test each pair of groups and draw brackets with stars above the plot (groups found by
    their tick labels). Returns the tests, with raw and corrected p values."""
    if test not in TESTS:
        raise ValueError(f"unknown test {test!r}; choose from {', '.join(sorted(TESTS))}")
    labels = [label.get_text() for label in ax.get_xticklabels()]
    ticks = list(ax.get_xticks())
    order = {
        name: index
        for index, name in enumerate(str(item) for item in frame[group].dropna().unique())
    }

    def where(name: Any) -> float:
        text = str(name)
        if text in labels:
            return float(ticks[labels.index(text)])
        return float(order.get(text, 0))

    ordered = sorted(pairs, key=lambda item: abs(where(item[1]) - where(item[0])))
    if test == "tukey":
        names = list(dict.fromkeys(str(name) for item in ordered for name in item))
        samples = [_values(frame, group, value, name) for name in names]
        tukey = scipy_stats.tukey_hsd(*samples)
        results = []
        for a, b in ordered:
            i, j = names.index(str(a)), names.index(str(b))
            p = float(tukey.pvalue[i][j])
            results.append(
                {
                    "a": str(a),
                    "b": str(b),
                    "test": "Tukey HSD",
                    "p": p,
                    "p_text": format_p(p),
                    "stars": stars(p),
                }
            )
        correction = "none"
    else:
        results = [compare(frame, group, value, a, b, test, pair) for a, b in ordered]
    corrected = adjust([item["p"] for item in results], correction)
    low, high = ax.get_ylim()
    span = max(high - low, 1e-9)
    base, step = high + span * 0.05, span * 0.12
    for number, (item, p_value) in enumerate(zip(results, corrected, strict=True)):
        item["p_corrected"] = p_value
        item["correction"] = correction
        item["stars"] = stars(p_value)
        left, right = where(item["a"]), where(item["b"])
        level = base + number * step
        tip = step * 0.25
        ax.plot([left, left, right, right], [level - tip, level, level, level - tip], lw=1.0, c="k")
        ax.text(
            (left + right) / 2,
            level + tip * 0.2,
            item["stars"],
            ha="center",
            va="bottom",
            fontsize="medium",
        )
    ax.set_ylim(low, base + (len(results) + 0.5) * step)
    return results


def fit_line(
    ax: Any,
    frame: pd.DataFrame,
    x: str,
    y: str,
    degree: int = 1,
    *,
    color: str = "#d62728",
    show: bool = True,
) -> dict[str, Any]:
    """Least-squares polynomial fit (degree 1-3), drawn with its equation and R²."""
    if degree not in {1, 2, 3}:
        raise ValueError("degree is 1, 2 or 3")
    values = frame[[x, y]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(values) < degree + 2:
        raise ValueError(f"a degree {degree} fit needs at least {degree + 2} points")
    xs, ys = values[x].to_numpy(float), values[y].to_numpy(float)
    coefficients = np.polyfit(xs, ys, degree)
    predicted = np.polyval(coefficients, xs)
    total = float(np.sum((ys - ys.mean()) ** 2))
    r_squared = 1.0 - float(np.sum((ys - predicted) ** 2)) / total if total > 0 else 1.0
    terms = []
    for power, value in zip(range(degree, -1, -1), coefficients, strict=True):
        variable = "" if power == 0 else ("x" if power == 1 else f"x^{power}")
        sign = "-" if value < 0 else ("" if not terms else "+")
        terms.append(
            f"{sign} {abs(value):.4g}{variable}".strip()
            if terms
            else f"{sign}{abs(value):.4g}{variable}"
        )
    result: dict[str, Any] = {
        "coefficients": [float(value) for value in coefficients],
        "r_squared": round(r_squared, 6),
        "n": len(values),
        "equation": "y = " + " ".join(terms),
    }
    if degree == 1:
        result["p"] = float(scipy_stats.linregress(xs, ys).pvalue)
    if show:
        grid = np.linspace(xs.min(), xs.max(), 200)
        ax.plot(grid, np.polyval(coefficients, grid), color=color, linewidth=1.5)
        label = f"{result['equation']}\nR² = {r_squared:.4f}"
        if "p" in result:
            label += f"\n{format_p(result['p'])}"
        ax.text(
            0.03,
            0.97,
            label,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize="small",
            bbox={
                "boxstyle": "round,pad=0.3",
                "facecolor": "white",
                "alpha": 0.8,
                "edgecolor": "none",
            },
        )
    return result
