"""Visualisation helpers for non-linear HRV analysis.

Three public functions cover the Poincaré domain:

* :func:`plot_poincare`            — Poincaré scatter with SD1/SD2 ellipse and arrows.
* :func:`plot_poincare_comparison` — Side-by-side supine vs standing Poincaré plots.
* :func:`plot_sd1_sd2_evolution`   — SD1, SD2 and SD1/SD2 ratio evolution over sessions.
"""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse

from cardiolab.protocols.resting import HRVFeatures
from cardiolab.signals.rr import RRSeries

# ── Constants ─────────────────────────────────────────────────────────────────

_MIN_INTERVALS_POINCARE = 3

# ── Colour palette ────────────────────────────────────────────────────────────

_SD1_COLOR = "#2980b9"
_SD2_COLOR = "#e67e22"
_RATIO_COLOR = "#27ae60"
_SUPINE_COLOR = "#2980b9"
_STANDING_COLOR = "#e74c3c"
_IDENTITY_COLOR = "#95a5a6"
_SCATTER_COLOR = "#7f8c8d"
_ELLIPSE_COLOR = "#2c3e50"
_DARK = "#2c3e50"
_GRAY = "#95a5a6"


# ── Public functions ──────────────────────────────────────────────────────────


def plot_poincare(
    rr: RRSeries,
    title: str = "Poincaré Plot",
    figsize: tuple[float, float] = (6, 6),
) -> Figure:
    """Plot a Poincaré scatter diagram of RR(n) vs RR(n+1) with SD1/SD2 ellipse.

    Draws a scatter cloud of consecutive interval pairs (RR_n, RR_{n+1}),
    the identity line y=x, and the SD1/SD2 ellipse centred on the mean RR.
    SD1 (short axis, blue) and SD2 (long axis, orange) are annotated as arrows
    from the centroid.  A text box reports the three scalar values.

    Args:
        rr: :class:`~cardiolab.signals.rr.RRSeries` to visualise.
        title: Figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``rr`` is not an :class:`~cardiolab.signals.rr.RRSeries`.
        ValueError: If ``rr`` contains fewer than ``_MIN_INTERVALS_POINCARE`` intervals.

    """
    _validate_rr(rr)

    stats = _poincare_stats(rr)
    limits = _poincare_limits(rr)

    fig, ax = plt.subplots(figsize=figsize)
    _draw_poincare_on_ax(
        ax, rr, scatter_color=_SCATTER_COLOR, limits=limits, show_arrows=True
    )
    _add_stats_annotation(ax, stats)

    legend_elements = [
        Line2D(
            [0], [0], color=_SD1_COLOR, lw=1.5, label=f"SD1 = {stats['sd1']:.1f} ms"
        ),
        Line2D(
            [0], [0], color=_SD2_COLOR, lw=1.5, label=f"SD2 = {stats['sd2']:.1f} ms"
        ),
        Line2D([0], [0], color=_IDENTITY_COLOR, lw=0.9, linestyle="--", label="y = x"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8)
    ax.set_xlabel("RR(n) (ms)", fontsize=10)
    ax.set_ylabel("RR(n+1) (ms)", fontsize=10)
    ax.grid(alpha=0.20, linestyle=":")
    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_poincare_comparison(
    rr_supine: RRSeries,
    rr_standing: RRSeries,
    label_supine: str = "Supine",
    label_standing: str = "Standing",
    title: str = "Poincaré Plot — Orthostatic Comparison",
    figsize: tuple[float, float] = (12, 6),
) -> Figure:
    """Plot two side-by-side Poincaré diagrams for supine and standing phases.

    Both panels share the same axis range so the change in cloud geometry is
    directly comparable.  The supine cloud is drawn in blue and the standing
    cloud in red.  Each panel shows SD1/SD2 ellipse, identity line, SD arrows
    and a compact stats annotation box.

    The contraction of SD1 on standing (vagal withdrawal) is the key feature
    to identify: a smaller, more elongated ellipse in the standing panel
    reflects sympathetic activation.

    Args:
        rr_supine: :class:`~cardiolab.signals.rr.RRSeries` for the supine phase.
        rr_standing: :class:`~cardiolab.signals.rr.RRSeries` for the standing phase.
        label_supine: Subplot title for the supine panel.
        label_standing: Subplot title for the standing panel.
        title: Overall figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If either argument is not an :class:`~cardiolab.signals.rr.RRSeries`.
        ValueError: If either series has fewer than ``_MIN_INTERVALS_POINCARE`` intervals.

    """
    _validate_rr(rr_supine)
    _validate_rr(rr_standing)

    stats_supine = _poincare_stats(rr_supine)
    stats_standing = _poincare_stats(rr_standing)

    # Shared axis range across both series
    lim_min = min(
        _poincare_limits(rr_supine)[0],
        _poincare_limits(rr_standing)[0],
    )
    lim_max = max(
        _poincare_limits(rr_supine)[1],
        _poincare_limits(rr_standing)[1],
    )
    limits = (lim_min, lim_max)

    fig, (ax_sup, ax_sta) = plt.subplots(1, 2, figsize=figsize)

    for ax, rr, color, stats, label in (
        (ax_sup, rr_supine, _SUPINE_COLOR, stats_supine, label_supine),
        (ax_sta, rr_standing, _STANDING_COLOR, stats_standing, label_standing),
    ):
        _draw_poincare_on_ax(
            ax, rr, scatter_color=color, limits=limits, show_arrows=True
        )
        _add_stats_annotation(ax, stats)
        ax.set_title(label, fontsize=11, fontweight="bold")
        ax.set_xlabel("RR(n) (ms)", fontsize=9)
        ax.set_ylabel("RR(n+1) (ms)", fontsize=9)
        ax.grid(alpha=0.20, linestyle=":")
        legend_elements = [
            Line2D([0], [0], color=color, lw=1.5, label=f"SD1 = {stats['sd1']:.1f} ms"),
            Line2D(
                [0], [0], color=_SD2_COLOR, lw=1.5, label=f"SD2 = {stats['sd2']:.1f} ms"
            ),
            Line2D(
                [0], [0], color=_IDENTITY_COLOR, lw=0.9, linestyle="--", label="y = x"
            ),
        ]
        ax.legend(handles=legend_elements, loc="lower right", fontsize=7)

    fig.suptitle(title, fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_sd1_sd2_evolution(
    features_list: list[HRVFeatures],
    labels: list[str] | None = None,
    title: str = "SD1 / SD2 Evolution",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot SD1, SD2, and their ratio over a sequence of resting sessions.

    Produces a single figure with:

    * **Left axis** — SD1 (blue) and SD2 (orange) in milliseconds, one point
      per session.  SD1 reflects short-term (vagal) variability; SD2 reflects
      overall autonomic regulation.
    * **Right axis** — SD1/SD2 ratio (green dashed), indicating the shape of
      the Poincaré ellipse.  A decreasing ratio over time signals growing
      sympathetic dominance.

    ``float('nan')`` values in SD1/SD2 ratio are plotted as gaps.

    Args:
        features_list: List of :class:`~cardiolab.protocols.resting.HRVFeatures`
            in chronological order.
        labels: X-axis session labels.  Falls back to the ``date`` attribute of
            each :class:`~cardiolab.protocols.resting.HRVFeatures` or to
            ``"Session N"`` when no date is set.
        title: Figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``features_list`` is not a list or contains non-HRVFeatures
            elements.
        ValueError: If ``features_list`` is empty.
        ValueError: If ``labels`` length does not match ``features_list``.

    """
    _validate_features_list(features_list)
    n = len(features_list)

    if labels is not None and len(labels) != n:
        raise ValueError(
            f"labels length ({len(labels)}) must match features_list length ({n})"
        )

    labels = labels or _default_labels(features_list)
    x = np.arange(n)

    sd1_arr = np.array([f.sd1 for f in features_list], dtype=float)
    sd2_arr = np.array([f.sd2 for f in features_list], dtype=float)
    ratio_arr = np.array(
        [
            f.sd_ratio if not math.isnan(f.sd_ratio) else float("nan")
            for f in features_list
        ],
        dtype=float,
    )

    fig, ax = plt.subplots(figsize=figsize)
    ax_ratio = ax.twinx()

    # SD1 and SD2 on the left axis
    ax.plot(
        x,
        sd1_arr,
        color=_SD1_COLOR,
        linewidth=1.8,
        marker="o",
        markersize=5,
        label="SD1 (ms)",
        zorder=4,
    )
    ax.plot(
        x,
        sd2_arr,
        color=_SD2_COLOR,
        linewidth=1.8,
        marker="s",
        markersize=5,
        label="SD2 (ms)",
        zorder=4,
    )
    ax.set_ylabel("SD1 / SD2 (ms)", fontsize=10)
    ax.grid(alpha=0.20, linestyle=":")

    # SD1/SD2 ratio on the right axis
    ax_ratio.plot(
        x,
        ratio_arr,
        color=_RATIO_COLOR,
        linewidth=1.4,
        linestyle="--",
        marker="^",
        markersize=5,
        label="SD1/SD2 ratio",
        zorder=3,
    )
    ax_ratio.set_ylabel("SD1/SD2 ratio", fontsize=10, color=_RATIO_COLOR)
    ax_ratio.tick_params(axis="y", colors=_RATIO_COLOR)
    ax_ratio.set_ylim(0, None)

    # Shared x-axis
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=9)

    # Combined legend
    handles_left, labels_left = ax.get_legend_handles_labels()
    handles_right, labels_right = ax_ratio.get_legend_handles_labels()
    ax.legend(
        handles_left + handles_right,
        labels_left + labels_right,
        loc="upper left",
        fontsize=8,
    )

    fig.suptitle(title, fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()
    return fig


# ── Private helpers ───────────────────────────────────────────────────────────


def _poincare_stats(rr: RRSeries) -> dict:
    """Compute Poincaré cloud statistics (centroid, SD1, SD2, ratio).

    Returns a dict with keys ``cx``, ``cy``, ``sd1``, ``sd2``, ``ratio``.

    """
    intervals = np.array(rr.intervals, dtype=float)
    cx = float(np.mean(intervals[:-1]))
    cy = float(np.mean(intervals[1:]))
    diff = np.diff(intervals)
    sd1_val = float(np.sqrt(np.mean(diff**2)) / np.sqrt(2))
    sdnn_val = float(np.std(intervals, ddof=1))
    sd2_sq = max(2.0 * sdnn_val**2 - sd1_val**2, 0.0)
    sd2_val = float(np.sqrt(sd2_sq))
    ratio = sd1_val / sd2_val if sd2_val > 0.0 else float("nan")
    return {"cx": cx, "cy": cy, "sd1": sd1_val, "sd2": sd2_val, "ratio": ratio}


def _poincare_limits(rr: RRSeries) -> tuple[float, float]:
    """Return symmetric axis limits with 5 % padding for a Poincaré plot."""
    intervals = np.array(rr.intervals, dtype=float)
    lo = float(intervals.min()) * 0.95
    hi = float(intervals.max()) * 1.05
    return lo, hi


def _draw_poincare_on_ax(
    ax: plt.Axes,
    rr: RRSeries,
    scatter_color: str,
    limits: tuple[float, float],
    show_arrows: bool = True,
) -> None:
    """Draw scatter, identity line, SD1/SD2 ellipse and arrows on an existing axis.

    Does not set labels, grid, or title — the caller is responsible for those.

    Args:
        ax: Target matplotlib :class:`~matplotlib.axes.Axes`.
        rr: :class:`~cardiolab.signals.rr.RRSeries` to plot.
        scatter_color: Colour for scatter points and SD1 arrow.
        limits: ``(min, max)`` axis bounds for both x and y.
        show_arrows: Whether to draw SD1/SD2 arrows from the centroid.

    """
    intervals = np.array(rr.intervals, dtype=float)
    rr_n = intervals[:-1]
    rr_n1 = intervals[1:]
    stats = _poincare_stats(rr)
    cx, cy = stats["cx"], stats["cy"]
    sd1_val, sd2_val = stats["sd1"], stats["sd2"]

    lo, hi = limits

    # Identity line
    ax.plot(
        [lo, hi],
        [lo, hi],
        color=_IDENTITY_COLOR,
        linewidth=0.9,
        linestyle="--",
        alpha=0.7,
    )

    # Scatter
    ax.scatter(rr_n, rr_n1, s=8, color=scatter_color, alpha=0.35, zorder=2)

    # SD1/SD2 ellipse (rotated 45°: width=long axis=SD2, height=short axis=SD1)
    ellipse = Ellipse(
        (cx, cy),
        width=2 * sd2_val,
        height=2 * sd1_val,
        angle=45,
        edgecolor=_ELLIPSE_COLOR,
        facecolor="none",
        linewidth=1.5,
        zorder=3,
    )
    ax.add_patch(ellipse)

    # Centroid dot
    ax.scatter([cx], [cy], s=40, color=_DARK, zorder=5)

    if show_arrows:
        sqrt2 = float(np.sqrt(2))
        # SD1: perpendicular to identity line — direction (-1, +1)/√2
        ax.annotate(
            "",
            xy=(cx - sd1_val / sqrt2, cy + sd1_val / sqrt2),
            xytext=(cx, cy),
            arrowprops={"arrowstyle": "->", "color": scatter_color, "lw": 1.5},
            zorder=6,
        )
        # SD2: along identity line — direction (+1, +1)/√2
        ax.annotate(
            "",
            xy=(cx + sd2_val / sqrt2, cy + sd2_val / sqrt2),
            xytext=(cx, cy),
            arrowprops={"arrowstyle": "->", "color": _SD2_COLOR, "lw": 1.5},
            zorder=6,
        )

    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal")


def _add_stats_annotation(ax: plt.Axes, stats: dict) -> None:
    """Add an SD1/SD2/ratio text box in the top-left corner of an axis."""
    ratio_str = f"{stats['ratio']:.2f}" if not math.isnan(stats["ratio"]) else "—"
    text = (
        f"SD1 = {stats['sd1']:.1f} ms\n"
        f"SD2 = {stats['sd2']:.1f} ms\n"
        f"SD1/SD2 = {ratio_str}"
    )
    ax.text(
        0.03,
        0.97,
        text,
        transform=ax.transAxes,
        va="top",
        bbox={
            "boxstyle": "round,pad=0.4",
            "facecolor": "white",
            "alpha": 0.85,
            "edgecolor": "#bdc3c7",
        },
        fontsize=9,
    )


def _validate_rr(rr: RRSeries) -> None:
    """Raise TypeError or ValueError when rr is not a valid RRSeries."""
    if not isinstance(rr, RRSeries):
        raise TypeError(f"rr must be an RRSeries, got {type(rr).__name__}")
    if len(rr.intervals) < _MIN_INTERVALS_POINCARE:
        raise ValueError(
            f"rr must have at least {_MIN_INTERVALS_POINCARE} intervals, "
            f"got {len(rr.intervals)}"
        )


def _validate_features_list(features_list: list[HRVFeatures]) -> None:
    """Raise TypeError or ValueError when features_list is not valid."""
    if not isinstance(features_list, list):
        raise TypeError(
            f"features_list must be a list, got {type(features_list).__name__}"
        )
    if len(features_list) == 0:
        raise ValueError("features_list must contain at least one HRVFeatures.")
    for idx, item in enumerate(features_list):
        if not isinstance(item, HRVFeatures):
            raise TypeError(
                f"features_list[{idx}] must be an HRVFeatures, "
                f"got {type(item).__name__}"
            )


def _default_labels(features_list: list[HRVFeatures]) -> list[str]:
    """Return date strings from features or fallback 'Session N' labels."""
    return [
        str(f.date) if f.date else f"Session {i + 1}"
        for i, f in enumerate(features_list)
    ]
