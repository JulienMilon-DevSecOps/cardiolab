"""Visualisation helpers for cardiac drift analysis.

Two public functions cover the cardiac drift domain:

* :func:`plot_drift_curve`  — Windowed HR scatter + linear regression line with
                               coloured background for a single session.
* :func:`plot_drift_zones`  — Multi-session drift-rate evolution with clinical
                               zone bands for immediate severity reading.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from cardiolab.labels import lbl
from cardiolab.protocols.cardiac_drift import DriftResult
from cardiolab.signals.rr import RRSeries

# ── Clinical thresholds (bpm/min) ─────────────────────────────────────────────

_DRIFT_NO_THRESHOLD: float = 0.5
_DRIFT_MILD_THRESHOLD: float = 1.5
_DRIFT_MOD_THRESHOLD: float = 3.0
_DRIFT_MAX_AXIS: float = 5.0

_MIN_WINDOWS: int = 3

# ── Zone definitions: (low, high, fill_color, label) ─────────────────────────

_DRIFT_ZONES: list[tuple[float, float, str, str]] = [
    (0.0, _DRIFT_NO_THRESHOLD, "#d5f5e3", "No drift  (< 0.5)"),
    (_DRIFT_NO_THRESHOLD, _DRIFT_MILD_THRESHOLD, "#fef9e7", "Mild      (0.5–1.5)"),
    (_DRIFT_MILD_THRESHOLD, _DRIFT_MOD_THRESHOLD, "#fdebd0", "Moderate  (1.5–3.0)"),
    (_DRIFT_MOD_THRESHOLD, _DRIFT_MAX_AXIS, "#fadbd8", "Strong    (> 3.0)"),
]
_DRIFT_ZONE_KEYS = ["zone_drift_no_drift", "zone_drift_mild", "zone_drift_moderate", "zone_drift_strong"]

# ── Category colours ──────────────────────────────────────────────────────────

_CATEGORY_COLORS: dict[str, str] = {
    "no_drift": "#27ae60",
    "mild": "#f39c12",
    "moderate": "#e67e22",
    "strong": "#e74c3c",
}

_ZONE_BG: dict[str, str] = {
    "no_drift": "#eafaf1",
    "mild": "#fefdf0",
    "moderate": "#fdf2e9",
    "strong": "#fdf0ef",
}

_DARK = "#2c3e50"
_GRAY = "#95a5a6"


# ── Public functions ──────────────────────────────────────────────────────────


def plot_drift_curve(
    rr: RRSeries,
    result: DriftResult,
    window_sec: float = 60.0,
    title: str = "Cardiac Drift — HR per Window + Linear Regression",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot windowed HR over time with linear regression and zone background.

    Recomputes the same non-overlapping windows as
    :func:`~cardiolab.protocols.cardiac_drift.cardiac_drift` and draws each
    window's mean HR as a scatter point.  The linear regression from ``result``
    is overlaid as a dashed line.  The axes background is tinted with the
    category colour for immediate severity reading.

    Args:
        rr: Exercise :class:`~cardiolab.signals.rr.RRSeries`.
        result: :class:`~cardiolab.protocols.cardiac_drift.DriftResult` from
            :func:`~cardiolab.protocols.cardiac_drift.cardiac_drift`.
        window_sec: Window length in seconds — must match the value used when
            computing ``result``. Defaults to 60.0.
        title: Figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``rr`` or ``result`` have the wrong type.
        ValueError: If ``rr`` is too short for at least ``_MIN_WINDOWS`` windows.

    """
    _validate_rr(rr, window_sec)
    _validate_result(result)

    win_times_min, win_hrs = _drift_windows(rr, window_sec)

    fig, ax = plt.subplots(figsize=figsize)

    # Background tinted by category
    ax.set_facecolor(_ZONE_BG.get(result.interpretation, "#f8f9fa"))

    cat_color = _CATEGORY_COLORS.get(result.interpretation, _DARK)

    # Windowed HR scatter
    ax.scatter(
        win_times_min,
        win_hrs,
        s=60,
        color=cat_color,
        zorder=4,
        label="Mean HR per window",
    )

    # Linear regression line (centroid-anchored)
    t_mean = float(np.mean(win_times_min))
    hr_mean = float(np.mean(win_hrs))
    intercept = hr_mean - result.drift_rate * t_mean
    t_line = np.linspace(win_times_min[0], win_times_min[-1], 200)
    hr_line = result.drift_rate * t_line + intercept
    sign = "+" if result.drift_rate >= 0 else ""
    ax.plot(
        t_line,
        hr_line,
        color=_DARK,
        linewidth=1.8,
        linestyle="--",
        zorder=5,
        label=f"Regression  {sign}{result.drift_rate:.2f} bpm/min",
    )

    # Initial / final HR horizontal references
    ax.axhline(
        result.initial_hr,
        color=_GRAY,
        linewidth=0.7,
        linestyle=":",
        alpha=0.7,
        label=f"Initial HR ({result.initial_hr:.0f} bpm)",
    )
    ax.axhline(
        result.final_hr,
        color=cat_color,
        linewidth=0.7,
        linestyle=":",
        alpha=0.7,
        label=f"Final HR ({result.final_hr:.0f} bpm)",
    )

    # Annotation box
    interp_label = result.interpretation.replace("_", " ").title()
    txt = (
        f"Drift rate  : {sign}{result.drift_rate:.2f} bpm/min\n"
        f"Magnitude   : {result.drift_magnitude:+.1f} bpm\n"
        f"R²          : {result.r_squared:.3f}\n"
        f"Category    : {interp_label}"
    )
    ax.text(
        0.02,
        0.97,
        txt,
        transform=ax.transAxes,
        fontsize=8,
        va="top",
        ha="left",
        bbox={
            "boxstyle": "round,pad=0.4",
            "fc": "white",
            "alpha": 0.88,
            "ec": cat_color,
        },
        zorder=6,
    )

    ax.set_xlabel("Time (min)", fontsize=10)
    ax.set_ylabel("Heart rate (bpm)", fontsize=10)
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(alpha=0.20, linestyle=":")
    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_drift_zones(
    results: list[DriftResult],
    session_labels: list[str] | None = None,
    labels: dict[str, str] | None = None,
    title: str = "Cardiac Drift — Session Evolution",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot drift-rate evolution over sessions with clinical zone backgrounds.

    Each session is plotted as a coloured dot (colour encodes the clinical
    category).  Horizontal coloured bands mark the four clinical zones,
    allowing immediate severity comparison across sessions.

    The y-axis uses the **absolute** drift rate so that any direction of
    progressive HR change (upward or downward) is evaluated against the same
    clinical thresholds.

    Args:
        results: :class:`~cardiolab.protocols.cardiac_drift.DriftResult` list
            in chronological order.
        session_labels: X-axis session labels. Falls back to date attributes
            or ``'Session N'`` when ``None``.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``results`` is not a list or contains non-DriftResult elements.
        ValueError: If ``results`` is empty or ``labels`` length mismatches.

    """
    _validate_results_list(results)
    n = len(results)

    if session_labels is not None and len(session_labels) != n:
        raise ValueError(
            f"session_labels length ({len(session_labels)}) must match results length ({n})"
        )
    session_labels = session_labels or _default_labels(results)

    drift_rates = [abs(r.drift_rate) for r in results]
    categories = [r.interpretation for r in results]
    y_max = max(_DRIFT_MAX_AXIS, max(drift_rates) * 1.15)

    fig, ax = plt.subplots(figsize=figsize)

    # Background zone bands
    legend_patches: list[Patch] = []
    for low, high, color, zone_label in _DRIFT_ZONES:
        top = min(high, y_max)
        ax.axhspan(low, top, color=color, alpha=0.45, zorder=0)
        legend_patches.append(Patch(facecolor=color, label=zone_label, alpha=0.65))

    # Threshold boundary lines
    for threshold in (_DRIFT_NO_THRESHOLD, _DRIFT_MILD_THRESHOLD, _DRIFT_MOD_THRESHOLD):
        if threshold < y_max:
            ax.axhline(threshold, color=_GRAY, linewidth=0.7, linestyle=":", alpha=0.8)

    # Zone labels on the right margin
    x_label_pos = n - 0.5
    zone_mids = [
        (
            _DRIFT_NO_THRESHOLD / 2.0,
            (_DRIFT_NO_THRESHOLD + _DRIFT_MILD_THRESHOLD) / 2.0,
            (_DRIFT_MILD_THRESHOLD + _DRIFT_MOD_THRESHOLD) / 2.0,
            (_DRIFT_MOD_THRESHOLD + y_max) / 2.0,
        ),
        ("No drift", "Mild", "Moderate", "Strong"),
    ]
    for y_mid, zone_text in zip(zone_mids[0], zone_mids[1], strict=True):
        if float(y_mid) <= y_max:
            ax.text(
                x_label_pos,
                float(y_mid),
                str(zone_text),
                ha="right",
                va="center",
                fontsize=8,
                color=_GRAY,
            )

    # Session points connected by a neutral line
    xs = list(range(n))
    ax.plot(xs, drift_rates, color=_GRAY, linewidth=1.2, zorder=3, alpha=0.6)
    for x, rate, cat in zip(xs, drift_rates, categories, strict=False):
        color = _CATEGORY_COLORS.get(cat, _DARK)
        ax.scatter([x], [rate], s=70, color=color, zorder=5)
        ax.text(
            x,
            rate + y_max * 0.015,
            f"{rate:.2f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color=color,
        )

    ax.set_xticks(xs)
    ax.set_xticklabels(session_labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylim(0.0, y_max)
    ax.set_ylabel(lbl(labels, "drift_rate", "|Drift rate| (%/min)"), fontsize=10)
    ax.legend(
        handles=legend_patches,
        loc="upper left",
        fontsize=8,
        title="Clinical zones",
        title_fontsize=8,
    )
    ax.grid(alpha=0.20, linestyle=":", axis="y")
    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


# ── Private helpers ───────────────────────────────────────────────────────────


def _drift_windows(
    rr: RRSeries,
    window_sec: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (times_min, mean_hr_per_window) matching the protocol's windows."""
    rr_ms = np.array(rr.intervals, dtype=float)
    time_s = np.cumsum(rr_ms) / 1000.0
    time_s -= time_s[0]
    duration = float(time_s[-1])
    hrs: list[float] = []
    times: list[float] = []
    t_start = 0.0
    while t_start + window_sec <= duration:
        t_end = t_start + window_sec
        mask = (time_s >= t_start) & (time_s < t_end)
        beats = rr_ms[mask]
        if len(beats) > 0:
            hrs.append(60_000.0 / float(np.mean(beats)))
            times.append((t_start + window_sec / 2.0) / 60.0)
        t_start += window_sec
    return np.array(times), np.array(hrs)


def _validate_rr(rr: RRSeries, window_sec: float) -> None:
    """Raise TypeError or ValueError when rr is invalid for drift plotting."""
    if not isinstance(rr, RRSeries):
        raise TypeError(f"rr must be an RRSeries, got {type(rr).__name__}")
    rr_ms = np.array(rr.intervals, dtype=float)
    time_s = np.cumsum(rr_ms) / 1000.0
    duration = float(time_s[-1] - time_s[0])
    n_windows = int(duration // window_sec)
    if n_windows < _MIN_WINDOWS:
        raise ValueError(
            f"RRSeries too short: need at least {_MIN_WINDOWS} windows of "
            f"{window_sec:.0f} s (found {n_windows}). "
            f"Record at least {_MIN_WINDOWS * window_sec:.0f} s."
        )


def _validate_result(result: DriftResult) -> None:
    """Raise TypeError when result is not a DriftResult."""
    if not isinstance(result, DriftResult):
        raise TypeError(f"result must be a DriftResult, got {type(result).__name__}")


def _validate_results_list(results: list[DriftResult]) -> None:
    """Raise TypeError or ValueError when results list is invalid."""
    if not isinstance(results, list):
        raise TypeError(f"results must be a list, got {type(results).__name__}")
    if len(results) == 0:
        raise ValueError("results must contain at least one DriftResult.")
    for idx, res in enumerate(results):
        if not isinstance(res, DriftResult):
            raise TypeError(
                f"results[{idx}] must be a DriftResult, got {type(res).__name__}"
            )


def _default_labels(results: list[DriftResult]) -> list[str]:
    """Return date strings from results or fallback 'Session N' labels."""
    return [
        str(r.date) if r.date else f"Session {i + 1}" for i, r in enumerate(results)
    ]
