"""Tabular reporting for the Training Load (ATL / CTL / TSB) model.

Public functions:

* :func:`table_training_load_history` — dense ATL/CTL/TSB history table with
  gradient colouring and TSB zone highlighting.
* :func:`summary_training_load` — scalar summary of the latest training load
  state: ATL, CTL, TSB, TSB zone, and CTL trend.
"""

from __future__ import annotations

import pandas as pd

from cardiolab.analytics.training_load import TrainingLoad
from cardiolab.reporting._core import (
    _TSB_ZONE_COLORS,
    caption,
    fmt_float,
    gradient_bad,
    gradient_good,
    highlight_category,
)

# ── TSB zone classification ────────────────────────────────────────────────────
# Thresholds from Coggan 2003 / Plews et al. 2013.

_TSB_THRESHOLDS: list[tuple[float, str]] = [
    (25.0, "fresh_detraining"),
    (5.0, "optimal"),
    (-10.0, "neutral"),
    (-30.0, "accumulated_fatigue"),
]


def _tsb_zone_label(tsb: float) -> str:
    for threshold, zone in _TSB_THRESHOLDS:
        if tsb > threshold:
            return zone
    return "overload"


def _ctl_trend(
    ctl_array: list | object, window: int = 7, threshold: float = 1.0
) -> str:
    """Return 'increasing', 'stable', or 'decreasing' based on CTL over *window* days."""
    n = len(ctl_array)
    if n < window + 1:
        return "stable"
    diff = float(ctl_array[-1]) - float(ctl_array[-(window + 1)])
    if diff > threshold:
        return "increasing"
    if diff < -threshold:
        return "decreasing"
    return "stable"


# ── Public functions ───────────────────────────────────────────────────────────


def table_training_load_history(
    training_load: TrainingLoad,
    caption_text: str = "Historique Training Load — ATL / CTL / TSB",
) -> pd.Styler:
    """Build a daily ATL / CTL / TSB history table.

    One row per day.  CTL (fitness) is highlighted green when high; ATL
    (fatigue) is highlighted red when high; the TSB zone column is coloured
    by physiological band (Coggan 2003 / Plews 2013).

    Args:
        training_load: A populated
            :class:`~cardiolab.analytics.training_load.TrainingLoad` instance.
        caption_text: Caption shown below the table.

    Returns:
        A :class:`~pandas.io.formats.style.Styler` ready for ``display()``.

    Raises:
        ValueError: If ``training_load`` contains no data.

    """
    if not training_load.dates:
        raise ValueError("TrainingLoad must contain at least one day of data.")

    rows = []
    for i, date in enumerate(training_load.dates):
        tsb_val = float(training_load.tsb[i])
        rows.append(
            {
                "date": date,
                "trimp": float(training_load.trimp[i]),
                "atl": float(training_load.atl[i]),
                "ctl": float(training_load.ctl[i]),
                "tsb": tsb_val,
                "tsb_zone": _tsb_zone_label(tsb_val),
            }
        )

    df = pd.DataFrame(rows)

    fmt: dict = {
        "trimp": fmt_float(1),
        "atl": fmt_float(2),
        "ctl": fmt_float(2),
        "tsb": fmt_float(2),
    }

    styler = df.style.format(fmt, na_rep="n/a")
    styler = gradient_good(styler, ["ctl"], vmin=0)
    styler = gradient_bad(styler, ["atl"], vmin=0)
    styler = highlight_category(styler, "tsb_zone", _TSB_ZONE_COLORS)

    return caption(styler, caption_text)


def summary_training_load(training_load: TrainingLoad) -> dict:
    """Return a scalar summary of the latest training load state.

    All values are computed from the last day in ``training_load``.

    Args:
        training_load: A populated
            :class:`~cardiolab.analytics.training_load.TrainingLoad` instance.

    Returns:
        A dict with keys:

        * ``atl`` — latest Acute Training Load (fatigue), rounded to 2 d.p.
        * ``ctl`` — latest Chronic Training Load (fitness), rounded to 2 d.p.
        * ``tsb`` — latest Training Stress Balance (form), rounded to 2 d.p.
        * ``tsb_zone`` — physiological zone label (str).
        * ``ctl_trend`` — ``"increasing"`` / ``"stable"`` / ``"decreasing"``
          based on the 7-day CTL change.

    Raises:
        ValueError: If ``training_load`` contains no data.

    """
    if not training_load.dates:
        raise ValueError("TrainingLoad must contain at least one day of data.")

    atl = round(float(training_load.atl[-1]), 2)
    ctl = round(float(training_load.ctl[-1]), 2)
    tsb = round(float(training_load.tsb[-1]), 2)

    return {
        "atl": atl,
        "ctl": ctl,
        "tsb": tsb,
        "tsb_zone": _tsb_zone_label(tsb),
        "ctl_trend": _ctl_trend(training_load.ctl),
    }
