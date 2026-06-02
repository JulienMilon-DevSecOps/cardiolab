"""Visualisation helpers for resting HRV session histories."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from cardiolab.labels import lbl
from cardiolab.protocols.resting import HRVFeatures

# ── Colour palette ────────────────────────────────────────────────────────────

_RMSSD_COLOR = "#2980b9"
_ROLLING_COLOR = "#e67e22"
_SCORE_COLOR = "#27ae60"
_DARK = "#2c3e50"
_GRAY = "#95a5a6"

# ── Readiness score threshold bands ──────────────────────────────────────────
# Colours and bounds used consistently across all score visualisations.

_SCORE_ZONES = [
    (80, 100, "#d5f5e3", "Very good"),
    (60, 80, "#fef9e7", "Normal"),
    (40, 60, "#fdebd0", "Moderate fatigue"),
    (0, 40, "#fadbd8", "Fatigued"),
]


# ── Public functions ──────────────────────────────────────────────────────────


def plot_resting_evolution(
    features_list: list[HRVFeatures],
    scores: list[float],
    session_labels: list[str] | None = None,
    labels: dict[str, str] | None = None,
    title: str = "RMSSD and Readiness Score Evolution",
    figsize: tuple[float, float] = (12, 7),
) -> Figure:
    """Plot RMSSD and readiness score across resting sessions.

    Returns a single :class:`~matplotlib.figure.Figure` with two vertically
    stacked panels:

    * **Top** — RMSSD (ms) over sessions, with the overall mean as a dashed
      reference line.
    * **Bottom** — Readiness score (0–100) with coloured threshold bands.

    Args:
        features_list: List of :class:`~cardiolab.protocols.resting.HRVFeatures`
            in chronological order.
        scores: Readiness score (0–100) for each session.  Must have the same
            length as ``features_list``.
        session_labels: X-axis session labels. Falls back to date attributes
            or ``'Session N'`` when ``None``.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Overall figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``features_list`` is not a list or contains non-HRVFeatures
            elements.
        TypeError: If ``scores`` is not a list.
        ValueError: If ``features_list`` is empty.
        ValueError: If ``scores`` and ``features_list`` have different lengths.
        ValueError: If ``labels`` is provided with a mismatched length.

    """
    _validate_features_list(features_list)
    if not isinstance(scores, list):
        raise TypeError(f"scores must be a list, got {type(scores).__name__}")
    if len(scores) != len(features_list):
        raise ValueError(
            f"scores length ({len(scores)}) must match features_list length "
            f"({len(features_list)})"
        )
    if session_labels is not None and len(session_labels) != len(features_list):
        raise ValueError(
            f"session_labels length ({len(session_labels)}) must match features_list length "
            f"({len(features_list)})"
        )

    n = len(features_list)
    session_labels = session_labels or _default_labels(features_list)
    x = np.arange(n)
    rmssd = np.array([f.rmssd for f in features_list])
    scores_arr = np.array(scores, dtype=float)

    fig, (ax_rmssd, ax_score) = plt.subplots(2, 1, figsize=figsize, sharex=True)

    # ── Top: RMSSD ────────────────────────────────────────────────────────────
    ax_rmssd.plot(
        x,
        rmssd,
        color=_RMSSD_COLOR,
        linewidth=1.8,
        marker="o",
        markersize=5,
        label="RMSSD",
    )
    mean_rmssd = float(np.mean(rmssd))
    ax_rmssd.axhline(
        mean_rmssd,
        color=_GRAY,
        linewidth=0.9,
        linestyle="--",
        alpha=0.8,
        label=f"Mean {mean_rmssd:.1f} ms",
    )
    ax_rmssd.set_ylabel(lbl(labels, "rmssd", "RMSSD (ms)"), fontsize=10)
    ax_rmssd.legend(loc="upper left", fontsize=8)
    ax_rmssd.grid(alpha=0.20, linestyle=":")

    # ── Bottom: readiness score ───────────────────────────────────────────────
    _draw_score_bands(ax_score)
    ax_score.plot(
        x,
        scores_arr,
        color=_SCORE_COLOR,
        linewidth=1.8,
        marker="o",
        markersize=5,
        zorder=4,
    )
    ax_score.set_ylim(0, 105)
    ax_score.set_ylabel(lbl(labels, "score", "Readiness score"), fontsize=10)
    ax_score.set_xticks(x)
    ax_score.set_xticklabels(session_labels, rotation=40, ha="right", fontsize=9)
    ax_score.grid(alpha=0.20, linestyle=":", axis="y")

    fig.suptitle(title, fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()
    return fig


def plot_resting_evolution_rolling(
    features_list: list[HRVFeatures],
    scores: list[float],
    rolling_rmssd: list[float | None],
    session_labels: list[str] | None = None,
    labels: dict[str, str] | None = None,
    title: str = "RMSSD Evolution — with Rolling Median",
    figsize: tuple[float, float] = (12, 7),
) -> Figure:
    """Plot RMSSD with its rolling median and readiness score across sessions.

    Identical layout to :func:`plot_resting_evolution` but adds an orange
    dashed line on the top panel showing the rolling RMSSD median.  The
    rolling median smooths day-to-day noise and reveals longer-term trends.

    Args:
        features_list: List of :class:`~cardiolab.protocols.resting.HRVFeatures`
            in chronological order.
        scores: Readiness score (0–100) per session.
        rolling_rmssd: Rolling RMSSD median per session.  A ``None`` value
            (e.g. for the first session when no prior baseline exists) is
            plotted as a gap.  Must have the same length as ``features_list``.
        session_labels: X-axis session labels. Falls back to date attributes
            or ``'Session N'`` when ``None``.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Overall figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``features_list`` is not a list or contains non-HRVFeatures
            elements.
        TypeError: If ``scores`` or ``rolling_rmssd`` is not a list.
        ValueError: If ``features_list`` is empty.
        ValueError: If ``scores``, ``rolling_rmssd``, or ``labels`` have a
            length that differs from ``features_list``.

    """
    _validate_features_list(features_list)
    for param_name, param_val in (("scores", scores), ("rolling_rmssd", rolling_rmssd)):
        if not isinstance(param_val, list):
            raise TypeError(
                f"{param_name} must be a list, got {type(param_val).__name__}"
            )
        if len(param_val) != len(features_list):
            raise ValueError(
                f"{param_name} length ({len(param_val)}) must match "
                f"features_list length ({len(features_list)})"
            )
    if session_labels is not None and len(session_labels) != len(features_list):
        raise ValueError(
            f"session_labels length ({len(session_labels)}) must match features_list length "
            f"({len(features_list)})"
        )

    n = len(features_list)
    session_labels = session_labels or _default_labels(features_list)
    x = np.arange(n)
    rmssd = np.array([f.rmssd for f in features_list])
    scores_arr = np.array(scores, dtype=float)

    # Build rolling array — replace None with NaN so matplotlib draws gaps
    rolling_arr = np.array(
        [v if v is not None else float("nan") for v in rolling_rmssd],
        dtype=float,
    )

    fig, (ax_rmssd, ax_score) = plt.subplots(2, 1, figsize=figsize, sharex=True)

    # ── Top: RMSSD + rolling median ───────────────────────────────────────────
    ax_rmssd.plot(
        x,
        rmssd,
        color=_RMSSD_COLOR,
        linewidth=1.8,
        marker="o",
        markersize=5,
        label="RMSSD",
        zorder=4,
    )
    ax_rmssd.plot(
        x,
        rolling_arr,
        color=_ROLLING_COLOR,
        linewidth=1.6,
        linestyle="--",
        marker="s",
        markersize=4,
        label="Rolling median",
        zorder=3,
    )
    ax_rmssd.set_ylabel(lbl(labels, "rmssd", "RMSSD (ms)"), fontsize=10)
    ax_rmssd.legend(loc="upper left", fontsize=8)
    ax_rmssd.grid(alpha=0.20, linestyle=":")

    # ── Bottom: readiness score ───────────────────────────────────────────────
    _draw_score_bands(ax_score)
    ax_score.plot(
        x,
        scores_arr,
        color=_SCORE_COLOR,
        linewidth=1.8,
        marker="o",
        markersize=5,
        zorder=4,
    )
    ax_score.set_ylim(0, 105)
    ax_score.set_ylabel(lbl(labels, "score", "Readiness score"), fontsize=10)
    ax_score.set_xticks(x)
    ax_score.set_xticklabels(session_labels, rotation=40, ha="right", fontsize=9)
    ax_score.grid(alpha=0.20, linestyle=":", axis="y")

    fig.suptitle(title, fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()
    return fig


# ── Private helpers ───────────────────────────────────────────────────────────


def _validate_features_list(features_list: list[HRVFeatures]) -> None:
    """Validate that ``features_list`` is a non-empty list of HRVFeatures."""
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
    """Return date strings from features or fallback ``'Session N'`` labels."""
    return [
        str(f.date) if f.date else f"Session {i + 1}"
        for i, f in enumerate(features_list)
    ]


def _draw_score_bands(ax: plt.Axes) -> None:
    """Fill horizontal coloured bands on a readiness score axis."""
    for low, high, color, _ in _SCORE_ZONES:
        ax.axhspan(low, high, color=color, alpha=0.45, zorder=0)
    for threshold in (40, 60, 80):
        ax.axhline(threshold, color=_GRAY, linewidth=0.6, linestyle=":", alpha=0.7)
