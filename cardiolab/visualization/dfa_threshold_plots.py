"""Visualisation of the DFA α1 thresholds and of the training zones.

* :func:`plot_dfa_alpha1` — α1 and heart rate over the test, with the 0.75 / 0.5
  lines and the moment of each threshold.
* :func:`plot_alpha1_vs_hr` — α1 against heart rate: the decline the
  thresholds are read from.
* :func:`plot_training_zones` — the heart rate zones as a coloured scale.
* :func:`plot_threshold_evolution` — HRVT1 / HRVT2 test after test.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from cardiolab.analytics.zones import HeartRateZone
from cardiolab.labels import lbl
from cardiolab.protocols.dfa_thresholds import DFAThresholdsResult
from cardiolab.visualization._common import GRAY

_VT1_COLOR = "#e67e22"
_VT2_COLOR = "#c0392b"
_ALPHA_COLOR = "#2c3e50"
_HR_COLOR = "#2980b9"

_ZONE_COLORS: dict[int, str] = {
    1: "#aed6f1",
    2: "#82e0aa",
    3: "#f9e79f",
    4: "#f5b041",
    5: "#ec7063",
}
_THREE_ZONE_COLORS: dict[int, str] = {1: "#82e0aa", 2: "#f9e79f", 3: "#ec7063"}


def plot_dfa_alpha1(
    result: DFAThresholdsResult,
    labels: dict[str, str] | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot α1 and heart rate over the test with both thresholds.

    Args:
        result: Output of :func:`~cardiolab.protocols.dfa_thresholds.dfa_thresholds`.
        labels: Translation dict (``LABELS_EN`` / ``LABELS_FR``), or ``None``.
        title: Figure title; a default one is used when ``None``.
        figsize: Figure size in inches.

    Returns:
        Matplotlib figure: α1 on the left axis, heart rate on the right axis,
        horizontal lines at 0.75 and 0.5, a vertical line at each detected
        threshold.

    Raises:
        TypeError: If ``result`` is not a ``DFAThresholdsResult``.

    """
    _check(result)
    t_min = result.times / 60.0
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(t_min, result.alpha1, color=_ALPHA_COLOR, lw=1.6, label="DFA α1")
    for est, color in ((result.vt1, _VT1_COLOR), (result.vt2, _VT2_COLOR)):
        ax.axhline(est.alpha, color=color, ls="--", lw=1)
        if est.detected:
            ax.axvline(est.time_sec / 60.0, color=color, ls=":", lw=1.2)
            ax.annotate(
                _threshold_text(est, result.intensity_unit, labels),
                xy=(est.time_sec / 60.0, est.alpha),
                xytext=(6, 8),
                textcoords="offset points",
                color=color,
                fontsize=9,
                fontweight="bold",
            )
    ax.set_xlabel(lbl(labels, "time_min", "Time (min)"))
    ax.set_ylabel("DFA α1")
    ax.set_ylim(0, max(1.6, float(np.nanmax(result.alpha1)) + 0.1))
    ax.grid(alpha=0.3)

    ax_hr = ax.twinx()
    ax_hr.plot(t_min, result.hr, color=_HR_COLOR, lw=1, alpha=0.7)
    ax_hr.set_ylabel(lbl(labels, "mean_hr", "HR (bpm)"), color=_HR_COLOR)
    ax_hr.tick_params(axis="y", colors=_HR_COLOR)

    ax.set_title(
        title or lbl(labels, "dfa_thresholds_title", "DFA α1 thresholds"),
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    return fig


def plot_alpha1_vs_hr(
    result: DFAThresholdsResult,
    labels: dict[str, str] | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (7, 5),
) -> Figure:
    """Plot α1 against heart rate up to the peak heart rate.

    Each point is one 2-minute window. The thresholds are the heart rates
    where the decline crosses 0.75 and 0.5.

    Args:
        result: Output of ``dfa_thresholds``.
        labels: Translation dict, or ``None``.
        title: Figure title; a default one is used when ``None``.
        figsize: Figure size in inches.

    Returns:
        Matplotlib figure.

    Raises:
        TypeError: If ``result`` is not a ``DFAThresholdsResult``.

    """
    _check(result)
    peak = int(np.nanargmax(np.where(np.isfinite(result.hr), result.hr, -np.inf)))
    hr = result.hr[: peak + 1]
    alpha = result.alpha1[: peak + 1]
    fig, ax = plt.subplots(figsize=figsize)
    ax.scatter(hr, alpha, s=10, color=_ALPHA_COLOR, alpha=0.5)
    for est, color in ((result.vt1, _VT1_COLOR), (result.vt2, _VT2_COLOR)):
        ax.axhline(est.alpha, color=color, ls="--", lw=1)
        if est.detected:
            ax.axvline(est.hr, color=color, ls=":", lw=1.2)
            ax.plot(est.hr, est.alpha, "o", color=color, ms=9)
            ax.annotate(
                f"{est.hr:.0f} bpm",
                xy=(est.hr, est.alpha),
                xytext=(8, 8),
                textcoords="offset points",
                color=color,
                fontweight="bold",
            )
    ax.set_xlabel(lbl(labels, "mean_hr", "HR (bpm)"))
    ax.set_ylabel("DFA α1")
    ax.grid(alpha=0.3)
    ax.set_title(
        title or lbl(labels, "alpha1_vs_hr_title", "DFA α1 against heart rate"),
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    return fig


def plot_training_zones(
    zones: list[HeartRateZone],
    labels: dict[str, str] | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (10, 2.6),
) -> Figure:
    """Draw the heart rate zones as one coloured horizontal scale.

    Args:
        zones: Output of :func:`~cardiolab.analytics.zones.five_zones` or
            :func:`~cardiolab.analytics.zones.three_zones` (or
            ``DFAThresholdsResult.zones()``).
        labels: Translation dict, or ``None`` (zone names from the
            ``zone_hr_<name>`` keys).
        title: Figure title; a default one is used when ``None``.
        figsize: Figure size in inches.

    Returns:
        Matplotlib figure.

    Raises:
        ValueError: If ``zones`` is empty.

    """
    if not zones:
        raise ValueError("zones must not be empty")
    colors = _ZONE_COLORS if len(zones) == 5 else _THREE_ZONE_COLORS
    lo = zones[0].hr_low if zones[0].hr_low > 0 else zones[0].hr_high * 0.7
    fig, ax = plt.subplots(figsize=figsize)
    for z in zones:
        start = max(z.hr_low, lo)
        ax.barh(0, z.hr_high - start, left=start, color=colors.get(z.zone, GRAY))
        ax.text(
            (start + z.hr_high) / 2,
            0,
            f"Z{z.zone}\n{lbl(labels, 'zone_hr_' + z.name, z.name)}",
            ha="center",
            va="center",
            fontsize=9,
        )
        ax.text(z.hr_high, -0.55, f"{z.hr_high:.0f}", ha="center", fontsize=8)
    ax.text(lo, -0.55, f"{lo:.0f}", ha="center", fontsize=8)
    ax.set_xlim(lo, zones[-1].hr_high)
    ax.set_ylim(-0.7, 0.5)
    ax.set_yticks([])
    ax.set_xlabel(lbl(labels, "mean_hr", "HR (bpm)"))
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.set_title(
        title or lbl(labels, "training_zones_title", "Training zones"),
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    return fig


def plot_threshold_evolution(
    results: list[DFAThresholdsResult],
    session_labels: list[str] | None = None,
    labels: dict[str, str] | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (10, 5),
) -> Figure:
    """Plot HRVT1 and HRVT2 test after test (and their intensity, when known).

    Args:
        results: Threshold tests in chronological order.
        session_labels: X-axis labels (e.g. dates); ``"Test N"`` by default.
        labels: Translation dict, or ``None``.
        title: Figure title; a default one is used when ``None``.
        figsize: Figure size in inches.

    Returns:
        Matplotlib figure; thresholds not detected are left out.

    Raises:
        ValueError: If ``results`` is empty or ``session_labels`` has another
            length.

    """
    if not results:
        raise ValueError("results must not be empty")
    n = len(results)
    if session_labels is not None and len(session_labels) != n:
        raise ValueError("session_labels must have one label per result")
    session_labels = session_labels or [f"Test {i + 1}" for i in range(n)]
    x = np.arange(n)
    fig, ax = plt.subplots(figsize=figsize)
    for name, color in (("vt1", _VT1_COLOR), ("vt2", _VT2_COLOR)):
        hr = [
            getattr(r, name).hr if getattr(r, name).detected else np.nan
            for r in results
        ]
        ax.plot(x, hr, "o-", color=color, label=lbl(labels, name, "HR" + name.upper()))
    ax.set_xticks(x)
    ax.set_xticklabels(session_labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel(lbl(labels, "mean_hr", "HR (bpm)"))
    ax.grid(alpha=0.3)

    units = {r.intensity_unit for r in results if r.intensity_unit}
    if len(units) == 1:
        ax_i = ax.twinx()
        for name, color in (("vt1", _VT1_COLOR), ("vt2", _VT2_COLOR)):
            val = [
                getattr(r, name).intensity if getattr(r, name).detected else np.nan
                for r in results
            ]
            ax_i.plot(x, val, "s--", color=color, alpha=0.5)
        ax_i.set_ylabel(units.pop())
    ax.legend(loc="upper left")
    ax.set_title(
        title or lbl(labels, "threshold_evolution_title", "Thresholds over time"),
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    return fig


# ── Helpers ───────────────────────────────────────────────────────────────────


def _check(result) -> None:
    """Raise ``TypeError`` unless ``result`` is a ``DFAThresholdsResult``."""
    if not isinstance(result, DFAThresholdsResult):
        raise TypeError(f"Expected DFAThresholdsResult, got {type(result).__name__}")


def _threshold_text(est, unit: str | None, labels: dict[str, str] | None) -> str:
    """Return the annotation of a threshold: name, heart rate, intensity."""
    name = lbl(labels, "vt1" if est.alpha == 0.75 else "vt2", "HRVT")
    text = f"{name} {est.hr:.0f} bpm"
    if unit and np.isfinite(est.intensity):
        text += f" · {est.intensity:.0f} {unit}"
    return text
