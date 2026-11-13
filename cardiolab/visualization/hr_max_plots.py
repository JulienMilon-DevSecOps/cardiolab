"""HRmax charts — one field test, and HRmax over time per sport."""

from __future__ import annotations

from datetime import date

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from cardiolab.analytics.hr_max import (
    clean_heart_rate,
    heart_rate_1hz,
    held_heart_rate,
)
from cardiolab.labels import lbl
from cardiolab.sports import get_sport
from cardiolab.visualization._common import DARK, text

_RAW = "#bdc3c7"
_HELD = "#2c3e50"
_PEAK = "#c0392b"
_EFFORT = "#e67e22"
_PROFILE = "#7f8c8d"


def sport_color(code: str) -> str:
    """Chart colour of a sport (reference list)."""
    return get_sport(code).color


def plot_hr_max_test(
    time_sec,
    heart_rate,
    result,
    *,
    profile_hr_max: float | None = None,
    labels: dict[str, str] | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot an HRmax field test: heart rate, held heart rate, the peak retained.

    * light grey — heart rate, second by second;
    * dark line — heart rate held 5 s (what the HRmax is read on);
    * orange band — final effort (held ≥ 90 % of the peak before it);
    * red dot — the HRmax retained, with its value;
    * grey cross — an isolated spike set aside (sensor artefact);
    * grey dotted line — the HRmax of the profile, when given.

    Args:
        time_sec: Time of each sample (s).
        heart_rate: Heart rate (bpm).
        result: :class:`~cardiolab.protocols.hr_max_test.HRMaxTestResult`.
        profile_hr_max: HRmax of the profile, drawn for comparison.
        labels: Translation dict (``LABELS_EN`` / ``LABELS_FR``).
        title: Figure title. Defaults to the ``hr_max_test_title`` label.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    """
    t, hr = clean_heart_rate(time_sec, heart_rate)
    grid, hr_1hz = heart_rate_1hz(time_sec, heart_rate)
    held = held_heart_rate(grid, hr_1hz)
    minutes = t / 60.0
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(minutes, hr, color=_RAW, linewidth=0.8, label=text(labels, "hr_max_raw"))
    ax.plot(
        grid / 60.0, held, color=_HELD, linewidth=1.6, label=text(labels, "hr_max_held")
    )

    peak_min = result.peak_time_sec / 60.0
    if result.final_effort_sec > 0:
        ax.axvspan(
            peak_min - result.final_effort_sec / 60.0,
            peak_min,
            color=_EFFORT,
            alpha=0.15,
            linewidth=0,
            label=text(labels, "hr_max_final_effort"),
        )
    ax.scatter(
        [peak_min],
        [result.hr_max],
        s=70,
        color=_PEAK,
        zorder=5,
        label=text(labels, "hr_max_retained").format(hr=f"{result.hr_max:.0f}"),
    )
    ax.annotate(
        f"{result.hr_max:.0f} bpm",
        (peak_min, result.hr_max),
        textcoords="offset points",
        xytext=(8, 8),
        color=_PEAK,
        fontweight="bold",
    )
    if result.raw_max - result.hr_max > 5.0:
        raw = np.asarray(heart_rate, dtype=float)
        i = int(np.nanargmax(np.where(raw <= 230.0, raw, np.nan)))
        ax.scatter(
            [np.asarray(time_sec, dtype=float)[i] / 60.0],
            [result.raw_max],
            marker="x",
            s=50,
            color=_PROFILE,
            zorder=5,
            label=text(labels, "hr_max_spike"),
        )
    if profile_hr_max:
        ax.axhline(
            profile_hr_max,
            color=_PROFILE,
            linestyle=":",
            linewidth=1.2,
            label=text(labels, "hr_max_profile").format(hr=f"{profile_hr_max:.0f}"),
        )
    ax.set_xlabel(text(labels, "time_min"))
    ax.set_ylabel(text(labels, "hr_bpm"))
    ax.grid(alpha=0.2, linestyle=":")
    ax.legend(loc="upper left", fontsize=8)
    fig.suptitle(
        title or text(labels, "hr_max_test_title"),
        fontsize=12,
        fontweight="bold",
        color=DARK,
    )
    plt.tight_layout()
    return fig


def plot_hr_max_history(
    tests,
    *,
    observed=None,
    profile_hr_max: float | None = None,
    labels: dict[str, str] | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot HRmax over time, one colour per sport.

    * filled dots — field tests (``doubtful`` ones hollow, ``invalid`` left
      out), labelled with their value;
    * hollow squares — HRmax observed in sessions;
    * grey dotted line — HRmax of the profile.

    Args:
        tests: :class:`~cardiolab.protocols.hr_max_test.HRMaxTestResult` list
            (with dates).
        observed: Optional ``{sport: ObservedHRMax}`` from
            :func:`~cardiolab.analytics.hr_max.observed_hr_max` (with dates).
        profile_hr_max: HRmax of the profile.
        labels: Translation dict.
        title: Figure title. Defaults to the ``hr_max_history_title`` label.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        ValueError: If there is nothing dated to plot.

    """
    points = [r for r in tests if r.date and r.status != "invalid"]
    seen = [o for o in (observed or {}).values() if o.date]
    if not points and not seen:
        raise ValueError("No dated HRmax to plot.")
    fig, ax = plt.subplots(figsize=figsize)
    shown: set[str] = set()
    for r in points:
        color = sport_color(r.sport)
        label = None
        if r.sport not in shown:
            label = lbl(labels, f"sport_{r.sport}", get_sport(r.sport).label_en)
            shown.add(r.sport)
        day = date.fromisoformat(str(r.date)[:10])
        ax.scatter(
            [day],
            [r.hr_max],
            s=70,
            color=color if r.status == "valid" else "white",
            edgecolors=color,
            linewidths=1.5,
            zorder=4,
            label=label,
        )
        ax.annotate(
            f"{r.hr_max:.0f}",
            (day, r.hr_max),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=8,
        )
    for k, o in enumerate(seen):
        ax.scatter(
            [date.fromisoformat(str(o.date)[:10])],
            [o.hr_max],
            marker="s",
            s=50,
            facecolors="none",
            edgecolors=sport_color(o.sport),
            zorder=3,
            label=text(labels, "hr_max_observed") if k == 0 else None,
        )
    if profile_hr_max:
        ax.axhline(
            profile_hr_max,
            color=_PROFILE,
            linestyle=":",
            linewidth=1.2,
            label=text(labels, "hr_max_profile").format(hr=f"{profile_hr_max:.0f}"),
        )
    ax.set_ylabel(text(labels, "hr_bpm"))
    ax.grid(alpha=0.2, linestyle=":")
    ax.legend(loc="lower left", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    fig.autofmt_xdate()
    fig.suptitle(
        title or text(labels, "hr_max_history_title"),
        fontsize=12,
        fontweight="bold",
        color=DARK,
    )
    plt.tight_layout()
    return fig
