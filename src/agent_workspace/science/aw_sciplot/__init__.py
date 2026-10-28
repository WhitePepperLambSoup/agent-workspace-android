"""Figure helpers for research: journal styles, figures and panels sized to journal columns,
statistics on the plot, common research figures, journal checks, and saving figures so their
points can be dragged back into the data in Agent Workspace.

    import aw_sciplot as sp
    df = sp.read("data/measurements.csv")
    fig, ax = sp.figure("nature", journal="nature")
    ax.scatter(df["dose"], df["response"])
    sp.save(fig, "figures/dose_response")        # PNG, PDF, SVG and the point map
    print(sp.check("figures/dose_response", "nature"))

Follows Quick SciPlot (MIT, Copyright 2026 WhitePepperLambSoup).
"""

from aw_sciplot import templates
from aw_sciplot.check import check
from aw_sciplot.data import read
from aw_sciplot.figures import (
    JOURNALS,
    column_width,
    figure,
    fit_to_journal,
    label_panels,
    panels,
    save,
)
from aw_sciplot.stats import across, adjust, annotate_pairs, compare, fit_line
from aw_sciplot.style import STYLES, use

__version__ = "1.0.0"
__all__ = [
    "JOURNALS",
    "STYLES",
    "across",
    "adjust",
    "annotate_pairs",
    "check",
    "column_width",
    "compare",
    "figure",
    "fit_line",
    "fit_to_journal",
    "label_panels",
    "panels",
    "read",
    "save",
    "templates",
    "use",
]
