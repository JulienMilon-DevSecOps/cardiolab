"""Visualisation helpers for raw RR interval signals.

Five public functions cover the core signal-level views:

* :func:`plot_rr_tachogram`  — time series of RR intervals (ms) with optional HR axis.
* :func:`plot_rr_distribution` — histogram + KDE of the interval distribution.
* :func:`plot_rr_filtered`  — side-by-side raw vs. filtered overlay, removed beats in red.
* :func:`plot_rr_comparison` — stacked tachograms for multi-session comparison.
* :func:`plot_rr_summary`   — 2×2 compound figure combining all views plus a stats panel.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from scipy.stats import gaussian_kde

from cardiolab.signals.rr import RRSeries

# ── Colour palette ───────────────────────────────────────────────────────────

_BLUE = "#2980b9"
_GREEN = "#27ae60"
_RED = "#e74c3c"
_ORANGE = "#f39c12"
_GRAY = "#95a5a6"
_DARK = "#2c3e50"

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


# ── Internal helpers ─────────────────────────────────────────────────────────


def _time_axis(rr: RRSeries) -> np.ndarray:
    """Return the cumulative time axis in seconds from an RRSeries."""
    return np.cumsum(rr.intervals) / 1000.0


def _basic_stats(rr: RRSeries) -> dict:
    """Compute lightweight HRV stats without importing protocols."""
    intervals = rr.intervals
    diffs = np.diff(intervals)
    rmssd = float(np.sqrt(np.mean(diffs**2)))
    sdnn = float(np.std(intervals, ddof=1))
    pnn50 = (
        float(100.0 * np.sum(np.abs(diffs) > 50) / len(diffs))
        if len(diffs) > 0
        else 0.0
    )
    return {
        "n": len(intervals),
        "duration_s": rr.duration,
        "mean_rr": float(np.mean(intervals)),
        "mean_hr": rr.mean_hr,
        "min_hr": rr.min_hr,
        "max_hr": rr.max_hr,
        "rmssd": rmssd,
        "sdnn": sdnn,
        "pnn50": pnn50,
    }


def _rr_to_hr(rr_ms: np.ndarray) -> np.ndarray:
    return 60_000.0 / np.maximum(rr_ms, 1.0)


def _hr_to_rr(hr_bpm: np.ndarray) -> np.ndarray:
    return 60_000.0 / np.maximum(hr_bpm, 1.0)


def _add_hr_axis(ax: Axes) -> None:
    """Add a secondary y-axis displaying heart rate (bpm)."""
    ax_hr = ax.secondary_yaxis("right", functions=(_rr_to_hr, _hr_to_rr))
    ax_hr.set_ylabel("FC (bpm)", color=_GRAY, fontsize=9)
    ax_hr.tick_params(axis="y", colors=_GRAY, labelsize=8)
    hr_ticks = [40, 50, 60, 70, 80, 90, 100, 120, 150, 200]
    ax_hr.yaxis.set_major_locator(mticker.FixedLocator(hr_ticks))


# ── Public functions ─────────────────────────────────────────────────────────


def plot_rr_tachogram(
    rr: RRSeries,
    title: str = "Tachogramme RR",
    color: str = _BLUE,
    show_mean: bool = True,
    show_band: bool = True,
    show_hr_axis: bool = True,
    figsize: tuple[float, float] = (14, 4),
) -> Figure:
    """Plot a single-session RR tachogram (time series of intervals).

    The left y-axis shows RR intervals in milliseconds.  An optional right
    y-axis converts the scale to heart rate (bpm) via a non-linear transform
    (HR = 60 000 / RR).

    Args:
        rr: RR interval series to plot.
        title: Figure title.
        color: Line and scatter colour.
        show_mean: Draw a horizontal dashed line at the mean RR value.
        show_band: Shade the ±1 standard-deviation band around the mean.
        show_hr_axis: Add a secondary y-axis in bpm.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure` object (save with
        ``fig.savefig(...)``).

    """
    t = _time_axis(rr)
    intervals = rr.intervals
    mean_rr = float(np.mean(intervals))
    std_rr = float(np.std(intervals, ddof=1))

    fig, ax = plt.subplots(figsize=figsize)

    ax.plot(t, intervals, color=color, linewidth=0.9, alpha=0.85, zorder=2)
    ax.scatter(t, intervals, color=color, s=6, alpha=0.7, zorder=3)

    if show_band:
        ax.axhspan(
            mean_rr - std_rr,
            mean_rr + std_rr,
            alpha=0.10,
            color=color,
            label=f"±1 σ  ({std_rr:.0f} ms)",
        )

    if show_mean:
        ax.axhline(
            mean_rr,
            color=_DARK,
            linewidth=1.3,
            linestyle="--",
            label=f"Moyenne  {mean_rr:.0f} ms  ({60_000.0 / mean_rr:.0f} bpm)",
        )

    ax.set_xlabel("Temps (s)", fontsize=10)
    ax.set_ylabel("Intervalle RR (ms)", fontsize=10)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_xlim(t[0], t[-1])
    ax.grid(axis="y", alpha=0.25, linestyle=":")

    if show_hr_axis:
        _add_hr_axis(ax)

    plt.tight_layout()
    return fig


def plot_rr_distribution(
    rr: RRSeries,
    title: str = "Distribution des intervalles RR",
    color: str = _BLUE,
    bins: int = 40,
    show_kde: bool = True,
    show_stats: bool = True,
    figsize: tuple[float, float] = (8, 5),
) -> Figure:
    """Plot a histogram of RR intervals with an optional KDE overlay.

    A Gaussian kernel density estimate (via :func:`scipy.stats.gaussian_kde`)
    is drawn on a secondary y-axis so its scale is independent of the bin
    count.  Vertical markers indicate the mean and ±1 standard deviation.

    Args:
        rr: RR interval series.
        title: Figure title.
        color: Fill and line colour.
        bins: Number of histogram bins.
        show_kde: Overlay a KDE curve.
        show_stats: Annotate mean, std and basic counts.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    """
    intervals = rr.intervals
    mean_rr = float(np.mean(intervals))
    std_rr = float(np.std(intervals, ddof=1))

    fig, ax = plt.subplots(figsize=figsize)

    ax.hist(
        intervals,
        bins=bins,
        color=color,
        alpha=0.55,
        edgecolor="white",
        linewidth=0.5,
        label="Fréquence",
    )
    ax.set_xlabel("Intervalle RR (ms)", fontsize=10)
    ax.set_ylabel("Nombre d'intervalles", fontsize=10)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)

    # Vertical markers
    ax.axvline(
        mean_rr,
        color=_DARK,
        linewidth=1.5,
        linestyle="--",
        label=f"Moyenne {mean_rr:.0f} ms",
    )
    ax.axvline(mean_rr - std_rr, color=_GRAY, linewidth=1.0, linestyle=":", alpha=0.8)
    ax.axvline(
        mean_rr + std_rr,
        color=_GRAY,
        linewidth=1.0,
        linestyle=":",
        alpha=0.8,
        label=f"±1 σ ({std_rr:.0f} ms)",
    )

    # KDE on secondary axis
    if show_kde and len(intervals) >= 5:
        ax2 = ax.twinx()
        x_kde = np.linspace(intervals.min() - 50, intervals.max() + 50, 400)
        kde = gaussian_kde(intervals, bw_method="scott")
        ax2.plot(x_kde, kde(x_kde), color=_DARK, linewidth=2.0, label="Densité (KDE)")
        ax2.set_ylabel("Densité de probabilité", fontsize=9, color=_DARK)
        ax2.tick_params(axis="y", colors=_DARK, labelsize=8)
        ax2.set_ylim(bottom=0)
        ax2.legend(loc="upper left", fontsize=8)

    # Stats annotation
    if show_stats:
        hr_mean = 60_000.0 / mean_rr
        stats_text = (
            f"n = {len(intervals)}\n"
            f"Durée = {rr.duration:.0f} s\n"
            f"RR moy. = {mean_rr:.0f} ms\n"
            f"FC moy. = {hr_mean:.1f} bpm\n"
            f"σ = {std_rr:.0f} ms\n"
            f"Min = {intervals.min():.0f} ms\n"
            f"Max = {intervals.max():.0f} ms"
        )
        ax.text(
            0.97,
            0.97,
            stats_text,
            transform=ax.transAxes,
            fontsize=8,
            verticalalignment="top",
            horizontalalignment="right",
            bbox={
                "boxstyle": "round,pad=0.4",
                "facecolor": "white",
                "alpha": 0.8,
                "edgecolor": _GRAY,
            },
        )

    ax.legend(loc="upper center", fontsize=8)
    ax.grid(axis="y", alpha=0.20, linestyle=":")

    plt.tight_layout()
    return fig


def plot_rr_filtered(
    rr: RRSeries,
    rr_filtered: RRSeries | None = None,
    title: str = "Intervalles RR — brut vs filtré",
    low: float = 300.0,
    high: float = 2000.0,
    figsize: tuple[float, float] = (14, 5),
) -> Figure:
    """Overlay raw and filtered RR series, highlighting removed beats.

    Artefactual beats (outside physiological bounds or statistical outliers)
    are drawn in red on the raw signal so the extent of artefact contamination
    is immediately visible.

    Args:
        rr: Raw RR series.
        rr_filtered: Pre-filtered series.  If ``None``, threshold filtering
            between ``low`` and ``high`` ms is applied automatically.
        title: Figure title.
        low: Lower physiological bound (ms) used when ``rr_filtered`` is None.
        high: Upper physiological bound (ms) used when ``rr_filtered`` is None.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    """
    intervals_raw = rr.intervals
    t_raw = _time_axis(rr)

    # Compute the outlier mask from the raw series
    mask_ok = (intervals_raw >= low) & (intervals_raw <= high)
    n_removed = int(np.sum(~mask_ok))

    # Auto-filter if not provided
    if rr_filtered is None:
        rr_filtered = rr.remove_outliers(low=low, high=high, method="threshold")

    intervals_filt = rr_filtered.intervals
    t_filt = _time_axis(rr_filtered)

    fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=figsize, sharex=False)

    # ── Top panel: raw signal + highlighted artefacts ────────────────────────
    ax_top.plot(
        t_raw, intervals_raw, color=_GRAY, linewidth=0.8, alpha=0.7, label="Brut"
    )
    ax_top.scatter(
        t_raw[mask_ok],
        intervals_raw[mask_ok],
        color=_BLUE,
        s=5,
        alpha=0.6,
        zorder=3,
        label="Valide",
    )
    if n_removed > 0:
        ax_top.scatter(
            t_raw[~mask_ok],
            intervals_raw[~mask_ok],
            color=_RED,
            s=30,
            marker="x",
            linewidths=1.5,
            zorder=4,
            label=f"Artefacts supprimés ({n_removed})",
        )
    ax_top.axhline(low, color=_RED, linewidth=0.8, linestyle=":", alpha=0.6)
    ax_top.axhline(high, color=_RED, linewidth=0.8, linestyle=":", alpha=0.6)
    ax_top.set_ylabel("RR (ms)", fontsize=9)
    ax_top.set_title(f"{title}  —  Signal brut", fontsize=10, fontweight="bold")
    ax_top.legend(loc="upper right", fontsize=8)
    ax_top.grid(axis="y", alpha=0.20, linestyle=":")
    _add_hr_axis(ax_top)

    # ── Bottom panel: filtered signal ────────────────────────────────────────
    ax_bot.plot(t_filt, intervals_filt, color=_GREEN, linewidth=0.9, alpha=0.9)
    ax_bot.scatter(t_filt, intervals_filt, color=_GREEN, s=5, alpha=0.7, zorder=3)
    mean_filt = float(np.mean(intervals_filt))
    ax_bot.axhline(
        mean_filt,
        color=_DARK,
        linewidth=1.2,
        linestyle="--",
        label=f"Moyenne {mean_filt:.0f} ms ({60_000.0 / mean_filt:.0f} bpm)",
    )
    ax_bot.set_xlabel("Temps (s)", fontsize=9)
    ax_bot.set_ylabel("RR (ms)", fontsize=9)
    ax_bot.set_title(
        f"Signal filtré  ({len(intervals_filt)} intervalles, −{n_removed} artefacts)",
        fontsize=10,
        fontweight="bold",
    )
    ax_bot.legend(loc="upper right", fontsize=8)
    ax_bot.grid(axis="y", alpha=0.20, linestyle=":")
    _add_hr_axis(ax_bot)

    plt.suptitle(title, fontsize=12, fontweight="bold", y=1.01)
    plt.tight_layout()
    return fig


def plot_rr_comparison(
    rr_list: list[RRSeries],
    labels: list[str] | None = None,
    title: str = "Comparaison multi-sessions — Tachogramme RR",
    normalize_time: bool = False,
    figsize: tuple[float, float] = (14, 3.5),
) -> Figure:
    """Plot stacked tachograms for multiple sessions.

    Each session is drawn in its own subplot sharing the y-axis scale, so
    amplitude differences between sessions are immediately comparable.

    Args:
        rr_list: List of RR series, one per session.
        labels: Display labels for each session.  Falls back to
            ``"Session N"`` if not provided.
        title: Overall figure title.
        normalize_time: If ``True``, rescale each session's time axis to
            [0, 100 %] so sessions of different lengths align horizontally.
        figsize: Width × height *per panel* — total height is
            ``figsize[1] × n_sessions``.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    """
    n = len(rr_list)
    if n == 0:
        raise ValueError("rr_list must contain at least one RRSeries.")

    if labels is None:
        labels = [f"Session {i + 1}" for i in range(n)]

    # Shared y limits across all panels
    all_intervals = np.concatenate([rr.intervals for rr in rr_list])
    y_min = float(np.percentile(all_intervals, 1)) - 20
    y_max = float(np.percentile(all_intervals, 99)) + 20

    total_height = figsize[1] * n
    fig, axes = plt.subplots(n, 1, figsize=(figsize[0], total_height), squeeze=False)

    for i, (rr, label, color) in enumerate(
        zip(rr_list, labels, _PALETTE * 4, strict=False)
    ):
        ax = axes[i, 0]
        t = _time_axis(rr)
        if normalize_time and t[-1] > 0:
            t = t / t[-1] * 100.0
            xlabel = "Temps normalisé (%)"
        else:
            xlabel = "Temps (s)"

        intervals = rr.intervals
        mean_rr = float(np.mean(intervals))

        ax.plot(t, intervals, color=color, linewidth=0.9, alpha=0.85)
        ax.scatter(t, intervals, color=color, s=5, alpha=0.6, zorder=3)
        ax.axhline(
            mean_rr,
            color=_DARK,
            linewidth=1.1,
            linestyle="--",
            alpha=0.7,
            label=f"Moy. {mean_rr:.0f} ms ({60_000.0 / mean_rr:.0f} bpm)",
        )

        ax.set_ylim(y_min, y_max)
        ax.set_ylabel("RR (ms)", fontsize=9)
        ax.set_title(label, fontsize=10, fontweight="bold", loc="left", pad=4)
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(axis="y", alpha=0.20, linestyle=":")
        _add_hr_axis(ax)

        if i == n - 1:
            ax.set_xlabel(xlabel, fontsize=9)

    plt.suptitle(title, fontsize=12, fontweight="bold", y=1.01)
    plt.tight_layout()
    return fig


def plot_rr_summary(
    rr: RRSeries,
    title: str = "",
    figsize: tuple[float, float] = (14, 9),
) -> Figure:
    """2×2 compound figure combining tachogram, distribution, filtered view and stats.

    Layout::

        ┌───────────────────┬───────────────────┐
        │  Tachogramme RR   │   Distribution    │
        │  (signal brut)    │  Histogramme+KDE  │
        ├───────────────────┼───────────────────┤
        │  Brut vs filtré   │  Statistiques HRV │
        │  (artefacts rouges│  (tableau texte)  │
        └───────────────────┴───────────────────┘

    Args:
        rr: RR interval series.
        title: Overall figure title (displayed at the top).
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    """
    intervals = rr.intervals
    t = _time_axis(rr)
    stats = _basic_stats(rr)
    mask_ok = (intervals >= 300.0) & (intervals <= 2000.0)
    n_removed = int(np.sum(~mask_ok))

    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(2, 2, hspace=0.38, wspace=0.35)

    # ── Panel A: Tachogramme ─────────────────────────────────────────────────
    ax_a = fig.add_subplot(gs[0, 0])
    mean_rr = float(np.mean(intervals))
    std_rr = float(np.std(intervals, ddof=1))

    ax_a.plot(t, intervals, color=_BLUE, linewidth=0.8, alpha=0.85)
    ax_a.scatter(t, intervals, color=_BLUE, s=4, alpha=0.6, zorder=3)
    ax_a.axhline(mean_rr, color=_DARK, linewidth=1.2, linestyle="--", alpha=0.8)
    ax_a.axhspan(mean_rr - std_rr, mean_rr + std_rr, alpha=0.09, color=_BLUE)
    ax_a.set_xlabel("Temps (s)", fontsize=9)
    ax_a.set_ylabel("RR (ms)", fontsize=9)
    ax_a.set_title("A — Tachogramme", fontsize=10, fontweight="bold")
    ax_a.grid(axis="y", alpha=0.20, linestyle=":")
    _add_hr_axis(ax_a)

    # ── Panel B: Distribution ────────────────────────────────────────────────
    ax_b = fig.add_subplot(gs[0, 1])
    ax_b.hist(
        intervals, bins=35, color=_BLUE, alpha=0.55, edgecolor="white", linewidth=0.4
    )
    ax_b.axvline(
        mean_rr, color=_DARK, linewidth=1.4, linestyle="--", label=f"{mean_rr:.0f} ms"
    )
    ax_b.axvline(mean_rr - std_rr, color=_GRAY, linewidth=0.9, linestyle=":", alpha=0.8)
    ax_b.axvline(mean_rr + std_rr, color=_GRAY, linewidth=0.9, linestyle=":", alpha=0.8)
    if len(intervals) >= 5:
        ax_b2 = ax_b.twinx()
        x_kde = np.linspace(intervals.min() - 30, intervals.max() + 30, 300)
        kde = gaussian_kde(intervals, bw_method="scott")
        ax_b2.plot(x_kde, kde(x_kde), color=_DARK, linewidth=1.8)
        ax_b2.set_ylabel("Densité", fontsize=8, color=_DARK)
        ax_b2.tick_params(axis="y", colors=_DARK, labelsize=7)
        ax_b2.set_ylim(bottom=0)
    ax_b.set_xlabel("RR (ms)", fontsize=9)
    ax_b.set_ylabel("Fréquence", fontsize=9)
    ax_b.set_title("B — Distribution + KDE", fontsize=10, fontweight="bold")
    ax_b.legend(fontsize=8)
    ax_b.grid(axis="y", alpha=0.20, linestyle=":")

    # ── Panel C: Filtré vs brut ──────────────────────────────────────────────
    ax_c = fig.add_subplot(gs[1, 0])
    ax_c.plot(t, intervals, color=_GRAY, linewidth=0.7, alpha=0.5, label="Brut")
    ax_c.scatter(
        t[mask_ok],
        intervals[mask_ok],
        color=_GREEN,
        s=5,
        alpha=0.7,
        zorder=3,
        label="Valide",
    )
    if n_removed > 0:
        ax_c.scatter(
            t[~mask_ok],
            intervals[~mask_ok],
            color=_RED,
            s=30,
            marker="x",
            linewidths=1.5,
            zorder=4,
            label=f"Artefacts ({n_removed})",
        )
    ax_c.axhline(300.0, color=_RED, linewidth=0.7, linestyle=":", alpha=0.5)
    ax_c.axhline(2000.0, color=_RED, linewidth=0.7, linestyle=":", alpha=0.5)
    ax_c.set_xlabel("Temps (s)", fontsize=9)
    ax_c.set_ylabel("RR (ms)", fontsize=9)
    ax_c.set_title("C — Brut vs filtré", fontsize=10, fontweight="bold")
    ax_c.legend(loc="upper right", fontsize=8)
    ax_c.grid(axis="y", alpha=0.20, linestyle=":")
    _add_hr_axis(ax_c)

    # ── Panel D: Statistiques HRV ────────────────────────────────────────────
    ax_d = fig.add_subplot(gs[1, 1])
    ax_d.axis("off")

    rows = [
        ("Indicateur", "Valeur", "Référence repos"),
        ("n intervalles", f"{stats['n']}", ""),
        ("Durée", f"{stats['duration_s']:.0f} s", "≥ 300 s recommandé"),
        ("RR moyen", f"{stats['mean_rr']:.0f} ms", ""),
        ("FC moyenne", f"{stats['mean_hr']:.1f} bpm", "50 – 70 bpm"),
        ("FC min", f"{stats['min_hr']:.1f} bpm", ""),
        ("FC max", f"{stats['max_hr']:.1f} bpm", ""),
        ("RMSSD", f"{stats['rmssd']:.1f} ms", "> 20 ms"),
        ("SDNN", f"{stats['sdnn']:.1f} ms", "> 50 ms"),
        ("pNN50", f"{stats['pnn50']:.1f} %", "> 3 %"),
        ("Artefacts", f"{n_removed}", "0 idéal"),
    ]

    col_x = [0.02, 0.45, 0.72]
    row_h = 0.077
    y_start = 0.96

    for r_idx, row in enumerate(rows):
        y = y_start - r_idx * row_h
        is_header = r_idx == 0
        weight = "bold" if is_header else "normal"
        bg_color = (
            "#ecf0f1" if is_header else ("white" if r_idx % 2 == 0 else "#f8f9fa")
        )
        ax_d.add_patch(
            plt.Rectangle(
                (0.0, y - row_h + 0.005),
                1.0,
                row_h - 0.005,
                transform=ax_d.transAxes,
                facecolor=bg_color,
                linewidth=0,
            )
        )
        for _c_idx, (text, x) in enumerate(zip(row, col_x, strict=False)):
            ha = "left"
            color = _DARK if is_header else "black"
            ax_d.text(
                x,
                y - 0.01,
                text,
                transform=ax_d.transAxes,
                fontsize=8.5,
                fontweight=weight,
                color=color,
                ha=ha,
                va="top",
            )

    ax_d.set_title("D — Statistiques HRV", fontsize=10, fontweight="bold")

    # Overall title
    header = title if title else "Analyse des intervalles RR"
    fig.suptitle(header, fontsize=13, fontweight="bold", y=1.005)

    return fig
