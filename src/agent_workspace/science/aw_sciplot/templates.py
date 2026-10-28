"""Common research figures in one call: volcano plot, Kaplan-Meier curves with a log-rank test,
PCA, clustered heatmap, dose-response curves (4PL, EC50), correlation heatmap with significance,
and bars with the points and SD or SEM. Each returns (figure, axes) in the current style."""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _numeric(frame: pd.DataFrame, columns: list[str] | None) -> list[str]:
    return list(columns) if columns else frame.select_dtypes(include=[np.number]).columns.tolist()


def volcano(
    frame: pd.DataFrame,
    fold_change: str,
    p_value: str,
    *,
    label: str | None = None,
    fc_threshold: float = 1.0,
    p_threshold: float = 0.05,
    top: int = 10,
) -> tuple[Any, Any]:
    data = frame[[column for column in (fold_change, p_value, label) if column]].copy()
    data[fold_change] = pd.to_numeric(data[fold_change], errors="coerce")
    data[p_value] = pd.to_numeric(data[p_value], errors="coerce")
    data = data.dropna(subset=[fold_change, p_value])
    data = data[data[p_value] > 0]
    data["neg_log_p"] = -np.log10(data[p_value])
    up = (data[fold_change] >= fc_threshold) & (data[p_value] < p_threshold)
    down = (data[fold_change] <= -fc_threshold) & (data[p_value] < p_threshold)
    other = ~(up | down)
    fig, ax = plt.subplots(figsize=(5, 4.2))
    for mask, color, name, size in (
        (other, "#bdbdbd", "NS", 10),
        (up, "#d62728", "Up", 14),
        (down, "#1f77b4", "Down", 14),
    ):
        ax.scatter(
            data.loc[mask, fold_change],
            data.loc[mask, "neg_log_p"],
            s=size,
            color=color,
            alpha=0.75,
            linewidths=0,
            label=f"{name} ({int(mask.sum())})",
        )
    for x in (fc_threshold, -fc_threshold):
        ax.axvline(x, color="gray", linestyle="--", linewidth=0.8)
    ax.axhline(-np.log10(p_threshold), color="gray", linestyle="--", linewidth=0.8)
    if label:
        for _, row in data[up | down].nsmallest(top, p_value).iterrows():
            ax.annotate(
                str(row[label]),
                (row[fold_change], row["neg_log_p"]),
                fontsize=7,
                xytext=(3, 3),
                textcoords="offset points",
            )
    ax.set_xlabel(f"log2 fold change ({fold_change})")
    ax.set_ylabel(f"-log10({p_value})")
    ax.legend(frameon=False, fontsize=8)
    return fig, ax


def kaplan_meier(
    frame: pd.DataFrame, time: str, event: str, group: str | None = None
) -> tuple[Any, Any]:
    from statsmodels.duration.survfunc import SurvfuncRight, survdiff

    data = frame[[column for column in (time, event, group) if column]].copy()
    data[time] = pd.to_numeric(data[time], errors="coerce")
    data[event] = pd.to_numeric(data[event], errors="coerce")
    data = data.dropna()
    data[event] = (data[event] > 0).astype(int)
    groups: list[str | None] = sorted(data[group].astype(str).unique())[:8] if group else [None]
    fig, ax = plt.subplots(figsize=(5.5, 4))
    for name in groups:
        subset = data if name is None else data[data[group].astype(str) == name]
        if subset.empty:
            continue
        curve = SurvfuncRight(subset[time].to_numpy(), subset[event].to_numpy())
        ax.step(
            np.concatenate([[0.0], curve.surv_times]),
            np.concatenate([[1.0], curve.surv_prob]),
            where="post",
            linewidth=1.5,
            label=f"{'All' if name is None else name} (n={len(subset)})",
        )
    if group and len(groups) >= 2:
        _, p = survdiff(
            data[time].to_numpy(), data[event].to_numpy(), data[group].astype(str).to_numpy()
        )
        ax.text(
            0.98,
            0.95,
            f"Log-rank p = {p:.3g}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8,
        )
    ax.set_ylim(0, 1.05)
    ax.set_xlabel(str(time))
    ax.set_ylabel("Survival probability")
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    return fig, ax


def pca(
    frame: pd.DataFrame, columns: list[str] | None = None, group: str | None = None
) -> tuple[Any, Any]:
    chosen = _numeric(frame, columns)
    if len(chosen) < 2:
        raise ValueError("PCA needs at least two numeric columns")
    values = frame[chosen].apply(pd.to_numeric, errors="coerce").dropna()
    if len(values) < 3:
        raise ValueError("PCA needs at least three complete rows")
    standardized = (values - values.mean()) / values.std(ddof=0).replace(0, 1)
    u, s, _ = np.linalg.svd(standardized.to_numpy(), full_matrices=False)
    scores = u[:, :2] * s[:2]
    explained = s**2 / np.sum(s**2)
    fig, ax = plt.subplots(figsize=(5, 4.2))
    if group:
        labels = frame.loc[values.index, group].astype(str)
        for name in list(dict.fromkeys(labels))[:12]:
            mask = (labels == name).to_numpy()
            ax.scatter(scores[mask, 0], scores[mask, 1], s=22, alpha=0.8, label=name)
        ax.legend(frameon=False, fontsize=8)
    else:
        ax.scatter(scores[:, 0], scores[:, 1], s=22, alpha=0.8)
    ax.axhline(0, color="gray", linewidth=0.6)
    ax.axvline(0, color="gray", linewidth=0.6)
    ax.set_xlabel(f"PC1 ({explained[0] * 100:.1f}%)")
    ax.set_ylabel(f"PC2 ({explained[1] * 100:.1f}%)")
    return fig, ax


def clustermap(
    frame: pd.DataFrame,
    columns: list[str] | None = None,
    label: str | None = None,
    standardize: bool = True,
) -> Any:
    """A clustered heatmap (seaborn ClusterGrid; its figure is ``.figure``)."""
    import seaborn as sns

    chosen = _numeric(frame, columns)
    matrix = frame[chosen].apply(pd.to_numeric, errors="coerce").dropna()
    if label:
        matrix.index = frame.loc[matrix.index, label].astype(str)
    matrix = matrix.iloc[:200]
    if len(matrix) < 2 or len(chosen) < 2:
        raise ValueError("a clustered heatmap needs at least two rows and two numeric columns")
    return sns.clustermap(
        matrix,
        z_score=1 if standardize else None,
        center=0 if standardize else None,
        cmap="vlag",
        figsize=(6, 6.5),
        dendrogram_ratio=0.15,
        yticklabels=len(matrix) <= 60,
    )


def four_parameter_logistic(x: Any, bottom: float, top: float, log_ec50: float, hill: float) -> Any:
    return bottom + (top - bottom) / (1 + 10 ** ((log_ec50 - np.log10(x)) * hill))


def dose_response(
    frame: pd.DataFrame, dose: str, response: str, group: str | None = None
) -> tuple[Any, Any, dict[str, float]]:
    """Points and 4PL fits on a log dose axis; also returns each group's EC50."""
    from scipy.optimize import curve_fit

    data = frame[[column for column in (dose, response, group) if column]].copy()
    data[dose] = pd.to_numeric(data[dose], errors="coerce")
    data[response] = pd.to_numeric(data[response], errors="coerce")
    data = data.dropna()
    data = data[data[dose] > 0]
    groups: list[str | None] = list(dict.fromkeys(data[group].astype(str)))[:8] if group else [None]
    fig, ax = plt.subplots(figsize=(5, 4))
    ec50: dict[str, float] = {}
    for index, name in enumerate(groups):
        subset = data if name is None else data[data[group].astype(str) == name]
        x, y = subset[dose].to_numpy(float), subset[response].to_numpy(float)
        color = plt.cm.tab10(index % 10)
        title = "Response" if name is None else name
        ax.scatter(x, y, s=16, color=color, alpha=0.75)
        try:
            guess = [float(np.min(y)), float(np.max(y)), float(np.median(np.log10(x))), 1.0]
            params, _ = curve_fit(four_parameter_logistic, x, y, p0=guess, maxfev=20000)
            grid = np.logspace(np.log10(x.min()), np.log10(x.max()), 200)
            ec50[title] = float(10 ** params[2])
            ax.plot(
                grid,
                four_parameter_logistic(grid, *params),
                color=color,
                linewidth=1.5,
                label=f"{title}: EC50 = {ec50[title]:.3g}",
            )
        except (RuntimeError, ValueError):
            ax.plot([], [], color=color, label=f"{title}: no fit")
    ax.set_xscale("log")
    ax.set_xlabel(str(dose))
    ax.set_ylabel(str(response))
    ax.legend(frameon=False, fontsize=8)
    return fig, ax, ec50


def correlation(
    frame: pd.DataFrame, columns: list[str] | None = None, method: str = "pearson"
) -> tuple[Any, Any]:
    import seaborn as sns
    from scipy import stats as scipy_stats

    chosen = _numeric(frame, columns)
    if len(chosen) < 2:
        raise ValueError("a correlation heatmap needs at least two numeric columns")
    values = frame[chosen].apply(pd.to_numeric, errors="coerce").dropna()
    corr = values.corr(method=method)
    notes = corr.copy().astype(object)
    test = scipy_stats.pearsonr if method == "pearson" else scipy_stats.spearmanr
    for i, first in enumerate(chosen):
        for j, second in enumerate(chosen):
            if i == j:
                notes.iloc[i, j] = ""
                continue
            p = test(values[first], values[second])[1]
            mark = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
            notes.iloc[i, j] = f"{corr.iloc[i, j]:.2f}{mark}"
    size = max(4.0, 0.6 * len(chosen) + 2)
    fig, ax = plt.subplots(figsize=(size, size * 0.85))
    sns.heatmap(
        corr,
        mask=np.triu(np.ones_like(corr, dtype=bool)),
        cmap="RdBu_r",
        vmin=-1,
        vmax=1,
        annot=notes,
        fmt="",
        square=True,
        linewidths=0.5,
        cbar_kws={"shrink": 0.8, "label": f"{method} r"},
        ax=ax,
        annot_kws={"fontsize": 8},
    )
    return fig, ax


def bar_points(
    frame: pd.DataFrame, group: str, value: str, error: str = "sd", seed: int = 0
) -> tuple[Any, Any]:
    """Mean bars with SD (or SEM) and every point jittered over its bar."""
    if error not in {"sd", "sem"}:
        raise ValueError("error is 'sd' or 'sem'")
    data = frame[[group, value]].copy()
    data[value] = pd.to_numeric(data[value], errors="coerce")
    data = data.dropna()
    data[group] = data[group].astype(str)
    order = list(dict.fromkeys(data[group]))[:20]
    summary = data.groupby(group)[value].agg(["mean", "std", "count"]).reindex(order)
    spread = summary["std"] if error == "sd" else summary["std"] / np.sqrt(summary["count"])
    fig, ax = plt.subplots(figsize=(max(3.5, 0.8 * len(order) + 1.5), 4))
    positions = np.arange(len(order))
    ax.bar(
        positions,
        summary["mean"],
        yerr=spread.fillna(0),
        capsize=4,
        color=[plt.cm.tab10(i % 10) for i in range(len(order))],
        alpha=0.7,
        edgecolor="black",
        linewidth=0.8,
    )
    rng = np.random.default_rng(seed)
    for where, name in zip(positions, order, strict=True):
        points = data.loc[data[group] == name, value].to_numpy()
        ax.scatter(
            where + rng.uniform(-0.15, 0.15, len(points)),
            points,
            s=12,
            color="black",
            alpha=0.6,
            zorder=3,
        )
    ax.set_xticks(positions)
    ax.set_xticklabels(order)
    ax.set_xlabel(str(group))
    ax.set_ylabel(f"{value} (mean ± {error.upper()})")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return fig, ax
