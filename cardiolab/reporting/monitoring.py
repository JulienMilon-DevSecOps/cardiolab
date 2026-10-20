"""Weekly training adaptation table — 7-day lnRMSSD, CV and state (Plews)."""

from __future__ import annotations

import math
from datetime import date

import pandas as pd

from cardiolab.analytics.monitoring import MonitoringPoint, as_monitoring_points
from cardiolab.reporting._core import (
    apply_labels,
    caption,
    fmt_float,
    highlight_category,
)

_STATE_COLORS: dict[str, str] = {
    "coping": "#d5f5e3",
    "normal": "#fef9e7",
    "maladaptation": "#fdebd0",
    "overreaching_risk": "#fadbd8",
}


def weekly_monitoring_rows(baseline) -> list[dict]:
    """One row per ISO week, with the values of the week's last measurement day.

    Args:
        baseline: :class:`~cardiolab.analytics.baseline.Baseline`, list of
            ``HRVFeatures`` or monitoring points.

    Returns:
        Rows with ``week`` (``YYYY-Www``), ``last_date``, ``n_measures``,
        ``ln_rmssd_mean_7d``, ``cv_7d``, ``swc_low``, ``swc_high`` and
        ``state``.

    """
    points = as_monitoring_points(baseline)
    weeks: dict[str, list[MonitoringPoint]] = {}
    for p in points:
        iso = date.fromisoformat(p.date).isocalendar()
        weeks.setdefault(f"{iso.year}-W{iso.week:02d}", []).append(p)
    rows = []
    for week, items in weeks.items():
        last = items[-1]
        rows.append(
            {
                "week": week,
                "last_date": last.date,
                "n_measures": len(items),
                "ln_rmssd_mean_7d": last.mean_7d,
                "cv_7d": last.cv_7d,
                "swc_low": last.band.low if last.band else math.nan,
                "swc_high": last.band.high if last.band else math.nan,
                "state": last.state,
            }
        )
    return rows


def table_weekly_monitoring(
    baseline,
    labels: dict[str, str] | None = None,
    caption_text: str = "HRV monitoring — weekly 7-day lnRMSSD, CV and state",
) -> pd.Styler:
    """Build the weekly training adaptation table.

    Each row is an ISO week, with the 7-day mean and CV of lnRMSSD on its
    last measurement day, the SWC band and the state (coping / normal /
    maladaptation / overreaching risk, coloured).

    Args:
        baseline: :class:`~cardiolab.analytics.baseline.Baseline` (``poor``
            sessions excluded), list of ``HRVFeatures`` or monitoring points.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`).
        caption_text: Caption shown below the table.

    Returns:
        A :class:`~pandas.io.formats.style.Styler`.

    Raises:
        ValueError: If there is no dated session with an RMSSD.

    """
    rows = weekly_monitoring_rows(baseline)
    if not rows:
        raise ValueError("No dated session with an RMSSD.")
    df = pd.DataFrame(rows)

    def _state(val) -> str:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return "n/a"
        return labels.get(f"monitoring_state_{val}", val) if labels else str(val)

    fmt = {c: fmt_float(3) for c in ("ln_rmssd_mean_7d", "swc_low", "swc_high")}
    fmt["cv_7d"] = fmt_float(1)
    styler = df.style.format(fmt, na_rep="n/a").format(_state, subset=["state"])
    styler = highlight_category(styler, "state", _STATE_COLORS)
    styler = apply_labels(styler, labels)
    return caption(styler, caption_text)
