"""Visualisation helpers for VO2max estimation from HRV.

Three public functions cover the VO2max domain:

* :func:`plot_vo2max_comparison` — Grouped bars for the three model estimates
                                    (Uth / Esco-Flatt / ln-RMSSD) with ACSM
                                    fitness zone backgrounds.
* :func:`plot_vo2max_evolution`  — Multi-session best-estimate line with ±10 %
                                    model-uncertainty band and zone thresholds.
* :func:`plot_vo2max_gauge`      — Semi-circular fitness gauge (poor → excellent)
                                    with needle pointing to the best estimate.
"""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Wedge

from cardiolab.labels import lbl
from cardiolab.protocols.vo2max import VO2maxResult

# ── ACSM fitness thresholds (mL/kg/min) ──────────────────────────────────────

_VO2MAX_POOR: float = 28.0
_VO2MAX_FAIR: float = 38.0
_VO2MAX_GOOD: float = 48.0
_VO2MAX_VERY_GOOD: float = 58.0
_VO2MAX_MAX_GAUGE: float = 70.0

_MODEL_UNCERTAINTY: float = 0.10  # ±10 % band on the best estimate

# ── Zone definitions: (low, high, fill_color, label) ─────────────────────────

_VO2MAX_ZONES: list[tuple[float, float, str, str]] = [
    (0.0, _VO2MAX_POOR, "#fadbd8", "Poor      (< 28)"),
    (_VO2MAX_POOR, _VO2MAX_FAIR, "#fdebd0", "Fair      (28–37)"),
    (_VO2MAX_FAIR, _VO2MAX_GOOD, "#fef9e7", "Good      (38–47)"),
    (_VO2MAX_GOOD, _VO2MAX_VERY_GOOD, "#d6eaf8", "Very good (48–57)"),
    (_VO2MAX_VERY_GOOD, _VO2MAX_MAX_GAUGE, "#d5f5e3", "Excellent (≥ 58)"),
]
_VO2MAX_ZONE_KEYS = [
    "zone_vo2_poor", "zone_vo2_fair", "zone_vo2_good", "zone_vo2_very_good", "zone_vo2_excellent"
]

# ── Colour palettes ───────────────────────────────────────────────────────────

_CATEGORY_COLORS: dict[str, str] = {
    "poor": "#e74c3c",
    "fair": "#e67e22",
    "good": "#f39c12",
    "very_good": "#2980b9",
    "excellent": "#27ae60",
}

_MODEL_COLORS: dict[str, str] = {
    "Uth": "#2980b9",
    "Esco-Flatt": "#27ae60",
    "ln-RMSSD": "#e67e22",
}

# ── Gauge geometry ────────────────────────────────────────────────────────────

_GAUGE_R_OUTER: float = 1.0
_GAUGE_R_INNER: float = 0.58
_GAUGE_R_NEEDLE: float = 0.82
_GAUGE_R_LABEL: float = 1.22
_GAUGE_R_TICK_IN: float = 0.54
_GAUGE_R_TICK_OUT: float = 1.04

_DARK = "#2c3e50"
_GRAY = "#95a5a6"


# ── Public functions ──────────────────────────────────────────────────────────


def plot_vo2max_comparison(
    result: VO2maxResult,
    labels: dict[str, str] | None = None,
    title: str = "VO2max Estimates — Model Comparison",
    figsize: tuple[float, float] = (10, 5),
) -> Figure:
    """Plot grouped bars for all available VO2max model estimates.

    Draws one bar per model (Uth when ``hr_max`` was provided, Esco & Flatt,
    ln-RMSSD) against ACSM fitness-zone coloured backgrounds.  Zone threshold
    lines and right-margin labels allow immediate clinical positioning.

    Args:
        result: :class:`~cardiolab.protocols.vo2max.VO2maxResult` from
            :func:`~cardiolab.protocols.vo2max.vo2max_from_hrv`.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``result`` is not a :class:`~cardiolab.protocols.vo2max.VO2maxResult`.

    """
    _validate_result(result)

    # Build the list of (label, value, color) — skip Uth when not available
    models: list[tuple[str, float]] = []
    if not math.isnan(result.vo2max_uth):
        models.append(("Uth", result.vo2max_uth))
    models.append(("Esco-Flatt", result.vo2max_esco_flatt))
    models.append(("ln-RMSSD", result.vo2max_ln_rmssd))

    model_names = [m[0] for m in models]
    values = [m[1] for m in models]
    colors = [_MODEL_COLORS[m[0]] for m in models]

    y_max = max(_VO2MAX_MAX_GAUGE, max(values) * 1.12)

    fig, ax = plt.subplots(figsize=figsize)

    # Background zone bands
    for low, high, color, _ in _VO2MAX_ZONES:
        top = min(high, y_max)
        ax.axhspan(low, top, color=color, alpha=0.40, zorder=0)

    # Zone threshold lines + right-margin labels
    x_label = len(models) - 0.4
    for threshold in (_VO2MAX_POOR, _VO2MAX_FAIR, _VO2MAX_GOOD, _VO2MAX_VERY_GOOD):
        if threshold < y_max:
            ax.axhline(threshold, color=_GRAY, linewidth=0.7, linestyle=":", alpha=0.8)
    for (low, high, _, zone_label), zone_key in zip(_VO2MAX_ZONES, _VO2MAX_ZONE_KEYS, strict=True):
        mid = (low + min(high, y_max)) / 2.0
        if mid < y_max:
            ax.text(
                x_label,
                mid,
                lbl(labels, zone_key, zone_label).split()[0],
                ha="right",
                va="center",
                fontsize=8,
                color=_GRAY,
            )

    # Bars
    xs = list(range(len(models)))
    bars = ax.bar(xs, values, color=colors, width=0.5, zorder=4, alpha=0.85)

    # Value annotation on each bar
    for bar, val in zip(bars, values, strict=False):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            val + y_max * 0.015,
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color=bar.get_facecolor(),
        )

    # Annotation box — category + inputs
    cat = result.fitness_category.replace("_", " ").title()
    cat_color = _CATEGORY_COLORS.get(result.fitness_category, _DARK)
    hr_max_str = f"{result.hr_max:.0f} bpm" if not math.isnan(result.hr_max) else "n/a"
    txt = (
        f"Category  : {cat}\n"
        f"RMSSD     : {result.rmssd_used:.1f} ms\n"
        f"HR rest   : {result.hr_rest:.0f} bpm\n"
        f"HR max    : {hr_max_str}"
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

    ax.set_xticks(xs)
    ax.set_xticklabels(model_names, fontsize=10)
    ax.set_ylim(0.0, y_max)
    ax.set_ylabel(lbl(labels, "vo2max_uth", "VO2max (mL/kg/min)"), fontsize=10)
    ax.grid(alpha=0.20, linestyle=":", axis="y")
    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_vo2max_evolution(
    results: list[VO2maxResult],
    session_labels: list[str] | None = None,
    labels: dict[str, str] | None = None,
    title: str = "VO2max Evolution",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot VO2max best-estimate evolution over sessions with uncertainty band.

    The best estimate per session is Uth when available, otherwise ln-RMSSD.
    A ±10 % shaded band reflects typical model uncertainty (Uth: ±10–15 %,
    Esco-Flatt / ln-RMSSD: ±7–12 %).  ACSM zone backgrounds and threshold
    lines allow immediate fitness-category reading.

    Args:
        results: :class:`~cardiolab.protocols.vo2max.VO2maxResult` list in
            chronological order.
        session_labels: X-axis session labels. Falls back to date attributes
            or ``'Session N'`` when ``None``.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``results`` is not a list or contains non-VO2maxResult elements.
        ValueError: If ``results`` is empty or ``labels`` length mismatches.

    """
    _validate_results_list(results)
    n = len(results)

    if session_labels is not None and len(session_labels) != n:
        raise ValueError(
            f"session_labels length ({len(session_labels)}) must match results length ({n})"
        )
    session_labels = session_labels or _default_labels(results)

    best = np.array([_best_estimate(r) for r in results])
    categories = [r.fitness_category for r in results]
    y_max = max(_VO2MAX_MAX_GAUGE, float(np.max(best)) * 1.15)

    fig, ax = plt.subplots(figsize=figsize)

    # Background zone bands
    for low, high, color, _ in _VO2MAX_ZONES:
        top = min(high, y_max)
        ax.axhspan(low, top, color=color, alpha=0.35, zorder=0)

    # Threshold lines
    for threshold in (_VO2MAX_POOR, _VO2MAX_FAIR, _VO2MAX_GOOD, _VO2MAX_VERY_GOOD):
        if threshold < y_max:
            ax.axhline(threshold, color=_GRAY, linewidth=0.7, linestyle=":", alpha=0.8)

    # ±10 % uncertainty band
    xs = list(range(n))
    ax.fill_between(
        xs,
        best * (1.0 - _MODEL_UNCERTAINTY),
        best * (1.0 + _MODEL_UNCERTAINTY),
        color="#aed6f1",
        alpha=0.40,
        zorder=1,
        label=f"±{_MODEL_UNCERTAINTY:.0%} model uncertainty",
    )

    # Best estimate line
    ax.plot(xs, best, color=_DARK, linewidth=1.8, zorder=3, label="Best estimate")

    # Session dots coloured by category
    for x, val, cat in zip(xs, best, categories, strict=False):
        color = _CATEGORY_COLORS.get(cat, _DARK)
        ax.scatter([x], [val], s=65, color=color, zorder=5)
        ax.text(
            x,
            val + y_max * 0.02,
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color=color,
        )

    # Zone labels on right margin
    x_r = n - 0.5
    for (low, high, _, zone_label), zone_key in zip(_VO2MAX_ZONES, _VO2MAX_ZONE_KEYS, strict=True):
        mid = (low + min(high, y_max)) / 2.0
        if mid < y_max:
            ax.text(
                x_r,
                mid,
                lbl(labels, zone_key, zone_label).split()[0],
                ha="right",
                va="center",
                fontsize=8,
                color=_GRAY,
            )

    ax.set_xticks(xs)
    ax.set_xticklabels(session_labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylim(0.0, y_max)
    ax.set_ylabel(lbl(labels, "vo2max_uth", "VO2max (mL/kg/min)"), fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.20, linestyle=":", axis="y")
    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_vo2max_gauge(
    result: VO2maxResult,
    labels: dict[str, str] | None = None,
    title: str = "VO2max Fitness Gauge",
    figsize: tuple[float, float] = (6, 4),
) -> Figure:
    """Plot a semi-circular VO2max fitness gauge (poor → excellent).

    Five coloured annular sectors span 0–70 mL/kg/min and map to the ACSM
    fitness categories.  A needle points to the best available estimate (Uth
    when ``hr_max`` was provided, otherwise ln-RMSSD).  The numeric value and
    category are displayed below the pivot.

    Args:
        result: :class:`~cardiolab.protocols.vo2max.VO2maxResult` from
            :func:`~cardiolab.protocols.vo2max.vo2max_from_hrv`.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``result`` is not a :class:`~cardiolab.protocols.vo2max.VO2maxResult`.

    """
    _validate_result(result)

    best = _best_estimate(result)
    gauge_width = _GAUGE_R_OUTER - _GAUGE_R_INNER

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.45, 1.45)
    ax.set_ylim(-0.70, 1.35)

    # Coloured annular sectors
    for low, high, color, _ in _VO2MAX_ZONES:
        theta1 = _angle_from_vo2max(high)
        theta2 = _angle_from_vo2max(low)
        ax.add_patch(
            Wedge(
                (0.0, 0.0),
                _GAUGE_R_OUTER,
                theta1,
                theta2,
                width=gauge_width,
                color=color,
                zorder=2,
            )
        )

    # Outer arc outline
    ax.add_patch(
        Wedge(
            (0.0, 0.0),
            _GAUGE_R_OUTER,
            0.0,
            180.0,
            width=gauge_width,
            fill=False,
            edgecolor=_DARK,
            linewidth=0.8,
            zorder=3,
        )
    )

    # Tick marks at zone boundaries + max
    tick_vals = [
        0.0,
        _VO2MAX_POOR,
        _VO2MAX_FAIR,
        _VO2MAX_GOOD,
        _VO2MAX_VERY_GOOD,
        _VO2MAX_MAX_GAUGE,
    ]
    tick_lbls = ["0", "28", "38", "48", "58", "70"]
    for val, tick_label in zip(tick_vals, tick_lbls, strict=True):
        a_rad = math.radians(_angle_from_vo2max(val))
        xi = _GAUGE_R_TICK_IN * math.cos(a_rad)
        yi = _GAUGE_R_TICK_IN * math.sin(a_rad)
        xo = _GAUGE_R_TICK_OUT * math.cos(a_rad)
        yo = _GAUGE_R_TICK_OUT * math.sin(a_rad)
        ax.plot([xi, xo], [yi, yo], color=_DARK, linewidth=0.8, zorder=4)
        xl = _GAUGE_R_LABEL * math.cos(a_rad)
        yl = _GAUGE_R_LABEL * math.sin(a_rad)
        ax.text(xl, yl, tick_label, ha="center", va="center", fontsize=7, color=_DARK)

    # Zone labels inside sectors
    zone_r = (_GAUGE_R_OUTER + _GAUGE_R_INNER) / 2.0
    for (low, high, _, zone_label), zone_key in zip(_VO2MAX_ZONES, _VO2MAX_ZONE_KEYS, strict=True):
        mid_val = (low + high) / 2.0
        a_rad = math.radians(_angle_from_vo2max(mid_val))
        xl = zone_r * math.cos(a_rad)
        yl = zone_r * math.sin(a_rad)
        word = lbl(labels, zone_key, zone_label).split()[0]
        ax.text(
            xl,
            yl,
            word,
            ha="center",
            va="center",
            fontsize=5,
            color=_DARK,
            alpha=0.8,
            rotation=_angle_from_vo2max(mid_val) - 90,
        )

    # Needle
    val_clamped = max(0.0, min(best, _VO2MAX_MAX_GAUGE))
    a_rad = math.radians(_angle_from_vo2max(val_clamped))
    nx = _GAUGE_R_NEEDLE * math.cos(a_rad)
    ny = _GAUGE_R_NEEDLE * math.sin(a_rad)
    ax.plot(
        [0.0, nx],
        [0.0, ny],
        color=_DARK,
        linewidth=2.2,
        solid_capstyle="round",
        zorder=5,
    )
    ax.add_patch(plt.Circle((0.0, 0.0), 0.06, color=_DARK, zorder=6))

    # Central text
    cat = result.fitness_category.replace("_", " ").title()
    cat_color = _CATEGORY_COLORS.get(result.fitness_category, _DARK)
    ax.text(
        0.0,
        -0.18,
        f"{best:.0f}",
        ha="center",
        va="center",
        fontsize=24,
        fontweight="bold",
        color=cat_color,
    )
    ax.text(0.0, -0.38, "mL/kg/min", ha="center", va="center", fontsize=9, color=_GRAY)
    ax.text(
        0.0,
        -0.54,
        cat,
        ha="center",
        va="center",
        fontsize=11,
        fontweight="bold",
        color=cat_color,
    )

    fig.suptitle(title, fontsize=12, fontweight="bold", y=0.98)
    plt.tight_layout()
    return fig


# ── Private helpers ───────────────────────────────────────────────────────────


def _angle_from_vo2max(value: float) -> float:
    """Convert a VO2max value (mL/kg/min) to a gauge angle (degrees, 0–180).

    0 mL/kg/min maps to 180° (left); ``_VO2MAX_MAX_GAUGE`` maps to 0° (right).

    """
    clamped = max(0.0, min(value, _VO2MAX_MAX_GAUGE))
    return 180.0 - (clamped / _VO2MAX_MAX_GAUGE) * 180.0


def _best_estimate(result: VO2maxResult) -> float:
    """Return the best available VO2max estimate: Uth > ln-RMSSD > Esco-Flatt."""
    if not math.isnan(result.vo2max_uth):
        return result.vo2max_uth
    return result.vo2max_ln_rmssd


def _validate_result(result: VO2maxResult) -> None:
    """Raise TypeError when result is not a VO2maxResult."""
    if not isinstance(result, VO2maxResult):
        raise TypeError(f"result must be a VO2maxResult, got {type(result).__name__}")


def _validate_results_list(results: list[VO2maxResult]) -> None:
    """Raise TypeError or ValueError when results list is invalid."""
    if not isinstance(results, list):
        raise TypeError(f"results must be a list, got {type(results).__name__}")
    if len(results) == 0:
        raise ValueError("results must contain at least one VO2maxResult.")
    for idx, res in enumerate(results):
        if not isinstance(res, VO2maxResult):
            raise TypeError(
                f"results[{idx}] must be a VO2maxResult, got {type(res).__name__}"
            )


def _default_labels(results: list[VO2maxResult]) -> list[str]:
    """Return date strings from results or fallback 'Session N' labels."""
    return [
        str(r.date) if r.date else f"Session {i + 1}" for i, r in enumerate(results)
    ]
