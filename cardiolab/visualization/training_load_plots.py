"""Visualisation helpers for the ATL / CTL / TSB training load model."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from cardiolab.labels import lbl

if TYPE_CHECKING:
    from cardiolab.analytics.training_load import TrainingLoad

# ── Colour palette ────────────────────────────────────────────────────────────

_ATL_COLOR = "#e74c3c"  # red — acute fatigue
_CTL_COLOR = "#2980b9"  # blue — chronic fitness
_TSB_COLOR = "#8e44ad"  # purple — form
_TRIMP_COLOR = "#e67e22"  # orange — default TRIMP bar
_GRAY = "#95a5a6"
_DARK = "#2c3e50"

# ── TSB zone definitions ──────────────────────────────────────────────────────
# (low, high, background_colour, label) — from Coggan 2003 / Plews 2013.

_TSB_ZONES = [
    (25.0, 60.0, "#d6eaf8", "Fresh / detraining"),
    (5.0, 25.0, "#d5f5e3", "Optimal"),
    (-10.0, 5.0, "#fef9e7", "Neutral"),
    (-30.0, -10.0, "#fdebd0", "Accumulated fatigue"),
    (-60.0, -30.0, "#fadbd8", "Overload"),
]
_TSB_ZONE_KEYS = [
    "zone_tsb_fresh",
    "zone_tsb_optimal",
    "zone_tsb_neutral",
    "zone_tsb_fatigue",
    "zone_tsb_overload",
]

# ── Default sport-type colour map ─────────────────────────────────────────────

_DEFAULT_SPORT_COLORS: dict[str, str] = {
    "running": "#e74c3c",
    "cycling": "#2980b9",
    "swimming": "#1abc9c",
    "strength": "#8e44ad",
    "trail": "#d35400",
    "rowing": "#16a085",
}


# ── Validation ────────────────────────────────────────────────────────────────


def _validate_training_load(tl: TrainingLoad) -> None:
    """Raise if *tl* is empty or has inconsistent array lengths."""
    if not tl.dates:
        raise ValueError("TrainingLoad must contain at least one day of data.")
    n = len(tl.dates)
    for name, arr in (
        ("trimp", tl.trimp),
        ("atl", tl.atl),
        ("ctl", tl.ctl),
        ("tsb", tl.tsb),
    ):
        if len(arr) != n:
            raise ValueError(
                f"TrainingLoad.{name} length ({len(arr)}) differs from "
                f"dates length ({n})."
            )


def _x_ticks(dates: list[str], max_labels: int = 15) -> tuple[np.ndarray, list[str]]:
    """Return evenly spaced tick positions and labels for a date axis."""
    n = len(dates)
    if n <= max_labels:
        idx = np.arange(n)
    else:
        idx = np.linspace(0, n - 1, max_labels, dtype=int)
    return idx, [dates[i] for i in idx]


# ── Public plot functions ─────────────────────────────────────────────────────


def plot_atl_ctl_tsb(
    training_load: TrainingLoad,
    labels: dict[str, str] | None = None,
    title: str = "Training Load — ATL / CTL / TSB",
    figsize: tuple[float, float] = (13, 7),
) -> Figure:
    """Plot the ATL / CTL / TSB time series.

    Returns a :class:`~matplotlib.figure.Figure` with two vertically stacked
    panels sharing the same date x-axis:

    * **Top** — ATL (red) and CTL (blue) lines with a shaded area between
      them.  When ATL > CTL the area is red (accumulating fatigue); when
      CTL > ATL the area is blue (building fitness above current fatigue).
    * **Bottom** — TSB line (purple) with coloured zone backgrounds
      (see :data:`_TSB_ZONES`) and a zero-reference line.

    Args:
        training_load: A populated :class:`~cardiolab.analytics.training_load.TrainingLoad`
            instance.  Must contain at least one day of data.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Figure title.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        ValueError: If ``training_load`` is empty or has inconsistent arrays.

    """
    _validate_training_load(training_load)

    dates = training_load.dates
    x = np.arange(len(dates))
    atl = training_load.atl
    ctl = training_load.ctl
    tsb = training_load.tsb

    fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=figsize, sharex=True)

    # ── Top: ATL + CTL ────────────────────────────────────────────────────────
    ax_top.plot(
        x,
        atl,
        color=_ATL_COLOR,
        linewidth=1.8,
        label=lbl(labels, "atl", "ATL (fatigue τ=7)"),
    )
    ax_top.plot(
        x,
        ctl,
        color=_CTL_COLOR,
        linewidth=1.8,
        label=lbl(labels, "ctl", "CTL (fitness τ=42)"),
    )

    # Shaded area between ATL and CTL
    ax_top.fill_between(x, atl, ctl, where=(atl >= ctl), alpha=0.15, color=_ATL_COLOR)
    ax_top.fill_between(x, atl, ctl, where=(ctl > atl), alpha=0.15, color=_CTL_COLOR)

    ax_top.set_ylabel(lbl(labels, "atl", "Load (a.u.)"), fontsize=10)
    ax_top.legend(loc="upper left", fontsize=8)
    ax_top.grid(alpha=0.20, linestyle=":")

    # ── Bottom: TSB with zone bands ───────────────────────────────────────────
    tsb_min = min(float(np.min(tsb)), -35.0)
    tsb_max = max(float(np.max(tsb)), 30.0)

    for (low, high, color, label), zone_key in zip(
        _TSB_ZONES, _TSB_ZONE_KEYS, strict=True
    ):
        if high >= tsb_min and low <= tsb_max:
            ax_bot.axhspan(
                max(low, tsb_min - 5),
                min(high, tsb_max + 5),
                color=color,
                alpha=0.55,
                zorder=0,
                label=lbl(labels, zone_key, label),
            )

    ax_bot.axhline(0, color=_GRAY, linewidth=0.9, linestyle="--", alpha=0.8)
    ax_bot.plot(
        x,
        tsb,
        color=_TSB_COLOR,
        linewidth=1.8,
        zorder=4,
        label=lbl(labels, "tsb", "TSB (form)"),
    )
    ax_bot.set_ylabel(lbl(labels, "tsb", "TSB"), fontsize=10)
    ax_bot.legend(loc="upper left", fontsize=8, ncol=2)
    ax_bot.grid(alpha=0.15, linestyle=":", axis="y")

    tick_idx, tick_labels = _x_ticks(dates)
    ax_bot.set_xticks(tick_idx)
    ax_bot.set_xticklabels(tick_labels, rotation=40, ha="right", fontsize=8)

    fig.suptitle(title, fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_trimp_history(
    training_load: TrainingLoad,
    sessions: list[dict] | None = None,
    sport_colors: dict[str, str] | None = None,
    labels: dict[str, str] | None = None,
    title: str = "TRIMP History",
    figsize: tuple[float, float] = (13, 5),
) -> Figure:
    """Plot the daily TRIMP history as a bar chart.

    Bars are coloured by sport type when *sessions* is provided.  A 7-day
    rolling mean is drawn on top as a dashed line to reveal short-term trends.

    Args:
        training_load: A populated :class:`~cardiolab.analytics.training_load.TrainingLoad`.
        sessions: Optional list of session dicts from
            ``HRVRepository.load_training_sessions()`` — used to look up
            sport types for bar colouring.  If ``None``, all bars use the
            default TRIMP colour.
        sport_colors: Optional mapping of sport-type label → hex colour.
            Unknown sport types fall back to :data:`_TRIMP_COLOR`.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Figure title.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        ValueError: If ``training_load`` is empty or has inconsistent arrays.

    """
    _validate_training_load(training_load)

    dates = training_load.dates
    trimp = training_load.trimp
    x = np.arange(len(dates))
    colors_map = {**_DEFAULT_SPORT_COLORS, **(sport_colors or {})}

    fig, ax = plt.subplots(figsize=figsize)

    if sessions:
        # Group all activities by date — preserves multi-activity days
        sessions_by_date: dict[str, list[dict]] = defaultdict(list)
        for s in sessions:
            sessions_by_date[str(s["date"])[:10]].append(s)

        # Draw bars: stacked for multi-activity days, single otherwise
        for i, date in enumerate(dates):
            day = sessions_by_date.get(date, [])
            individual = [float(s.get("trimp") or 0.0) for s in day]
            has_data = any(t > 0 for t in individual)

            if has_data and len(day) > 1:
                # Stacked bars — each segment = one activity
                bottom = 0.0
                for s, t in zip(day, individual, strict=True):
                    if t <= 0:
                        continue
                    sport = s.get("sport_type") or ""
                    ax.bar(
                        i,
                        t,
                        bottom=bottom,
                        color=colors_map.get(sport, _TRIMP_COLOR),
                        width=0.8,
                        alpha=0.80,
                        edgecolor="white",
                        linewidth=0.4,
                        zorder=3,
                    )
                    bottom += t
            elif trimp[i] > 0:
                # Single activity (or trimp-only fallback)
                sport = day[0].get("sport_type") or "" if day else ""
                ax.bar(
                    i,
                    trimp[i],
                    color=colors_map.get(sport, _TRIMP_COLOR),
                    width=0.8,
                    alpha=0.80,
                    zorder=3,
                )

        # Legend: all unique sport types across all sessions
        seen: set[str] = set()
        patches = []
        for s in sessions:
            sport = s.get("sport_type") or ""
            if sport and sport not in seen:
                seen.add(sport)
                patches.append(
                    Patch(facecolor=colors_map.get(sport, _TRIMP_COLOR), label=sport)
                )
    else:
        ax.bar(x, trimp, color=_TRIMP_COLOR, width=0.8, alpha=0.80, zorder=3)
        patches = []

    # 7-day rolling mean (computed on aggregated daily TRIMP)
    if len(trimp) >= 7:
        rolling = np.convolve(trimp, np.ones(7) / 7, mode="valid")
        ax.plot(
            np.arange(6, len(trimp)),
            rolling,
            color=_DARK,
            linewidth=1.6,
            linestyle="--",
            label="7-day mean",
            zorder=4,
        )
        if patches:
            patches.append(
                Patch(facecolor=_DARK, label="7-day mean", linestyle="--", fill=False)
            )

    ax.set_ylabel(lbl(labels, "trimp", "TRIMP"), fontsize=10)
    ax.grid(alpha=0.20, linestyle=":", axis="y")

    tick_idx, tick_labels = _x_ticks(dates)
    ax.set_xticks(tick_idx)
    ax.set_xticklabels(tick_labels, rotation=40, ha="right", fontsize=8)

    if patches:
        ax.legend(handles=patches, loc="upper right", fontsize=8)
    elif len(trimp) >= 7:
        ax.legend(fontsize=8)

    ax.set_title(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_tsb_zones(
    training_load: TrainingLoad,
    labels: dict[str, str] | None = None,
    title: str = "Training Stress Balance — TSB Zones",
    figsize: tuple[float, float] = (13, 5),
) -> Figure:
    """Plot the TSB time series with coloured physiological zone bands.

    The coloured bands follow Coggan (2003) / Plews et al. (2013):

    * **Fresh / detraining** (blue)  > +25
    * **Optimal** (green)            +5 to +25
    * **Neutral** (yellow)           −10 to +5
    * **Accumulated fatigue** (orange) −30 to −10
    * **Overload** (red)             < −30

    Args:
        training_load: A populated :class:`~cardiolab.analytics.training_load.TrainingLoad`.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Figure title.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        ValueError: If ``training_load`` is empty or has inconsistent arrays.

    """
    _validate_training_load(training_load)

    dates = training_load.dates
    tsb = training_load.tsb
    x = np.arange(len(dates))

    tsb_min = min(float(np.min(tsb)), -35.0)
    tsb_max = max(float(np.max(tsb)), 30.0)
    pad = (tsb_max - tsb_min) * 0.08

    fig, ax = plt.subplots(figsize=figsize)

    legend_patches = []
    for (low, high, color, label), zone_key in zip(
        _TSB_ZONES, _TSB_ZONE_KEYS, strict=True
    ):
        clipped_low = max(low, tsb_min - pad)
        clipped_high = min(high, tsb_max + pad)
        if clipped_high > clipped_low:
            ax.axhspan(clipped_low, clipped_high, color=color, alpha=0.55, zorder=0)
            legend_patches.append(
                Patch(facecolor=color, alpha=0.55, label=lbl(labels, zone_key, label))
            )

    ax.axhline(0, color=_GRAY, linewidth=1.0, linestyle="--", alpha=0.8)
    ax.axhline(-10, color=_GRAY, linewidth=0.5, linestyle=":", alpha=0.6)
    ax.axhline(5, color=_GRAY, linewidth=0.5, linestyle=":", alpha=0.6)
    ax.axhline(25, color=_GRAY, linewidth=0.5, linestyle=":", alpha=0.6)
    ax.axhline(-30, color=_GRAY, linewidth=0.5, linestyle=":", alpha=0.6)

    ax.plot(x, tsb, color=_TSB_COLOR, linewidth=2.0, zorder=4)
    ax.fill_between(x, tsb, 0, where=(tsb >= 0), alpha=0.15, color=_CTL_COLOR)
    ax.fill_between(x, tsb, 0, where=(tsb < 0), alpha=0.15, color=_ATL_COLOR)

    ax.set_ylabel(lbl(labels, "tsb", "TSB (form)"), fontsize=10)
    ax.set_ylim(tsb_min - pad, tsb_max + pad)
    ax.grid(alpha=0.15, linestyle=":", axis="y")

    tick_idx, tick_labels = _x_ticks(dates)
    ax.set_xticks(tick_idx)
    ax.set_xticklabels(tick_labels, rotation=40, ha="right", fontsize=8)

    ax.legend(
        handles=legend_patches,
        loc="upper right",
        fontsize=8,
        framealpha=0.85,
    )

    ax.set_title(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig
