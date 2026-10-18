"""Training adaptation monitoring chart — 7-day lnRMSSD, SWC band, CV (Plews)."""

from __future__ import annotations

import math
from datetime import date

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from cardiolab.analytics.monitoring import as_monitoring_points
from cardiolab.labels import lbl

_DAILY_COLOR = "#95a5a6"
_MEAN_COLOR = "#2980b9"
_BAND_COLOR = "#27ae60"
_CV_COLOR = "#e67e22"
_DARK = "#2c3e50"

STATE_COLORS: dict[str, str] = {
    "coping": "#27ae60",
    "normal": "#2980b9",
    "maladaptation": "#e67e22",
    "overreaching_risk": "#c0392b",
}
"""Colour of each training adaptation state."""


def plot_ln_rmssd_monitoring(
    baseline,
    labels: dict[str, str] | None = None,
    title: str = "HRV monitoring — 7-day lnRMSSD",
    figsize: tuple[float, float] = (12, 6),
) -> Figure:
    """Plot the 7-day lnRMSSD mean against the SWC band, with the CV on a second axis.

    * grey dots — daily lnRMSSD;
    * blue line — 7-day rolling mean, its markers coloured by training
      adaptation state (coping / normal / maladaptation / overreaching risk);
    * green band — smallest worthwhile change around the 28-day baseline;
    * orange dashed line (right axis) — 7-day coefficient of variation.

    Args:
        baseline: :class:`~cardiolab.analytics.baseline.Baseline` (``poor``
            sessions excluded), list of ``HRVFeatures``, or the points of
            :func:`~cardiolab.analytics.monitoring.monitoring_series`.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`).
        title: Figure title.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        ValueError: If there is no dated session with an RMSSD.

    """
    points = as_monitoring_points(baseline)
    if not points:
        raise ValueError("No dated session with an RMSSD to plot.")

    days = [date.fromisoformat(p.date) for p in points]
    daily = np.array([p.ln_rmssd for p in points])
    mean = np.array([p.mean_7d for p in points])
    cv = np.array([p.cv_7d for p in points])
    low = np.array([p.band.low if p.band else math.nan for p in points])
    high = np.array([p.band.high if p.band else math.nan for p in points])

    fig, ax = plt.subplots(figsize=figsize)
    ax.fill_between(
        days,
        low,
        high,
        color=_BAND_COLOR,
        alpha=0.18,
        step="mid",
        label=lbl(labels, "monitoring_swc_band", "SWC band (baseline ± 0.5 SD)"),
    )
    ax.scatter(
        days,
        daily,
        s=14,
        color=_DAILY_COLOR,
        zorder=3,
        label=lbl(labels, "monitoring_daily", "Daily lnRMSSD"),
    )
    ax.plot(
        days,
        mean,
        color=_MEAN_COLOR,
        linewidth=2.0,
        zorder=4,
        label=lbl(labels, "monitoring_mean_7d", "7-day mean"),
    )
    for state, color in STATE_COLORS.items():
        idx = [i for i, p in enumerate(points) if p.state == state]
        if idx:
            ax.scatter(
                [days[i] for i in idx],
                mean[idx],
                s=36,
                color=color,
                edgecolors="white",
                linewidths=0.6,
                zorder=5,
                label=lbl(labels, f"monitoring_state_{state}", state.replace("_", " ")),
            )
    ax.set_ylabel(lbl(labels, "ln_rmssd", "lnRMSSD"), fontsize=10)
    ax.grid(alpha=0.2, linestyle=":")

    ax_cv = ax.twinx()
    ax_cv.plot(
        days,
        cv,
        color=_CV_COLOR,
        linestyle="--",
        linewidth=1.3,
        label=lbl(labels, "monitoring_cv_7d", "7-day CV (%)"),
    )
    ax_cv.set_ylabel(lbl(labels, "monitoring_cv_7d", "7-day CV (%)"), color=_CV_COLOR)
    ax_cv.tick_params(axis="y", colors=_CV_COLOR)
    finite_cv = cv[np.isfinite(cv)]
    ax_cv.set_ylim(
        0, max(10.0, float(finite_cv.max()) * 2.5) if finite_cv.size else 10.0
    )

    handles, names = ax.get_legend_handles_labels()
    cv_handles, cv_names = ax_cv.get_legend_handles_labels()
    ax.legend(handles + cv_handles, names + cv_names, loc="upper left", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    fig.autofmt_xdate()
    fig.suptitle(title, fontsize=12, fontweight="bold", color=_DARK)
    plt.tight_layout()
    return fig
