"""Visualisation of the Lamberts submaximal cycle test (LSCT).

* :func:`plot_lsct_session` — heart rate and power during one test, with the
  three stages, their target heart rates and the recovery.
* :func:`plot_lsct_evolution` — power of stages 2 and 3 and HRR60 test after
  test, with the tests whose stage 3 target was not reached.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from cardiolab.labels import lbl
from cardiolab.protocols.lsct import HRR_SEC, RECOVERY_SEC, STAGES, LSCTResult

_STAGE_COLORS = ("#d6eaf8", "#fcf3cf", "#fadbd8")
_HR_COLOR = "#c0392b"
_POWER_COLOR = "#2c3e50"
_RECOVERY_COLOR = "#e8f8f5"
_GRAY = "#95a5a6"


def plot_lsct_session(
    time_sec: np.ndarray,
    heart_rate: np.ndarray,
    power: np.ndarray,
    result: LSCTResult,
    labels: dict[str, str] | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (12, 6),
) -> Figure:
    """Plot heart rate and power during one test.

    Args:
        time_sec: Sample times (s) — the series given to
            :func:`~cardiolab.protocols.lsct.lsct`.
        heart_rate: Heart rate (bpm).
        power: Power (W).
        result: The test analysed from these series.
        labels: Translation dict (``LABELS_EN`` / ``LABELS_FR``), or ``None``.
        title: Figure title; a default one is used when ``None``.
        figsize: Figure size in inches.

    Returns:
        Matplotlib figure with two panels sharing the time axis: heart rate
        with each stage's target, power with each stage's mean.

    Raises:
        TypeError: If ``result`` is not an ``LSCTResult``.
        ValueError: If the series differ in length.

    """
    if not isinstance(result, LSCTResult):
        raise TypeError(f"Expected LSCTResult, got {type(result).__name__}")
    t = np.asarray(time_sec, dtype=float)
    hr = np.asarray(heart_rate, dtype=float)
    pw = np.asarray(power, dtype=float)
    if not (len(t) == len(hr) == len(pw)):
        raise ValueError("time_sec, heart_rate and power must have the same length")

    end = result.start_sec + sum(d for _, d in STAGES)
    view = (t >= result.start_sec - 60) & (t <= end + RECOVERY_SEC + 30)
    t_min = (t - result.start_sec) / 60.0

    fig, (ax_hr, ax_pw) = plt.subplots(2, 1, figsize=figsize, sharex=True)
    t0 = 0.0
    for stage, (_, duration), color in zip(
        result.stages, STAGES, _STAGE_COLORS, strict=True
    ):
        t1 = t0 + duration / 60.0
        for ax in (ax_hr, ax_pw):
            ax.axvspan(t0, t1, color=color, alpha=0.7, lw=0)
        ax_hr.hlines(stage.target_hr, t0, t1, colors=_HR_COLOR, linestyles="--", lw=1)
        ax_hr.text(
            (t0 + t1) / 2,
            stage.target_hr + 2,
            f"{stage.target_pct:.0f} % · {stage.target_hr:.0f}",
            ha="center",
            fontsize=8,
            color=_HR_COLOR,
        )
        ax_pw.hlines(stage.mean_power, t0, t1, colors=_POWER_COLOR, lw=2)
        ax_pw.text(
            (t0 + t1) / 2,
            stage.mean_power + 5,
            f"{stage.mean_power:.0f} W",
            ha="center",
            fontsize=9,
            fontweight="bold",
        )
        t0 = t1
    for ax in (ax_hr, ax_pw):
        ax.axvspan(t0, t0 + RECOVERY_SEC / 60.0, color=_RECOVERY_COLOR, lw=0)

    ax_hr.plot(t_min[view], hr[view], color=_HR_COLOR, lw=1)
    ax_pw.plot(t_min[view], pw[view], color=_GRAY, lw=0.8)
    ax_hr.set_ylabel(lbl(labels, "mean_hr", "HR (bpm)"))
    ax_pw.set_ylabel(lbl(labels, "power", "Power (W)"))
    ax_pw.set_xlabel(lbl(labels, "lsct_time", "Time from the start of stage 1 (min)"))
    if np.isfinite(result.hrr_60):
        ax_hr.annotate(
            f"HRR60 {result.hrr_60:.0f} bpm",
            xy=(t0 + HRR_SEC / 60.0, float(np.nanmin(hr[view]))),
            fontsize=9,
            ha="right",
        )
    for ax in (ax_hr, ax_pw):
        ax.grid(alpha=0.3)
    ax_hr.set_title(
        title or lbl(labels, "lsct_title", "Lamberts submaximal cycle test"),
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    return fig


def plot_lsct_evolution(
    results: list[LSCTResult],
    session_labels: list[str] | None = None,
    labels: dict[str, str] | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (11, 5),
) -> Figure:
    """Plot the power of stages 2 and 3 and HRR60 test after test.

    Args:
        results: Tests in chronological order.
        session_labels: X-axis labels; the test dates (or ``"Test N"``) by
            default.
        labels: Translation dict, or ``None``.
        title: Figure title; a default one is used when ``None``.
        figsize: Figure size in inches.

    Returns:
        Matplotlib figure: power lines (left axis), HRR60 bars (right axis),
        a red cross where the stage 3 target was not reached.

    Raises:
        ValueError: If ``results`` is empty or ``session_labels`` has another
            length.

    """
    if not results:
        raise ValueError("results must not be empty")
    n = len(results)
    if session_labels is not None and len(session_labels) != n:
        raise ValueError("session_labels must have one label per result")
    session_labels = session_labels or [
        r.date or f"Test {i + 1}" for i, r in enumerate(results)
    ]
    x = np.arange(n)

    fig, ax = plt.subplots(figsize=figsize)
    ax_hrr = ax.twinx()
    hrr = [r.hrr_60 for r in results]
    ax_hrr.bar(x, hrr, width=0.5, color="#d5f5e3", zorder=0)
    ax_hrr.set_ylabel("HRR60 (bpm)")
    ax.set_zorder(ax_hrr.get_zorder() + 1)
    ax.patch.set_visible(False)

    for number, style in ((2, "o-"), (3, "s-")):
        ax.plot(
            x,
            [r.stage(number).mean_power for r in results],
            style,
            color=_POWER_COLOR if number == 3 else _GRAY,
            label=lbl(labels, f"lsct_stage{number}_power", f"Stage {number} power (W)"),
        )
    missed = [i for i, r in enumerate(results) if not r.stage(3).target_reached]
    if missed:
        ax.plot(
            x[missed],
            [results[i].stage(3).mean_power for i in missed],
            "x",
            color=_HR_COLOR,
            ms=12,
            mew=2,
            label=lbl(labels, "lsct_target_missed", "Stage 3 target not reached"),
        )
    ax.set_xticks(x)
    ax.set_xticklabels(session_labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel(lbl(labels, "power", "Power (W)"))
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title(
        title or lbl(labels, "lsct_evolution_title", "LSCT — power and recovery"),
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    return fig
