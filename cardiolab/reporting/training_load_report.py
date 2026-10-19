"""Tabular reporting for the Training Load (ATL / CTL / TSB) model.

Public functions:

* :func:`table_training_load_history` — dense ATL/CTL/TSB history table with
  gradient colouring and TSB zone highlighting.
* :func:`summary_training_load` — scalar summary of the latest training load
  state: ATL, CTL, TSB, relative form and its zone, and CTL trend.

Changed in 0.5.0: the zone is read on the relative form (TSB in % of CTL,
:func:`~cardiolab.analytics.training_load.form_zone`), no longer on TSB
against fixed thresholds (+25 / +5 / −10 / −30) that only suit one load scale.
"""

from __future__ import annotations

import pandas as pd

from cardiolab.analytics.training_load import TrainingLoad, form_zone
from cardiolab.reporting._core import (
    _TSB_ZONE_COLORS,
    apply_labels,
    caption,
    fmt_float,
    gradient_bad,
    gradient_good,
    highlight_category,
)


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
    labels: dict[str, str] | None = None,
    caption_text: str = "Training load history — ATL / CTL / TSB",
) -> pd.Styler:
    """Build a daily ATL / CTL / TSB history table.

    One row per day.  CTL (fitness) is highlighted green when high; ATL
    (fatigue) is highlighted red when high; ``form_pct`` is TSB in % of CTL
    and the ``tsb_zone`` column its zone (empty during the first 42 days).

    Args:
        training_load: A populated
            :class:`~cardiolab.analytics.training_load.TrainingLoad` instance.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
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
        form = float(training_load.form[i])
        rows.append(
            {
                "date": date,
                "trimp": float(training_load.trimp[i]),
                "atl": float(training_load.atl[i]),
                "ctl": float(training_load.ctl[i]),
                "tsb": float(training_load.tsb[i]),
                "form_pct": form,
                "tsb_zone": form_zone(form),
            }
        )

    df = pd.DataFrame(rows)

    fmt: dict = {
        "trimp": fmt_float(1),
        "atl": fmt_float(2),
        "ctl": fmt_float(2),
        "tsb": fmt_float(2),
        "form_pct": fmt_float(0),
    }

    styler = df.style.format(fmt, na_rep="n/a")
    styler = gradient_good(styler, ["ctl"], vmin=0)
    styler = gradient_bad(styler, ["atl"], vmin=0)
    styler = highlight_category(styler, "tsb_zone", _TSB_ZONE_COLORS)
    styler = apply_labels(styler, labels)

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
        * ``form_pct`` — TSB in % of CTL, rounded to 1 d.p. (``None``
          during the first 42 days).
        * ``load_ratio`` — ATL / CTL, rounded to 2 d.p. (``None`` likewise).
        * ``tsb_zone`` — zone of ``form_pct`` (``None`` likewise).
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
    form = float(training_load.form[-1])
    known = form == form  # not nan

    return {
        "atl": atl,
        "ctl": ctl,
        "tsb": tsb,
        "form_pct": round(form, 1) if known else None,
        "load_ratio": round(1.0 - form / 100.0, 2) if known else None,
        "tsb_zone": form_zone(form),
        "ctl_trend": _ctl_trend(training_load.ctl),
    }
