"""Visualisation helpers for Heart Rate Recovery (HRR) analysis.

Three public functions cover the HRR domain:

* :func:`plot_hrr_curve`       — HR recovery curve with HRR1/HRR2 markers and category.
* :func:`plot_hrr_comparison`  — Multi-session HR-drop curves coloured by date.
* :func:`plot_hrr_gauge`       — Semi-circular HRR1 gauge (red → green).
"""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Wedge

from cardiolab.protocols.hrr import HRRResult
from cardiolab.signals.rr import RRSeries

# ── Clinical thresholds (Cole et al. 1999 for HRR1) ──────────────────────────

_HRR_EXCELLENT_BPM = 25.0
_HRR_GOOD_BPM = 20.0
_HRR_NORMAL_BPM = 12.0
_HRR_MAX_GAUGE_BPM = 40.0

# ── Processing constants ──────────────────────────────────────────────────────

_MIN_INTERVALS_HRR = 5
_HRR_INTERP_FS: float = 4.0

# ── Gauge geometry ────────────────────────────────────────────────────────────

_GAUGE_R_OUTER: float = 1.0
_GAUGE_R_INNER: float = 0.58
_GAUGE_R_NEEDLE: float = 0.82
_GAUGE_R_LABEL: float = 1.22
_GAUGE_R_TICK_IN: float = 0.54
_GAUGE_R_TICK_OUT: float = 1.04

# ── Colour palette ────────────────────────────────────────────────────────────

_HR_COLOR = "#2980b9"
_HRR1_COLOR = "#e74c3c"
_HRR2_COLOR = "#8e44ad"
_DARK = "#2c3e50"
_GRAY = "#95a5a6"

_PALETTE = [
    "#2980b9",
    "#27ae60",
    "#e74c3c",
    "#f39c12",
    "#8e44ad",
    "#16a085",
    "#d35400",
    "#7f8c8d",
]

_CATEGORY_COLORS: dict[str, str] = {
    "excellent": "#27ae60",
    "good": "#2980b9",
    "normal": "#f39c12",
    "impaired": "#e74c3c",
}

# Low → high, used for comparison background bands and gauge sectors
_HRR_ZONES: list[tuple[float, float, str, str]] = [
    (0.0, _HRR_NORMAL_BPM, "#fadbd8", "Impaired  (< 12)"),
    (_HRR_NORMAL_BPM, _HRR_GOOD_BPM, "#fdebd0", "Normal   (12–19)"),
    (_HRR_GOOD_BPM, _HRR_EXCELLENT_BPM, "#d6eaf8", "Good     (20–24)"),
    (_HRR_EXCELLENT_BPM, _HRR_MAX_GAUGE_BPM, "#d5f5e3", "Excellent (≥ 25)"),
]


# ── Public functions ──────────────────────────────────────────────────────────


def plot_hrr_curve(
    rr: RRSeries,
    result: HRRResult,
    fs: float = _HRR_INTERP_FS,
    title: str = "Heart Rate Recovery Curve",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot the post-exercise HR recovery curve with HRR1 and HRR2 markers.

    Draws the interpolated HR time series from peak effort (t = 0) to the end
    of the recording.  Double-headed arrows at t = 60 s and t = 120 s show the
    HR drop (HRR1 and HRR2) with their clinical categories.

    Args:
        rr: Post-exercise :class:`~cardiolab.signals.rr.RRSeries` starting at
            peak effort.
        result: :class:`~cardiolab.protocols.hrr.HRRResult` from
            :func:`~cardiolab.protocols.hrr.heart_rate_recovery`.
        fs: Resampling frequency in Hz. Defaults to 4.0.
        title: Figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``rr`` or ``result`` have the wrong type.
        ValueError: If ``rr`` has fewer than ``_MIN_INTERVALS_HRR`` intervals.

    """
    _validate_rr(rr)
    _validate_result(result)

    time_s, hr_interp = _hrr_time_series(rr, fs)

    fig, ax = plt.subplots(figsize=figsize)

    ax.plot(
        time_s, hr_interp, color=_HR_COLOR, linewidth=1.8, label="HR (bpm)", zorder=4
    )
    ax.axhline(
        result.hr_peak,
        color=_GRAY,
        linewidth=0.8,
        linestyle="--",
        alpha=0.7,
        label=f"Peak HR ({result.hr_peak:.0f} bpm)",
    )

    # HRR1 marker at 60 s
    _draw_hrr_marker(
        ax,
        t=60.0,
        hr_ref=result.hr_peak,
        hr_mark=result.hr_at_60s,
        drop=result.hrr_60,
        category=result.hrr_60_category,
        color=_HRR1_COLOR,
        label="HRR1",
    )

    # HRR2 marker at 120 s (when available)
    if not math.isnan(result.hrr_120) and result.duration >= 120.0:
        _draw_hrr_marker(
            ax,
            t=120.0,
            hr_ref=result.hr_peak,
            hr_mark=result.hr_at_120s,
            drop=result.hrr_120,
            category=result.hrr_120_category,
            color=_HRR2_COLOR,
            label="HRR2",
        )

    ax.set_xlabel("Time post-peak (s)", fontsize=10)
    ax.set_ylabel("Heart rate (bpm)", fontsize=10)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.20, linestyle=":")
    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_hrr_comparison(
    rr_list: list[RRSeries],
    results: list[HRRResult],
    labels: list[str] | None = None,
    fs: float = _HRR_INTERP_FS,
    title: str = "Heart Rate Recovery — Session Comparison",
    figsize: tuple[float, float] = (12, 6),
) -> Figure:
    """Plot multiple HR-drop recovery curves superimposed and coloured by session.

    All curves are expressed as HR drop from peak (bpm): ``HR_peak − HR(t)``.
    They all start at 0 and rise as recovery progresses.  Background horizontal
    bands indicate clinical HRR1 thresholds at the 60 s mark.

    Args:
        rr_list: Post-exercise :class:`~cardiolab.signals.rr.RRSeries` per session.
        results: :class:`~cardiolab.protocols.hrr.HRRResult` per session.
            Must have the same length as ``rr_list``.
        labels: Session labels. Falls back to ``result.date`` or ``"Session N"``.
        fs: Resampling frequency in Hz. Defaults to 4.0.
        title: Figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``rr_list`` or ``results`` have the wrong type or element type.
        ValueError: If ``rr_list`` is empty, or lengths differ, or ``labels``
            length mismatches.

    """
    _validate_rr_results(rr_list, results)
    n = len(results)

    if labels is not None and len(labels) != n:
        raise ValueError(
            f"labels length ({len(labels)}) must match results length ({n})"
        )
    labels = labels or _default_labels(results)

    fig, ax = plt.subplots(figsize=figsize)

    # Background interpretation bands for the HR-drop axis
    for low, high, color, _ in _HRR_ZONES:
        ax.axhspan(low, high, color=color, alpha=0.30, zorder=0)
    for threshold in (_HRR_NORMAL_BPM, _HRR_GOOD_BPM, _HRR_EXCELLENT_BPM):
        ax.axhline(threshold, color=_GRAY, linewidth=0.6, linestyle=":", alpha=0.7)

    # Vertical reference line at t=60 s
    ax.axvline(60.0, color=_GRAY, linewidth=0.7, linestyle="--", alpha=0.5)
    ax.text(60.5, 1.5, "60 s", fontsize=7, color=_GRAY)

    max_t = 0.0
    for idx, (rr, res, lbl) in enumerate(zip(rr_list, results, labels, strict=False)):
        color = _PALETTE[idx % len(_PALETTE)]
        time_s, hr_interp = _hrr_time_series(rr, fs)
        hr_drop = res.hr_peak - hr_interp
        hr_drop = np.clip(hr_drop, 0.0, None)  # prevent negative artefacts at t=0
        cat = res.hrr_60_category.title() if res.hrr_60_category else "—"
        ax.plot(
            time_s,
            hr_drop,
            color=color,
            linewidth=1.6,
            label=f"{lbl}  HRR1={res.hrr_60:.0f} ({cat})",
            zorder=4,
        )
        # Marker at 60 s
        if res.duration >= 60.0:
            ax.scatter([60.0], [res.hrr_60], s=50, color=color, zorder=5)
        max_t = max(max_t, float(time_s[-1]))

    # Zone labels on the right margin
    for low, high, _, zone_label in _HRR_ZONES:
        mid = (low + high) / 2.0
        ax.text(
            max_t * 0.99,
            mid,
            zone_label,
            ha="right",
            va="center",
            fontsize=7,
            color=_GRAY,
        )

    ax.set_xlim(left=0.0)
    ax.set_ylim(bottom=0.0)
    ax.set_xlabel("Time post-peak (s)", fontsize=10)
    ax.set_ylabel("HR drop from peak (bpm)", fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.20, linestyle=":", axis="both")
    fig.suptitle(title, fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()
    return fig


def plot_hrr_gauge(
    result: HRRResult,
    title: str = "HRR1 Gauge",
    figsize: tuple[float, float] = (6, 4),
) -> Figure:
    """Plot a semi-circular HRR1 gauge coloured red → green by clinical zone.

    The gauge spans 0–{_HRR_MAX_GAUGE_BPM} bpm. Zones are drawn as coloured
    annular sectors (Wedge patches).  A needle points to the HRR1 value.
    The numeric value and clinical category are displayed below the pivot.

    Args:
        result: :class:`~cardiolab.protocols.hrr.HRRResult` from
            :func:`~cardiolab.protocols.hrr.heart_rate_recovery`.
        title: Figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``result`` is not a :class:`~cardiolab.protocols.hrr.HRRResult`.

    """
    _validate_result(result)

    gauge_width = _GAUGE_R_OUTER - _GAUGE_R_INNER

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.45, 1.45)
    ax.set_ylim(-0.70, 1.35)

    # ── Coloured annular sectors ──────────────────────────────────────────────
    for low, high, color, _ in _HRR_ZONES:
        theta1 = _angle_from_hrr(high)
        theta2 = _angle_from_hrr(low)
        wedge = Wedge(
            (0.0, 0.0),
            _GAUGE_R_OUTER,
            theta1,
            theta2,
            width=gauge_width,
            color=color,
            zorder=2,
        )
        ax.add_patch(wedge)

    # Outer arc outline
    arc_wedge = Wedge(
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
    ax.add_patch(arc_wedge)

    # ── Tick marks and labels at zone boundaries ──────────────────────────────
    for tick_val, tick_label in (
        (0.0, "0"),
        (_HRR_NORMAL_BPM, "12"),
        (_HRR_GOOD_BPM, "20"),
        (_HRR_EXCELLENT_BPM, "25"),
        (_HRR_MAX_GAUGE_BPM, "40"),
    ):
        angle_rad = math.radians(_angle_from_hrr(tick_val))
        xi = _GAUGE_R_TICK_IN * math.cos(angle_rad)
        yi = _GAUGE_R_TICK_IN * math.sin(angle_rad)
        xo = _GAUGE_R_TICK_OUT * math.cos(angle_rad)
        yo = _GAUGE_R_TICK_OUT * math.sin(angle_rad)
        ax.plot([xi, xo], [yi, yo], color=_DARK, linewidth=0.8, zorder=4)
        xl = _GAUGE_R_LABEL * math.cos(angle_rad)
        yl = _GAUGE_R_LABEL * math.sin(angle_rad)
        ax.text(xl, yl, tick_label, ha="center", va="center", fontsize=8, color=_DARK)

    # ── Zone labels (inside sectors) ─────────────────────────────────────────
    zone_label_r = (_GAUGE_R_OUTER + _GAUGE_R_INNER) / 2.0
    for low, high, _, zone_label in _HRR_ZONES:
        mid_val = (low + high) / 2.0
        angle_rad = math.radians(_angle_from_hrr(mid_val))
        xl = zone_label_r * math.cos(angle_rad)
        yl = zone_label_r * math.sin(angle_rad)
        # Remove the threshold range from the label (just keep the word)
        word = zone_label.split()[0]
        ax.text(
            xl,
            yl,
            word,
            ha="center",
            va="center",
            fontsize=6,
            color=_DARK,
            alpha=0.8,
            rotation=_angle_from_hrr(mid_val) - 90,
        )

    # ── Needle ────────────────────────────────────────────────────────────────
    hrr1_clamped = max(0.0, min(result.hrr_60, _HRR_MAX_GAUGE_BPM))
    needle_angle_rad = math.radians(_angle_from_hrr(hrr1_clamped))
    nx = _GAUGE_R_NEEDLE * math.cos(needle_angle_rad)
    ny = _GAUGE_R_NEEDLE * math.sin(needle_angle_rad)
    ax.plot(
        [0.0, nx],
        [0.0, ny],
        color=_DARK,
        linewidth=2.2,
        solid_capstyle="round",
        zorder=5,
    )
    ax.add_patch(plt.Circle((0.0, 0.0), 0.06, color=_DARK, zorder=6))

    # ── Central value display ─────────────────────────────────────────────────
    cat = result.hrr_60_category or "—"
    cat_color = _CATEGORY_COLORS.get(cat, _DARK)
    ax.text(
        0.0,
        -0.18,
        f"{result.hrr_60:.0f}",
        ha="center",
        va="center",
        fontsize=26,
        fontweight="bold",
        color=cat_color,
    )
    ax.text(0.0, -0.38, "bpm HRR1", ha="center", va="center", fontsize=9, color=_GRAY)
    ax.text(
        0.0,
        -0.54,
        cat.title(),
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


def _hrr_time_series(
    rr: RRSeries,
    fs: float = _HRR_INTERP_FS,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute a uniform HR time series (bpm) from a post-exercise RRSeries.

    Returns a tuple ``(time_s, hr_interp)`` where ``time_s`` starts at 0 and
    ``hr_interp`` is the linearly interpolated instantaneous HR.

    """
    rr_ms = np.array(rr.intervals, dtype=float)
    time_s = np.cumsum(rr_ms) / 1000.0
    time_s -= time_s[0]
    hr_inst = 60_000.0 / rr_ms
    interp_time = np.arange(0, time_s[-1], 1.0 / fs)
    hr_interp = np.interp(interp_time, time_s, hr_inst)
    return interp_time, hr_interp


def _draw_hrr_marker(
    ax: plt.Axes,
    t: float,
    hr_ref: float,
    hr_mark: float,
    drop: float,
    category: str,
    color: str,
    label: str,
) -> None:
    """Draw a vertical marker line, scatter dot, and drop arrow on the axis."""
    cat_word = category.title() if category else "—"
    ax.axvline(t, color=color, linewidth=0.8, linestyle=":", alpha=0.7, zorder=3)
    ax.scatter([t], [hr_mark], s=60, color=color, zorder=5)
    ax.annotate(
        "",
        xy=(t, hr_mark),
        xytext=(t, hr_ref),
        arrowprops={"arrowstyle": "<->", "color": color, "lw": 1.2},
        zorder=4,
    )
    ax.text(
        t + 1.5,
        (hr_mark + hr_ref) / 2.0,
        f"{label} = {drop:.0f} bpm\n({cat_word})",
        color=color,
        fontsize=8,
        va="center",
    )


def _angle_from_hrr(value: float) -> float:
    """Convert an HRR value (bpm) to a gauge angle (degrees, 0–180).

    0 bpm maps to 180° (left); ``_HRR_MAX_GAUGE_BPM`` maps to 0° (right).

    """
    clamped = max(0.0, min(value, _HRR_MAX_GAUGE_BPM))
    return 180.0 - (clamped / _HRR_MAX_GAUGE_BPM) * 180.0


def _validate_rr(rr: RRSeries) -> None:
    """Raise TypeError or ValueError when rr is not a valid RRSeries."""
    if not isinstance(rr, RRSeries):
        raise TypeError(f"rr must be an RRSeries, got {type(rr).__name__}")
    if len(rr.intervals) < _MIN_INTERVALS_HRR:
        raise ValueError(
            f"rr must have at least {_MIN_INTERVALS_HRR} intervals, "
            f"got {len(rr.intervals)}"
        )


def _validate_result(result: HRRResult) -> None:
    """Raise TypeError when result is not an HRRResult."""
    if not isinstance(result, HRRResult):
        raise TypeError(f"result must be an HRRResult, got {type(result).__name__}")


def _validate_rr_results(
    rr_list: list[RRSeries],
    results: list[HRRResult],
) -> None:
    """Raise TypeError or ValueError when rr_list or results are invalid."""
    if not isinstance(rr_list, list):
        raise TypeError(f"rr_list must be a list, got {type(rr_list).__name__}")
    if not isinstance(results, list):
        raise TypeError(f"results must be a list, got {type(results).__name__}")
    if len(rr_list) == 0:
        raise ValueError("rr_list must contain at least one RRSeries.")
    if len(rr_list) != len(results):
        raise ValueError(
            f"rr_list length ({len(rr_list)}) must match "
            f"results length ({len(results)})"
        )
    for idx, rr in enumerate(rr_list):
        if not isinstance(rr, RRSeries):
            raise TypeError(
                f"rr_list[{idx}] must be an RRSeries, got {type(rr).__name__}"
            )
    for idx, res in enumerate(results):
        if not isinstance(res, HRRResult):
            raise TypeError(
                f"results[{idx}] must be an HRRResult, got {type(res).__name__}"
            )


def _default_labels(results: list[HRRResult]) -> list[str]:
    """Return date strings from results or fallback 'Session N' labels."""
    return [
        str(r.date) if r.date else f"Session {i + 1}" for i, r in enumerate(results)
    ]
