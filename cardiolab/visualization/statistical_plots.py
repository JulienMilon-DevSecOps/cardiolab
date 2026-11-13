"""Statistical charts — multivariate anomalies over time, trends with confidence band."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date, timedelta

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from cardiolab.analytics.trends import (
    _metric_series,
    detect_sustained_decline,
    trend_line,
)
from cardiolab.labels import LABELS_EN, lbl

_DIST_COLOR = "#2c3e50"
_THRESHOLD_COLOR = "#c0392b"
_ANOMALY_COLOR = "#7c5cc4"
_MUTED = "#95a5a6"
_DARK = "#2c3e50"
_Z_LIMIT = 4.0

TREND_COLORS: dict[str, str] = {
    "increasing": "#27ae60",
    "decreasing": "#c0392b",
    "stable": "#2980b9",
}
"""Colour of the trend line for each label."""

_REQUIRED = ("date", "mahalanobis", "threshold", "is_anomaly", "status")


def _day(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _t(labels: dict[str, str] | None, key: str) -> str:
    """Label of *key*, English by default."""
    return lbl(labels, key, LABELS_EN[key])


def _p_text(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.2g}"


def _runs(flags: Sequence[bool]) -> list[tuple[int, int]]:
    """``(first, last)`` index of each run of ``True``."""
    runs, start = [], None
    for i, flag in enumerate(flags):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(flags) - 1))
    return runs


# ======================
# ANOMALY TIMELINE
# ======================


def plot_anomaly_timeline(
    report,
    labels: dict[str, str] | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (12, 7),
) -> Figure:
    """Plot the Mahalanobis distance of each session against its threshold.

    Top panel:

    * dark line and dots — distance of each session to the cloud of its
      reference sessions;
    * red dashed steps — alert threshold (it depends on the number of
      reference sessions);
    * purple diamonds and shading — unusual sessions (distance above the
      threshold);
    * grey band — sessions without enough reference (``insufficient_data``);
    * hollow grey circles on the axis — sessions not checked (a metric is
      missing).

    Bottom panel (when the report has ``z_<metric>`` columns): one row per
    metric, one square per session, coloured by its deviation from the
    reference in SD (blue below, red above, capped at ±4). It shows which
    metric makes a session unusual.

    Args:
        report: DataFrame returned by
            :func:`~cardiolab.analytics.multivariate.anomaly_report`.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`).
        title: Figure title. Defaults to the ``anomaly_timeline_title`` label.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        ValueError: If the report is empty or lacks a required column.

    """
    missing = [c for c in _REQUIRED if c not in report.columns]
    if missing:
        raise ValueError(f"Not an anomaly_report() table: missing {missing}.")
    if len(report) == 0:
        raise ValueError("The report has no session to plot.")

    days = [_day(d) for d in report["date"]]
    dist = report["mahalanobis"].to_numpy(dtype=float)
    thr = report["threshold"].to_numpy(dtype=float)
    status = list(report["status"])
    anomaly = report["is_anomaly"].to_numpy(dtype=bool)
    z_cols = [c for c in report.columns if c.startswith("z_")]

    if z_cols:
        fig, (ax, ax_z) = plt.subplots(
            2,
            1,
            figsize=figsize,
            sharex=True,
            gridspec_kw={"height_ratios": [3, 0.45 * len(z_cols) + 0.6]},
        )
    else:
        fig, ax = plt.subplots(figsize=figsize)
        ax_z = None

    half = timedelta(hours=12)
    for k, (first, last) in enumerate(
        _runs([s == "insufficient_data" for s in status])
    ):
        ax.axvspan(
            days[first] - half,
            days[last] + half,
            color=_MUTED,
            alpha=0.15,
            linewidth=0,
            label=_t(labels, "anomaly_building") if k == 0 else None,
        )

    ok = np.isfinite(dist)
    if ok.any():
        d_days = [d for d, keep in zip(days, ok, strict=True) if keep]
        ax.plot(d_days, dist[ok], color=_DIST_COLOR, linewidth=1.0, alpha=0.7)
        ax.scatter(
            d_days,
            dist[ok],
            s=14,
            color=_DIST_COLOR,
            zorder=3,
            label=_t(labels, "anomaly_distance"),
        )
        t_ok = np.isfinite(thr)
        ax.step(
            [d for d, keep in zip(days, t_ok, strict=True) if keep],
            thr[t_ok],
            where="mid",
            color=_THRESHOLD_COLOR,
            linestyle="--",
            linewidth=1.3,
            label=_t(labels, "anomaly_threshold"),
        )
        both = ok & t_ok
        ax.fill_between(
            days,
            np.where(both, thr, np.nan),
            np.where(both, dist, np.nan),
            where=both & (dist > thr),
            color=_ANOMALY_COLOR,
            alpha=0.25,
            interpolate=True,
            linewidth=0,
        )
    if anomaly.any():
        ax.scatter(
            [d for d, a in zip(days, anomaly, strict=True) if a],
            dist[anomaly],
            marker="D",
            s=60,
            color=_ANOMALY_COLOR,
            edgecolors="white",
            linewidths=0.8,
            zorder=5,
            label=_t(labels, "anomaly_marker"),
        )
    unchecked = [s in ("missing_features", "no_variability") for s in status]
    if any(unchecked):
        ax.scatter(
            [d for d, u in zip(days, unchecked, strict=True) if u],
            [0.0] * sum(unchecked),
            marker="o",
            s=30,
            facecolors="none",
            edgecolors=_MUTED,
            zorder=4,
            clip_on=False,
            label=_t(labels, "anomaly_not_checked"),
        )

    finite = np.concatenate([dist[ok], thr[np.isfinite(thr)]])
    ax.set_ylim(0, max(5.0, float(finite.max()) * 1.1) if finite.size else 5.0)
    ax.set_ylabel(_t(labels, "anomaly_distance"))
    ax.grid(alpha=0.2, linestyle=":")
    ax.legend(loc="upper left", fontsize=8)

    if ax_z is not None:
        size = max(6.0, min(60.0, 3000.0 / len(days)))
        scatter = None
        for row, col in enumerate(z_cols):
            z = report[col].to_numpy(dtype=float)
            keep = np.isfinite(z)
            if keep.any():
                scatter = ax_z.scatter(
                    [d for d, k in zip(days, keep, strict=True) if k],
                    [row] * int(keep.sum()),
                    c=np.clip(z[keep], -_Z_LIMIT, _Z_LIMIT),
                    cmap="RdBu_r",
                    vmin=-_Z_LIMIT,
                    vmax=_Z_LIMIT,
                    marker="s",
                    s=size,
                    linewidths=0,
                )
        ax_z.set_yticks(range(len(z_cols)))
        ax_z.set_yticklabels([lbl(labels, c[2:], c[2:]) for c in z_cols], fontsize=8)
        ax_z.set_ylim(-0.6, len(z_cols) - 0.4)
        ax_z.invert_yaxis()
        ax_z.grid(False)
        if scatter is not None:
            cax = ax_z.inset_axes([1.01, 0.0, 0.012, 1.0])
            bar = fig.colorbar(scatter, cax=cax)
            bar.set_label(
                _t(labels, "anomaly_zscore"),
                fontsize=7,
            )
            bar.ax.tick_params(labelsize=7)
        bottom = ax_z
    else:
        bottom = ax

    bottom.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    fig.autofmt_xdate()
    fig.suptitle(
        title or _t(labels, "anomaly_timeline_title"),
        fontsize=12,
        fontweight="bold",
        color=_DARK,
    )
    plt.tight_layout()
    return fig


# ======================
# TREND OVERLAY
# ======================


def _dated_pairs(series, metric: str) -> list[tuple[date, float]]:
    items = list(series.sessions if hasattr(series, "sessions") else series)
    if items and not isinstance(items[0], (tuple, list)):
        items = _metric_series(items, metric)
    pairs = []
    for item in items:
        day, value = item
        if day is None or value is None:
            continue
        value = float(value)
        if math.isfinite(value):
            pairs.append((_day(day), value))
    return sorted(pairs, key=lambda p: p[0])


def plot_trend_overlay(
    series,
    windows: Sequence[int | None] = (30,),
    *,
    metric: str = "score",
    end: str | date | None = None,
    level: float = 0.95,
    show_decline: bool = True,
    labels: dict[str, str] | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (12, 6),
) -> Figure:
    """Plot a series with the trend line of one or several windows and its band.

    * grey dots — the values (up to ``end``);
    * one line per window — the fitted trend
      (:func:`~cardiolab.analytics.trends.trend_line`), green when
      ``increasing``, red when ``decreasing``, blue when ``stable``; solid,
      dashed then dotted for the following windows;
    * shaded band of the same colour — confidence band of the line
      (``level``, 95 % by default), corrected for autocorrelation like the
      p-value;
    * legend — slope per week, p-value and label of each window;
    * red rings and dotted line — with ``show_decline``, the last values
      below the usual range
      (:func:`~cardiolab.analytics.trends.detect_sustained_decline`).

    Args:
        series: ``[(date, value), …]``, a
            :class:`~cardiolab.analytics.baseline.Baseline` or a list of dated
            ``HRVFeatures`` (``metric`` is then read on each session).
        windows: Window lengths in days; ``None`` = the whole series.
        metric: Attribute read on the sessions (``"score"``, ``"rmssd"``…);
            also the y-axis label key.
        end: Last day shown and last day of every window. Defaults to the last
            date of the series.
        level: Confidence level of the bands.
        show_decline: Highlight a sustained decline of the last values.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`).
        title: Figure title. Defaults to the ``trend_overlay_title`` label.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        ValueError: If the series has no dated value, or ``windows`` is empty.

    """
    if not windows:
        raise ValueError("Give at least one window (None = the whole series).")
    pairs = _dated_pairs(series, metric)
    if end is not None:
        last = _day(end)
        pairs = [p for p in pairs if p[0] <= last]
    if not pairs:
        raise ValueError("No dated value to plot.")
    days = [d for d, _ in pairs]
    values = np.array([v for _, v in pairs])

    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(days, values, color=_MUTED, linewidth=0.8, alpha=0.6)
    ax.scatter(
        days,
        values,
        s=14,
        color=_MUTED,
        zorder=3,
        label=_t(labels, "trend_values"),
    )

    styles = ("-", "--", ":")
    per_week = _t(labels, "trend_per_week")
    band_label = _t(labels, "trend_band").format(level=f"{level * 100:g}")
    band_shown = False
    for i, window in enumerate(windows):
        tl = trend_line(pairs, window, level=level)
        res = tl.result
        name = (
            _t(labels, "trend_window_all")
            if window is None
            else _t(labels, "trend_window_days").format(days=window)
        )
        state = _t(labels, f"trend_{res.label}")
        if res.label == "insufficient_data" or tl.days is None:
            ax.plot(
                [], [], color=_MUTED, linestyle=styles[i % 3], label=f"{name}: {state}"
            )
            continue
        color = TREND_COLORS.get(res.label, TREND_COLORS["stable"])
        ax.plot(
            tl.days,
            tl.fitted,
            color=color,
            linestyle=styles[i % 3],
            linewidth=2.0,
            zorder=4,
            label=f"{name}: {res.slope * 7:+.1f}{per_week}, {_p_text(res.p_value)} — {state}",
        )
        if np.isfinite(tl.lower).any():
            ax.fill_between(
                tl.days,
                tl.lower,
                tl.upper,
                color=color,
                alpha=0.15,
                linewidth=0,
                label=None if band_shown else band_label,
            )
            band_shown = True

    if show_decline:
        decline = detect_sustained_decline(pairs)
        if decline.detected:
            run_days = days[-decline.run_length :]
            ax.scatter(
                run_days,
                values[-decline.run_length :],
                s=70,
                facecolors="none",
                edgecolors=TREND_COLORS["decreasing"],
                linewidths=1.2,
                zorder=5,
                label=_t(labels, "trend_sustained_decline").format(
                    n=decline.run_length
                ),
            )
            ax.hlines(
                decline.limit,
                run_days[0],
                run_days[-1],
                colors=TREND_COLORS["decreasing"],
                linestyles=":",
                linewidth=1.2,
            )

    ax.set_ylabel(lbl(labels, metric, metric))
    ax.grid(alpha=0.2, linestyle=":")
    ax.legend(loc="best", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    fig.autofmt_xdate()
    fig.suptitle(
        title or _t(labels, "trend_overlay_title"),
        fontsize=12,
        fontweight="bold",
        color=_DARK,
    )
    plt.tight_layout()
    return fig
